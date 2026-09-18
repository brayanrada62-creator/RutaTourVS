from django.urls import path
from .views import (
    LoginView,
    UsuarioPerfilView,
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
    PagoView, PagoIdView, UsuarioDocumentoView,
    AgenciaNitView, AgenciaDireccionView, BusPlacaView, 
    AsientoNumeroView, DestinoDepartamentoView,
    DestinoNombreView, HospedajeNombreView,
    SitioTuristicoNombreView, ImagenUrlView,
    PaqueteDescripcionView, PaqueteNombreView,
    ItinerarioTituloView, ItinerarioLugarView,
    ReservaFechaView, ReservaUsuarioView, 
    PagoPrecioView, PagoReferenciaView
)

urlpatterns = [
    # Login
    path('login/', LoginView.as_view(), name='login'),

    # Usuario
    path('usuario/', UsuarioView.as_view(), name='usuario'),
    path('usuario/<int:id>/', UsuarioIdView.as_view(), name='usuario-id'),
    path('usuarios/documento/<str:numero_documento>/', UsuarioDocumentoView.as_view(), name='usuario-documento'),
    

    # Agencia
    path('agencia/', AgenciaView.as_view(), name='agencia'),
    path('agencia/<int:id>/', AgenciaIdView.as_view(), name='agencia-id'),
    path('agencia/nit/<str:nit>/', AgenciaNitView.as_view(), name='agencia-nit'),
    path('agencia/direccion/<str:direccion>/', AgenciaDireccionView.as_view(), name='agencia-direccion'),
    
    # TipoBus
    path('tipobus/', TipoBusView.as_view(), name='tipobus'),
    path('tipobus/<int:id>/', TipoBusIdView.as_view(), name='tipobus-id'),

    # Bus
    path('bus/', BusView.as_view(), name='bus'),
    path('bus/<int:id>/', BusIdView.as_view(), name='bus-id'),
    path('bus/placa/<str:placa>/', BusPlacaView.as_view(), name='bus-placa'),

    # Asiento
    path('asiento/', AsientoView.as_view(), name='asiento'),
    path('asiento/<int:id>/', AsientoIdView.as_view(), name='asiento-id'),
    path('asiento/numero/<int:numero_asiento>/', AsientoNumeroView.as_view(), name='asiento-numero'),

    # Destino
    path('destino/', DestinoView.as_view(), name='destino'),
    path('destino/<int:id>/', DestinoIdView.as_view(), name='destino-id'),
    path('destino/nombre/<str:nombre>/', DestinoNombreView.as_view(), name='destino-nombre'),
    path('destino/departamento/<str:departamento>/', DestinoDepartamentoView.as_view(), name='destino-departamento'),


    # Hospedaje
    path('hospedaje/', HospedajeView.as_view(), name='hospedaje'),
    path('hospedaje/<int:id>/', HospedajeIdView.as_view(), name='hospedaje-id'),
    path('hospedaje/nombre/<str:nombre>/', HospedajeNombreView.as_view(), name='hospedaje-nombre'),

    # SitioTuristico
    path('sitioturistico/', SitioTuristicoView.as_view(), name='sitioturistico'),
    path('sitioturistico/<int:id>/', SitioTuristicoIdView.as_view(), name='sitioturistico-id'),
    path('sitio-turistico/nombre/<str:nombre>/', SitioTuristicoNombreView.as_view(), name='sitio-turistico-nombre'),

    # Imagen
    path('imagen/', ImagenView.as_view(), name='imagen'),
    path('imagen/<int:id>/', ImagenIdView.as_view(), name='imagen-id'),
    path('imagen/url/<path:url_img>/', ImagenUrlView.as_view(), name='imagen-url'),

    # Paquete
    path('paquete/', PaqueteView.as_view(), name='paquete'),
    path('paquete/<int:id>/', PaqueteIdView.as_view(), name='paquete-id'),
    path('paquete/nombre/<str:nombre>/', PaqueteNombreView.as_view(), name='paquete-nombre'),
    path('paquete/descripcion/<str:descripcion>/', PaqueteDescripcionView.as_view(), name='paquete-descripcion'),

    # PaqueteDestino
    path('paquetedestino/', PaqueteDestinoView.as_view(), name='paquetedestino'),
    path('paquetedestino/<int:id>/', PaqueteDestinoIdView.as_view(), name='paquetedestino-id'),

    # Itinerario
    path('itinerario/', ItinerarioView.as_view(), name='itinerario'),
    path('itinerario/<int:id>/', ItinerarioIdView.as_view(), name='itinerario-id'),
    path('itinerario/titulo/<str:titulo>/', ItinerarioTituloView.as_view(), name='itinerario-titulo'),
    path('itinerario/lugar/<str:lugar>/', ItinerarioLugarView.as_view(), name='itinerario-lugar'),

    # Reserva
    path('reserva/', ReservaView.as_view(), name='reserva'),
    path('reserva/<int:id>/', ReservaIdView.as_view(), name='reserva-id'),
    path('reserva/fecha/<str:fecha_reserva>/', ReservaFechaView.as_view(), name='reserva-fecha'),
    path('reserva/usuario/<int:usuario_id>/', ReservaUsuarioView.as_view(), name='reserva-usuario'),

    
    # AsientoReserva
    path('asientoreserva/', AsientoReservaView.as_view(), name='asientoreserva'),
    path('asientoreserva/<int:id>/', AsientoReservaIdView.as_view(), name='asientoreserva-id'),

    # Pago
    path('pago/', PagoView.as_view(), name='pago'),
    path('pago/<int:id>/', PagoIdView.as_view(), name='pago-id'),
    path('pago/precio/<str:precio>/', PagoPrecioView.as_view(), name='pago-precio'),
    path('pago/referencia/<str:referencia>/', PagoReferenciaView.as_view(), name='pago-referencia'),
    path('usuario/perfil/', UsuarioPerfilView.as_view(), name='usuario-perfil'),
]