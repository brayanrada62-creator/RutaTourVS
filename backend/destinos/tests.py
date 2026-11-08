from pagos.tests import imagen
from django.test import override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
import tempfile
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
                "telefono": "3001234567",
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
        datos = {"nombre": "", "direccion": "d", "telefono": "3001234567", "descripcion": "d"}
        self.assertEqual(self.admin.post("/api/hospedaje/", datos, format="json").status_code, 400)


class MigracionBogotaTest(TestCase):
    def test_agrega_bogota_una_sola_vez(self):
        from django.apps import apps
        from importlib import import_module

        migracion = import_module("destinos.migrations.0007_departamento_bogota")
        migracion.agregar_bogota(apps, None)
        migracion.agregar_bogota(apps, None)
        self.assertEqual(Departamento.objects.filter(nombre="Bogotá D.C.").count(), 1)


class LimitesTextoDestinoTest(TestCase):
    """Los textos largos responden 400 con su motivo, no un error 500."""

    def setUp(self):
        self.e = Escenario()
        self.admin = Escenario.cliente_http(self.e.admin_a)
        self.depto = Departamento.objects.create(nombre="Caldas")

    def crear(self, **cambios):
        datos = {"nombre": "Villa", "departamento": self.depto.id, "descripcion": "d", **cambios}
        return self.admin.post("/api/destino/", datos, format="json")

    def test_limites(self):
        self.assertEqual(self.crear(nombre="x" * 151).status_code, 400)
        r = self.crear(descripcion="x" * 2001)
        self.assertEqual(r.status_code, 400)
        self.assertIn("2000", r.json()["message"])
        self.assertEqual(self.crear(descripcion="x" * 2000).status_code, 201)

    def test_editar_con_texto_largo(self):
        destino = self.crear().json()["id"]
        r = self.admin.patch(f"/api/destino/{destino}/", {"descripcion": "x" * 2001}, format="json")
        self.assertEqual(r.status_code, 400)


class LimitesTextoHospedajeTest(TestCase):
    """Los textos largos del hospedaje responden 400 con su motivo, no un error 500."""

    def setUp(self):
        self.admin = Escenario.cliente_http(Escenario().admin_a)

    def crear(self, **cambios):
        datos = {"nombre": "Hotel", "direccion": "d", "telefono": "3001234567", "descripcion": "d", **cambios}
        return self.admin.post("/api/hospedaje/", datos, format="json")

    def test_celular_obligatorio_y_fijo_opcional(self):
        for malo in ("123", "6011234567", "30012345678", ""):
            r = self.crear(nombre=f"H{malo}", telefono=malo)
            self.assertEqual(r.status_code, 400, malo)
            self.assertIn("celular", r.json()["message"])
        for malo in ("123", "3001234567", "601123456"):
            r = self.crear(nombre=f"F{malo}", telefono_fijo=malo)
            self.assertEqual(r.status_code, 400, malo)
            self.assertIn("fijo", r.json()["message"])
        self.assertEqual(self.crear(nombre="Con fijo", telefono_fijo="6028201234").status_code, 200)
        hotel = Hospedaje.objects.get(nombre="Con fijo")
        self.assertEqual((hotel.telefono, hotel.telefono_fijo), ("3001234567", "6028201234"))
        self.assertEqual(self.admin.get(f"/api/hospedaje/{hotel.id}/").json()["telefono_fijo"], "6028201234")
        # Vacío borra el fijo (es opcional).
        self.assertEqual(self.admin.put(f"/api/hospedaje/{hotel.id}/", {"telefono_fijo": ""}, format="json").status_code, 200)
        hotel.refresh_from_db()
        self.assertEqual(hotel.telefono_fijo, "")

    def test_hotel_antiguo_edita_sin_cambiar_su_telefono(self):
        viejo = Hospedaje.objects.create(nombre="Viejo", direccion="d", telefono="30013131311", descripcion="d")
        url = f"/api/hospedaje/{viejo.id}/"
        r = self.admin.put(url, {"nombre": "Viejo 2", "telefono": "30013131311"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.admin.put(url, {"telefono": "3001"}, format="json").status_code, 400)

    def test_limites(self):
        for cambio in ({"nombre": "x" * 151}, {"direccion": "x" * 256}, {"telefono": "3" * 21},
                       {"descripcion": "x" * 2001}):
            self.assertEqual(self.crear(**cambio).status_code, 400, cambio)
        self.assertEqual(self.crear(descripcion="x" * 2000).status_code, 200)

    def test_editar_con_texto_largo(self):
        self.crear()
        hospedaje = Hospedaje.objects.get(nombre="Hotel")
        r = self.admin.put(f"/api/hospedaje/{hospedaje.id}/", {"descripcion": "x" * 2001}, format="json")
        self.assertEqual(r.status_code, 400)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class FotoHotelTest(TestCase):
    def setUp(self):
        self.admin = Escenario.cliente_http(Escenario().admin_a)

    def test_foto_del_hotel_validada(self):
        datos = {"nombre": "Hotel Foto", "direccion": "d", "telefono": "3001234567", "descripcion": "d"}
        falso = SimpleUploadedFile("h.jpg", b"no es imagen", content_type="image/jpeg")
        r = self.admin.post("/api/hospedaje/", {**datos, "imagen": falso}, format="multipart")
        self.assertEqual((r.status_code, r.json()["campo"]), (400, "imagen"))
        self.assertEqual(self.admin.post("/api/hospedaje/", {**datos, "imagen": imagen("h.png")}, format="multipart").status_code, 200)
        hotel = Hospedaje.objects.get(nombre="Hotel Foto")
        self.assertTrue(hotel.imagen.name.startswith("hospedajes/"))
        self.assertTrue(self.admin.get(f"/api/hospedaje/{hotel.id}/").json()["imagen"].startswith("http://testserver/media/hospedajes/"))

