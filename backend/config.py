import os

# 项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)

# 数据库配置
DB_PATH = os.path.join(PROJECT_DIR, 'data', 'erp.db')

# JWT配置
JWT_SECRET_KEY = 'erp-lite-jwt-secret-key-2024-change-me-in-production-env'
JWT_ACCESS_TOKEN_EXPIRES = 86400  # 24小时

# RSA公钥路径
RSA_PUBLIC_PATH = os.path.join(BASE_DIR, 'rsa_public.pem')

# 默认管理员账号
DEFAULT_ADMIN = {
    'username': 'admin',
    'password': 'admin123',
    'role': 'admin',
    'name': '系统管理员'
}

# 默认演示账号（按角色预置页面及操作权限）
DEFAULT_USERS = [
    {'username': '88888', 'password': '88888', 'role': 'finance', 'name': '财务'},
    {'username': '66666', 'password': '66666', 'role': 'operator', 'name': '制单员'}
]

# 库存预警阈值
STOCK_WARNING_THRESHOLD = 10
