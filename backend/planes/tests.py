import io
import tempfile
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from planes.models import PlanAgencias
from planes.vigencia import fecha_colombia
from reservas.models import Reserva
from usuarios.pruebas import Escenario

MEDIA = tempfile.mkdtemp()


def png():
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(buf, "PNG")
    return SimpleUploadedFile("comprobante.png", buf.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT=MEDIA)
class MembresiaCatalogoTest(TestCase):
    def setUp(self):
        self.e = Escenario()
        self.anonimo = APIClient()
        self.admin = Escenario.cliente_http(self.e.admin_a)
        self.super = Escenario.cliente_http(self.e.super)
        self.cliente = Escenario.cliente_http(self.e.cliente)

    def ids(self, cliente, url="/api/paquete/"):
        return {p["id"] for p in cliente.get(url).json()}

    def vencer(self, agencia):
        PlanAgencias.objects.filter(id_agencia=agencia).update(
            vencimiento=fecha_colombia() - timedelta(days=1), estado="activo",
        )

    def test_sin_membresia_el_visitante_no_ve_el_paquete_y_el_admin_si(self):
        self.vencer(self.e.ag_b)
        self.assertNotIn(self.e.paq_b.id, self.ids(self.anonimo))
        self.assertEqual(self.anonimo.get(f"/api/paquete/{self.e.paq_b.id}/").status_code, 404)
        self.assertIn(self.e.paq_a.id, self.ids(self.anonimo))
        self.assertIn(self.e.paq_b.id, self.ids(self.super))
        self.assertIn(self.e.paq_b.id, self.ids(Escenario.cliente_http(self.e.admin_b)))

    def test_no_se_reserva_si_la_membresia_vencio_y_el_cliente_conserva_el_paquete(self):
        self.vencer(self.e.ag_b)
        Reserva.objects.create(
            usuario=self.e.cliente, paquete=self.e.paq_b, fecha_reserva=timezone.now(), estado="confirmada",
        )
        self.assertEqual(self.cliente.get(f"/api/paquete/{self.e.paq_b.id}/").status_code, 200)
        nueva = self.cliente.post("/api/reserva/", {"paquete_id": self.e.paq_b.id}, format="json")
        self.assertEqual(nueva.status_code, 400)
        self.assertIn("membresía", nueva.json()["message"])

    def test_aprobar_el_comprobante_guarda_la_foto_y_devuelve_el_paquete(self):
        self.vencer(self.e.ag_a)
        self.assertNotIn(self.e.paq_a.id, self.ids(self.anonimo))
        creada = self.admin.post(
            "/api/solicitudes-plan/",
            {"plan_id": self.e.plan.id, "periodo": "mensual", "comprobante": png()},
            format="multipart",
        )
        self.assertEqual(creada.status_code, 201)
        cuerpo = creada.json()
        self.assertEqual(cuerpo["estado"], "validando")
        self.assertTrue(cuerpo["comprobante"])
        self.assertEqual(self.cliente.get("/api/solicitudes-plan/").status_code, 403)
        aprobada = self.super.post(f"/api/solicitudes-plan/{cuerpo['id']}/aprobar/", {}, format="json")
        self.assertEqual(aprobada.status_code, 200)
        self.assertEqual(aprobada.json()["estado"], "aprobado")
        self.assertIsNotNone(aprobada.json()["venceEl"])
        self.assertIn(self.e.paq_a.id, self.ids(self.anonimo))
        self.assertTrue(PlanAgencias.objects.filter(
            id_agencia=self.e.ag_a, estado="activo", vencimiento__gte=fecha_colombia(),
        ).exists())

    def test_rechazar_no_reactiva_el_catalogo(self):
        self.vencer(self.e.ag_a)
        creada = self.admin.post(
            "/api/solicitudes-plan/",
            {"plan_id": self.e.plan.id, "periodo": "mensual", "comprobante": png()},
            format="multipart",
        )
        sid = creada.json()["id"]
        vacio = self.super.post(f"/api/solicitudes-plan/{sid}/rechazar/", {}, format="json")
        self.assertEqual(vacio.status_code, 400)
        rechazada = self.super.post(
            f"/api/solicitudes-plan/{sid}/rechazar/", {"motivo": "Foto ilegible"}, format="json",
        )
        self.assertEqual(rechazada.status_code, 200)
        self.assertEqual(rechazada.json()["estado"], "rechazado")
        self.assertEqual(rechazada.json()["motivo"], "Foto ilegible")
        self.assertNotIn(self.e.paq_a.id, self.ids(self.anonimo))
