from django.test import TestCase
from rest_framework.test import APIRequestFactory

from .models import Agencia, Rol, Usuario, UsuarioAgencia
from .views import UsuarioView


class UsuarioViewTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.rol = Rol.objects.create(rol='Administrador')
        self.agencia = Agencia.objects.create(
            nombre='Agencia de prueba',
            nit='900123456',
            direccion='Calle 1',
            telefono='3001234567',
            correo='agencia@example.com',
        )
        self.payload = {
            'nombre_completo': 'Usuario de prueba',
            'rol_id': self.rol.id,
            'tipo_documento': 'CC',
            'numero_documento': '123456789',
            'correo': 'usuario@example.com',
            'telefono': '3007654321',
            'contrasena': 'secreto',
        }

    def post_usuario(self, payload):
        request = self.factory.post('/usuario/', payload, format='json')
        return UsuarioView.as_view()(request)

    def test_post_creates_usuario_and_agency_association(self):
        response = self.post_usuario({
            **self.payload,
            'agencia_id': self.agencia.id,
        })

        self.assertEqual(response.status_code, 200)
        usuario = Usuario.objects.get(numero_documento=self.payload['numero_documento'])
        self.assertTrue(
            UsuarioAgencia.objects.filter(
                usuario=usuario,
                agencia=self.agencia,
            ).exists()
        )

    def test_post_without_agency_creates_usuario_without_association(self):
        response = self.post_usuario(self.payload)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Usuario.objects.filter(numero_documento=self.payload['numero_documento']).exists()
        )
        self.assertFalse(UsuarioAgencia.objects.exists())

    def test_post_with_unknown_agency_returns_validation_error(self):
        response = self.post_usuario({
            **self.payload,
            'agencia_id': self.agencia.id + 1,
        })

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Usuario.objects.exists())
