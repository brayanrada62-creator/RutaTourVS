from datetime import timedelta

from django.test import TestCase
from rest_framework.test import APIClient

from buses.models import Viaje
from paquetes.views import hoy_colombia
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
