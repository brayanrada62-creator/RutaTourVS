from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema

from .serializer import ReservaEntrada, AsientoReservaEntrada, MensajeSalida
from .models import Reserva, AsientoReserva, GpsPunto, Novedad, ChatMensaje
import hashlib
import hmac
import re

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from usuarios.models import Usuario
from pagos.models import Pago
from buses.models import Asiento
from paquetes.models import Paquete
from buses.models import Viaje
from buses.views import conductor_autorizado
from usuarios.permisos import (
    SoloPersonal, agencias_de, es_admin, es_cliente_de_paquete, es_super, gestiona_agencia,
    prohibido, trabaja_en_agencia, usuario_de,
)


ESTADOS_ABORDAJE = ("PENDIENTE", "ABORDO", "AUSENTE")


def firma_reserva(reserva_id):
    """Firma corta del tiquete: evita que un QR se fabrique cambiando el número de la reserva."""
    clave = settings.SECRET_KEY.encode("utf-8")
    return hmac.new(clave, f"reserva:{reserva_id}".encode("utf-8"), hashlib.sha256).hexdigest()[:8].upper()


def codigo_reserva(reserva_id):
    return f"RT-{reserva_id}-{firma_reserva(reserva_id)}"


def leer_codigo(texto):
    """Devuelve el id de la reserva si el código del QR es válido (RT-<id>-<firma>), si no None."""
    m = re.fullmatch(r"RT-(\d+)-([0-9A-Fa-f]{8})", (texto or "").strip())
    if not m:
        return None
    reserva_id = int(m.group(1))
    return reserva_id if hmac.compare_digest(m.group(2).upper(), firma_reserva(reserva_id)) else None


def estado_pago(reserva):
    """Estado del último pago registrado de la reserva ("" si no tiene)."""
    pago = Pago.objects.filter(reserva=reserva).order_by("-id").first()
    return pago.estado if pago else ""


def agencia_del_paquete(paquete_id):
    return Paquete.objects.filter(id=paquete_id).values_list("agencia_id", flat=True).first()


def reservas_visibles(yo):
    """Superadmin: todas. Admin: las de los paquetes de su agencia. Cliente: las suyas."""
    if es_super(yo):
        return Reserva.objects.all()
    if es_admin(yo):
        return Reserva.objects.filter(paquete__agencia_id__in=agencias_de(yo))
    return Reserva.objects.filter(usuario=yo)


def puede_ver_reserva(yo, reserva):
    return reserva.usuario_id == yo.id or gestiona_agencia(yo, reserva.paquete.agencia_id)


def puede_ver_paquete_operativo(yo, paquete_id):
    """GPS y chat: personal o conductor de la agencia, o un cliente con reserva en el paquete."""
    agencia_id = agencia_del_paquete(paquete_id)
    if agencia_id is None:
        return False
    return trabaja_en_agencia(yo, agencia_id) or es_cliente_de_paquete(yo, paquete_id)


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
        "codigo": codigo_reserva(reserva.id),
        "pago_estado": pago.estado if pago else "",
        "viaje_id": reserva.viaje_id,
    }


class ReservaView(APIView):
    @swagger_auto_schema(operation_description="Listar reservas")
    def get(self, request):
        yo = usuario_de(request)
        if yo.rol_id == 3:
            return prohibido("El conductor consulta sus pasajeros desde su viaje")
        return Response([reserva_json(r) for r in reservas_visibles(yo)])

    @swagger_auto_schema(
        operation_description="Guardar reserva",
        request_body=ReservaEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        yo = usuario_de(request)
        paquete_id = request.data.get("paquete_id")
        agencia_id = agencia_del_paquete(paquete_id)
        if agencia_id is None:
            return Response({"message": "El paquete no existe"}, status=status.HTTP_404_NOT_FOUND)
        personal = gestiona_agencia(yo, agencia_id)
        # Un cliente solo reserva para sí mismo y siempre queda "pendiente".
        usuario_id = request.data.get("usuario_id") if personal else yo.id
        estado = (request.data.get("estado") or "pendiente") if personal else "pendiente"
        reserva = Reserva.objects.create(
            fecha_reserva=request.data.get("fecha_reserva"),
            usuario_id=usuario_id,
            paquete_id=paquete_id,
            estado=estado,
        )
        return Response(reserva_json(reserva), status=status.HTTP_201_CREATED)


class ReservaIdView(APIView):
    def get(self, request, id):
        reserva = get_object_or_404(Reserva, id=id)
        if not puede_ver_reserva(usuario_de(request), reserva):
            return prohibido()
        return Response(reserva_json(reserva))

    def put(self, request, id):
        reservaB = get_object_or_404(Reserva, id=id)
        yo = usuario_de(request)
        if not gestiona_agencia(yo, reservaB.paquete.agencia_id):
            return prohibido("Solo la agencia puede modificar la reserva")
        if "paquete_id" in request.data and not gestiona_agencia(yo, agencia_del_paquete(request.data.get("paquete_id"))):
            return prohibido()
        reservaB.fecha_reserva = request.data.get("fecha_reserva", reservaB.fecha_reserva)
        reservaB.usuario_id = request.data.get("usuario_id", reservaB.usuario_id)
        reservaB.paquete_id = request.data.get("paquete_id", reservaB.paquete_id)
        if "estado" in request.data:
            reservaB.estado = request.data.get("estado")
        reservaB.save()
        return Response(reserva_json(reservaB))

    def delete(self, request, id):
        reserva = get_object_or_404(Reserva, id=id)
        yo = usuario_de(request)
        pagada = Pago.objects.filter(reserva=reserva, estado="aprobado").exists()
        es_dueno = reserva.usuario_id == yo.id and not pagada
        if not (es_dueno or gestiona_agencia(yo, reserva.paquete.agencia_id)):
            return prohibido("Una reserva pagada solo la puede eliminar la agencia")
        reserva.delete()
        return Response({"mensaje": "Reserva eliminada"})


class ReservaFechaView(APIView):
    permission_classes = [SoloPersonal]

    def get(self, request, fecha_reserva):
        lista = reservas_visibles(usuario_de(request)).filter(fecha_reserva=fecha_reserva)
        return Response([reserva_json(r) for r in lista])


class ReservaUsuarioView(APIView):
    def get(self, request, usuario_id):
        yo = usuario_de(request)
        if yo.id == usuario_id:
            lista = Reserva.objects.filter(usuario_id=usuario_id)
        elif es_super(yo) or es_admin(yo):
            lista = reservas_visibles(yo).filter(usuario_id=usuario_id)
        else:
            return prohibido()
        return Response([reserva_json(r) for r in lista])


class AsientoReservaView(APIView):
    def get(self, request):
        yo = usuario_de(request)
        lista = AsientoReserva.objects.filter(reserva__in=reservas_visibles(yo)) if yo.rol_id != 3 else []
        return Response([
            {"id": ar.id, "asiento_id": ar.asiento_id, "reserva_id": ar.reserva_id}
            for ar in lista
        ])

    @swagger_auto_schema(
        operation_description="Reservar un asiento. Responde 409 si el asiento ya está reservado "
                              "en otra reserva no cancelada del mismo paquete.",
        request_body=AsientoReservaEntrada,
    )
    def post(self, request):
        asiento_id = request.data.get("asiento_id")
        reserva_id = request.data.get("reserva_id")
        with transaction.atomic():
            # Bloquea la fila del asiento: si dos personas confirman a la vez, la segunda espera.
            asiento = Asiento.objects.select_for_update().filter(id=asiento_id).first()
            reserva = Reserva.objects.filter(id=reserva_id).first()
            if asiento is None or reserva is None:
                return Response({"message": "Asiento o reserva no existe"}, status=status.HTTP_400_BAD_REQUEST)
            yo = usuario_de(request)
            if not (reserva.usuario_id == yo.id or gestiona_agencia(yo, reserva.paquete.agencia_id)):
                return prohibido("Esa reserva no es tuya")
            ocupado = (
                AsientoReserva.objects
                .filter(asiento_id=asiento.id, reserva__paquete_id=reserva.paquete_id)
                .exclude(reserva__estado__iexact="cancelada")
                .exists()
            )
            if ocupado:
                return Response({"message": "El asiento ya está reservado"}, status=status.HTTP_409_CONFLICT)
            AsientoReserva.objects.create(asiento_id=asiento.id, reserva_id=reserva.id)
        return Response({"mensaje": "Asiento reservado correctamente", "id": reserva_id})


class AsientoReservaIdView(APIView):
    permission_classes = [SoloPersonal]

    def get(self, request, id):
        ar = get_object_or_404(AsientoReserva, id=id)
        if not gestiona_agencia(usuario_de(request), ar.reserva.paquete.agencia_id):
            return prohibido()
        return Response({"id": ar.id, "asiento_id": ar.asiento_id, "reserva_id": ar.reserva_id})

    def put(self, request, id):
        arB = get_object_or_404(AsientoReserva, id=id)
        if not gestiona_agencia(usuario_de(request), arB.reserva.paquete.agencia_id):
            return prohibido()
        arB.asiento_id = request.data.get("asiento_id")
        arB.reserva_id = request.data.get("reserva_id")
        arB.save()
        return Response({"mensaje": "Asiento reservado actualizado"})

    def delete(self, request, id):
        ar = get_object_or_404(AsientoReserva, id=id)
        if not gestiona_agencia(usuario_de(request), ar.reserva.paquete.agencia_id):
            return prohibido()
        ar.delete()
        return Response({"mensaje": "Asiento reservado eliminado"})


class PaquetePasajerosView(APIView):
    def get(self, request, paquete_id):
        agencia_id = agencia_del_paquete(paquete_id)
        if agencia_id is None:
            return Response({"message": "El paquete no existe"}, status=status.HTTP_404_NOT_FOUND)
        if not gestiona_agencia(usuario_de(request), agencia_id):
            return prohibido("El conductor consulta los pasajeros desde su viaje")
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
                "codigo": codigo_reserva(r.id),
                "asiento": ",".join(str(n) for n in asientos) or "-",
                "estado": r.abordado,
                "pago_estado": estado_pago(r),
            })
        return Response(lista)


class PaqueteAbordarView(APIView):
    """Compatibilidad para el panel: el personal marca abordaje por paquete con la misma regla de pago."""

    def post(self, request, paquete_id):
        agencia_id = agencia_del_paquete(paquete_id)
        if agencia_id is None:
            return Response({"message": "El paquete no existe"}, status=status.HTTP_404_NOT_FOUND)
        if not gestiona_agencia(usuario_de(request), agencia_id):
            return prohibido("El conductor registra el abordaje desde su viaje")
        return registrar_abordaje(request, Reserva.objects.filter(paquete_id=paquete_id), viaje=None)


def reservas_del_viaje(viaje):
    """Pasajeros de un viaje: reservas no canceladas de su paquete, de ese viaje o sin viaje asignado."""
    return (
        Reserva.objects.filter(paquete_id=viaje.paquete_id)
        .exclude(estado__iexact="cancelada")
        .filter(Q(viaje=viaje) | Q(viaje__isnull=True))
    )


def pasajero_json(r):
    usuario = Usuario.objects.filter(id=r.usuario_id).first()
    asientos = list(AsientoReserva.objects.filter(reserva=r).values_list("asiento__numero_asiento", flat=True))
    pago = estado_pago(r)
    return {
        "id": r.id,
        "nombre": usuario.nombre_completo if usuario else f"Pasajero {r.usuario_id}",
        "detalle": r.paquete.nombre if r.paquete_id else "",
        "codigo": codigo_reserva(r.id),
        "asiento": ",".join(str(n) for n in asientos) or "-",
        "estado": r.abordado,
        "pago_estado": pago,
        "puede_abordar": pago == "aprobado",
    }


def registrar_abordaje(request, reservas_validas, viaje):
    """Regla 2: solo aborda una reserva válida para este viaje y con el último pago APROBADO.
    El estado del pago se lee de la tabla de pagos; nunca se confía en lo que envía la app."""
    estado = str(request.data.get("estado") or "ABORDO").upper()
    if estado not in ESTADOS_ABORDAJE:
        return Response({"message": "Estado de abordaje inválido"}, status=status.HTTP_400_BAD_REQUEST)
    codigo = request.data.get("codigo")
    if codigo:
        reserva_id = leer_codigo(codigo)
        if reserva_id is None:
            return Response({"message": "Código QR no válido", "motivo": "qr_invalido"},
                            status=status.HTTP_400_BAD_REQUEST)
    else:
        reserva_id = request.data.get("reserva_id")
    with transaction.atomic():
        reserva = Reserva.objects.select_for_update().filter(id=reserva_id).first()
        if reserva is None:
            return Response({"message": "La reserva no existe", "motivo": "no_existe"},
                            status=status.HTTP_404_NOT_FOUND)
        if not reservas_validas.filter(id=reserva.id).exists():
            return Response({"message": "La reserva no pertenece a este viaje", "motivo": "otro_viaje"},
                            status=status.HTTP_409_CONFLICT)
        if estado == "ABORDO":
            pago = estado_pago(reserva)
            if pago != "aprobado":
                motivo = {"pendiente": "pago_pendiente", "rechazado": "pago_rechazado"}.get(pago, "sin_pago")
                texto = {"pago_pendiente": "El pago está pendiente de aprobación",
                         "pago_rechazado": "El pago fue rechazado",
                         "sin_pago": "La reserva no tiene un pago registrado"}[motivo]
                return Response({"message": texto, "motivo": motivo, "pasajero": pasajero_json(reserva)},
                                status=status.HTTP_409_CONFLICT)
        if reserva.abordado == estado:
            datos = pasajero_json(reserva)
            datos["sin_cambios"] = True  # ya estaba así: no se duplica nada
            return Response(datos)
        reserva.abordado = estado
        if viaje is not None and reserva.viaje_id is None:
            reserva.viaje = viaje  # queda ligada al viaje en el que abordó
        reserva.save(update_fields=["abordado", "viaje"])
    return Response(pasajero_json(reserva))


class ViajePasajerosView(APIView):
    @swagger_auto_schema(operation_description="Pasajeros del viaje con el estado de su pago. Conductor del bus o admin.")
    def get(self, request, id):
        viaje = get_object_or_404(Viaje.objects.select_related("bus"), id=id)
        yo = usuario_de(request)
        if not (conductor_autorizado(yo, viaje) or gestiona_agencia(yo, viaje.bus.agencia_id)):
            return prohibido("Este viaje no pertenece a tu bus")
        return Response([pasajero_json(r) for r in reservas_del_viaje(viaje).order_by("id")])


class ViajeAbordarView(APIView):
    @swagger_auto_schema(
        operation_description=(
            "Registrar abordaje. Body: {codigo: 'RT-<id>-<firma>'} (QR) o {reserva_id}, y estado "
            "ABORDO | AUSENTE | PENDIENTE. ABORDO exige el último pago aprobado (409 con 'motivo' si no)."
        )
    )
    def post(self, request, id):
        viaje = get_object_or_404(Viaje.objects.select_related("bus"), id=id)
        yo = usuario_de(request)
        if not (conductor_autorizado(yo, viaje) or gestiona_agencia(yo, viaje.bus.agencia_id)):
            return prohibido("Este viaje no pertenece a tu bus")
        if viaje.estado == Viaje.COMPLETADO:
            return Response({"message": "El viaje ya finalizó"}, status=status.HTTP_409_CONFLICT)
        return registrar_abordaje(request, reservas_del_viaje(viaje), viaje)


GPS_INTERVALO_MINIMO_SEG = 5  # puntos más seguidos se ignoran (no se duplican)


def gps_json(g):
    viaje = g.viaje
    return {
        "id": g.id, "paquete_id": g.paquete_id, "viaje_id": g.viaje_id,
        "bus_id": viaje.bus_id if viaje else None,
        "placa": viaje.bus.placa if viaje else None,
        "lat": str(g.lat), "lng": str(g.lng), "velocidad": str(g.velocidad), "fecha": g.fecha,
    }


def puede_ver_viaje_gps(yo, viaje):
    return (
        gestiona_agencia(yo, viaje.bus.agencia_id)
        or conductor_autorizado(yo, viaje)
        or es_cliente_de_paquete(yo, viaje.paquete_id)
    )


class GpsView(APIView):
    @swagger_auto_schema(
        operation_description=(
            "Puntos GPS (más recientes primero). ?viaje_id= un viaje · /gps/<paquete_id>/ un paquete · "
            "?ultimos=1 el último punto de cada viaje EN_CURSO visible (panel de tiempo real)."
        )
    )
    def get(self, request, paquete_id=None):
        yo = usuario_de(request)
        lista = GpsPunto.objects.select_related("viaje__bus")
        viaje_id = request.query_params.get("viaje_id")
        paquete_id = paquete_id or request.query_params.get("paquete_id")
        if viaje_id:
            viaje = get_object_or_404(Viaje.objects.select_related("bus"), id=viaje_id)
            if not puede_ver_viaje_gps(yo, viaje):
                return prohibido()
            lista = lista.filter(viaje=viaje)
        elif paquete_id:
            if not puede_ver_paquete_operativo(yo, paquete_id):
                return prohibido()
            lista = lista.filter(paquete_id=paquete_id)
        elif es_admin(yo):
            lista = lista.filter(paquete__agencia_id__in=agencias_de(yo))
        elif not es_super(yo):
            return Response({"message": "Indica viaje_id o paquete_id"}, status=status.HTTP_400_BAD_REQUEST)

        if request.query_params.get("ultimos"):
            activos = lista.filter(viaje__estado=Viaje.EN_CURSO)
            ultimos = {}
            for g in activos.order_by("-fecha", "-id"):
                ultimos.setdefault(g.viaje_id, g)
            return Response([gps_json(g) for g in ultimos.values()])
        return Response([gps_json(g) for g in lista.order_by("-fecha", "-id")[:80]])

    @swagger_auto_schema(
        operation_description=(
            "El conductor que inició el viaje envía su ubicación: {viaje_id, lat, lng, velocidad}. "
            "403 si no es su viaje, 409 si el viaje no está EN_CURSO (la app debe detener el seguimiento)."
        )
    )
    def post(self, request, paquete_id=None):
        yo = usuario_de(request)
        viaje_id = request.data.get("viaje_id")
        if viaje_id:
            viaje = Viaje.objects.select_related("bus").filter(id=viaje_id).first()
        else:
            # Compatibilidad: sin viaje_id se usa el viaje EN_CURSO de este conductor en ese paquete.
            paquete_id = paquete_id or request.data.get("paquete_id")
            viaje = Viaje.objects.select_related("bus").filter(
                paquete_id=paquete_id, conductor=yo, estado=Viaje.EN_CURSO).first()
        if viaje is None:
            if not viaje_id and not trabaja_en_agencia(yo, agencia_del_paquete(paquete_id)):
                return prohibido("Solo el conductor de la agencia envía GPS")
            return Response({"message": "No hay un viaje en curso para esa ubicación"},
                            status=status.HTTP_409_CONFLICT)
        if not conductor_autorizado(yo, viaje):
            return prohibido("Este viaje no pertenece a tu bus")
        if viaje.estado != Viaje.EN_CURSO:
            return Response({"message": f"El viaje está {viaje.estado}", "estado": viaje.estado},
                            status=status.HTTP_409_CONFLICT)
        if viaje.conductor_id != yo.id:
            return prohibido("Solo el conductor que inició el viaje envía su ubicación")
        try:
            lat = float(request.data.get("lat"))
            lng = float(request.data.get("lng"))
            velocidad = max(0.0, float(request.data.get("velocidad") or 0))
        except (TypeError, ValueError):
            return Response({"message": "Coordenadas inválidas"}, status=status.HTTP_400_BAD_REQUEST)
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            return Response({"message": "Coordenadas fuera de rango"}, status=status.HTTP_400_BAD_REQUEST)
        ultimo = GpsPunto.objects.filter(viaje=viaje).order_by("-fecha", "-id").first()
        if ultimo and (timezone.now() - ultimo.fecha).total_seconds() < GPS_INTERVALO_MINIMO_SEG:
            return Response({"id": ultimo.id, "viaje_id": viaje.id, "ignorado": True})
        punto = GpsPunto.objects.create(
            paquete_id=viaje.paquete_id, viaje=viaje,
            lat=round(lat, 6), lng=round(lng, 6), velocidad=round(min(velocidad, 9999.99), 2),
        )
        return Response({"id": punto.id, "paquete_id": punto.paquete_id, "viaje_id": viaje.id},
                        status=status.HTTP_201_CREATED)


def viaje_operativo(yo, viaje_id):
    """(viaje, error) para novedades y chat ligados a un viaje: conductor del bus, personal o cliente del paquete."""
    viaje = Viaje.objects.select_related("bus").filter(id=viaje_id).first()
    if viaje is None:
        return None, Response({"message": "El viaje no existe"}, status=status.HTTP_404_NOT_FOUND)
    if not puede_ver_viaje_gps(yo, viaje):
        return None, prohibido("Este viaje no es tuyo")
    return viaje, None


def novedad_json(n):
    return {"id": n.id, "paquete_id": n.paquete_id, "viaje_id": n.viaje_id, "tipo": n.tipo,
            "detalle": n.detalle, "fecha": n.fecha}


class NovedadView(APIView):
    @swagger_auto_schema(operation_description="Novedades de la agencia (personal). Filtro ?viaje_id=")
    def get(self, request):
        yo = usuario_de(request)
        if es_super(yo):
            lista = Novedad.objects.all()
        elif es_admin(yo):
            lista = Novedad.objects.filter(paquete__agencia_id__in=agencias_de(yo))
        else:
            return prohibido()
        if request.query_params.get("viaje_id"):
            lista = lista.filter(viaje_id=request.query_params.get("viaje_id"))
        return Response([novedad_json(n) for n in lista.order_by("-fecha")])

    @swagger_auto_schema(operation_description="Reportar novedad: {viaje_id, tipo, detalle} (o paquete_id para el personal).")
    def post(self, request):
        yo = usuario_de(request)
        viaje = None
        if request.data.get("viaje_id"):
            viaje, error = viaje_operativo(yo, request.data.get("viaje_id"))
            if error:
                return error
            if not (conductor_autorizado(yo, viaje) or gestiona_agencia(yo, viaje.bus.agencia_id)):
                return prohibido("Solo el conductor o la agencia reportan novedades")
            paquete_id = viaje.paquete_id
        else:
            paquete_id = request.data.get("paquete_id")
            if not trabaja_en_agencia(yo, agencia_del_paquete(paquete_id)):
                return prohibido("Indica un viaje o un paquete de tu agencia")
        tipo = (request.data.get("tipo") or "novedad").strip()[:80]
        detalle = (request.data.get("detalle") or "").strip()[:400]
        if not detalle:
            return Response({"message": "Escribe el detalle de la novedad"}, status=status.HTTP_400_BAD_REQUEST)
        n = Novedad.objects.create(paquete_id=paquete_id, viaje=viaje, tipo=tipo, detalle=detalle)
        return Response(novedad_json(n), status=status.HTTP_201_CREATED)


def chat_json(m):
    return {"id": m.id, "paquete_id": m.paquete_id, "viaje_id": m.viaje_id, "usuario_id": m.usuario_id,
            "texto": m.texto, "fecha": m.fecha}


class ChatView(APIView):
    @swagger_auto_schema(operation_description="Mensajes de un viaje (?viaje_id=) o de un paquete (?paquete_id=).")
    def get(self, request):
        yo = usuario_de(request)
        viaje_id = request.query_params.get("viaje_id")
        paquete_id = request.query_params.get("paquete_id")
        if viaje_id:
            viaje, error = viaje_operativo(yo, viaje_id)
            if error:
                return error
            lista = ChatMensaje.objects.filter(viaje=viaje)
        elif paquete_id:
            if not puede_ver_paquete_operativo(yo, paquete_id):
                return prohibido()
            lista = ChatMensaje.objects.filter(paquete_id=paquete_id)
        else:
            return Response({"message": "Indica viaje_id o paquete_id"}, status=status.HTTP_400_BAD_REQUEST)
        return Response([chat_json(m) for m in lista.order_by("fecha", "id")])

    @swagger_auto_schema(operation_description="Enviar mensaje: {viaje_id o paquete_id, texto}. El autor es quien tiene la sesión.")
    def post(self, request):
        yo = usuario_de(request)
        viaje = None
        if request.data.get("viaje_id"):
            viaje, error = viaje_operativo(yo, request.data.get("viaje_id"))
            if error:
                return error
            paquete_id = viaje.paquete_id
        else:
            paquete_id = request.data.get("paquete_id")
            if not puede_ver_paquete_operativo(yo, paquete_id):
                return prohibido()
        texto = (request.data.get("texto") or "").strip()[:400]
        if not texto:
            return Response({"message": "Escribe un mensaje"}, status=status.HTTP_400_BAD_REQUEST)
        m = ChatMensaje.objects.create(paquete_id=paquete_id, viaje=viaje, usuario_id=yo.id, texto=texto)
        return Response(chat_json(m), status=status.HTTP_201_CREATED)
