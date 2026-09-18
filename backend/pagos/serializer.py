from rest_framework import serializers


class MensajeSalida(serializers.Serializer):
    message = serializers.CharField(max_length=255)

    class Meta:
        ref_name = "PagosMensajeSalida"



class PagoEntrada(serializers.Serializer):
    precio = serializers.DecimalField(max_digits=10, decimal_places=2)
    reserva_id = serializers.IntegerField()
    fecha_pago = serializers.DateField()
    referencia = serializers.CharField(max_length=100)
    comprobante = serializers.FileField()
    estado = serializers.CharField(max_length=20)
    motivo_rechazo = serializers.CharField(max_length=255)