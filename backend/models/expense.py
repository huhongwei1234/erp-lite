from models.db import get_db_connection


class ExpenseModel:
    @staticmethod
    def list_all(status=None, expense_type=None, start_date=None, end_date=None, keyword=''):
        conn = get_db_connection()
        cursor = conn.cursor()
        sql = 'SELECT * FROM expenses WHERE 1=1'
        params = []
        if status:
            sql += ' AND status = ?'
            params.append(status)
        if expense_type:
            sql += ' AND type = ?'
            params.append(expense_type)
        if start_date:
            sql += ' AND date(created_at) >= date(?)'
            params.append(start_date)
        if end_date:
            sql += ' AND date(created_at) <= date(?)'
            params.append(end_date)
        if keyword:
            sql += ' AND (applicant LIKE ? OR description LIKE ? OR remark LIKE ? OR type LIKE ?)'
            params.extend([f'%{keyword}%', f'%{keyword}%', f'%{keyword}%', f'%{keyword}%'])
        sql += ' ORDER BY id DESC'
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_by_id(expense_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM expenses WHERE id = ?', (expense_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def create(data):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO expenses (type, amount, description, applicant, operator, status, remark, handled_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (data.get('type', ''), data.get('amount', 0), data.get('description', ''),
              data.get('applicant', ''), data.get('operator', ''), data.get('status', 'pending'), data.get('remark', ''), data.get('handled_at', '')))
        conn.commit()
        expense_id = cursor.lastrowid
        conn.close()
        return expense_id

    @staticmethod
    def update(expense_id, data):
        conn = get_db_connection()
        cursor = conn.cursor()
        fields = []
        values = []
        for key in ['type', 'amount', 'description', 'applicant', 'operator', 'status', 'remark', 'handled_at']:
            if key in data:
                fields.append(f'{key} = ?')
                values.append(data[key])
        if not fields:
            conn.close()
            return False
        values.append(expense_id)
        cursor.execute(f"UPDATE expenses SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
        conn.close()
        return True

    @staticmethod
    def delete(expense_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM expenses WHERE id = ?', (expense_id,))
        conn.commit()
        conn.close()
