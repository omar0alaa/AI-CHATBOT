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
        chunks = self._chunk_text(text, max_chars=6000, overlap=300)
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

        product_rows = self._normalize_products(all_products)
        catalog_entries = self._build_catalog_entries(product_rows)
        all_entries.extend(catalog_entries)

        _progress(82, 'normalizing', 'Normalizing and de-duplicating entries')
        log_info(f'Total raw entries before dedupe: {len(all_entries)}, products detected: {len(product_rows)}')
        normalized = self._normalize_and_dedupe(all_entries)
        log_info(f'After dedupe: {len(normalized)} entries')
        if not normalized:
            log_error(f'Zero entries survived. Raw entries count was {len(all_entries)}. '
                      f'Text length: {len(text)}, chunks: {len(chunks)}, products: {len(product_rows)}')
            raise RuntimeError(
                f'AI did not return valid KB entries. '
                f'Text extracted: {len(text)} chars, {len(chunks)} chunks processed, '
                f'{len(all_entries)} raw entries generated but none passed validation. '
                f'Check server logs for details.'
            )

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
            'You are building a bilingual (English + Arabic) knowledge base from a document.\n\n'
            'TASK: For EVERY distinct item, product, service, course, property, or offering mentioned '
            'in this chunk, generate DETAILED Q&A pairs that capture the real information from the text.\n\n'
            'For each item you find, create these Q&A entries (skip any that lack info in the text):\n'
            '1) IDENTITY: "What is [item name / code]?" -> Answer with: full name, type/category, '
            'and a one-sentence description.\n'
            '2) SPECS/DETAILS: "What are the specifications/details of [item]?" -> Answer listing ALL '
            'concrete details found in the text: technical specs, dimensions, features, location, duration, '
            'requirements, included items, etc.\n'
            '3) KEY FEATURES/HIGHLIGHTS: "What are the key features/highlights of [item]?" -> Answer listing '
            'the standout selling points, benefits, or unique characteristics.\n\n'
            'Also create general entries when applicable:\n'
            '- "What [category] options are available?" (group similar items)\n'
            '- "What is the difference between [A] and [B]?" (only when details differ clearly in the text)\n\n'
            'Return JSON ONLY (no markdown fences), as an array of objects with keys exactly:\n'
            'question_EN, question_AR, answer_EN, answer_AR\n\n'
            'STRICT RULES:\n'
            '- Include ALL numbers, specs, measurements, and units exactly as written in the text\n'
            '- Repeat the item name/code in every answer\n'
            '- Do NOT invent details or information not present in the text\n'
            '- Do NOT write vague answers like "available in catalog" or "ask for details" or "please inquire"\n'
            '- Every answer MUST contain real, concrete information extracted from the text\n'
            '- If an item only has a name and zero details in the text, SKIP it entirely (do not create a Q&A)\n'
            '- If a field like price or dates is NOT in the text, do not mention it\n\n'
            f'Chunk {chunk_index}/{total_chunks}:\n{chunk_text}'
        )

        payload = {
            'model': self.model_name,
            'messages': [
                {'role': 'system', 'content': 'You are a knowledge base builder. You output strict JSON arrays only. Every answer must contain real details and specifications from the provided text. Never output placeholder or generic answers.'},
                {'role': 'user', 'content': prompt},
            ],
            'max_tokens': int(getattr(ai_config, 'KB_INGEST_MAX_TOKENS', 6000)),
            'temperature': 0.15,
            'top_p': 0.9,
            'stream': False,
        }

        try:
            content = self._call_llm(payload)
        except Exception as e:
            log_error(f'Chunk {chunk_index}/{total_chunks} LLM call failed: {e}')
            return []
        entries = self._parse_entries_json(content)
        log_info(f'Chunk {chunk_index}/{total_chunks} generated {len(entries)} entries')
        return entries

    def _extract_products_from_chunk(self, chunk_text, chunk_index=1, total_chunks=1):
        prompt = (
            'Extract all distinct items (products, services, courses, properties, or offerings) '
            'from the following content.\n'
            'Return JSON ONLY as an array of objects with keys exactly:\n'
            'name_EN, name_AR, details_EN, details_AR\n\n'
            'Guidelines:\n'
            '1) Include only items explicitly mentioned in this chunk.\n'
            '2) In details_EN, write 2-4 sentences summarizing:\n'
            '   - Full name, code/SKU if available\n'
            '   - Type or category\n'
            '   - Key details: specs, features, location, duration, area, capacity, or any concrete attributes\n'
            '3) Use numbers and units exactly as in the text.\n'
            '4) If a code/SKU or exact English name is visible, include it in name_EN.\n'
            '5) If Arabic is not present in the text, translate the English name and details to Arabic.\n'
            '6) Do not invent details; only use information in the text.\n'
            '7) If no items exist in this chunk, return [].\n\n'
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

        try:
            content = self._call_llm(payload)
        except Exception as e:
            log_error(f'Chunk {chunk_index}/{total_chunks} product extraction failed: {e}')
            return []
        products = self._parse_products_json(content)
        log_info(f'Chunk {chunk_index}/{total_chunks} detected {len(products)} products')
        return products

    def _extract_products_from_full_text(self, text):
        # Additional pass to improve product recall across the full document
        sample = text[:45000]
        prompt = (
            'From the following document, extract a comprehensive list of all distinct items '
            '(products, services, courses, properties, or offerings).\n'
            'Return JSON ONLY as an array of objects with keys exactly:\n'
            'name_EN, name_AR, details_EN, details_AR\n\n'
            'Rules:\n'
            '1) Capture every distinct item, product line, SKU, service, or offering that appears.\n'
            '2) Deduplicate obvious duplicates by name/code, keeping the most complete details.\n'
            '3) In details_EN, summarize category + key details + standout features or highlights.\n'
            '4) Do not invent missing values; keep unknown Arabic fields empty.\n'
            '5) If no items exist, return [].\n\n'
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

    def _clean_json_response(self, content):
        """Strip markdown fences and extract the JSON array from LLM output."""
        raw = (content or '').strip()
        # Remove markdown code fences
        if '```' in raw:
            # Extract content between fences
            match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw, re.DOTALL)
            if match:
                raw = match.group(1).strip()
            else:
                raw = raw.replace('```json', '').replace('```', '').strip()
        return raw

    def _repair_truncated_json(self, raw):
        """Attempt to salvage complete JSON objects from a truncated JSON array.
        When the LLM runs out of tokens, the response is cut off mid-object.
        We find the last complete object and close the array."""
        start = raw.find('[')
        if start == -1:
            return None

        # Find the last complete object by looking for }, followed by optional whitespace
        # then either another { or an incomplete one
        array_content = raw[start:]

        # Try progressively shorter substrings until we find valid JSON
        # Look for the last },  or }\n pattern (end of a complete object in the array)
        last_good = -1
        brace_depth = 0
        in_string = False
        escape_next = False

        for i, ch in enumerate(array_content):
            if escape_next:
                escape_next = False
                continue
            if ch == '\\':
                if in_string:
                    escape_next = True
                continue
            if ch == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '{':
                brace_depth += 1
            elif ch == '}':
                brace_depth -= 1
                if brace_depth == 0:
                    last_good = i

        if last_good > 0:
            repaired = array_content[:last_good + 1] + ']'
            try:
                result = json.loads(repaired)
                if isinstance(result, list) and len(result) > 0:
                    log_info(f'Repaired truncated JSON: salvaged {len(result)} complete objects')
                    return result
            except Exception:
                pass

        return None

    def _parse_entries_json(self, content):
        raw = self._clean_json_response(content)
        log_debug(f'Parsing entries from LLM response ({len(raw)} chars): {raw[:300]}...')

        parsed = None
        try:
            parsed = json.loads(raw)
        except Exception:
            start = raw.find('[')
            end = raw.rfind(']')
            if start != -1 and end != -1 and end > start:
                try:
                    parsed = json.loads(raw[start:end + 1])
                except Exception as e:
                    log_error(f'Failed to parse entries JSON: {e}')
                    parsed = self._repair_truncated_json(raw)
            elif start != -1:
                # Has [ but no ] — truncated response
                log_info('LLM response was truncated (no closing ]). Attempting repair...')
                parsed = self._repair_truncated_json(raw)
            else:
                log_error(f'No JSON array found in LLM response: {raw[:500]}')

            if parsed is None:
                parsed = []

        if not isinstance(parsed, list):
            log_error(f'Parsed result is not a list: {type(parsed)}')
            return []

        entries = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            q_en = (item.get('question_EN') or '').strip()
            q_ar = (item.get('question_AR') or '').strip()
            a_en = (item.get('answer_EN') or '').strip()
            a_ar = (item.get('answer_AR') or '').strip()

            # Must have at least English Q&A; auto-fill Arabic if missing
            if not q_en or not a_en:
                continue
            if not q_ar:
                q_ar = q_en  # fallback: use English as Arabic placeholder
            if not a_ar:
                a_ar = a_en  # fallback: use English as Arabic placeholder

            entries.append({
                'question_EN': q_en,
                'question_AR': q_ar,
                'answer_EN': a_en,
                'answer_AR': a_ar,
            })

        log_debug(f'Parsed {len(entries)} valid entries from {len(parsed)} raw items')
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
        raw = self._clean_json_response(content)
        log_debug(f'Parsing products from LLM response ({len(raw)} chars): {raw[:300]}...')

        parsed = None
        try:
            parsed = json.loads(raw)
        except Exception:
            start = raw.find('[')
            end = raw.rfind(']')
            if start != -1 and end != -1 and end > start:
                try:
                    parsed = json.loads(raw[start:end + 1])
                except Exception as e:
                    log_error(f'Failed to parse products JSON: {e}')
                    parsed = self._repair_truncated_json(raw)
            elif start != -1:
                log_info('Products LLM response was truncated. Attempting repair...')
                parsed = self._repair_truncated_json(raw)
            else:
                log_error(f'No JSON array found in products response: {raw[:500]}')

            if parsed is None:
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
        category_like_names = {
            'power banks',
            'car chargers',
            'travel chargers',
            'chargers',
            'power bank',
            'car charger',
            'travel charger',
        }

        def _is_low_quality_name(name, details_en):
            candidate = re.sub(r'\s+', ' ', (name or '').strip())
            if not candidate:
                return True

            lowered = candidate.lower().strip(' .-_:;()[]{}')
            if lowered in category_like_names:
                return True

            if re.fullmatch(r'(new|hot|special\s+offer|offer)', lowered, flags=re.IGNORECASE):
                return True

            has_sku_like = bool(re.search(r'[A-Za-z]{1,6}-[A-Za-z0-9]{2,}', candidate))
            if not has_sku_like and not (details_en or '').strip():
                words = re.findall(r'[A-Za-z0-9\u0600-\u06FF]+', candidate)
                if len(words) <= 4:
                    return True

            return False

        for product in products:
            name_en = (product.get('name_EN') or '').strip()
            name_ar = (product.get('name_AR') or '').strip()
            if not name_en and not name_ar:
                continue

            details_en = (product.get('details_EN') or '').strip()
            details_ar = (product.get('details_AR') or '').strip()

            if _is_low_quality_name(name_en or name_ar, details_en):
                continue

            key = (name_en.lower(), name_ar.lower())
            if key in seen:
                continue
            seen.add(key)
            out.append({
                'name_EN': name_en,
                'name_AR': name_ar,
                'details_EN': details_en,
                'details_AR': details_ar,
            })
        return out

    def _build_catalog_entries(self, products):
        """Build master item list and AI-detected per-category summary entries.
        Individual product/item Q&A comes from _generate_entries_from_chunk, NOT here."""
        if not products:
            return []

        products = products[:500]
        entries = []

        # --- Master item list ---
        en_names = [p['name_EN'] for p in products if p.get('name_EN')]
        ar_names = [p['name_AR'] for p in products if p.get('name_AR')]

        if en_names:
            entries.append({
                'question_EN': 'What do you offer?',
                'question_AR': 'ماذا تقدمون؟',
                'answer_EN': 'We offer the following:\n' + '\n'.join(f'- {n}' for n in en_names),
                'answer_AR': 'نقدم ما يلي:\n' + '\n'.join(f'- {n}' for n in (ar_names or en_names)),
            })

        # --- Ask the LLM to categorize the products dynamically ---
        if len(products) >= 3:
            cat_entries = self._ai_categorize_products(products)
            entries.extend(cat_entries)

        return entries

    def _ai_categorize_products(self, products):
        """Use the LLM to group products into categories and generate per-category Q&A."""
        product_lines = []
        for p in products[:300]:
            name = p.get('name_EN') or p.get('name_AR') or ''
            details = (p.get('details_EN') or '')[:120]
            product_lines.append(f'{name} | {details}' if details else name)

        product_list_text = '\n'.join(product_lines)

        prompt = (
            'Given the following list of items from a catalog, group them into logical categories.\n'
            'Then for EACH category that has 2 or more items, create a Q&A entry.\n\n'
            'Return JSON ONLY (no markdown) as an array of objects with keys exactly:\n'
            'question_EN, question_AR, answer_EN, answer_AR\n\n'
            'For each category:\n'
            '- question_EN: "What [category] options/items do you have?" (use natural phrasing)\n'
            '- question_AR: Arabic translation of the question\n'
            '- answer_EN: "We offer the following [category]:" followed by a bullet list of item names\n'
            '- answer_AR: Arabic translation of the answer with the same item names\n\n'
            'Rules:\n'
            '- Detect categories from the actual content (electronics, real estate, courses, food, etc.)\n'
            '- Do NOT hardcode categories; derive them from the items\n'
            '- Keep category names short and natural\n'
            '- If all items belong to one category, create just one entry\n'
            '- Skip items that do not clearly fit any category\n'
            '- Maximum 15 categories\n\n'
            f'Items:\n{product_list_text}'
        )

        payload = {
            'model': self.model_name,
            'messages': [
                {'role': 'system', 'content': 'You output strict JSON arrays only.'},
                {'role': 'user', 'content': prompt},
            ],
            'max_tokens': min(3000, int(getattr(ai_config, 'KB_INGEST_MAX_TOKENS', 6000))),
            'temperature': 0.15,
            'top_p': 0.9,
            'stream': False,
        }

        try:
            content = self._call_llm(payload)
            return self._parse_entries_json(content)
        except Exception as e:
            log_error(f'AI categorization failed: {e}')
            return []


kb_ingestion_service = KBIngestionService()
