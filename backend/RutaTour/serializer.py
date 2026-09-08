from rest_framework import serializers


class loginSerializer(serializers.Serializer):
    correo = serializers.EmailField()
    contrasena = serializers.CharField(max_length=100)
    
class UsuarioEntrada(serializers.Serializer):
    nombre_completo = serializers.CharField(max_length=200)
    agencia_id = serializers.IntegerField()
    rol_id = serializers.IntegerField()
    tipo_documento = serializers.CharField(max_length=30)
    numero_documento = serializers.CharField(max_length=30)
    correo = serializers.EmailField(max_length=150)
    telefono = serializers.CharField(max_length=20)
    contrasena = serializers.CharField(max_length=255)
    
class AgenciaEntrada(serializers.Serializer):
    nombre = serializers.CharField(max_length=150)
    nit = serializers.CharField(max_length=30)
    direccion = serializers.CharField(max_length=255)
    telefono = serializers.CharField(max_length=20)
    correo = serializers.EmailField(max_length=150)
    
class TipoBusEntrada(serializers.Serializer):
    nombre = serializers.CharField(max_length=100)
    agencia_id = serializers.IntegerField()
    capacidad = serializers.IntegerField()
    descripcion = serializers.CharField(max_length=300)
    
class BusEntrada(serializers.Serializer):
    placa = serializers.CharField(max_length=20)
    agencia_id = serializers.IntegerField()
    tipo_bus_id = serializers.IntegerField()
    marca = serializers.CharField(max_length=100)
    modelo = serializers.CharField(max_length=100)
    estado = serializers.CharField(max_length=20)
    fecha_registro = serializers.DateField()
    
class AsientoEntrada(serializers.Serializer):
    bus_id = serializers.IntegerField()
    numero_asiento = serializers.IntegerField()
    
class DestinoEntrada(serializers.Serializer):
    nombre = serializers.CharField(max_length=100)
    departamento = serializers.CharField(max_length=100)
    descripcion = serializers.CharField(max_length=300)

class HopedajeEntrada(serializers.Serializer):
    nombre = serializers.CharField(max_length=100)
    destino_id = serializers.IntegerField()
    direccion = serializers.CharField(max_length=255)
    telefono = serializers.CharField(max_length=20)
    descripcion = serializers.CharField(max_length=300)
    
class SitioTuristicoEntrada(serializers.Serializer):
    nombre = serializers.CharField(max_length=100)
    destino_id = serializers.IntegerField()
    descripcion = serializers.CharField(max_length=300)
    recomendaciones = serializers.CharField(max_length=300)
    
class ImagenEntrada(serializers.Serializer):
    url_img = serializers.ImageField(max_length=225)
    destino_id = serializers.IntegerField()
    descripcion = serializers.CharField(max_length=300)
    
class PaqueteEntrada(serializers.Serializer):
    nombre = serializers.CharField(max_length=100)
    agencia_id = serializers.IntegerField()
    descripcion = serializers.CharField(max_length=300)
    duracion_estimada = serializers.CharField(max_length=100)
    estado = serializers.CharField(max_length=20)
    fecha_creacion = serializers.DateField()
    
class PaqueteDestinoEntrada(serializers.Serializer):
    paquete_id = serializers.IntegerField()
    destino_id = serializers.IntegerField()
    
class ItinerarioEntrada(serializers.Serializer):
    titulo = serializers.CharField(max_length=100)
    paquete_id = serializers.IntegerField()
    dia = serializers.IntegerField()
    descripcion = serializers.CharField(max_length=300)
    hora = serializers.TimeField()
    lugar = serializers.CharField(max_length=100)
    
class ReservaEntrada(serializers.Serializer):
    fecha_reserva = serializers.DateField()
    usuario_id = serializers.IntegerField()
    paquete_id = serializers.IntegerField()
    
class AsientoReservaEntrada(serializers.Serializer):
    asiento_id = serializers.IntegerField()
    reserva_id = serializers.IntegerField()
    
class PagoEntrada(serializers.Serializer):
    precio = serializers.DecimalField(max_digits=10, decimal_places=2)
    reserva_id = serializers.IntegerField()
    fecha_pago = serializers.DateField()
    referencia = serializers.CharField(max_length=100)
    comprobante = serializers.FileField()
    estado = serializers.CharField(max_length=20)
    motivo_rechazo = serializers.CharField(max_length=255)

class MensajeSalida(serializers.Serializer):
    message = serializers.CharField(max_length=255)