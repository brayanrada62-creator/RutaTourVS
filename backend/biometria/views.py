import json
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from pydantic import ValidationError
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.exceptions import WebAuthnException
from webauthn.helpers.structs import (
    AuthenticatorAttachment,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from usuarios.permisos import MENSAJE_AGENCIA_DESACTIVADA, agencia_desactivada, es_personal, usuario_de
from usuarios.views import emitir_sesion

from .models import CredencialBiometrica, RetoBiometrico

VIGENCIA = timedelta(minutes=2)
SOLO_ADMIN = "Solo administradores pueden ingresar."


def _error(mensaje, codigo):
    return Response({"message": mensaje, "mensaje": mensaje}, status=codigo)


def _opciones_dict(opciones):
    return json.loads(options_to_json(opciones))


def _guardar_reto(challenge, proposito, usuario=None):
    RetoBiometrico.limpiar_viejos()
    RetoBiometrico.objects.update_or_create(
        challenge=challenge,
        defaults={
            "usuario": usuario,
            "proposito": proposito,
            "expira": timezone.now() + VIGENCIA,
        },
    )


def _consumir_reto(credential, proposito):
    """Lee el reto que viaja dentro de la respuesta del navegador y lo borra (un solo uso)."""
    try:
        crudo = credential.get("response", {}).get("clientDataJSON")
        datos = json.loads(base64url_to_bytes(crudo))
        challenge = datos.get("challenge")
    except (TypeError, ValueError, AttributeError, KeyError):
        return None
    if not challenge:
        return None
    fila = RetoBiometrico.objects.filter(challenge=challenge, proposito=proposito).select_related("usuario").first()
    if fila is None:
        return None
    if fila.expira < timezone.now():
        fila.delete()
        return None
    usuario = fila.usuario
    fila.delete()
    return challenge, usuario


class RegistroOpciones(APIView):
    """El administrador ya entró con contraseña. Prepara el alta del equipo."""

    def post(self, request):
        usuario = usuario_de(request)
        if not es_personal(usuario):
            return _error("Solo administradores pueden activar este acceso.", status.HTTP_403_FORBIDDEN)

        existentes = [
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(fila.credential_id))
            for fila in usuario.credenciales_biometricas.all()
        ]
        opciones = generate_registration_options(
            rp_id=settings.WEBAUTHN_RP_ID,
            rp_name=settings.WEBAUTHN_RP_NAME,
            user_id=str(usuario.pk).encode(),
            user_name=usuario.correo,
            user_display_name=usuario.nombre_completo or usuario.correo,
            authenticator_selection=AuthenticatorSelectionCriteria(
                authenticator_attachment=AuthenticatorAttachment.PLATFORM,
                resident_key=ResidentKeyRequirement.PREFERRED,
                user_verification=UserVerificationRequirement.REQUIRED,
            ),
            exclude_credentials=existentes,
        )
        cuerpo = _opciones_dict(opciones)
        _guardar_reto(cuerpo["challenge"], "registro", usuario)
        return Response(cuerpo)


class RegistroVerificar(APIView):
    """Comprueba la firma del equipo y guarda la llave pública."""

    def post(self, request):
        usuario = usuario_de(request)
        if not es_personal(usuario):
            return _error("Solo administradores pueden activar este acceso.", status.HTTP_403_FORBIDDEN)

        tomado = _consumir_reto(request.data, "registro")
        if tomado is None or tomado[1] is None or tomado[1].pk != usuario.pk:
            return _error("La activación venció. Intenta de nuevo.", status.HTTP_400_BAD_REQUEST)
        challenge, _ = tomado

        try:
            verificado = verify_registration_response(
                credential=request.data,
                expected_challenge=base64url_to_bytes(challenge),
                expected_rp_id=settings.WEBAUTHN_RP_ID,
                expected_origin=settings.WEBAUTHN_ORIGINS,
                require_user_verification=True,
            )
        except (WebAuthnException, ValidationError, ValueError):
            return _error("No se pudo activar este equipo.", status.HTTP_400_BAD_REQUEST)

        CredencialBiometrica.objects.update_or_create(
            credential_id=bytes_to_base64url(verificado.credential_id),
            defaults={
                "usuario": usuario,
                "llave_publica": bytes_to_base64url(verificado.credential_public_key),
                "contador": verificado.sign_count,
            },
        )
        return Response({"message": "Equipo activado.", "mensaje": "Equipo activado."})


class LoginOpciones(APIView):
    """Reto para entrar sin contraseña. La ruta lleva /login/ y el panel no manda el token."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        opciones = generate_authentication_options(
            rp_id=settings.WEBAUTHN_RP_ID,
            user_verification=UserVerificationRequirement.REQUIRED,
            allow_credentials=[],
        )
        cuerpo = _opciones_dict(opciones)
        _guardar_reto(cuerpo["challenge"], "login")
        return Response(cuerpo)


class LoginVerificar(APIView):
    """Si la firma corresponde a una llave guardada, devuelve la misma sesión que /login/."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        tomado = _consumir_reto(request.data, "login")
        if tomado is None:
            return _error("La verificación venció. Intenta de nuevo.", status.HTTP_400_BAD_REQUEST)
        challenge, _ = tomado

        fila = (
            CredencialBiometrica.objects.select_related("usuario", "usuario__rol")
            .filter(credential_id=request.data.get("id"))
            .first()
        )
        if fila is None:
            return _error(
                "Este equipo no tiene acceso activado. Entra con tu contraseña y actívalo en el menú.",
                status.HTTP_401_UNAUTHORIZED,
            )

        usuario = fila.usuario
        if not es_personal(usuario):
            return _error(SOLO_ADMIN, status.HTTP_403_FORBIDDEN)
        if not usuario.activo:
            return _error("Usuario suspendido. Comunícate con tu agencia", status.HTTP_403_FORBIDDEN)
        if agencia_desactivada(usuario):
            return _error(MENSAJE_AGENCIA_DESACTIVADA, status.HTTP_403_FORBIDDEN)

        try:
            verificado = verify_authentication_response(
                credential=request.data,
                expected_challenge=base64url_to_bytes(challenge),
                expected_rp_id=settings.WEBAUTHN_RP_ID,
                expected_origin=settings.WEBAUTHN_ORIGINS,
                credential_public_key=base64url_to_bytes(fila.llave_publica),
                credential_current_sign_count=fila.contador,
                require_user_verification=True,
            )
        except (WebAuthnException, ValidationError, ValueError):
            return _error("No se pudo verificar este equipo.", status.HTTP_401_UNAUTHORIZED)

        fila.contador = verificado.new_sign_count
        fila.save(update_fields=["contador"])
        return Response(emitir_sesion(usuario))
