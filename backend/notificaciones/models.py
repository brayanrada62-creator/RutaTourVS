from django.db import models


class Tipo(models.TextChoices):
    """Tipos de notificación. Para agregar uno: nuevo valor aquí, su rol en TIPOS_POR_ROL (servicio.py)
    y su disparo en el punto del flujo de negocio; no cambia ninguna tabla."""
    COMPROBANTE_PLAN = "COMPROBANTE_PLAN", "Comprobante de membresía pendiente"
    COMPROBANTE_PLAN_APROBADO = "COMPROBANTE_PLAN_APROBADO", "Membresía aprobada"
    COMPROBANTE_PLAN_RECHAZADO = "COMPROBANTE_PLAN_RECHAZADO", "Membresía rechazada"
    PAGO_PENDIENTE = "PAGO_PENDIENTE", "Comprobante pendiente de revisión"
    PAGO_APROBADO = "PAGO_APROBADO", "Pago aprobado"
    CAMBIO_VIAJE = "CAMBIO_VIAJE", "Cambio en un viaje asignado"
    NOVEDAD_INCIDENTE = "NOVEDAD_INCIDENTE", "Novedad o incidente reportado"


class Notificacion(models.Model):
    destinatario = models.ForeignKey("usuarios.Usuario", on_delete=models.CASCADE, related_name="notificaciones")
    tipo = models.CharField(max_length=30, choices=Tipo.choices)
    titulo = models.CharField(max_length=150)
    mensaje = models.CharField(max_length=500)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    leida = models.BooleanField(default=False)
    # Recurso al que lleva la notificación: viaje, novedad o compra (reserva).
    referencia_id = models.PositiveIntegerField(null=True, blank=True)
    referencia_tipo = models.CharField(max_length=20, blank=True, default="")
    datos = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "notificaciones"
        ordering = ["-fecha_creacion", "-id"]
        indexes = [models.Index(fields=["destinatario", "-fecha_creacion"])]


class PreferenciaNotificacion(models.Model):
    usuario = models.ForeignKey("usuarios.Usuario", on_delete=models.CASCADE, related_name="preferencias_notificacion")
    tipo = models.CharField(max_length=30, choices=Tipo.choices)
    activa = models.BooleanField(default=True)

    class Meta:
        db_table = "preferencias_notificacion"
        constraints = [models.UniqueConstraint(fields=["usuario", "tipo"], name="preferencia_usuario_tipo_unica")]


class DispositivoFCM(models.Model):
    usuario = models.ForeignKey("usuarios.Usuario", on_delete=models.CASCADE, related_name="dispositivos_fcm")
    token = models.CharField(max_length=255, unique=True)
    plataforma = models.CharField(max_length=20, default="android")
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "dispositivos_fcm"
