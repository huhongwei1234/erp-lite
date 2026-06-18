import sqlite3
import shutil
import os
from datetime import datetime
from models.db import get_db_connection

DB_PATH = os.environ.get('DB_PATH', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'erp.db'))

class BackupModel:
    @staticmethod
    def get_settings():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM backup_settings ORDER BY id DESC LIMIT 1')
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def save_settings(data):
        conn = get_db_connection()
        cursor = conn.cursor()
        settings = BackupModel.get_settings()
        if settings:
            cursor.execute('''
                UPDATE backup_settings SET enabled=?, interval_hours=?, target_path=? WHERE id=?
            ''', (int(data.get('enabled', 0)), int(data.get('interval_hours', 24)), data.get('target_path', ''), settings['id']))
        else:
            cursor.execute('''
                INSERT INTO backup_settings (enabled, interval_hours, target_path)
                VALUES (?, ?, ?)
            ''', (int(data.get('enabled', 0)), int(data.get('interval_hours', 24)), data.get('target_path', '')))
        conn.commit()
        conn.close()
        return True

    @staticmethod
    def update_last_status(status, backup_at=None):
        conn = get_db_connection()
        cursor = conn.cursor()
        settings = BackupModel.get_settings()
        if settings:
            cursor.execute('''
                UPDATE backup_settings SET last_status=?, last_backup_at=? WHERE id=?
            ''', (status, backup_at or datetime.now().strftime('%Y-%m-%d %H:%M:%S'), settings['id']))
            conn.commit()
        conn.close()
        return True

    @staticmethod
    def do_backup(target_path):
        """执行备份，返回 (success, message)"""
        if not target_path:
            return False, '未设置备份目标路径'
        target_path = os.path.expanduser(target_path)
        try:
            os.makedirs(target_path, exist_ok=True)
        except Exception as e:
            return False, f'无法创建备份目录: {e}'
        
        if not os.path.exists(DB_PATH):
            return False, '数据库文件不存在'
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f'erp_backup_{timestamp}.db'
        backup_path = os.path.join(target_path, backup_name)
        
        try:
            shutil.copy2(DB_PATH, backup_path)
            return True, backup_path
        except Exception as e:
            return False, f'备份失败: {e}'
