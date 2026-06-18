import json
from functools import wraps
from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from models.user import UserModel

# 所有可用权限模块
ALL_PERMISSIONS = [
    'dashboard', 'product', 'supplier', 'customer',
    'purchase', 'sale', 'inventory', 'stock_check', 'stock_records',
    'finance', 'cash_flow', 'expense', 'report', 'profit_report',
    'notice', 'settings', 'backup', 'sale_log'
]

# 各角色的默认页面权限
DEFAULT_PERMISSIONS = {
    'admin': ALL_PERMISSIONS,
    'finance': ['dashboard', 'finance', 'cash_flow', 'expense', 'report', 'profit_report'],
    'operator': ['dashboard', 'supplier', 'customer', 'product', 'purchase', 'sale', 'inventory', 'stock_check', 'stock_records', 'expense', 'report', 'profit_report'],
    'viewer': ['dashboard', 'supplier', 'customer', 'product', 'purchase', 'sale', 'inventory', 'stock_check', 'stock_records', 'finance', 'cash_flow', 'expense', 'report', 'profit_report', 'notice'],
    'salesman': ['dashboard', 'customer', 'product', 'sale', 'inventory', 'stock_check', 'stock_records', 'report', 'profit_report']
}

# 每个页面支持的操作权限
MODULE_ACTIONS = {
    'dashboard': [],
    'product': ['can_create', 'can_edit', 'can_delete', 'can_download'],
    'supplier': ['can_create', 'can_edit', 'can_delete', 'can_download'],
    'customer': ['can_create', 'can_edit', 'can_delete', 'can_download'],
    'purchase': ['can_create', 'can_edit', 'can_delete', 'can_download'],
    'sale': ['can_create', 'can_edit', 'can_delete', 'can_download', 'can_return'],
    'inventory': ['can_edit', 'can_delete', 'can_download'],
    'stock_check': ['can_create', 'can_edit', 'can_delete', 'can_download'],
    'stock_records': ['can_delete', 'can_download'],
    'finance': ['can_create', 'can_edit', 'can_delete', 'can_download', 'can_receive'],
    'cash_flow': ['can_create', 'can_edit', 'can_delete', 'can_download'],
    'expense': ['can_create', 'can_edit', 'can_delete', 'can_download', 'can_approve', 'can_handle'],
    'report': ['can_download'],
    'profit_report': ['can_download'],
    'notice': ['can_create', 'can_edit', 'can_delete'],
    'settings': ['can_create', 'can_edit', 'can_delete'],
    'backup': [],
    'sale_log': ['can_download']
}

# 各角色默认的按页面操作权限
DEFAULT_MODULE_ACTIONS = {
    'admin': {mod: list(actions) for mod, actions in MODULE_ACTIONS.items()},
    'finance': {
        'dashboard': [],
        'finance': ['can_download', 'can_receive'],
        'cash_flow': ['can_download'],
        'expense': ['can_download', 'can_approve', 'can_handle'],
        'report': ['can_download'],
        'profit_report': ['can_download']
    },
    'operator': {
        'dashboard': [],
        'supplier': ['can_create', 'can_edit', 'can_download'],
        'customer': ['can_create', 'can_edit', 'can_download'],
        'product': ['can_create', 'can_edit', 'can_download'],
        'purchase': ['can_create', 'can_edit', 'can_download'],
        'sale': ['can_create', 'can_edit', 'can_download'],
        'inventory': ['can_edit', 'can_download'],
        'stock_check': ['can_create', 'can_edit', 'can_download'],
        'stock_records': ['can_download'],
        'expense': ['can_create', 'can_edit', 'can_download'],
        'report': ['can_download'],
        'profit_report': ['can_download']
    },
    'salesman': {
        'dashboard': [],
        'customer': ['can_create', 'can_edit', 'can_download'],
        'product': ['can_create', 'can_edit', 'can_download'],
        'sale': ['can_create', 'can_edit', 'can_download', 'can_return'],
        'inventory': ['can_edit', 'can_download'],
        'stock_check': ['can_create', 'can_edit', 'can_download'],
        'stock_records': ['can_download'],
        'report': ['can_download'],
        'profit_report': ['can_download']
    },
    'viewer': {}
}


def compute_global_actions(module_actions):
    """从 module_actions 聚合出全局 can_* 标志，兼容 list/dict 两种形式"""
    actions = {
        'can_create': 0, 'can_edit': 0, 'can_delete': 0, 'can_download': 0,
        'can_approve': 0, 'can_handle': 0, 'can_receive': 0, 'can_return': 0
    }
    for mod_actions in (module_actions or {}).values():
        items = mod_actions.items() if isinstance(mod_actions, dict) else ((a, True) for a in mod_actions)
        for action, val in items:
            if val and action in actions:
                actions[action] = 1
    return actions


def role_required(allowed_roles):
    """
    角色权限装饰器
    allowed_roles: 允许访问的角色列表，如 ['admin']
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user_id = int(get_jwt_identity())
            user = UserModel.get_by_id(user_id)
            if not user or user['role'] not in allowed_roles:
                return jsonify({'code': 403, 'message': '权限不足，当前角色无法执行此操作'}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def admin_required(fn):
    """仅管理员可访问"""
    return role_required(['admin'])(fn)


def permission_required(*modules):
    """
    模块权限装饰器
    modules: 需要的权限模块，如 'finance', 'product'
    admin 自动拥有所有权限
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user_id = int(get_jwt_identity())
            user = UserModel.get_by_id(user_id)
            if not user:
                return jsonify({'code': 403, 'message': '权限不足'}), 403
            # admin 拥有所有权限
            if user['role'] == 'admin':
                return fn(*args, **kwargs)
            # 获取用户权限列表
            perms = user.get('permissions', [])
            if not perms:
                perms = DEFAULT_PERMISSIONS.get(user['role'], [])
            for module in modules:
                if module not in perms:
                    return jsonify({'code': 403, 'message': f'权限不足，缺少 {module} 模块权限'}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def create_required(fn=None, module=None):
    """新增权限装饰器：admin 或有 can_create 权限的用户。
    如果传入 module，优先按 module_actions 精确校验；当用户没有 module_actions 数据时回退到全局 can_create。"""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user_id = int(get_jwt_identity())
            user = UserModel.get_by_id(user_id)
            if not user:
                return jsonify({'code': 403, 'message': '权限不足'}), 403
            if user['role'] == 'admin':
                return fn(*args, **kwargs)
            if module:
                module_actions = user.get('module_actions') or {}
                if module_actions:
                    if UserModel.has_module_action(user, module, 'can_create'):
                        return fn(*args, **kwargs)
                    return jsonify({'code': 403, 'message': '权限不足，无该页面的新增权限'}), 403
                if user.get('can_create'):
                    return fn(*args, **kwargs)
                return jsonify({'code': 403, 'message': '权限不足，无新增权限'}), 403
            if user.get('can_create'):
                return fn(*args, **kwargs)
            return jsonify({'code': 403, 'message': '权限不足，无新增权限'}), 403
        return wrapper
    if fn is None:
        return decorator
    return decorator(fn)


def edit_required(fn=None, module=None):
    """编辑权限装饰器：admin 或有 can_edit 权限的用户。
    如果传入 module，优先按 module_actions 精确校验；当用户没有 module_actions 数据时回退到全局 can_edit。"""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user_id = int(get_jwt_identity())
            user = UserModel.get_by_id(user_id)
            if not user:
                return jsonify({'code': 403, 'message': '权限不足'}), 403
            if user['role'] == 'admin':
                return fn(*args, **kwargs)
            if module:
                module_actions = user.get('module_actions') or {}
                if module_actions:
                    if UserModel.has_module_action(user, module, 'can_edit'):
                        return fn(*args, **kwargs)
                    return jsonify({'code': 403, 'message': '权限不足，无该页面的编辑权限'}), 403
                if user.get('can_edit'):
                    return fn(*args, **kwargs)
                return jsonify({'code': 403, 'message': '权限不足，无编辑权限'}), 403
            if user.get('can_edit'):
                return fn(*args, **kwargs)
            return jsonify({'code': 403, 'message': '权限不足，无编辑权限'}), 403
        return wrapper
    if fn is None:
        return decorator
    return decorator(fn)


def module_action_required(module, action):
    """模块操作权限装饰器：admin 或指定模块有指定操作权限的用户"""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user_id = int(get_jwt_identity())
            user = UserModel.get_by_id(user_id)
            if not user:
                return jsonify({'code': 403, 'message': '权限不足'}), 403
            if UserModel.has_module_action(user, module, action):
                return fn(*args, **kwargs)
            return jsonify({'code': 403, 'message': f'权限不足，无 {module} 模块的 {action} 权限'}), 403
        return wrapper
    return decorator


def delete_required(fn=None, module=None):
    """删除权限装饰器：admin 或有 can_delete 权限的用户。
    如果传入 module，优先按 module_actions 精确校验；当用户没有 module_actions 数据时回退到全局 can_delete。"""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user_id = int(get_jwt_identity())
            user = UserModel.get_by_id(user_id)
            if not user:
                return jsonify({'code': 403, 'message': '权限不足'}), 403
            if user['role'] == 'admin':
                return fn(*args, **kwargs)
            if module:
                module_actions = user.get('module_actions') or {}
                if module_actions:
                    if UserModel.has_module_action(user, module, 'can_delete'):
                        return fn(*args, **kwargs)
                    return jsonify({'code': 403, 'message': '权限不足，无该页面的删除权限'}), 403
                # 兼容旧数据：未配置 module_actions 时按全局 can_delete 判断
                if user.get('can_delete'):
                    return fn(*args, **kwargs)
                return jsonify({'code': 403, 'message': '权限不足，无删除权限'}), 403
            if user.get('can_delete'):
                return fn(*args, **kwargs)
            return jsonify({'code': 403, 'message': '权限不足，无删除权限'}), 403
        return wrapper
    if fn is None:
        return decorator
    return decorator(fn)


def download_required(fn=None, module=None):
    """下载权限装饰器：admin 或有 can_download 权限的用户。
    如果传入 module，优先按 module_actions 精确校验；当用户没有 module_actions 数据时回退到全局 can_download。"""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user_id = int(get_jwt_identity())
            user = UserModel.get_by_id(user_id)
            if not user:
                return jsonify({'code': 403, 'message': '权限不足'}), 403
            if user['role'] == 'admin':
                return fn(*args, **kwargs)
            if module:
                module_actions = user.get('module_actions') or {}
                if module_actions:
                    if UserModel.has_module_action(user, module, 'can_download'):
                        return fn(*args, **kwargs)
                    return jsonify({'code': 403, 'message': '权限不足，无该页面的下载权限'}), 403
                if user.get('can_download'):
                    return fn(*args, **kwargs)
                return jsonify({'code': 403, 'message': '权限不足，无下载权限'}), 403
            if user.get('can_download'):
                return fn(*args, **kwargs)
            return jsonify({'code': 403, 'message': '权限不足，无下载权限'}), 403
        return wrapper
    if fn is None:
        return decorator
    return decorator(fn)


def approve_required(fn=None, module=None):
    """审批权限装饰器：admin 或有 can_approve 权限的用户。
    如果传入 module，优先按 module_actions 精确校验；当用户没有 module_actions 数据时回退到全局 can_approve。"""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user_id = int(get_jwt_identity())
            user = UserModel.get_by_id(user_id)
            if not user:
                return jsonify({'code': 403, 'message': '权限不足'}), 403
            if user['role'] == 'admin':
                return fn(*args, **kwargs)
            if module:
                module_actions = user.get('module_actions') or {}
                if module_actions:
                    if UserModel.has_module_action(user, module, 'can_approve'):
                        return fn(*args, **kwargs)
                    return jsonify({'code': 403, 'message': '权限不足，无该页面的审批权限'}), 403
                if user.get('can_approve'):
                    return fn(*args, **kwargs)
                return jsonify({'code': 403, 'message': '权限不足，无审批权限'}), 403
            if user.get('can_approve'):
                return fn(*args, **kwargs)
            return jsonify({'code': 403, 'message': '权限不足，无审批权限'}), 403
        return wrapper
    if fn is None:
        return decorator
    return decorator(fn)


def handle_required(fn=None, module=None):
    """办理权限装饰器：admin 或有 can_handle 权限的用户。
    如果传入 module，优先按 module_actions 精确校验；当用户没有 module_actions 数据时回退到全局 can_handle。"""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user_id = int(get_jwt_identity())
            user = UserModel.get_by_id(user_id)
            if not user:
                return jsonify({'code': 403, 'message': '权限不足'}), 403
            if user['role'] == 'admin':
                return fn(*args, **kwargs)
            if module:
                module_actions = user.get('module_actions') or {}
                if module_actions:
                    if UserModel.has_module_action(user, module, 'can_handle'):
                        return fn(*args, **kwargs)
                    return jsonify({'code': 403, 'message': '权限不足，无该页面的办理权限'}), 403
                if user.get('can_handle'):
                    return fn(*args, **kwargs)
                return jsonify({'code': 403, 'message': '权限不足，无办理权限'}), 403
            if user.get('can_handle'):
                return fn(*args, **kwargs)
            return jsonify({'code': 403, 'message': '权限不足，无办理权限'}), 403
        return wrapper
    if fn is None:
        return decorator
    return decorator(fn)


def receive_required(fn=None, module=None):
    """收款权限装饰器：admin 或有 can_receive 权限的用户。
    如果传入 module，优先按 module_actions 精确校验；当用户没有 module_actions 数据时回退到全局 can_receive。"""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user_id = int(get_jwt_identity())
            user = UserModel.get_by_id(user_id)
            if not user:
                return jsonify({'code': 403, 'message': '权限不足'}), 403
            if user['role'] == 'admin':
                return fn(*args, **kwargs)
            if module:
                module_actions = user.get('module_actions') or {}
                if module_actions:
                    if UserModel.has_module_action(user, module, 'can_receive'):
                        return fn(*args, **kwargs)
                    return jsonify({'code': 403, 'message': '权限不足，无该页面的收款权限'}), 403
                if user.get('can_receive'):
                    return fn(*args, **kwargs)
                return jsonify({'code': 403, 'message': '权限不足，无收款权限'}), 403
            if user.get('can_receive'):
                return fn(*args, **kwargs)
            return jsonify({'code': 403, 'message': '权限不足，无收款权限'}), 403
        return wrapper
    if fn is None:
        return decorator
    return decorator(fn)


def return_required(fn=None, module=None):
    """退货权限装饰器：admin 或有 can_return 权限的用户。
    如果传入 module，则优先检查该模块的 can_return 操作权限。"""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user_id = int(get_jwt_identity())
            user = UserModel.get_by_id(user_id)
            if not user:
                return jsonify({'code': 403, 'message': '权限不足'}), 403
            if user['role'] == 'admin':
                return fn(*args, **kwargs)
            if module and UserModel.has_module_action(user, module, 'can_return'):
                return fn(*args, **kwargs)
            if user.get('can_return'):
                return fn(*args, **kwargs)
            return jsonify({'code': 403, 'message': '权限不足，无退货权限'}), 403
        return wrapper
    if fn is None:
        return decorator
    return decorator(fn)
