import json
import re
from datetime import date

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import ProtectedError, Q
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from decimal import Decimal, InvalidOperation

from destinos.imagenes import destino_json, guardar_imagen_destino, imagen_url, resolver_departamento
from destinos.models import Destino
from buses.models import Viaje
from buses.views import entero_o_none, hoy_colombia

from .serializer import (
    PaqueteRegistrarEntrada, PaqueteDestinoEntrada, ItinerarioEntrada, MensajeSalida, PaqueteValidar
)
from .models import Paquete, PaqueteDestino, Itinerario, ordenar_itinerario
from usuarios.paginacion import PARAMETRO_AGENCIA, PARAMETROS_LISTA, entero_query, paginar, texto_busqueda
from usuarios.permisos import (
    LecturaPublica, agencia_para_guardar, es_admin, es_cliente_de_paquete, filtrar_agencia_super, filtrar_catalogo,
    gestiona_agencia, paquetes_reservados, prohibido, usuario_de,
)


class VistaCatalogo(APIView):
    """Lectura pública; crear, editar y borrar solo administrador o superadministrador."""
    permission_classes = [LecturaPublica]



def parse_ids(valor):
    if valor is None or valor == "":
        return []
    if isinstance(valor, (list, tuple)):
        piezas = valor
    else:
        texto = str(valor).strip()
        if texto.startswith("[") and texto.endswith("]"):
            texto = texto[1:-1]
        piezas = texto.replace(";", ",").split(",")
    ids = []
    for pieza in piezas:
        pieza = str(pieza).strip().strip('"').strip("'")
        if pieza.isdigit():
            ids.append(int(pieza))
    return ids


def maybe_json(valor):
    if isinstance(valor, (list, dict)):
        return valor
    if not isinstance(valor, str):
        return valor
    texto = valor.strip()
    if not texto or texto[0] not in "[{":
        return valor
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        return valor


def valores_campo(data, *claves):
    valores = []
    for clave in claves:
        if hasattr(data, "getlist"):
            valores.extend([v for v in data.getlist(clave) if v not in (None, "")])
            valores.extend([v for v in data.getlist(f"{clave}[]") if v not in (None, "")])
        got = data.get(clave) if hasattr(data, "get") else None
        if got not in (None, "", [], valores):
            if got not in valores:
                valores.append(got)
    return valores


def resolver_destino(item, archivo=None):
    if isinstance(item, Destino):
        guardar_imagen_destino(item, archivo)
        return item
    if isinstance(item, int) or (isinstance(item, str) and str(item).strip().isdigit()):
        destino = Destino.objects.filter(id=int(item)).first()
        if not destino:
            raise ValueError(f"El destino {item} no existe")
        guardar_imagen_destino(destino, archivo)
        return destino
    if isinstance(item, str):
        item = {"nombre": item.strip()}
    if not isinstance(item, dict):
        raise ValueError("Formato de destino no válido")

    destino_id = item.get("id") or item.get("destino_id")
    archivo = archivo or item.get("imagen") or item.get("url_img") or item.get("foto")
    if destino_id:
        destino = Destino.objects.filter(id=int(destino_id)).first()
        if not destino:
            raise ValueError(f"El destino {destino_id} no existe")
        guardar_imagen_destino(destino, archivo, item.get("descripcion_imagen") or "")
        return destino

    nombre = (item.get("nombre") or item.get("destino") or "").strip()
    if not nombre:
        raise ValueError("Cada destino necesita id o nombre")
    descripcion = item.get("descripcion") or ""
    destino = Destino.objects.filter(nombre__iexact=nombre).first()
    if destino is None:
        destino = Destino.objects.create(
            nombre=nombre[:150],
            departamento=resolver_departamento(item.get("departamento") or item.get("departamento_id")),
            descripcion=str(descripcion)[:300],
        )
    elif descripcion and not destino.descripcion:
        destino.descripcion = str(descripcion)[:300]
        destino.save(update_fields=["descripcion"])
    guardar_imagen_destino(destino, archivo, item.get("descripcion_imagen") or "")
    return destino


def destinos_anidados(data, files):
    por_indice = {}
    patron = re.compile(r"^destinos\[(\d+)\]\[(\w+)\]$|^destinos\.(\d+)\.(\w+)$")
    fuentes = []
    if hasattr(data, "keys"):
        fuentes.append(data)
    if files is not None and hasattr(files, "keys"):
        fuentes.append(files)
    for fuente in fuentes:
        for clave in fuente.keys():
            match = patron.match(clave)
            if not match:
                continue
            indice = int(match.group(1) or match.group(3))
            campo = match.group(2) or match.group(4)
            por_indice.setdefault(indice, {})
            if hasattr(fuente, "getlist"):
                valores = fuente.getlist(clave)
                por_indice[indice][campo] = valores[0] if len(valores) == 1 else valores
            else:
                por_indice[indice][campo] = fuente.get(clave)
    return [por_indice[i] for i in sorted(por_indice)]


def extraer_items_destino(request):
    data = request.data
    items = destinos_anidados(data, request.FILES)
    if items:
        return items, True

    enviados = False
    for valor in valores_campo(
        data,
        "destinos",
        "destino",
        "destino_ids",
        "destino_id",
        "destinos_ids",
        "ids_destino",
    ):
        enviados = True
        valor = maybe_json(valor)
        if isinstance(valor, list):
            items.extend(valor)
        elif isinstance(valor, str) and "," in valor and "{" not in valor:
            items.extend([parte.strip() for parte in valor.split(",") if parte.strip()])
        else:
            items.append(valor)

    if hasattr(data, "getlist"):
        extras = data.getlist("destino_ids") + data.getlist("destino_id") + data.getlist("destinos[]")
        if extras:
            enviados = True
            for extra in extras:
                extra = maybe_json(extra)
                if extra not in items:
                    items.append(extra)
    return items, enviados


def archivos_destino(request, cantidad):
    archivos = []
    if hasattr(request.FILES, "getlist"):
        archivos.extend(request.FILES.getlist("imagenes_destino"))
        archivos.extend(request.FILES.getlist("imagen_destino"))
        archivos.extend(request.FILES.getlist("imagenes_destinos"))
    for i in range(cantidad):
        archivo = request.FILES.get(f"imagen_destino_{i}") or request.FILES.get(f"destinos[{i}][imagen]")
        if archivo:
            while len(archivos) <= i:
                archivos.append(None)
            archivos[i] = archivo
    return archivos


def destinos_de_paquete(paquete, request=None):
    relaciones = (
        PaqueteDestino.objects
        .filter(paquete=paquete)
        .select_related("destino", "destino__departamento")
    )
    return [destino_json(rel.destino, request) for rel in relaciones]


def salidas_de_paquete(paquete):
    """Fechas (AAAA-MM-DD) de las salidas programadas desde hoy, sin repetir y en orden."""
    fechas = (
        Viaje.objects
        .filter(paquete=paquete, estado=Viaje.PROGRAMADO, fecha__gte=hoy_colombia())
        .order_by("fecha")
        .values_list("fecha", flat=True)
        .distinct()
    )
    return [f.isoformat() for f in fechas]


def proxima_salida(paquete):
    """Salida programada más cercana desde hoy ({"fecha", "hora"}) o None si no hay ninguna."""
    viaje = (
        Viaje.objects
        .filter(paquete=paquete, estado=Viaje.PROGRAMADO, fecha__gte=hoy_colombia())
        .order_by("fecha", "hora")
        .first()
    )
    return {"fecha": viaje.fecha.isoformat(), "hora": viaje.hora.strftime("%H:%M")} if viaje else None


def paquete_json(paquete, request=None):
    return {
        "id": paquete.id,
        "nombre": paquete.nombre,
        "agencia_id": paquete.agencia_id,
        "descripcion": paquete.descripcion,
        "duracion_estimada": paquete.duracion_estimada,
        "estado": paquete.estado,
        "fecha_creacion": paquete.fecha_creacion,
        "precio": str(paquete.precio),
        "imagen": imagen_url(getattr(paquete, "imagen", None), request),
        "destinos": destinos_de_paquete(paquete, request),
        "salidas": salidas_de_paquete(paquete),
        "proxima_salida": proxima_salida(paquete),
    }


def vincular_destinos(paquete, destinos):
    vistos = set()
    for destino in destinos:
        if destino.id in vistos:
            continue
        PaqueteDestino.objects.get_or_create(paquete=paquete, destino=destino)
        vistos.add(destino.id)


class SinPermisoAgencia(Exception):
    """El administrador intentó guardar un paquete en una agencia que no gestiona."""


def validar_paquete(datos):
    """Valida nombre, agencia, duración y precio; ValueError con el primer problema (HU-W-21)."""
    serializador = PaqueteValidar(data={
        campo: datos.get(campo) for campo in ("nombre", "agencia_id", "duracion_estimada", "precio")
        if datos.get(campo) is not None
    })
    if not serializador.is_valid():
        campo, errores = next(iter(serializador.errors.items()))
        raise ValueError(str(errores[0]))
    return serializador.validated_data


def paquete_gestionable(yo, paquete_id):
    """(paquete, error). El paquete existe (404) y es de una agencia que administra quien hace la petición (403)."""
    paquete = Paquete.objects.filter(id=entero_o_none(paquete_id)).first()
    if paquete is None:
        return None, Response({"mensaje": "El paquete no existe"}, status=status.HTTP_404_NOT_FOUND)
    if not gestiona_agencia(yo, paquete.agencia_id):
        return None, prohibido("Ese paquete es de otra agencia")
    return paquete, None


def crear_o_actualizar_paquete(request, paquete=None):
    yo = usuario_de(request)
    # La agencia no se toma a ciegas del body: el admin usa la suya (o la del paquete al editar).
    agencia_id, error = agencia_para_guardar(yo, request.data.get("agencia_id"),
                                             actual=paquete.agencia_id if paquete else None)
    if error:
        codigo, mensaje = error
        if codigo == status.HTTP_403_FORBIDDEN:
            raise SinPermisoAgencia(mensaje)
        raise ValueError(mensaje)
    campos = {campo: request.data.get(campo) for campo in ("nombre", "duracion_estimada", "precio")}
    validos = validar_paquete({**campos, "agencia_id": agencia_id})
    agencias = {validos["agencia_id"]} | ({paquete.agencia_id} if paquete else set())
    if not all(gestiona_agencia(yo, agencia) for agencia in agencias):
        raise SinPermisoAgencia("Solo puedes guardar paquetes de tu agencia")
    items, destinos_enviados = extraer_items_destino(request)
    archivos = archivos_destino(request, len(items))
    destinos = []
    for indice, item in enumerate(items):
        archivo = archivos[indice] if indice < len(archivos) else None
        destinos.append(resolver_destino(item, archivo))

    if destinos_enviados and not destinos:
        raise ValueError("No se pudieron leer los destinos. Envíalos como destinos o destino_ids.")

    estado = str(request.data.get("estado") or "activo").strip().lower()
    estados_validos = [valor for valor, _ in Paquete.ESTADOS]
    if estado not in estados_validos:
        raise ValueError(f"Estado no válido. Usa uno de: {', '.join(estados_validos)}")

    imagen = request.FILES.get("imagen")
    datos = {
        "nombre": validos["nombre"],
        "agencia_id": validos["agencia_id"],
        "descripcion": request.data.get("descripcion") or "",
        "duracion_estimada": validos["duracion_estimada"],
        "estado": estado,
        "precio": validos["precio"],
    }
    fecha = request.data.get("fecha_creacion")
    with transaction.atomic():
        if paquete is None:
            paquete = Paquete.objects.create(
                **datos,
                fecha_creacion=fecha or timezone.now(),
                imagen=imagen,
            )
        else:
            paquete.nombre = datos["nombre"]
            paquete.agencia_id = datos["agencia_id"]
            paquete.descripcion = datos["descripcion"]
            paquete.duracion_estimada = datos["duracion_estimada"]
            paquete.estado = datos["estado"]
            paquete.precio = datos["precio"]
            if fecha:
                paquete.fecha_creacion = fecha
            if imagen:
                paquete.imagen = imagen
            paquete.save()
            if destinos_enviados:
                PaqueteDestino.objects.filter(paquete=paquete).delete()
        vincular_destinos(paquete, destinos)
    return paquete

class PaqueteView(VistaCatalogo):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @swagger_auto_schema(
        operation_description=(
            "Listar paquetes con destinos e imagen. Superadmin: todos. Admin: solo los de su agencia "
            "(su ?agencia_id= se ignora). Un cliente registrado por una agencia solo ve los de esa agencia. "
            "Las agencias desactivadas salen del catálogo. Opcional: ?search=, ?destino_id=, ?estado=, ?agencia_id=, "
            "?precio_min=, ?precio_max=, ?fecha= (AAAA-MM-DD, desde hoy), ?page= y ?page_size="
        ),
        manual_parameters=PARAMETROS_LISTA + [
            openapi.Parameter("fecha", openapi.IN_QUERY, type=openapi.TYPE_STRING, example="2026-11-02"),
            openapi.Parameter("destino_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter("estado", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("agencia_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER,
                              description="Filtra por agencia. Para el admin se ignora."),
            openapi.Parameter("precio_min", openapi.IN_QUERY, type=openapi.TYPE_NUMBER),
            openapi.Parameter("precio_max", openapi.IN_QUERY, type=openapi.TYPE_NUMBER),
        ],
    )
    def get(self, request):
        yo = usuario_de(request)
        paqueteLista = filtrar_catalogo(yo, Paquete.objects.all())
        texto = texto_busqueda(request)
        if texto:
            paqueteLista = paqueteLista.filter(
                Q(nombre__icontains=texto)
                | Q(descripcion__icontains=texto)
                | Q(paquetedestino__destino__nombre__icontains=texto)
            ).distinct()
        destino_id = entero_query(request, "destino_id")
        if destino_id:
            paqueteLista = paqueteLista.filter(paquetedestino__destino_id=destino_id).distinct()
        estado = (request.query_params.get("estado") or "").strip()
        if estado:
            paqueteLista = paqueteLista.filter(estado__iexact=estado)
        agencia_id = entero_query(request, "agencia_id")
        if agencia_id and not es_admin(yo):
            paqueteLista = paqueteLista.filter(agencia_id=agencia_id)
        for campo, lookup in (("precio_min", "precio__gte"), ("precio_max", "precio__lte")):
            crudo = request.query_params.get(campo)
            if crudo not in (None, ""):
                try:
                    paqueteLista = paqueteLista.filter(**{lookup: Decimal(str(crudo))})
                except InvalidOperation:
                    return Response({"mensaje": f"{campo} no es un número válido"}, status=status.HTTP_400_BAD_REQUEST)
        crudo = (request.query_params.get("fecha") or "").strip()
        if crudo:
            try:
                fecha = date.fromisoformat(crudo)
            except ValueError:
                return Response({"mensaje": "fecha debe tener el formato AAAA-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)
            if fecha < hoy_colombia():
                return Response({"mensaje": "La fecha no puede ser anterior a hoy"}, status=status.HTTP_400_BAD_REQUEST)
            paqueteLista = paqueteLista.filter(
                viaje__fecha=fecha, viaje__estado=Viaje.PROGRAMADO
            ).distinct()
        return Response(paginar(request, paqueteLista.order_by("id"), lambda p: paquete_json(p, request)))

    @swagger_auto_schema(
        operation_description="Guardar paquete. Acepta imagen de portada, destino_ids e imagenes_destino.",
        request_body=PaqueteRegistrarEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        try:
            paquete = crear_o_actualizar_paquete(request)
        except ValueError as error:
            return Response({"mensaje": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        except SinPermisoAgencia as error:
            return Response({"mensaje": str(error)}, status=status.HTTP_403_FORBIDDEN)
        data = paquete_json(paquete, request)
        data["mensaje"] = "Paquete almacenado correctamente"
        return Response(data, status=status.HTTP_201_CREATED)


class PaqueteRegistrarView(VistaCatalogo):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @swagger_auto_schema(
        operation_description=(
            "Registra un paquete con su imagen de portada y destinos. "
            "La imagen del destino se guarda en ImagenDestino (app destinos), no en el paquete. "
            "Enviar multipart/form-data: imagen, destino_ids (ej: 1,2), "
            "imagenes_destino (archivo, se puede repetir) y destinos_imagen (ej: 1,2) en el mismo orden."
        ),
        request_body=PaqueteRegistrarEntrada,
    )
    def post(self, request):
        if not request.data.get("nombre"):
            return Response({"mensaje": "El nombre es obligatorio"}, status=status.HTTP_400_BAD_REQUEST)
        # agencia_id ya no es obligatorio: al admin se le toma de su sesión (crear_o_actualizar_paquete).
        try:
            paquete = crear_o_actualizar_paquete(request)
        except ValueError as error:
            return Response({"mensaje": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        except SinPermisoAgencia as error:
            return Response({"mensaje": str(error)}, status=status.HTTP_403_FORBIDDEN)
        data = paquete_json(paquete, request)
        data["mensaje"] = "Paquete registrado correctamente"
        return Response(data, status=status.HTTP_201_CREATED)


class PaqueteIdView(VistaCatalogo):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @swagger_auto_schema(
        operation_description=(
            "Listar paquete por id, con destinos e imágenes. Admin: solo los de su agencia (404). "
            "El cliente con reserva lo sigue viendo aunque la agencia se desactive."
        )
    )
    def get(self, request, id):
        yo = usuario_de(request)
        registroEncontrado = filtrar_catalogo(yo, Paquete.objects.filter(id=id)).first()
        if not registroEncontrado and es_cliente_de_paquete(yo, id):
            registroEncontrado = Paquete.objects.filter(id=id).first()
        if not registroEncontrado:
            return Response({"mensaje": "Paquete no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        return Response(paquete_json(registroEncontrado, request))

    @swagger_auto_schema(
        operation_description="Actualizar paquete, imagen y destinos",
        request_body=PaqueteRegistrarEntrada
    )
    def put(self, request, id):
        paqueteB = Paquete.objects.filter(id=id).first()
        if not paqueteB:
            return Response({"mensaje": "Paquete no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        try:
            paqueteB = crear_o_actualizar_paquete(request, paqueteB)
        except ValueError as error:
            return Response({"mensaje": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        except SinPermisoAgencia as error:
            return Response({"mensaje": str(error)}, status=status.HTTP_403_FORBIDDEN)
        data = paquete_json(paqueteB, request)
        data["mensaje"] = "Paquete actualizado"
        return Response(data)

    @swagger_auto_schema(
        operation_description=(
            "Eliminar paquete. Solo el admin de su agencia o el superadmin (403). 404 si no existe; "
            "409 si tiene reservas (se conservan por trazabilidad: cámbialo a inactivo)."
        ),
        responses={200: MensajeSalida, 403: "Paquete de otra agencia", 404: "No existe", 409: "Tiene reservas"},
    )
    def delete(self, request, id):
        paqueteEliminar, error = paquete_gestionable(usuario_de(request), id)
        if error:
            return error
        try:
            paqueteEliminar.delete()
        except ProtectedError:
            return Response({"mensaje": "El paquete tiene reservas; cámbialo a inactivo en lugar de eliminarlo"},
                            status=status.HTTP_409_CONFLICT)
        return Response({"mensaje": "Paquete eliminado"})


class PaqueteDescripcionView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Busca paquetes por descripción"
    )
    def get(self, request, descripcion):
        paqueteLista = filtrar_catalogo(usuario_de(request), Paquete.objects.filter(descripcion__icontains=descripcion))
        return Response([paquete_json(paquete, request) for paquete in paqueteLista])


class PaqueteNombreView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Busca paquetes por nombre"
    )
    def get(self, request, nombre):
        paqueteLista = filtrar_catalogo(usuario_de(request), Paquete.objects.filter(nombre__icontains=nombre))
        return Response([paquete_json(paquete, request) for paquete in paqueteLista])


##################################################################################################
def paquete_destino_json(rel):
    return {"id": rel.id, "paquete_id": rel.paquete_id, "destino_id": rel.destino_id}


def relaciones_visibles(yo):
    """Relaciones paquete-destino que ve el usuario: las de los paquetes de su catálogo (filtrar_catalogo)."""
    return filtrar_catalogo(yo, PaqueteDestino.objects.all(), "paquete__agencia_id")


def leer_paquete_destino(request):
    """(paquete, destino, error) a partir de paquete_id y destino_id del body, con la agencia validada."""
    entrada = PaqueteDestinoEntrada(data=request.data)
    if not entrada.is_valid():
        campo, errores = next(iter(entrada.errors.items()))
        return None, None, Response({"mensaje": f"{campo}: {errores[0]}"}, status=status.HTTP_400_BAD_REQUEST)
    paquete, error = paquete_gestionable(usuario_de(request), entrada.validated_data["paquete_id"])
    if error:
        return None, None, error
    destino = Destino.objects.filter(id=entrada.validated_data["destino_id"]).first()
    if destino is None:
        return None, None, Response({"mensaje": "El destino no existe"}, status=status.HTTP_404_NOT_FOUND)
    return paquete, destino, None


class PaqueteDestinoView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description=(
            "Listar relaciones paquete-destino. Opcional: ?paquete_id= y ?agencia_id= (solo superadmin). "
            "El admin y el cliente ligado a una agencia solo ven las de esa agencia (igual que /paquete/)."
        ),
        manual_parameters=[openapi.Parameter("paquete_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
                           PARAMETRO_AGENCIA],
    )
    def get(self, request):
        relLista = filtrar_agencia_super(request, relaciones_visibles(usuario_de(request)), "paquete__agencia_id")
        paquete_id = entero_query(request, "paquete_id")
        if paquete_id:
            relLista = relLista.filter(paquete_id=paquete_id)
        return Response([paquete_destino_json(rel) for rel in relLista.order_by("id")])

    @swagger_auto_schema(
        operation_description=(
            "Vincular un destino existente a un paquete. Solo el admin de la agencia del paquete o el superadmin "
            "(403). 404 si el paquete o el destino no existen; 409 si ya estaban vinculados. Responde 201 con id."
        ),
        request_body=PaqueteDestinoEntrada,
        responses={201: "Relación creada", 403: "Paquete de otra agencia", 404: "No existe", 409: "Ya vinculado"},
    )
    def post(self, request):
        paquete, destino, error = leer_paquete_destino(request)
        if error:
            return error
        if PaqueteDestino.objects.filter(paquete=paquete, destino=destino).exists():
            return Response({"mensaje": "Ese destino ya está en el paquete"}, status=status.HTTP_409_CONFLICT)
        rel = PaqueteDestino.objects.create(paquete=paquete, destino=destino)
        return Response({**paquete_destino_json(rel), "mensaje": "Relacion paquete-destino almacenada correctamente"},
                        status=status.HTTP_201_CREATED)


class PaqueteDestinoIdView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Listar relacion paquete-destino por id (404 si no existe o no es visible)"
    )
    def get(self, request, id):
        registroEncontrado = relaciones_visibles(usuario_de(request)).filter(id=id).first()
        if registroEncontrado is None:
            return Response({"mensaje": "Relación no encontrada"}, status=status.HTTP_404_NOT_FOUND)
        return Response(paquete_destino_json(registroEncontrado))

    @swagger_auto_schema(
        operation_description=(
            "Actualizar relacion paquete-destino. El paquete actual y el nuevo deben ser de tu agencia (403); "
            "409 si la relación nueva ya existe."
        ),
        request_body=PaqueteDestinoEntrada,
        responses={200: MensajeSalida, 403: "Paquete de otra agencia", 404: "No existe", 409: "Ya vinculado"},
    )
    def put(self, request, id):
        relB = PaqueteDestino.objects.filter(id=id).first()
        if relB is None:
            return Response({"mensaje": "Relación no encontrada"}, status=status.HTTP_404_NOT_FOUND)
        _, error = paquete_gestionable(usuario_de(request), relB.paquete_id)
        if error:
            return error
        paquete, destino, error = leer_paquete_destino(request)
        if error:
            return error
        if PaqueteDestino.objects.filter(paquete=paquete, destino=destino).exclude(id=relB.id).exists():
            return Response({"mensaje": "Ese destino ya está en el paquete"}, status=status.HTTP_409_CONFLICT)
        relB.paquete = paquete
        relB.destino = destino
        relB.save()
        return Response({**paquete_destino_json(relB), "mensaje": "Relacion paquete-destino actualizada"})

    @swagger_auto_schema(
        operation_description=(
            "Quitar un destino de un paquete (el destino NO se borra). Solo el admin de la agencia del paquete "
            "o el superadmin (403); 404 si no existe."
        ),
        responses={200: MensajeSalida, 403: "Paquete de otra agencia", 404: "No existe"},
    )
    def delete(self, request, id):
        relEliminar = PaqueteDestino.objects.filter(id=id).first()
        if relEliminar is None:
            return Response({"mensaje": "Relación no encontrada"}, status=status.HTTP_404_NOT_FOUND)
        _, error = paquete_gestionable(usuario_de(request), relEliminar.paquete_id)
        if error:
            return error
        relEliminar.delete()
        return Response({"mensaje": "Relacion paquete-destino eliminada"})


##################################################################################################
def leer_parada(datos, parcial=False):
    """(datos validados, error 400). Sin esto un POST sin hora terminaba en error 500."""
    entrada = ItinerarioEntrada(data=datos, partial=parcial)
    if not entrada.is_valid():
        return None, Response({"message": "Revisa título, día, hora y lugar de la parada", "errores": entrada.errors},
                              status=status.HTTP_400_BAD_REQUEST)
    return entrada.validated_data, None


def itinerarios_visibles(yo):
    """Paradas de los paquetes del catálogo del usuario, más las de los paquetes que el cliente ya reservó."""
    catalogo = filtrar_catalogo(yo, Itinerario.objects.all(), "paquete__agencia_id")
    return Itinerario.objects.filter(Q(id__in=catalogo.values("id")) | Q(paquete_id__in=paquetes_reservados(yo)))


class ItinerarioView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description=(
            "Listar itinerarios ordenados por día y hora. El admin solo ve los de su agencia. "
            "Opcional: ?paquete_id=, ?agencia_id= (solo superadmin), ?search=, ?page= y ?page_size="
        ),
        manual_parameters=PARAMETROS_LISTA + [
            openapi.Parameter("paquete_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            PARAMETRO_AGENCIA,
        ],
    )
    def get(self, request):
        itinerarioLista = filtrar_agencia_super(request, itinerarios_visibles(usuario_de(request)), "paquete__agencia_id")
        texto = texto_busqueda(request)
        if texto:
            itinerarioLista = itinerarioLista.filter(
                Q(titulo__icontains=texto) | Q(lugar__icontains=texto) | Q(descripcion__icontains=texto)
            )
        paquete_id = entero_query(request, "paquete_id")
        if paquete_id:
            itinerarioLista = itinerarioLista.filter(paquete_id=paquete_id)

        def itinerario_json(itinerario):
            return {
                "id": itinerario.id,
                "titulo": itinerario.titulo,
                "paquete_id": itinerario.paquete_id,
                "dia": itinerario.dia,
                "descripcion": itinerario.descripcion,
                "hora": itinerario.hora,
                "lugar": itinerario.lugar,
            }

        return Response(paginar(request, ordenar_itinerario(itinerarioLista), itinerario_json))

    @swagger_auto_schema(
        operation_description=(
            "Guardar itinerario. Solo el admin de la agencia del paquete o el superadmin (403). "
            "400 si faltan título, día, hora o lugar, o si no son válidos."
        ),
        request_body=ItinerarioEntrada,
        responses={201: MensajeSalida, 400: "Datos inválidos", 403: "Paquete de otra agencia", 404: "No existe"},
    )
    def post(self, request):
        # Solo el admin de la agencia del paquete (o el superadmin) le agrega paradas.
        paquete, error = paquete_gestionable(usuario_de(request), request.data.get("paquete_id"))
        if error:
            return error
        datos, error = leer_parada(request.data)
        if error:
            return error

        itinerario = Itinerario.objects.create(
            titulo=datos["titulo"],
            paquete=paquete,
            dia=str(datos["dia"]),
            descripcion=datos.get("descripcion", ""),
            hora=datos["hora"],
            lugar=datos["lugar"]
        )
        return Response({"id": itinerario.id, "mensaje": "Itinerario almacenado correctamente"},
                        status=status.HTTP_201_CREATED)


class ItinerarioIdView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Listar itinerario por id"
    )
    def get(self, request, id):
        registroEncontrado = itinerarios_visibles(usuario_de(request)).filter(id=id).first()
        if registroEncontrado is None:
            return Response({"mensaje": "Itinerario no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            "id": registroEncontrado.id,
            "titulo": registroEncontrado.titulo,
            "paquete_id": registroEncontrado.paquete_id,
            "dia": registroEncontrado.dia,
            "descripcion": registroEncontrado.descripcion,
            "hora": registroEncontrado.hora,
            "lugar": registroEncontrado.lugar,
        })

    @swagger_auto_schema(
        operation_description=(
            "Actualizar itinerario; los campos que no se envían se conservan. El paquete actual y el nuevo "
            "(paquete_id) deben ser de tu agencia (403); 400 si un dato no es válido; 404 si no existe."
        ),
        request_body=ItinerarioEntrada,
        responses={200: MensajeSalida, 400: "Datos inválidos", 403: "Paquete de otra agencia", 404: "No existe"},
    )
    def put(self, request, id):
        itinerarioB = Itinerario.objects.filter(id=id).first()
        if itinerarioB is None:
            return Response({"mensaje": "Itinerario no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        yo = usuario_de(request)
        _, error = paquete_gestionable(yo, itinerarioB.paquete_id)
        if error:
            return error
        paquete, error = paquete_gestionable(yo, request.data.get("paquete_id", itinerarioB.paquete_id))
        if error:
            return error
        datos, error = leer_parada(request.data, parcial=True)
        if error:
            return error
        itinerarioB.titulo = datos.get("titulo", itinerarioB.titulo)
        itinerarioB.paquete = paquete
        itinerarioB.dia = str(datos.get("dia", itinerarioB.dia))
        itinerarioB.descripcion = datos.get("descripcion", itinerarioB.descripcion)
        itinerarioB.hora = datos.get("hora", itinerarioB.hora)
        itinerarioB.lugar = datos.get("lugar", itinerarioB.lugar)
        itinerarioB.save()
        return Response({"mensaje": "Itinerario actualizado"})

    @swagger_auto_schema(
        operation_description="Eliminar itinerario. Solo el admin de la agencia del paquete o el superadmin (403).",
        responses={200: MensajeSalida, 403: "Paquete de otra agencia", 404: "No existe"},
    )
    def delete(self, request, id):
        itinerarioEliminar = Itinerario.objects.filter(id=id).first()
        if itinerarioEliminar is None:
            return Response({"mensaje": "Itinerario no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        _, error = paquete_gestionable(usuario_de(request), itinerarioEliminar.paquete_id)
        if error:
            return error
        itinerarioEliminar.delete()
        return Response({"mensaje": "Itinerario eliminado"})


class ItinerarioTituloView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Busca itinerarios por título"
    )
    def get(self, request, titulo):
        itinerarioLista = itinerarios_visibles(usuario_de(request)).filter(titulo__icontains=titulo)
        lista = []
        for itinerario in itinerarioLista:
            lista.append({
                "id": itinerario.id,
                "titulo": itinerario.titulo,
                "paquete_id": itinerario.paquete_id,
                "dia": itinerario.dia,
                "descripcion": itinerario.descripcion,
                "hora": itinerario.hora,
                "lugar": itinerario.lugar,
            })
        return Response(lista)



class ItinerarioLugarView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Busca itinerarios por lugar"
    )
    def get(self, request, lugar):
        itinerarioLista = itinerarios_visibles(usuario_de(request)).filter(lugar__icontains=lugar)
        lista = []
        for itinerario in itinerarioLista:
            lista.append({
                "id": itinerario.id,
                "titulo": itinerario.titulo,
                "paquete_id": itinerario.paquete_id,
                "dia": itinerario.dia,
                "descripcion": itinerario.descripcion,
                "hora": itinerario.hora,
                "lugar": itinerario.lugar,
            })
        return Response(lista)