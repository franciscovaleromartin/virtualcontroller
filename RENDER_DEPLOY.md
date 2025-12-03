# Guía de Despliegue en Render

## Configuración Recomendada

### 1. Configuración del Servicio Web

En el dashboard de Render, asegúrate de tener estas configuraciones:

**Build & Deploy:**
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `bash start.sh`

**Environment:**
- **Runtime:** Python 3.11.14 (especificado en `runtime.txt`)

**Health Check:**
- **Health Check Path:** `/health`
- **Health Check Interval:** 30 seconds
- **Timeout:** 30 seconds

### 2. Variables de Entorno Requeridas

Configura estas variables en el dashboard de Render:

```bash
# ClickUp OAuth
CLICKUP_CLIENT_ID=<tu_client_id>
CLICKUP_CLIENT_SECRET=<tu_client_secret>
CLICKUP_API_TOKEN=<tu_api_token>
REDIRECT_URI=<tu_redirect_uri>

# Email (opcional para alertas)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_EMAIL=<tu_email>
SMTP_PASSWORD=<tu_password>

# Webhook Security (opcional)
WEBHOOK_SECRET_TOKEN=<tu_token_secreto>

# Database (opcional, por defecto usa SQLite local)
DATABASE_PATH=/opt/render/project/data/virtualcontroller.db
```

### 3. Verificación del Despliegue

Después del despliegue, verifica:

1. **Health Check:**
   ```bash
   curl https://tu-app.onrender.com/health
   ```
   Debe retornar:
   ```json
   {"status": "ok", "timestamp": "...", "service": "virtualcontroller"}
   ```

2. **Logs:**
   Busca estas líneas en los logs:
   ```
   [Gunicorn Config] Puerto: 10000
   [STARTUP] Python version: 3.11.14
   [STARTUP] Inicializando aplicación...
   [DB] Inicializando base de datos...
   [DB] Base de datos inicializada correctamente
   [Gunicorn] ✓ Servidor listo y escuchando en 0.0.0.0:10000
   ```

### 4. Solución de Problemas Comunes

#### "No open ports detected"

**Causa:** El servidor no está levantando a tiempo o no responde al health check.

**Solución:**
1. Verifica que el health check path esté configurado a `/health` en el dashboard
2. Revisa los logs para ver dónde se queda el startup
3. Verifica que todas las dependencias se instalaron correctamente

#### "Build failed - gevent compilation error"

**Causa:** Python 3.13+ no es compatible con gevent 24.2.1.

**Solución:**
- El archivo `runtime.txt` especifica Python 3.11.14
- Si Render ignora `runtime.txt`, especifica la versión en Settings → Environment → Python Version

#### "Worker timeout"

**Causa:** El worker tarda más de 120 segundos en arrancar.

**Solución:**
1. Verifica que la base de datos SQLite se pueda crear en el path especificado
2. Considera usar `/opt/render/project/data/` para datos persistentes
3. Revisa logs de [DB] para ver si hay errores de inicialización

### 5. Actualización del Código

Para actualizar el código:

```bash
git add .
git commit -m "Tu mensaje"
git push origin main
```

Render automáticamente detectará los cambios y redesplegará.

### 6. Monitoreo

- **Health Check:** Render verifica `/health` cada 30 segundos
- **Logs:** Accesibles en el dashboard bajo la pestaña "Logs"
- **Métricas:** CPU, memoria y tráfico en la pestaña "Metrics"

## Arquitectura

```
Render.com
├── Build: pip install -r requirements.txt
├── Runtime: Python 3.11.14 (runtime.txt)
├── Start: bash start.sh
│   └── gunicorn -c gunicorn_config.py app:app
│       ├── Worker class: gevent (para WebSocket)
│       ├── Workers: 1 (requerido para Flask-SocketIO)
│       └── Port: $PORT (asignado por Render)
└── Health Check: GET /health (cada 30s)
```

## Soporte

Si el despliegue falla:
1. Revisa los logs completos en el dashboard
2. Verifica que todas las variables de entorno estén configuradas
3. Confirma que el health check path sea `/health`
4. Verifica que Python 3.11.14 esté siendo usado
