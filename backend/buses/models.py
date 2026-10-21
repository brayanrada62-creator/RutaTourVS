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
        constraints = [
            models.UniqueConstraint(fields=["bus", "conductor"], name="bus_conductor_unico"),
        ]


class Asiento(models.Model):
    numero_asiento = models.IntegerField()
    tipo_bus = models.ForeignKey(TipoBus, on_delete=models.CASCADE)

    def __str__(self):
        return str(self.numero_asiento)

    class Meta:
        db_table = "asientos"

class Viaje(models.Model):
    """Salida programada de un paquete en un bus. El conductor no se asigna aquí:
    hereda los viajes del bus que tiene asignado (Bus_Conductor)."""

    PROGRAMADO = "PROGRAMADO"
    EN_CURSO = "EN_CURSO"
    COMPLETADO = "COMPLETADO"
    ESTADOS = [
        (PROGRAMADO, "Programado"),
        (EN_CURSO, "En curso"),
        (COMPLETADO, "Completado"),
    ]

    paquete = models.ForeignKey("paquetes.Paquete", on_delete=models.CASCADE)
    bus = models.ForeignKey(Bus, on_delete=models.PROTECT)
    fecha = models.DateField()
    hora = models.TimeField()
    estado = models.CharField(max_length=20, choices=ESTADOS, default=PROGRAMADO)
    # Conductor que inició el recorrido (para GPS y auditoría).
    conductor = models.ForeignKey("usuarios.Usuario", null=True, blank=True, on_delete=models.SET_NULL)
    iniciado_en = models.DateTimeField(null=True, blank=True)
    finalizado_en = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.paquete_id} · {self.bus_id} · {self.fecha} {self.hora}"

    class Meta:
        db_table = "viajes_bus"
        ordering = ["fecha", "hora", "id"]


class ParadaCumplida(models.Model):
    """Parada del itinerario del paquete que el conductor marcó como realizada en un viaje."""

    viaje = models.ForeignKey(Viaje, on_delete=models.CASCADE)
    itinerario = models.ForeignKey("paquetes.Itinerario", on_delete=models.CASCADE)
    cumplida_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "paradas_cumplidas"
        constraints = [models.UniqueConstraint(fields=["viaje", "itinerario"], name="parada_cumplida_unica")]
