from rest_framework import serializers


class MensajeSalida(serializers.Serializer):
    message = serializers.CharField(max_length=255)

    class Meta:
        ref_name = "ReservasMensajeSalida"



class ReservaEntrada(serializers.Serializer):
    fecha_reserva = serializers.DateField()
    usuario_id = serializers.IntegerField()
    paquete_id = serializers.IntegerField()
    viaje_id = serializers.IntegerField(required=False, allow_null=True)
    estado = serializers.CharField(required=False, allow_blank=True)


class AsientoReservaEntrada(serializers.Serializer):
    asiento_id = serializers.IntegerField()
    reserva_id = serializers.IntegerField()