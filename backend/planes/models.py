from decimal import Decimal

from django.db import models
from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone

class PrecioPlanNoDisponible(Exception):
    pass

class Plan(models.Model):
    PRECIOS = {
        "Básico": {1: Decimal("149000"), 3: Decimal("424000"), 12: Decimal("1490000")},
        "Profesional": {1: Decimal("349000"), 3: Decimal("995000"), 12: Decimal("3490000")},
        "Empresarial": {1: Decimal("790000"), 3: Decimal("2250000"), 12: Decimal("7900000")},
    }

    nombre = models.CharField(max_length=100)
    descripcion = models.TextField()
    maximo_agencias = models.IntegerField(null=True, blank=True)
    maximo_paquetes = models.IntegerField(null=True, blank=True)
    maximo_buses = models.IntegerField(null=True, blank=True)
    maximo_administradores = models.IntegerField(null=True, blank=True)

    def precio_de(self, periodo):
        return self.PRECIOS[self.nombre][periodo]

    def precio_vigente(self, periodo):
        try:
            precio = PrecioPlan.objects.filter(id_plan=self, periodo=periodo).order_by('-desde_el', '-id').first()
        except (OperationalError, ProgrammingError):
            precio = None
        if precio is not None:
            return precio.monto
        claves = {'mensual': 1, 'trimestral': 3, 'anual': 12}
        return self.precio_de(claves[periodo])

    def registrar_precio(self, periodo, monto):
        monto = Decimal(str(monto))
        vigente = self.precio_vigente(periodo)
        if vigente is not None and Decimal(vigente) == monto:
            return None
        try:
            return PrecioPlan.objects.create(
                id_plan=self,
                periodo=periodo,
                monto=monto,
                desde_el=timezone.localdate(),
            )
        except (OperationalError, ProgrammingError):
            raise PrecioPlanNoDisponible('La tabla de precios todavía no está creada en la base.')

    def __str__(self):
        return self.nombre

class PlanAgencias(models.Model):
    ESTADOS = [
        ('activo', 'Activo'),
        ('suspendida', 'Suspendida'),
        ('inactivo', 'Inactivo'),
    ]
    id_plan = models.ForeignKey(Plan, on_delete=models.CASCADE)
    id_agencia = models.ForeignKey('usuarios.Agencia', on_delete=models.CASCADE)
    periodo=models.CharField(max_length=20, choices=[
        ('mensual', 'Mensual'), 
        ('trimestral', 'Trimestral'), 
        ('anual', 'Anual')
        ])

    inicia_el=models.DateField(null=True, blank=True)
    vencimiento=models.DateField()
    estado=models.CharField(max_length=20, choices=ESTADOS, default='activo')


    def __str__(self):
        return f"{self.id_plan.nombre} - {self.id_agencia.nombre}"

class SolicitudPlan(models.Model):
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('aprobada', 'Aprobada'),
        ('rechazada', 'Rechazada'),
    ]

    PERIODOS=[
        ('mensual', 'Mensual'),
        ('trimestral', 'Trimestral'),
        ('anual', 'Anual'),
    ]
    id_agencia = models.ForeignKey('usuarios.Agencia', on_delete=models.CASCADE)
    id_plan = models.ForeignKey(Plan, on_delete=models.CASCADE)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    periodo = models.CharField(max_length=20, choices=PERIODOS, default="mensual")
    precio = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    comprobante = models.ImageField(upload_to="comprobantes_planes/", blank=True)
    motivo = models.CharField(max_length=255, blank=True)
    inicia_el = models.DateField(null=True, blank=True)
    vence_el = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.id_agencia.nombre} - {self.id_plan.nombre} - {self.estado}"

NUMERO_WHATSAPP_INICIAL = "3022726350"


class ContactoLanding(models.Model):
    """Un solo celular: el botón de WhatsApp de la landing de la app."""

    whatsapp = models.CharField(max_length=10)

    def __str__(self):
        return self.whatsapp


class PrecioPlan(models.Model):
    PERIODOS = [
        ('mensual', 'Mensual'),
        ('trimestral', 'Trimestral'),
        ('anual', 'Anual'),
    ]
    id_plan = models.ForeignKey(Plan, on_delete=models.CASCADE)
    periodo = models.CharField(max_length=20, choices=PERIODOS)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    desde_el = models.DateField()

    def __str__(self):
        return f"{self.id_plan.nombre} - {self.periodo} - {self.monto}"

    