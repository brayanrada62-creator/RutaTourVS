from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from .serializer import (
    UsuarioEntrada, loginSerializer, AgenciaEntrada, MensajeSalida, TipoBusEntrada,
    BusEntrada, AsientoEntrada, DestinoEntrada, HopedajeEntrada, SitioTuristicoEntrada,
    ImagenEntrada, PaqueteEntrada, PaqueteDestinoEntrada, ItinerarioEntrada,
    ReservaEntrada, AsientoReservaEntrada, PagoEntrada
)
from .models import (
    Usuario, Agencia, TipoBus, Bus, Asiento, Destino, Hospedaje, SitioTuristico,
    ImagenDestino, Paquete, PaqueteDestino, Itinerario, Reserva, AsientoReserva, Pago
)
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
        agenciaB.direccion=request.data.get("direccion")
        agenciaB.telefono=request.data.get("telefono")
        agenciaB.correo=request.data.get("correo")
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
        tipoBusEliminar.delete()
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
        
##################################################################################################
class BusView(APIView):
    @swagger_auto_schema(
        operation_description="Listar Buses"
    )
    def get(self, request):
        busLista = Bus.objects.all()
        lista = []
        for bus in busLista:
            lista.append({
                "id": bus.id,
                "placa": bus.placa,
                "agencia_id": bus.agencia_id,
                "tipo_bus_id": bus.tipo_bus_id,
                "marca": bus.marca,
                "modelo": bus.modelo,
                "estado": bus.estado,
                "fecha_registro": bus.fecha_registro,
            })
        return Response(lista)

    @swagger_auto_schema(
        operation_description="Guardar Bus",
        request_body=BusEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        placa = request.data.get("placa")
        agencia_id = request.data.get("agencia_id")
        tipo_bus_id = request.data.get("tipo_bus_id")
        marca = request.data.get("marca")
        modelo = request.data.get("modelo")
        estado = request.data.get("estado")
        fecha_registro = request.data.get("fecha_registro")

        Bus.objects.create(
            placa=placa,
            agencia_id=agencia_id,
            tipo_bus_id=tipo_bus_id,
            marca=marca,
            modelo=modelo,
            estado=estado,
            fecha_registro=fecha_registro
        )
        return Response({"mensaje": "Bus almacenado correctamente"})


class BusIdView(APIView):
    @swagger_auto_schema(
        operation_description="Listar bus por id"
    )
    def get(self, request, id):
        registroEncontrado = Bus.objects.get(id=id)
        return Response({
            "id": registroEncontrado.id,
            "placa": registroEncontrado.placa,
            "agencia_id": registroEncontrado.agencia_id,
            "tipo_bus_id": registroEncontrado.tipo_bus_id,
            "marca": registroEncontrado.marca,
            "modelo": registroEncontrado.modelo,
            "estado": registroEncontrado.estado,
            "fecha_registro": registroEncontrado.fecha_registro,
        })

    @swagger_auto_schema(
        operation_description="Actualizar bus",
        request_body=BusEntrada
    )
    def put(self, request, id):
        busB = Bus.objects.get(id=id)
        busB.placa = request.data.get("placa")
        busB.agencia_id = request.data.get("agencia_id")
        busB.tipo_bus_id = request.data.get("tipo_bus_id")
        busB.marca = request.data.get("marca")
        busB.modelo = request.data.get("modelo")
        busB.estado = request.data.get("estado")
        busB.fecha_registro = request.data.get("fecha_registro")
        busB.save()
        return Response({"mensaje": "Bus actualizado"})

    @swagger_auto_schema(
        operation_description="Eliminar bus"
    )
    def delete(self, request, id):
        busEliminar = Bus.objects.get(id=id)
        busEliminar.delete()
        return Response({"mensaje": "Bus eliminado"})


##################################################################################################
class AsientoView(APIView):
    @swagger_auto_schema(
        operation_description="Listar asientos"
    )
    def get(self, request):
        asientoLista = Asiento.objects.all()
        lista = []
        for asiento in asientoLista:
            lista.append({
                "id": asiento.id,
                "bus_id": asiento.bus_id,
                "numero_asiento": asiento.numero_asiento,
            })
        return Response(lista)

    @swagger_auto_schema(
        operation_description="Guardar asiento",
        request_body=AsientoEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        bus_id = request.data.get("bus_id")
        numero_asiento = request.data.get("numero_asiento")

        Asiento.objects.create(
            bus_id=bus_id,
            numero_asiento=numero_asiento
        )
        return Response({"mensaje": "Asiento almacenado correctamente"})


class AsientoIdView(APIView):
    @swagger_auto_schema(
        operation_description="Listar asiento por id"
    )
    def get(self, request, id):
        registroEncontrado = Asiento.objects.get(id=id)
        return Response({
            "id": registroEncontrado.id,
            "bus_id": registroEncontrado.bus_id,
            "numero_asiento": registroEncontrado.numero_asiento,
        })

    @swagger_auto_schema(
        operation_description="Actualizar asiento",
        request_body=AsientoEntrada
    )
    def put(self, request, id):
        asientoB = Asiento.objects.get(id=id)
        asientoB.bus_id = request.data.get("bus_id")
        asientoB.numero_asiento = request.data.get("numero_asiento")
        asientoB.save()
        return Response({"mensaje": "Asiento actualizado"})

    @swagger_auto_schema(
        operation_description="Eliminar asiento"
    )
    def delete(self, request, id):
        asientoEliminar = Asiento.objects.get(id=id)
        asientoEliminar.delete()
        return Response({"mensaje": "Asiento eliminado"})


##################################################################################################
class DestinoView(APIView):
    @swagger_auto_schema(
        operation_description="Listar destinos"
    )
    def get(self, request):
        destinoLista = Destino.objects.all()
        lista = []
        for destino in destinoLista:
            lista.append({
                "id": destino.id,
                "nombre": destino.nombre,
                "departamento": destino.departamento,
                "descripcion": destino.descripcion,
            })
        return Response(lista)

    @swagger_auto_schema(
        operation_description="Guardar destino",
        request_body=DestinoEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        nombre = request.data.get("nombre")
        departamento = request.data.get("departamento")
        descripcion = request.data.get("descripcion")

        Destino.objects.create(
            nombre=nombre,
            departamento=departamento,
            descripcion=descripcion
        )
        return Response({"mensaje": "Destino almacenado correctamente"})


class DestinoIdView(APIView):
    @swagger_auto_schema(
        operation_description="Listar destino por id"
    )
    def get(self, request, id):
        registroEncontrado = Destino.objects.get(id=id)
        return Response({
            "id": registroEncontrado.id,
            "nombre": registroEncontrado.nombre,
            "departamento": registroEncontrado.departamento,
            "descripcion": registroEncontrado.descripcion,
        })

    @swagger_auto_schema(
        operation_description="Actualizar destino",
        request_body=DestinoEntrada
    )
    def put(self, request, id):
        destinoB = Destino.objects.get(id=id)
        destinoB.nombre = request.data.get("nombre")
        destinoB.departamento = request.data.get("departamento")
        destinoB.descripcion = request.data.get("descripcion")
        destinoB.save()
        return Response({"mensaje": "Destino actualizado"})

    @swagger_auto_schema(
        operation_description="Eliminar destino"
    )
    def delete(self, request, id):
        destinoEliminar = Destino.objects.get(id=id)
        destinoEliminar.delete()
        return Response({"mensaje": "Destino eliminado"})


##################################################################################################
class HospedajeView(APIView):
    @swagger_auto_schema(
        operation_description="Listar hospedajes"
    )
    def get(self, request):
        hospedajeLista = Hospedaje.objects.all()
        lista = []
        for hospedaje in hospedajeLista:
            lista.append({
                "id": hospedaje.id,
                "nombre": hospedaje.nombre,
                "destino_id": hospedaje.destino_id,
                "direccion": hospedaje.direccion,
                "telefono": hospedaje.telefono,
                "descripcion": hospedaje.descripcion,
            })
        return Response(lista)

    @swagger_auto_schema(
        operation_description="Guardar hospedaje",
        request_body=HopedajeEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        nombre = request.data.get("nombre")
        destino_id = request.data.get("destino_id")
        direccion = request.data.get("direccion")
        telefono = request.data.get("telefono")
        descripcion = request.data.get("descripcion")

        Hospedaje.objects.create(
            nombre=nombre,
            destino_id=destino_id,
            direccion=direccion,
            telefono=telefono,
            descripcion=descripcion
        )
        return Response({"mensaje": "Hospedaje almacenado correctamente"})


class HospedajeIdView(APIView):
    @swagger_auto_schema(
        operation_description="Listar hospedaje por id"
    )
    def get(self, request, id):
        registroEncontrado = Hospedaje.objects.get(id=id)
        return Response({
            "id": registroEncontrado.id,
            "nombre": registroEncontrado.nombre,
            "destino_id": registroEncontrado.destino_id,
            "direccion": registroEncontrado.direccion,
            "telefono": registroEncontrado.telefono,
            "descripcion": registroEncontrado.descripcion,
        })

    @swagger_auto_schema(
        operation_description="Actualizar hospedaje",
        request_body=HopedajeEntrada
    )
    def put(self, request, id):
        hospedajeB = Hospedaje.objects.get(id=id)
        hospedajeB.nombre = request.data.get("nombre")
        hospedajeB.destino_id = request.data.get("destino_id")
        hospedajeB.direccion = request.data.get("direccion")
        hospedajeB.telefono = request.data.get("telefono")
        hospedajeB.descripcion = request.data.get("descripcion")
        hospedajeB.save()
        return Response({"mensaje": "Hospedaje actualizado"})

    @swagger_auto_schema(
        operation_description="Eliminar hospedaje"
    )
    def delete(self, request, id):
        hospedajeEliminar = Hospedaje.objects.get(id=id)
        hospedajeEliminar.delete()
        return Response({"mensaje": "Hospedaje eliminado"})


##################################################################################################
class SitioTuristicoView(APIView):
    @swagger_auto_schema(
        operation_description="Listar sitios turisticos"
    )
    def get(self, request):
        sitioLista = SitioTuristico.objects.all()
        lista = []
        for sitio in sitioLista:
            lista.append({
                "id": sitio.id,
                "nombre": sitio.nombre,
                "destino_id": sitio.destino_id,
                "descripcion": sitio.descripcion,
                "recomendaciones": sitio.recomendaciones,
            })
        return Response(lista)

    @swagger_auto_schema(
        operation_description="Guardar sitio turistico",
        request_body=SitioTuristicoEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        nombre = request.data.get("nombre")
        destino_id = request.data.get("destino_id")
        descripcion = request.data.get("descripcion")
        recomendaciones = request.data.get("recomendaciones")

        SitioTuristico.objects.create(
            nombre=nombre,
            destino_id=destino_id,
            descripcion=descripcion,
            recomendaciones=recomendaciones
        )
        return Response({"mensaje": "Sitio turistico almacenado correctamente"})


class SitioTuristicoIdView(APIView):
    @swagger_auto_schema(
        operation_description="Listar sitio turistico por id"
    )
    def get(self, request, id):
        registroEncontrado = SitioTuristico.objects.get(id=id)
        return Response({
            "id": registroEncontrado.id,
            "nombre": registroEncontrado.nombre,
            "destino_id": registroEncontrado.destino_id,
            "descripcion": registroEncontrado.descripcion,
            "recomendaciones": registroEncontrado.recomendaciones,
        })

    @swagger_auto_schema(
        operation_description="Actualizar sitio turistico",
        request_body=SitioTuristicoEntrada
    )
    def put(self, request, id):
        sitioB = SitioTuristico.objects.get(id=id)
        sitioB.nombre = request.data.get("nombre")
        sitioB.destino_id = request.data.get("destino_id")
        sitioB.descripcion = request.data.get("descripcion")
        sitioB.recomendaciones = request.data.get("recomendaciones")
        sitioB.save()
        return Response({"mensaje": "Sitio turistico actualizado"})

    @swagger_auto_schema(
        operation_description="Eliminar sitio turistico"
    )
    def delete(self, request, id):
        sitioEliminar = SitioTuristico.objects.get(id=id)
        sitioEliminar.delete()
        return Response({"mensaje": "Sitio turistico eliminado"})


##################################################################################################
class ImagenView(APIView):
    @swagger_auto_schema(
        operation_description="Listar imagenes"
    )
    def get(self, request):
        imagenLista = ImagenDestino.objects.all()
        lista = []
        for imagen in imagenLista:
            lista.append({
                "id": imagen.id,
                "url_img": imagen.url_img.url if imagen.url_img else None,
                "destino_id": imagen.destino_id,
                "descripcion": imagen.descripcion,
            })
        return Response(lista)

    @swagger_auto_schema(
        operation_description="Guardar imagen",
        request_body=ImagenEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        url_img = request.data.get("url_img")
        destino_id = request.data.get("destino_id")
        descripcion = request.data.get("descripcion")

        ImagenDestino.objects.create(
            url_img=url_img,
            destino_id=destino_id,
            descripcion=descripcion
        )
        return Response({"mensaje": "Imagen almacenada correctamente"})


class ImagenIdView(APIView):
    @swagger_auto_schema(
        operation_description="Listar imagen por id"
    )
    def get(self, request, id):
        registroEncontrado = ImagenDestino.objects.get(id=id)
        return Response({
            "id": registroEncontrado.id,
            "url_img": registroEncontrado.url_img.url if registroEncontrado.url_img else None,
            "destino_id": registroEncontrado.destino_id,
            "descripcion": registroEncontrado.descripcion,
        })

    @swagger_auto_schema(
        operation_description="Actualizar imagen",
        request_body=ImagenEntrada
    )
    def put(self, request, id):
        imagenB = ImagenDestino.objects.get(id=id)
        if request.data.get("url_img"):
            imagenB.url_img = request.data.get("url_img")
        imagenB.destino_id = request.data.get("destino_id")
        imagenB.descripcion = request.data.get("descripcion")
        imagenB.save()
        return Response({"mensaje": "Imagen actualizada"})

    @swagger_auto_schema(
        operation_description="Eliminar imagen"
    )
    def delete(self, request, id):
        imagenEliminar = ImagenDestino.objects.get(id=id)
        imagenEliminar.delete()
        return Response({"mensaje": "Imagen eliminada"})


##################################################################################################
class PaqueteView(APIView):
    @swagger_auto_schema(
        operation_description="Listar paquetes"
    )
    def get(self, request):
        paqueteLista = Paquete.objects.all()
        lista = []
        for paquete in paqueteLista:
            lista.append({
                "id": paquete.id,
                "nombre": paquete.nombre,
                "agencia_id": paquete.agencia_id,
                "descripcion": paquete.descripcion,
                "duracion_estimada": paquete.duracion_estimada,
                "estado": paquete.estado,
                "fecha_creacion": paquete.fecha_creacion,
            })
        return Response(lista)

    @swagger_auto_schema(
        operation_description="Guardar paquete",
        request_body=PaqueteEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        nombre = request.data.get("nombre")
        agencia_id = request.data.get("agencia_id")
        descripcion = request.data.get("descripcion")
        duracion_estimada = request.data.get("duracion_estimada")
        estado = request.data.get("estado")
        fecha_creacion = request.data.get("fecha_creacion")

        Paquete.objects.create(
            nombre=nombre,
            agencia_id=agencia_id,
            descripcion=descripcion,
            duracion_estimada=duracion_estimada,
            estado=estado,
            fecha_creacion=fecha_creacion
        )
        return Response({"mensaje": "Paquete almacenado correctamente"})


class PaqueteIdView(APIView):
    @swagger_auto_schema(
        operation_description="Listar paquete por id"
    )
    def get(self, request, id):
        registroEncontrado = Paquete.objects.get(id=id)
        return Response({
            "id": registroEncontrado.id,
            "nombre": registroEncontrado.nombre,
            "agencia_id": registroEncontrado.agencia_id,
            "descripcion": registroEncontrado.descripcion,
            "duracion_estimada": registroEncontrado.duracion_estimada,
            "estado": registroEncontrado.estado,
            "fecha_creacion": registroEncontrado.fecha_creacion,
        })

    @swagger_auto_schema(
        operation_description="Actualizar paquete",
        request_body=PaqueteEntrada
    )
    def put(self, request, id):
        paqueteB = Paquete.objects.get(id=id)
        paqueteB.nombre = request.data.get("nombre")
        paqueteB.agencia_id = request.data.get("agencia_id")
        paqueteB.descripcion = request.data.get("descripcion")
        paqueteB.duracion_estimada = request.data.get("duracion_estimada")
        paqueteB.estado = request.data.get("estado")
        paqueteB.fecha_creacion = request.data.get("fecha_creacion")
        paqueteB.save()
        return Response({"mensaje": "Paquete actualizado"})

    @swagger_auto_schema(
        operation_description="Eliminar paquete"
    )
    def delete(self, request, id):
        paqueteEliminar = Paquete.objects.get(id=id)
        paqueteEliminar.delete()
        return Response({"mensaje": "Paquete eliminado"})


##################################################################################################
class PaqueteDestinoView(APIView):
    @swagger_auto_schema(
        operation_description="Listar relaciones paquete-destino"
    )
    def get(self, request):
        relLista = PaqueteDestino.objects.all()
        lista = []
        for rel in relLista:
            lista.append({
                "id": rel.id,
                "paquete_id": rel.paquete_id,
                "destino_id": rel.destino_id,
            })
        return Response(lista)

    @swagger_auto_schema(
        operation_description="Guardar relacion paquete-destino",
        request_body=PaqueteDestinoEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        paquete_id = request.data.get("paquete_id")
        destino_id = request.data.get("destino_id")

        PaqueteDestino.objects.create(
            paquete_id=paquete_id,
            destino_id=destino_id
        )
        return Response({"mensaje": "Relacion paquete-destino almacenada correctamente"})


class PaqueteDestinoIdView(APIView):
    @swagger_auto_schema(
        operation_description="Listar relacion paquete-destino por id"
    )
    def get(self, request, id):
        registroEncontrado = PaqueteDestino.objects.get(id=id)
        return Response({
            "id": registroEncontrado.id,
            "paquete_id": registroEncontrado.paquete_id,
            "destino_id": registroEncontrado.destino_id,
        })

    @swagger_auto_schema(
        operation_description="Actualizar relacion paquete-destino",
        request_body=PaqueteDestinoEntrada
    )
    def put(self, request, id):
        relB = PaqueteDestino.objects.get(id=id)
        relB.paquete_id = request.data.get("paquete_id")
        relB.destino_id = request.data.get("destino_id")
        relB.save()
        return Response({"mensaje": "Relacion paquete-destino actualizada"})

    @swagger_auto_schema(
        operation_description="Eliminar relacion paquete-destino"
    )
    def delete(self, request, id):
        relEliminar = PaqueteDestino.objects.get(id=id)
        relEliminar.delete()
        return Response({"mensaje": "Relacion paquete-destino eliminada"})


##################################################################################################
class ItinerarioView(APIView):
    @swagger_auto_schema(
        operation_description="Listar itinerarios"
    )
    def get(self, request):
        itinerarioLista = Itinerario.objects.all()
        lista = []
        for itinerario in itinerarioLista:
            lista.append({
                "id": itinerario.id,
                "titulo": itinerario.titulo,
                "paquete_id": itinerario.paquete_id,
                "dia": itinerario.dia,
                "descripcion": itinerario.descripcion,
                "hora": itinerario.hora,
                "lugar": itinerario.lugar,
            })
        return Response(lista)

    @swagger_auto_schema(
        operation_description="Guardar itinerario",
        request_body=ItinerarioEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        titulo = request.data.get("titulo")
        paquete_id = request.data.get("paquete_id")
        dia = request.data.get("dia")
        descripcion = request.data.get("descripcion")
        hora = request.data.get("hora")
        lugar = request.data.get("lugar")

        Itinerario.objects.create(
            titulo=titulo,
            paquete_id=paquete_id,
            dia=dia,
            descripcion=descripcion,
            hora=hora,
            lugar=lugar
        )
        return Response({"mensaje": "Itinerario almacenado correctamente"})


class ItinerarioIdView(APIView):
    @swagger_auto_schema(
        operation_description="Listar itinerario por id"
    )
    def get(self, request, id):
        registroEncontrado = Itinerario.objects.get(id=id)
        return Response({
            "id": registroEncontrado.id,
            "titulo": registroEncontrado.titulo,
            "paquete_id": registroEncontrado.paquete_id,
            "dia": registroEncontrado.dia,
            "descripcion": registroEncontrado.descripcion,
            "hora": registroEncontrado.hora,
            "lugar": registroEncontrado.lugar,
        })

    @swagger_auto_schema(
        operation_description="Actualizar itinerario",
        request_body=ItinerarioEntrada
    )
    def put(self, request, id):
        itinerarioB = Itinerario.objects.get(id=id)
        itinerarioB.titulo = request.data.get("titulo")
        itinerarioB.paquete_id = request.data.get("paquete_id")
        itinerarioB.dia = request.data.get("dia")
        itinerarioB.descripcion = request.data.get("descripcion")
        itinerarioB.hora = request.data.get("hora")
        itinerarioB.lugar = request.data.get("lugar")
        itinerarioB.save()
        return Response({"mensaje": "Itinerario actualizado"})

    @swagger_auto_schema(
        operation_description="Eliminar itinerario"
    )
    def delete(self, request, id):
        itinerarioEliminar = Itinerario.objects.get(id=id)
        itinerarioEliminar.delete()
        return Response({"mensaje": "Itinerario eliminado"})


##################################################################################################
class ReservaView(APIView):
    @swagger_auto_schema(
        operation_description="Listar reservas"
    )
    def get(self, request):
        reservaLista = Reserva.objects.all()
        lista = []
        for reserva in reservaLista:
            lista.append({
                "id": reserva.id,
                "fecha_reserva": reserva.fecha_reserva,
                "usuario_id": reserva.usuario_id,
                "paquete_id": reserva.paquete_id,
            })
        return Response(lista)

    @swagger_auto_schema(
        operation_description="Guardar reserva",
        request_body=ReservaEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        fecha_reserva = request.data.get("fecha_reserva")
        usuario_id = request.data.get("usuario_id")
        paquete_id = request.data.get("paquete_id")

        Reserva.objects.create(
            fecha_reserva=fecha_reserva,
            usuario_id=usuario_id,
            paquete_id=paquete_id
        )
        return Response({"mensaje": "Reserva almacenada correctamente"})


class ReservaIdView(APIView):
    @swagger_auto_schema(
        operation_description="Listar reserva por id"
    )
    def get(self, request, id):
        registroEncontrado = Reserva.objects.get(id=id)
        return Response({
            "id": registroEncontrado.id,
            "fecha_reserva": registroEncontrado.fecha_reserva,
            "usuario_id": registroEncontrado.usuario_id,
            "paquete_id": registroEncontrado.paquete_id,
        })

    @swagger_auto_schema(
        operation_description="Actualizar reserva",
        request_body=ReservaEntrada
    )
    def put(self, request, id):
        reservaB = Reserva.objects.get(id=id)
        reservaB.fecha_reserva = request.data.get("fecha_reserva")
        reservaB.usuario_id = request.data.get("usuario_id")
        reservaB.paquete_id = request.data.get("paquete_id")
        reservaB.save()
        return Response({"mensaje": "Reserva actualizada"})

    @swagger_auto_schema(
        operation_description="Eliminar reserva"
    )
    def delete(self, request, id):
        reservaEliminar = Reserva.objects.get(id=id)
        reservaEliminar.delete()
        return Response({"mensaje": "Reserva eliminada"})


##################################################################################################
class AsientoReservaView(APIView):
    @swagger_auto_schema(
        operation_description="Listar asientos reservados"
    )
    def get(self, request):
        asientoReservaLista = AsientoReserva.objects.all()
        lista = []
        for ar in asientoReservaLista:
            lista.append({
                "id": ar.id,
                "asiento_id": ar.asiento_id,
                "reserva_id": ar.reserva_id,
            })
        return Response(lista)

    @swagger_auto_schema(
        operation_description="Guardar asiento reservado",
        request_body=AsientoReservaEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        asiento_id = request.data.get("asiento_id")
        reserva_id = request.data.get("reserva_id")

        AsientoReserva.objects.create(
            asiento_id=asiento_id,
            reserva_id=reserva_id
        )
        return Response({"mensaje": "Asiento reservado correctamente"})


class AsientoReservaIdView(APIView):
    @swagger_auto_schema(
        operation_description="Listar asiento reservado por id"
    )
    def get(self, request, id):
        registroEncontrado = AsientoReserva.objects.get(id=id)
        return Response({
            "id": registroEncontrado.id,
            "asiento_id": registroEncontrado.asiento_id,
            "reserva_id": registroEncontrado.reserva_id,
        })

    @swagger_auto_schema(
        operation_description="Actualizar asiento reservado",
        request_body=AsientoReservaEntrada
    )
    def put(self, request, id):
        arB = AsientoReserva.objects.get(id=id)
        arB.asiento_id = request.data.get("asiento_id")
        arB.reserva_id = request.data.get("reserva_id")
        arB.save()
        return Response({"mensaje": "Asiento reservado actualizado"})

    @swagger_auto_schema(
        operation_description="Eliminar asiento reservado"
    )
    def delete(self, request, id):
        arEliminar = AsientoReserva.objects.get(id=id)
        arEliminar.delete()
        return Response({"mensaje": "Asiento reservado eliminado"})


##################################################################################################
class PagoView(APIView):
    @swagger_auto_schema(
        operation_description="Listar pagos"
    )
    def get(self, request):
        pagoLista = Pago.objects.all()
        lista = []
        for pago in pagoLista:
            lista.append({
                "id": pago.id,
                "precio": pago.precio,
                "reserva_id": pago.reserva_id,
                "fecha_pago": pago.fecha_pago,
                "referencia": pago.referencia,
                "comprobante": pago.comprobante.url if pago.comprobante else None,
                "estado": pago.estado,
                "motivo_rechazo": pago.motivo_rechazo,
            })
        return Response(lista)

    @swagger_auto_schema(
        operation_description="Guardar pago",
        request_body=PagoEntrada,
        responses={201: MensajeSalida}
    )
    def post(self, request):
        precio = request.data.get("precio")
        reserva_id = request.data.get("reserva_id")
        fecha_pago = request.data.get("fecha_pago")
        referencia = request.data.get("referencia")
        comprobante = request.data.get("comprobante")
        estado = request.data.get("estado")
        motivo_rechazo = request.data.get("motivo_rechazo")

        Pago.objects.create(
            precio=precio,
            reserva_id=reserva_id,
            fecha_pago=fecha_pago,
            referencia=referencia,
            comprobante=comprobante,
            estado=estado,
            motivo_rechazo=motivo_rechazo
        )
        return Response({"mensaje": "Pago almacenado correctamente"})


class PagoIdView(APIView):
    @swagger_auto_schema(
        operation_description="Listar pago por id"
    )
    def get(self, request, id):
        registroEncontrado = Pago.objects.get(id=id)
        return Response({
            "id": registroEncontrado.id,
            "precio": registroEncontrado.precio,
            "reserva_id": registroEncontrado.reserva_id,
            "fecha_pago": registroEncontrado.fecha_pago,
            "referencia": registroEncontrado.referencia,
            "comprobante": registroEncontrado.comprobante.url if registroEncontrado.comprobante else None,
            "estado": registroEncontrado.estado,
            "motivo_rechazo": registroEncontrado.motivo_rechazo,
        })

    @swagger_auto_schema(
        operation_description="Actualizar pago",
        request_body=PagoEntrada
    )
    def put(self, request, id):
        pagoB = Pago.objects.get(id=id)
        pagoB.precio = request.data.get("precio")
        pagoB.reserva_id = request.data.get("reserva_id")
        pagoB.fecha_pago = request.data.get("fecha_pago")
        pagoB.referencia = request.data.get("referencia")
        if request.data.get("comprobante"):
            pagoB.comprobante = request.data.get("comprobante")
        pagoB.estado = request.data.get("estado")
        pagoB.motivo_rechazo = request.data.get("motivo_rechazo")
        pagoB.save()
        return Response({"mensaje": "Pago actualizado"})

    @swagger_auto_schema(
        operation_description="Eliminar pago"
    )
    def delete(self, request, id):
        pagoEliminar = Pago.objects.get(id=id)
        pagoEliminar.delete()
        return Response({"mensaje": "Pago eliminado"})