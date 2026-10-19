from rest_framework import serializers


class MensajeSalida(serializers.Serializer):
    message = serializers.CharField(max_length=255)

    class Meta:
        ref_name = "ReservasMensajeSalida"



class ReservaEntrada(serializers.Serializer):
    fecha_reserva = serializers.DateField(required=False)
    usuario_id = serializers.IntegerField(required=False)
    paquete_id = serializers.IntegerField()
    viaje_id = serializers.IntegerField(required=False, allow_null=True)
    estado = serializers.CharField(required=False, allow_blank=True)
    asientos = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="IDs de asiento separados por coma, ej: 1,2,3",
    )
    asiento_ids = serializers.CharField(required=False, allow_blank=True)


class AsientoReservaEntrada(serializers.Serializer):
    asiento_id = serializers.IntegerField()
    reserva_id = serializers.IntegerField()
    
class GpsPuntoEntrada(serializers.Serializer):
    paquete_id = serializers.IntegerField()
    lat = serializers.DecimalField(max_digits=10, decimal_places=6)
    lng = serializers.DecimalField(max_digits=10, decimal_places=6)
    velocidad = serializers.DecimalField(max_digits=6, decimal_places=2)
    fecha = serializers.DateTimeField(required=False, allow_null=True)
    
class NovedadEntrada(serializers.Serializer):
    paquete_id = serializers.IntegerField(required=False, allow_null=True)
    tipo = serializers.CharField(max_length=80, required=False, allow_blank=True)
    detalle = serializers.CharField(max_length=400, required=False, allow_blank=True)
    fecha = serializers.DateTimeField(required=False, allow_null=True)
    