from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from middleware.auth import admin_required, create_required, edit_required, delete_required, download_required
from models.product import ProductModel, CategoryModel
from models.supplier import SupplierModel
from models.record import RecordModel
from models.user import UserModel
from models.financial import FinancialModel
from models.db import get_db_connection
from utils.logger import log_action
from utils.code_generator import generate_daily_serial
import csv
import io
import sqlite3
import openpyxl

products_bp = Blueprint('products', __name__, url_prefix='/api/products')

@products_bp.route('', methods=['GET'])
@jwt_required()
def list_products():
    """商品列表（含实时库存）"""
    keyword = request.args.get('keyword', '')
    category_id = request.args.get('category_id', type=int)
    supplier_id = request.args.get('supplier_id', type=int)
    products = ProductModel.list_all(keyword, category_id, supplier_id=supplier_id)
    
    # 为每个商品计算实时库存
    product_ids = [p['id'] for p in products]
    stock_map = {}
    if product_ids:
        conn = get_db_connection()
        cursor = conn.cursor()
        placeholders = ','.join('?' * len(product_ids))
        cursor.execute(
            f'''
            SELECT product_id,
                COALESCE(SUM(CASE 
                    WHEN type IN ('purchase_in', 'sale_return') THEN quantity
                    WHEN type IN ('sale_out', 'purchase_return') THEN -quantity
                    WHEN type = 'stock_check' THEN quantity
                    ELSE 0
                END), 0) as stock
            FROM records
            WHERE product_id IN ({placeholders})
            GROUP BY product_id
            ''',
            product_ids
        )
        for row in cursor.fetchall():
            stock_map[row['product_id']] = row['stock']
        conn.close()
    
    for p in products:
        p['stock'] = stock_map.get(p['id'], 0)
    
    return jsonify({'code': 200, 'data': products})

@products_bp.route('/<int:product_id>', methods=['GET'])
@jwt_required()
def get_product(product_id):
    """商品详情"""
    product = ProductModel.get_by_id(product_id)
    if not product:
        return jsonify({'code': 404, 'message': '商品不存在'})
    return jsonify({'code': 200, 'data': product})

@products_bp.route('', methods=['POST'])
@jwt_required()
@create_required(module='product')
def create_product():
    """新增商品"""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    if not data.get('name'):
        return jsonify({'code': 400, 'message': '商品名称不能为空'})
    # 如果未提供编码且选择了供应商，自动生成编码：供应商前缀 + 年月日 + 5位递增号
    if not data.get('code') and data.get('supplier_id'):
        supplier = SupplierModel.get_by_id(data['supplier_id'])
        prefix = supplier.get('code_prefix', '') if supplier else ''
        data['code'] = generate_daily_serial(prefix, 'products', 'code', date_format='%Y%m', serial_digits=4)
    if not data.get('code'):
        return jsonify({'code': 400, 'message': '商品编码不能为空'})
    try:
        product_id = ProductModel.create(data)
    except sqlite3.IntegrityError as e:
        return jsonify({'code': 400, 'message': f'商品编码已存在或数据冲突: {str(e)}'})
    except Exception as e:
        return jsonify({'code': 500, 'message': f'保存失败: {str(e)}'})

    # 如果有初始库存，自动创建入库记录
    stock = int(data.get('stock', 0) or 0)
    if stock > 0:
        try:
            user = UserModel.get_by_id(user_id)
            operator_name = user.get('name', '') if user else ''
            supplier = SupplierModel.get_by_id(data.get('supplier_id')) if data.get('supplier_id') else None
            supplier_name = supplier.get('name', '') if supplier else ''
            price = float(data.get('cost_excl', 0) or 0)
            total = price * stock
            RecordModel.create({
                'type': 'purchase_in',
                'order_no': generate_daily_serial('RK', 'records', 'order_no'),
                'product_id': product_id,
                'quantity': stock,
                'price': price,
                'total': total,
                'party_type': 'supplier',
                'party_id': data.get('supplier_id'),
                'party_name': supplier_name,
                'operator': operator_name,
                'tax_rate': data.get('tax_rate', 13),
                'is_tax_included': 0,
                'remark': '新增商品自动入库'
            })
        except Exception:
            pass

    log_action(user_id, '新增商品', f"新增商品: {data['name']}")
    return jsonify({'code': 200, 'message': '新增成功', 'data': {'id': product_id}})

@products_bp.route('/<int:product_id>', methods=['PUT'])
@jwt_required()
@edit_required(module='product')
def update_product(product_id):
    """修改商品"""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    if not data.get('code') or not data.get('name'):
        return jsonify({'code': 400, 'message': '商品编码和名称不能为空'})
    ProductModel.update(product_id, data)
    log_action(user_id, '修改商品', f"修改商品ID: {product_id}")
    return jsonify({'code': 200, 'message': '修改成功'})

@products_bp.route('/<int:product_id>', methods=['DELETE'])
@jwt_required()
@delete_required(module='product')
def delete_product(product_id):
    """删除商品"""
    user_id = int(get_jwt_identity())
    ProductModel.delete(product_id)
    log_action(user_id, '删除商品', f"删除商品ID: {product_id}")
    return jsonify({'code': 200, 'message': '删除成功'})

@products_bp.route('/export', methods=['GET'])
@jwt_required()
@download_required(module='product')
def export_products():
    """导出商品"""
    products = ProductModel.list_all()
    data = []
    for p in products:
        data.append({
            '编码': p['code'],
            '名称': p['name'],
            '供应商': p.get('supplier_name', ''),
            '规格': p.get('spec', ''),
            '单位': p.get('unit', ''),
            '售价(不含税)': p.get('price_excl', 0),
            '售价(含税)': p.get('price_incl', 0),
            '成本(不含税)': p.get('cost_excl', 0),
            '成本(含税)': p.get('cost_incl', 0),
            '库存': p.get('stock', 0),
            '备注': p.get('remark', '')
        })
    return jsonify({'code': 200, 'data': data})

@products_bp.route('/import', methods=['POST'])
@jwt_required()
@create_required(module='product')
def import_products():
    """导入商品（支持 Excel .xlsx/.xls）"""
    user_id = int(get_jwt_identity())
    file = request.files.get('file')
    if not file:
        return jsonify({'code': 400, 'message': '请选择文件'})

    filename = (file.filename or '').lower()
    if not filename.endswith(('.xlsx', '.xls')):
        return jsonify({'code': 400, 'message': '请上传 Excel 文件（.xlsx 或 .xls）'})

    # 导入前必须选择供应商
    try:
        supplier_id = int(request.form.get('default_supplier_id') or 0) or None
    except (ValueError, TypeError):
        supplier_id = None
    if not supplier_id:
        return jsonify({'code': 400, 'message': '导入前请先选择供应商'})

    supplier = SupplierModel.get_by_id(supplier_id)
    if not supplier:
        return jsonify({'code': 400, 'message': '选择的供应商不存在'})

    try:
        file_bytes = file.read()
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
    except Exception as e:
        return jsonify({'code': 400, 'message': f'无法读取 Excel 文件: {str(e)}'})

    if not rows:
        return jsonify({'code': 400, 'message': 'Excel 文件为空'})

    headers = [str(h).strip() if h is not None else '' for h in rows[0]]

    def get_col_index(name):
        try:
            return headers.index(name)
        except ValueError:
            return None

    count = 0
    for row in rows[1:]:
        values = [str(v).strip() if v is not None else '' for v in row]
        def get_value(name):
            idx = get_col_index(name)
            return values[idx] if idx is not None and idx < len(values) else ''

        name = get_value('名称')
        if not name:
            continue

        try:
            price_excl = float(get_value('售价(不含税)') or 0)
        except ValueError:
            price_excl = 0
        try:
            price_incl = float(get_value('售价(含税)') or 0)
        except ValueError:
            price_incl = 0
        try:
            cost_excl = float(get_value('成本(不含税)') or 0)
        except ValueError:
            cost_excl = 0
        try:
            cost_incl = float(get_value('成本(含税)') or 0)
        except ValueError:
            cost_incl = 0
        # 根据供应商前缀自动生成编码
        prefix = supplier.get('code_prefix', '') or ''
        code = generate_daily_serial(prefix, 'products', 'code', date_format='%Y%m', serial_digits=4)

        data = {
            'code': code,
            'name': name,
            'supplier_id': supplier_id,
            'spec': get_value('型号'),
            'unit': get_value('单位') or '件',
            'price_excl': price_excl,
            'price_incl': price_incl,
            'cost_excl': cost_excl,
            'cost_incl': cost_incl,
            'stock': 0,
            'remark': get_value('备注')
        }

        try:
            ProductModel.create(data)
            count += 1
        except Exception:
            pass
    log_action(user_id, '导入商品', f"导入商品数量: {count}")
    return jsonify({'code': 200, 'message': f'成功导入 {count} 条商品'})

# 分类管理
@products_bp.route('/categories', methods=['GET'])
@jwt_required()
def list_categories():
    """分类列表"""
    categories = CategoryModel.list_all()
    return jsonify({'code': 200, 'data': categories})

@products_bp.route('/categories', methods=['POST'])
@jwt_required()
@create_required(module='product')
def create_category():
    """新增分类"""
    data = request.get_json()
    name = data.get('name', '')
    if not name:
        return jsonify({'code': 400, 'message': '分类名称不能为空'})
    category_id = CategoryModel.create(name)
    return jsonify({'code': 200, 'message': '新增成功', 'data': {'id': category_id}})

@products_bp.route('/categories/<int:category_id>', methods=['DELETE'])
@jwt_required()
@delete_required(module='product')
def delete_category(category_id):
    """删除分类"""
    CategoryModel.delete(category_id)
    return jsonify({'code': 200, 'message': '删除成功'})


@products_bp.route('/<int:product_id>/adjust-stock', methods=['POST'])
@jwt_required()
@edit_required(module='product')
def adjust_stock(product_id):
    """直接调整库存（正数入库，负数出库）"""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    delta = int(data.get('delta', 0))
    if delta == 0:
        return jsonify({'code': 400, 'message': '调整数量不能为0'})

    product = ProductModel.get_by_id(product_id)
    if not product:
        return jsonify({'code': 404, 'message': '商品不存在'})

    current_stock = product.get('stock', 0) or 0
    new_stock = current_stock + delta
    if new_stock < 0:
        return jsonify({'code': 400, 'message': '库存不足，无法出库'})

    ProductModel.update_stock(product_id, delta)

    user = UserModel.get_by_id(user_id)
    operator_name = user.get('name', '') if user else ''
    price = float(product.get('cost_excl', 0) or 0)
    total = abs(delta) * price
    remark = data.get('remark', '')

    if delta > 0:
        RecordModel.create({
            'type': 'purchase_in',
            'order_no': generate_daily_serial('RK', 'records', 'order_no'),
            'product_id': product_id,
            'quantity': delta,
            'price': price,
            'total': total,
            'party_type': 'supplier',
            'party_id': product.get('supplier_id'),
            'party_name': product.get('supplier_name', ''),
            'operator': operator_name,
            'tax_rate': product.get('tax_rate', 13),
            'is_tax_included': 0,
            'remark': (remark + ' ' if remark else '') + f'直接入库(原库存:{current_stock})'
        })
        log_action(user_id, '直接入库', f"商品 [{product['name']}] 入库 {delta}，原库存: {current_stock}")
    else:
        RecordModel.create({
            'type': 'stock_check',
            'order_no': generate_daily_serial('CK', 'records', 'order_no'),
            'product_id': product_id,
            'quantity': abs(delta),
            'price': price,
            'total': total,
            'party_type': '',
            'party_id': None,
            'party_name': '',
            'operator': operator_name,
            'tax_rate': product.get('tax_rate', 13),
            'is_tax_included': 0,
            'remark': (remark + ' ' if remark else '') + f'直接出库(原库存:{current_stock})'
        })
        log_action(user_id, '直接出库', f"商品 [{product['name']}] 出库 {abs(delta)}，原库存: {current_stock}")

    return jsonify({'code': 200, 'message': f'调整成功，当前库存: {new_stock}'})


@products_bp.route('/<int:product_id>/inbound', methods=['POST'])
@jwt_required()
@create_required(module='purchase')
def product_inbound(product_id):
    """商品直接入库"""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    quantity = int(data.get('quantity', 0))
    if quantity <= 0:
        return jsonify({'code': 400, 'message': '入库数量必须大于0'})

    product = ProductModel.get_by_id(product_id)
    if not product:
        return jsonify({'code': 404, 'message': '商品不存在'})

    supplier_id = data.get('supplier_id') or product.get('supplier_id')
    supplier = SupplierModel.get_by_id(supplier_id) if supplier_id else None
    supplier_name = supplier.get('name', '') if supplier else ''

    price = float(data.get('price', 0) or product.get('cost_excl', 0) or 0)
    total = price * quantity

    ProductModel.update_stock(product_id, quantity)

    user = UserModel.get_by_id(user_id)
    operator_name = user.get('name', '') if user else ''

    order_no = generate_daily_serial('RK', 'records', 'order_no')
    payment_type = data.get('payment_type', '现结')

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
        'operator': operator_name,
        'tax_rate': product.get('tax_rate', 13),
        'is_tax_included': 0,
        'payment_type': payment_type,
        'remark': data.get('remark', '直接入库')
    })

    # 生成应付账款 / 现金支出
    if total > 0:
        if payment_type == '现结':
            FinancialModel.create({
                'type': 'payable',
                'amount': total,
                'party_type': 'supplier',
                'party_id': supplier_id,
                'party_name': supplier_name,
                'status': 'paid',
                'order_no': order_no,
                'remark': f'商品入库 {order_no} (现结)'
            })
            FinancialModel.create({
                'type': 'expense',
                'amount': total,
                'party_type': 'supplier',
                'party_id': supplier_id,
                'party_name': supplier_name,
                'status': 'paid',
                'order_no': order_no,
                'payment_method': '现结',
                'remark': f'商品入库 {order_no} (现结)'
            })
        elif payment_type == '应付':
            FinancialModel.create({
                'type': 'payable',
                'amount': total,
                'party_type': 'supplier',
                'party_id': supplier_id,
                'party_name': supplier_name,
                'status': 'unpaid',
                'order_no': order_no,
                'remark': f'商品入库 {order_no} (应付)'
            })

    log_action(user_id, '商品入库', f"商品 [{product['name']}] 入库 {quantity}，单价: {price:.2f}")
    return jsonify({'code': 200, 'message': f'入库成功，当前库存: {(product.get("stock", 0) or 0) + quantity}'})


@products_bp.route('/suggest-code', methods=['GET'])
@jwt_required()
def suggest_code():
    """获取建议商品编码"""
    supplier_id = request.args.get('supplier_id', type=int)
    prefix = ''
    if supplier_id:
        supplier = SupplierModel.get_by_id(supplier_id)
        prefix = supplier.get('code_prefix', '') if supplier else ''
    code = generate_daily_serial(prefix, 'products', 'code', date_format='%Y%m', serial_digits=4)
    return jsonify({'code': 200, 'data': {'code': code}})


@products_bp.route('/<int:product_id>/records', methods=['GET'])
@jwt_required()
def product_records(product_id):
    """获取商品库存变动记录"""
    records = RecordModel.get_stock_records(product_id=product_id)
    return jsonify({'code': 200, 'data': records})


@products_bp.route('/sale-search', methods=['GET'])
@jwt_required()
def sale_search():
    """销售出库商品搜索：默认显示最近销售的5种商品"""
    keyword = request.args.get('keyword', '')
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if not keyword:
        # 返回最近有销售记录的5种商品
        sql = '''
            SELECT p.*, s.name as supplier_name
            FROM products p
            INNER JOIN (
                SELECT product_id, MAX(created_at) as max_date
                FROM records
                WHERE type IN ('sale_out', 'sale_return')
                GROUP BY product_id
                ORDER BY max_date DESC
                LIMIT 5
            ) latest ON p.id = latest.product_id
            LEFT JOIN suppliers s ON p.supplier_id = s.id
            ORDER BY latest.max_date DESC
        '''
        cursor.execute(sql)
    else:
        # 从所有商品中模糊搜索
        sql = '''
            SELECT p.*, s.name as supplier_name
            FROM products p
            LEFT JOIN suppliers s ON p.supplier_id = s.id
            WHERE (p.name LIKE ? OR p.code LIKE ? OR p.spec LIKE ?)
            ORDER BY p.id DESC
            LIMIT 50
        '''
        cursor.execute(sql, (f'%{keyword}%', f'%{keyword}%', f'%{keyword}%'))
    
    rows = cursor.fetchall()
    
    # 为每个商品计算实时库存
    product_ids = [row['id'] for row in rows]
    stock_map = {}
    if product_ids:
        placeholders = ','.join('?' * len(product_ids))
        cursor.execute(
            f'''
            SELECT product_id,
                COALESCE(SUM(CASE 
                    WHEN type IN ('purchase_in', 'sale_return') THEN quantity
                    WHEN type IN ('sale_out', 'purchase_return') THEN -quantity
                    WHEN type = 'stock_check' THEN quantity
                    ELSE 0
                END), 0) as stock
            FROM records
            WHERE product_id IN ({placeholders})
            GROUP BY product_id
            ''',
            product_ids
        )
        for row in cursor.fetchall():
            stock_map[row['product_id']] = row['stock']
    
    conn.close()
    data = []
    for row in rows:
        r = dict(row)
        r['stock'] = stock_map.get(r['id'], 0)
        data.append(r)
    return jsonify({'code': 200, 'data': data})
