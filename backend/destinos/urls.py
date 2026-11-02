from django.urls import path
from .views import (
    DestinoView, DestinoIdView, DestinoNombreView, DestinoDepartamentoView,
    HospedajeView, HospedajeIdView, HospedajeNombreView, HospedajeDestinoView, HospedajeDestinoIdView,
    ImagenView, ImagenIdView, ImagenUrlView, DepartamentoView, BusquedaCatalogoView,
)
urlpatterns = [
    path('buscar/', BusquedaCatalogoView.as_view(), name='buscar-catalogo'),
    # Departamento
    path('departamento/', DepartamentoView.as_view(), name='departamento'),
    # Destino
    path('destino/', DestinoView.as_view(), name='destino'),
    path('destino/<int:id>/', DestinoIdView.as_view(), name='destino-id'),
    path('destino/nombre/<str:nombre>/', DestinoNombreView.as_view(), name='destino-nombre'),
    path('destino/departamento/<str:departamento>/', DestinoDepartamentoView.as_view(), name='destino-departamento'),

    # Hospedaje
    path('hospedaje/', HospedajeView.as_view(), name='hospedaje'),
    path('hospedaje/<int:id>/', HospedajeIdView.as_view(), name='hospedaje-id'),
    path('hospedaje/nombre/<str:nombre>/', HospedajeNombreView.as_view(), name='hospedaje-nombre'),
    path('hospedaje-destino/', HospedajeDestinoView.as_view(), name='hospedaje-destino'),
    path('hospedaje-destino/<int:id>/', HospedajeDestinoIdView.as_view(), name='hospedaje-destino-id'),

    # Imagen
    path('imagen/', ImagenView.as_view(), name='imagen'),
    path('imagen/<int:id>/', ImagenIdView.as_view(), name='imagen-id'),
    path('imagen/url/<path:url_img>/', ImagenUrlView.as_view(), name='imagen-url'),
]