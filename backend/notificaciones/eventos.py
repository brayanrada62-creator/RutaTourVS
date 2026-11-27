"""Reglas de negocio de qué se notifica y a quién. Las llaman las vistas en el punto exacto del flujo.

El alcance (agencia, conductor asignado, cliente dueño) se decide aquí, en el servidor; las apps solo leen.
"""
import functools
import logging

from .models import Tipo
from .servicio import notificar

logger = logging.getLogger(__name__)


def sin_romper_el_flujo(funcion):
    """Un fallo al notificar (BD, FCM, WebSocket...) nunca debe deshacer ni romper la operación de negocio
    que lo originó (aprobar un pago, editar un viaje, guardar una novedad): se registra y se sigue."""
    @functools.wraps(funcion)
    def envuelta(*args, **kwargs):
        try:
            return funcion(*args, **kwargs)
        except Exception:  # noqa: BLE001
            logger.exception("No se pudo notificar (%s)", funcion.__name__)
            return None
    return envuelta


def conductores_del_viaje(viaje):
    """Conductores asignados al bus del viaje (el viaje hereda el conductor del bus: Bus_Conductor)."""
    from buses.models import Bus_Conductor
    return [bc.conductor for bc in Bus_Conductor.objects.filter(bus_id=viaje.bus_id).select_related("conductor")]


def administradores_de_agencia(agencia_id):
    """Solo los administradores (rol 2) de esa agencia. Nunca los de otras agencias."""
    from usuarios.models import UsuarioAgencia
    from usuarios.permisos import ROL_ADMIN
    return [
        ua.usuario for ua in UsuarioAgencia.objects.filter(agencia_id=agencia_id, usuario__rol_id=ROL_ADMIN).select_related("usuario")
    ]


@sin_romper_el_flujo
def notificar_comprobante_plan(solicitud):
    from usuarios.models import Usuario
    from usuarios.permisos import ROL_SUPER

    for superadmin in Usuario.objects.filter(rol_id=ROL_SUPER, activo=True):
        notificar(
            superadmin, Tipo.COMPROBANTE_PLAN, "Nuevo comprobante de membresía",
            f"{solicitud.id_agencia.nombre} envió un comprobante para el plan {solicitud.id_plan.nombre}.",
            referencia_id=solicitud.id,
        )


@sin_romper_el_flujo
def notificar_resultado_plan(solicitud):
    """Avisa a los administradores de esa agencia cuando el super aprueba o rechaza el comprobante."""
    aprobada = solicitud.estado == "aprobada"
    tipo = Tipo.COMPROBANTE_PLAN_APROBADO if aprobada else Tipo.COMPROBANTE_PLAN_RECHAZADO
    if aprobada:
        hasta = solicitud.vencimiento.isoformat() if solicitud.vencimiento else ""
        titulo = "Membresía aprobada"
        mensaje = f"El comprobante del plan {solicitud.id_plan.nombre} fue aprobado. Queda vigente hasta {hasta}."
    else:
        titulo = "Membresía rechazada"
        motivo = solicitud.motivo or "Sin motivo"
        mensaje = f"El comprobante del plan {solicitud.id_plan.nombre} fue rechazado. Motivo: {motivo}."
    for admin in administradores_de_agencia(solicitud.id_agencia_id):
        notificar(admin, tipo, titulo, mensaje, referencia_id=solicitud.id)


@sin_romper_el_flujo
def notificar_pago_pendiente(pago):
    """Avisa a la agencia cuando un cliente envía un comprobante nuevo."""
    reserva = pago.reserva
    for admin in administradores_de_agencia(reserva.paquete.agencia_id):
        notificar(
            admin, Tipo.PAGO_PENDIENTE, "Nuevo comprobante pendiente de revisión",
            f"Hay un comprobante para la reserva #{reserva.id} de {reserva.paquete.nombre}.",
            referencia_id=pago.id, datos={"reserva_id": reserva.id},
        )


@sin_romper_el_flujo
def notificar_pago_aprobado(pago):
    """HU-M-11: al cliente dueño de la reserva. Se llama solo cuando el estado pasa a aprobado (no con rechazado)."""
    reserva = pago.reserva
    notificar(
        reserva.usuario, Tipo.PAGO_APROBADO, "Pago aprobado",
        f"Tu pago de {reserva.paquete.nombre} fue aprobado. Tu compra está confirmada y ya puedes ver tu tiquete con el QR.",
        referencia_id=reserva.id, datos={"pago_id": pago.id, "paquete": reserva.paquete.nombre},
    )


@sin_romper_el_flujo
def notificar_cambio_viaje(viaje, cambios):
    """HU-M-53: a los conductores asignados a ese viaje. `cambios` = campos relevantes que cambiaron (fecha, hora, paradas)."""
    if not cambios:
        return
    resumen = ", ".join(cambios)
    for conductor in conductores_del_viaje(viaje):
        notificar(
            conductor, Tipo.CAMBIO_VIAJE, "Cambió un viaje asignado",
            f"El viaje de {viaje.paquete.nombre} tiene cambios en: {resumen}. Salida: {viaje.fecha.isoformat()} {viaje.hora.strftime('%H:%M')}.",
            referencia_id=viaje.id, datos={"cambios": list(cambios)},
        )


@sin_romper_el_flujo
def notificar_cambio_paradas(paquete_id):
    """Las paradas (itinerario) son del paquete: avisa a los conductores de sus viajes que aún no terminaron."""
    from buses.models import Viaje
    for viaje in Viaje.objects.filter(paquete_id=paquete_id).exclude(estado=Viaje.COMPLETADO).select_related("paquete", "bus"):
        notificar_cambio_viaje(viaje, ["paradas"])


@sin_romper_el_flujo
def notificar_novedad(novedad, conductor):
    """HU-W-46: solo a los administradores de la agencia de la novedad (paquete o bus del viaje) del conductor
    que reportó. Nunca a administradores de otras agencias."""
    from reservas.views import agencia_de_novedad
    agencia_id = agencia_de_novedad(novedad)
    if agencia_id is None:
        return
    paquete = novedad.paquete or (novedad.viaje.paquete if novedad.viaje_id else None)
    donde = f" en {paquete.nombre}" if paquete else ""
    for admin in administradores_de_agencia(agencia_id):
        notificar(
            admin, Tipo.NOVEDAD_INCIDENTE, f"Novedad: {novedad.tipo}",
            f"{conductor.nombre_completo} reportó{donde}: {novedad.detalle[:200]}",
            referencia_id=novedad.id,
            datos={"viaje_id": novedad.viaje_id, "conductor": conductor.nombre_completo},
        )
