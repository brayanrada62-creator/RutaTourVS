from rest_framework import serializers


class DepartamentoSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(max_length=100)   

class MensajeSalida(serializers.Serializer):
    message = serializers.CharField(max_length=255)

    class Meta:
        ref_name = "DestinosMensajeSalida"



class DestinoEntrada(serializers.Serializer):
    nombre = serializers.CharField(max_length=150)
    departamento = serializers.CharField(max_length=100)
    descripcion = serializers.CharField(max_length=2000)


class HopedajeEntrada(serializers.Serializer):
    nombre = serializers.CharField(max_length=150)
    destino_id = serializers.IntegerField(required=False)
    destino_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    direccion = serializers.CharField(max_length=255)
    telefono = serializers.CharField(max_length=20)
    descripcion = serializers.CharField(max_length=2000)
    imagen = serializers.ImageField(required=False)


class HospedajeDestinoEntrada(serializers.Serializer):
    hospedaje_id = serializers.IntegerField()
    destino_id = serializers.IntegerField()


class ImagenEntrada(serializers.Serializer):
    url_img = serializers.ImageField(max_length=225)
    destino_id = serializers.IntegerField()
    descripcion = serializers.CharField(max_length=2000)