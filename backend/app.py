import sys
import os
from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
import yaml

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(BASE_DIR, 'config.yaml')
FRONTEND_DIR = os.path.join(BASE_DIR, 'frontend')

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {}

config = load_config()

app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = config.get('jwt', {}).get('secret_key', 'erp-lite-secret-key')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = config.get('jwt', {}).get('expire_hours', 24) * 3600

CORS(app)
jwt = JWTManager(app)

print(f"BASE_DIR: {BASE_DIR}")
print(f"FRONTEND_DIR: {FRONTEND_DIR}")

@app.route('/')
def serve_index():
    return send_from_directory(FRONTEND_DIR, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    if path.startswith('api/'):
        return jsonify({'code': 404, 'message': 'Not Found'}), 404
    file_path = os.path.join(FRONTEND_DIR, path)
    if os.path.exists(file_path):
        return send_from_directory(FRONTEND_DIR, path)
    return send_from_directory(FRONTEND_DIR, 'index.html')

if __name__ == '__main__':
    host = config.get('server', {}).get('host', '0.0.0.0')
    port = config.get('server', {}).get('port', 5001)
    debug = config.get('server', {}).get('debug', False)
    app.run(host=host, port=port, debug=debug)
