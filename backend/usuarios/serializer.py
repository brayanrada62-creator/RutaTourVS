from rest_framework import serializers


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
    licencia = serializers.CharField(max_length=30, required=False, allow_blank=True)


class AgenciaEntrada(serializers.Serializer):
    nombre = serializers.CharField(max_length=150)
    nit = serializers.CharField(max_length=30)
    direccion = serializers.CharField(max_length=255)
    telefono = serializers.CharField(max_length=20)
    correo = serializers.EmailField(max_length=150)