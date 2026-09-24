from django.db import models


class Rol(models.Model):
    rol = models.CharField(max_length=50)

    def __str__(self):
        return self.rol

    class Meta:
        db_table = "roles"


class Agencia(models.Model):
    nombre = models.CharField(max_length=150)
    nit = models.CharField(max_length=30)
    direccion = models.CharField(max_length=255)
    telefono = models.CharField(max_length=20)
    correo = models.EmailField(max_length=150)

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = "agencia"


class Usuario(models.Model):
    nombre_completo = models.CharField(max_length=200)
    agencia = models.ForeignKey(
        Agencia,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    rol = models.ForeignKey(Rol, on_delete=models.PROTECT)
    tipo_documento = models.CharField(max_length=30)
    numero_documento = models.CharField(max_length=30, unique=True)
    correo = models.EmailField(max_length=150)
    telefono = models.CharField(max_length=20)
    contrasena = models.CharField(max_length=255)
    licencia = models.CharField(max_length=30, blank=True, default="")

    def __str__(self):
        return self.nombre_completo

    class Meta:
        db_table = "usuarios"