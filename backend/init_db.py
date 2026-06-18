import sqlite3
import os
import json
import sys
import bcrypt

# 设置 Python 路径，确保能导入 middleware
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DB_PATH, DEFAULT_ADMIN, DEFAULT_USERS
from middleware.auth import DEFAULT_PERMISSIONS, DEFAULT_MODULE_ACTIONS, compute_global_actions

def init_db():
    """初始化数据库：创建表结构和默认数据"""
    # 确保数据目录存在
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    
    # 1. 公司信息表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS company (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            address TEXT,
            phone TEXT,
            email TEXT,
            tax_no TEXT,
            bank TEXT,
            account TEXT,
            remark TEXT
        )
    ''')
    
    # 2. 用户表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT,
            role TEXT DEFAULT 'viewer',
            permissions TEXT,
            module_actions TEXT,
            can_edit INTEGER DEFAULT 0,
            can_download INTEGER DEFAULT 0,
            theme TEXT DEFAULT 'dark-blue',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # 兼容：为已有数据库添加新字段
    for col in ['permissions', 'module_actions', 'can_create', 'can_edit', 'can_delete', 'can_download', 'can_approve', 'can_handle', 'can_receive', 'can_return', 'can_delete_purchase', 'can_delete_sale', 'theme', 'session_id']:
        try:
            if col in ['permissions', 'module_actions']:
                cursor.execute(f'ALTER TABLE users ADD COLUMN {col} TEXT')
            elif col == 'theme':
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT DEFAULT 'dark-blue'")
            else:
                cursor.execute(f'ALTER TABLE users ADD COLUMN {col} INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass  # 字段已存在
    
    # 3. 供应商表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code_prefix TEXT,
            contact TEXT,
            phone TEXT,
            address TEXT,
            remark TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # 兼容：为已有 suppliers 表添加 code_prefix 字段
    try:
        cursor.execute("ALTER TABLE suppliers ADD COLUMN code_prefix TEXT")
    except sqlite3.OperationalError:
        pass
    
    # 4. 客户表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact TEXT,
            phone TEXT,
            address TEXT,
            remark TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 5. 商品分类表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 6. 商品表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            category_id INTEGER,
            supplier_id INTEGER,
            spec TEXT,
            unit TEXT DEFAULT '件',
            price REAL DEFAULT 0,
            cost REAL DEFAULT 0,
            stock INTEGER DEFAULT 0,
            tax_rate REAL DEFAULT 13,
            is_tax_included INTEGER DEFAULT 1,
            remark TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # 兼容：为已有 products 表添加 supplier_id 字段
    try:
        cursor.execute("ALTER TABLE products ADD COLUMN supplier_id INTEGER")
    except sqlite3.OperationalError:
        pass
    
    # 7. 出入库记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            order_no TEXT,
            product_id INTEGER,
            quantity INTEGER,
            price REAL,
            total REAL,
            party_type TEXT,
            party_id INTEGER,
            party_name TEXT,
            operator TEXT,
            delivery_type TEXT,
            tax_rate REAL DEFAULT 13,
            is_tax_included INTEGER DEFAULT 0,
            remark TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 兼容：为已有 records 表添加 payment_type 和 item_remark 字段
    try:
        cursor.execute("ALTER TABLE records ADD COLUMN payment_type TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE records ADD COLUMN item_remark TEXT")
    except sqlite3.OperationalError:
        pass
    # 8. 财务流水表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS financials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            amount REAL DEFAULT 0,
            party_type TEXT,
            party_id INTEGER,
            party_name TEXT,
            status TEXT DEFAULT 'unpaid',
            remark TEXT,
            order_no TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # 兼容：为已有 financials 表添加 order_no 字段
    try:
        cursor.execute("ALTER TABLE financials ADD COLUMN order_no TEXT")
    except sqlite3.OperationalError:
        pass
    
    # 9. 授权表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS license (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_code TEXT,
            license_key TEXT,
            expire_date TEXT,
            activated INTEGER DEFAULT 0
        )
    ''')
    
    # 10. 费用报销表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            amount REAL DEFAULT 0,
            description TEXT,
            applicant TEXT,
            operator TEXT,
            status TEXT DEFAULT 'pending',
            remark TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 兼容：为已有 records 表添加 delivery_type / tax_rate / is_tax_included / project_name / payment_type / item_remark 字段
    for col_def in ["delivery_type TEXT", "tax_rate REAL DEFAULT 13", "is_tax_included INTEGER DEFAULT 0", "project_name TEXT", "payment_type TEXT", "item_remark TEXT"]:
        try:
            cursor.execute(f"ALTER TABLE records ADD COLUMN {col_def}")
        except sqlite3.OperationalError:
            pass

    # 兼容：为已有 expenses 表添加 operator 字段
    try:
        cursor.execute("ALTER TABLE expenses ADD COLUMN operator TEXT")
    except sqlite3.OperationalError:
        pass
    
    # 兼容：为已有 expenses 表添加 handled_at 字段（办理日期）
    try:
        cursor.execute("ALTER TABLE expenses ADD COLUMN handled_at TEXT")
    except sqlite3.OperationalError:
        pass
    
    # 11. 公告表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT,
            visible INTEGER DEFAULT 1,
            pinned INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 12. 系统日志表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            detail TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 13. 备份设置表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS backup_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            enabled INTEGER DEFAULT 0,
            interval_hours INTEGER DEFAULT 24,
            target_path TEXT,
            last_backup_at TEXT,
            last_status TEXT DEFAULT 'none',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 插入/更新默认账号（按角色写入默认页面权限及按页面操作权限）
    def _ensure_default_user(user_info):
        username = user_info['username']
        role = user_info['role']
        cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        row = cursor.fetchone()
        permissions = DEFAULT_PERMISSIONS.get(role, [])
        # DEFAULT_MODULE_ACTIONS 是 list 形式，转换为数据库存储的 dict 形式
        raw_module_actions = DEFAULT_MODULE_ACTIONS.get(role, {})
        module_actions = {
            mod: {action: True for action in actions}
            for mod, actions in raw_module_actions.items()
        }
        global_actions = compute_global_actions(module_actions)
        values = {
            'name': user_info['name'],
            'role': role,
            'permissions': json.dumps(permissions, ensure_ascii=False),
            'module_actions': json.dumps(module_actions, ensure_ascii=False),
            **global_actions
        }
        if not row:
            password_hash = bcrypt.hashpw(user_info['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            columns = ['username', 'password'] + list(values.keys())
            placeholders = ', '.join(['?'] * len(columns))
            cursor.execute(
                f"INSERT INTO users ({', '.join(columns)}) VALUES ({placeholders})",
                [username, password_hash] + list(values.values())
            )
            print(f'默认用户已创建: {username} / {user_info["password"]}')
        else:
            # 仅对默认账号补齐/同步默认权限（避免覆盖用户手动调整的其他账号）
            sets = ', '.join([f'{k} = ?' for k in values.keys()])
            cursor.execute(
                f'UPDATE users SET {sets} WHERE username = ?',
                list(values.values()) + [username]
            )
            print(f'默认用户已同步: {username}')

    _ensure_default_user(DEFAULT_ADMIN)
    for user in DEFAULT_USERS:
        _ensure_default_user(user)
    
    conn.commit()
    conn.close()
    print('数据库初始化完成')

if __name__ == '__main__':
    init_db()
