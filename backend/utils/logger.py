import sqlite3
import datetime
from config import DB_PATH

def log_action(user_id, action, detail=''):
    """
    记录系统操作日志
    """
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO logs (user_id, action, detail, created_at)
            VALUES (?, ?, ?, ?)
        ''', (user_id, action, detail, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f'日志记录失败: {e}')
