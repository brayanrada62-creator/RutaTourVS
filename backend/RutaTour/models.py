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
    agencia = models.ForeignKey(Agencia, on_delete=models.CASCADE, related_name="usuarios")
    rol = models.ForeignKey(Rol, on_delete=models.PROTECT, related_name="usuarios")
    tipo_documento = models.CharField(max_length=30)
    numero_documento = models.CharField(max_length=30, unique=True)
    correo = models.EmailField(max_length=150)
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
    agencia = models.ForeignKey(Agencia, on_delete=models.CASCADE, related_name="buses")
    tipo_bus = models.ForeignKey(TipoBus, on_delete=models.PROTECT, related_name="buses")
    marca = models.CharField(max_length=100)
    modelo = models.CharField(max_length=100)
    estado = models.CharField(max_length=20, default="activo")
    fecha_registro = models.DateTimeField()

    def __str__(self):
        return self.placa

    class Meta:
        db_table = "buses"


class Asiento(models.Model):
    numero_asiento = models.IntegerField()
    tipo_bus = models.ForeignKey(TipoBus, on_delete=models.CASCADE, related_name="asientos")

    def __str__(self):
        return str(self.numero_asiento)

    class Meta:
        db_table = "asientos"

class Destino(models.Model):
    nombre = models.CharField(max_length=150)
    departamento = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=300)

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = "destino"


class Hospedaje(models.Model):
    nombre = models.CharField(max_length=150)
    destino = models.ForeignKey(Destino, on_delete=models.CASCADE, related_name="hospedajes")
    direccion = models.CharField(max_length=255)
    telefono = models.CharField(max_length=20)
    descripcion = models.CharField(max_length=300)

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = "hospedaje"


class SitioTuristico(models.Model):
    destino = models.ForeignKey(Destino, on_delete=models.CASCADE, related_name="sitios_turisticos")
    nombre = models.CharField(max_length=150)
    descripcion = models.CharField(max_length=300)
    recomendaciones = models.CharField(max_length=300)

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = "sitio_turistico"


class ImagenDestino(models.Model):
    url_img = models.ImageField(max_length=255)
    destino = models.ForeignKey(Destino, on_delete=models.CASCADE, related_name="imagenes")
    descripcion = models.CharField(max_length=255)

    def __str__(self):
        return self.url_img

    class Meta:
        db_table = "imagenes_destino"

class Paquete(models.Model):
    ESTADOS = [
        ("activo", "Activo"),
        ("inactivo", "Inactivo"),
        ("agotado", "Agotado"),
    ]

    nombre = models.CharField(max_length=150)
    agencia = models.ForeignKey(Agencia, on_delete=models.CASCADE, related_name="paquetes")
    descripcion = models.CharField(max_length=300)
    duracion_estimada = models.CharField(max_length=50)
    estado = models.CharField(max_length=20, default="activo")
    fecha_creacion = models.DateTimeField()

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

class Itinerario(models.Model):
    titulo = models.CharField(max_length=150)
    paquete = models.ForeignKey(Paquete, on_delete=models.CASCADE, related_name="itinerarios")
    dia = models.CharField(max_length=50)
    descripcion = models.CharField(max_length=300)
    hora = models.TimeField()
    lugar = models.CharField(max_length=150)

    def __str__(self):
        return self.titulo

    class Meta:
        db_table = "itinerarios"

class Reserva(models.Model):
    fecha_reserva = models.DateTimeField()
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="reservas")
    paquete = models.ForeignKey(Paquete, on_delete=models.PROTECT, related_name="reservas")

    def __str__(self):
        return self.fecha_reserva

    class Meta:
        db_table = "reserva"

class AsientoReserva(models.Model):
    reserva = models.ForeignKey(Reserva, on_delete=models.CASCADE, related_name="asientos_reserva")
    asiento = models.ForeignKey(Asiento, on_delete=models.PROTECT, related_name="reservas_asiento")

    def __str__(self):
        return f"Reserva #{self.reserva_id} - Asiento {self.asiento.numero_asiento}"

    class Meta:
        db_table = "asientos_reserva"

class Categoria(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=255)

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

    precio = models.DecimalField(max_digits=10, decimal_places=2)
    reserva = models.ForeignKey(Reserva, on_delete=models.CASCADE, related_name="pagos")
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name="pagos")
    fecha_pago = models.DateTimeField()
    referencia = models.ImageField(max_length=100)
    comprobante = models.CharField(max_length=255)
    estado = models.CharField(max_length=20, default="pendiente")
    motivo_rechazo = models.CharField(max_length=255)

    def __str__(self):
        return self.precio

    class Meta:
        db_table = "pagos"