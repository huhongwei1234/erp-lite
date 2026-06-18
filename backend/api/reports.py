from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from middleware.auth import download_required
import sqlite3
import datetime
from config import DB_PATH

reports_bp = Blueprint('reports', __name__, url_prefix='/api/reports')

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

@reports_bp.route('/sales', methods=['GET'])
@jwt_required()
def sale_report():
    """销售报表"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    conn = get_db()
    cursor = conn.cursor()
    
    # 判断按日还是按月分组：如果日期跨度 <= 31 天则按日分组
    group_by_day = False
    if start_date and end_date:
        try:
            s = datetime.datetime.strptime(start_date, '%Y-%m-%d')
            e = datetime.datetime.strptime(end_date, '%Y-%m-%d')
            if (e - s).days <= 31:
                group_by_day = True
        except ValueError:
            pass
    
    if group_by_day:
        sql = '''
            SELECT 
                strftime('%Y-%m-%d', created_at) as date,
                SUM(CASE WHEN type='sale_out' AND is_tax_included=1 THEN ABS(total) WHEN type='sale_out' AND is_tax_included=0 THEN ABS(total) / (1 + tax_rate / 100.0) ELSE 0 END) as sale_amount,
                SUM(CASE WHEN type='sale_return' AND is_tax_included=1 THEN ABS(total) WHEN type='sale_return' AND is_tax_included=0 THEN ABS(total) / (1 + tax_rate / 100.0) ELSE 0 END) as return_amount,
                SUM(CASE WHEN type='sale_out' THEN ABS(quantity) ELSE 0 END) as sale_qty,
                SUM(CASE WHEN type='sale_return' THEN ABS(quantity) ELSE 0 END) as return_qty
            FROM records
            WHERE type IN ('sale_out', 'sale_return')
        '''
        params = []
        if start_date:
            sql += ' AND created_at >= ?'
            params.append(start_date)
        if end_date:
            sql += ' AND created_at <= ?'
            params.append(end_date + ' 23:59:59')
        sql += " GROUP BY strftime('%Y-%m-%d', created_at) ORDER BY date"
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        
        # 补全日期范围中无数据的日期为0
        from collections import OrderedDict
        date_data = OrderedDict()
        s = datetime.datetime.strptime(start_date, '%Y-%m-%d')
        e = datetime.datetime.strptime(end_date, '%Y-%m-%d')
        d = s
        while d <= e:
            date_str = d.strftime('%Y-%m-%d')
            date_data[date_str] = {
                'sale_amount': 0,
                'return_amount': 0,
                'sale_qty': 0,
                'return_qty': 0
            }
            d += datetime.timedelta(days=1)
        
        for row in rows:
            date_data[row['date']] = {
                'sale_amount': row['sale_amount'] or 0,
                'return_amount': row['return_amount'] or 0,
                'sale_qty': row['sale_qty'] or 0,
                'return_qty': row['return_qty'] or 0
            }
        
        data = []
        for date_str, md in date_data.items():
            sale_amount = md['sale_amount']
            return_amount = md['return_amount']
            data.append({
                'date': date_str,
                'sale_amount': sale_amount,
                'return_amount': return_amount,
                'net_amount': sale_amount - return_amount,
                'sale_qty': md['sale_qty'],
                'return_qty': md['return_qty']
            })
        
        return jsonify({'code': 200, 'data': data})
    
    # 按月分组（原逻辑）
    year = datetime.datetime.now().year
    sql = '''
        SELECT 
            strftime('%Y-%m', created_at) as month,
            SUM(CASE WHEN type='sale_out' AND is_tax_included=1 THEN ABS(total) WHEN type='sale_out' AND is_tax_included=0 THEN ABS(total) / (1 + tax_rate / 100.0) ELSE 0 END) as sale_amount,
            SUM(CASE WHEN type='sale_return' AND is_tax_included=1 THEN ABS(total) WHEN type='sale_return' AND is_tax_included=0 THEN ABS(total) / (1 + tax_rate / 100.0) ELSE 0 END) as return_amount,
            SUM(CASE WHEN type='sale_out' THEN ABS(quantity) ELSE 0 END) as sale_qty,
            SUM(CASE WHEN type='sale_return' THEN ABS(quantity) ELSE 0 END) as return_qty
        FROM records
        WHERE type IN ('sale_out', 'sale_return')
    '''
    params = []
    if start_date:
        sql += ' AND created_at >= ?'
        params.append(start_date)
    if end_date:
        sql += ' AND created_at <= ?'
        params.append(end_date + ' 23:59:59')
    sql += " GROUP BY strftime('%Y-%m', created_at) ORDER BY month"
    
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()
    
    month_data = {}
    for row in rows:
        month_data[row['month']] = {
            'sale_amount': row['sale_amount'] or 0,
            'return_amount': row['return_amount'] or 0,
            'sale_qty': row['sale_qty'] or 0,
            'return_qty': row['return_qty'] or 0
        }
    
    data = []
    for m in range(1, 13):
        month_str = f"{year}-{m:02d}"
        md = month_data.get(month_str, {})
        sale_amount = md.get('sale_amount', 0)
        return_amount = md.get('return_amount', 0)
        data.append({
            'date': month_str,
            'sale_amount': sale_amount,
            'return_amount': return_amount,
            'net_amount': sale_amount - return_amount,
            'sale_qty': md.get('sale_qty', 0),
            'return_qty': md.get('return_qty', 0)
        })
    
    return jsonify({'code': 200, 'data': data})

@reports_bp.route('/profit/export', methods=['GET'])
@jwt_required()
@download_required(module='profit_report')
def export_profit_report():
    """导出利润报表"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    conn = get_db()
    cursor = conn.cursor()
    
    year = datetime.datetime.now().year
    sql = '''
        SELECT 
            strftime('%Y-%m', r.created_at) as month,
            SUM(CASE WHEN r.type='sale_out' THEN ABS(r.total) / (1 + r.tax_rate / 100.0) WHEN r.type='sale_return' THEN -ABS(r.total) / (1 + r.tax_rate / 100.0) ELSE 0 END) as revenue,
            SUM(CASE WHEN r.type='sale_out' AND r.is_tax_included=1 THEN ABS(r.total) - ABS(r.total) / (1 + r.tax_rate / 100.0) WHEN r.type='sale_return' AND r.is_tax_included=1 THEN -(ABS(r.total) - ABS(r.total) / (1 + r.tax_rate / 100.0)) ELSE 0 END) as tax_amount,
            SUM(CASE WHEN r.type='sale_out' THEN ABS(r.quantity) * COALESCE(p.cost_excl, 0) WHEN r.type='sale_return' THEN -ABS(r.quantity) * COALESCE(p.cost_excl, 0) ELSE 0 END) as cost
        FROM records r
        LEFT JOIN products p ON r.product_id = p.id
        WHERE r.type IN ('sale_out', 'sale_return')
    '''
    params = []
    if start_date:
        sql += ' AND r.created_at >= ?'
        params.append(start_date)
    if end_date:
        sql += ' AND r.created_at <= ?'
        params.append(end_date + ' 23:59:59')
    sql += " GROUP BY strftime('%Y-%m', r.created_at) ORDER BY month"
    
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()
    
    month_data = {}
    for row in rows:
        month_data[row['month']] = {
            'revenue': row['revenue'] or 0,
            'tax_amount': row['tax_amount'] or 0,
            'cost': row['cost'] or 0
        }
    
    data = []
    for m in range(1, 13):
        month_str = f"{year}-{m:02d}"
        md = month_data.get(month_str, {})
        revenue = md.get('revenue', 0)
        tax_amount = md.get('tax_amount', 0)
        cost = md.get('cost', 0)
        gross_profit = revenue - cost
        data.append({
            '月份': month_str,
            '不含税收入': round(revenue, 2),
            '税额': round(tax_amount, 2),
            '销售成本': round(cost, 2),
            '毛利': round(gross_profit, 2),
            '毛利率(%)': round(gross_profit / revenue * 100, 2) if revenue > 0 else 0
        })
    
    return jsonify({'code': 200, 'data': data})

@reports_bp.route('/sales/export', methods=['GET'])
@jwt_required()
@download_required(module='report')
def export_sale_report():
    """导出销售报表"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    conn = get_db()
    cursor = conn.cursor()
    
    year = datetime.datetime.now().year
    sql = '''
        SELECT 
            strftime('%Y-%m', created_at) as month,
            SUM(CASE WHEN type='sale_out' AND is_tax_included=1 THEN ABS(total) WHEN type='sale_out' AND is_tax_included=0 THEN ABS(total) / (1 + tax_rate / 100.0) ELSE 0 END) as sale_amount,
            SUM(CASE WHEN type='sale_return' AND is_tax_included=1 THEN ABS(total) WHEN type='sale_return' AND is_tax_included=0 THEN ABS(total) / (1 + tax_rate / 100.0) ELSE 0 END) as return_amount,
            SUM(CASE WHEN type='sale_out' THEN ABS(quantity) ELSE 0 END) as sale_qty,
            SUM(CASE WHEN type='sale_return' THEN ABS(quantity) ELSE 0 END) as return_qty
        FROM records
        WHERE type IN ('sale_out', 'sale_return')
    '''
    params = []
    if start_date:
        sql += ' AND created_at >= ?'
        params.append(start_date)
    if end_date:
        sql += ' AND created_at <= ?'
        params.append(end_date + ' 23:59:59')
    sql += " GROUP BY strftime('%Y-%m', created_at) ORDER BY month"
    
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()
    
    month_data = {}
    for row in rows:
        month_data[row['month']] = {
            'sale_amount': row['sale_amount'] or 0,
            'return_amount': row['return_amount'] or 0,
            'sale_qty': row['sale_qty'] or 0,
            'return_qty': row['return_qty'] or 0
        }
    
    data = []
    for m in range(1, 13):
        month_str = f"{year}-{m:02d}"
        md = month_data.get(month_str, {})
        sale_amount = md.get('sale_amount', 0)
        return_amount = md.get('return_amount', 0)
        data.append({
            '月份': month_str,
            '销售金额': round(sale_amount, 2),
            '退货金额': round(return_amount, 2),
            '净销售额': round(sale_amount - return_amount, 2),
            '销售数量': md.get('sale_qty', 0),
            '退货数量': md.get('return_qty', 0)
        })
    
    return jsonify({'code': 200, 'data': data})

@reports_bp.route('/profit', methods=['GET'])
@jwt_required()
def profit_report():
    """利润报表"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    conn = get_db()
    cursor = conn.cursor()
    
    # 统计销售收入、成本、毛利，按月份分组并补全1-12月
    year = datetime.datetime.now().year
    sql = '''
        SELECT 
            strftime('%Y-%m', r.created_at) as month,
            SUM(CASE WHEN r.type='sale_out' THEN ABS(r.total) / (1 + r.tax_rate / 100.0) WHEN r.type='sale_return' THEN -ABS(r.total) / (1 + r.tax_rate / 100.0) ELSE 0 END) as revenue,
            SUM(CASE WHEN r.type='sale_out' AND r.is_tax_included=1 THEN ABS(r.total) - ABS(r.total) / (1 + r.tax_rate / 100.0) WHEN r.type='sale_return' AND r.is_tax_included=1 THEN -(ABS(r.total) - ABS(r.total) / (1 + r.tax_rate / 100.0)) ELSE 0 END) as tax_amount,
            SUM(CASE WHEN r.type='sale_out' THEN ABS(r.quantity) * COALESCE(p.cost_excl, 0) WHEN r.type='sale_return' THEN -ABS(r.quantity) * COALESCE(p.cost_excl, 0) ELSE 0 END) as cost
        FROM records r
        LEFT JOIN products p ON r.product_id = p.id
        WHERE r.type IN ('sale_out', 'sale_return')
    '''
    params = []
    if start_date:
        sql += ' AND r.created_at >= ?'
        params.append(start_date)
    if end_date:
        sql += ' AND r.created_at <= ?'
        params.append(end_date + ' 23:59:59')
    sql += " GROUP BY strftime('%Y-%m', r.created_at) ORDER BY month"
    
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()
    
    # 构建月份到数据的映射
    month_data = {}
    for row in rows:
        month_data[row['month']] = {
            'revenue': row['revenue'] or 0,
            'tax_amount': row['tax_amount'] or 0,
            'cost': row['cost'] or 0
        }
    
    # 补全1-12月
    data = []
    for m in range(1, 13):
        month_str = f"{year}-{m:02d}"
        md = month_data.get(month_str, {})
        revenue = md.get('revenue', 0)
        tax_amount = md.get('tax_amount', 0)
        cost = md.get('cost', 0)
        data.append({
            'date': month_str,
            'revenue': revenue,
            'tax_amount': tax_amount,
            'cost': cost,
            'gross_profit': revenue - cost,
            'profit_margin': round((revenue - cost) / revenue * 100, 2) if revenue > 0 else 0
        })
    
    return jsonify({'code': 200, 'data': data})
