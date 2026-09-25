from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema

from .serializer import TipoBusEntrada, BusEntrada, AsientoEntrada, MensajeSalida, BusConductorEntrada
from .models import Bus_Conductor, TipoBus, Bus, Asiento
from reservas.models import AsientoReserva


class TipoBusView(APIView):
    @swagger_auto_schema(
        operation_description="Listar tipos de bus"
    )
    def get(self, request):
        tipoBusLista = TipoBus.objects.all()
        lista = []
        for tipoBus in tipoBusLista:
            lista.append({
                "id": tipoBus.id,
                "nombre": tipoBus.nombre,
                "agencia_id": tipoBus.agencia_id,
                "capacidad": tipoBus.capacidad,
                "descripcion": tipoBus.descripcion,
            })
        return Response(lista)

    @swagger_auto_schema(
        operation_description="Guardar tipo de bus",
        request_body=TipoBusEntrada
    )
    def post(self, request):
        nombre = request.data.get("nombre")
        agencia_id = request.data.get("agencia_id")
        capacidad = request.data.get("capacidad")
        descripcion = request.data.get("descripcion")

        TipoBus.objects.create(
            nombre=nombre,
            agencia_id=agencia_id,
            capacidad=capacidad,
            descripcion=descripcion
        )
        return Response({"mensaje": "Tipo de bus almacenado correctamente"})


class TipoBusIdView(APIView):
    @swagger_auto_schema(
        operation_description="Actualizar Tipo de bus",
        request_body=TipoBusEntrada
    )
    def put(self, request, id):
        tipoBusB = TipoBus.objects.get(id=id)
        tipoBusB.nombre = request.data.get("nombre")
        tipoBusB.agencia_id = request.data.get("agencia_id")
        tipoBusB.capacidad = request.data.get("capacidad")
        tipoBusB.descripcion = request.data.get("descripcion")
        tipoBusB.save()
        return Response({"mensaje": "Tipo de bus actualizado"})

    @swagger_auto_schema(
        operation_description="Eliminar tipo de bus"
    )
    def delete(self, request, id):
        tipoBusEliminar = TipoBus.objects.get(id=id)
        tipoBusEliminar.delete()
        return Response({"mensaje": "Tipo de bus eliminado"})

    @swagger_auto_schema(
        operation_description="Listar tipo de bus por id"
    )
    def get(self, request, id):
        registroEncontrado = TipoBus.objects.get(id=id)
        return Response({
            "id": registroEncontrado.id,
            "nombre": registroEncontrado.nombre,
            "agencia_id": registroEncontrado.agencia_id,
            "capacidad": registroEncontrado.capacidad,
            "descripcion": registroEncontrado.descripcion,
        })


##################################################################################################
class BusView(APIView):
    @swagger_auto_schema(
        operation_description="Listar Buses"
    )
    def get(self, request):
        busLista = Bus.objects.all()
        lista = []
        for bus in busLista:
            lista.append({
                "id": bus.id,
                "placa": bus.placa,
                "agencia_id": bus.agencia_id,
                "tipo_bus_id": bus.tipo_bus_id,
                "marca": bus.marca,
                "modelo": bus.modelo,
                "estado": bus.estado,
                "fecha_registro": bus.fecha_registro,
            })
        return Response(lista)

    @swagger_auto_schema(
        operation_description="Guardar Bus",
        request_body=BusEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        placa = request.data.get("placa")
        agencia_id = request.data.get("agencia_id")
        tipo_bus_id = request.data.get("tipo_bus_id")
        marca = request.data.get("marca")
        modelo = request.data.get("modelo")
        estado = request.data.get("estado")
        fecha_registro = request.data.get("fecha_registro")

        Bus.objects.create(
            placa=placa,
            agencia_id=agencia_id,
            tipo_bus_id=tipo_bus_id,
            marca=marca,
            modelo=modelo,
            estado=estado,
            fecha_registro=fecha_registro
        )
        return Response({"mensaje": "Bus almacenado correctamente"})


class BusIdView(APIView):
    @swagger_auto_schema(
        operation_description="Listar bus por id"
    )
    def get(self, request, id):
        registroEncontrado = Bus.objects.get(id=id)
        return Response({
            "id": registroEncontrado.id,
            "placa": registroEncontrado.placa,
            "agencia_id": registroEncontrado.agencia_id,
            "tipo_bus_id": registroEncontrado.tipo_bus_id,
            "marca": registroEncontrado.marca,
            "modelo": registroEncontrado.modelo,
            "estado": registroEncontrado.estado,
            "fecha_registro": registroEncontrado.fecha_registro,
        })

    @swagger_auto_schema(
        operation_description="Actualizar bus",
        request_body=BusEntrada
    )
    def put(self, request, id):
        busB = Bus.objects.get(id=id)
        busB.placa = request.data.get("placa")
        busB.agencia_id = request.data.get("agencia_id")
        busB.tipo_bus_id = request.data.get("tipo_bus_id")
        busB.marca = request.data.get("marca")
        busB.modelo = request.data.get("modelo")
        busB.estado = request.data.get("estado")
        busB.fecha_registro = request.data.get("fecha_registro")
        busB.save()
        return Response({"mensaje": "Bus actualizado"})

    @swagger_auto_schema(
        operation_description="Eliminar bus"
    )
    def delete(self, request, id):
        busEliminar = Bus.objects.get(id=id)
        busEliminar.delete()
        return Response({"mensaje": "Bus eliminado"})


class BusPlacaView(APIView):
    @swagger_auto_schema(
        operation_description="Busca un bus por su placa"
    )
    def get(self, request, placa):
        bus = Bus.objects.filter(placa=placa).first()
        if not bus:
            return Response({"mensaje": "Bus no encontrado"})
        return Response({
            "id": bus.id,
            "placa": bus.placa,
            "agencia_id": bus.agencia_id,
            "tipo_bus_id": bus.tipo_bus_id,
            "marca": bus.marca,
            "modelo": bus.modelo,
            "estado": bus.estado,
            "fecha_registro": bus.fecha_registro,
        })
        
######################################################################################################################
class BusConductorView(APIView):
    @swagger_auto_schema(
        operation_description="Asociar un bus con un conductor",
        request_body=BusConductorEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        bus_id = request.data.get("bus_id")
        conductor_id = request.data.get("conductor_id")
        
        Bus_Conductor.objects.create(
            bus_id=bus_id,
            conductor_id=conductor_id
        )
        return Response({"mensaje": "Bus asociado con conductor correctamente"})
    
    @swagger_auto_schema(
        operation_description="Listar buses asociados a un conductor"
    )
    def get(self, request, conductor_id):
        bus_conductor_lista = Bus_Conductor.objects.filter(conductor_id=conductor_id)
        lista = []
        for bus_conductor in bus_conductor_lista:
            lista.append({
                "id": bus_conductor.id,
                "bus_id": bus_conductor.bus_id,
                "conductor_id": bus_conductor.conductor_id,
            })
        return Response(lista)

    @swagger_auto_schema(
        operation_description="Eliminar asociación de bus y conductor"
    )
    def delete(self, request, id):
        bus_conductor_eliminar = Bus_Conductor.objects.get(id=id)
        bus_conductor_eliminar.delete()
        return Response({"mensaje": "Asociación de bus y conductor eliminada"})
    
    @swagger_auto_schema(
        operation_description="Actualizar asociación de bus y conductor",
        request_body=BusConductorEntrada
    )
    def put(self, request, id):
        bus_conductor_actualizar = Bus_Conductor.objects.get(id=id)
        bus_conductor_actualizar.bus_id = request.data.get("bus_id")
        bus_conductor_actualizar.conductor_id = request.data.get("conductor_id")
        bus_conductor_actualizar.save()
        return Response({"mensaje": "Asociación de bus y conductor actualizada"})
    
##################################################################################################
class AsientoView(APIView):
    @swagger_auto_schema(
        operation_description="Listar asientos"
    )
    def get(self, request):
        asientoLista = Asiento.objects.all()
        tipo = request.query_params.get("tipo_bus_id")
        if tipo:
            asientoLista = asientoLista.filter(tipo_bus_id=tipo)
        ocupados = set(
            AsientoReserva.objects.exclude(reserva__estado="cancelada").values_list("asiento_id", flat=True)
        )
        lista = []
        for asiento in asientoLista:
            lista.append({
                "id": asiento.id,
                "tipo_bus_id": asiento.tipo_bus_id,
                "numero_asiento": asiento.numero_asiento,
                "ocupado": asiento.id in ocupados,
            })
        return Response(lista)

    @swagger_auto_schema(
        operation_description="Guardar asiento",
        request_body=AsientoEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        tipo_bus_id = request.data.get("tipo_bus_id")
        numero_asiento = request.data.get("numero_asiento")

        Asiento.objects.create(
            tipo_bus_id=tipo_bus_id,
            numero_asiento=numero_asiento
        )
        return Response({"mensaje": "Asiento almacenado correctamente"})


class AsientoIdView(APIView):
    @swagger_auto_schema(
        operation_description="Listar asiento por id"
    )
    def get(self, request, id):
        registroEncontrado = Asiento.objects.get(id=id)
        return Response({
            "id": registroEncontrado.id,
            "tipo_bus_id": registroEncontrado.tipo_bus_id,
            "numero_asiento": registroEncontrado.numero_asiento,
        })

    @swagger_auto_schema(
        operation_description="Actualizar asiento",
        request_body=AsientoEntrada
    )
    def put(self, request, id):
        asientoB = Asiento.objects.get(id=id)
        asientoB.tipo_bus_id = request.data.get("tipo_bus_id")
        asientoB.numero_asiento = request.data.get("numero_asiento")
        asientoB.save()
        return Response({"mensaje": "Asiento actualizado"})

    @swagger_auto_schema(
        operation_description="Eliminar asiento"
    )
    def delete(self, request, id):
        asientoEliminar = Asiento.objects.get(id=id)
        asientoEliminar.delete()
        return Response({"mensaje": "Asiento eliminado"})


class AsientoNumeroView(APIView):
    @swagger_auto_schema(
        operation_description="Busca asientos por número de asiento"
    )
    def get(self, request, numero_asiento):
        asientoLista = Asiento.objects.filter(numero_asiento=numero_asiento)
        lista = []
        for asiento in asientoLista:
            lista.append({
                "id": asiento.id,
                "tipo_bus_id": asiento.tipo_bus_id,
                "numero_asiento": asiento.numero_asiento,
            })
        return Response(lista)