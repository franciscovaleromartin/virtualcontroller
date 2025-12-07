# Virtual Controller SIDN

## ¿Qué es?

**Virtual Controller** es un sistema de monitoreo inteligente y alertas automáticas para proyectos de ClickUp. Funciona como un "vigilante" que te avisa cuando tus tareas llevan demasiado tiempo sin actualizarse, ayudándote a mantener tus proyectos en movimiento.

Es una aplicación web Flask que se conecta a tu cuenta de ClickUp y te permite:
- Visualizar todas tus tareas con el tiempo real que has trabajado en ellas
- Configurar alertas personalizadas por email para cada tarea
- Recibir notificaciones automáticas cuando una tarea necesita atención
- Integrar webhooks para sincronización en tiempo real con ClickUp

## ¿Por qué debería importarte?

### 🚀 Problemas que resuelve

**¿Te suena familiar alguno de estos escenarios?**

- ❌ Tareas importantes que se quedan olvidadas durante días o semanas
- ❌ Pérdida de tiempo revisando manualmente ClickUp para ver qué tareas están estancadas
- ❌ Falta de visibilidad del tiempo real trabajado en cada tarea
- ❌ Necesidad de recordar manualmente hacer seguimiento de tareas críticas
- ❌ Clientes o stakeholders preguntando por tareas que llevan tiempo sin moverse

**Virtual Controller soluciona todo esto automáticamente:**

- ✅ **Alertas automáticas**: Recibes un email cuando una tarea lleva X tiempo sin actualizarse
- ✅ **Ahorro de tiempo**: No más revisiones manuales constantes de ClickUp
- ✅ **Visibilidad real**: Ve exactamente cuánto tiempo se ha trabajado en cada tarea (solo cuando está "In Progress")
- ✅ **Proactividad**: Actúa antes de que los problemas se conviertan en crisis
- ✅ **Sincronización en tiempo real**: Con webhooks, los cambios en ClickUp se reflejan instantáneamente

### 💡 Casos de uso ideales

- **Project Managers**: Mantén todos los proyectos activos sin tareas abandonadas
- **Equipos de desarrollo**: Asegúrate de que ningún bug o tarea quede olvidada
- **Agencias**: Monitorea múltiples proyectos de clientes simultáneamente
- **Freelancers**: Ten control total de tu carga de trabajo y tiempos
- **Cualquiera que use ClickUp**: Y quiera ser más productivo sin esfuerzo extra

## ¿Cómo se usa?

### Instalación rápida

1. **Clona el repositorio**:
   ```bash
   git clone <repository-url>
   cd virtualcontroller
   ```

2. **Instala las dependencias**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configura tus credenciales**:
   ```bash
   cp .env.example .env
   # Edita .env con tus credenciales (ver sección de configuración abajo)
   ```

4. **Ejecuta la aplicación**:
   ```bash
   python app.py
   ```

5. **Abre tu navegador** en `http://localhost:5000`

### Configuración inicial

#### 1. Configurar ClickUp OAuth

1. Ve a https://app.clickup.com/settings/apps
2. Crea una nueva aplicación OAuth
3. Configura la **Redirect URL**:
   - **Desarrollo local**: `http://localhost:5000`
   - **Producción**: `https://tu-dominio.com`
   - ⚠️ **Importante**: Sin `/` al final, sin `/callback` ni subdirectorios
4. Copia el `Client ID` y `Client Secret` al archivo `.env`:
   ```env
   CLICKUP_CLIENT_ID=tu_client_id
   CLICKUP_CLIENT_SECRET=tu_client_secret
   ```

#### 2. Configurar Email para Alertas (Gmail)

1. Activa la **verificación en dos pasos** en tu cuenta de Gmail
2. Genera una **Contraseña de Aplicación** en https://myaccount.google.com/apppasswords
3. Configura en tu `.env`:
   ```env
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   SMTP_EMAIL=tu-email@gmail.com
   SMTP_PASSWORD=tu_contraseña_de_aplicacion
   ```

#### 3. Variables de entorno completas

Edita el archivo `.env` con todas estas variables:

```env
# ClickUp OAuth
CLICKUP_CLIENT_ID=tu_client_id
CLICKUP_CLIENT_SECRET=tu_client_secret

# Email (SMTP)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_EMAIL=tu-email@gmail.com
SMTP_PASSWORD=tu_contraseña_de_aplicacion

# Webhook (opcional pero recomendado)
WEBHOOK_SECRET_TOKEN=genera_un_token_aleatorio_aqui

# Base de datos (opcional, tiene un default)
DATABASE_PATH=virtualcontroller.db
```

### Uso básico

#### Visualizar tus tareas

1. **Inicia sesión** con tu cuenta de ClickUp (OAuth)
2. **Selecciona un Space** (espacio) de ClickUp
3. **Selecciona un proyecto** (carpeta o lista)
4. 🎉 **¡Listo!** Verás todas tus tareas con:
   - Estado actual (completada, en progreso, pendiente)
   - Tiempo trabajado (solo cuando está "In Progress")
   - Última actualización
   - Tiempo total del proyecto

#### Configurar alertas para una tarea

1. Haz clic en el botón **"Configurar"** de cualquier tarea
2. En el modal:
   - ✅ Activa **"Activar aviso de demora"**
   - 📧 Ingresa el **email** donde recibirás alertas
   - ⏰ Configura el **tiempo sin actualización** (horas y minutos) para enviar la alerta
3. Haz clic en **"Guardar"**
4. 🔔 Ahora recibirás un email si la tarea no se actualiza en el tiempo configurado

#### Cómo funcionan las alertas

- ✅ Verificación automática cada **5 minutos**
- ✅ Email de alerta cuando la tarea no se actualiza en el tiempo configurado
- ✅ **Máximo 1 email por día** por tarea (evita spam)
- ✅ El email incluye un **enlace directo** a la tarea en ClickUp
- ✅ Las alertas se desactivan automáticamente después de enviar el email

## Características avanzadas

### 🔗 Integración con Webhooks (Make.com)

Los webhooks permiten que Virtual Controller reciba actualizaciones en **tiempo real** desde ClickUp, sin necesidad de consultar constantemente la API.

#### Ventajas de usar webhooks

- ⚡ **Actualizaciones instantáneas** sin polling constante
- 💰 **Menor uso de la API** de ClickUp (evita límites)
- 🔔 **Alertas más rápidas** cuando las tareas cambian
- 📦 **Caché local** de tareas para consultas ultra-rápidas
- 💾 **Persistencia automática** en base de datos SQLite

#### Configuración de webhooks

1. **Genera un token de seguridad**:
   ```bash
   openssl rand -hex 32
   ```

2. **Agrega el token a tu `.env`**:
   ```env
   WEBHOOK_SECRET_TOKEN=tu_token_secreto_generado
   ```

3. **Configura Make.com**:
   - Crea un nuevo escenario en make.com
   - Conecta el trigger de ClickUp (ej: "cuando una tarea se actualiza")
   - Agrega un módulo HTTP para hacer POST a:
     ```
     https://tu-dominio.com/webhook/clickup?token=tu_token_secreto
     ```
   - O envía el token en el header `X-Webhook-Token`

4. **Formato del payload** que debe enviar Make.com:
   ```json
   {
     "task_id": "abc123",
     "task_name": "Nombre de la tarea",
     "status": "in progress",
     "date_updated": 1234567890000,
     "url": "https://app.clickup.com/t/...",
     "event_type": "taskUpdated",
     "horas_trabajadas": 5,
     "minutos_trabajados": 30
   }
   ```

#### Endpoints disponibles

- **POST /webhook/clickup** - Recibe webhooks de ClickUp
- **GET /api/webhook/tasks/cache** - Consulta el caché de tareas
  - Opcional: `?task_id=abc123` para una tarea específica
- **DELETE /api/webhook/tasks/cache** - Limpia el caché (útil para testing)
- **GET /api/webhook/stats** - Estadísticas de webhooks procesados

#### Eventos soportados

- ✅ `taskCreated`, `taskUpdated`, `taskDeleted`, `taskStatusUpdated`
- ✅ `listCreated`, `listUpdated`, `listDeleted`
- ✅ `folderCreated`, `folderUpdated`, `folderDeleted`
- ✅ `spaceCreated`, `spaceUpdated`

### 💾 Persistencia de datos (SQLite)

Virtual Controller almacena todos los datos localmente en una base de datos SQLite:

**Tablas principales:**
- `spaces` - Espacios de ClickUp
- `folders` - Carpetas dentro de espacios
- `lists` - Listas de tareas
- `tasks` - Tareas completas (estado, fechas, tiempos, etc.)
- `task_alerts` - Configuración de alertas
- `webhooks_log` - Log de todos los webhooks recibidos

**Ventajas:**
- ✅ Datos persisten entre reinicios
- ✅ Sincronización automática con webhooks
- ✅ Log completo de eventos para debugging
- ✅ No requiere configuración manual

## Estructura del proyecto

```
virtualcontroller/
├── app.py                    # Aplicación Flask principal
├── db.py                     # Módulo de persistencia con SQLite
├── templates/
│   └── index.html           # Interfaz de usuario
├── .env                     # Variables de entorno (no en git)
├── .env.example             # Plantilla de variables de entorno
├── requirements.txt         # Dependencias Python
├── virtualcontroller.db     # Base de datos SQLite (auto-generado)
└── README.md               # Este archivo
```

## Requisitos del sistema

- **Python** 3.8 o superior
- **Cuenta de ClickUp** con API OAuth configurada
- **Cuenta de email** para envío de alertas (Gmail recomendado)
- **Make.com** (opcional, para webhooks)

## Notas técnicas importantes

### Cálculo del tiempo trabajado

El sistema calcula el tiempo trabajado **solo cuando la tarea está en estado "In Progress"**:

1. Analiza el historial de cambios de estado de cada tarea
2. Suma todos los períodos en los que la tarea estuvo "In Progress"
3. Si la tarea cambia a "To Do" o "Complete", el contador se detiene
4. Si vuelve a "In Progress", el contador continúa desde donde estaba

Esto permite saber el **tiempo real dedicado** a trabajar en cada tarea.

### Arquitectura

- **Backend**: Flask (Python)
- **Base de datos**: SQLite con módulo `db.py`
- **Frontend**: HTML/JavaScript con Bootstrap
- **Autenticación**: OAuth 2.0 con ClickUp
- **Alertas**: SMTP (Gmail o cualquier servidor compatible)
- **Scheduler**: APScheduler para verificaciones periódicas

### Seguridad

- ✅ Tokens de webhook para validar requests
- ✅ Sesiones de usuario independientes
- ✅ Credenciales en variables de entorno (nunca en código)
- ✅ OAuth 2.0 para autenticación segura

## Solución de problemas

### ❌ Las alertas no se envían

**Posibles causas:**
- Credenciales SMTP incorrectas en `.env`
- No estás usando una "Contraseña de Aplicación" en Gmail
- Firewall bloqueando puerto 587

**Solución:**
1. Verifica las credenciales en `.env`
2. Genera una nueva Contraseña de Aplicación en Gmail
3. Revisa los logs del servidor para ver errores específicos

### ❌ No aparecen las tareas

**Posibles causas:**
- Token de ClickUp expirado o inválido
- Sin permisos para acceder al espacio seleccionado
- Error en la configuración de OAuth

**Solución:**
1. Cierra sesión y vuelve a autenticarte
2. Verifica que tienes permisos en ClickUp para ese espacio
3. Revisa la consola del navegador (F12) para ver errores de API

### ❌ Webhooks no funcionan

**Posibles causas:**
- Token de webhook incorrecto
- Formato de payload incorrecto desde Make.com
- URL del webhook incorrecta

**Solución:**
1. Verifica que el token en `.env` coincida con el de Make.com
2. Revisa el formato del payload en la documentación arriba
3. Consulta `/api/webhook/stats` para ver si los webhooks llegan

## Contribuciones

Las contribuciones son bienvenidas. Por favor:
1. Abre un **issue** primero para discutir los cambios propuestos
2. Haz un **fork** del proyecto
3. Crea una **rama** para tu feature (`git checkout -b feature/AmazingFeature`)
4. Haz **commit** de tus cambios (`git commit -m 'Add some AmazingFeature'`)
5. Haz **push** a la rama (`git push origin feature/AmazingFeature`)
6. Abre un **Pull Request**

## Licencia

Este proyecto es de código abierto y está disponible bajo la licencia que decidas aplicar.

## Soporte

Si tienes problemas o preguntas:
- 🐛 Abre un **issue** en GitHub
- 📧 Contacta al equipo de desarrollo
- 📖 Consulta la **documentación** en este README

---

**Hecho con ❤️ para hacer la gestión de proyectos más fácil y automatizada**
