from django.db import models

class Rol(models.Model):
    rol = models.CharField(max_length=50)

    def __str__(self):
        return self.rol

    class Meta:
        db_table = "roles"


class Agencia(models.Model):
    nombre = models.CharField(max_length=150)
    nit = models.CharField(max_length=30, unique=True)
    direccion = models.CharField(max_length=255)
    telefono = models.CharField(max_length=20)
    correo = models.EmailField(max_length=150)

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = "agencia"


class Usuario(models.Model):
    nombre_completo = models.CharField(max_length=200)
    agencia = models.ForeignKey(Agencia, on_delete=models.CASCADE, related_name="usuarios")
    rol = models.ForeignKey(Rol, on_delete=models.PROTECT, related_name="usuarios")
    tipo_documento = models.CharField(max_length=30)
    numero_documento = models.CharField(max_length=30, unique=True)
    correo = models.EmailField(max_length=150, unique=True)
    telefono = models.CharField(max_length=20)
    contrasena = models.CharField(max_length=255)

    def __str__(self):
        return self.nombre_completo

    class Meta:
        db_table = "usuarios"

class TipoBus(models.Model):
    nombre = models.CharField(max_length=100)
    agencia = models.ForeignKey(Agencia, on_delete=models.CASCADE, related_name="tipos_bus")
    capacidad = models.PositiveIntegerField()
    descripcion = models.TextField(blank=True, null=True)

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

    placa = models.CharField(max_length=15, unique=True)
    agencia = models.ForeignKey(Agencia, on_delete=models.CASCADE, related_name="buses")
    tipo_bus = models.ForeignKey(TipoBus, on_delete=models.PROTECT, related_name="buses")
    marca = models.CharField(max_length=100)
    modelo = models.CharField(max_length=100)
    estado = models.CharField(max_length=20, choices=ESTADOS, default="activo")
    fecha_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.placa

    class Meta:
        db_table = "buses"


class Asiento(models.Model):
    numero_asiento = models.PositiveIntegerField()
    tipo_bus = models.ForeignKey(TipoBus, on_delete=models.CASCADE, related_name="asientos")

    def __str__(self):
        return self.numero_asiento

    class Meta:
        db_table = "asientos"

class Destino(models.Model):
    nombre = models.CharField(max_length=150)
    departamento = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = "destino"


class Hospedaje(models.Model):
    destino = models.ForeignKey(Destino, on_delete=models.CASCADE, related_name="hospedajes")
    nombre = models.CharField(max_length=150)
    direccion = models.CharField(max_length=255)
    telefono = models.CharField(max_length=20)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = "hospedaje"


class SitioTuristico(models.Model):
    destino = models.ForeignKey(Destino, on_delete=models.CASCADE, related_name="sitios_turisticos")
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True, null=True)
    recomendaciones = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = "sitio_turistico"


class ImagenDestino(models.Model):
    destino = models.ForeignKey(Destino, on_delete=models.CASCADE, related_name="imagenes")
    url_img = models.ImageField(upload_to="destinos/imagenes/")
    descripcion = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"Imagen de {self.destino.nombre}"

    class Meta:
        db_table = "imagenes_destino"

class Paquete(models.Model):
    ESTADOS = [
        ("activo", "Activo"),
        ("inactivo", "Inactivo"),
        ("agotado", "Agotado"),
    ]

    agencia = models.ForeignKey(Agencia, on_delete=models.CASCADE, related_name="paquetes")
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True, null=True)
    duracion_estimada = models.CharField(max_length=50)
    estado = models.CharField(max_length=20, choices=ESTADOS, default="activo")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = "paquetes"


class PaqueteDestino(models.Model):
    paquete = models.ForeignKey(Paquete, on_delete=models.CASCADE, related_name="paquete_destinos")
    destino = models.ForeignKey(Destino, on_delete=models.CASCADE, related_name="paquete_destinos")

    def __str__(self):
        return f"{self.paquete.nombre} - {self.destino.nombre}"

    class Meta:
        db_table = "paquetes_destino"
        unique_together = ("paquete", "destino")


class Itinerario(models.Model):
    id_itinerario = models.AutoField(primary_key=True)
    paquete = models.ForeignKey(Paquete, on_delete=models.CASCADE, related_name="itinerarios")
    dia = models.PositiveIntegerField()
    titulo = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True, null=True)
    hora = models.TimeField()
    lugar = models.CharField(max_length=150)

    def __str__(self):
        return f"Día {self.dia} - {self.titulo}"

    class Meta:
        db_table = "itinerarios"

class Reserva(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="reservas")
    paquete = models.ForeignKey(Paquete, on_delete=models.PROTECT, related_name="reservas")
    fecha_reserva = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reserva #{self.id_reserva} - {self.usuario.nombre_completo}"

    class Meta:
        db_table = "reserva"


class AsientoReserva(models.Model):
    reserva = models.ForeignKey(Reserva, on_delete=models.CASCADE, related_name="asientos_reserva")
    asiento = models.ForeignKey(Asiento, on_delete=models.PROTECT, related_name="reservas_asiento")

    def __str__(self):
        return f"Reserva #{self.reserva_id} - Asiento {self.asiento.numero_asiento}"

    class Meta:
        db_table = "asientos_reserva"
        unique_together = ("reserva", "asiento")


class Categoria(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = "categoria"


class Pago(models.Model):
    ESTADOS = [
        ("pendiente", "Pendiente"),
        ("aprobado", "Aprobado"),
        ("rechazado", "Rechazado"),
    ]

    reserva = models.ForeignKey(Reserva, on_delete=models.CASCADE, related_name="pagos")
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name="pagos")
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_pago = models.DateTimeField(auto_now_add=True)
    referencia = models.CharField(max_length=100, blank=True, null=True)
    comprobante = models.FileField(upload_to="pagos/comprobantes/", blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default="pendiente")
    motivo_rechazo = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Pago #{self.id_pago} - {self.estado}"

    class Meta:
        db_table = "pagos"