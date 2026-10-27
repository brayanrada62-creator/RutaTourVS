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
    descripcion = models.CharField(max_length=300)

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = "destino"


class Hospedaje(models.Model):
    nombre = models.CharField(max_length=150)
    destino = models.ForeignKey(Destino, on_delete=models.CASCADE)
    direccion = models.CharField(max_length=255)
    telefono = models.CharField(max_length=20)
    descripcion = models.CharField(max_length=300)
    # Agencia dueña del hospedaje (vacía = hospedaje anterior, sin dueño asignado).
    agencia = models.ForeignKey("usuarios.Agencia", on_delete=models.SET_NULL, null=True, blank=True)
    imagen = models.ImageField(upload_to="hospedajes/", max_length=255, blank=True, null=True)

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = "hospedaje"


class SitioTuristico(models.Model):
    destino = models.ForeignKey(Destino, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=150)
    descripcion = models.CharField(max_length=300)
    recomendaciones = models.CharField(max_length=300)

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = "sitio_turistico"


class ImagenDestino(models.Model):
    url_img = models.ImageField(upload_to="destinos/", max_length=255)
    destino = models.ForeignKey(Destino, on_delete=models.CASCADE)
    descripcion = models.CharField(max_length=255)

    def __str__(self):
        return self.descripcion

    class Meta:
        db_table = "imagenes_destino"