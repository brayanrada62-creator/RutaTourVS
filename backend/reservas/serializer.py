from rest_framework import serializers


class MensajeSalida(serializers.Serializer):
    message = serializers.CharField(max_length=255)

    class Meta:
        ref_name = "ReservasMensajeSalida"



class ReservaEntrada(serializers.Serializer):
    paquete_id = serializers.IntegerField()
    viaje_id = serializers.IntegerField(required=False, allow_null=True,
                                       help_text="Salida PROGRAMADA del paquete (obligatoria para el cliente)")
    asientos = serializers.CharField(required=False, allow_blank=True,
                                     help_text="Ids de las sillas separados por coma, ej. 12,13")
    clave_idempotencia = serializers.CharField(required=False, allow_blank=True, max_length=64,
                                               help_text="Repetir con la misma clave devuelve la misma reserva")
    fecha_reserva = serializers.DateField(required=False, help_text="Solo personal; el cliente usa la del servidor")
    usuario_id = serializers.IntegerField(required=False, help_text="Solo personal; el cliente reserva para sí")
    estado = serializers.CharField(required=False, allow_blank=True, help_text="Solo personal: pendiente o cancelada")
    pasajero_nombre = serializers.CharField(required=False, allow_blank=True, max_length=120,
                                            help_text="Vacío = viaja el titular")
    pasajero_documento = serializers.CharField(required=False, allow_blank=True, max_length=15,
                                               help_text="Solo dígitos, 5 a 15")


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
    