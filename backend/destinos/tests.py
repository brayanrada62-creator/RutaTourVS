from django.test import TestCase

from destinos.models import Departamento, Destino, Hospedaje
from usuarios.pruebas import Escenario


class HospedajeDestinoCrudTest(TestCase):
    def setUp(self):
        self.e = Escenario()
        self.c = Escenario.cliente_http(self.e.admin_a)
        self.departamento = Departamento.objects.create(nombre="Caldas")
        self.destino_a = Destino.objects.create(
            nombre="Manizales", departamento=self.departamento, descripcion=""
        )
        self.destino_b = Destino.objects.create(
            nombre="Villamaría", departamento=self.departamento, descripcion=""
        )
        self.destino_c = Destino.objects.create(
            nombre="Neira", departamento=self.departamento, descripcion=""
        )

    def test_hospedaje_admite_varios_destinos_y_crud_de_relacion(self):
        respuesta = self.c.post(
            "/api/hospedaje/",
            {
                "nombre": "Hotel Central",
                "destino_id": self.destino_a.id,
                "direccion": "Centro",
                "telefono": "123",
                "descripcion": "Hotel",
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 200)
        hospedaje = Hospedaje.objects.get(nombre="Hotel Central")

        relacion = self.c.post(
            "/api/hospedaje-destino/",
            {"hospedaje_id": hospedaje.id, "destino_id": self.destino_b.id},
            format="json",
        )
        self.assertEqual(relacion.status_code, 201)
        relacion_id = relacion.json()["id"]

        detalle = self.c.get(f"/api/hospedaje/{hospedaje.id}/").json()
        self.assertEqual(set(detalle["destino_ids"]), {self.destino_a.id, self.destino_b.id})
        self.assertNotIn("agencia_id", detalle)

        self.assertEqual(self.c.get(f"/api/hospedaje-destino/{relacion_id}/").status_code, 200)
        self.assertEqual(
            self.c.put(
                f"/api/hospedaje-destino/{relacion_id}/",
                {"hospedaje_id": hospedaje.id, "destino_id": self.destino_c.id},
                format="json",
            ).status_code,
            200,
        )
        self.assertEqual(self.c.delete(f"/api/hospedaje-destino/{relacion_id}/").status_code, 200)
        relaciones = self.c.get(f"/api/hospedaje-destino/?hospedaje_id={hospedaje.id}").json()
        self.assertEqual(len(relaciones), 1)
        self.assertEqual(relaciones[0]["destino_id"], self.destino_a.id)

    def test_busqueda_no_incluye_sitios_turisticos(self):
        respuesta = self.c.get("/api/buscar/?search=hotel").json()
        self.assertEqual(set(respuesta), {"search", "destinos", "paquetes", "hospedajes"})


class ValidacionCatalogoTest(TestCase):
    """Destinos y hospedajes: el nombre es obligatorio y el departamento debe existir."""

    def setUp(self):
        self.e = Escenario()
        self.admin = Escenario.cliente_http(self.e.admin_a)
        self.depto = Departamento.objects.create(nombre="Boyacá")

    def test_destino_invalido(self):
        datos = {"nombre": "Villa", "departamento": self.depto.id, "descripcion": "d"}
        self.assertEqual(self.admin.post("/api/destino/", {**datos, "nombre": " "}, format="json").status_code, 400)
        r = self.admin.post("/api/destino/", {**datos, "departamento": 999999}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Departamento.objects.filter(nombre="999999").exists())
        self.assertEqual(self.admin.post("/api/destino/", datos, format="json").status_code, 201)
        por_nombre = {**datos, "nombre": "Paipa", "departamento": "boyacá"}
        self.assertEqual(self.admin.post("/api/destino/", por_nombre, format="json").status_code, 201)

    def test_hospedaje_sin_nombre(self):
        datos = {"nombre": "", "direccion": "d", "telefono": "1", "descripcion": "d"}
        self.assertEqual(self.admin.post("/api/hospedaje/", datos, format="json").status_code, 400)


class MigracionBogotaTest(TestCase):
    def test_agrega_bogota_una_sola_vez(self):
        from django.apps import apps
        from importlib import import_module

        migracion = import_module("destinos.migrations.0007_departamento_bogota")
        migracion.agregar_bogota(apps, None)
        migracion.agregar_bogota(apps, None)
        self.assertEqual(Departamento.objects.filter(nombre="Bogotá D.C.").count(), 1)
