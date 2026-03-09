import time
from pathlib import Path
from flask import Flask, send_from_directory, abort
from flask_cors import CORS
import os
from dotenv import load_dotenv
import nltk
from flask_session import Session
from services.logging_service import setup_logger
from services.database_service import init_db

# Load environment variables from the project root explicitly (handles service cwd differences)
load_dotenv(dotenv_path=Path(__file__).resolve().parent / '.env')

# Import route blueprints (after env is loaded so config picks up .env values)
from routes.main_routes import main_bp
from routes.admin_routes import admin_bp
from routes.api_routes import api_bp

# Ensure nltk punkt tokenizer is available
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

# Initialize Flask app
app = Flask(__name__, static_folder='static')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'protoai-secret-key')
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Enable CORS for all routes
CORS(app, supports_credentials=True)

# Initialize logger
setup_logger()

# Initialize database
init_db()

# Register blueprints
app.register_blueprint(main_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(api_bp)

# Serve uploaded KB media files
UPLOADS_DIR = Path(__file__).resolve().parent / 'uploads' / 'kb'

@app.route('/uploads/kb/<path:filepath>')
def serve_kb_upload(filepath):
    full_path = (UPLOADS_DIR / filepath).resolve()
    # Prevent path traversal
    if not str(full_path).startswith(str(UPLOADS_DIR.resolve())):
        abort(403)
    return send_from_directory(str(UPLOADS_DIR), filepath)

if __name__ == '__main__':
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('PORT', os.getenv('FLASK_PORT', '5000')))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host=host, port=port, debug=debug)