# 🔍 Guía de Diagnóstico de Emails - Sistema de Alertas

Esta guía te ayudará a diagnosticar y resolver problemas con el envío de emails de alerta.

---

## 📋 Checklist de Configuración

### 1. Variables de Entorno en Render

Verifica que estas variables estén configuradas en tu servicio de Render:

```bash
SMTP_SERVER=smtp-relay.brevo.com
SMTP_PORT=587
SMTP_EMAIL=tu_email@dominio.com    # ← Email configurado en Brevo
SMTP_PASSWORD=tu_smtp_key           # ← SMTP Key de Brevo (NO tu contraseña)
```

⚠️ **IMPORTANTE:** `SMTP_PASSWORD` debe ser la **SMTP Key** de Brevo, no tu contraseña de login.

**Dónde obtener la SMTP Key:**
1. Ve a https://app.brevo.com/settings/keys/smtp
2. Copia la clave SMTP (no la API key)
3. Úsala como `SMTP_PASSWORD`

---

## 🛠️ Herramientas de Diagnóstico

### A. Script de Diagnóstico Local

Para probar la configuración SMTP localmente:

```bash
# Crear archivo .env con tus credenciales
cat > .env << EOF
SMTP_SERVER=smtp-relay.brevo.com
SMTP_PORT=587
SMTP_EMAIL=tu_email@dominio.com
SMTP_PASSWORD=tu_smtp_key_de_brevo
EOF

# Ejecutar script de diagnóstico
python3 test_smtp_brevo.py
```

Este script:
- ✅ Verifica que todas las variables estén configuradas
- ✅ Prueba la conexión al servidor SMTP
- ✅ Valida las credenciales
- ✅ (Opcional) Envía un email de prueba

---

### B. Endpoint de Estado SMTP

**GET** `/api/smtp-status`

Verifica el estado de la configuración SMTP desde la aplicación:

```bash
curl https://tu-app.onrender.com/api/smtp-status
```

**Respuesta:**
```json
{
  "smtp_server": "smtp-relay.brevo.com",
  "smtp_port": "587",
  "smtp_email": "tu_email@dominio.com",
  "smtp_password_configured": true,
  "all_configured": true,
  "connection_test": "SUCCESS"
}
```

---

### C. Endpoint de Prueba de Email

**POST** `/api/test-email`

Envía un email de prueba para verificar que todo funciona:

```bash
curl -X POST https://tu-app.onrender.com/api/test-email \
  -H "Content-Type: application/json" \
  -d '{"email": "tu_email_de_prueba@gmail.com"}'
```

**Respuesta exitosa:**
```json
{
  "success": true,
  "message": "Email de prueba enviado exitosamente a tu_email_de_prueba@gmail.com",
  "smtp_config": {
    "server": "smtp-relay.brevo.com",
    "port": "587",
    "email": "tu_email@dominio.com"
  }
}
```

---

## 🐛 Problemas Comunes y Soluciones

### ❌ Error: "Configuración SMTP no disponible"

**Causa:** Las variables de entorno no están configuradas en Render.

**Solución:**
1. Ve a tu servicio en Render
2. Settings → Environment
3. Agrega las 4 variables SMTP
4. Reinicia el servicio (Deploy → Manual Deploy → Clear build cache & deploy)

---

### ❌ Error: "SMTPAuthenticationError"

**Causa:** Credenciales incorrectas.

**Soluciones posibles:**

1. **Estás usando tu contraseña en lugar de la SMTP Key:**
   - Ve a https://app.brevo.com/settings/keys/smtp
   - Copia la **SMTP Key** (no tu contraseña de login)
   - Actualiza `SMTP_PASSWORD` en Render

2. **Email incorrecto:**
   - Verifica que `SMTP_EMAIL` sea el email configurado en tu cuenta de Brevo
   - Debe coincidir con el email verificado en Brevo

3. **Cuenta de Brevo no activada:**
   - Verifica tu email para activar la cuenta de Brevo
   - Completa la verificación de dominio si es necesario

---

### ❌ Error: "SMTPConnectError" o "Connection timeout"

**Causa:** No se puede conectar al servidor SMTP.

**Soluciones:**

1. **Puerto bloqueado:**
   - Verifica que Render permita conexiones salientes al puerto 587
   - Render generalmente permite esto, pero verifica en su documentación

2. **Servidor incorrecto:**
   - Verifica que `SMTP_SERVER` sea exactamente: `smtp-relay.brevo.com`
   - Verifica que `SMTP_PORT` sea: `587`

---

### ❌ Los emails van a SPAM

**Soluciones:**

1. **Verifica tu dominio en Brevo:**
   - Ve a https://app.brevo.com/senders
   - Agrega y verifica tu dominio
   - Configura SPF, DKIM y DMARC

2. **Usa un email verificado como remitente:**
   - El email en `SMTP_EMAIL` debe estar verificado en Brevo

3. **Evita palabras spam:**
   - El asunto del email ya está optimizado
   - No modifiques el contenido del email sin revisar las mejores prácticas

---

### ❌ Los emails no llegan (sin error)

**Pasos de diagnóstico:**

1. **Revisa los logs de Render:**
   ```bash
   # En Render dashboard → Logs
   # Busca líneas que empiecen con [EMAIL]
   ```

2. **Verifica los logs de Brevo:**
   - Ve a https://app.brevo.com/logs
   - Revisa el estado de los emails enviados
   - Si aparecen como "enviados" pero no llegan, revisa spam

3. **Verifica la bandeja de spam:**
   - Los primeros emails pueden ir a spam
   - Márcalos como "No es spam" para futuros envíos

4. **Usa el endpoint de prueba:**
   ```bash
   curl -X POST https://tu-app.onrender.com/api/test-email \
     -H "Content-Type: application/json" \
     -d '{"email": "tu_email@gmail.com"}'
   ```

---

## 📊 Interpretando los Logs

### Logs Exitosos

```
[EMAIL] ===== Iniciando envío de email de alerta =====
[EMAIL] Destino: francisco@example.com
[EMAIL] Tarea: Implementar Dashboard
[EMAIL] Proyecto: Proyecto SIDN
[EMAIL] ✓ Configuración SMTP disponible
[EMAIL]    Servidor: smtp-relay.brevo.com:587
[EMAIL]    De: tu_email@dominio.com
[EMAIL] ✓ Mensaje creado
[EMAIL] ✓ Contenido del mensaje adjuntado (HTML + texto plano)
[EMAIL] Conectando al servidor SMTP...
[EMAIL] ✓ Conexión establecida
[EMAIL] Iniciando STARTTLS...
[EMAIL] ✓ STARTTLS iniciado
[EMAIL] Autenticando...
[EMAIL] ✓ Autenticación exitosa
[EMAIL] Enviando mensaje...
[EMAIL] ✓ Mensaje enviado exitosamente
[EMAIL] ===== Email enviado a francisco@example.com =====
[INFO] ✅ Email de alerta enviado para tarea 'Implementar Dashboard'
```

### Logs de Error - Configuración Faltante

```
[EMAIL] ❌ ERROR: Configuración de email no disponible
[EMAIL]    SMTP_SERVER: smtp-relay.brevo.com
[EMAIL]    SMTP_PORT: 587
[EMAIL]    SMTP_EMAIL: NO CONFIGURADO  ← Aquí está el problema
[EMAIL]    SMTP_PASSWORD: configurado
```

### Logs de Error - Autenticación

```
[EMAIL] ❌ ERROR DE AUTENTICACIÓN SMTP:
[EMAIL]    (535, b'5.7.1 Authentication failed')
[EMAIL]    Verifica las credenciales SMTP_EMAIL y SMTP_PASSWORD en Render
```

---

## ✅ Verificación Final

Una vez configurado todo, sigue estos pasos para verificar que funciona:

1. **Verifica el estado:**
   ```bash
   curl https://tu-app.onrender.com/api/smtp-status
   ```

2. **Envía un email de prueba:**
   ```bash
   curl -X POST https://tu-app.onrender.com/api/test-email \
     -H "Content-Type: application/json" \
     -d '{"email": "tu_email@gmail.com"}'
   ```

3. **Configura una alerta en una tarea:**
   - Abre una tarea en el frontend
   - Click en "Configurar"
   - Activa "Aviso de demora"
   - Ingresa tu email
   - Configura tiempo bajo (ej: 0 horas, 5 minutos)
   - Guarda

4. **Pon la tarea en progreso:**
   - Cambia el estado de la tarea a "En Progreso" en ClickUp
   - Espera 5-10 minutos

5. **Verifica el envío:**
   - Revisa los logs de Render
   - Busca `[EMAIL]` para ver el flujo
   - Revisa tu email (y spam)

---

## 🆘 Soporte Adicional

Si después de seguir todos estos pasos aún no funciona:

1. **Captura los logs completos:**
   - Ve a Render → Logs
   - Copia todo el output desde el inicio del intento de envío

2. **Verifica tu cuenta de Brevo:**
   - Estado de la cuenta: https://app.brevo.com
   - Límites de envío: https://app.brevo.com/settings/limits
   - Logs de envío: https://app.brevo.com/logs

3. **Verifica las variables:**
   ```bash
   curl https://tu-app.onrender.com/api/smtp-status
   ```

4. **Contacta soporte de Brevo:**
   - Si las credenciales son correctas pero no funciona
   - https://help.brevo.com/

---

## 📚 Recursos

- [Documentación SMTP de Brevo](https://developers.brevo.com/docs/send-emails-with-smtp)
- [Configurar SPF/DKIM en Brevo](https://help.brevo.com/hc/en-us/articles/209467485)
- [Variables de entorno en Render](https://render.com/docs/environment-variables)
- [Script de diagnóstico](./test_smtp_brevo.py)

---

## 📝 Última Actualización

**Fecha:** 2025-12-04
**Versión:** 1.0
**Autor:** Claude (Virtual Controller SIDN)
