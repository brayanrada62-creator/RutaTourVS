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
from django.contrib.auth.hashers import make_password
from django.db import transaction
from rest_framework.permissions import AllowAny, IsAuthenticated

from .serializer import (
    UsuarioEntrada, loginSerializer, AgenciaEntrada, MensajeSalida,
    UsuarioAgenciaEntrada, RecuperarContrasenaEntrada,
    ConfirmarContrasenaEntrada, LoginGoogleEntrada,
)
from .models import Usuario, Agencia, Rol, UsuarioAgencia, RecuperarContrasena

def usuario_json(usuario):
    return {
        'id': usuario.id,
        'nombre_completo': usuario.nombre_completo,
        'rol_id': usuario.rol_id,
        'tipo_documento': usuario.tipo_documento,
        'numero_documento': usuario.numero_documento,
        'correo': usuario.correo,
        'telefono': usuario.telefono,
        'licencia': usuario.licencia,
    }


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
        logeo = Usuario.objects.filter(correo=email, contrasena=password).first()
        if logeo:
            return Response(emitir_sesion(logeo))
        return Response({'message': 'Credenciales inválidas'})


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
        if not correo:
            return Response({"message": "Escribe el correo"}, status=status.HTTP_400_BAD_REQUEST)

        respuesta = {"message": MENSAJE_RECUPERAR}
        usuario = Usuario.objects.filter(correo__iexact=correo).first()
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
        usuario.contrasena = contrasena
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
                agencia=None,
                rol=rol_cliente(),
                tipo_documento="google",
                numero_documento=documento,
                correo=correo,
                telefono="",
                contrasena="",
            )
        return Response(emitir_sesion(usuario))

##################################################################################################
class UsuarioView(APIView):
    @swagger_auto_schema(
        operation_description="Crea un nuevo usuario",
        request_body=UsuarioEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        serializer = UsuarioEntrada(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        usuario_data = serializer.validated_data.copy()
        agencia = usuario_data.pop('agencia', None)
        with transaction.atomic():
            usuario = Usuario.objects.create(**usuario_data)
            if agencia is not None:
                UsuarioAgencia.objects.create(usuario=usuario, agencia=agencia)
        return Response({'message': 'Usuario creado exitosamente'})

    @swagger_auto_schema(
        operation_description="Obtiene todos los usuarios",
        responses={200: UsuarioEntrada()}
    )
    def get(self, request):
        usuariolista = Usuario.objects.all()
        lista_usuarios = []
        for usuario in usuariolista:
            lista_usuarios.append({
                'id': usuario.id,
                'nombre_completo': usuario.nombre_completo,
                'rol_id': usuario.rol_id,
                'tipo_documento': usuario.tipo_documento,
                'numero_documento': usuario.numero_documento,
                'correo': usuario.correo,
                'telefono': usuario.telefono,
                'licencia': usuario.licencia,
            })
        return Response(lista_usuarios)


class UsuarioIdView(APIView):
    @swagger_auto_schema(
        operation_description="Obtiene un usuario por su ID",
        responses={200: UsuarioEntrada()}
    )
    def get(self, request, id):
        usuario = Usuario.objects.get(id=id)
        return Response({
            'id': usuario.id,
            'nombre_completo': usuario.nombre_completo,
            'rol_id': usuario.rol_id,
            'tipo_documento': usuario.tipo_documento,
            'numero_documento': usuario.numero_documento,
            'correo': usuario.correo,
            'telefono': usuario.telefono,
            'licencia': usuario.licencia,
        })

    @swagger_auto_schema(
        operation_description="Actualiza un usuario por su ID",
        request_body=UsuarioEntrada,
        responses={200: MensajeSalida}
    )
    def put(self, request, id):
        usuario = Usuario.objects.get(id=id)
        usuario.nombre_completo = request.data.get('nombre_completo')
        usuario.rol_id = request.data.get('rol_id')
        usuario.tipo_documento = request.data.get('tipo_documento')
        usuario.numero_documento = request.data.get('numero_documento')
        usuario.correo = request.data.get('correo')
        usuario.telefono = request.data.get('telefono')
        if request.data.get('contrasena'):
            usuario.contrasena = request.data.get('contrasena')
        if request.data.get('licencia') is not None:
            usuario.licencia = request.data.get('licencia')
        usuario.save()
        return Response({'message': 'Usuario actualizado exitosamente'})

    @swagger_auto_schema(
        operation_description="Elimina un usuario por su ID",
        responses={200: MensajeSalida}
    )
    def delete(self, request, id):
        usuario = Usuario.objects.get(id=id)
        usuario.delete()
        return Response({'message': 'Usuario eliminado exitosamente'})


class UsuarioDocumentoView(APIView):
    @swagger_auto_schema(
        operation_description="Busca un usuario por su número de documento"
    )
    def get(self, request, numero_documento):
        usuario = Usuario.objects.filter(numero_documento=numero_documento).first()
        if not usuario:
            return Response({'message': 'Usuario no encontrado'})
        return Response({
            'id': usuario.id,
            'nombre_completo': usuario.nombre_completo,
            'rol_id': usuario.rol_id,
            'tipo_documento': usuario.tipo_documento,
            'numero_documento': usuario.numero_documento,
            'correo': usuario.correo,
            'telefono': usuario.telefono,
            'licencia': usuario.licencia,
        })


##################################################################################################
class AgenciaView(APIView):
    @swagger_auto_schema(
        operation_description="Crea una nueva agencia",
        request_body=AgenciaEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
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
    @swagger_auto_schema(
        operation_description="Actualizar Agencia",
        request_body=AgenciaEntrada
    )
    def put(self, request, id):
        agenciaB = Agencia.objects.get(id=id)
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
        agenciaEliminar = Agencia.objects.get(id=id)
        agenciaEliminar.delete()
        return Response({"mensaje": "Agencia eliminada"})

    @swagger_auto_schema(
        operation_description="Listar Agencia"
    )
    def get(self, request, id):
        registroEncontrado = Agencia.objects.get(id=id)
        return Response({
            "id": registroEncontrado.id,
            "nombre": registroEncontrado.nombre,
            "nit": registroEncontrado.nit,
            "direccion": registroEncontrado.direccion,
            "telefono": registroEncontrado.telefono,
            "correo": registroEncontrado.correo,
        })


class AgenciaNitView(APIView):
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
        usuario_id = request.data.get('usuario_id')
        agencia_id = request.data.get('agencia_id')

        UsuarioAgencia.objects.create(
            usuario_id=usuario_id,
            agencia_id=agencia_id
        )
        return Response({'message': 'Usuario asociado a la agencia exitosamente'})
    
    @swagger_auto_schema(
        operation_description="Obtiene todas las asociaciones de usuarios y agencias",
        responses={200: UsuarioAgenciaEntrada()}
    )   
    def get(self, request):
        asociaciones = UsuarioAgencia.objects.all()
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
        asociacion = UsuarioAgencia.objects.get(id=id)
        asociacion.delete()
        return Response({'message': 'Asociación de usuario y agencia eliminada exitosamente'})