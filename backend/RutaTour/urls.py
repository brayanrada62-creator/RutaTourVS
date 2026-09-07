from django.urls import path
from .views import UsuarioView, LoginView, AgenciaView
urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('usuario/', UsuarioView.as_view(), name='usuario'),
    path('agencia/', AgenciaView.as_view(), name='agencia')
]