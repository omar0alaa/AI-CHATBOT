# Main application routes - Landing pages and static content

from flask import render_template
from flask import Blueprint

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    # Main chatbot interface
    return render_template('index.html')

@main_bp.route('/widget')
def widget():
    # Widget interface for embedding
    return render_template('widget.html')
