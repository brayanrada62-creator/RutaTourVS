from django.db import models

class Plan(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField()
    precio_mensual = models.DecimalField(max_digits=10, decimal_places=2)
    precio_trimestral = models.DecimalField(max_digits=10, decimal_places=2)
    precio_anual = models.DecimalField(max_digits=10, decimal_places=2)
    maximo_agencias = models.IntegerField(null=True, blank=True)
    maximo_paquetes = models.IntegerField(null=True, blank=True)
    maximo_buses = models.IntegerField(null=True, blank=True)
    maximo_administradores = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return self.nombre

class PlanAgencias(models.Model):
    id_plan = models.ForeignKey(Plan, on_delete=models.CASCADE)
    id_agencia = models.ForeignKey('usuarios.Agencia', on_delete=models.CASCADE)
    periodo=models.CharField(max_length=20, choices=[('mensual', 'Mensual'), ('trimestral', 'Trimestral'), ('anual', 'Anual')])
    vencimiento=models.DateField()
    estado=models.CharField(max_length=20, choices=[('activo', 'Activo'), ('inactivo', 'Inactivo')], default='activo')


    def __str__(self):
        return f"{self.id_plan.nombre} - {self.id_agencia.nombre}"