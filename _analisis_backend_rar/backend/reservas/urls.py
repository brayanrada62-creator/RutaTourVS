from django.urls import path
from .views import (
    ReservaView, ReservaIdView, ReservaFechaView, ReservaUsuarioView,
    AsientoReservaView, AsientoReservaIdView,
)

urlpatterns = [
    # Reserva
    path('reserva/', ReservaView.as_view(), name='reserva'),
    path('reserva/<int:id>/', ReservaIdView.as_view(), name='reserva-id'),
    path('reserva/fecha/<str:fecha_reserva>/', ReservaFechaView.as_view(), name='reserva-fecha'),
    path('reserva/usuario/<int:usuario_id>/', ReservaUsuarioView.as_view(), name='reserva-usuario'),

    # AsientoReserva
    path('asientoreserva/', AsientoReservaView.as_view(), name='asientoreserva'),
    path('asientoreserva/<int:id>/', AsientoReservaIdView.as_view(), name='asientoreserva-id'),
]