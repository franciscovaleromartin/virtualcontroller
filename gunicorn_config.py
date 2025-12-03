"""
Configuración de Gunicorn para Flask-SocketIO con gevent
"""

import multiprocessing
import os
import sys

# Obtener puerto de la variable de entorno (Render usa PORT)
port = os.getenv('PORT', '10000')

print(f"[Gunicorn Config] Puerto detectado: {port}", flush=True)
print(f"[Gunicorn Config] Python: {sys.version}", flush=True)

# Número de workers
# Para gevent con SocketIO, usar 1 worker para evitar problemas de estado compartido
workers = 1

# Tipo de worker - gevent para Flask-SocketIO con async_mode='gevent'
worker_class = 'gevent'

# Timeout para mantener conexiones WebSocket vivas
timeout = 300
graceful_timeout = 120

# Keep alive timeout
keepalive = 5

# Bind to all interfaces with the PORT from environment
bind = f"0.0.0.0:{port}"

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'
capture_output = True
enable_stdio_inheritance = True

# NO preload app para permitir monkey patching de gevent
preload_app = False

# Max requests before worker restart
max_requests = 1000
max_requests_jitter = 50

# Worker connections
worker_connections = 1000

# Worker temporary directory (importante para Render)
worker_tmp_dir = '/dev/shm'

def on_starting(server):
    """Called just before the master process is initialized."""
    print(f"[Gunicorn] Iniciando servidor en puerto {port}", flush=True)
    print(f"[Gunicorn] Bind address: {bind}", flush=True)

def when_ready(server):
    """Called just after the server is started."""
    print(f"[Gunicorn] ✓ Servidor listo y escuchando en {bind}", flush=True)
    print(f"[Gunicorn] ✓ Health check disponible en http://0.0.0.0:{port}/health", flush=True)

def worker_int(worker):
    """Called when a worker receives SIGINT or SIGQUIT."""
    print(f"[Gunicorn] Worker {worker.pid} recibió señal de interrupción", flush=True)

def worker_abort(worker):
    """Called when a worker is killed due to a timeout."""
    print(f"[Gunicorn] Worker {worker.pid} abortado por timeout", flush=True)

def post_worker_init(worker):
    """Called just after a worker has been forked."""
    print(f"[Gunicorn] Worker {worker.pid} inicializado", flush=True)
