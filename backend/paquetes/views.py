from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema

from destinos.models import Destino, ImagenDestino

from .serializer import (
    PaqueteRegistrarEntrada, PaqueteDestinoEntrada, ItinerarioEntrada, MensajeSalida
)
from .models import Paquete, PaqueteDestino, Itinerario


def imagen_url(campo):
    if not campo:
        return None
    try:
        return campo.url
    except ValueError:
        return None


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
        pieza = str(pieza).strip()
        if pieza.isdigit():
            ids.append(int(pieza))
    return ids


def destinos_de_paquete(paquete):
    relaciones = (
        PaqueteDestino.objects
        .filter(paquete=paquete)
        .select_related("destino", "destino__departamento")
    )
    destinos = []
    for rel in relaciones:
        destino = rel.destino
        imagenes = [
            {
                "id": img.id,
                "url_img": imagen_url(img.url_img),
                "descripcion": img.descripcion,
            }
            for img in ImagenDestino.objects.filter(destino=destino)
        ]
        destinos.append({
            "id": destino.id,
            "nombre": destino.nombre,
            "departamento": destino.departamento.nombre if destino.departamento_id else None,
            "descripcion": destino.descripcion,
            "imagen": imagenes[0]["url_img"] if imagenes else None,
            "imagenes": imagenes,
        })
    return destinos


def paquete_json(paquete):
    return {
        "id": paquete.id,
        "nombre": paquete.nombre,
        "agencia_id": paquete.agencia_id,
        "descripcion": paquete.descripcion,
        "duracion_estimada": paquete.duracion_estimada,
        "estado": paquete.estado,
        "fecha_creacion": paquete.fecha_creacion,
        "precio": str(paquete.precio),
        "imagen": imagen_url(getattr(paquete, "imagen", None)),
        "destinos": destinos_de_paquete(paquete),
    }


def vincular_destinos(paquete, destino_ids):
    if not destino_ids:
        return
    existentes = list(Destino.objects.filter(id__in=destino_ids))
    if len(existentes) != len(set(destino_ids)):
        raise ValueError("Uno o más destinos no existen")
    for destino_id in set(destino_ids):
        PaqueteDestino.objects.get_or_create(paquete=paquete, destino_id=destino_id)


def guardar_imagenes_destino(request, destino_ids):
    archivos = request.FILES.getlist("imagenes_destino")
    if not archivos:
        archivo = request.FILES.get("imagen_destino")
        archivos = [archivo] if archivo else []
    destinos_imagen = parse_ids(
        request.data.get("destinos_imagen") or request.data.get("destino_ids_imagen")
    )
    if archivos and not destinos_imagen and len(destino_ids) == 1:
        destinos_imagen = [destino_ids[0]] * len(archivos)
    if archivos and len(destinos_imagen) != len(archivos):
        raise ValueError("Cada imagen de destino debe indicar su destino_id en destinos_imagen")
    for archivo, destino_id in zip(archivos, destinos_imagen):
        if not Destino.objects.filter(id=destino_id).exists():
            raise ValueError(f"El destino {destino_id} no existe")
        ImagenDestino.objects.create(
            url_img=archivo,
            destino_id=destino_id,
            descripcion=request.data.get("descripcion_imagen") or "",
        )


def crear_o_actualizar_paquete(request, paquete=None):
    destino_ids = parse_ids(
        request.data.get("destino_ids") or request.data.get("destino_id")
    )
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
            vincular_destinos(paquete, destino_ids)
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
            if "destino_ids" in request.data or "destino_id" in request.data:
                PaqueteDestino.objects.filter(paquete=paquete).delete()
                vincular_destinos(paquete, destino_ids)
        guardar_imagenes_destino(request, destino_ids)
    return paquete

class PaqueteView(APIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @swagger_auto_schema(
        operation_description="Listar paquetes con destinos e imágenes"
    )
    def get(self, request):
        paqueteLista = Paquete.objects.all()
        lista = []
        for paquete in paqueteLista:
            lista.append(paquete_json(paquete))
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
        data = paquete_json(paquete)
        data["mensaje"] = "Paquete almacenado correctamente"
        return Response(data, status=status.HTTP_201_CREATED)


class PaqueteRegistrarView(APIView):
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
        data = paquete_json(paquete)
        data["mensaje"] = "Paquete registrado correctamente"
        return Response(data, status=status.HTTP_201_CREATED)


class PaqueteIdView(APIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @swagger_auto_schema(
        operation_description="Listar paquete por id, con destinos e imágenes"
    )
    def get(self, request, id):
        registroEncontrado = Paquete.objects.filter(id=id).first()
        if not registroEncontrado:
            return Response({"mensaje": "Paquete no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        return Response(paquete_json(registroEncontrado))

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
        data = paquete_json(paqueteB)
        data["mensaje"] = "Paquete actualizado"
        return Response(data)

    @swagger_auto_schema(
        operation_description="Eliminar paquete"
    )
    def delete(self, request, id):
        paqueteEliminar = Paquete.objects.get(id=id)
        paqueteEliminar.delete()
        return Response({"mensaje": "Paquete eliminado"})


class PaqueteDescripcionView(APIView):
    @swagger_auto_schema(
        operation_description="Busca paquetes por descripción"
    )
    def get(self, request, descripcion):
        paqueteLista = Paquete.objects.filter(descripcion__icontains=descripcion)
        return Response([paquete_json(paquete) for paquete in paqueteLista])


class PaqueteNombreView(APIView):
    @swagger_auto_schema(
        operation_description="Busca paquetes por nombre"
    )
    def get(self, request, nombre):
        paqueteLista = Paquete.objects.filter(nombre__icontains=nombre)
        return Response([paquete_json(paquete) for paquete in paqueteLista])


##################################################################################################
class PaqueteDestinoView(APIView):
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


class PaqueteDestinoIdView(APIView):
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
class ItinerarioView(APIView):
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


class ItinerarioIdView(APIView):
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


class ItinerarioTituloView(APIView):
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



class ItinerarioLugarView(APIView):
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