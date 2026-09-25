from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema

from .serializer import ReservaEntrada, AsientoReservaEntrada, MensajeSalida
from .models import Reserva, AsientoReserva, GpsPunto, Novedad, ChatMensaje
from usuarios.models import Usuario
from pagos.models import Pago


def reserva_json(reserva):
    asientos = list(
        AsientoReserva.objects.filter(reserva=reserva).values_list("asiento__numero_asiento", flat=True)
    )
    pago = Pago.objects.filter(reserva=reserva).order_by("-id").first()
    estado = reserva.estado
    if pago and pago.estado == "aprobado" and estado == "pendiente":
        estado = "pagada"
    return {
        "id": reserva.id,
        "fecha_reserva": reserva.fecha_reserva,
        "usuario_id": reserva.usuario_id,
        "paquete_id": reserva.paquete_id,
        "viaje_id": reserva.viaje_id,
        "estado": estado,
        "abordado": reserva.abordado,
        "asientos": ",".join(str(n) for n in asientos),
        "codigo": f"RT-{reserva.id}",
        "pago_estado": pago.estado if pago else "",
    }


class ReservaView(APIView):
    @swagger_auto_schema(operation_description="Listar reservas")
    def get(self, request):
        return Response([reserva_json(r) for r in Reserva.objects.all()])

    @swagger_auto_schema(
        operation_description="Guardar reserva",
        request_body=ReservaEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        reserva = Reserva.objects.create(
            fecha_reserva=request.data.get("fecha_reserva"),
            usuario_id=request.data.get("usuario_id"),
            paquete_id=request.data.get("paquete_id"),
            viaje_id=request.data.get("viaje_id"),
            estado=request.data.get("estado") or "pendiente",
        )
        return Response(reserva_json(reserva), status=status.HTTP_201_CREATED)


class ReservaIdView(APIView):
    def get(self, request, id):
        return Response(reserva_json(Reserva.objects.get(id=id)))

    def put(self, request, id):
        reservaB = Reserva.objects.get(id=id)
        reservaB.fecha_reserva = request.data.get("fecha_reserva", reservaB.fecha_reserva)
        reservaB.usuario_id = request.data.get("usuario_id", reservaB.usuario_id)
        reservaB.paquete_id = request.data.get("paquete_id", reservaB.paquete_id)
        if "viaje_id" in request.data:
            reservaB.viaje_id = request.data.get("viaje_id")
        if "estado" in request.data:
            reservaB.estado = request.data.get("estado")
        reservaB.save()
        return Response(reserva_json(reservaB))

    def delete(self, request, id):
        Reserva.objects.get(id=id).delete()
        return Response({"mensaje": "Reserva eliminada"})


class ReservaFechaView(APIView):
    def get(self, request, fecha_reserva):
        return Response([reserva_json(r) for r in Reserva.objects.filter(fecha_reserva=fecha_reserva)])


class ReservaUsuarioView(APIView):
    def get(self, request, usuario_id):
        return Response([reserva_json(r) for r in Reserva.objects.filter(usuario_id=usuario_id)])


class AsientoReservaView(APIView):
    def get(self, request):
        return Response([
            {"id": ar.id, "asiento_id": ar.asiento_id, "reserva_id": ar.reserva_id}
            for ar in AsientoReserva.objects.all()
        ])

    def post(self, request):
        asiento_id = request.data.get("asiento_id")
        reserva_id = request.data.get("reserva_id")
        AsientoReserva.objects.create(asiento_id=asiento_id, reserva_id=reserva_id)
        return Response({"mensaje": "Asiento reservado correctamente", "id": reserva_id})


class AsientoReservaIdView(APIView):
    def get(self, request, id):
        ar = AsientoReserva.objects.get(id=id)
        return Response({"id": ar.id, "asiento_id": ar.asiento_id, "reserva_id": ar.reserva_id})

    def put(self, request, id):
        arB = AsientoReserva.objects.get(id=id)
        arB.asiento_id = request.data.get("asiento_id")
        arB.reserva_id = request.data.get("reserva_id")
        arB.save()
        return Response({"mensaje": "Asiento reservado actualizado"})

    def delete(self, request, id):
        AsientoReserva.objects.get(id=id).delete()
        return Response({"mensaje": "Asiento reservado eliminado"})


class PaquetePasajerosView(APIView):
    def get(self, request, id):
        lista = []
        for r in Reserva.objects.filter(paquete_id=id).exclude(estado="cancelada"):
            usuario = Usuario.objects.filter(id=r.usuario_id).first()
            asientos = list(
                AsientoReserva.objects.filter(reserva=r).values_list("asiento__numero_asiento", flat=True)
            )
            lista.append({
                "id": r.id,
                "nombre": usuario.nombre_completo if usuario else f"Pasajero {r.usuario_id}",
                "detalle": r.paquete.nombre if r.paquete_id else "",
                "codigo": f"RT-{r.id}",
                "asiento": ",".join(str(n) for n in asientos) or "-",
                "estado": r.abordado,
            })
        return Response(lista)


class PaqueteAbordarView(APIView):
    def post(self, request, id):
        codigo = str(request.data.get("codigo") or "")
        reserva_id = request.data.get("reserva_id")
        estado = request.data.get("estado") or "ABORDO"
        reserva = None
        if reserva_id:
            reserva = Reserva.objects.filter(id=reserva_id, paquete_id=id).first()
        elif codigo.upper().startswith("RT-"):
            rid = codigo.split("-")[-1]
            reserva = Reserva.objects.filter(id=rid, paquete_id=id).first()
        if reserva is None:
            return Response({"message": "Pasajero no encontrado"})
        reserva.abordado = estado
        reserva.save()
        return Response({"id": reserva.id, "codigo": f"RT-{reserva.id}", "estado": reserva.abordado})


class GpsView(APIView):
    def get(self, request, paquete_id=None):
        paquete_id = paquete_id or request.query_params.get("paquete_id")
        lista = GpsPunto.objects.all()
        if paquete_id:
            lista = lista.filter(paquete_id=paquete_id)
        return Response([
            {"id": g.id, "paquete_id": g.paquete_id, "lat": str(g.lat), "lng": str(g.lng), "velocidad": str(g.velocidad), "fecha": g.fecha}
            for g in lista.order_by("-fecha")[:80]
        ])

    def post(self, request, paquete_id=None):
        punto = GpsPunto.objects.create(
            paquete_id=paquete_id or request.data.get("paquete_id"),
            lat=request.data.get("lat") or 0,
            lng=request.data.get("lng") or 0,
            velocidad=request.data.get("velocidad") or 0,
        )
        return Response({"id": punto.id, "paquete_id": punto.paquete_id})


class NovedadView(APIView):
    def get(self, request):
        return Response([
            {"id": n.id, "paquete_id": n.paquete_id, "tipo": n.tipo, "detalle": n.detalle, "fecha": n.fecha}
            for n in Novedad.objects.all().order_by("-fecha")
        ])

    def post(self, request):
        n = Novedad.objects.create(
            paquete_id=request.data.get("paquete_id"),
            tipo=request.data.get("tipo") or "novedad",
            detalle=request.data.get("detalle") or "",
        )
        return Response({"id": n.id, "tipo": n.tipo, "detalle": n.detalle})


class ChatView(APIView):
    def get(self, request):
        lista = ChatMensaje.objects.all()
        paquete_id = request.query_params.get("paquete_id")
        if paquete_id:
            lista = lista.filter(paquete_id=paquete_id)
        return Response([
            {"id": m.id, "paquete_id": m.paquete_id, "usuario_id": m.usuario_id, "texto": m.texto, "fecha": m.fecha}
            for m in lista.order_by("fecha")
        ])

    def post(self, request):
        m = ChatMensaje.objects.create(
            paquete_id=request.data.get("paquete_id"),
            usuario_id=request.data.get("usuario_id"),
            texto=request.data.get("texto") or "",
        )
        return Response({"id": m.id, "texto": m.texto})
