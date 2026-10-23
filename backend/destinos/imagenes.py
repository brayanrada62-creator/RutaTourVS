from .models import Departamento, ImagenDestino


def imagen_url(campo, request=None):
    if not campo:
        return None
    try:
        url = campo.url
    except ValueError:
        return None
    if request is not None:
        return request.build_absolute_uri(url)
    return url


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
