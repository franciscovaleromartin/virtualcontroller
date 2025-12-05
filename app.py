import sys
print(f"[STARTUP] Python version: {sys.version}", flush=True)
print(f"[STARTUP] Iniciando aplicación...", flush=True)

from flask import Flask, render_template, jsonify, request, redirect, session, url_for
import requests
from datetime import datetime, timedelta
import json
import os
import re
from dotenv import load_dotenv
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import quote
import db  # Importar módulo de base de datos
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import atexit

# Google OAuth y Sheets API
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

print(f"[STARTUP] Imports completados exitosamente", flush=True)

load_dotenv()

print(f"[STARTUP] Variables de entorno cargadas", flush=True)

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configurar logging para silenciar health checks
import logging
from werkzeug.serving import WSGIRequestHandler

class HealthCheckFilter(logging.Filter):
    """Filtro para silenciar logs de health checks"""
    def filter(self, record):
        # Filtrar requests a /health, /healthz, /api/health
        return not any(path in record.getMessage() for path in ['/health', '/healthz'])

# Aplicar filtro al logger de werkzeug (servidor de desarrollo de Flask)
log = logging.getLogger('werkzeug')
log.addFilter(HealthCheckFilter())

print(f"[STARTUP] Flask app creada", flush=True)

CLICKUP_CLIENT_ID = os.getenv('CLICKUP_CLIENT_ID')
CLICKUP_CLIENT_SECRET = os.getenv('CLICKUP_CLIENT_SECRET')
CLICKUP_API_TOKEN = os.getenv('CLICKUP_API_TOKEN')  # Token personal para webhooks
REDIRECT_URI = os.getenv('REDIRECT_URI')  # URL de callback de OAuth

# Configuración de email para alertas (Brevo API - más confiable que SMTP)
BREVO_API_KEY = os.getenv('BREVO_API_KEY', '')
SMTP_EMAIL = os.getenv('SMTP_EMAIL', '')  # Email del remitente

# Configuración de webhook
WEBHOOK_SECRET_TOKEN = os.getenv('WEBHOOK_SECRET_TOKEN', '')

# Configuración de Google OAuth y Sheets
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:5000/oauth/google/callback')

# Scopes necesarios para Google Sheets
GOOGLE_SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/userinfo.email',
    'openid'
]

# ID del Google Sheet donde se exportarán los datos
GOOGLE_SHEET_ID = '1Q1WUv9Cteq4McQh4MPCQFdK9_9stSjMvtVFKVW2VP1c'
SHEET_NAME = 'Hoja 1'

# Almacenamiento en memoria de alertas por tarea
# Estructura: {tarea_id: {aviso_activado, email_aviso, aviso_horas, aviso_minutos, ultima_actualizacion, ultimo_envio_email}}
alertas_tareas = {}

alertas_config = {}

# Caché de tareas actualizado vía webhook
# Estructura: {tarea_id: {datos_tarea, timestamp_actualizacion}}
tareas_cache = {}

# ============================================================================
# SCHEDULER DE BACKEND PARA VERIFICACIÓN AUTOMÁTICA DE ALERTAS
# ============================================================================

def verificar_alertas_automaticamente():
    """
    Función ejecutada por el scheduler de backend cada 5 minutos.
    Verifica todas las alertas activas independientemente del frontend.
    """
    with app.app_context():
        try:
            print("\n" + "⏰"*40)
            print("⏰ SCHEDULER BACKEND: Verificación automática de alertas")
            print(f"⏰ Timestamp: {datetime.now().isoformat()}")
            print("⏰"*40)

            # Obtener todas las alertas activas
            alertas_activas = db.get_all_active_alerts()
            print(f"📋 [SCHEDULER] Alertas activas encontradas: {len(alertas_activas)}")

            if len(alertas_activas) == 0:
                print("⏰ [SCHEDULER] No hay alertas activas. Esperando próxima ejecución...")
                print("⏰"*40 + "\n")
                return

            alertas_enviadas = 0

            for alerta in alertas_activas:
                tarea_id = alerta['task_id']
                tarea_nombre = alerta['task_name']

                try:
                    # Obtener tarea de BD
                    tarea_bd = db.get_task(tarea_id)
                    if not tarea_bd or tarea_bd['status'] != 'en_progreso':
                        continue

                    # Calcular tiempo
                    tiempo_max_segundos = (alerta['aviso_horas'] * 3600) + (alerta['aviso_minutos'] * 60)
                    tiempo_data = db.calculate_task_time_in_progress(tarea_id)
                    tiempo_en_progreso = tiempo_data['total_seconds']

                    # Sumar sesión actual si aplica
                    if tiempo_data['is_currently_in_progress'] and tiempo_data['current_session_start']:
                        try:
                            session_start = datetime.fromisoformat(tiempo_data['current_session_start'])
                            from datetime import timezone
                            now = datetime.now(timezone.utc)
                            tiempo_sesion = (now - session_start).total_seconds()
                            tiempo_en_progreso += tiempo_sesion
                        except:
                            pass

                    # Verificar si superó el límite (con margen de 30s)
                    MARGEN_TOLERANCIA = 30
                    if tiempo_en_progreso >= (tiempo_max_segundos - MARGEN_TOLERANCIA):
                        print(f"🚨 [SCHEDULER] Alerta activada para tarea: {tarea_nombre}")

                        horas = int(tiempo_en_progreso // 3600)
                        minutos = int((tiempo_en_progreso % 3600) // 60)
                        tiempo_str = f"{horas} horas y {minutos} minutos"

                        proyecto_nombre = db.get_task_project_name(tarea_id)
                        tarea_url = alerta['task_url']

                        # Enviar email
                        if enviar_email_alerta(alerta['email_aviso'], tarea_nombre, proyecto_nombre, tarea_url, tiempo_str):
                            print(f"✅ [SCHEDULER] Email enviado para: {tarea_nombre}")
                            db.deactivate_task_alert(tarea_id)
                            alertas_enviadas += 1
                        else:
                            print(f"❌ [SCHEDULER] Error al enviar email para: {tarea_nombre}")

                except Exception as e:
                    print(f"❌ [SCHEDULER] Error procesando {tarea_nombre}: {str(e)}")

            print("⏰"*40)
            print(f"⏰ SCHEDULER: Verificación completada - {alertas_enviadas} alertas enviadas")
            print("⏰"*40 + "\n")

        except Exception as e:
            print(f"❌ [SCHEDULER] Error crítico: {str(e)}")
            import traceback
            traceback.print_exc()

# Inicializar scheduler solo en el worker principal
# Usar file lock para asegurar que solo un worker ejecute el scheduler
import fcntl

def init_scheduler():
    """Inicializa el scheduler solo en un worker (usando file lock)"""
    lock_file_path = '/tmp/scheduler_lock'

    try:
        # Intentar abrir/crear el archivo de lock
        lock_file = open(lock_file_path, 'w')
        # Intentar obtener lock exclusivo (no bloqueante)
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

        # Si llegamos aquí, somos el worker principal
        print(f"[STARTUP] Este worker obtuvo el lock del scheduler (PID: {os.getpid()})", flush=True)

        scheduler = BackgroundScheduler()
        scheduler.add_job(
            func=verificar_alertas_automaticamente,
            trigger=IntervalTrigger(minutes=5),
            id='verificar_alertas_job',
            name='Verificar alertas de tareas automáticamente',
            replace_existing=True
        )

        scheduler.start()
        print("[STARTUP] ✓ Scheduler de backend iniciado (verificación cada 5 minutos)", flush=True)

        # Asegurar shutdown cuando se cierre la app
        atexit.register(lambda: scheduler.shutdown())

        return True

    except IOError:
        # Otro worker ya tiene el lock
        print(f"[STARTUP] Otro worker ya tiene el scheduler activo (PID: {os.getpid()})", flush=True)
        return False

# Intentar inicializar el scheduler
init_scheduler()

# ============================================================================

@app.route('/health')
def health():
    """Health check endpoint for Render"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'service': 'virtualcontroller'
    }), 200

@app.route('/healthz')
def healthz():
    """Kubernetes-style health check endpoint"""
    return jsonify({
        'status': 'ok',
        'service': 'virtualcontroller'
    }), 200

@app.route('/api/health')
def api_health():
    """Alternative health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'virtualcontroller',
        'timestamp': datetime.now().isoformat()
    }), 200

@app.route('/api/endpoints')
def list_endpoints():
    """Lista todos los endpoints disponibles para diagnóstico"""
    endpoints = []
    for rule in app.url_map.iter_rules():
        if rule.endpoint != 'static':
            endpoints.append({
                'endpoint': rule.rule,
                'methods': sorted(list(rule.methods - {'HEAD', 'OPTIONS'}))
            })

    return jsonify({
        'total_endpoints': len(endpoints),
        'endpoints': sorted(endpoints, key=lambda x: x['endpoint']),
        'smtp_endpoints': {
            'status': '/api/smtp-status (GET)',
            'test': '/api/test-email (POST)'
        },
        'timestamp': datetime.now().isoformat()
    }), 200

@app.route('/')
def inicio():
    code = request.args.get('code')

    print(f"[DEBUG] Ruta '/' accedida. Code presente: {bool(code)}")

    # Si viene el código de OAuth, procesarlo
    if code:
        print(f"[DEBUG] Procesando OAuth callback...")
        return handle_oauth_callback(code)

    # Si no hay access token, redirigir a login
    if 'access_token' not in session:
        print(f"[DEBUG] No hay access_token, redirigiendo a login")
        return redirect(url_for('login'))

    print(f"[DEBUG] Usuario autenticado, mostrando página principal")
    return render_template('index.html')

def handle_oauth_callback(code):
    print(f"[DEBUG] OAuth callback recibido con código: {code[:10]}...")
    token_url = "https://api.clickup.com/api/v2/oauth/token"

    # ClickUp requiere estos parámetros como query params
    params = {
        'client_id': CLICKUP_CLIENT_ID,
        'client_secret': CLICKUP_CLIENT_SECRET,
        'code': code
    }

    print(f"[DEBUG] Enviando request a ClickUp para obtener token...")
    print(f"[DEBUG] Client ID: {CLICKUP_CLIENT_ID[:10]}...")

    try:
        # ClickUp OAuth requiere parámetros como query params, no como body
        response = requests.post(token_url, params=params)

        print(f"[DEBUG] Respuesta de ClickUp: Status {response.status_code}")
        print(f"[DEBUG] Response body: {response.text}")

        if response.status_code != 200:
            print(f"[ERROR] Error al obtener token: {response.text}")
            return f"Error al obtener token (Status {response.status_code}): {response.text}", 400

        token_data = response.json()

        # Verificar que el access_token esté presente
        if 'access_token' not in token_data:
            print(f"[ERROR] No se recibió access_token en la respuesta: {token_data}")
            return "Error: No se recibió access_token de ClickUp", 400

        session['access_token'] = token_data['access_token']

        print(f"[DEBUG] Token obtenido y guardado en sesión correctamente")

        return redirect('/')

    except Exception as e:
        print(f"[ERROR] Excepción en OAuth callback: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"Error: {str(e)}", 500

@app.route('/login')
def login():
    # Validar que las variables de entorno estén configuradas
    if not CLICKUP_CLIENT_ID:
        return "Error: CLICKUP_CLIENT_ID no está configurado en .env", 500

    if not CLICKUP_CLIENT_SECRET:
        return "Error: CLICKUP_CLIENT_SECRET no está configurado en .env", 500

    # Usar REDIRECT_URI si está configurada, sino generar automáticamente
    if REDIRECT_URI:
        callback_url = REDIRECT_URI
        print(f"[DEBUG] Usando REDIRECT_URI de variable de entorno: {callback_url}")
    else:
        callback_url = url_for('inicio', _external=True)
        print(f"[DEBUG] Generando callback_url automáticamente: {callback_url}")

    print(f"[DEBUG] CLIENT_ID: {CLICKUP_CLIENT_ID}")

    # Codificar la URL de callback para asegurar compatibilidad
    encoded_callback_url = quote(callback_url, safe='')
    auth_url = f"https://app.clickup.com/api?client_id={CLICKUP_CLIENT_ID}&redirect_uri={encoded_callback_url}"

    print(f"[DEBUG] Callback URL original: {callback_url}")
    print(f"[DEBUG] Callback URL codificada: {encoded_callback_url}")
    print(f"[DEBUG] Redirigiendo a ClickUp OAuth: {auth_url}")

    # Si hay parámetro ?debug=1, mostrar info en vez de redirigir
    if request.args.get('debug') == '1':
        return f"""
        <html>
        <head><title>Debug OAuth</title></head>
        <body style="font-family: monospace; padding: 20px;">
            <h1>Información de Debug OAuth</h1>
            <h2>Variables de Entorno:</h2>
            <p><strong>CLICKUP_CLIENT_ID:</strong> {CLICKUP_CLIENT_ID}</p>
            <p><strong>CLICKUP_CLIENT_SECRET:</strong> {'✓ Configurado' if CLICKUP_CLIENT_SECRET else '✗ NO configurado'}</p>

            <h2>URLs Generadas:</h2>
            <p><strong>Callback URL:</strong> <code>{callback_url}</code></p>
            <p><strong>URL de Autorización:</strong></p>
            <textarea style="width: 100%; height: 100px; font-family: monospace;">{auth_url}</textarea>

            <h2>¿Qué verificar en ClickUp?</h2>
            <ol>
                <li>Ve a <a href="https://app.clickup.com/settings/apps" target="_blank">https://app.clickup.com/settings/apps</a></li>
                <li>Busca la aplicación con CLIENT_ID: <strong>{CLICKUP_CLIENT_ID}</strong></li>
                <li>Verifica que la <strong>Redirect URL</strong> registrada sea EXACTAMENTE: <code>{callback_url}</code></li>
                <li>Verifica que la aplicación esté <strong>Activa</strong> (no deshabilitada)</li>
            </ol>

            <h2>Problemas comunes:</h2>
            <ul>
                <li>❌ La URL tiene <code>http</code> en ClickUp pero aquí genera <code>https</code> (o viceversa)</li>
                <li>❌ La URL tiene <code>www</code> en ClickUp pero aquí no (o viceversa)</li>
                <li>❌ El CLIENT_ID no existe o fue copiado mal</li>
                <li>❌ La aplicación OAuth fue eliminada o deshabilitada en ClickUp</li>
            </ul>

            <br><br>
            <a href="/login" style="background: #667eea; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                Intentar Login Normal
            </a>
        </body>
        </html>
        """

    return redirect(auth_url)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

def fetch_task_from_clickup_api(task_id, access_token=None):
    """
    Obtiene los detalles completos de una tarea desde la API de ClickUp

    Args:
        task_id: ID de la tarea
        access_token: Token de acceso (opcional, usa el de sesión o CLICKUP_API_TOKEN)

    Returns:
        dict con los datos de la tarea o None si hay error
    """
    try:
        # Prioridad de tokens:
        # 1. Token proporcionado como argumento
        # 2. Token de sesión (si existe)
        # 3. Token de configuración CLICKUP_API_TOKEN
        if not access_token and 'access_token' in session:
            access_token = session['access_token']

        if not access_token and CLICKUP_API_TOKEN:
            access_token = CLICKUP_API_TOKEN
            print(f"[INFO] Usando CLICKUP_API_TOKEN para obtener detalles de tarea {task_id}")

        if not access_token:
            print(f"[ERROR] No hay token de acceso disponible para obtener tarea {task_id}")
            print("[ERROR] Configure CLICKUP_API_TOKEN en el archivo .env para permitir webhooks desde Make.com")
            return None

        headers = {
            'Authorization': access_token,
            'Content-Type': 'application/json'
        }

        url = f'https://api.clickup.com/api/v2/task/{task_id}'
        print(f"[INFO] Obteniendo detalles de tarea {task_id} desde API de ClickUp...")

        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            task_data = response.json()
            print(f"[INFO] Tarea {task_id} obtenida exitosamente desde API")
            return task_data
        else:
            print(f"[ERROR] Error al obtener tarea {task_id}: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        print(f"[ERROR] Excepción al obtener tarea {task_id} desde API: {str(e)}")
        return None


def parse_date_flexible(date_value):
    """
    Convierte una fecha en múltiples formatos a ISO string

    Soporta:
    - Timestamps Unix en milisegundos (int o string): "1701456488876" o 1701456488876
    - Strings ISO 8601: "2025-12-01T20:28:08.876Z"
    - Strings vacíos: ""
    - None

    Returns:
        String en formato ISO o None
    """
    if not date_value or date_value == "":
        return None

    try:
        # Si ya es un string ISO 8601, verificar y retornarlo
        if isinstance(date_value, str) and 'T' in date_value:
            # Intentar parsear para validar
            try:
                datetime.fromisoformat(date_value.replace('Z', '+00:00'))
                return date_value
            except:
                pass

        # Si es un número o string de número (timestamp Unix en ms)
        try:
            timestamp_ms = int(date_value) if isinstance(date_value, str) else date_value
            return datetime.fromtimestamp(timestamp_ms / 1000).isoformat()
        except (ValueError, TypeError):
            pass

        # Si es un string, intentar parsearlo como ISO
        if isinstance(date_value, str):
            try:
                dt = datetime.fromisoformat(date_value.replace('Z', '+00:00'))
                return dt.isoformat()
            except:
                pass

        print(f"[WARNING] No se pudo parsear fecha: {date_value} (tipo: {type(date_value)})")
        return None

    except Exception as e:
        print(f"[ERROR] Error al parsear fecha {date_value}: {str(e)}")
        return None


def parse_date_to_display(date_value):
    """
    Convierte una fecha en múltiples formatos a formato ISO con timezone UTC.
    El frontend convertirá este timestamp a la hora local del usuario.

    Returns:
        String en formato ISO con 'Z' (UTC) o timestamp actual si hay error
    """
    iso_date = parse_date_flexible(date_value)
    if iso_date:
        # Si ya tiene 'Z' o '+', retornarlo tal cual
        if iso_date.endswith('Z') or '+' in iso_date or '-' in iso_date[-6:]:
            return iso_date
        # Si no, asumir UTC y añadir 'Z'
        return iso_date + 'Z'

    # Si hay error, retornar timestamp actual en UTC
    return datetime.utcnow().isoformat() + 'Z'



@app.route('/webhook/clickup', methods=['POST'])
def webhook_clickup():
    """
    Endpoint para recibir webhooks de ClickUp (directo o vía make.com)

    Soporta eventos de ClickUp:
    - taskCreated, taskUpdated, taskDeleted, taskStatusUpdated
    - listCreated, listUpdated, listDeleted
    - folderCreated, folderUpdated, folderDeleted
    - spaceCreated, spaceUpdated

    Formatos aceptados:
    1. Webhook directo de ClickUp con estructura estándar
    2. Webhook desde make.com con formato simplificado
    3. Webhook con solo task_id (obtiene detalles desde API)

    Headers esperados:
    - X-Webhook-Token: token de seguridad
    """
    webhook_log_id = None

    try:
        # Registrar información del request para debugging
        print(f"[DEBUG] Webhook recibido - Content-Type: {request.content_type}")
        print(f"[DEBUG] Webhook recibido - User-Agent: {request.headers.get('User-Agent')}")
        print(f"[DEBUG] Webhook recibido - Content-Length: {request.content_length}")

        # Validar token de seguridad
        token_header = request.headers.get('X-Webhook-Token')
        token_query = request.args.get('token')

        if not WEBHOOK_SECRET_TOKEN:
            print("[WARNING] WEBHOOK_SECRET_TOKEN no está configurado. Se aceptan todos los webhooks.")
        elif token_header != WEBHOOK_SECRET_TOKEN and token_query != WEBHOOK_SECRET_TOKEN:
            print(f"[ERROR] Token inválido en webhook. Header: {token_header}, Query: {token_query}")
            return jsonify({'error': 'Unauthorized', 'message': 'Token inválido'}), 401

        # Obtener datos del webhook de forma más robusta
        # Usar get_json con force=True para ignorar Content-Type y silent=True para no lanzar excepciones
        data = None
        raw_data = None

        try:
            # Intentar primero con el Content-Type correcto
            data = request.get_json(silent=True)

            # Si no funciona, intentar forzar el parseo
            if data is None:
                print("[WARNING] No se pudo parsear JSON con Content-Type, intentando force=True")
                data = request.get_json(force=True, silent=True)

            # Si aún no funciona, intentar leer el body raw
            if data is None:
                raw_data = request.get_data(as_text=True)
                print(f"[DEBUG] Body raw recibido ({len(raw_data)} caracteres):")
                print(f"[DEBUG] {raw_data[:1000]}")  # Primeros 1000 caracteres para ver el problema

                if raw_data:
                    try:
                        # Intentar parsear el JSON directamente
                        data = json.loads(raw_data)
                    except json.JSONDecodeError as e:
                        print(f"[ERROR] Error al parsear JSON: {str(e)}")
                        print(f"[DEBUG] Línea con error (aproximada):")

                        # Intentar mostrar la línea con el error
                        try:
                            lines = raw_data.split('\n')
                            error_line = e.lineno - 1 if e.lineno <= len(lines) else 0
                            if error_line >= 0 and error_line < len(lines):
                                print(f"[DEBUG] Línea {e.lineno}: {lines[error_line]}")
                                print(f"[DEBUG] Posición del error: {' ' * (e.colno - 1)}^")
                        except:
                            pass

                        # Intentar limpiar problemas comunes de JSON
                        print("[INFO] Intentando limpiar JSON malformado...")
                        try:
                            # Limpiar problemas comunes:
                            # 1. Trailing commas: {"key": value,}
                            # 2. Valores undefined o null mal escritos
                            # 3. Valores vacíos: "key": , -> "key": null
                            # 4. Arrays vacíos malformados: "key": , -> "key": []
                            cleaned_data = raw_data

                            # Remover trailing commas antes de } o ]
                            cleaned_data = re.sub(r',\s*}', '}', cleaned_data)
                            cleaned_data = re.sub(r',\s*]', ']', cleaned_data)

                            # Arreglar valores vacíos: "key": , -> "key": null
                            # Primero, reemplazar arrays/objetos vacíos explícitos
                            cleaned_data = re.sub(r':\s*,', ': null,', cleaned_data)
                            cleaned_data = re.sub(r':\s*\n', ': null\n', cleaned_data)

                            # Casos específicos de Make.com donde arrays están vacíos
                            # "assignees": , -> "assignees": []
                            cleaned_data = re.sub(r'"assignees"\s*:\s*null', '"assignees": []', cleaned_data)
                            cleaned_data = re.sub(r'"tags"\s*:\s*null', '"tags": []', cleaned_data)
                            cleaned_data = re.sub(r'"custom_fields"\s*:\s*null', '"custom_fields": {}', cleaned_data)

                            # Intentar parsear el JSON limpio
                            data = json.loads(cleaned_data)
                            print("[INFO] ✓ JSON limpiado exitosamente")
                            print(f"[DEBUG] JSON limpio: {json.dumps(data, indent=2)}")

                        except json.JSONDecodeError as e2:
                            print(f"[ERROR] No se pudo limpiar el JSON: {str(e2)}")

                            # Si Make.com está enviando datos malformados, intentar extraer al menos
                            # los campos esenciales manualmente
                            print("[WARNING] Intentando extraer campos básicos del JSON malformado...")
                            try:
                                # Buscar task_id usando regex
                                task_id_match = re.search(r'"task_id"\s*:\s*"([^"]+)"', raw_data)
                                event_match = re.search(r'"event"\s*:\s*"([^"]+)"', raw_data)

                                if task_id_match:
                                    # Crear un objeto mínimo con los datos extraídos
                                    data = {
                                        'task_id': task_id_match.group(1),
                                        'event': event_match.group(1) if event_match else 'taskStatusUpdated',
                                        '_extracted_from_malformed': True,
                                        '_original_error': str(e)
                                    }
                                    print(f"[INFO] ✓ Extraído task_id: {data['task_id']}")
                                    print("[INFO] Se obtendrán los detalles completos desde la API de ClickUp")
                                else:
                                    # No se pudo extraer nada útil
                                    return jsonify({
                                        'error': 'Bad Request',
                                        'message': 'El JSON está malformado y no se pudieron extraer campos básicos',
                                        'details': str(e),
                                        'line': e.lineno,
                                        'column': e.colno,
                                        'suggestion': 'Verifica la configuración del webhook en Make.com. Asegúrate de enviar JSON válido.'
                                    }), 400
                            except Exception as e3:
                                print(f"[ERROR] No se pudieron extraer campos básicos: {str(e3)}")
                                return jsonify({
                                    'error': 'Bad Request',
                                    'message': 'El cuerpo de la solicitud no es JSON válido',
                                    'details': str(e),
                                    'line': e.lineno,
                                    'column': e.colno
                                }), 400

        except Exception as e:
            print(f"[ERROR] Excepción al obtener datos JSON: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'error': 'Bad Request',
                'message': 'Error al procesar el cuerpo de la solicitud',
                'details': str(e)
            }), 400

        if not data:
            print("[ERROR] Webhook recibido sin datos JSON o con datos vacíos")
            return jsonify({'error': 'Bad Request', 'message': 'No se recibieron datos válidos'}), 400

        print(f"[INFO] Webhook recibido: {json.dumps(data, indent=2)}")

        # Detectar tipo de evento
        event_type = data.get('event') or data.get('event_type', 'unknown')

        # Extraer IDs según el tipo de evento
        task_id = data.get('task_id')
        list_id = data.get('list_id')
        folder_id = data.get('folder_id')
        space_id = data.get('space_id')

        # Si es un evento de tarea pero faltan datos completos, obtenerlos de la API
        if 'task' in event_type.lower() and task_id:
            # Verificar si tenemos los datos mínimos necesarios
            if not data.get('task_name') and not data.get('name'):
                print(f"[INFO] Webhook incompleto detectado, obteniendo detalles de tarea {task_id} desde API...")
                task_details = fetch_task_from_clickup_api(task_id)

                if task_details:
                    # Enriquecer los datos del webhook con la información completa
                    data['task_name'] = task_details.get('name', 'Sin nombre')
                    data['status'] = task_details.get('status', {}).get('status', 'Sin estado')
                    data['list_id'] = task_details.get('list', {}).get('id')
                    data['folder_id'] = task_details.get('folder', {}).get('id')
                    data['space_id'] = task_details.get('space', {}).get('id')
                    data['url'] = task_details.get('url', '')
                    data['description'] = task_details.get('description', '')
                    data['priority'] = task_details.get('priority', {}).get('priority')
                    data['assignees'] = task_details.get('assignees', [])
                    data['date_created'] = task_details.get('date_created')
                    data['date_updated'] = task_details.get('date_updated')
                    data['due_date'] = task_details.get('due_date')
                    data['start_date'] = task_details.get('start_date')
                    data['time_estimate'] = task_details.get('time_estimate')
                    data['time_spent'] = task_details.get('time_spent')
                    data['tags'] = task_details.get('tags', [])
                    data['custom_fields'] = task_details.get('custom_fields', [])

                    # Actualizar IDs si no estaban presentes
                    if not list_id:
                        list_id = data.get('list_id')
                    if not folder_id:
                        folder_id = data.get('folder_id')
                    if not space_id:
                        space_id = data.get('space_id')

                    print(f"[INFO] Datos de tarea {task_id} enriquecidos desde API")
                else:
                    print(f"[WARNING] No se pudieron obtener detalles de la tarea {task_id} desde API")

        # Registrar webhook en base de datos
        webhook_log_id = db.log_webhook(
            event_type=event_type,
            payload=data,
            task_id=task_id,
            list_id=list_id,
            folder_id=folder_id,
            space_id=space_id
        )

        print(f"[INFO] Procesando evento '{event_type}' (webhook_log_id: {webhook_log_id})")

        # Extraer el timestamp del webhook (viene de Make.com en el nivel superior)
        webhook_timestamp = data.get('timestamp')

        # Procesar según el tipo de evento
        result = None

        if 'task' in event_type.lower():
            result = process_task_event(event_type, data, webhook_timestamp)
        elif 'list' in event_type.lower():
            result = process_list_event(event_type, data)
        elif 'folder' in event_type.lower():
            result = process_folder_event(event_type, data)
        elif 'space' in event_type.lower():
            result = process_space_event(event_type, data)
        else:
            print(f"[WARNING] Tipo de evento no reconocido: {event_type}")
            result = {'status': 'ignored', 'message': 'Evento no soportado'}

        # Marcar webhook como procesado
        db.mark_webhook_processed(webhook_log_id, error=None)

        return jsonify({
            'success': True,
            'event_type': event_type,
            'result': result,
            'timestamp': datetime.now().isoformat()
        }), 200

    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] Error al procesar webhook: {error_msg}")
        import traceback
        traceback.print_exc()

        # Marcar webhook como error si se registró
        if webhook_log_id:
            db.mark_webhook_processed(webhook_log_id, error=error_msg)

        return jsonify({'error': 'Internal Server Error', 'message': error_msg}), 500


def process_task_event(event_type, data, webhook_timestamp=None):
    """
    Procesa eventos relacionados con tareas

    Args:
        event_type: Tipo de evento (taskCreated, taskUpdated, etc.)
        data: Datos del webhook
        webhook_timestamp: Timestamp del webhook en formato ISO (opcional)
    """
    print(f"\n[WEBHOOK] ===== Recibido evento: {event_type} =====")
    print(f"[WEBHOOK] Timestamp: {datetime.now().isoformat()}")

    task_id = data.get('task_id')

    if not task_id:
        print("[WEBHOOK] ❌ ERROR: Evento de tarea sin task_id")
        return {'status': 'error', 'message': 'task_id requerido'}

    print(f"[WEBHOOK] Task ID: {task_id}")

    if event_type in ['taskDeleted', 'taskDeleted']:
        # Obtener list_id antes de eliminar
        old_task = db.get_task(task_id)
        list_id_deleted = old_task.get('list_id') if old_task else None

        # Eliminar tarea de la base de datos
        db.delete_task(task_id)
        # Eliminar del caché
        if task_id in tareas_cache:
            del tareas_cache[task_id]

        print(f"[INFO] Tarea {task_id} eliminada")
        return {'status': 'deleted', 'task_id': task_id}

    # Para taskCreated, taskUpdated, taskStatusUpdated
    task_name = data.get('task_name') or data.get('name', 'Sin nombre')
    status = data.get('status', '').lower()
    date_updated = data.get('date_updated') or data.get('date_updated_unix')
    task_url = data.get('url', '')
    list_id = data.get('list_id')
    description = data.get('description', '')
    priority = data.get('priority')
    assignees = data.get('assignees', [])
    date_created = data.get('date_created')
    due_date = data.get('due_date')
    start_date = data.get('start_date')
    time_estimate = data.get('time_estimate')
    time_spent = data.get('time_spent')
    tags = data.get('tags', [])
    custom_fields = data.get('custom_fields', [])

    # Obtener el estado anterior de la tarea
    old_task = db.get_task(task_id)
    old_status = old_task.get('status') if old_task else None
    old_status_text = old_task.get('status_text') if old_task else None

    # Determinar el estado de la tarea
    estado = 'pendiente'
    if status in ['complete', 'closed', 'completed']:
        estado = 'completada'
    elif 'progress' in status or 'review' in status or 'doing' in status:
        estado = 'en_progreso'

    # Preparar datos de tarea para guardar en BD
    task_data = {
        'id': task_id,
        'name': task_name,
        'list_id': list_id,
        'status': estado,
        'status_text': data.get('status', 'Sin estado'),
        'url': task_url,
        'description': description,
        'priority': priority,
        'assignees': assignees,
        'date_created': parse_date_flexible(date_created),
        'date_updated': parse_date_flexible(date_updated) or datetime.now().isoformat(),
        'due_date': parse_date_flexible(due_date),
        'start_date': parse_date_flexible(start_date),
        'time_estimate': time_estimate,
        'time_spent': time_spent,
        'horas_trabajadas': data.get('horas_trabajadas', 0),
        'minutos_trabajados': data.get('minutos_trabajados', 0),
        'tags': tags,
        'custom_fields': custom_fields,
        'metadata': data
    }

    # Guardar en base de datos
    db.save_task(task_data)

    # Registrar cambio de estado si ha cambiado
    if old_status != estado:
        # Usar el timestamp del webhook si está disponible, sino parse_date_flexible del date_updated
        changed_at_timestamp = None

        # Si la tarea está cambiando A estado "en_progreso" (desde cualquier otro estado),
        # usar timestamp actual UTC para que el temporizador comience desde 0
        if estado == 'en_progreso' and old_status != 'en_progreso':
            changed_at_timestamp = datetime.utcnow().isoformat() + 'Z'
            print(f"[INFO] Tarea cambiando a 'en_progreso', usando timestamp actual UTC: {changed_at_timestamp}")
        elif webhook_timestamp:
            # El timestamp del webhook ya viene en formato ISO
            changed_at_timestamp = parse_date_flexible(webhook_timestamp)
            print(f"[INFO] Usando timestamp del webhook para cambio de estado: {changed_at_timestamp}")
        elif date_updated:
            changed_at_timestamp = parse_date_flexible(date_updated)
            print(f"[INFO] Usando date_updated para cambio de estado: {changed_at_timestamp}")

        db.save_status_change(
            task_id=task_id,
            old_status=old_status,
            new_status=estado,
            old_status_text=old_status_text,
            new_status_text=data.get('status', 'Sin estado'),
            changed_at=changed_at_timestamp
        )
        print(f"[INFO] Cambio de estado registrado: {task_id} de '{old_status}' a '{estado}' en {changed_at_timestamp}")
    elif estado == 'en_progreso':
        # Si la tarea ya estaba en progreso, verificar si tiene historial
        # Si no tiene historial de entrada a "en_progreso", crear uno con timestamp actual UTC
        history = db.get_status_history(task_id)
        has_progress_entry = any(h['new_status'] == 'en_progreso' for h in history)
        if not has_progress_entry:
            changed_at_timestamp = datetime.utcnow().isoformat() + 'Z'
            db.save_status_change(
                task_id=task_id,
                old_status=None,
                new_status=estado,
                old_status_text=None,
                new_status_text=data.get('status', 'Sin estado'),
                changed_at=changed_at_timestamp
            )
            print(f"[INFO] Creado registro inicial para tarea en progreso: {task_id} con timestamp actual UTC: {changed_at_timestamp}")

    # Guardar en caché para acceso rápido
    tareas_cache[task_id] = {
        'id': task_id,
        'nombre': task_name,
        'estado': estado,
        'estado_texto': data.get('status', 'Sin estado'),
        'url': task_url,
        'fecha_actualizacion': parse_date_to_display(date_updated),
        'event_type': event_type,
        'timestamp_cache': datetime.now().isoformat(),
        'horas_trabajadas': data.get('horas_trabajadas', 0),
        'minutos_trabajados': data.get('minutos_trabajados', 0),
    }

    print(f"[INFO] Tarea {task_id} guardada en BD y caché: {task_name}")

    # Verificar alertas si está configurada
    print(f"[WEBHOOK] Verificando si la tarea {task_id} tiene alerta configurada...")
    alert = db.get_task_alert(task_id)
    if alert and alert.get('aviso_activado'):
        print(f"[WEBHOOK] ✓ Alerta encontrada y activa para tarea {task_id}")
        check_and_send_alert(task_id, task_name, task_url, date_updated, alert)
    else:
        if alert:
            print(f"[WEBHOOK] - Alerta encontrada pero desactivada para tarea {task_id}")
        else:
            print(f"[WEBHOOK] - No hay alerta configurada para tarea {task_id}")

    return {'status': 'saved', 'task_id': task_id, 'name': task_name}


def process_list_event(event_type, data):
    """Procesa eventos relacionados con listas (proyectos)"""
    list_id = data.get('list_id')
    if not list_id:
        return {'status': 'error', 'message': 'list_id requerido'}

    list_name = data.get('list_name') or data.get('name', 'Sin nombre')
    space_id = data.get('space_id')
    folder_id = data.get('folder_id')
    archived = data.get('archived', False)

    if event_type == 'listDeleted':
        print(f"[INFO] Lista {list_id} eliminada")
        return {'status': 'deleted', 'list_id': list_id}

    # Guardar lista en BD
    db.save_list(list_id, list_name, space_id, folder_id, archived, metadata=data)
    print(f"[INFO] Lista {list_id} guardada: {list_name}")

    return {'status': 'saved', 'list_id': list_id, 'name': list_name}


def process_folder_event(event_type, data):
    """Procesa eventos relacionados con carpetas (proyectos)"""
    folder_id = data.get('folder_id')
    if not folder_id:
        return {'status': 'error', 'message': 'folder_id requerido'}

    folder_name = data.get('folder_name') or data.get('name', 'Sin nombre')
    space_id = data.get('space_id')
    hidden = data.get('hidden', False)

    if event_type == 'folderDeleted':
        print(f"[INFO] Carpeta {folder_id} eliminada")
        return {'status': 'deleted', 'folder_id': folder_id}

    db.save_folder(folder_id, folder_name, space_id, hidden, metadata=data)
    print(f"[INFO] Carpeta {folder_id} guardada: {folder_name}")

    return {'status': 'saved', 'folder_id': folder_id, 'name': folder_name}


def process_space_event(event_type, data):
    """Procesa eventos relacionados con espacios"""
    space_id = data.get('space_id')
    if not space_id:
        return {'status': 'error', 'message': 'space_id requerido'}

    space_name = data.get('space_name') or data.get('name', 'Sin nombre')
    team_id = data.get('team_id')

    if event_type == 'spaceDeleted':
        print(f"[INFO] Espacio {space_id} eliminado")
        return {'status': 'deleted', 'space_id': space_id}

    db.save_space(space_id, space_name, team_id, metadata=data)
    print(f"[INFO] Espacio {space_id} guardado: {space_name}")

    return {'status': 'saved', 'space_id': space_id, 'name': space_name}


def check_and_send_alert(task_id, task_name, task_url, date_updated, alert_config):
    """Verifica y envía alerta si es necesario basándose en el tiempo total en progreso"""
    try:
        print("\n" + "="*80)
        print(f"🔔 [ALERTA] Verificando alerta para: {task_name}")
        print(f"🔔 [ALERTA] ID de tarea: {task_id}")
        print("="*80)

        # Obtener configuración de la alerta
        tiempo_max_horas = alert_config.get('aviso_horas', 0)
        tiempo_max_minutos = alert_config.get('aviso_minutos', 0)
        email_destino = alert_config.get('email_aviso')

        print(f"⚙️  [CONFIG] Límite configurado: {tiempo_max_horas}h {tiempo_max_minutos}m")
        print(f"📧 [CONFIG] Email destino: {email_destino}")

        # Validar configuración
        tiempo_max_segundos = (tiempo_max_horas * 3600) + (tiempo_max_minutos * 60)
        if tiempo_max_segundos <= 0:
            print(f"⚠️  [WARNING] Tarea {task_id} tiene tiempo máximo de 0. Saltando...")
            print("="*80 + "\n")
            return

        if not email_destino:
            print(f"⚠️  [WARNING] Tarea {task_id} no tiene email configurado. Saltando...")
            print("="*80 + "\n")
            return

        # Obtener información de la tarea desde la BD
        tarea_bd = db.get_task(task_id)
        if not tarea_bd:
            print(f"⚠️  [WARNING] Tarea {task_id} no encontrada en BD. Saltando...")
            print("="*80 + "\n")
            return

        # Verificar si la tarea está actualmente en progreso
        print(f"📊 [STATUS] Estado actual de la tarea: {tarea_bd['status']}")
        if tarea_bd['status'] != 'en_progreso':
            print(f"ℹ️  [INFO] Tarea no está en 'en_progreso'. No se verifica alerta.")
            print("="*80 + "\n")
            return

        # Calcular el tiempo total en progreso usando el historial de estados
        print("⏱️  [CALC] Calculando tiempo total en progreso...")
        tiempo_data = db.calculate_task_time_in_progress(task_id)
        tiempo_en_progreso_segundos = tiempo_data['total_seconds']

        # Si está actualmente en progreso, sumar el tiempo de la sesión actual
        if tiempo_data['is_currently_in_progress'] and tiempo_data['current_session_start']:
            try:
                session_start = datetime.fromisoformat(tiempo_data['current_session_start'])
                # Usar datetime.now() con timezone UTC para poder restar
                from datetime import timezone
                now = datetime.now(timezone.utc)
                tiempo_sesion_actual = (now - session_start).total_seconds()
                tiempo_en_progreso_segundos += tiempo_sesion_actual
                print(f"⏱️  [CALC] Sesión actual: +{tiempo_sesion_actual/3600:.2f}h")
            except Exception as e:
                print(f"⚠️  [WARNING] Error al calcular sesión actual: {str(e)}")
                # Fallback: intentar sin timezone
                try:
                    session_start_naive = datetime.fromisoformat(tiempo_data['current_session_start'].replace('+00:00', '').replace('Z', ''))
                    tiempo_sesion_actual = (datetime.utcnow() - session_start_naive).total_seconds()
                    tiempo_en_progreso_segundos += tiempo_sesion_actual
                    print(f"⏱️  [CALC] Sesión actual (fallback): +{tiempo_sesion_actual/3600:.2f}h")
                except Exception as e2:
                    print(f"⚠️  [ERROR] No se pudo calcular tiempo de sesión actual: {str(e2)}")

        horas_actuales = tiempo_en_progreso_segundos / 3600
        horas_limite = tiempo_max_segundos / 3600
        print(f"⏱️  [CALC] Tiempo en progreso: {horas_actuales:.2f}h")
        print(f"⏱️  [CALC] Límite configurado: {horas_limite:.2f}h")

        # Verificar si se superó el tiempo máximo (con margen de 30 segundos de tolerancia)
        MARGEN_TOLERANCIA = 30  # segundos
        if tiempo_en_progreso_segundos >= (tiempo_max_segundos - MARGEN_TOLERANCIA):
            print("\n" + "🚨"*20)
            print("🚨 ¡ALERTA ACTIVADA! - TIEMPO LÍMITE SUPERADO")
            print("🚨"*20)

            # Formatear el tiempo en progreso para el email
            horas = int(tiempo_en_progreso_segundos // 3600)
            minutos = int((tiempo_en_progreso_segundos % 3600) // 60)
            tiempo_en_progreso_str = f"{horas} horas y {minutos} minutos"

            # Obtener el nombre del proyecto
            proyecto_nombre = db.get_task_project_name(task_id)

            # Enviar email de alerta
            print(f"\n📤 [EMAIL] Iniciando envío de email de alerta...")
            print(f"📤 [EMAIL] Destinatario: {email_destino}")
            print(f"📤 [EMAIL] Tarea: {task_name}")
            print(f"📤 [EMAIL] Proyecto: {proyecto_nombre}")
            print(f"📤 [EMAIL] Tiempo en progreso: {tiempo_en_progreso_str}")

            email_enviado = enviar_email_alerta(
                email_destino,
                task_name,
                proyecto_nombre,
                task_url,
                tiempo_en_progreso_str
            )

            if email_enviado:
                print("\n" + "✅"*20)
                print("✅ EMAIL ENVIADO EXITOSAMENTE")
                print("✅"*20)
                print(f"✅ [RESULT] Alerta enviada a: {email_destino}")
                print(f"✅ [RESULT] Tarea: {task_name}")
                print(f"✅ [RESULT] Tiempo: {tiempo_en_progreso_str}")

                # Desactivar la alerta después del envío
                db.deactivate_task_alert(task_id)
                print(f"🔕 [RESULT] Alerta desactivada automáticamente")

                # También actualizar la caché en memoria si existe
                if task_id in alertas_tareas:
                    alertas_tareas[task_id]['aviso_activado'] = False
                    alertas_tareas[task_id]['ultimo_envio_email'] = datetime.now().isoformat()

                print("✅"*20 + "\n")
            else:
                print("\n" + "❌"*20)
                print("❌ ERROR: NO SE PUDO ENVIAR EL EMAIL")
                print("❌"*20)
                print(f"❌ [ERROR] Destinatario: {email_destino}")
                print(f"❌ [ERROR] Revisa la configuración SMTP y los logs anteriores")
                print("❌"*20 + "\n")
        else:
            diferencia = tiempo_max_segundos - tiempo_en_progreso_segundos
            print(f"✓ [OK] Tarea dentro del límite. Faltan {diferencia/3600:.2f}h para activar alerta")

        print("="*80 + "\n")

    except Exception as e:
        print("\n" + "❌"*20)
        print(f"❌ [ERROR] Error crítico al verificar alerta para tarea {task_id}")
        print(f"❌ [ERROR] {str(e)}")
        print("❌"*20)
        import traceback
        traceback.print_exc()
        print("="*80 + "\n")

@app.route('/api/webhook/tasks/cache', methods=['GET'])
def obtener_cache_tareas():
    """
    Endpoint para obtener el caché de tareas actualizadas vía webhook
    Puede filtrar por task_id específico o devolver todo el caché
    """
    try:
        task_id = request.args.get('task_id')

        if task_id:
            # Devolver una tarea específica
            if task_id in tareas_cache:
                return jsonify({
                    'success': True,
                    'task': tareas_cache[task_id]
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'message': f'Tarea {task_id} no encontrada en caché'
                }), 404
        else:
            # Devolver todo el caché
            return jsonify({
                'success': True,
                'tasks': list(tareas_cache.values()),
                'count': len(tareas_cache),
                'timestamp': datetime.now().isoformat()
            }), 200

    except Exception as e:
        print(f"[ERROR] Error al obtener caché: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/webhook/tasks/cache', methods=['DELETE'])
def limpiar_cache_tareas():
    """
    Endpoint para limpiar el caché de tareas (útil para testing y mantenimiento)
    """
    try:
        global tareas_cache
        tareas_cache = {}

        print("[INFO] Caché de tareas limpiado")

        return jsonify({
            'success': True,
            'message': 'Caché limpiado correctamente'
        }), 200

    except Exception as e:
        print(f"[ERROR] Error al limpiar caché: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/webhook/stats', methods=['GET'])
def obtener_stats_webhooks():
    """
    Endpoint para obtener estadísticas de webhooks procesados
    """
    try:
        stats = db.get_webhook_stats()

        return jsonify({
            'success': True,
            'stats': stats,
            'timestamp': datetime.now().isoformat()
        }), 200

    except Exception as e:
        print(f"[ERROR] Error al obtener estadísticas: {str(e)}")
        return jsonify({'error': str(e)}), 500

def get_headers():
    if 'access_token' not in session:
        return None
    
    return {
        'Authorization': session['access_token'],
        'Content-Type': 'application/json'
    }

@app.route('/api/spaces')
def get_spaces():
    try:
        headers = get_headers()
        if not headers:
            return jsonify({'error': 'No autenticado', 'redirect': '/login'}), 401

        teams_response = requests.get('https://api.clickup.com/api/v2/team', headers=headers, timeout=10)

        if teams_response.status_code == 401:
            session.clear()
            return jsonify({'error': 'Sesión expirada', 'redirect': '/login'}), 401

        if teams_response.status_code != 200:
            return jsonify({
                'error': 'Error al conectar con ClickUp',
                'details': teams_response.text,
                'status': teams_response.status_code
            }), 400

        teams = teams_response.json()['teams']

        all_spaces = []
        for team in teams:
            spaces_response = requests.get(
                f'https://api.clickup.com/api/v2/team/{team["id"]}/space',
                headers=headers,
                timeout=10
            )
            if spaces_response.status_code == 200:
                spaces = spaces_response.json()['spaces']
                for space in spaces:
                    space_data = {
                        'id': space['id'],
                        'name': space['name'],
                        'team_id': team['id']
                    }
                    all_spaces.append(space_data)

                    # Guardar el espacio en la base de datos
                    db.save_space(space['id'], space['name'], team['id'], metadata=space)
                    print(f"[INFO] Espacio {space['id']} guardado en BD: {space['name']}")

        return jsonify({'spaces': all_spaces})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/space/<space_id>/projects')
def get_projects(space_id):
    """Obtiene todas las carpetas y listas de un espacio, siempre sincronizando desde la API de ClickUp"""
    try:
        headers = get_headers()
        if not headers:
            return jsonify({'error': 'No autenticado', 'redirect': '/login'}), 401

        # Siempre sincronizar desde la API para obtener datos actualizados
        print(f"[INFO] Sincronizando proyectos desde API para space {space_id}...")
        return sync_projects_from_api(space_id, headers)

    except Exception as e:
        print(f"[ERROR] Error al obtener proyectos: {str(e)}")
        return jsonify({'error': str(e)}), 500


def sync_projects_from_api(space_id, headers):
    """Sincroniza proyectos desde la API de ClickUp y los guarda en la BD"""
    try:
        proyectos = []

        # Obtener folders del space desde la API
        folders_response = requests.get(
            f'https://api.clickup.com/api/v2/space/{space_id}/folder',
            headers=headers,
            timeout=10
        )

        if folders_response.status_code == 200:
            folders = folders_response.json()['folders']
            for folder in folders:
                # Guardar folder en BD
                db.save_folder(folder['id'], folder['name'], space_id, folder.get('hidden', False), metadata=folder)

                proyectos.append({
                    'id': f'folder_{folder["id"]}',
                    'name': f'📁 {folder["name"]}',
                    'type': 'folder',
                    'folder_id': folder['id']
                })

                # Obtener las listas dentro de cada folder
                folder_lists_response = requests.get(
                    f'https://api.clickup.com/api/v2/folder/{folder["id"]}/list',
                    headers=headers,
                    timeout=10
                )
                if folder_lists_response.status_code == 200:
                    for lista in folder_lists_response.json()['lists']:
                        # Guardar lista en BD
                        db.save_list(lista['id'], lista['name'], space_id, folder['id'],
                                   lista.get('archived', False), metadata=lista)

                        proyectos.append({
                            'id': f'list_{lista["id"]}',
                            'name': f'  📄 {lista["name"]}',
                            'type': 'list',
                            'list_id': lista['id']
                        })

        # Obtener listas sin folder (directamente en el space)
        lists_response = requests.get(
            f'https://api.clickup.com/api/v2/space/{space_id}/list',
            headers=headers,
            timeout=10
        )

        if lists_response.status_code == 200:
            listas = lists_response.json()['lists']
            for lista in listas:
                # Guardar lista en BD
                db.save_list(lista['id'], lista['name'], space_id, None,
                           lista.get('archived', False), metadata=lista)

                proyectos.append({
                    'id': f'list_{lista["id"]}',
                    'name': f'📄 {lista["name"]}',
                    'type': 'list',
                    'list_id': lista['id']
                })

        print(f"[INFO] Proyectos sincronizados desde API para space {space_id}")
        return jsonify({'projects': proyectos})

    except Exception as e:
        print(f"[ERROR] Error al sincronizar proyectos: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/project/<project_type>/<project_id>/tasks')
def get_project_tasks(project_type, project_id):
    """Obtiene las tareas de un proyecto específico (folder o list)"""
    try:
        headers = get_headers()
        if not headers:
            return jsonify({'error': 'No autenticado', 'redirect': '/login'}), 401

        todas_tareas = []

        if project_type == 'folder':
            # Si es un folder, obtener todas las listas del folder
            folder_lists_response = requests.get(
                f'https://api.clickup.com/api/v2/folder/{project_id}/list',
                headers=headers,
                timeout=10
            )
            if folder_lists_response.status_code == 200:
                for lista in folder_lists_response.json()['lists']:
                    tareas = obtener_tareas_de_lista(lista['id'], headers)
                    todas_tareas.extend(tareas)
        elif project_type == 'list':
            # Si es una lista, obtener las tareas directamente
            tareas = obtener_tareas_de_lista(project_id, headers)
            todas_tareas.extend(tareas)

        return jsonify({'tasks': todas_tareas})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/space/<space_id>/lists')
def get_lists(space_id):
    """Obtiene todas las tareas de un espacio (mantener para compatibilidad)"""
    try:
        headers = get_headers()
        if not headers:
            return jsonify({'error': 'No autenticado', 'redirect': '/login'}), 401

        folders_response = requests.get(
            f'https://api.clickup.com/api/v2/space/{space_id}/folder',
            headers=headers,
            timeout=10
        )

        lists_response = requests.get(
            f'https://api.clickup.com/api/v2/space/{space_id}/list',
            headers=headers,
            timeout=10
        )

        todas_tareas = []

        if lists_response.status_code == 200:
            listas = lists_response.json()['lists']
            for lista in listas:
                tareas = obtener_tareas_de_lista(lista['id'], headers)
                todas_tareas.extend(tareas)

        if folders_response.status_code == 200:
            folders = folders_response.json()['folders']
            for folder in folders:
                folder_lists = requests.get(
                    f'https://api.clickup.com/api/v2/folder/{folder["id"]}/list',
                    headers=headers,
                    timeout=10
                )
                if folder_lists.status_code == 200:
                    for lista in folder_lists.json()['lists']:
                        tareas = obtener_tareas_de_lista(lista['id'], headers)
                        todas_tareas.extend(tareas)

        return jsonify({'tasks': todas_tareas})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

def calcular_tiempo_en_progreso(tarea_id, estado_actual, headers):
    """Calcula el tiempo total que una tarea ha estado en estado 'in progress' usando datos locales de la BD"""
    try:
        # Usar la función de base de datos que calcula tiempo desde el historial local
        time_data = db.calculate_task_time_in_progress(tarea_id)

        tiempo_total_segundos = time_data['total_seconds']

        # Convertir a horas y minutos
        horas = int(tiempo_total_segundos // 3600)
        minutos = int((tiempo_total_segundos % 3600) // 60)

        print(f"[INFO] Tiempo total 'In Progress' calculado desde BD local: {horas}h {minutos}m")

        return horas, minutos

    except Exception as e:
        print(f"[ERROR] Error al calcular tiempo en progreso para tarea {tarea_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return 0, 0

def get_task_time_in_current_status(task_id, headers):
    """
    Obtiene el tiempo que una tarea ha estado en su estado actual usando la API de ClickUp.
    Retorna el timestamp calculado de cuándo entró al estado actual.

    Returns:
        tuple: (tiempo_en_segundos, timestamp_inicio_calculado) o (None, None) si falla
    """
    try:
        response = requests.get(
            f'https://api.clickup.com/api/v2/task/{task_id}/time_in_status',
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            print(f"[DEBUG] Time in Status API response para tarea {task_id}: {json.dumps(data, indent=2)}")

            # La estructura de respuesta puede variar, intentar diferentes formatos
            time_in_current_ms = None

            # Intentar obtener el tiempo del estado actual desde diferentes estructuras posibles
            # Formato 1: current_status.total_time
            if 'current_status' in data:
                current_status = data['current_status']
                if isinstance(current_status, dict):
                    total_time = current_status.get('total_time')
                    if isinstance(total_time, dict):
                        time_in_current_ms = total_time.get('by_minute') or total_time.get('total')
                    elif isinstance(total_time, (int, float)):
                        time_in_current_ms = total_time

            # Formato 2: status_history con el último estado
            if time_in_current_ms is None and 'status_history' in data:
                history = data['status_history']
                if isinstance(history, list) and len(history) > 0:
                    last_status = history[-1]
                    if isinstance(last_status, dict):
                        time_in_current_ms = last_status.get('total_time') or last_status.get('duration')

            # Formato 3: respuesta directa con 'time' o 'duration'
            if time_in_current_ms is None:
                time_in_current_ms = data.get('time') or data.get('duration') or data.get('total_time')

            if time_in_current_ms:
                # Convertir a segundos (asumiendo que viene en milisegundos)
                time_in_current_seconds = int(time_in_current_ms) / 1000 if time_in_current_ms > 10000 else int(time_in_current_ms)

                # Calcular el timestamp de inicio restando el tiempo del timestamp actual
                now = datetime.utcnow()
                start_timestamp = now - timedelta(seconds=time_in_current_seconds)
                start_timestamp_iso = start_timestamp.isoformat() + 'Z'

                print(f"[INFO] Tarea {task_id}: Tiempo en estado actual desde API: {time_in_current_seconds}s, inicio calculado: {start_timestamp_iso}")
                return time_in_current_seconds, start_timestamp_iso
            else:
                print(f"[WARNING] No se pudo extraer el tiempo del estado actual de la respuesta para tarea {task_id}")

        elif response.status_code == 404:
            print(f"[WARNING] Time in Status no disponible para tarea {task_id} (puede no estar habilitado o no soportado en el plan)")
        else:
            print(f"[WARNING] Error al obtener time in status para tarea {task_id}: {response.status_code}")
            try:
                print(f"[DEBUG] Respuesta: {response.text[:500]}")
            except:
                pass

    except Exception as e:
        print(f"[WARNING] No se pudo obtener time in status para tarea {task_id}: {str(e)}")
        import traceback
        traceback.print_exc()

    return None, None


def obtener_tareas_de_lista(lista_id, headers):
    """Obtiene todas las tareas de una lista con su estado, fechas de comienzo y término"""
    try:
        print(f"[INFO] Obteniendo tareas de la lista {lista_id}")
        tasks_response = requests.get(
            f'https://api.clickup.com/api/v2/list/{lista_id}/task',
            headers=headers,
            params={'include_closed': 'true'},
            timeout=10
        )

        tareas_procesadas = []

        if tasks_response.status_code == 200:
            tasks = tasks_response.json()['tasks']
            print(f"[INFO] Se encontraron {len(tasks)} tareas en la lista {lista_id}")
            for tarea in tasks:
                # Determinar el estado de la tarea
                status_type = tarea.get('status', {}).get('status', '').lower()
                estado = 'pendiente'

                # Los estados pueden variar, pero generalmente:
                # - 'complete', 'closed' = completada
                # - 'in progress', 'in review' = en progreso
                # - todo lo demás = pendiente
                if status_type in ['complete', 'closed', 'completed']:
                    estado = 'completada'
                elif 'progress' in status_type or 'review' in status_type or 'doing' in status_type:
                    estado = 'en_progreso'

                # Fecha de última actualización (enviar como ISO con timezone para conversión en cliente)
                fecha_actualizacion_dt = datetime.utcfromtimestamp(int(tarea['date_updated']) / 1000)
                fecha_actualizacion = fecha_actualizacion_dt.isoformat() + 'Z'

                # Guardar tarea en la base de datos PRIMERO (necesario para calcular tiempo)
                task_data = {
                    'id': tarea['id'],
                    'name': tarea['name'],
                    'list_id': lista_id,
                    'status': estado,
                    'status_text': tarea.get('status', {}).get('status', 'Sin estado'),
                    'url': tarea['url'],
                    'description': tarea.get('description', ''),
                    'priority': tarea.get('priority', {}).get('priority') if isinstance(tarea.get('priority'), dict) else tarea.get('priority'),
                    'assignees': tarea.get('assignees', []),
                    'date_created': parse_date_flexible(tarea.get('date_created')),
                    'date_updated': parse_date_flexible(tarea.get('date_updated')),
                    'due_date': parse_date_flexible(tarea.get('due_date')),
                    'start_date': parse_date_flexible(tarea.get('start_date')),
                    'time_estimate': tarea.get('time_estimate'),
                    'time_spent': tarea.get('time_spent'),
                    'tags': tarea.get('tags', []),
                    'custom_fields': tarea.get('custom_fields', []),
                    'metadata': tarea
                }

                # Verificar si la tarea existe para detectar cambio de estado
                old_task = db.get_task(tarea['id'])
                old_status = old_task.get('status') if old_task else None

                # Guardar la tarea
                db.save_task(task_data)
                print(f"[INFO] Tarea {tarea['id']} guardada en BD: {tarea['name']}")

                # IMPORTANTE: Registrar cambio de estado ANTES de calcular tiempo
                # Esto asegura que el historial esté completo cuando se calcula el tiempo
                if old_status != estado:
                    print(f"[INFO] Detectado cambio de estado para tarea {tarea['id']}: '{old_status}' → '{estado}'")

                    # Determinar el timestamp correcto del cambio
                    if estado == 'en_progreso' and old_status != 'en_progreso':
                        # Tarea entrando a "en_progreso": intentar obtener el tiempo real desde ClickUp
                        time_in_status, calculated_start = get_task_time_in_current_status(tarea['id'], headers)

                        if calculated_start:
                            # Usar el timestamp calculado desde la API de Time in Status
                            changed_at = calculated_start
                            print(f"[INFO] Tarea cambiando A 'en_progreso', usando timestamp desde Time in Status API: {changed_at}")
                        else:
                            # Fallback: usar date_updated como aproximación
                            changed_at = fecha_actualizacion
                            print(f"[INFO] Tarea cambiando A 'en_progreso', Time in Status no disponible, usando date_updated: {changed_at}")

                    elif old_status == 'en_progreso' and estado != 'en_progreso':
                        # Tarea saliendo DE "en_progreso": usar date_updated
                        changed_at = fecha_actualizacion
                        print(f"[INFO] Tarea cambiando DESDE 'en_progreso' a '{estado}', usando date_updated: {changed_at}")
                    else:
                        # Otros cambios: usar date_updated
                        changed_at = parse_date_flexible(tarea.get('date_updated'))
                        print(f"[INFO] Usando date_updated para cambio: {changed_at}")

                    db.save_status_change(
                        task_id=tarea['id'],
                        old_status=old_status,
                        new_status=estado,
                        old_status_text=old_task.get('status_text') if old_task else None,
                        new_status_text=task_data['status_text'],
                        changed_at=changed_at
                    )
                    print(f"[INFO] Cambio de estado registrado en historial: {tarea['id']}")
                elif estado == 'en_progreso':
                    # Si la tarea ya estaba en progreso, verificar si tiene historial
                    # Si no tiene historial de entrada a "en_progreso", crear uno usando Time in Status de ClickUp
                    history = db.get_status_history(tarea['id'])
                    has_progress_entry = any(h['new_status'] == 'en_progreso' for h in history)
                    if not has_progress_entry:
                        # Intentar obtener el tiempo exacto desde la API de ClickUp
                        time_in_status, calculated_start = get_task_time_in_current_status(tarea['id'], headers)

                        if calculated_start:
                            # Usar el timestamp calculado desde la API de Time in Status
                            changed_at = calculated_start
                            print(f"[INFO] Usando timestamp calculado desde Time in Status API: {changed_at}")
                        else:
                            # Fallback: usar date_updated si la API no está disponible
                            changed_at = fecha_actualizacion
                            print(f"[INFO] Time in Status API no disponible, usando date_updated como fallback: {changed_at}")

                        db.save_status_change(
                            task_id=tarea['id'],
                            old_status=None,
                            new_status=estado,
                            old_status_text=None,
                            new_status_text=task_data['status_text'],
                            changed_at=changed_at
                        )
                        print(f"[INFO] Creado registro inicial para tarea en progreso: {tarea['id']} con timestamp: {changed_at}")

                # Calcular tiempo en estado "in progress" usando el historial
                # NOTA: Esto se hace DESPUÉS de registrar el cambio de estado para que el tiempo sea correcto
                print(f"[INFO] Calculando tiempo para tarea: {tarea['name']} (ID: {tarea['id']})")

                # Obtener información completa del tiempo en progreso
                try:
                    time_data = db.calculate_task_time_in_progress(tarea['id'])
                    tiempo_total_segundos = time_data['total_seconds']
                    sesion_actual_inicio = time_data['current_session_start']
                    actualmente_en_progreso = time_data['is_currently_in_progress']

                    # Calcular horas y minutos para compatibilidad
                    horas_trabajadas = int(tiempo_total_segundos // 3600)
                    minutos_trabajados = int((tiempo_total_segundos % 3600) // 60)

                    print(f"[INFO] Tiempo calculado para tarea {tarea['id']}: {horas_trabajadas}h {minutos_trabajados}m (total: {tiempo_total_segundos}s, en progreso: {actualmente_en_progreso})")
                except Exception as e:
                    # Si hay error al calcular tiempo, usar valores por defecto para no bloquear el listado de tareas
                    print(f"[ERROR] Error al calcular tiempo para tarea {tarea['id']}: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    # Valores por defecto
                    tiempo_total_segundos = 0
                    sesion_actual_inicio = None
                    actualmente_en_progreso = False
                    horas_trabajadas = 0
                    minutos_trabajados = 0
                    print(f"[WARNING] Usando valores por defecto para tarea {tarea['id']} para evitar bloqueo del listado")

                # Obtener configuración de alerta para esta tarea desde el diccionario en memoria
                alerta_config = alertas_tareas.get(tarea['id'], {
                    'aviso_activado': False,
                    'email_aviso': '',
                    'aviso_horas': 0,
                    'aviso_minutos': 0
                })

                tareas_procesadas.append({
                    'id': tarea['id'],
                    'nombre': tarea['name'],
                    'estado': estado,
                    'estado_texto': tarea.get('status', {}).get('status', 'Sin estado'),
                    'url': tarea['url'],
                    'fecha_actualizacion': fecha_actualizacion,
                    'horas_trabajadas': int(horas_trabajadas),
                    'minutos_trabajados': int(minutos_trabajados),
                    # Información completa para cálculo en tiempo real en el frontend
                    'tiempo_total_segundos': tiempo_total_segundos,
                    'sesion_actual_inicio': sesion_actual_inicio,
                    'actualmente_en_progreso': actualmente_en_progreso,
                    'alerta': alerta_config
                })

        return tareas_procesadas

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Error al obtener tareas de la lista {lista_id}: {str(e)}")
        return []
    except Exception as e:
        print(f"[ERROR] Error inesperado en obtener_tareas_de_lista: {str(e)}")
        return []

@app.route('/api/alerta/tarea/guardar', methods=['POST'])
def guardar_alerta_tarea():
    """Guarda la configuración de alerta para una tarea específica"""
    try:
        data = request.json
        tarea_id = data['tarea_id']
        aviso_activado = data.get('aviso_activado', False)
        email_aviso = data.get('email_aviso', '')
        aviso_horas = int(data.get('aviso_horas', 0))
        aviso_minutos = int(data.get('aviso_minutos', 0))

        # Guardar en base de datos
        db.save_task_alert(tarea_id, aviso_activado, email_aviso, aviso_horas, aviso_minutos)

        # Mantener también en memoria para compatibilidad
        alertas_tareas[tarea_id] = {
            'aviso_activado': aviso_activado,
            'email_aviso': email_aviso,
            'aviso_horas': aviso_horas,
            'aviso_minutos': aviso_minutos,
            'ultima_actualizacion': datetime.now().isoformat()
        }

        print(f"[INFO] Alerta guardada para tarea {tarea_id} en BD y memoria")

        return jsonify({'success': True, 'message': 'Alerta guardada correctamente'})

    except Exception as e:
        print(f"[ERROR] Error al guardar alerta de tarea: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/alerta/tarea/<tarea_id>', methods=['GET'])
def obtener_alerta_tarea_endpoint(tarea_id):
    """Obtiene la configuración de alerta para una tarea específica"""
    try:
        # Intentar obtener de la base de datos primero
        alerta = db.get_task_alert(tarea_id)

        if not alerta:
            # Si no está en BD, intentar de memoria (migración)
            alerta = alertas_tareas.get(tarea_id)

        if not alerta:
            # Si no existe, devolver valores por defecto
            alerta = {
                'aviso_activado': False,
                'email_aviso': '',
                'aviso_horas': 0,
                'aviso_minutos': 0
            }

        return jsonify(alerta)
    except Exception as e:
        print(f"[ERROR] Error al obtener alerta de tarea: {str(e)}")
        return jsonify({'error': str(e)}), 500

def enviar_email_alerta(email_destino, tarea_nombre, proyecto_nombre, tarea_url, tiempo_en_progreso):
    """Envía un email de alerta usando Brevo API (no SMTP porque Render bloquea puerto 587)"""
    try:
        # Verificar configuración
        if not BREVO_API_KEY or not SMTP_EMAIL:
            print(f"[EMAIL] ❌ Error: Configuración incompleta (BREVO_API_KEY o SMTP_EMAIL faltante)")
            return False

        print(f"[EMAIL] Enviando alerta para '{tarea_nombre}' a {email_destino}...")

        # Crear el cuerpo del email en HTML
        html_content = f"""
        <html>
          <head>
            <style>
              body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
              .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
              .header {{ background-color: #f8d7da; color: #721c24; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
              .content {{ background-color: #f9f9f9; padding: 20px; border-radius: 5px; }}
              .btn {{ background-color: #667eea; color: white; padding: 12px 24px; text-decoration: none;
                     border-radius: 5px; display: inline-block; margin-top: 15px; }}
              .footer {{ color: #666; font-size: 12px; margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd; }}
              .warning-icon {{ font-size: 48px; margin-bottom: 10px; }}
            </style>
          </head>
          <body>
            <div class="container">
              <div class="header">
                <div class="warning-icon">⚠️</div>
                <h2 style="margin: 0;">Alerta de Demora en Tarea</h2>
              </div>
              <div class="content">
                <p><strong>Proyecto:</strong> {proyecto_nombre}</p>
                <p><strong>Tarea:</strong> {tarea_nombre}</p>
                <p style="font-size: 16px; color: #d9534f;">
                  ⏱️ Esta tarea lleva <strong>{tiempo_en_progreso}</strong> en estado "En Progreso"
                  y ha superado el tiempo máximo configurado.
                </p>
                <p>Por favor, revisa el estado de esta tarea y toma las acciones necesarias:</p>
                <a href="{tarea_url}" class="btn">Ver Tarea en ClickUp</a>
              </div>
              <div class="footer">
                <p>Este es un email automático del sistema Virtual Controller SIDN.</p>
                <p>La alerta ha sido desactivada automáticamente. Para recibir una nueva alerta,
                   reactiva la configuración desde el panel de control.</p>
              </div>
            </div>
          </body>
        </html>
        """

        # Preparar el payload para la API de Brevo
        payload = {
            "sender": {
                "name": "Virtual Controller SIDN",
                "email": SMTP_EMAIL
            },
            "to": [
                {
                    "email": email_destino,
                    "name": email_destino.split('@')[0]
                }
            ],
            "subject": f"⚠️ Alerta: Demora en tarea \"{tarea_nombre}\" - {proyecto_nombre}",
            "htmlContent": html_content
        }

        print(f"[EMAIL] Enviando vía Brevo API...")

        # Enviar usando la API de Brevo
        response = requests.post(
            'https://api.brevo.com/v3/smtp/email',
            headers={
                'accept': 'application/json',
                'api-key': BREVO_API_KEY,
                'content-type': 'application/json'
            },
            json=payload,
            timeout=10
        )

        if response.status_code == 201:
            print(f"[EMAIL] ✅ Email enviado exitosamente a {email_destino}")
            return True
        else:
            print(f"[EMAIL] ❌ Error HTTP {response.status_code}: {response.text}")
            return False

    except requests.exceptions.Timeout:
        print(f"[EMAIL] ❌ Timeout al conectar con Brevo API")
        return False

    except Exception as e:
        print(f"[EMAIL] ❌ Error: {str(e)}")
        return False

@app.route('/api/verificar-alertas', methods=['POST'])
def verificar_alertas():
    """Verifica si alguna tarea en progreso necesita enviar alerta basándose en su tiempo en progreso"""
    try:
        print("\n" + "🔍"*40)
        print("🔍 VERIFICACIÓN PERIÓDICA DE ALERTAS INICIADA")
        print(f"🔍 Timestamp: {datetime.now().isoformat()}")
        print("🔍"*40)

        # Obtener todas las alertas activas de la base de datos
        alertas_activas = db.get_all_active_alerts()
        print(f"📋 [INFO] Alertas activas encontradas: {len(alertas_activas)}")

        if len(alertas_activas) == 0:
            print("⚠️  [INFO] No hay alertas activas configuradas. Finalizando verificación.")
            print("🔍"*40 + "\n")
            return jsonify({
                'success': True,
                'alertas_enviadas': [],
                'total_verificadas': 0,
                'mensaje': 'No hay alertas activas configuradas'
            })

        # Mostrar información de cada alerta activa
        for i, alerta in enumerate(alertas_activas, 1):
            print(f"   {i}. Tarea: {alerta['task_name']} (ID: {alerta['task_id'][:8]}...) - Límite: {alerta['aviso_horas']}h {alerta['aviso_minutos']}m")

        alertas_enviadas = []

        for alerta in alertas_activas:
            tarea_id = alerta['task_id']
            tarea_nombre = alerta['task_name']
            tarea_url = alerta['task_url']
            email_destino = alerta['email_aviso']
            tiempo_max_horas = alerta['aviso_horas']
            tiempo_max_minutos = alerta['aviso_minutos']

            print(f"\n[INFO] Verificando alerta para tarea: {tarea_nombre} (ID: {tarea_id})")

            # Calcular el tiempo máximo configurado en segundos
            tiempo_max_segundos = (tiempo_max_horas * 3600) + (tiempo_max_minutos * 60)

            if tiempo_max_segundos <= 0:
                print(f"[WARNING] Tarea {tarea_id} tiene tiempo máximo de 0. Saltando...")
                continue

            if not email_destino:
                print(f"[WARNING] Tarea {tarea_id} no tiene email configurado. Saltando...")
                continue

            try:
                # Obtener información de la tarea desde la BD
                tarea_bd = db.get_task(tarea_id)

                if not tarea_bd:
                    print(f"[WARNING] Tarea {tarea_id} no encontrada en BD. Saltando...")
                    continue

                # Verificar si la tarea está actualmente en progreso
                if tarea_bd['status'] != 'en_progreso':
                    print(f"[INFO] Tarea {tarea_id} no está en estado 'en_progreso' (estado actual: {tarea_bd['status']}). Saltando...")
                    continue

                # Calcular el tiempo total en progreso
                tiempo_data = db.calculate_task_time_in_progress(tarea_id)
                tiempo_en_progreso_segundos = tiempo_data['total_seconds']

                # Si está actualmente en progreso, sumar el tiempo de la sesión actual
                if tiempo_data['is_currently_in_progress'] and tiempo_data['current_session_start']:
                    try:
                        session_start = datetime.fromisoformat(tiempo_data['current_session_start'])
                        # Usar datetime.now() con timezone UTC para poder restar
                        from datetime import timezone
                        now = datetime.now(timezone.utc)
                        tiempo_sesion_actual = (now - session_start).total_seconds()
                        tiempo_en_progreso_segundos += tiempo_sesion_actual
                        print(f"[INFO] Sumando tiempo de sesión actual: {tiempo_sesion_actual/3600:.2f}h")
                    except Exception as e:
                        print(f"[WARNING] Error al calcular sesión actual: {str(e)}")
                        # Fallback: intentar sin timezone
                        try:
                            session_start_naive = datetime.fromisoformat(tiempo_data['current_session_start'].replace('+00:00', '').replace('Z', ''))
                            tiempo_sesion_actual = (datetime.utcnow() - session_start_naive).total_seconds()
                            tiempo_en_progreso_segundos += tiempo_sesion_actual
                            print(f"[INFO] Sesión actual (fallback): +{tiempo_sesion_actual/3600:.2f}h")
                        except Exception as e2:
                            print(f"[ERROR] No se pudo calcular tiempo de sesión actual: {str(e2)}")

                print(f"[INFO] Tiempo en progreso: {tiempo_en_progreso_segundos/3600:.2f}h ({tiempo_en_progreso_segundos}s)")
                print(f"[INFO] Tiempo máximo configurado: {tiempo_max_segundos/3600:.2f}h ({tiempo_max_segundos}s)")

                # Verificar si se superó el tiempo máximo (con margen de 30 segundos de tolerancia)
                MARGEN_TOLERANCIA = 30  # segundos
                if tiempo_en_progreso_segundos >= (tiempo_max_segundos - MARGEN_TOLERANCIA):
                    print("\n" + "🚨"*20)
                    print("🚨 ¡ALERTA ACTIVADA! - TIEMPO LÍMITE SUPERADO")
                    print("🚨"*20)

                    # Formatear el tiempo en progreso para el email
                    horas = int(tiempo_en_progreso_segundos // 3600)
                    minutos = int((tiempo_en_progreso_segundos % 3600) // 60)
                    tiempo_en_progreso_str = f"{horas} horas y {minutos} minutos"

                    # Obtener el nombre del proyecto
                    proyecto_nombre = db.get_task_project_name(tarea_id)

                    # Enviar email de alerta
                    print(f"\n📤 [EMAIL] Iniciando envío de email de alerta...")
                    print(f"📤 [EMAIL] Destinatario: {email_destino}")
                    print(f"📤 [EMAIL] Tarea: {tarea_nombre}")
                    print(f"📤 [EMAIL] Proyecto: {proyecto_nombre}")

                    if enviar_email_alerta(
                        email_destino,
                        tarea_nombre,
                        proyecto_nombre,
                        tarea_url,
                        tiempo_en_progreso_str
                    ):
                        print("\n" + "✅"*20)
                        print("✅ EMAIL ENVIADO EXITOSAMENTE (desde verificación periódica)")
                        print("✅"*20)
                        print(f"✅ [RESULT] Alerta enviada a: {email_destino}")
                        print(f"✅ [RESULT] Tarea: {tarea_nombre}")
                        print("✅"*20 + "\n")

                        # Desactivar la alerta después del envío
                        db.deactivate_task_alert(tarea_id)

                        # También actualizar la caché en memoria si existe
                        if tarea_id in alertas_tareas:
                            alertas_tareas[tarea_id]['aviso_activado'] = False
                            alertas_tareas[tarea_id]['ultimo_envio_email'] = datetime.now().isoformat()

                        alertas_enviadas.append({
                            'tarea_id': tarea_id,
                            'nombre': tarea_nombre,
                            'proyecto': proyecto_nombre,
                            'email': email_destino,
                            'tiempo_en_progreso': tiempo_en_progreso_str
                        })
                    else:
                        print("\n" + "❌"*20)
                        print("❌ ERROR: NO SE PUDO ENVIAR EL EMAIL")
                        print("❌"*20 + "\n")
                else:
                    diferencia = tiempo_max_segundos - tiempo_en_progreso_segundos
                    print(f"[INFO] Tarea aún no supera el límite. Faltan {diferencia/3600:.2f}h")

            except Exception as e:
                print(f"[ERROR] Error al procesar alerta para tarea {tarea_id}: {str(e)}")
                import traceback
                traceback.print_exc()
                continue

        print("🔍"*40)
        print(f"🔍 VERIFICACIÓN COMPLETADA - {len(alertas_enviadas)} alertas enviadas")
        print("🔍"*40 + "\n")

        return jsonify({
            'success': True,
            'alertas_enviadas': alertas_enviadas,
            'total_verificadas': len(alertas_activas)
        })

    except Exception as e:
        print(f"[ERROR] Error crítico en verificación de alertas: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/debug/verificar-alertas-ahora', methods=['GET', 'POST'])
def debug_verificar_alertas_ahora():
    """Endpoint de debug para forzar verificación inmediata de todas las alertas activas"""
    try:
        print(f"\n[DEBUG] Verificación manual forzada - {datetime.now().isoformat()}")

        # Obtener todas las alertas activas
        alertas_activas = db.get_all_active_alerts()
        print(f"[DEBUG] Alertas activas: {len(alertas_activas)}")

        if len(alertas_activas) == 0:
            msg = "No hay alertas activas configuradas"
            return jsonify({
                'success': True,
                'mensaje': msg,
                'alertas_activas': 0,
                'alertas_verificadas': 0,
                'alertas_enviadas': []
            })

        # Mostrar detalles de cada alerta
        print("\n📋 [DEBUG] Detalles de alertas activas:")
        for i, alerta in enumerate(alertas_activas, 1):
            print(f"   {i}. ID: {alerta['task_id'][:12]}...")
            print(f"      Tarea: {alerta['task_name']}")
            print(f"      Email: {alerta['email_aviso']}")
            print(f"      Límite: {alerta['aviso_horas']}h {alerta['aviso_minutos']}m")

        # Verificar cada alerta
        alertas_enviadas = []
        alertas_dentro_limite = []
        alertas_no_en_progreso = []
        alertas_error = []

        for alerta in alertas_activas:
            tarea_id = alerta['task_id']
            tarea_nombre = alerta['task_name']

            try:
                print(f"\n[DEBUG] ──── Procesando: {tarea_nombre} ────")

                # Obtener tarea de BD
                tarea_bd = db.get_task(tarea_id)
                if not tarea_bd:
                    print(f"⚠️  [DEBUG] Tarea no encontrada en BD")
                    alertas_error.append({
                        'tarea': tarea_nombre,
                        'error': 'Tarea no encontrada en BD'
                    })
                    continue

                estado = tarea_bd['status']
                print(f"[DEBUG] Estado actual: {estado}")

                if estado != 'en_progreso':
                    print(f"ℹ️  [DEBUG] No está en progreso, saltando")
                    alertas_no_en_progreso.append(tarea_nombre)
                    continue

                # Calcular tiempo
                tiempo_max_segundos = (alerta['aviso_horas'] * 3600) + (alerta['aviso_minutos'] * 60)
                tiempo_data = db.calculate_task_time_in_progress(tarea_id)
                tiempo_en_progreso = tiempo_data['total_seconds']

                # Sumar sesión actual si aplica
                if tiempo_data['is_currently_in_progress'] and tiempo_data['current_session_start']:
                    try:
                        session_start = datetime.fromisoformat(tiempo_data['current_session_start'])
                        from datetime import timezone
                        now = datetime.now(timezone.utc)
                        tiempo_sesion = (now - session_start).total_seconds()
                        tiempo_en_progreso += tiempo_sesion
                    except Exception as e:
                        print(f"[ERROR] No se pudo calcular tiempo de sesión actual: {str(e)}")

                horas_actuales = tiempo_en_progreso / 3600
                horas_limite = tiempo_max_segundos / 3600

                # Verificar si se superó el tiempo máximo (con margen de 30 segundos de tolerancia)
                MARGEN_TOLERANCIA = 30  # segundos
                if tiempo_en_progreso >= (tiempo_max_segundos - MARGEN_TOLERANCIA):
                    horas = int(tiempo_en_progreso // 3600)
                    minutos = int((tiempo_en_progreso % 3600) // 60)
                    tiempo_str = f"{horas} horas y {minutos} minutos"

                    proyecto_nombre = db.get_task_project_name(tarea_id)
                    tarea_url = alerta['task_url']

                    # Intentar enviar email
                    if enviar_email_alerta(alerta['email_aviso'], tarea_nombre, proyecto_nombre, tarea_url, tiempo_str):
                        db.deactivate_task_alert(tarea_id)
                        alertas_enviadas.append({
                            'tarea': tarea_nombre,
                            'email': alerta['email_aviso'],
                            'tiempo': tiempo_str
                        })
                    else:
                        alertas_error.append({
                            'tarea': tarea_nombre,
                            'error': 'Error al enviar email via Brevo API'
                        })
                else:
                    diferencia = (tiempo_max_segundos - tiempo_en_progreso) / 3600
                    alertas_dentro_limite.append({
                        'tarea': tarea_nombre,
                        'tiempo_actual': f"{horas_actuales:.2f}h",
                        'limite': f"{horas_limite:.2f}h",
                        'restante': f"{diferencia:.2f}h"
                    })

            except Exception as e:
                print(f"❌ [DEBUG] Error procesando tarea {tarea_nombre}: {str(e)}")
                import traceback
                traceback.print_exc()
                alertas_error.append({
                    'tarea': tarea_nombre,
                    'error': str(e)
                })

        print(f"\n[DEBUG] Verificación completada: {len(alertas_enviadas)} enviadas, {len(alertas_error)} errores")

        return jsonify({
            'success': True,
            'alertas_activas': len(alertas_activas),
            'alertas_enviadas': alertas_enviadas,
            'alertas_dentro_limite': alertas_dentro_limite,
            'alertas_no_en_progreso': alertas_no_en_progreso,
            'alertas_error': alertas_error
        })

    except Exception as e:
        print(f"❌ [DEBUG] Error crítico: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/test-email', methods=['POST'])
def test_email():
    """Endpoint para probar el envío de emails de alerta"""
    try:
        data = request.json
        email_destino = data.get('email')

        if not email_destino:
            return jsonify({'error': 'Se requiere un email de destino'}), 400

        # Verificar configuración Brevo API
        if not SMTP_EMAIL or not BREVO_API_KEY:
            return jsonify({
                'error': 'Configuración de email no disponible',
                'details': {
                    'SMTP_EMAIL': 'configurado' if SMTP_EMAIL else 'NO CONFIGURADO',
                    'BREVO_API_KEY': 'configurado' if BREVO_API_KEY else 'NO CONFIGURADO'
                }
            }), 500

        # Intentar enviar email de prueba
        resultado = enviar_email_alerta(
            email_destino=email_destino,
            tarea_nombre="Tarea de Prueba del Sistema",
            proyecto_nombre="Proyecto de Prueba",
            tarea_url="https://app.clickup.com/t/test123",
            tiempo_en_progreso="2 horas y 30 minutos"
        )

        if resultado:
            return jsonify({
                'success': True,
                'message': f'Email de prueba enviado exitosamente a {email_destino}',
                'email_config': {
                    'from': SMTP_EMAIL,
                    'service': 'Brevo API'
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No se pudo enviar el email. Revisa los logs del servidor.'
            }), 500

    except Exception as e:
        print(f"[ERROR] Error en test de email: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/smtp-status', methods=['GET'])
def smtp_status():
    """Verifica el estado de la configuración SMTP"""
    try:
        status = {
            'smtp_server': SMTP_SERVER,
            'smtp_port': SMTP_PORT,
            'smtp_email': SMTP_EMAIL if SMTP_EMAIL else None,
            'smtp_password_configured': bool(SMTP_PASSWORD),
            'all_configured': all([SMTP_SERVER, SMTP_PORT, SMTP_EMAIL, SMTP_PASSWORD])
        }

        # Intentar conexión de prueba
        if status['all_configured']:
            try:
                import socket
                sock = socket.create_connection((SMTP_SERVER, int(SMTP_PORT)), timeout=5)
                sock.close()
                status['connection_test'] = 'SUCCESS'
            except Exception as e:
                status['connection_test'] = f'FAILED: {str(e)}'
        else:
            status['connection_test'] = 'SKIPPED - Configuración incompleta'

        return jsonify(status)

    except Exception as e:
        print(f"[ERROR] Error al verificar estado SMTP: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/tasks/time-tracking', methods=['GET'])
def get_tasks_time_tracking():
    """
    Obtiene información de tiempo para todas las tareas en progreso
    Retorna un diccionario con task_id como clave y datos de tiempo como valor
    """
    try:
        # Obtener todas las tareas actualmente en progreso
        in_progress_tasks = db.get_active_in_progress_tasks()

        result = {}
        for task in in_progress_tasks:
            task_id = task['id']
            time_data = db.calculate_task_time_in_progress(task_id)
            result[task_id] = {
                'task_id': task_id,
                'task_name': task['name'],
                'total_seconds': time_data['total_seconds'],
                'current_session_start': time_data['current_session_start'],
                'is_currently_in_progress': time_data['is_currently_in_progress']
            }

        return jsonify({
            'success': True,
            'tasks': result
        })

    except Exception as e:
        print(f"[ERROR] Error al obtener tiempos de tareas: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/tasks/time-tracking/batch', methods=['POST'])
def get_tasks_time_tracking_batch():
    """
    Obtiene información de tiempo para un conjunto de tareas específicas
    Acepta una lista de task_ids en el body y retorna el tiempo calculado para cada una
    """
    try:
        data = request.json
        task_ids = data.get('task_ids', [])

        if not task_ids:
            return jsonify({
                'success': True,
                'tasks': {}
            })

        result = {}
        for task_id in task_ids:
            try:
                # Verificar que la tarea existe
                task = db.get_task(task_id)
                if not task:
                    continue

                # Calcular tiempo para esta tarea
                time_data = db.calculate_task_time_in_progress(task_id)
                result[task_id] = {
                    'task_id': task_id,
                    'task_name': task['name'],
                    'total_seconds': time_data['total_seconds'],
                    'current_session_start': time_data['current_session_start'],
                    'is_currently_in_progress': time_data['is_currently_in_progress']
                }
            except Exception as e:
                print(f"[ERROR] Error al procesar tarea {task_id}: {str(e)}")
                continue

        return jsonify({
            'success': True,
            'tasks': result
        })

    except Exception as e:
        print(f"[ERROR] Error al obtener tiempos de tareas (batch): {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/task/<task_id>/time-tracking', methods=['GET'])
def get_task_time_tracking(task_id):
    """
    Obtiene información de tiempo para una tarea específica
    """
    try:
        task = db.get_task(task_id)
        if not task:
            return jsonify({'error': 'Tarea no encontrada'}), 404

        time_data = db.calculate_task_time_in_progress(task_id)

        return jsonify({
            'success': True,
            'task_id': task_id,
            'task_name': task['name'],
            'status': task['status'],
            'total_seconds': time_data['total_seconds'],
            'current_session_start': time_data['current_session_start'],
            'is_currently_in_progress': time_data['is_currently_in_progress']
        })

    except Exception as e:
        print(f"[ERROR] Error al obtener tiempo de tarea {task_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/task/<task_id>/status-history', methods=['GET'])
def get_task_status_history_api(task_id):
    """
    Obtiene el historial de cambios de estado de una tarea
    """
    try:
        history = db.get_status_history(task_id)
        task = db.get_task(task_id)
        time_data = db.calculate_task_time_in_progress(task_id)

        return jsonify({
            'success': True,
            'task_id': task_id,
            'task_name': task['name'] if task else 'Unknown',
            'current_status': task['status'] if task else 'Unknown',
            'history': history,
            'time_calculation': {
                'total_seconds': time_data['total_seconds'],
                'current_session_start': time_data['current_session_start'],
                'is_currently_in_progress': time_data['is_currently_in_progress']
            }
        })

    except Exception as e:
        print(f"[ERROR] Error al obtener historial de tarea {task_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ============================================================================
# ENDPOINTS DE GOOGLE OAUTH Y GOOGLE SHEETS
# ============================================================================

@app.route('/oauth/google/login')
def google_oauth_login():
    """Inicia el flujo de OAuth de Google"""
    try:
        # Crear el objeto de configuración para OAuth
        client_config = {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uris": [GOOGLE_REDIRECT_URI],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        }

        # Crear el flujo de OAuth
        flow = Flow.from_client_config(
            client_config,
            scopes=GOOGLE_SCOPES,
            redirect_uri=GOOGLE_REDIRECT_URI
        )

        # Generar la URL de autorización
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )

        # Guardar el state en la sesión para verificar después
        session['google_oauth_state'] = state

        return redirect(authorization_url)

    except Exception as e:
        print(f"[ERROR] Error al iniciar login de Google: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/oauth/google/callback')
def google_oauth_callback():
    """Callback de OAuth de Google"""
    try:
        # Verificar el state para prevenir CSRF
        state = session.get('google_oauth_state')
        if not state:
            return "Error: No se encontró el estado de OAuth", 400

        # Crear el objeto de configuración para OAuth
        client_config = {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uris": [GOOGLE_REDIRECT_URI],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        }

        # Crear el flujo de OAuth
        flow = Flow.from_client_config(
            client_config,
            scopes=GOOGLE_SCOPES,
            state=state,
            redirect_uri=GOOGLE_REDIRECT_URI
        )

        # Obtener el token usando el código de autorización
        flow.fetch_token(authorization_response=request.url)

        # Guardar las credenciales en la sesión
        credentials = flow.credentials
        session['google_credentials'] = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }

        # Obtener el email del usuario
        try:
            service = build('oauth2', 'v2', credentials=credentials)
            user_info = service.userinfo().get().execute()
            session['google_email'] = user_info.get('email', '')
        except Exception as e:
            print(f"[WARNING] No se pudo obtener el email del usuario: {str(e)}")
            session['google_email'] = ''

        # Cerrar la ventana popup y notificar al padre
        return """
        <html>
        <script>
            window.opener.postMessage({
                type: 'google-auth-success',
                token: '""" + credentials.token + """',
                email: '""" + session.get('google_email', '') + """'
            }, '*');
            window.close();
        </script>
        <body>
            <p>Autenticación exitosa. Puedes cerrar esta ventana.</p>
        </body>
        </html>
        """

    except Exception as e:
        print(f"[ERROR] Error en callback de Google: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"Error en la autenticación: {str(e)}", 500


@app.route('/api/google/auth-status')
def google_auth_status():
    """Verifica si el usuario está autenticado con Google"""
    try:
        google_creds = session.get('google_credentials')

        if google_creds:
            # Verificar si el token sigue siendo válido
            credentials = Credentials(
                token=google_creds['token'],
                refresh_token=google_creds.get('refresh_token'),
                token_uri=google_creds['token_uri'],
                client_id=google_creds['client_id'],
                client_secret=google_creds['client_secret'],
                scopes=google_creds['scopes']
            )

            # Si el token expiró, intentar refrescarlo
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                # Actualizar las credenciales en la sesión
                session['google_credentials']['token'] = credentials.token

            return jsonify({
                'authenticated': True,
                'email': session.get('google_email', ''),
                'token': credentials.token
            })
        else:
            return jsonify({'authenticated': False})

    except Exception as e:
        print(f"[ERROR] Error al verificar estado de Google Auth: {str(e)}")
        return jsonify({'authenticated': False})


@app.route('/api/google/logout', methods=['POST'])
def google_logout():
    """Desconecta al usuario de Google"""
    try:
        if 'google_credentials' in session:
            del session['google_credentials']
        if 'google_email' in session:
            del session['google_email']
        if 'google_oauth_state' in session:
            del session['google_oauth_state']

        return jsonify({'success': True})

    except Exception as e:
        print(f"[ERROR] Error al desconectar de Google: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/export-to-google-sheets', methods=['POST'])
def export_to_google_sheets():
    """Exporta el informe de horas de proyectos a Google Sheets"""
    try:
        # Verificar autenticación de Google
        google_creds = session.get('google_credentials')
        if not google_creds:
            return jsonify({'error': 'No estás autenticado con Google'}), 401

        # Obtener parámetros
        data = request.json
        fecha_inicio = data.get('fecha_inicio')
        fecha_fin = data.get('fecha_fin')

        if not fecha_inicio or not fecha_fin:
            return jsonify({'error': 'Faltan las fechas de inicio y fin'}), 400

        # Convertir fechas a datetime con timezone UTC
        from datetime import timezone
        fecha_inicio_dt = datetime.strptime(fecha_inicio, '%Y-%m-%d').replace(hour=0, minute=0, second=0, tzinfo=timezone.utc)
        fecha_fin_dt = datetime.strptime(fecha_fin, '%Y-%m-%d').replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)

        print(f"[INFO] Exportando informe desde {fecha_inicio} hasta {fecha_fin}")

        # Crear credenciales de Google
        credentials = Credentials(
            token=google_creds['token'],
            refresh_token=google_creds.get('refresh_token'),
            token_uri=google_creds['token_uri'],
            client_id=google_creds['client_id'],
            client_secret=google_creds['client_secret'],
            scopes=google_creds['scopes']
        )

        # Refrescar token si es necesario
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            session['google_credentials']['token'] = credentials.token

        # Obtener todos los proyectos (folders y lists) de todos los espacios
        espacios = db.get_all_spaces()
        proyectos_con_horas = []

        print(f"[INFO] Procesando {len(espacios)} espacios...")

        for espacio in espacios:
            # Obtener folders del espacio
            folders = db.get_folders_by_space(espacio['id'])
            print(f"[INFO] Espacio '{espacio['name']}': {len(folders)} folders")

            for folder in folders:
                horas_totales = calcular_horas_proyecto('folder', folder['id'], fecha_inicio_dt, fecha_fin_dt)
                print(f"[INFO] Folder '{folder['name']}': {horas_totales:.2f} horas")
                # Añadir TODOS los proyectos, incluso con 0 horas
                proyectos_con_horas.append({
                    'nombre': folder['name'],
                    'horas': horas_totales
                })

            # Obtener lists del espacio
            lists = db.get_lists_by_space(espacio['id'])
            print(f"[INFO] Espacio '{espacio['name']}': {len(lists)} listas")

            for lista in lists:
                horas_totales = calcular_horas_proyecto('list', lista['id'], fecha_inicio_dt, fecha_fin_dt)
                print(f"[INFO] Lista '{lista['name']}': {horas_totales:.2f} horas")
                # Añadir TODOS los proyectos, incluso con 0 horas
                proyectos_con_horas.append({
                    'nombre': lista['name'],
                    'horas': horas_totales
                })

        print(f"[INFO] Total de proyectos a exportar: {len(proyectos_con_horas)}")

        # Preparar datos para Google Sheets
        fecha_reporte = datetime.now().strftime('%Y-%m-%d')
        valores = []

        print(f"[INFO] Preparando valores para {len(proyectos_con_horas)} proyectos...")

        for proyecto in proyectos_con_horas:
            fila = [
                fecha_reporte,
                proyecto['nombre'],
                f"{proyecto['horas']:.2f}"
            ]
            valores.append(fila)
            print(f"[INFO] Añadida fila: {fila}")

        print(f"[INFO] Total de valores preparados: {len(valores)}")
        print(f"[INFO] Valores a escribir: {valores}")

        # Escribir en Google Sheets
        service = build('sheets', 'v4', credentials=credentials)

        # Primero verificar si existe la hoja, si no, crearla
        try:
            sheet_metadata = service.spreadsheets().get(spreadsheetId=GOOGLE_SHEET_ID).execute()
            sheets = sheet_metadata.get('sheets', [])
            sheet_exists = any(sheet['properties']['title'] == SHEET_NAME for sheet in sheets)

            if not sheet_exists:
                # Crear la hoja
                request_body = {
                    'requests': [{
                        'addSheet': {
                            'properties': {
                                'title': SHEET_NAME
                            }
                        }
                    }]
                }
                service.spreadsheets().batchUpdate(
                    spreadsheetId=GOOGLE_SHEET_ID,
                    body=request_body
                ).execute()

                # Añadir cabeceras
                cabeceras = [['Fecha Reporte', 'Nombre Proyecto', 'Total Horas Registradas']]
                service.spreadsheets().values().update(
                    spreadsheetId=GOOGLE_SHEET_ID,
                    range=f'{SHEET_NAME}!A1:C1',
                    valueInputOption='RAW',
                    body={'values': cabeceras}
                ).execute()

        except Exception as e:
            print(f"[WARNING] Error al verificar/crear hoja: {str(e)}")

        # Añadir los datos (append para añadir al final)
        if valores:
            print(f"[INFO] Escribiendo {len(valores)} filas en Google Sheets...")
            print(f"[INFO] Sheet ID: {GOOGLE_SHEET_ID}")
            print(f"[INFO] Sheet Name: {SHEET_NAME}")
            print(f"[INFO] Range: {SHEET_NAME}!A:C")

            try:
                result = service.spreadsheets().values().append(
                    spreadsheetId=GOOGLE_SHEET_ID,
                    range=f'{SHEET_NAME}!A:C',
                    valueInputOption='RAW',
                    insertDataOption='INSERT_ROWS',
                    body={'values': valores}
                ).execute()

                print(f"[INFO] Respuesta de Google Sheets: {result}")
                filas_escritas = result.get('updates', {}).get('updatedRows', 0)
                print(f"[INFO] Filas escritas según Google: {filas_escritas}")
            except Exception as e:
                print(f"[ERROR] Error al escribir en Google Sheets: {str(e)}")
                import traceback
                traceback.print_exc()
                raise
        else:
            print(f"[WARNING] No hay valores para escribir en el sheet")
            filas_escritas = 0

        sheet_url = f'https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/edit#gid=0'

        print(f"[INFO] Exportación completada. Filas escritas: {filas_escritas}, Proyectos: {len(proyectos_con_horas)}")

        return jsonify({
            'success': True,
            'filas_escritas': filas_escritas,
            'url': sheet_url,
            'proyectos_exportados': len(proyectos_con_horas)
        })

    except Exception as e:
        print(f"[ERROR] Error al exportar a Google Sheets: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def calcular_horas_proyecto(project_type, project_id, fecha_inicio, fecha_fin):
    """
    Calcula las horas totales de un proyecto en el rango de fechas especificado.
    Suma todo el tiempo que las tareas estuvieron en estado "en_progreso" dentro del rango.

    Args:
        project_type: 'folder' o 'list'
        project_id: ID del proyecto
        fecha_inicio: datetime de inicio del rango
        fecha_fin: datetime de fin del rango

    Returns:
        float: Total de horas trabajadas en el rango de fechas
    """
    try:
        # Obtener todas las tareas del proyecto
        if project_type == 'folder':
            # Obtener listas del folder
            listas = db.get_lists_by_folder(project_id)
            tareas = []
            for lista in listas:
                tareas.extend(db.get_tasks_by_list(lista['id']))
        else:  # list
            tareas = db.get_tasks_by_list(project_id)

        print(f"[DEBUG] Proyecto {project_type} {project_id}: {len(tareas)} tareas, rango: {fecha_inicio.date()} - {fecha_fin.date()}")

        total_segundos = 0

        for tarea in tareas:
            # Obtener el historial de estados de la tarea
            historial = db.get_status_history(tarea['id'])

            if not historial:
                continue

            # Calcular tiempo en "en_progreso" dentro del rango de fechas
            in_progress_start = None

            for i, cambio in enumerate(historial):
                try:
                    # Parsear timestamp
                    timestamp = datetime.fromisoformat(cambio['changed_at'].replace('Z', '+00:00'))
                    # Si el timestamp no tiene timezone, añadirle UTC
                    if timestamp.tzinfo is None:
                        from datetime import timezone
                        timestamp = timestamp.replace(tzinfo=timezone.utc)
                except:
                    # Si falla el parseo, intentar sin timezone
                    try:
                        timestamp = datetime.fromisoformat(cambio['changed_at'])
                        # Añadir timezone UTC si no tiene
                        if timestamp.tzinfo is None:
                            from datetime import timezone
                            timestamp = timestamp.replace(tzinfo=timezone.utc)
                    except:
                        print(f"[WARNING] No se pudo parsear fecha '{cambio['changed_at']}' para tarea {tarea['name']}")
                        continue

                # Cuando cambia a "en_progreso", marcar inicio
                if cambio['new_status'] == 'en_progreso':
                    in_progress_start = timestamp

                # Cuando cambia a otro estado, calcular duración del período en progreso
                elif in_progress_start is not None:
                    fin_progreso = timestamp

                    # Calcular intersección con el rango de fechas
                    inicio_efectivo = max(in_progress_start, fecha_inicio)
                    fin_efectivo = min(fin_progreso, fecha_fin)

                    # Solo sumar si hay intersección
                    if inicio_efectivo < fin_efectivo:
                        segundos = (fin_efectivo - inicio_efectivo).total_seconds()
                        if segundos > 0:
                            total_segundos += segundos
                            print(f"[DEBUG]   Tarea '{tarea['name']}': +{segundos/3600:.2f}h ({inicio_efectivo.date()} - {fin_efectivo.date()})")

                    in_progress_start = None

            # Si la tarea sigue en progreso (no hubo cambio de estado después)
            if in_progress_start is not None and tarea['status'] == 'en_progreso':
                # Usar la fecha actual como fin, pero limitado a fecha_fin
                from datetime import timezone
                ahora = datetime.now(timezone.utc)

                fin_progreso = min(ahora, fecha_fin)

                # Calcular intersección con el rango de fechas
                inicio_efectivo = max(in_progress_start, fecha_inicio)
                fin_efectivo = min(fin_progreso, fecha_fin)

                # Solo sumar si hay intersección
                if inicio_efectivo < fin_efectivo:
                    segundos = (fin_efectivo - inicio_efectivo).total_seconds()
                    if segundos > 0:
                        total_segundos += segundos
                        print(f"[DEBUG]   Tarea '{tarea['name']}' (en progreso): +{segundos/3600:.2f}h ({inicio_efectivo.date()} - {fin_efectivo.date()})")

        # Convertir segundos a horas
        total_horas = total_segundos / 3600

        print(f"[DEBUG] Total proyecto: {total_horas:.2f} horas en rango de fechas")

        return total_horas

    except Exception as e:
        print(f"[ERROR] Error al calcular horas del proyecto {project_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return 0.0


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
