from django.urls import path, include
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
    path('api/', include('RutaTour.urls')),
    path(
        'swagger/',
        schema_view.with_ui('swagger', cache_timeout=0),
    ),
]
