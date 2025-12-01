from flask import Flask, render_template, jsonify, request, redirect, session, url_for
import requests
from datetime import datetime, timedelta
import json
import os
from dotenv import load_dotenv
import threading
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

CLICKUP_CLIENT_ID = os.getenv('CLICKUP_CLIENT_ID')
CLICKUP_CLIENT_SECRET = os.getenv('CLICKUP_CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI', 'https://virtualcontroller.onrender.com')

# Configuración de email para alertas
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_EMAIL = os.getenv('SMTP_EMAIL', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')

# Almacenamiento en memoria de alertas por tarea
# Estructura: {tarea_id: {aviso_activado, email_aviso, aviso_horas, aviso_minutos, ultima_actualizacion, ultimo_envio_email}}
alertas_tareas = {}

alertas_config = {}

@app.route('/')
def inicio():
    code = request.args.get('code')

    print(f"[DEBUG] Ruta '/' accedida. Code presente: {bool(code)}")

    if code:
        print(f"[DEBUG] Procesando OAuth callback...")
        return handle_oauth_callback(code)

    if 'access_token' not in session:
        print(f"[DEBUG] No hay access_token, redirigiendo a login")
        return redirect(url_for('login'))

    print(f"[DEBUG] Usuario autenticado, mostrando página principal")
    return render_template('index.html')

def handle_oauth_callback(code):
    print(f"[DEBUG] OAuth callback recibido con código: {code[:10]}...")
    token_url = "https://api.clickup.com/api/v2/oauth/token"

    payload = {
        'client_id': CLICKUP_CLIENT_ID,
        'client_secret': CLICKUP_CLIENT_SECRET,
        'code': code
    }

    print(f"[DEBUG] Enviando request a ClickUp para obtener token...")

    try:
        response = requests.post(token_url, data=payload)

        print(f"[DEBUG] Respuesta de ClickUp: Status {response.status_code}")

        if response.status_code != 200:
            print(f"[ERROR] Error al obtener token: {response.text}")
            return f"Error al obtener token (Status {response.status_code}): {response.text}", 400

        token_data = response.json()
        session['access_token'] = token_data['access_token']

        print(f"[DEBUG] Token obtenido y guardado en sesión correctamente")

        return redirect('/')

    except Exception as e:
        print(f"[ERROR] Excepción en OAuth callback: {str(e)}")
        return f"Error: {str(e)}", 500

@app.route('/login')
def login():
    auth_url = f"https://app.clickup.com/api?client_id={CLICKUP_CLIENT_ID}&redirect_uri={REDIRECT_URI}"
    print(f"[DEBUG] Redirigiendo a ClickUp OAuth: {auth_url}")
    return redirect(auth_url)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

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
            if time_in_status_response.status_code == 404:
                print(f"[ERROR] La ClickApp 'Total time in Status' NO está habilitada en tu Workspace")
                print(f"[INFO] Para habilitarla: Settings > ClickApps > Busca 'Time in Status' > Activar")
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

        # Guardar en el diccionario en memoria
        alertas_tareas[tarea_id] = {
            'aviso_activado': aviso_activado,
            'email_aviso': email_aviso,
            'aviso_horas': aviso_horas,
            'aviso_minutos': aviso_minutos,
            'ultima_actualizacion': datetime.now().isoformat()
        }

        print(f"[INFO] Alerta guardada para tarea {tarea_id}: {alertas_tareas[tarea_id]}")

        return jsonify({'success': True, 'message': 'Alerta guardada correctamente'})

    except Exception as e:
        print(f"[ERROR] Error al guardar alerta de tarea: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/alerta/tarea/<tarea_id>', methods=['GET'])
def obtener_alerta_tarea_endpoint(tarea_id):
    """Obtiene la configuración de alerta para una tarea específica"""
    try:
        alerta = alertas_tareas.get(tarea_id, {
            'aviso_activado': False,
            'email_aviso': '',
            'aviso_horas': 0,
            'aviso_minutos': 0
        })
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
