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
            conn.close()

            clients = []
            for name in names:
                if name == 'youlearnt_bank':
                    clients.append({'client_id': 'youlearnt', 'table': name})
                elif name.startswith('kb_'):
                    clients.append({'client_id': name[3:], 'table': name})
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
            
            # Find top 3 most similar Q&A pairs
            scored = []
            for q_en, q_ar, a_en, a_ar in rows:
                # Compare with both English and Arabic questions
                score_en = SequenceMatcher(None, user_message.lower(), q_en.lower()).ratio()
                score_ar = SequenceMatcher(None, user_message.lower(), q_ar.lower()).ratio()
                # Use the higher score
                score = max(score_en, score_ar)
                # Return answer in user's language
                answer = a_ar if user_lang == 'ar' else a_en
                scored.append((score, q_en, answer))
            
            scored.sort(reverse=True)
            # Return top N answers above configurable threshold
            top_contexts = [a for s, q, a in scored[:ai_config.MAX_KNOWLEDGE_CONTEXTS] 
                          if s >= ai_config.SIMILARITY_THRESHOLD]
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


# Create singleton instance
database_service = DatabaseService()

# Convenience function for backward compatibility
def get_answer_from_db(user_message, user_lang='en', client_id=DEFAULT_CLIENT_ID):
    #Convenience function for getting answers from database
    return database_service.get_answer_from_db(user_message, user_lang, client_id)
