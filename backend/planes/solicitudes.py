from calendar import monthrange

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from destinos.imagenes import imagen_url, validar_foto
from notificaciones.eventos import notificar_comprobante_plan
from usuarios.models import Agencia
from usuarios.permisos import agencia_para_guardar, agencias_de, es_admin, es_super, prohibido, usuario_activo

from .models import Plan, SolicitudPlan


MESES = {"mensual": 1, "trimestral": 3, "anual": 12}
ESTADOS_WEB = {"pendiente": "validando", "aprobada": "aprobado", "rechazada": "rechazado"}


def solicitud_json(solicitud, request):
    return {
        "id": str(solicitud.id),
        "agenciaId": str(solicitud.id_agencia_id),
        "agencia": solicitud.id_agencia.nombre,
        "planId": solicitud.id_plan_id,
        "planNombre": solicitud.id_plan.nombre,
        "planDescripcion": solicitud.id_plan.descripcion,
        "periodo": solicitud.periodo,
        "precio": float(solicitud.precio),
        "comprobante": imagen_url(solicitud.comprobante, request),
        "archivo": "",
        "estado": ESTADOS_WEB[solicitud.estado],
        "motivo": solicitud.motivo,
        "creadaEn": solicitud.fecha_solicitud,
        "iniciaEl": solicitud.inicia_el,
        "venceEl": solicitud.vence_el,
    }


class SolicitudesPlanView(APIView):
    def get(self, request):
        usuario = usuario_activo(request)
        solicitudes = SolicitudPlan.objects.exclude(comprobante="").select_related("id_agencia", "id_plan")
        if es_admin(usuario):
            solicitudes = solicitudes.filter(id_agencia_id__in=agencias_de(usuario))
        elif not es_super(usuario):
            return prohibido()
        return Response([solicitud_json(s, request) for s in solicitudes.order_by("-id")])

    def post(self, request):
        usuario = usuario_activo(request)
        if not es_admin(usuario):
            return prohibido()
        agencia_id, error = agencia_para_guardar(usuario, request.data.get("agencia_id"))
        if error:
            return Response({"message": error[1]}, status=error[0])
        agencia = get_object_or_404(Agencia, pk=agencia_id, activo=True)
        periodo = str(request.data.get("periodo", ""))
        plan_id = str(request.data.get("plan_id", ""))
        if periodo not in MESES or not plan_id.isascii() or not plan_id.isdecimal():
            return Response({"message": "Elige un plan y un periodo válidos"}, status=400)
        plan = get_object_or_404(Plan, pk=plan_id)
        if plan.nombre not in Plan.PRECIOS:
            return Response({"message": "El plan no tiene un precio configurado"}, status=400)
        foto = request.FILES.get("comprobante")
        error = validar_foto(foto, "El comprobante") if foto else "Adjunta la foto del comprobante"
        if error:
            return Response({"message": error}, status=400)

        with transaction.atomic():
            get_object_or_404(Agencia.objects.select_for_update(), pk=agencia.id, activo=True)
            if SolicitudPlan.objects.filter(id_agencia=agencia, estado="pendiente").exclude(comprobante="").exists():
                return Response({"message": "Tu agencia ya tiene un comprobante en revisión"}, status=409)
            solicitud = SolicitudPlan.objects.create(
                id_agencia=agencia, id_plan=plan, periodo=periodo, precio=plan.precio_de(MESES[periodo]),
                comprobante=foto,
            )
            transaction.on_commit(lambda: notificar_comprobante_plan(solicitud))
        return Response(solicitud_json(solicitud, request), status=201)


class RevisarSolicitudPlanView(APIView):
    def patch(self, request, id):
        if not es_super(usuario_activo(request)):
            return prohibido()
        estado = request.data.get("estado")
        motivo = str(request.data.get("motivo") or "").strip()
        if estado not in ("aprobado", "rechazado") or (estado == "rechazado" and not 0 < len(motivo) <= 255):
            return Response({"message": "Indica una decisión válida y el motivo si rechazas"}, status=400)
        with transaction.atomic():
            solicitud = get_object_or_404(SolicitudPlan.objects.select_for_update().exclude(comprobante=""), pk=id)
            if solicitud.estado != "pendiente":
                return Response({"message": "Este comprobante ya fue revisado"}, status=409)
            if estado == "aprobado":
                hoy = timezone.localdate()
                anio, mes = divmod(hoy.year * 12 + hoy.month - 1 + MESES[solicitud.periodo], 12)
                solicitud.estado = "aprobada"
                solicitud.inicia_el = hoy
                solicitud.vence_el = hoy.replace(year=anio, month=mes + 1, day=min(hoy.day, monthrange(anio, mes + 1)[1]))
            else:
                solicitud.estado = "rechazada"
                solicitud.motivo = motivo
            solicitud.save(update_fields=["estado", "motivo", "inicia_el", "vence_el"])
        return Response(solicitud_json(solicitud, request))
