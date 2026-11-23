from django.db import models
from django.utils import timezone

from usuarios.models import Usuario


class CredencialBiometrica(models.Model):
    """Llave pública de un equipo (Touch ID, Windows Hello o Face ID). No guarda el rostro ni la huella."""

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="credenciales_biometricas")
    credential_id = models.CharField(max_length=255, unique=True)
    llave_publica = models.TextField()
    contador = models.PositiveIntegerField(default=0)
    creado = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.usuario.correo} {self.credential_id[:12]}"

    class Meta:
        db_table = "credencial_biometrica"


class RetoBiometrico(models.Model):
    """Reto de un solo uso. Dura dos minutos y se borra al verificar."""

    challenge = models.CharField(max_length=255, unique=True)
    usuario = models.ForeignKey(
        Usuario,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="retos_biometricos",
    )
    proposito = models.CharField(max_length=20)
    expira = models.DateTimeField()

    class Meta:
        db_table = "reto_biometrico"

    @classmethod
    def limpiar_viejos(cls):
        cls.objects.filter(expira__lt=timezone.now()).delete()
