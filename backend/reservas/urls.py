from django.urls import path
from .views import (
    ReservaView, ReservaIdView, ReservaFechaView, ReservaUsuarioView,
    AsientoReservaView, AsientoReservaIdView,
    ViajePasajerosView, ViajeAbordarView, GpsView, NovedadView, ChatView, ParadaViajeView,
)

urlpatterns = [
    path('reserva/', ReservaView.as_view(), name='reserva'),
    path('reserva/<int:id>/', ReservaIdView.as_view(), name='reserva-id'),
    path('reserva/fecha/<str:fecha_reserva>/', ReservaFechaView.as_view(), name='reserva-fecha'),
    path('reserva/usuario/<int:usuario_id>/', ReservaUsuarioView.as_view(), name='reserva-usuario'),
    path('asientoreserva/', AsientoReservaView.as_view(), name='asientoreserva'),
    path('asientoreserva/<int:id>/', AsientoReservaIdView.as_view(), name='asientoreserva-id'),
    path('viaje/<int:id>/pasajeros/', ViajePasajerosView.as_view(), name='viaje-pasajeros'),
    path('viaje/<int:id>/abordar/', ViajeAbordarView.as_view(), name='viaje-abordar'),
    path('viaje/<int:id>/parada/', ParadaViajeView.as_view(), name='viaje-parada'),
    path('gps/', GpsView.as_view(), name='gps'),
    path('gps/<int:viaje_id>/', GpsView.as_view(), name='gps-viaje'),
    path('novedad/', NovedadView.as_view(), name='novedad'),
    path('chat/', ChatView.as_view(), name='chat'),
]
