"""WebSocket del panel web: ws://<host>/ws/alertas/?token=<access JWT>.

Solo los administradores (rol 2) se conectan, y cada uno se une únicamente a su propio grupo
`notif_usuario_<id>`; así nadie recibe avisos de otra agencia (el alcance lo decide `notificar`, no el panel).
Requiere `channels` (ver config/asgi.py); sin él este módulo no se importa y la API REST sigue igual.
"""
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .ws import grupo_de

CODIGO_SIN_SESION = 4401
CODIGO_SIN_PERMISO = 4403


def admin_del_token(token):
    """Usuario administrador activo dueño de un access JWT válido, o None."""
    from django.contrib.auth.models import User
    from rest_framework_simplejwt.exceptions import TokenError
    from rest_framework_simplejwt.tokens import AccessToken

    from usuarios.models import Usuario
    from usuarios.permisos import ROL_ADMIN

    try:
        datos = AccessToken(token)
        auth_user = User.objects.filter(id=datos["user_id"]).first()
    except (TokenError, KeyError, TypeError, ValueError):
        return None
    if auth_user is None:
        return None
    correo = auth_user.email or auth_user.username
    usuario = Usuario.objects.filter(correo__iexact=correo, activo=True).first()
    return usuario if usuario is not None and usuario.rol_id == ROL_ADMIN else None


class AlertasConsumer(AsyncJsonWebsocketConsumer):
    grupo = None

    async def connect(self):
        token = (parse_qs(self.scope.get("query_string", b"").decode()).get("token") or [""])[0]
        if not token:
            await self.close(code=CODIGO_SIN_SESION)
            return
        usuario = await database_sync_to_async(admin_del_token)(token)
        if usuario is None:
            await self.close(code=CODIGO_SIN_PERMISO)
            return
        self.grupo = grupo_de(usuario.id)
        await self.channel_layer.group_add(self.grupo, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if self.grupo:
            await self.channel_layer.group_discard(self.grupo, self.channel_name)

    async def alerta(self, evento):
        """Mensaje de ws.emitir(): se reenvía tal cual (titulo, mensaje, fecha + campos de la notificación)."""
        await self.send_json(evento["carga"])
