from django.urls import path
from .views import (
    TipoBusView, TipoBusIdView,
    BusView, BusIdView, BusPlacaView,
    AsientoView, AsientoIdView, AsientoNumeroView, BusConductorView
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
    path('bus-conductor/<int:id>/', BusConductorView.as_view(), name='bus-conductor-id'),

    # Asiento
    path('asiento/', AsientoView.as_view(), name='asiento'),
    path('asiento/<int:id>/', AsientoIdView.as_view(), name='asiento-id'),
    path('asiento/numero/<int:numero_asiento>/', AsientoNumeroView.as_view(), name='asiento-numero'),
]