from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

import tempfile
from datetime import timedelta

from django.test import override_settings

from buses.models import Asiento, Bus_Conductor, Viaje
from buses.views import hoy_colombia
from pagos.models import Pago
from reservas.models import ChatMensaje, Reserva
from usuarios.models import RecuperarContrasena, Usuario
from usuarios.views import hash_valor
from pagos.tests import imagen
from usuarios.pruebas import CLAVE, Escenario


class AutenticacionTest(TestCase):
    def setUp(self):
        self.e = Escenario()

    def test_login_y_contrasena_cifrada(self):
        c = APIClient()
        ok = c.post("/api/login/", {"correo": self.e.cliente.correo, "contrasena": CLAVE}, format="json")
        self.assertEqual(ok.status_code, 200)
        self.assertTrue(ok.json()["token"])
        malo = c.post("/api/login/", {"correo": self.e.cliente.correo, "contrasena": "mala"}, format="json")
        self.assertEqual(malo.status_code, 401)
        self.assertEqual(malo.json()["mensaje"], "Usuario o contraseña incorrectos")

    def test_login_trae_rol_agencia_y_usuario_como_objeto(self):
        r = APIClient().post("/api/login/", {"correo": self.e.admin_a.correo, "contrasena": CLAVE}, format="json")
        self.assertEqual(r.status_code, 200)
        datos = r.json()
        # Angular lee rol_id y agencia_id; Android lee "usuario" como objeto.
        self.assertEqual(datos["id"], self.e.admin_a.id)
        self.assertEqual(datos["rol_id"], 2)
        self.assertEqual(datos["agencia_id"], self.e.ag_a.id)
        self.assertEqual(datos["correo"], self.e.admin_a.correo)
        self.assertEqual(datos["access"], datos["token"])
        self.assertEqual(datos["usuario"]["id"], self.e.admin_a.id)
        self.assertEqual(datos["usuario"]["rol_id"], 2)
        self.assertEqual(datos["usuario"]["agencia_id"], self.e.ag_a.id)

    def test_solo_acepta_prefijo_bearer(self):
        r = APIClient().post("/api/login/", {"correo": self.e.cliente.correo, "contrasena": CLAVE}, format="json")
        access = r.json()["token"]
        for prefijo, esperado in (("Bearer", 200), ("Token", 401)):
            c = APIClient()
            c.credentials(HTTP_AUTHORIZATION=f"{prefijo} {access}")
            self.assertEqual(c.get("/api/usuario/perfil/").status_code, esperado, prefijo)

    def test_clave_vieja_en_texto_plano_se_cifra_al_entrar(self):
        viejo = self.e.usuario("viejo@rt.co", 4, clave="plana1", cifrar=False)
        r = APIClient().post("/api/login/", {"correo": "viejo@rt.co", "contrasena": "plana1"}, format="json")
        self.assertEqual(r.status_code, 200)
        viejo.refresh_from_db()
        self.assertTrue(viejo.contrasena.startswith("pbkdf2_sha256$"))
        self.assertTrue(check_password("plana1", viejo.contrasena))

    def test_login_sincroniza_contrasena_auth_desactualizada(self):
        auth_user = User.objects.create_user(
            username=self.e.cliente.correo,
            email=self.e.cliente.correo,
            password="clave-anterior",
        )

        respuesta = APIClient().post(
            "/api/login/",
            {"correo": self.e.cliente.correo, "contrasena": CLAVE},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200)
        auth_user.refresh_from_db()
        self.assertTrue(auth_user.check_password(CLAVE))

    def test_sin_token_401_y_logout_invalida_token(self):
        self.assertEqual(APIClient().get("/api/reserva/").status_code, 401)
        c = Escenario.cliente_http(self.e.cliente)
        self.assertEqual(c.get("/api/reserva/").status_code, 200)
        refresh = c.refresh_token
        self.assertEqual(c.post("/api/logout/", {"refresh": refresh}, format="json").status_code, 200)
        self.assertEqual(
            c.post("/api/token/refresh/", {"refresh": refresh}, format="json").status_code,
            401,
        )

    def test_catalogo_publico_escritura_restringida(self):
        anonimo = APIClient()
        self.assertEqual(anonimo.get("/api/paquete/").status_code, 200)
        self.assertEqual(anonimo.get("/api/agencia/").status_code, 200)
        self.assertEqual(anonimo.get("/api/tipobus/").status_code, 200)
        self.assertEqual(anonimo.post("/api/tipobus/", {"nombre": "x"}, format="json").status_code, 401)
        cliente = Escenario.cliente_http(self.e.cliente)
        self.assertEqual(cliente.post("/api/tipobus/", {"nombre": "x"}, format="json").status_code, 403)


class UsuariosTest(TestCase):
    def setUp(self):
        self.e = Escenario()

    def test_registro_publico_siempre_cliente(self):
        r = APIClient().post("/api/usuario/", {
            "nombre_completo": "Nuevo Cliente", "rol_id": 1, "agencia_id": self.e.ag_a.id, "tipo_documento": "CC",
            "numero_documento": "99999", "correo": "nuevo@rt.co", "telefono": "3001234567", "contrasena": "clave1234",
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.json()["token"])
        self.assertTrue(r.json()["refresh"])
        self.assertEqual(r.json()["rol_id"], 4)
        self.assertEqual(r.json()["usuario"]["correo"], "nuevo@rt.co")
        nuevo = Usuario.objects.get(correo="nuevo@rt.co")
        self.assertEqual(nuevo.rol_id, 4)
        self.assertTrue(nuevo.contrasena.startswith("pbkdf2_sha256$"))

    def test_registro_duplicado_400(self):
        r = APIClient().post("/api/usuario/", {
            "nombre_completo": "Nuevo Cliente", "numero_documento": "7777777", "correo": self.e.cliente.correo,
            "telefono": "3001234567", "contrasena": "clave1234",
        }, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Ya existe", r.json()["message"])

    def test_registro_valida_datos(self):
        valido = {"nombre_completo": "Nuevo Cliente", "numero_documento": "1234567", "correo": "nuevo@rt.co",
                  "telefono": "3001234567", "contrasena": "clave1234"}
        malos = [
            {"nombre_completo": ""},
            {"correo": "no-es-correo"},
            {"numero_documento": "12ab567"},
            {"numero_documento": "1234"},
            {"contrasena": "corta12"},
            {"telefono": "12"},
        ]
        for cambio in malos:
            r = APIClient().post("/api/usuario/", {**valido, **cambio}, format="json")
            self.assertEqual(r.status_code, 400, cambio)
            self.assertTrue(r.json()["message"])
        self.assertFalse(Usuario.objects.filter(correo="nuevo@rt.co").exists())
        self.assertEqual(APIClient().post("/api/usuario/", valido, format="json").status_code, 201)

    def test_confirmar_clave_minimo_8(self):
        RecuperarContrasena.objects.create(usuario=self.e.cliente, token_hash=hash_valor("tok"),
                                           codigo_hash=hash_valor("123456"))
        corta = APIClient().post("/api/password/reset/confirmar/", {"token": "tok", "contrasena": "corta12"},
                                 format="json")
        self.assertEqual(corta.status_code, 400)
        ok = APIClient().post("/api/password/reset/confirmar/", {"token": "tok", "contrasena": "clave1234"},
                              format="json")
        self.assertEqual(ok.status_code, 200)

    def test_nadie_cambia_clave_ni_rol_ajeno(self):
        c = Escenario.cliente_http(self.e.cond_a)
        r = c.put(f"/api/usuario/{self.e.cliente.id}/", {"rol_id": 1, "contrasena": "hack"}, format="json")
        self.assertEqual(r.status_code, 403)
        self.e.cliente.refresh_from_db()
        self.assertEqual(self.e.cliente.rol_id, 4)
        self.assertEqual(APIClient().put(f"/api/usuario/{self.e.cliente.id}/", {"rol_id": 1}, format="json").status_code, 401)

    def test_no_se_sube_su_propio_rol(self):
        c = Escenario.cliente_http(self.e.cond_a)
        self.assertEqual(c.put(f"/api/usuario/{self.e.cond_a.id}/", {"rol_id": 1}, format="json").status_code, 403)
        self.assertEqual(c.put(f"/api/usuario/{self.e.cond_a.id}/", {"telefono": "300"}, format="json").status_code, 200)

    def test_admin_limites(self):
        a = Escenario.cliente_http(self.e.admin_a)
        crear_admin = a.post("/api/usuario/", {
            "nombre_completo": "X", "rol_id": 2, "agencia_id": self.e.ag_a.id, "numero_documento": "555",
            "correo": "x@rt.co", "telefono": "1", "contrasena": "abc123"}, format="json")
        self.assertEqual(crear_admin.status_code, 403)
        otra_agencia = a.post("/api/usuario/", {
            "nombre_completo": "X", "rol_id": 3, "agencia_id": self.e.ag_b.id, "numero_documento": "556",
            "correo": "y@rt.co", "telefono": "1", "contrasena": "abc123"}, format="json")
        self.assertEqual(otra_agencia.status_code, 403)
        self.assertEqual(a.get(f"/api/usuario/{self.e.cond_b.id}/").status_code, 403)
        correos = {u["correo"] for u in a.get("/api/usuario/").json()}
        self.assertIn(self.e.cond_a.correo, correos)
        self.assertNotIn(self.e.cond_b.correo, correos)
        self.assertEqual(Escenario.cliente_http(self.e.cliente).get("/api/usuario/").status_code, 403)

    def test_cambio_de_correo_mantiene_sesion(self):
        c = Escenario.cliente_http(self.e.cliente)
        self.assertEqual(c.put(f"/api/usuario/{self.e.cliente.id}/", {"correo": "nuevo.correo@rt.co"}, format="json").status_code, 200)
        self.assertEqual(c.get("/api/reserva/").status_code, 200)


class AsignacionesTest(TestCase):
    def setUp(self):
        self.e = Escenario()
        Bus_Conductor.objects.create(bus=self.e.bus_a, conductor=self.e.cond_a)
        Bus_Conductor.objects.create(bus=self.e.bus_b, conductor=self.e.cond_b)

    def test_conductor_solo_ve_las_suyas(self):
        c = Escenario.cliente_http(self.e.cond_a)
        lista = c.get("/api/bus-conductor/").json()
        self.assertEqual([x["bus_id"] for x in lista], [self.e.bus_a.id])
        # aunque pida las de otro conductor
        self.assertEqual(c.get(f"/api/bus-conductor/?conductor_id={self.e.cond_b.id}").json(), [])

    def test_admin_de_otra_agencia_no_asigna(self):
        b = Escenario.cliente_http(self.e.admin_b)
        r = b.post("/api/bus-conductor/", {"bus_id": self.e.bus_a2.id, "conductor_id": self.e.cond_a.id}, format="json")
        self.assertEqual(r.status_code, 403)
        a = Escenario.cliente_http(self.e.admin_a)
        r = a.post("/api/bus-conductor/", {"bus_id": self.e.bus_a2.id, "conductor_id": self.e.cond_a.id}, format="json")
        self.assertEqual(r.status_code, 201)


class ReservasPagosTest(TestCase):
    def setUp(self):
        self.e = Escenario()
        self.salida = Viaje.objects.create(paquete=self.e.paq_a, bus=self.e.bus_a,
                                           fecha=hoy_colombia() + timedelta(days=7), hora="06:30")

    def test_cliente_reserva_para_si_y_pago_queda_pendiente(self):
        c = Escenario.cliente_http(self.e.cliente)
        r = c.post("/api/reserva/", {"fecha_reserva": "2026-10-20", "usuario_id": self.e.otro_cliente.id,
                                     "paquete_id": self.e.paq_a.id, "viaje_id": self.salida.id,
                                     "estado": "pagada"}, format="json")
        self.assertEqual(r.status_code, 201)
        reserva = Reserva.objects.get(id=r.json()["id"])
        self.assertEqual(reserva.usuario_id, self.e.cliente.id)
        self.assertEqual(reserva.estado, "pendiente")
        silla = Asiento.objects.create(numero_asiento=1, tipo_bus=self.e.tipo_a)
        c.post("/api/asientoreserva/", {"asiento_id": silla.id, "reserva_id": reserva.id}, format="json")
        # Fase 2: el cliente sube la foto del comprobante (multipart); el estado lo ignora el servidor.
        with override_settings(MEDIA_ROOT=tempfile.mkdtemp()):
            p = c.post("/api/pago/", {"precio": "1000", "reserva_id": reserva.id, "fecha_pago": "2026-10-20",
                                      "referencia": "x.jpg", "estado": "aprobado", "comprobante": imagen()})
        self.assertEqual(p.status_code, 200, p.content)
        self.assertEqual(Pago.objects.get(reserva=reserva).estado, "pendiente")
        pago = Pago.objects.get(reserva=reserva)
        self.assertEqual(c.put(f"/api/pago/{pago.id}/", {"estado": "aprobado"}, format="json").status_code, 403)
        self.assertEqual(Escenario.cliente_http(self.e.admin_b).put(f"/api/pago/{pago.id}/", {"estado": "aprobado"}, format="json").status_code, 403)
        self.assertEqual(Escenario.cliente_http(self.e.admin_a).put(f"/api/pago/{pago.id}/", {"estado": "aprobado"}, format="json").status_code, 200)

    def test_no_ve_reservas_ajenas(self):
        ajena = Reserva.objects.create(fecha_reserva="2026-10-20", usuario=self.e.otro_cliente, paquete=self.e.paq_a)
        c = Escenario.cliente_http(self.e.cliente)
        self.assertEqual(c.get(f"/api/reserva/{ajena.id}/").status_code, 403)
        self.assertEqual(c.get(f"/api/reserva/usuario/{self.e.otro_cliente.id}/").status_code, 403)
        self.assertEqual(c.get("/api/reserva/").json(), [])
        self.assertEqual(c.delete(f"/api/reserva/{ajena.id}/").status_code, 403)
        ids_admin_b = [r["id"] for r in Escenario.cliente_http(self.e.admin_b).get("/api/reserva/").json()]
        self.assertNotIn(ajena.id, ids_admin_b)

    def test_conductor_de_otra_agencia_no_aborda_ni_lee(self):
        Reserva.objects.create(fecha_reserva="2026-10-20", usuario=self.e.cliente, paquete=self.e.paq_a)
        b = Escenario.cliente_http(self.e.cond_b)
        self.assertEqual(b.get(f"/api/paquete/{self.e.paq_a.id}/pasajeros/").status_code, 403)
        self.assertEqual(b.post(f"/api/paquete/{self.e.paq_a.id}/abordar/", {"codigo": "RT-1"}, format="json").status_code, 403)
        self.assertEqual(b.post("/api/gps/", {"paquete_id": self.e.paq_a.id, "lat": 1, "lng": 1}, format="json").status_code, 403)

    def test_chat_aislado_por_paquete(self):
        ChatMensaje.objects.create(paquete=self.e.paq_a, usuario=self.e.cond_a, texto="hola A")
        ChatMensaje.objects.create(paquete=self.e.paq_b, usuario=self.e.cond_b, texto="hola B")
        Reserva.objects.create(fecha_reserva="2026-10-20", usuario=self.e.cliente, paquete=self.e.paq_a)
        c = Escenario.cliente_http(self.e.cliente)
        self.assertEqual([m["texto"] for m in c.get(f"/api/chat/?paquete_id={self.e.paq_a.id}").json()], ["hola A"])
        self.assertEqual(c.get(f"/api/chat/?paquete_id={self.e.paq_b.id}").status_code, 403)
        self.assertEqual(c.get("/api/chat/").status_code, 400)
        enviado = c.post("/api/chat/", {"paquete_id": self.e.paq_a.id, "usuario_id": self.e.cond_a.id, "texto": "x"}, format="json")
        self.assertEqual(enviado.status_code, 201)
        self.assertEqual(ChatMensaje.objects.get(texto="x").usuario_id, self.e.cliente.id)


from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class MigracionContrasenasTest(TransactionTestCase):
    def tearDown(self):
        # Deja la base con TODAS las migraciones: las pruebas que vienen después necesitan las tablas nuevas.
        ejecutor = MigrationExecutor(connection)
        ejecutor.loader.build_graph()
        ejecutor.migrate(ejecutor.loader.graph.leaf_nodes())

    def test_cifra_las_planas_y_respeta_las_cifradas(self):
        e = MigrationExecutor(connection)
        e.migrate([("usuarios", "0006_merge_usuarioagencia_recuperarcontrasena")])
        viejas = e.loader.project_state([("usuarios", "0006_merge_usuarioagencia_recuperarcontrasena")]).apps
        Rol, UsuarioViejo = viejas.get_model("usuarios", "Rol"), viejas.get_model("usuarios", "Usuario")
        rol = Rol.objects.create(rol="cliente")
        plano = UsuarioViejo.objects.create(nombre_completo="p", rol_id=rol.id, tipo_documento="CC", numero_documento="1",
                                       correo="p@rt.co", telefono="1", contrasena="plana1")
        vacio = UsuarioViejo.objects.create(nombre_completo="g", rol_id=rol.id, tipo_documento="google", numero_documento="2",
                                       correo="g@rt.co", telefono="1", contrasena="")
        e = MigrationExecutor(connection)
        e.loader.build_graph()
        e.migrate([("usuarios", "0007_cifrar_contrasenas")])
        nuevas = e.loader.project_state([("usuarios", "0007_cifrar_contrasenas")]).apps.get_model("usuarios", "Usuario")
        plano, vacio = nuevas.objects.get(id=plano.id), nuevas.objects.get(id=vacio.id)
        self.assertTrue(check_password("plana1", plano.contrasena))
        self.assertEqual(vacio.contrasena, "")



class SuspensionTest(TestCase):
    def setUp(self):
        self.e = Escenario()

    def test_suspendido_no_entra_y_pierde_su_sesion(self):
        sesion = Escenario.cliente_http(self.e.cond_a)
        admin = Escenario.cliente_http(self.e.admin_a)
        self.assertEqual(admin.put(f"/api/usuario/{self.e.cond_a.id}/", {"activo": False}, format="json").status_code, 200)
        self.assertEqual(sesion.get("/api/viaje/").status_code, 401)  # token borrado
        r = APIClient().post("/api/login/", {"correo": self.e.cond_a.correo, "contrasena": CLAVE}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertFalse(Usuario.objects.get(id=self.e.cond_a.id).activo)
        lista = {u["id"]: u["activo"] for u in admin.get("/api/usuario/").json()}
        self.assertFalse(lista[self.e.cond_a.id])
        self.assertEqual(admin.put(f"/api/usuario/{self.e.cond_a.id}/", {"activo": True}, format="json").status_code, 200)
        self.assertEqual(APIClient().post("/api/login/", {"correo": self.e.cond_a.correo, "contrasena": CLAVE}, format="json").status_code, 200)

    def test_nadie_se_suspende_solo_ni_suspende_ajenos(self):
        c = Escenario.cliente_http(self.e.cond_a)
        self.assertEqual(c.put(f"/api/usuario/{self.e.cond_a.id}/", {"activo": False}, format="json").status_code, 403)
        b = Escenario.cliente_http(self.e.admin_b)
        self.assertEqual(b.put(f"/api/usuario/{self.e.cond_a.id}/", {"activo": False}, format="json").status_code, 403)


from django.core.files.uploadedfile import SimpleUploadedFile

from usuarios.models import Usuario

MEDIA_LICENCIAS = tempfile.mkdtemp()


def pdf(nombre="licencia.pdf", contenido=b"%PDF-1.4\n%prueba\n"):
    return SimpleUploadedFile(nombre, contenido, content_type="application/pdf")


@override_settings(MEDIA_ROOT=MEDIA_LICENCIAS)
class LicenciaPdfTest(TestCase):
    """Sub-paso 1D: el admin de la agencia sube la licencia del conductor en PDF (máx. 5 MB)."""

    def setUp(self):
        self.e = Escenario()
        self.admin = Escenario.cliente_http(self.e.admin_a)

    def crear(self, c, archivo, rol=3, documento="900100", correo="nuevo@rt.co"):
        return c.post("/api/usuario/", {
            "nombre_completo": "Nuevo Conductor", "agencia_id": self.e.ag_a.id, "rol_id": rol,
            "tipo_documento": "CC", "numero_documento": documento, "correo": correo, "telefono": "3001234567",
            "contrasena": "clave12345", "licencia": "LIC-123", "licencia_pdf": archivo,
        }, format="multipart")

    def test_admin_crea_conductor_con_pdf_y_ve_la_url(self):
        r = self.crear(self.admin, pdf())
        self.assertEqual(r.status_code, 200, r.content)
        nuevo = Usuario.objects.get(id=r.json()["id"])
        self.assertTrue(nuevo.licencia_pdf.name.startswith("licencias/licencia_"))
        self.assertNotIn("900100", nuevo.licencia_pdf.name)  # nombre aleatorio
        datos = self.admin.get(f"/api/usuario/{nuevo.id}/").json()
        self.assertTrue(datos["tiene_licencia_pdf"])
        self.assertTrue(datos["licencia_pdf_url"].startswith("http://testserver/media/licencias/"))
        self.assertEqual(datos["licencia"], "LIC-123")

    def test_valida_pdf_y_tamano(self):
        self.assertEqual(self.crear(self.admin, pdf("foto.png")).status_code, 400)
        self.assertEqual(self.crear(self.admin, pdf(contenido=b"no soy un pdf")).status_code, 400)
        grande = pdf(contenido=b"%PDF-" + b"0" * (5 * 1024 * 1024))
        self.assertEqual(self.crear(self.admin, grande).status_code, 400)
        self.assertEqual(self.crear(self.admin, pdf(), rol=4).status_code, 400)  # cliente no lleva licencia
        self.assertFalse(Usuario.objects.filter(numero_documento="900100").exists())

    def test_registro_publico_no_sube_pdf(self):
        self.assertEqual(self.crear(APIClient(), pdf()).status_code, 403)

    def test_solo_admin_de_su_agencia_reemplaza_y_ve_el_pdf(self):
        url = f"/api/usuario/{self.e.cond_a.id}/"
        self.assertEqual(self.admin.put(url, {"licencia_pdf": pdf()}, format="multipart").status_code, 200)
        primero = Usuario.objects.get(id=self.e.cond_a.id).licencia_pdf.name
        self.assertEqual(self.admin.put(url, {"licencia_pdf": pdf()}, format="multipart").status_code, 200)
        segundo = Usuario.objects.get(id=self.e.cond_a.id).licencia_pdf.name
        self.assertNotEqual(primero, segundo)
        storage = Usuario._meta.get_field("licencia_pdf").storage
        self.assertFalse(storage.exists(primero))  # el anterior se borró
        # el propio conductor no sube ni ve la URL; otra agencia tampoco
        conductor = Escenario.cliente_http(self.e.cond_a)
        self.assertEqual(conductor.put(url, {"licencia_pdf": pdf()}, format="multipart").status_code, 403)
        self.assertIsNone(conductor.get(url).json()["licencia_pdf_url"])
        self.assertTrue(conductor.get(url).json()["tiene_licencia_pdf"])
        b = Escenario.cliente_http(self.e.admin_b)
        self.assertEqual(b.put(url, {"licencia_pdf": pdf()}, format="multipart").status_code, 403)
        sup = Escenario.cliente_http(self.e.super).get(url).json()
        self.assertIsNotNone(sup["licencia_pdf_url"])

    def test_editar_en_json_sigue_funcionando_y_borrar_limpia_el_pdf(self):
        url = f"/api/usuario/{self.e.cond_a.id}/"
        self.assertEqual(self.admin.put(url, {"telefono": "3110000000"}, format="json").status_code, 200)
        self.admin.put(url, {"licencia_pdf": pdf()}, format="multipart")
        nombre = Usuario.objects.get(id=self.e.cond_a.id).licencia_pdf.name
        self.assertEqual(self.admin.delete(url).status_code, 200)
        self.assertFalse(Usuario._meta.get_field("licencia_pdf").storage.exists(nombre))
