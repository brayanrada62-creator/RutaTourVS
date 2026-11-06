from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Q
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from .serializer import (
    DestinoEntrada, HopedajeEntrada, HospedajeDestinoEntrada, ImagenEntrada, MensajeSalida, DepartamentoSerializer
)
from .models import Destino, Hospedaje, HospedajeDestino, ImagenDestino, Departamento
from .imagenes import (
    archivo_imagen, destino_json, guardar_imagen_destino, imagen_url, resolver_departamento,
)
from usuarios.permisos import (
    LecturaPublica, agencias_de, es_super, filtrar_agencia_super, filtrar_catalogo, usuario_de,
)
from usuarios.paginacion import PARAMETRO_AGENCIA, PARAMETROS_LISTA, entero_query, paginar, texto_busqueda

AVISO_COMPARTIDO = "Admin: 409 si lo usan paquetes de otra agencia. Superadmin: sin esa restricción."


def catalogo_compartido(request, destino_ids):
    """Destinos y hoteles no tienen agencia: son un catálogo compartido. Devuelve un 409 si un admin
    intenta cambiar algo que usan paquetes de otra agencia; None si puede hacerlo."""
    from paquetes.models import PaqueteDestino  # import local para evitar ciclos entre apps

    yo = usuario_de(request)
    if es_super(yo):
        return None
    usado = PaqueteDestino.objects.filter(destino_id__in=destino_ids).exclude(paquete__agencia_id__in=agencias_de(yo))
    if usado.exists():
        return Response({"message": "Lo usan paquetes de otra agencia; solo el superadministrador puede cambiarlo"},
                        status=status.HTTP_409_CONFLICT)
    return None


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

def error_destino(datos, creando=False):
    """Mensaje si el nombre viene vacío o el departamento no existe; None si sirven."""
    if (creando or datos.get("nombre") is not None) and not str(datos.get("nombre") or "").strip():
        return "El nombre es obligatorio"
    valor = str(datos.get("departamento") or "").strip()
    if valor:
        por_id = Q(id=int(valor)) if valor.isdigit() else Q(pk__in=[])
        if not Departamento.objects.filter(por_id | Q(nombre__iexact=valor)).exists():
            return "El departamento no existe"
    return None


class DestinoView(VistaCatalogo):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @swagger_auto_schema(
        operation_description=(
            "Listar destinos con su imagen (catálogo compartido entre agencias). Opcional: ?search=, "
            "?departamento= (id o nombre), ?agencia_id= (solo superadmin: los que usan sus paquetes), "
            "?page= y ?page_size="
        ),
        manual_parameters=PARAMETROS_LISTA + [
            openapi.Parameter("departamento", openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              description="Id o nombre del departamento"),
            PARAMETRO_AGENCIA,
        ],
    )
    def get(self, request):
        destinos = filtrar_agencia_super(request, Destino.objects.select_related("departamento"),
                                         "paquetedestino__paquete__agencia_id")
        texto = texto_busqueda(request)
        if texto:
            destinos = destinos.filter(
                Q(nombre__icontains=texto)
                | Q(descripcion__icontains=texto)
                | Q(departamento__nombre__icontains=texto)
            )
        depto = (request.query_params.get("departamento") or request.query_params.get("departamento_id") or "").strip()
        if depto:
            if depto.isdigit():
                destinos = destinos.filter(departamento_id=int(depto))
            else:
                destinos = destinos.filter(departamento__nombre__icontains=depto)
        return Response(paginar(request, destinos.order_by("id"), lambda d: destino_json(d, request)))

    @swagger_auto_schema(
        operation_description="Guardar destino con foto opcional",
        request_body=DestinoEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        error = error_destino(request.data, creando=True)
        if error:
            return Response({"message": error}, status=status.HTTP_400_BAD_REQUEST)
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
        registroEncontrado = get_object_or_404(Destino, id=id)
        return Response(destino_json(registroEncontrado, request))

    def _guardar(self, request, id):
        destino = get_object_or_404(Destino, id=id)
        error = catalogo_compartido(request, [destino.id])
        if error:
            return error
        error = error_destino(request.data)
        if error:
            return Response({"message": error}, status=status.HTTP_400_BAD_REQUEST)
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
        operation_description="Actualizar destino e imagen. " + AVISO_COMPARTIDO,
        request_body=DestinoEntrada
    )
    def put(self, request, id):
        return self._guardar(request, id)

    def patch(self, request, id):
        return self._guardar(request, id)

    @swagger_auto_schema(
        operation_description="Eliminar destino. " + AVISO_COMPARTIDO
    )
    def delete(self, request, id):
        destinoEliminar = get_object_or_404(Destino, id=id)
        error = catalogo_compartido(request, [destinoEliminar.id])
        if error:
            return error
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
def hospedaje_json(h, request=None):
    destino_ids = [destino.id for destino in h.destinos.all()]
    return {
        "id": h.id,
        "nombre": h.nombre,
        "destino_id": destino_ids[0] if destino_ids else None,
        "destino_ids": destino_ids,
        "direccion": h.direccion,
        "telefono": h.telefono,
        "descripcion": h.descripcion,
        "imagen": imagen_url(h.imagen, request),
    }


def destino_ids_de(data):
    destino_ids = data.get("destino_ids")
    if destino_ids is None:
        destino_id = data.get("destino_id")
        if destino_id is None:
            return None, None
        destino_ids = [destino_id]
    elif isinstance(destino_ids, str):
        destino_ids = destino_ids.split(",")

    try:
        ids = list(dict.fromkeys(int(destino_id) for destino_id in destino_ids))
    except (TypeError, ValueError):
        return None, Response({"mensaje": "destino_ids debe contener IDs enteros"}, status=status.HTTP_400_BAD_REQUEST)

    if any(destino_id < 1 for destino_id in ids):
        return None, Response({"mensaje": "Los IDs de destino deben ser positivos"}, status=status.HTTP_400_BAD_REQUEST)
    if ids:
        existentes = set(Destino.objects.filter(id__in=ids).values_list("id", flat=True))
        faltantes = [destino_id for destino_id in ids if destino_id not in existentes]
        if faltantes:
            return None, Response({"mensaje": f"No existen destinos: {faltantes}"}, status=status.HTTP_404_NOT_FOUND)
    return ids, None


class HospedajeView(VistaCatalogo):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @swagger_auto_schema(
        operation_description=(
            "Listar hospedajes con sus destinos e imagen (catálogo compartido entre agencias). Opcional: ?search=, "
            "?destino_id=, ?agencia_id= (solo superadmin: los de los destinos de sus paquetes), ?page= y ?page_size="
        ),
        manual_parameters=PARAMETROS_LISTA + [
            openapi.Parameter("destino_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            PARAMETRO_AGENCIA,
        ],
    )
    def get(self, request):
        hospedajeLista = filtrar_agencia_super(request, Hospedaje.objects.prefetch_related("destinos"),
                                               "destinos__paquetedestino__paquete__agencia_id")
        texto = texto_busqueda(request)
        if texto:
            hospedajeLista = hospedajeLista.filter(Q(nombre__icontains=texto) | Q(direccion__icontains=texto))
        destino_id = entero_query(request, "destino_id")
        if destino_id:
            hospedajeLista = hospedajeLista.filter(destinos__id=destino_id)
        return Response(paginar(request, hospedajeLista.distinct().order_by("id"), lambda h: hospedaje_json(h, request)))

    @swagger_auto_schema(
        operation_description="Guardar hospedaje",
        request_body=HopedajeEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        nombre = request.data.get("nombre")
        if not str(nombre or "").strip():
            return Response({"message": "El nombre es obligatorio"}, status=status.HTTP_400_BAD_REQUEST)
        direccion = request.data.get("direccion")
        telefono = request.data.get("telefono")
        descripcion = request.data.get("descripcion")
        destino_ids, error = destino_ids_de(request.data)
        if error:
            return error
        hospedaje = Hospedaje.objects.create(
            nombre=nombre,
            direccion=direccion,
            telefono=telefono,
            descripcion=descripcion,
            imagen=request.FILES.get("imagen"),
        )
        if destino_ids is not None:
            hospedaje.destinos.set(destino_ids)
        return Response({"mensaje": "Hospedaje almacenado correctamente"})


class HospedajeIdView(VistaCatalogo):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @swagger_auto_schema(
        operation_description="Listar hospedaje por id"
    )
    def get(self, request, id):
        registroEncontrado = get_object_or_404(Hospedaje.objects.prefetch_related("destinos"), id=id)
        return Response(hospedaje_json(registroEncontrado, request))

    @swagger_auto_schema(
        operation_description="Actualizar hospedaje. " + AVISO_COMPARTIDO,
        request_body=HopedajeEntrada
    )
    def put(self, request, id):
        hospedajeB = get_object_or_404(Hospedaje, id=id)
        error = catalogo_compartido(request, list(hospedajeB.destinos.values_list("id", flat=True)))
        if error:
            return error
        destino_ids, error = destino_ids_de(request.data)
        if error:
            return error
        if request.data.get("nombre") is not None and not str(request.data.get("nombre")).strip():
            return Response({"message": "El nombre es obligatorio"}, status=status.HTTP_400_BAD_REQUEST)
        if request.FILES.get("imagen"):
            hospedajeB.imagen = request.FILES.get("imagen")
        for campo in ("nombre", "direccion", "telefono", "descripcion"):
            if request.data.get(campo) is not None:
                setattr(hospedajeB, campo, request.data.get(campo))
        hospedajeB.save()
        if destino_ids is not None:
            hospedajeB.destinos.set(destino_ids)
        return Response({"mensaje": "Hospedaje actualizado"})

    @swagger_auto_schema(
        operation_description="Eliminar hospedaje. " + AVISO_COMPARTIDO
    )
    def delete(self, request, id):
        hospedajeEliminar = get_object_or_404(Hospedaje, id=id)
        error = catalogo_compartido(request, list(hospedajeEliminar.destinos.values_list("id", flat=True)))
        if error:
            return error
        hospedajeEliminar.delete()
        return Response({"mensaje": "Hospedaje eliminado"})


class HospedajeNombreView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description="Busca hospedajes por nombre"
    )
    def get(self, request, nombre):
        hospedajeLista = Hospedaje.objects.prefetch_related("destinos").filter(nombre__icontains=nombre)
        return Response([hospedaje_json(h, request) for h in hospedajeLista])


class HospedajeDestinoView(VistaCatalogo):
    @swagger_auto_schema(operation_description="Listar relaciones entre hospedajes y destinos")
    def get(self, request):
        relaciones = HospedajeDestino.objects.order_by("id")
        hospedaje_id = entero_query(request, "hospedaje_id")
        destino_id = entero_query(request, "destino_id")
        if hospedaje_id:
            relaciones = relaciones.filter(hospedaje_id=hospedaje_id)
        if destino_id:
            relaciones = relaciones.filter(destino_id=destino_id)
        return Response([
            {"id": relacion.id, "hospedaje_id": relacion.hospedaje_id, "destino_id": relacion.destino_id}
            for relacion in relaciones
        ])

    @swagger_auto_schema(
        operation_description="Asociar un hospedaje a un destino",
        request_body=HospedajeDestinoEntrada,
    )
    def post(self, request):
        hospedaje = get_object_or_404(Hospedaje, id=request.data.get("hospedaje_id"))
        destino = get_object_or_404(Destino, id=request.data.get("destino_id"))
        relacion, creada = HospedajeDestino.objects.get_or_create(hospedaje=hospedaje, destino=destino)
        return Response(
            {"id": relacion.id, "hospedaje_id": relacion.hospedaje_id, "destino_id": relacion.destino_id},
            status=status.HTTP_201_CREATED if creada else status.HTTP_200_OK,
        )


class HospedajeDestinoIdView(VistaCatalogo):
    @swagger_auto_schema(operation_description="Listar una relación entre hospedaje y destino")
    def get(self, request, id):
        relacion = get_object_or_404(HospedajeDestino, id=id)
        return Response({"id": relacion.id, "hospedaje_id": relacion.hospedaje_id, "destino_id": relacion.destino_id})

    @swagger_auto_schema(
        operation_description="Actualizar una relación entre hospedaje y destino. " + AVISO_COMPARTIDO,
        request_body=HospedajeDestinoEntrada,
    )
    def put(self, request, id):
        relacion = get_object_or_404(HospedajeDestino, id=id)
        error = catalogo_compartido(request, [relacion.destino_id])
        if error:
            return error
        hospedaje = get_object_or_404(Hospedaje, id=request.data.get("hospedaje_id"))
        destino = get_object_or_404(Destino, id=request.data.get("destino_id"))
        duplicada = HospedajeDestino.objects.exclude(id=id).filter(hospedaje=hospedaje, destino=destino).exists()
        if duplicada:
            return Response({"mensaje": "La relación ya existe"}, status=status.HTTP_409_CONFLICT)
        relacion.hospedaje = hospedaje
        relacion.destino = destino
        relacion.save()
        return Response({"id": relacion.id, "hospedaje_id": relacion.hospedaje_id, "destino_id": relacion.destino_id})

    @swagger_auto_schema(operation_description="Eliminar una relación entre hospedaje y destino. " + AVISO_COMPARTIDO)
    def delete(self, request, id):
        relacion = get_object_or_404(HospedajeDestino, id=id)
        error = catalogo_compartido(request, [relacion.destino_id])
        if error:
            return error
        relacion.delete()
        return Response({"mensaje": "Relación eliminada"})


##################################################################################################
class ImagenView(VistaCatalogo):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @swagger_auto_schema(
        operation_description="Listar imágenes. Opcional: ?destino_id=",
        manual_parameters=[
            openapi.Parameter("destino_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
        ],
    )
    def get(self, request):
        imagenLista = ImagenDestino.objects.all()
        destino_id = entero_query(request, "destino_id")
        if destino_id:
            imagenLista = imagenLista.filter(destino_id=destino_id)
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
        registroEncontrado = get_object_or_404(ImagenDestino, id=id)
        return Response({
            "id": registroEncontrado.id,
            "url_img": imagen_url(registroEncontrado.url_img, request),
            "destino_id": registroEncontrado.destino_id,
            "descripcion": registroEncontrado.descripcion,
        })

    @swagger_auto_schema(
        operation_description="Actualizar imagen. " + AVISO_COMPARTIDO,
        request_body=ImagenEntrada
    )
    def put(self, request, id):
        imagenB = get_object_or_404(ImagenDestino, id=id)
        error = catalogo_compartido(request, [imagenB.destino_id])
        if error:
            return error
        if request.data.get("url_img"):
            imagenB.url_img = request.data.get("url_img")
        imagenB.destino_id = request.data.get("destino_id")
        imagenB.descripcion = request.data.get("descripcion")
        imagenB.save()
        return Response({"mensaje": "Imagen actualizada"})

    @swagger_auto_schema(
        operation_description="Eliminar imagen. " + AVISO_COMPARTIDO
    )
    def delete(self, request, id):
        imagenEliminar = get_object_or_404(ImagenDestino, id=id)
        error = catalogo_compartido(request, [imagenEliminar.destino_id])
        if error:
            return error
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
            "url_img": imagen_url(imagen.url_img, request),
            "destino_id": imagen.destino_id,
            "descripcion": imagen.descripcion,
        })


class BusquedaCatalogoView(VistaCatalogo):
    @swagger_auto_schema(
        operation_description=(
            "Búsqueda del catálogo para la app: destinos, paquetes y hospedajes. "
            "Usa ?search= (obligatorio para filtrar; vacío devuelve listas vacías). "
            "Opcional: ?limite= (por tipo, por defecto 8, máximo 20)."
        ),
        manual_parameters=[
            openapi.Parameter("search", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=True),
            openapi.Parameter("limite", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
        ],
    )
    def get(self, request):
        from paquetes.models import Paquete
        from paquetes.views import paquete_json

        texto = texto_busqueda(request)
        limite = entero_query(request, "limite") or 8
        limite = min(max(limite, 1), 20)
        if not texto:
            return Response({"search": texto, "destinos": [], "paquetes": [], "hospedajes": []})

        destinos = Destino.objects.select_related("departamento").filter(
            Q(nombre__icontains=texto) | Q(descripcion__icontains=texto) | Q(departamento__nombre__icontains=texto)
        ).order_by("id")[:limite]
        paquetes = filtrar_catalogo(usuario_de(request), Paquete.objects.all()).filter(
            Q(nombre__icontains=texto)
            | Q(descripcion__icontains=texto)
            | Q(paquetedestino__destino__nombre__icontains=texto)
        ).distinct().order_by("id")[:limite]
        hospedajes = Hospedaje.objects.prefetch_related("destinos").filter(
            Q(nombre__icontains=texto) | Q(direccion__icontains=texto) | Q(destinos__nombre__icontains=texto)
        ).distinct().order_by("id")[:limite]
        return Response({
            "search": texto,
            "destinos": [destino_json(d, request) for d in destinos],
            "paquetes": [paquete_json(p, request) for p in paquetes],
            "hospedajes": [hospedaje_json(h, request) for h in hospedajes],
        })