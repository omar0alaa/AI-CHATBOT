# Admin routes - Debug controls and database management

from flask import Blueprint, request, jsonify, render_template
from services.admin_service import admin_service
from services.database_service import database_service

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
