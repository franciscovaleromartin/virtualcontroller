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
timeout = 120
graceful_timeout = 120

# Keep alive timeout
keepalive = 5

# Bind
port = os.getenv('PORT', '5000')
bind = f"0.0.0.0:{port}"

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Preload app for better performance
preload_app = False

# Max requests before worker restart
max_requests = 1000
max_requests_jitter = 50

# Worker connections
worker_connections = 1000

def on_starting(server):
    """Called just before the master process is initialized."""
    print(f"[Gunicorn] Iniciando servidor en puerto {port}")
    print(f"[Gunicorn] Bind address: {bind}")

def when_ready(server):
    """Called just after the server is started."""
    print(f"[Gunicorn] Servidor listo y escuchando en {bind}")

def on_reload(server):
    """Called to recycle workers during a reload."""
    print("[Gunicorn] Recargando workers")
