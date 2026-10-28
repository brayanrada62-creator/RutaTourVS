from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

# Estados que se GUARDAN en la reserva. "pagada" no se guarda: se deduce del último pago aprobado.
ESTADOS_RESERVA = [
    ("pendiente", "Pendiente"),   # guarda sus sillas (con plazo si no hay pago en revisión)
    ("cancelada", "Cancelada"),   # la canceló el cliente o la agencia: sus sillas quedan libres
    ("vencida", "Vencida"),       # pasó el plazo sin comprobante: sus sillas quedan libres
]
ESTADOS_QUE_LIBERAN = ("cancelada", "vencida")


def plazo_de_pago():
    """Hasta cuándo se guardan las sillas sin comprobante: ahora + RESERVA_MINUTOS_PAGO (60 por defecto)."""
    return timezone.now() + timedelta(minutes=settings.RESERVA_MINUTOS_PAGO)


class Reserva(models.Model):
    fecha_reserva = models.DateTimeField()
    usuario = models.ForeignKey("usuarios.Usuario", on_delete=models.CASCADE)
    paquete = models.ForeignKey("paquetes.Paquete", on_delete=models.PROTECT)
    estado = models.CharField(max_length=20, choices=ESTADOS_RESERVA, default="pendiente")
    # Vencimiento de las sillas. Vacío = el plazo está detenido (pago en revisión o aprobado)
    # o es una reserva anterior a esta regla.
    vence_en = models.DateTimeField(null=True, blank=True)
    # La app la envía para que un reintento no cree una segunda reserva.
    clave_idempotencia = models.CharField(max_length=64, null=True, blank=True)
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
        constraints = [
            models.UniqueConstraint(fields=["usuario", "clave_idempotencia"], name="reserva_clave_unica"),
        ]

    @property
    def vencida(self):
        """True si pasó el plazo, aunque el estado guardado todavía diga "pendiente"."""
        return self.estado == "vencida" or (
            self.estado == "pendiente" and self.vence_en is not None and self.vence_en <= timezone.now()
        )


def reservas_activas():
    """Reservas que todavía guardan sus sillas: ni canceladas ni vencidas (aunque nadie las haya marcado)."""
    return (
        Reserva.objects.exclude(estado__in=ESTADOS_QUE_LIBERAN)
        .filter(models.Q(vence_en__isnull=True) | models.Q(vence_en__gt=timezone.now()))
    )


def marcar_vencidas():
    """Pasa a "vencida" las reservas pendientes cuyo plazo terminó. La ocupación ya las ignora;
    esto solo deja el estado al día para las pantallas."""
    return Reserva.objects.filter(estado="pendiente", vence_en__lte=timezone.now()).update(estado="vencida")


def reservas_que_ocupan(paquete_id, viaje_id=None):
    """Reservas que ocupan sillas. Con salida: las de esa salida y las antiguas sin salida del mismo
    paquete (no se sabe en cuál viajan, así que bloquean en todas). Sin salida: todas las del paquete."""
    lista = reservas_activas().filter(paquete_id=paquete_id)
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
