from decimal import Decimal

from rest_framework import serializers


class MensajeSalida(serializers.Serializer):
    message = serializers.CharField(max_length=255)

    class Meta:
        ref_name = "PaquetesMensajeSalida"



class PaqueteEntrada(serializers.Serializer):
    nombre = serializers.CharField(max_length=100)
    agencia_id = serializers.IntegerField()
    descripcion = serializers.CharField(max_length=10000)
    duracion_estimada = serializers.CharField(max_length=100)
    estado = serializers.CharField(max_length=20)
    fecha_creacion = serializers.DateField()
    precio = serializers.DecimalField(max_digits=12, decimal_places=2)
    imagen = serializers.ImageField(required=False)
    destinos = serializers.CharField(
        required=False,
        help_text='Lista JSON: [{"nombre":"Guatapé","departamento":"Antioquia"}] o IDs: 1,2,3',
    )
    destino_ids = serializers.CharField(required=False)
    imagenes_destino = serializers.ImageField(required=False)


class PaqueteRegistrarEntrada(serializers.Serializer):
    nombre = serializers.CharField(max_length=150)
    agencia_id = serializers.IntegerField(required=False)
    descripcion = serializers.CharField(max_length=10000, required=False, allow_blank=True)
    duracion_estimada = serializers.CharField(max_length=50, required=False, allow_blank=True)
    estado = serializers.CharField(max_length=20, required=False)
    fecha_creacion = serializers.DateTimeField(required=False)
    precio = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    imagen = serializers.ImageField(required=False)
    destinos = serializers.CharField(
        required=False,
        help_text='Lista JSON: [{"nombre":"Guatapé","departamento":"Antioquia"}] o IDs: 1,2,3',
    )
    destino_ids = serializers.CharField(required=False)
    imagenes_destino = serializers.ImageField(required=False)


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


class PaqueteValidar(serializers.Serializer):
    """HU-W-21: lo mínimo que debe traer un paquete para guardarse (precio y duración válidos)."""
    nombre = serializers.CharField(
        max_length=150,
        error_messages={"required": "El nombre es obligatorio", "blank": "El nombre es obligatorio",
                        "null": "El nombre es obligatorio"},
    )
    agencia_id = serializers.IntegerField(
        min_value=1,
        error_messages={"required": "La agencia es obligatoria", "null": "La agencia es obligatoria",
                        "invalid": "La agencia no es válida", "min_value": "La agencia no es válida"},
    )
    duracion_estimada = serializers.CharField(
        max_length=50,
        error_messages={"required": "La duración es obligatoria", "blank": "La duración es obligatoria",
                        "null": "La duración es obligatoria", "max_length": "La duración admite máximo 50 caracteres"},
    )
    precio = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01"),
        error_messages={"required": "El precio es obligatorio", "null": "El precio es obligatorio",
                        "invalid": "El precio debe ser un número", "min_value": "El precio debe ser mayor que 0",
                        "max_digits": "El precio es demasiado grande",
                        "max_whole_digits": "El precio es demasiado grande",
                        "max_decimal_places": "El precio admite máximo 2 decimales"},
    )
