from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema

from .serializer import (
    DestinoEntrada, HopedajeEntrada, SitioTuristicoEntrada, ImagenEntrada, MensajeSalida, DepartamentoSerializer
)
from .models import Destino, Hospedaje, SitioTuristico, ImagenDestino, Departamento
from .imagenes import (
    archivo_imagen, destino_json, guardar_imagen_destino, imagen_url, resolver_departamento,
)
from usuarios.permisos import LecturaPublica


class VistaCatalogo(APIView):
    """Lectura pública; crear, editar y borrar solo administrador o superadministrador."""
    permission_classes = [LecturaPublica]


class DepartamentoView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Listar departamentos"
    )
    def get(self, request):
        departamentoLista = Departamento.objects.all()
        lista = []
        for departamento in departamentoLista:
            lista.append({
                "id": departamento.id,
                "nombre": departamento.nombre,
            })
        return Response(lista)
    
##########################################################################################3

class DestinoView(VistaCatalogo):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @swagger_auto_schema(
        operation_description="Listar destinos"
    )
    def get(self, request):
        return Response([destino_json(destino, request) for destino in Destino.objects.all()])

    @swagger_auto_schema(
        operation_description="Guardar destino con foto opcional",
        request_body=DestinoEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        nombre = request.data.get("nombre")
        descripcion = request.data.get("descripcion") or ""
        destino = Destino.objects.create(
            nombre=nombre,
            departamento=resolver_departamento(request.data.get("departamento")),
            descripcion=descripcion,
        )
        guardar_imagen_destino(destino, archivo_imagen(request), descripcion)
        data = destino_json(destino, request)
        data["mensaje"] = "Destino almacenado correctamente"
        return Response(data, status=status.HTTP_201_CREATED)


class DestinoIdView(VistaCatalogo):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @swagger_auto_schema(
        operation_description="Listar destino por id"
    )
    def get(self, request, id):
        registroEncontrado = Destino.objects.get(id=id)
        return Response(destino_json(registroEncontrado, request))

    def _guardar(self, request, destino):
        if request.data.get("nombre") is not None:
            destino.nombre = request.data.get("nombre")
        if request.data.get("departamento") is not None:
            destino.departamento = resolver_departamento(request.data.get("departamento"))
        if request.data.get("descripcion") is not None:
            destino.descripcion = request.data.get("descripcion")
        destino.save()
        guardar_imagen_destino(destino, archivo_imagen(request), request.data.get("descripcion") or "")
        data = destino_json(destino, request)
        data["mensaje"] = "Destino actualizado"
        return Response(data)

    @swagger_auto_schema(
        operation_description="Actualizar destino e imagen",
        request_body=DestinoEntrada
    )
    def put(self, request, id):
        return self._guardar(request, Destino.objects.get(id=id))

    def patch(self, request, id):
        return self._guardar(request, Destino.objects.get(id=id))

    @swagger_auto_schema(
        operation_description="Eliminar destino"
    )
    def delete(self, request, id):
        destinoEliminar = Destino.objects.get(id=id)
        destinoEliminar.delete()
        return Response({"mensaje": "Destino eliminado"})


class DestinoDepartamentoView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Busca destinos por departamento"
    )
    def get(self, request, departamento):
        destinoLista = Destino.objects.filter(departamento__nombre__icontains=departamento)
        lista = []
        for destino in destinoLista:
            lista.append(destino_json(destino, request))
        return Response(lista)


class DestinoNombreView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Busca destinos por nombre"
    )
    def get(self, request, nombre):
        destinoLista = Destino.objects.filter(nombre__icontains=nombre)
        lista = []
        for destino in destinoLista:
            lista.append(destino_json(destino, request))
        return Response(lista)


##################################################################################################
class HospedajeView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Listar hospedajes"
    )
    def get(self, request):
        hospedajeLista = Hospedaje.objects.all()
        lista = []
        for hospedaje in hospedajeLista:
            lista.append({
                "id": hospedaje.id,
                "nombre": hospedaje.nombre,
                "destino_id": hospedaje.destino_id,
                "direccion": hospedaje.direccion,
                "telefono": hospedaje.telefono,
                "descripcion": hospedaje.descripcion,
            })
        return Response(lista)

    @swagger_auto_schema(
        operation_description="Guardar hospedaje",
        request_body=HopedajeEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        nombre = request.data.get("nombre")
        destino_id = request.data.get("destino_id")
        direccion = request.data.get("direccion")
        telefono = request.data.get("telefono")
        descripcion = request.data.get("descripcion")

        Hospedaje.objects.create(
            nombre=nombre,
            destino_id=destino_id,
            direccion=direccion,
            telefono=telefono,
            descripcion=descripcion
        )
        return Response({"mensaje": "Hospedaje almacenado correctamente"})


class HospedajeIdView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Listar hospedaje por id"
    )
    def get(self, request, id):
        registroEncontrado = Hospedaje.objects.get(id=id)
        return Response({
            "id": registroEncontrado.id,
            "nombre": registroEncontrado.nombre,
            "destino_id": registroEncontrado.destino_id,
            "direccion": registroEncontrado.direccion,
            "telefono": registroEncontrado.telefono,
            "descripcion": registroEncontrado.descripcion,
        })

    @swagger_auto_schema(
        operation_description="Actualizar hospedaje",
        request_body=HopedajeEntrada
    )
    def put(self, request, id):
        hospedajeB = Hospedaje.objects.get(id=id)
        hospedajeB.nombre = request.data.get("nombre")
        hospedajeB.destino_id = request.data.get("destino_id")
        hospedajeB.direccion = request.data.get("direccion")
        hospedajeB.telefono = request.data.get("telefono")
        hospedajeB.descripcion = request.data.get("descripcion")
        hospedajeB.save()
        return Response({"mensaje": "Hospedaje actualizado"})

    @swagger_auto_schema(
        operation_description="Eliminar hospedaje"
    )
    def delete(self, request, id):
        hospedajeEliminar = Hospedaje.objects.get(id=id)
        hospedajeEliminar.delete()
        return Response({"mensaje": "Hospedaje eliminado"})


class HospedajeNombreView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Busca hospedajes por nombre"
    )
    def get(self, request, nombre):
        hospedajeLista = Hospedaje.objects.filter(nombre__icontains=nombre)
        lista = []
        for hospedaje in hospedajeLista:
            lista.append({
                "id": hospedaje.id,
                "nombre": hospedaje.nombre,
                "destino_id": hospedaje.destino_id,
                "direccion": hospedaje.direccion,
                "telefono": hospedaje.telefono,
                "descripcion": hospedaje.descripcion,
            })
        return Response(lista)


##################################################################################################
class SitioTuristicoView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Listar sitios turisticos"
    )
    def get(self, request):
        sitioLista = SitioTuristico.objects.all()
        lista = []
        for sitio in sitioLista:
            lista.append({
                "id": sitio.id,
                "nombre": sitio.nombre,
                "destino_id": sitio.destino_id,
                "descripcion": sitio.descripcion,
                "recomendaciones": sitio.recomendaciones,
            })
        return Response(lista)

    @swagger_auto_schema(
        operation_description="Guardar sitio turistico",
        request_body=SitioTuristicoEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        nombre = request.data.get("nombre")
        destino_id = request.data.get("destino_id")
        descripcion = request.data.get("descripcion")
        recomendaciones = request.data.get("recomendaciones")

        SitioTuristico.objects.create(
            nombre=nombre,
            destino_id=destino_id,
            descripcion=descripcion,
            recomendaciones=recomendaciones
        )
        return Response({"mensaje": "Sitio turistico almacenado correctamente"})


class SitioTuristicoIdView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Listar sitio turistico por id"
    )
    def get(self, request, id):
        registroEncontrado = SitioTuristico.objects.get(id=id)
        return Response({
            "id": registroEncontrado.id,
            "nombre": registroEncontrado.nombre,
            "destino_id": registroEncontrado.destino_id,
            "descripcion": registroEncontrado.descripcion,
            "recomendaciones": registroEncontrado.recomendaciones,
        })

    @swagger_auto_schema(
        operation_description="Actualizar sitio turistico",
        request_body=SitioTuristicoEntrada
    )
    def put(self, request, id):
        sitioB = SitioTuristico.objects.get(id=id)
        sitioB.nombre = request.data.get("nombre")
        sitioB.destino_id = request.data.get("destino_id")
        sitioB.descripcion = request.data.get("descripcion")
        sitioB.recomendaciones = request.data.get("recomendaciones")
        sitioB.save()
        return Response({"mensaje": "Sitio turistico actualizado"})

    @swagger_auto_schema(
        operation_description="Eliminar sitio turistico"
    )
    def delete(self, request, id):
        sitioEliminar = SitioTuristico.objects.get(id=id)
        sitioEliminar.delete()
        return Response({"mensaje": "Sitio turistico eliminado"})


class SitioTuristicoNombreView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Busca sitios turísticos por nombre"
    )
    def get(self, request, nombre):
        sitioLista = SitioTuristico.objects.filter(nombre__icontains=nombre)
        lista = []
        for sitio in sitioLista:
            lista.append({
                "id": sitio.id,
                "nombre": sitio.nombre,
                "destino_id": sitio.destino_id,
                "descripcion": sitio.descripcion,
                "recomendaciones": sitio.recomendaciones,
            })
        return Response(lista)


##################################################################################################
class ImagenView(VistaCatalogo):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @swagger_auto_schema(
        operation_description="Listar imagenes"
    )
    def get(self, request):
        imagenLista = ImagenDestino.objects.all()
        lista = []
        for imagen in imagenLista:
            lista.append({
                "id": imagen.id,
                "url_img": imagen_url(imagen.url_img, request),
                "destino_id": imagen.destino_id,
                "descripcion": imagen.descripcion,
            })
        return Response(lista)

    @swagger_auto_schema(
        operation_description="Guardar imagen",
        request_body=ImagenEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        destino_id = request.data.get("destino_id")
        descripcion = request.data.get("descripcion")
        archivo = archivo_imagen(request) or request.data.get("url_img")
        imagen = ImagenDestino.objects.create(
            url_img=archivo,
            destino_id=destino_id,
            descripcion=descripcion or "",
        )
        return Response({
            "id": imagen.id,
            "url_img": imagen_url(imagen.url_img, request),
            "destino_id": imagen.destino_id,
            "descripcion": imagen.descripcion,
            "mensaje": "Imagen almacenada correctamente",
        }, status=status.HTTP_201_CREATED)


class ImagenIdView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Listar imagen por id"
    )
    def get(self, request, id):
        registroEncontrado = ImagenDestino.objects.get(id=id)
        return Response({
            "id": registroEncontrado.id,
            "url_img": imagen_url(registroEncontrado.url_img, request),
            "destino_id": registroEncontrado.destino_id,
            "descripcion": registroEncontrado.descripcion,
        })

    @swagger_auto_schema(
        operation_description="Actualizar imagen",
        request_body=ImagenEntrada
    )
    def put(self, request, id):
        imagenB = ImagenDestino.objects.get(id=id)
        if request.data.get("url_img"):
            imagenB.url_img = request.data.get("url_img")
        imagenB.destino_id = request.data.get("destino_id")
        imagenB.descripcion = request.data.get("descripcion")
        imagenB.save()
        return Response({"mensaje": "Imagen actualizada"})

    @swagger_auto_schema(
        operation_description="Eliminar imagen"
    )
    def delete(self, request, id):
        imagenEliminar = ImagenDestino.objects.get(id=id)
        imagenEliminar.delete()
        return Response({"mensaje": "Imagen eliminada"})


class ImagenUrlView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Busca una imagen por su URL"
    )
    def get(self, request, url_img):
        imagen = ImagenDestino.objects.filter(url_img=url_img).first()
        if not imagen:
            return Response({"mensaje": "Imagen no encontrada"}, status=404)
        return Response({
            "id": imagen.id,
            "url_img": imagen.url_img.url if imagen.url_img else None,
            "destino_id": imagen.destino_id,
            "descripcion": imagen.descripcion,
        })