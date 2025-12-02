# Virtual Controller SIDN

Sistema de monitoreo y alertas para tareas de ClickUp.

## Características

- **Autenticación OAuth con ClickUp**: Integración segura con tu cuenta de ClickUp
- **Selector de Proyectos**: Navega por espacios, carpetas y listas de manera jerárquica
- **Visualización de Tareas**: Muestra todas las tareas de tus proyectos de ClickUp con:
  - Estado actual (completada, en progreso, pendiente)
  - Tiempo trabajado en cada tarea (horas y minutos)
  - Última actualización
  - Tiempo total del trabajo
- **Sistema de Alertas Automáticas**: Configura alertas por email para tareas que no han sido actualizadas
- **Monitoreo en Tiempo Real**: Verificación periódica automática de tareas

## Requisitos

- Python 3.8+
- Cuenta de ClickUp con API OAuth configurada
- Cuenta de email para envío de alertas (opcional)

## Instalación

1. Clona el repositorio:
```bash
git clone <repository-url>
cd virtualcontroller
```

2. Instala las dependencias:
```bash
pip install -r requirements.txt
```

3. Configura las variables de entorno:
```bash
cp .env.example .env
# Edita .env con tus credenciales
```

4. Ejecuta la aplicación:
```bash
python app.py
```

## Configuración

### Variables de Entorno

Edita el archivo `.env` con las siguientes variables:

- `CLICKUP_CLIENT_ID`: ID de tu aplicación OAuth de ClickUp
- `CLICKUP_CLIENT_SECRET`: Secret de tu aplicación OAuth
- `REDIRECT_URI`: URL de redirección OAuth (por defecto: https://virtualcontroller.onrender.com)
- `SMTP_SERVER`: Servidor SMTP para envío de emails (por defecto: smtp.gmail.com)
- `SMTP_PORT`: Puerto SMTP (por defecto: 587)
- `SMTP_EMAIL`: Email desde el cual se enviarán las alertas
- `SMTP_PASSWORD`: Contraseña del email (se recomienda usar App Password de Gmail)
- `WEBHOOK_SECRET_TOKEN`: Token de seguridad para validar webhooks de make.com (opcional pero recomendado)

### Configuración de ClickUp OAuth

1. Ve a https://app.clickup.com/settings/apps
2. Crea una nueva aplicación OAuth
3. Configura la URL de redirección con tu dominio
4. Copia el Client ID y Client Secret al archivo .env

### Configuración de Email (Gmail)

Para usar Gmail como servidor SMTP:

1. Activa la verificación en dos pasos en tu cuenta de Gmail
2. Genera una "Contraseña de Aplicación" en https://myaccount.google.com/apppasswords
3. Usa esa contraseña en `SMTP_PASSWORD`

## Uso

### Visualizar Tareas

1. Selecciona un espacio (Space) de ClickUp
2. Selecciona un proyecto (Carpeta o Lista)
3. Se mostrarán todas las tareas del proyecto con su tiempo trabajado

### Configurar Alertas por Tarea

1. Selecciona un espacio (Space) de ClickUp
2. Selecciona un proyecto
3. Haz clic en el botón "Configurar" de cualquier tarea
4. En el modal de configuración:
   - Activa el checkbox "Activar aviso de demora"
   - Ingresa el email donde recibirás las alertas
   - Configura el tiempo (horas y minutos) sin actualización para enviar alerta
5. Haz clic en "Guardar"

### Integración con Webhooks (Make.com)

El sistema incluye un endpoint webhook que permite recibir actualizaciones en tiempo real desde ClickUp a través de make.com:

#### Configuración del Webhook

1. **Genera un token de seguridad**:
   ```bash
   # En Linux/Mac:
   openssl rand -hex 32

   # O usa cualquier generador de tokens aleatorios
   ```

2. **Configura el token** en tu archivo `.env`:
   ```
   WEBHOOK_SECRET_TOKEN=tu_token_secreto_aqui
   ```

3. **Configura Make.com**:
   - Crea un nuevo escenario en make.com
   - Conecta el trigger de ClickUp (cuando una tarea se actualiza)
   - Agrega un módulo HTTP para hacer una petición POST a tu webhook
   - URL del webhook: `https://tu-dominio.com/webhook/clickup?token=tu_token_secreto`
   - O alternativamente, envía el token en el header `X-Webhook-Token`

#### Formato del Payload

El webhook espera recibir un JSON con el siguiente formato:

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

**Campos requeridos:**
- `task_id`: ID de la tarea en ClickUp
- `task_name`: Nombre de la tarea
- `status`: Estado actual de la tarea
- `date_updated`: Timestamp de la última actualización (en milisegundos)
- `url`: URL de la tarea en ClickUp

**Campos opcionales:**
- `event_type`: Tipo de evento (taskUpdated, taskCreated, etc.)
- `horas_trabajadas`: Horas trabajadas en la tarea
- `minutos_trabajados`: Minutos trabajados en la tarea

#### Endpoints del Webhook

- **POST /webhook/clickup**: Recibe actualizaciones de tareas desde make.com
- **GET /api/webhook/tasks/cache**: Consulta el caché de tareas actualizadas vía webhook
  - Parámetro opcional: `?task_id=abc123` para obtener una tarea específica
- **DELETE /api/webhook/tasks/cache**: Limpia el caché de tareas (útil para testing)

#### Ventajas del Webhook

- ✅ Actualizaciones en tiempo real sin polling constante
- ✅ Menor uso de la API de ClickUp
- ✅ Alertas instantáneas cuando las tareas cambian
- ✅ Caché local de tareas para consultas rápidas

### Cómo Funcionan las Alertas

- El sistema verifica automáticamente cada 5 minutos las tareas con alertas activas
- Si una tarea no ha sido actualizada en el tiempo configurado, se envía un email de alerta
- Las alertas no se envían más de una vez por día para evitar spam
- El email incluye un enlace directo a la tarea en ClickUp

## Estructura del Proyecto

```
virtualcontroller/
├── app.py                 # Aplicación Flask principal
├── templates/
│   └── index.html        # Interfaz de usuario
├── .env                  # Variables de entorno (no incluido en git)
├── .env.example          # Plantilla de variables de entorno
├── requirements.txt      # Dependencias Python
└── README.md            # Este archivo
```

## Notas Técnicas

- Las configuraciones de alertas se almacenan en memoria durante la ejecución
- El tiempo trabajado se calcula **solo cuando la tarea está en estado "In Progress"**:
  - El sistema analiza el historial de cambios de estado de cada tarea
  - Suma todos los períodos en los que la tarea estuvo en "In Progress"
  - Si la tarea cambia a "To Do" o "Complete", el contador se detiene
  - Si vuelve a "In Progress", el contador continúa desde donde estaba
  - Esto permite saber el tiempo real dedicado a trabajar en cada tarea
- El sistema suma automáticamente todo el tiempo trabajado en las tareas para mostrar un total del proyecto
- El sistema soporta múltiples usuarios simultáneos con sesiones independientes
- La verificación de alertas se realiza desde el frontend usando el token del usuario activo

## Solución de Problemas

### Las alertas no se envían

- Verifica que las credenciales SMTP en `.env` sean correctas
- Asegúrate de usar una "Contraseña de Aplicación" si usas Gmail
- Revisa los logs del servidor para ver mensajes de error

### No aparecen las tareas

- Verifica que tu token de ClickUp sea válido
- Asegúrate de tener permisos para acceder al espacio seleccionado
- Revisa la consola del navegador para ver errores de API

## Contribuciones

Las contribuciones son bienvenidas. Por favor, abre un issue primero para discutir los cambios propuestos
