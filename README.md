# Virtual Controller SIDN

Sistema de monitoreo y alertas para tareas de ClickUp.

## Características

- **Autenticación OAuth con ClickUp**: Integración segura con tu cuenta de ClickUp
- **Visualización de Tareas**: Muestra todas las tareas de tus espacios de ClickUp con:
  - Estado actual (completada, en progreso, pendiente)
  - Fecha de comienzo
  - Fecha de término
  - Última actualización
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

### Configurar Alertas por Tarea

1. Selecciona un espacio (Space) de ClickUp
2. Haz clic en el botón "Configurar" de cualquier tarea
3. En el modal de configuración:
   - Activa el checkbox "Activar aviso de demora"
   - Ingresa el email donde recibirás las alertas
   - Configura el tiempo (horas y minutos) sin actualización para enviar alerta
4. Haz clic en "Guardar"

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
- Las fechas de comienzo y término se obtienen directamente de la API de ClickUp
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
