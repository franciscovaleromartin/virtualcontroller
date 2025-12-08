# Virtual Controller

## ¿Qué es?

**Virtual Controller** es un sistema de monitoreo inteligente y alertas automáticas para proyectos de ClickUp. Funciona como un "vigilante" que te avisa cuando tus tareas llevan demasiado tiempo trabajándose, ayudándote a detectar tareas que consumen más tiempo del esperado y mantener tus proyectos bajo control.

Es una aplicación web Flask que se conecta a tu cuenta de ClickUp y te permite:
- Visualizar todas tus tareas con el tiempo real que has trabajado en ellas
- Configurar alertas personalizadas por email para cada tarea
- Recibir notificaciones automáticas cuando una tarea necesita atención
- Integrar webhooks para sincronización en tiempo real con ClickUp
- Generar informes de horas trabajadas y exportarlos a Google Sheets

## ¿Por qué debería importarte?

### 🚀 Problemas que resuelve

**¿Te suena familiar alguno de estos escenarios?**

- ❌ Tareas importantes que se quedan olvidadas durante días o semanas
- ❌ Pérdida de tiempo revisando manualmente ClickUp para ver qué tareas están estancadas
- ❌ Falta de visibilidad del tiempo real trabajado en cada tarea
- ❌ Necesidad de recordar manualmente hacer seguimiento de tareas críticas
- ❌ Clientes o stakeholders preguntando por tareas que llevan tiempo sin moverse
- ❌ Dificultad para generar reportes de horas trabajadas para facturación

**Virtual Controller soluciona todo esto automáticamente:**

- ✅ **Alertas automáticas por tiempo trabajado**: Recibes un email cuando una tarea lleva demasiado tiempo en estado "In Progress"
- ✅ **Ahorro de tiempo**: No más revisiones manuales constantes de ClickUp
- ✅ **Visibilidad real**: Ve exactamente cuánto tiempo se ha trabajado en cada tarea (solo cuando está "In Progress")
- ✅ **Proactividad**: Actúa antes de que los problemas se conviertan en crisis
- ✅ **Sincronización en tiempo real**: Con webhooks, los cambios en ClickUp se reflejan instantáneamente
- ✅ **Informes automáticos**: Genera reportes de horas trabajadas por proyecto y expórtalos a Google Sheets con un clic

### 💡 Casos de uso ideales

- **Project Managers**: Mantén todos los proyectos activos sin tareas abandonadas y genera informes de horas para stakeholders
- **Equipos de desarrollo**: Asegúrate de que ningún bug o tarea quede olvidada y mide el tiempo real invertido
- **Agencias**: Monitorea múltiples proyectos de clientes simultáneamente y genera reportes de facturación automáticos
- **Freelancers**: Ten control total de tu carga de trabajo, tiempos y genera informes para cobrar a tus clientes
- **Consultores**: Trackea el tiempo dedicado a cada proyecto y exporta reportes para justificar horas facturadas
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

# Google OAuth para Informes (opcional)
GOOGLE_CLIENT_ID=tu_google_client_id
GOOGLE_CLIENT_SECRET=tu_google_client_secret
GOOGLE_REDIRECT_URI=http://localhost:5000/oauth/google/callback

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
   - ⏰ Configura el **límite de tiempo trabajado** (horas y minutos)
3. Haz clic en **"Guardar"**
4. 🔔 Recibirás un email cuando la tarea supere el tiempo configurado en estado "In Progress"

#### Cómo funcionan las alertas

El sistema de alertas funciona basándose en el **tiempo total trabajado** en cada tarea:

- ⏱️ **Cálculo inteligente**: El sistema suma solo el tiempo que la tarea ha estado en estado "In Progress"
- ✅ **Verificación automática cada 5 minutos**: Revisa todas las tareas con alertas activas
- 🎯 **Alerta por tiempo trabajado**: Se envía email cuando el tiempo trabajado supera el límite configurado
- 📧 **Email automático**: Incluye nombre de la tarea, proyecto, tiempo trabajado y enlace directo
- 🔕 **Desactivación automática**: La alerta se desactiva después de enviar el email (evita spam)

**Ejemplo práctico:**
- Configuras una alerta de 8 horas para una tarea
- La tarea pasa 4 horas en "In Progress", luego cambia a "To Do"
- Más tarde vuelve a "In Progress" y pasa 5 horas más
- Total: 9 horas trabajadas → Se envía la alerta ✉️

**Importante:**
- ❗ La alerta **solo se verifica** cuando la tarea está actualmente en estado "In Progress"
- ❗ El contador **no avanza** cuando la tarea está en "To Do" o "Complete"
- ❗ El tiempo se calcula desde el historial completo de cambios de estado

#### Generar informes de horas trabajadas

1. Haz clic en el botón **"📊 Importar Informe"** en la barra superior
2. Si es tu primera vez:
   - Se abrirá una ventana para autenticarte con Google
   - Acepta los permisos para Google Sheets
   - Solo necesitas hacer esto una vez
3. Selecciona el **rango de fechas**:
   - Fecha de inicio (ej: 2024-12-01)
   - Fecha de fin (ej: 2024-12-31)
4. Haz clic en **"Importar Informe"**
5. Espera unos segundos mientras el sistema:
   - Sincroniza los datos desde ClickUp
   - Calcula las horas por proyecto
   - Exporta a Google Sheets
6. 📊 **¡Listo!** Haz clic en "Ver Informe en Google Sheets" para abrir el reporte

**El informe incluye:**
- Fecha del reporte
- Nombre de cada proyecto (folders y listas)
- Total de horas trabajadas en formato "Xh Ym"
- Solo proyectos con tiempo registrado (> 0 horas)

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

### 📊 Generación de Informes a Google Sheets

Virtual Controller incluye un potente sistema de exportación de informes que te permite generar reportes de horas trabajadas por proyecto y exportarlos directamente a Google Sheets.

#### ¿Qué información exporta?

El informe incluye:
- **Fecha del reporte**: Cuándo se generó el informe
- **Nombre del proyecto**: Cada carpeta y lista de ClickUp
- **Total de horas trabajadas**: Tiempo real trabajado (solo en estado "In Progress")

#### Cómo usar los informes

1. **Autenticación con Google**:
   - Haz clic en el botón **"📊 Importar Informe"** en la interfaz
   - Inicia sesión con tu cuenta de Google (se solicitarán permisos para Google Sheets)
   - Solo necesitas hacer esto una vez

2. **Configurar las credenciales de Google OAuth** (si eres el administrador):
   - Ve a [Google Cloud Console](https://console.cloud.google.com/)
   - Crea un proyecto nuevo o usa uno existente
   - Activa la **Google Sheets API**
   - Crea credenciales OAuth 2.0
   - Descarga el JSON de credenciales
   - Agrega las credenciales a tu `.env`:
     ```env
     GOOGLE_CLIENT_ID=tu_client_id
     GOOGLE_CLIENT_SECRET=tu_client_secret
     GOOGLE_REDIRECT_URI=https://tu-dominio.com/oauth/google/callback
     ```

3. **Generar un informe**:
   - Haz clic en **"📊 Importar Informe"**
   - Selecciona el **rango de fechas** (fecha inicio y fecha fin)
   - Haz clic en **"Importar Informe"**
   - El sistema automáticamente:
     1. 🔄 Sincroniza todos los datos desde ClickUp
     2. 📊 Calcula las horas trabajadas por proyecto en ese rango
     3. 📤 Exporta los datos a Google Sheets
     4. ✅ Te muestra un enlace directo al informe

4. **Ver el informe**:
   - Haz clic en el enlace **"📊 Ver Informe en Google Sheets"**
   - El informe se abre en una nueva pestaña
   - Los datos se añaden al final (modo append), por lo que puedes generar múltiples informes

#### Cálculo inteligente de horas

El sistema calcula las horas de forma precisa:

- ✅ **Solo tiempo "In Progress"**: Cuenta únicamente cuando las tareas están siendo trabajadas
- ✅ **Filtrado por rango**: Solo incluye el tiempo trabajado dentro de las fechas seleccionadas
- ✅ **Historial completo**: Analiza todos los cambios de estado de cada tarea
- ✅ **Sin duplicados**: Evita contar el mismo tiempo dos veces
- ✅ **Solo proyectos con horas**: No exporta proyectos con 0 horas (mantiene el informe limpio)

**Ejemplo de cálculo:**
- Rango del informe: 1-15 de Diciembre
- Tarea 1: estuvo 5h en "In Progress" el día 3 de Diciembre → ✅ Se cuenta
- Tarea 2: estuvo 3h en "In Progress" el 25 de Noviembre → ❌ No se cuenta (fuera del rango)
- Tarea 3: 2h "In Progress" el 14 de Diciembre + 2h el 20 de Diciembre → ✅ Solo se cuentan las 2h del día 14

#### Ventajas de los informes

- 📈 **Análisis de productividad**: Ve cuántas horas se dedican a cada proyecto
- 💼 **Facturación precisa**: Datos exactos para cobrar a clientes
- 📊 **Histórico completo**: Genera informes de cualquier período pasado
- 🔄 **Siempre actualizado**: Sincroniza con ClickUp antes de cada export
- 📝 **Fácil de compartir**: Los informes están en Google Sheets, accesibles para todo tu equipo
- 🎯 **Sin configuración manual**: Todo es automático, solo selecciona las fechas

#### Configuración del Spreadsheet

Por defecto, el sistema exporta a un Google Spreadsheet específico. Si quieres cambiar el destino:

1. Crea un nuevo Google Spreadsheet
2. Copia el ID del Spreadsheet (está en la URL):
   ```
   https://docs.google.com/spreadsheets/d/[ESTE_ES_EL_ID]/edit
   ```
3. Modifica el archivo `app.py` y cambia la variable `GOOGLE_SHEET_ID`

**Formato del informe en Google Sheets:**

| Fecha Reporte | Nombre Proyecto | Total Horas Registradas |
|--------------|----------------|------------------------|
| 2024-12-07   | Proyecto Web   | 15h 30m                |
| 2024-12-07   | App Mobile     | 8h 45m                 |
| 2024-12-07   | Marketing      | 3h 15m                 |

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
