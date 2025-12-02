from flask import Flask, render_template, jsonify, request, redirect, session, url_for
import requests
from datetime import datetime, timedelta
import json
import os
import re
from dotenv import load_dotenv
import threading
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import quote
import db  # Importar módulo de base de datos
from flask_socketio import SocketIO, emit

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Inicializar SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

CLICKUP_CLIENT_ID = os.getenv('CLICKUP_CLIENT_ID')
CLICKUP_CLIENT_SECRET = os.getenv('CLICKUP_CLIENT_SECRET')
CLICKUP_API_TOKEN = os.getenv('CLICKUP_API_TOKEN')  # Token personal para webhooks
REDIRECT_URI = os.getenv('REDIRECT_URI')  # URL de callback de OAuth

# Configuración de email para alertas
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_EMAIL = os.getenv('SMTP_EMAIL', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')

# Configuración de webhook
WEBHOOK_SECRET_TOKEN = os.getenv('WEBHOOK_SECRET_TOKEN', '')

# Almacenamiento en memoria de alertas por tarea
# Estructura: {tarea_id: {aviso_activado, email_aviso, aviso_horas, aviso_minutos, ultima_actualizacion, ultimo_envio_email}}
alertas_tareas = {}

alertas_config = {}

# Caché de tareas actualizado vía webhook
# Estructura: {tarea_id: {datos_tarea, timestamp_actualizacion}}
tareas_cache = {}

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
    Convierte una fecha en múltiples formatos a formato display (YYYY-MM-DD HH:MM:SS)

    Returns:
        String en formato display o datetime.now() si hay error
    """
    iso_date = parse_date_flexible(date_value)
    if iso_date:
        try:
            dt = datetime.fromisoformat(iso_date.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            pass

    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')



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

        # Procesar según el tipo de evento
        result = None

        if 'task' in event_type.lower():
            result = process_task_event(event_type, data)
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


def process_task_event(event_type, data):
    """Procesa eventos relacionados con tareas"""
    task_id = data.get('task_id')

    if not task_id:
        print("[WARNING] Evento de tarea sin task_id")
        return {'status': 'error', 'message': 'task_id requerido'}

    if event_type in ['taskDeleted', 'taskDeleted']:
        # Obtener list_id antes de eliminar
        old_task = db.get_task(task_id)
        list_id_deleted = old_task.get('list_id') if old_task else None

        # Eliminar tarea de la base de datos
        db.delete_task(task_id)
        # Eliminar del caché
        if task_id in tareas_cache:
            del tareas_cache[task_id]

        # Emitir evento WebSocket
        socketio.emit('task_deleted', {
            'task_id': task_id,
            'list_id': list_id_deleted
        }, namespace='/')

        print(f"[INFO] Tarea {task_id} eliminada")
        print(f"[INFO] Evento WebSocket 'task_deleted' emitido para tarea {task_id}")
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
        db.save_status_change(
            task_id=task_id,
            old_status=old_status,
            new_status=estado,
            old_status_text=old_status_text,
            new_status_text=data.get('status', 'Sin estado')
        )
        print(f"[INFO] Cambio de estado registrado: {task_id} de '{old_status}' a '{estado}'")

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

    # Emitir evento WebSocket según el tipo de evento
    if event_type == 'taskCreated':
        socketio.emit('task_created', {
            'task_id': task_id,
            'task': tareas_cache[task_id],
            'list_id': list_id
        }, namespace='/')
        print(f"[INFO] Evento WebSocket 'task_created' emitido para tarea {task_id}")
    elif event_type == 'taskDeleted':
        socketio.emit('task_deleted', {
            'task_id': task_id,
            'list_id': list_id
        }, namespace='/')
        print(f"[INFO] Evento WebSocket 'task_deleted' emitido para tarea {task_id}")
    elif event_type in ['taskUpdated', 'taskStatusUpdated']:
        socketio.emit('task_updated', {
            'task_id': task_id,
            'task': tareas_cache[task_id],
            'list_id': list_id,
            'status_changed': old_status != estado,
            'old_status': old_status,
            'new_status': estado
        }, namespace='/')
        print(f"[INFO] Evento WebSocket 'task_updated' emitido para tarea {task_id}")

    # Verificar alertas si está configurada
    alert = db.get_task_alert(task_id)
    if alert and alert.get('aviso_activado'):
        check_and_send_alert(task_id, task_name, task_url, date_updated, alert)

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
        # Emitir evento WebSocket
        socketio.emit('project_deleted', {
            'project_id': list_id,
            'project_type': 'list',
            'space_id': space_id
        }, namespace='/')

        print(f"[INFO] Lista {list_id} eliminada")
        print(f"[INFO] Evento WebSocket 'project_deleted' emitido para lista {list_id}")
        return {'status': 'deleted', 'list_id': list_id}

    # Guardar lista en BD
    db.save_list(list_id, list_name, space_id, folder_id, archived, metadata=data)
    print(f"[INFO] Lista {list_id} guardada: {list_name}")

    # Emitir evento WebSocket
    event_name = 'project_created' if event_type == 'listCreated' else 'project_updated'
    socketio.emit(event_name, {
        'project_id': list_id,
        'project_type': 'list',
        'project_name': list_name,
        'space_id': space_id,
        'folder_id': folder_id,
        'archived': archived
    }, namespace='/')
    print(f"[INFO] Evento WebSocket '{event_name}' emitido para lista {list_id}")

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
        # Emitir evento WebSocket
        socketio.emit('project_deleted', {
            'project_id': folder_id,
            'project_type': 'folder',
            'space_id': space_id
        }, namespace='/')

        print(f"[INFO] Carpeta {folder_id} eliminada")
        print(f"[INFO] Evento WebSocket 'project_deleted' emitido para carpeta {folder_id}")
        return {'status': 'deleted', 'folder_id': folder_id}

    db.save_folder(folder_id, folder_name, space_id, hidden, metadata=data)
    print(f"[INFO] Carpeta {folder_id} guardada: {folder_name}")

    # Emitir evento WebSocket
    event_name = 'project_created' if event_type == 'folderCreated' else 'project_updated'
    socketio.emit(event_name, {
        'project_id': folder_id,
        'project_type': 'folder',
        'project_name': folder_name,
        'space_id': space_id,
        'hidden': hidden
    }, namespace='/')
    print(f"[INFO] Evento WebSocket '{event_name}' emitido para carpeta {folder_id}")

    return {'status': 'saved', 'folder_id': folder_id, 'name': folder_name}


def process_space_event(event_type, data):
    """Procesa eventos relacionados con espacios"""
    space_id = data.get('space_id')
    if not space_id:
        return {'status': 'error', 'message': 'space_id requerido'}

    space_name = data.get('space_name') or data.get('name', 'Sin nombre')
    team_id = data.get('team_id')

    if event_type == 'spaceDeleted':
        # Emitir evento WebSocket
        socketio.emit('space_deleted', {
            'space_id': space_id
        }, namespace='/')

        print(f"[INFO] Espacio {space_id} eliminado")
        print(f"[INFO] Evento WebSocket 'space_deleted' emitido para espacio {space_id}")
        return {'status': 'deleted', 'space_id': space_id}

    db.save_space(space_id, space_name, team_id, metadata=data)
    print(f"[INFO] Espacio {space_id} guardado: {space_name}")

    # Emitir evento WebSocket
    event_name = 'space_created' if event_type == 'spaceCreated' else 'space_updated'
    socketio.emit(event_name, {
        'space_id': space_id,
        'space_name': space_name,
        'team_id': team_id
    }, namespace='/')
    print(f"[INFO] Evento WebSocket '{event_name}' emitido para espacio {space_id}")

    return {'status': 'saved', 'space_id': space_id, 'name': space_name}


def check_and_send_alert(task_id, task_name, task_url, date_updated, alert_config):
    """Verifica y envía alerta si es necesario"""
    try:
        fecha_actualizacion = datetime.fromtimestamp(int(date_updated) / 1000) if date_updated else datetime.now()
        tiempo_transcurrido = datetime.now() - fecha_actualizacion

        tiempo_alerta = timedelta(
            hours=alert_config.get('aviso_horas', 0),
            minutes=alert_config.get('aviso_minutos', 0)
        )

        if tiempo_transcurrido >= tiempo_alerta:
            # Verificar último envío
            ultimo_envio = alert_config.get('ultimo_envio_email')
            if ultimo_envio:
                # Parsear timestamp de SQLite
                try:
                    ultimo_envio_dt = datetime.fromisoformat(ultimo_envio.replace('Z', '+00:00'))
                except:
                    ultimo_envio_dt = datetime.now() - timedelta(days=2)  # Forzar envío

                if datetime.now() - ultimo_envio_dt < timedelta(days=1):
                    return  # No enviar, ya se envió hace menos de 1 día

            # Enviar email
            email_destino = alert_config.get('email_aviso')
            if email_destino:
                horas = int(tiempo_transcurrido.total_seconds() // 3600)
                minutos = int((tiempo_transcurrido.total_seconds() % 3600) // 60)
                tiempo_sin_act = f"{horas} horas y {minutos} minutos"

                if enviar_email_alerta(email_destino, task_name, task_url, tiempo_sin_act):
                    db.update_alert_last_sent(task_id)
                    print(f"[INFO] Email de alerta enviado para tarea {task_id}")

    except Exception as e:
        print(f"[ERROR] Error al verificar alerta para tarea {task_id}: {str(e)}")

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
                    all_spaces.append({
                        'id': space['id'],
                        'name': space['name'],
                        'team_id': team['id']
                    })
        
        return jsonify({'spaces': all_spaces})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/space/<space_id>/projects')
def get_projects(space_id):
    """Obtiene todas las carpetas y listas de un espacio"""
    try:
        headers = get_headers()
        if not headers:
            return jsonify({'error': 'No autenticado', 'redirect': '/login'}), 401

        proyectos = []

        # Obtener folders del space
        folders_response = requests.get(
            f'https://api.clickup.com/api/v2/space/{space_id}/folder',
            headers=headers,
            timeout=10
        )

        if folders_response.status_code == 200:
            folders = folders_response.json()['folders']
            for folder in folders:
                # Añadir el folder como proyecto
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
                proyectos.append({
                    'id': f'list_{lista["id"]}',
                    'name': f'📄 {lista["name"]}',
                    'type': 'list',
                    'list_id': lista['id']
                })

        return jsonify({'projects': proyectos})

    except Exception as e:
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
    """Calcula el tiempo total que una tarea ha estado en estado 'in progress' usando time_in_status de ClickUp"""
    try:
        # Obtener información completa de la tarea
        tarea_response = requests.get(
            f'https://api.clickup.com/api/v2/task/{tarea_id}',
            headers=headers,
            timeout=10
        )

        if tarea_response.status_code != 200:
            print(f"[WARNING] No se pudo obtener información de tarea {tarea_id}")
            return 0, 0

        tarea_info = tarea_response.json()

        # Obtener estado actual de la tarea
        estado_actual_lower = tarea_info.get('status', {}).get('status', '').lower()
        estado_actual_nombre = tarea_info.get('status', {}).get('status', 'Sin estado')
        print(f"[INFO] Estado actual de tarea {tarea_id}: {estado_actual_nombre}")

        # Usar el endpoint de time_in_status para obtener el tiempo en cada estado
        time_in_status_response = requests.get(
            f'https://api.clickup.com/api/v2/task/{tarea_id}/time_in_status',
            headers=headers,
            timeout=10
        )

        tiempo_total_segundos = 0

        if time_in_status_response.status_code == 200:
            time_in_status_data = time_in_status_response.json()

            print(f"[INFO] Obteniendo tiempo por estado desde ClickUp time_in_status")

            # El formato esperado de respuesta:
            # {
            #   "current_status": {...},
            #   "status_history": [...]
            # }

            status_history = time_in_status_data.get('status_history', [])
            current_status = time_in_status_data.get('current_status', {})

            print(f"[DEBUG] Estados en historial: {len(status_history)}")

            # Sumar tiempo de todos los estados que contengan "progress" o "doing"
            for status_entry in status_history:
                status_name = status_entry.get('status', '').lower()
                total_time = status_entry.get('total_time', {})

                # Verificar si es un estado "in progress"
                if 'progress' in status_name or 'doing' in status_name:
                    # El tiempo puede venir en diferentes formatos
                    # Intentar obtener milisegundos primero
                    if 'by_minute' in total_time:
                        minutos = total_time['by_minute']
                        segundos = minutos * 60
                    elif 'milliseconds' in total_time:
                        segundos = total_time['milliseconds'] / 1000
                    else:
                        segundos = 0

                    tiempo_total_segundos += segundos
                    print(f"[INFO] ✓ Estado '{status_entry.get('status')}': {segundos/3600:.2f}h ({segundos/60:.1f}min)")

            # Si el estado actual es "in progress", también incluir su tiempo
            if current_status:
                current_status_name = current_status.get('status', '').lower()
                if 'progress' in current_status_name or 'doing' in current_status_name:
                    total_time = current_status.get('total_time', {})
                    if 'by_minute' in total_time:
                        minutos = total_time['by_minute']
                        segundos = minutos * 60
                        tiempo_total_segundos += segundos
                        print(f"[INFO] ✓ Estado actual '{current_status.get('status')}': {segundos/3600:.2f}h ({segundos/60:.1f}min)")

            print(f"[INFO] Tiempo total en estados 'In Progress': {tiempo_total_segundos/3600:.2f}h")

        else:
            print(f"[WARNING] No se pudo obtener time_in_status para tarea {tarea_id}, status code: {time_in_status_response.status_code}")
            if time_in_status_response.status_code == 403:
                print(f"[WARNING] La ClickApp 'Time in Status' requiere plan Business o superior")
                print(f"[INFO] Usando tiempo rastreado manualmente (time_spent) como alternativa")
            elif time_in_status_response.status_code == 404:
                print(f"[WARNING] La ClickApp 'Total time in Status' NO está habilitada")
                print(f"[INFO] Usando tiempo rastreado manualmente (time_spent) como alternativa")

            # Fallback: usar time_spent (tiempo rastreado manualmente por usuarios)
            time_spent = tarea_info.get('time_spent', 0)
            if time_spent > 0:
                # time_spent está en milisegundos
                tiempo_total_segundos = time_spent / 1000
                print(f"[INFO] Usando time_spent (tiempo manual): {tiempo_total_segundos/3600:.2f}h")
            else:
                print(f"[WARNING] No hay tiempo rastreado manualmente para esta tarea")
                print(f"[INFO] Los usuarios deben usar el Time Tracker de ClickUp para registrar tiempo")
                return 0, 0

        # Convertir a horas y minutos
        horas = int(tiempo_total_segundos // 3600)
        minutos = int((tiempo_total_segundos % 3600) // 60)

        print(f"[INFO] Tiempo total 'In Progress' calculado desde activity: {horas}h {minutos}m (Estado actual: {estado_actual_nombre})")

        return horas, minutos

    except Exception as e:
        print(f"[ERROR] Error al calcular tiempo en progreso para tarea {tarea_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return 0, 0

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

                # Fecha de última actualización
                fecha_actualizacion = datetime.fromtimestamp(int(tarea['date_updated']) / 1000).strftime('%Y-%m-%d %H:%M:%S')

                # Calcular tiempo en estado "in progress" usando el historial
                print(f"[INFO] Calculando tiempo para tarea: {tarea['name']} (ID: {tarea['id']})")
                horas_trabajadas, minutos_trabajados = calcular_tiempo_en_progreso(tarea['id'], estado, headers)
                print(f"[INFO] Tiempo calculado para tarea {tarea['id']}: {horas_trabajadas}h {minutos_trabajados}m")

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
                    'alerta': alerta_config
                })

        return tareas_procesadas

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Error al obtener tareas de la lista {lista_id}: {str(e)}")
        return []
    except Exception as e:
        print(f"[ERROR] Error inesperado en obtener_tareas_de_lista: {str(e)}")
        return []

def procesar_lista(lista, headers):
    lista_id = lista['id']
    lista_nombre = lista['name']

    tasks_response = requests.get(
        f'https://api.clickup.com/api/v2/list/{lista_id}/task',
        headers=headers,
        params={'order_by': 'updated', 'reverse': 'true', 'page': 0},
        timeout=10
    )

    ultima_actualizacion = None
    titulo_ultima_tarea = "Sin tareas"
    enlace_tarea = ""
    tarea_id = ""

    if tasks_response.status_code == 200:
        tasks = tasks_response.json()['tasks']
        if tasks:
            tarea = tasks[0]
            ultima_actualizacion = datetime.fromtimestamp(int(tarea['date_updated']) / 1000)
            titulo_ultima_tarea = tarea['name']
            tarea_id = tarea['id']
            enlace_tarea = tarea['url']

    alerta_config = alertas_config.get(lista_id, {
        'activa': False,
        'email': '',
        'horas': 0,
        'minutos': 0
    })

    return {
        'id': lista_id,
        'nombre': lista_nombre,
        'ultima_actualizacion': ultima_actualizacion.strftime('%Y-%m-%d %H:%M:%S') if ultima_actualizacion else 'N/A',
        'titulo_ultima': titulo_ultima_tarea,
        'enlace_tarea': enlace_tarea,
        'tarea_id': tarea_id,
        'alerta': alerta_config
    }

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

def enviar_email_alerta(email_destino, tarea_nombre, tarea_url, tiempo_sin_actualizacion):
    """Envía un email de alerta cuando una tarea no ha sido actualizada"""
    try:
        if not SMTP_EMAIL or not SMTP_PASSWORD:
            print("[WARNING] Configuración de email no disponible. No se puede enviar email.")
            return False

        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'Alerta: Tarea sin actualización - {tarea_nombre}'
        msg['From'] = SMTP_EMAIL
        msg['To'] = email_destino

        # Crear el cuerpo del email en HTML
        html = f"""
        <html>
          <head></head>
          <body>
            <h2>Alerta de Tarea sin Actualización</h2>
            <p>La tarea <strong>{tarea_nombre}</strong> no ha recibido actualizaciones en <strong>{tiempo_sin_actualizacion}</strong>.</p>
            <p>Por favor, revisa el estado de esta tarea:</p>
            <p><a href="{tarea_url}" style="background-color: #667eea; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">Ver Tarea en ClickUp</a></p>
            <br>
            <p style="color: #666;">Este es un email automático del sistema Virtual Controller SIDN.</p>
          </body>
        </html>
        """

        # Crear el cuerpo del email en texto plano
        text = f"""
        Alerta de Tarea sin Actualización

        La tarea "{tarea_nombre}" no ha recibido actualizaciones en {tiempo_sin_actualizacion}.

        Por favor, revisa el estado de esta tarea:
        {tarea_url}

        Este es un email automático del sistema Virtual Controller SIDN.
        """

        part1 = MIMEText(text, 'plain')
        part2 = MIMEText(html, 'html')

        msg.attach(part1)
        msg.attach(part2)

        # Enviar el email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)

        print(f"[INFO] Email de alerta enviado a {email_destino} para tarea {tarea_nombre}")
        return True

    except Exception as e:
        print(f"[ERROR] Error al enviar email: {str(e)}")
        return False

@app.route('/api/verificar-alertas', methods=['POST'])
def verificar_alertas():
    """Verifica si alguna tarea necesita enviar alerta basándose en su última actualización"""
    try:
        headers = get_headers()
        if not headers:
            return jsonify({'error': 'No autenticado'}), 401

        data = request.json
        tareas_a_verificar = data.get('tareas', [])

        alertas_enviadas = []

        for tarea_data in tareas_a_verificar:
            tarea_id = tarea_data['id']

            # Verificar si esta tarea tiene alerta configurada
            if tarea_id not in alertas_tareas:
                continue

            config_alerta = alertas_tareas[tarea_id]

            if not config_alerta.get('aviso_activado'):
                continue

            # Obtener información actualizada de la tarea desde ClickUp
            try:
                tarea_response = requests.get(
                    f'https://api.clickup.com/api/v2/task/{tarea_id}',
                    headers=headers,
                    timeout=10
                )

                if tarea_response.status_code != 200:
                    print(f"[WARNING] No se pudo obtener información de tarea {tarea_id}")
                    continue

                tarea = tarea_response.json()

                # Obtener la última fecha de actualización
                fecha_actualizacion = datetime.fromtimestamp(int(tarea['date_updated']) / 1000)
                tiempo_transcurrido = datetime.now() - fecha_actualizacion

                # Calcular el tiempo de alerta configurado
                tiempo_alerta = timedelta(
                    hours=config_alerta.get('aviso_horas', 0),
                    minutes=config_alerta.get('aviso_minutos', 0)
                )

                # Verificar si ya pasó el tiempo de alerta
                if tiempo_transcurrido >= tiempo_alerta:
                    # Verificar si ya se envió un email recientemente (no enviar más de 1 por día)
                    ultimo_envio = config_alerta.get('ultimo_envio_email')
                    if ultimo_envio:
                        ultimo_envio_dt = datetime.fromisoformat(ultimo_envio)
                        if datetime.now() - ultimo_envio_dt < timedelta(days=1):
                            continue

                    # Enviar email de alerta
                    email_destino = config_alerta.get('email_aviso')
                    if email_destino:
                        # Formatear el tiempo sin actualización
                        horas = int(tiempo_transcurrido.total_seconds() // 3600)
                        minutos = int((tiempo_transcurrido.total_seconds() % 3600) // 60)
                        tiempo_sin_act = f"{horas} horas y {minutos} minutos"

                        if enviar_email_alerta(
                            email_destino,
                            tarea['name'],
                            tarea['url'],
                            tiempo_sin_act
                        ):
                            # Actualizar fecha del último envío
                            alertas_tareas[tarea_id]['ultimo_envio_email'] = datetime.now().isoformat()
                            alertas_enviadas.append({
                                'tarea_id': tarea_id,
                                'nombre': tarea['name'],
                                'email': email_destino
                            })

            except Exception as e:
                print(f"[ERROR] Error al verificar tarea {tarea_id}: {str(e)}")
                continue

        return jsonify({
            'success': True,
            'alertas_enviadas': alertas_enviadas
        })

    except Exception as e:
        print(f"[ERROR] Error en verificación de alertas: {str(e)}")
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
        return jsonify({
            'success': True,
            'task_id': task_id,
            'history': history
        })

    except Exception as e:
        print(f"[ERROR] Error al obtener historial de tarea {task_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
