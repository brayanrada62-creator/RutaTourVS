from django.db import models


class Pago(models.Model):
    ESTADOS = [
        ("pendiente", "Pendiente"),
        ("aprobado", "Aprobado"),
        ("rechazado", "Rechazado"),
    ]

    precio = models.DecimalField(max_digits=10, decimal_places=2)
    # PROTECT: un pago nunca se borra junto con su reserva (trazabilidad del SRS).
    reserva = models.ForeignKey("reservas.Reserva", on_delete=models.PROTECT)
    fecha_pago = models.DateTimeField()
    comprobante = models.ImageField(max_length=100, blank=True)
    referencia = models.CharField(max_length=255, blank=True, default="")

    estado = models.CharField(max_length=20, choices=ESTADOS, default="pendiente")
    motivo_rechazo = models.CharField(max_length=255, blank=True, default="")
    # Auditoría: quién aprobó o rechazó el pago y cuándo.
    revisado_por = models.ForeignKey("usuarios.Usuario", null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="pagos_revisados")
    revisado_en = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return str(self.precio)

    class Meta:
        db_table = "pagos"