from rest_framework import serializers
from .models import Agencia, Usuario


class MensajeSalida(serializers.Serializer):
    message = serializers.CharField(max_length=255)

    class Meta:
        ref_name = "UsuariosMensajeSalida"


class UsuarioCreadoSalida(serializers.Serializer):
    message = serializers.CharField(max_length=255)
    id = serializers.IntegerField()
    usuario_id = serializers.IntegerField()



class loginSerializer(serializers.Serializer):
    correo = serializers.EmailField()
    contrasena = serializers.CharField(max_length=100)


class UsuarioEntrada(serializers.Serializer):
    nombre_completo = serializers.CharField(max_length=200)
    rol_id = serializers.IntegerField()
    tipo_documento = serializers.CharField(max_length=30)
    numero_documento = serializers.CharField(max_length=30)
    correo = serializers.EmailField(max_length=150)
    telefono = serializers.CharField(max_length=20)
    contrasena = serializers.CharField(max_length=255)
    licencia = serializers.CharField(max_length=30, required=False, allow_blank=True)


class RecuperarContrasenaEntrada(serializers.Serializer):
    correo = serializers.EmailField()


class ConfirmarContrasenaEntrada(serializers.Serializer):
    token = serializers.CharField(required=False, allow_blank=True)
    correo = serializers.EmailField(required=False)
    codigo = serializers.CharField(required=False, max_length=6, allow_blank=True)
    contrasena = serializers.CharField(min_length=6, max_length=255)
    confirmar = serializers.CharField(required=False, allow_blank=True)


class LoginGoogleEntrada(serializers.Serializer):
    id_token = serializers.CharField(help_text="ID token que devuelve Google Sign-In en la app o web")


class AgenciaEntrada(serializers.Serializer):
    nombre = serializers.CharField(max_length=150)
    nit = serializers.CharField(max_length=30)
    direccion = serializers.CharField(max_length=255)
    telefono = serializers.CharField(max_length=20)
    correo = serializers.EmailField(max_length=150)
    
class UsuarioAgenciaEntrada(serializers.Serializer):
    usuario_id = serializers.PrimaryKeyRelatedField(
        source='usuario',
        queryset=Usuario.objects.all(),
    )
    agencia_id = serializers.PrimaryKeyRelatedField(
        source='agencia',
        queryset=Agencia.objects.all(),
    )