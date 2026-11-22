from django.urls import path

from .views import (
    DispositivoView, NotificacionIdView, NotificacionLeidaView, NotificacionNoLeidasView, NotificacionView,
    PreferenciaView,
)

urlpatterns = [
    path('notificaciones/', NotificacionView.as_view(), name='notificaciones'),
    # Rutas fijas antes que <int:id> para que no se confundan.
    path('notificaciones/no-leidas/count/', NotificacionNoLeidasView.as_view(), name='notificaciones-no-leidas'),
    path('notificaciones/preferencias/', PreferenciaView.as_view(), name='notificaciones-preferencias'),
    path('notificaciones/<int:id>/', NotificacionIdView.as_view(), name='notificacion-id'),
    path('notificaciones/<int:id>/leida/', NotificacionLeidaView.as_view(), name='notificacion-leida'),
    # La app Android ya usa dispositivo/; dispositivos/fcm/ es el mismo recurso con el nombre del contrato.
    path('dispositivo/', DispositivoView.as_view(), name='dispositivo'),
    path('dispositivos/fcm/', DispositivoView.as_view(), name='dispositivo-fcm'),
]
