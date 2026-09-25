from django.db import models


class Reserva(models.Model):
    fecha_reserva = models.DateTimeField()
    usuario = models.ForeignKey("usuarios.Usuario", on_delete=models.CASCADE)
    paquete = models.ForeignKey("paquetes.Paquete", on_delete=models.PROTECT)

    def __str__(self):
        return str(self.fecha_reserva)

    class Meta:
        db_table = "reserva"


class AsientoReserva(models.Model):
    reserva = models.ForeignKey(Reserva, on_delete=models.CASCADE)
    asiento = models.ForeignKey("buses.Asiento", on_delete=models.PROTECT)

    def __str__(self):
        return f"Reserva #{self.reserva_id} - Asiento {self.asiento.numero_asiento}"

    class Meta:
        db_table = "asientos_reserva"