from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from middleware.auth import create_required, edit_required, delete_required, download_required
from models.product import ProductModel
from models.record import RecordModel
from models.db import get_db_connection
from config import STOCK_WARNING_THRESHOLD
from utils.logger import log_action
import datetime
import csv
import io

inventory_bp = Blueprint('inventory', __name__, url_prefix='/api/inventory')

@inventory_bp.route('', methods=['GET'])
@jwt_required()
def list_inventory():
    """实时库存列表（对应商品列表，所有商品都显示，库存实时计算）"""
    keyword = request.args.get('keyword', '')
    conn = get_db_connection()
    cursor = conn.cursor()
    sql = '''
        SELECT 
            p.id,
            p.code,
            p.name,
            p.spec,
            p.unit,
            p.price_excl,
            p.price_incl,
            COALESCE(SUM(CASE 
                WHEN r.type IN ('purchase_in', 'sale_return') THEN r.quantity
                WHEN r.type IN ('sale_out', 'purchase_return') THEN -r.quantity
                WHEN r.type = 'stock_check' THEN r.quantity
                ELSE 0
            END), 0) as stock
        FROM products p
        LEFT JOIN records r ON p.id = r.product_id
        WHERE 1=1
    '''
    params = []
    if keyword:
        sql += ' AND (p.name LIKE ? OR p.code LIKE ? OR p.spec LIKE ?)'
        params.extend([f'%{keyword}%', f'%{keyword}%', f'%{keyword}%'])
    sql += ' GROUP BY p.id HAVING stock > 0 ORDER BY p.id DESC'
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()
    result = []
    for row in rows:
        try:
            stock = float(row['stock'] or 0)
        except (ValueError, TypeError):
            stock = 0
        result.append({
            'id': row['id'],
            'code': row['code'],
            'name': row['name'],
            'spec': row['spec'],
            'unit': row['unit'],
            'price_excl': row['price_excl'],
            'price_incl': row['price_incl'],
            'stock': stock,
            'warning': stock <= STOCK_WARNING_THRESHOLD
        })
    return jsonify({'code': 200, 'data': result})

@inventory_bp.route('/warning', methods=['GET'])
@jwt_required()
def stock_warning():
    """库存预警"""
    products = ProductModel.list_all()
    warning_list = []
    for p in products:
        try:
            stock = float(p.get('stock', 0) or 0)
        except (ValueError, TypeError):
            stock = 0
        if stock <= STOCK_WARNING_THRESHOLD:
            p['warning'] = True
            warning_list.append(p)
    return jsonify({'code': 200, 'data': warning_list})

@inventory_bp.route('/check', methods=['POST'])
@jwt_required()
@create_required(module='stock_check')
def stock_check():
    """库存盘点"""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    product_id = data['product_id']
    try:
        actual_stock = int(data['actual_stock'])
    except (ValueError, TypeError):
        return jsonify({'code': 400, 'message': '盘点库存必须为数字'})
    
    product = ProductModel.get_by_id(product_id)
    if not product:
        return jsonify({'code': 404, 'message': '商品不存在'})
    
    diff = actual_stock - product['stock']
    # 更新库存
    ProductModel.update_stock(product_id, diff)
    
    # 记录盘点流水
    order_no = f"PD{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    RecordModel.create({
        'type': 'stock_check',
        'order_no': order_no,
        'product_id': product_id,
        'quantity': diff,
        'price': 0,
        'total': 0,
        'party_type': '',
        'party_id': None,
        'party_name': '',
        'operator': data.get('operator', ''),
        'remark': f'盘点: 账面{product["stock"]} -> 实际{actual_stock}'
    })
    
    log_action(user_id, '库存盘点', f'商品: {product["name"]}, 差异: {diff}')
    return jsonify({'code': 200, 'message': '盘点成功', 'data': {'diff': diff}})

@inventory_bp.route('/records', methods=['GET'])
@jwt_required()
def list_stock_records():
    """库存流水"""
    product_id = request.args.get('product_id', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    records = RecordModel.get_stock_records(product_id, start_date, end_date)
    return jsonify({'code': 200, 'data': records})

@inventory_bp.route('/records/<int:record_id>', methods=['DELETE'])
@jwt_required()
@delete_required(module='stock_records')
def delete_stock_record(record_id):
    """删除库存流水记录（恢复库存）"""
    try:
        user_id = int(get_jwt_identity())
    except Exception:
        return jsonify({'code': 401, 'message': '登录信息无效'})

    record = RecordModel.get_by_id(record_id)
    if not record:
        return jsonify({'code': 404, 'message': '记录不存在'})

    record_type = record.get('type')
    if record_type not in ('purchase_in', 'purchase_return', 'sale_out', 'sale_return', 'stock_check'):
        return jsonify({'code': 400, 'message': '非库存记录，无法删除'})

    try:
        qty = int(record.get('quantity') or 0)
    except (ValueError, TypeError):
        qty = 0

    product_id = record.get('product_id')
    order_no = record.get('order_no', '') or ''

    # 恢复库存（反向操作）
    if product_id:
        try:
            if record_type in ('purchase_in', 'sale_return'):
                # 入库/销售退货增加库存，删除时减少库存
                ProductModel.update_stock(product_id, -qty)
            elif record_type in ('purchase_return', 'sale_out'):
                # 采购退货/销售出库减少库存，删除时增加库存
                ProductModel.update_stock(product_id, qty)
            elif record_type == 'stock_check':
                # 盘点差异已带符号，删除时直接反向
                ProductModel.update_stock(product_id, -qty)
        except Exception as e:
            return jsonify({'code': 500, 'message': f'恢复库存失败: {str(e)}'})

    # 删除记录
    try:
        RecordModel.delete(record_id)
    except Exception as e:
        return jsonify({'code': 500, 'message': f'删除记录失败: {str(e)}'})

    log_action(user_id, '删除库存记录', f"删除记录ID: {record_id}, 单号: {order_no}")
    return jsonify({'code': 200, 'message': '删除成功'})

@inventory_bp.route('/export', methods=['GET'])
@jwt_required()
@download_required(module='inventory')
def export_inventory():
    """导出库存（从入库记录计算，不显示价格）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    sql = '''
        SELECT 
            p.id,
            p.code,
            p.name,
            p.spec,
            p.unit,
            COALESCE(SUM(CASE 
                WHEN r.type IN ('purchase_in', 'sale_return') THEN r.quantity
                WHEN r.type IN ('sale_out', 'purchase_return') THEN -r.quantity
                WHEN r.type = 'stock_check' THEN r.quantity
                ELSE 0
            END), 0) as stock
        FROM products p
        LEFT JOIN records r ON p.id = r.product_id
        WHERE EXISTS (SELECT 1 FROM records r2 WHERE r2.product_id = p.id AND r2.type = 'purchase_in')
        GROUP BY p.id
        HAVING stock > 0
        ORDER BY p.id DESC
    '''
    cursor.execute(sql)
    rows = cursor.fetchall()
    
    conn.close()
    data = []
    for row in rows:
        try:
            stock = float(row['stock'] or 0)
        except (ValueError, TypeError):
            stock = 0
        data.append({
            '编码': row['code'],
            '名称': row['name'],
            '规格': row['spec'] or '',
            '单位': row['unit'] or '',
            '库存': stock,
            '预警状态': '预警' if stock <= STOCK_WARNING_THRESHOLD else '正常'
        })
    return jsonify({'code': 200, 'data': data})
