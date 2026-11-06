"""Envío de correo con la API HTTP de Resend.

El plan gratuito de Render bloquea los puertos SMTP, así que el correo sale por HTTPS.
Para activarlo en Render: EMAIL_BACKEND=usuarios.correo.ResendBackend, RESEND_API_KEY y DEFAULT_FROM_EMAIL.
"""
import json
import urllib.request

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

RESEND_URL = "https://api.resend.com/emails"


class ResendBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        enviados = 0
        for mensaje in email_messages:
            try:
                self.enviar(mensaje)
                enviados += 1
            except Exception:
                if not self.fail_silently:
                    raise
        return enviados

    def enviar(self, mensaje):
        datos = {
            "from": mensaje.from_email,
            "to": mensaje.recipients(),
            "subject": mensaje.subject,
            "text": mensaje.body,
        }
        peticion = urllib.request.Request(
            RESEND_URL,
            data=json.dumps(datos).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                "Content-Type": "application/json",
                "User-Agent": "RutaTour/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(peticion, timeout=10):
            pass
