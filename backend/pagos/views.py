from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Q
from drf_yasg.utils import swagger_auto_schema

from django.shortcuts import get_object_or_404
from django.utils import timezone
from PIL import Image
from rest_framework import status

from .serializer import PagoEntrada, MensajeSalida
from .models import Pago
from reservas.models import AsientoReserva, Reserva
from reservas.views import codigo_reserva, total_reserva
from usuarios.paginacion import PARAMETROS_LISTA, paginar, texto_busqueda
from usuarios.permisos import SoloPersonal, agencias_de, es_admin, es_super, gestiona_agencia, prohibido, usuario_de


COMPROBANTE_MAX_BYTES = 5 * 1024 * 1024
FORMATOS_COMPROBANTE = {"JPEG", "PNG", "WEBP"}


def error_comprobante(archivo):
    """Mensaje de error si el archivo no es una imagen JPG, PNG o WEBP de máximo 5 MB; None si sirve.
    Se revisa el contenido con Pillow: cambiarle la extensión a un PDF no basta."""
    if archivo.size > COMPROBANTE_MAX_BYTES:
        return "El comprobante supera 5 MB"
    try:
        with Image.open(archivo) as foto:
            formato = foto.format
            foto.verify()
    except Exception:
        formato = None
    archivo.seek(0)
    if formato not in FORMATOS_COMPROBANTE:
        return "El comprobante debe ser una imagen JPG, PNG o WEBP"
    return None


def pagos_visibles(yo):
    """Superadmin: todos. Admin: los de su agencia. Cliente: los de sus reservas."""
    if es_super(yo):
        qs = Pago.objects.all()
    elif es_admin(yo):
        qs = Pago.objects.filter(reserva__paquete__agencia_id__in=agencias_de(yo))
    else:
        qs = Pago.objects.filter(reserva__usuario=yo)
    # Una sola consulta: así el cliente y el paquete no se piden con otros endpoints.
    return qs.select_related("reserva__usuario", "reserva__paquete")


def pago_json(pago):
    return {
        "id": pago.id,
        "precio": pago.precio,
        "reserva_id": pago.reserva_id,
        "fecha_pago": pago.fecha_pago,
        "referencia": pago.referencia,
        "comprobante": pago.comprobante.url if pago.comprobante else None,
        "estado": pago.estado,
        "motivo_rechazo": pago.motivo_rechazo,
        "cliente": pago.reserva.usuario.nombre_completo,
        "correo": pago.reserva.usuario.correo,
        "paquete": pago.reserva.paquete.nombre,
        "codigo": codigo_reserva(pago.reserva_id),
    }


class PagoView(APIView):
    @swagger_auto_schema(
        operation_description=(
            "Listar pagos con cliente, correo, paquete y código de la reserva. "
            "Opcional: ?search=, ?page= y ?page_size="
        ),
        manual_parameters=PARAMETROS_LISTA,
    )
    def get(self, request):
        pagoLista = pagos_visibles(usuario_de(request))
        texto = texto_busqueda(request)
        if texto:
            pagoLista = pagoLista.filter(
                Q(referencia__icontains=texto)
                | Q(reserva__usuario__nombre_completo__icontains=texto)
                | Q(reserva__paquete__nombre__icontains=texto)
            )
        return Response(paginar(request, pagoLista.order_by("id"), pago_json))

    @swagger_auto_schema(
        operation_description=(
            "Guardar pago (multipart/form-data). Cliente: 'comprobante' obligatorio (JPG, PNG o WEBP, máx. 5 MB); "
            "el precio lo calcula el servidor (precio del paquete × sillas), la fecha es la del servidor y el pago "
            "queda pendiente. 409 si la reserva ya tiene un pago pendiente o aprobado; 400 si está cancelada."
        ),
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
        if comprobante:
            error = error_comprobante(comprobante)
            if error:
                return Response({"message": error}, status=status.HTTP_400_BAD_REQUEST)
        if not personal:
            if reserva.estado.lower() == "cancelada":
                return Response({"message": "La reserva está cancelada"}, status=status.HTTP_400_BAD_REQUEST)
            previo = Pago.objects.filter(reserva=reserva, estado__in=["pendiente", "aprobado"]).order_by("-id").first()
            if previo:
                texto = "Esta reserva ya está pagada" if previo.estado == "aprobado" \
                    else "Ya hay un pago en revisión para esta reserva"
                return Response({"message": texto}, status=status.HTTP_409_CONFLICT)
            if not comprobante:
                return Response({"message": "Adjunta la foto del comprobante"}, status=status.HTTP_400_BAD_REQUEST)
            sillas = AsientoReserva.objects.filter(reserva=reserva).count()
            if sillas == 0:
                return Response({"message": "La reserva no tiene sillas reservadas"},
                                status=status.HTTP_400_BAD_REQUEST)
            precio = total_reserva(reserva, sillas)
            # Solo la agencia aprueba o rechaza: el pago del cliente siempre entra pendiente.
            estado, motivo_rechazo = "pendiente", ""
            fecha_pago = timezone.now()
            referencia = (referencia or "")[:255]

        pago = Pago.objects.create(
            precio=precio,
            reserva_id=reserva_id,
            fecha_pago=fecha_pago,
            referencia=referencia,
            comprobante=comprobante,
            estado=estado,
            motivo_rechazo=motivo_rechazo
        )
        return Response({"mensaje": "Pago almacenado correctamente", "id": pago.id, "estado": pago.estado})


class PagoIdView(APIView):
    @swagger_auto_schema(
        operation_description="Listar pago por id"
    )
    def get(self, request, id):
        registroEncontrado = get_object_or_404(Pago.objects.select_related("reserva__usuario", "reserva__paquete"), id=id)
        yo = usuario_de(request)
        if not (registroEncontrado.reserva.usuario_id == yo.id
                or gestiona_agencia(yo, registroEncontrado.reserva.paquete.agencia_id)):
            return prohibido()
        return Response(pago_json(registroEncontrado))

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
            lista.append(pago_json(pago))
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
        return Response(pago_json(pago))