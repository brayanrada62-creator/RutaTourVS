from django.db import models



class Departamento(models.Model):
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = "departamento"
        
class Destino(models.Model):
    nombre = models.CharField(max_length=150)
    departamento = models.ForeignKey(Departamento, on_delete=models.CASCADE)
    descripcion = models.CharField(max_length=2000)

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = "destino"


class Hospedaje(models.Model):
    nombre = models.CharField(max_length=150)
    destinos = models.ManyToManyField(Destino, through="HospedajeDestino", related_name="hospedajes")
    direccion = models.CharField(max_length=255)
    telefono = models.CharField(max_length=20)
    descripcion = models.CharField(max_length=2000)
    imagen = models.ImageField(upload_to="hospedajes/", max_length=255, blank=True, null=True)

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = "hospedaje"


class HospedajeDestino(models.Model):
    hospedaje = models.ForeignKey(Hospedaje, on_delete=models.CASCADE)
    destino = models.ForeignKey(Destino, on_delete=models.CASCADE)

    class Meta:
        db_table = "hospedaje_destino"
        constraints = [
            models.UniqueConstraint(fields=["hospedaje", "destino"], name="hospedaje_destino_unico"),
        ]


class ImagenDestino(models.Model):
    url_img = models.ImageField(upload_to="destinos/", max_length=255)
    destino = models.ForeignKey(Destino, on_delete=models.CASCADE)
    descripcion = models.CharField(max_length=2000)

    def __str__(self):
        return self.descripcion

    class Meta:
        db_table = "imagenes_destino"