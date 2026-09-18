from django.urls import path, include
from django.views.generic import RedirectView
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
    openapi.Info(
        title="ORM",
        default_version='v1',
        description="orm",
    ),
)

urlpatterns = [
    path('api/', include('usuarios.urls')),
    path('api/', include('buses.urls')),
    path('api/', include('destinos.urls')),
    path('api/', include('paquetes.urls')),
    path('api/', include('reservas.urls')),
    path('api/', include('pagos.urls')),
    path(
        'swagger/',
        schema_view.with_ui('swagger', cache_timeout=0),
    ),
]