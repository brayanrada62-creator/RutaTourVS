from datetime import timedelta

from django.test import TestCase
from rest_framework.test import APIClient

from buses.models import Viaje
from buses.views import hoy_colombia
from usuarios.pruebas import Escenario


class BusquedaPorFechaTest(TestCase):
    """HU-M-05: el catálogo público trae las salidas y se filtra por fecha desde hoy."""

    def setUp(self):
        self.e = Escenario()
        self.hoy = hoy_colombia()
        self.manana = self.hoy + timedelta(days=1)
        Viaje.objects.create(paquete=self.e.paq_a, bus=self.e.bus_a, fecha=self.manana, hora="06:30")
        Viaje.objects.create(paquete=self.e.paq_a, bus=self.e.bus_a2, fecha=self.manana, hora="08:00")
        Viaje.objects.create(paquete=self.e.paq_a, bus=self.e.bus_a, fecha=self.hoy - timedelta(days=3), hora="06:30")
        Viaje.objects.create(paquete=self.e.paq_b, bus=self.e.bus_b, fecha=self.hoy + timedelta(days=5), hora="06:30")

    def buscar(self, **params):
        return APIClient().get("/api/paquete/", params)

    def test_salidas_futuras_sin_repetir_y_sin_pasadas(self):
        r = self.buscar()
        self.assertEqual(r.status_code, 200)
        salidas = {p["id"]: p["salidas"] for p in r.json()}
        self.assertEqual(salidas[self.e.paq_a.id], [self.manana.isoformat()])
        self.assertEqual(salidas[self.e.paq_b.id], [(self.hoy + timedelta(days=5)).isoformat()])

    def test_filtra_por_fecha(self):
        r = self.buscar(fecha=self.manana.isoformat())
        self.assertEqual(r.status_code, 200)
        self.assertEqual([p["id"] for p in r.json()], [self.e.paq_a.id])

    def test_fecha_sin_salidas_lista_vacia(self):
        r = self.buscar(fecha=(self.hoy + timedelta(days=30)).isoformat())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), [])

    def test_fecha_anterior_a_hoy_400(self):
        r = self.buscar(fecha=(self.hoy - timedelta(days=1)).isoformat())
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["mensaje"], "La fecha no puede ser anterior a hoy")

    def test_fecha_mal_escrita_400(self):
        self.assertEqual(self.buscar(fecha="02/11/2026").status_code, 400)

    def test_viaje_completado_no_cuenta(self):
        Viaje.objects.filter(paquete=self.e.paq_b).update(estado=Viaje.COMPLETADO)
        r = self.buscar(fecha=(self.hoy + timedelta(days=5)).isoformat())
        self.assertEqual(r.json(), [])



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
