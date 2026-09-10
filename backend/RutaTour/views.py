from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from .serializer import UsuarioEntrada, loginSerializer, AgenciaEntrada,MensajeSalida,TipoBusEntrada
from .models import Usuario, Agencia, TipoBus
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

    @swagger_auto_schema(
        operation_description="Listar Agencias"
    )    

    def get (self,request):
        agenciaLista = Agencia.objects.all()
        lista=[]
        for agencia in agenciaLista:
            lista.append({
                "nombre": agencia.id,
                "nit":agencia.nit,
                "direccion":agencia.direccion,
                "telefono":agencia.telefono,
                "correo":agencia.correo,

            })
        return Response(agencia)

class AgenciaIdView(APIView):
    @swagger_auto_schema(
        operation_description="Actualizar Agencia",
        request_body=AgenciaEntrada
    )

    def put(self, request, id):
        #buscar select * from transporte where id=2
        agenciaB=Agencia.objects.get(id=id)
        agenciaB.nombre=request.data.get("nombre")
        agenciaB.nit=request.data.get("nit")
        agenciaB.direccion.data.get("direccion")
        agenciaB.telefono.data.get("telefono")
        agenciaB.correo.data.get("correo")
        agenciaB.save()
        return Response({
            "mensaje":"Agencia actualizada"
        })

    @swagger_auto_schema(
            operation_description="Eliminar  agencia"
    )

    def delete(self,request, id):
        agenciaEliminar=Agencia.objects.get(id=id)
        agenciaEliminar.delete() #delete from agencia where id=2
        return Response({
            "mensaje": "Agencia eliminada"
        })

    @swagger_auto_schema(
            operation_description="Listar Agencia"
    )

    def get(self, request, id):
        registroEncontrado=Agencia.objects.get(id=id)
        return Response({
            "id": registroEncontrado.id,
            "nombre": registroEncontrado.nombre,
            "nit":registroEncontrado.nit,
            "direccion":registroEncontrado.direccion,
            "telefono":registroEncontrado.telefono,
            "correo":registroEncontrado.correo,
        })
###################################################################
class TipoBusView(APIView):
    @swagger_auto_schema(
        operation_description="Listar Buses"
    )
    def get (self,request):
        tipoBusLista= TipoBus.objects.all()
        lista=[]
        for tipoBus in tipoBusLista:
            lista.append({
                "nombre":tipoBus.id,
                "agencia_id":tipoBus.agencia,
                "capacidad":tipoBus.capacidad,
                "descripcion":tipoBus.descripcion,

            })
            return Response (lista)

    @swagger_auto_schema(
        operation_description="Guardar Bus",
        request_body=TipoBusEntrada
        )
    def post (self, request):
        nombre=request.data.get("nombre")
        agencia_id=request.data.get("agencia_id")
        capacidad=request.data.get("capacidad")
        descripcion=request.data.get("descripcion")

        tipoBusB=TipoBus.objects.create(
            nombre=nombre,
            agencia=agencia_id,
            capacidad=capacidad,
            descripcion=descripcion
        )
        return Response ({"mensaje": "Tipo de bus almacenado correctamente"})

class TipoBusIdView(APIView):
    @swagger_auto_schema (
        operation_description="Actualizar Tipo de bus",
        request_body=TipoBusEntrada

    )
    def put(self,request,id):
        tipoBusB=TipoBus.objects.get(id=id)
        tipoBusB.nombre=request.data.get("nombre")
        tipoBusB.agencia=request.data.get("agencia")
        tipoBusB.capacidad=request.data.get("capacidad")
        tipoBusB.descripcion=request.data.get("descripcion")
        return Response({
            "mensaje":"Tipo de bus actualizado"
        })

    @swagger_auto_schema(
            operation_description="Eliminar tipo de bus"
    )

    def delete(self, request, id):
        tipoBusEliminar=TipoBus.objects.get(id=id)
        tipoBusEliminar=TipoBus.delete()
        return Response({
            "mensaje":"Tipo de bus eliminado"
        })

    @swagger_auto_schema(
        operation_description="Listar tipo de bus por id"
    )
    def get (self,request,id):
        registroEncontrado=TipoBus.objects.get(id=id)
        return Response({
            "id":registroEncontrado.id,
            "nombre":registroEncontrado.nombre,
            "agencia_id":registroEncontrado.agencia,
            "capacidad":registroEncontrado.capacidad,
            "descripcion":registroEncontrado.descripcion,
        })