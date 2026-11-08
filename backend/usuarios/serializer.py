import re

from rest_framework import serializers
from .models import Agencia, Usuario

# Celular de Colombia: 10 dígitos y empieza por 3 (por ejemplo 3001234567). Solo se aceptan celulares.
CELULAR_CO = re.compile(r"3\d{9}")
MENSAJE_CELULAR = "El celular debe tener 10 dígitos y empezar por 3"


def error_telefono(valor):
    """Mensaje si el celular no sirve; None si es válido. Lo usan el registro, el personal y las agencias."""
    return None if CELULAR_CO.fullmatch(str(valor or "").strip()) else MENSAJE_CELULAR


def validar_celular(valor):
    error = error_telefono(valor)
    if error:
        raise serializers.ValidationError(error)


# Teléfono fijo de Colombia (desde 2021): 10 dígitos que empiezan por 60 + indicativo (6012345678 Bogotá).
FIJO_CO = re.compile(r"60\d{8}")
MENSAJE_FIJO = "El teléfono fijo debe tener 10 dígitos y empezar por 60 (por ejemplo 6012345678)"


def error_telefono_fijo(valor):
    """Mensaje si el fijo no sirve; None si es válido o viene vacío (es opcional)."""
    texto = str(valor or "").strip()
    return None if not texto or FIJO_CO.fullmatch(texto) else MENSAJE_FIJO


def validar_fijo(valor):
    error = error_telefono_fijo(valor)
    if error:
        raise serializers.ValidationError(error)


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
    telefono = serializers.CharField(max_length=10, validators=[validar_celular],
                                     help_text="Celular de Colombia: 10 dígitos y empieza por 3")
    contrasena = serializers.CharField(max_length=255)
    licencia = serializers.CharField(max_length=30, required=False, allow_blank=True,
                                     help_text="Número de la licencia de conducción")
    foto = serializers.ImageField(required=False, help_text="Foto de perfil: JPG, PNG o WEBP de máx. 5 MB (multipart)")
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
    telefono = serializers.CharField(max_length=10, required=False, validators=[validar_celular],
                                     help_text="Celular de Colombia: 10 dígitos y empieza por 3. "
                                               "Se valida solo si cambia")
    contrasena = serializers.CharField(max_length=255, required=False)
    licencia = serializers.CharField(max_length=30, required=False, allow_blank=True,
                                     help_text="Número de la licencia de conducción")
    licencia_pdf = serializers.FileField(required=False,
                                         help_text="Reemplaza el PDF del conductor (.pdf, máx. 5 MB). "
                                                   "Solo el admin de su agencia o el superadmin")
    activo = serializers.BooleanField(required=False, help_text="false = suspender")
    foto = serializers.ImageField(required=False, help_text="Reemplaza la foto: JPG, PNG o WEBP de máx. 5 MB (multipart). "
                                                            "La anterior se borra de Cloudinary")
    quitar_foto = serializers.BooleanField(required=False, help_text="true = quitar la foto de perfil")


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
    telefono = serializers.CharField(max_length=10, validators=[validar_celular],
                                     help_text="Celular de Colombia: 10 dígitos y empieza por 3")
    correo = serializers.EmailField(max_length=150)
    activo = serializers.BooleanField(required=False, help_text="Solo el superadministrador lo cambia")
    banco = serializers.CharField(max_length=100, required=False, allow_blank=True)
    tipo_cuenta = serializers.CharField(max_length=30, required=False, allow_blank=True)
    numero_cuenta = serializers.CharField(max_length=40, required=False, allow_blank=True)
    titular = serializers.CharField(max_length=150, required=False, allow_blank=True)

class UsuarioAgenciaEntrada(serializers.Serializer):
    usuario_id = serializers.PrimaryKeyRelatedField(
        source='usuario',
        queryset=Usuario.objects.all(),
    )
    agencia_id = serializers.PrimaryKeyRelatedField(
        source='agencia',
        queryset=Agencia.objects.all(),
    )