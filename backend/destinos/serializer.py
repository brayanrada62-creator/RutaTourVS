from rest_framework import serializers

from usuarios.serializer import validar_celular, validar_fijo



class MensajeSalida(serializers.Serializer):
    message = serializers.CharField(max_length=255)

    class Meta:
        ref_name = "DestinosMensajeSalida"



class DestinoEntrada(serializers.Serializer):
    nombre = serializers.CharField(max_length=150)
    departamento = serializers.CharField(max_length=100)
    descripcion = serializers.CharField(max_length=2000)


class HopedajeEntrada(serializers.Serializer):
    nombre = serializers.CharField(max_length=150)
    destino_id = serializers.IntegerField(required=False)
    destino_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    direccion = serializers.CharField(max_length=255)
    telefono = serializers.CharField(max_length=10, validators=[validar_celular],
                                     help_text="Celular: 10 dígitos y empieza por 3. Al editar se valida solo si cambia")
    telefono_fijo = serializers.CharField(max_length=10, required=False, allow_blank=True, validators=[validar_fijo],
                                          help_text="Opcional. Fijo: 10 dígitos y empieza por 60 (6012345678)")
    descripcion = serializers.CharField(max_length=2000)
    imagen = serializers.ImageField(required=False)


class HospedajeDestinoEntrada(serializers.Serializer):
    hospedaje_id = serializers.IntegerField()
    destino_id = serializers.IntegerField()


class ImagenEntrada(serializers.Serializer):
    url_img = serializers.ImageField(max_length=225)
    destino_id = serializers.IntegerField()
    descripcion = serializers.CharField(max_length=2000)