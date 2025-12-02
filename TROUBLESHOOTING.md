# Solución de Problemas - Login de ClickUp

## Error: "¡Uy! No se puede autorizar a tus equipos"

Este error puede ocurrir por varias razones. Sigue estos pasos para diagnosticar el problema:

### 1. Verificar Variables de Entorno en Render

Ve a tu dashboard de Render y verifica que estas variables estén configuradas:

```
CLICKUP_CLIENT_ID=tu_client_id_real
CLICKUP_CLIENT_SECRET=tu_client_secret_real
```

**Cosas a verificar:**
- ✅ Las variables NO deben tener espacios al inicio o final
- ✅ Las variables NO deben tener comillas
- ✅ El CLIENT_ID debe tener un formato como: `ABC123DEF456`
- ✅ El CLIENT_SECRET debe ser una cadena larga de caracteres

**¿Cambiaste algo recientemente?**
- Si agregaste o editaste variables en Render, debes hacer un **Redeploy** para que se apliquen
- Las variables no se actualizan automáticamente hasta que redespliegas

### 2. Verificar URL de Callback en ClickUp

1. Ve a https://app.clickup.com/settings/apps
2. Selecciona tu aplicación OAuth
3. Verifica que la **Redirect URL** sea exactamente:
   - Para producción: `https://virtualcontroller.onrender.com/`
   - Para desarrollo: `http://localhost:5000/`

**IMPORTANTE:**
- Debe ser la raíz del dominio (solo `/` al final)
- NO debe ser `/oauth/callback` ni otro path
- Debe coincidir EXACTAMENTE (http vs https, con/sin www)

### 3. Verificar Configuración de ClickUp App

1. Ve a https://app.clickup.com/settings/apps
2. Verifica que tu aplicación:
   - Esté **activa** (no deshabilitada)
   - Tenga los permisos correctos
   - No haya sido eliminada o recreada (si la recreaste, el CLIENT_ID y SECRET cambian)

### 4. Verificar Logs de la Aplicación

Si estás usando Render, ve a los logs y busca:

```
[DEBUG] Callback URL generada: https://...
[DEBUG] Redirigiendo a ClickUp OAuth: https://...
[ERROR] Error al obtener token: ...
```

Los logs te dirán exactamente qué URL está usando y qué error recibe de ClickUp.

### 5. Probar Localmente

Si el problema está en producción, prueba localmente:

```bash
# 1. Asegúrate de tener las variables en tu .env local
cat .env

# 2. Ejecuta la aplicación
python app.py

# 3. Abre http://localhost:5000 y prueba el login
```

Si funciona localmente pero no en Render, el problema es la configuración en Render.

### 6. Limpiar Sesión/Cookies

A veces el problema es la sesión corrupta:

1. Abre tu navegador en modo incógnito
2. Intenta hacer login nuevamente
3. Si funciona en incógnito, limpia las cookies del navegador normal

### 7. Verificar que ClickUp esté Funcionando

Ve a https://status.clickup.com/ para verificar que no haya problemas con la API de ClickUp.

## Pasos de Solución Rápida

**Si ayer funcionaba y hoy no:**

1. ✅ Verifica que NO hayas cambiado las variables de entorno en Render sin hacer redeploy
2. ✅ Verifica que NO hayas cambiado la URL de callback en ClickUp
3. ✅ Verifica que NO hayas recreado la aplicación OAuth en ClickUp
4. ✅ Haz un redeploy manual en Render para forzar que use las variables actuales
5. ✅ Prueba en modo incógnito para descartar problemas de sesión/cookies

## Comandos de Diagnóstico

Si tienes acceso al servidor, ejecuta estos comandos para diagnosticar:

```python
# En Python shell dentro del servidor
import os
print("CLIENT_ID:", os.getenv('CLICKUP_CLIENT_ID')[:10] + "...")
print("SECRET:", "Configurado" if os.getenv('CLICKUP_CLIENT_SECRET') else "NO configurado")
```

## Contacto

Si ninguna de estas soluciones funciona, revisa:
1. Los logs completos de la aplicación
2. La configuración exacta en ClickUp Settings
3. Las variables de entorno en Render Dashboard
