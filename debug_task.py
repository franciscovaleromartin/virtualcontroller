"""
Script de debugging para verificar el estado de una tarea específica
Uso: python debug_task.py <task_id>
"""
import sys
import sqlite3
from datetime import datetime

if len(sys.argv) < 2:
    print("Uso: python debug_task.py <task_id>")
    sys.exit(1)

task_id = sys.argv[1]
DATABASE_PATH = 'virtualcontroller.db'

print(f"\n=== DEBUG PARA TAREA {task_id} ===\n")
print(f"Timestamp actual UTC: {datetime.utcnow().isoformat()}Z\n")

try:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Verificar si la tarea existe
    print("1. TAREA EN BD:")
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    if task:
        task_dict = dict(task)
        print(f"   Nombre: {task_dict.get('name')}")
        print(f"   Estado: {task_dict.get('status')} ({task_dict.get('status_text')})")
        print(f"   date_updated: {task_dict.get('date_updated')}")
    else:
        print("   ❌ Tarea NO encontrada en BD")

    # 2. Verificar historial
    print("\n2. HISTORIAL DE CAMBIOS DE ESTADO:")
    cursor.execute("""
        SELECT * FROM task_status_history
        WHERE task_id = ?
        ORDER BY changed_at ASC
    """, (task_id,))
    history = cursor.fetchall()

    if history:
        for i, record in enumerate(history):
            rec_dict = dict(record)
            print(f"   [{i}] {rec_dict.get('old_status')} → {rec_dict.get('new_status')} @ {rec_dict.get('changed_at')}")
    else:
        print("   ❌ NO hay registros de historial")

    # 3. Calcular tiempo
    print("\n3. CÁLCULO DE TIEMPO:")
    if task and task_dict.get('status') == 'en_progreso':
        print("   Tarea está en progreso")

        # Buscar el último registro de entrada a en_progreso
        in_progress_start = None
        for record in history:
            rec_dict = dict(record)
            if rec_dict['new_status'] == 'en_progreso':
                in_progress_start = rec_dict['changed_at']
                print(f"   Último inicio en progreso: {in_progress_start}")

        if in_progress_start:
            try:
                start_dt = datetime.fromisoformat(in_progress_start.replace('Z', '+00:00'))
                now_dt = datetime.utcnow()
                elapsed = (now_dt - start_dt).total_seconds()
                hours = int(elapsed // 3600)
                minutes = int((elapsed % 3600) // 60)
                seconds = int(elapsed % 60)
                print(f"   Tiempo transcurrido: {hours}h {minutes}m {seconds}s ({elapsed}s)")
            except Exception as e:
                print(f"   ❌ Error al calcular tiempo: {e}")
        else:
            print("   ❌ NO se encontró registro de inicio en progreso")
    else:
        print("   Tarea NO está en progreso actualmente")

    conn.close()

except FileNotFoundError:
    print(f"❌ Base de datos no encontrada: {DATABASE_PATH}")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*50 + "\n")
