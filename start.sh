#!/bin/bash
# Script de inicio para Flask-SocketIO con gevent en Render

echo "[START] Iniciando Virtual Controller..."
echo "[START] Puerto: $PORT"
echo "[START] Python: $(python --version 2>&1)"
echo "[START] Gunicorn: $(gunicorn --version 2>&1)"
echo "[START] Directorio: $(pwd)"

# Verificar archivos críticos
if [ ! -f "app.py" ]; then
    echo "[START ERROR] app.py no encontrado"
    exit 1
fi

if [ ! -f "gunicorn_config.py" ]; then
    echo "[START ERROR] gunicorn_config.py no encontrado"
    exit 1
fi

echo "[START] ✓ Archivos verificados"
echo "[START] Iniciando gunicorn con gevent worker..."

# Iniciar gunicorn con configuración
exec gunicorn -c gunicorn_config.py app:app
