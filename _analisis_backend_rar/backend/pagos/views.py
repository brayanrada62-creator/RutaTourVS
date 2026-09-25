from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema

from .serializer import PagoEntrada, MensajeSalida
from .models import Pago


class PagoView(APIView):
    @swagger_auto_schema(
        operation_description="Listar pagos"
    )
    def get(self, request):
        pagoLista = Pago.objects.all()
        lista = []
        for pago in pagoLista:
            lista.append({
                "id": pago.id,
                "precio": pago.precio,
                "reserva_id": pago.reserva_id,
                "fecha_pago": pago.fecha_pago,
                "referencia": pago.referencia,
                "comprobante": pago.comprobante.url if pago.comprobante else None,
                "estado": pago.estado,
                "motivo_rechazo": pago.motivo_rechazo,
            })
        return Response(lista)

    @swagger_auto_schema(
        operation_description="Guardar pago",
        request_body=PagoEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        precio = request.data.get("precio")
        reserva_id = request.data.get("reserva_id")
        fecha_pago = request.data.get("fecha_pago")
        referencia = request.data.get("referencia")
        comprobante = request.data.get("comprobante")
        estado = request.data.get("estado")
        motivo_rechazo = request.data.get("motivo_rechazo")

        Pago.objects.create(
            precio=precio,
            reserva_id=reserva_id,
            fecha_pago=fecha_pago,
            referencia=referencia,
            comprobante=comprobante,
            estado=estado,
            motivo_rechazo=motivo_rechazo
        )
        return Response({"mensaje": "Pago almacenado correctamente"})


class PagoIdView(APIView):
    @swagger_auto_schema(
        operation_description="Listar pago por id"
    )
    def get(self, request, id):
        registroEncontrado = Pago.objects.get(id=id)
        return Response({
            "id": registroEncontrado.id,
            "precio": registroEncontrado.precio,
            "reserva_id": registroEncontrado.reserva_id,
            "fecha_pago": registroEncontrado.fecha_pago,
            "referencia": registroEncontrado.referencia,
            "comprobante": registroEncontrado.comprobante.url if registroEncontrado.comprobante else None,
            "estado": registroEncontrado.estado,
            "motivo_rechazo": registroEncontrado.motivo_rechazo,
        })

    @swagger_auto_schema(
        operation_description="Actualizar pago",
        request_body=PagoEntrada
    )
    def put(self, request, id):
        pagoB = Pago.objects.get(id=id)
        pagoB.precio = request.data.get("precio")
        pagoB.reserva_id = request.data.get("reserva_id")
        pagoB.fecha_pago = request.data.get("fecha_pago")
        pagoB.referencia = request.data.get("referencia")
        if request.data.get("comprobante"):
            pagoB.comprobante = request.data.get("comprobante")
        pagoB.estado = request.data.get("estado")
        pagoB.motivo_rechazo = request.data.get("motivo_rechazo")
        pagoB.save()
        return Response({"mensaje": "Pago actualizado"})

    @swagger_auto_schema(
        operation_description="Eliminar pago"
    )
    def delete(self, request, id):
        pagoEliminar = Pago.objects.get(id=id)
        pagoEliminar.delete()
        return Response({"mensaje": "Pago eliminado"})


class PagoPrecioView(APIView):
    @swagger_auto_schema(
        operation_description="Busca pagos por precio"
    )
    def get(self, request, precio):
        pagoLista = Pago.objects.filter(precio=precio)
        lista = []
        for pago in pagoLista:
            lista.append({
                "id": pago.id,
                "precio": pago.precio,
                "reserva_id": pago.reserva_id,
                "fecha_pago": pago.fecha_pago,
                "referencia": pago.referencia,
                "comprobante": pago.comprobante.url if pago.comprobante else None,
                "estado": pago.estado,
                "motivo_rechazo": pago.motivo_rechazo,
            })
        return Response(lista)


class PagoReferenciaView(APIView):
    @swagger_auto_schema(
        operation_description="Busca un pago por su referencia"
    )
    def get(self, request, referencia):
        pago = Pago.objects.filter(referencia=referencia).first()
        if not pago:
            return Response({"mensaje": "Pago no encontrado"}, status=404)
        return Response({
            "id": pago.id,
            "precio": pago.precio,
            "reserva_id": pago.reserva_id,
            "fecha_pago": pago.fecha_pago,
            "referencia": pago.referencia,
            "comprobante": pago.comprobante.url if pago.comprobante else None,
            "estado": pago.estado,
            "motivo_rechazo": pago.motivo_rechazo,
        })