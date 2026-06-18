from models.db import get_db_connection

class ProductModel:
    @staticmethod
    def get_by_code(code):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM products WHERE code = ?', (code,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_by_id(product_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.*, s.name as supplier_name, s.code_prefix as supplier_code_prefix
            FROM products p 
            LEFT JOIN suppliers s ON p.supplier_id = s.id
            WHERE p.id = ?
        ''', (product_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def list_all(keyword='', category_id=None, supplier_id=None):
        conn = get_db_connection()
        cursor = conn.cursor()
        sql = '''
            SELECT p.*, s.name as supplier_name, s.code_prefix as supplier_code_prefix
            FROM products p 
            LEFT JOIN suppliers s ON p.supplier_id = s.id
            WHERE 1=1
        '''
        params = []
        if keyword:
            sql += ' AND (p.name LIKE ? OR p.code LIKE ? OR p.spec LIKE ?)'
            params.extend([f'%{keyword}%', f'%{keyword}%', f'%{keyword}%'])
        if category_id:
            sql += ' AND p.category_id = ?'
            params.append(category_id)
        if supplier_id:
            sql += ' AND p.supplier_id = ?'
            params.append(supplier_id)
        sql += ' ORDER BY p.id DESC'
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def create(data):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO products (code, name, supplier_id, spec, unit, price_excl, price_incl, cost_excl, cost_incl, stock, tax_rate, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (data['code'], data['name'], data.get('supplier_id'), data.get('spec', ''),
              data.get('unit', '件'), data.get('price_excl', 0), data.get('price_incl', 0),
              data.get('cost_excl', 0), data.get('cost_incl', 0), data.get('stock', 0),
              data.get('tax_rate', 13), data.get('remark', '')))
        conn.commit()
        product_id = cursor.lastrowid
        conn.close()
        return product_id

    @staticmethod
    def update(product_id, data):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE products SET code=?, name=?, supplier_id=?, spec=?, unit=?, price_excl=?, price_incl=?, cost_excl=?, cost_incl=?, tax_rate=?, remark=?
            WHERE id=?
        ''', (data['code'], data['name'], data.get('supplier_id'), data.get('spec', ''),
              data.get('unit', '件'), data.get('price_excl', 0), data.get('price_incl', 0),
              data.get('cost_excl', 0), data.get('cost_incl', 0),
              data.get('tax_rate', 13), data.get('remark', ''), product_id))
        conn.commit()
        conn.close()

    @staticmethod
    def get_count_by_supplier(supplier_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) as cnt FROM products WHERE supplier_id = ?', (supplier_id,))
        row = cursor.fetchone()
        conn.close()
        return row['cnt'] if row else 0

    @staticmethod
    def update_stock(product_id, quantity):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE products SET stock = stock + ? WHERE id = ?', (quantity, product_id))
        conn.commit()
        conn.close()

    @staticmethod
    def update_prices(product_id, cost_excl=None, price_excl=None, price_incl=None):
        conn = get_db_connection()
        cursor = conn.cursor()
        fields = []
        params = []
        if cost_excl is not None:
            fields.append('cost_excl = ?')
            params.append(cost_excl)
        if price_excl is not None:
            fields.append('price_excl = ?')
            params.append(price_excl)
        if price_incl is not None:
            fields.append('price_incl = ?')
            params.append(price_incl)
        if fields:
            sql = f"UPDATE products SET {', '.join(fields)} WHERE id = ?"
            params.append(product_id)
            cursor.execute(sql, params)
            conn.commit()
        conn.close()

    @staticmethod
    def delete(product_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM products WHERE id = ?', (product_id,))
        conn.commit()
        conn.close()

class CategoryModel:
    @staticmethod
    def list_all():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM categories ORDER BY id DESC')
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def create(name):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO categories (name) VALUES (?)', (name,))
        conn.commit()
        category_id = cursor.lastrowid
        conn.close()
        return category_id

    @staticmethod
    def delete(category_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM categories WHERE id = ?', (category_id,))
        conn.commit()
        conn.close()
