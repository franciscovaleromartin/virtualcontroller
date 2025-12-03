# 🔍 PASOS DE DEBUG PARA RENDER

## Problema Actual: Deploy falla sin logs

Esto indica un problema crítico en la configuración o en el inicio de la aplicación.

## ✅ PASO 1: Probar con App Mínima

He creado una versión ultra-simple de la app (`app_minimal.py`) que NO usa:
- ❌ gevent
- ❌ Flask-SocketIO
- ❌ Base de datos
- ❌ Imports complejos

### Configurar en Render Dashboard:

1. Ve a **Settings** → **Build & Deploy**

2. **Start Command:** Cambia a uno de estos (prueba en orden):

   **Opción A - Script mínimo:**
   ```bash
   bash start_minimal.sh
   ```

   **Opción B - Comando directo simple:**
   ```bash
   gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 120 --access-logfile - --error-logfile - --log-level debug app_minimal:app
   ```

3. **Health Check Path:** `/health`

4. **Redeploy** y observa los logs

### Logs Esperados:

```
======================================
[MINIMAL] Iniciando prueba mínima...
[MINIMAL] Puerto: 10000
[MINIMAL] Python: Python 3.11.14
======================================
[MINIMAL] Python: 3.11.14
[MINIMAL] Iniciando app mínima...
[MINIMAL] Flask importado
[MINIMAL] Flask app creada
[MINIMAL] Rutas configuradas
[MINIMAL] App lista para servir
[INFO] Booting worker with pid: XXXXX
==> Your service is live 🎉
```

### ¿Qué nos dice esto?

- **✅ Si funciona:** El problema está en la app completa (gevent, SocketIO, o db)
- **❌ Si falla:** El problema es la configuración de Render o el entorno

---

## ✅ PASO 2: Si la app mínima funciona, volver a la completa

Una vez que confirmes que la app mínima funciona, cambia el Start Command a:

```bash
gunicorn --worker-class gevent --workers 1 --bind 0.0.0.0:$PORT --timeout 120 --access-logfile - --error-logfile - --log-level info app:app
```

**IMPORTANTE:** SIN el flag `--preload` (causa problemas con gevent)

---

## ✅ PASO 3: Verificar configuración en Render

### Build Command debe ser:
```bash
pip install -r requirements.txt
```

### Environment Variables críticas:

Verifica que NO tengas variables que puedan estar causando conflictos:

- `PYTHON_VERSION` → debe ser `3.11.14` o vacío
- `PORT` → NO configurar (Render lo asigna automáticamente)
- `GUNICORN_CMD_ARGS` → NO configurar (puede sobrescribir nuestros parámetros)

---

## 🚨 Errores Comunes y Soluciones

### "No logs at all" (sin logs)

**Causa:** El proceso muere inmediatamente sin output

**Soluciones:**
1. Usa la app mínima primero para aislar el problema
2. Verifica que `runtime.txt` existe con `python-3.11.14`
3. Revisa si hay errores en la fase de Build (antes del deploy)

### "Build succeeds but Deploy fails silently"

**Causa:** Error en el Start Command o en la inicialización de Python

**Soluciones:**
1. Cambia a `app_minimal.py` temporalmente
2. Usa `--log-level debug` en gunicorn
3. Verifica que el archivo `app.py` existe después del build

### "Module not found" errors

**Causa:** Dependencias no instaladas o path incorrecto

**Soluciones:**
1. Verifica que `requirements.txt` está en la raíz
2. El Build Command debe ejecutarse antes del Start Command
3. Usa `pip list` para ver paquetes instalados

---

## 📊 Checklist de Configuración

Verifica estos puntos en el dashboard:

- [ ] **Environment:** Python 3.11.14
- [ ] **Build Command:** `pip install -r requirements.txt`
- [ ] **Start Command:** Uno de los comandos de arriba
- [ ] **Health Check Path:** `/health`
- [ ] **Variables de entorno:** Solo las necesarias (sin PYTHON_VERSION ni PORT)
- [ ] **Root Directory:** `.` (raíz del repo)

---

## 🆘 Si TODO falla

Comparte una **captura de pantalla** de:

1. **Settings → Build & Deploy** (Build Command y Start Command)
2. **Settings → Environment** (variables configuradas, oculta los valores sensibles)
3. **Logs completos** del último deploy (desde "==> Building" hasta el error)
4. **Build logs** (la fase de instalación de dependencias)

Con esa información podré identificar exactamente qué está fallando.
