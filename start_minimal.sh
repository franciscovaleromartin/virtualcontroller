#!/bin/bash
# Script de inicio MÍNIMO para probar Render

echo "========================================"
echo "[MINIMAL] Iniciando prueba mínima..."
echo "[MINIMAL] Puerto: $PORT"
echo "[MINIMAL] Python: $(python --version 2>&1)"
echo "========================================"

# Comando simple de gunicorn sin gevent
gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 120 --access-logfile - --error-logfile - --log-level debug app_minimal:app
