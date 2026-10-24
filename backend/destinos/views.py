from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Prefetch, Q
from drf_yasg.utils import swagger_auto_schema
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from .serializer import (
    DestinoEntrada, HopedajeEntrada, SitioTuristicoEntrada, ImagenEntrada, MensajeSalida, DepartamentoSerializer
)
from .models import Destino, Hospedaje, SitioTuristico, ImagenDestino, Departamento
from usuarios.paginacion import PARAMETROS_LISTA, paginar, texto_busqueda
from usuarios.permisos import LecturaPublica, agencias_de, es_admin, prohibido, usuario_de


def imagen_url(campo):
    if not campo:
        return None
    try:
        return campo.url
    except ValueError:
        return None


def hospedajes_visibles(yo):
    """Administrador: los de su agencia (y los que aún no tienen dueño). Los demás: el catálogo completo."""
    if es_admin(yo):
        return Hospedaje.objects.filter(Q(agencia_id__in=agencias_de(yo)) | Q(agencia__isnull=True))
    return Hospedaje.objects.all()


def hospedaje_json(hospedaje):
    return {
        "id": hospedaje.id,
        "nombre": hospedaje.nombre,
        "destino_id": hospedaje.destino_id,
        "direccion": hospedaje.direccion,
        "telefono": hospedaje.telefono,
        "descripcion": hospedaje.descripcion,
        "agencia_id": hospedaje.agencia_id,
        "imagen": imagen_url(hospedaje.imagen),
    }


def destino_json(destino):
    """Destino con su primera imagen y sus hoteles (se usa prefetch_related para no hacer una consulta por destino)."""
    imagenes = list(destino.imagendestino_set.all())
    return {
        "id": destino.id,
        "nombre": destino.nombre,
        "departamento": destino.departamento.nombre,
        "descripcion": destino.descripcion,
        "imagen": imagen_url(imagenes[0].url_img) if imagenes else None,
        "hoteles": [{"id": h.id, "nombre": h.nombre} for h in destino.hospedaje_set.all()],
    }


def agencia_para_hospedaje(yo, agencia_id):
    """(agencia_id, error). El administrador solo crea hospedajes de su agencia; si no indica una, usa la suya."""
    if not es_admin(yo):
        return (agencia_id or None), None
    propias = sorted(agencias_de(yo))
    if agencia_id in (None, ""):
        return (propias[0] if propias else None), None
    if not str(agencia_id).isdigit() or int(agencia_id) not in propias:
        return None, prohibido("Solo puedes usar hospedajes de tu agencia")
    return int(agencia_id), None


def hospedaje_ajeno(yo, hospedaje):
    """True si un administrador intenta tocar un hospedaje que pertenece a otra agencia."""
    return es_admin(yo) and hospedaje.agencia_id is not None and hospedaje.agencia_id not in agencias_de(yo)


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
    @swagger_auto_schema(
        operation_description=(
            "Listar destinos con su imagen y sus hoteles. Opcional: ?search=, ?page= y ?page_size=. "
            "Un administrador solo ve los hoteles de su agencia."
        ),
        manual_parameters=PARAMETROS_LISTA,
    )
    def get(self, request):
        hoteles = Prefetch("hospedaje_set", queryset=hospedajes_visibles(usuario_de(request)))
        destinoLista = Destino.objects.select_related("departamento").prefetch_related("imagendestino_set", hoteles)
        texto = texto_busqueda(request)
        if texto:
            destinoLista = destinoLista.filter(Q(nombre__icontains=texto) | Q(departamento__nombre__icontains=texto))
        return Response(paginar(request, destinoLista.order_by("id"), destino_json))

    @swagger_auto_schema(
        operation_description="Guardar destino",
        request_body=DestinoEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        nombre = request.data.get("nombre")
        departamento = request.data.get("departamento")
        descripcion = request.data.get("descripcion")

        Destino.objects.create(
            nombre=nombre,
            departamento=departamento,
            descripcion=descripcion
        )
        return Response({"mensaje": "Destino almacenado correctamente"})


class DestinoIdView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Listar destino por id"
    )
    def get(self, request, id):
        registroEncontrado = Destino.objects.get(id=id)
        return Response(destino_json(registroEncontrado))

    @swagger_auto_schema(
        operation_description="Actualizar destino",
        request_body=DestinoEntrada
    )
    def put(self, request, id):
        destinoB = Destino.objects.get(id=id)
        destinoB.nombre = request.data.get("nombre")
        destinoB.departamento = request.data.get("departamento")
        destinoB.descripcion = request.data.get("descripcion")
        destinoB.save()
        return Response({"mensaje": "Destino actualizado"})

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
        return Response([destino_json(d) for d in destinoLista])


class DestinoNombreView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Busca destinos por nombre"
    )
    def get(self, request, nombre):
        destinoLista = Destino.objects.filter(nombre__icontains=nombre)
        return Response([destino_json(d) for d in destinoLista])


##################################################################################################
class HospedajeView(VistaCatalogo):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @swagger_auto_schema(
        operation_description=(
            "Listar hospedajes con agencia_id e imagen. Un administrador solo ve los de su agencia. "
            "Opcional: ?search=, ?page= y ?page_size="
        ),
        manual_parameters=PARAMETROS_LISTA,
    )
    def get(self, request):
        hospedajeLista = hospedajes_visibles(usuario_de(request))
        texto = texto_busqueda(request)
        if texto:
            hospedajeLista = hospedajeLista.filter(Q(nombre__icontains=texto) | Q(direccion__icontains=texto))
        return Response(paginar(request, hospedajeLista.order_by("id"), hospedaje_json))

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

        agencia_id, error = agencia_para_hospedaje(usuario_de(request), request.data.get("agencia_id"))
        if error:
            return error
        Hospedaje.objects.create(
            nombre=nombre,
            destino_id=destino_id,
            direccion=direccion,
            telefono=telefono,
            descripcion=descripcion,
            agencia_id=agencia_id,
            imagen=request.FILES.get("imagen"),
        )
        return Response({"mensaje": "Hospedaje almacenado correctamente"})


class HospedajeIdView(VistaCatalogo):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @swagger_auto_schema(
        operation_description="Listar hospedaje por id"
    )
    def get(self, request, id):
        registroEncontrado = Hospedaje.objects.get(id=id)
        return Response(hospedaje_json(registroEncontrado))

    @swagger_auto_schema(
        operation_description="Actualizar hospedaje",
        request_body=HopedajeEntrada
    )
    def put(self, request, id):
        hospedajeB = Hospedaje.objects.get(id=id)
        yo = usuario_de(request)
        if hospedaje_ajeno(yo, hospedajeB):
            return prohibido("Solo puedes editar hospedajes de tu agencia")
        if request.data.get("agencia_id") not in (None, ""):
            agencia_id, error = agencia_para_hospedaje(yo, request.data.get("agencia_id"))
            if error:
                return error
            hospedajeB.agencia_id = agencia_id
        if request.FILES.get("imagen"):
            hospedajeB.imagen = request.FILES.get("imagen")
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
        if hospedaje_ajeno(usuario_de(request), hospedajeEliminar):
            return prohibido("Solo puedes eliminar hospedajes de tu agencia")
        hospedajeEliminar.delete()
        return Response({"mensaje": "Hospedaje eliminado"})


class HospedajeNombreView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Busca hospedajes por nombre"
    )
    def get(self, request, nombre):
        hospedajeLista = hospedajes_visibles(usuario_de(request)).filter(nombre__icontains=nombre)
        return Response([hospedaje_json(h) for h in hospedajeLista])


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
    @swagger_auto_schema(
        operation_description="Listar imagenes"
    )
    def get(self, request):
        imagenLista = ImagenDestino.objects.all()
        lista = []
        for imagen in imagenLista:
            lista.append({
                "id": imagen.id,
                "url_img": imagen.url_img.url if imagen.url_img else None,
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
        url_img = request.data.get("url_img")
        destino_id = request.data.get("destino_id")
        descripcion = request.data.get("descripcion")

        ImagenDestino.objects.create(
            url_img=url_img,
            destino_id=destino_id,
            descripcion=descripcion
        )
        return Response({"mensaje": "Imagen almacenada correctamente"})


class ImagenIdView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Listar imagen por id"
    )
    def get(self, request, id):
        registroEncontrado = ImagenDestino.objects.get(id=id)
        return Response({
            "id": registroEncontrado.id,
            "url_img": registroEncontrado.url_img.url if registroEncontrado.url_img else None,
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