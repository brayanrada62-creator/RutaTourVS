"""Envío de correo por la API HTTP de Mailjet.

El plan gratuito de Render bloquea los puertos SMTP, así que el correo sale por HTTPS.
En Render: EMAIL_BACKEND=usuarios.correo.MailjetBackend, MAILJET_API_KEY, MAILJET_SECRET_KEY y
DEFAULT_FROM_EMAIL (las credenciales van solo en variables de entorno).
"""
import base64
import json
import urllib.request
from email.utils import parseaddr

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

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
