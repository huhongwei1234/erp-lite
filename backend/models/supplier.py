from models.db import get_db_connection

class SupplierModel:
    @staticmethod
    def get_by_code_prefix(code_prefix):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM suppliers WHERE code_prefix = ?', (code_prefix,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_by_id(supplier_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM suppliers WHERE id = ?', (supplier_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_by_name(name):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM suppliers WHERE name = ?', (name,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def list_all(keyword=''):
        conn = get_db_connection()
        cursor = conn.cursor()
        sql = 'SELECT * FROM suppliers WHERE 1=1'
        params = []
        if keyword:
            sql += ' AND (name LIKE ? OR contact LIKE ? OR phone LIKE ? OR address LIKE ?)'
            params.extend([f'%{keyword}%', f'%{keyword}%', f'%{keyword}%', f'%{keyword}%'])
        sql += ' ORDER BY id DESC'
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def create(data):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO suppliers (name, code_prefix, contact, phone, address, remark)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (data['name'], data.get('code_prefix', ''), data.get('contact', ''), data.get('phone', ''), data.get('address', ''), data.get('remark', '')))
        conn.commit()
        supplier_id = cursor.lastrowid
        conn.close()
        return supplier_id

    @staticmethod
    def update(supplier_id, data):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE suppliers SET name=?, code_prefix=?, contact=?, phone=?, address=?, remark=?
            WHERE id=?
        ''', (data['name'], data.get('code_prefix', ''), data.get('contact', ''), data.get('phone', ''), data.get('address', ''), data.get('remark', ''), supplier_id))
        conn.commit()
        conn.close()

    @staticmethod
    def delete(supplier_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM suppliers WHERE id = ?', (supplier_id,))
        conn.commit()
        conn.close()
