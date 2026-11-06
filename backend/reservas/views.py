from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from .serializer import (
    AsientoReservaEntrada, MensajeSalida, PaqueteAbordarEntrada, ReservaEditarEntrada, ReservaEntrada,
)
from .models import (
    ESTADOS_QUE_LIBERAN, ESTADOS_RESERVA, AsientoReserva, ChatMensaje, GpsPunto, Novedad, Reserva,
    marcar_vencidas, plazo_de_pago, reservas_que_ocupan,
)
import hashlib
import hmac
import re

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from usuarios.models import Usuario
from pagos.models import Pago
from buses.models import Asiento, Bus_Conductor
from paquetes.models import Paquete
from buses.models import Viaje
from buses.views import conductor_autorizado, entero_o_none, hoy_colombia
from usuarios.paginacion import PARAMETRO_AGENCIA, PARAMETROS_LISTA, entero_query, paginar, texto_busqueda
from usuarios.permisos import (
    ROL_CLIENTE, SoloPersonal, agencias_de, agencias_de_catalogo, es_admin, es_cliente_de_paquete, es_cliente_de_viaje, es_conductor,
    es_super, filtrar_agencia_super, gestiona_agencia, prohibido, trabaja_en_agencia, usuario_de,
)


ESTADOS_ABORDAJE = ("PENDIENTE", "ABORDO", "AUSENTE")

PARAMETRO_VIAJE = openapi.Parameter(
    "viaje_id", openapi.IN_QUERY, description="Solo las reservas de esta salida", type=openapi.TYPE_INTEGER,
)


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


def error_pasajero(nombre, documento):
    """Vacíos = viaja el titular. Si es otra persona: nombre de 3 a 120 letras y documento de 5 a 15 dígitos."""
    if not nombre and not documento:
        return None
    if not (3 <= len(nombre) <= 120):
        return "Escribe el nombre completo del pasajero"
    if not (documento.isdigit() and 5 <= len(documento) <= 15):
        return "El documento del pasajero debe tener de 5 a 15 dígitos"
    return None


def nombre_pasajero(reserva, usuario=None):
    """Nombre de quien viaja: el pasajero indicado o, si no hay, el titular."""
    if reserva.pasajero_nombre:
        return reserva.pasajero_nombre
    usuario = usuario or reserva.usuario
    return usuario.nombre_completo if usuario else f"Pasajero {reserva.usuario_id}"


def total_reserva(reserva, cantidad_sillas=None):
    """Precio del paquete × sillas reservadas. Lo calcula el servidor, nunca la app."""
    if cantidad_sillas is None:
        cantidad_sillas = AsientoReserva.objects.filter(reserva=reserva).count()
    return reserva.paquete.precio * cantidad_sillas


def reserva_json(reserva):
    asientos = list(
        AsientoReserva.objects.filter(reserva=reserva).values_list("asiento__numero_asiento", flat=True)
    )
    pago = Pago.objects.filter(reserva=reserva).order_by("-id").first()
    estado = "vencida" if reserva.vencida else reserva.estado
    if pago and pago.estado == "aprobado" and estado == "pendiente":
        estado = "pagada"
    viaje = reserva.viaje
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
        # Por qué la agencia rechazó el último pago ("" si no está rechazado).
        "pago_motivo": pago.motivo_rechazo if pago and pago.estado == "rechazado" else "",
        "viaje_id": reserva.viaje_id,
        # Hasta cuándo se guardan las sillas sin comprobante (null = plazo detenido).
        "vence_en": reserva.vence_en,
        "pasajero_nombre": reserva.pasajero_nombre,
        "pasajero_documento": reserva.pasajero_documento,
        "paquete": reserva.paquete.nombre,  # nombre del paquete
        "cliente_nombre": reserva.usuario.nombre_completo,  # titular de la cuenta que reservó
        "agencia_id": reserva.paquete.agencia_id,
        "total": str(total_reserva(reserva, len(asientos))),
        # Salida elegida (null en reservas antiguas sin salida).
        "viaje_fecha": viaje.fecha.isoformat() if viaje else None,
        "viaje_hora": viaje.hora.strftime("%H:%M") if viaje else None,
        "viaje_estado": viaje.estado if viaje else None,
        "placa": viaje.bus.placa if viaje else None,
    }


def leer_ids_asientos(valor):
    """Acepta [3, 4], "3,4" o vacío. Devuelve (lista de ids, error)."""
    if valor in (None, "", []):
        return [], None
    partes = valor if isinstance(valor, (list, tuple)) else str(valor).split(",")
    ids = []
    for parte in partes:
        numero = entero_o_none(str(parte).strip())
        if numero is None or numero <= 0:
            return None, "Las sillas deben ser números separados por coma"
        ids.append(numero)
    return ids, None


def tomar_sillas(reserva, asiento_ids, excluir_asiento_reserva=None, excluir_reserva=None):
    """Valida las sillas de una reserva. Debe llamarse dentro de transaction.atomic().

    Bloquea las filas de las sillas en orden de id (así dos compras simultáneas se turnan y no se
    traban entre sí), revisa que sean del bus de la salida y que nadie más las tenga.
    excluir_reserva: no cuenta las sillas que ya tiene esa reserva (al asignarle salida a una antigua).
    Devuelve (sillas, None) o (None, Response con el error)."""
    ids = sorted(set(asiento_ids))
    sillas = list(Asiento.objects.select_for_update().select_related("tipo_bus").filter(id__in=ids).order_by("id"))
    if not ids or len(sillas) != len(ids):
        return None, Response({"message": "Alguna silla no existe"}, status=status.HTTP_400_BAD_REQUEST)
    for silla in sillas:
        if reserva.viaje_id:
            propia = reserva.viaje.bus.tipos_bus.filter(id=silla.tipo_bus_id).exists()
        else:
            propia = silla.tipo_bus.agencia_id == reserva.paquete.agencia_id
        if not propia:
            return None, Response({"message": f"La silla {silla.numero_asiento} no es del bus de la salida"},
                                  status=status.HTTP_400_BAD_REQUEST)
    ocupadas = AsientoReserva.objects.filter(
        asiento_id__in=ids, reserva__in=reservas_que_ocupan(reserva.paquete_id, reserva.viaje_id),
    )
    if excluir_asiento_reserva is not None:
        ocupadas = ocupadas.exclude(id=excluir_asiento_reserva)
    if excluir_reserva is not None:
        ocupadas = ocupadas.exclude(reserva_id=excluir_reserva)
    numeros = sorted(set(ocupadas.values_list("asiento__numero_asiento", flat=True)))
    if numeros:
        texto = "La silla" if len(numeros) == 1 else "Las sillas"
        return None, Response(
            {"message": f"{texto} {', '.join(str(n) for n in numeros)} ya está(n) reservada(s)", "ocupadas": numeros},
            status=status.HTTP_409_CONFLICT,
        )
    return sillas, None


class ReservaView(APIView):
    @swagger_auto_schema(
        operation_description=(
            "Listar reservas (superadmin: todas · admin: las de su agencia · cliente: las suyas). "
            "Cada reserva trae viaje_id, viaje_fecha, viaje_hora, paquete (nombre) y cliente_nombre. "
            "Filtro ?viaje_id= (solo esa salida; 400 si no es un número). Opcional: ?agencia_id= (solo superadmin), "
            "?search=, ?page= y ?page_size="
        ),
        manual_parameters=PARAMETROS_LISTA + [PARAMETRO_VIAJE, PARAMETRO_AGENCIA],
    )
    def get(self, request):
        yo = usuario_de(request)
        if es_conductor(yo):
            return prohibido("El conductor consulta sus pasajeros desde su viaje")
        lista = reservas_visibles(yo).select_related("usuario", "paquete", "viaje__bus")
        lista = filtrar_agencia_super(request, lista, "paquete__agencia_id")
        if "viaje_id" in request.query_params:
            viaje_id = entero_query(request, "viaje_id")
            if viaje_id is None:
                return Response({"message": "viaje_id debe ser un número"}, status=status.HTTP_400_BAD_REQUEST)
            # Se filtra sobre reservas_visibles: un viaje de otra agencia devuelve la lista vacía.
            lista = lista.filter(viaje_id=viaje_id)
        texto = texto_busqueda(request)
        if texto:
            lista = lista.filter(Q(paquete__nombre__icontains=texto) | Q(usuario__nombre_completo__icontains=texto))
        return Response(paginar(request, lista.order_by("id"), reserva_json))

    @swagger_auto_schema(
        operation_description=(
            "Guardar reserva CON sus sillas en una sola operación. viaje_id es OBLIGATORIO para todos "
            "(cliente y personal) y debe ser una salida de ese paquete; sin él responde 400. "
            "El cliente solo elige salidas PROGRAMADAS desde hoy. asientos: ids, ej. \"12,13\"; si una silla "
            "está ocupada EN ESA SALIDA responde 409 con 'ocupadas' y no guarda nada. Las sillas se guardan "
            f"{settings.RESERVA_MINUTOS_PAGO} minutos (vence_en) mientras llega el comprobante. "
            "clave_idempotencia (opcional): repetir la petición con la misma clave devuelve la misma reserva (200). "
            "Sin asientos se crea la reserva sola (compatibilidad: luego POST /asientoreserva/)."
        ),
        request_body=ReservaEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        yo = usuario_de(request)
        paquete = Paquete.objects.filter(id=entero_o_none(request.data.get("paquete_id"))).first()
        if paquete is None:
            return Response({"message": "El paquete no existe"}, status=status.HTTP_404_NOT_FOUND)
        personal = gestiona_agencia(yo, paquete.agencia_id)
        catalogo = agencias_de_catalogo(yo)
        if catalogo is not None and paquete.agencia_id not in catalogo:
            return prohibido("Ese paquete no es de tu agencia")
        if not personal and (paquete.estado != "activo" or not paquete.agencia.activo):
            return Response({"message": "Este paquete no está disponible para reservar"},
                            status=status.HTTP_400_BAD_REQUEST)
        clave = str(request.data.get("clave_idempotencia") or "").strip()[:64] or None
        if clave:
            repetida = Reserva.objects.filter(usuario=yo, clave_idempotencia=clave).first()
            if repetida:
                return Response(reserva_json(repetida), status=status.HTTP_200_OK)
        # La salida es obligatoria para TODOS (también el personal): así las reservas de dos
        # viajes del mismo paquete nunca se cruzan.
        viaje_id = entero_o_none(request.data.get("viaje_id"))
        viaje = Viaje.objects.select_related("bus").filter(id=viaje_id, paquete_id=paquete.id).first() if viaje_id else None
        if viaje is None:
            return Response({"message": "Elige una salida (viaje_id) de este paquete"},
                            status=status.HTTP_400_BAD_REQUEST)
        if not personal and (viaje.estado != Viaje.PROGRAMADO or viaje.fecha < hoy_colombia()):
            return Response({"message": "Esa salida ya no recibe reservas"}, status=status.HTTP_400_BAD_REQUEST)
        asiento_ids, error = leer_ids_asientos(request.data.get("asientos"))
        if error:
            return Response({"message": error}, status=status.HTTP_400_BAD_REQUEST)
        pasajero_nombre = str(request.data.get("pasajero_nombre") or "").strip()
        pasajero_documento = str(request.data.get("pasajero_documento") or "").strip()
        error = error_pasajero(pasajero_nombre, pasajero_documento)
        if error:
            return Response({"message": error}, status=status.HTTP_400_BAD_REQUEST)
        # Un cliente solo reserva para sí mismo, con la fecha del servidor, y siempre queda "pendiente".
        usuario_id = (request.data.get("usuario_id") or yo.id) if personal else yo.id
        estado = (request.data.get("estado") or "pendiente") if personal else "pendiente"
        if estado not in dict(ESTADOS_RESERVA):
            return Response({"message": "Estado de reserva no válido"}, status=status.HTTP_400_BAD_REQUEST)
        fecha = (request.data.get("fecha_reserva") if personal else None) or timezone.now()
        marcar_vencidas()
        try:
            with transaction.atomic():
                reserva = Reserva.objects.create(
                    fecha_reserva=fecha,
                    usuario_id=usuario_id,
                    paquete=paquete,
                    estado=estado,
                    viaje=viaje,
                    vence_en=plazo_de_pago(),
                    clave_idempotencia=clave,
                    pasajero_nombre=pasajero_nombre,
                    pasajero_documento=pasajero_documento,
                )
                if asiento_ids:
                    sillas, error = tomar_sillas(reserva, asiento_ids)
                    if error:
                        transaction.set_rollback(True)  # no queda ni la reserva ni ninguna silla
                        return error
                    AsientoReserva.objects.bulk_create([AsientoReserva(reserva=reserva, asiento=a) for a in sillas])
        except IntegrityError:
            # Dos envíos con la misma clave llegaron a la vez: se devuelve la que sí se guardó.
            repetida = Reserva.objects.filter(usuario=yo, clave_idempotencia=clave).first() if clave else None
            if repetida is None:
                raise
            return Response(reserva_json(repetida), status=status.HTTP_200_OK)
        return Response(reserva_json(reserva), status=status.HTTP_201_CREATED)


class ReservaIdView(APIView):
    def get(self, request, id):
        reserva = get_object_or_404(Reserva, id=id)
        if not puede_ver_reserva(usuario_de(request), reserva):
            return prohibido()
        return Response(reserva_json(reserva))

    @swagger_auto_schema(
        operation_description=(
            "Modificar una reserva. Solo la agencia del paquete (o superadmin). "
            "viaje_id: asigna la salida a una reserva ANTIGUA sin salida (sus sillas deben estar libres en "
            "esa salida, si no 409 con 'ocupadas') o mueve una reserva SIN sillas a otra salida del mismo paquete. "
            "Una reserva con sillas que ya tiene salida no se mueve (409): se cancela y se crea otra. "
            "Cambiar paquete_id exige que no tenga sillas y que venga viaje_id del paquete nuevo (400)."
        ),
        request_body=ReservaEditarEntrada,
    )
    def put(self, request, id):
        reservaB = get_object_or_404(Reserva.objects.select_related("paquete", "viaje__bus"), id=id)
        yo = usuario_de(request)
        if not gestiona_agencia(yo, reservaB.paquete.agencia_id):
            return prohibido("Solo la agencia puede modificar la reserva")
        if "paquete_id" in request.data and not gestiona_agencia(yo, agencia_del_paquete(request.data.get("paquete_id"))):
            return prohibido()
        tiene_sillas = AsientoReserva.objects.filter(reserva=reservaB).exists()
        nuevo_paquete = entero_o_none(request.data.get("paquete_id"))
        cambia_paquete = nuevo_paquete is not None and nuevo_paquete != reservaB.paquete_id
        if cambia_paquete and tiene_sillas:
            return Response({"message": "La reserva ya tiene sillas; cancélala y crea otra en el paquete nuevo"},
                            status=status.HTTP_409_CONFLICT)
        nuevo_viaje_id = entero_o_none(request.data.get("viaje_id"))
        if "viaje_id" in request.data and nuevo_viaje_id is None:
            return Response({"message": "viaje_id debe ser el número de una salida"},
                            status=status.HTTP_400_BAD_REQUEST)
        if cambia_paquete and nuevo_viaje_id is None:
            return Response({"message": "Al cambiar de paquete indica también la salida (viaje_id) del paquete nuevo"},
                            status=status.HTTP_400_BAD_REQUEST)
        nuevo_viaje = None
        if nuevo_viaje_id is not None and nuevo_viaje_id != reservaB.viaje_id:
            paquete_final = nuevo_paquete if cambia_paquete else reservaB.paquete_id
            nuevo_viaje = Viaje.objects.select_related("bus").filter(id=nuevo_viaje_id, paquete_id=paquete_final).first()
            if nuevo_viaje is None:
                return Response({"message": "Esa salida no es del paquete de la reserva"},
                                status=status.HTTP_400_BAD_REQUEST)
            if tiene_sillas and reservaB.viaje_id is not None:
                return Response({"message": "La reserva ya tiene sillas en otra salida; cancélala y crea una nueva"},
                                status=status.HTTP_409_CONFLICT)
        if "estado" in request.data:
            estado = request.data.get("estado")
            if estado not in dict(ESTADOS_RESERVA):
                return Response({"message": "Estado de reserva no válido"}, status=status.HTTP_400_BAD_REQUEST)
            if (reservaB.estado in ESTADOS_QUE_LIBERAN or reservaB.vencida) and estado == "pendiente":
                # Sus sillas ya pudieron venderse a otra persona: no se reactiva.
                return Response({"message": "Una reserva cancelada o vencida no se reactiva; crea una nueva"},
                                status=status.HTTP_409_CONFLICT)
            reservaB.estado = estado
        reservaB.fecha_reserva = request.data.get("fecha_reserva", reservaB.fecha_reserva)
        reservaB.usuario_id = request.data.get("usuario_id", reservaB.usuario_id)
        if nuevo_paquete is not None:
            reservaB.paquete_id = nuevo_paquete
        with transaction.atomic():
            if nuevo_viaje is not None:
                reservaB.viaje = nuevo_viaje
                if tiene_sillas:
                    # Reserva antigua: sus sillas deben existir en el bus de la salida y estar libres en ella.
                    ids = list(AsientoReserva.objects.filter(reserva=reservaB).values_list("asiento_id", flat=True))
                    _, error = tomar_sillas(reservaB, ids, excluir_reserva=reservaB.id)
                    if error:
                        return error
            reservaB.save()
        return Response(reserva_json(Reserva.objects.select_related("paquete", "usuario", "viaje__bus").get(id=reservaB.id)))

    @swagger_auto_schema(
        operation_description=(
            "Cancelar la reserva: pasa a 'cancelada' y sus sillas quedan libres. No borra nada "
            "(los pagos se conservan para la auditoría). Una reserva pagada solo la cancela la agencia."
        )
    )
    def delete(self, request, id):
        reserva = get_object_or_404(Reserva, id=id)
        yo = usuario_de(request)
        pagada = Pago.objects.filter(reserva=reserva, estado="aprobado").exists()
        es_dueno = reserva.usuario_id == yo.id and not pagada
        if not (es_dueno or gestiona_agencia(yo, reserva.paquete.agencia_id)):
            return prohibido("Una reserva pagada solo la puede cancelar la agencia")
        reserva.estado = "cancelada"
        reserva.save(update_fields=["estado"])
        return Response({"mensaje": "Reserva cancelada", "id": reserva.id})


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
        operation_description="Agregar una silla a una reserva (compatibilidad; lo recomendado es enviar 'asientos' "
                              "en POST /reserva/). 409 si la silla ya está reservada en la misma salida (o en una "
                              "reserva antigua sin salida del paquete); 400 si no es del bus de la salida o si la "
                              "reserva está cancelada o vencida.",
        request_body=AsientoReservaEntrada,
    )
    def post(self, request):
        asiento_id = entero_o_none(request.data.get("asiento_id"))
        reserva_id = entero_o_none(request.data.get("reserva_id"))
        reserva = Reserva.objects.select_related("paquete", "viaje__bus").filter(id=reserva_id).first()
        if asiento_id is None or reserva is None:
            return Response({"message": "Asiento o reserva no existe"}, status=status.HTTP_400_BAD_REQUEST)
        yo = usuario_de(request)
        if not (reserva.usuario_id == yo.id or gestiona_agencia(yo, reserva.paquete.agencia_id)):
            return prohibido("Esa reserva no es tuya")
        if reserva.estado in ESTADOS_QUE_LIBERAN or reserva.vencida:
            return Response({"message": "La reserva está cancelada o vencida"}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            sillas, error = tomar_sillas(reserva, [asiento_id])
            if error:
                return error
            AsientoReserva.objects.create(asiento=sillas[0], reserva=reserva)
        return Response({"mensaje": "Asiento reservado correctamente", "id": reserva.id})


class AsientoReservaIdView(APIView):
    permission_classes = [SoloPersonal]

    def get(self, request, id):
        ar = get_object_or_404(AsientoReserva, id=id)
        if not gestiona_agencia(usuario_de(request), ar.reserva.paquete.agencia_id):
            return prohibido()
        return Response({"id": ar.id, "asiento_id": ar.asiento_id, "reserva_id": ar.reserva_id})

    @swagger_auto_schema(
        operation_description="Cambiar la silla (o la reserva) de un registro. Aplica las mismas reglas que "
                              "POST /asientoreserva/: 409 si la silla nueva ya está vendida en esa salida.",
        request_body=AsientoReservaEntrada,
    )
    def put(self, request, id):
        arB = get_object_or_404(AsientoReserva, id=id)
        yo = usuario_de(request)
        if not gestiona_agencia(yo, arB.reserva.paquete.agencia_id):
            return prohibido()
        reserva = Reserva.objects.select_related("paquete", "viaje__bus").filter(
            id=entero_o_none(request.data.get("reserva_id")) or arB.reserva_id).first()
        asiento_id = entero_o_none(request.data.get("asiento_id")) or arB.asiento_id
        if reserva is None or not gestiona_agencia(yo, reserva.paquete.agencia_id):
            return prohibido()
        with transaction.atomic():
            sillas, error = tomar_sillas(reserva, [asiento_id], excluir_asiento_reserva=arB.id)
            if error:
                return error
            arB.asiento = sillas[0]
            arB.reserva = reserva
            arB.save()
        return Response({"mensaje": "Asiento reservado actualizado"})

    def delete(self, request, id):
        ar = get_object_or_404(AsientoReserva, id=id)
        if not gestiona_agencia(usuario_de(request), ar.reserva.paquete.agencia_id):
            return prohibido()
        ar.delete()
        return Response({"mensaje": "Asiento reservado eliminado"})


class PaquetePasajerosView(APIView):
    @swagger_auto_schema(
        operation_description=(
            "Pasajeros del paquete (solo la agencia o superadmin). Cada fila trae viaje_id, viaje_fecha y "
            "viaje_hora para no mezclar salidas; vienen ordenados por salida. Con ?viaje_id= solo los de esa "
            "salida (400 si no es de este paquete). Las reservas antiguas sin salida traen viaje_id null."
        ),
        manual_parameters=[PARAMETRO_VIAJE],
    )
    def get(self, request, paquete_id):
        agencia_id = agencia_del_paquete(paquete_id)
        if agencia_id is None:
            return Response({"message": "El paquete no existe"}, status=status.HTTP_404_NOT_FOUND)
        if not gestiona_agencia(usuario_de(request), agencia_id):
            return prohibido("El conductor consulta los pasajeros desde su viaje")
        lista = Reserva.objects.filter(paquete_id=paquete_id).exclude(estado__in=ESTADOS_QUE_LIBERAN)
        if "viaje_id" in request.query_params:
            viaje = Viaje.objects.filter(id=entero_query(request, "viaje_id"), paquete_id=paquete_id).first()
            if viaje is None:
                return Response({"message": "Esa salida no es de este paquete"}, status=status.HTTP_400_BAD_REQUEST)
            lista = reservas_del_viaje(viaje)
        lista = lista.select_related("paquete", "viaje").order_by("viaje__fecha", "viaje__hora", "id")
        return Response([pasajero_json(r) for r in lista])


class PaqueteAbordarView(APIView):
    """Compatibilidad para el panel: el personal marca abordaje por paquete con la misma regla de pago."""

    @swagger_auto_schema(
        operation_description=(
            "Registrar abordaje desde el panel (solo la agencia o superadmin). viaje_id es OBLIGATORIO: "
            "solo aborda una reserva de ESA salida (409 'otro_viaje' si es de otra salida del mismo paquete). "
            "Misma regla que /viaje/<id>/abordar/: ABORDO exige el último pago aprobado."
        ),
        request_body=PaqueteAbordarEntrada,
    )
    def post(self, request, paquete_id):
        agencia_id = agencia_del_paquete(paquete_id)
        if agencia_id is None:
            return Response({"message": "El paquete no existe"}, status=status.HTTP_404_NOT_FOUND)
        if not gestiona_agencia(usuario_de(request), agencia_id):
            return prohibido("El conductor registra el abordaje desde su viaje")
        viaje_id = entero_o_none(request.data.get("viaje_id"))
        viaje = Viaje.objects.filter(id=viaje_id, paquete_id=paquete_id).first() if viaje_id else None
        if viaje is None:
            return Response({"message": "Indica la salida (viaje_id) de este paquete en la que aborda el pasajero"},
                            status=status.HTTP_400_BAD_REQUEST)
        if viaje.estado == Viaje.COMPLETADO:
            return Response({"message": "El viaje ya finalizó"}, status=status.HTTP_409_CONFLICT)
        return registrar_abordaje(request, reservas_del_viaje(viaje), viaje)


def reservas_del_viaje(viaje):
    """Pasajeros de un viaje: reservas no canceladas ni vencidas de su paquete, de ese viaje o antiguas
    sin viaje asignado (nunca las de otra salida del mismo paquete)."""
    return (
        Reserva.objects.filter(paquete_id=viaje.paquete_id)
        .exclude(estado__in=ESTADOS_QUE_LIBERAN)
        .filter(Q(viaje=viaje) | Q(viaje__isnull=True))
    )


def documento_pasajero(r, usuario):
    """Documento de quien viaja: el del pasajero indicado o, si viaja el titular, el del titular."""
    if r.pasajero_nombre or r.pasajero_documento:
        return r.pasajero_documento
    return usuario.numero_documento if usuario else ""


def pasajero_json(r):
    usuario = Usuario.objects.filter(id=r.usuario_id).first()
    asientos = list(AsientoReserva.objects.filter(reserva=r).values_list("asiento__numero_asiento", flat=True))
    pago = estado_pago(r)
    viaje = r.viaje
    return {
        "id": r.id,
        "nombre": nombre_pasajero(r, usuario),
        "documento": documento_pasajero(r, usuario),
        "detalle": r.paquete.nombre if r.paquete_id else "",
        "codigo": codigo_reserva(r.id),
        "asiento": ",".join(str(n) for n in asientos) or "-",
        "estado": r.abordado,
        "pago_estado": pago,
        "puede_abordar": pago == "aprobado",
        # Salida de la reserva (null = reserva antigua sin salida).
        "viaje_id": r.viaje_id,
        "viaje_fecha": viaje.fecha.isoformat() if viaje else None,
        "viaje_hora": viaje.hora.strftime("%H:%M") if viaje else None,
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
    @swagger_auto_schema(operation_description="Pasajeros del viaje con su documento y el estado de su pago. Conductor del bus o admin.")
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
            "ABORDO | AUSENTE | PENDIENTE. ABORDO exige el último pago aprobado (409 con 'motivo' si no). "
            "Responde el pasajero: nombre, documento, detalle (paquete), asiento, pago_estado, viaje_fecha, viaje_hora."
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
    """GPS, chat y novedades de una salida: su agencia, su conductor o un cliente de ESA salida."""
    return (
        gestiona_agencia(yo, viaje.bus.agencia_id)
        or conductor_autorizado(yo, viaje)
        or es_cliente_de_viaje(yo, viaje)
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


def conductores_por_bus(bus_ids):
    """{bus_id: nombre del conductor asignado} en una sola consulta."""
    asignaciones = Bus_Conductor.objects.filter(bus_id__in=bus_ids).select_related("conductor").order_by("id")
    return {a.bus_id: a.conductor.nombre_completo for a in asignaciones}


def novedad_json(n, conductores=None):
    viaje = n.viaje
    paquete = n.paquete or (viaje.paquete if viaje else None)
    bus_id = viaje.bus_id if viaje else None
    if conductores is None:
        conductores = conductores_por_bus([bus_id]) if bus_id else {}
    return {"id": n.id, "paquete_id": n.paquete_id, "viaje_id": n.viaje_id, "tipo": n.tipo,
            "detalle": n.detalle, "fecha": n.fecha, "resuelta": n.resuelta,
            "paquete": paquete.nombre if paquete else None,
            "placa": viaje.bus.placa if viaje else None,
            "conductor": conductores.get(bus_id)}


def agencia_de_novedad(n):
    if n.paquete_id:
        return n.paquete.agencia_id
    return n.viaje.bus.agencia_id if n.viaje_id else None


class NovedadView(APIView):
    @swagger_auto_schema(
        operation_description=(
            "Novedades de la agencia (personal), con paquete, placa y conductor. "
            "Filtro ?viaje_id=. Opcional: ?search=, ?page= y ?page_size="
        ),
        manual_parameters=PARAMETROS_LISTA,
    )
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
        texto = texto_busqueda(request)
        if texto:
            lista = lista.filter(Q(tipo__icontains=texto) | Q(detalle__icontains=texto))
        lista = lista.select_related("paquete", "viaje__paquete", "viaje__bus").order_by("-fecha", "-id")
        conductores = conductores_por_bus(lista.exclude(viaje__isnull=True).values("viaje__bus_id"))
        return Response(paginar(request, lista, lambda n: novedad_json(n, conductores)))

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


class NovedadIdView(APIView):
    @swagger_auto_schema(operation_description="Marcar una novedad como resuelta o no: {resuelta: true|false}")
    def put(self, request, id):
        n = get_object_or_404(Novedad.objects.select_related("paquete", "viaje__bus", "viaje__paquete"), id=id)
        if not gestiona_agencia(usuario_de(request), agencia_de_novedad(n)):
            return prohibido("Solo la agencia de la novedad puede cambiarla")
        if "resuelta" not in request.data:
            return Response({"message": "Indica resuelta: true o false"}, status=status.HTTP_400_BAD_REQUEST)
        valor = request.data.get("resuelta")
        n.resuelta = valor is True or str(valor).lower() in ("true", "1", "si", "sí")
        n.save()
        return Response(novedad_json(n))

    @swagger_auto_schema(operation_description="Eliminar una novedad")
    def delete(self, request, id):
        n = get_object_or_404(Novedad.objects.select_related("paquete", "viaje__bus"), id=id)
        if not gestiona_agencia(usuario_de(request), agencia_de_novedad(n)):
            return prohibido("Solo la agencia de la novedad puede eliminarla")
        n.delete()
        return Response({"mensaje": "Novedad eliminada"})


def chat_json(m):
    autor = m.usuario
    return {"id": m.id, "paquete_id": m.paquete_id, "viaje_id": m.viaje_id, "usuario_id": m.usuario_id,
            "autor": autor.nombre_completo if autor else "", "rol_id": autor.rol_id if autor else None,
            "texto": m.texto, "fecha": m.fecha}


class ChatView(APIView):
    @swagger_auto_schema(operation_description=(
        "Mensajes de un viaje (?viaje_id=) o de un paquete (?paquete_id=), con autor y rol_id. "
        "Un cliente solo ve sus mensajes y los del conductor o la agencia."
    ))
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
        if yo.rol_id == ROL_CLIENTE:
            # Privacidad entre pasajeros: cada cliente ve lo suyo y lo que escriben conductor y agencia.
            lista = lista.filter(Q(usuario=yo) | ~Q(usuario__rol_id=ROL_CLIENTE))
        return Response([chat_json(m) for m in lista.select_related("usuario").order_by("fecha", "id")])

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
