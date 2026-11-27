"""Envío del push con Firebase Cloud Messaging (solo el aviso; el historial vive en la base de datos).
"""
import logging
import os

logger = logging.getLogger(__name__)
_app = None


def _iniciar():
    global _app
    if _app is not None:
        return _app
    ruta = os.environ.get("FIREBASE_CREDENTIALS_FILE", "")
    if not ruta:
        return None
    import firebase_admin
    from firebase_admin import credentials
    _app = firebase_admin.initialize_app(credentials.Certificate(ruta))
    return _app


def enviar_push(tokens, titulo, mensaje, datos):
    
    if not tokens:
        return []
    try:
        app = _iniciar()
        if app is None:
            return []
        from firebase_admin import messaging
        # Solo "data" (todo texto): así MensajesPush.onMessageReceived corre también con la app cerrada.
        carga = {k: str(v) for k, v in datos.items()}
        carga.update({"titulo": titulo, "cuerpo": mensaje})
        invalidos = []
        for token in tokens:
            try:
                messaging.send(
                    messaging.Message(token=token, data=carga, android=messaging.AndroidConfig(priority="high")),
                    app=app,
                )
            except (messaging.UnregisteredError, messaging.SenderIdMismatchError):
                invalidos.append(token)
            except Exception:  # noqa: BLE001 - red, cuota, etc.
                logger.exception("No se pudo enviar el push FCM")
        return invalidos
    except Exception:  # noqa: BLE001
        logger.exception("FCM no está disponible")
        return []
