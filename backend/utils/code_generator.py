from datetime import datetime
from models.db import get_db_connection


def generate_daily_serial(prefix, table, column, date_format='%Y%m%d', serial_digits=5):
    """
    生成按周期递增的流水编号。
    默认格式: {prefix}{YYYYMMDD}{NNNNN}
    支持自定义日期格式和流水号位数。

    :param prefix: 编号前缀（如 'XS', 'CG', 'my'）
    :param table: 查询的数据表名
    :param column: 查询的列名（如 'order_no', 'code'）
    :param date_format: 日期格式，默认 '%Y%m%d'
    :param serial_digits: 流水号位数，默认 5
    :return: 生成的编号字符串
    """
    date_str = datetime.now().strftime(date_format)
    pattern = f"{prefix}{date_str}%"
    expected_len = len(prefix) + len(date_str) + serial_digits

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT {column} FROM {table} WHERE {column} LIKE ? AND LENGTH({column}) = ? ORDER BY {column} DESC LIMIT 1",
        (pattern, expected_len)
    )
    row = cursor.fetchone()
    conn.close()

    if row and row[0]:
        last_code = row[0]
        try:
            serial = int(last_code[-serial_digits:]) + 1
        except ValueError:
            serial = 1
    else:
        serial = 1

    return f"{prefix}{date_str}{serial:0{serial_digits}d}"
