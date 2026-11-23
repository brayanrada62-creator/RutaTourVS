from django.urls import path

from .views import LoginOpciones, LoginVerificar, RegistroOpciones, RegistroVerificar

urlpatterns = [
    path("registro/opciones/", RegistroOpciones.as_view(), name="biometria-registro-opciones"),
    path("registro/verificar/", RegistroVerificar.as_view(), name="biometria-registro-verificar"),
    path("login/opciones/", LoginOpciones.as_view(), name="biometria-login-opciones"),
    path("login/verificar/", LoginVerificar.as_view(), name="biometria-login-verificar"),
]
