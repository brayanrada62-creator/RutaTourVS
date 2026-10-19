import json
from datetime import date as date_cls
from datetime import datetime

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from drf_yasg.utils import swagger_auto_schema

from buses.models import Asiento
from paquetes.models import Paquete
from usuarios.models import Usuario
from pagos.models import Pago

from .serializer import ReservaEntrada, AsientoReservaEntrada, MensajeSalida
from .models import Reserva, AsientoReserva, GpsPunto, Novedad, ChatMensaje


def usuario_desde_request(request, data=None):
    data = data if data is not None else request.data
    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        email = (getattr(user, "email", None) or getattr(user, "username", None) or "").strip()
        if email:
            encontrado = Usuario.objects.filter(correo__iexact=email).first()
            if encontrado:
                return encontrado
    uid = data.get("usuario_id") if hasattr(data, "get") else None
    if uid:
        return Usuario.objects.filter(id=uid).first()
    return None


def parse_ids(valor):
    if valor in (None, ""):
        return []
    if isinstance(valor, int):
        return [valor]
    if isinstance(valor, (list, tuple)):
        piezas = valor
    else:
        texto = str(valor).strip()
        if texto.startswith("["):
            try:
                piezas = json.loads(texto)
            except json.JSONDecodeError:
                piezas = texto.strip("[]").replace(";", ",").split(",")
        else:
            piezas = texto.replace(";", ",").split(",")
    ids = []
    for pieza in piezas:
        if isinstance(pieza, dict):
            pieza = pieza.get("id") or pieza.get("asiento_id") or pieza.get("numero_asiento")
        texto = str(pieza).strip().strip('"').strip("'")
        if texto.isdigit():
            ids.append(int(texto))
    return ids


def extraer_asiento_ids(data):
    ids = []
    for clave in ("asientos", "asiento_ids", "asiento_id", "asientos_ids"):
        if hasattr(data, "getlist"):
            for valor in data.getlist(clave) + data.getlist(f"{clave}[]"):
                ids.extend(parse_ids(valor))
        if hasattr(data, "get"):
            ids.extend(parse_ids(data.get(clave)))
    vistos = []
    for asiento_id in ids:
        if asiento_id not in vistos:
            vistos.append(asiento_id)
    return vistos


def asientos_ocupados(paquete_id=None):
    qs = AsientoReserva.objects.exclude(reserva__estado__iexact="cancelada")
    if paquete_id:
        qs = qs.filter(reserva__paquete_id=paquete_id)
    return set(qs.values_list("asiento_id", flat=True))


def con_zona(dt):
    if timezone.is_naive(dt) and timezone.is_aware(timezone.now()):
        return timezone.make_aware(dt)
    return dt


def parse_fecha_reserva(valor):
    if not valor:
        return timezone.now()
    if isinstance(valor, datetime):
        return con_zona(valor)
    if isinstance(valor, date_cls):
        return con_zona(datetime.combine(valor, datetime.min.time()))
    texto = str(valor).strip()
    dt = parse_datetime(texto)
    if dt:
        return con_zona(dt)
    d = parse_date(texto)
    if d:
        return con_zona(datetime.combine(d, datetime.min.time()))
    return timezone.now()


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
        "estado": estado,
        "abordado": reserva.abordado,
        "asientos": ",".join(str(n) for n in asientos),
        "asientos_ids": list(
            AsientoReserva.objects.filter(reserva=reserva).values_list("asiento_id", flat=True)
        ),
        "codigo": f"RT-{reserva.id}",
        "pago_estado": pago.estado if pago else "",
    }


def crear_reserva_con_asientos(request):
    paquete_id = request.data.get("paquete_id")
    if not paquete_id:
        raise ValueError("El paquete_id es obligatorio")
    paquete = Paquete.objects.filter(id=paquete_id).first()
    if not paquete:
        raise ValueError("El paquete no existe")

    usuario = usuario_desde_request(request)
    if not usuario:
        raise ValueError("Inicia sesión o envía usuario_id")

    asiento_ids = extraer_asiento_ids(request.data)
    fecha = parse_fecha_reserva(request.data.get("fecha_reserva"))

    with transaction.atomic():
        asientos = []
        if asiento_ids:
            asientos = list(Asiento.objects.select_for_update().filter(id__in=asiento_ids))
            if len(asientos) != len(set(asiento_ids)):
                raise ValueError("Uno o más asientos no existen")
            ocupados = asientos_ocupados(paquete.id)
            tomados = [a.numero_asiento for a in asientos if a.id in ocupados]
            if tomados:
                raise ValueError(
                    "Estos asientos ya están ocupados: " + ", ".join(str(n) for n in tomados)
                )

        reserva = Reserva.objects.create(
            fecha_reserva=fecha,
            usuario=usuario,
            paquete=paquete,
            estado=request.data.get("estado") or "pendiente",
        )
        for asiento in asientos:
            AsientoReserva.objects.get_or_create(reserva=reserva, asiento=asiento)
    return reserva


class ReservaView(APIView):
    @swagger_auto_schema(operation_description="Listar reservas. Filtra con ?usuario_id=")
    def get(self, request):
        lista = Reserva.objects.all().order_by("-id")
        uid = request.query_params.get("usuario_id")
        if uid:
            lista = lista.filter(usuario_id=uid)
        return Response([reserva_json(r) for r in lista])

    @swagger_auto_schema(
        operation_description="Guarda la reserva del usuario y marca los asientos como ocupados.",
        request_body=ReservaEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        try:
            reserva = crear_reserva_con_asientos(request)
        except ValueError as error:
            return Response({"mensaje": str(error), "message": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(reserva_json(reserva), status=status.HTTP_201_CREATED)


class ReservaCrearView(APIView):
    @swagger_auto_schema(
        operation_description=(
            "Crea la reserva y bloquea asientos en un solo paso. "
            "Body: paquete_id, usuario_id (o token), asientos (ids: 1,2,3)."
        ),
        request_body=ReservaEntrada,
    )
    def post(self, request):
        try:
            reserva = crear_reserva_con_asientos(request)
        except ValueError as error:
            return Response({"mensaje": str(error), "message": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(reserva_json(reserva), status=status.HTTP_201_CREATED)


class ReservaMiasView(APIView):
    @swagger_auto_schema(operation_description="Reservas del usuario autenticado o de usuario_id")
    def get(self, request):
        yo = usuario_desde_request(request, request.query_params)
        if not yo:
            return Response(
                {"mensaje": "Inicia sesión o envía usuario_id"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response([reserva_json(r) for r in Reserva.objects.filter(usuario=yo).order_by("-id")])


class PaqueteAsientosView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(operation_description="Mapa de asientos del paquete, con ocupado=true si ya hay reserva")
    def get(self, request, paquete_id):
        paquete = Paquete.objects.filter(id=paquete_id).first()
        if not paquete:
            return Response({"mensaje": "Paquete no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        ocupados = asientos_ocupados(paquete.id)
        tipo = request.query_params.get("tipo_bus_id")
        asientos = Asiento.objects.all()
        if tipo:
            asientos = asientos.filter(tipo_bus_id=tipo)
        return Response([
            {
                "id": asiento.id,
                "tipo_bus_id": asiento.tipo_bus_id,
                "numero_asiento": asiento.numero_asiento,
                "ocupado": asiento.id in ocupados,
                "paquete_id": paquete.id,
            }
            for asiento in asientos
        ])


class ReservaIdView(APIView):
    def get(self, request, id):
        return Response(reserva_json(Reserva.objects.get(id=id)))

    def put(self, request, id):
        reservaB = Reserva.objects.get(id=id)
        reservaB.fecha_reserva = request.data.get("fecha_reserva", reservaB.fecha_reserva)
        reservaB.usuario_id = request.data.get("usuario_id", reservaB.usuario_id)
        reservaB.paquete_id = request.data.get("paquete_id", reservaB.paquete_id)
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
        reserva_id = request.data.get("reserva_id")
        asiento_id = request.data.get("asiento_id")
        reserva = Reserva.objects.filter(id=reserva_id).first()
        if not reserva:
            return Response({"mensaje": "La reserva no existe"}, status=status.HTTP_400_BAD_REQUEST)
        asiento = Asiento.objects.filter(id=asiento_id).first()
        if not asiento:
            return Response({"mensaje": "El asiento no existe"}, status=status.HTTP_400_BAD_REQUEST)
        ya_mio = AsientoReserva.objects.filter(reserva=reserva, asiento=asiento).exists()
        if asiento.id in asientos_ocupados(reserva.paquete_id) and not ya_mio:
            return Response(
                {"mensaje": f"El asiento {asiento.numero_asiento} ya está ocupado"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        asiento_reserva, _ = AsientoReserva.objects.get_or_create(reserva=reserva, asiento=asiento)
        return Response({
            "id": asiento_reserva.id,
            "reserva_id": asiento_reserva.reserva_id,
            "asiento_id": asiento_reserva.asiento_id,
            "mensaje": "Asiento reservado correctamente",
        }, status=status.HTTP_201_CREATED)


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
    def get(self, request, paquete_id):
        lista = []
        for r in Reserva.objects.filter(paquete_id=paquete_id).exclude(estado="cancelada"):
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
    def post(self, request, paquete_id):
        codigo = str(request.data.get("codigo") or "")
        reserva_id = request.data.get("reserva_id")
        estado = request.data.get("estado") or "ABORDO"
        reserva = None
        if reserva_id:
            reserva = Reserva.objects.filter(id=reserva_id, paquete_id=paquete_id).first()
        elif codigo.upper().startswith("RT-"):
            rid = codigo.split("-")[-1]
            reserva = Reserva.objects.filter(id=rid, paquete_id=paquete_id).first()
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
