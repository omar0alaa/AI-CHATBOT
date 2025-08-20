import time
from flask import Flask
import os
from dotenv import load_dotenv
import nltk
from flask_session import Session
from services.logging_service import setup_logger
from services.database_service import init_db

# Import route blueprints
from routes.main_routes import main_bp
from routes.admin_routes import admin_bp
from routes.api_routes import api_bp

# Load environment variables
load_dotenv()

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

# Initialize logger
setup_logger()

# Initialize database
init_db()

# Register blueprints
app.register_blueprint(main_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(api_bp)

if __name__ == '__main__':
    app.run(debug=True)