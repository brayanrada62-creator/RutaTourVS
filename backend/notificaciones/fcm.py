"""Envío del push con Firebase Cloud Messaging (solo el aviso; el historial vive en la base de datos).

Usa la misma cuenta de servicio que el chat: FIREBASE_CREDENTIALS (JSON) o, si existe,
FIREBASE_CREDENTIALS_FILE (ruta a ese JSON).
"""
import json
import logging
import os

logger = logging.getLogger(__name__)
_app = None


def _iniciar():
    global _app
    if _app is not None:
        return _app
    import firebase_admin
    from firebase_admin import credentials
    try:
        _app = firebase_admin.get_app("rutatour-avisos")
        return _app
    except ValueError:
        pass
    ruta = os.environ.get("FIREBASE_CREDENTIALS_FILE", "")
    crudo = os.environ.get("FIREBASE_CREDENTIALS", "")
    if not ruta and not crudo:
        return None
    try:
        certificado = credentials.Certificate(ruta) if ruta else credentials.Certificate(json.loads(crudo))
        _app = firebase_admin.initialize_app(certificado, name="rutatour-avisos")
    except Exception:
        logger.exception("FCM no pudo leer las credenciales")
        return None
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
