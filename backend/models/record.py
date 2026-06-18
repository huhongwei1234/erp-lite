from models.db import get_db_connection
import datetime

class RecordModel:
    @staticmethod
    def get_by_id(record_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM records WHERE id = ?', (record_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def list_all(record_type=None, start_date=None, end_date=None, keyword=''):
        conn = get_db_connection()
        cursor = conn.cursor()
        sql = '''
            SELECT r.*, p.name as product_name, p.code as product_code, p.spec as product_spec
            FROM records r
            LEFT JOIN products p ON r.product_id = p.id
            WHERE 1=1
        '''
        params = []
        if record_type:
            sql += ' AND r.type = ?'
            params.append(record_type)
        if start_date:
            sql += ' AND r.created_at >= ?'
            params.append(start_date)
        if end_date:
            sql += ' AND r.created_at <= ?'
            params.append(end_date + ' 23:59:59')
        if keyword:
            sql += ' AND (p.name LIKE ? OR p.code LIKE ? OR p.spec LIKE ? OR r.order_no LIKE ? OR r.party_name LIKE ? OR r.operator LIKE ? OR r.remark LIKE ?)'
            params.extend([f'%{keyword}%', f'%{keyword}%', f'%{keyword}%', f'%{keyword}%', f'%{keyword}%', f'%{keyword}%', f'%{keyword}%'])
        sql += ' ORDER BY r.id DESC'
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def create(data):
        conn = get_db_connection()
        cursor = conn.cursor()
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            INSERT INTO records (type, order_no, product_id, quantity, price, total, party_type, party_id, party_name, operator, delivery_type, tax_rate, is_tax_included, project_name, remark, payment_type, item_remark, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (data['type'], data.get('order_no', ''), data['product_id'], data['quantity'], data.get('price', 0),
              data.get('total', 0), data.get('party_type', ''), data.get('party_id'), data.get('party_name', ''),
              data.get('operator', ''), data.get('delivery_type', ''), data.get('tax_rate', 13), data.get('is_tax_included', 0), '', data.get('remark', ''), data.get('payment_type', ''), data.get('item_remark', ''), now))
        conn.commit()
        record_id = cursor.lastrowid
        conn.close()
        return record_id

    @staticmethod
    def delete(record_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM records WHERE id = ?', (record_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def get_by_order_no(order_no, exclude_id=None):
        conn = get_db_connection()
        cursor = conn.cursor()
        sql = 'SELECT * FROM records WHERE order_no = ?'
        params = [order_no]
        if exclude_id:
            sql += ' AND id != ?'
            params.append(exclude_id)
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_stock_records(product_id=None, start_date=None, end_date=None):
        """获取库存流水"""
        conn = get_db_connection()
        cursor = conn.cursor()
        sql = '''
            SELECT r.*, p.name as product_name, p.code as product_code
            FROM records r
            LEFT JOIN products p ON r.product_id = p.id
            WHERE r.type IN ('purchase_in', 'purchase_return', 'sale_out', 'sale_return', 'stock_check')
        '''
        params = []
        if product_id:
            sql += ' AND r.product_id = ?'
            params.append(product_id)
        if start_date:
            sql += ' AND r.created_at >= ?'
            params.append(start_date)
        if end_date:
            sql += ' AND r.created_at <= ?'
            params.append(end_date + ' 23:59:59')
        sql += ' ORDER BY r.id DESC'
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
