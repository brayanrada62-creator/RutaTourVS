from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import User
import json
from unittest.mock import patch

from django.core.mail import send_mail
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

import tempfile
from datetime import timedelta

from django.test import override_settings
from django.utils import timezone

from buses.models import Asiento, Bus_Conductor, Viaje
from buses.views import hoy_colombia
from destinos.models import Departamento, Destino, Hospedaje, HospedajeDestino, ImagenDestino
from pagos.models import Pago
from paquetes.models import Itinerario, Paquete, PaqueteDestino
from reservas.models import ChatMensaje, Reserva
from usuarios.models import Agencia, RecuperarContrasena, Usuario, UsuarioAgencia
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
        self.assertEqual(malo.json()["campo"], "contrasena")
        self.assertEqual(malo.json()["message"], "La contraseña es incorrecta")

    def test_login_dice_que_campo_esta_mal(self):
        c = APIClient()
        r = c.post("/api/login/", {"correo": "nadie@rt.co", "contrasena": CLAVE}, format="json")
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()["campo"], "correo")
        self.assertEqual(r.json()["message"], "Correo no registrado")
        # El correo se compara sin importar mayúsculas: solo falla la contraseña.
        r = c.post("/api/login/", {"correo": self.e.cliente.correo.upper(), "contrasena": "otra-clave"}, format="json")
        self.assertEqual((r.status_code, r.json()["campo"]), (401, "contrasena"))
        r = c.post("/api/login/", {"correo": "", "contrasena": CLAVE}, format="json")
        self.assertEqual((r.status_code, r.json()["campo"]), (400, "correo"))
        r = c.post("/api/login/", {"correo": self.e.cliente.correo, "contrasena": ""}, format="json")
        self.assertEqual((r.status_code, r.json()["campo"]), (400, "contrasena"))

    def test_suspendido_con_clave_mala_no_revela_la_suspension(self):
        Usuario.objects.filter(id=self.e.cliente.id).update(activo=False)
        c = APIClient()
        r = c.post("/api/login/", {"correo": self.e.cliente.correo, "contrasena": "mala"}, format="json")
        self.assertEqual((r.status_code, r.json()["campo"]), (401, "contrasena"))
        r = c.post("/api/login/", {"correo": self.e.cliente.correo, "contrasena": CLAVE}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertIn("suspendido", r.json()["message"])

    def test_superadmin_suspende_administradores_y_clientes_sin_agencia(self):
        sup = Escenario.cliente_http(self.e.super)
        for objetivo in (self.e.admin_a, self.e.cliente):  # cliente = registrado desde la app, sin agencia
            self.assertEqual(sup.put(f"/api/usuario/{objetivo.id}/", {"activo": False}, format="json").status_code, 200)
            r = APIClient().post("/api/login/", {"correo": objetivo.correo, "contrasena": CLAVE}, format="json")
            self.assertEqual(r.status_code, 403, objetivo.correo)
            self.assertEqual(sup.put(f"/api/usuario/{objetivo.id}/", {"activo": True}, format="json").status_code, 200)
        # Un admin no puede suspender a otro admin ni a un cliente sin agencia (no es de su agencia).
        admin = Escenario.cliente_http(self.e.admin_a)
        for objetivo in (self.e.admin_b, self.e.cliente):
            self.assertEqual(admin.put(f"/api/usuario/{objetivo.id}/", {"activo": False}, format="json").status_code, 403)
        self.assertTrue(Usuario.objects.get(id=self.e.cliente.id).activo)

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

    def test_login_y_perfil_traen_el_nombre_de_la_agencia(self):
        cliente_agencia = self.e.usuario("cli.agencia@rt.co", 4, self.e.ag_a)
        for usuario, esperado in ((cliente_agencia, self.e.ag_a.nombre), (self.e.cliente, None)):
            r = APIClient().post("/api/login/", {"correo": usuario.correo, "contrasena": CLAVE}, format="json")
            self.assertEqual(r.json()["agencia_nombre"], esperado, usuario.correo)
            self.assertEqual(r.json()["usuario"]["agencia_nombre"], esperado)
            perfil = Escenario.cliente_http(usuario).get("/api/usuario/perfil/").json()
            self.assertEqual(perfil["agencia_nombre"], esperado)

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

    def test_cuenta_bancaria_solo_con_sesion(self):
        admin = Escenario.cliente_http(self.e.admin_a)
        r = admin.put(f"/api/agencia/{self.e.ag_a.id}/", {"banco": "Banco", "tipo_cuenta": "Ahorros",
                                                          "numero_cuenta": "123", "titular": "Agencia"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        cliente = Escenario.cliente_http(self.e.cliente)
        mia = next(a for a in cliente.get("/api/agencia/").json() if a["id"] == self.e.ag_a.id)
        self.assertEqual(mia["numero_cuenta"], "123")
        self.assertEqual(mia["titular"], "Agencia")
        for agencia in APIClient().get("/api/agencia/").json():
            self.assertNotIn("numero_cuenta", agencia)
        self.assertNotIn("numero_cuenta", APIClient().get(f"/api/agencia/{self.e.ag_a.id}/").json())


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
            {"telefono": "6011234567"},   # fijo de Bogotá: solo se aceptan celulares
            {"telefono": "300123456"},    # 9 dígitos
            {"telefono": "30012345678"},  # 11 dígitos
            {"telefono": "300-123-4567"},
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
        self.assertEqual(c.put(f"/api/usuario/{self.e.cond_a.id}/", {"telefono": "300"}, format="json").status_code, 400)
        self.assertEqual(c.put(f"/api/usuario/{self.e.cond_a.id}/", {"telefono": "3001234567"}, format="json").status_code, 200)

    def test_celular_del_personal_y_telefono_antiguo(self):
        sup = Escenario.cliente_http(self.e.super)
        base = {"nombre_completo": "Cond", "rol_id": 3, "agencia_id": self.e.ag_a.id, "tipo_documento": "CC",
                "numero_documento": "8080808", "correo": "cond.nuevo@rt.co", "contrasena": "clave1234"}
        r = sup.post("/api/usuario/", {**base, "telefono": "6011234567"}, format="json")
        self.assertEqual((r.status_code, r.json()["campo"]), (400, "telefono"))
        self.assertFalse(Usuario.objects.filter(correo="cond.nuevo@rt.co").exists())
        self.assertEqual(sup.post("/api/usuario/", {**base, "telefono": "3109876543"}, format="json").status_code, 200)
        # El escenario tiene teléfono "1" (formato antiguo): editar otros datos enviándolo igual no falla.
        r = sup.put(f"/api/usuario/{self.e.cond_a.id}/", {"nombre_completo": "Nuevo", "telefono": "1"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(sup.put(f"/api/usuario/{self.e.cond_a.id}/", {"telefono": "2"}, format="json").status_code, 400)

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
        # RUT-60: por paquete (reserva sin salida) el chat es solo de lectura.
        sin_salida = c.post("/api/chat/", {"paquete_id": self.e.paq_a.id, "texto": "x"}, format="json")
        self.assertEqual(sin_salida.status_code, 409)
        # Con su salida sí escribe, y el autor lo pone el servidor aunque el body diga otro usuario.
        Reserva.objects.create(fecha_reserva="2026-10-20", usuario=self.e.cliente, paquete=self.e.paq_a, viaje=self.salida)
        enviado = c.post("/api/chat/", {"viaje_id": self.salida.id, "usuario_id": self.e.cond_a.id, "texto": "x"},
                         format="json")
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



class SesionRenovableTest(TestCase):
    """Los 7 días del refresh cuentan desde el último uso (rotación), no desde el login."""

    def setUp(self):
        self.e = Escenario()
        login = APIClient().post("/api/login/", {"correo": self.e.cond_a.correo, "contrasena": CLAVE}, format="json")
        self.refresh = login.json()["refresh"]

    def renovar(self, refresh):
        return APIClient().post("/api/token/refresh/", {"refresh": refresh}, format="json")

    def test_renovar_entrega_un_refresh_nuevo_que_vence_despues(self):
        with patch("rest_framework_simplejwt.tokens.aware_utcnow",
                   return_value=timezone.now() + timedelta(days=6)):
            r = self.renovar(self.refresh)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["access"])
        nuevo = r.json()["refresh"]
        self.assertNotEqual(nuevo, self.refresh)
        vence_viejo = RefreshToken(self.refresh, verify=False)["exp"]
        vence_nuevo = RefreshToken(nuevo, verify=False)["exp"]  # emitido "dentro de 6 días"
        self.assertGreater(vence_nuevo - vence_viejo, 5 * 24 * 3600)  # ~6 días más

    def test_apps_viejas_que_no_guardan_el_nuevo_siguen_funcionando(self):
        self.assertEqual(self.renovar(self.refresh).status_code, 200)
        self.assertEqual(self.renovar(self.refresh).status_code, 200)

    def test_suspender_revoca_tambien_los_refresh_renovados(self):
        nuevo = self.renovar(self.refresh).json()["refresh"]
        admin = Escenario.cliente_http(self.e.admin_a)
        self.assertEqual(admin.put(f"/api/usuario/{self.e.cond_a.id}/", {"activo": False}, format="json").status_code, 200)
        self.assertEqual(self.renovar(nuevo).status_code, 401)
        self.assertEqual(self.renovar(self.refresh).status_code, 401)


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


class SuperadminAgenciasTest(TestCase):
    """Paso 4B: el superadmin administra cualquier agencia; el admin queda limitado a la suya."""

    def setUp(self):
        self.e = e = Escenario()
        self.sup = Escenario.cliente_http(e.super)
        self.adm = Escenario.cliente_http(e.admin_a)
        self.anonimo = Escenario.cliente_http()
        fecha = timezone.localdate() + timedelta(days=5)
        self.viaje_a = Viaje.objects.create(paquete=e.paq_a, bus=e.bus_a, fecha=fecha, hora="06:00")
        self.viaje_b = Viaje.objects.create(paquete=e.paq_b, bus=e.bus_b, fecha=fecha, hora="06:00")
        self.reserva_a = self.reservar(e.paq_a, self.viaje_a)
        self.reserva_b = self.reservar(e.paq_b, self.viaje_b)
        self.pago_b = Pago.objects.create(reserva=self.reserva_b, precio=100, fecha_pago=timezone.now(),
                                          referencia="REF-B", estado="aprobado")
        departamento = Departamento.objects.create(nombre="Meta")
        self.destino_b = Destino.objects.create(nombre="Solo B", departamento=departamento, descripcion="d")
        self.destino_libre = Destino.objects.create(nombre="Libre", departamento=departamento, descripcion="d")
        PaqueteDestino.objects.create(paquete=e.paq_b, destino=self.destino_b)
        self.hotel_b = Hospedaje.objects.create(nombre="Hotel B", direccion="d", telefono="1", descripcion="d")
        self.hotel_b.destinos.add(self.destino_b)
        self.parada_b = Itinerario.objects.create(paquete=e.paq_b, titulo="Parada B", dia=1, descripcion="d",
                                                  hora="08:00", lugar="Lugar B")

    def reservar(self, paquete, viaje):
        return Reserva.objects.create(usuario=self.e.cliente, paquete=paquete, viaje=viaje,
                                      fecha_reserva=timezone.now(), estado="confirmada")

    def ids(self, cliente, ruta):
        respuesta = cliente.get(ruta)
        self.assertEqual(respuesta.status_code, 200, ruta)
        return {fila["id"] for fila in respuesta.json()}

    # ---------- Listados con ?agencia_id= ----------
    def test_super_filtra_por_agencia_y_sin_filtro_ve_todo(self):
        e, b = self.e, self.e.ag_b.id
        casos = {
            "bus": (e.bus_a.id, e.bus_b.id), "tipobus": (e.tipo_a.id, e.tipo_b.id),
            "paquete": (e.paq_a.id, e.paq_b.id), "viaje": (self.viaje_a.id, self.viaje_b.id),
            "reserva": (self.reserva_a.id, self.reserva_b.id), "usuario": (e.cond_a.id, e.cond_b.id),
        }
        for ruta, (de_a, de_b) in casos.items():
            con_filtro = self.ids(self.sup, f"/api/{ruta}/?agencia_id={b}")
            self.assertIn(de_b, con_filtro, ruta)
            self.assertNotIn(de_a, con_filtro, ruta)
            self.assertTrue({de_a, de_b} <= self.ids(self.sup, f"/api/{ruta}/"), ruta)
        self.assertEqual(self.ids(self.sup, f"/api/pago/?agencia_id={b}"), {self.pago_b.id})
        self.assertEqual(self.ids(self.sup, f"/api/pago/?agencia_id={e.ag_a.id}"), set())
        self.assertEqual(self.ids(self.sup, f"/api/destino/?agencia_id={b}"), {self.destino_b.id})
        self.assertEqual(self.ids(self.sup, f"/api/hospedaje/?agencia_id={b}"), {self.hotel_b.id})
        self.assertEqual(self.ids(self.sup, f"/api/itinerario/?agencia_id={b}"), {self.parada_b.id})

    def test_admin_ignora_agencia_id_ajeno(self):
        e, b = self.e, self.e.ag_b.id
        for ruta, propio, ajeno in (("bus", e.bus_a.id, e.bus_b.id), ("tipobus", e.tipo_a.id, e.tipo_b.id),
                                    ("paquete", e.paq_a.id, e.paq_b.id), ("viaje", self.viaje_a.id, self.viaje_b.id),
                                    ("reserva", self.reserva_a.id, self.reserva_b.id),
                                    ("usuario", e.cond_a.id, e.cond_b.id)):
            for url in (f"/api/{ruta}/", f"/api/{ruta}/?agencia_id={b}"):
                visibles = self.ids(self.adm, url)
                self.assertIn(propio, visibles, url)
                self.assertNotIn(ajeno, visibles, url)
        self.assertEqual(self.ids(self.adm, f"/api/pago/?agencia_id={b}"), set())

    def test_admin_no_ve_detalle_ni_busqueda_de_otra_agencia(self):
        e = self.e
        self.assertEqual(self.adm.get(f"/api/paquete/{e.paq_b.id}/").status_code, 404)
        self.assertEqual(self.adm.get(f"/api/agencia/{e.ag_b.id}/").status_code, 403)
        self.assertEqual(self.ids(self.adm, "/api/agencia/"), {e.ag_a.id})
        self.assertEqual(self.ids(self.adm, "/api/itinerario/"), set())
        self.assertEqual(self.adm.get(f"/api/itinerario/{self.parada_b.id}/").status_code, 404)
        self.assertEqual(self.adm.get("/api/itinerario/titulo/Parada/").json(), [])
        self.assertEqual(self.adm.get("/api/itinerario/lugar/Lugar/").json(), [])
        self.assertEqual(self.adm.get("/api/buscar/?search=PB").json()["paquetes"], [])

    def test_admin_no_modifica_otra_agencia_y_super_si(self):
        e = self.e
        datos = {"nombre": "Nuevo", "nit": "9", "direccion": "x", "telefono": "3001112233", "correo": "n@n.co"}
        self.assertEqual(self.adm.put(f"/api/agencia/{e.ag_b.id}/", datos, format="json").status_code, 403)
        self.assertEqual(self.adm.delete(f"/api/paquete/{e.paq_b.id}/").status_code, 403)
        self.assertEqual(self.adm.delete(f"/api/viaje/{self.viaje_b.id}/").status_code, 403)
        self.assertEqual(self.adm.delete(f"/api/usuario/{e.cond_b.id}/").status_code, 403)
        self.assertEqual(self.sup.put(f"/api/agencia/{e.ag_b.id}/", datos, format="json").status_code, 200)
        self.assertEqual(Agencia.objects.get(id=e.ag_b.id).nombre, "Nuevo")
        self.assertEqual(self.sup.delete(f"/api/viaje/{self.viaje_b.id}/").status_code, 409)  # tiene reserva
        self.assertEqual(self.sup.delete(f"/api/usuario/{e.cond_b.id}/").status_code, 200)

    def test_listados_que_daban_500(self):
        self.assertEqual(self.sup.get("/api/usuario/?rol_id=3").status_code, 200)
        self.assertEqual(self.sup.get("/api/usuario/?search=admin").status_code, 200)
        self.assertEqual(self.sup.get("/api/dashboard/resumen/").status_code, 403)
        self.assertEqual(self.adm.get("/api/dashboard/resumen/").status_code, 200)

    def test_pago_trae_agencia(self):
        self.assertEqual(self.sup.get(f"/api/pago/{self.pago_b.id}/").json()["agencia_id"], self.e.ag_b.id)

    # ---------- Datos de la agencia ----------
    def test_validacion_de_agencia(self):
        url = f"/api/agencia/{self.e.ag_b.id}/"
        self.assertEqual(self.sup.post("/api/agencia/", {}, format="json").status_code, 400)
        self.assertEqual(self.sup.put(url, {"nombre": ""}, format="json").status_code, 400)
        self.assertEqual(self.sup.put(url, {"correo": "malo"}, format="json").status_code, 400)
        r = self.sup.put(url, {"telefono": "555"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("10 dígitos", r.json()["message"])
        self.assertEqual(self.sup.put(url, {"telefono": "3155550000"}, format="json").status_code, 200)
        agencia = Agencia.objects.get(id=self.e.ag_b.id)
        self.assertEqual((agencia.telefono, agencia.nombre), ("3155550000", "B"))  # lo que no se envía se conserva

    def test_agencia_nueva_exige_celular_y_la_antigua_edita_sin_cambiarlo(self):
        datos = {"nombre": "Nueva", "nit": "777", "direccion": "d", "telefono": "6015551234", "correo": "n@rt.co"}
        self.assertEqual(self.sup.post("/api/agencia/", datos, format="json").status_code, 400)
        self.assertEqual(self.sup.post("/api/agencia/", {**datos, "telefono": "3015551234"}, format="json").status_code, 200)
        # ag_a tiene teléfono "1" (antiguo): el formulario lo reenvía al editar el nombre y no debe fallar.
        url = f"/api/agencia/{self.e.ag_a.id}/"
        self.assertEqual(self.sup.put(url, {"nombre": "A2", "telefono": "1"}, format="json").status_code, 200)
        self.assertEqual(Agencia.objects.get(id=self.e.ag_a.id).nombre, "A2")

    def test_eliminar_agencia_con_datos_responde_409_con_totales(self):
        respuesta = self.sup.delete(f"/api/agencia/{self.e.ag_b.id}/")
        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(respuesta.json()["totales"]["paquetes"], 1)
        self.assertEqual(respuesta.json()["totales"]["usuarios"], 2)
        self.assertTrue(Agencia.objects.filter(id=self.e.ag_b.id).exists())

    def test_agencia_con_solo_paquetes_no_se_borra_en_cascada(self):
        agencia = Agencia.objects.create(nombre="C", nit="3", direccion="d", telefono="3", correo="c@c.co")
        paquete = Paquete.objects.create(nombre="PC", agencia=agencia, descripcion="", duracion_estimada="1",
                                         fecha_creacion=timezone.now())
        self.assertEqual(self.sup.delete(f"/api/agencia/{agencia.id}/").status_code, 409)
        self.assertTrue(Paquete.objects.filter(id=paquete.id).exists())

    def test_eliminar_agencia_vacia(self):
        agencia = Agencia.objects.create(nombre="V", nit="4", direccion="d", telefono="4", correo="v@v.co")
        self.assertEqual(self.adm.delete(f"/api/agencia/{agencia.id}/").status_code, 403)
        self.assertEqual(self.sup.delete(f"/api/agencia/{agencia.id}/").status_code, 200)
        self.assertFalse(Agencia.objects.filter(id=agencia.id).exists())

    # ---------- Desactivar una agencia ----------
    def desactivar_b(self):
        respuesta = self.sup.put(f"/api/agencia/{self.e.ag_b.id}/", {"activo": False}, format="json")
        self.assertEqual(respuesta.status_code, 200)

    def test_solo_el_super_activa_o_desactiva(self):
        respuesta = self.adm.put(f"/api/agencia/{self.e.ag_a.id}/", {"activo": False}, format="json")
        self.assertEqual(respuesta.status_code, 403)
        self.assertTrue(Agencia.objects.get(id=self.e.ag_a.id).activo)

    def test_agencia_desactivada_bloquea_a_su_personal(self):
        admin_b = Escenario.cliente_http(self.e.admin_b)
        self.desactivar_b()
        self.assertEqual(admin_b.get("/api/usuario/").status_code, 401)  # el token ya emitido deja de servir
        renovar = self.anonimo.post("/api/token/refresh/", {"refresh": admin_b.refresh_token}, format="json")
        self.assertEqual(renovar.status_code, 401)
        for usuario in (self.e.admin_b, self.e.cond_b):
            login = self.anonimo.post("/api/login/", {"correo": usuario.correo, "contrasena": CLAVE}, format="json")
            self.assertEqual(login.status_code, 403)
        self.assertEqual(self.sup.put(f"/api/agencia/{self.e.ag_b.id}/", {"activo": True}, format="json").status_code, 200)
        Escenario.cliente_http(self.e.admin_b)  # reactivada: vuelve a entrar

    def test_personal_con_otra_agencia_activa_sigue_entrando(self):
        UsuarioAgencia.objects.create(usuario=self.e.admin_b, agencia=self.e.ag_a)
        self.desactivar_b()
        Escenario.cliente_http(self.e.admin_b)

    def test_agencia_desactivada_sale_del_catalogo_y_conserva_reservas(self):
        e = self.e
        self.desactivar_b()
        self.assertNotIn(e.ag_b.id, self.ids(self.anonimo, "/api/agencia/"))
        self.assertIn(e.ag_b.id, self.ids(self.sup, "/api/agencia/"))
        self.assertNotIn(e.paq_b.id, self.ids(self.anonimo, "/api/paquete/"))
        self.assertEqual(self.anonimo.get(f"/api/paquete/{e.paq_b.id}/").status_code, 404)
        self.assertEqual(self.anonimo.get("/api/buscar/?search=PB").json()["paquetes"], [])
        self.assertIn(e.paq_b.id, self.ids(self.sup, "/api/paquete/"))
        # El cliente que ya reservó conserva su reserva, el paquete y el itinerario.
        cliente = Escenario.cliente_http(e.cliente)
        self.assertIn(self.reserva_b.id, self.ids(cliente, "/api/reserva/"))
        self.assertEqual(cliente.get(f"/api/paquete/{e.paq_b.id}/").status_code, 200)
        self.assertIn(self.parada_b.id, self.ids(cliente, f"/api/itinerario/?paquete_id={e.paq_b.id}"))
        # ...pero nadie nuevo reserva allí.
        Paquete.objects.filter(id=e.paq_b.id).update(estado="activo")  # el 400 debe venir de la agencia
        otro = Escenario.cliente_http(e.otro_cliente)
        nueva = otro.post("/api/reserva/", {"paquete_id": e.paq_b.id, "viaje_id": self.viaje_b.id}, format="json")
        self.assertEqual(nueva.status_code, 400)
        self.assertNotIn(self.viaje_b.id, self.ids(otro, "/api/viaje/"))

    # ---------- Destinos y hoteles compartidos ----------
    def test_admin_no_toca_catalogo_usado_por_otra_agencia(self):
        d = self.destino_b.id
        self.assertEqual(self.adm.delete(f"/api/destino/{d}/").status_code, 409)
        self.assertEqual(self.adm.put(f"/api/destino/{d}/", {"nombre": "X"}, format="json").status_code, 409)
        self.assertEqual(self.adm.patch(f"/api/destino/{d}/", {"nombre": "X"}, format="json").status_code, 409)
        h = self.hotel_b.id
        self.assertEqual(self.adm.put(f"/api/hospedaje/{h}/", {"nombre": "X"}, format="json").status_code, 409)
        self.assertEqual(self.adm.delete(f"/api/hospedaje/{h}/").status_code, 409)
        relacion = HospedajeDestino.objects.get(hospedaje=self.hotel_b, destino=self.destino_b)
        self.assertEqual(self.adm.delete(f"/api/hospedaje-destino/{relacion.id}/").status_code, 409)
        imagen = ImagenDestino.objects.create(destino=self.destino_b, url_img="destinos/x.jpg", descripcion="i")
        self.assertEqual(self.adm.delete(f"/api/imagen/{imagen.id}/").status_code, 409)
        self.assertEqual(Destino.objects.get(id=d).nombre, "Solo B")
        self.assertEqual(Hospedaje.objects.get(id=h).nombre, "Hotel B")
        self.assertTrue(PaqueteDestino.objects.filter(paquete=self.e.paq_b, destino_id=d).exists())

    def test_catalogo_propio_o_libre_se_edita_y_el_super_siempre(self):
        libre = self.destino_libre.id
        self.assertEqual(self.adm.put(f"/api/destino/{libre}/", {"nombre": "Editado"}, format="json").status_code, 200)
        self.assertEqual(self.adm.delete(f"/api/destino/{libre}/").status_code, 200)
        self.assertEqual(self.sup.put(f"/api/destino/{self.destino_b.id}/", {"nombre": "Por super"}, format="json").status_code, 200)
        self.assertEqual(self.sup.delete(f"/api/hospedaje/{self.hotel_b.id}/").status_code, 200)

    def test_destino_inexistente_da_404(self):
        self.assertEqual(self.sup.delete("/api/destino/99999/").status_code, 404)
        self.assertEqual(self.sup.get("/api/destino/99999/").status_code, 404)


class ResumenAgenciasTest(TestCase):
    """Paso 4D: GET /dashboard/agencias/ con los totales de cada agencia, solo para el superadmin."""

    def setUp(self):
        self.e = e = Escenario()
        self.sup = Escenario.cliente_http(e.super)
        hoy = hoy_colombia()
        fuera_del_mes = hoy.replace(day=1) - timedelta(days=1)
        self.viaje_b = Viaje.objects.create(paquete=e.paq_b, bus=e.bus_b, fecha=hoy, hora="06:00")
        Viaje.objects.create(paquete=e.paq_b, bus=e.bus_b, fecha=fuera_del_mes, hora="06:00")
        aprobada = self.reservar()
        Pago.objects.create(reserva=aprobada, precio=100, fecha_pago=timezone.now(), estado="aprobado")
        Pago.objects.create(reserva=aprobada, precio=50, fecha_pago=timezone.now(), estado="aprobado")
        pendiente = self.reservar()
        Pago.objects.create(reserva=pendiente, precio=999, fecha_pago=timezone.now(), estado="pendiente")
        rechazada = self.reservar()
        Pago.objects.create(reserva=rechazada, precio=999, fecha_pago=timezone.now(), estado="rechazado")
        self.reservar(estado="cancelada")
        self.reservar(vence_en=timezone.now() - timedelta(minutes=1))  # venció y nadie la marcó

    def reservar(self, **extra):
        return Reserva.objects.create(usuario=self.e.cliente, paquete=self.e.paq_b, viaje=self.viaje_b,
                                      fecha_reserva=timezone.now(), **extra)

    def fila(self, agencia):
        respuesta = self.sup.get("/api/dashboard/agencias/")
        self.assertEqual(respuesta.status_code, 200)
        return next(f for f in respuesta.json() if f["id"] == agencia.id)

    def test_totales_de_la_agencia(self):
        fila = self.fila(self.e.ag_b)
        self.assertEqual(fila["nombre"], "B")
        self.assertTrue(fila["activo"])
        self.assertEqual(fila["buses"], 1)
        self.assertEqual(fila["conductores"], 1)
        self.assertEqual(fila["paquetes"], 1)
        self.assertEqual(fila["viajes_mes"], 1)  # el del mes pasado no cuenta
        self.assertEqual(fila["reservas"], 3)  # sin la cancelada ni la vencida
        self.assertEqual(float(fila["ingresos_aprobados"]), 150.0)  # solo pagos aprobados

    def test_los_datos_no_se_cruzan_entre_agencias(self):
        fila = self.fila(self.e.ag_a)
        self.assertEqual(fila["buses"], 2)
        self.assertEqual(fila["viajes_mes"], 0)
        self.assertEqual(fila["reservas"], 0)
        self.assertEqual(float(fila["ingresos_aprobados"]), 0.0)

    def test_incluye_las_desactivadas_y_las_vacias(self):
        vacia = Agencia.objects.create(nombre="V", nit="4", direccion="d", telefono="4", correo="v@v.co", activo=False)
        fila = self.fila(vacia)
        self.assertFalse(fila["activo"])
        self.assertEqual(fila["buses"], 0)
        self.assertEqual(float(fila["ingresos_aprobados"]), 0.0)

    def test_solo_el_superadmin(self):
        self.assertEqual(Escenario.cliente_http(self.e.admin_a).get("/api/dashboard/agencias/").status_code, 403)
        self.assertEqual(Escenario.cliente_http(self.e.cond_a).get("/api/dashboard/agencias/").status_code, 403)
        self.assertEqual(Escenario.cliente_http(self.e.cliente).get("/api/dashboard/agencias/").status_code, 403)
        self.assertEqual(Escenario.cliente_http().get("/api/dashboard/agencias/").status_code, 401)


class ValidacionUsuariosTest(TestCase):
    """Datos inválidos del personal: responden 400 y no dejan nada guardado a medias."""

    def setUp(self):
        self.e = Escenario()
        self.sup = Escenario.cliente_http(self.e.super)

    def datos(self, **extra):
        return {"nombre_completo": "Nuevo", "rol_id": 2, "agencia_id": self.e.ag_a.id, "tipo_documento": "CC",
                "numero_documento": "70000001", "correo": "nuevo.val@rt.co", "telefono": "3001234567",
                "contrasena": "clave-segura", **extra}

    def test_agencia_inexistente_no_crea_el_usuario(self):
        r = self.sup.post("/api/usuario/", self.datos(agencia_id=999999), format="json")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Usuario.objects.filter(correo="nuevo.val@rt.co").exists())

    def test_correo_y_clave_invalidos(self):
        self.assertEqual(self.sup.post("/api/usuario/", self.datos(correo="malo"), format="json").status_code, 400)
        self.assertEqual(self.sup.post("/api/usuario/", self.datos(contrasena="1"), format="json").status_code, 400)

    def test_editar_con_datos_repetidos_no_cambia_nada(self):
        objetivo, otro = self.e.cond_a, self.e.cond_b
        ruta = f"/api/usuario/{objetivo.id}/"
        for cambio in ({"correo": otro.correo}, {"numero_documento": otro.numero_documento},
                       {"correo": "malo"}, {"rol_id": 99}, {"agencia_id": 999999}):
            self.assertEqual(self.sup.put(ruta, cambio, format="json").status_code, 400, cambio)
        guardado = Usuario.objects.get(id=objetivo.id)
        self.assertEqual(guardado.correo, objetivo.correo)
        self.assertEqual(guardado.numero_documento, objetivo.numero_documento)

    def test_eliminar_libera_el_correo(self):
        creado = self.sup.post("/api/usuario/", self.datos(), format="json").json()["id"]
        self.assertEqual(self.sup.delete(f"/api/usuario/{creado}/").status_code, 200)
        self.assertEqual(self.sup.post("/api/usuario/", self.datos(), format="json").status_code, 200)

    def test_nit_repetido(self):
        agencia = {"nombre": "Otra", "nit": self.e.ag_a.nit, "direccion": "d", "telefono": "3001234567", "correo": "o@rt.co"}
        self.assertEqual(self.sup.post("/api/agencia/", agencia, format="json").status_code, 400)
        r = self.sup.put(f"/api/agencia/{self.e.ag_b.id}/", {"nit": self.e.ag_a.nit}, format="json")
        self.assertEqual(r.status_code, 400)

    @override_settings(DEBUG=True)
    def test_recuperar_nunca_devuelve_el_codigo(self):
        r = Escenario.cliente_http().post("/api/password/reset/", {"correo": self.e.cliente.correo}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("codigo", r.json())
        self.assertNotIn("token", r.json())


class UsuarioAgenciaRutasTest(TestCase):
    """Asociaciones: sin duplicados, el admin no quita a otro admin y las rutas no terminan en error 500."""

    def setUp(self):
        self.e = Escenario()
        self.sup = Escenario.cliente_http(self.e.super)
        self.admin = Escenario.cliente_http(self.e.admin_a)

    def test_repetir_no_duplica(self):
        datos = {"usuario_id": self.e.cliente.id, "agencia_id": self.e.ag_a.id}
        primero = self.sup.post("/api/usuario-agencia/", datos, format="json")
        segundo = self.sup.post("/api/usuario-agencia/", datos, format="json")
        self.assertEqual((primero.status_code, segundo.status_code), (201, 200))
        self.assertEqual(primero.json()["id"], segundo.json()["id"])
        self.assertEqual(UsuarioAgencia.objects.filter(usuario=self.e.cliente, agencia=self.e.ag_a).count(), 1)

    def test_el_admin_no_quita_a_un_admin(self):
        propia = UsuarioAgencia.objects.get(usuario=self.e.admin_a, agencia=self.e.ag_a)
        self.assertEqual(self.admin.delete(f"/api/usuario-agencia/{propia.id}/").status_code, 403)
        self.assertTrue(UsuarioAgencia.objects.filter(id=propia.id).exists())

    def test_el_admin_quita_a_un_conductor_y_el_super_a_un_admin(self):
        conductor = UsuarioAgencia.objects.get(usuario=self.e.cond_a, agencia=self.e.ag_a)
        admin = UsuarioAgencia.objects.get(usuario=self.e.admin_b, agencia=self.e.ag_b)
        self.assertEqual(self.admin.delete(f"/api/usuario-agencia/{conductor.id}/").status_code, 200)
        self.assertEqual(self.sup.delete(f"/api/usuario-agencia/{admin.id}/").status_code, 200)

    def test_metodos_no_validos_responden_405(self):
        self.assertEqual(self.sup.delete("/api/usuario-agencia/").status_code, 405)
        self.assertEqual(self.sup.get("/api/usuario-agencia/1/").status_code, 405)
        self.assertEqual(self.sup.post("/api/usuario-agencia/1/", {}, format="json").status_code, 405)


@override_settings(EMAIL_BACKEND="usuarios.correo.ResendBackend", RESEND_API_KEY="clave-de-prueba")
class ResendBackendTest(TestCase):
    """El correo sale por HTTPS a Resend; aquí se simula la respuesta, no se envía nada."""

    @patch("usuarios.correo.urllib.request.urlopen")
    def test_envia_a_la_api(self, urlopen):
        self.assertEqual(send_mail("Asunto", "Cuerpo", "RutaTour <no@rt.co>", ["cliente@rt.co"]), 1)
        peticion = urlopen.call_args.args[0]
        self.assertEqual(peticion.full_url, "https://api.resend.com/emails")
        self.assertEqual(peticion.get_header("Authorization"), "Bearer clave-de-prueba")
        self.assertEqual(json.loads(peticion.data), {
            "from": "RutaTour <no@rt.co>", "to": ["cliente@rt.co"], "subject": "Asunto", "text": "Cuerpo",
        })

    @patch("usuarios.correo.urllib.request.urlopen", side_effect=OSError("sin red"))
    def test_un_fallo_no_cambia_la_respuesta_de_recuperar(self, urlopen):
        e = Escenario()
        with self.assertLogs("usuarios.views", level="ERROR"):
            r = Escenario.cliente_http().post("/api/password/reset/", {"correo": e.cliente.correo}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(urlopen.called)


@override_settings(EMAIL_BACKEND="usuarios.correo.MailjetBackend", MAILJET_API_KEY="k", MAILJET_SECRET_KEY="s")
class MailjetBackendTest(TestCase):
    """El correo sale por HTTPS a Mailjet; aquí se simula la respuesta, no se envía nada."""

    def respuesta(self, urlopen, estado):
        urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(
            {"Messages": [{"Status": estado}]}
        ).encode("utf-8")

    @patch("usuarios.correo.urllib.request.urlopen")
    def test_envia_a_la_api(self, urlopen):
        self.respuesta(urlopen, "success")
        self.assertEqual(send_mail("Asunto", "Cuerpo", "RutaTour <no@rt.co>", ["cliente@rt.co"]), 1)
        peticion = urlopen.call_args.args[0]
        self.assertEqual(peticion.full_url, "https://api.mailjet.com/v3.1/send")
        self.assertEqual(peticion.get_header("Authorization"), "Basic azpz")
        self.assertEqual(json.loads(peticion.data), {"Messages": [{
            "From": {"Email": "no@rt.co", "Name": "RutaTour"}, "To": [{"Email": "cliente@rt.co"}],
            "Subject": "Asunto", "TextPart": "Cuerpo",
        }]})

    @patch("usuarios.correo.urllib.request.urlopen")
    def test_remitente_sin_nombre(self, urlopen):
        self.respuesta(urlopen, "success")
        send_mail("Asunto", "Cuerpo", "no@rt.co", ["cliente@rt.co"])
        self.assertEqual(json.loads(urlopen.call_args.args[0].data)["Messages"][0]["From"], {"Email": "no@rt.co"})

    @patch("usuarios.correo.urllib.request.urlopen")
    def test_mensaje_rechazado_es_un_fallo(self, urlopen):
        self.respuesta(urlopen, "error")
        with self.assertRaises(RuntimeError):
            send_mail("Asunto", "Cuerpo", "no@rt.co", ["cliente@rt.co"])


from decimal import Decimal as _Decimal

from reservas.models import AsientoReserva, Novedad


class ReporteGeneralTest(TestCase):
    """RUT-85 (HU-W-13): reporte de operación, ventas y ocupación por rango de fechas."""

    def setUp(self):
        self.e = Escenario()
        hoy = hoy_colombia()
        self.desde, self.hasta = hoy - timedelta(days=3), hoy + timedelta(days=3)
        # Sillas que el administrador asignó: 10 en los buses de A y 8 en el de B.
        sillas_a = [Asiento.objects.create(numero_asiento=n, tipo_bus=self.e.tipo_a) for n in range(1, 11)]
        sillas_b = [Asiento.objects.create(numero_asiento=n, tipo_bus=self.e.tipo_b) for n in range(1, 9)]
        v_a = Viaje.objects.create(paquete=self.e.paq_a, bus=self.e.bus_a, fecha=hoy, hora="06:30")
        v_fuera = Viaje.objects.create(paquete=self.e.paq_a, bus=self.e.bus_a2, fecha=hoy + timedelta(days=30), hora="06:30")
        v_b = Viaje.objects.create(paquete=self.e.paq_b, bus=self.e.bus_b, fecha=hoy + timedelta(days=1), hora="07:00")

        r1 = self.reserva(v_a, sillas_a[:2])
        Pago.objects.create(precio=100, reserva=r1, fecha_pago=timezone.now(), estado="aprobado")
        # Pago aprobado FUERA del rango: no cuenta en ventas.
        Pago.objects.create(precio=999, reserva=r1, fecha_pago=timezone.now() - timedelta(days=60), estado="aprobado")
        # Pago pendiente: no es una venta.
        Pago.objects.create(precio=70, reserva=self.reserva(v_a, sillas_a[2:3]), fecha_pago=timezone.now(), estado="pendiente")
        # Reserva cancelada: sus sillas no ocupan.
        self.reserva(v_a, sillas_a[3:5], estado="cancelada")
        # Salida fuera del rango: no cuenta.
        self.reserva(v_fuera, sillas_a[5:6])
        rb = self.reserva(v_b, sillas_b[:1])
        Pago.objects.create(precio=50, reserva=rb, fecha_pago=timezone.now(), estado="aprobado")

        Novedad.objects.create(paquete=self.e.paq_a, viaje=v_a, tipo="Accidente", detalle="choque")
        Novedad.objects.create(paquete=self.e.paq_a, tipo="Queja", detalle="aire", resuelta=True)
        Bus_Conductor.objects.create(bus=self.e.bus_a, conductor=self.e.cond_a)

    def reserva(self, viaje, sillas, estado="pendiente"):
        r = Reserva.objects.create(fecha_reserva=timezone.now(), usuario=self.e.cliente, paquete=viaje.paquete,
                                   viaje=viaje, estado=estado)
        for s in sillas:
            AsientoReserva.objects.create(reserva=r, asiento=s)
        return r

    def url(self, extra=""):
        return f"/api/dashboard/reporte/?desde={self.desde}&hasta={self.hasta}{extra}"

    def fila(self, datos, agencia):
        return next(f for f in datos["agencias"] if f["agencia_id"] == agencia.id)

    def test_superadmin_ve_todas_las_agencias_con_sus_metricas(self):
        datos = Escenario.cliente_http(self.e.super).get(self.url()).json()
        self.assertEqual({f["agencia_id"] for f in datos["agencias"]}, {self.e.ag_a.id, self.e.ag_b.id})
        a = self.fila(datos, self.e.ag_a)
        self.assertEqual(a["ventas"], {"pagos_aprobados": 1, "total": "100.00"})
        self.assertEqual(a["ocupacion"], {"viajes": 1, "sillas_ofrecidas": 10, "sillas_reservadas": 3, "porcentaje": 30.0})
        self.assertEqual((a["operacion"]["viajes_programados"], a["operacion"]["novedades"],
                          a["operacion"]["novedades_atendidas"], a["operacion"]["incidentes_graves"]), (1, 2, 1, 1))
        b = self.fila(datos, self.e.ag_b)
        self.assertEqual(b["ventas"]["total"], "50.00")
        self.assertEqual(b["ocupacion"]["porcentaje"], 12.5)

    def test_totales_coinciden_con_los_reportes_por_agencia(self):
        general = Escenario.cliente_http(self.e.super).get(self.url()).json()["totales"]
        por_agencia = [Escenario.cliente_http(admin).get(self.url()).json()["totales"]
                       for admin in (self.e.admin_a, self.e.admin_b)]
        self.assertEqual(general["ventas"]["pagos_aprobados"], sum(t["ventas"]["pagos_aprobados"] for t in por_agencia))
        self.assertEqual(_Decimal(general["ventas"]["total"]), sum(_Decimal(t["ventas"]["total"]) for t in por_agencia))
        for seccion, campos in (("ocupacion", ("viajes", "sillas_ofrecidas", "sillas_reservadas")),
                                ("operacion", tuple(general["operacion"]))):
            for campo in campos:
                self.assertEqual(general[seccion][campo], sum(t[seccion][campo] for t in por_agencia), campo)
        self.assertEqual(general["ventas"]["total"], "150.00")
        self.assertEqual(general["ocupacion"]["porcentaje"], round(4 * 100 / 18, 1))

    def test_solo_datos_del_rango(self):
        hoy = hoy_colombia()
        lejos = f"/api/dashboard/reporte/?desde={hoy + timedelta(days=20)}&hasta={hoy + timedelta(days=40)}"
        a = self.fila(Escenario.cliente_http(self.e.super).get(lejos).json(), self.e.ag_a)
        self.assertEqual(a["ventas"], {"pagos_aprobados": 0, "total": "0.00"})
        self.assertEqual(a["ocupacion"]["viajes"], 1)          # solo la salida de dentro de 30 días
        self.assertEqual(a["ocupacion"]["sillas_reservadas"], 1)
        self.assertEqual(a["operacion"]["novedades"], 0)
        hace_60 = hoy - timedelta(days=60)
        viejo = Escenario.cliente_http(self.e.super).get(f"/api/dashboard/reporte/?desde={hace_60}&hasta={hace_60}").json()
        self.assertEqual(self.fila(viejo, self.e.ag_a)["ventas"]["total"], "999.00")

    def test_admin_solo_ve_su_agencia(self):
        admin_a = Escenario.cliente_http(self.e.admin_a)
        datos = admin_a.get(self.url(f"&agencia_id={self.e.ag_b.id}")).json()
        self.assertEqual([f["agencia_id"] for f in datos["agencias"]], [self.e.ag_a.id])

    def test_superadmin_filtra_una_agencia(self):
        datos = Escenario.cliente_http(self.e.super).get(self.url(f"&agencia_id={self.e.ag_b.id}")).json()
        self.assertEqual([f["agencia_id"] for f in datos["agencias"]], [self.e.ag_b.id])
        self.assertEqual(datos["totales"]["ventas"]["total"], "50.00")

    def test_conductor_y_cliente_403(self):
        for u in (self.e.cond_a, self.e.cliente):
            self.assertEqual(Escenario.cliente_http(u).get(self.url()).status_code, 403)

    def test_fechas_invalidas_400_y_sin_fechas_usa_el_mes(self):
        sup = Escenario.cliente_http(self.e.super)
        self.assertEqual(sup.get("/api/dashboard/reporte/?desde=2026-13-01").status_code, 400)
        self.assertEqual(sup.get(f"/api/dashboard/reporte/?desde={self.hasta}&hasta={self.desde}").status_code, 400)
        r = sup.get("/api/dashboard/reporte/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["desde"].endswith("-01"))


class RegistroUsuarioExistenteTest(TestCase):
    """Registro con datos repetidos: cada caso con su mensaje, y la cuenta de sesión huérfana no bloquea el correo."""

    def setUp(self):
        self.e = Escenario()
        self.datos = {"nombre_completo": "Ana Nueva", "numero_documento": "55555555", "correo": "ana@rt.co",
                      "telefono": "3001234567", "contrasena": "clave1234"}

    def registrar(self, **cambios):
        return APIClient().post("/api/usuario/", {**self.datos, **cambios}, format="json")

    def test_correo_repetido_dice_correo(self):
        r = self.registrar(correo=self.e.cliente.correo.upper())
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["motivo"], "correo_existente")
        self.assertIn("correo", r.json()["message"])

    def test_documento_repetido_dice_documento(self):
        Usuario.objects.filter(id=self.e.cliente.id).update(numero_documento="12345678")  # válido: 5 a 15 dígitos
        r = self.registrar(numero_documento="12345678")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["motivo"], "documento_existente")
        self.assertIn("documento", r.json()["message"])

    def test_cuenta_de_sesion_huerfana_se_reutiliza(self):
        viejo = User.objects.create_user(username="ana@rt.co", email="ana@rt.co", password="otraclave99")
        viejo.is_active = False
        viejo.save()
        refresh_viejo = str(RefreshToken.for_user(viejo))
        r = self.registrar()
        self.assertEqual(r.status_code, 201)
        self.assertEqual(User.objects.filter(username__iexact="ana@rt.co").count(), 1)
        reutilizado = User.objects.get(username__iexact="ana@rt.co")
        self.assertEqual(reutilizado.id, viejo.id)
        self.assertTrue(reutilizado.is_active)
        self.assertTrue(reutilizado.check_password("clave1234"))
        self.assertTrue(Usuario.objects.filter(correo="ana@rt.co", rol_id=4).exists())
        # Con la clave nueva entra; la sesión vieja ya no se puede renovar.
        login = APIClient().post("/api/login/", {"correo": "ana@rt.co", "contrasena": "clave1234"}, format="json")
        self.assertEqual(login.status_code, 200)
        self.assertNotEqual(APIClient().post("/api/token/refresh/", {"refresh": refresh_viejo}, format="json").status_code, 200)

    def test_cuenta_staff_de_django_no_se_reutiliza(self):
        User.objects.create_superuser(username="ana@rt.co", email="ana@rt.co", password="otraclave99")
        r = self.registrar()
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["motivo"], "correo_existente")
        self.assertTrue(User.objects.get(username="ana@rt.co").check_password("otraclave99"))
        self.assertFalse(Usuario.objects.filter(correo="ana@rt.co").exists())
