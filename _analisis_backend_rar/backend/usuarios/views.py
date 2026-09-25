from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from .serializer import (UsuarioEntrada, loginSerializer, AgenciaEntrada, MensajeSalida)
from .models import (Usuario, Agencia)
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated

class LoginView(APIView):
    @swagger_auto_schema(
        request_body=loginSerializer,
        responses={200: MensajeSalida}
        )
    def post(self, request):
        email = request.data.get('correo')
        password = request.data.get('contrasena')
        logeo = Usuario.objects.filter(correo=email, contrasena=password).first()
        if logeo:
            usuario, created = User.objects.get_or_create(
                username=logeo.correo,
                defaults={'email': logeo.correo},
            )
            token, created = Token.objects.get_or_create(user=usuario)
            return Response({'message': 'Inicio de sesión exitoso', 'token': token.key})
        return Response({'message': 'Credenciales inválidas'})


class UsuarioPerfilView(APIView):
    """
    Devuelve el nombre y el rol del usuario actualmente autenticado
    (a partir del token enviado en el header Authorization).
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Obtiene el nombre y el rol del usuario autenticado"
    )
    def get(self, request):
        usuario = Usuario.objects.filter(correo=request.user.email).first()
        if not usuario:
            return Response({'name': '', 'role': ''})
        return Response({
            'name': usuario.nombre_completo,
            'role': usuario.rol.rol
        })

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
        lista_usuarios = []
        for usuario in usuariolista:
            lista_usuarios.append({
                'id': usuario.id,
                'nombre_completo': usuario.nombre_completo,
                'agencia_id': usuario.agencia_id,
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
            'agencia_id': usuario.agencia_id,
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
        usuario.agencia_id = request.data.get('agencia_id')
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
            'agencia_id': usuario.agencia_id,
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