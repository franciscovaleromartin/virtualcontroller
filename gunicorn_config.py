"""
Configuración de Gunicorn para Flask-SocketIO con gevent
"""

import multiprocessing
import os

# Número de workers
# Para gevent con SocketIO, usar 1 worker para evitar problemas de estado compartido
workers = 1

# Tipo de worker - gevent para Flask-SocketIO con async_mode='gevent'
worker_class = 'gevent'

# Timeout para mantener conexiones WebSocket vivas (mayor para WebSocket)
timeout = 300

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
