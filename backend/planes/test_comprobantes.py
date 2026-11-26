import io
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from notificaciones.models import Notificacion, Tipo
from usuarios.pruebas import Escenario
from .models import Plan


class ComprobantePlanTest(TestCase):
    def test_envio_revision_y_alcance(self):
        escenario = Escenario()
        admin = escenario.cliente_http(escenario.admin_a)
        otra = escenario.cliente_http(escenario.admin_b)
        superadmin = escenario.cliente_http(escenario.super)
        plan = Plan.objects.create(nombre="Básico", descripcion="Plan de prueba")
        ruta = "/api/solicitudes-plan/"

        def enviar(agencia):
            datos = io.BytesIO()
            Image.new("RGB", (16, 16)).save(datos, format="PNG")
            foto = SimpleUploadedFile("pago.png", datos.getvalue(), content_type="image/png")
            return admin.post(ruta, {"agencia_id": agencia.id, "plan_id": plan.id,
                                    "periodo": "mensual", "comprobante": foto}, format="multipart")

        with TemporaryDirectory() as media, self.settings(MEDIA_ROOT=media):
            with self.captureOnCommitCallbacks(execute=True):
                self.assertEqual(enviar(escenario.ag_b).status_code, 403)
                respuesta = enviar(escenario.ag_a)
                self.assertEqual(respuesta.status_code, 201)
                self.assertEqual(enviar(escenario.ag_a).status_code, 409)
            solicitud = respuesta.json()
            self.assertTrue(solicitud["comprobante"])
            aviso = Notificacion.objects.get(tipo=Tipo.COMPROBANTE_PLAN)
            self.assertEqual(aviso.destinatario, escenario.super)
            self.assertEqual(aviso.referencia_id, int(solicitud["id"]))
            self.assertEqual(otra.get(ruta).json(), [])
            self.assertEqual(superadmin.get(ruta).json()[0]["id"], solicitud["id"])

            detalle = f"{ruta}{solicitud['id']}/"
            self.assertEqual(admin.patch(detalle, {"estado": "aprobado"}, format="json").status_code, 403)
            revisada = superadmin.patch(detalle, {"estado": "rechazado", "motivo": "Foto borrosa"}, format="json")
            self.assertEqual(revisada.status_code, 200)
            self.assertEqual(admin.get(ruta).json()[0]["motivo"], "Foto borrosa")
            self.assertEqual(superadmin.patch(detalle, {"estado": "aprobado"}, format="json").status_code, 409)
