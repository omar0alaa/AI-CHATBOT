# Speech service - Azure Speech-to-Text (STT) and Text-to-Speech (TTS)

import base64
import os
import subprocess
import tempfile
import requests
from .ai_config import ai_config
from .logging_service import log_debug, log_error


class SpeechService:
    def __init__(self):
        self.key = ai_config.AZURE_SPEECH_KEY
        self.region = ai_config.AZURE_SPEECH_REGION
        self.endpoint = (ai_config.AZURE_SPEECH_ENDPOINT or '').strip().rstrip('/')

    def is_configured(self):
        return bool(self.key and (self.region or self.endpoint))

    def _require_config(self):
        if not self.is_configured():
            raise ValueError("Azure Speech is not configured. Set AZURE_SPEECH_KEY and either AZURE_SPEECH_REGION or AZURE_SPEECH_ENDPOINT.")

    def _speech_base_url(self, service='stt'):
        # Prefer region-based Speech hosts when region is available.
        # Generic Cognitive endpoint (e.g. *.api.cognitive.microsoft.com)
        # often returns 404 for Speech REST paths used here.
        if self.region:
            if service == 'tts':
                return f"https://{self.region}.tts.speech.microsoft.com"
            return f"https://{self.region}.stt.speech.microsoft.com"

        if self.endpoint:
            return self.endpoint
        raise ValueError("Azure Speech base URL could not be resolved. Set AZURE_SPEECH_REGION or AZURE_SPEECH_ENDPOINT.")

    def _map_ui_lang_to_locale(self, lang):
        lang_code = (lang or "").strip().lower()
        if lang_code.startswith('ar'):
            return 'ar-SA'
        if lang_code.startswith('en'):
            return 'en-US'
        return ai_config.AZURE_SPEECH_STT_DEFAULT_LOCALE

    def _default_voice_for_lang(self, lang):
        lang_code = (lang or "").strip().lower()
        if lang_code.startswith('ar'):
            return ai_config.AZURE_SPEECH_TTS_DEFAULT_VOICE_AR
        return ai_config.AZURE_SPEECH_TTS_DEFAULT_VOICE_EN

    def resolve_tts_format(self, requested_format=None):
        """
        Resolve API requested audio format to Azure output format + mime type + file extension.

        Supported request values:
        - mp3 (default)
        - ogg / opus / ogg-opus
        """
        fmt = (requested_format or 'mp3').strip().lower()

        # OGG/Opus output
        if fmt in ['ogg', 'opus', 'ogg-opus', 'audio/ogg']:
            return {
                'azure_output_format': 'ogg-24khz-16bit-mono-opus',
                'mime_type': 'audio/ogg',
                'extension': 'ogg',
                'api_format': 'ogg-opus',
            }

        # Default MP3 output
        return {
            'azure_output_format': 'audio-16khz-32kbitrate-mono-mp3',
            'mime_type': 'audio/mpeg',
            'extension': 'mp3',
            'api_format': 'mp3',
        }

    def speech_to_text(self, audio_bytes, content_type='audio/wav', lang=None):
        """
        Convert audio bytes to text using Azure Speech REST API.

        Note:
        Azure conversation STT endpoint expects PCM WAV-like audio. If clients send
        formats like OGG/Opus, conversion must be done before this call.
        """
        self._require_config()

        locale = self._map_ui_lang_to_locale(lang)

        # Best-effort conversion to PCM WAV for Azure STT when needed
        normalized_bytes, normalized_content_type = self._ensure_wav(audio_bytes, content_type)
        url = (
            f"{self._speech_base_url('stt')}/"
            f"speech/recognition/conversation/cognitiveservices/v1?language={locale}"
        )

        headers = {
            'Ocp-Apim-Subscription-Key': self.key,
            'Content-Type': normalized_content_type,
            'Accept': 'application/json',
        }

        log_debug(f"Calling Azure STT with locale={locale}, content_type={headers['Content-Type']}")
        resp = requests.post(url, headers=headers, data=normalized_bytes, timeout=60)

        if resp.status_code != 200:
            log_error(f"Azure STT failed ({resp.status_code}): {resp.text}")
            raise RuntimeError(f"Azure STT request failed: {resp.status_code}")

        payload = resp.json()
        # Azure may return DisplayText or lexical fields depending on endpoint behavior
        text = (payload.get('DisplayText') or payload.get('NBest', [{}])[0].get('Display') or '').strip()
        log_debug(f"Azure STT result length: {len(text)}")
        return text

    def _ensure_wav(self, audio_bytes, content_type):
        ctype = (content_type or '').lower()
        if 'wav' in ctype or 'pcm' in ctype:
            return audio_bytes, 'audio/wav; codecs=audio/pcm; samplerate=16000'

        # Try ffmpeg conversion for formats like ogg/opus/webm/m4a
        converted = self._convert_with_ffmpeg(audio_bytes)
        if converted is None:
            raise ValueError(
                "Unsupported audio format for STT. Please send WAV/PCM audio, "
                "or install ffmpeg on the server to auto-convert voice notes."
            )
        return converted, 'audio/wav; codecs=audio/pcm; samplerate=16000'

    def _convert_with_ffmpeg(self, audio_bytes):
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.input') as src:
                src.write(audio_bytes)
                src_path = src.name
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as dst:
                dst_path = dst.name

            cmd = [
                ai_config.FFMPEG_BINARY, '-y', '-i', src_path,
                '-ac', '1', '-ar', '16000', '-f', 'wav', dst_path,
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            if result.returncode != 0:
                log_error(f"ffmpeg conversion failed: {result.stderr.decode('utf-8', errors='ignore')[:500]}")
                return None

            with open(dst_path, 'rb') as f:
                return f.read()
        except Exception as e:
            log_error(f"ffmpeg conversion exception: {e}")
            return None
        finally:
            try:
                if 'src_path' in locals() and os.path.exists(src_path):
                    os.remove(src_path)
                if 'dst_path' in locals() and os.path.exists(dst_path):
                    os.remove(dst_path)
            except Exception:
                pass

    def text_to_speech(self, text, lang=None, voice=None, output_format='audio-16khz-32kbitrate-mono-mp3'):
        """Convert text to speech audio bytes using Azure TTS REST API."""
        self._require_config()

        selected_voice = voice or self._default_voice_for_lang(lang)
        url = f"{self._speech_base_url('tts')}/cognitiveservices/v1"

        ssml = f"""
<speak version='1.0' xml:lang='en-US'>
  <voice name='{selected_voice}'>{self._xml_escape(text)}</voice>
</speak>
""".strip()

        headers = {
            'Ocp-Apim-Subscription-Key': self.key,
            'Content-Type': 'application/ssml+xml',
            'X-Microsoft-OutputFormat': output_format,
            'User-Agent': 'AI-CHATBOT-AzureSpeech',
        }

        log_debug(f"Calling Azure TTS with voice={selected_voice}, format={output_format}")
        resp = requests.post(url, headers=headers, data=ssml.encode('utf-8'), timeout=60)

        if resp.status_code != 200:
            log_error(f"Azure TTS failed ({resp.status_code}): {resp.text}")
            raise RuntimeError(f"Azure TTS request failed: {resp.status_code}")

        return resp.content, selected_voice, output_format

    @staticmethod
    def _xml_escape(text):
        return (text or '') \
            .replace('&', '&amp;') \
            .replace('<', '&lt;') \
            .replace('>', '&gt;') \
            .replace('"', '&quot;') \
            .replace("'", '&apos;')

    @staticmethod
    def to_base64(audio_bytes):
        return base64.b64encode(audio_bytes).decode('utf-8')


speech_service = SpeechService()
