"""Envío de correo por API HTTP (Resend o Mailjet).

El plan gratuito de Render bloquea los puertos SMTP, así que el correo sale por HTTPS.
Para activarlo en Render, define DEFAULT_FROM_EMAIL y una de estas opciones:
- Resend: EMAIL_BACKEND=usuarios.correo.ResendBackend y RESEND_API_KEY.
- Mailjet: EMAIL_BACKEND=usuarios.correo.MailjetBackend, MAILJET_API_KEY y MAILJET_SECRET_KEY.
"""
import base64
import json
import urllib.request
from email.utils import parseaddr

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

RESEND_URL = "https://api.resend.com/emails"
MAILJET_URL = "https://api.mailjet.com/v3.1/send"


class CorreoHttpBackend(BaseEmailBackend):
    """Recorre los mensajes; cada proveedor define cómo enviar uno con enviar()."""

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


class ResendBackend(CorreoHttpBackend):
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


class MailjetBackend(CorreoHttpBackend):
    def enviar(self, mensaje):
        nombre, correo = parseaddr(mensaje.from_email)
        remitente = {"Email": correo}
        if nombre:
            remitente["Name"] = nombre
        datos = {"Messages": [{
            "From": remitente,
            "To": [{"Email": destino} for destino in mensaje.recipients()],
            "Subject": mensaje.subject,
            "TextPart": mensaje.body,
        }]}
        credenciales = f"{settings.MAILJET_API_KEY}:{settings.MAILJET_SECRET_KEY}".encode("utf-8")
        peticion = urllib.request.Request(
            MAILJET_URL,
            data=json.dumps(datos).encode("utf-8"),
            headers={
                "Authorization": "Basic " + base64.b64encode(credenciales).decode("ascii"),
                "Content-Type": "application/json",
                "User-Agent": "RutaTour/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(peticion, timeout=10) as respuesta:
            resultado = json.loads(respuesta.read())
        # Mailjet puede responder 200 y rechazar el mensaje: se revisa el estado de cada uno.
        estados = [m.get("Status") for m in resultado.get("Messages", [])]
        if not estados or any(estado != "success" for estado in estados):
            raise RuntimeError(f"Mailjet no aceptó el mensaje: {estados}")
