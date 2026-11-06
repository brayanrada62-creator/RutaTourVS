from rest_framework import serializers
from .models import Agencia, Usuario


class MensajeSalida(serializers.Serializer):
    message = serializers.CharField(max_length=255)

    class Meta:
        ref_name = "UsuariosMensajeSalida"


class loginSerializer(serializers.Serializer):
    correo = serializers.EmailField()
    contrasena = serializers.CharField(max_length=100)


class UsuarioEntrada(serializers.Serializer):
    nombre_completo = serializers.CharField(max_length=200)
    agencia_id = serializers.IntegerField(required=False, allow_null=True)
    rol_id = serializers.IntegerField()
    tipo_documento = serializers.CharField(max_length=30)
    numero_documento = serializers.CharField(max_length=30)
    correo = serializers.EmailField(max_length=150)
    telefono = serializers.CharField(max_length=20)
    contrasena = serializers.CharField(max_length=255)
    licencia = serializers.CharField(max_length=30, required=False, allow_blank=True,
                                     help_text="Número de la licencia de conducción")
    licencia_pdf = serializers.FileField(required=False,
                                         help_text="Solo conductores, enviado como multipart/form-data por el admin "
                                                   "de su agencia o el superadmin. Archivo .pdf de máximo 5 MB")


class UsuarioEditarEntrada(serializers.Serializer):
    """PUT /usuario/<id>/: todos los campos son opcionales (los que no llegan se conservan)."""
    nombre_completo = serializers.CharField(max_length=200, required=False)
    agencia_id = serializers.IntegerField(required=False, allow_null=True)
    rol_id = serializers.IntegerField(required=False)
    tipo_documento = serializers.CharField(max_length=30, required=False)
    numero_documento = serializers.CharField(max_length=30, required=False)
    correo = serializers.EmailField(max_length=150, required=False)
    telefono = serializers.CharField(max_length=20, required=False)
    contrasena = serializers.CharField(max_length=255, required=False)
    licencia = serializers.CharField(max_length=30, required=False, allow_blank=True,
                                     help_text="Número de la licencia de conducción")
    licencia_pdf = serializers.FileField(required=False,
                                         help_text="Reemplaza el PDF del conductor (.pdf, máx. 5 MB). "
                                                   "Solo el admin de su agencia o el superadmin")
    activo = serializers.BooleanField(required=False, help_text="false = suspender")


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
    activo = serializers.BooleanField(required=False, help_text="Solo el superadministrador lo cambia")

class UsuarioAgenciaEntrada(serializers.Serializer):
    usuario_id = serializers.PrimaryKeyRelatedField(
        source='usuario',
        queryset=Usuario.objects.all(),
    )
    agencia_id = serializers.PrimaryKeyRelatedField(
        source='agencia',
        queryset=Agencia.objects.all(),
    )