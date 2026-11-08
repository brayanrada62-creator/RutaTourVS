from django.conf import settings
from django.core.files.storage import default_storage
from django.db import models


def almacenamiento_pdf():
    """Dónde se guardan los PDF: Cloudinary como resource_type "raw" (no son imágenes) si hay
    CLOUDINARY_URL; si no, el almacenamiento local (MEDIA_ROOT). Es una función para que la
    migración no dependa de si la variable existe en cada computador."""
    if getattr(settings, "CLOUDINARY_ACTIVO", False):
        from cloudinary_storage.storage import RawMediaCloudinaryStorage
        return RawMediaCloudinaryStorage()
    return default_storage


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
    # Desactivada: su personal no entra y sus paquetes salen del catálogo; las reservas se conservan.
    activo = models.BooleanField(default=True)
    # Cuenta donde el cliente transfiere. La app solo la muestra si tiene banco, número y titular.
    banco = models.CharField(max_length=100, blank=True, default="")
    tipo_cuenta = models.CharField(max_length=30, blank=True, default="")
    numero_cuenta = models.CharField(max_length=40, blank=True, default="")
    titular = models.CharField(max_length=150, blank=True, default="")

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = "agencia"


class Usuario(models.Model):
    nombre_completo = models.CharField(max_length=200)
    rol = models.ForeignKey(Rol, on_delete=models.PROTECT)
    tipo_documento = models.CharField(max_length=30)
    numero_documento = models.CharField(max_length=30, unique=True)
    correo = models.EmailField(max_length=150)
    telefono = models.CharField(max_length=20)
    contrasena = models.CharField(max_length=255)
    licencia = models.CharField(max_length=30, blank=True, default="")  # número de la licencia
    # Copia de la licencia del conductor en PDF (máx. 5 MB). Solo la sube y la ve el admin de su
    # agencia o el superadmin. Se guarda con nombre aleatorio para que la URL no se pueda adivinar.
    licencia_pdf = models.FileField(upload_to="licencias/", storage=almacenamiento_pdf, max_length=255,
                                    blank=True, null=True)
    # Suspensión: un usuario inactivo no puede iniciar sesión ni usar su token.
    activo = models.BooleanField(default=True)
    # Foto de perfil (JPG/PNG/WEBP, máx. 5 MB). Con CLOUDINARY_URL se guarda en la carpeta usuarios/.
    foto = models.ImageField(upload_to="usuarios/", max_length=255, blank=True, null=True)

    def __str__(self):
        return self.nombre_completo

    class Meta:
        db_table = "usuarios"
        
class UsuarioAgencia(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    agencia = models.ForeignKey(Agencia, on_delete=models.CASCADE)
    
    def __str__(self):
        return f"{self.usuario.nombre_completo} - {self.agencia.nombre}"
    class Meta:
        db_table = "usuario_agencia"


class Dispositivo(models.Model):
    """Teléfono con la app instalada: su token de Firebase para recibir notificaciones push (D1)."""
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="dispositivos")
    token = models.CharField(max_length=255, unique=True)
    plataforma = models.CharField(max_length=20, default="android")
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "dispositivos"


class VerificacionCorreo(models.Model):
    """Código de 6 dígitos enviado a un correo antes de crear la cuenta (A4). Se guarda solo su hash."""
    correo = models.EmailField(max_length=150, db_index=True)
    codigo_hash = models.CharField(max_length=64)
    creado = models.DateTimeField(auto_now_add=True)
    intentos = models.PositiveSmallIntegerField(default=0)
    verificado = models.BooleanField(default=False)

    class Meta:
        db_table = "verificar_correo"


class RecuperarContrasena(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    token_hash = models.CharField(max_length=64, unique=True)
    codigo_hash = models.CharField(max_length=64)
    creado = models.DateTimeField(auto_now_add=True)
    usado = models.BooleanField(default=False)

    class Meta:
        db_table = "recuperar_contrasena"
