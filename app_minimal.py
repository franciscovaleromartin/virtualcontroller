"""
Aplicación mínima para probar despliegue en Render
"""
import sys
print(f"[MINIMAL] Python: {sys.version}", flush=True)
print(f"[MINIMAL] Iniciando app mínima...", flush=True)

from flask import Flask, jsonify
from datetime import datetime

print(f"[MINIMAL] Flask importado", flush=True)

app = Flask(__name__)

print(f"[MINIMAL] Flask app creada", flush=True)

@app.route('/')
def index():
    return jsonify({
        'status': 'ok',
        'message': 'Virtual Controller Minimal Test',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/health')
def health():
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat()
    }), 200

print(f"[MINIMAL] Rutas configuradas", flush=True)
print(f"[MINIMAL] App lista para servir", flush=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
