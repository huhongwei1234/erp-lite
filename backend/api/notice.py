from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from middleware.auth import admin_required, create_required, edit_required, delete_required
from models.notice import NoticeModel
from utils.logger import log_action

notices_bp = Blueprint('notices', __name__, url_prefix='/api/notices')

@notices_bp.route('', methods=['GET'])
@jwt_required()
def list_notices():
    """公告列表（管理用，返回全部）"""
    notices = NoticeModel.list_all()
    return jsonify({'code': 200, 'data': notices})

@notices_bp.route('/visible', methods=['GET'])
def list_visible_notices():
    """可见公告列表（公开，无需登录）"""
    notices = NoticeModel.list_visible()
    return jsonify({'code': 200, 'data': notices})

@notices_bp.route('', methods=['POST'])
@jwt_required()
@create_required(module='notice')
def create_notice():
    """新增公告"""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    if not data.get('title'):
        return jsonify({'code': 400, 'message': '公告标题不能为空'})
    notice_id = NoticeModel.create(data)
    log_action(user_id, '新增公告', f"新增公告: {data['title']}")
    return jsonify({'code': 200, 'message': '新增成功', 'data': {'id': notice_id}})

@notices_bp.route('/<int:notice_id>', methods=['PUT'])
@jwt_required()
@edit_required(module='notice')
def update_notice(notice_id):
    """修改公告"""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    if not data.get('title'):
        return jsonify({'code': 400, 'message': '公告标题不能为空'})
    NoticeModel.update(notice_id, data)
    log_action(user_id, '修改公告', f"修改公告ID: {notice_id}")
    return jsonify({'code': 200, 'message': '修改成功'})

@notices_bp.route('/<int:notice_id>', methods=['DELETE'])
@jwt_required()
@delete_required(module='notice')
def delete_notice(notice_id):
    """删除公告"""
    user_id = int(get_jwt_identity())
    NoticeModel.delete(notice_id)
    log_action(user_id, '删除公告', f"删除公告ID: {notice_id}")
    return jsonify({'code': 200, 'message': '删除成功'})
