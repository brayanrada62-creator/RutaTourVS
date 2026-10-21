import hashlib
import json
import secrets
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from rest_framework.authtoken.models import Token
from django.contrib.auth.hashers import check_password, identify_hasher, make_password
from django.shortcuts import get_object_or_404
from rest_framework.permissions import AllowAny, IsAuthenticated

from .serializer import (
    UsuarioEntrada, loginSerializer, AgenciaEntrada, MensajeSalida,
    UsuarioAgenciaEntrada, RecuperarContrasenaEntrada,
    ConfirmarContrasenaEntrada, LoginGoogleEntrada,
)
from .models import Usuario, Agencia, Rol, UsuarioAgencia, RecuperarContrasena
from .permisos import (
    ROL_ADMIN, ROL_CLIENTE, ROL_CONDUCTOR, ROL_SUPER, LecturaPublica, SoloPersonal,
    agencias_de, es_admin, es_super, gestiona_agencia, prohibido, usuario_de,
)


def agencia_ids_de(usuario):
    return list(
        UsuarioAgencia.objects.filter(usuario=usuario).order_by("id").values_list("agencia_id", flat=True)
    )


def asociar_agencia(usuario, agencia_id):
    if agencia_id in (None, ""):
        return
    UsuarioAgencia.objects.get_or_create(usuario=usuario, agencia_id=agencia_id)


def usuario_json(usuario):
    ids = agencia_ids_de(usuario)
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


def emitir_sesion(usuario_negocio):
    auth_user, _created = User.objects.get_or_create(
        username=usuario_negocio.correo,
        defaults={'email': usuario_negocio.correo},
    )
    if not auth_user.email:
        auth_user.email = usuario_negocio.correo
        auth_user.save(update_fields=['email'])
    token, _created = Token.objects.get_or_create(user=auth_user)
    data = usuario_json(usuario_negocio)
    return {
        'message': 'Inicio de sesión exitoso',
        'token': token.key,
        'id': usuario_negocio.id,
        'usuario_id': usuario_negocio.id,
        'agencia_id': data.get('agencia_id'),
        'rol_id': usuario_negocio.rol_id,
        'nombre_completo': usuario_negocio.nombre_completo,
        'correo': usuario_negocio.correo,
        'telefono': usuario_negocio.telefono,
        'usuario': data,
    }


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
        responses={200: MensajeSalida}
        )
    def post(self, request):
        email = request.data.get('correo')
        password = request.data.get('contrasena')
        logeo = Usuario.objects.filter(correo__iexact=(email or "").strip()).first()
        if logeo and clave_correcta(logeo, password or ""):
            if not logeo.activo:
                return Response({'message': 'Usuario suspendido. Comunícate con tu agencia'},
                                status=status.HTTP_403_FORBIDDEN)
            return Response(emitir_sesion(logeo))
        return Response({'message': 'Credenciales inválidas'}, status=status.HTTP_401_UNAUTHORIZED)


class LogoutView(APIView):
    """Invalida el token en el servidor (el cliente además lo borra de su almacenamiento)."""

    @swagger_auto_schema(operation_description="Cerrar sesión: elimina el token del usuario")
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response({'message': 'Sesión cerrada'})


class UsuarioPerfilView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Obtiene el perfil del usuario autenticado"
    )
    def get(self, request):
        usuario = Usuario.objects.filter(correo=request.user.email).first()
        if not usuario:
            return Response({'name': '', 'role': ''})
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

        if len(contrasena) < 6:
            return Response(
                {"message": "La contraseña debe tener al menos 6 caracteres"},
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
            Token.objects.filter(user=auth_user).delete()

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
        return Response(emitir_sesion(usuario))

##################################################################################################
class UsuarioView(APIView):
    # El registro desde la app es público (queda como cliente); el resto se revisa por rol.
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description=(
            "Crea un usuario. Sin sesión: registro de cliente (rol 4, sin agencia). "
            "Administrador: conductores o clientes de su agencia. Superadministrador: cualquiera."
        ),
        request_body=UsuarioEntrada,
        responses={201: MensajeSalida}
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
        if yo is None:
            rol_id, agencia_id = ROL_CLIENTE, None
        elif es_admin(yo):
            if str(rol_id) not in (str(ROL_CONDUCTOR), str(ROL_CLIENTE)):
                return prohibido("Un administrador solo crea conductores o clientes")
            if not gestiona_agencia(yo, agencia_id):
                return prohibido("Solo puedes crear usuarios de tu agencia")
        elif not es_super(yo):
            return prohibido()

        if not correo or not numero_documento or not contrasena:
            return Response({'message': 'Correo, documento y contraseña son obligatorios'},
                            status=status.HTTP_400_BAD_REQUEST)
        if Usuario.objects.filter(correo__iexact=correo).exists() or \
                Usuario.objects.filter(numero_documento=numero_documento).exists():
            return Response({'message': 'Ya existe un usuario con ese correo o documento'},
                            status=status.HTTP_400_BAD_REQUEST)
        usuario = Usuario.objects.create(
            nombre_completo=nombre_completo,
            rol_id=rol_id,
            tipo_documento=tipo_documento,
            numero_documento=numero_documento,
            correo=correo,
            telefono=telefono,
            contrasena=make_password(contrasena),
            licencia=licencia
        )
        asociar_agencia(usuario, agencia_id)
        return Response({'message': 'Usuario creado exitosamente'})

    @swagger_auto_schema(
        operation_description="Obtiene todos los usuarios",
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
        lista_usuarios = []
        for usuario in usuariolista:
            lista_usuarios.append(usuario_json(usuario))
        return Response(lista_usuarios)


class UsuarioIdView(APIView):
    @swagger_auto_schema(
        operation_description="Obtiene un usuario por su ID",
        responses={200: UsuarioEntrada()}
    )
    def get(self, request, id):
        usuario = get_object_or_404(Usuario, id=id)
        if not puede_ver_usuario(usuario_de(request), usuario):
            return prohibido()
        return Response(usuario_json(usuario))

    @swagger_auto_schema(
        operation_description="Actualiza un usuario por su ID",
        request_body=UsuarioEntrada,
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
        if 'activo' in datos:
            nuevo_activo = str(datos.get('activo')).lower() in ("true", "1")
            if mismo and nuevo_activo != usuario.activo:
                return prohibido("No puedes suspenderte a ti mismo")
            usuario.activo = nuevo_activo
        usuario.save()
        if not usuario.activo:
            # La suspensión corta las sesiones abiertas (app y web).
            Token.objects.filter(user__username=usuario.correo).delete()
        sincronizar_auth_user(correo_anterior, usuario)
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
        usuario.delete()
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
        return Response(usuario_json(usuario))


##################################################################################################
class AgenciaView(APIView):
    permission_classes = [LecturaPublica]

    @swagger_auto_schema(
        operation_description="Crea una nueva agencia",
        request_body=AgenciaEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        if not es_super(usuario_de(request)):
            return prohibido("Solo el superadministrador crea agencias")
        nombre = request.data.get('nombre')
        nit = request.data.get('nit')
        direccion = request.data.get('direccion')
        telefono = request.data.get('telefono')
        correo = request.data.get('correo')

        Agencia.objects.create(
            nombre=nombre,
            nit=nit,
            direccion=direccion,
            telefono=telefono,
            correo=correo
        )
        return Response({'message': 'Agencia creada exitosamente'})

    @swagger_auto_schema(
        operation_description="Listar Agencias"
    )
    def get(self, request):
        agenciaLista = Agencia.objects.all()
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


class AgenciaIdView(APIView):
    permission_classes = [LecturaPublica]

    @swagger_auto_schema(
        operation_description="Actualizar Agencia",
        request_body=AgenciaEntrada
    )
    def put(self, request, id):
        agenciaB = get_object_or_404(Agencia, id=id)
        if not gestiona_agencia(usuario_de(request), agenciaB.id):
            return prohibido()
        agenciaB.nombre = request.data.get("nombre")
        agenciaB.nit = request.data.get("nit")
        agenciaB.direccion = request.data.get("direccion")
        agenciaB.telefono = request.data.get("telefono")
        agenciaB.correo = request.data.get("correo")
        agenciaB.save()
        return Response({"mensaje": "Agencia actualizada"})

    @swagger_auto_schema(
        operation_description="Eliminar agencia"
    )
    def delete(self, request, id):
        agenciaEliminar = get_object_or_404(Agencia, id=id)
        if not es_super(usuario_de(request)):
            return prohibido("Solo el superadministrador elimina agencias")
        agenciaEliminar.delete()
        return Response({"mensaje": "Agencia eliminada"})

    @swagger_auto_schema(
        operation_description="Listar Agencia"
    )
    def get(self, request, id):
        registroEncontrado = get_object_or_404(Agencia, id=id)
        return Response({
            "id": registroEncontrado.id,
            "nombre": registroEncontrado.nombre,
            "nit": registroEncontrado.nit,
            "direccion": registroEncontrado.direccion,
            "telefono": registroEncontrado.telefono,
            "correo": registroEncontrado.correo,
        })


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