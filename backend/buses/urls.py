from django.urls import path
from .views import (
    TipoBusView, TipoBusIdView,
    BusView, BusIdView, BusPlacaView,
    AsientoView, AsientoIdView, AsientoNumeroView, BusConductorView, BusConductorIdView,
    ViajeView, ViajeIdView, ViajeIniciarView, ViajeFinalizarView, ViajeParadasView, ViajeParadaCumplirView,
)

urlpatterns = [
    # TipoBus
    path('tipobus/', TipoBusView.as_view(), name='tipobus'),
    path('tipobus/<int:id>/', TipoBusIdView.as_view(), name='tipobus-id'),

    # Bus
    path('bus/', BusView.as_view(), name='bus'),
    path('bus/<int:id>/', BusIdView.as_view(), name='bus-id'),
    path('bus/placa/<str:placa>/', BusPlacaView.as_view(), name='bus-placa'),
    
    # Bus-Conductor
    path('bus-conductor/', BusConductorView.as_view(), name='bus-conductor'),
    path('bus-conductor/<int:id>/', BusConductorIdView.as_view(), name='bus-conductor-id'),

    # Viajes (salidas por bus)
    path('viaje/', ViajeView.as_view(), name='viaje'),
    path('viaje/<int:id>/', ViajeIdView.as_view(), name='viaje-id'),
    path('viaje/<int:id>/iniciar/', ViajeIniciarView.as_view(), name='viaje-iniciar'),
    path('viaje/<int:id>/finalizar/', ViajeFinalizarView.as_view(), name='viaje-finalizar'),
    path('viaje/<int:id>/paradas/', ViajeParadasView.as_view(), name='viaje-paradas'),
    path('viaje/<int:id>/paradas/<int:itinerario_id>/cumplir/', ViajeParadaCumplirView.as_view(), name='viaje-parada-cumplir'),

    # Asiento
    path('asiento/', AsientoView.as_view(), name='asiento'),
    path('asiento/<int:id>/', AsientoIdView.as_view(), name='asiento-id'),
    path('asiento/numero/<int:numero_asiento>/', AsientoNumeroView.as_view(), name='asiento-numero'),
]