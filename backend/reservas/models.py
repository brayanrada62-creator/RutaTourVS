from django.db import models


class Reserva(models.Model):
    fecha_reserva = models.DateTimeField()
    usuario = models.ForeignKey("usuarios.Usuario", on_delete=models.CASCADE)
    paquete = models.ForeignKey("paquetes.Paquete", on_delete=models.PROTECT)
    estado = models.CharField(max_length=20, default="pendiente")
    abordado = models.CharField(max_length=20, default="PENDIENTE")
    # Salida elegida. Las reservas anteriores (sin salida) pertenecen al paquete.
    viaje = models.ForeignKey("buses.Viaje", null=True, blank=True, on_delete=models.SET_NULL)
    # Quién viaja, si no es el titular de la cuenta (vacío = viaja el titular).
    pasajero_nombre = models.CharField(max_length=120, blank=True, default="")
    pasajero_documento = models.CharField(max_length=15, blank=True, default="")

    def __str__(self):
        return str(self.fecha_reserva)

    class Meta:
        db_table = "reserva"


def reservas_que_ocupan(paquete_id, viaje_id=None):
    """Reservas que ocupan sillas. Con salida: las de esa salida y las antiguas sin salida del mismo
    paquete (no se sabe en cuál viajan, así que bloquean en todas). Sin salida: todas las del paquete."""
    lista = Reserva.objects.filter(paquete_id=paquete_id).exclude(estado__iexact="cancelada")
    if viaje_id:
        lista = lista.filter(models.Q(viaje_id=viaje_id) | models.Q(viaje__isnull=True))
    return lista


class AsientoReserva(models.Model):
    reserva = models.ForeignKey(Reserva, on_delete=models.CASCADE)
    asiento = models.ForeignKey("buses.Asiento", on_delete=models.PROTECT)

    def __str__(self):
        return f"Reserva #{self.reserva_id} - Asiento {self.asiento.numero_asiento}"

    class Meta:
        db_table = "asientos_reserva"


class GpsPunto(models.Model):
    paquete = models.ForeignKey("paquetes.Paquete", on_delete=models.CASCADE)
    viaje = models.ForeignKey("buses.Viaje", null=True, blank=True, on_delete=models.CASCADE)
    lat = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    lng = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    velocidad = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "gps_puntos"


class Novedad(models.Model):
    paquete = models.ForeignKey("paquetes.Paquete", on_delete=models.SET_NULL, null=True, blank=True)
    viaje = models.ForeignKey("buses.Viaje", on_delete=models.SET_NULL, null=True, blank=True)
    tipo = models.CharField(max_length=80, default="novedad")
    detalle = models.CharField(max_length=400, default="")
    fecha = models.DateTimeField(auto_now_add=True)
    # La agencia la marca como atendida desde Reportes.
    resuelta = models.BooleanField(default=False)

    class Meta:
        db_table = "novedades"


class ChatMensaje(models.Model):
    paquete = models.ForeignKey("paquetes.Paquete", on_delete=models.SET_NULL, null=True, blank=True)
    viaje = models.ForeignKey("buses.Viaje", on_delete=models.SET_NULL, null=True, blank=True)
    usuario = models.ForeignKey("usuarios.Usuario", on_delete=models.SET_NULL, null=True, blank=True)
    texto = models.CharField(max_length=400, default="")
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "chat_mensajes"
