
import calendar
from datetime import date
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from .models import PlanAgencias

MESES = {'mensual': 1, 'trimestral': 3, 'anual': 12}


def fecha_colombia(momento=None):
    
    momento = momento or timezone.now()
    return timezone.localtime(momento, ZoneInfo('America/Bogota')).date()


def ids_agencias_vigentes(hoy=None):

    hoy = hoy or fecha_colombia()
    return PlanAgencias.objects.filter(estado='activo', vencimiento__gte=hoy).values_list('id_agencia_id', flat=True)


def agencia_puede_vender(agencia_id, hoy=None):
    hoy = hoy or fecha_colombia()
    if agencia_id is None:
        return False
    return PlanAgencias.objects.filter(
        id_agencia_id=agencia_id, estado='activo', vencimiento__gte=hoy,
    ).exists()


def sumar_meses(inicio, meses):
    mes0 = inicio.month - 1 + meses
    anio = inicio.year + mes0 // 12
    mes = mes0 % 12 + 1
    dia = min(inicio.day, calendar.monthrange(anio, mes)[1])
    return date(anio, mes, dia)


def activar_membresia(solicitud, hoy=None):
    hoy = hoy or fecha_colombia()
    meses = MESES[solicitud.periodo]
    with transaction.atomic():
        fila = (PlanAgencias.objects.select_for_update()
                .filter(id_agencia_id=solicitud.id_agencia_id)
                .order_by('-vencimiento', '-id')
                .first())
        inicio = hoy
        if fila is not None and fila.estado == 'activo' and fila.vencimiento >= hoy:
            inicio = fila.vencimiento
        fin = sumar_meses(inicio, meses)
        if fila is None:
            fila = PlanAgencias(id_agencia_id=solicitud.id_agencia_id)
        fila.id_plan = solicitud.id_plan
        fila.periodo = solicitud.periodo
        fila.inicia_el = inicio
        fila.vencimiento = fin
        fila.estado = 'activo'
        fila.save()
        (PlanAgencias.objects.filter(id_agencia_id=solicitud.id_agencia_id)
         .exclude(id=fila.id)
         .update(estado='inactivo'))
        solicitud.estado = 'aprobada'
        solicitud.motivo = ''
        solicitud.inicia_el = inicio
        solicitud.vencimiento = fin
        solicitud.save(update_fields=['estado', 'motivo', 'inicia_el', 'vencimiento'])
    return solicitud
