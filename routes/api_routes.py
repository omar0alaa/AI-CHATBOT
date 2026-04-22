# API routes - Chat functionality and AI interactions
import io
import os
import re
from pathlib import Path
from flask import Blueprint, request, jsonify, session, send_file
from services.chat_service import chat_service
from services.speech_service import speech_service
from services.database_service import database_service
from services.kb_ingestion_service import kb_ingestion_service

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


def _get_client_name(data=None, form=None, args=None):
    data = data or {}
    form = form or {}
    args = args or {}
    value = data.get('client_name') or form.get('client_name') or args.get('client_name')
    if value and str(value).strip():
        return str(value).strip()
    # fallback to client_id when no explicit display name is provided
    return _get_client_id(data=data, form=form, args=args)


def _get_custom_persona(data=None, form=None, args=None):
    data = data or {}
    form = form or {}
    args = args or {}
    value = data.get('custom_persona') or form.get('custom_persona') or args.get('custom_persona')
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None

@api_bp.route('/chat', methods=['POST'])
def chat():
    # Main chat endpoint - processes user messages and returns AI responses
    try:
        # Parse request
        data = request.json
        user_message = data.get('message', '')
        ui_lang = data.get('lang')
        client_id = _get_client_id(data=data)
        client_name = _get_client_name(data=data)
        custom_persona = _get_custom_persona(data=data)
        
        if not user_message:
            return jsonify({'error': 'No message provided'}), 400
        
        # Get chat history from session
        if 'chat_history_by_client' not in session:
            session['chat_history_by_client'] = {}
        history_map = session['chat_history_by_client']
        chat_history = history_map.get(client_id, [])
        
        # Process message using chat service
        processed_answer, updated_history, media = chat_service.process_message(
            user_message, ui_lang, chat_history, client_id, client_name, custom_persona
        )
        
        # Update session
        history_map[client_id] = updated_history
        session['chat_history_by_client'] = history_map
        
        # Return response with media if available
        response = {'message': str(processed_answer), 'client_id': client_id}
        if media:
            response['media'] = media
        return jsonify(response)
        
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
        client_name = _get_client_name(form=request.form, args=request.args)
        custom_persona = _get_custom_persona(form=request.form, args=request.args)

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

        reply_text, updated_history, media = chat_service.process_message(transcript, ui_lang, chat_history, client_id, client_name, custom_persona)
        history_map[client_id] = updated_history
        session['chat_history_by_client'] = history_map

        response_payload = {
            'transcript': transcript,
            'reply': str(reply_text),
            'summary_enabled': summarize,
            'client_id': client_id,
        }

        if media:
            response_payload['media'] = media

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
        image_url = (data.get('image_url') or '').strip() or None
        video_url = (data.get('video_url') or '').strip() or None
        product_url = (data.get('product_url') or '').strip() or None

        if not question_en or not question_ar or not answer_en or not answer_ar:
            return jsonify({'error': 'Missing required fields (question_EN, question_AR, answer_EN, answer_AR)'}), 400

        success = database_service.add_entry(question_en, question_ar, answer_en, answer_ar, client_id, image_url, video_url, product_url)
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
        image_url = (data.get('image_url') or '').strip() or None
        video_url = (data.get('video_url') or '').strip() or None
        product_url = (data.get('product_url') or '').strip() or None

        if not question_en or not question_ar or not answer_en or not answer_ar:
            return jsonify({'error': 'Missing required fields (question_EN, question_AR, answer_EN, answer_AR)'}), 400

        success = database_service.update_entry(qa_id, question_en, question_ar, answer_en, answer_ar, client_id, image_url, video_url, product_url)
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


@api_bp.route('/knowledge/entries/clear', methods=['POST'])
def knowledge_entries_clear():
    try:
        data = request.get_json(silent=True) or {}
        client_id = _get_client_id(data=data, args=request.args)
        success = database_service.clear_client_entries(client_id)
        if not success:
            return jsonify({'error': 'Failed to clear entries'}), 500
        return jsonify({'success': True, 'client_id': client_id})
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500


ALLOWED_MEDIA_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.mp4', '.webm', '.mov', '.avi'}
UPLOAD_BASE = Path(__file__).resolve().parent.parent / 'uploads' / 'kb'

@api_bp.route('/knowledge/media/upload', methods=['POST'])
def knowledge_media_upload():
    try:
        media_file = request.files.get('file')
        if not media_file or not media_file.filename:
            return jsonify({'error': 'No file provided'}), 400

        client_id = _get_client_id(form=request.form, args=request.args)
        safe_client = re.sub(r'[^a-z0-9_]', '_', client_id.lower())

        filename = media_file.filename
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_MEDIA_EXTENSIONS:
            return jsonify({'error': f'File type {ext} not allowed'}), 400

        # Sanitize filename
        safe_name = re.sub(r'[^\w.\-]', '_', Path(filename).stem) + ext
        dest_dir = UPLOAD_BASE / safe_client
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest_path = dest_dir / safe_name
        # Avoid overwrites by appending counter
        counter = 1
        while dest_path.exists():
            dest_path = dest_dir / f"{Path(safe_name).stem}_{counter}{ext}"
            counter += 1

        media_file.save(str(dest_path))

        # Return relative URL path
        rel_url = f'/uploads/kb/{safe_client}/{dest_path.name}'
        return jsonify({'success': True, 'url': rel_url, 'filename': dest_path.name})
    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500


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


@api_bp.route('/knowledge/import', methods=['POST'])
def knowledge_import_from_file():
    """
    Upload a PDF/DOCX/TXT file and auto-populate the selected client KB table.
    multipart/form-data fields:
      - file: required
      - client_id: optional (default: youlearnt)
      - replace_existing: optional bool (default: false)
    """
    try:
        upload = request.files.get('file')
        if not upload:
            return jsonify({'error': 'No file provided. Use multipart/form-data field: file'}), 400

        file_name = upload.filename or 'uploaded_file'
        file_bytes = upload.read()
        if not file_bytes:
            return jsonify({'error': 'Uploaded file is empty'}), 400

        client_id = _get_client_id(form=request.form, args=request.args)
        async_mode = _to_bool(request.form.get('async', request.args.get('async')), default=False)
        replace_existing_requested = _to_bool(
            request.form.get('replace_existing', request.args.get('replace_existing')),
            default=False,
        )
        force_replace = _to_bool(
            request.form.get('force_replace', request.args.get('force_replace')),
            default=False,
        )

        # Safety guard: avoid accidental repeated wipes across consecutive runs.
        # If replace is requested multiple times in the same session for same client,
        # only first run clears unless force_replace=true is explicitly sent.
        replaced_clients = set(session.get('kb_replaced_clients', []))
        replace_existing_effective = replace_existing_requested
        if replace_existing_requested and not force_replace and client_id in replaced_clients:
            replace_existing_effective = False

        if async_mode:
            job_id = kb_ingestion_service.start_ingestion_job(
                file_name=file_name,
                file_bytes=file_bytes,
                client_id=client_id,
                replace_existing=replace_existing_effective,
            )
            if replace_existing_effective:
                replaced_clients.add(client_id)
                session['kb_replaced_clients'] = list(replaced_clients)
            return jsonify({
                'success': True,
                'async': True,
                'job_id': job_id,
                'client_id': client_id,
                'replace_requested': replace_existing_requested,
                'replace_applied': replace_existing_effective,
                'force_replace': force_replace,
            }), 202

        result = kb_ingestion_service.ingest_file_to_kb(
            file_name=file_name,
            file_bytes=file_bytes,
            client_id=client_id,
            replace_existing=replace_existing_effective,
        )
        if replace_existing_effective:
            replaced_clients.add(client_id)
            session['kb_replaced_clients'] = list(replaced_clients)

        result['replace_requested'] = replace_existing_requested
        result['replace_applied'] = replace_existing_effective
        result['force_replace'] = force_replace
        return jsonify({'success': True, **result})

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 502
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500


@api_bp.route('/knowledge/import/status/<job_id>', methods=['GET'])
def knowledge_import_status(job_id):
    try:
        job = kb_ingestion_service.get_job_status(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        return jsonify(job)
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500
