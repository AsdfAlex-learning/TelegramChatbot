import sqlite3
import csv
import os
import threading
from datetime import datetime, timedelta

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

USER_MEMORIES_DIR = os.path.join(PROJECT_ROOT, "user_memories")
os.makedirs(USER_MEMORIES_DIR, exist_ok=True)

class LongTermMemory:
    def __init__(self, user_id):
        self.user_id = user_id
        self.db_path = os.path.join(USER_MEMORIES_DIR, f"user_{user_id}.db")
        self.csv_path = os.path.join(USER_MEMORIES_DIR, f"user_{user_id}_backup.csv")
        self.lock = threading.Lock()
        self.init_database()

    def init_database(self):
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event TEXT NOT NULL,
                    keywords TEXT NOT NULL,
                    importance INTEGER NOT NULL,
                    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expiry_days INTEGER NOT NULL,
                    last_mentioned TIMESTAMP
                )
            ''')
            conn.commit()
            conn.close()

    def load_valid_memories(self):
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM memories 
                WHERE importance >= 30 
                AND (expiry_days = 365 OR create_time >= datetime('now', '-' || expiry_days || ' days'))
            ''')
            memories = cursor.fetchall()
            conn.close()
            return memories

    def match_keywords(self, input_keywords, max_matches=2):
        matched = []
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM memories WHERE importance >= 50")
            memories = cursor.fetchall()
            
            for mem in memories:
                mem_id, event, keywords, imp, create_time, expiry, last_mention = mem
                if any(kw in keywords for kw in input_keywords):
                    matched.append(mem)
                    if len(matched) >= max_matches:
                        break
            conn.close()
        return matched

    def update_last_mentioned(self, memory_id):
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE memories SET last_mentioned = CURRENT_TIMESTAMP WHERE id = ?",
                (memory_id,)
            )
            conn.commit()
            conn.close()

    def update_memories(self, new_memories):
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT id, importance, last_mentioned FROM memories")
            all_mem = cursor.fetchall()
            for mem_id, imp, last_mention in all_mem:
                if last_mention and datetime.fromisoformat(last_mention) >= datetime.now() - timedelta(days=7):
                    new_imp = imp * 0.98
                else:
                    new_imp = imp * 0.95
                cursor.execute("UPDATE memories SET importance = ? WHERE id = ?", (new_imp, mem_id))
            
            for mem in new_memories:
                event, keywords, importance, expiry_days = mem
                cursor.execute("SELECT id, importance FROM memories WHERE event LIKE ?", (f"%{event.split(' ')[1]}%",))
                duplicates = cursor.fetchall()
                if duplicates:
                    for dup_id, dup_imp in duplicates:
                        if importance > dup_imp:
                            cursor.execute("DELETE FROM memories WHERE id = ?", (dup_id,))
                cursor.execute('''
                    INSERT INTO memories (event, keywords, importance, expiry_days)
                    VALUES (?, ?, ?, ?)
                ''', (event, keywords, importance, expiry_days))
            
            cursor.execute("DELETE FROM memories WHERE importance < 10")
            cursor.execute('''
                DELETE FROM memories 
                WHERE expiry_days != 365 
                AND create_time < datetime('now', '-' || expiry_days || ' days')
                AND last_mentioned < datetime('now', '-7 days')
            ''')
            
            conn.commit()
            conn.close()
        
        self.sync_to_csv()

    def sync_to_csv(self):
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM memories")
            rows = cursor.fetchall()
            conn.close()
            
            with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['id', 'event', 'keywords', 'importance', 'create_time', 'expiry_days', 'last_mentioned'])
                writer.writerows(rows)

