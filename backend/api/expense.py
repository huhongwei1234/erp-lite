from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from middleware.auth import create_required, edit_required, delete_required, download_required, admin_required, permission_required, approve_required, handle_required
from models.expense import ExpenseModel
from models.user import UserModel
from utils.logger import log_action
import csv
import io

expense_bp = Blueprint('expense', __name__, url_prefix='/api/expenses')

@expense_bp.route('', methods=['GET'])
@jwt_required()
def list_expenses():
    """费用报销列表"""
    status = request.args.get('status')
    expense_type = request.args.get('type')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    keyword = request.args.get('keyword', '')
    records = ExpenseModel.list_all(status, expense_type, start_date, end_date, keyword)
    return jsonify({'code': 200, 'data': records})

@expense_bp.route('/<int:expense_id>', methods=['GET'])
@jwt_required()
def get_expense(expense_id):
    """费用报销详情"""
    record = ExpenseModel.get_by_id(expense_id)
    if not record:
        return jsonify({'code': 404, 'message': '记录不存在'})
    return jsonify({'code': 200, 'data': record})

@expense_bp.route('', methods=['POST'])
@jwt_required()
@permission_required('expense')
@create_required(module='expense')
def create_expense():
    """新增费用报销（有费用报销模块权限即可申请）"""
    user_id = int(get_jwt_identity())
    user = UserModel.get_by_id(user_id)
    data = request.get_json()
    if not data.get('type') or data.get('amount') is None:
        return jsonify({'code': 400, 'message': '报销类型和金额不能为空'})
    # 自动填充申请人为当前登录用户
    data['applicant'] = user.get('name') or user.get('username', '')
    expense_id = ExpenseModel.create(data)
    log_action(user_id, '新增费用报销', f"类型: {data['type']}, 金额: {data['amount']}")
    return jsonify({'code': 200, 'message': '新增成功', 'data': {'id': expense_id}})

@expense_bp.route('/<int:expense_id>', methods=['PUT'])
@jwt_required()
@edit_required(module='expense')
def update_expense(expense_id):
    """修改费用报销"""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    ExpenseModel.update(expense_id, data)
    log_action(user_id, '修改费用报销', f'报销ID: {expense_id}')
    return jsonify({'code': 200, 'message': '修改成功'})

@expense_bp.route('/<int:expense_id>', methods=['DELETE'])
@jwt_required()
@delete_required(module='expense')
def delete_expense(expense_id):
    """删除费用报销"""
    user_id = int(get_jwt_identity())
    ExpenseModel.delete(expense_id)
    log_action(user_id, '删除费用报销', f'报销ID: {expense_id}')
    return jsonify({'code': 200, 'message': '删除成功'})

@expense_bp.route('/<int:expense_id>/approve', methods=['POST'])
@jwt_required()
@approve_required(module='expense')
def approve_expense(expense_id):
    """审批通过费用报销（仅管理员）"""
    user_id = int(get_jwt_identity())
    record = ExpenseModel.get_by_id(expense_id)
    if not record:
        return jsonify({'code': 404, 'message': '记录不存在'})
    if record.get('status') != 'pending':
        return jsonify({'code': 400, 'message': '该记录已审批'})
    ExpenseModel.update(expense_id, {'status': 'approved'})
    log_action(user_id, '审批费用报销', f'报销ID: {expense_id}, 金额: {record.get("amount", 0)}')
    return jsonify({'code': 200, 'message': '审批通过'})

@expense_bp.route('/<int:expense_id>/handle', methods=['POST'])
@jwt_required()
@handle_required(module='expense')
def handle_expense(expense_id):
    """办理费用报销（仅管理员/财务）"""
    user_id = int(get_jwt_identity())
    record = ExpenseModel.get_by_id(expense_id)
    if not record:
        return jsonify({'code': 404, 'message': '记录不存在'})
    if record.get('status') != 'approved':
        return jsonify({'code': 400, 'message': '该记录未审批或已办理'})
    from datetime import datetime
    ExpenseModel.update(expense_id, {'status': 'handled', 'handled_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
    log_action(user_id, '办理费用报销', f'报销ID: {expense_id}, 金额: {record.get("amount", 0)}')
    return jsonify({'code': 200, 'message': '办理成功'})


@expense_bp.route('/pending-count', methods=['GET'])
@jwt_required()
def pending_count():
    """获取待审批费用报销数量"""
    records = ExpenseModel.list_all(status='pending')
    return jsonify({'code': 200, 'data': {'count': len(records)}})


@expense_bp.route('/export', methods=['GET'])
@jwt_required()
@download_required(module='expense')
def export_expenses():
    """导出费用报销"""
    records = ExpenseModel.list_all()
    status_map = {'pending': '待审批', 'approved': '已通过', 'rejected': '已拒绝'}
    data = []
    for r in records:
        data.append({
            'ID': r['id'],
            '报销类型': r.get('type', ''),
            '金额': r.get('amount', 0),
            '事由': r.get('description', ''),
            '申请人': r.get('applicant', ''),
            '业务员': r.get('operator', ''),
            '状态': status_map.get(r.get('status', ''), r.get('status', '')),
            '备注': r.get('remark', ''),
            '日期': r.get('created_at', '')
        })
    return jsonify({'code': 200, 'data': data})
