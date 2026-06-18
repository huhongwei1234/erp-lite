"""
ERP Lite WSGI 入口文件
使用 waitress 作为生产级 WSGI 服务器
"""
import os
import sys

# 将 backend 目录加入 Python 路径，确保能导入 config 等模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app import app
from waitress import serve

if __name__ == '__main__':
    # host='0.0.0.0' 表示监听所有网卡，允许局域网内其他设备访问
    # port=5001 为默认端口
    serve(app, host='0.0.0.0', port=5001)
