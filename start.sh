#!/bin/bash
# Script de inicio para Flask-SocketIO con gevent en Render

echo "Iniciando servidor con gevent..."
echo "Puerto configurado: $PORT"

# Usar gunicorn con configuración desde archivo
exec gunicorn -c gunicorn_config.py app:app
