from flask import Flask, render_template, jsonify, request, redirect, session, url_for
import requests
from datetime import datetime, timedelta
import json
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

CLICKUP_CLIENT_ID = os.getenv('CLICKUP_CLIENT_ID')
CLICKUP_CLIENT_SECRET = os.getenv('CLICKUP_CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI', 'https://virtualcontroller.onrender.com')

alertas_config = {}

@app.route('/')
def inicio():
    code = request.args.get('code')
    
    if code:
        return handle_oauth_callback(code)
    
    if 'access_token' not in session:
        return redirect(url_for('login'))
    
    return render_template('index.html')

def handle_oauth_callback(code):
    token_url = "https://api.clickup.com/api/v2/oauth/token"
    
    payload = {
        'client_id': CLICKUP_CLIENT_ID,
        'client_secret': CLICKUP_CLIENT_SECRET,
        'code': code
    }
    
    try:
        response = requests.post(token_url, data=payload)
        
        if response.status_code != 200:
            return f"Error al obtener token (Status {response.status_code}): {response.text}", 400
        
        token_data = response.json()
        session['access_token'] = token_data['access_token']
        
        return redirect('/')
    
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/login')
def login():
    auth_url = f"https://app.clickup.com/api?client_id={CLICKUP_CLIENT_ID}&redirect_uri={REDIRECT_URI}"
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
        
        teams_response = requests.get('https://api.clickup.com/api/v2/team', headers=headers)
        
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
                headers=headers
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

@app.route('/api/space/<space_id>/lists')
def get_lists(space_id):
    try:
        headers = get_headers()
        if not headers:
            return jsonify({'error': 'No autenticado', 'redirect': '/login'}), 401

        folders_response = requests.get(
            f'https://api.clickup.com/api/v2/space/{space_id}/folder',
            headers=headers
        )

        lists_response = requests.get(
            f'https://api.clickup.com/api/v2/space/{space_id}/list',
            headers=headers
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
                    headers=headers
                )
                if folder_lists.status_code == 200:
                    for lista in folder_lists.json()['lists']:
                        tareas = obtener_tareas_de_lista(lista['id'], headers)
                        todas_tareas.extend(tareas)

        return jsonify({'tasks': todas_tareas})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

def obtener_tareas_de_lista(lista_id, headers):
    """Obtiene todas las tareas de una lista con su estado y tiempo estimado"""
    tasks_response = requests.get(
        f'https://api.clickup.com/api/v2/list/{lista_id}/task',
        headers=headers,
        params={'include_closed': 'true'}
    )

    tareas_procesadas = []

    if tasks_response.status_code == 200:
        tasks = tasks_response.json()['tasks']
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

            # Obtener tiempo estimado (en milisegundos)
            time_estimate = tarea.get('time_estimate', 0)
            # Convertir a horas (milisegundos / 1000 / 60 / 60)
            horas_estimadas = time_estimate / 3600000 if time_estimate else 0

            # Fecha de última actualización
            fecha_actualizacion = datetime.fromtimestamp(int(tarea['date_updated']) / 1000).strftime('%Y-%m-%d %H:%M:%S')

            tareas_procesadas.append({
                'id': tarea['id'],
                'nombre': tarea['name'],
                'estado': estado,
                'estado_texto': tarea.get('status', {}).get('status', 'Sin estado'),
                'url': tarea['url'],
                'fecha_actualizacion': fecha_actualizacion,
                'horas_estimadas': round(horas_estimadas, 2)
            })

    return tareas_procesadas

def procesar_lista(lista, headers):
    lista_id = lista['id']
    lista_nombre = lista['name']

    tasks_response = requests.get(
        f'https://api.clickup.com/api/v2/list/{lista_id}/task',
        headers=headers,
        params={'order_by': 'updated', 'reverse': 'true', 'page': 0}
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

@app.route('/api/alerta/guardar', methods=['POST'])
def guardar_alerta():
    try:
        data = request.json
        lista_id = data['lista_id']
        
        alertas_config[lista_id] = {
            'activa': data['activa'],
            'email': data['email'],
            'horas': int(data['horas']),
            'minutos': int(data['minutos'])
        }
        
        return jsonify({'success': True, 'message': 'Alerta guardada correctamente'})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
