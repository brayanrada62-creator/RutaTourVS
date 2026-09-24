from rest_framework import serializers


class MensajeSalida(serializers.Serializer):
    message = serializers.CharField(max_length=255)

    class Meta:
        ref_name = "BusesMensajeSalida"



class TipoBusEntrada(serializers.Serializer):
    nombre = serializers.CharField(max_length=100)
    agencia_id = serializers.IntegerField()
    capacidad = serializers.IntegerField()
    descripcion = serializers.CharField(max_length=300)


class BusEntrada(serializers.Serializer):
    placa = serializers.CharField(max_length=20)
    agencia_id = serializers.IntegerField()
    tipo_bus_id = serializers.IntegerField()
    marca = serializers.CharField(max_length=100)
    modelo = serializers.CharField(max_length=100)
    estado = serializers.CharField(max_length=20)
    fecha_registro = serializers.DateField()
    conductor_id = serializers.IntegerField(required=False, allow_null=True)


class AsientoEntrada(serializers.Serializer):
    tipo_bus_id = serializers.IntegerField()
    numero_asiento = serializers.IntegerField()