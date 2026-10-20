from django.test import TestCase
from rest_framework.test import APIRequestFactory

from .models import Agencia, Rol, Usuario, UsuarioAgencia
from .views import UsuarioAgenciaView, UsuarioView


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

    def test_post_creates_usuario_without_agency_field(self):
        response = self.post_usuario(self.payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['message'], 'Usuario creado exitosamente')
        self.assertTrue(Usuario.objects.filter(
            numero_documento=self.payload['numero_documento']
        ).exists())
        self.assertFalse(UsuarioAgencia.objects.exists())

    def test_post_with_agencia_id_creates_association(self):
        payload = dict(self.payload)
        payload['agencia_id'] = self.agencia.id
        response = self.post_usuario(payload)

        self.assertEqual(response.status_code, 200)
        usuario = Usuario.objects.get(numero_documento=self.payload['numero_documento'])
        self.assertTrue(UsuarioAgencia.objects.filter(
            usuario=usuario,
            agencia=self.agencia,
        ).exists())

        request = self.factory.get('/usuario/')
        lista = UsuarioView.as_view()(request)
        self.assertEqual(lista.data[0]['agencia_id'], self.agencia.id)
        self.assertEqual(lista.data[0]['agencia_ids'], [self.agencia.id])

    def test_association_endpoint_links_existing_user_and_agency(self):
        self.post_usuario(self.payload)
        usuario = Usuario.objects.get(numero_documento=self.payload['numero_documento'])
        response = self.client.post(
            '/api/usuario-agencia/',
            data={
                'usuario_id': usuario.id,
                'agencia_id': self.agencia.id,
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(UsuarioAgencia.objects.filter(
            usuario=usuario,
            agencia=self.agencia,
        ).exists())

    def test_association_endpoint_rejects_unknown_ids(self):
        request = self.factory.post(
            '/usuario-agencia/',
            {'usuario_id': 999, 'agencia_id': self.agencia.id},
            format='json',
        )

        response = UsuarioAgenciaView.as_view()(request)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Usuario.objects.exists())
