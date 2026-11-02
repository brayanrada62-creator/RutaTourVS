from rest_framework import serializers


class MensajeSalida(serializers.Serializer):
    message = serializers.CharField(max_length=255)

    class Meta:
        ref_name = "PagosMensajeSalida"



class PagoEntrada(serializers.Serializer):
    reserva_id = serializers.IntegerField()
    comprobante = serializers.FileField(required=False, help_text="Obligatorio para el cliente: JPG, PNG o WEBP, máx. 5 MB")
    referencia = serializers.CharField(max_length=255, required=False, allow_blank=True)
    precio = serializers.DecimalField(max_digits=10, decimal_places=2, required=False,
                                      help_text="Solo personal; para el cliente lo calcula el servidor")
    fecha_pago = serializers.DateField(required=False, help_text="Solo personal; para el cliente es la del servidor")
    estado = serializers.CharField(max_length=20, required=False, help_text="pendiente | aprobado | rechazado (solo la agencia)")
    motivo_rechazo = serializers.CharField(max_length=255, required=False, allow_blank=True)
