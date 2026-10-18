from rest_framework import serializers


class MensajeSalida(serializers.Serializer):
    message = serializers.CharField(max_length=255)

    class Meta:
        ref_name = "PaquetesMensajeSalida"



class PaqueteEntrada(serializers.Serializer):
    nombre = serializers.CharField(max_length=100)
    agencia_id = serializers.IntegerField()
    descripcion = serializers.CharField(max_length=10000)
    duracion_estimada = serializers.CharField(max_length=100)
    estado = serializers.CharField(max_length=20)
    fecha_creacion = serializers.DateField()
    precio = serializers.DecimalField(max_digits=12, decimal_places=2)
    imagen = serializers.ImageField(required=False)
    destino_ids = serializers.CharField(required=False)
    imagenes_destino = serializers.ImageField(required=False)
    destinos_imagen = serializers.CharField(
        required=False,
    )


class PaqueteRegistrarEntrada(serializers.Serializer):
    nombre = serializers.CharField(max_length=150)
    agencia_id = serializers.IntegerField(required=False)
    descripcion = serializers.CharField(max_length=10000, required=False, allow_blank=True)
    duracion_estimada = serializers.CharField(max_length=50, required=False, allow_blank=True)
    estado = serializers.CharField(max_length=20, required=False)
    fecha_creacion = serializers.DateTimeField(required=False)
    precio = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    imagen = serializers.ImageField(required=False)
    destino_ids = serializers.CharField(required=False)
    imagenes_destino = serializers.ImageField(required=False)
    destinos_imagen = serializers.CharField(
        required=False,
    )


class PaqueteDestinoEntrada(serializers.Serializer):
    paquete_id = serializers.IntegerField()
    destino_id = serializers.IntegerField()


class ItinerarioEntrada(serializers.Serializer):
    titulo = serializers.CharField(max_length=100)
    paquete_id = serializers.IntegerField()
    dia = serializers.IntegerField()
    descripcion = serializers.CharField(max_length=300)
    hora = serializers.TimeField()
    lugar = serializers.CharField(max_length=100)