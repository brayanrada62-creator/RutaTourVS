from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema

from .serializer import (
    PaqueteEntrada, PaqueteDestinoEntrada, ItinerarioEntrada, MensajeSalida
)
from .models import Paquete, PaqueteDestino, Itinerario


def paquete_json(paquete):
    return {
        "id": paquete.id,
        "nombre": paquete.nombre,
        "agencia_id": paquete.agencia_id,
        "descripcion": paquete.descripcion,
        "duracion_estimada": paquete.duracion_estimada,
        "estado": paquete.estado,
        "fecha_creacion": paquete.fecha_creacion,
        "precio": str(paquete.precio),
    }

class PaqueteView(APIView):
    @swagger_auto_schema(
        operation_description="Listar paquetes"
    )
    def get(self, request):
        paqueteLista = Paquete.objects.all()
        lista = []
        for paquete in paqueteLista:
            lista.append(paquete_json(paquete))
        return Response(lista)

    @swagger_auto_schema(
        operation_description="Guardar paquete",
        request_body=PaqueteEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        nombre = request.data.get("nombre")
        agencia_id = request.data.get("agencia_id")
        descripcion = request.data.get("descripcion")
        duracion_estimada = request.data.get("duracion_estimada")
        estado = request.data.get("estado")
        fecha_creacion = request.data.get("fecha_creacion")

        Paquete.objects.create(
            nombre=nombre,
            agencia_id=agencia_id,
            descripcion=descripcion,
            duracion_estimada=duracion_estimada,
            estado=estado,
            fecha_creacion=fecha_creacion,
            precio=request.data.get("precio") or 0
        )
        return Response({"mensaje": "Paquete almacenado correctamente"})


class PaqueteIdView(APIView):
    @swagger_auto_schema(
        operation_description="Listar paquete por id"
    )
    def get(self, request, id):
        registroEncontrado = Paquete.objects.get(id=id)
        return Response(paquete_json(registroEncontrado))

    @swagger_auto_schema(
        operation_description="Actualizar paquete",
        request_body=PaqueteEntrada
    )
    def put(self, request, id):
        paqueteB = Paquete.objects.get(id=id)
        paqueteB.nombre = request.data.get("nombre")
        paqueteB.agencia_id = request.data.get("agencia_id")
        paqueteB.descripcion = request.data.get("descripcion")
        paqueteB.duracion_estimada = request.data.get("duracion_estimada")
        paqueteB.estado = request.data.get("estado")
        paqueteB.fecha_creacion = request.data.get("fecha_creacion")
        paqueteB.save()
        return Response({"mensaje": "Paquete actualizado"})

    @swagger_auto_schema(
        operation_description="Eliminar paquete"
    )
    def delete(self, request, id):
        paqueteEliminar = Paquete.objects.get(id=id)
        paqueteEliminar.delete()
        return Response({"mensaje": "Paquete eliminado"})


class PaqueteDescripcionView(APIView):
    @swagger_auto_schema(
        operation_description="Busca paquetes por descripción"
    )
    def get(self, request, descripcion):
        paqueteLista = Paquete.objects.filter(descripcion__icontains=descripcion)
        lista = []
        for paquete in paqueteLista:
            lista.append({
                "id": paquete.id,
                "nombre": paquete.nombre,
                "agencia_id": paquete.agencia_id,
                "descripcion": paquete.descripcion,
                "duracion_estimada": paquete.duracion_estimada,
                "estado": paquete.estado,
                "fecha_creacion": paquete.fecha_creacion,
            })
        return Response(lista)


class PaqueteNombreView(APIView):
    @swagger_auto_schema(
        operation_description="Busca paquetes por nombre"
    )
    def get(self, request, nombre):
        paqueteLista = Paquete.objects.filter(nombre__icontains=nombre)
        lista = []
        for paquete in paqueteLista:
            lista.append({
                "id": paquete.id,
                "nombre": paquete.nombre,
                "agencia_id": paquete.agencia_id,
                "descripcion": paquete.descripcion,
                "duracion_estimada": paquete.duracion_estimada,
                "estado": paquete.estado,
                "fecha_creacion": paquete.fecha_creacion,
            })
        return Response(lista)


##################################################################################################
class PaqueteDestinoView(APIView):
    @swagger_auto_schema(
        operation_description="Listar relaciones paquete-destino"
    )
    def get(self, request):
        relLista = PaqueteDestino.objects.all()
        lista = []
        for rel in relLista:
            lista.append({
                "id": rel.id,
                "paquete_id": rel.paquete_id,
                "destino_id": rel.destino_id,
            })
        return Response(lista)

    @swagger_auto_schema(
        operation_description="Guardar relacion paquete-destino",
        request_body=PaqueteDestinoEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        paquete_id = request.data.get("paquete_id")
        destino_id = request.data.get("destino_id")

        PaqueteDestino.objects.create(
            paquete_id=paquete_id,
            destino_id=destino_id
        )
        return Response({"mensaje": "Relacion paquete-destino almacenada correctamente"})


class PaqueteDestinoIdView(APIView):
    @swagger_auto_schema(
        operation_description="Listar relacion paquete-destino por id"
    )
    def get(self, request, id):
        registroEncontrado = PaqueteDestino.objects.get(id=id)
        return Response({
            "id": registroEncontrado.id,
            "paquete_id": registroEncontrado.paquete_id,
            "destino_id": registroEncontrado.destino_id,
        })

    @swagger_auto_schema(
        operation_description="Actualizar relacion paquete-destino",
        request_body=PaqueteDestinoEntrada
    )
    def put(self, request, id):
        relB = PaqueteDestino.objects.get(id=id)
        relB.paquete_id = request.data.get("paquete_id")
        relB.destino_id = request.data.get("destino_id")
        relB.save()
        return Response({"mensaje": "Relacion paquete-destino actualizada"})

    @swagger_auto_schema(
        operation_description="Eliminar relacion paquete-destino"
    )
    def delete(self, request, id):
        relEliminar = PaqueteDestino.objects.get(id=id)
        relEliminar.delete()
        return Response({"mensaje": "Relacion paquete-destino eliminada"})


##################################################################################################
class ItinerarioView(APIView):
    @swagger_auto_schema(
        operation_description="Listar itinerarios"
    )
    def get(self, request):
        itinerarioLista = Itinerario.objects.all()
        lista = []
        for itinerario in itinerarioLista:
            lista.append({
                "id": itinerario.id,
                "titulo": itinerario.titulo,
                "paquete_id": itinerario.paquete_id,
                "dia": itinerario.dia,
                "descripcion": itinerario.descripcion,
                "hora": itinerario.hora,
                "lugar": itinerario.lugar,
            })
        return Response(lista)

    @swagger_auto_schema(
        operation_description="Guardar itinerario",
        request_body=ItinerarioEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        titulo = request.data.get("titulo")
        paquete_id = request.data.get("paquete_id")
        dia = request.data.get("dia")
        descripcion = request.data.get("descripcion")
        hora = request.data.get("hora")
        lugar = request.data.get("lugar")

        Itinerario.objects.create(
            titulo=titulo,
            paquete_id=paquete_id,
            dia=dia,
            descripcion=descripcion,
            hora=hora,
            lugar=lugar
        )
        return Response({"mensaje": "Itinerario almacenado correctamente"})


class ItinerarioIdView(APIView):
    @swagger_auto_schema(
        operation_description="Listar itinerario por id"
    )
    def get(self, request, id):
        registroEncontrado = Itinerario.objects.get(id=id)
        return Response({
            "id": registroEncontrado.id,
            "titulo": registroEncontrado.titulo,
            "paquete_id": registroEncontrado.paquete_id,
            "dia": registroEncontrado.dia,
            "descripcion": registroEncontrado.descripcion,
            "hora": registroEncontrado.hora,
            "lugar": registroEncontrado.lugar,
        })

    @swagger_auto_schema(
        operation_description="Actualizar itinerario",
        request_body=ItinerarioEntrada
    )
    def put(self, request, id):
        itinerarioB = Itinerario.objects.get(id=id)
        itinerarioB.titulo = request.data.get("titulo")
        itinerarioB.paquete_id = request.data.get("paquete_id")
        itinerarioB.dia = request.data.get("dia")
        itinerarioB.descripcion = request.data.get("descripcion")
        itinerarioB.hora = request.data.get("hora")
        itinerarioB.lugar = request.data.get("lugar")
        itinerarioB.save()
        return Response({"mensaje": "Itinerario actualizado"})

    @swagger_auto_schema(
        operation_description="Eliminar itinerario"
    )
    def delete(self, request, id):
        itinerarioEliminar = Itinerario.objects.get(id=id)
        itinerarioEliminar.delete()
        return Response({"mensaje": "Itinerario eliminado"})


class ItinerarioTituloView(APIView):
    @swagger_auto_schema(
        operation_description="Busca itinerarios por título"
    )
    def get(self, request, titulo):
        itinerarioLista = Itinerario.objects.filter(titulo__icontains=titulo)
        lista = []
        for itinerario in itinerarioLista:
            lista.append({
                "id": itinerario.id,
                "titulo": itinerario.titulo,
                "paquete_id": itinerario.paquete_id,
                "dia": itinerario.dia,
                "descripcion": itinerario.descripcion,
                "hora": itinerario.hora,
                "lugar": itinerario.lugar,
            })
        return Response(lista)



class ItinerarioLugarView(APIView):
    @swagger_auto_schema(
        operation_description="Busca itinerarios por lugar"
    )
    def get(self, request, lugar):
        itinerarioLista = Itinerario.objects.filter(lugar__icontains=lugar)
        lista = []
        for itinerario in itinerarioLista:
            lista.append({
                "id": itinerario.id,
                "titulo": itinerario.titulo,
                "paquete_id": itinerario.paquete_id,
                "dia": itinerario.dia,
                "descripcion": itinerario.descripcion,
                "hora": itinerario.hora,
                "lugar": itinerario.lugar,
            })
        return Response(lista)