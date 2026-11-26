from django.db.utils import OperationalError, ProgrammingError
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import SAFE_METHODS
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from .serializers import PlanEntrada
from .models import NUMERO_WHATSAPP_INICIAL, ContactoLanding, Plan, PlanAgencias, PrecioPlanNoDisponible
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
        try:
            guardar_precios(planNuevo, request.data)
        except PrecioPlanNoDisponible as exc:
            return Response({'message': str(exc)}, status=400)

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
                'precio_mensual': plan.precio_vigente('mensual'),
                'precio_trimestral': plan.precio_vigente('trimestral'),
                'precio_anual': plan.precio_vigente('anual'),
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
        try:
            guardar_precios(plan, request.data)
        except PrecioPlanNoDisponible as exc:
            return Response({'message': str(exc)}, status=400)
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


def normalizar_whatsapp(valor):
    """Celular de Colombia: 10 dígitos que empiezan por 3. Acepta el 57 delante y lo quita."""
    digitos = "".join(caracter for caracter in str(valor or "") if caracter.isdigit())
    if len(digitos) == 12 and digitos.startswith("57"):
        digitos = digitos[2:]
    if len(digitos) == 10 and digitos.startswith("3"):
        return digitos
    return None


def whatsapp_guardado():
    """El número que abre el chat. Si la tabla aún no existe, se usa el inicial."""
    try:
        fila = ContactoLanding.objects.order_by("id").first()
    except (OperationalError, ProgrammingError):
        return NUMERO_WHATSAPP_INICIAL
    if fila is None or not fila.whatsapp.strip():
        return NUMERO_WHATSAPP_INICIAL
    return fila.whatsapp


class ContactoLandingView(APIView):
    """GET público para la landing. PUT solo el superadministrador."""

    permission_classes = [PlanesPermiso]

    def get(self, request):
        return Response({"whatsapp": whatsapp_guardado()})

    def put(self, request):
        numero = normalizar_whatsapp(request.data.get("whatsapp"))
        if numero is None:
            return Response(
                {"message": "Escribe un celular de 10 dígitos que empiece por 3."},
                status=400,
            )
        try:
            fila = ContactoLanding.objects.order_by("id").first()
            if fila is None:
                ContactoLanding.objects.create(whatsapp=numero)
            else:
                fila.whatsapp = numero
                fila.save(update_fields=["whatsapp"])
        except (OperationalError, ProgrammingError):
            return Response(
                {"message": "La tabla del WhatsApp todavía no está creada. Hay que migrar antes de guardar otro número."},
                status=503,
            )
        return Response({"whatsapp": numero})


def guardar_precios(plan, data):
    pares = (
        ('mensual', data.get('precio_mensual')),
        ('trimestral', data.get('precio_trimestral')),
        ('anual', data.get('precio_anual')),
    )
    for periodo, monto in pares:
        if monto is None or monto == '':
            continue
        plan.registrar_precio(periodo, monto)
