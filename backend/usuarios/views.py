from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from .serializer import (UsuarioEntrada, loginSerializer, AgenciaEntrada, MensajeSalida)
from .models import (Usuario, Agencia, Rol)
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated


def es_superadmin(rol_id):
    if rol_id in (None, ""):
        return False
    rol = Rol.objects.filter(pk=rol_id).only("rol").first()
    if not rol or not rol.rol:
        return False
    nombre = rol.rol.replace(" ", "").replace("_", "").lower()
    return nombre == "superadmin"


def normalizar_agencia_id(rol_id, agencia_id):
    if es_superadmin(rol_id) or agencia_id in (None, "", "null"):
        return None
    return agencia_id


def usuario_json(usuario):
    return {
        'id': usuario.id,
        'nombre_completo': usuario.nombre_completo,
        'agencia_id': usuario.agencia_id,
        'rol_id': usuario.rol_id,
        'tipo_documento': usuario.tipo_documento,
        'numero_documento': usuario.numero_documento,
        'correo': usuario.correo,
        'telefono': usuario.telefono,
        'licencia': usuario.licencia,
        'activo': usuario.activo,
    }


class LoginView(APIView):
    @swagger_auto_schema(
        request_body=loginSerializer,
        responses={200: MensajeSalida}
        )
    def post(self, request):
        email = request.data.get('correo')
        password = request.data.get('contrasena')
        logeo = Usuario.objects.filter(correo=email, contrasena=password).first()
        if logeo and not logeo.activo:
            return Response({'message': 'Esta cuenta está desactivada'})
        if logeo:
            usuario, created = User.objects.get_or_create(
                username=logeo.correo,
                defaults={'email': logeo.correo},
            )
            if not usuario.email:
                usuario.email = logeo.correo
                usuario.save(update_fields=['email'])
            token, created = Token.objects.get_or_create(user=usuario)
            data = usuario_json(logeo)
            return Response({
                'message': 'Inicio de sesión exitoso',
                'token': token.key,
                'id': logeo.id,
                'usuario_id': logeo.id,
                'rol_id': logeo.rol_id,
                'nombre_completo': logeo.nombre_completo,
                'correo': logeo.correo,
                'telefono': logeo.telefono,
                'usuario': data,
            })
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


class PasswordResetView(APIView):
    @swagger_auto_schema(operation_description="Solicita restablecer contraseña")
    def post(self, request):
        correo = request.data.get("correo")
        if not correo:
            return Response({"message": "Escribe el correo"})
        return Response({"message": "Si el correo existe, se enviará el enlace"})

##################################################################################################
class UsuarioView(APIView):
    @swagger_auto_schema(
        operation_description="Crea un nuevo usuario",
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
        agencia_id = normalizar_agencia_id(rol_id, agencia_id)
        Usuario.objects.create(
            nombre_completo=nombre_completo,
            agencia_id=agencia_id,
            rol_id=rol_id,
            tipo_documento=tipo_documento,
            numero_documento=numero_documento,
            correo=correo,
            telefono=telefono,
            contrasena=contrasena,
            licencia=licencia
        )
        return Response({'message': 'Usuario creado exitosamente'})

    @swagger_auto_schema(
        operation_description="Obtiene todos los usuarios",
        responses={200: UsuarioEntrada()}
    )
    def get(self, request):
        usuariolista = Usuario.objects.all()
        return Response([usuario_json(usuario) for usuario in usuariolista])


class UsuarioIdView(APIView):
    @swagger_auto_schema(
        operation_description="Obtiene un usuario por su ID",
        responses={200: UsuarioEntrada()}
    )
    def get(self, request, id):
        usuario = Usuario.objects.get(id=id)
        return Response(usuario_json(usuario))

    @swagger_auto_schema(
        operation_description="Actualiza un usuario por su ID",
        request_body=UsuarioEntrada,
        responses={200: MensajeSalida}
    )
    def put(self, request, id):
        usuario = Usuario.objects.get(id=id)
        usuario.nombre_completo = request.data.get('nombre_completo')
        usuario.rol_id = request.data.get('rol_id')
        usuario.agencia_id = normalizar_agencia_id(
            usuario.rol_id,
            request.data.get('agencia_id'),
        )
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
        return Response(usuario_json(usuario))


class UsuarioEstadoView(APIView):
    @swagger_auto_schema(
        operation_description="Activa o desactiva un usuario",
        responses={200: MensajeSalida}
    )
    def post(self, request, id):
        usuario = Usuario.objects.filter(id=id).first()
        if not usuario:
            return Response({'message': 'Usuario no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        if 'activo' not in request.data:
            return Response({'message': 'Falta el estado del usuario'}, status=status.HTTP_400_BAD_REQUEST)
        usuario.activo = valor_activo(request.data.get('activo'))
        usuario.save(update_fields=['activo'])
        return Response(usuario_json(usuario))


def valor_activo(valor):
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, str):
        return valor.strip().lower() in ('1', 'true', 'si', 'sí')
    return bool(valor)


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