# API routes - Chat functionality and AI interactions
from flask import Blueprint, request, jsonify, session
from services.chat_service import chat_service

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/chat', methods=['POST'])
def chat():
    # Main chat endpoint - processes user messages and returns AI responses
    try:
        # Parse request
        data = request.json
        user_message = data.get('message', '')
        ui_lang = data.get('lang')
        
        if not user_message:
            return jsonify({'error': 'No message provided'}), 400
        
        # Get chat history from session
        if 'chat_history' not in session:
            session['chat_history'] = []
        chat_history = session['chat_history']
        
        # Process message using chat service
        processed_answer, updated_history = chat_service.process_message(
            user_message, ui_lang, chat_history
        )
        
        # Update session
        session['chat_history'] = updated_history
        
        # Return response
        return jsonify({'message': str(processed_answer)})
        
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500
