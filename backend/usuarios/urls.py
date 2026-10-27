from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    LoginView,
    LoginGoogleView,
    LogoutView,
    UsuarioPerfilView,
    PasswordResetView,
    PasswordResetConfirmarView,
    UsuarioView, UsuarioIdView, UsuarioDocumentoView, RolView,
    UsuarioAgenciaView,
    DashboardResumenView,
    AgenciaView, AgenciaIdView, AgenciaNitView, AgenciaDireccionView,
)

urlpatterns = [
    # Login
    path('login/', LoginView.as_view(), name='login'),
    path('login/google/', LoginGoogleView.as_view(), name='login-google'),
    path('logout/', LogoutView.as_view(), name='logout'),
    # Renovar la sesión: POST {"refresh": "..."} devuelve {"access": "..."}
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('password/reset/', PasswordResetView.as_view(), name='password-reset'),
    path('password/reset/confirmar/', PasswordResetConfirmarView.as_view(), name='password-reset-confirmar'),
    path('recuperar-contrasena/', PasswordResetView.as_view(), name='recuperar-contrasena'),
    path('recuperar-contrasena/confirmar/', PasswordResetConfirmarView.as_view(), name='recuperar-contrasena-confirmar'),

    # Usuario
    path('usuario/', UsuarioView.as_view(), name='usuario'),
    path('usuario/<int:id>/', UsuarioIdView.as_view(), name='usuario-id'),
    path('usuario/perfil/', UsuarioPerfilView.as_view(), name='usuario-perfil'),
    path('usuarios/documento/<str:numero_documento>/', UsuarioDocumentoView.as_view(), name='usuario-documento'),
    path('usuario-agencia/', UsuarioAgenciaView.as_view(), name='usuario-agencia'),
    path('usuario-agencia/<int:id>/', UsuarioAgenciaView.as_view(), name='usuario-agencia-id'),

    # Dashboard
    path('dashboard/resumen/', DashboardResumenView.as_view(), name='dashboard-resumen'),

    # Agencia
    path('agencia/', AgenciaView.as_view(), name='agencia'),
    path('agencia/<int:id>/', AgenciaIdView.as_view(), name='agencia-id'),
    path('agencia/nit/<str:nit>/', AgenciaNitView.as_view(), name='agencia-nit'),
    path('agencia/direccion/<str:direccion>/', AgenciaDireccionView.as_view(), name='agencia-direccion'),
]