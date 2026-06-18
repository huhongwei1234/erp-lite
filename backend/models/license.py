from models.db import get_db_connection

class LicenseModel:
    @staticmethod
    def get_license():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM license LIMIT 1')
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def save(machine_code, license_key, expire_date):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM license')
        cursor.execute('''
            INSERT INTO license (machine_code, license_key, expire_date, activated)
            VALUES (?, ?, ?, 1)
        ''', (machine_code, license_key, expire_date))
        conn.commit()
        conn.close()

    @staticmethod
    def clear():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM license')
        conn.commit()
        conn.close()
