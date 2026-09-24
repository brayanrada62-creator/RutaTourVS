from rest_framework import serializers


class MensajeSalida(serializers.Serializer):
    message = serializers.CharField(max_length=255)

    class Meta:
        ref_name = "PaquetesMensajeSalida"



class PaqueteEntrada(serializers.Serializer):
    nombre = serializers.CharField(max_length=100)
    agencia_id = serializers.IntegerField()
    descripcion = serializers.CharField(max_length=300)
    duracion_estimada = serializers.CharField(max_length=100)
    estado = serializers.CharField(max_length=20)
    fecha_creacion = serializers.DateField()


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