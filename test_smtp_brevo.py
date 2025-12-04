#!/usr/bin/env python3
"""
Script de diagnóstico para probar conexión SMTP con Brevo
y envío de emails de alerta
"""

import os
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

print("=" * 80)
print("DIAGNÓSTICO DE CONFIGURACIÓN SMTP - BREVO")
print("=" * 80)

# Cargar variables de entorno
from dotenv import load_dotenv
load_dotenv()

print("\n[PASO 1] Verificando variables de entorno...")
print("-" * 80)

SMTP_SERVER = os.getenv('SMTP_SERVER', '')
SMTP_PORT = os.getenv('SMTP_PORT', '')
SMTP_EMAIL = os.getenv('SMTP_EMAIL', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')

# Mostrar configuración (ocultando password)
configs = {
    'SMTP_SERVER': SMTP_SERVER,
    'SMTP_PORT': SMTP_PORT,
    'SMTP_EMAIL': SMTP_EMAIL,
    'SMTP_PASSWORD': '***' if SMTP_PASSWORD else ''
}

all_configured = True
for key, value in configs.items():
    if value:
        if key == 'SMTP_PASSWORD':
            print(f"✅ {key}: {'*' * min(len(SMTP_PASSWORD), 20)}")
        else:
            print(f"✅ {key}: {value}")
    else:
        print(f"❌ {key}: NO CONFIGURADO")
        all_configured = False

if not all_configured:
    print("\n❌ ERROR: No todas las variables SMTP están configuradas")
    print("\nPara configurar, crea un archivo .env con:")
    print("""
SMTP_SERVER=smtp-relay.brevo.com
SMTP_PORT=587
SMTP_EMAIL=tu_email@dominio.com
SMTP_PASSWORD=tu_password_de_brevo
""")
    print("\nO configúralas en las variables de entorno de Render")
    sys.exit(1)

print("\n✅ Todas las variables SMTP están configuradas")

# Test 2: Verificar configuración específica de Brevo
print("\n[PASO 2] Verificando configuración específica de Brevo...")
print("-" * 80)

if SMTP_SERVER == 'smtp-relay.brevo.com':
    print("✅ Servidor SMTP correcto: smtp-relay.brevo.com")
else:
    print(f"⚠️  Servidor SMTP: {SMTP_SERVER} (esperado: smtp-relay.brevo.com)")

if SMTP_PORT == '587':
    print("✅ Puerto SMTP correcto: 587 (STARTTLS)")
    port_int = 587
elif SMTP_PORT == '465':
    print("⚠️  Puerto SMTP: 465 (SSL) - Brevo recomienda 587")
    port_int = 465
else:
    print(f"❌ Puerto SMTP incorrecto: {SMTP_PORT} (debe ser 587)")
    sys.exit(1)

# Test 3: Probar conexión al servidor SMTP
print("\n[PASO 3] Probando conexión al servidor SMTP...")
print("-" * 80)

try:
    print(f"Conectando a {SMTP_SERVER}:{port_int}...")
    server = smtplib.SMTP(SMTP_SERVER, port_int, timeout=10)
    print("✅ Conexión establecida")

    print("Iniciando STARTTLS...")
    server.starttls()
    print("✅ STARTTLS iniciado correctamente")

    print("Intentando login...")
    server.login(SMTP_EMAIL, SMTP_PASSWORD)
    print("✅ Login exitoso")

    server.quit()
    print("✅ Conexión cerrada correctamente")

    print("\n🎉 CONEXIÓN SMTP EXITOSA")

except smtplib.SMTPAuthenticationError as e:
    print(f"\n❌ ERROR DE AUTENTICACIÓN:")
    print(f"   {str(e)}")
    print("\nPosibles causas:")
    print("   1. Email o password incorrectos")
    print("   2. La API key de Brevo no es válida")
    print("   3. La cuenta de Brevo no está activada")
    print("\nVerifica en: https://app.brevo.com/settings/keys/smtp")
    sys.exit(1)

except smtplib.SMTPConnectError as e:
    print(f"\n❌ ERROR DE CONEXIÓN:")
    print(f"   {str(e)}")
    print("\nPosibles causas:")
    print("   1. Servidor SMTP incorrecto")
    print("   2. Puerto bloqueado por firewall")
    print("   3. Problemas de red")
    sys.exit(1)

except Exception as e:
    print(f"\n❌ ERROR INESPERADO:")
    print(f"   {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Enviar email de prueba
print("\n[PASO 4] ¿Deseas enviar un email de prueba?")
print("-" * 80)

email_destino = input("Ingresa el email de destino (o presiona Enter para saltar): ").strip()

if email_destino:
    print(f"\nEnviando email de prueba a {email_destino}...")

    try:
        # Crear mensaje
        msg = MIMEMultipart('alternative')
        msg['Subject'] = '🧪 TEST - Sistema de Alertas Virtual Controller SIDN'
        msg['From'] = SMTP_EMAIL
        msg['To'] = email_destino

        # Cuerpo HTML
        html = f"""
        <html>
          <head>
            <style>
              body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
              .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
              .header {{ background-color: #4CAF50; color: white; padding: 20px; border-radius: 5px; margin-bottom: 20px; }}
              .content {{ background-color: #f9f9f9; padding: 20px; border-radius: 5px; }}
              .success {{ color: #4CAF50; font-size: 48px; }}
            </style>
          </head>
          <body>
            <div class="container">
              <div class="header">
                <div class="success">✅</div>
                <h2 style="margin: 0;">Test de Email Exitoso</h2>
              </div>
              <div class="content">
                <p><strong>¡Configuración SMTP funcionando correctamente!</strong></p>
                <p>Este es un email de prueba del sistema de alertas de Virtual Controller SIDN.</p>
                <p><strong>Detalles de la prueba:</strong></p>
                <ul>
                  <li>Servidor SMTP: {SMTP_SERVER}</li>
                  <li>Puerto: {SMTP_PORT}</li>
                  <li>Email remitente: {SMTP_EMAIL}</li>
                  <li>Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</li>
                </ul>
                <p>Si recibes este email, significa que el sistema de alertas está listo para enviar notificaciones.</p>
              </div>
            </div>
          </body>
        </html>
        """

        # Cuerpo texto plano
        text = f"""
TEST DE EMAIL - Sistema de Alertas Virtual Controller SIDN

¡Configuración SMTP funcionando correctamente!

Este es un email de prueba del sistema de alertas de Virtual Controller SIDN.

Detalles de la prueba:
- Servidor SMTP: {SMTP_SERVER}
- Puerto: {SMTP_PORT}
- Email remitente: {SMTP_EMAIL}
- Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Si recibes este email, significa que el sistema de alertas está listo para enviar notificaciones.
        """

        part1 = MIMEText(text, 'plain')
        part2 = MIMEText(html, 'html')

        msg.attach(part1)
        msg.attach(part2)

        # Enviar email
        with smtplib.SMTP(SMTP_SERVER, port_int, timeout=10) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)

        print(f"✅ Email enviado exitosamente a {email_destino}")
        print("\nRevisa tu bandeja de entrada (y spam) para confirmar la recepción.")

    except Exception as e:
        print(f"❌ Error al enviar email: {str(e)}")
        import traceback
        traceback.print_exc()
else:
    print("\nTest de envío omitido.")

# Test 5: Simular envío de alerta real
print("\n[PASO 5] Simulando formato de email de alerta real...")
print("-" * 80)

print("\n📧 FORMATO DEL EMAIL DE ALERTA QUE SE ENVIARÁ:")
print("-" * 80)

ejemplo_asunto = '⚠️ Alerta: Demora en tarea "Implementar Dashboard" - Proyecto SIDN'
ejemplo_proyecto = "Proyecto SIDN"
ejemplo_tarea = "Implementar Dashboard"
ejemplo_tiempo = "3 horas y 15 minutos"
ejemplo_url = "https://app.clickup.com/t/abc123"

print(f"\nAsunto: {ejemplo_asunto}")
print(f"De: {SMTP_EMAIL}")
print(f"Para: [email configurado en la alerta]")
print(f"\nContenido:")
print(f"  Proyecto: {ejemplo_proyecto}")
print(f"  Tarea: {ejemplo_tarea}")
print(f"  Tiempo en progreso: {ejemplo_tiempo}")
print(f"  URL: {ejemplo_url}")

print("\n" + "=" * 80)
print("RESUMEN DEL DIAGNÓSTICO")
print("=" * 80)
print("✅ Variables de entorno configuradas")
print("✅ Conexión SMTP exitosa")
print("✅ Autenticación correcta")
if email_destino:
    print("✅ Email de prueba enviado")
print("\n🎯 El sistema está listo para enviar alertas por email")
print("=" * 80)
