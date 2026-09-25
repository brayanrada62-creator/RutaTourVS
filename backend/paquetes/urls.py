from django.urls import path
from .views import (
    PaqueteView, PaqueteIdView, PaqueteNombreView, PaqueteDescripcionView,
    PaqueteDestinoView, PaqueteDestinoIdView,
    ItinerarioView, ItinerarioIdView, ItinerarioTituloView, ItinerarioLugarView,
)

urlpatterns = [
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
]