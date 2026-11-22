from decimal import Decimal

from django.db import models

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

    def __str__(self):
        return f"{self.id_agencia.nombre} - {self.id_plan.nombre} - {self.estado}"

    