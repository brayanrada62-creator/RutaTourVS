"""Emisión por WebSocket al panel web (administradores).

Requiere django-channels con una capa de canales; si no está instalada no hace nada (el panel igual
carga el historial con GET /api/notificaciones/). Grupo por usuario: `notif_usuario_<id>`; el consumidor
(autenticado con el JWT) solo une a cada administrador a su propio grupo, así nadie recibe lo de otra agencia.
"""
import logging

logger = logging.getLogger(__name__)


def grupo_de(usuario_id):
    return f"notif_usuario_{usuario_id}"


def emitir(usuario_id, carga):
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
    except ImportError:
        return
    try:
        capa = get_channel_layer()
        if capa is not None:
            async_to_sync(capa.group_send)(grupo_de(usuario_id), {"type": "alerta", "carga": carga})
    except Exception:  # noqa: BLE001
        logger.exception("No se pudo emitir por WebSocket")
