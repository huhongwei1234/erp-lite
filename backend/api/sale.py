from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from middleware.auth import create_required, edit_required, delete_required, download_required, return_required
from models.record import RecordModel
from models.product import ProductModel
from models.financial import FinancialModel
from utils.logger import log_action
from utils.code_generator import generate_daily_serial
from models.db import get_db_connection
import csv
import io

sale_bp = Blueprint('sale', __name__, url_prefix='/api/sale')


def generate_order_no(prefix):
    """生成单据编号：前缀 + 年月日 + 5位递增号"""
    return generate_daily_serial(prefix, 'records', 'order_no')


def calc_item_total(price, quantity, tax_rate, is_tax_included):
    """计算含税总价
    is_tax_included=True:  price 为含税单价，返回含税总价
    is_tax_included=False: price 为不含税单价，返回含税总价
    """
    if is_tax_included:
        return price * quantity
    else:
        return price * quantity * (1 + tax_rate / 100)


def _calc_tax_amount(total, tax_rate):
    """根据含税总价和税率计算税额"""
    try:
        total = float(total or 0)
        rate = float(tax_rate or 0) / 100
        if rate <= 0 or total <= 0:
            return 0
        return total - total / (1 + rate)
    except (ValueError, TypeError):
        return 0


def _build_sale_records(start_date, end_date, keyword, tax_included=None):
    """构建销售记录列表（出库+退货）"""
    records = RecordModel.list_all(record_type=None, start_date=start_date, end_date=end_date, keyword=keyword)
    sale_types = {'sale_out', 'sale_return'}
    records = [r for r in records if r['type'] in sale_types]

    # 含税筛选
    if tax_included is not None:
        records = [r for r in records if int(r.get('is_tax_included', 0) or 0) == tax_included]

    # 关联查询 financials 表，标记已收款的订单
    order_nos = list({r['order_no'] for r in records if r.get('order_no')})
    paid_order_nos = set()
    if order_nos:
        conn = get_db_connection()
        cursor = conn.cursor()
        placeholders = ','.join('?' * len(order_nos))
        cursor.execute(
            f"SELECT order_no FROM financials WHERE order_no IN ({placeholders}) AND type = 'receivable' AND status = 'paid'",
            order_nos
        )
        paid_order_nos = {row[0] for row in cursor.fetchall()}
        conn.close()

    for r in records:
        r['payment_status'] = 'paid' if r.get('order_no') in paid_order_nos else 'unpaid'
    return records


@sale_bp.route('/outbound', methods=['POST'])
@jwt_required()
@create_required(module='sale')
def sale_outbound():
    """销售出库单"""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    items = data.get('items', [])
    if not items:
        return jsonify({'code': 400, 'message': '商品明细不能为空'})

    try:
        tax_rate = float(data.get('tax_rate', 13))
        is_tax_included = int(data.get('is_tax_included', 0))
    except (ValueError, TypeError):
        return jsonify({'code': 400, 'message': '税率和含税标记必须为数字'})

    # 检查库存：先汇总同一商品的数量（避免同一订单中同一商品多次出现导致超卖）
    from collections import Counter
    product_qty_map = Counter()
    for item in items:
        try:
            product_qty_map[item['product_id']] += int(item.get('quantity', 0))
        except (ValueError, TypeError):
            return jsonify({'code': 400, 'message': '商品数量必须为数字'})

    for product_id, total_qty in product_qty_map.items():
        product = ProductModel.get_by_id(product_id)
        if not product:
            return jsonify({'code': 404, 'message': f"商品不存在 (ID: {product_id})"})
        try:
            stock = float(product.get('stock', 0) or 0)
        except (ValueError, TypeError):
            stock = 0
        if stock < total_qty:
            return jsonify({'code': 400, 'message': f"商品 [{product['name']}] 库存不足，当前库存 {stock}，需要 {total_qty}"})

    order_no = generate_order_no('XS')
    for item in items:
        product_id = item['product_id']
        try:
            quantity = int(item['quantity'])
            price = float(item.get('price', 0))
        except (ValueError, TypeError):
            return jsonify({'code': 400, 'message': '商品数量和单价必须为数字'})
        item_is_tax_included = int(item.get('is_tax_included', is_tax_included))
        total = calc_item_total(price, quantity, tax_rate, item_is_tax_included)
        # 减少库存
        ProductModel.update_stock(product_id, -quantity)
        RecordModel.create({
            'type': 'sale_out',
            'order_no': order_no,
            'product_id': product_id,
            'quantity': quantity,
            'price': price,
            'total': total,
            'party_type': 'customer',
            'party_id': data.get('customer_id'),
            'party_name': data.get('customer_name', ''),
            'operator': data.get('operator', ''),
            'delivery_type': data.get('delivery_type', ''),
            'tax_rate': tax_rate,
            'is_tax_included': item_is_tax_included,
            'remark': data.get('remark', ''),
            'payment_type': data.get('payment_type', ''),
            'item_remark': item.get('item_remark', '')
        })

    # 生成应收账款 / 现金收入
    try:
        total_amount = sum(calc_item_total(float(i.get('price', 0)), int(i['quantity']), tax_rate, int(i.get('is_tax_included', is_tax_included))) for i in items)
    except (ValueError, TypeError):
        return jsonify({'code': 400, 'message': '商品数量和单价必须为数字'})
    payment_type = data.get('payment_type', '应收')
    if total_amount > 0:
        if payment_type == '现结':
            FinancialModel.create({
                'type': 'receivable',
                'amount': total_amount,
                'party_type': 'customer',
                'party_id': data.get('customer_id'),
                'party_name': data.get('customer_name', ''),
                'status': 'paid',
                'order_no': order_no,
                'remark': f'销售出库单 {order_no} (现结)'
            })
            FinancialModel.create({
                'type': 'income',
                'amount': total_amount,
                'party_type': 'customer',
                'party_id': data.get('customer_id'),
                'party_name': data.get('customer_name', ''),
                'status': 'paid',
                'order_no': order_no,
                'payment_method': '现结',
                'remark': f'销售出库单 {order_no} (现结)'
            })
        elif payment_type == '应收':
            FinancialModel.create({
                'type': 'receivable',
                'amount': total_amount,
                'party_type': 'customer',
                'party_id': data.get('customer_id'),
                'party_name': data.get('customer_name', ''),
                'status': 'unpaid',
                'order_no': order_no,
                'remark': f'销售出库单 {order_no} (应收)'
            })

    log_action(user_id, '销售出库', f'单号: {order_no}')
    return jsonify({'code': 200, 'message': '出库成功', 'data': {'order_no': order_no}})


@sale_bp.route('/return', methods=['POST'])
@jwt_required()
@return_required(module='sale')
def sale_return():
    """销售退货单"""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    items = data.get('items', [])
    if not items:
        return jsonify({'code': 400, 'message': '商品明细不能为空'})

    try:
        tax_rate = float(data.get('tax_rate', 13))
        is_tax_included = int(data.get('is_tax_included', 0))
    except (ValueError, TypeError):
        return jsonify({'code': 400, 'message': '税率和含税标记必须为数字'})

    order_no = generate_order_no('TH')
    for item in items:
        product_id = item['product_id']
        try:
            quantity = int(item['quantity'])
            price = float(item.get('price', 0))
        except (ValueError, TypeError):
            return jsonify({'code': 400, 'message': '商品数量和单价必须为数字'})
        if quantity <= 0:
            return jsonify({'code': 400, 'message': '退货数量必须大于0'})
        item_is_tax_included = int(item.get('is_tax_included', is_tax_included))
        total = calc_item_total(price, quantity, tax_rate, item_is_tax_included)
        # 增加库存
        ProductModel.update_stock(product_id, quantity)
        RecordModel.create({
            'type': 'sale_return',
            'order_no': order_no,
            'product_id': product_id,
            'quantity': quantity,
            'price': price,
            'total': -total,
            'party_type': 'customer',
            'party_id': data.get('customer_id'),
            'party_name': data.get('customer_name', ''),
            'operator': data.get('operator', ''),
            'delivery_type': data.get('delivery_type', ''),
            'tax_rate': tax_rate,
            'is_tax_included': item_is_tax_included,
            'remark': data.get('remark', ''),
            'payment_type': data.get('payment_type', ''),
            'item_remark': item.get('item_remark', '')
        })

    log_action(user_id, '销售退货', f'单号: {order_no}')
    return jsonify({'code': 200, 'message': '退货成功', 'data': {'order_no': order_no}})


@sale_bp.route('/records', methods=['GET'])
@jwt_required()
def list_sale_records():
    """销售记录"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    keyword = request.args.get('keyword', '')
    tax_included = request.args.get('tax_included')
    try:
        tax_included = int(tax_included) if tax_included is not None else None
    except (ValueError, TypeError):
        tax_included = None
    records = _build_sale_records(start_date, end_date, keyword, tax_included)
    return jsonify({'code': 200, 'data': records})


@sale_bp.route('/records/export', methods=['GET'])
@jwt_required()
@download_required(module='sale')
def export_sale_records():
    """导出销售记录"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    keyword = request.args.get('keyword', '')
    tax_included = request.args.get('tax_included')
    try:
        tax_included = int(tax_included) if tax_included is not None else None
    except (ValueError, TypeError):
        tax_included = None
    records = _build_sale_records(start_date, end_date, keyword, tax_included)
    data = []
    for r in records:
        payment_type = r.get('payment_type', '') or ''
        payment_status = r.get('payment_status', '')
        if payment_type == '现结':
            status_label = '现结'
        elif payment_status == 'paid':
            status_label = '已收款'
        else:
            status_label = '应收'
        tax_amount = _calc_tax_amount(abs(float(r.get('total', 0) or 0)), r.get('tax_rate', 13))
        data.append({
            '单据编号': r['order_no'],
            '类型': '销售出库' if r['type'] == 'sale_out' else '销售退货',
            '客户': r.get('party_name', ''),
            '商品': r.get('product_name', ''),
            '型号': r.get('product_spec', ''),
            '数量': abs(r.get('quantity', 0) or 0),
            '单价': round(float(r.get('price', 0) or 0), 2),
            '金额': round(abs(float(r.get('total', 0) or 0)), 2),
            '税额': round(tax_amount, 2),
            '配送方式': r.get('delivery_type', ''),
            '付款方式': status_label,
            '含税': '含税' if r.get('is_tax_included') else '不含税',
            '经手人': r.get('operator', ''),
            '备注': r.get('item_remark', ''),
            '时间': r.get('created_at', '')
        })
    return jsonify({'code': 200, 'data': data})


@sale_bp.route('/records/<int:record_id>', methods=['DELETE'])
@jwt_required()
@delete_required(module='sale')
def delete_sale_record(record_id):
    """删除销售记录（恢复库存）"""
    try:
        user_id = int(get_jwt_identity())
    except Exception:
        return jsonify({'code': 401, 'message': '登录信息无效'})

    record = RecordModel.get_by_id(record_id)
    if not record:
        return jsonify({'code': 404, 'message': '记录不存在'})

    try:
        # 安全获取数量
        try:
            qty = int(record.get('quantity') or 0)
        except (ValueError, TypeError):
            qty = 0

        # 安全获取关键字段
        record_type = record.get('type')
        product_id = record.get('product_id')
        order_no = record.get('order_no', '') or ''

        # 恢复库存（销售出库删除时加回库存，销售退货删除时扣减库存）
        if product_id:
            try:
                if record_type == 'sale_out':
                    ProductModel.update_stock(product_id, qty)
                elif record_type == 'sale_return':
                    ProductModel.update_stock(product_id, -qty)
            except Exception as e:
                print(f'恢复库存失败: {e}')
                return jsonify({'code': 500, 'message': f'恢复库存失败: {str(e)}'})

        # 检查同单号是否还有其他记录，如果没有则删除财务记录；否则更新财务记录金额
        if order_no:
            try:
                remaining = RecordModel.get_by_order_no(order_no, exclude_id=record_id)
                if not remaining:
                    FinancialModel.delete_by_order_no(order_no)
                else:
                    # 更新财务记录金额为剩余记录的总金额
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
            print(f'删除记录失败: {e}')
            return jsonify({'code': 500, 'message': f'删除记录失败: {str(e)}'})

        log_action(user_id, '删除销售记录', f"删除记录ID: {record_id}, 单号: {order_no}")
        return jsonify({'code': 200, 'message': '删除成功'})
    except Exception as e:
        print(f'删除销售记录失败: {e}')
        return jsonify({'code': 500, 'message': f'删除失败: {str(e)}'})


@sale_bp.route('/logs', methods=['GET'])
@jwt_required()
def list_sale_logs():
    """查询操作日志（销售相关）"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    keyword = request.args.get('keyword', '')
    conn = get_db_connection()
    cursor = conn.cursor()
    sql = '''
        SELECT l.*, u.name as user_name, u.username
        FROM logs l
        LEFT JOIN users u ON l.user_id = u.id
        WHERE 1=1
    '''
    params = []
    if start_date:
        sql += ' AND l.created_at >= ?'
        params.append(start_date)
    if end_date:
        sql += ' AND l.created_at <= ?'
        params.append(end_date + ' 23:59:59')
    if keyword:
        sql += ' AND (l.action LIKE ? OR l.detail LIKE ? OR u.name LIKE ?)'
        params.extend([f'%{keyword}%', f'%{keyword}%', f'%{keyword}%'])
    sql += ' ORDER BY l.id DESC LIMIT 2000'
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()
    data = []
    for row in rows:
        r = dict(row)
        data.append({
            'id': r.get('id'),
            'user_id': r.get('user_id'),
            'user_name': r.get('user_name') or r.get('username') or '',
            'action': r.get('action', ''),
            'detail': r.get('detail', ''),
            'created_at': r.get('created_at', '')
        })
    return jsonify({'code': 200, 'data': data})
