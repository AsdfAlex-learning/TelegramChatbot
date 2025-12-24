import sqlite3
import csv
import time
from datetime import datetime, timedelta
import threading

class LongTermMemory:
    def __init__(self, user_id):
        self.user_id = user_id
        self.db_path = f"user_{user_id}.db"
        self.csv_path = f"user_{user_id}_backup.csv"
        self.lock = threading.Lock()  # 线程安全锁
        self.init_database()  # 初始化数据库表

    # 1. 初始化数据库表（若不存在）
    def init_database(self):
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event TEXT NOT NULL,  # 事件（格式：YYYY-MM-DD + 具体事件）
                    keywords TEXT NOT NULL,  # 关键词（逗号分隔）
                    importance INTEGER NOT NULL,  # 重要程度(0-100)
                    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expiry_days INTEGER NOT NULL,  # 有效期（天，如365=永久）
                    last_mentioned TIMESTAMP
                )
            ''')
            conn.commit()
            conn.close()

    # 2. 加载有效记忆（未过期 + 重要度≥30）
    def load_valid_memories(self):
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # 计算当前时间减去有效期，过滤未过期项
            cursor.execute('''
                SELECT * FROM memories 
                WHERE importance >= 30 
                AND (expiry_days = 365 OR create_time >= datetime('now', '-' || expiry_days || ' days'))
            ''')
            memories = cursor.fetchall()
            conn.close()
            return memories

    # 3. 关键词匹配（用于对话阶段触发记忆）
    def match_keywords(self, input_keywords, max_matches=2):
        matched = []
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # 筛选重要度≥50的记忆
            cursor.execute("SELECT * FROM memories WHERE importance >= 50")
            memories = cursor.fetchall()
            
            for mem in memories:
                mem_id, event, keywords, imp, create_time, expiry, last_mention = mem
                # 模糊匹配关键词（包含任一关键词即可）
                if any(kw in keywords for kw in input_keywords):
                    # 检查频率控制（至少间隔5轮对话，需结合对话轮数记录）
                    matched.append(mem)
                    if len(matched) >= max_matches:
                        break
            conn.close()
        return matched

    # 4. 更新记忆（衰减旧记忆 + 插入新记忆 + 去重 + 同步CSV）
    def update_memories(self, new_memories):
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 旧记忆衰减
            cursor.execute("SELECT id, importance, last_mentioned FROM memories")
            all_mem = cursor.fetchall()
            for mem_id, imp, last_mention in all_mem:
                # 计算衰减系数（7天内提及过则衰减更慢）
                if last_mention and datetime.fromisoformat(last_mention) >= datetime.now() - timedelta(days=7):
                    new_imp = imp * 0.98
                else:
                    new_imp = imp * 0.95
                cursor.execute("UPDATE memories SET importance = ? WHERE id = ?", (new_imp, mem_id))
            
            # 插入新记忆（去重：保留最新且重要度最高的）
            for mem in new_memories:
                event, keywords, importance, expiry_days = mem
                # 检查重复事件
                cursor.execute("SELECT id, importance FROM memories WHERE event LIKE ?", (f"%{event.split(' ')[1]}%",))
                duplicates = cursor.fetchall()
                if duplicates:
                    # 比较重要度，保留更高的
                    for dup_id, dup_imp in duplicates:
                        if importance > dup_imp:
                            cursor.execute("DELETE FROM memories WHERE id = ?", (dup_id,))
                # 插入新记忆
                cursor.execute('''
                    INSERT INTO memories (event, keywords, importance, expiry_days)
                    VALUES (?, ?, ?, ?)
                ''', (event, keywords, importance, expiry_days))
            
            # 删除低价值记忆（重要度<10或过期）
            cursor.execute("DELETE FROM memories WHERE importance < 10")
            cursor.execute('''
                DELETE FROM memories 
                WHERE expiry_days != 365 
                AND create_time < datetime('now', '-' || expiry_days || ' days')
                AND last_mentioned < datetime('now', '-7 days')
            ''')
            
            conn.commit()
            conn.close()
        
        # 同步到CSV备份
        self.sync_to_csv()

    # 5. 同步SQLite数据到CSV
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