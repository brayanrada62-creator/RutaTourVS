from rest_framework import serializers


class MensajeSalida(serializers.Serializer):
    message = serializers.CharField(max_length=255)

    class Meta:
        ref_name = "BusesMensajeSalida"



class TipoBusEntrada(serializers.Serializer):
    nombre = serializers.CharField(max_length=100)
    agencia_id = serializers.IntegerField(required=False, allow_null=True,
                                          help_text="Solo superadmin. Al admin se le toma de su sesión")
    capacidad = serializers.IntegerField(min_value=1, help_text="Número de sillas (mayor que 0)")
    descripcion = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class TipoBusEditarEntrada(TipoBusEntrada):
    """PUT /tipobus/<id>/: todos opcionales; los campos que no llegan se conservan."""
    nombre = serializers.CharField(max_length=100, required=False)
    capacidad = serializers.IntegerField(min_value=1, required=False)
    descripcion = serializers.CharField(max_length=300, required=False, allow_blank=True)


class BusEntrada(serializers.Serializer):
    placa = serializers.CharField(max_length=20)
    agencia_id = serializers.IntegerField(required=False, allow_null=True,
                                          help_text="Solo superadmin. Al admin se le toma de su sesión (se ignora)")
    tipo_bus_id = serializers.IntegerField(help_text="Tipo de bus de la misma agencia")
    marca = serializers.CharField(max_length=100, required=False, allow_blank=True)
    marca_id = serializers.IntegerField(required=False, allow_null=True,
                                        help_text="Marca del catálogo. Si viene, se guarda en marcaBus")
    modelo = serializers.CharField(max_length=100)
    estado = serializers.ChoiceField(choices=["activo", "inactivo", "mantenimiento"], required=False,
                                     help_text="activo (por defecto), inactivo o mantenimiento")
    fecha_registro = serializers.DateField()
    conductor_id = serializers.IntegerField(required=False, allow_null=True)
    sillas = serializers.IntegerField(required=False, min_value=1, max_value=100,
                                      help_text="Sillas del bus (1 a 100). Se guardan en su tipo de bus")
    
class BusConductorEntrada(serializers.Serializer):
    bus_id = serializers.IntegerField()
    conductor_id = serializers.IntegerField()


class BusTipoBusEntrada(serializers.Serializer):
    bus_id = serializers.IntegerField()
    tipo_bus_id = serializers.IntegerField()


class AsientoEntrada(serializers.Serializer):
    tipo_bus_id = serializers.IntegerField()
    numero_asiento = serializers.IntegerField()

class AsientosBusEntrada(serializers.Serializer):
    cantidad = serializers.IntegerField(
        min_value=1, max_value=100,
        help_text="Número de sillas del bus (1 a 100). Se numeran de 1 a cantidad."
    )


class AsientoMapaEntrada(serializers.Serializer):
    numero = serializers.IntegerField(min_value=1, max_value=100)
    fila = serializers.IntegerField(min_value=1, max_value=40)
    columna = serializers.IntegerField(min_value=1, max_value=10)
    lado = serializers.ChoiceField(choices=["izquierda", "derecha"])


class MapaAsientosEntrada(serializers.Serializer):
    """Mapa confirmado por el conductor. Se guarda en ese bus, no en un tipo compartido."""

    filas = serializers.IntegerField(min_value=1, max_value=40)
    columnas = serializers.IntegerField(min_value=1, max_value=10)
    pasillo_despues_de_columna = serializers.IntegerField(min_value=0, max_value=10)
    asientos = AsientoMapaEntrada(many=True)
