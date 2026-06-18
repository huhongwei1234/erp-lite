from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from middleware.auth import create_required, edit_required, delete_required, download_required
from models.supplier import SupplierModel
from models.product import ProductModel
from utils.logger import log_action
import csv
import io

suppliers_bp = Blueprint('suppliers', __name__, url_prefix='/api/suppliers')

@suppliers_bp.route('', methods=['GET'])
@jwt_required()
def list_suppliers():
    """供应商列表"""
    keyword = request.args.get('keyword', '')
    suppliers = SupplierModel.list_all(keyword)
    return jsonify({'code': 200, 'data': suppliers})

@suppliers_bp.route('/<int:supplier_id>', methods=['GET'])
@jwt_required()
def get_supplier(supplier_id):
    """供应商详情"""
    supplier = SupplierModel.get_by_id(supplier_id)
    if not supplier:
        return jsonify({'code': 404, 'message': '供应商不存在'})
    return jsonify({'code': 200, 'data': supplier})

@suppliers_bp.route('', methods=['POST'])
@jwt_required()
@create_required(module='supplier')
def create_supplier():
    """新增供应商"""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    if not data.get('name'):
        return jsonify({'code': 400, 'message': '供应商名称不能为空'})
    code_prefix = data.get('code_prefix', '').strip()
    if not code_prefix:
        return jsonify({'code': 400, 'message': '供应商编号不能为空'})
    if code_prefix:
        existing = SupplierModel.get_by_code_prefix(code_prefix)
        if existing:
            return jsonify({'code': 400, 'message': '供应商编号已存在'})
    supplier_id = SupplierModel.create(data)
    log_action(user_id, '新增供应商', f"新增供应商: {data['name']}")
    return jsonify({'code': 200, 'message': '新增成功', 'data': {'id': supplier_id}})

@suppliers_bp.route('/<int:supplier_id>', methods=['PUT'])
@jwt_required()
@edit_required(module='supplier')
def update_supplier(supplier_id):
    """修改供应商"""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    if not data.get('name'):
        return jsonify({'code': 400, 'message': '供应商名称不能为空'})
    code_prefix = data.get('code_prefix', '').strip()
    if not code_prefix:
        return jsonify({'code': 400, 'message': '供应商编号不能为空'})
    if code_prefix:
        existing = SupplierModel.get_by_code_prefix(code_prefix)
        if existing and existing['id'] != supplier_id:
            return jsonify({'code': 400, 'message': '供应商编号已存在'})
    SupplierModel.update(supplier_id, data)
    log_action(user_id, '修改供应商', f"修改供应商ID: {supplier_id}")
    return jsonify({'code': 200, 'message': '修改成功'})

@suppliers_bp.route('/<int:supplier_id>', methods=['DELETE'])
@jwt_required()
@delete_required(module='supplier')
def delete_supplier(supplier_id):
    """删除供应商"""
    user_id = int(get_jwt_identity())
    SupplierModel.delete(supplier_id)
    log_action(user_id, '删除供应商', f"删除供应商ID: {supplier_id}")
    return jsonify({'code': 200, 'message': '删除成功'})

@suppliers_bp.route('/export', methods=['GET'])
@jwt_required()
@download_required(module='supplier')
def export_suppliers():
    """导出供应商"""
    suppliers = SupplierModel.list_all()
    data = []
    for s in suppliers:
        data.append({
            '名称': s['name'],
            '编号': s.get('code_prefix', ''),
            '联系人': s.get('contact', ''),
            '电话': s.get('phone', ''),
            '地址': s.get('address', ''),
            '备注': s.get('remark', '')
        })
    return jsonify({'code': 200, 'data': data})
