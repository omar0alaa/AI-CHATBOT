# Database service - Handles all database operations

import sqlite3
import re
from pathlib import Path
from difflib import SequenceMatcher
from .logging_service import log_info, log_error, log_debug
from .ai_config import ai_config

DB_PATH = str(Path(__file__).resolve().parent.parent / 'youlearnt_bank.db')
DEFAULT_CLIENT_ID = 'youlearnt'


def init_db():
    #Initialize the database with required tables
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # Backward-compatible default table
        c.execute('''CREATE TABLE IF NOT EXISTS youlearnt_bank (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            question_EN TEXT NOT NULL,
            question_AR TEXT NOT NULL,
            answer_EN TEXT NOT NULL,
            answer_AR TEXT NOT NULL,
            created_date TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        # Preferred per-client table for default client
        c.execute('''CREATE TABLE IF NOT EXISTS kb_youlearnt (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            question_EN TEXT NOT NULL,
            question_AR TEXT NOT NULL,
            answer_EN TEXT NOT NULL,
            answer_AR TEXT NOT NULL,
            created_date TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        conn.commit()
        conn.close()
        log_info("Database initialized successfully")
    except Exception as e:
        log_error(f"Database initialization failed: {e}")
        raise


class DatabaseService:
    #Service class for database operations
    
    def __init__(self):
        self.db_path = DB_PATH

    def _ensure_table_schema(self, conn, table):
        # Ensure required columns exist for older DB files/migrations
        c = conn.cursor()
        c.execute(f"PRAGMA table_info({table})")
        columns = {row[1] for row in c.fetchall()}
        if 'created_date' not in columns:
            c.execute(f'ALTER TABLE {table} ADD COLUMN created_date TEXT')
        conn.commit()

    def _normalize_client_id(self, client_id):
        cid = (client_id or DEFAULT_CLIENT_ID).strip().lower()
        cid = re.sub(r'[^a-z0-9_]+', '_', cid)
        cid = re.sub(r'_+', '_', cid).strip('_')
        if not cid:
            cid = DEFAULT_CLIENT_ID
        return cid

    def _table_name(self, client_id):
        cid = self._normalize_client_id(client_id)
        if cid == 'youlearnt':
            # Use existing table for backward compatibility
            return 'youlearnt_bank'
        return f'kb_{cid}'

    def ensure_client_table(self, client_id):
        table = self._table_name(client_id)
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute(f'''CREATE TABLE IF NOT EXISTS {table} (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                question_EN TEXT NOT NULL,
                question_AR TEXT NOT NULL,
                answer_EN TEXT NOT NULL,
                answer_AR TEXT NOT NULL,
                created_date TEXT DEFAULT CURRENT_TIMESTAMP
            )''')
            self._ensure_table_schema(conn, table)
            conn.commit()
            conn.close()
            return table
        except Exception as e:
            log_error(f"Failed ensuring client table {table}: {e}")
            raise

    def list_client_tables(self):
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name='youlearnt_bank' OR name LIKE 'kb_%') ORDER BY name ASC")
            names = [row[0] for row in c.fetchall()]

            clients = []
            for name in names:
                try:
                    c.execute(f'SELECT COUNT(1) FROM {name}')
                    entry_count = int(c.fetchone()[0])
                except Exception:
                    entry_count = 0
                if name == 'youlearnt_bank':
                    clients.append({'client_id': 'youlearnt', 'table': name, 'entry_count': entry_count})
                elif name.startswith('kb_'):
                    clients.append({'client_id': name[3:], 'table': name, 'entry_count': entry_count})
            conn.close()
            return clients
        except Exception as e:
            log_error(f"Failed to list client tables: {e}")
            return []
    
    def get_answer_from_db(self, user_message, user_lang='en', client_id=DEFAULT_CLIENT_ID):
        #Retrieve relevant answers from knowledge database
        try:
            table = self.ensure_client_table(client_id)
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute(f'SELECT question_EN, question_AR, answer_EN, answer_AR FROM {table}')
            rows = c.fetchall()
            conn.close()
            
            msg_lower = user_message.lower().strip()
            msg_words = set(re.findall(r'[a-z0-9\u0600-\u06ff]{2,}', msg_lower))
            
            scored = []
            for q_en, q_ar, a_en, a_ar in rows:
                q_en_lower = (q_en or '').lower()
                q_ar_lower = (q_ar or '').lower()
                a_en_lower = (a_en or '').lower()
                
                # 1) SequenceMatcher on question text
                seq_en = SequenceMatcher(None, msg_lower, q_en_lower).ratio()
                seq_ar = SequenceMatcher(None, msg_lower, q_ar_lower).ratio()
                seq_score = max(seq_en, seq_ar)
                
                # 2) Keyword overlap scoring (words in common / total words)
                q_words = set(re.findall(r'[a-z0-9\u0600-\u06ff]{2,}', q_en_lower + ' ' + q_ar_lower))
                a_words = set(re.findall(r'[a-z0-9\u0600-\u06ff]{2,}', a_en_lower))
                all_kb_words = q_words | a_words
                
                if msg_words and all_kb_words:
                    common = msg_words & all_kb_words
                    keyword_score = len(common) / max(len(msg_words), 1)
                else:
                    keyword_score = 0.0
                
                # 3) Combine: take the higher of the two approaches
                final_score = max(seq_score, keyword_score * 0.85)
                
                answer = a_ar if user_lang == 'ar' else a_en
                scored.append((final_score, q_en, answer))
            
            scored.sort(reverse=True)
            top_contexts = [a for s, q, a in scored[:ai_config.MAX_KNOWLEDGE_CONTEXTS] 
                          if s >= ai_config.SIMILARITY_THRESHOLD]
            
            log_debug(f'KB search for "{user_message[:60]}" -> top scores: {[(round(s,3), q[:50]) for s, q, _ in scored[:8]]}')
            return top_contexts
            
        except Exception as e:
            log_error(f"Database query failed: {e}")
            return []
    
    def get_all_entries(self, client_id=DEFAULT_CLIENT_ID):
        #Get all knowledge bank entries
        try:
            table = self.ensure_client_table(client_id)
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute(f'SELECT ID, question_EN, question_AR, answer_EN, answer_AR, created_date FROM {table} ORDER BY ID ASC')
            rows = [dict(ID=row[0], question_EN=row[1], question_AR=row[2], answer_EN=row[3], answer_AR=row[4], created_date=row[5]) for row in c.fetchall()]
            conn.close()
            return rows
        except Exception as e:
            log_error(f"Failed to get all entries: {e}")
            return []
    
    def add_entry(self, question_en, question_ar, answer_en, answer_ar, client_id=DEFAULT_CLIENT_ID):
        #Add new knowledge bank entry
        try:
            table = self.ensure_client_table(client_id)
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute(f'INSERT INTO {table} (question_EN, question_AR, answer_EN, answer_AR) VALUES (?, ?, ?, ?)', 
                      (question_en, question_ar, answer_en, answer_ar))
            conn.commit()
            conn.close()
            log_info(f"Added new entry to {table}: {question_en[:50]}...")
            return True
        except Exception as e:
            log_error(f"Failed to add entry: {e}")
            return False
    
    def update_entry(self, qa_id, question_en, question_ar, answer_en, answer_ar, client_id=DEFAULT_CLIENT_ID):
        #Update existing knowledge bank entry
        try:
            table = self.ensure_client_table(client_id)
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute(f'UPDATE {table} SET question_EN = ?, question_AR = ?, answer_EN = ?, answer_AR = ? WHERE ID = ?', 
                      (question_en, question_ar, answer_en, answer_ar, qa_id))
            conn.commit()
            conn.close()
            log_info(f"Updated entry ID {qa_id}: {question_en[:50]}...")
            return True
        except Exception as e:
            log_error(f"Failed to update entry ID {qa_id}: {e}")
            return False
    
    def delete_entry(self, qa_id, client_id=DEFAULT_CLIENT_ID):
        #Delete knowledge bank entry
        try:
            table = self.ensure_client_table(client_id)
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute(f'DELETE FROM {table} WHERE ID = ?', (qa_id,))
            conn.commit()
            conn.close()
            log_info(f"Deleted entry ID {qa_id}")
            return True
        except Exception as e:
            log_error(f"Failed to delete entry ID {qa_id}: {e}")
            return False

    def clear_client_entries(self, client_id=DEFAULT_CLIENT_ID):
        #Delete all entries for a client table
        try:
            table = self.ensure_client_table(client_id)
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute(f'DELETE FROM {table}')
            conn.commit()
            conn.close()
            log_info(f"Cleared all entries from {table}")
            return True
        except Exception as e:
            log_error(f"Failed clearing entries for client {client_id}: {e}")
            return False

    def add_entries_bulk(self, entries, client_id=DEFAULT_CLIENT_ID):
        #Bulk insert entries [{question_EN, question_AR, answer_EN, answer_AR}, ...]
        if not entries:
            return 0
        try:
            table = self.ensure_client_table(client_id)
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.executemany(
                f'INSERT INTO {table} (question_EN, question_AR, answer_EN, answer_AR) VALUES (?, ?, ?, ?)',
                [
                    (
                        (entry.get('question_EN') or '').strip(),
                        (entry.get('question_AR') or '').strip(),
                        (entry.get('answer_EN') or '').strip(),
                        (entry.get('answer_AR') or '').strip(),
                    )
                    for entry in entries
                ]
            )
            inserted = c.rowcount if c.rowcount and c.rowcount > 0 else len(entries)
            conn.commit()
            conn.close()
            log_info(f"Bulk inserted {inserted} entries into {table}")
            return inserted
        except Exception as e:
            log_error(f"Failed bulk insert for client {client_id}: {e}")
            return 0


# Create singleton instance
database_service = DatabaseService()

# Convenience function for backward compatibility
def get_answer_from_db(user_message, user_lang='en', client_id=DEFAULT_CLIENT_ID):
    #Convenience function for getting answers from database
    return database_service.get_answer_from_db(user_message, user_lang, client_id)
