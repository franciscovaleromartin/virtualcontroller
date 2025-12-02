#!/bin/bash
# Script de inicio para Flask-SocketIO con gevent en Render

echo "Iniciando servidor con gevent..."

# Usar gunicorn con worker de gevent
exec gunicorn \
  --worker-class gevent \
  --workers 1 \
  --timeout 300 \
  --bind 0.0.0.0:$PORT \
  --access-logfile - \
  --error-logfile - \
  --log-level info \
  app:app
