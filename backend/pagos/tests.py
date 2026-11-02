import io
import shutil
import tempfile
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image

from buses.models import Asiento, Viaje
from buses.views import hoy_colombia
from pagos.models import Pago
from reservas.models import AsientoReserva, Reserva
from usuarios.pruebas import Escenario

MEDIA_PRUEBAS = tempfile.mkdtemp()


def imagen(nombre="comprobante.png", formato="PNG"):
    datos = io.BytesIO()
    Image.new("RGB", (20, 20), "white").save(datos, format=formato)
    return SimpleUploadedFile(nombre, datos.getvalue(), content_type=f"image/{formato.lower()}")


@override_settings(MEDIA_ROOT=MEDIA_PRUEBAS)
class ComprobanteTest(TestCase):
    """Fase 2 (AND-004): el cliente sube la foto del comprobante; el monto lo pone el servidor."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_PRUEBAS, ignore_errors=True)

    def setUp(self):
        self.e = Escenario()
        self.e.paq_a.precio = 50000
        self.e.paq_a.save()
        salida = Viaje.objects.create(paquete=self.e.paq_a, bus=self.e.bus_a,
                                      fecha=hoy_colombia() + timedelta(days=7), hora="06:30")
        self.reserva = Reserva.objects.create(fecha_reserva=timezone.now(), usuario=self.e.cliente,
                                              paquete=self.e.paq_a, viaje=salida)
        for numero in (1, 2):
            silla = Asiento.objects.create(numero_asiento=numero, tipo_bus=self.e.tipo_a)
            AsientoReserva.objects.create(reserva=self.reserva, asiento=silla)
        self.c = Escenario.cliente_http(self.e.cliente)

    def pagar(self, archivo=None, precio="1"):
        datos = {"precio": precio, "reserva_id": self.reserva.id, "fecha_pago": "2026-10-27", "referencia": "transferencia"}
        if archivo is not None:
            datos["comprobante"] = archivo
        return self.c.post("/api/pago/", datos)

    def test_cliente_sube_imagen(self):
        r = self.pagar(imagen())
        self.assertEqual(r.status_code, 200)
        pago = Pago.objects.get(reserva=self.reserva)
        self.assertEqual(pago.estado, "pendiente")
        self.assertTrue(pago.comprobante.name)
        self.assertTrue(self.c.get(f"/api/pago/{pago.id}/").json()["comprobante"])

    def test_acepta_jpg_y_webp(self):
        self.assertEqual(self.pagar(imagen("c.jpg", "JPEG")).status_code, 200)
        Pago.objects.update(estado="rechazado")
        self.assertEqual(self.pagar(imagen("c.webp", "WEBP")).status_code, 200)

    def test_precio_lo_pone_el_servidor(self):
        self.pagar(imagen(), precio="1")
        self.assertEqual(Pago.objects.get(reserva=self.reserva).precio, 100000)

    def test_comprobante_no_imagen(self):
        falso = SimpleUploadedFile("comprobante.jpg", b"%PDF-1.4 esto no es una foto", content_type="image/jpeg")
        r = self.pagar(falso)
        self.assertEqual(r.status_code, 400)
        self.assertIn("imagen", r.json()["message"])
        self.assertFalse(Pago.objects.exists())

    def test_comprobante_obligatorio(self):
        self.assertEqual(self.pagar().status_code, 400)
        self.assertFalse(Pago.objects.exists())

    def test_comprobante_de_mas_de_5_mb(self):
        grande = SimpleUploadedFile("c.png", b"0" * (5 * 1024 * 1024 + 1), content_type="image/png")
        self.assertEqual(self.pagar(grande).status_code, 400)

    def test_no_duplica_pago_en_revision(self):
        self.assertEqual(self.pagar(imagen()).status_code, 200)
        r = self.pagar(imagen())
        self.assertEqual(r.status_code, 409)
        self.assertEqual(Pago.objects.filter(reserva=self.reserva).count(), 1)

    def test_tras_rechazo_puede_pagar_otra_vez(self):
        self.pagar(imagen())
        Pago.objects.update(estado="rechazado")
        self.assertEqual(self.pagar(imagen()).status_code, 200)
        self.assertEqual(Pago.objects.filter(reserva=self.reserva).count(), 2)

    def test_reserva_cancelada_no_se_paga(self):
        Reserva.objects.filter(id=self.reserva.id).update(estado="cancelada")
        self.assertEqual(self.pagar(imagen()).status_code, 400)

    def test_sin_sillas_no_se_paga(self):
        AsientoReserva.objects.filter(reserva=self.reserva).delete()
        r = self.pagar(imagen())
        self.assertEqual(r.status_code, 400)
        self.assertIn("sillas", r.json()["message"])

    def test_paquete_sin_precio_igual_registra_el_pago(self):
        self.e.paq_a.precio = 0
        self.e.paq_a.save()
        self.assertEqual(self.pagar(imagen()).status_code, 200)
        self.assertEqual(Pago.objects.get(reserva=self.reserva).precio, 0)
