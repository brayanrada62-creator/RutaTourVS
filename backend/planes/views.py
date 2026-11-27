from django.db.utils import OperationalError, ProgrammingError
from rest_framework.exceptions import NotAuthenticated
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import SAFE_METHODS
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from destinos.imagenes import imagen_url, validar_foto
from notificaciones.eventos import notificar_comprobante_plan, notificar_resultado_plan
from .serializers import PlanEntrada
from .models import NUMERO_WHATSAPP_INICIAL, ContactoLanding, Plan, PlanAgencias, PrecioPlanNoDisponible, SolicitudPlan
from .vigencia import activar_membresia
from usuarios.models import Agencia
from usuarios.permisos import (
    SesionVigente, agencia_para_guardar, agencias_de, es_admin, es_super, prohibido, usuario_activo, usuario_de,
)


class PlanesPermiso(SesionVigente):

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
    digitos = "".join(caracter for caracter in str(valor or "") if caracter.isdigit())
    if len(digitos) == 12 and digitos.startswith("57"):
        digitos = digitos[2:]
    if len(digitos) == 10 and digitos.startswith("3"):
        return digitos
    return None


def whatsapp_guardado():
    try:
        fila = ContactoLanding.objects.order_by("id").first()
    except (OperationalError, ProgrammingError):
        return NUMERO_WHATSAPP_INICIAL
    if fila is None or not fila.whatsapp.strip():
        return NUMERO_WHATSAPP_INICIAL
    return fila.whatsapp


class ContactoLandingView(APIView):

    permission_classes = [PlanesPermiso]

    def get(self, request):
        return Response({"whatsapp": whatsapp_guardado()})

    def put(self, request):
        numero = normalizar_whatsapp(request.data.get("whatsapp"))
        if numero is None:
            return Response(
                {"message": "Escribe un celular de 10 dígitos que empiece por 3."},
            
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
                
            )
        return Response({"whatsapp": numero})


ESTADOS_PARA_EL_PANEL = {
    'pendiente': 'validando',
    'aprobada': 'aprobado',
    'rechazada': 'rechazado',
}


def solicitud_json(solicitud, request):
    comprobante = imagen_url(solicitud.comprobante, request)
    return {
        'id': solicitud.id,
        'agenciaId': str(solicitud.id_agencia_id),
        'agencia': solicitud.id_agencia.nombre,
        'planId': solicitud.id_plan_id,
        'planNombre': solicitud.id_plan.nombre,
        'planDescripcion': solicitud.id_plan.descripcion,
        'periodo': solicitud.periodo,
        'precio': int(solicitud.precio),
        'comprobante': comprobante or '',
        'archivo': solicitud.comprobante.name.rsplit('/', 1)[-1] if solicitud.comprobante else '',
        'estado': ESTADOS_PARA_EL_PANEL.get(solicitud.estado, solicitud.estado),
        'motivo': solicitud.motivo,
        'creadaEn': solicitud.fecha_solicitud.isoformat(),
        'iniciaEl': solicitud.inicia_el.isoformat() if solicitud.inicia_el else None,
        'venceEl': solicitud.vencimiento.isoformat() if solicitud.vencimiento else None,
    }


class SolicitudPlanView(APIView):
    """El administrador envía el comprobante. El superadministrador lista todas."""

    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        yo = usuario_de(request)
        if es_super(yo):
            lista = SolicitudPlan.objects.all()
        elif es_admin(yo):
            lista = SolicitudPlan.objects.filter(id_agencia_id__in=agencias_de(yo))
        else:
            return prohibido('No puedes ver estos comprobantes')
        lista = lista.select_related('id_agencia', 'id_plan').order_by('-id')
        return Response([solicitud_json(solicitud, request) for solicitud in lista])

    def post(self, request):
        yo = usuario_de(request)
        if not es_admin(yo):
            return prohibido('Solo el administrador de la agencia envía el comprobante')
        agencia_id, error = agencia_para_guardar(yo, request.data.get('agencia_id') or request.data.get('id_agencia'))
        if error:
            return Response({'message': error[1]}, status=error[0])
        plan = Plan.objects.filter(id=request.data.get('plan_id') or request.data.get('id_plan')).first()
        periodo = request.data.get('periodo')
        if plan is None:
            return Response({'message': 'El plan no existe'}, status=status.HTTP_400_BAD_REQUEST)
        if periodo not in dict(SolicitudPlan.PERIODOS):
            return Response({'message': 'El periodo debe ser mensual, trimestral o anual'}, status=status.HTTP_400_BAD_REQUEST)
        archivo = request.FILES.get('comprobante')
        if archivo is None:
            return Response({'message': 'Adjunta la foto del comprobante'}, status=status.HTTP_400_BAD_REQUEST)
        error_foto = validar_foto(archivo, 'El comprobante')
        if error_foto:
            return Response({'message': error_foto}, status=status.HTTP_400_BAD_REQUEST)
        if SolicitudPlan.objects.filter(id_agencia_id=agencia_id, estado='pendiente').exists():
            return Response({'message': 'Ya hay un comprobante en revisión'}, status=status.HTTP_400_BAD_REQUEST)
        solicitud = SolicitudPlan.objects.create(
            id_agencia_id=agencia_id,
            id_plan=plan,
            periodo=periodo,
            precio=plan.precio_vigente(periodo),
            comprobante=archivo,
        )
        notificar_comprobante_plan(solicitud)
        return Response(solicitud_json(solicitud, request), status=status.HTTP_201_CREATED)


class SolicitudPlanResolverView(APIView):
    """Aprueba o rechaza un comprobante. Aprobar renueva PlanAgencias en la misma transacción."""

    def post(self, request, id, accion):
        yo = usuario_de(request)
        if not es_super(yo):
            return prohibido('Solo el superadministrador aprueba o rechaza comprobantes')
        solicitud = SolicitudPlan.objects.select_related('id_agencia', 'id_plan').filter(id=id).first()
        if solicitud is None:
            return Response({'message': 'El comprobante no existe'}, status=status.HTTP_404_NOT_FOUND)
        if solicitud.estado != 'pendiente':
            return Response({'message': 'Ese comprobante ya fue revisado'}, status=status.HTTP_400_BAD_REQUEST)
        if accion == 'aprobar':
            activar_membresia(solicitud)
        elif accion == 'rechazar':
            motivo = str(request.data.get('motivo') or '').strip()
            if not motivo:
                return Response({'message': 'Escribe el motivo del rechazo'}, status=status.HTTP_400_BAD_REQUEST)
            solicitud.estado = 'rechazada'
            solicitud.motivo = motivo[:255]
            solicitud.save(update_fields=['estado', 'motivo'])
        else:
            return Response({'message': 'Acción no válida'}, status=status.HTTP_404_NOT_FOUND)
        solicitud.refresh_from_db()
        notificar_resultado_plan(solicitud)
        return Response(solicitud_json(solicitud, request))


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
