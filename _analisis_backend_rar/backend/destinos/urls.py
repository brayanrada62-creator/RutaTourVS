from django.urls import path
from .views import (
    DestinoView, DestinoIdView, DestinoNombreView, DestinoDepartamentoView,
    HospedajeView, HospedajeIdView, HospedajeNombreView,
    SitioTuristicoView, SitioTuristicoIdView, SitioTuristicoNombreView,
    ImagenView, ImagenIdView, ImagenUrlView,
)

urlpatterns = [
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
]