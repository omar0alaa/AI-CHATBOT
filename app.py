import time
from flask import Flask, request, jsonify, render_template, session
import requests
import os
from dotenv import load_dotenv
import json
import sqlite3
import nltk
from flask_session import Session
from langdetect import detect
from persona import get_persona_prompt
import re
from difflib import SequenceMatcher
from postprocess import contains_forbidden_phrase, get_fallback_message

# Load environment variables
load_dotenv()

# Ensure nltk punkt tokenizer is available
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')


app = Flask(__name__, static_folder='static')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'protoai-secret-key')
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/widget')
def widget():
    return render_template('widget.html')


DB_PATH = 'youlearnt_bank.db'

# --- Admin API endpoints for DB CRUD ---
@app.route('/admin/db')
def admin_db_page():
    return render_template('admin_db.html')

@app.route('/admin/api/bank', methods=['GET'])
def admin_get_bank():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT ID, question, answer FROM youlearnt_bank ORDER BY ID ASC')
    rows = [dict(ID=row[0], question=row[1], answer=row[2]) for row in c.fetchall()]
    conn.close()
    return jsonify(rows)

@app.route('/admin/api/bank', methods=['POST'])
def admin_add_bank():
    data = request.get_json()
    question = data.get('question', '').strip()
    answer = data.get('answer', '').strip()
    if not question or not answer:
        return jsonify({'error': 'Missing question or answer'}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO youlearnt_bank (question, answer) VALUES (?, ?)', (question, answer))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/admin/api/bank/edit/<int:qa_id>', methods=['PUT'])
def admin_edit_bank(qa_id):
    data = request.get_json()
    question = data.get('question', '').strip()
    answer = data.get('answer', '').strip()
    if not question or not answer:
        return jsonify({'error': 'Missing question or answer'}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE youlearnt_bank SET question = ?, answer = ? WHERE ID = ?', (question, answer, qa_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/admin/api/bank/delete/<int:qa_id>', methods=['DELETE'])
def admin_delete_bank(qa_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM youlearnt_bank WHERE ID = ?', (qa_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS youlearnt_bank (
        ID INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT NOT NULL,
        answer TEXT NOT NULL
    )''')
    conn.commit()
    conn.close()

init_db()

def get_answer_from_db(user_message):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT question, answer FROM youlearnt_bank')
    rows = c.fetchall()
    conn.close()
    # Find top 3 most similar Q&A pairs
    scored = []
    for q, a in rows:
        score = SequenceMatcher(None, user_message.lower(), q.lower()).ratio()
        scored.append((score, q, a))
    scored.sort(reverse=True)
    # Return top 3 answers above threshold
    top_contexts = [a for s, q, a in scored[:3] if s >= 0.5]
    return top_contexts

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message', '')
    ui_lang = data.get('lang')
    if not user_message:
        return jsonify({'error': 'No message provided'}), 400

    # Language detection and persona
    if ui_lang == 'ar':
        user_lang = 'ar'
    elif ui_lang == 'en':
        user_lang = 'en'
    else:
        try:
            user_lang = detect(user_message)
        except Exception:
            user_lang = 'en'
    lang_instruction = get_persona_prompt(user_lang)
    if user_lang == 'ar':
        user_message = user_message

    # Flask session for chat history
    if 'chat_history' not in session:
        session['chat_history'] = []
    chat_history = session['chat_history']
    # Always keep persona/system prompt at the start
    chat_history = [msg for msg in chat_history if msg['role'] != 'system']
    chat_history.insert(0, {"role": "system", "content": lang_instruction})
    chat_history.append({"role": "user", "content": user_message})
    session['chat_history'] = chat_history

    # --- Knowledge base retrieval ---
    contexts = get_answer_from_db(user_message)
    fallback_message = get_fallback_message(user_lang)

    ollama_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/generate")
    model_name = os.getenv("OLLAMA_MODEL", "gemma3:1b")
    if not contexts:
        print(f"[DB] No relevant contexts found for: {user_message}")
        # Persona-only prompt, no knowledge base
        from persona import get_persona_fallback_prompt
        prompt = get_persona_fallback_prompt(user_lang, user_message)
    else:
        # Build context string for Ollama
        context_str = "\n".join([f"- {c}" for c in contexts])
        prompt = f"{lang_instruction}\n\nKnowledge Base:\n{context_str}\n\nUser Question: {user_message}\n\nAnswer strictly using the above knowledge base."
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False
    }
    try:
        resp = requests.post(ollama_url, json=payload, timeout=120)
        resp.raise_for_status()
        result = resp.json()
        answer = result.get("response", fallback_message)
    except Exception as e:
        answer = f"Error:\n{e}\n"

    # Post-processing filter for forbidden phrases
    answer_original = answer
    try:
        from rewrite import rewrite_to_compliant
    except ImportError:
        def rewrite_to_compliant(a, b, c, d):
            return a
    if contains_forbidden_phrase(answer, user_lang):
        rewritten = rewrite_to_compliant(answer, user_message, user_lang, fallback_message)
        if not rewritten or rewritten == answer:
            answer = fallback_message
        else:
            answer = rewritten
    processed_answer = str(answer)
    chat_history.append({"role": "assistant", "content": processed_answer})
    # Keep only the last 5 messages (excluding system prompt)
    system_msgs = [msg for msg in chat_history if msg['role'] == 'system']
    non_system_msgs = [msg for msg in chat_history if msg['role'] != 'system']
    chat_history = system_msgs + non_system_msgs[-5:]
    session['chat_history'] = chat_history
    with open('last_prompt.json', 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': __import__('datetime').datetime.now().isoformat(),
            'chat_history': chat_history,
            'user_message': user_message,
            'original_ai_response': answer_original,
            'postprocessed_response': processed_answer
        }, f, ensure_ascii=False, indent=2)
    return jsonify({'message': str(answer)})

if __name__ == '__main__':
    app.run(debug=True)