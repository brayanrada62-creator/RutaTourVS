from django.urls import path
from .views import (
    LoginView,
    UsuarioPerfilView,
    UsuarioView, UsuarioIdView, UsuarioDocumentoView,
    AgenciaView, AgenciaIdView, AgenciaNitView, AgenciaDireccionView,
)

urlpatterns = [
    # Login
    path('login/', LoginView.as_view(), name='login'),

    # Usuario
    path('usuario/', UsuarioView.as_view(), name='usuario'),
    path('usuario/<int:id>/', UsuarioIdView.as_view(), name='usuario-id'),
    path('usuario/perfil/', UsuarioPerfilView.as_view(), name='usuario-perfil'),
    path('usuarios/documento/<str:numero_documento>/', UsuarioDocumentoView.as_view(), name='usuario-documento'),

    # Agencia
    path('agencia/', AgenciaView.as_view(), name='agencia'),
    path('agencia/<int:id>/', AgenciaIdView.as_view(), name='agencia-id'),
    path('agencia/nit/<str:nit>/', AgenciaNitView.as_view(), name='agencia-nit'),
    path('agencia/direccion/<str:direccion>/', AgenciaDireccionView.as_view(), name='agencia-direccion'),
]