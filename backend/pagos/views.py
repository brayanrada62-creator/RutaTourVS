from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema

from django.shortcuts import get_object_or_404
from rest_framework import status

from .serializer import PagoEntrada, MensajeSalida
from .models import Pago
from reservas.models import Reserva
from usuarios.permisos import SoloPersonal, agencias_de, es_admin, es_super, gestiona_agencia, prohibido, usuario_de


def pagos_visibles(yo):
    """Superadmin: todos. Admin: los de su agencia. Cliente: los de sus reservas."""
    if es_super(yo):
        return Pago.objects.all()
    if es_admin(yo):
        return Pago.objects.filter(reserva__paquete__agencia_id__in=agencias_de(yo))
    return Pago.objects.filter(reserva__usuario=yo)


class PagoView(APIView):
    @swagger_auto_schema(
        operation_description="Listar pagos"
    )
    def get(self, request):
        pagoLista = pagos_visibles(usuario_de(request))
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

        yo = usuario_de(request)
        reserva = Reserva.objects.filter(id=reserva_id).select_related("paquete").first()
        if reserva is None:
            return Response({"message": "La reserva no existe"}, status=status.HTTP_404_NOT_FOUND)
        personal = gestiona_agencia(yo, reserva.paquete.agencia_id)
        if not personal and reserva.usuario_id != yo.id:
            return prohibido("Esa reserva no es tuya")
        if not personal:
            # Solo la agencia aprueba o rechaza: el pago del cliente siempre entra pendiente.
            estado, motivo_rechazo = "pendiente", ""

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
        registroEncontrado = get_object_or_404(Pago, id=id)
        yo = usuario_de(request)
        if not (registroEncontrado.reserva.usuario_id == yo.id
                or gestiona_agencia(yo, registroEncontrado.reserva.paquete.agencia_id)):
            return prohibido()
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
        pagoB = get_object_or_404(Pago, id=id)
        yo = usuario_de(request)
        if not gestiona_agencia(yo, pagoB.reserva.paquete.agencia_id):
            return prohibido("Solo la agencia puede aprobar o rechazar pagos")
        if request.data.get("reserva_id") not in (None, "", pagoB.reserva_id):
            reserva_nueva = Reserva.objects.filter(id=request.data.get("reserva_id")).select_related("paquete").first()
            if reserva_nueva is None or not gestiona_agencia(yo, reserva_nueva.paquete.agencia_id):
                return prohibido()
        pagoB.precio = request.data.get("precio", pagoB.precio)
        pagoB.reserva_id = request.data.get("reserva_id", pagoB.reserva_id)
        pagoB.fecha_pago = request.data.get("fecha_pago", pagoB.fecha_pago)
        pagoB.referencia = request.data.get("referencia", pagoB.referencia)
        if request.data.get("comprobante"):
            pagoB.comprobante = request.data.get("comprobante")
        pagoB.estado = request.data.get("estado", pagoB.estado)
        pagoB.motivo_rechazo = request.data.get("motivo_rechazo", pagoB.motivo_rechazo)
        pagoB.save()
        return Response({"mensaje": "Pago actualizado"})

    @swagger_auto_schema(
        operation_description="Eliminar pago"
    )
    def delete(self, request, id):
        pagoEliminar = get_object_or_404(Pago, id=id)
        if not gestiona_agencia(usuario_de(request), pagoEliminar.reserva.paquete.agencia_id):
            return prohibido()
        pagoEliminar.delete()
        return Response({"mensaje": "Pago eliminado"})


class PagoPrecioView(APIView):
    permission_classes = [SoloPersonal]

    @swagger_auto_schema(
        operation_description="Busca pagos por precio"
    )
    def get(self, request, precio):
        pagoLista = pagos_visibles(usuario_de(request)).filter(precio=precio)
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
    permission_classes = [SoloPersonal]

    @swagger_auto_schema(
        operation_description="Busca un pago por su referencia"
    )
    def get(self, request, referencia):
        pago = pagos_visibles(usuario_de(request)).filter(referencia=referencia).first()
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