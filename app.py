from flask import Flask, request, jsonify, render_template, session
import requests
import os
from dotenv import load_dotenv
import json
import nltk
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer
from flask_session import Session

# Load environment variables
load_dotenv()

# Ensure nltk punkt tokenizer is available
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')
try:
    nltk.data.find('tokenizers/punkt_tab/english.pickle')
except LookupError:
    try:
        nltk.download('punkt_tab')
    except Exception:
        pass

# Initialize Flask app
app = Flask(__name__, static_folder='static')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'protoai-secret-key')

# Configure server-side session
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = './flask_session/'
app.config['SESSION_PERMANENT'] = False
Session(app)

# OLLAMA API endpoint (default for local server)
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/chat")

@app.route('/')
def index():
    #Render the chat interface.
    return render_template('index.html')

@app.route('/widget')
def widget():
    #Render the widget chat interface.
    return render_template('widget.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    #Process user messages and get AI responses from Ollama, sending system prompt only at start of session.
    data = request.json
    user_message = data.get('message', '')
    
    if not user_message:
        return jsonify({'error': 'No message provided'}), 400
    
    # Get or initialize chat history in session
    chat_history = session.get('chat_history', [])
    if not chat_history:
        # Add system prompt only at the start
        chat_history.append({
            "role": "system",
            "content": "Your name is Proto AI. You are a helpful, friendly AI assistant, but users should see you as 'Proto AI'. You have a slightly playful and enthusiastic personality. You're knowledgeable, curious, and always willing to help."
        })
    # Add user message
    chat_history.append({"role": "user", "content": user_message})
    
    # Summarize all messages before the last MAX_HISTORY into a single summary message, but skip system messages
    MAX_HISTORY = 5
    summarizer = LsaSummarizer()
    # Only keep the very first system message at the start
    first_system = next((msg for msg in chat_history if msg['role'] == 'system'), None)
    summarized_history = [first_system] if first_system else []
    # Collect messages to summarize (exclude all system messages)
    to_summarize = [msg for msg in chat_history[1:-(MAX_HISTORY)] if msg['role'] != 'system'] if len(chat_history) > (MAX_HISTORY + 1) else []
    if to_summarize:
        all_text = '\n'.join([msg['content'] for msg in to_summarize if msg['content'].strip() and not msg['content'].strip().lower().startswith('summary:')])
        if all_text.strip():
            parser = PlaintextParser.from_string(all_text, Tokenizer("english"))
            summary_sentences = summarizer(parser.document, 5)
            summary = ' '.join(str(sentence) for sentence in summary_sentences)
            if not summary.strip() or summary.strip().lower().startswith('summary:'):
                summary = all_text
            summarized_history.append({"role": "system", "content": f"Summary of earlier conversation: {summary}"})
            
    # Summarize the next (older) messages one by one, except the last MAX_HISTORY
    for msg in chat_history[-MAX_HISTORY:-1]:
        content = msg['content']
        if msg['role'] == 'system':
            continue  # skip any system messages except the first
        elif content.strip() and not content.strip().lower().startswith('summary:'):
            parser = PlaintextParser.from_string(content, Tokenizer("english"))
            summary_sentences = summarizer(parser.document, 3)
            summary = ' '.join(str(sentence) for sentence in summary_sentences)
            if not summary.strip() or summary.strip().lower().startswith('summary:'):
                summarized_history.append({"role": msg['role'], "content": content})
            else:
                summarized_history.append({"role": msg['role'], "content": f"Summary: {summary}"})
        else:
            summarized_history.append({"role": msg['role'], "content": content})
    
    # Add the very last message in full (not summarized)
    if len(chat_history) > 1 and chat_history[-1]['role'] != 'system':
        summarized_history.append(chat_history[-1])
    prompt_history = summarized_history
    try:
        payload = {
            "model": "gemma2:2b",
            "messages": prompt_history
        }
        response = requests.post(OLLAMA_API_URL, json=payload, stream=True)
        response.raise_for_status()
        response_text = ''
        for line in response.iter_lines(decode_unicode=True):
            if line:
                try:
                    response_data = json.loads(line)
                    if 'message' in response_data and 'content' in response_data['message']:
                        response_text += response_data['message']['content']
                except Exception:
                    continue
        if not response_text:
            # fallback for non-streaming response
            response_data = response.json()
            response_text = response_data['message']['content']
        # Add assistant reply to chat history
        chat_history.append({"role": "assistant", "content": response_text})
        session['chat_history'] = chat_history
        
        #----------------------------------------REMOVE IN PRODUCTION --------------------------------------------------------------
        # Output the prompt to a file for inspection, with more details 
        with open('last_prompt.json', 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': __import__('datetime').datetime.now().isoformat(),
                'chat_history': chat_history,
                'payload': payload,
                'user_message': user_message,
                'summarized_history': summarized_history if 'summarized_history' in locals() else None
            }, f, ensure_ascii=False, indent=2)
        #---------------------------------------------------------------------------------------------------------------------------
        return jsonify({'message': response_text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)