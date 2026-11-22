from rest_framework import serializers

class PlanEntrada(serializers.Serializer):
    nombre = serializers.CharField(max_length=100)
    descripcion = serializers.CharField(max_length=500, required=False, allow_blank=True)
    maximo_agencias = serializers.IntegerField(allow_null=True, required=False)
    maximo_paquetes = serializers.IntegerField(allow_null=True, required=False)
    maximo_buses = serializers.IntegerField(allow_null=True, required=False)
    maximo_administradores = serializers.IntegerField(allow_null=True, required=False)
    id_agencia = serializers.IntegerField(required=False, allow_null=True)
    periodo = serializers.ChoiceField(choices=[('mensual', 'Mensual'), ('trimestral', 'Trimestral'), ('anual', 'Anual')], required=False, allow_null=True)
    vencimiento = serializers.DateField(required=False, allow_null=True)
    estado = serializers.ChoiceField(choices=[('activo', 'Activo'), ('inactivo', 'Inactivo')], required=False, allow_null=True)