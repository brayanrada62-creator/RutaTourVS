from django.urls import path

from .consumers import AlertasConsumer

websocket_urlpatterns = [
    path("ws/alertas/", AlertasConsumer.as_asgi()),
]
