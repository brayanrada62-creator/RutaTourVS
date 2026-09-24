from django.db import models


class Reserva(models.Model):
    fecha_reserva = models.DateTimeField()
    usuario = models.ForeignKey("usuarios.Usuario", on_delete=models.CASCADE)
    paquete = models.ForeignKey("paquetes.Paquete", on_delete=models.PROTECT)
    viaje = models.ForeignKey("paquetes.Viaje", on_delete=models.SET_NULL, null=True, blank=True)
    estado = models.CharField(max_length=20, default="pendiente")
    abordado = models.CharField(max_length=20, default="PENDIENTE")

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


class GpsPunto(models.Model):
    viaje = models.ForeignKey("paquetes.Viaje", on_delete=models.CASCADE)
    lat = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    lng = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    velocidad = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "gps_puntos"


class Novedad(models.Model):
    viaje = models.ForeignKey("paquetes.Viaje", on_delete=models.SET_NULL, null=True, blank=True)
    tipo = models.CharField(max_length=80, default="novedad")
    detalle = models.CharField(max_length=400, default="")
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "novedades"


class ChatMensaje(models.Model):
    viaje = models.ForeignKey("paquetes.Viaje", on_delete=models.SET_NULL, null=True, blank=True)
    usuario = models.ForeignKey("usuarios.Usuario", on_delete=models.SET_NULL, null=True, blank=True)
    texto = models.CharField(max_length=400, default="")
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "chat_mensajes"


class ParadaViaje(models.Model):
    viaje = models.ForeignKey("paquetes.Viaje", on_delete=models.CASCADE)
    nombre = models.CharField(max_length=150)
    orden = models.IntegerField(default=1)
    cumplida = models.BooleanField(default=False)

    class Meta:
        db_table = "paradas_viaje"