from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_yasg.utils import swagger_auto_schema

from usuarios.paginacion import paginar
from usuarios.permisos import usuario_de

from .models import DispositivoFCM, Notificacion, PreferenciaNotificacion
from .servicio import notificacion_json, tipo_activo, tipos_del_usuario

# Todas las vistas filtran por el usuario del token: nadie ve ni toca avisos ajenos.


class NotificacionView(APIView):
    @swagger_auto_schema(operation_description="Mis notificaciones, de la más reciente a la más antigua. ?page=&page_size= pagina "
                                               "({count, results}); ?leida=false solo las no leídas.")
    def get(self, request):
        lista = Notificacion.objects.filter(destinatario=usuario_de(request))
        if request.query_params.get("leida") in ("false", "0"):
            lista = lista.filter(leida=False)
        return Response(paginar(request, lista.order_by("-fecha_creacion", "-id"), notificacion_json))


class NotificacionIdView(APIView):
    @swagger_auto_schema(operation_description="Detalle de una notificación mía (404 si no es mía)")
    def get(self, request, id):
        return Response(notificacion_json(get_object_or_404(Notificacion, id=id, destinatario=usuario_de(request))))


class NotificacionLeidaView(APIView):
    @swagger_auto_schema(operation_description="Marcar como leída una notificación mía")
    def patch(self, request, id):
        n = get_object_or_404(Notificacion, id=id, destinatario=usuario_de(request))
        if not n.leida:
            n.leida = True
            n.save(update_fields=["leida"])
        return Response(notificacion_json(n))


class NotificacionNoLeidasView(APIView):
    @swagger_auto_schema(operation_description="Cantidad de notificaciones no leídas (para el badge)")
    def get(self, request):
        return Response({"count": Notificacion.objects.filter(destinatario=usuario_de(request), leida=False).count()})


class PreferenciaView(APIView):
    @swagger_auto_schema(operation_description="Tipos de notificación aplicables a mi rol, con su estado activa/inactiva")
    def get(self, request):
        return Response(self._lista(usuario_de(request)))

    @swagger_auto_schema(operation_description="Guardar preferencias. Cuerpo: [{\"tipo\": \"PAGO_APROBADO\", \"activa\": false}]. "
                                               "Un tipo que no corresponde a mi rol da 400. Con un tipo desactivado no llegan "
                                               "ni se guardan esos avisos.")
    def put(self, request):
        yo = usuario_de(request)
        cuerpo = request.data
        if isinstance(cuerpo, dict):
            cuerpo = cuerpo.get("preferencias")
        if not isinstance(cuerpo, list):
            return Response({"message": "Envía una lista de {tipo, activa}"}, status=status.HTTP_400_BAD_REQUEST)
        validos = set(tipos_del_usuario(yo))
        cambios = {}
        for item in cuerpo:
            if not isinstance(item, dict) or item.get("tipo") not in validos or not isinstance(item.get("activa"), bool):
                return Response({"message": "Tipo no válido para tu rol o 'activa' no es booleano"},
                                status=status.HTTP_400_BAD_REQUEST)
            cambios[item["tipo"]] = item["activa"]
        with transaction.atomic():
            for tipo, activa in cambios.items():
                PreferenciaNotificacion.objects.update_or_create(usuario=yo, tipo=tipo, defaults={"activa": activa})
        return Response(self._lista(yo))

    @staticmethod
    def _lista(usuario):
        from .models import Tipo
        etiquetas = dict(Tipo.choices)
        return [{"tipo": t, "nombre": etiquetas[t], "activa": tipo_activo(usuario, t)} for t in tipos_del_usuario(usuario)]


class DispositivoView(APIView):
    @swagger_auto_schema(operation_description="Registrar o actualizar el token FCM de este teléfono. Cuerpo: {token, plataforma}. "
                                               "Si el token ya existía (otro usuario en el mismo teléfono), pasa a ser de quien llama.")
    def post(self, request):
        token = (request.data.get("token") or "").strip()
        if not token or len(token) > 255:
            return Response({"message": "Falta el token del dispositivo"}, status=status.HTTP_400_BAD_REQUEST)
        plataforma = (request.data.get("plataforma") or "android")[:20]
        DispositivoFCM.objects.update_or_create(token=token, defaults={"usuario": usuario_de(request), "plataforma": plataforma})
        return Response({"mensaje": "Dispositivo registrado"})

    @swagger_auto_schema(operation_description="Quitar el token FCM de este teléfono (al cerrar sesión). Solo borra los tokens míos.")
    def delete(self, request):
        token = (request.data.get("token") or "").strip()
        DispositivoFCM.objects.filter(usuario=usuario_de(request), token=token).delete()
        return Response({"mensaje": "Dispositivo eliminado"})
