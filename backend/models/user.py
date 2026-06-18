import json
from models.db import get_db_connection


class UserModel:
    @staticmethod
    def _parse_row(row_dict):
        """解析用户行数据"""
        # 解析 permissions JSON
        perms = row_dict.get('permissions')
        if perms:
            try:
                row_dict['permissions'] = json.loads(perms)
            except (json.JSONDecodeError, TypeError):
                row_dict['permissions'] = []
        else:
            row_dict['permissions'] = []
        # 解析 module_actions JSON（按模块的操作权限）
        module_actions = row_dict.get('module_actions')
        if module_actions:
            try:
                row_dict['module_actions'] = json.loads(module_actions)
            except (json.JSONDecodeError, TypeError):
                row_dict['module_actions'] = {}
        else:
            row_dict['module_actions'] = {}
        # theme 默认值
        if not row_dict.get('theme'):
            row_dict['theme'] = 'dark-blue'
        return row_dict

    @staticmethod
    def get_by_username(username):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        row = cursor.fetchone()
        conn.close()
        return UserModel._parse_row(dict(row)) if row else None

    @staticmethod
    def get_by_id(user_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, name, role, permissions, module_actions, can_create, can_edit, can_delete, can_download, can_approve, can_handle, can_receive, can_return, can_delete_purchase, can_delete_sale, theme, session_id, created_at FROM users WHERE id = ?', (user_id,))
        row = cursor.fetchone()
        conn.close()
        return UserModel._parse_row(dict(row)) if row else None

    @staticmethod
    def create(username, password_hash, name, role='viewer', permissions=None, module_actions=None,
               can_create=0, can_edit=0, can_delete=0, can_download=0, can_approve=0, can_handle=0, can_receive=0, can_return=0,
               theme='dark-blue'):
        conn = get_db_connection()
        cursor = conn.cursor()
        perms_json = json.dumps(permissions, ensure_ascii=False) if permissions else None
        module_actions_json = json.dumps(module_actions, ensure_ascii=False) if module_actions else None
        cursor.execute('''
            INSERT INTO users (username, password, name, role, permissions, module_actions,
                               can_create, can_edit, can_delete, can_download, can_approve, can_handle, can_receive, can_return, theme)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (username, password_hash, name, role, perms_json, module_actions_json,
              int(can_create), int(can_edit), int(can_delete), int(can_download), int(can_approve), int(can_handle), int(can_receive), int(can_return), theme))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return user_id

    @staticmethod
    def update(user_id, data):
        """更新用户信息"""
        conn = get_db_connection()
        cursor = conn.cursor()
        fields = []
        values = []
        for key in ['name', 'role', 'theme', 'session_id']:
            if key in data:
                fields.append(f'{key} = ?')
                values.append(data[key])
        if 'permissions' in data:
            fields.append('permissions = ?')
            values.append(json.dumps(data['permissions'], ensure_ascii=False))
        if 'module_actions' in data:
            fields.append('module_actions = ?')
            values.append(json.dumps(data['module_actions'], ensure_ascii=False))
        # 旧全局权限字段保留兼容，但新逻辑优先使用 module_actions
        for key in ['can_create', 'can_edit', 'can_delete', 'can_download', 'can_approve', 'can_handle', 'can_receive', 'can_return', 'can_delete_purchase', 'can_delete_sale']:
            if key in data:
                try:
                    val = int(data[key])
                    fields.append(f'{key} = ?')
                    values.append(val)
                except (ValueError, TypeError):
                    pass
        if not fields:
            conn.close()
            return False
        values.append(user_id)
        cursor.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
        conn.close()
        return True

    @staticmethod
    def has_module_action(user, module, action):
        """检查用户是否拥有指定模块的指定操作权限（admin 始终拥有）"""
        if not user:
            return False
        if user.get('role') == 'admin':
            return True
        return user.get('module_actions', {}).get(module, {}).get(action, False)

    @staticmethod
    def update_password(user_id, password_hash):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET password = ? WHERE id = ?', (password_hash, user_id))
        conn.commit()
        conn.close()

    @staticmethod
    def delete(user_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def list_all():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, name, role, permissions, module_actions, can_create, can_edit, can_delete, can_download, can_approve, can_handle, can_receive, can_return, can_delete_purchase, can_delete_sale, theme, session_id, created_at FROM users ORDER BY id DESC')
        rows = cursor.fetchall()
        conn.close()
        return [UserModel._parse_row(dict(row)) for row in rows]
