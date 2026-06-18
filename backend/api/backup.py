from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from middleware.auth import admin_required
from models.backup import BackupModel
from utils.logger import log_action
import threading
import os

backup_bp = Blueprint('backup', __name__, url_prefix='/api/backup')

# 全局定时器
_backup_timer = None


def _schedule_next_backup():
    """调度下一次备份"""
    global _backup_timer
    settings = BackupModel.get_settings()
    if not settings or not settings.get('enabled'):
        return
    interval = settings.get('interval_hours', 24)
    # 使用小时为单位的定时器
    _backup_timer = threading.Timer(interval * 3600, _run_scheduled_backup)
    _backup_timer.daemon = True
    _backup_timer.start()


def _run_scheduled_backup():
    """执行定时备份"""
    settings = BackupModel.get_settings()
    if not settings or not settings.get('enabled'):
        return
    target_path = settings.get('target_path', '')
    success, msg = BackupModel.do_backup(target_path)
    status = 'success' if success else 'failed'
    BackupModel.update_last_status(status)
    log_action(0, '定时备份', f'状态: {status}, 详情: {msg}')
    _schedule_next_backup()


def init_backup_scheduler():
    """启动时初始化备份调度器"""
    _schedule_next_backup()


@backup_bp.route('/settings', methods=['GET'])
@jwt_required()
@admin_required
def get_settings():
    settings = BackupModel.get_settings()
    return jsonify({'code': 200, 'data': settings or {}})


@backup_bp.route('/settings', methods=['PUT'])
@jwt_required()
@admin_required
def update_settings():
    user_id = int(get_jwt_identity())
    data = request.get_json()
    BackupModel.save_settings(data)
    # 重新调度
    global _backup_timer
    if _backup_timer:
        _backup_timer.cancel()
    _schedule_next_backup()
    log_action(user_id, '修改备份设置', f'enabled={data.get("enabled")}, interval={data.get("interval_hours")}, path={data.get("target_path")}')
    return jsonify({'code': 200, 'message': '设置已保存'})


@backup_bp.route('/run', methods=['POST'])
@jwt_required()
@admin_required
def run_backup():
    user_id = int(get_jwt_identity())
    settings = BackupModel.get_settings()
    target_path = request.json.get('target_path') or (settings.get('target_path') if settings else '')
    success, msg = BackupModel.do_backup(target_path)
    status = 'success' if success else 'failed'
    BackupModel.update_last_status(status)
    log_action(user_id, '手动备份', f'状态: {status}, 详情: {msg}')
    if success:
        return jsonify({'code': 200, 'message': '备份成功', 'data': {'path': msg}})
    return jsonify({'code': 500, 'message': msg})
