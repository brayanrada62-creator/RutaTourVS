import hashlib
import json
import secrets
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db.models import Count, ProtectedError, Q, Sum
from django.db.models.functions import TruncDate
from django.core.validators import validate_email
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from django.contrib.auth.hashers import check_password, identify_hasher, make_password
from django.shortcuts import get_object_or_404
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from drf_yasg import openapi

from .serializer import (
    UsuarioEditarEntrada, UsuarioEntrada, loginSerializer, AgenciaEntrada, MensajeSalida,
    UsuarioAgenciaEntrada, RecuperarContrasenaEntrada,
    ConfirmarContrasenaEntrada, LoginGoogleEntrada,
)
from .models import Usuario, Agencia, Rol, UsuarioAgencia, RecuperarContrasena
from .paginacion import PARAMETRO_AGENCIA, PARAMETROS_LISTA, paginar, texto_busqueda
from .permisos import (
    MENSAJE_AGENCIA_DESACTIVADA, ROL_ADMIN, ROL_CLIENTE, ROL_CONDUCTOR, LecturaPublica, SesionVigente, SoloPersonal,
    agencia_desactivada, agencias_de, es_admin, es_super, filtrar_agencia_super, gestiona_agencia, prohibido, usuario_de,
)
from buses.models import Bus, TipoBus, Viaje
from destinos.imagenes import imagen_url
from destinos.models import Hospedaje
from pagos.models import Pago
from paquetes.models import Paquete
from reservas.models import reservas_activas


def agencia_ids_de(usuario):
    return list(
        UsuarioAgencia.objects.filter(usuario=usuario).order_by("id").values_list("agencia_id", flat=True)
    )


def asociar_agencia(usuario, agencia_id):
    if agencia_id in (None, ""):
        return
    UsuarioAgencia.objects.get_or_create(usuario=usuario, agencia_id=agencia_id)


LICENCIA_PDF_MAX_BYTES = 5 * 1024 * 1024


def error_licencia_pdf(archivo):
    """Mensaje de error si el archivo no es un PDF de máximo 5 MB; None si sirve.
    Se revisa la extensión y también el contenido (todo PDF empieza con %PDF-)."""
    if not str(archivo.name).lower().endswith(".pdf"):
        return "La licencia debe ser un archivo .pdf"
    if archivo.size > LICENCIA_PDF_MAX_BYTES:
        return "La licencia en PDF supera 5 MB"
    inicio = archivo.read(5)
    archivo.seek(0)
    if inicio != b"%PDF-":
        return "El archivo no es un PDF válido"
    return None


def puede_gestionar_licencia(yo, objetivo):
    """Subir o ver la licencia en PDF: superadmin, o admin de una agencia en común con el usuario."""
    if es_super(yo):
        return True
    return es_admin(yo) and bool(agencias_de(yo) & agencias_de(objetivo))


def archivo_licencia(request):
    """El PDF enviado en multipart con el nombre 'licencia_pdf' (o None)."""
    return request.FILES.get("licencia_pdf") if hasattr(request, "FILES") else None


def validar_licencia_pdf(archivo):
    """Mensaje de error, o None si sirve. Si sirve le pone un nombre aleatorio (después de validar):
    así la URL del archivo no se puede adivinar a partir del documento del conductor."""
    error = error_licencia_pdf(archivo)
    if error is None:
        archivo.name = f"licencia_{secrets.token_hex(8)}.pdf"
    return error


def borrar_licencia_pdf(usuario):
    """Borra del almacenamiento (local o Cloudinary) el PDF guardado, si hay uno."""
    if usuario.licencia_pdf:
        usuario.licencia_pdf.storage.delete(usuario.licencia_pdf.name)


def usuario_json(usuario, request=None):
    """licencia_pdf_url solo aparece para el superadmin o el admin de la misma agencia (con request)."""
    ids = agencia_ids_de(usuario)
    yo = usuario_de(request) if request is not None else None
    puede_ver_pdf = yo is not None and puede_gestionar_licencia(yo, usuario)
    return {
        'id': usuario.id,
        'nombre_completo': usuario.nombre_completo,
        'agencia_id': ids[0] if ids else None,
        'agencia_ids': ids,
        'rol_id': usuario.rol_id,
        'tipo_documento': usuario.tipo_documento,
        'numero_documento': usuario.numero_documento,
        'correo': usuario.correo,
        'telefono': usuario.telefono,
        'licencia': usuario.licencia,
        'tiene_licencia_pdf': bool(usuario.licencia_pdf),
        'licencia_pdf_url': imagen_url(usuario.licencia_pdf, request) if puede_ver_pdf else None,
        'activo': usuario.activo,
    }


def es_hash(valor):
    try:
        identify_hasher(valor)
        return True
    except ValueError:
        return False


def clave_correcta(usuario, clave):
    """Compara con el hash de Django. Una clave vieja en texto plano se acepta
    una sola vez y se guarda ya cifrada."""
    guardada = usuario.contrasena or ""
    if not guardada or not clave:
        return False
    if es_hash(guardada):
        return check_password(clave, guardada)
    if secrets.compare_digest(guardada, clave):
        usuario.contrasena = make_password(clave)
        usuario.save(update_fields=["contrasena"])
        return True
    return False


def sincronizar_auth_user(correo_anterior, usuario):
    """El token pertenece al auth.User con username = correo; si cambia el correo, se actualiza."""
    auth_user = User.objects.filter(username=correo_anterior).first()
    if auth_user and correo_anterior != usuario.correo:
        auth_user.username = usuario.correo
        auth_user.email = usuario.correo
        auth_user.save(update_fields=["username", "email"])


def puede_ver_usuario(yo, objetivo):
    """El mismo usuario, el superadmin, o el admin de una agencia común (solo conductores y clientes)."""
    if yo is None:
        return False
    if yo.id == objetivo.id or es_super(yo):
        return True
    return (
        es_admin(yo)
        and objetivo.rol_id in (ROL_CONDUCTOR, ROL_CLIENTE)
        and bool(agencias_de(yo) & agencias_de(objetivo))
    )


def hash_valor(valor):
    return hashlib.sha256(valor.encode("utf-8")).hexdigest()


def revocar_sesiones(auth_user):
    """Pone en la lista negra todos los refresh token del usuario: nadie puede renovar su sesión (app y web).
    El access que ya se emitió sigue válido hasta que venza (1 hora), pero Autenticado exige que el usuario esté activo."""
    for emitido in OutstandingToken.objects.filter(user=auth_user):
        BlacklistedToken.objects.get_or_create(token=emitido)


def emitir_sesion(usuario_negocio, auth_user=None):
    if auth_user is None:
        auth_user = User.objects.filter(username__iexact=usuario_negocio.correo).first()
        if auth_user is None:
            auth_user = User.objects.create_user(
                username=usuario_negocio.correo,
                email=usuario_negocio.correo,
            )
    if not auth_user.email:
        auth_user.email = usuario_negocio.correo
        auth_user.save(update_fields=['email'])
    return datos_sesion(usuario_negocio, auth_user)


def datos_sesion(usuario_negocio, auth_user, mensaje='Login correcto'):
    """Tokens + datos del usuario. La app (Android) lee "usuario" como objeto y el panel (Angular)
    lee rol_id y agencia_id; "correo" conserva el valor que antes iba en "usuario"."""
    refresh = RefreshToken.for_user(auth_user)
    access = str(refresh.access_token)
    data = usuario_json(usuario_negocio)
    return {
        'message': 'Inicio de sesión exitoso',
        'mensaje': 'Login correcto',
        'token': access,  # Angular y Android leen 'token'
        'access': access,
        'refresh': str(refresh),
        'id': usuario_negocio.id,
        'usuario_id': usuario_negocio.id,
        'agencia_id': data.get('agencia_id'),
        'rol_id': usuario_negocio.rol_id,
        'rol': usuario_negocio.rol.rol,
        'nombre_completo': usuario_negocio.nombre_completo,
        'correo': usuario_negocio.correo,
        'telefono': usuario_negocio.telefono,
        'usuario': data,
    }


CLAVE_MINIMA = 8


def error_registro(nombre, correo, documento, telefono, clave):
    """Reglas del registro público (las mismas que valida la app). Devuelve el mensaje o None."""
    if not str(nombre or "").strip():
        return "Escribe tu nombre completo"
    try:
        validate_email(str(correo or ""))
    except ValidationError:
        return "Escribe un correo válido"
    documento = str(documento or "")
    if not (documento.isdigit() and 5 <= len(documento) <= 15):
        return "El documento debe tener de 5 a 15 dígitos"
    telefono = str(telefono or "")
    if telefono and not (telefono.isdigit() and 7 <= len(telefono) <= 15):
        return "El teléfono debe tener de 7 a 15 dígitos"
    if len(str(clave or "")) < CLAVE_MINIMA:
        return f"La contraseña debe tener al menos {CLAVE_MINIMA} caracteres"
    return None


def rol_cliente():
    rol = Rol.objects.filter(rol__iexact="cliente").first()
    if rol:
        return rol
    return Rol.objects.get_or_create(rol="cliente")[0]


def verificar_google_id_token(id_token):
    url = "https://oauth2.googleapis.com/tokeninfo?id_token=" + urllib.parse.quote(id_token)
    try:
        with urllib.request.urlopen(url, timeout=10) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, ValueError):
        return None
    client_id = getattr(settings, "GOOGLE_CLIENT_ID", "") or ""
    if client_id and datos.get("aud") != client_id:
        return None
    if str(datos.get("email_verified", "")).lower() not in {"true", "1"}:
        return None
    if not datos.get("email"):
        return None
    return datos


class LoginView(APIView):
    permission_classes = [AllowAny]
    @swagger_auto_schema(
        request_body=loginSerializer,
        responses={200: openapi.Response(description="Tokens JWT y datos del usuario")}
        )
    def post(self, request):
        email = str(request.data.get('correo') or '').strip()
        password = request.data.get('contrasena')
        usuario_negocio = Usuario.objects.filter(correo__iexact=email).first()
        if (
            usuario_negocio is None
            or not isinstance(password, str)
            or not clave_correcta(usuario_negocio, password)
        ):
            return Response(
                {"message": "Credenciales inválidas", "mensaje": "Usuario o contraseña incorrectos"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if not usuario_negocio.activo:
            return Response(
                {"message": "Usuario suspendido. Comunícate con tu agencia",
                 "mensaje": "Usuario suspendido. Comunícate con tu agencia"},
                status=status.HTTP_403_FORBIDDEN,
            )
        if agencia_desactivada(usuario_negocio):
            return Response({"message": MENSAJE_AGENCIA_DESACTIVADA, "mensaje": MENSAJE_AGENCIA_DESACTIVADA},
                            status=status.HTTP_403_FORBIDDEN)

        auth_user = User.objects.filter(username__iexact=usuario_negocio.correo).first()
        if auth_user is None:
            auth_user = User.objects.create_user(
                username=usuario_negocio.correo,
                email=usuario_negocio.correo,
                password=password,
            )
        elif not auth_user.check_password(password):
            auth_user.set_password(password)
            auth_user.save(update_fields=["password"])

        return Response(emitir_sesion(usuario_negocio, auth_user))


class LogoutView(APIView):
    """Invalida el refresh token; el access token vence en pocos minutos."""

    @swagger_auto_schema(
        operation_description="Cierra sesión invalidando el refresh token.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={"refresh": openapi.Schema(type=openapi.TYPE_STRING)},
            required=["refresh"],
        ),
    )
    def post(self, request):
        refresh = request.data.get("refresh")
        if not refresh:
            return Response(
                {"mensaje": "Debes enviar el refresh token"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            refresh_token = RefreshToken(refresh)
        except TokenError:
            return Response(
                {"mensaje": "El refresh token no es válido"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if str(refresh_token.get("user_id")) != str(request.user.id):
            return Response(
                {"mensaje": "Ese refresh token pertenece a otro usuario"},
                status=status.HTTP_403_FORBIDDEN,
            )
        refresh_token.blacklist()
        return Response({"mensaje": "Sesión cerrada"})


class UsuarioPerfilView(APIView):
    # Permiso por defecto (Autenticado): token válido y usuario activo.

    @swagger_auto_schema(
        operation_description="Obtiene el perfil del usuario autenticado"
    )
    def get(self, request):
        usuario = usuario_de(request)
        data = usuario_json(usuario)
        data['name'] = usuario.nombre_completo
        data['role'] = usuario.rol.rol
        return Response(data)


MENSAJE_RECUPERAR = "Si el correo existe, enviaremos un código para restablecer la contraseña."


class PasswordResetView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description="Solicita recuperar contraseña. Envía un código al correo.",
        request_body=RecuperarContrasenaEntrada,
        responses={200: MensajeSalida},
    )
    def post(self, request):
        correo = (request.data.get("correo") or "").strip()
        telefono = "".join(ch for ch in str(request.data.get("telefono") or "") if ch.isdigit())
        if not correo and not telefono:
            return Response({"message": "Escribe el correo"}, status=status.HTTP_400_BAD_REQUEST)

        respuesta = {"message": MENSAJE_RECUPERAR}
        if correo:
            usuario = Usuario.objects.filter(correo__iexact=correo).first()
        else:
            # Búsqueda por teléfono en el servidor: la lista de usuarios ya no es pública.
            usuario = next(
                (u for u in Usuario.objects.exclude(telefono="")
                 if "".join(ch for ch in u.telefono if ch.isdigit()).endswith(telefono[-10:])),
                None,
            ) if len(telefono) >= 7 else None
        if not usuario:
            return Response(respuesta)

        RecuperarContrasena.objects.filter(usuario=usuario, usado=False).update(usado=True)
        token = secrets.token_urlsafe(32)
        codigo = f"{secrets.randbelow(1000000):06d}"
        RecuperarContrasena.objects.create(
            usuario=usuario,
            token_hash=hash_valor(token),
            codigo_hash=hash_valor(codigo),
        )

        enlace = ""
        base = getattr(settings, "FRONTEND_RESET_URL", "") or ""
        if base:
            separador = "&" if "?" in base else "?"
            enlace = f"{base}{separador}token={token}"

        cuerpo = (
            f"Hola {usuario.nombre_completo},\n\n"
            "Recibimos una solicitud para restablecer tu contraseña de RutaTour.\n"
            f"Tu código es: {codigo}\n"
            "Vence en 1 hora.\n"
        )
        if enlace:
            cuerpo += f"\nTambién puedes usar este enlace:\n{enlace}\n"
        cuerpo += "\nSi no fuiste tú, ignora este correo.\n"

        try:
            send_mail(
                "Recuperar contraseña RutaTour",
                cuerpo,
                settings.DEFAULT_FROM_EMAIL,
                [usuario.correo],
                fail_silently=False,
            )
        except Exception:
            pass

        if settings.DEBUG:
            respuesta["codigo"] = codigo
            respuesta["token"] = token
        return Response(respuesta)


class PasswordResetConfirmarView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description="Confirma el restablecimiento con token o con correo + código de 6 dígitos.",
        request_body=ConfirmarContrasenaEntrada,
        responses={200: MensajeSalida},
    )
    def post(self, request):
        token = (request.data.get("token") or "").strip()
        correo = (request.data.get("correo") or "").strip()
        codigo = (request.data.get("codigo") or "").strip()
        contrasena = request.data.get("contrasena") or ""
        confirmar = request.data.get("confirmar") or contrasena

        if len(contrasena) < CLAVE_MINIMA:
            return Response(
                {"message": f"La contraseña debe tener al menos {CLAVE_MINIMA} caracteres"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if contrasena != confirmar:
            return Response(
                {"message": "Las contraseñas no coinciden"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        registro = None
        limite = timezone.now() - timedelta(hours=1)
        pendientes = RecuperarContrasena.objects.filter(usado=False, creado__gte=limite)
        if token:
            registro = pendientes.filter(token_hash=hash_valor(token)).first()
        elif correo and codigo:
            usuario = Usuario.objects.filter(correo__iexact=correo).first()
            if usuario:
                registro = pendientes.filter(
                    usuario=usuario,
                    codigo_hash=hash_valor(codigo),
                ).first()

        if not registro:
            return Response(
                {"message": "El código o el enlace no es válido o ya venció"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        usuario = registro.usuario
        usuario.contrasena = make_password(contrasena)
        usuario.save(update_fields=["contrasena"])
        registro.usado = True
        registro.save(update_fields=["usado"])

        auth_user = User.objects.filter(username=usuario.correo).first()
        if auth_user:
            auth_user.set_password(contrasena)
            auth_user.save()
            for token_guardado in OutstandingToken.objects.filter(user=auth_user):
                try:
                    RefreshToken(token_guardado.token).blacklist()
                except TokenError:
                    pass

        return Response({"message": "Contraseña actualizada. Ya puedes iniciar sesión."})


class LoginGoogleView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description=(
            "Login con Google. El frontend/app obtiene el id_token de Google Sign-In "
            "y lo envía aquí. El backend lo valida y devuelve el token de RutaTour."
        ),
        request_body=LoginGoogleEntrada,
    )
    def post(self, request):
        id_token = (request.data.get("id_token") or "").strip()
        if not id_token:
            return Response(
                {"message": "Falta el id_token de Google"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        datos = verificar_google_id_token(id_token)
        if not datos:
            return Response(
                {"message": "El token de Google no es válido"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        correo = datos["email"].strip()
        nombre = datos.get("name") or correo.split("@")[0]
        google_id = datos.get("sub") or correo
        usuario = Usuario.objects.filter(correo__iexact=correo).first()
        if usuario is None:
            documento = ("G" + google_id)[-30:]
            if Usuario.objects.filter(numero_documento=documento).exists():
                documento = f"G{secrets.randbelow(10**9)}"
            usuario = Usuario.objects.create(
                nombre_completo=nombre,
                rol=rol_cliente(),
                tipo_documento="google",
                numero_documento=documento,
                correo=correo,
                telefono="",
                contrasena="",
            )
        if not usuario.activo:
            return Response({'message': 'Usuario suspendido. Comunícate con tu agencia'},
                            status=status.HTTP_403_FORBIDDEN)
        if agencia_desactivada(usuario):
            return Response({'message': MENSAJE_AGENCIA_DESACTIVADA}, status=status.HTTP_403_FORBIDDEN)
        return Response(emitir_sesion(usuario))

##################################################################################################
def datos_conductores(usuarios):
    """bus_id, placa y viajes_pendientes (programados o en curso) de cada conductor."""
    from buses.models import Bus_Conductor, Viaje  # import local para evitar ciclos entre apps

    ids = list(usuarios.values_list("id", flat=True))
    datos = {i: {"bus_id": None, "placa": None, "viajes_pendientes": 0} for i in ids}
    buses = {}
    for asignacion in Bus_Conductor.objects.filter(conductor_id__in=ids).select_related("bus").order_by("id"):
        buses[asignacion.conductor_id] = asignacion.bus
    pendientes = {
        fila["bus_id"]: fila["n"]
        for fila in Viaje.objects.filter(bus_id__in=[b.id for b in buses.values()])
        .exclude(estado=Viaje.COMPLETADO)
        .values("bus_id")
        .annotate(n=Count("id"))
    }
    for conductor_id, bus in buses.items():
        datos[conductor_id] = {"bus_id": bus.id, "placa": bus.placa, "viajes_pendientes": pendientes.get(bus.id, 0)}
    return datos


class RolView(APIView):
    @swagger_auto_schema(operation_description="Listar roles: [{id, nombre}]")
    def get(self, request):
        return Response([{"id": rol.id, "nombre": rol.rol} for rol in Rol.objects.order_by("id")])


class UsuarioView(APIView):
    # El registro desde la app es público (queda como cliente); el resto se revisa por rol.
    permission_classes = [SesionVigente]
    # JSON como siempre, o multipart/form-data cuando el conductor trae su licencia en PDF.
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @swagger_auto_schema(
        operation_description=(
            "Crea un usuario. Sin sesión: registro de cliente (rol 4, sin agencia) con nombre, correo válido, "
            "documento de 5 a 15 dígitos, contraseña de 8 o más y teléfono de 7 a 15 dígitos si se envía (400 si no). "
            "Administrador: conductores o clientes de su agencia. Superadministrador: cualquiera. "
            "Conductor (rol 3): se puede enviar como multipart/form-data con 'licencia_pdf' (.pdf, máx. 5 MB; "
            "400 si no cumple). Solo el admin de la agencia o el superadmin suben ese PDF (403 sin sesión)."
        ),
        request_body=UsuarioEntrada,
        # Swagger muestra formulario con selector de archivo; la vista acepta también JSON.
        consumes=["multipart/form-data"],
        responses={201: openapi.Response(description="Registro exitoso con tokens JWT")}
    )
    def post(self, request):
        nombre_completo = request.data.get('nombre_completo')
        agencia_id = request.data.get('agencia_id')
        rol_id = request.data.get('rol_id')
        tipo_documento = request.data.get('tipo_documento')
        numero_documento = request.data.get('numero_documento')
        correo = request.data.get('correo')
        telefono = request.data.get('telefono')
        contrasena = request.data.get('contrasena')
        licencia = request.data.get('licencia', '')

        yo = usuario_de(request)
        registro_publico = not request.user.is_authenticated
        if registro_publico:
            rol_id, agencia_id = ROL_CLIENTE, None
            error = error_registro(nombre_completo, correo, numero_documento, telefono, contrasena)
            if error:
                return Response({'message': error}, status=status.HTTP_400_BAD_REQUEST)
            tipo_documento = tipo_documento or "CC"
        elif yo is None:
            return prohibido()
        elif es_admin(yo):
            if str(rol_id) not in (str(ROL_CONDUCTOR), str(ROL_CLIENTE)):
                return prohibido("Un administrador solo crea conductores o clientes")
            if not gestiona_agencia(yo, agencia_id):
                return prohibido("Solo puedes crear usuarios de tu agencia")
        elif not es_super(yo):
            return prohibido()

        licencia_pdf = archivo_licencia(request)
        if licencia_pdf is not None:
            if registro_publico:
                return prohibido("Solo la agencia sube la licencia del conductor")
            if str(rol_id) != str(ROL_CONDUCTOR):
                return Response({'message': 'La licencia en PDF solo aplica a conductores'},
                                status=status.HTTP_400_BAD_REQUEST)
            error = validar_licencia_pdf(licencia_pdf)
            if error:
                return Response({'message': error}, status=status.HTTP_400_BAD_REQUEST)

        if not correo or not numero_documento or not contrasena:
            return Response({'message': 'Correo, documento y contraseña son obligatorios'},
                            status=status.HTTP_400_BAD_REQUEST)
        if Usuario.objects.filter(correo__iexact=correo).exists() or \
                Usuario.objects.filter(numero_documento=numero_documento).exists() or \
                User.objects.filter(username__iexact=correo).exists():
            return Response({'message': 'Ya existe un usuario con ese correo o documento'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            rol = Rol.objects.get(id=rol_id)
        except Rol.DoesNotExist:
            return Response(
                {"mensaje": "El rol seleccionado no existe"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        usuario = Usuario.objects.create(
            nombre_completo=nombre_completo,
            rol=rol,
            tipo_documento=tipo_documento,
            numero_documento=numero_documento,
            correo=correo,
            telefono=telefono,
            contrasena=make_password(contrasena),
            licencia=licencia,
            licencia_pdf=licencia_pdf,
        )
        auth_user = User.objects.create_user(
            username=correo,
            email=correo,
            password=contrasena,
        )
        asociar_agencia(usuario, agencia_id)
        if registro_publico:
            return Response(datos_sesion(usuario, auth_user, "Registro correcto"), status=status.HTTP_201_CREATED)
        return Response({'message': 'Usuario creado exitosamente', 'id': usuario.id})

    @swagger_auto_schema(
        operation_description=(
            "Obtiene los usuarios visibles para quien consulta. Filtros opcionales: "
            "?rol_id= (3 conductores, 2 administradores; con 3 cada conductor trae bus_id, placa y viajes_pendientes), "
            "?agencia_id= (solo superadmin; para el admin se ignora), ?search=, ?page= y ?page_size=. "
            "Cada usuario trae tiene_licencia_pdf y "
            "licencia_pdf_url (solo visible para el superadmin o el admin de su agencia; si no, null)."
        ),
        manual_parameters=[
            openapi.Parameter("rol_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            PARAMETRO_AGENCIA,
        ] + PARAMETROS_LISTA,
        responses={200: UsuarioEntrada()}
    )
    def get(self, request):
        yo = usuario_de(request)
        if es_super(yo):
            usuariolista = Usuario.objects.all()
        elif es_admin(yo):
            ids = UsuarioAgencia.objects.filter(agencia_id__in=agencias_de(yo)).values_list("usuario_id", flat=True)
            usuariolista = Usuario.objects.filter(id__in=set(ids) | {yo.id})
        else:
            return prohibido()
        params = request.query_params
        if str(params.get("rol_id", "")).isdigit():
            usuariolista = usuariolista.filter(rol_id=params["rol_id"])
        usuariolista = filtrar_agencia_super(request, usuariolista, "usuarioagencia__agencia_id")
        texto = texto_busqueda(request)
        if texto:
            usuariolista = usuariolista.filter(
                Q(nombre_completo__icontains=texto) | Q(correo__icontains=texto) | Q(numero_documento__icontains=texto)
            )
        usuariolista = usuariolista.order_by("id")
        extras = datos_conductores(usuariolista) if str(params.get("rol_id")) == str(ROL_CONDUCTOR) else {}
        return Response(paginar(request, usuariolista, lambda u: {**usuario_json(u, request), **extras.get(u.id, {})}))


class UsuarioIdView(APIView):
    # JSON como siempre, o multipart/form-data para reemplazar la licencia en PDF del conductor.
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @swagger_auto_schema(
        operation_description=(
            "Obtiene un usuario por su ID. licencia_pdf_url solo la ven el superadmin y el admin de su agencia."
        ),
        responses={200: UsuarioEntrada()}
    )
    def get(self, request, id):
        usuario = get_object_or_404(Usuario, id=id)
        if not puede_ver_usuario(usuario_de(request), usuario):
            return prohibido()
        return Response(usuario_json(usuario, request))

    @swagger_auto_schema(
        operation_description=(
            "Actualiza un usuario por su ID (JSON o multipart/form-data). Los campos que no se envían se conservan. "
            "'licencia_pdf' (.pdf, máx. 5 MB) reemplaza el PDF anterior del conductor: solo el admin de su "
            "agencia o el superadmin (403); 400 si no es PDF, pesa más de 5 MB o el usuario no es conductor."
        ),
        request_body=UsuarioEditarEntrada,
        # Swagger muestra formulario con selector de archivo; la vista acepta también JSON.
        consumes=["multipart/form-data"],
        responses={200: MensajeSalida}
    )
    def put(self, request, id):
        usuario = get_object_or_404(Usuario, id=id)
        yo = usuario_de(request)
        if not puede_ver_usuario(yo, usuario):
            return prohibido()
        datos = request.data
        mismo = yo.id == usuario.id
        rol_nuevo = datos.get('rol_id', usuario.rol_id)
        agencia_nueva = datos.get('agencia_id')
        if not es_super(yo):
            # Nadie cambia su propio rol, y un admin no puede crear administradores.
            if str(rol_nuevo) != str(usuario.rol_id) and (mismo or str(rol_nuevo) not in (str(ROL_CONDUCTOR), str(ROL_CLIENTE))):
                return prohibido("No puedes cambiar ese rol")
            if agencia_nueva not in (None, "") and (mismo or not gestiona_agencia(yo, agencia_nueva)):
                return prohibido("No puedes asignar esa agencia")
        licencia_pdf = archivo_licencia(request)
        if licencia_pdf is not None:
            if not puede_gestionar_licencia(yo, usuario):
                return prohibido("Solo el administrador de su agencia sube la licencia del conductor")
            if str(rol_nuevo) != str(ROL_CONDUCTOR):
                return Response({'message': 'La licencia en PDF solo aplica a conductores'},
                                status=status.HTTP_400_BAD_REQUEST)
            error = validar_licencia_pdf(licencia_pdf)
            if error:
                return Response({'message': error}, status=status.HTTP_400_BAD_REQUEST)
        correo_anterior = usuario.correo
        usuario.nombre_completo = datos.get('nombre_completo', usuario.nombre_completo)
        usuario.rol_id = rol_nuevo
        usuario.tipo_documento = datos.get('tipo_documento', usuario.tipo_documento)
        usuario.numero_documento = datos.get('numero_documento', usuario.numero_documento)
        usuario.correo = datos.get('correo', usuario.correo)
        usuario.telefono = datos.get('telefono', usuario.telefono)
        if datos.get('contrasena'):
            usuario.contrasena = make_password(datos.get('contrasena'))
        if datos.get('licencia') is not None:
            usuario.licencia = datos.get('licencia')
        if licencia_pdf is not None:
            borrar_licencia_pdf(usuario)  # el PDF anterior no queda huérfano en el almacenamiento
            usuario.licencia_pdf = licencia_pdf
        if 'activo' in datos:
            nuevo_activo = str(datos.get('activo')).lower() in ("true", "1")
            if mismo and nuevo_activo != usuario.activo:
                return prohibido("No puedes suspenderte a ti mismo")
            usuario.activo = nuevo_activo
        usuario.save()
        sincronizar_auth_user(correo_anterior, usuario)
        auth_user = User.objects.filter(username=usuario.correo).first()
        if auth_user and not usuario.activo:
            for token_guardado in OutstandingToken.objects.filter(user=auth_user):
                try:
                    RefreshToken(token_guardado.token).blacklist()
                except TokenError:
                    pass
        if datos.get('contrasena'):
            if auth_user:
                auth_user.set_password(datos.get('contrasena'))
                auth_user.save(update_fields=["password"])
        if not mismo:
            asociar_agencia(usuario, agencia_nueva)
        return Response({'message': 'Usuario actualizado exitosamente'})

    @swagger_auto_schema(
        operation_description="Elimina un usuario por su ID",
        responses={200: MensajeSalida}
    )
    def delete(self, request, id):
        usuario = get_object_or_404(Usuario, id=id)
        yo = usuario_de(request)
        if yo.id == usuario.id or not (es_super(yo) or (es_admin(yo) and puede_ver_usuario(yo, usuario))):
            return prohibido()
        archivo_pdf = usuario.licencia_pdf.name if usuario.licencia_pdf else None
        try:
            usuario.delete()
        except ProtectedError:
            # Sus pagos se conservan para la auditoría: se suspende en lugar de borrarlo.
            return Response({'message': 'El usuario tiene pagos registrados; suspéndelo en lugar de eliminarlo'},
                            status=status.HTTP_409_CONFLICT)
        if archivo_pdf:
            Usuario._meta.get_field("licencia_pdf").storage.delete(archivo_pdf)
        return Response({'message': 'Usuario eliminado exitosamente'})


class UsuarioDocumentoView(APIView):
    permission_classes = [SoloPersonal]

    @swagger_auto_schema(
        operation_description="Busca un usuario por su número de documento"
    )
    def get(self, request, numero_documento):
        usuario = Usuario.objects.filter(numero_documento=numero_documento).first()
        if not usuario or not puede_ver_usuario(usuario_de(request), usuario):
            return Response({'message': 'Usuario no encontrado'})
        return Response(usuario_json(usuario, request))


class DashboardResumenView(APIView):
    @swagger_auto_schema(
        operation_description=(
            "Obtiene las estadísticas de las agencias asociadas al administrador "
            "autenticado y los últimos paquetes y pagos."
        )
    )
    def get(self, request):
        correo_usuario = request.user.email or request.user.username
        try:
            usuario = Usuario.objects.get(correo__iexact=correo_usuario)
        except Usuario.DoesNotExist:
            return Response(
                {"mensaje": "No se encontró un usuario asociado al token"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if usuario.rol_id != ROL_ADMIN:
            return Response(
                {"mensaje": "Solo un administrador puede consultar el resumen"},
                status=status.HTTP_403_FORBIDDEN,
            )

        agencia_ids = agencias_de(usuario)
        if not agencia_ids:
            return Response(
                {"mensaje": "El administrador no tiene una agencia vinculada"},
                status=status.HTTP_403_FORBIDDEN,
            )

        cantidad_usuarios = Usuario.objects.filter(
            usuarioagencia__agencia_id__in=agencia_ids
        ).distinct().count()
        cantidad_paquetes = Paquete.objects.filter(agencia_id__in=agencia_ids).count()
        cantidad_buses = Bus.objects.filter(agencia_id__in=agencia_ids).count()
        cantidad_hospedajes = Hospedaje.objects.filter(
            destinos__paquetedestino__paquete__agencia_id__in=agencia_ids
        ).distinct().count()

        zona_horaria = ZoneInfo("America/Bogota")
        fecha_actual = timezone.localtime(timezone.now(), zona_horaria).date()
        fecha_inicio = fecha_actual - timedelta(days=6)
        fecha_inicio_local = timezone.make_aware(
            datetime.combine(fecha_inicio, time.min),
            zona_horaria,
        )
        fecha_fin_local = timezone.make_aware(
            datetime.combine(fecha_actual + timedelta(days=1), time.min),
            zona_horaria,
        )

        pagos_aprobados = Pago.objects.filter(
            estado="aprobado",
            reserva__paquete__agencia_id__in=agencia_ids,
        )
        pagos_por_fecha = pagos_aprobados.filter(
            fecha_pago__gte=fecha_inicio_local,
            fecha_pago__lt=fecha_fin_local,
        ).annotate(
            fecha=TruncDate("fecha_pago", tzinfo=zona_horaria)
        ).values(
            "fecha"
        ).annotate(
            total=Sum("precio")
        ).order_by("fecha")

        pagos_ultimos_7_dias = []
        for numero_dia in range(7):
            fecha_dia = fecha_inicio + timedelta(days=numero_dia)
            pagos_ultimos_7_dias.append({
                "fecha": fecha_dia.isoformat(),
                "total": Decimal("0.00"),
            })

        for pago_dia in pagos_por_fecha:
            for dia in pagos_ultimos_7_dias:
                if dia["fecha"] == pago_dia["fecha"].isoformat():
                    dia["total"] = pago_dia["total"] or Decimal("0.00")

        paquetes_recientes = Paquete.objects.filter(
            agencia_id__in=agencia_ids
        ).order_by("-fecha_creacion", "-id")[:3]
        ultimos_paquetes = []
        for paquete in paquetes_recientes:
            ultimos_paquetes.append({
                "id": paquete.id,
                "nombre": paquete.nombre,
                "fecha_creacion": timezone.localtime(
                    paquete.fecha_creacion, zona_horaria
                ).isoformat(),
                "precio": paquete.precio,
                "estado": paquete.estado,
            })

        pagos_recientes = pagos_aprobados.select_related(
            "reserva__paquete"
        ).order_by("-fecha_pago", "-id")[:3]
        ultimos_pagos = []
        for pago in pagos_recientes:
            ultimos_pagos.append({
                "id": pago.id,
                "precio": pago.precio,
                "fecha_pago": timezone.localtime(
                    pago.fecha_pago, zona_horaria
                ).isoformat(),
                "estado": pago.estado,
                "reserva_id": pago.reserva_id,
                "paquete_nombre": pago.reserva.paquete.nombre,
            })

        return Response({
            "total_usuarios": cantidad_usuarios,
            "total_paquetes": cantidad_paquetes,
            "total_buses": cantidad_buses,
            "total_hospedajes": cantidad_hospedajes,
            "pagos_ultimos_7_dias": pagos_ultimos_7_dias,
            "ultimos_paquetes": ultimos_paquetes,
            "ultimos_pagos": ultimos_pagos,
        })


##################################################################################################
def resumen_de_agencia(agencia, hoy):
    """Totales de una agencia para el inicio del superadmin."""
    ingresos = Pago.objects.filter(estado="aprobado", reserva__paquete__agencia=agencia).aggregate(total=Sum("precio"))
    return {
        "id": agencia.id,
        "nombre": agencia.nombre,
        "correo": agencia.correo,
        "activo": agencia.activo,
        "buses": Bus.objects.filter(agencia=agencia).count(),
        "conductores": UsuarioAgencia.objects.filter(agencia=agencia, usuario__rol_id=ROL_CONDUCTOR).count(),
        "paquetes": Paquete.objects.filter(agencia=agencia).count(),
        "viajes_mes": Viaje.objects.filter(bus__agencia=agencia, fecha__year=hoy.year, fecha__month=hoy.month).count(),
        "reservas": reservas_activas().filter(paquete__agencia=agencia).count(),
        "ingresos_aprobados": str(ingresos["total"] or Decimal("0.00")),
    }


class ResumenAgenciasView(APIView):
    @swagger_auto_schema(
        operation_description=(
            "Totales de cada agencia, también las desactivadas. Solo superadmin (403). viajes_mes: viajes del mes "
            "actual en hora de Colombia. reservas: las vigentes (ni canceladas ni vencidas). ingresos_aprobados: "
            "suma histórica de los pagos aprobados."
        ),
        responses={
            200: openapi.Response("Una fila por agencia", openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                    "id": openapi.Schema(type=openapi.TYPE_INTEGER),
                    "nombre": openapi.Schema(type=openapi.TYPE_STRING),
                    "correo": openapi.Schema(type=openapi.TYPE_STRING),
                    "activo": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    "buses": openapi.Schema(type=openapi.TYPE_INTEGER),
                    "conductores": openapi.Schema(type=openapi.TYPE_INTEGER),
                    "paquetes": openapi.Schema(type=openapi.TYPE_INTEGER),
                    "viajes_mes": openapi.Schema(type=openapi.TYPE_INTEGER),
                    "reservas": openapi.Schema(type=openapi.TYPE_INTEGER),
                    "ingresos_aprobados": openapi.Schema(type=openapi.TYPE_STRING, example="150000.00"),
                }),
            )),
            401: "Sin sesión",
            403: "Solo superadmin",
        },
    )
    def get(self, request):
        if not es_super(usuario_de(request)):
            return prohibido("Solo el superadministrador consulta el resumen de agencias")
        hoy = timezone.localtime(timezone.now(), ZoneInfo("America/Bogota")).date()
        return Response([resumen_de_agencia(agencia, hoy) for agencia in Agencia.objects.order_by("id")])


def agencia_json(agencia):
    return {
        "id": agencia.id,
        "nombre": agencia.nombre,
        "nit": agencia.nit,
        "direccion": agencia.direccion,
        "telefono": agencia.telefono,
        "correo": agencia.correo,
        "activo": agencia.activo,
    }


def leer_agencia(datos, parcial=False):
    """(datos validados, error 400). Sin esto un POST o PUT incompleto terminaba en error 500."""
    entrada = AgenciaEntrada(data=datos, partial=parcial)
    if entrada.is_valid():
        return entrada.validated_data, None
    campo, errores = next(iter(entrada.errors.items()))
    return None, Response({"message": f"{campo}: {errores[0]}"}, status=status.HTTP_400_BAD_REQUEST)


def cerrar_sesiones_de_agencia(agencia):
    """Al desactivar: revoca los refresh de su personal que ya no tenga otra agencia activa."""
    for relacion in UsuarioAgencia.objects.filter(agencia=agencia).select_related("usuario"):
        if agencia_desactivada(relacion.usuario):
            auth_user = User.objects.filter(username__iexact=relacion.usuario.correo).first()
            if auth_user:
                revocar_sesiones(auth_user)


class AgenciaView(APIView):
    permission_classes = [LecturaPublica]

    @swagger_auto_schema(
        operation_description="Crea una nueva agencia. Solo superadmin (403). 400 si falta un dato o no es válido.",
        request_body=AgenciaEntrada,
        responses={200: MensajeSalida, 400: "Datos inválidos", 403: "Solo superadmin"}
    )
    def post(self, request):
        if not es_super(usuario_de(request)):
            return prohibido("Solo el superadministrador crea agencias")
        datos, error = leer_agencia(request.data)
        if error:
            return error
        Agencia.objects.create(**datos)
        return Response({'message': 'Agencia creada exitosamente'})

    @swagger_auto_schema(
        operation_description=(
            "Listar agencias. Superadmin: todas, también las desactivadas. Admin: solo las suyas. "
            "Cliente, conductor y sin sesión: solo las activas."
        )
    )
    def get(self, request):
        yo = usuario_de(request)
        agenciaLista = Agencia.objects.order_by("id")
        if es_admin(yo):
            agenciaLista = agenciaLista.filter(id__in=agencias_de(yo))
        elif not es_super(yo):
            agenciaLista = agenciaLista.filter(activo=True)
        return Response([agencia_json(agencia) for agencia in agenciaLista])


class AgenciaIdView(APIView):
    permission_classes = [LecturaPublica]

    @swagger_auto_schema(
        operation_description=(
            "Actualizar agencia; los campos que no se envían se conservan. Superadmin: cualquiera. "
            "Admin: solo la suya (403) y sin cambiar 'activo' (403). Con activo=false su personal no puede "
            "entrar, se cierran sus sesiones y sus paquetes salen del catálogo; las reservas se conservan."
        ),
        request_body=AgenciaEntrada,
        responses={200: MensajeSalida, 400: "Datos inválidos", 403: "Sin permiso", 404: "No existe"}
    )
    def put(self, request, id):
        agenciaB = get_object_or_404(Agencia, id=id)
        yo = usuario_de(request)
        if not gestiona_agencia(yo, agenciaB.id):
            return prohibido()
        datos, error = leer_agencia(request.data, parcial=True)
        if error:
            return error
        if "activo" in datos and not es_super(yo):
            return prohibido("Solo el superadministrador activa o desactiva agencias")
        se_desactiva = agenciaB.activo and datos.get("activo") is False
        for campo, valor in datos.items():
            setattr(agenciaB, campo, valor)
        agenciaB.save()
        if se_desactiva:
            cerrar_sesiones_de_agencia(agenciaB)
        return Response({"mensaje": "Agencia actualizada"})

    @swagger_auto_schema(
        operation_description=(
            "Eliminar agencia. Solo superadmin (403) y solo si está vacía: si tiene buses, tipos de bus, paquetes "
            "o usuarios responde 409 con 'totales' y no borra nada. Para retirarla usa PUT con activo=false."
        ),
        responses={200: MensajeSalida, 403: "Solo superadmin", 404: "No existe", 409: "La agencia tiene datos"}
    )
    def delete(self, request, id):
        agenciaEliminar = get_object_or_404(Agencia, id=id)
        if not es_super(usuario_de(request)):
            return prohibido("Solo el superadministrador elimina agencias")
        totales = {
            "buses": Bus.objects.filter(agencia=agenciaEliminar).count(),
            "tipos_bus": TipoBus.objects.filter(agencia=agenciaEliminar).count(),
            "paquetes": Paquete.objects.filter(agencia=agenciaEliminar).count(),
            "usuarios": UsuarioAgencia.objects.filter(agencia=agenciaEliminar).count(),
        }
        if any(totales.values()):
            return Response(
                {"message": f"La agencia tiene {totales['buses']} buses, {totales['tipos_bus']} tipos de bus, "
                            f"{totales['paquetes']} paquetes y {totales['usuarios']} usuarios. "
                            "Desactívala en lugar de eliminarla.",
                 "totales": totales},
                status=status.HTTP_409_CONFLICT,
            )
        agenciaEliminar.delete()
        return Response({"mensaje": "Agencia eliminada"})

    @swagger_auto_schema(
        operation_description="Consultar agencia. Admin: solo la suya (403). Los demás roles: cualquiera."
    )
    def get(self, request, id):
        registroEncontrado = get_object_or_404(Agencia, id=id)
        yo = usuario_de(request)
        if es_admin(yo) and not gestiona_agencia(yo, registroEncontrado.id):
            return prohibido()
        return Response(agencia_json(registroEncontrado))


class AgenciaNitView(APIView):
    permission_classes = [AllowAny]
    @swagger_auto_schema(
        operation_description="Busca una agencia por su NIT"
    )
    def get(self, request, nit):
        agencia = Agencia.objects.filter(nit=nit).first()
        if not agencia:
            return Response({"mensaje": "Agencia no encontrada"})
        return Response({
            "id": agencia.id,
            "nombre": agencia.nombre,
            "nit": agencia.nit,
            "direccion": agencia.direccion,
            "telefono": agencia.telefono,
            "correo": agencia.correo,
        })


class AgenciaDireccionView(APIView):
    permission_classes = [AllowAny]
    @swagger_auto_schema(
        operation_description="Busca agencias por dirección"
    )
    def get(self, request, direccion):
        agenciaLista = Agencia.objects.filter(direccion__icontains=direccion)
        lista = []
        for agencia in agenciaLista:
            lista.append({
                "id": agencia.id,
                "nombre": agencia.nombre,
                "nit": agencia.nit,
                "direccion": agencia.direccion,
                "telefono": agencia.telefono,
                "correo": agencia.correo,
            })
        return Response(lista)
    
#######################################################################################################################################################

class UsuarioAgenciaView(APIView):
    @swagger_auto_schema(
        operation_description="Asocia un usuario a una agencia",
        request_body=UsuarioAgenciaEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        serializer = UsuarioAgenciaEntrada(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        datos = serializer.validated_data
        yo = usuario_de(request)
        objetivo = datos.get("usuario")
        objetivo = objetivo if isinstance(objetivo, Usuario) else Usuario.objects.filter(id=request.data.get("usuario_id")).first()
        agencia = datos.get("agencia")
        agencia_id = agencia.id if isinstance(agencia, Agencia) else request.data.get("agencia_id")
        if not gestiona_agencia(yo, agencia_id) or (
            not es_super(yo) and objetivo is not None and objetivo.rol_id not in (ROL_CONDUCTOR, ROL_CLIENTE)
        ):
            return prohibido()
        asociacion = UsuarioAgencia.objects.create(**datos)
        return Response(
            {
                'id': asociacion.id,
                'usuario_id': asociacion.usuario_id,
                'agencia_id': asociacion.agencia_id,
            },
            status=status.HTTP_201_CREATED,
        )
    
    @swagger_auto_schema(
        operation_description="Obtiene todas las asociaciones de usuarios y agencias",
        responses={200: UsuarioAgenciaEntrada()}
    )   
    def get(self, request):
        yo = usuario_de(request)
        if es_super(yo):
            asociaciones = UsuarioAgencia.objects.all()
        elif es_admin(yo):
            asociaciones = UsuarioAgencia.objects.filter(agencia_id__in=agencias_de(yo))
        else:
            asociaciones = UsuarioAgencia.objects.filter(usuario=yo)
        lista_asociaciones = []
        for asociacion in asociaciones:
            lista_asociaciones.append({
                'id': asociacion.id,
                'usuario_id': asociacion.usuario_id,
                'agencia_id': asociacion.agencia_id,
            })
        return Response(lista_asociaciones)
    
    @swagger_auto_schema(
        operation_description="Elimina una asociación de usuario y agencia por su ID",
        responses={200: MensajeSalida}
    )
    def delete(self, request, id):
        asociacion = get_object_or_404(UsuarioAgencia, id=id)
        if not gestiona_agencia(usuario_de(request), asociacion.agencia_id):
            return prohibido()
        asociacion.delete()
        return Response({'message': 'Asociación de usuario y agencia eliminada exitosamente'})
