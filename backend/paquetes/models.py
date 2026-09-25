from django.db import models


class Paquete(models.Model):
    ESTADOS = [
        ("activo", "Activo"),
        ("inactivo", "Inactivo"),
        ("agotado", "Agotado"),
    ]

    nombre = models.CharField(max_length=150)
    agencia = models.ForeignKey("usuarios.Agencia", on_delete=models.CASCADE)
    descripcion = models.CharField(max_length=300)
    duracion_estimada = models.CharField(max_length=50)
    estado = models.CharField(max_length=20, default="activo")
    fecha_creacion = models.DateTimeField()
    precio = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = "paquetes"


class PaqueteDestino(models.Model):
    paquete = models.ForeignKey(Paquete, on_delete=models.CASCADE)
    destino = models.ForeignKey("destinos.Destino", on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.paquete.nombre} - {self.destino.nombre}"

    class Meta:
        db_table = "paquetes_destino"


class Itinerario(models.Model):
    titulo = models.CharField(max_length=150)
    paquete = models.ForeignKey(Paquete, on_delete=models.CASCADE)
    dia = models.CharField(max_length=50)
    descripcion = models.CharField(max_length=300)
    hora = models.TimeField()
    lugar = models.CharField(max_length=150)

    def __str__(self):
        return self.titulo

    class Meta:
        db_table = "itinerarios"

