from models.db import get_db_connection

class CustomerModel:
    @staticmethod
    def get_by_id(customer_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM customers WHERE id = ?', (customer_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def list_all(keyword=''):
        conn = get_db_connection()
        cursor = conn.cursor()
        sql = 'SELECT * FROM customers WHERE 1=1'
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
            INSERT INTO customers (name, contact, phone, address, remark)
            VALUES (?, ?, ?, ?, ?)
        ''', (data['name'], data.get('contact', ''), data.get('phone', ''), data.get('address', ''), data.get('remark', '')))
        conn.commit()
        customer_id = cursor.lastrowid
        conn.close()
        return customer_id

    @staticmethod
    def update(customer_id, data):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE customers SET name=?, contact=?, phone=?, address=?, remark=?
            WHERE id=?
        ''', (data['name'], data.get('contact', ''), data.get('phone', ''), data.get('address', ''), data.get('remark', ''), customer_id))
        conn.commit()
        conn.close()

    @staticmethod
    def delete(customer_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM customers WHERE id = ?', (customer_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def get_receivable(customer_id):
        """获取客户应收金额"""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT SUM(amount) as total FROM financials 
            WHERE party_type = 'customer' AND party_id = ? AND type = 'receivable' AND status = 'unpaid'
        ''', (customer_id,))
        row = cursor.fetchone()
        conn.close()
        return row['total'] or 0
