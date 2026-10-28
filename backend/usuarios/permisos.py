"""Permisos de Ruta Tour.

Roles (tabla roles): 1 superadministrador, 2 administrador, 3 conductor, 4 cliente.
El token JWT pertenece al usuario de Django (auth.User, username = correo);
aquí se busca el Usuario de negocio con ese correo.
"""
from rest_framework import status
from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.response import Response

from .models import Usuario, UsuarioAgencia

ROL_SUPER = 1
ROL_ADMIN = 2
ROL_CONDUCTOR = 3
ROL_CLIENTE = 4


class EsSuperadministrador(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        correo = request.user.email or request.user.username
        return Usuario.objects.filter(
            correo__iexact=correo,
            rol__rol__iexact="superadministrador",
            activo=True,
        ).exists()


class EsAdministrador(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        correo = request.user.email or request.user.username
        return Usuario.objects.filter(
            correo__iexact=correo,
            rol__rol__iexact="administrador",
            activo=True,
        ).exists()


class EsConductor(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        correo = request.user.email or request.user.username
        return Usuario.objects.filter(
            correo__iexact=correo,
            rol__rol__iexact="conductor",
            activo=True,
        ).exists()


class EsCliente(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        correo = request.user.email or request.user.username
        return Usuario.objects.filter(
            correo__iexact=correo,
            rol__rol__iexact="cliente",
            activo=True,
        ).exists()


def usuario_de(request):
    """Usuario de negocio del token, o None si no hay sesión válida."""
    if hasattr(request, "_usuario_rt"):
        return request._usuario_rt
    usuario = None
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        correo = user.email or user.username
        usuario = Usuario.objects.filter(correo__iexact=correo).first()
    request._usuario_rt = usuario
    return usuario


def agencias_de(usuario):
    if usuario is None:
        return set()
    return set(UsuarioAgencia.objects.filter(usuario=usuario).values_list("agencia_id", flat=True))


def es_super(usuario):
    return usuario is not None and usuario.rol_id == ROL_SUPER


def es_admin(usuario):
    return usuario is not None and usuario.rol_id == ROL_ADMIN


def es_conductor(usuario):
    return usuario is not None and usuario.rol_id == ROL_CONDUCTOR


def es_personal(usuario):
    """Superadministrador o administrador."""
    return es_super(usuario) or es_admin(usuario)


def usuario_activo(request):
    """Usuario de negocio del token, solo si existe y no está suspendido."""
    usuario = usuario_de(request)
    if usuario is not None and usuario.activo:
        return usuario
    return None


def gestiona_agencia(usuario, agencia_id):
    """Superadmin: todas. Administrador: solo las agencias a las que pertenece."""
    if es_super(usuario):
        return True
    return es_admin(usuario) and agencia_id is not None and int(agencia_id) in agencias_de(usuario)


def trabaja_en_agencia(usuario, agencia_id):
    """Administrador o conductor de esa agencia (o superadmin)."""
    if gestiona_agencia(usuario, agencia_id):
        return True
    return es_conductor(usuario) and agencia_id is not None and int(agencia_id) in agencias_de(usuario)


def prohibido(mensaje="No tienes permiso para esta operación"):
    return Response({"message": mensaje}, status=status.HTTP_403_FORBIDDEN)


class Autenticado(BasePermission):
    """Token válido y Usuario de negocio existente y activo (permiso por defecto de la API)."""
    message = "Debes iniciar sesión"

    def has_permission(self, request, view):
        return usuario_activo(request) is not None


class LecturaPublica(BasePermission):
    """Catálogo: cualquiera puede leer; escribir solo administrador o superadministrador."""
    message = "Solo un administrador puede modificar el catálogo"

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return es_personal(usuario_activo(request))


class SoloPersonal(BasePermission):
    """Solo administrador o superadministrador."""
    message = "Solo un administrador puede hacer esta operación"

    def has_permission(self, request, view):
        return es_personal(usuario_activo(request))


def agencias_de_catalogo(usuario):
    """Agencias cuyo catálogo ve el usuario. Un cliente registrado por una agencia queda ligado a ella:
    solo ve y reserva lo suyo. None = sin restricción (cliente independiente, anónimo o personal)."""
    if usuario is None or usuario.rol_id != ROL_CLIENTE:
        return None
    return agencias_de(usuario) or None


def filtrar_catalogo(usuario, lista, campo="agencia_id"):
    """Aplica agencias_de_catalogo a un QuerySet (campo = ruta hasta el id de la agencia)."""
    agencias = agencias_de_catalogo(usuario)
    return lista if agencias is None else lista.filter(**{f"{campo}__in": agencias})


def es_cliente_de_viaje(usuario, viaje):
    """Cliente con una reserva no cancelada ni vencida en esa salida (o antigua, sin salida, del mismo paquete)."""
    from django.db.models import Q
    from reservas.models import Reserva  # import local para evitar ciclos entre apps

    if usuario is None or viaje is None:
        return False
    return (
        Reserva.objects.filter(usuario=usuario, paquete_id=viaje.paquete_id)
        .exclude(estado__in=("cancelada", "vencida"))
        .filter(Q(viaje=viaje) | Q(viaje__isnull=True))
        .exists()
    )


def es_cliente_de_paquete(usuario, paquete_id):
    """Cliente con una reserva no cancelada ni vencida en ese paquete."""
    from reservas.models import Reserva  # import local para evitar ciclos entre apps

    if usuario is None or not paquete_id:
        return False
    return Reserva.objects.filter(usuario=usuario, paquete_id=paquete_id).exclude(estado__in=("cancelada", "vencida")).exists()
