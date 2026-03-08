# KB ingestion service - extract text from files and populate per-client KB tables via AI

import io
import json
import re
import threading
import time
import uuid
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
        self._jobs = {}
        self._jobs_lock = threading.Lock()

    def start_ingestion_job(self, file_name, file_bytes, client_id='youlearnt', replace_existing=False):
        job_id = str(uuid.uuid4())
        job = {
            'job_id': job_id,
            'status': 'queued',
            'progress': 0,
            'stage': 'queued',
            'message': 'Job queued',
            'client_id': client_id,
            'source_file': file_name,
            'created_at': int(time.time()),
            'updated_at': int(time.time()),
            'result': None,
            'error': None,
        }
        with self._jobs_lock:
            self._jobs[job_id] = job

        thread = threading.Thread(
            target=self._run_ingestion_job,
            args=(job_id, file_name, file_bytes, client_id, replace_existing),
            daemon=True,
        )
        thread.start()
        return job_id

    def get_job_status(self, job_id):
        with self._jobs_lock:
            return dict(self._jobs.get(job_id) or {})

    def _update_job(self, job_id, **updates):
        with self._jobs_lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job.update(updates)
            job['updated_at'] = int(time.time())

    def _run_ingestion_job(self, job_id, file_name, file_bytes, client_id, replace_existing):
        try:
            self._update_job(job_id, status='running', progress=3, stage='starting', message='Starting ingestion')

            def progress_cb(progress, stage, message):
                self._update_job(job_id, progress=max(0, min(100, int(progress))), stage=stage, message=message)

            result = self.ingest_file_to_kb(
                file_name=file_name,
                file_bytes=file_bytes,
                client_id=client_id,
                replace_existing=replace_existing,
                progress_cb=progress_cb,
            )
            self._update_job(
                job_id,
                status='completed',
                progress=100,
                stage='completed',
                message='Import completed',
                result=result,
            )
        except Exception as e:
            log_error(f'KB ingestion job failed: {e}')
            self._update_job(
                job_id,
                status='failed',
                stage='failed',
                message='Import failed',
                error=str(e),
            )

    def ingest_file_to_kb(self, file_name, file_bytes, client_id='youlearnt', replace_existing=False, progress_cb=None):
        def _progress(p, stage, message):
            if progress_cb:
                progress_cb(p, stage, message)

        _progress(5, 'extracting_text', 'Extracting text from file')
        text = self.extract_text(file_name, file_bytes)
        if not text or not text.strip():
            raise ValueError('No extractable text found in file')

        _progress(12, 'chunking', 'Chunking extracted content')
        chunks = self._chunk_text(text, max_chars=12000, overlap=400)
        all_entries = []
        all_products = []
        for idx, chunk in enumerate(chunks):
            base = 15
            span = 55
            frac = (idx / max(1, len(chunks)))
            _progress(base + int(span * frac), 'ai_chunk_processing', f'Processing chunk {idx + 1}/{len(chunks)}')
            chunk_entries = self._generate_entries_from_chunk(chunk, chunk_index=idx + 1, total_chunks=len(chunks))
            all_entries.extend(chunk_entries)
            chunk_products = self._extract_products_from_chunk(chunk, chunk_index=idx + 1, total_chunks=len(chunks))
            all_products.extend(chunk_products)

        _progress(72, 'product_enrichment', 'Running full-document product extraction')
        all_products.extend(self._extract_products_from_full_text(text))
        all_products.extend(self._extract_products_heuristic(text))

        product_rows = self._normalize_products(all_products)
        product_entries = self._product_rows_to_entries(product_rows)
        all_entries.extend(product_entries)
        all_entries.extend(self._category_rows_to_entries(product_rows))

        _progress(82, 'normalizing', 'Normalizing and de-duplicating entries')
        normalized = self._normalize_and_dedupe(all_entries)
        if not normalized:
            raise RuntimeError('AI did not return valid KB entries from the file content')

        if replace_existing:
            _progress(88, 'clearing_existing', 'Clearing existing client KB entries')
            database_service.clear_client_entries(client_id)

        _progress(93, 'saving', 'Saving generated entries to database')
        inserted = database_service.add_entries_bulk(normalized, client_id)
        _progress(99, 'finalizing', 'Finalizing import result')
        return {
            'client_id': client_id,
            'source_file': file_name,
            'source_text_length': len(text),
            'chunks_processed': len(chunks),
            'products_detected': len(product_rows),
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
            'You are building a bilingual product knowledge base from a commercial catalog.\n'
            'The document contains many SKUs with names, categories, specs, features, '
            'certifications, packaging info, and general notes.\n\n'
            'Your task: extract atomic, practical Q&A pairs ONLY from the content provided in this chunk.\n'
            'Focus on:\n'
            '- Product identity (what is SKU X, what category it belongs to)\n'
            '- Product specs (capacity, ports, power, resolution, battery, OS, etc.)\n'
            '- Product features/benefits (wireless CarPlay, ENC, night vision, 4G, Wi-Fi 6, etc.)\n'
            '- Category questions (which dashcams / power banks / car chargers are available)\n'
            '- General catalog questions (what categories exist, what certifications are used)\n\n'
            'Return JSON ONLY (no markdown), as an array of objects with keys exactly:\n'
            'question_EN, question_AR, answer_EN, answer_AR\n\n'
            'Rules:\n'
            '1) Keep each answer concise but complete and self-contained (no reference to "this chunk").\n'
            '2) Do NOT invent facts or SKUs not in the text.\n'
            '3) If the content does not clearly support a full Q&A, skip it.\n'
            '4) Avoid duplicates and near-duplicates.\n'
            '5) Prefer high-value product, category, and catalog information.\n'
            '6) If products are listed, create multiple Q&As per product: identity, specs, features where possible.\n'
            '7) When answering, repeat the SKU and product name in the answer whenever available.\n'
            '8) If a field like price or warranty is NOT present, do not mention it.\n\n'
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

    def _extract_products_from_chunk(self, chunk_text, chunk_index=1, total_chunks=1):
        prompt = (
            'Extract products from the following catalog content.\n'
            'Each product usually has an SKU, name, specs and features.\n'
            'Return JSON ONLY as an array of objects with keys exactly:\n'
            'name_EN, name_AR, details_EN, details_AR\n\n'
            'Guidelines:\n'
            '1) Include only products explicitly mentioned in this chunk.\n'
            '2) In details_EN, write 1-3 sentences summarizing SKU, category, key specs '
            '(capacity/power/resolution/etc.), and main features.\n'
            '3) If the SKU or exact English name is visible, include it in name_EN.\n'
            '4) If Arabic is not present in the text, translate it to arabic.\n'
            '5) Do not invent specs or categories; only use information in the text.\n'
            '6) If no products/services exist in this chunk, return [].\n\n'
            f'Chunk {chunk_index}/{total_chunks}:\n{chunk_text}'
        )

        payload = {
            'model': self.model_name,
            'messages': [
                {'role': 'system', 'content': 'You output strict JSON only.'},
                {'role': 'user', 'content': prompt},
            ],
            'max_tokens': min(1800, int(getattr(ai_config, 'KB_INGEST_MAX_TOKENS', 3500))),
            'temperature': 0.1,
            'top_p': 0.9,
            'stream': False,
        }

        content = self._call_llm(payload)
        products = self._parse_products_json(content)
        log_debug(f'Chunk {chunk_index}/{total_chunks} detected products: {len(products)}')
        return products

    def _extract_products_from_full_text(self, text):
        # Additional pass to improve product recall across the full document
        sample = text[:45000]
        prompt = (
            'From the following document, extract a comprehensive list of products mentioned in the full catalog document.\n'
            'Return JSON ONLY as an array of objects with keys exactly:\n'
            'name_EN, name_AR, details_EN, details_AR\n\n'
            'Rules:\n'
            '1) Capture every distinct product line or SKU that appears.\n'
            '2) Deduplicate obvious duplicates by SKU/name, keeping the most complete details.\n'
            '3) In details_EN, summarize category + key specs + standout features.\n'
            '4) Do not invent missing values; keep unknown Arabic fields empty.\n'
            '5) If no products exist, return [].\n\n'
            f'{sample}'
        )

        payload = {
            'model': self.model_name,
            'messages': [
                {'role': 'system', 'content': 'You output strict JSON only.'},
                {'role': 'user', 'content': prompt},
            ],
            'max_tokens': min(2200, int(getattr(ai_config, 'KB_INGEST_MAX_TOKENS', 3500))),
            'temperature': 0.1,
            'top_p': 0.9,
            'stream': False,
        }

        content = self._call_llm(payload)
        return self._parse_products_json(content)

    def _extract_products_heuristic(self, text):
        # Heuristic fallback for bullet/numbered product lists in catalogs
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        candidates = []
        for line in lines:
            clean = re.sub(r'^[\-\*•\d\)\.(\s]+', '', line).strip()
            if len(clean) < 3 or len(clean) > 140:
                continue
            if not re.search(r'[A-Za-z\u0600-\u06FF]', clean):
                continue
            if re.search(r'\b(page|copyright|www\.|http)\b', clean.lower()):
                continue
            # Keep likely item-style lines
            if re.match(r'^[A-Za-z\u0600-\u06FF][^:]{2,120}$', clean):
                if re.search(r'[\u0600-\u06FF]', clean):
                    candidates.append({'name_EN': '', 'name_AR': clean, 'details_EN': '', 'details_AR': ''})
                else:
                    candidates.append({'name_EN': clean, 'name_AR': '', 'details_EN': '', 'details_AR': ''})
            if len(candidates) >= 400:
                break
        return candidates

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

    def _parse_products_json(self, content):
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

        out = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            name_en = (item.get('name_EN') or '').strip()
            name_ar = (item.get('name_AR') or '').strip()
            details_en = (item.get('details_EN') or '').strip()
            details_ar = (item.get('details_AR') or '').strip()
            if name_en or name_ar:
                out.append({
                    'name_EN': name_en,
                    'name_AR': name_ar,
                    'details_EN': details_en,
                    'details_AR': details_ar,
                })
        return out

    def _normalize_products(self, products):
        seen = set()
        out = []
        for product in products:
            name_en = (product.get('name_EN') or '').strip()
            name_ar = (product.get('name_AR') or '').strip()
            if not name_en and not name_ar:
                continue
            key = (name_en.lower(), name_ar.lower())
            if key in seen:
                continue
            seen.add(key)
            out.append({
                'name_EN': name_en,
                'name_AR': name_ar,
                'details_EN': (product.get('details_EN') or '').strip(),
                'details_AR': (product.get('details_AR') or '').strip(),
            })
        return out

    def _product_rows_to_entries(self, products):
        if not products:
            return []

        # Cap to avoid runaway KB growth for very large catalogs in one run
        products = products[:300]

        en_names = [p['name_EN'] for p in products if p.get('name_EN')]
        ar_names = [p['name_AR'] for p in products if p.get('name_AR')]

        entries = [
            {
                'question_EN': 'What products or services do you offer?',
                'question_AR': 'ما هي المنتجات أو الخدمات التي تقدمونها؟',
                'answer_EN': '\n'.join([f'- {n}' for n in en_names]) if en_names else 'Please ask for the available products.',
                'answer_AR': '\n'.join([f'- {n}' for n in ar_names]) if ar_names else 'يرجى السؤال عن المنتجات المتاحة.',
            }
        ]

        for product in products:
            name_en = product.get('name_EN') or product.get('name_AR') or 'this product'
            name_ar = product.get('name_AR') or product.get('name_EN') or 'هذا المنتج'
            details_en = product.get('details_EN') or f'{name_en} is available in our catalog.'
            details_ar = product.get('details_AR') or f'{name_ar} متاح ضمن منتجاتنا.'

            entries.append({
                'question_EN': f'Tell me about {name_en}.',
                'question_AR': f'أعطني تفاصيل عن {name_ar}.',
                'answer_EN': details_en,
                'answer_AR': details_ar,
            })

        return entries

    def _category_rows_to_entries(self, products):
        if not products:
            return []

        categories = set()
        for product in products:
            details = (product.get('details_EN') or '').strip()
            if not details:
                continue

            # Try common patterns like "Category: Cameras" or "category - Networking".
            match = re.search(r'\bcategory\s*[:\-]\s*([^\n\.;]{2,80})', details, re.IGNORECASE)
            if match:
                categories.add(match.group(1).strip())

        if not categories:
            return []

        ordered_categories = sorted(categories)
        return [
            {
                'question_EN': 'What product categories do you provide?',
                'question_AR': 'ما هي فئات المنتجات التي توفرونها؟',
                'answer_EN': '\n'.join([f'- {c}' for c in ordered_categories]),
                'answer_AR': 'تتوفر فئات متعددة من المنتجات. يمكنني تزويدك بالتفاصيل حسب الفئة المطلوبة.',
            }
        ]


kb_ingestion_service = KBIngestionService()
