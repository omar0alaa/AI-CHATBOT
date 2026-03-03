# API routes - Chat functionality and AI interactions
import io
from flask import Blueprint, request, jsonify, session, send_file
from services.chat_service import chat_service
from services.speech_service import speech_service
from services.database_service import database_service

api_bp = Blueprint('api', __name__, url_prefix='/api')


def _to_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ['1', 'true', 'yes', 'on']


def _get_client_id(data=None, form=None, args=None):
    data = data or {}
    form = form or {}
    args = args or {}
    return (
        data.get('client_id')
        or form.get('client_id')
        or args.get('client_id')
        or 'youlearnt'
    )

@api_bp.route('/chat', methods=['POST'])
def chat():
    # Main chat endpoint - processes user messages and returns AI responses
    try:
        # Parse request
        data = request.json
        user_message = data.get('message', '')
        ui_lang = data.get('lang')
        client_id = _get_client_id(data=data)
        
        if not user_message:
            return jsonify({'error': 'No message provided'}), 400
        
        # Get chat history from session
        if 'chat_history_by_client' not in session:
            session['chat_history_by_client'] = {}
        history_map = session['chat_history_by_client']
        chat_history = history_map.get(client_id, [])
        
        # Process message using chat service
        processed_answer, updated_history = chat_service.process_message(
            user_message, ui_lang, chat_history, client_id
        )
        
        # Update session
        history_map[client_id] = updated_history
        session['chat_history_by_client'] = history_map
        
        # Return response
        return jsonify({'message': str(processed_answer), 'client_id': client_id})
        
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500


@api_bp.route('/voice/chat', methods=['POST'])
def voice_chat():
    """
    Voice workflow endpoint:
    1) Receive audio file
    2) Convert voice to text using Azure STT
    3) Generate AI reply text
    4) Optionally include summary of transcript (toggle)
    """
    try:
        if not speech_service.is_configured():
            return jsonify({'error': 'Azure Speech is not configured'}), 500

        audio_file = request.files.get('audio')
        if not audio_file:
            return jsonify({'error': 'No audio file provided. Use multipart/form-data field: audio'}), 400

        audio_bytes = audio_file.read()
        if not audio_bytes:
            return jsonify({'error': 'Audio file is empty'}), 400

        # Request controls
        ui_lang = request.form.get('lang') or request.args.get('lang') or 'en'
        summarize = _to_bool(request.form.get('summarize', request.args.get('summarize')), default=False)
        client_id = _get_client_id(form=request.form, args=request.args)

        # STT
        transcript = speech_service.speech_to_text(
            audio_bytes=audio_bytes,
            content_type=audio_file.mimetype or 'audio/wav',
            lang=ui_lang
        )

        if not transcript:
            return jsonify({'error': 'Speech could not be recognized. Try clearer audio or supported format.'}), 422

        # Chat reply using existing core flow + session history
        if 'chat_history_by_client' not in session:
            session['chat_history_by_client'] = {}
        history_map = session['chat_history_by_client']
        chat_history = history_map.get(client_id, [])

        reply_text, updated_history = chat_service.process_message(transcript, ui_lang, chat_history, client_id)
        history_map[client_id] = updated_history
        session['chat_history_by_client'] = history_map

        response_payload = {
            'transcript': transcript,
            'reply': str(reply_text),
            'summary_enabled': summarize,
            'client_id': client_id,
        }

        if summarize:
            response_payload['summary'] = chat_service.summarize_message(transcript, ui_lang)

        return jsonify(response_payload)

    except RuntimeError as e:
        return jsonify({'error': str(e)}), 502
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500


@api_bp.route('/knowledge/clients', methods=['GET'])
def knowledge_clients_list():
    try:
        return jsonify({'clients': database_service.list_client_tables()})
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500


@api_bp.route('/knowledge/clients', methods=['POST'])
def knowledge_clients_create():
    try:
        data = request.get_json(silent=True) or {}
        client_id = _get_client_id(data=data)
        table = database_service.ensure_client_table(client_id)
        return jsonify({'success': True, 'client_id': client_id, 'table': table})
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500


@api_bp.route('/knowledge/entries', methods=['GET'])
def knowledge_entries_get():
    try:
        client_id = _get_client_id(args=request.args)
        entries = database_service.get_all_entries(client_id)
        return jsonify({'client_id': client_id, 'entries': entries})
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500


@api_bp.route('/knowledge/entries', methods=['POST'])
def knowledge_entries_add():
    try:
        data = request.get_json(silent=True) or {}
        client_id = _get_client_id(data=data)
        question_en = (data.get('question_EN') or '').strip()
        question_ar = (data.get('question_AR') or '').strip()
        answer_en = (data.get('answer_EN') or '').strip()
        answer_ar = (data.get('answer_AR') or '').strip()

        if not question_en or not question_ar or not answer_en or not answer_ar:
            return jsonify({'error': 'Missing required fields (question_EN, question_AR, answer_EN, answer_AR)'}), 400

        success = database_service.add_entry(question_en, question_ar, answer_en, answer_ar, client_id)
        if not success:
            return jsonify({'error': 'Failed to add entry'}), 500

        return jsonify({'success': True, 'client_id': client_id})
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500


@api_bp.route('/knowledge/entries/<int:qa_id>', methods=['PUT'])
def knowledge_entries_update(qa_id):
    try:
        data = request.get_json(silent=True) or {}
        client_id = _get_client_id(data=data)
        question_en = (data.get('question_EN') or '').strip()
        question_ar = (data.get('question_AR') or '').strip()
        answer_en = (data.get('answer_EN') or '').strip()
        answer_ar = (data.get('answer_AR') or '').strip()

        if not question_en or not question_ar or not answer_en or not answer_ar:
            return jsonify({'error': 'Missing required fields (question_EN, question_AR, answer_EN, answer_AR)'}), 400

        success = database_service.update_entry(qa_id, question_en, question_ar, answer_en, answer_ar, client_id)
        if not success:
            return jsonify({'error': 'Failed to update entry'}), 500

        return jsonify({'success': True, 'client_id': client_id, 'id': qa_id})
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500


@api_bp.route('/knowledge/entries/<int:qa_id>', methods=['DELETE'])
def knowledge_entries_delete(qa_id):
    try:
        data = request.get_json(silent=True) or {}
        client_id = _get_client_id(data=data, args=request.args)
        success = database_service.delete_entry(qa_id, client_id)
        if not success:
            return jsonify({'error': 'Failed to delete entry'}), 500

        return jsonify({'success': True, 'client_id': client_id, 'id': qa_id})
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500


@api_bp.route('/voice/tts', methods=['POST'])
def voice_tts():
    """
    TTS endpoint:
    - Accepts text
    - Returns synthesized speech audio (mp3) by default
    """
    try:
        if not speech_service.is_configured():
            return jsonify({'error': 'Azure Speech is not configured'}), 500

        data = request.get_json(silent=True) or {}
        text = (data.get('text') or '').strip()
        lang = data.get('lang', 'en')
        voice = data.get('voice')
        as_base64 = _to_bool(data.get('base64'), default=False)
        requested_format = data.get('format', 'mp3')

        if not text:
            return jsonify({'error': 'No text provided'}), 400

        format_config = speech_service.resolve_tts_format(requested_format)
        audio_bytes, selected_voice, output_format = speech_service.text_to_speech(
            text=text,
            lang=lang,
            voice=voice,
            output_format=format_config['azure_output_format'],
        )

        if as_base64:
            return jsonify({
                'audio_base64': speech_service.to_base64(audio_bytes),
                'voice': selected_voice,
                'format': output_format,
                'api_format': format_config['api_format'],
                'mime_type': format_config['mime_type'],
            })

        return send_file(
            io.BytesIO(audio_bytes),
            mimetype=format_config['mime_type'],
            as_attachment=False,
            download_name=f"speech.{format_config['extension']}"
        )

    except RuntimeError as e:
        return jsonify({'error': str(e)}), 502
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500
