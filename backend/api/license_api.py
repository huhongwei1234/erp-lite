from flask import Blueprint, request, jsonify
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
import base64
import datetime
from models.license import LicenseModel
from utils.machine_code import get_machine_code
from config import RSA_PUBLIC_PATH

license_bp = Blueprint('license', __name__, url_prefix='/api/license')

def load_public_key():
    """加载RSA公钥"""
    with open(RSA_PUBLIC_PATH, 'rb') as f:
        return serialization.load_pem_public_key(f.read())

@license_bp.route('/machine-code', methods=['GET'])
def get_machine_code_api():
    """获取机器码"""
    return jsonify({'code': 200, 'data': {'machine_code': get_machine_code()}})

@license_bp.route('/activate', methods=['POST'])
def activate():
    """激活系统"""
    data = request.get_json()
    license_key = data.get('license_key', '')
    
    if not license_key:
        return jsonify({'code': 400, 'message': '激活码不能为空'})
    
    try:
        # 解码激活码
        payload = base64.b64decode(license_key).decode('utf-8')
        # 格式: machine_code|expire_date|base64_signature
        parts = payload.split('|')
        if len(parts) != 3:
            return jsonify({'code': 400, 'message': '激活码格式无效'})
        
        mc, expire_date, sig_b64 = parts
        signature = base64.b64decode(sig_b64)
        
        # 验证机器码
        if mc != get_machine_code():
            return jsonify({'code': 400, 'message': '激活码与当前设备不匹配'})
        
        # 使用RSA公钥验证签名
        content = f"{mc}|{expire_date}".encode('utf-8')
        public_key = load_public_key()
        public_key.verify(signature, content, padding.PKCS1v15(), hashes.SHA256())
        
        # 验证有效期
        if datetime.datetime.strptime(expire_date, '%Y-%m-%d').date() < datetime.date.today():
            return jsonify({'code': 400, 'message': '激活码已过期'})
        
        # 保存授权信息
        LicenseModel.save(mc, license_key, expire_date)
        
        return jsonify({'code': 200, 'message': '激活成功', 'data': {'expire_date': expire_date}})
    except Exception as e:
        return jsonify({'code': 400, 'message': f'激活失败: {str(e)}'})

@license_bp.route('/status', methods=['GET'])
def get_status():
    """获取授权状态"""
    license_info = LicenseModel.get_license()
    if not license_info or not license_info.get('activated'):
        response = jsonify({'code': 200, 'data': {'activated': False}})
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, proxy-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    
    # 检查是否过期
    expire_date = license_info.get('expire_date', '')
    is_expired = datetime.datetime.strptime(expire_date, '%Y-%m-%d').date() < datetime.date.today()
    
    response = jsonify({
        'code': 200,
        'data': {
            'activated': not is_expired,
            'expire_date': expire_date,
            'machine_code': license_info.get('machine_code', '')
        }
    })
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, proxy-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response
