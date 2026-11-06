from datetime import timedelta

from django.test import TestCase
from rest_framework.test import APIClient

from buses.models import Viaje
from buses.views import hoy_colombia
from paquetes.models import Paquete
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


class GuardarPaqueteTest(TestCase):
    """HU-W-21: precio y duración válidos, paquete de la agencia del administrador y GET con lo guardado."""

    def setUp(self):
        self.e = Escenario()
        self.admin = Escenario.cliente_http(self.e.admin_a)
        self.antes = Paquete.objects.count()

    def datos(self, **cambios):
        base = {"nombre": "Guatapé", "agencia_id": self.e.ag_a.id, "descripcion": "Día de campo",
                "duracion_estimada": "2 días", "precio": "150000"}
        base.update(cambios)
        return {k: v for k, v in base.items() if v is not None}

    def test_guarda_y_el_get_devuelve_duracion_y_precio(self):
        r = self.admin.post("/api/paquete/", self.datos(), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        guardado = Paquete.objects.get(id=r.json()["id"])
        self.assertEqual(guardado.agencia_id, self.e.ag_a.id)
        listado = {p["id"]: p for p in self.admin.get("/api/paquete/").json()}
        self.assertEqual(listado[guardado.id]["duracion_estimada"], "2 días")
        self.assertEqual(listado[guardado.id]["precio"], "150000.00")

    def test_precio_vacio_no_numerico_o_no_positivo_da_400(self):
        for precio in ("", "abc", "-5", "0", "12.345", None):
            r = self.admin.post("/api/paquete/", self.datos(precio=precio), format="json")
            self.assertEqual(r.status_code, 400, precio)
            self.assertIn("precio", r.json()["mensaje"].lower())
        self.assertEqual(Paquete.objects.count(), self.antes)

    def test_duracion_vacia_da_400(self):
        for duracion in ("", "  ", None):
            r = self.admin.post("/api/paquete/", self.datos(duracion_estimada=duracion), format="json")
            self.assertEqual(r.status_code, 400, duracion)
        self.assertEqual(Paquete.objects.count(), self.antes)

    def test_admin_no_guarda_en_otra_agencia(self):
        r = self.admin.post("/api/paquete/", self.datos(agencia_id=self.e.ag_b.id), format="json")
        self.assertEqual(r.status_code, 403)
        r = self.admin.put(f"/api/paquete/{self.e.paq_b.id}/", self.datos(), format="json")
        self.assertEqual(r.status_code, 403)
        r = self.admin.put(f"/api/paquete/{self.e.paq_a.id}/", self.datos(agencia_id=self.e.ag_b.id), format="json")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(Paquete.objects.count(), self.antes)

    def test_superadmin_guarda_en_cualquier_agencia(self):
        sup = Escenario.cliente_http(self.e.super)
        r = sup.post("/api/paquete/", self.datos(agencia_id=self.e.ag_b.id), format="json")
        self.assertEqual(r.status_code, 201, r.content)

    def test_put_actualiza_precio_valido(self):
        r = self.admin.put(f"/api/paquete/{self.e.paq_a.id}/", self.datos(precio="99000.50"), format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["precio"], "99000.50")

    def test_proxima_salida_en_el_paquete(self):
        self.assertIsNone(self.admin.get(f"/api/paquete/{self.e.paq_a.id}/").json()["proxima_salida"])
        dia = hoy_colombia() + timedelta(days=4)
        Viaje.objects.create(paquete=self.e.paq_a, bus=self.e.bus_a, fecha=dia, hora="08:00")
        Viaje.objects.create(paquete=self.e.paq_a, bus=self.e.bus_a2, fecha=dia, hora="06:30")
        self.assertEqual(self.admin.get(f"/api/paquete/{self.e.paq_a.id}/").json()["proxima_salida"],
                         {"fecha": dia.isoformat(), "hora": "06:30"})


from destinos.models import Departamento, Destino
from paquetes.models import Itinerario, PaqueteDestino


class PaqueteAgenciaSesionTest(TestCase):
    """El admin ya no envía agencia_id: sale de su sesión. Si la envía y no es suya: 403."""

    def setUp(self):
        self.e = Escenario()
        self.admin = Escenario.cliente_http(self.e.admin_a)
        self.datos = {"nombre": "Salento", "descripcion": "x", "duracion_estimada": "1 día", "precio": "90000"}

    def test_admin_crea_sin_agencia_y_queda_en_la_suya(self):
        r = self.admin.post("/api/paquete/", self.datos, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Paquete.objects.get(id=r.json()["id"]).agencia_id, self.e.ag_a.id)

    def test_admin_edita_sin_agencia_y_la_conserva(self):
        r = self.admin.put(f"/api/paquete/{self.e.paq_a.id}/", self.datos, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.e.paq_a.refresh_from_db()
        self.assertEqual(self.e.paq_a.agencia_id, self.e.ag_a.id)

    def test_superadmin_sin_agencia_400(self):
        r = Escenario.cliente_http(self.e.super).post("/api/paquete/", self.datos, format="json")
        self.assertEqual(r.status_code, 400)

    def test_eliminar_paquete_de_otra_agencia_403_y_inexistente_404(self):
        self.assertEqual(self.admin.delete(f"/api/paquete/{self.e.paq_b.id}/").status_code, 403)
        self.assertTrue(Paquete.objects.filter(id=self.e.paq_b.id).exists())
        self.assertEqual(self.admin.delete("/api/paquete/999999/").status_code, 404)
        self.assertEqual(self.admin.delete(f"/api/paquete/{self.e.paq_a.id}/").status_code, 200)


class PaqueteDestinoAgenciaTest(TestCase):
    """/paquetedestino/: solo el admin de la agencia del paquete vincula o quita destinos."""

    def setUp(self):
        self.e = Escenario()
        self.admin = Escenario.cliente_http(self.e.admin_a)
        depto = Departamento.objects.create(nombre="Quindío")
        self.destino = Destino.objects.create(nombre="Salento", departamento=depto, descripcion="x")
        self.rel_b = PaqueteDestino.objects.create(paquete=self.e.paq_b, destino=self.destino)

    def test_vincular_en_paquete_propio_201_con_id_y_repetido_409(self):
        datos = {"paquete_id": self.e.paq_a.id, "destino_id": self.destino.id}
        r = self.admin.post("/api/paquetedestino/", datos, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(PaqueteDestino.objects.filter(id=r.json()["id"], paquete=self.e.paq_a).exists())
        self.assertEqual(self.admin.post("/api/paquetedestino/", datos, format="json").status_code, 409)

    def test_no_toca_paquetes_de_otra_agencia(self):
        r = self.admin.post("/api/paquetedestino/", {"paquete_id": self.e.paq_b.id, "destino_id": self.destino.id},
                            format="json")
        self.assertEqual(r.status_code, 403)
        r = self.admin.put(f"/api/paquetedestino/{self.rel_b.id}/",
                           {"paquete_id": self.e.paq_a.id, "destino_id": self.destino.id}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.admin.delete(f"/api/paquetedestino/{self.rel_b.id}/").status_code, 403)
        self.assertTrue(PaqueteDestino.objects.filter(id=self.rel_b.id).exists())

    def test_inexistentes_404_y_anonimo_no_escribe(self):
        r = self.admin.post("/api/paquetedestino/", {"paquete_id": self.e.paq_a.id, "destino_id": 999999},
                            format="json")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.admin.delete("/api/paquetedestino/999999/").status_code, 404)
        anonimo = APIClient()
        self.assertEqual(anonimo.get("/api/paquetedestino/").status_code, 200)
        self.assertEqual(anonimo.delete(f"/api/paquetedestino/{self.rel_b.id}/").status_code, 401)

    def test_quitar_destino_no_borra_el_destino(self):
        rel = PaqueteDestino.objects.create(paquete=self.e.paq_a, destino=self.destino)
        self.assertEqual(self.admin.delete(f"/api/paquetedestino/{rel.id}/").status_code, 200)
        self.assertTrue(Destino.objects.filter(id=self.destino.id).exists())


class ItinerarioAgenciaTest(TestCase):
    """/itinerario/: las paradas de un paquete solo las cambia el admin de su agencia."""

    def setUp(self):
        self.e = Escenario()
        self.admin = Escenario.cliente_http(self.e.admin_a)
        self.parada_b = Itinerario.objects.create(titulo="P", paquete=self.e.paq_b, dia="1", descripcion="d",
                                                  hora="08:00", lugar="L")

    def datos(self, paquete):
        return {"titulo": "Mirador", "paquete_id": paquete.id, "dia": "1", "descripcion": "d", "hora": "09:00",
                "lugar": "Cocora"}

    def test_crea_en_su_paquete_y_no_en_otro(self):
        self.assertEqual(self.admin.post("/api/itinerario/", self.datos(self.e.paq_a), format="json").status_code, 201)
        self.assertEqual(self.admin.post("/api/itinerario/", self.datos(self.e.paq_b), format="json").status_code, 403)

    def test_no_edita_ni_borra_paradas_de_otra_agencia(self):
        url = f"/api/itinerario/{self.parada_b.id}/"
        self.assertEqual(self.admin.put(url, self.datos(self.e.paq_a), format="json").status_code, 403)
        self.assertEqual(self.admin.delete(url).status_code, 403)
        self.assertTrue(Itinerario.objects.filter(id=self.parada_b.id).exists())
        self.assertEqual(self.admin.get("/api/itinerario/999999/").status_code, 404)

    def test_lista_el_paquete_ordenada_por_dia_y_hora(self):
        for dia, hora in (("10", "07:00"), ("2", "09:00"), ("2", "06:00")):
            Itinerario.objects.create(titulo="P", paquete=self.e.paq_a, dia=dia, descripcion="", hora=hora, lugar="L")
        lista = self.admin.get(f"/api/itinerario/?paquete_id={self.e.paq_a.id}").json()
        self.assertEqual([(p["dia"], str(p["hora"])[:5]) for p in lista], [("2", "06:00"), ("2", "09:00"), ("10", "07:00")])

    def test_datos_invalidos_responden_400(self):
        for cambio in ({"hora": ""}, {"dia": "uno"}, {"dia": 0}, {"titulo": ""}, {"lugar": "x" * 151}):
            r = self.admin.post("/api/itinerario/", {**self.datos(self.e.paq_a), **cambio}, format="json")
            self.assertEqual(r.status_code, 400, cambio)
        self.assertFalse(Itinerario.objects.filter(paquete=self.e.paq_a).exists())

    def test_la_descripcion_es_opcional(self):
        datos = self.datos(self.e.paq_a)
        del datos["descripcion"]
        self.assertEqual(self.admin.post("/api/itinerario/", datos, format="json").status_code, 201)

    def test_editar_conserva_lo_que_no_se_envia(self):
        id_ = self.admin.post("/api/itinerario/", self.datos(self.e.paq_a), format="json").json()["id"]
        self.assertEqual(self.admin.put(f"/api/itinerario/{id_}/", {"titulo": "Nuevo"}, format="json").status_code, 200)
        parada = Itinerario.objects.get(id=id_)
        self.assertEqual((parada.titulo, parada.lugar, parada.dia), ("Nuevo", "Cocora", "1"))


class LimiteDescripcionPaqueteTest(TestCase):
    def test_descripcion_larga_responde_400(self):
        e = Escenario()
        datos = {"nombre": "Largo", "duracion_estimada": "1 dia", "precio": "1000", "descripcion": "x" * 10001}
        r = Escenario.cliente_http(e.admin_a).post("/api/paquete/", datos, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("10000", r.json()["mensaje"])
