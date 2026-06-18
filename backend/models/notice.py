from models.db import get_db_connection

class NoticeModel:
    @staticmethod
    def list_all():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM notices ORDER BY pinned DESC, created_at DESC
        ''')
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def list_visible():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM notices WHERE visible = 1 ORDER BY pinned DESC, created_at DESC
        ''')
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_by_id(notice_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM notices WHERE id = ?', (notice_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def create(data):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            visible = int(data.get('visible', 1))
            pinned = int(data.get('pinned', 0))
        except (ValueError, TypeError):
            visible = 1
            pinned = 0
        cursor.execute('''
            INSERT INTO notices (title, content, visible, pinned)
            VALUES (?, ?, ?, ?)
        ''', (data['title'], data.get('content', ''), visible, pinned))
        conn.commit()
        notice_id = cursor.lastrowid
        conn.close()
        return notice_id

    @staticmethod
    def update(notice_id, data):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            visible = int(data.get('visible', 1))
            pinned = int(data.get('pinned', 0))
        except (ValueError, TypeError):
            visible = 1
            pinned = 0
        cursor.execute('''
            UPDATE notices SET title=?, content=?, visible=?, pinned=? WHERE id=?
        ''', (data['title'], data.get('content', ''), visible, pinned, notice_id))
        conn.commit()
        conn.close()

    @staticmethod
    def delete(notice_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM notices WHERE id = ?', (notice_id,))
        conn.commit()
        conn.close()
