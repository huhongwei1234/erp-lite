from flask import Blueprint, request, jsonify
import bcrypt
import uuid
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, get_jwt
from models.user import UserModel
from utils.logger import log_action

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route('/login', methods=['POST'])
def login():
    """用户登录接口"""
    data = request.get_json()
    username = data.get('username', '')
    password = data.get('password', '')
    
    user = UserModel.get_by_username(username)
    if not user:
        return jsonify({'code': 401, 'message': '用户名或密码错误'}), 401
    
    # 验证密码
    if not bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
        return jsonify({'code': 401, 'message': '用户名或密码错误'}), 401
    
    # 生成会话ID并存储，实现单点登录（后登录踢掉先登录的）
    session_id = str(uuid.uuid4())
    UserModel.update(user['id'], {'session_id': session_id})
    
    # 生成JWT Token（携带session_id）
    token = create_access_token(identity=str(user['id']), additional_claims={'session_id': session_id})
    
    log_action(user['id'], '登录', f'用户 {username} 登录系统')
    
    return jsonify({
        'code': 200,
        'message': '登录成功',
        'data': {
            'token': token,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'name': user['name'],
                'role': user['role'],
                'permissions': user.get('permissions', []),
                'module_actions': user.get('module_actions', {}),
                'can_create': user.get('can_create', False),
                'can_edit': user.get('can_edit', False),
                'can_delete': user.get('can_delete', False),
                'can_download': user.get('can_download', False),
                'can_approve': user.get('can_approve', False),
                'can_handle': user.get('can_handle', False),
                'can_receive': user.get('can_receive', False),
                'can_return': user.get('can_return', False),
                'theme': user.get('theme', 'dark-blue')
            }
        }
    })

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_me():
    """获取当前登录用户信息"""
    user_id = int(get_jwt_identity())
    user = UserModel.get_by_id(user_id)
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'})
    return jsonify({'code': 200, 'data': user})

@auth_bp.route('/theme', methods=['PUT'])
@jwt_required()
def update_theme():
    """修改个人主题"""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    theme = data.get('theme', 'dark-blue')
    UserModel.update(user_id, {'theme': theme})
    return jsonify({'code': 200, 'message': '主题已更新'})

@auth_bp.route('/password', methods=['PUT'])
@jwt_required()
def change_password():
    """修改密码"""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')
    
    if len(new_password) < 6:
        return jsonify({'code': 400, 'message': '新密码长度不能少于6位'})
    
    user = UserModel.get_by_id(user_id)
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'})
    # get_by_id 不返回密码，需要通过用户名获取完整信息
    full_user = UserModel.get_by_username(user['username'])
    if not full_user or not bcrypt.checkpw(old_password.encode('utf-8'), full_user['password'].encode('utf-8')):
        return jsonify({'code': 400, 'message': '原密码错误'})
    
    password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    UserModel.update_password(user_id, password_hash)
    
    log_action(user_id, '修改密码', '用户修改了登录密码')
    
    return jsonify({'code': 200, 'message': '密码修改成功'})
