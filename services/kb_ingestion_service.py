# KB ingestion service - extract text from files and populate per-client KB tables via AI

import io
import json
import re
import requests
from pypdf import PdfReader
from docx import Document

from .ai_config import ai_config
from .database_service import database_service
from .logging_service import log_info, log_error, log_debug


class KBIngestionService:
    def __init__(self):
        self.api_url = ai_config.GROQ_API_URL
        self.model_name = ai_config.GROQ_MODEL
        self.api_key = ai_config.GROQ_API_KEY

    def ingest_file_to_kb(self, file_name, file_bytes, client_id='youlearnt', replace_existing=False):
        text = self.extract_text(file_name, file_bytes)
        if not text or not text.strip():
            raise ValueError('No extractable text found in file')

        chunks = self._chunk_text(text, max_chars=12000, overlap=400)
        all_entries = []
        for idx, chunk in enumerate(chunks):
            chunk_entries = self._generate_entries_from_chunk(chunk, chunk_index=idx + 1, total_chunks=len(chunks))
            all_entries.extend(chunk_entries)

        normalized = self._normalize_and_dedupe(all_entries)
        if not normalized:
            raise RuntimeError('AI did not return valid KB entries from the file content')

        if replace_existing:
            database_service.clear_client_entries(client_id)

        inserted = database_service.add_entries_bulk(normalized, client_id)
        return {
            'client_id': client_id,
            'source_file': file_name,
            'source_text_length': len(text),
            'chunks_processed': len(chunks),
            'generated_entries': len(normalized),
            'inserted_entries': inserted,
            'replace_existing': bool(replace_existing),
            'preview': normalized[:5],
        }

    def extract_text(self, file_name, file_bytes):
        lowered = (file_name or '').lower()
        if lowered.endswith('.pdf'):
            return self._extract_pdf(file_bytes)
        if lowered.endswith('.docx'):
            return self._extract_docx(file_bytes)
        if lowered.endswith('.txt'):
            return file_bytes.decode('utf-8', errors='ignore')
        raise ValueError('Unsupported file type. Supported: .pdf, .docx, .txt')

    def _extract_pdf(self, file_bytes):
        reader = PdfReader(io.BytesIO(file_bytes))
        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or '')
        return '\n'.join(pages)

    def _extract_docx(self, file_bytes):
        doc = Document(io.BytesIO(file_bytes))
        parts = [p.text for p in doc.paragraphs if p.text]
        return '\n'.join(parts)

    def _chunk_text(self, text, max_chars=12000, overlap=400):
        clean = re.sub(r'\n{3,}', '\n\n', text).strip()
        if len(clean) <= max_chars:
            return [clean]
        chunks = []
        start = 0
        length = len(clean)
        while start < length:
            end = min(start + max_chars, length)
            chunk = clean[start:end]
            if end < length:
                split_pos = chunk.rfind('\n\n')
                if split_pos > max_chars // 2:
                    chunk = chunk[:split_pos]
                    end = start + split_pos
            chunks.append(chunk.strip())
            if end >= length:
                break
            start = max(0, end - overlap)
        return [c for c in chunks if c]

    def _generate_entries_from_chunk(self, chunk_text, chunk_index=1, total_chunks=1):
        prompt = (
            'You are building a bilingual customer support knowledge base from document content.\n'
            'Extract atomic, practical Q&A pairs only from the content provided.\n'
            'Return JSON ONLY (no markdown), as an array of objects with keys exactly:\n'
            'question_EN, question_AR, answer_EN, answer_AR\n\n'
            'Rules:\n'
            '1) Keep each answer concise but complete.\n'
            '2) Do not invent facts.\n'
            '3) If content does not support a field, skip that entry entirely.\n'
            '4) Avoid duplicates and near-duplicates.\n'
            '5) Prefer high-value operational/business/support information.\n'
            '6) Generate as many high-quality entries as possible from this chunk.\n\n'
            f'Chunk {chunk_index}/{total_chunks}:\n{chunk_text}'
        )

        payload = {
            'model': self.model_name,
            'messages': [
                {'role': 'system', 'content': 'You output strict JSON only.'},
                {'role': 'user', 'content': prompt},
            ],
            # Higher token budget than chat path for ingestion tasks
            'max_tokens': int(getattr(ai_config, 'KB_INGEST_MAX_TOKENS', 3500)),
            'temperature': 0.2,
            'top_p': 0.95,
            'stream': False,
        }

        content = self._call_llm(payload)
        entries = self._parse_entries_json(content)
        log_debug(f'Chunk {chunk_index}/{total_chunks} generated entries: {len(entries)}')
        return entries

    def _call_llm(self, payload):
        if not self.api_key:
            raise RuntimeError('Missing GROQ_API_KEY environment variable')

        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
        resp = requests.post(
            self.api_url,
            headers=headers,
            json=payload,
            timeout=max(120, int(getattr(ai_config, 'GROQ_REQUEST_TIMEOUT', 120))),
        )
        if resp.status_code != 200:
            log_error(f'Ingestion LLM error {resp.status_code}: {resp.text[:500]}')
            raise RuntimeError(f'Ingestion LLM request failed: {resp.status_code}')

        result = resp.json()
        choices = result.get('choices', [])
        if not choices:
            return '[]'
        return (choices[0].get('message', {}) or {}).get('content', '[]') or '[]'

    def _parse_entries_json(self, content):
        raw = (content or '').strip()
        if raw.startswith('```'):
            raw = raw.strip('`')
            raw = raw.replace('json\n', '', 1)

        parsed = None
        try:
            parsed = json.loads(raw)
        except Exception:
            start = raw.find('[')
            end = raw.rfind(']')
            if start != -1 and end != -1 and end > start:
                try:
                    parsed = json.loads(raw[start:end + 1])
                except Exception:
                    parsed = []
            else:
                parsed = []

        if not isinstance(parsed, list):
            return []

        entries = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            q_en = (item.get('question_EN') or '').strip()
            q_ar = (item.get('question_AR') or '').strip()
            a_en = (item.get('answer_EN') or '').strip()
            a_ar = (item.get('answer_AR') or '').strip()
            if q_en and q_ar and a_en and a_ar:
                entries.append({
                    'question_EN': q_en,
                    'question_AR': q_ar,
                    'answer_EN': a_en,
                    'answer_AR': a_ar,
                })
        return entries

    def _normalize_and_dedupe(self, entries):
        seen = set()
        out = []
        for entry in entries:
            key = (
                (entry.get('question_EN') or '').strip().lower(),
                (entry.get('question_AR') or '').strip().lower(),
            )
            if not key[0] or not key[1]:
                continue
            if key in seen:
                continue
            seen.add(key)
            out.append(entry)
        return out


kb_ingestion_service = KBIngestionService()
