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
from logger import log_debug, log_info, log_warning, log_error, setup_logger, update_logger

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

# Initialize logger
setup_logger()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/widget')
def widget():
    return render_template('widget.html')

@app.route('/admin/debug/toggle', methods=['POST'])
def toggle_debug():
    """Toggle debug mode for showing detailed error info in chat"""
    current_debug = os.environ.get("SHOW_DEBUG", "false").lower() == "true"
    new_debug = not current_debug
    os.environ["SHOW_DEBUG"] = "true" if new_debug else "false"
    
    # Reinitialize logger with new debug setting
    setup_logger()
    
    if new_debug:
        log_info("Debug mode enabled - logging to file started")
    else:
        log_info("Debug mode disabled - file logging stopped")
    
    return jsonify({
        'debug_enabled': new_debug,
        'message': f"Debug mode {'enabled' if new_debug else 'disabled'}"
    })

@app.route('/admin/debug/status', methods=['GET'])
def debug_status():
    """Get current debug status"""
    current_debug = os.environ.get("SHOW_DEBUG", "false").lower() == "true"
    return jsonify({'debug_enabled': current_debug})


DB_PATH = 'youlearnt_bank.db'

# --- Admin API endpoints for DB CRUD ---
@app.route('/admin/db')
def admin_db_page():
    return render_template('admin_db.html')

@app.route('/admin/api/bank', methods=['GET'])
def admin_get_bank():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT ID, question_EN, question_AR, answer_EN, answer_AR, created_date FROM youlearnt_bank ORDER BY ID ASC')
    rows = [dict(ID=row[0], question_EN=row[1], question_AR=row[2], answer_EN=row[3], answer_AR=row[4], created_date=row[5]) for row in c.fetchall()]
    conn.close()
    return jsonify(rows)

@app.route('/admin/api/bank', methods=['POST'])
def admin_add_bank():
    data = request.get_json()
    question_en = data.get('question_EN', '').strip()
    question_ar = data.get('question_AR', '').strip()
    answer_en = data.get('answer_EN', '').strip()
    answer_ar = data.get('answer_AR', '').strip()
    if not question_en or not question_ar or not answer_en or not answer_ar:
        return jsonify({'error': 'Missing required fields (question_EN, question_AR, answer_EN, answer_AR)'}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO youlearnt_bank (question_EN, question_AR, answer_EN, answer_AR) VALUES (?, ?, ?, ?)', 
              (question_en, question_ar, answer_en, answer_ar))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/admin/api/bank/edit/<int:qa_id>', methods=['PUT'])
def admin_edit_bank(qa_id):
    data = request.get_json()
    question_en = data.get('question_EN', '').strip()
    question_ar = data.get('question_AR', '').strip()
    answer_en = data.get('answer_EN', '').strip()
    answer_ar = data.get('answer_AR', '').strip()
    if not question_en or not question_ar or not answer_en or not answer_ar:
        return jsonify({'error': 'Missing required fields (question_EN, question_AR, answer_EN, answer_AR)'}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE youlearnt_bank SET question_EN = ?, question_AR = ?, answer_EN = ?, answer_AR = ? WHERE ID = ?', 
              (question_en, question_ar, answer_en, answer_ar, qa_id))
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
        question_EN TEXT NOT NULL,
        question_AR TEXT NOT NULL,
        answer_EN TEXT NOT NULL,
        answer_AR TEXT NOT NULL,
        created_date TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

init_db()

def get_answer_from_db(user_message, user_lang='en'):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT question_EN, question_AR, answer_EN, answer_AR FROM youlearnt_bank')
    rows = c.fetchall()
    conn.close()
    
    # Find top 3 most similar Q&A pairs
    scored = []
    for q_en, q_ar, a_en, a_ar in rows:
        # Compare with both English and Arabic questions
        score_en = SequenceMatcher(None, user_message.lower(), q_en.lower()).ratio()
        score_ar = SequenceMatcher(None, user_message.lower(), q_ar.lower()).ratio()
        # Use the higher score
        score = max(score_en, score_ar)
        # Return answer in user's language
        answer = a_ar if user_lang == 'ar' else a_en
        scored.append((score, q_en, answer))
    
    scored.sort(reverse=True)
    # Return top 3 answers above threshold
    top_contexts = [a for s, q, a in scored[:3] if s >= 0.5]
    return top_contexts

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message', '')
    ui_lang = data.get('lang')
    
    log_info("========== NEW CHAT REQUEST ==========")
    log_debug(f"Received message: {user_message}")
    log_debug(f"UI Language: {ui_lang}")
    
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
            log_debug(f"Auto-detected language: {user_lang}")
        except Exception as e:
            log_error(f"Language detection failed: {e}")
            user_lang = 'en'
    
    log_debug(f"Final language: {user_lang}")
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

    # Ollama configuration
    ollama_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/generate")
    model_name = os.getenv("OLLAMA_MODEL", "gemma3:1b")
    
    log_debug(f"Ollama URL: {ollama_url}")
    log_debug(f"Model: {model_name}")

    # --- Knowledge base retrieval ---
    try:
        contexts = get_answer_from_db(user_message, user_lang)
        log_debug(f"Found {len(contexts)} contexts from database")
        if contexts:
            for i, ctx in enumerate(contexts):
                log_debug(f"Context {i+1}: {ctx[:100]}...")
        else:
            log_debug(f"No relevant contexts found for message: {user_message}")
    except Exception as e:
        log_error(f"Database query failed: {e}")
        contexts = []
    
    fallback_message = get_fallback_message(user_lang)

    if not contexts:
        log_debug("Using persona fallback prompt (no database match)")
        # Persona-only prompt, no knowledge base
        from persona import get_persona_fallback_prompt
        prompt = get_persona_fallback_prompt(user_lang, user_message)
    else:
        log_debug(f"Using knowledge base prompt with {len(contexts)} contexts")
        # Build context string for Ollama
        context_str = "\n".join([f"- {c}" for c in contexts])
        prompt = f"{lang_instruction}\n\nKnowledge Base:\n{context_str}\n\nUser Question: {user_message}\n\nAnswer strictly using the above knowledge base."
    
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False
    }
    
    log_debug(f"Sending request to Ollama at {ollama_url}...")
    log_debug(f"Prompt length: {len(payload['prompt'])} characters")
    
    answer_original = fallback_message
    
    try:
        import time
        start_time = time.time()
        
        # Test Ollama connectivity first
        try:
            test_resp = requests.get(ollama_url.replace('/api/generate', '/api/tags'), timeout=5)
            log_debug(f"Ollama connectivity test: {test_resp.status_code}")
        except Exception as conn_e:
            log_error(f"Ollama connectivity test failed: {conn_e}")
            log_warning(f"Make sure Ollama is running: ollama serve")
            answer = fallback_message
            raise Exception(f"Ollama not accessible: {conn_e}")
        
        resp = requests.post(ollama_url, json=payload, timeout=120)
        end_time = time.time()
        
        log_debug(f"Response time: {end_time - start_time:.2f} seconds")
        log_debug(f"Response status: {resp.status_code}")
        
        if resp.status_code != 200:
            log_error(f"Ollama error {resp.status_code}: {resp.text}")
            answer = fallback_message
        else:
            try:
                result = resp.json()
                log_debug(f"Response keys: {list(result.keys())}")
                
                raw_response = result.get("response", "")
                if not raw_response or raw_response.strip() == "":
                    log_error(f"Empty response from Ollama")
                    answer = fallback_message
                else:
                    answer = raw_response
                    answer_original = answer
                    log_debug(f"Got valid response ({len(answer)} chars)")
                    
            except json.JSONDecodeError as json_e:
                log_error(f"JSON parse error: {json_e}")
                log_debug(f"Raw response: {resp.text}")
                answer = fallback_message
                
    except requests.exceptions.Timeout:
        log_error(f"Ollama request timed out after 120 seconds")
        answer = fallback_message
    except requests.exceptions.ConnectionError as e:
        log_error(f"Cannot connect to Ollama: {e}")
        log_warning(f"Is Ollama running? Try: ollama serve")
        answer = fallback_message
    except requests.exceptions.RequestException as e:
        log_error(f"Request failed: {e}")
        answer = fallback_message
    except Exception as e:
        log_error(f"Unexpected error: {e}")
        answer = fallback_message

    # Post-processing filter for forbidden phrases
    log_debug(f"Starting post-processing...")
    try:
        from rewrite import rewrite_to_compliant
        log_debug(f"Rewrite module available")
    except ImportError:
        log_warning(f"Rewrite module not available")
        def rewrite_to_compliant(a, b, c, d):
            return a
    
    try:
        if contains_forbidden_phrase(answer, user_lang):
            log_debug(f"Forbidden phrase detected, rewriting...")
            rewritten = rewrite_to_compliant(answer, user_message, user_lang, fallback_message)
            if not rewritten or rewritten == answer:
                log_warning(f"Rewrite failed, using fallback")
                answer = fallback_message
            else:
                log_debug(f"Rewrite successful")
                answer = rewritten
        else:
            log_debug(f"No forbidden phrases detected")
    except Exception as pp_e:
        log_error(f"Post-processing failed: {pp_e}")
        # Don't change the answer if post-processing fails
    
    processed_answer = str(answer)
    log_debug(f"Final answer: {len(processed_answer)} characters")
    
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