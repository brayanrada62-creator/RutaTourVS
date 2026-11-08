import secrets

from PIL import Image

from .models import Departamento, ImagenDestino

FOTO_MAX_BYTES = 5 * 1024 * 1024
FORMATOS_FOTO = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}


def validar_foto(archivo, que="La foto"):
    """Mensaje de error si no es una imagen JPG, PNG o WEBP de máximo 5 MB; None si sirve.
    Se revisa el contenido con Pillow (cambiarle la extensión a otro archivo no basta). Si sirve, se le
    pone un nombre aleatorio: la URL en Cloudinary no se puede adivinar ni dice de quién es."""
    if archivo.size > FOTO_MAX_BYTES:
        return f"{que} supera 5 MB"
    try:
        with Image.open(archivo) as imagen:
            formato = imagen.format
            imagen.verify()
    except Exception:
        formato = None
    archivo.seek(0)
    if formato not in FORMATOS_FOTO:
        return f"{que} debe ser una imagen JPG, PNG o WEBP"
    archivo.name = f"{secrets.token_hex(8)}.{FORMATOS_FOTO[formato]}"
    return None


def borrar_archivo(campo):
    """Borra del almacenamiento (Cloudinary o local) el archivo de un campo, si tiene uno."""
    if campo:
        try:
            campo.storage.delete(campo.name)
        except Exception:
            pass  # si ya no existe, no impide guardar el nuevo


def imagen_url(campo, request=None):
    """URL completa de una imagen o archivo (también la usan pagos y la licencia en PDF).
    Cloudinary ya la entrega absoluta (https://res.cloudinary.com/...) y se devuelve tal cual;
    en local (MEDIA_ROOT) es relativa (/media/...) y se completa con el dominio de la petición."""
    if not campo:
        return None
    try:
        url = campo.url
    except ValueError:
        return None
    if url.startswith(("http://", "https://")) or request is None:
        return url
    return request.build_absolute_uri(url)


def archivo_imagen(request):
    if not hasattr(request, "FILES"):
        return None
    return (
        request.FILES.get("imagen")
        or request.FILES.get("url_img")
        or request.FILES.get("foto")
        or request.FILES.get("image")
    )


def resolver_departamento(valor):
    if valor in (None, ""):
        depto = Departamento.objects.order_by("id").first()
        if depto:
            return depto
        return Departamento.objects.create(nombre="General")
    if str(valor).isdigit():
        depto = Departamento.objects.filter(id=int(valor)).first()
        if depto:
            return depto
    nombre = str(valor).strip()
    depto = Departamento.objects.filter(nombre__iexact=nombre).first()
    if depto:
        return depto
    return Departamento.objects.create(nombre=nombre[:100])


def guardar_imagen_destino(destino, archivo, descripcion=""):
    if not archivo:
        return
    ImagenDestino.objects.create(
        url_img=archivo,
        destino=destino,
        descripcion=descripcion or "",
    )


def destino_json(destino, request=None):
    imagenes = [
        {
            "id": img.id,
            "url_img": imagen_url(img.url_img, request),
            "descripcion": img.descripcion,
        }
        for img in ImagenDestino.objects.filter(destino=destino)
    ]
    primera = imagenes[0]["url_img"] if imagenes else None
    return {
        "id": destino.id,
        "nombre": destino.nombre,
        "departamento": destino.departamento.nombre if destino.departamento_id else None,
        "descripcion": destino.descripcion,
        "imagen": primera,
        "url_img": primera,
        "imagenes": imagenes,
    }
