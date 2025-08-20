# Database service - Handles all database operations

import sqlite3
from difflib import SequenceMatcher
from logger import log_info, log_error, log_debug

DB_PATH = 'youlearnt_bank.db'


def init_db():
    #Initialize the database with required tables
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS youlearnt_bank (
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
    
    def get_answer_from_db(self, user_message, user_lang='en'):
        #Retrieve relevant answers from knowledge database
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('SELECT question_EN, question_AR, answer_EN, answer_AR FROM youlearnt_bank')
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
            # Return top 3 answers above higher threshold (more restrictive)
            top_contexts = [a for s, q, a in scored[:3] if s >= 0.7]
            return top_contexts
            
        except Exception as e:
            log_error(f"Database query failed: {e}")
            return []
    
    def get_all_entries(self):
        #Get all knowledge bank entries
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('SELECT ID, question_EN, question_AR, answer_EN, answer_AR, created_date FROM youlearnt_bank ORDER BY ID ASC')
            rows = [dict(ID=row[0], question_EN=row[1], question_AR=row[2], answer_EN=row[3], answer_AR=row[4], created_date=row[5]) for row in c.fetchall()]
            conn.close()
            return rows
        except Exception as e:
            log_error(f"Failed to get all entries: {e}")
            return []
    
    def add_entry(self, question_en, question_ar, answer_en, answer_ar):
        #Add new knowledge bank entry
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('INSERT INTO youlearnt_bank (question_EN, question_AR, answer_EN, answer_AR) VALUES (?, ?, ?, ?)', 
                      (question_en, question_ar, answer_en, answer_ar))
            conn.commit()
            conn.close()
            log_info(f"Added new entry: {question_en[:50]}...")
            return True
        except Exception as e:
            log_error(f"Failed to add entry: {e}")
            return False
    
    def update_entry(self, qa_id, question_en, question_ar, answer_en, answer_ar):
        #Update existing knowledge bank entry
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('UPDATE youlearnt_bank SET question_EN = ?, question_AR = ?, answer_EN = ?, answer_AR = ? WHERE ID = ?', 
                      (question_en, question_ar, answer_en, answer_ar, qa_id))
            conn.commit()
            conn.close()
            log_info(f"Updated entry ID {qa_id}: {question_en[:50]}...")
            return True
        except Exception as e:
            log_error(f"Failed to update entry ID {qa_id}: {e}")
            return False
    
    def delete_entry(self, qa_id):
        #Delete knowledge bank entry
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('DELETE FROM youlearnt_bank WHERE ID = ?', (qa_id,))
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
def get_answer_from_db(user_message, user_lang='en'):
    #Convenience function for getting answers from database
    return database_service.get_answer_from_db(user_message, user_lang)
