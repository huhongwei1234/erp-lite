import sqlite3
from config import DB_PATH

def get_db_connection():
    """
    获取数据库连接，设置row_factory以便通过列名访问数据
    """
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn
