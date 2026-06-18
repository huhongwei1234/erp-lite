from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from middleware.auth import admin_required
import sqlite3
from config import DB_PATH
from utils.logger import log_action

company_bp = Blueprint('company', __name__, url_prefix='/api/company')

@company_bp.route('', methods=['GET'])
@jwt_required()
def get_company():
    """获取公司信息"""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM company LIMIT 1')
    row = cursor.fetchone()
    conn.close()
    if not row:
        return jsonify({'code': 200, 'data': {}})
    return jsonify({'code': 200, 'data': dict(row)})

@company_bp.route('', methods=['PUT'])
@jwt_required()
@admin_required
def update_company():
    """更新公司信息"""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM company')
    cursor.execute('''
        INSERT INTO company (name, address, phone, email, tax_no, bank, account, remark)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (data.get('name', ''), data.get('address', ''), data.get('phone', ''), data.get('email', ''),
          data.get('tax_no', ''), data.get('bank', ''), data.get('account', ''), data.get('remark', '')))
    conn.commit()
    conn.close()
    log_action(user_id, '更新公司信息', '')
    return jsonify({'code': 200, 'message': '保存成功'})

@company_bp.route('/users', methods=['GET'])
@jwt_required()
def list_users():
    """用户列表"""
    from models.user import UserModel
    users = UserModel.list_all()
    return jsonify({'code': 200, 'data': users})

@company_bp.route('/users', methods=['POST'])
@jwt_required()
@admin_required
def create_user():
    """新增用户"""
    import bcrypt
    user_id = int(get_jwt_identity())
    data = request.get_json()
    from models.user import UserModel
    if not data.get('username') or not data.get('password'):
        return jsonify({'code': 400, 'message': '用户名和密码不能为空'})
    if UserModel.get_by_username(data['username']):
        return jsonify({'code': 400, 'message': '用户名已存在'})
    password_hash = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    module_actions = data.get('module_actions') or {}
    def _global(action):
        if module_actions:
            return int(any(actions.get(action) for actions in module_actions.values()))
        return int(data.get(action, 0))
    new_id = UserModel.create(
        data['username'],
        password_hash,
        data.get('name', ''),
        data.get('role', 'viewer'),
        data.get('permissions'),
        module_actions,
        _global('can_create'),
        _global('can_edit'),
        _global('can_delete'),
        _global('can_download'),
        _global('can_approve'),
        _global('can_handle'),
        _global('can_receive'),
        _global('can_return')
    )
    log_action(user_id, '新增用户', f"新增用户: {data['username']}")
    return jsonify({'code': 200, 'message': '新增成功', 'data': {'id': new_id}})

@company_bp.route('/users/<int:target_id>', methods=['PUT'])
@jwt_required()
@admin_required
def update_user(target_id):
    """修改用户信息（角色、权限、姓名、编辑/下载权限）"""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    from models.user import UserModel
    if target_id == user_id:
        # 不允许通过此接口修改自己的角色/权限
        forbidden_keys = ['role', 'permissions', 'module_actions', 'can_create', 'can_edit', 'can_delete', 'can_download', 'can_approve', 'can_handle', 'can_receive', 'can_return']
        if any(k in data for k in forbidden_keys):
            return jsonify({'code': 400, 'message': '不能修改自己的角色或权限'})
        # 允许自己修改 theme
        pass
    UserModel.update(target_id, data)
    log_action(user_id, '修改用户', f"修改用户ID: {target_id}")
    return jsonify({'code': 200, 'message': '修改成功'})

@company_bp.route('/users/<int:user_id>', methods=['DELETE'])
@jwt_required()
@admin_required
def delete_user(user_id):
    """删除用户"""
    current_user_id = int(get_jwt_identity())
    from models.user import UserModel
    if user_id == current_user_id:
        return jsonify({'code': 400, 'message': '不能删除当前登录用户'})
    UserModel.delete(user_id)
    log_action(current_user_id, '删除用户', f'删除用户ID: {user_id}')
    return jsonify({'code': 200, 'message': '删除成功'})
