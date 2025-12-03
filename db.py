"""
Sistema de persistencia de datos para Virtual Controller
Base de datos SQLite con tablas para espacios, proyectos, tareas y webhooks
"""

import sqlite3
import json
from datetime import datetime
from contextlib import contextmanager
import os

DATABASE_PATH = os.getenv('DATABASE_PATH', 'virtualcontroller.db')


@contextmanager
def get_db():
    """Context manager para conexiones de base de datos"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Inicializa la base de datos con todas las tablas necesarias"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Tabla de espacios (Spaces)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS spaces (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                team_id TEXT,
                private BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        """)

        # Tabla de carpetas (Folders)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS folders (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                space_id TEXT NOT NULL,
                hidden BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT,
                FOREIGN KEY (space_id) REFERENCES spaces(id) ON DELETE CASCADE
            )
        """)

        # Tabla de listas (Lists)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lists (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                space_id TEXT,
                folder_id TEXT,
                archived BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT,
                FOREIGN KEY (space_id) REFERENCES spaces(id) ON DELETE CASCADE,
                FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE CASCADE
            )
        """)

        # Tabla de tareas (Tasks)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                list_id TEXT NOT NULL,
                status TEXT DEFAULT 'pendiente',
                status_text TEXT,
                url TEXT,
                description TEXT,
                priority INTEGER,
                assignees TEXT,
                date_created TIMESTAMP,
                date_updated TIMESTAMP,
                date_closed TIMESTAMP,
                due_date TIMESTAMP,
                start_date TIMESTAMP,
                time_estimate INTEGER,
                time_spent INTEGER,
                horas_trabajadas INTEGER DEFAULT 0,
                minutos_trabajados INTEGER DEFAULT 0,
                parent_task_id TEXT,
                custom_fields TEXT,
                tags TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT,
                FOREIGN KEY (list_id) REFERENCES lists(id) ON DELETE CASCADE
            )
        """)

        # Tabla de configuración de alertas por tarea
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                aviso_activado BOOLEAN DEFAULT 0,
                email_aviso TEXT,
                aviso_horas INTEGER DEFAULT 0,
                aviso_minutos INTEGER DEFAULT 0,
                ultima_actualizacion TIMESTAMP,
                ultimo_envio_email TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                UNIQUE(task_id)
            )
        """)

        # Tabla de log de webhooks recibidos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS webhooks_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                task_id TEXT,
                list_id TEXT,
                folder_id TEXT,
                space_id TEXT,
                payload TEXT NOT NULL,
                processed BOOLEAN DEFAULT 0,
                error TEXT,
                received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP
            )
        """)

        # Tabla de historial de cambios de estado de tareas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_status_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                old_status TEXT,
                new_status TEXT NOT NULL,
                old_status_text TEXT,
                new_status_text TEXT,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
            )
        """)

        # Índices para mejorar rendimiento
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_list_id ON tasks(list_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_date_updated ON tasks(date_updated)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lists_space_id ON lists(space_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lists_folder_id ON lists(folder_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_folders_space_id ON folders(space_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_webhooks_event_type ON webhooks_log(event_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_webhooks_processed ON webhooks_log(processed)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status_history_task_id ON task_status_history(task_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status_history_changed_at ON task_status_history(changed_at)")

        conn.commit()
        print("[INFO] Base de datos inicializada correctamente")


# === FUNCIONES PARA SPACES ===

def save_space(space_id, name, team_id=None, metadata=None):
    """Guarda o actualiza un espacio"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO spaces (id, name, team_id, metadata, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                team_id = excluded.team_id,
                metadata = excluded.metadata,
                updated_at = CURRENT_TIMESTAMP
        """, (space_id, name, team_id, json.dumps(metadata) if metadata else None))
        conn.commit()


def get_space(space_id):
    """Obtiene un espacio por ID"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM spaces WHERE id = ?", (space_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_all_spaces():
    """Obtiene todos los espacios"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM spaces ORDER BY name")
        return [dict(row) for row in cursor.fetchall()]


# === FUNCIONES PARA FOLDERS ===

def save_folder(folder_id, name, space_id, hidden=False, metadata=None):
    """Guarda o actualiza una carpeta"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO folders (id, name, space_id, hidden, metadata, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                space_id = excluded.space_id,
                hidden = excluded.hidden,
                metadata = excluded.metadata,
                updated_at = CURRENT_TIMESTAMP
        """, (folder_id, name, space_id, hidden, json.dumps(metadata) if metadata else None))
        conn.commit()


def get_folders_by_space(space_id):
    """Obtiene todas las carpetas de un espacio"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM folders WHERE space_id = ? ORDER BY name", (space_id,))
        return [dict(row) for row in cursor.fetchall()]


# === FUNCIONES PARA LISTS ===

def save_list(list_id, name, space_id=None, folder_id=None, archived=False, metadata=None):
    """Guarda o actualiza una lista"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO lists (id, name, space_id, folder_id, archived, metadata, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                space_id = excluded.space_id,
                folder_id = excluded.folder_id,
                archived = excluded.archived,
                metadata = excluded.metadata,
                updated_at = CURRENT_TIMESTAMP
        """, (list_id, name, space_id, folder_id, archived, json.dumps(metadata) if metadata else None))
        conn.commit()


def get_lists_by_space(space_id):
    """Obtiene todas las listas de un espacio"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM lists WHERE space_id = ? ORDER BY name", (space_id,))
        return [dict(row) for row in cursor.fetchall()]


def get_lists_by_folder(folder_id):
    """Obtiene todas las listas de una carpeta"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM lists WHERE folder_id = ? ORDER BY name", (folder_id,))
        return [dict(row) for row in cursor.fetchall()]


# === FUNCIONES PARA TASKS ===

def save_task(task_data):
    """
    Guarda o actualiza una tarea
    task_data debe ser un diccionario con los campos de la tarea
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Preparar datos
        task_id = task_data.get('id')
        name = task_data.get('name', 'Sin nombre')
        list_id = task_data.get('list_id')
        status = task_data.get('status', 'pendiente')
        status_text = task_data.get('status_text')
        url = task_data.get('url')
        description = task_data.get('description')
        priority = task_data.get('priority')

        # Convertir assignees a JSON si es una lista (incluso si está vacía)
        assignees = task_data.get('assignees')
        if isinstance(assignees, list):
            assignees = json.dumps(assignees)
        elif assignees is not None and not isinstance(assignees, str):
            assignees = json.dumps(assignees)

        date_updated = task_data.get('date_updated')
        date_created = task_data.get('date_created')
        date_closed = task_data.get('date_closed')
        due_date = task_data.get('due_date')
        start_date = task_data.get('start_date')
        time_estimate = task_data.get('time_estimate')
        time_spent = task_data.get('time_spent')
        horas_trabajadas = task_data.get('horas_trabajadas', 0)
        minutos_trabajados = task_data.get('minutos_trabajados', 0)
        parent_task_id = task_data.get('parent_task_id')

        # Convertir custom_fields a JSON si es lista/dict (incluso si está vacío)
        custom_fields = task_data.get('custom_fields')
        if custom_fields is not None and not isinstance(custom_fields, str):
            custom_fields = json.dumps(custom_fields)

        # Convertir tags a JSON si es una lista (incluso si está vacía)
        tags = task_data.get('tags')
        if isinstance(tags, list):
            tags = json.dumps(tags)
        elif tags is not None and not isinstance(tags, str):
            tags = json.dumps(tags)

        # Convertir metadata a JSON si es dict/list (incluso si está vacío)
        metadata = task_data.get('metadata')
        if metadata is not None and not isinstance(metadata, str):
            metadata = json.dumps(metadata)

        cursor.execute("""
            INSERT INTO tasks (
                id, name, list_id, status, status_text, url, description, priority,
                assignees, date_created, date_updated, date_closed, due_date, start_date,
                time_estimate, time_spent, horas_trabajadas, minutos_trabajados,
                parent_task_id, custom_fields, tags, metadata, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                list_id = excluded.list_id,
                status = excluded.status,
                status_text = excluded.status_text,
                url = excluded.url,
                description = excluded.description,
                priority = excluded.priority,
                assignees = excluded.assignees,
                date_created = excluded.date_created,
                date_updated = excluded.date_updated,
                date_closed = excluded.date_closed,
                due_date = excluded.due_date,
                start_date = excluded.start_date,
                time_estimate = excluded.time_estimate,
                time_spent = excluded.time_spent,
                horas_trabajadas = excluded.horas_trabajadas,
                minutos_trabajados = excluded.minutos_trabajados,
                parent_task_id = excluded.parent_task_id,
                custom_fields = excluded.custom_fields,
                tags = excluded.tags,
                metadata = excluded.metadata,
                updated_at = CURRENT_TIMESTAMP
        """, (
            task_id, name, list_id, status, status_text, url, description, priority,
            assignees, date_created, date_updated, date_closed, due_date, start_date,
            time_estimate, time_spent, horas_trabajadas, minutos_trabajados,
            parent_task_id, custom_fields, tags, metadata
        ))
        conn.commit()


def get_task(task_id):
    """Obtiene una tarea por ID"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        if row:
            task = dict(row)
            # Parsear JSON fields
            if task.get('assignees'):
                try:
                    task['assignees'] = json.loads(task['assignees'])
                except:
                    pass
            if task.get('custom_fields'):
                try:
                    task['custom_fields'] = json.loads(task['custom_fields'])
                except:
                    pass
            if task.get('tags'):
                try:
                    task['tags'] = json.loads(task['tags'])
                except:
                    pass
            if task.get('metadata'):
                try:
                    task['metadata'] = json.loads(task['metadata'])
                except:
                    pass
            return task
        return None


def get_tasks_by_list(list_id):
    """Obtiene todas las tareas de una lista"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM tasks
            WHERE list_id = ?
            ORDER BY date_updated DESC
        """, (list_id,))
        tasks = []
        for row in cursor.fetchall():
            task = dict(row)
            # Parsear JSON fields
            if task.get('assignees'):
                try:
                    task['assignees'] = json.loads(task['assignees'])
                except:
                    pass
            if task.get('tags'):
                try:
                    task['tags'] = json.loads(task['tags'])
                except:
                    pass
            tasks.append(task)
        return tasks


def delete_task(task_id):
    """Elimina una tarea"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()


# === FUNCIONES PARA TASK ALERTS ===

def save_task_alert(task_id, aviso_activado, email_aviso, aviso_horas, aviso_minutos):
    """Guarda o actualiza la configuración de alerta de una tarea"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO task_alerts (
                task_id, aviso_activado, email_aviso, aviso_horas, aviso_minutos,
                ultima_actualizacion, updated_at
            )
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(task_id) DO UPDATE SET
                aviso_activado = excluded.aviso_activado,
                email_aviso = excluded.email_aviso,
                aviso_horas = excluded.aviso_horas,
                aviso_minutos = excluded.aviso_minutos,
                ultima_actualizacion = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
        """, (task_id, aviso_activado, email_aviso, aviso_horas, aviso_minutos))
        conn.commit()


def get_task_alert(task_id):
    """Obtiene la configuración de alerta de una tarea"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM task_alerts WHERE task_id = ?", (task_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_all_active_alerts():
    """Obtiene todas las alertas activas"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ta.*, t.name as task_name, t.url as task_url, t.date_updated
            FROM task_alerts ta
            JOIN tasks t ON ta.task_id = t.id
            WHERE ta.aviso_activado = 1
        """)
        return [dict(row) for row in cursor.fetchall()]


def update_alert_last_sent(task_id):
    """Actualiza la fecha del último envío de email de alerta"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE task_alerts
            SET ultimo_envio_email = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE task_id = ?
        """, (task_id,))
        conn.commit()


# === FUNCIONES PARA WEBHOOKS LOG ===

def log_webhook(event_type, payload, task_id=None, list_id=None, folder_id=None, space_id=None):
    """Registra un webhook recibido"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO webhooks_log (
                event_type, task_id, list_id, folder_id, space_id, payload
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (event_type, task_id, list_id, folder_id, space_id, json.dumps(payload)))
        conn.commit()
        return cursor.lastrowid


def mark_webhook_processed(webhook_log_id, error=None):
    """Marca un webhook como procesado"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE webhooks_log
            SET processed = 1, processed_at = CURRENT_TIMESTAMP, error = ?
            WHERE id = ?
        """, (error, webhook_log_id))
        conn.commit()


def get_webhook_stats():
    """Obtiene estadísticas de webhooks procesados"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                event_type,
                COUNT(*) as total,
                SUM(CASE WHEN processed = 1 THEN 1 ELSE 0 END) as processed,
                SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as errors
            FROM webhooks_log
            GROUP BY event_type
        """)
        return [dict(row) for row in cursor.fetchall()]


# === FUNCIONES PARA TASK STATUS HISTORY ===

def save_status_change(task_id, old_status, new_status, old_status_text=None, new_status_text=None, changed_at=None):
    """
    Registra un cambio de estado de una tarea

    Args:
        task_id: ID de la tarea
        old_status: Estado anterior
        new_status: Nuevo estado
        old_status_text: Texto del estado anterior (opcional)
        new_status_text: Texto del nuevo estado (opcional)
        changed_at: Timestamp del cambio en formato ISO (opcional, usa CURRENT_TIMESTAMP si no se proporciona)
    """
    with get_db() as conn:
        cursor = conn.cursor()

        if changed_at:
            # Usar el timestamp proporcionado
            cursor.execute("""
                INSERT INTO task_status_history (
                    task_id, old_status, new_status, old_status_text, new_status_text, changed_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (task_id, old_status, new_status, old_status_text, new_status_text, changed_at))
        else:
            # Usar CURRENT_TIMESTAMP si no se proporciona
            cursor.execute("""
                INSERT INTO task_status_history (
                    task_id, old_status, new_status, old_status_text, new_status_text, changed_at
                )
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (task_id, old_status, new_status, old_status_text, new_status_text))

        conn.commit()
        return cursor.lastrowid


def get_status_history(task_id):
    """Obtiene el historial de cambios de estado de una tarea"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM task_status_history
            WHERE task_id = ?
            ORDER BY changed_at ASC
        """, (task_id,))
        return [dict(row) for row in cursor.fetchall()]


def get_active_in_progress_tasks():
    """Obtiene todas las tareas actualmente en estado 'en_progreso'"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, list_id, status, status_text, date_updated
            FROM tasks
            WHERE status = 'en_progreso'
        """)
        return [dict(row) for row in cursor.fetchall()]


def calculate_task_time_in_progress(task_id):
    """
    Calcula el tiempo total que una tarea ha estado en progreso
    Retorna un diccionario con:
    - total_seconds: segundos totales en progreso
    - current_session_start: timestamp del inicio de la sesión actual (si está en progreso)
    - is_currently_in_progress: boolean indicando si está actualmente en progreso
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Obtener el estado actual de la tarea
        cursor.execute("SELECT status FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        current_status = dict(row)['status'] if row else None

        # Obtener historial de cambios de estado
        cursor.execute("""
            SELECT new_status, changed_at
            FROM task_status_history
            WHERE task_id = ?
            ORDER BY changed_at ASC
        """, (task_id,))

        history = [dict(row) for row in cursor.fetchall()]

        total_seconds = 0
        current_session_start = None
        in_progress_start = None

        # Calcular tiempo acumulado
        for record in history:
            status = record['new_status']
            timestamp = datetime.fromisoformat(record['changed_at'])

            if status == 'en_progreso':
                # Inicio de un periodo en progreso
                in_progress_start = timestamp
            elif in_progress_start:
                # Fin de un periodo en progreso
                duration = (timestamp - in_progress_start).total_seconds()
                total_seconds += duration
                in_progress_start = None

        # Si actualmente está en progreso, el periodo actual está abierto
        is_currently_in_progress = current_status == 'en_progreso'
        if is_currently_in_progress and in_progress_start:
            current_session_start = in_progress_start.isoformat()
        elif is_currently_in_progress and not in_progress_start:
            # No hay historial pero está en progreso, buscar la fecha de actualización
            cursor.execute("SELECT date_updated FROM tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if row:
                date_updated = dict(row)['date_updated']
                if date_updated:
                    try:
                        current_session_start = datetime.fromisoformat(date_updated).isoformat()
                    except:
                        current_session_start = datetime.now().isoformat()

        return {
            'total_seconds': total_seconds,
            'current_session_start': current_session_start,
            'is_currently_in_progress': is_currently_in_progress
        }


# Inicializar base de datos al importar el módulo
try:
    print("[DB] Inicializando base de datos...", flush=True)
    init_db()
    print("[DB] Base de datos inicializada correctamente", flush=True)
except Exception as e:
    print(f"[DB ERROR] No se pudo inicializar la base de datos: {e}", flush=True)
    import traceback
    traceback.print_exc()
