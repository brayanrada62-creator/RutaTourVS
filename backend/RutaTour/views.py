from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from .serializer import UsuarioEntrada, loginSerializer, AgenciaEntrada,MensajeSalida
from .models import Usuario, Agencia
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
    
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
        return Response({'message': 'Credenciales inválidas'}, status=401)
    
###########################################################################################
    
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
        usuario = Usuario.objects.create(
            nombre_completo=nombre_completo,
            agencia_id=agencia_id,
            rol_id=rol_id,
            tipo_documento=tipo_documento,
            numero_documento=numero_documento,
            correo=correo,
            telefono=telefono,
            contrasena=contrasena
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
                'telefono': usuario.telefono
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
            'telefono': usuario.telefono
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
        usuario.contrasena = request.data.get('contrasena')
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
        agencia = Agencia.objects.create(
            nombre=nombre,
            nit=nit,
            direccion=direccion,
            telefono=telefono,
            correo=correo
        )
        return Response({'message': 'Agencia creada exitosamente'})
    
