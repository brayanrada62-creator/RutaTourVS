from django.db import models


class TipoBus(models.Model):
    nombre = models.CharField(max_length=100)
    agencia = models.ForeignKey("usuarios.Agencia", on_delete=models.CASCADE)
    capacidad = models.PositiveIntegerField()
    descripcion = models.CharField(max_length=300)

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = "tipo_bus"


class Bus(models.Model):
    ESTADOS = [
        ("activo", "Activo"),
        ("mantenimiento", "Mantenimiento"),
        ("inactivo", "Inactivo"),
    ]

    placa = models.CharField(max_length=15)
    agencia = models.ForeignKey("usuarios.Agencia", on_delete=models.CASCADE)
    tipo_bus = models.ForeignKey(TipoBus, on_delete=models.PROTECT)
    marca = models.CharField(max_length=100)
    modelo = models.CharField(max_length=100)
    estado = models.CharField(max_length=20, default="activo")
    fecha_registro = models.DateTimeField()

    def __str__(self):
        return self.placa

    class Meta:
        db_table = "buses"
        
class Bus_Conductor(models.Model):
    bus = models.ForeignKey(Bus, on_delete=models.CASCADE)
    conductor = models.ForeignKey("usuarios.Usuario", on_delete=models.CASCADE)

    class Meta:
        db_table = "bus_conductor"


class Asiento(models.Model):
    numero_asiento = models.IntegerField()
    tipo_bus = models.ForeignKey(TipoBus, on_delete=models.CASCADE)

    def __str__(self):
        return str(self.numero_asiento)

    class Meta:
        db_table = "asientos"