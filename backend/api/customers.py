from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from middleware.auth import create_required, edit_required, delete_required, download_required
from models.customer import CustomerModel
from utils.logger import log_action
import csv
import io

customers_bp = Blueprint('customers', __name__, url_prefix='/api/customers')

@customers_bp.route('', methods=['GET'])
@jwt_required()
def list_customers():
    """客户列表"""
    keyword = request.args.get('keyword', '')
    customers = CustomerModel.list_all(keyword)
    # 查询每个客户的应收金额
    for c in customers:
        c['receivable'] = CustomerModel.get_receivable(c['id'])
    return jsonify({'code': 200, 'data': customers})

@customers_bp.route('/<int:customer_id>', methods=['GET'])
@jwt_required()
def get_customer(customer_id):
    """客户详情"""
    customer = CustomerModel.get_by_id(customer_id)
    if not customer:
        return jsonify({'code': 404, 'message': '客户不存在'})
    customer['receivable'] = CustomerModel.get_receivable(customer_id)
    return jsonify({'code': 200, 'data': customer})

@customers_bp.route('', methods=['POST'])
@jwt_required()
@create_required(module='customer')
def create_customer():
    """新增客户"""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    if not data.get('name'):
        return jsonify({'code': 400, 'message': '客户名称不能为空'})
    customer_id = CustomerModel.create(data)
    log_action(user_id, '新增客户', f"新增客户: {data['name']}")
    return jsonify({'code': 200, 'message': '新增成功', 'data': {'id': customer_id}})

@customers_bp.route('/<int:customer_id>', methods=['PUT'])
@jwt_required()
@edit_required(module='customer')
def update_customer(customer_id):
    """修改客户"""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    if not data.get('name'):
        return jsonify({'code': 400, 'message': '客户名称不能为空'})
    CustomerModel.update(customer_id, data)
    log_action(user_id, '修改客户', f"修改客户ID: {customer_id}")
    return jsonify({'code': 200, 'message': '修改成功'})

@customers_bp.route('/<int:customer_id>', methods=['DELETE'])
@jwt_required()
@delete_required(module='customer')
def delete_customer(customer_id):
    """删除客户"""
    user_id = int(get_jwt_identity())
    CustomerModel.delete(customer_id)
    log_action(user_id, '删除客户', f"删除客户ID: {customer_id}")
    return jsonify({'code': 200, 'message': '删除成功'})

@customers_bp.route('/<int:customer_id>/receivable', methods=['GET'])
@jwt_required()
def get_customer_receivable(customer_id):
    """获取客户应收"""
    receivable = CustomerModel.get_receivable(customer_id)
    return jsonify({'code': 200, 'data': {'receivable': receivable}})

@customers_bp.route('/export', methods=['GET'])
@jwt_required()
@download_required(module='customer')
def export_customers():
    """导出客户"""
    customers = CustomerModel.list_all()
    data = []
    for c in customers:
        data.append({
            '名称': c['name'],
            '联系人': c.get('contact', ''),
            '电话': c.get('phone', ''),
            '地址': c.get('address', ''),
            '应收金额': CustomerModel.get_receivable(c['id']),
            '备注': c.get('remark', '')
        })
    return jsonify({'code': 200, 'data': data})
