from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from usuarios.paginacion import PARAMETRO_AGENCIA, PARAMETROS_LISTA, entero_query, paginar, texto_busqueda
from .serializer import (
    TipoBusEntrada, TipoBusEditarEntrada, BusEntrada, AsientoEntrada, MensajeSalida, BusConductorEntrada, BusTipoBusEntrada,AsientosBusEntrada
)
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from django.db import IntegrityError, transaction
from django.db.models import ProtectedError, Q
from django.utils import timezone

from .models import Bus_Conductor, TipoBus, Bus, BusTipoBus, Asiento, Viaje, ParadaCumplida
from paquetes.models import Itinerario, Paquete, ordenar_itinerario
from reservas.models import AsientoReserva, Reserva, marcar_vencidas, reservas_activas, reservas_que_ocupan
from usuarios.models import Agencia, Usuario, UsuarioAgencia

from usuarios.permisos import (
    ROL_CLIENTE, ROL_CONDUCTOR, LecturaPublica, agencia_para_guardar, agencias_de, agencias_de_catalogo, filtrar_agencia_super, filtrar_catalogo,
    es_admin, es_conductor, es_super, gestiona_agencia, prohibido, usuario_de,
)


def hoy_colombia():
    """Fecha de hoy en Colombia. TIME_ZONE es UTC (para guardar fechas); las salidas se programan en hora local."""
    return timezone.localtime(timezone.now(), ZoneInfo("America/Bogota")).date()


class VistaCatalogo(APIView):
    """Lectura pública; crear, editar y borrar solo administrador o superadministrador."""
    permission_classes = [LecturaPublica]



def tipo_bus_de(yo, tipo_bus_id):
    """(tipo, error). El tipo de bus existe y es de una agencia que administra quien hace la petición."""
    tipo = TipoBus.objects.filter(id=entero_o_none(tipo_bus_id)).first()
    if tipo is None:
        return None, Response({"message": "El tipo de bus no existe"}, status=status.HTTP_404_NOT_FOUND)
    if not gestiona_agencia(yo, tipo.agencia_id):
        return None, prohibido("Ese tipo de bus es de otra agencia")
    return tipo, None


def hay_ventas_en_viajes(viajes):
    """True si alguna reserva activa de esas salidas ya tiene sillas."""
    return AsientoReserva.objects.filter(reserva__in=reservas_activas().filter(viaje__in=viajes)).exists()


def tipo_bus_json(tipo):
    return {
        "id": tipo.id,
        "nombre": tipo.nombre,
        "agencia_id": tipo.agencia_id,
        "capacidad": tipo.capacidad,
        "descripcion": tipo.descripcion,
    }


def tipos_bus_visibles(yo):
    """Admin y conductor: solo los tipos de sus agencias. Superadmin, cliente y anónimo: todos
    (la app del cliente lee la capacidad del bus de cada salida)."""
    lista = TipoBus.objects.all()
    if es_admin(yo) or es_conductor(yo):
        return lista.filter(agencia_id__in=agencias_de(yo))
    return lista


def error_de_datos(serializador):
    """400 con el primer error del serializer, en el formato {"message": "campo: detalle"}."""
    campo, errores = next(iter(serializador.errors.items()))
    return Response({"message": f"{campo}: {errores[0]}"}, status=status.HTTP_400_BAD_REQUEST)


class TipoBusView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description=(
            "Listar tipos de bus. Admin y conductor: solo los de su agencia. Superadmin, cliente y anónimo: todos. "
            "Superadmin: ?agencia_id= limita a esa agencia."
        ),
        manual_parameters=[PARAMETRO_AGENCIA],
    )
    def get(self, request):
        lista = filtrar_agencia_super(request, tipos_bus_visibles(usuario_de(request))).order_by("id")
        return Response([tipo_bus_json(tipo) for tipo in lista])

    @swagger_auto_schema(
        operation_description=(
            "Guardar tipo de bus. El admin no envía agencia_id (sale de su sesión; si la envía y no es suya: 403). "
            "El superadmin sí la indica. capacidad > 0. Responde 201 con el tipo creado (incluye id)."
        ),
        request_body=TipoBusEntrada,
        responses={201: "Tipo de bus creado", 400: "Datos inválidos", 403: "Agencia ajena"},
    )
    def post(self, request):
        entrada = TipoBusEntrada(data=request.data)
        if not entrada.is_valid():
            return error_de_datos(entrada)
        datos = entrada.validated_data
        agencia_id, error = agencia_para_guardar(usuario_de(request), datos.get("agencia_id"))
        if error:
            return Response({"message": error[1]}, status=error[0])
        tipo = TipoBus.objects.create(
            nombre=datos["nombre"].strip(),
            agencia_id=agencia_id,
            capacidad=datos["capacidad"],
            descripcion=datos.get("descripcion") or "",
        )
        return Response({**tipo_bus_json(tipo), "mensaje": "Tipo de bus almacenado correctamente"},
                        status=status.HTTP_201_CREATED)


class TipoBusIdView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description=(
            "Actualizar tipo de bus (campos opcionales: los que no llegan se conservan). Solo el admin de su "
            "agencia o el superadmin. Cambiar de agencia (solo superadmin) un tipo que ya usan buses: 409."
        ),
        request_body=TipoBusEditarEntrada,
        responses={200: "Tipo de bus actualizado", 400: "Datos inválidos", 403: "Agencia ajena", 409: "En uso"},
    )
    def put(self, request, id):
        yo = usuario_de(request)
        tipoBusB, error = tipo_bus_de(yo, id)
        if error:
            return error
        entrada = TipoBusEditarEntrada(data=request.data)
        if not entrada.is_valid():
            return error_de_datos(entrada)
        datos = entrada.validated_data
        agencia_id, error = agencia_para_guardar(yo, datos.get("agencia_id"), actual=tipoBusB.agencia_id)
        if error:
            return Response({"message": error[1]}, status=error[0])
        if agencia_id != tipoBusB.agencia_id and BusTipoBus.objects.filter(tipo_bus=tipoBusB).exists():
            return Response({"message": "El tipo de bus ya lo usan buses de su agencia; no se puede pasar a otra"},
                            status=status.HTTP_409_CONFLICT)
        tipoBusB.nombre = datos.get("nombre", tipoBusB.nombre).strip()
        tipoBusB.agencia_id = agencia_id
        tipoBusB.capacidad = datos.get("capacidad", tipoBusB.capacidad)
        tipoBusB.descripcion = datos.get("descripcion", tipoBusB.descripcion)
        tipoBusB.save()
        return Response({**tipo_bus_json(tipoBusB), "mensaje": "Tipo de bus actualizado"})

    @swagger_auto_schema(
        operation_description="Eliminar tipo de bus"
    )
    def delete(self, request, id):
        tipoBusEliminar, error = tipo_bus_de(usuario_de(request), id)
        if error:
            return error
        try:
            tipoBusEliminar.delete()
        except ProtectedError:
            return Response({"message": "El tipo de bus está en uso (buses o sillas reservadas)"},
                            status=status.HTTP_409_CONFLICT)
        return Response({"mensaje": "Tipo de bus eliminado"})

    @swagger_auto_schema(
        operation_description="Listar tipo de bus por id"
    )
    def get(self, request, id):
        registroEncontrado = get_object_or_404(tipos_bus_visibles(usuario_de(request)), id=id)
        return Response(tipo_bus_json(registroEncontrado))


def tipo_bus_ids_de(request, required=False):
    tipo_bus_ids = request.data.get("tipo_bus_ids")
    if tipo_bus_ids is None:
        tipo_bus_id = request.data.get("tipo_bus_id")
        if tipo_bus_id is None:
            if required:
                return None, Response({"mensaje": "Indica tipo_bus_id o tipo_bus_ids"}, status=status.HTTP_400_BAD_REQUEST)
            return None, None
        tipo_bus_ids = [tipo_bus_id]
    elif isinstance(tipo_bus_ids, str):
        tipo_bus_ids = tipo_bus_ids.split(",")

    try:
        ids = list(dict.fromkeys(int(tipo_bus_id) for tipo_bus_id in tipo_bus_ids))
    except (TypeError, ValueError):
        return None, Response({"mensaje": "tipo_bus_ids debe contener IDs enteros"}, status=status.HTTP_400_BAD_REQUEST)

    if any(tipo_bus_id < 1 for tipo_bus_id in ids):
        return None, Response({"mensaje": "Los IDs de tipo de bus deben ser positivos"}, status=status.HTTP_400_BAD_REQUEST)
    if not ids:
        return None, Response({"mensaje": "Asocia al menos un tipo de bus"}, status=status.HTTP_400_BAD_REQUEST)
    if ids:
        existentes = set(TipoBus.objects.filter(id__in=ids).values_list("id", flat=True))
        faltantes = [tipo_bus_id for tipo_bus_id in ids if tipo_bus_id not in existentes]
        if faltantes:
            return None, Response({"mensaje": f"No existen tipos de bus: {faltantes}"}, status=status.HTTP_404_NOT_FOUND)
    return ids, None


def validar_tipos_bus_de_agencia(agencia_id, tipo_bus_ids):
    otros_tipos = TipoBus.objects.filter(id__in=tipo_bus_ids).exclude(agencia_id=agencia_id)
    if otros_tipos.exists():
        return Response(
            {"mensaje": "Cada tipo de bus debe pertenecer a la misma agencia del bus"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return None


##################################################################################################
def bus_json(bus):
    tipos_bus = list(bus.tipos_bus.order_by("id"))
    tipo_bus = tipos_bus[0] if tipos_bus else None
    return {
        "id": bus.id,
        "placa": bus.placa,
        "agencia_id": bus.agencia_id,
        "tipo_bus_id": tipo_bus.id if tipo_bus else None,
        "tipo_bus_ids": [tipo.id for tipo in tipos_bus],
        "tipos_bus": [
            {"id": tipo.id, "nombre": tipo.nombre, "capacidad": tipo.capacidad}
            for tipo in tipos_bus
        ],
        "tipo_bus_nombre": tipo_bus.nombre if tipo_bus else None,
        "capacidad": tipo_bus.capacidad if tipo_bus else None,
        "marca": bus.marca,
        "modelo": bus.modelo,
        "estado": bus.estado,
        "fecha_registro": bus.fecha_registro,
    }


ESTADOS_BUS = dict(Bus.ESTADOS)  # activo, mantenimiento, inactivo


def buses_visibles(yo):
    """Multitenant: superadmin ve todos; admin y conductor, solo los de su(s) agencia(s);
    cliente o sin sesión, ninguno (la app del cliente recibe placa y tipo de bus dentro de /viaje/)."""
    base = Bus.objects.prefetch_related("tipos_bus")
    if es_super(yo):
        return base
    if es_admin(yo) or es_conductor(yo):
        return base.filter(agencia_id__in=agencias_de(yo))
    return base.none()


def viajes_pendientes_del_bus(bus):
    """Viajes que todavía dependen del bus: EN_CURSO, o PROGRAMADOS desde hoy."""
    return Viaje.objects.select_related("bus", "paquete").filter(
        Q(estado=Viaje.EN_CURSO) | Q(estado=Viaje.PROGRAMADO, fecha__gte=hoy_colombia()), bus=bus,
    )


def leer_estado_bus(valor, actual="activo"):
    """(estado, error). Vacío = se conserva el actual ("activo" al crear). Acepta mayúsculas ("Activo")."""
    estado = str(valor).strip().lower() if valor not in (None, "") else actual
    if estado not in ESTADOS_BUS:
        return None, Response({"message": "Estado no válido: usa activo, inactivo o mantenimiento"},
                              status=status.HTTP_400_BAD_REQUEST)
    return estado, None


def agencia_del_bus(yo, datos, bus=None):
    """(agencia_id, error). La agencia NUNCA se toma del body para el admin: sale de su sesión.
    - Superadmin: la indica en agencia_id (al editar, si no la envía se conserva la del bus).
    - Admin al editar: la del bus (debe ser una de sus agencias; no puede pasarlo a otra).
    - Admin al crear: su agencia; si pertenece a varias, agencia_id debe ser una de ellas."""
    if es_super(yo):
        agencia_id = entero_o_none(datos.get("agencia_id")) or (bus.agencia_id if bus else None)
        if agencia_id is None or not Agencia.objects.filter(id=agencia_id).exists():
            return None, Response({"message": "Indica una agencia (agencia_id) que exista"},
                                  status=status.HTTP_400_BAD_REQUEST)
        return agencia_id, None
    mias = agencias_de(yo) if es_admin(yo) else set()
    if bus is not None:
        if bus.agencia_id not in mias:
            return None, prohibido("Solo puedes editar buses de tu agencia")
        return bus.agencia_id, None
    if not mias:
        return None, prohibido("Solo el administrador de una agencia registra buses")
    if len(mias) == 1:
        return next(iter(mias)), None
    pedida = entero_o_none(datos.get("agencia_id"))
    if pedida in mias:
        return pedida, None
    return None, Response({"message": "Perteneces a varias agencias: indica agencia_id de una de ellas"},
                          status=status.HTTP_400_BAD_REQUEST)


def error_placa(placa, bus=None):
    """Mensaje si la placa está vacía o ya la usa otro bus; None si sirve."""
    placa = str(placa or "").strip()
    if not placa:
        return "La placa es obligatoria"
    repetidas = Bus.objects.filter(placa__iexact=placa)
    if bus is not None:
        repetidas = repetidas.exclude(id=bus.id)
    return "Ya existe un bus con esa placa" if repetidas.exists() else None


class BusView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description=(
            "Listar Buses con tipo_bus_nombre y capacidad. Superadmin: todos. Admin y conductor: solo los de "
            "su agencia. Cliente o sin sesión: lista vacía. Opcional: ?agencia_id= (solo superadmin), ?search=, "
            "?page= y ?page_size="
        ),
        manual_parameters=PARAMETROS_LISTA + [PARAMETRO_AGENCIA],
    )
    def get(self, request):
        busLista = filtrar_agencia_super(request, buses_visibles(usuario_de(request)))
        texto = texto_busqueda(request)
        if texto:
            busLista = busLista.filter(
                Q(placa__icontains=texto) | Q(marca__icontains=texto) | Q(modelo__icontains=texto)
            )
        return Response(paginar(request, busLista.order_by("id"), bus_json))

    @swagger_auto_schema(
        operation_description=(
            "Guardar Bus. Admin: la agencia sale de su sesión (agencia_id del body se ignora). "
            "Superadmin: agencia_id obligatorio. estado: activo (por defecto), inactivo o mantenimiento; "
            "otro valor responde 400. El tipo de bus debe ser de la misma agencia (400)."
        ),
        request_body=BusEntrada,
        responses={200: MensajeSalida}
    )
    def post(self, request):
        yo = usuario_de(request)
        agencia_id, error = agencia_del_bus(yo, request.data)
        if error:
            return error
        tipo_bus_ids, error = tipo_bus_ids_de(request, required=True)
        if error:
            return error
        error = validar_tipos_bus_de_agencia(agencia_id, tipo_bus_ids)
        if error:
            return error
        estado, error = leer_estado_bus(request.data.get("estado"))
        if error:
            return error
        error = error_placa(request.data.get("placa"))
        if error:
            return Response({"message": error}, status=status.HTTP_400_BAD_REQUEST)
        sillas, error = leer_sillas(request.data)
        if error:
            return error
        tipo = TipoBus.objects.get(id=min(tipo_bus_ids))
        error = error_reducir_sillas(tipo, sillas)
        if error:
            return error

        with transaction.atomic():
            bus = Bus.objects.create(
                placa=request.data.get("placa"),
                agencia_id=agencia_id,
                marca=request.data.get("marca"),
                modelo=request.data.get("modelo"),
                estado=estado,
                fecha_registro=request.data.get("fecha_registro")
            )
            bus.tipos_bus.set(tipo_bus_ids)
            guardar_sillas(tipo, sillas)
        return Response({"mensaje": "Bus almacenado correctamente", "id": bus.id})


class BusIdView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Consultar bus por id. 404 si no existe o es de otra agencia (superadmin ve todos)."
    )
    def get(self, request, id):
        registroEncontrado = get_object_or_404(buses_visibles(usuario_de(request)), id=id)
        return Response(bus_json(registroEncontrado))

    @swagger_auto_schema(
        operation_description=(
            "Actualizar bus. Los campos que no se envían conservan su valor. Admin: el bus debe ser de su "
            "agencia y no puede pasarlo a otra (agencia_id del body se ignora). Superadmin: puede cambiar "
            "agencia_id si el bus no tiene viajes (409). estado: activo, inactivo o mantenimiento (400 si no). "
            "No pasa a inactivo/mantenimiento si tiene viajes EN_CURSO o PROGRAMADOS desde hoy: 409 con 'viajes'."
        ),
        request_body=BusEntrada
    )
    def put(self, request, id):
        busB = get_object_or_404(Bus, id=id)
        yo = usuario_de(request)
        if not gestiona_agencia(yo, busB.agencia_id):
            return prohibido("Solo puedes editar buses de tu agencia")
        agencia_id, error = agencia_del_bus(yo, request.data, busB)
        if error:
            return error
        if agencia_id != busB.agencia_id and Viaje.objects.filter(bus=busB).exists():
            return Response({"message": "El bus tiene viajes; no se puede pasar a otra agencia"},
                            status=status.HTTP_409_CONFLICT)
        tipo_bus_ids, error = tipo_bus_ids_de(request)
        if error:
            return error
        actuales = sorted(busB.tipos_bus.values_list("id", flat=True))
        nuevos = sorted(tipo_bus_ids) if tipo_bus_ids is not None else actuales
        error = validar_tipos_bus_de_agencia(agencia_id, nuevos)
        if error:
            return error
        if nuevos != actuales and hay_ventas_en_viajes(Viaje.objects.filter(bus=busB)):
            # Las sillas vendidas son del mapa del tipo actual: cambiarlo dejaría esas ventas fuera del bus.
            return Response({"message": "El bus tiene sillas vendidas en sus salidas; no se puede cambiar su tipo"},
                            status=status.HTTP_409_CONFLICT)
        estado, error = leer_estado_bus(request.data.get("estado"), busB.estado)
        if error:
            return error
        if estado != "activo" and busB.estado == "activo":
            pendientes = list(viajes_pendientes_del_bus(busB))
            if pendientes:
                return Response({
                    "message": f"El bus tiene {len(pendientes)} viaje(s) programado(s) o en curso; "
                               f"cámbialos a otro bus o elimínalos antes de pasarlo a {estado}",
                    "viajes": [viaje_json(v) for v in pendientes],
                }, status=status.HTTP_409_CONFLICT)
        if request.data.get("placa"):
            error = error_placa(request.data.get("placa"), busB)
            if error:
                return Response({"message": error}, status=status.HTTP_400_BAD_REQUEST)
        sillas, error = leer_sillas(request.data)
        if error:
            return error
        tipo = TipoBus.objects.filter(id__in=nuevos).order_by("id").first()
        error = error_reducir_sillas(tipo, sillas)
        if error:
            return error
        busB.placa = request.data.get("placa") or busB.placa
        busB.agencia_id = agencia_id
        busB.marca = request.data.get("marca") or busB.marca
        busB.modelo = request.data.get("modelo") or busB.modelo
        busB.estado = estado
        busB.fecha_registro = request.data.get("fecha_registro") or busB.fecha_registro
        with transaction.atomic():
            busB.save()
            if nuevos != actuales:
                busB.tipos_bus.set(nuevos)
            guardar_sillas(tipo, sillas)
        return Response({"mensaje": "Bus actualizado"})

    @swagger_auto_schema(
        operation_description="Eliminar bus"
    )
    def delete(self, request, id):
        busEliminar = get_object_or_404(Bus, id=id)
        if not gestiona_agencia(usuario_de(request), busEliminar.agencia_id):
            return prohibido("Solo puedes eliminar buses de tu agencia")
        try:
            busEliminar.delete()
        except ProtectedError:
            return Response({"message": "El bus tiene viajes programados; elimínalos primero"},
                            status=status.HTTP_409_CONFLICT)
        return Response({"mensaje": "Bus eliminado"})


class BusTipoBusView(VistaCatalogo):
    @swagger_auto_schema(operation_description="Listar relaciones entre buses y tipos de bus")
    def get(self, request):
        relaciones = BusTipoBus.objects.order_by("id")
        return Response([
            {"id": relacion.id, "bus_id": relacion.bus_id, "tipo_bus_id": relacion.tipo_bus_id}
            for relacion in relaciones
        ])

    @swagger_auto_schema(
        operation_description="Asociar un tipo de bus a un bus",
        request_body=BusTipoBusEntrada,
    )
    def post(self, request):
        bus = get_object_or_404(Bus, id=request.data.get("bus_id"))
        tipo_bus = get_object_or_404(TipoBus, id=request.data.get("tipo_bus_id"))
        if not gestiona_agencia(usuario_de(request), bus.agencia_id):
            return prohibido("Solo puedes asociar tipos a buses de tu agencia")
        error = validar_tipos_bus_de_agencia(bus.agencia_id, [tipo_bus.id])
        if error:
            return error
        relacion, creada = BusTipoBus.objects.get_or_create(bus=bus, tipo_bus=tipo_bus)
        return Response(
            {"id": relacion.id, "bus_id": relacion.bus_id, "tipo_bus_id": relacion.tipo_bus_id},
            status=status.HTTP_201_CREATED if creada else status.HTTP_200_OK,
        )


class BusTipoBusIdView(VistaCatalogo):
    @swagger_auto_schema(operation_description="Listar una relación entre bus y tipo de bus")
    def get(self, request, id):
        relacion = get_object_or_404(BusTipoBus, id=id)
        return Response({"id": relacion.id, "bus_id": relacion.bus_id, "tipo_bus_id": relacion.tipo_bus_id})

    @swagger_auto_schema(
        operation_description="Actualizar una relación entre bus y tipo de bus",
        request_body=BusTipoBusEntrada,
    )
    def put(self, request, id):
        relacion = get_object_or_404(BusTipoBus, id=id)
        bus = get_object_or_404(Bus, id=request.data.get("bus_id"))
        tipo_bus = get_object_or_404(TipoBus, id=request.data.get("tipo_bus_id"))
        yo = usuario_de(request)
        if not gestiona_agencia(yo, relacion.bus.agencia_id) or not gestiona_agencia(yo, bus.agencia_id):
            return prohibido("Solo puedes editar relaciones de buses de tu agencia")
        error = validar_tipos_bus_de_agencia(bus.agencia_id, [tipo_bus.id])
        if error:
            return error
        duplicada = BusTipoBus.objects.exclude(id=id).filter(bus=bus, tipo_bus=tipo_bus).exists()
        if duplicada:
            return Response({"mensaje": "La relación ya existe"}, status=status.HTTP_409_CONFLICT)
        relacion.bus = bus
        relacion.tipo_bus = tipo_bus
        relacion.save()
        return Response({"id": relacion.id, "bus_id": relacion.bus_id, "tipo_bus_id": relacion.tipo_bus_id})

    @swagger_auto_schema(operation_description="Eliminar una relación entre bus y tipo de bus")
    def delete(self, request, id):
        relacion = get_object_or_404(BusTipoBus, id=id)
        if not gestiona_agencia(usuario_de(request), relacion.bus.agencia_id):
            return prohibido("Solo puedes eliminar relaciones de buses de tu agencia")
        if relacion.bus.tipos_bus.count() == 1:
            return Response(
                {"mensaje": "El bus debe conservar al menos un tipo asociado"},
                status=status.HTTP_409_CONFLICT,
            )
        relacion.delete()
        return Response({"mensaje": "Relación eliminada"})


class BusPlacaView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description=(
            "Busca un bus por su placa, solo entre los buses de tu agencia (superadmin: todos). "
            "Si no está responde {mensaje: 'Bus no encontrado'}."
        )
    )
    def get(self, request, placa):
        bus = buses_visibles(usuario_de(request)).filter(placa=placa).first()
        if not bus:
            return Response({"mensaje": "Bus no encontrado"})
        return Response(bus_json(bus))
        
def tipo_principal(bus):
    """Tipo de bus con el que se arma el mapa de sillas del bus: el primero (el mismo tipo_bus_id de bus_json)."""
    return bus.tipos_bus.order_by("id").first()


def leer_sillas(datos):
    """(sillas o None si no llegan, error 400). Es opcional para no romper a otros clientes del API."""
    valor = datos.get("sillas")
    if valor in (None, ""):
        return None, None
    entrada = AsientosBusEntrada(data={"cantidad": valor})
    if not entrada.is_valid():
        return None, Response({"message": "Las sillas deben ser un número entre 1 y 100"},
                              status=status.HTTP_400_BAD_REQUEST)
    return entrada.validated_data["cantidad"], None


def error_reducir_sillas(tipo, cantidad):
    """409 si quitar sillas tocaría alguna ya reservada; None si se puede guardar."""
    if cantidad is None or tipo is None:
        return None
    reservadas = AsientoReserva.objects.filter(
        asiento__tipo_bus=tipo, asiento__numero_asiento__gt=cantidad
    ).values_list("asiento__numero_asiento", flat=True).distinct()
    if reservadas:
        numeros = ", ".join(str(n) for n in sorted(reservadas))
        return Response({"message": f"No se puede reducir: las sillas {numeros} ya están reservadas"},
                        status=status.HTTP_409_CONFLICT)
    return None


def guardar_sillas(tipo, cantidad):
    """Deja las sillas 1..cantidad del tipo de bus. Son las que usa la app móvil para reservar."""
    if cantidad is None or tipo is None:
        return
    Asiento.objects.filter(tipo_bus=tipo, numero_asiento__gt=cantidad).delete()
    existentes = set(Asiento.objects.filter(tipo_bus=tipo).values_list("numero_asiento", flat=True))
    Asiento.objects.bulk_create([
        Asiento(tipo_bus=tipo, numero_asiento=n) for n in range(1, cantidad + 1) if n not in existentes
    ])
    tipo.capacidad = cantidad
    tipo.save(update_fields=["capacidad"])


def asientos_bus_json(bus):
    """Sillas del bus. El mapa es una plantilla del tipo de bus: todos los buses de ese tipo la comparten."""
    tipo = tipo_principal(bus)
    if tipo is None:
        return {"bus_id": bus.id, "placa": bus.placa, "tipo_bus_id": None, "tipo_bus_nombre": None,
                "capacidad": 0, "cantidad": 0, "buses_mismo_tipo": 0}
    return {
        "bus_id": bus.id,
        "placa": bus.placa,
        "tipo_bus_id": tipo.id,
        "tipo_bus_nombre": tipo.nombre,
        "capacidad": tipo.capacidad,
        "cantidad": Asiento.objects.filter(tipo_bus=tipo).count(),
        "buses_mismo_tipo": tipo.buses.count(),
    }


class BusAsientosView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description=(
            "Cuántas sillas tiene el bus. Las sillas pertenecen al TIPO de bus, así que "
            "buses_mismo_tipo indica cuántos buses comparten ese mapa."
        ),
    )
    def get(self, request, id):
        bus = get_object_or_404(buses_visibles(usuario_de(request)), id=id)
        return Response(asientos_bus_json(bus))

    @swagger_auto_schema(
        operation_description=(
            "Asignar el número de sillas del bus: {cantidad} de 1 a 100. Crea las sillas 1..cantidad del tipo "
            "de bus, borra las que sobren y actualiza la capacidad. Afecta a todos los buses de ese tipo. "
            "Solo el administrador de la agencia del bus (o el superadministrador). "
            "409 si hay que quitar sillas que ya están reservadas."
        ),
        request_body=AsientosBusEntrada,
    )
    def post(self, request, id):
        bus = get_object_or_404(Bus, id=id)
        yo = usuario_de(request)
        # El tipo de bus también debe ser de la agencia: no se tocan plantillas de otra agencia.
        if not gestiona_agencia(yo, bus.agencia_id):
            return prohibido("Solo puedes cambiar las sillas de los buses de tu agencia")
        tipo = tipo_principal(bus)
        if tipo is None:
            return Response({"message": "El bus no tiene tipo de bus; asígnale uno en Editar bus"},
                            status=status.HTTP_400_BAD_REQUEST)
        if not gestiona_agencia(yo, tipo.agencia_id):
            return prohibido("El tipo de bus de este bus es de otra agencia; cámbialo en Editar bus por uno de tu agencia")
        entrada = AsientosBusEntrada(data=request.data)
        if not entrada.is_valid():
            return Response({"message": "La cantidad debe ser un número entre 1 y 100", "errores": entrada.errors},
                            status=status.HTTP_400_BAD_REQUEST)
        cantidad = entrada.validated_data["cantidad"]

        error = error_reducir_sillas(tipo, cantidad)
        if error:
            return error
        with transaction.atomic():
            guardar_sillas(tipo, cantidad)

        respuesta = asientos_bus_json(bus)
        respuesta["mensaje"] = f"El bus {bus.placa} quedó con {cantidad} sillas"
        return Response(respuesta)


######################################################################################################################
def bus_conductor_json(asignacion):
    return {
        "id": asignacion.id,
        "bus_id": asignacion.bus_id,
        "conductor_id": asignacion.conductor_id,
        "placa": asignacion.bus.placa,
        "agencia_id": asignacion.bus.agencia_id,
    }


def entero_o_none(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def validar_bus_conductor(bus_id, conductor_id):
    """Devuelve (bus, conductor, error). El conductor debe tener rol 3 y pertenecer a la agencia del bus."""
    bus = Bus.objects.filter(id=bus_id).first()
    if bus is None:
        return None, None, Response({"message": "El bus no existe"}, status=status.HTTP_404_NOT_FOUND)
    conductor = Usuario.objects.filter(id=conductor_id).first()
    if conductor is None:
        return None, None, Response({"message": "El conductor no existe"}, status=status.HTTP_404_NOT_FOUND)
    if conductor.rol_id != ROL_CONDUCTOR:
        return None, None, Response({"message": "El usuario no es conductor"}, status=status.HTTP_400_BAD_REQUEST)
    if not UsuarioAgencia.objects.filter(usuario=conductor, agencia_id=bus.agencia_id).exists():
        return None, None, Response(
            {"message": "El conductor no pertenece a la agencia del bus"}, status=status.HTTP_400_BAD_REQUEST
        )
    return bus, conductor, None


def viaje_en_curso_en(conductor, bus_ids):
    return Viaje.objects.filter(conductor=conductor, bus_id__in=bus_ids, estado=Viaje.EN_CURSO).exists()


class BusConductorView(APIView):
    @swagger_auto_schema(
        operation_description=(
            "Listar asignaciones bus-conductor. Filtros opcionales: ?conductor_id=, ?bus_id= y "
            "?agencia_id= (solo superadmin)"
        ),
        manual_parameters=[
            openapi.Parameter("conductor_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter("bus_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            PARAMETRO_AGENCIA,
        ],
    )
    def get(self, request):
        yo = usuario_de(request)
        lista = Bus_Conductor.objects.select_related("bus").order_by("id")
        if es_conductor(yo):
            lista = lista.filter(conductor=yo)  # un conductor solo ve sus propias asignaciones
        elif not es_super(yo):
            if yo.rol_id != 2:
                return prohibido()
            lista = lista.filter(bus__agencia_id__in=agencias_de(yo))
        lista = filtrar_agencia_super(request, lista, "bus__agencia_id")
        for campo in ("conductor_id", "bus_id"):
            valor = request.query_params.get(campo)
            if valor is not None:
                numero = entero_o_none(valor)
                if numero is None:
                    return Response({"message": f"{campo} debe ser un número"}, status=status.HTTP_400_BAD_REQUEST)
                lista = lista.filter(**{campo: numero})
        return Response([bus_conductor_json(a) for a in lista])

    @swagger_auto_schema(
        operation_description=(
            "Asignar un bus a un conductor. Si la asignación ya existe, la devuelve sin duplicarla. "
            "El conductor tiene un bus por agencia: asignar otro de la misma agencia reemplaza el anterior "
            "(409 si tiene un viaje en curso en él) y no toca sus buses de otras agencias."
        ),
        request_body=BusConductorEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        bus, conductor, error = validar_bus_conductor(
            entero_o_none(request.data.get("bus_id")), entero_o_none(request.data.get("conductor_id"))
        )
        if error:
            return error
        if not gestiona_agencia(usuario_de(request), bus.agencia_id):
            return prohibido("Solo el administrador de la agencia del bus puede asignarlo")
        # Regla: un conductor tiene UN bus por agencia. Asignar otro de la misma agencia reemplaza
        # el anterior, salvo que tenga un viaje en curso en él. Sus buses de otras agencias no se tocan.
        anteriores = Bus_Conductor.objects.filter(
            conductor=conductor, bus__agencia_id=bus.agencia_id,
        ).exclude(bus=bus)
        if viaje_en_curso_en(conductor, [a.bus_id for a in anteriores]):
            return Response(
                {"message": "El conductor tiene un viaje en curso; debe finalizarlo antes de cambiar de bus"},
                status=status.HTTP_409_CONFLICT,
            )
        with transaction.atomic():
            reemplazadas = anteriores.count()
            anteriores.delete()
            asignacion, creada = Bus_Conductor.objects.get_or_create(bus=bus, conductor=conductor)
        datos = bus_conductor_json(asignacion)
        datos["reemplazadas"] = reemplazadas
        datos["mensaje"] = "Bus asociado con conductor correctamente" if creada else "La asignación ya existía"
        return Response(datos, status=status.HTTP_201_CREATED if creada else status.HTTP_200_OK)


class BusConductorIdView(APIView):
    @swagger_auto_schema(operation_description="Consultar una asignación bus-conductor")
    def get(self, request, id):
        asignacion = get_object_or_404(Bus_Conductor.objects.select_related("bus"), id=id)
        yo = usuario_de(request)
        if not (asignacion.conductor_id == yo.id or gestiona_agencia(yo, asignacion.bus.agencia_id)):
            return prohibido()
        return Response(bus_conductor_json(asignacion))

    @swagger_auto_schema(
        operation_description="Actualizar asociación de bus y conductor",
        request_body=BusConductorEntrada
    )
    def put(self, request, id):
        asignacion = get_object_or_404(Bus_Conductor.objects.select_related("bus"), id=id)
        if not gestiona_agencia(usuario_de(request), asignacion.bus.agencia_id):
            return prohibido()
        bus, conductor, error = validar_bus_conductor(
            entero_o_none(request.data.get("bus_id")), entero_o_none(request.data.get("conductor_id"))
        )
        if error:
            return error
        if not gestiona_agencia(usuario_de(request), bus.agencia_id):
            return prohibido()
        repetida = Bus_Conductor.objects.filter(bus=bus, conductor=conductor).exclude(id=asignacion.id).exists()
        if repetida:
            return Response({"message": "Esa asignación ya existe"}, status=status.HTTP_409_CONFLICT)
        asignacion.bus = bus
        asignacion.conductor = conductor
        asignacion.save()
        return Response(bus_conductor_json(asignacion))

    @swagger_auto_schema(operation_description="Eliminar asociación de bus y conductor")
    def delete(self, request, id):
        asignacion = get_object_or_404(Bus_Conductor.objects.select_related("bus"), id=id)
        if not gestiona_agencia(usuario_de(request), asignacion.bus.agencia_id):
            return prohibido()
        if viaje_en_curso_en(asignacion.conductor, [asignacion.bus_id]):
            return Response({"message": "El conductor tiene un viaje en curso en este bus"},
                            status=status.HTTP_409_CONFLICT)
        asignacion.delete()
        return Response({"mensaje": "Asociación de bus y conductor eliminada"})

##################################################################################################
def agencias_de_sillas(yo):
    """Agencias cuyas sillas ve el usuario. Admin, conductor y cliente ligado a una agencia: solo las suyas.
    None = sin restricción (superadmin, cliente independiente y sin sesión: el mapa es parte del catálogo)."""
    return agencias_de(yo) if es_conductor(yo) else agencias_de_catalogo(yo)


class AsientoView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description=(
            "Listar asientos. ?viaje_id= devuelve las sillas del bus de esa salida con 'ocupado' calculado "
            "para esa salida (recomendado para la app). ?tipo_bus_id= (y opcional ?paquete_id=) se mantiene. "
            "Sin viaje_id ni tipo_bus_id responde 400. Las reservas canceladas o vencidas no ocupan. "
            "Admin, conductor y cliente ligado a una agencia solo ven las sillas de la suya (404)."
        ),
        manual_parameters=[
            openapi.Parameter("viaje_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter("tipo_bus_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter("paquete_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
        ],
    )
    def get(self, request):
        viaje_id = request.query_params.get("viaje_id")
        tipo = entero_query(request, "tipo_bus_id")
        paquete_id = entero_query(request, "paquete_id")
        mias = agencias_de_sillas(usuario_de(request))
        marcar_vencidas()
        if viaje_id is not None:
            viaje = Viaje.objects.select_related("bus").filter(id=entero_o_none(viaje_id)).first()
            if viaje is None or (mias is not None and viaje.bus.agencia_id not in mias):
                return Response({"message": "La salida no existe"}, status=status.HTTP_404_NOT_FOUND)
            # El mapa es el de los tipos del bus de ESA salida y la ocupación es solo de esa salida.
            tipos = list(viaje.bus.tipos_bus.values_list("id", flat=True))
            ocupadoras = reservas_que_ocupan(viaje.paquete_id, viaje.id)
        elif tipo:
            agencia_id = TipoBus.objects.filter(id=tipo).values_list("agencia_id", flat=True).first()
            if mias is not None and agencia_id is not None and agencia_id not in mias:
                return Response({"message": "El tipo de bus no existe"}, status=status.HTTP_404_NOT_FOUND)
            tipos = [tipo]
            ocupadoras = reservas_que_ocupan(paquete_id) if paquete_id else reservas_activas()
        else:
            # Sin filtro se mezclarían los mapas de todos los buses y agencias.
            return Response({"message": "Indica viaje_id (recomendado) o tipo_bus_id"},
                            status=status.HTTP_400_BAD_REQUEST)
        ocupados = set(AsientoReserva.objects.filter(reserva__in=ocupadoras).values_list("asiento_id", flat=True))
        lista = []
        for asiento in Asiento.objects.filter(tipo_bus_id__in=tipos).order_by("numero_asiento", "id"):
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
        tipo, error = tipo_bus_de(usuario_de(request), request.data.get("tipo_bus_id"))
        if error:
            return error
        numero_asiento = entero_o_none(request.data.get("numero_asiento"))
        if numero_asiento is None or numero_asiento <= 0:
            return Response({"message": "El número de la silla debe ser mayor que 0"}, status=status.HTTP_400_BAD_REQUEST)
        if Asiento.objects.filter(tipo_bus=tipo, numero_asiento=numero_asiento).exists():
            return Response({"message": "Ese tipo de bus ya tiene esa silla"}, status=status.HTTP_409_CONFLICT)
        Asiento.objects.create(tipo_bus=tipo, numero_asiento=numero_asiento)
        return Response({"mensaje": "Asiento almacenado correctamente"})


class AsientoIdView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Listar asiento por id"
    )
    def get(self, request, id):
        registroEncontrado = get_object_or_404(Asiento.objects.select_related("tipo_bus"), id=id)
        mias = agencias_de_sillas(usuario_de(request))
        if mias is not None and registroEncontrado.tipo_bus.agencia_id not in mias:
            return Response({"message": "La silla no existe"}, status=status.HTTP_404_NOT_FOUND)
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
        asientoB = get_object_or_404(Asiento, id=id)
        yo = usuario_de(request)
        _, error = tipo_bus_de(yo, asientoB.tipo_bus_id)
        if error:
            return error
        tipo, error = tipo_bus_de(yo, request.data.get("tipo_bus_id"))
        if error:
            return error
        numero_asiento = entero_o_none(request.data.get("numero_asiento"))
        if numero_asiento is None or numero_asiento <= 0:
            return Response({"message": "El número de la silla debe ser mayor que 0"}, status=status.HTTP_400_BAD_REQUEST)
        if AsientoReserva.objects.filter(asiento=asientoB, reserva__in=reservas_activas()).exists():
            return Response({"message": "La silla está reservada; no se puede cambiar"}, status=status.HTTP_409_CONFLICT)
        if Asiento.objects.filter(tipo_bus=tipo, numero_asiento=numero_asiento).exclude(id=asientoB.id).exists():
            return Response({"message": "Ese tipo de bus ya tiene esa silla"}, status=status.HTTP_409_CONFLICT)
        asientoB.tipo_bus = tipo
        asientoB.numero_asiento = numero_asiento
        asientoB.save()
        return Response({"mensaje": "Asiento actualizado"})

    @swagger_auto_schema(
        operation_description="Eliminar asiento"
    )
    def delete(self, request, id):
        asientoEliminar = get_object_or_404(Asiento, id=id)
        _, error = tipo_bus_de(usuario_de(request), asientoEliminar.tipo_bus_id)
        if error:
            return error
        try:
            asientoEliminar.delete()
        except ProtectedError:
            return Response({"message": "La silla tiene reservas; no se puede eliminar"}, status=status.HTTP_409_CONFLICT)
        return Response({"mensaje": "Asiento eliminado"})


class AsientoNumeroView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Busca asientos por número de asiento"
    )
    def get(self, request, numero_asiento):
        asientoLista = Asiento.objects.filter(numero_asiento=numero_asiento)
        mias = agencias_de_sillas(usuario_de(request))
        if mias is not None:
            asientoLista = asientoLista.filter(tipo_bus__agencia_id__in=mias)
        lista = []
        for asiento in asientoLista:
            lista.append({
                "id": asiento.id,
                "tipo_bus_id": asiento.tipo_bus_id,
                "numero_asiento": asiento.numero_asiento,
            })
        return Response(lista)

##################################################################################################
# Viajes (salidas programadas por bus). El conductor ve los viajes de su bus asignado.

def viaje_json(viaje):
    tipo_bus_ids = list(viaje.bus.tipos_bus.values_list("id", flat=True))
    return {
        "id": viaje.id,
        "paquete_id": viaje.paquete_id,
        "paquete": viaje.paquete.nombre,
        "bus_id": viaje.bus_id,
        "placa": viaje.bus.placa,
        "tipo_bus_id": tipo_bus_ids[0] if tipo_bus_ids else None,
        "tipo_bus_ids": tipo_bus_ids,
        "agencia_id": viaje.bus.agencia_id,
        "fecha": viaje.fecha.isoformat(),
        "hora": viaje.hora.strftime("%H:%M"),
        "estado": viaje.estado,
        "conductor_id": viaje.conductor_id,
        "iniciado_en": viaje.iniciado_en,
        "finalizado_en": viaje.finalizado_en,
        "parada_actual": parada_actual_json(viaje),
    }


def parada_actual_json(viaje):
    """Parada donde está el bus: la última que el conductor marcó con el viaje EN_CURSO (None si aún no
    llega a ninguna o el viaje no está en curso). Vive en el backend: si la app se cierra a mitad de la
    validación, al volver a entrar el conductor retoma esa parada con los abordajes ya guardados."""
    if viaje.estado != Viaje.EN_CURSO:
        return None
    ultima = (ParadaCumplida.objects.filter(viaje=viaje).select_related("itinerario")
              .order_by("-cumplida_en", "-id").first())
    if ultima is None:
        return None
    it = ultima.itinerario
    return {"id": it.id, "nombre": it.titulo or it.lugar, "lugar": it.lugar, "llegada": ultima.cumplida_en}


def buses_del_conductor(conductor):
    return list(Bus_Conductor.objects.filter(conductor=conductor).values_list("bus_id", flat=True))


def viajes_visibles(yo):
    """Superadmin: todos. Admin: los de buses de su agencia. Conductor: los de su bus asignado.
    Cliente: las salidas programadas desde hoy (para reservar) y las de sus propias reservas."""
    base = Viaje.objects.select_related("bus", "paquete")
    if es_super(yo):
        return base
    if es_conductor(yo):
        return base.filter(bus_id__in=buses_del_conductor(yo), bus__agencia_id__in=agencias_de(yo))
    if es_admin(yo):
        return base.filter(bus__agencia_id__in=agencias_de(yo))
    if yo is not None and yo.rol_id == ROL_CLIENTE:
        propias = Reserva.objects.filter(usuario=yo, viaje__isnull=False).values_list("viaje_id", flat=True)
        para_reservar = filtrar_catalogo(
            yo, base.filter(estado=Viaje.PROGRAMADO, fecha__gte=hoy_colombia()), "paquete__agencia_id")
        return base.filter(Q(id__in=para_reservar.values("id")) | Q(id__in=propias))
    return base.none()


def conductor_autorizado(yo, viaje):
    """El conductor solo gestiona viajes del bus que tiene asignado (y de su agencia)."""
    return (
        es_conductor(yo)
        and viaje.bus_id in buses_del_conductor(yo)
        and viaje.bus.agencia_id in agencias_de(yo)
    )


def ahora_colombia():
    """Fecha y hora (sin segundos) de Colombia, para comparar con las salidas."""
    return timezone.localtime(timezone.now(), ZoneInfo("America/Bogota")).replace(second=0, microsecond=0, tzinfo=None)


def leer_fecha_hora(datos, viaje=None):
    """Devuelve (fecha, hora, error) aceptando 'YYYY-MM-DD' y 'HH:MM'."""
    try:
        fecha = date.fromisoformat(str(datos.get("fecha"))) if datos.get("fecha") else (viaje.fecha if viaje else None)
        hora_txt = datos.get("hora")
        hora = time.fromisoformat(str(hora_txt)[:5]) if hora_txt else (viaje.hora if viaje else None)
    except ValueError:
        return None, None, Response({"message": "Fecha (AAAA-MM-DD) u hora (HH:MM) inválida"},
                                    status=status.HTTP_400_BAD_REQUEST)
    if fecha is None or hora is None:
        return None, None, Response({"message": "Fecha y hora son obligatorias"}, status=status.HTTP_400_BAD_REQUEST)
    # Solo se exige futuro al programar o al mover la salida: editar otro dato de un viaje que ya
    # pasó no debe fallar (HU-W-21).
    cambia = viaje is None or (fecha, hora) != (viaje.fecha, viaje.hora)
    if cambia and datetime.combine(fecha, hora) < ahora_colombia():
        return None, None, Response({"message": "La fecha y hora de salida no pueden estar en el pasado"},
                                    status=status.HTTP_400_BAD_REQUEST)
    return fecha, hora, None


def conflicto(mensaje, viaje=None):
    datos = {"message": mensaje}
    if viaje is not None:
        datos["viaje"] = viaje_json(viaje)
    return Response(datos, status=status.HTTP_409_CONFLICT)


def bus_ocupado_ese_dia(bus, fecha, excluir_id=None):
    """Regla: un bus hace UN solo viaje por día (sin importar la hora ni el paquete).
    Devuelve el 409 con el viaje que ya ocupa ese día, o None si el bus está libre.
    excluir_id: al editar, el propio viaje no cuenta."""
    otros = Viaje.objects.select_related("bus", "paquete").filter(bus=bus, fecha=fecha)
    if excluir_id is not None:
        otros = otros.exclude(id=excluir_id)
    otro = otros.first()
    if otro is None:
        return None
    return conflicto(
        f"El bus {bus.placa} ya tiene un viaje el {fecha.isoformat()} ({otro.paquete.nombre}, "
        f"{otro.hora.strftime('%H:%M')}). Un bus solo puede hacer un viaje por día",
        otro,
    )


def bus_no_disponible(bus):
    """Un bus en mantenimiento o inactivo no se programa en un viaje (400). None si está activo."""
    if bus.estado == "activo":
        return None
    return Response({"message": f"El bus {bus.placa} está en {bus.estado}; solo un bus activo se puede programar"},
                    status=status.HTTP_400_BAD_REQUEST)


class ViajeView(APIView):
    @swagger_auto_schema(
        operation_description=(
            "Listar viajes. Superadmin: todos. Conductor: los del bus que tiene asignado. Admin: los de su agencia. "
            "Cliente: salidas PROGRAMADAS desde hoy y las de sus reservas. "
            "Filtros: ?estado=, ?bus_id=, ?paquete_id=, ?agencia_id= (solo superadmin). "
            "Cada viaje EN_CURSO trae parada_actual {id, nombre, lugar, llegada}: la última parada marcada "
            "(null si aún no llega a ninguna); la app la usa para retomar la validación tras cerrarse."
        ),
        manual_parameters=[
            openapi.Parameter("estado", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("bus_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter("paquete_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            PARAMETRO_AGENCIA,
        ],
    )
    def get(self, request):
        lista = filtrar_agencia_super(request, viajes_visibles(usuario_de(request)), "bus__agencia_id")
        estado = request.query_params.get("estado")
        if estado:
            lista = lista.filter(estado=estado.upper())
        for campo in ("bus_id", "paquete_id"):
            valor = request.query_params.get(campo)
            if valor is not None:
                numero = entero_o_none(valor)
                if numero is None:
                    return Response({"message": f"{campo} debe ser un número"}, status=status.HTTP_400_BAD_REQUEST)
                lista = lista.filter(**{campo: numero})
        return Response([viaje_json(v) for v in lista])

    @swagger_auto_schema(
        operation_description=(
            "Programar una salida: paquete_id, bus_id, fecha (AAAA-MM-DD), hora (HH:MM). Solo el admin de la agencia o el superadmin. "
            "Un bus solo puede tener UN viaje por día (aunque sea otra hora u otro paquete): si ya tiene uno "
            "responde 409 con 'message' y el 'viaje' que ocupa ese día. El mismo paquete sí puede repetirse "
            "en días distintos o con otro bus. El bus debe estar 'activo' (400 si está en mantenimiento o inactivo) "
            "y el paquete también (400 si está inactivo, borrador, suspendido o agotado)."
        ),
        request_body=openapi.Schema(type=openapi.TYPE_OBJECT, properties={
            "paquete_id": openapi.Schema(type=openapi.TYPE_INTEGER),
            "bus_id": openapi.Schema(type=openapi.TYPE_INTEGER),
            "fecha": openapi.Schema(type=openapi.TYPE_STRING, example="2026-11-02"),
            "hora": openapi.Schema(type=openapi.TYPE_STRING, example="06:30"),
        }),
    )
    def post(self, request):
        yo = usuario_de(request)
        paquete = Paquete.objects.filter(id=entero_o_none(request.data.get("paquete_id"))).first()
        bus = Bus.objects.filter(id=entero_o_none(request.data.get("bus_id"))).first()
        if paquete is None or bus is None:
            return Response({"message": "El paquete o el bus no existe"}, status=status.HTTP_404_NOT_FOUND)
        if bus.agencia_id != paquete.agencia_id:
            return Response({"message": "El bus y el paquete deben ser de la misma agencia"},
                            status=status.HTTP_400_BAD_REQUEST)
        if not gestiona_agencia(yo, bus.agencia_id):
            return prohibido("Solo el administrador de la agencia programa viajes")
        error = bus_no_disponible(bus)
        if error:
            return error
        if str(paquete.estado).lower() != "activo":
            return Response({"message": f"El paquete {paquete.nombre} está en {paquete.estado}; "
                                        "solo un paquete activo se puede programar"},
                            status=status.HTTP_400_BAD_REQUEST)
        fecha, hora, error = leer_fecha_hora(request.data)
        if error:
            return error
        error = bus_ocupado_ese_dia(bus, fecha)
        if error:
            return error
        try:
            with transaction.atomic():
                viaje = Viaje.objects.create(paquete=paquete, bus=bus, fecha=fecha, hora=hora)
        except IntegrityError:
            # Otra petición programó ese bus ese día justo al mismo tiempo (restricción viaje_bus_fecha_unico).
            return bus_ocupado_ese_dia(bus, fecha) or conflicto("Un bus solo puede hacer un viaje por día")
        return Response(viaje_json(viaje), status=status.HTTP_201_CREATED)


class ViajeIdView(APIView):
    @swagger_auto_schema(operation_description="Consultar un viaje")
    def get(self, request, id):
        viaje = get_object_or_404(viajes_visibles(usuario_de(request)), id=id)
        return Response(viaje_json(viaje))

    @swagger_auto_schema(
        operation_description=(
            "Cambiar bus, fecha u hora de un viaje PROGRAMADO (campos opcionales). Solo el admin de la agencia o el superadmin. "
            "Si cambia el bus o la fecha y ese bus ya tiene otro viaje ese día responde 409 (el propio viaje "
            "no cuenta, así que cambiar solo la hora nunca choca consigo mismo)."
        ),
        request_body=openapi.Schema(type=openapi.TYPE_OBJECT, properties={
            "bus_id": openapi.Schema(type=openapi.TYPE_INTEGER),
            "fecha": openapi.Schema(type=openapi.TYPE_STRING, example="2026-11-02"),
            "hora": openapi.Schema(type=openapi.TYPE_STRING, example="06:30"),
        }),
    )
    def put(self, request, id):
        viaje = get_object_or_404(Viaje.objects.select_related("bus", "paquete"), id=id)
        yo = usuario_de(request)
        if not gestiona_agencia(yo, viaje.bus.agencia_id):
            return prohibido()
        if viaje.estado != Viaje.PROGRAMADO:
            return conflicto("Solo se puede editar un viaje programado", viaje)
        bus = viaje.bus
        if request.data.get("bus_id") not in (None, ""):
            bus = Bus.objects.filter(id=entero_o_none(request.data.get("bus_id"))).first()
            if bus is None:
                return Response({"message": "El bus no existe"}, status=status.HTTP_404_NOT_FOUND)
            if bus.agencia_id != viaje.paquete.agencia_id:
                return Response({"message": "El bus debe ser de la agencia del paquete"},
                                status=status.HTTP_400_BAD_REQUEST)
            if bus.id != viaje.bus_id:
                error = bus_no_disponible(bus)
                if error:
                    return error
            mismos_tipos = set(bus.tipos_bus.values_list("id", flat=True)) == set(
                viaje.bus.tipos_bus.values_list("id", flat=True))
            if not mismos_tipos and hay_ventas_en_viajes([viaje]):
                # Las sillas vendidas son del mapa del bus actual; con otro tipo quedarían fuera del bus.
                return conflicto("La salida ya tiene sillas vendidas; solo puede cambiar a un bus del mismo tipo", viaje)
        fecha, hora, error = leer_fecha_hora(request.data, viaje)
        if error:
            return error
        # Solo se valida si cambia el bus o el día: así un viaje antiguo que ya estaba repetido
        # se puede corregir (moverlo de día o de bus) sin que su gemelo lo bloquee.
        if (bus.id, fecha) != (viaje.bus_id, viaje.fecha):
            error = bus_ocupado_ese_dia(bus, fecha, excluir_id=viaje.id)
            if error:
                return error
        viaje.bus, viaje.fecha, viaje.hora = bus, fecha, hora
        try:
            with transaction.atomic():
                viaje.save()
        except IntegrityError:
            return bus_ocupado_ese_dia(bus, fecha, excluir_id=viaje.id) or conflicto("Un bus solo puede hacer un viaje por día")
        return Response(viaje_json(viaje))

    @swagger_auto_schema(operation_description="Eliminar un viaje PROGRAMADO sin reservas asociadas. Solo admin.")
    def delete(self, request, id):
        viaje = get_object_or_404(Viaje.objects.select_related("bus"), id=id)
        if not gestiona_agencia(usuario_de(request), viaje.bus.agencia_id):
            return prohibido()
        if viaje.estado != Viaje.PROGRAMADO:
            return conflicto("Solo se puede eliminar un viaje programado", viaje)
        if viaje.reserva_set.exists():
            return conflicto("El viaje tiene reservas asociadas")
        viaje.delete()
        return Response({"mensaje": "Viaje eliminado"})


class ViajeIniciarView(APIView):
    @swagger_auto_schema(
        operation_description=(
            "El conductor del bus inicia el viaje: PROGRAMADO → EN_CURSO. "
            "409 si el viaje no está programado o si el conductor ya tiene otro viaje en curso."
        )
    )
    def post(self, request, id):
        yo = usuario_de(request)
        with transaction.atomic():
            # Bloqueo de la fila: dos toques o dos teléfonos no inician dos veces.
            viaje = get_object_or_404(Viaje.objects.select_for_update().select_related("bus", "paquete"), id=id)
            if not conductor_autorizado(yo, viaje):
                return prohibido("Este viaje no pertenece a tu bus")
            if viaje.estado != Viaje.PROGRAMADO:
                return conflicto(f"El viaje ya está {viaje.estado}", viaje)
            if Viaje.objects.filter(conductor=yo, estado=Viaje.EN_CURSO).exclude(id=viaje.id).exists():
                return conflicto("Ya tienes otro viaje en curso; finalízalo primero", viaje)
            viaje.estado = Viaje.EN_CURSO
            viaje.conductor = yo
            viaje.iniciado_en = timezone.now()
            viaje.save(update_fields=["estado", "conductor", "iniciado_en"])
        return Response(viaje_json(viaje))


class ViajeFinalizarView(APIView):
    @swagger_auto_schema(
        operation_description=(
            "Finaliza el viaje: EN_CURSO → COMPLETADO. Lo hace el conductor que lo inició "
            "(o el administrador de la agencia). 409 si el viaje no está en curso."
        )
    )
    def post(self, request, id):
        yo = usuario_de(request)
        with transaction.atomic():
            viaje = get_object_or_404(Viaje.objects.select_for_update().select_related("bus", "paquete"), id=id)
            personal = gestiona_agencia(yo, viaje.bus.agencia_id)
            if not (personal or conductor_autorizado(yo, viaje)):
                return prohibido("Este viaje no pertenece a tu bus")
            if viaje.estado != Viaje.EN_CURSO:
                return conflicto(f"El viaje está {viaje.estado}; solo se finaliza un viaje en curso", viaje)
            if not personal and viaje.conductor_id != yo.id:
                return prohibido("Solo el conductor que inició el viaje puede finalizarlo")
            viaje.estado = Viaje.COMPLETADO
            viaje.finalizado_en = timezone.now()
            viaje.save(update_fields=["estado", "finalizado_en"])
        return Response(viaje_json(viaje))


def paradas_json(viaje):
    hechas = dict(ParadaCumplida.objects.filter(viaje=viaje).values_list("itinerario_id", "cumplida_en"))
    lista = []
    for orden, it in enumerate(ordenar_itinerario(Itinerario.objects.filter(paquete_id=viaje.paquete_id)), 1):
        lista.append({
            "id": it.id, "nombre": it.titulo or it.lugar, "lugar": it.lugar, "dia": it.dia,
            "hora": it.hora.strftime("%H:%M") if it.hora else "", "orden": orden,
            "cumplida": it.id in hechas, "cumplida_en": hechas.get(it.id),
        })
    return lista


class ViajeParadasView(APIView):
    @swagger_auto_schema(operation_description="Paradas del viaje: el itinerario del paquete con las ya cumplidas.")
    def get(self, request, id):
        viaje = get_object_or_404(viajes_visibles(usuario_de(request)), id=id)
        return Response(paradas_json(viaje))


class ViajeParadaCumplirView(APIView):
    @swagger_auto_schema(
        operation_description="El conductor que inició el viaje marca una parada del itinerario como cumplida (idempotente)."
    )
    def post(self, request, id, itinerario_id):
        yo = usuario_de(request)
        viaje = get_object_or_404(Viaje.objects.select_related("bus"), id=id)
        if not conductor_autorizado(yo, viaje):
            return prohibido("Este viaje no pertenece a tu bus")
        if viaje.estado != Viaje.EN_CURSO:
            return conflicto("Las paradas se marcan con el viaje en curso", viaje)
        if viaje.conductor_id != yo.id:
            return prohibido("Solo el conductor que inició el viaje marca paradas")
        itinerario = get_object_or_404(Itinerario, id=itinerario_id, paquete_id=viaje.paquete_id)
        ParadaCumplida.objects.get_or_create(viaje=viaje, itinerario=itinerario)
        return Response(paradas_json(viaje))
