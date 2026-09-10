from django.urls import path
from .views import (
    LoginView,
    UsuarioView, UsuarioIdView,
    AgenciaView, AgenciaIdView,
    TipoBusView, TipoBusIdView,
    BusView, BusIdView,
    AsientoView, AsientoIdView,
    DestinoView, DestinoIdView,
    HospedajeView, HospedajeIdView,
    SitioTuristicoView, SitioTuristicoIdView,
    ImagenView, ImagenIdView,
    PaqueteView, PaqueteIdView,
    PaqueteDestinoView, PaqueteDestinoIdView,
    ItinerarioView, ItinerarioIdView,
    ReservaView, ReservaIdView,
    AsientoReservaView, AsientoReservaIdView,
    PagoView, PagoIdView,
)

urlpatterns = [
    # Login
    path('login/', LoginView.as_view(), name='login'),

    # Usuario
    path('usuario/', UsuarioView.as_view(), name='usuario'),
    path('usuario/<int:id>/', UsuarioIdView.as_view(), name='usuario-id'),

    # Agencia
    path('agencia/', AgenciaView.as_view(), name='agencia'),
    path('agencia/<int:id>/', AgenciaIdView.as_view(), name='agencia-id'),

    # TipoBus
    path('tipobus/', TipoBusView.as_view(), name='tipobus'),
    path('tipobus/<int:id>/', TipoBusIdView.as_view(), name='tipobus-id'),

    # Bus
    path('bus/', BusView.as_view(), name='bus'),
    path('bus/<int:id>/', BusIdView.as_view(), name='bus-id'),

    # Asiento
    path('asiento/', AsientoView.as_view(), name='asiento'),
    path('asiento/<int:id>/', AsientoIdView.as_view(), name='asiento-id'),

    # Destino
    path('destino/', DestinoView.as_view(), name='destino'),
    path('destino/<int:id>/', DestinoIdView.as_view(), name='destino-id'),

    # Hospedaje
    path('hospedaje/', HospedajeView.as_view(), name='hospedaje'),
    path('hospedaje/<int:id>/', HospedajeIdView.as_view(), name='hospedaje-id'),

    # SitioTuristico
    path('sitioturistico/', SitioTuristicoView.as_view(), name='sitioturistico'),
    path('sitioturistico/<int:id>/', SitioTuristicoIdView.as_view(), name='sitioturistico-id'),

    # Imagen
    path('imagen/', ImagenView.as_view(), name='imagen'),
    path('imagen/<int:id>/', ImagenIdView.as_view(), name='imagen-id'),

    # Paquete
    path('paquete/', PaqueteView.as_view(), name='paquete'),
    path('paquete/<int:id>/', PaqueteIdView.as_view(), name='paquete-id'),

    # PaqueteDestino
    path('paquetedestino/', PaqueteDestinoView.as_view(), name='paquetedestino'),
    path('paquetedestino/<int:id>/', PaqueteDestinoIdView.as_view(), name='paquetedestino-id'),

    # Itinerario
    path('itinerario/', ItinerarioView.as_view(), name='itinerario'),
    path('itinerario/<int:id>/', ItinerarioIdView.as_view(), name='itinerario-id'),

    # Reserva
    path('reserva/', ReservaView.as_view(), name='reserva'),
    path('reserva/<int:id>/', ReservaIdView.as_view(), name='reserva-id'),

    # AsientoReserva
    path('asientoreserva/', AsientoReservaView.as_view(), name='asientoreserva'),
    path('asientoreserva/<int:id>/', AsientoReservaIdView.as_view(), name='asientoreserva-id'),

    # Pago
    path('pago/', PagoView.as_view(), name='pago'),
    path('pago/<int:id>/', PagoIdView.as_view(), name='pago-id'),
]