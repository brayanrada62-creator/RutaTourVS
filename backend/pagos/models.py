from django.db import models


class Pago(models.Model):
    ESTADOS = [
        ("pendiente", "Pendiente"),
        ("aprobado", "Aprobado"),
        ("rechazado", "Rechazado"),
    ]

    precio = models.DecimalField(max_digits=10, decimal_places=2)
    reserva = models.ForeignKey("reservas.Reserva", on_delete=models.CASCADE)
    fecha_pago = models.DateTimeField()
    comprobante = models.ImageField(max_length=100, blank=True)
    referencia = models.CharField(max_length=255, blank=True, default="")

    estado = models.CharField(max_length=20, default="pendiente")
    motivo_rechazo = models.CharField(max_length=255, blank=True, default="")

    def __str__(self):
        return str(self.precio)

    class Meta:
        db_table = "pagos"