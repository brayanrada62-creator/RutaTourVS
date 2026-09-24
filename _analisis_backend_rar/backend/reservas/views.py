from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema

from .serializer import ReservaEntrada, AsientoReservaEntrada, MensajeSalida
from .models import Reserva, AsientoReserva


class ReservaView(APIView):
    @swagger_auto_schema(
        operation_description="Listar reservas"
    )
    def get(self, request):
        reservaLista = Reserva.objects.all()
        lista = []
        for reserva in reservaLista:
            lista.append({
                "id": reserva.id,
                "fecha_reserva": reserva.fecha_reserva,
                "usuario_id": reserva.usuario_id,
                "paquete_id": reserva.paquete_id,
            })
        return Response(lista)

    @swagger_auto_schema(
        operation_description="Guardar reserva",
        request_body=ReservaEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        fecha_reserva = request.data.get("fecha_reserva")
        usuario_id = request.data.get("usuario_id")
        paquete_id = request.data.get("paquete_id")

        Reserva.objects.create(
            fecha_reserva=fecha_reserva,
            usuario_id=usuario_id,
            paquete_id=paquete_id
        )
        return Response({"mensaje": "Reserva almacenada correctamente"})


class ReservaIdView(APIView):
    @swagger_auto_schema(
        operation_description="Listar reserva por id"
    )
    def get(self, request, id):
        registroEncontrado = Reserva.objects.get(id=id)
        return Response({
            "id": registroEncontrado.id,
            "fecha_reserva": registroEncontrado.fecha_reserva,
            "usuario_id": registroEncontrado.usuario_id,
            "paquete_id": registroEncontrado.paquete_id,
        })

    @swagger_auto_schema(
        operation_description="Actualizar reserva",
        request_body=ReservaEntrada
    )
    def put(self, request, id):
        reservaB = Reserva.objects.get(id=id)
        reservaB.fecha_reserva = request.data.get("fecha_reserva")
        reservaB.usuario_id = request.data.get("usuario_id")
        reservaB.paquete_id = request.data.get("paquete_id")
        reservaB.save()
        return Response({"mensaje": "Reserva actualizada"})

    @swagger_auto_schema(
        operation_description="Eliminar reserva"
    )
    def delete(self, request, id):
        reservaEliminar = Reserva.objects.get(id=id)
        reservaEliminar.delete()
        return Response({"mensaje": "Reserva eliminada"})


class ReservaFechaView(APIView):
    @swagger_auto_schema(
        operation_description="Busca reservas por fecha"
    )
    def get(self, request, fecha_reserva):
        reservaLista = Reserva.objects.filter(fecha_reserva=fecha_reserva)
        lista = []
        for reserva in reservaLista:
            lista.append({
                "id": reserva.id,
                "fecha_reserva": reserva.fecha_reserva,
                "usuario_id": reserva.usuario_id,
                "paquete_id": reserva.paquete_id,
            })
        return Response(lista)


class ReservaUsuarioView(APIView):
    @swagger_auto_schema(
        operation_description="Busca reservas por usuario"
    )
    def get(self, request, usuario_id):
        reservaLista = Reserva.objects.filter(usuario_id=usuario_id)
        lista = []
        for reserva in reservaLista:
            lista.append({
                "id": reserva.id,
                "fecha_reserva": reserva.fecha_reserva,
                "usuario_id": reserva.usuario_id,
                "paquete_id": reserva.paquete_id,
            })
        return Response(lista)


##################################################################################################
class AsientoReservaView(APIView):
    @swagger_auto_schema(
        operation_description="Listar asientos reservados"
    )
    def get(self, request):
        asientoReservaLista = AsientoReserva.objects.all()
        lista = []
        for ar in asientoReservaLista:
            lista.append({
                "id": ar.id,
                "asiento_id": ar.asiento_id,
                "reserva_id": ar.reserva_id,
            })
        return Response(lista)

    @swagger_auto_schema(
        operation_description="Guardar asiento reservado",
        request_body=AsientoReservaEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        asiento_id = request.data.get("asiento_id")
        reserva_id = request.data.get("reserva_id")

        AsientoReserva.objects.create(
            asiento_id=asiento_id,
            reserva_id=reserva_id
        )
        return Response({"mensaje": "Asiento reservado correctamente"})


class AsientoReservaIdView(APIView):
    @swagger_auto_schema(
        operation_description="Listar asiento reservado por id"
    )
    def get(self, request, id):
        registroEncontrado = AsientoReserva.objects.get(id=id)
        return Response({
            "id": registroEncontrado.id,
            "asiento_id": registroEncontrado.asiento_id,
            "reserva_id": registroEncontrado.reserva_id,
        })

    @swagger_auto_schema(
        operation_description="Actualizar asiento reservado",
        request_body=AsientoReservaEntrada
    )
    def put(self, request, id):
        arB = AsientoReserva.objects.get(id=id)
        arB.asiento_id = request.data.get("asiento_id")
        arB.reserva_id = request.data.get("reserva_id")
        arB.save()
        return Response({"mensaje": "Asiento reservado actualizado"})

    @swagger_auto_schema(
        operation_description="Eliminar asiento reservado"
    )
    def delete(self, request, id):
        arEliminar = AsientoReserva.objects.get(id=id)
        arEliminar.delete()
        return Response({"mensaje": "Asiento reservado eliminado"})