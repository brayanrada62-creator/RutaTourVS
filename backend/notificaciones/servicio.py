"""Servicio central de notificaciones. Todo aviso del sistema pasa por `notificar`."""
from usuarios.permisos import ROL_ADMIN, ROL_CLIENTE, ROL_CONDUCTOR

from . import fcm, ws
from .models import DispositivoFCM, Notificacion, PreferenciaNotificacion, Tipo

# Tipos que puede recibir cada rol: define qué interruptores ve cada usuario en preferencias.
TIPOS_POR_ROL = {
    ROL_CLIENTE: [Tipo.PAGO_APROBADO],
    ROL_CONDUCTOR: [Tipo.CAMBIO_VIAJE],
    ROL_ADMIN: [Tipo.NOVEDAD_INCIDENTE],
}

# Tipo de recurso al que apunta cada notificación.
REFERENCIA_POR_TIPO = {
    Tipo.PAGO_APROBADO: "compra",
    Tipo.CAMBIO_VIAJE: "viaje",
    Tipo.NOVEDAD_INCIDENTE: "novedad",
}


def tipos_del_usuario(usuario):
    return [str(t) for t in TIPOS_POR_ROL.get(usuario.rol_id, [])]


def tipo_activo(usuario, tipo):
    """Sin fila de preferencia, el tipo está activo (por defecto todo se recibe)."""
    pref = PreferenciaNotificacion.objects.filter(usuario=usuario, tipo=tipo).first()
    return pref is None or pref.activa


def datos_push(n):
    return {
        "notificacion_id": n.id,
        "tipo": n.tipo,
        "referencia_id": n.referencia_id if n.referencia_id is not None else "",
        "referencia_tipo": n.referencia_tipo,
    }


def notificacion_json(n):
    return {
        "id": n.id,
        "tipo": n.tipo,
        "titulo": n.titulo,
        "mensaje": n.mensaje,
        "fecha_creacion": n.fecha_creacion.isoformat(),
        "leida": n.leida,
        "referencia_id": n.referencia_id,
        "referencia_tipo": n.referencia_tipo,
        "datos": n.datos,
    }


def notificar(destinatario, tipo, titulo, mensaje, referencia_id=None, referencia_tipo=None, datos=None):
    """Crea la notificación y la entrega. Devuelve la Notificacion, o None si el destinatario desactivó el tipo.

    Supuesto documentado (HU-M-51.2): con el tipo desactivado NO se guarda, NO se envía push y NO se emite
    por WebSocket. Quien lo desactiva no verá ese aviso ni en su historial.
    También se descarta si el tipo no corresponde al rol del destinatario (defensa en profundidad)."""
    if destinatario is None or not destinatario.activo:
        return None
    if str(tipo) not in tipos_del_usuario(destinatario):
        return None
    if not tipo_activo(destinatario, tipo):
        return None
    n = Notificacion.objects.create(
        destinatario=destinatario, tipo=tipo, titulo=titulo[:150], mensaje=mensaje[:500],
        referencia_id=referencia_id, referencia_tipo=referencia_tipo or REFERENCIA_POR_TIPO.get(tipo, ""),
        datos=datos,
    )
    tokens = list(DispositivoFCM.objects.filter(usuario=destinatario).values_list("token", flat=True))
    invalidos = fcm.enviar_push(tokens, n.titulo, n.mensaje, datos_push(n))
    if invalidos:
        DispositivoFCM.objects.filter(token__in=invalidos).delete()
    if destinatario.rol_id == ROL_ADMIN:
        ws.emitir(destinatario.id, {**notificacion_json(n), "fecha": n.fecha_creacion.isoformat()})
    return n
