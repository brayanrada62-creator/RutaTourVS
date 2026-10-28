from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from usuarios.paginacion import PARAMETROS_LISTA, entero_query, paginar, texto_busqueda
from .serializer import TipoBusEntrada, BusEntrada, AsientoEntrada, MensajeSalida, BusConductorEntrada, AsientosBusEntrada
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import ProtectedError, Q
from django.utils import timezone

from .models import Bus_Conductor, TipoBus, Bus, Asiento, Viaje, ParadaCumplida
from paquetes.models import Itinerario, Paquete
from reservas.models import AsientoReserva, Reserva, marcar_vencidas, reservas_activas, reservas_que_ocupan
from usuarios.models import Usuario, UsuarioAgencia

from usuarios.permisos import (
    ROL_CLIENTE, ROL_CONDUCTOR, LecturaPublica, agencias_de, filtrar_catalogo, es_admin, es_conductor, es_super, gestiona_agencia,
    prohibido, usuario_de,
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


class TipoBusView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Listar tipos de bus"
    )
    def get(self, request):
        tipoBusLista = TipoBus.objects.all()
        lista = []
        for tipoBus in tipoBusLista:
            lista.append({
                "id": tipoBus.id,
                "nombre": tipoBus.nombre,
                "agencia_id": tipoBus.agencia_id,
                "capacidad": tipoBus.capacidad,
                "descripcion": tipoBus.descripcion,
            })
        return Response(lista)

    @swagger_auto_schema(
        operation_description="Guardar tipo de bus",
        request_body=TipoBusEntrada
    )
    def post(self, request):
        nombre = request.data.get("nombre")
        agencia_id = request.data.get("agencia_id")
        capacidad = request.data.get("capacidad")
        descripcion = request.data.get("descripcion")
        if not gestiona_agencia(usuario_de(request), agencia_id):
            return prohibido("Solo puedes crear tipos de bus de tu agencia")

        TipoBus.objects.create(
            nombre=nombre,
            agencia_id=agencia_id,
            capacidad=capacidad,
            descripcion=descripcion
        )
        return Response({"mensaje": "Tipo de bus almacenado correctamente"})


class TipoBusIdView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Actualizar Tipo de bus",
        request_body=TipoBusEntrada
    )
    def put(self, request, id):
        tipoBusB, error = tipo_bus_de(usuario_de(request), id)
        if error:
            return error
        if not gestiona_agencia(usuario_de(request), request.data.get("agencia_id")):
            return prohibido("Solo puedes asignar tipos de bus a tu agencia")
        tipoBusB.nombre = request.data.get("nombre")
        tipoBusB.agencia_id = request.data.get("agencia_id")
        tipoBusB.capacidad = request.data.get("capacidad")
        tipoBusB.descripcion = request.data.get("descripcion")
        tipoBusB.save()
        return Response({"mensaje": "Tipo de bus actualizado"})

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
        registroEncontrado = get_object_or_404(TipoBus, id=id)
        return Response({
            "id": registroEncontrado.id,
            "nombre": registroEncontrado.nombre,
            "agencia_id": registroEncontrado.agencia_id,
            "capacidad": registroEncontrado.capacidad,
            "descripcion": registroEncontrado.descripcion,
        })


##################################################################################################
def bus_json(bus):
    return {
        "id": bus.id,
        "placa": bus.placa,
        "agencia_id": bus.agencia_id,
        "tipo_bus_id": bus.tipo_bus_id,
        "tipo_bus_nombre": bus.tipo_bus.nombre,
        "capacidad": bus.tipo_bus.capacidad,
        "marca": bus.marca,
        "modelo": bus.modelo,
        "estado": bus.estado,
        "fecha_registro": bus.fecha_registro,
    }


class BusView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description=(
            "Listar Buses con tipo_bus_nombre y capacidad. Opcional: ?search=, ?page= y ?page_size="
        ),
        manual_parameters=PARAMETROS_LISTA,
    )
    def get(self, request):
        busLista = Bus.objects.select_related("tipo_bus")
        texto = texto_busqueda(request)
        if texto:
            busLista = busLista.filter(
                Q(placa__icontains=texto) | Q(marca__icontains=texto) | Q(modelo__icontains=texto)
            )
        return Response(paginar(request, busLista.order_by("id"), bus_json))

    @swagger_auto_schema(
        operation_description="Guardar Bus",
        request_body=BusEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        placa = request.data.get("placa")
        agencia_id = request.data.get("agencia_id")
        if not gestiona_agencia(usuario_de(request), agencia_id):
            return prohibido("Solo puedes registrar buses de tu agencia")
        tipo_bus_id = request.data.get("tipo_bus_id")
        if not TipoBus.objects.filter(id=entero_o_none(tipo_bus_id), agencia_id=entero_o_none(agencia_id)).exists():
            return Response({"message": "El tipo de bus debe ser de la misma agencia del bus"},
                            status=status.HTTP_400_BAD_REQUEST)
        marca = request.data.get("marca")
        modelo = request.data.get("modelo")
        estado = request.data.get("estado")
        fecha_registro = request.data.get("fecha_registro")

        Bus.objects.create(
            placa=placa,
            agencia_id=agencia_id,
            tipo_bus_id=tipo_bus_id,
            marca=marca,
            modelo=modelo,
            estado=estado,
            fecha_registro=fecha_registro
        )
        return Response({"mensaje": "Bus almacenado correctamente"})


class BusIdView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Listar bus por id"
    )
    def get(self, request, id):
        registroEncontrado = get_object_or_404(Bus.objects.select_related("tipo_bus"), id=id)
        return Response(bus_json(registroEncontrado))

    @swagger_auto_schema(
        operation_description="Actualizar bus",
        request_body=BusEntrada
    )
    def put(self, request, id):
        busB = get_object_or_404(Bus, id=id)
        yo = usuario_de(request)
        if not gestiona_agencia(yo, busB.agencia_id) or not gestiona_agencia(yo, request.data.get("agencia_id")):
            return prohibido("Solo puedes editar buses de tu agencia")
        tipo_nuevo = entero_o_none(request.data.get("tipo_bus_id"))
        if not TipoBus.objects.filter(id=tipo_nuevo, agencia_id=entero_o_none(request.data.get("agencia_id"))).exists():
            return Response({"message": "El tipo de bus debe ser de la misma agencia del bus"},
                            status=status.HTTP_400_BAD_REQUEST)
        if tipo_nuevo != busB.tipo_bus_id and hay_ventas_en_viajes(Viaje.objects.filter(bus=busB)):
            # Las sillas vendidas son del mapa del tipo actual: cambiarlo dejaría esas ventas fuera del bus.
            return Response({"message": "El bus tiene sillas vendidas en sus salidas; no se puede cambiar su tipo"},
                            status=status.HTTP_409_CONFLICT)
        busB.placa = request.data.get("placa")
        busB.agencia_id = request.data.get("agencia_id")
        busB.tipo_bus_id = request.data.get("tipo_bus_id")
        busB.marca = request.data.get("marca")
        busB.modelo = request.data.get("modelo")
        busB.estado = request.data.get("estado")
        busB.fecha_registro = request.data.get("fecha_registro")
        busB.save()
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


class BusPlacaView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Busca un bus por su placa"
    )
    def get(self, request, placa):
        bus = Bus.objects.filter(placa=placa).first()
        if not bus:
            return Response({"mensaje": "Bus no encontrado"})
        return Response({
            "id": bus.id,
            "placa": bus.placa,
            "agencia_id": bus.agencia_id,
            "tipo_bus_id": bus.tipo_bus_id,
            "marca": bus.marca,
            "modelo": bus.modelo,
            "estado": bus.estado,
            "fecha_registro": bus.fecha_registro,
        })
        
def asientos_bus_json(bus):
    """Sillas del bus. El mapa es una plantilla del tipo de bus: todos los buses de ese tipo la comparten."""
    tipo = bus.tipo_bus
    return {
        "bus_id": bus.id,
        "placa": bus.placa,
        "tipo_bus_id": tipo.id,
        "tipo_bus_nombre": tipo.nombre,
        "capacidad": tipo.capacidad,
        "cantidad": Asiento.objects.filter(tipo_bus=tipo).count(),
        "buses_mismo_tipo": Bus.objects.filter(tipo_bus=tipo).count(),
    }


class BusAsientosView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description=(
            "Cuántas sillas tiene el bus. Las sillas pertenecen al TIPO de bus, así que "
            "buses_mismo_tipo indica cuántos buses comparten ese mapa."
        ),
    )
    def get(self, request, id):
        bus = get_object_or_404(Bus.objects.select_related("tipo_bus"), id=id)
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
        bus = get_object_or_404(Bus.objects.select_related("tipo_bus"), id=id)
        yo = usuario_de(request)
        # El tipo de bus también debe ser de la agencia: no se tocan plantillas de otra agencia.
        if not gestiona_agencia(yo, bus.agencia_id):
            return prohibido("Solo puedes cambiar las sillas de los buses de tu agencia")
        if not gestiona_agencia(yo, bus.tipo_bus.agencia_id):
            return prohibido("El tipo de bus de este bus es de otra agencia; cámbialo en Editar bus por uno de tu agencia")
        entrada = AsientosBusEntrada(data=request.data)
        if not entrada.is_valid():
            return Response({"message": "La cantidad debe ser un número entre 1 y 100", "errores": entrada.errors},
                            status=status.HTTP_400_BAD_REQUEST)
        cantidad = entrada.validated_data["cantidad"]
        tipo = bus.tipo_bus

        with transaction.atomic():
            sobrantes = Asiento.objects.filter(tipo_bus=tipo, numero_asiento__gt=cantidad)
            reservadas = AsientoReserva.objects.filter(asiento__in=sobrantes).values_list(
                "asiento__numero_asiento", flat=True).distinct()
            if reservadas:
                numeros = ", ".join(str(n) for n in sorted(reservadas))
                return Response({"message": f"No se puede reducir: las sillas {numeros} ya están reservadas"},
                                status=status.HTTP_409_CONFLICT)
            sobrantes.delete()
            existentes = set(Asiento.objects.filter(tipo_bus=tipo).values_list("numero_asiento", flat=True))
            Asiento.objects.bulk_create([
                Asiento(tipo_bus=tipo, numero_asiento=n) for n in range(1, cantidad + 1) if n not in existentes
            ])
            tipo.capacidad = cantidad
            tipo.save(update_fields=["capacidad"])

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
        operation_description="Listar asignaciones bus-conductor. Filtros opcionales: ?conductor_id= y ?bus_id=",
        manual_parameters=[
            openapi.Parameter("conductor_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter("bus_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
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
        for campo in ("conductor_id", "bus_id"):
            valor = request.query_params.get(campo)
            if valor is not None:
                numero = entero_o_none(valor)
                if numero is None:
                    return Response({"message": f"{campo} debe ser un número"}, status=status.HTTP_400_BAD_REQUEST)
                lista = lista.filter(**{campo: numero})
        return Response([bus_conductor_json(a) for a in lista])

    @swagger_auto_schema(
        operation_description="Asignar un bus a un conductor. Si la asignación ya existe, la devuelve sin duplicarla.",
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
        # Regla: un conductor tiene UN bus. Asignar otro reemplaza el anterior,
        # salvo que tenga un viaje en curso en ese bus anterior.
        anteriores = Bus_Conductor.objects.filter(conductor=conductor).exclude(bus=bus)
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
class AsientoView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description=(
            "Listar asientos. ?viaje_id= devuelve las sillas del bus de esa salida con 'ocupado' calculado "
            "para esa salida (recomendado para la app). ?tipo_bus_id= (y opcional ?paquete_id=) se mantiene. "
            "Sin viaje_id ni tipo_bus_id responde 400. Las reservas canceladas o vencidas no ocupan."
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
        marcar_vencidas()
        if viaje_id is not None:
            viaje = Viaje.objects.select_related("bus").filter(id=entero_o_none(viaje_id)).first()
            if viaje is None:
                return Response({"message": "La salida no existe"}, status=status.HTTP_404_NOT_FOUND)
            # El mapa es el del bus de ESA salida y la ocupación es solo de esa salida.
            tipo = viaje.bus.tipo_bus_id
            ocupadoras = reservas_que_ocupan(viaje.paquete_id, viaje.id)
        elif tipo:
            ocupadoras = reservas_que_ocupan(paquete_id) if paquete_id else reservas_activas()
        else:
            # Sin filtro se mezclarían los mapas de todos los buses y agencias.
            return Response({"message": "Indica viaje_id (recomendado) o tipo_bus_id"},
                            status=status.HTTP_400_BAD_REQUEST)
        ocupados = set(AsientoReserva.objects.filter(reserva__in=ocupadoras).values_list("asiento_id", flat=True))
        lista = []
        for asiento in Asiento.objects.filter(tipo_bus_id=tipo).order_by("numero_asiento", "id"):
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
        registroEncontrado = get_object_or_404(Asiento, id=id)
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
    return {
        "id": viaje.id,
        "paquete_id": viaje.paquete_id,
        "paquete": viaje.paquete.nombre,
        "bus_id": viaje.bus_id,
        "placa": viaje.bus.placa,
        "tipo_bus_id": viaje.bus.tipo_bus_id,
        "agencia_id": viaje.bus.agencia_id,
        "fecha": viaje.fecha.isoformat(),
        "hora": viaje.hora.strftime("%H:%M"),
        "estado": viaje.estado,
        "conductor_id": viaje.conductor_id,
        "iniciado_en": viaje.iniciado_en,
        "finalizado_en": viaje.finalizado_en,
    }


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


class ViajeView(APIView):
    @swagger_auto_schema(
        operation_description=(
            "Listar viajes. Conductor: los del bus que tiene asignado. Admin: los de su agencia. "
            "Cliente: salidas PROGRAMADAS desde hoy y las de sus reservas. "
            "Filtros: ?estado=, ?bus_id=, ?paquete_id="
        ),
        manual_parameters=[
            openapi.Parameter("estado", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("bus_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter("paquete_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
        ],
    )
    def get(self, request):
        lista = viajes_visibles(usuario_de(request))
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
        operation_description="Programar una salida: paquete_id, bus_id, fecha (AAAA-MM-DD), hora (HH:MM). Solo admin.",
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
        fecha, hora, error = leer_fecha_hora(request.data)
        if error:
            return error
        if Viaje.objects.filter(bus=bus, fecha=fecha, hora=hora).exists():
            return conflicto("Ese bus ya tiene una salida en esa fecha y hora")
        viaje = Viaje.objects.create(paquete=paquete, bus=bus, fecha=fecha, hora=hora)
        return Response(viaje_json(viaje), status=status.HTTP_201_CREATED)


class ViajeIdView(APIView):
    @swagger_auto_schema(operation_description="Consultar un viaje")
    def get(self, request, id):
        viaje = get_object_or_404(viajes_visibles(usuario_de(request)), id=id)
        return Response(viaje_json(viaje))

    @swagger_auto_schema(operation_description="Cambiar bus, fecha u hora de un viaje PROGRAMADO. Solo admin.")
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
            if bus.tipo_bus_id != viaje.bus.tipo_bus_id and hay_ventas_en_viajes([viaje]):
                # Las sillas vendidas son del mapa del bus actual; con otro tipo quedarían fuera del bus.
                return conflicto("La salida ya tiene sillas vendidas; solo puede cambiar a un bus del mismo tipo", viaje)
        fecha, hora, error = leer_fecha_hora(request.data, viaje)
        if error:
            return error
        if Viaje.objects.filter(bus=bus, fecha=fecha, hora=hora).exclude(id=viaje.id).exists():
            return conflicto("Ese bus ya tiene una salida en esa fecha y hora")
        viaje.bus, viaje.fecha, viaje.hora = bus, fecha, hora
        viaje.save()
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
    for orden, it in enumerate(Itinerario.objects.filter(paquete_id=viaje.paquete_id).order_by("dia", "hora", "id"), 1):
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
