from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from middleware.auth import create_required, edit_required, delete_required, download_required
from models.record import RecordModel
from models.product import ProductModel
from models.supplier import SupplierModel
from models.financial import FinancialModel
from utils.logger import log_action
from utils.code_generator import generate_daily_serial
import csv
import io

purchase_bp = Blueprint('purchase', __name__, url_prefix='/api/purchase')


def _build_purchase_records(start_date, end_date, keyword):
    """构建采购记录列表（入库+退货）"""
    records = RecordModel.list_all(record_type=None, start_date=start_date, end_date=end_date, keyword=keyword)
    purchase_types = {'purchase_in', 'purchase_return'}
    records = [r for r in records if r['type'] in purchase_types]

    # 关联查询 financials 表，标记已付款的订单
    from models.db import get_db_connection
    order_nos = list({r['order_no'] for r in records if r.get('order_no')})
    paid_order_nos = set()
    if order_nos:
        conn = get_db_connection()
        cursor = conn.cursor()
        placeholders = ','.join('?' * len(order_nos))
        cursor.execute(
            f"SELECT order_no FROM financials WHERE order_no IN ({placeholders}) AND type = 'payable' AND status = 'paid'",
            order_nos
        )
        paid_order_nos = {row[0] for row in cursor.fetchall()}
        conn.close()

    for r in records:
        r['payment_status'] = 'paid' if r.get('order_no') in paid_order_nos else 'unpaid'
    return records


def _filter_by_payment_status(records, status_filter):
    """按付款状态筛选：现结/已付款/应付"""
    if not status_filter:
        return records
    result = []
    for r in records:
        payment_type = r.get('payment_type', '') or ''
        payment_status = r.get('payment_status', '')
        if status_filter == '现结' and payment_type == '现结':
            result.append(r)
        elif status_filter == '已付款' and payment_type == '应付' and payment_status == 'paid':
            result.append(r)
        elif status_filter == '应付' and payment_type == '应付' and payment_status != 'paid':
            result.append(r)
    return result


@purchase_bp.route('/inbound', methods=['POST'])
@jwt_required()
@create_required(module='purchase')
def purchase_inbound():
    """采购入库单"""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    items = data.get('items', [])
    if not items:
        return jsonify({'code': 400, 'message': '商品明细不能为空'})

    supplier_id = data.get('supplier_id')
    supplier = SupplierModel.get_by_id(supplier_id) if supplier_id else None
    supplier_name = supplier.get('name', '') if supplier else ''

    order_no = generate_daily_serial('RK', 'records', 'order_no')
    for item in items:
        product_id = item['product_id']
        try:
            quantity = int(item['quantity'])
        except (ValueError, TypeError):
            return jsonify({'code': 400, 'message': '商品数量必须为数字'})
        # 从商品表获取成本价作为入库价
        product = ProductModel.get_by_id(product_id)
        if not product:
            return jsonify({'code': 404, 'message': f'商品不存在 (ID: {product_id})'})
        price = float(product.get('cost_excl', 0) or 0)
        total = price * quantity
        # 增加库存
        ProductModel.update_stock(product_id, quantity)
        RecordModel.create({
            'type': 'purchase_in',
            'order_no': order_no,
            'product_id': product_id,
            'quantity': quantity,
            'price': price,
            'total': total,
            'party_type': 'supplier',
            'party_id': supplier_id,
            'party_name': supplier_name,
            'operator': data.get('operator', ''),
            'delivery_type': data.get('delivery_type', ''),
            'tax_rate': data.get('tax_rate', 13),
            'is_tax_included': 0,
            'remark': data.get('remark', ''),
            'payment_type': data.get('payment_type', '现结')
        })

    # 生成应付账款 / 现金支出
    try:
        total_amount = 0
        for item in items:
            product = ProductModel.get_by_id(item['product_id'])
            price = float(product.get('cost_excl', 0) or 0) if product else 0
            total_amount += price * int(item['quantity'])
    except (ValueError, TypeError):
        total_amount = 0
    payment_type = data.get('payment_type', '现结')
    if total_amount > 0:
        if payment_type == '现结':
            # 现结：生成已付款应付 + 现金支出
            FinancialModel.create({
                'type': 'payable',
                'amount': total_amount,
                'party_type': 'supplier',
                'party_id': supplier_id,
                'party_name': supplier_name,
                'status': 'paid',
                'order_no': order_no,
                'remark': f'采购入库单 {order_no} (现结)'
            })
            FinancialModel.create({
                'type': 'expense',
                'amount': total_amount,
                'party_type': 'supplier',
                'party_id': supplier_id,
                'party_name': supplier_name,
                'status': 'paid',
                'order_no': order_no,
                'payment_method': '现结',
                'remark': f'采购入库单 {order_no} (现结)'
            })
        elif payment_type == '应付':
            FinancialModel.create({
                'type': 'payable',
                'amount': total_amount,
                'party_type': 'supplier',
                'party_id': supplier_id,
                'party_name': supplier_name,
                'status': 'unpaid',
                'order_no': order_no,
                'remark': f'采购入库单 {order_no} (应付)'
            })

    log_action(user_id, '采购入库', f'单号: {order_no}')
    return jsonify({'code': 200, 'message': '入库成功', 'data': {'order_no': order_no}})

@purchase_bp.route('/records', methods=['GET'])
@jwt_required()
def list_purchase_records():
    """入库记录"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    keyword = request.args.get('keyword', '')
    payment_status_filter = request.args.get('payment_status', '')
    records = _build_purchase_records(start_date, end_date, keyword)
    records = _filter_by_payment_status(records, payment_status_filter)
    return jsonify({'code': 200, 'data': records})

@purchase_bp.route('/records/export', methods=['GET'])
@jwt_required()
@download_required(module='purchase')
def export_purchase_records():
    """导出入库记录"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    keyword = request.args.get('keyword', '')
    payment_status_filter = request.args.get('payment_status', '')
    records = _build_purchase_records(start_date, end_date, keyword)
    records = _filter_by_payment_status(records, payment_status_filter)
    data = []
    for r in records:
        payment_type = r.get('payment_type', '') or ''
        payment_status = r.get('payment_status', '')
        if payment_type == '现结':
            status_label = '现结'
        elif payment_status == 'paid':
            status_label = '已付款'
        else:
            status_label = '应付'
        data.append({
            '单据编号': r['order_no'],
            '类型': '采购入库' if r['type'] == 'purchase_in' else '采购退货',
            '商品': r.get('product_name', ''),
            '型号': r.get('product_spec', ''),
            '数量': abs(r.get('quantity', 0) or 0),
            '单价(不含税)': round(float(r.get('price', 0) or 0), 2),
            '金额': round(float(r.get('total', 0) or 0), 2),
            '供应商': r.get('party_name', ''),
            '付款状态': status_label,
            '经手人': r.get('operator', ''),
            '商品编码': r.get('product_code', ''),
            '日期': r.get('created_at', '')
        })
    return jsonify({'code': 200, 'data': data})

@purchase_bp.route('/records/<int:record_id>', methods=['DELETE'])
@jwt_required()
@delete_required(module='purchase')
def delete_purchase_record(record_id):
    """删除采购记录（恢复库存）"""
    try:
        user_id = int(get_jwt_identity())
    except Exception:
        return jsonify({'code': 401, 'message': '登录信息无效'})

    record = RecordModel.get_by_id(record_id)
    if not record:
        return jsonify({'code': 404, 'message': '记录不存在'})

    record_type = record.get('type')
    if record_type not in ('purchase_in', 'purchase_return'):
        return jsonify({'code': 400, 'message': '非采购记录，无法删除'})

    try:
        qty = int(record.get('quantity') or 0)
    except (ValueError, TypeError):
        qty = 0

    product_id = record.get('product_id')
    order_no = record.get('order_no', '') or ''

    # 恢复库存
    if product_id:
        try:
            if record_type == 'purchase_in':
                ProductModel.update_stock(product_id, -qty)
            elif record_type == 'purchase_return':
                ProductModel.update_stock(product_id, qty)
        except Exception as e:
            return jsonify({'code': 500, 'message': f'恢复库存失败: {str(e)}'})

    # 检查同单号是否还有其他记录，如果没有则删除财务记录；否则更新财务记录金额
    if order_no:
        try:
            remaining = RecordModel.get_by_order_no(order_no, exclude_id=record_id)
            if not remaining:
                FinancialModel.delete_by_order_no(order_no)
            else:
                new_total = 0
                for r in remaining:
                    try:
                        new_total += float(r.get('total', 0) or 0)
                    except (ValueError, TypeError):
                        pass
                FinancialModel.update_amount_by_order_no(order_no, new_total)
        except Exception as e:
            print(f'处理财务记录失败: {e}')

    # 删除记录
    try:
        RecordModel.delete(record_id)
    except Exception as e:
        return jsonify({'code': 500, 'message': f'删除记录失败: {str(e)}'})

    log_action(user_id, '删除采购记录', f"删除记录ID: {record_id}, 单号: {order_no}")
    return jsonify({'code': 200, 'message': '删除成功'})
