from rest_framework import serializers


class MensajeSalida(serializers.Serializer):
    message = serializers.CharField(max_length=255)

    class Meta:
        ref_name = "BusesMensajeSalida"



class TipoBusEntrada(serializers.Serializer):
    nombre = serializers.CharField(max_length=100)
    agencia_id = serializers.IntegerField()
    capacidad = serializers.IntegerField()
    descripcion = serializers.CharField(max_length=300)


class BusEntrada(serializers.Serializer):
    placa = serializers.CharField(max_length=20)
    agencia_id = serializers.IntegerField(required=False, allow_null=True,
                                          help_text="Solo superadmin. Al admin se le toma de su sesión (se ignora)")
    tipo_bus_id = serializers.IntegerField(help_text="Tipo de bus de la misma agencia")
    marca = serializers.CharField(max_length=100)
    modelo = serializers.CharField(max_length=100)
    estado = serializers.ChoiceField(choices=["activo", "inactivo", "mantenimiento"], required=False,
                                     help_text="activo (por defecto), inactivo o mantenimiento")
    fecha_registro = serializers.DateField()
    conductor_id = serializers.IntegerField(required=False, allow_null=True)
    
class BusConductorEntrada(serializers.Serializer):
    bus_id = serializers.IntegerField()
    conductor_id = serializers.IntegerField()

class AsientoEntrada(serializers.Serializer):
    tipo_bus_id = serializers.IntegerField()
    numero_asiento = serializers.IntegerField()

class AsientosBusEntrada(serializers.Serializer):
    cantidad = serializers.IntegerField(
        min_value=1, max_value=100,
        help_text="Número de sillas del bus (1 a 100). Se numeran de 1 a cantidad."
    )
