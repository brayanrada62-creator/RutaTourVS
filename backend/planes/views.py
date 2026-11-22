from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import SAFE_METHODS
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from .serializers import PlanEntrada
from .models import Plan, PlanAgencias
from usuarios.models import Agencia
from usuarios.permisos import SesionVigente, es_super, usuario_activo


class PlanesPermiso(SesionVigente):
    """La landing lee sin token. Crear y editar solo el superadministrador."""

    message = "Solo el superadministrador puede modificar los planes"

    def has_permission(self, request, view):
        super().has_permission(request, view)
        if request.method in SAFE_METHODS:
            return True
        usuario = usuario_activo(request)
        if usuario is None:
            raise NotAuthenticated("Debes iniciar sesión")
        return es_super(usuario)


class PlanView(APIView):
    permission_classes = [PlanesPermiso]
    @swagger_auto_schema(request_body=PlanEntrada)
    def post(self, request):
        nombre = request.data.get('nombre')
        descripcion = request.data.get('descripcion')
        maximo_agencias = request.data.get('maximo_agencias')
        maximo_paquetes = request.data.get('maximo_paquetes')
        maximo_buses = request.data.get('maximo_buses')
        maximo_administradores = request.data.get('maximo_administradores')
        id_agencia = request.data.get('id_agencia')
        periodo = request.data.get('periodo')
        vencimiento = request.data.get('vencimiento')
        estado = request.data.get('estado')

        planNuevo = Plan.objects.create(
            nombre=nombre,
            descripcion=descripcion,
            maximo_agencias=maximo_agencias,
            maximo_paquetes=maximo_paquetes,
            maximo_buses=maximo_buses,
            maximo_administradores=maximo_administradores,
        )

        if id_agencia:
            if not periodo or not vencimiento:
                return Response({'message': 'periodo y vencimiento son obligatorios cuando envías id_agencia'}, status=400)
            agencia = Agencia.objects.get(id=id_agencia)
            PlanAgencias.objects.create(
                id_plan=planNuevo,
                id_agencia=agencia,
                periodo=periodo,
                vencimiento=vencimiento,
                estado=estado or 'activo',
            )

        return Response({'message': 'Plan creado exitosamente'})


    @swagger_auto_schema(request_body=PlanEntrada)
    def get(self, request):
        planes = Plan.objects.all()
        planes_data = []
        for plan in planes:
            plan_data = {
                'id': plan.id,
                'nombre': plan.nombre,
                'descripcion': plan.descripcion,
                'precio_mensual': plan.precio_de(1),
                'precio_trimestral': plan.precio_de(3),
                'precio_anual': plan.precio_de(12),
                'maximo_agencias': plan.maximo_agencias,
                'maximo_paquetes': plan.maximo_paquetes,
                'maximo_buses': plan.maximo_buses,
                'maximo_administradores': plan.maximo_administradores,
            }
            planes_data.append(plan_data)
        return Response(planes_data)
    

    @swagger_auto_schema(request_body=PlanEntrada)
    def put(self, request, id):
        plan = Plan.objects.get(id=id)
        plan.nombre = request.data.get('nombre')
        plan.descripcion = request.data.get('descripcion')
        plan.maximo_agencias = request.data.get('maximo_agencias')
        plan.maximo_paquetes = request.data.get('maximo_paquetes')
        plan.maximo_buses = request.data.get('maximo_buses')
        plan.maximo_administradores = request.data.get('maximo_administradores')
        plan.save()

        id_agencia = request.data.get('id_agencia')
        periodo = request.data.get('periodo')
        vencimiento = request.data.get('vencimiento')
        estado = request.data.get('estado')

        if id_agencia:
            if not periodo or not vencimiento:
                return Response({'message': 'periodo y vencimiento son obligatorios cuando envías id_agencia'}, status=400)
            agencia = Agencia.objects.get(id=id_agencia)
            # si ya existe el recibo lo actualiza, si no, lo crea
            PlanAgencias.objects.update_or_create(
                id_plan=plan,
                id_agencia=agencia,
                defaults={
                    'periodo': periodo,
                    'vencimiento': vencimiento,
                    'estado': estado or 'activo',
                },
            )

        return Response({'message': 'Plan actualizado exitosamente'})
