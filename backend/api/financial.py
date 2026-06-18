from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from middleware.auth import edit_required, download_required, receive_required
from models.financial import FinancialModel
from utils.logger import log_action
import csv
import io

financial_bp = Blueprint('financial', __name__, url_prefix='/api/financial')

@financial_bp.route('/receivables', methods=['GET'])
@jwt_required()
def list_receivables():
    """应收账款列表"""
    keyword = request.args.get('keyword', '')
    records = FinancialModel.list_all(fin_type='receivable', status='unpaid', keyword=keyword)
    return jsonify({'code': 200, 'data': records})

@financial_bp.route('/receive', methods=['POST'])
@jwt_required()
@receive_required(module='finance')
def receive_payment():
    """收款"""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    fin_id = data.get('financial_id')
    try:
        amount = float(data.get('amount', 0))
    except (ValueError, TypeError):
        return jsonify({'code': 400, 'message': '金额必须为数字'})
    
    order_no = ''
    if fin_id:
        fin = FinancialModel.get_by_id(fin_id)
        if not fin:
            return jsonify({'code': 404, 'message': '记录不存在'})
        FinancialModel.update_status(fin_id, 'paid')
        order_no = fin.get('order_no', '')
        remark = f'销售出库单 {order_no} 收款' if order_no else f'收款: {fin["party_name"]}, 金额: {amount}'
    else:
        remark = f'收款: {data.get("party_name", "")}, 金额: {amount}'
    
    # 记录收入流水
    FinancialModel.create({
        'type': 'income',
        'amount': amount,
        'party_type': data.get('party_type', ''),
        'party_id': data.get('party_id'),
        'party_name': data.get('party_name', ''),
        'status': 'paid',
        'order_no': order_no,
        'remark': remark,
        'payment_method': data.get('payment_method', '')
    })
    
    log_action(user_id, '收款', remark)
    return jsonify({'code': 200, 'message': '收款成功'})

@financial_bp.route('/cash-flow', methods=['GET'])
@jwt_required()
def cash_flow():
    """收支流水"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    keyword = request.args.get('keyword', '')
    fin_type = request.args.get('type')
    payment_method = request.args.get('payment_method')
    # 支持传入 income/expense 筛选类型
    records = FinancialModel.list_all(fin_type=fin_type, start_date=start_date, end_date=end_date, keyword=keyword, payment_method=payment_method)
    # 只保留收支记录
    records = [r for r in records if r['type'] in ('income', 'expense')]
    return jsonify({'code': 200, 'data': records})

@financial_bp.route('/cash-flow/export', methods=['GET'])
@jwt_required()
@download_required(module='cash_flow')
def export_cash_flow():
    """导出收支流水"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    keyword = request.args.get('keyword', '')
    fin_type = request.args.get('type')
    payment_method = request.args.get('payment_method')
    records = FinancialModel.list_all(fin_type=fin_type, start_date=start_date, end_date=end_date, keyword=keyword, payment_method=payment_method)
    records = [r for r in records if r['type'] in ('income', 'expense')]
    data = []
    for r in records:
        party_type_map = {'customer': '客户', 'supplier': '供应商'}
        data.append({
            '类型': '收入' if r['type'] == 'income' else '支出',
            '对象类型': party_type_map.get(r.get('party_type', ''), r.get('party_type', '')),
            '单号': r.get('order_no', ''),
            '金额': r.get('amount', 0),
            '往来方': r.get('party_name', ''),
            '支付方式': r.get('payment_method', ''),
            '备注': r.get('remark', ''),
            '日期': r.get('created_at', '')
        })
    return jsonify({'code': 200, 'data': data})

@financial_bp.route('/payables', methods=['GET'])
@jwt_required()
def list_payables():
    """应付账款列表"""
    keyword = request.args.get('keyword', '')
    records = FinancialModel.list_all(fin_type='payable', status='unpaid', keyword=keyword)
    return jsonify({'code': 200, 'data': records})


@financial_bp.route('/pay', methods=['POST'])
@jwt_required()
@receive_required(module='finance')
def pay_payment():
    """付款"""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    fin_id = data.get('financial_id')
    try:
        amount = float(data.get('amount', 0))
    except (ValueError, TypeError):
        return jsonify({'code': 400, 'message': '金额必须为数字'})

    order_no = ''
    if fin_id:
        fin = FinancialModel.get_by_id(fin_id)
        if not fin:
            return jsonify({'code': 404, 'message': '记录不存在'})
        FinancialModel.update_status(fin_id, 'paid')
        order_no = fin.get('order_no', '')
        remark = f'采购入库单 {order_no} 付款' if order_no else f'付款: {fin["party_name"]}, 金额: {amount}'
    else:
        remark = f'付款: {data.get("party_name", "")}, 金额: {amount}'

    # 记录支出流水
    FinancialModel.create({
        'type': 'expense',
        'amount': amount,
        'party_type': data.get('party_type', ''),
        'party_id': data.get('party_id'),
        'party_name': data.get('party_name', ''),
        'status': 'paid',
        'order_no': order_no,
        'remark': remark,
        'payment_method': data.get('payment_method', '')
    })

    log_action(user_id, '付款', remark)
    return jsonify({'code': 200, 'message': '付款成功'})


@financial_bp.route('/pending-count', methods=['GET'])
@jwt_required()
def pending_count():
    """未处理应收应付数量"""
    counts = FinancialModel.get_pending_count()
    return jsonify({'code': 200, 'data': {
        'receivable': counts.get('receivable', 0),
        'payable': counts.get('payable', 0)
    }})

@financial_bp.route('/summary', methods=['GET'])
@jwt_required()
def financial_summary():
    """财务汇总"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    summary = FinancialModel.get_cash_flow(start_date, end_date)
    return jsonify({
        'code': 200,
        'data': {
            'income': summary.get('income', 0),
            'expense': summary.get('expense', 0),
            'profit': summary.get('income', 0) - summary.get('expense', 0)
        }
    })
