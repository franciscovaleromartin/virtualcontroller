from flask import Flask, render_template, jsonify, request, redirect, session, url_for
import requests
from datetime import datetime, timedelta
import json
import os
import requests
from datetime import datetime, timedelta
import json
import os
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import atexit
import time

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

CLICKUP_CLIENT_ID = os.getenv('CLICKUP_CLIENT_ID')
CLICKUP_CLIENT_SECRET = os.getenv('CLICKUP_CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI', 'https://virtualcontroller.onrender.com')

# Email Config
SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')

ALERTS_FILE = 'alerts.json'

def load_alerts():
    if os.path.exists(ALERTS_FILE):
        try:
            with open(ALERTS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_alerts(alerts):
    with open(ALERTS_FILE, 'w') as f:
        json.dump(alerts, f)

alertas_config = load_alerts()
# Track sent alerts to avoid spamming: {task_id: timestamp}
sent_alerts = {}

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
        
        todas_listas = []
        
        if lists_response.status_code == 200:
            listas = lists_response.json()['lists']
            for lista in listas:
                info_lista = procesar_lista(lista, headers)
                todas_listas.append(info_lista)
        
        if folders_response.status_code == 200:
            folders = folders_response.json()['folders']
            for folder in folders:
                folder_lists = requests.get(
                    f'https://api.clickup.com/api/v2/folder/{folder["id"]}/list',
                    headers=headers
                )
                if folder_lists.status_code == 200:
                    for lista in folder_lists.json()['lists']:
                        info_lista = procesar_lista(lista, headers)
                        todas_listas.append(info_lista)
        
        return jsonify({'lists': todas_listas})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
            'minutos': int(data['minutos']),
            'token': session.get('access_token') # Save token for background job
        }
        
        save_alerts(alertas_config)
        
        return jsonify({'success': True, 'message': 'Alerta guardada correctamente'})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def send_email(to_email, subject, body):
    if not SMTP_USER or not SMTP_PASSWORD:
        print("SMTP credentials not configured")
        return False
        
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        text = msg.as_string()
        server.sendmail(SMTP_USER, to_email, text)
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

def check_tasks():
    print(f"Checking tasks for alerts... {datetime.now()}")
    for lista_id, config in alertas_config.items():
        if not config.get('activa') or not config.get('token'):
            continue
            
        try:
            headers = {
                'Authorization': config['token'],
                'Content-Type': 'application/json'
            }
            
            # Get tasks from list
            response = requests.get(
                f'https://api.clickup.com/api/v2/list/{lista_id}/task',
                headers=headers,
                params={'include_closed': 'false'} # Only open tasks
            )
            
            if response.status_code == 200:
                tasks = response.json()['tasks']
                limit_minutes = (config.get('horas', 0) * 60) + config.get('minutos', 0)
                
                for task in tasks:
                    # Check if task is in progress (status type custom or just assume open)
                    # Get time tracked
                    time_spent_ms = int(task.get('time_spent', 0) or 0)
                    time_spent_minutes = time_spent_ms / 1000 / 60
                    
                    if time_spent_minutes > limit_minutes and limit_minutes > 0:
                        # Check if we already sent an email recently (e.g., in the last 24h)
                        task_id = task['id']
                        if task_id not in sent_alerts:
                            # Send email
                            subject = f"Alerta: Tarea excedida de tiempo - {task['name']}"
                            body = f"""
                            <h1>Alerta de Tiempo</h1>
                            <p>La tarea <strong>{task['name']}</strong> ha excedido el tiempo límite.</p>
                            <p><strong>Tiempo transcurrido:</strong> {int(time_spent_minutes)} minutos</p>
                            <p><strong>Límite configurado:</strong> {limit_minutes} minutos</p>
                            <p><a href="{task['url']}">Ver tarea en ClickUp</a></p>
                            """
                            if send_email(config['email'], subject, body):
                                sent_alerts[task_id] = datetime.now()
                                print(f"Email sent for task {task_id}")
        except Exception as e:
            print(f"Error checking list {lista_id}: {e}")

@app.route('/api/dashboard')
def dashboard_data():
    # Aggregate data for the dashboard
    total_time_ms = 0
    active_tasks = []
    
    if 'access_token' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
        
    headers = {
        'Authorization': session['access_token'],
        'Content-Type': 'application/json'
    }
    
    return jsonify({
        'monitored_lists': len(alertas_config),
        'alerts_active': sum(1 for c in alertas_config.values() if c.get('activa'))
    })

@app.route('/api/verificar-alertas', methods=['POST'])
def webhook_verificar_alertas():
    try:
        check_tasks()
        return jsonify({'status': 'success', 'message': 'Verificación de alertas ejecutada'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

scheduler = BackgroundScheduler()
scheduler.add_job(func=check_tasks, trigger="interval", minutes=5)
scheduler.start()

atexit.register(lambda: scheduler.shutdown())

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
