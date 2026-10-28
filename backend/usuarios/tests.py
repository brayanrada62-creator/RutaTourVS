from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from buses.models import Bus_Conductor
from pagos.models import Pago
from reservas.models import ChatMensaje, Reserva
from usuarios.models import Usuario
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

    def test_acepta_prefijo_bearer_y_token(self):
        r = APIClient().post("/api/login/", {"correo": self.e.cliente.correo, "contrasena": CLAVE}, format="json")
        access = r.json()["token"]
        for prefijo in ("Bearer", "Token"):
            c = APIClient()
            c.credentials(HTTP_AUTHORIZATION=f"{prefijo} {access}")
            self.assertEqual(c.get("/api/usuario/perfil/").status_code, 200, prefijo)

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
            "nombre_completo": "N", "rol_id": 1, "agencia_id": self.e.ag_a.id, "tipo_documento": "CC",
            "numero_documento": "999", "correo": "nuevo@rt.co", "telefono": "1", "contrasena": "abc123",
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
            "nombre_completo": "N", "numero_documento": "777", "correo": self.e.cliente.correo,
            "telefono": "1", "contrasena": "abc123",
        }, format="json")
        self.assertEqual(r.status_code, 400)

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

    def test_cliente_reserva_para_si_y_pago_queda_pendiente(self):
        c = Escenario.cliente_http(self.e.cliente)
        r = c.post("/api/reserva/", {"fecha_reserva": "2026-10-20", "usuario_id": self.e.otro_cliente.id,
                                     "paquete_id": self.e.paq_a.id, "estado": "pagada"}, format="json")
        self.assertEqual(r.status_code, 201)
        reserva = Reserva.objects.get(id=r.json()["id"])
        self.assertEqual(reserva.usuario_id, self.e.cliente.id)
        self.assertEqual(reserva.estado, "pendiente")
        p = c.post("/api/pago/", {"precio": "1000", "reserva_id": reserva.id, "fecha_pago": "2026-10-20",
                                  "referencia": "x.jpg", "estado": "aprobado"}, format="json")
        self.assertEqual(p.status_code, 200)
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
