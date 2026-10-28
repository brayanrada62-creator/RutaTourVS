"""Datos y utilidades comunes para las pruebas (solo se usan en tests)."""
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from rest_framework.test import APIClient

from buses.models import Bus, TipoBus
from paquetes.models import Paquete
from usuarios.models import Agencia, Rol, Usuario, UsuarioAgencia

CLAVE = "clave123"


class Escenario:
    """Dos agencias (A y B), cada una con admin, conductor, bus y paquete; un cliente y un superadmin."""

    def __init__(self):
        for rid, nombre in ((1, "superadministrador"), (2, "administrador"), (3, "conductor"), (4, "cliente")):
            Rol.objects.get_or_create(id=rid, defaults={"rol": nombre})
        self.ag_a = Agencia.objects.create(nombre="A", nit="1", direccion="d", telefono="1", correo="a@a.co")
        self.ag_b = Agencia.objects.create(nombre="B", nit="2", direccion="d", telefono="2", correo="b@b.co")
        self.super = self.usuario("super@rt.co", 1)
        self.admin_a = self.usuario("admin.a@rt.co", 2, self.ag_a)
        self.admin_b = self.usuario("admin.b@rt.co", 2, self.ag_b)
        self.cond_a = self.usuario("cond.a@rt.co", 3, self.ag_a)
        self.cond_b = self.usuario("cond.b@rt.co", 3, self.ag_b)
        self.cliente = self.usuario("cliente@rt.co", 4)
        self.otro_cliente = self.usuario("otro@rt.co", 4)
        self.tipo_a = TipoBus.objects.create(nombre="T", agencia=self.ag_a, capacidad=10, descripcion="")
        self.tipo_b = TipoBus.objects.create(nombre="T", agencia=self.ag_b, capacidad=10, descripcion="")
        self.bus_a = self.bus("AAA111", self.ag_a, self.tipo_a)
        self.bus_a2 = self.bus("AAA222", self.ag_a, self.tipo_a)
        self.bus_b = self.bus("BBB111", self.ag_b, self.tipo_b)
        self.paq_a = Paquete.objects.create(nombre="PA", agencia=self.ag_a, descripcion="", duracion_estimada="1",
                                            fecha_creacion=timezone.now())
        self.paq_b = Paquete.objects.create(nombre="PB", agencia=self.ag_b, descripcion="", duracion_estimada="1",
                                            fecha_creacion=timezone.now())

    _doc = 100

    def usuario(self, correo, rol, agencia=None, clave=CLAVE, cifrar=True):
        Escenario._doc += 1
        u = Usuario.objects.create(nombre_completo=correo.split("@")[0], rol_id=rol, tipo_documento="CC",
                                   numero_documento=str(Escenario._doc), correo=correo, telefono="1",
                                   contrasena=make_password(clave) if cifrar else clave)
        if agencia:
            UsuarioAgencia.objects.create(usuario=u, agencia=agencia)
        return u

    @staticmethod
    def bus(placa, agencia, tipo):
        return Bus.objects.create(placa=placa, agencia=agencia, tipo_bus=tipo, marca="m", modelo="m",
                                  fecha_registro=timezone.now())

    @staticmethod
    def cliente_http(usuario=None, clave=CLAVE):
        """APIClient con el token de ese usuario, obtenido con el login real."""
        c = APIClient()
        if usuario is not None:
            r = c.post("/api/login/", {"correo": usuario.correo, "contrasena": clave}, format="json")
            assert r.status_code == 200, r.content
            c.credentials(HTTP_AUTHORIZATION="Bearer " + r.json()["token"])
        return c
