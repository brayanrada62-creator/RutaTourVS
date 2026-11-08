"""Notificaciones push con Firebase Cloud Messaging (D1).

Sin FIREBASE_CREDENTIALS no se envía nada (por ejemplo en desarrollo y en las pruebas): se registra en el log.
El envío corre en un hilo aparte para no demorar la respuesta de la API.
"""
import json
import logging
import threading

from django.conf import settings

from .models import Dispositivo

logger = logging.getLogger(__name__)
_app = None
_candado = threading.Lock()


def _firebase():
    """La app de Firebase (se crea una vez). None si no hay credenciales o no son válidas."""
    global _app
    credenciales = getattr(settings, "FIREBASE_CREDENTIALS", "")
    if not credenciales:
        return None
    with _candado:
        if _app is None:
            try:
                import firebase_admin
                from firebase_admin import credentials
                _app = firebase_admin.initialize_app(credentials.Certificate(json.loads(credenciales)), name="rutatour")
            except Exception:
                logger.exception("FIREBASE_CREDENTIALS no es válido: no se enviarán notificaciones")
                return None
    return _app


def enviar_push(usuario_ids, titulo, cuerpo, datos=None):
    """Envía la notificación a todos los teléfonos de esos usuarios. Devuelve cuántos tokens se usaron."""
    tokens = list(Dispositivo.objects.filter(usuario_id__in=set(usuario_ids)).values_list("token", flat=True))
    if not tokens:
        return 0
    app = _firebase()
    if app is None:
        logger.info("Push sin enviar (falta FIREBASE_CREDENTIALS): %s a %s teléfonos", titulo, len(tokens))
        return 0
    from firebase_admin import messaging
    # Solo datos (sin 'notification'): así la app siempre lo recibe, también en segundo plano, y ella misma
    # muestra el aviso en su canal "Chat" y lo guarda en su panel de notificaciones.
    mensaje = messaging.MulticastMessage(
        tokens=tokens,
        data={"titulo": titulo, "cuerpo": cuerpo, **{k: str(v) for k, v in (datos or {}).items()}},
        android=messaging.AndroidConfig(priority="high"),
    )
    try:
        respuesta = messaging.send_each_for_multicast(mensaje, app=app)
    except Exception:
        logger.exception("No se pudo enviar la notificación push")
        return 0
    # Tokens de apps desinstaladas o sesiones cerradas: se borran para no reintentar con ellos.
    vencidos = [tokens[i] for i, r in enumerate(respuesta.responses)
                if not r.success and r.exception is not None
                and type(r.exception).__name__ in ("UnregisteredError", "SenderIdMismatchError", "InvalidArgumentError")]
    if vencidos:
        Dispositivo.objects.filter(token__in=vencidos).delete()
    return len(tokens)


def enviar_push_en_segundo_plano(usuario_ids, titulo, cuerpo, datos=None):
    ids = list(usuario_ids)
    if not ids:
        return
    threading.Thread(target=enviar_push, args=(ids, titulo, cuerpo, datos), daemon=True).start()
