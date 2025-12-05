"""
Configuración de Gunicorn para Flask
"""

import multiprocessing
import os
import sys

# Obtener puerto de la variable de entorno (Render usa PORT)
port = os.getenv('PORT', '10000')

print(f"[Gunicorn Config] Puerto detectado: {port}", flush=True)
print(f"[Gunicorn Config] Python: {sys.version}", flush=True)

# Número de workers - usar múltiples workers para mejor rendimiento
workers = min(multiprocessing.cpu_count() * 2 + 1, 4)

# Tipo de worker - gthread para aplicaciones Flask estándar
worker_class = 'gthread'
threads = 2

# Timeout para requests HTTP (aumentado para deploy)
timeout = 300
graceful_timeout = 60

# Keep alive timeout
keepalive = 5

# Bind to all interfaces with the PORT from environment
bind = f"0.0.0.0:{port}"

# Logging personalizado para silenciar health checks
import logging

class HealthCheckFilter(logging.Filter):
    """Filtro para silenciar health checks de Render"""
    def filter(self, record):
        # Obtener el mensaje del log
        message = record.getMessage()
        # Silenciar requests a /health, /healthz, /api/health
        health_endpoints = ['/health ', '/healthz ', '/api/health ']
        return not any(endpoint in message for endpoint in health_endpoints)

# Configuración de logs
accesslog = '-'  # stdout
errorlog = '-'   # stderr
loglevel = 'info'
capture_output = True
enable_stdio_inheritance = True

# Aplicar filtro personalizado
logconfig_dict = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'health_check_filter': {
            '()': HealthCheckFilter,
        }
    },
    'formatters': {
        'generic': {
            'format': '%(asctime)s [%(process)d] [%(levelname)s] %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
            'class': 'logging.Formatter'
        },
        'access': {
            'format': '%(message)s',
            'class': 'logging.Formatter'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'generic',
            'stream': 'ext://sys.stdout'
        },
        'access_console': {
            'class': 'logging.StreamHandler',
            'formatter': 'access',
            'filters': ['health_check_filter'],
            'stream': 'ext://sys.stdout'
        },
        'error_console': {
            'class': 'logging.StreamHandler',
            'formatter': 'generic',
            'stream': 'ext://sys.stderr'
        }
    },
    'loggers': {
        'gunicorn.error': {
            'handlers': ['error_console'],
            'level': 'INFO',
            'propagate': False
        },
        'gunicorn.access': {
            'handlers': ['access_console'],
            'level': 'INFO',
            'propagate': False
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console']
    }
}

# Preload app desactivado para evitar timeouts en deploy
preload_app = False

# Max requests before worker restart
max_requests = 1000
max_requests_jitter = 50

# Worker temporary directory (importante para Render)
worker_tmp_dir = '/dev/shm'

def on_starting(server):
    """Called just before the master process is initialized."""
    print(f"[Gunicorn] Iniciando servidor en puerto {port}", flush=True)
    print(f"[Gunicorn] Bind address: {bind}", flush=True)
    print(f"[Gunicorn] Workers: {workers}, Threads: {threads}", flush=True)

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
