from rest_framework import serializers


class MensajeSalida(serializers.Serializer):
    message = serializers.CharField(max_length=255)

    class Meta:
        ref_name = "ReservasMensajeSalida"



class ReservaEntrada(serializers.Serializer):
    fecha_reserva = serializers.DateField()
    usuario_id = serializers.IntegerField()
    paquete_id = serializers.IntegerField()


class AsientoReservaEntrada(serializers.Serializer):
    asiento_id = serializers.IntegerField()
    reserva_id = serializers.IntegerField()