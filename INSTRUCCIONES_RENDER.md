# 🚨 INSTRUCCIONES PASO A PASO - SEGUIR EXACTAMENTE 🚨

## El Problema

Render está ejecutando `bash start.sh` porque NO has cambiado el Start Command en el dashboard. El archivo `render.yaml` NO se aplica automáticamente a servicios existentes.

---

## ✅ SOLUCIÓN - Sigue estos pasos EXACTAMENTE:

### PASO 1: Abrir Render Dashboard

1. Abre tu navegador
2. Ve a: https://dashboard.render.com
3. Haz clic en tu servicio **"virtualcontroller"**

### PASO 2: Ir a Settings

1. En el menú lateral IZQUIERDO, haz clic en **"Settings"**
2. Scroll hacia abajo hasta encontrar la sección **"Build & Deploy"**

### PASO 3: Cambiar Start Command

1. Busca el campo **"Start Command"**
2. Verás algo como: `bash start.sh` o similar
3. **BORRA TODO** lo que esté ahí
4. **COPIA Y PEGA** exactamente esto (sin modificar):

```
gunicorn --bind 0.0.0.0:$PORT --workers 1 --access-logfile - --error-logfile - app_minimal:app
```

5. **NO presiones Enter**, haz clic en el botón **"Save Changes"** que aparece abajo del campo

### PASO 4: Configurar Health Check

1. En la MISMA página de Settings
2. Scroll más abajo hasta **"Health & Alerts"**
3. En el campo **"Health Check Path"** pon: `/health`
4. Haz clic en **"Save Changes"**

### PASO 5: Manual Deploy

1. En la parte SUPERIOR DERECHA, busca el botón **"Manual Deploy"**
2. Haz clic en **"Manual Deploy"**
3. Selecciona **"Clear build cache & deploy"**
4. Haz clic en **"Deploy"**

### PASO 6: Ver los Logs

1. Mientras se despliega, haz clic en **"Logs"** en el menú lateral
2. Deberías ver INMEDIATAMENTE:
   ```
   ==> Building...
   ==> Downloading build...
   ==> Starting service...
   [MINIMAL] Python: 3.11.14
   [MINIMAL] Iniciando app mínima...
   Booting worker with pid: XXXXX
   ```

---

## 🔍 ¿Qué me dices si...?

### "No veo el botón Manual Deploy"
- Está en la esquina superior derecha, junto a "Settings"
- Si no lo ves, ve a la pestaña "Events" y haz clic en "Deploy"

### "No encuentro Health Check Path"
- Está en Settings, sección "Health & Alerts"
- Si no existe, déjalo en blanco por ahora

### "El Start Command no se guarda"
- Asegúrate de hacer clic en "Save Changes" DESPUÉS de pegar el comando
- Espera a que aparezca un mensaje de confirmación verde

### "Sigue diciendo 'bash start.sh' en los logs"
- Significa que NO guardaste el Start Command correctamente
- Vuelve a Settings y verifica que el campo muestre el nuevo comando
- Si muestra el viejo, repite el PASO 3

---

## 📸 CAPTURAS DE PANTALLA NECESARIAS

Si después de seguir TODOS estos pasos sigue fallando, necesito que me compartas capturas de:

1. **Settings → Build & Deploy** - Donde se ve el Start Command que configuraste
2. **Logs completos** - Desde "==> Building" hasta "==> Timed Out"
3. **El mensaje de error exacto** - Todo lo que sale después de "==> Running"

---

## ⚠️ CRÍTICO: Por qué no funciona render.yaml

`render.yaml` solo se aplica si:
- Creaste el servicio usando "Blueprint" desde GitHub
- O si vas a Settings → "Deploy" y conectas el blueprint manualmente

Como tu servicio ya existía, Render está ignorando `render.yaml` y usando la configuración que guardaste manualmente en el dashboard.

**Por eso DEBES cambiar el Start Command en el dashboard manualmente.**
