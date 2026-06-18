from models.db import get_db_connection
import datetime

class FinancialModel:
    @staticmethod
    def get_by_id(fin_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM financials WHERE id = ?', (fin_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def list_all(fin_type=None, status=None, party_type=None, start_date=None, end_date=None, keyword='', payment_method=None):
        conn = get_db_connection()
        cursor = conn.cursor()
        sql = 'SELECT * FROM financials WHERE 1=1'
        params = []
        if fin_type:
            sql += ' AND type = ?'
            params.append(fin_type)
        if status:
            sql += ' AND status = ?'
            params.append(status)
        if party_type:
            sql += ' AND party_type = ?'
            params.append(party_type)
        if payment_method:
            sql += ' AND payment_method = ?'
            params.append(payment_method)
        if start_date:
            sql += ' AND created_at >= ?'
            params.append(start_date)
        if end_date:
            sql += ' AND created_at <= ?'
            params.append(end_date + ' 23:59:59')
        if keyword:
            sql += ' AND (party_name LIKE ? OR remark LIKE ?)'
            params.extend([f'%{keyword}%', f'%{keyword}%'])
        sql += ' ORDER BY id DESC'
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
            INSERT INTO financials (type, amount, party_type, party_id, party_name, status, remark, order_no, payment_method, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (data['type'], data['amount'], data.get('party_type', ''), data.get('party_id'), data.get('party_name', ''),
              data.get('status', 'unpaid'), data.get('remark', ''), data.get('order_no', ''), data.get('payment_method', ''), now))
        conn.commit()
        fin_id = cursor.lastrowid
        conn.close()
        return fin_id

    @staticmethod
    def update_status(fin_id, status):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE financials SET status = ? WHERE id = ?', (status, fin_id))
        conn.commit()
        conn.close()

    @staticmethod
    def delete(fin_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM financials WHERE id = ?', (fin_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def delete_by_order_no(order_no):
        """根据关联单号删除财务记录"""
        if not order_no:
            return
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM financials WHERE order_no = ?", (order_no,))
        conn.commit()
        conn.close()

    @staticmethod
    def update_amount_by_order_no(order_no, amount):
        """根据关联单号更新财务记录金额"""
        if not order_no:
            return
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE financials SET amount = ? WHERE order_no = ?", (amount, order_no))
        conn.commit()
        conn.close()

    @staticmethod
    def get_pending_count():
        """获取未处理的应收应付数量"""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT type, COUNT(*) as cnt FROM financials WHERE status = 'unpaid' AND type IN ('receivable', 'payable') GROUP BY type")
        rows = cursor.fetchall()
        conn.close()
        return {row['type']: row['cnt'] for row in rows}

    @staticmethod
    def get_cash_flow(start_date=None, end_date=None):
        """获取收支流水统计"""
        conn = get_db_connection()
        cursor = conn.cursor()
        sql = '''
            SELECT type, SUM(amount) as total FROM financials 
            WHERE status = 'paid'
        '''
        params = []
        if start_date:
            sql += ' AND created_at >= ?'
            params.append(start_date)
        if end_date:
            sql += ' AND created_at <= ?'
            params.append(end_date + ' 23:59:59')
        sql += ' GROUP BY type'
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        return {row['type']: row['total'] or 0 for row in rows}
