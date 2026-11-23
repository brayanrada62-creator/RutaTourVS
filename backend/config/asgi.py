"""
ASGI config for config project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

django_asgi_app = get_asgi_application()

# WebSocket de notificaciones del panel (ws/alertas/). Solo si `channels` está instalado y el servidor es ASGI
# (uvicorn/daphne); con gunicorn + wsgi (como hoy) este archivo no se usa y todo sigue igual.
try:
    from channels.routing import ProtocolTypeRouter, URLRouter
    from notificaciones.routing import websocket_urlpatterns

    application = ProtocolTypeRouter({
        'http': django_asgi_app,
        'websocket': URLRouter(websocket_urlpatterns),
    })
except ImportError:
    application = django_asgi_app
