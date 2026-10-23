import json
import re

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema

from destinos.imagenes import destino_json, guardar_imagen_destino, imagen_url, resolver_departamento
from destinos.models import Destino

from .serializer import (
    PaqueteRegistrarEntrada, PaqueteDestinoEntrada, ItinerarioEntrada, MensajeSalida
)
from .models import Paquete, PaqueteDestino, Itinerario
from usuarios.permisos import LecturaPublica


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
    }


def vincular_destinos(paquete, destinos):
    vistos = set()
    for destino in destinos:
        if destino.id in vistos:
            continue
        PaqueteDestino.objects.get_or_create(paquete=paquete, destino=destino)
        vistos.add(destino.id)


def crear_o_actualizar_paquete(request, paquete=None):
    items, destinos_enviados = extraer_items_destino(request)
    archivos = archivos_destino(request, len(items))
    destinos = []
    for indice, item in enumerate(items):
        archivo = archivos[indice] if indice < len(archivos) else None
        destinos.append(resolver_destino(item, archivo))

    if destinos_enviados and not destinos:
        raise ValueError("No se pudieron leer los destinos. Envíalos como destinos o destino_ids.")

    imagen = request.FILES.get("imagen")
    datos = {
        "nombre": request.data.get("nombre"),
        "agencia_id": request.data.get("agencia_id"),
        "descripcion": request.data.get("descripcion") or "",
        "duracion_estimada": request.data.get("duracion_estimada") or "",
        "estado": request.data.get("estado") or "activo",
        "precio": request.data.get("precio") or 0,
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
        operation_description="Listar paquetes con destinos e imágenes"
    )
    def get(self, request):
        paqueteLista = Paquete.objects.all()
        lista = []
        for paquete in paqueteLista:
            lista.append(paquete_json(paquete, request))
        return Response(lista)

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
        if not request.data.get("agencia_id"):
            return Response({"mensaje": "La agencia es obligatoria"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            paquete = crear_o_actualizar_paquete(request)
        except ValueError as error:
            return Response({"mensaje": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        data = paquete_json(paquete, request)
        data["mensaje"] = "Paquete registrado correctamente"
        return Response(data, status=status.HTTP_201_CREATED)


class PaqueteIdView(VistaCatalogo):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @swagger_auto_schema(
        operation_description="Listar paquete por id, con destinos e imágenes"
    )
    def get(self, request, id):
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
        data = paquete_json(paqueteB, request)
        data["mensaje"] = "Paquete actualizado"
        return Response(data)

    @swagger_auto_schema(
        operation_description="Eliminar paquete"
    )
    def delete(self, request, id):
        paqueteEliminar = Paquete.objects.get(id=id)
        paqueteEliminar.delete()
        return Response({"mensaje": "Paquete eliminado"})


class PaqueteDescripcionView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Busca paquetes por descripción"
    )
    def get(self, request, descripcion):
        paqueteLista = Paquete.objects.filter(descripcion__icontains=descripcion)
        return Response([paquete_json(paquete, request) for paquete in paqueteLista])


class PaqueteNombreView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Busca paquetes por nombre"
    )
    def get(self, request, nombre):
        paqueteLista = Paquete.objects.filter(nombre__icontains=nombre)
        return Response([paquete_json(paquete, request) for paquete in paqueteLista])


##################################################################################################
class PaqueteDestinoView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Listar relaciones paquete-destino"
    )
    def get(self, request):
        relLista = PaqueteDestino.objects.all()
        lista = []
        for rel in relLista:
            lista.append({
                "id": rel.id,
                "paquete_id": rel.paquete_id,
                "destino_id": rel.destino_id,
            })
        return Response(lista)

    @swagger_auto_schema(
        operation_description="Guardar relacion paquete-destino",
        request_body=PaqueteDestinoEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        paquete_id = request.data.get("paquete_id")
        destino_id = request.data.get("destino_id")

        PaqueteDestino.objects.create(
            paquete_id=paquete_id,
            destino_id=destino_id
        )
        return Response({"mensaje": "Relacion paquete-destino almacenada correctamente"})


class PaqueteDestinoIdView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Listar relacion paquete-destino por id"
    )
    def get(self, request, id):
        registroEncontrado = PaqueteDestino.objects.get(id=id)
        return Response({
            "id": registroEncontrado.id,
            "paquete_id": registroEncontrado.paquete_id,
            "destino_id": registroEncontrado.destino_id,
        })

    @swagger_auto_schema(
        operation_description="Actualizar relacion paquete-destino",
        request_body=PaqueteDestinoEntrada
    )
    def put(self, request, id):
        relB = PaqueteDestino.objects.get(id=id)
        relB.paquete_id = request.data.get("paquete_id")
        relB.destino_id = request.data.get("destino_id")
        relB.save()
        return Response({"mensaje": "Relacion paquete-destino actualizada"})

    @swagger_auto_schema(
        operation_description="Eliminar relacion paquete-destino"
    )
    def delete(self, request, id):
        relEliminar = PaqueteDestino.objects.get(id=id)
        relEliminar.delete()
        return Response({"mensaje": "Relacion paquete-destino eliminada"})


##################################################################################################
class ItinerarioView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Listar itinerarios"
    )
    def get(self, request):
        itinerarioLista = Itinerario.objects.all()
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

    @swagger_auto_schema(
        operation_description="Guardar itinerario",
        request_body=ItinerarioEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        titulo = request.data.get("titulo")
        paquete_id = request.data.get("paquete_id")
        dia = request.data.get("dia")
        descripcion = request.data.get("descripcion")
        hora = request.data.get("hora")
        lugar = request.data.get("lugar")

        Itinerario.objects.create(
            titulo=titulo,
            paquete_id=paquete_id,
            dia=dia,
            descripcion=descripcion,
            hora=hora,
            lugar=lugar
        )
        return Response({"mensaje": "Itinerario almacenado correctamente"})


class ItinerarioIdView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Listar itinerario por id"
    )
    def get(self, request, id):
        registroEncontrado = Itinerario.objects.get(id=id)
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
        operation_description="Actualizar itinerario",
        request_body=ItinerarioEntrada
    )
    def put(self, request, id):
        itinerarioB = Itinerario.objects.get(id=id)
        itinerarioB.titulo = request.data.get("titulo")
        itinerarioB.paquete_id = request.data.get("paquete_id")
        itinerarioB.dia = request.data.get("dia")
        itinerarioB.descripcion = request.data.get("descripcion")
        itinerarioB.hora = request.data.get("hora")
        itinerarioB.lugar = request.data.get("lugar")
        itinerarioB.save()
        return Response({"mensaje": "Itinerario actualizado"})

    @swagger_auto_schema(
        operation_description="Eliminar itinerario"
    )
    def delete(self, request, id):
        itinerarioEliminar = Itinerario.objects.get(id=id)
        itinerarioEliminar.delete()
        return Response({"mensaje": "Itinerario eliminado"})


class ItinerarioTituloView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Busca itinerarios por título"
    )
    def get(self, request, titulo):
        itinerarioLista = Itinerario.objects.filter(titulo__icontains=titulo)
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
        itinerarioLista = Itinerario.objects.filter(lugar__icontains=lugar)
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