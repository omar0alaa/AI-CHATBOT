# Admin routes - Debug controls and database management

from flask import Blueprint, request, jsonify, render_template
from services.admin_service import admin_service
from services.database_service import database_service
from services.ai_config import ai_config

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# === Debug Management Routes ===

@admin_bp.route('/debug/toggle', methods=['POST'])
def toggle_debug():
    # Toggle debug mode for showing detailed error info in chat
    result = admin_service.toggle_debug_mode()
    return jsonify(result)

@admin_bp.route('/debug/status', methods=['GET'])
def debug_status():
    # Get current debug status
    result = admin_service.get_debug_status()
    return jsonify(result)

# === AI Configuration Routes ===

@admin_bp.route('/config', methods=['GET'])
def get_ai_config():
    # Get current AI configuration
    config = ai_config.get_config_summary()
    return jsonify(config)

@admin_bp.route('/config/similarity', methods=['POST'])
def update_similarity_threshold():
    # Update similarity threshold for knowledge base matching
    try:
        data = request.get_json()
        new_threshold = float(data.get('threshold', 0.7))
        
        if ai_config.update_similarity_threshold(new_threshold):
            return jsonify({
                'success': True, 
                'message': f'Similarity threshold updated to {new_threshold}',
                'new_threshold': new_threshold
            })
        else:
            return jsonify({
                'error': 'Invalid threshold value. Must be between 0.0 and 1.0'
            }), 400
            
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid threshold value provided'}), 400
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

# === Database Management Routes ===

@admin_bp.route('/db')
def admin_db_page():
    # Admin database management interface
    return render_template('admin_db.html')

@admin_bp.route('/api/bank', methods=['GET'])
def admin_get_bank():
    # Get all knowledge bank entries
    entries = database_service.get_all_entries()
    return jsonify(entries)

@admin_bp.route('/api/bank', methods=['POST'])
def admin_add_bank():
    # Add new knowledge bank entry
    try:
        data = request.get_json()
        question_en = data.get('question_EN', '').strip()
        question_ar = data.get('question_AR', '').strip()
        answer_en = data.get('answer_EN', '').strip()
        answer_ar = data.get('answer_AR', '').strip()
        
        if not question_en or not question_ar or not answer_en or not answer_ar:
            return jsonify({'error': 'Missing required fields (question_EN, question_AR, answer_EN, answer_AR)'}), 400
        
        success = database_service.add_entry(question_en, question_ar, answer_en, answer_ar)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Failed to add entry'}), 500
            
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@admin_bp.route('/api/bank/edit/<int:qa_id>', methods=['PUT'])
def admin_edit_bank(qa_id):
    # Edit existing knowledge bank entry
    try:
        data = request.get_json()
        question_en = data.get('question_EN', '').strip()
        question_ar = data.get('question_AR', '').strip()
        answer_en = data.get('answer_EN', '').strip()
        answer_ar = data.get('answer_AR', '').strip()
        
        if not question_en or not question_ar or not answer_en or not answer_ar:
            return jsonify({'error': 'Missing required fields (question_EN, question_AR, answer_EN, answer_AR)'}), 400
        
        success = database_service.update_entry(qa_id, question_en, question_ar, answer_en, answer_ar)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Failed to update entry'}), 500
            
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@admin_bp.route('/api/bank/delete/<int:qa_id>', methods=['DELETE'])
def admin_delete_bank(qa_id):
    # Delete knowledge bank entry
    try:
        success = database_service.delete_entry(qa_id)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Failed to delete entry'}), 500
            
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@admin_bp.route('/config/response-style', methods=['POST'])
def update_response_style():
    # Update response style (short, medium, long, detailed)
    try:
        data = request.get_json()
        style = data.get('style', 'medium').lower()
        
        if style == 'short':
            ai_config.OLLAMA_NUM_PREDICT = 256
            ai_config.OLLAMA_TEMPERATURE = 0.5
            ai_config.OLLAMA_TOP_P = 0.8
            message = "Response style set to SHORT - concise answers"
            
        elif style == 'medium':
            ai_config.OLLAMA_NUM_PREDICT = 512
            ai_config.OLLAMA_TEMPERATURE = 0.7
            ai_config.OLLAMA_TOP_P = 0.9
            message = "Response style set to MEDIUM - balanced answers"
            
        elif style == 'long':
            ai_config.OLLAMA_NUM_PREDICT = 1024
            ai_config.OLLAMA_TEMPERATURE = 0.8
            ai_config.OLLAMA_TOP_P = 0.95
            message = "Response style set to LONG - detailed answers"
            
        elif style == 'detailed':
            ai_config.OLLAMA_NUM_PREDICT = 1536
            ai_config.OLLAMA_TEMPERATURE = 0.9
            ai_config.OLLAMA_TOP_P = 0.98
            message = "Response style set to DETAILED - comprehensive answers"
            
        else:
            return jsonify({'error': 'Invalid style. Use: short, medium, long, or detailed'}), 400
        
        return jsonify({
            'success': True,
            'message': message,
            'new_settings': {
                'max_tokens': ai_config.OLLAMA_NUM_PREDICT,
                'temperature': ai_config.OLLAMA_TEMPERATURE,
                'top_p': ai_config.OLLAMA_TOP_P,
                'style': style
            }
        })
        
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@admin_bp.route('/config/restrictiveness', methods=['GET'])
def get_restrictiveness():
    # Get current AI restrictiveness level
    try:
        current_level = ai_config.get_restrictiveness()
        return jsonify({
            'success': True,
            'current_level': current_level,
            'available_levels': ['strict', 'balanced', 'open'],
            'descriptions': {
                'strict': 'Only answers from knowledge base',
                'balanced': 'Knowledge base + general business questions',
                'open': 'Allows most questions except inappropriate content'
            }
        })
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@admin_bp.route('/config/restrictiveness', methods=['POST'])
def update_restrictiveness():
    # Update AI restrictiveness level
    try:
        data = request.get_json()
        level = data.get('level', 'balanced').lower()
        
        # Actually update the AI configuration
        if level == 'strict':
            ai_config.set_restrictiveness('restrictive')
            message = "STRICT mode - Only answers from knowledge base"
            description = "AI will only respond to questions it can answer from the knowledge base. No general questions allowed."
            
        elif level == 'balanced':
            ai_config.set_restrictiveness('balanced')
            message = "BALANCED mode - Knowledge base + general business questions"
            description = "AI answers from knowledge base and allows general business questions while blocking inappropriate content."
            
        elif level == 'open':
            ai_config.set_restrictiveness('open')
            message = "OPEN mode - Allows most questions except inappropriate content"
            description = "AI will try to answer most questions unless they contain inappropriate content."
            
        else:
            return jsonify({'error': 'Invalid level. Use: strict, balanced, or open'}), 400
        
        return jsonify({
            'success': True,
            'message': message,
            'current_level': level,
            'description': description
        })
        
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500
