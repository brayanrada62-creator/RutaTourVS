from datetime import timedelta

from django.test import TestCase
from rest_framework.test import APIClient

from buses.models import Viaje
from buses.views import hoy_colombia
from usuarios.pruebas import Escenario


class CatalogoPorAgenciaTest(TestCase):
    """Fase 2 (AND-021): un cliente registrado por una agencia solo ve y reserva lo de esa agencia."""

    def setUp(self):
        self.e = Escenario()
        dia = hoy_colombia() + timedelta(days=5)
        self.salida_a = Viaje.objects.create(paquete=self.e.paq_a, bus=self.e.bus_a, fecha=dia, hora="06:30")
        self.salida_b = Viaje.objects.create(paquete=self.e.paq_b, bus=self.e.bus_b, fecha=dia, hora="06:30")
        self.ligado = Escenario.cliente_http(self.e.usuario("ligado@rt.co", 4, self.e.ag_a))

    @staticmethod
    def ids(respuesta):
        return {p["id"] for p in respuesta.json()}

    def test_cliente_de_agencia_no_ve_otra(self):
        self.assertEqual(self.ids(self.ligado.get("/api/paquete/")), {self.e.paq_a.id})
        self.assertEqual(self.ligado.get(f"/api/paquete/{self.e.paq_b.id}/").status_code, 404)
        self.assertEqual(self.ligado.get(f"/api/paquete/{self.e.paq_a.id}/").status_code, 200)
        self.assertEqual(self.ids(self.ligado.get("/api/viaje/")), {self.salida_a.id})
        r = self.ligado.post("/api/reserva/", {"fecha_reserva": "2026-10-27", "paquete_id": self.e.paq_b.id,
                                               "viaje_id": self.salida_b.id}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_independiente_y_anonimo_ven_todas(self):
        todos = {self.e.paq_a.id, self.e.paq_b.id}
        self.assertEqual(self.ids(Escenario.cliente_http(self.e.cliente).get("/api/paquete/")), todos)
        self.assertEqual(self.ids(APIClient().get("/api/paquete/")), todos)
        self.assertEqual(self.ids(Escenario.cliente_http(self.e.cliente).get("/api/viaje/")),
                         {self.salida_a.id, self.salida_b.id})
