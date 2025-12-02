"""
Configuración de Gunicorn para Flask-SocketIO con threading
"""

import multiprocessing
import os

# Número de workers (threads en este caso)
# Para threading con SocketIO, usar 1 worker
workers = 1

# Tipo de worker - threads para Flask-SocketIO con async_mode='threading'
worker_class = 'sync'

# Número de threads por worker
threads = 4

# Timeout para mantener conexiones WebSocket vivas
timeout = 120

# Keep alive timeout
keepalive = 5

# Bind
bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Preload app for better performance
preload_app = False

# Max requests before worker restart
max_requests = 1000
max_requests_jitter = 50
