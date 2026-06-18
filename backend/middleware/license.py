from functools import wraps
from flask import request, jsonify
from models.license import LicenseModel
import datetime

EXEMPT_PATHS = ['/api/license/machine-code', '/api/license/activate', '/api/license/status', '/api/auth/login', '/api/auth/me']

def check_license():
    """
    检查授权状态，未激活或已过期返回410
    只检查 /api/ 开头的接口，前端静态页面和激活页需要能正常加载
    """
    path = request.path
    # 只检查 API 接口
    if not path.startswith('/api/'):
        return None
    # 豁免路径不需要检查授权
    if any(path.startswith(p) for p in EXEMPT_PATHS):
        return None
    
    license_info = LicenseModel.get_license()
    if not license_info or not license_info.get('activated'):
        return jsonify({'code': 410, 'message': '系统未激活，请先激活'}), 410
    
    # 检查有效期
    expire_date = license_info.get('expire_date', '')
    if expire_date:
        try:
            if datetime.datetime.strptime(expire_date, '%Y-%m-%d').date() < datetime.date.today():
                return jsonify({'code': 410, 'message': '授权已过期，请重新激活'}), 410
        except ValueError:
            pass
    
    return None

def license_required(fn):
    """授权验证装饰器"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        result = check_license()
        if result:
            return result
        return fn(*args, **kwargs)
    return wrapper
