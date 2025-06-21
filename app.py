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
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext, load_index_from_storage
from llama_index.llms.ollama import Ollama
from llama_index.readers.file import PDFReader, DocxReader, ImageReader
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
import tempfile
from langdetect import detect

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
    # Process user messages and get AI responses from LlamaIndex (document Q&A) using Ollama
    data = request.json
    user_message = data.get('message', '')
    if not user_message:
        return jsonify({'error': 'No message provided'}), 400

    # Detect language of the user message
    try:
        user_lang = detect(user_message)
    except Exception:
        user_lang = 'en'
    lang_map = {'en': 'English', 'ar': 'Arabic'}
    lang_name = lang_map.get(user_lang, user_lang)
    lang_instruction = f"Please answer in {lang_name} regardless of the document language."

    # Get or initialize chat history in session
    chat_history = session.get('chat_history', [])
    if not chat_history:
        # Add system prompt only at the start
        chat_history.append({
            "role": "system",
            "content": "Your name is Proto AI. You are a helpful, friendly AI assistant, but users should see you as 'Proto AI'. You have a slightly playful and enthusiastic personality. You're knowledgeable, curious, and always willing to help."
        })
    # Add language instruction as a system message for this turn
    chat_history.append({"role": "system", "content": lang_instruction})
    # Add user message
    chat_history.append({"role": "user", "content": user_message})

    # Use LlamaIndex to answer the user's question based on indexed documents
    index = get_llama_index()
    if not index:
        return jsonify({'error': 'No documents indexed yet'}), 400
    llm = Ollama(model='gemma2:2b')
    query_engine = index.as_query_engine(llm=llm, embed_model=embed_model)
    try:
        answer = query_engine.query(user_message)
        # Add assistant reply to chat history
        chat_history.append({"role": "assistant", "content": str(answer)})
        session['chat_history'] = chat_history
        # Output the prompt to a file for inspection, with more details
        with open('last_prompt.json', 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': __import__('datetime').datetime.now().isoformat(),
                'chat_history': chat_history,
                'user_message': user_message,
                'detected_language': lang_name
            }, f, ensure_ascii=False, indent=2)
        return jsonify({'message': str(answer)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- LlamaIndex Setup ---
# Preload admin document (e.g. YouLearnt_logic.docx) at startup
ADMIN_DOC_PATH = 'YouLearnt_logic.docx'
llama_index = None
llama_docs = []
llama_index_storage_dir = './llamaindex_storage'

# Use a local HuggingFace embedding model
embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")

if os.path.exists(ADMIN_DOC_PATH):
    # Load admin doc at startup
    llama_docs = DocxReader().load_data(ADMIN_DOC_PATH)  # FIX: do not wrap in list
    # Build index and persist
    index = VectorStoreIndex.from_documents(llama_docs, show_progress=True, embed_model=embed_model)
    index.storage_context.persist(persist_dir=llama_index_storage_dir)
    llama_index = index
else:
    llama_index = None

# Helper: load or reload index from storage
def get_llama_index():
    global llama_index
    if llama_index is not None:
        return llama_index
    if os.path.exists(llama_index_storage_dir):
        storage_context = StorageContext.from_defaults(persist_dir=llama_index_storage_dir)
        llama_index = load_index_from_storage(storage_context, embed_model=embed_model)
        return llama_index
    return None

# --- File Upload Endpoint ---
from werkzeug.utils import secure_filename
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt', 'png', 'jpg', 'jpeg'}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        temp_path = os.path.join(tempfile.gettempdir(), filename)
        file.save(temp_path)
        # Load and index the file
        ext = filename.rsplit('.', 1)[1].lower()
        if ext == 'pdf':
            doc = PDFReader().load_data(temp_path)
        elif ext == 'docx':
            doc = DocxReader().load_data(temp_path)
        elif ext in {'png', 'jpg', 'jpeg'}:
            doc = ImageReader().load_data(temp_path)
        else:
            with open(temp_path, 'r', encoding='utf-8') as f:
                doc = [f.read()]
        # Add to index (in-memory for now, or you can persist)
        global llama_index
        if llama_index is not None:
            llama_index.insert_documents(doc)
        else:
            llama_index = VectorStoreIndex.from_documents(doc, embed_model=embed_model)
        return jsonify({'success': True, 'filename': filename})
    return jsonify({'error': 'File type not allowed'}), 400

# --- LlamaIndex Q&A Endpoint ---
@app.route('/api/llama_query', methods=['POST'])
def llama_query():
    data = request.json
    question = data.get('question', '')
    if not question:
        return jsonify({'error': 'No question provided'}), 400
    index = get_llama_index()
    if not index:
        return jsonify({'error': 'No documents indexed yet'}), 400
    llm = Ollama(model='gemma2:2b')
    query_engine = index.as_query_engine(llm=llm, embed_model=embed_model)
    answer = query_engine.query(question)
    return jsonify({'answer': str(answer)})

if __name__ == '__main__':
    app.run(debug=True)