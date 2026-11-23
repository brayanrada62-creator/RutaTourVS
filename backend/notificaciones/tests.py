import unittest
from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from buses.models import Bus_Conductor, Viaje
from buses.views import hoy_colombia
from notificaciones.models import DispositivoFCM, Notificacion, PreferenciaNotificacion, Tipo
from paquetes.models import Itinerario
from pagos.models import Pago
from reservas.models import Reserva
from usuarios.pruebas import Escenario


class Base(TestCase):
    def setUp(self):
        self.e = Escenario()
        Bus_Conductor.objects.create(bus=self.e.bus_a, conductor=self.e.cond_a)
        Bus_Conductor.objects.create(bus=self.e.bus_b, conductor=self.e.cond_b)
        self.viaje = Viaje.objects.create(paquete=self.e.paq_a, bus=self.e.bus_a,
                                          fecha=hoy_colombia() + timedelta(days=5), hora="06:30")
        self.viaje_b = Viaje.objects.create(paquete=self.e.paq_b, bus=self.e.bus_b,
                                            fecha=hoy_colombia() + timedelta(days=5), hora="07:00")

    def http(self, usuario):
        return Escenario.cliente_http(usuario)

    def de(self, usuario, tipo=None):
        lista = Notificacion.objects.filter(destinatario=usuario)
        return lista.filter(tipo=tipo) if tipo else lista


class NovedadTest(Base):
    """HU-W-46: la novedad avisa solo a los administradores de la agencia del conductor."""

    def reportar(self, conductor, viaje):
        return self.http(conductor).post("/api/novedad/", {"viaje_id": viaje.id, "tipo": "falla", "detalle": "Llanta pinchada"},
                                         format="json")

    def test_admin_de_la_agencia_recibe(self):
        self.assertEqual(self.reportar(self.e.cond_a, self.viaje).status_code, 201)
        n = self.de(self.e.admin_a, Tipo.NOVEDAD_INCIDENTE).get()
        self.assertEqual((n.referencia_tipo, n.leida), ("novedad", False))
        self.assertEqual(n.datos["viaje_id"], self.viaje.id)

    def test_admin_de_otra_agencia_no_recibe(self):  # HU-W-46.3
        self.reportar(self.e.cond_a, self.viaje)
        self.assertEqual(self.de(self.e.admin_b).count(), 0)
        self.assertEqual(self.de(self.e.cond_a).count(), 0)

    def test_reporte_de_otra_agencia_no_avisa_a_esta(self):
        self.reportar(self.e.cond_b, self.viaje_b)
        self.assertEqual(self.de(self.e.admin_a).count(), 0)
        self.assertEqual(self.de(self.e.admin_b).count(), 1)

    def test_el_admin_ve_la_novedad_con_su_viaje(self):  # HU-W-46.2
        self.reportar(self.e.cond_a, self.viaje)
        n = self.de(self.e.admin_a).get()
        r = self.http(self.e.admin_a).get(f"/api/novedad/{n.referencia_id}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["viaje_id"], self.viaje.id)
        self.assertEqual(self.http(self.e.admin_b).get(f"/api/novedad/{n.referencia_id}/").status_code, 403)


class CambioViajeTest(Base):
    """HU-M-53: solo fecha, hora o paradas, y solo al conductor asignado."""

    def editar(self, **cambios):
        datos = {"fecha": self.viaje.fecha.isoformat(), "hora": "06:30"}
        datos.update(cambios)
        return self.http(self.e.admin_a).put(f"/api/viaje/{self.viaje.id}/", datos, format="json")

    def test_cambio_de_hora_avisa_al_conductor_asignado(self):
        self.assertEqual(self.editar(hora="08:00").status_code, 200)
        n = self.de(self.e.cond_a, Tipo.CAMBIO_VIAJE).get()
        self.assertEqual((n.referencia_id, n.referencia_tipo), (self.viaje.id, "viaje"))
        self.assertEqual(n.datos["cambios"], ["hora"])

    def test_cambio_de_fecha(self):
        self.editar(fecha=(self.viaje.fecha + timedelta(days=1)).isoformat())
        self.assertEqual(self.de(self.e.cond_a).get().datos["cambios"], ["fecha"])

    def test_conductor_no_asignado_no_recibe(self):  # HU-M-53.3
        self.editar(hora="08:00")
        self.assertEqual(self.de(self.e.cond_b).count(), 0)

    def test_sin_cambio_relevante_no_avisa(self):
        self.assertEqual(self.editar().status_code, 200)
        self.assertEqual(self.de(self.e.cond_a).count(), 0)

    def test_cambio_de_bus_solo_no_avisa(self):
        Bus_Conductor.objects.create(bus=self.e.bus_a2, conductor=self.e.cond_a)
        self.editar(bus_id=self.e.bus_a2.id)
        self.assertEqual(self.de(self.e.cond_a).count(), 0)

    def test_cambio_de_parada_avisa_a_los_conductores_del_paquete(self):
        c = self.http(self.e.admin_a)
        base = {"titulo": "P", "paquete_id": self.e.paq_a.id, "dia": "1", "descripcion": "d", "hora": "08:00", "lugar": "Plaza"}
        self.assertEqual(c.post("/api/itinerario/", base, format="json").status_code, 200)
        self.assertEqual(self.de(self.e.cond_a).count(), 1)  # parada nueva
        parada = Itinerario.objects.get()
        c.put(f"/api/itinerario/{parada.id}/", {**base, "descripcion": "otra"}, format="json")
        self.assertEqual(self.de(self.e.cond_a).count(), 1)  # solo cambió la descripción
        c.put(f"/api/itinerario/{parada.id}/", {**base, "lugar": "Museo"}, format="json")
        self.assertEqual(self.de(self.e.cond_a).count(), 2)
        self.assertEqual(self.de(self.e.cond_b).count(), 0)


class PagoTest(Base):
    """HU-M-11: aprobado avisa al cliente dueño; rechazado no."""

    def setUp(self):
        super().setUp()
        reserva = Reserva.objects.create(fecha_reserva=timezone.now(), usuario=self.e.cliente, paquete=self.e.paq_a, viaje=self.viaje)
        self.pago = Pago.objects.create(precio=1000, reserva=reserva, fecha_pago=timezone.now())

    def decidir(self, estado):
        return self.http(self.e.admin_a).put(f"/api/pago/{self.pago.id}/", {"estado": estado}, format="json")

    def test_aprobado_avisa_al_cliente(self):
        self.assertEqual(self.decidir("aprobado").status_code, 200)
        n = self.de(self.e.cliente, Tipo.PAGO_APROBADO).get()
        self.assertEqual((n.referencia_id, n.referencia_tipo), (self.pago.reserva_id, "compra"))
        self.assertEqual(self.de(self.e.otro_cliente).count(), 0)

    def test_rechazado_no_avisa(self):
        self.decidir("rechazado")
        self.assertEqual(self.de(self.e.cliente).count(), 0)

    def test_aprobar_dos_veces_avisa_una_sola(self):
        self.decidir("aprobado")
        self.decidir("aprobado")
        self.assertEqual(self.de(self.e.cliente).count(), 1)

    def test_preferencia_desactivada_no_guarda_ni_envia(self):  # HU-M-51.2
        DispositivoFCM.objects.create(usuario=self.e.cliente, token="tok")
        self.http(self.e.cliente).put("/api/notificaciones/preferencias/", [{"tipo": "PAGO_APROBADO", "activa": False}], format="json")
        with mock.patch("notificaciones.fcm.enviar_push") as push, mock.patch("notificaciones.ws.emitir") as ws:
            self.decidir("aprobado")
        self.assertEqual(self.de(self.e.cliente).count(), 0)
        push.assert_not_called()
        ws.assert_not_called()

    def test_con_preferencia_activa_envia_push_con_datos(self):
        DispositivoFCM.objects.create(usuario=self.e.cliente, token="tok")
        with mock.patch("notificaciones.fcm.enviar_push", return_value=[]) as push:
            self.decidir("aprobado")
        tokens, _titulo, _mensaje, datos = push.call_args.args
        n = self.de(self.e.cliente).get()
        self.assertEqual(tokens, ["tok"])
        self.assertEqual(datos, {"notificacion_id": n.id, "tipo": "PAGO_APROBADO",
                                 "referencia_id": n.referencia_id, "referencia_tipo": "compra"})

    def test_token_rechazado_por_fcm_se_borra(self):
        DispositivoFCM.objects.create(usuario=self.e.cliente, token="viejo")
        with mock.patch("notificaciones.fcm.enviar_push", return_value=["viejo"]):
            self.decidir("aprobado")
        self.assertFalse(DispositivoFCM.objects.filter(token="viejo").exists())

    def test_admin_recibe_por_websocket(self):
        with mock.patch("notificaciones.ws.emitir") as ws:
            self.http(self.e.cond_a).post("/api/novedad/", {"viaje_id": self.viaje.id, "tipo": "x", "detalle": "y"}, format="json")
        self.assertEqual(ws.call_args.args[0], self.e.admin_a.id)


class EndpointsTest(Base):
    """Los endpoints solo ven lo del usuario del token."""

    def setUp(self):
        super().setUp()
        self.mia = Notificacion.objects.create(destinatario=self.e.cliente, tipo=Tipo.PAGO_APROBADO, titulo="t", mensaje="m")
        self.ajena = Notificacion.objects.create(destinatario=self.e.otro_cliente, tipo=Tipo.PAGO_APROBADO, titulo="t", mensaje="m")
        self.c = self.http(self.e.cliente)

    def test_lista_solo_mis_avisos_del_mas_reciente_al_mas_antiguo(self):
        segunda = Notificacion.objects.create(destinatario=self.e.cliente, tipo=Tipo.PAGO_APROBADO, titulo="t2", mensaje="m")
        r = self.c.get("/api/notificaciones/?page=1&page_size=10").json()
        self.assertEqual([n["id"] for n in r["results"]], [segunda.id, self.mia.id])
        self.assertEqual(r["count"], 2)

    def test_detalle_ajeno_404(self):
        self.assertEqual(self.c.get(f"/api/notificaciones/{self.mia.id}/").status_code, 200)
        self.assertEqual(self.c.get(f"/api/notificaciones/{self.ajena.id}/").status_code, 404)

    def test_marcar_leida_y_contador(self):
        self.assertEqual(self.c.get("/api/notificaciones/no-leidas/count/").json(), {"count": 1})
        self.assertEqual(self.c.patch(f"/api/notificaciones/{self.mia.id}/leida/").json()["leida"], True)
        self.assertEqual(self.c.get("/api/notificaciones/no-leidas/count/").json(), {"count": 0})
        self.assertEqual(self.c.patch(f"/api/notificaciones/{self.ajena.id}/leida/").status_code, 404)
        self.ajena.refresh_from_db()
        self.assertFalse(self.ajena.leida)

    def test_sin_token_401(self):
        self.assertEqual(Escenario.cliente_http().get("/api/notificaciones/").status_code, 401)

    def test_preferencias_por_rol_y_persisten(self):  # HU-M-51.1 y 51.3
        self.assertEqual(self.c.get("/api/notificaciones/preferencias/").json(),
                         [{"tipo": "PAGO_APROBADO", "nombre": "Pago aprobado", "activa": True}])
        r = self.c.put("/api/notificaciones/preferencias/", [{"tipo": "PAGO_APROBADO", "activa": False}], format="json")
        self.assertEqual(r.json()[0]["activa"], False)
        self.assertEqual(self.c.get("/api/notificaciones/preferencias/").json()[0]["activa"], False)
        self.assertEqual(PreferenciaNotificacion.objects.filter(usuario=self.e.cliente).count(), 1)
        self.c.put("/api/notificaciones/preferencias/", [{"tipo": "PAGO_APROBADO", "activa": True}], format="json")
        self.assertEqual(PreferenciaNotificacion.objects.filter(usuario=self.e.cliente).count(), 1)  # único por (usuario, tipo)

    def test_tipo_de_otro_rol_o_invalido_400(self):
        for cuerpo in ([{"tipo": "CAMBIO_VIAJE", "activa": False}], [{"tipo": "PAGO_APROBADO", "activa": "no"}], {"x": 1}):
            self.assertEqual(self.c.put("/api/notificaciones/preferencias/", cuerpo, format="json").status_code, 400)
        self.assertEqual(self.http(self.e.cond_a).get("/api/notificaciones/preferencias/").json()[0]["tipo"], "CAMBIO_VIAJE")

    def test_dispositivo_registra_reasigna_y_borra_solo_el_propio(self):
        for ruta in ("/api/dispositivo/", "/api/dispositivos/fcm/"):
            self.assertEqual(self.c.post(ruta, {"token": "abc", "plataforma": "android"}, format="json").status_code, 200)
        self.assertEqual(DispositivoFCM.objects.filter(token="abc", usuario=self.e.cliente).count(), 1)
        otro = self.http(self.e.otro_cliente)
        otro.delete("/api/dispositivo/", {"token": "abc"}, format="json")
        self.assertTrue(DispositivoFCM.objects.filter(token="abc").exists())  # no era suyo
        otro.post("/api/dispositivo/", {"token": "abc"}, format="json")  # mismo teléfono, otra cuenta
        self.assertEqual(DispositivoFCM.objects.get(token="abc").usuario, self.e.otro_cliente)
        self.assertEqual(self.c.post("/api/dispositivo/", {}, format="json").status_code, 400)
        otro.delete("/api/dispositivo/", {"token": "abc"}, format="json")
        self.assertFalse(DispositivoFCM.objects.filter(token="abc").exists())


class NoRompeElFlujoTest(PagoTest):
    """Si notificar falla (BD, FCM, WebSocket), la operación de negocio igual se completa."""

    def test_pago_se_aprueba_aunque_notificar_falle(self):
        with mock.patch("notificaciones.eventos.notificar", side_effect=RuntimeError("boom")):
            r = self.decidir("aprobado")
        self.assertEqual(r.status_code, 200)
        self.pago.refresh_from_db()
        self.assertEqual(self.pago.estado, "aprobado")

    def test_viaje_se_edita_aunque_notificar_falle(self):
        with mock.patch("notificaciones.eventos.notificar", side_effect=RuntimeError("boom")):
            r = self.http(self.e.admin_a).put(f"/api/viaje/{self.viaje.id}/",
                                              {"fecha": self.viaje.fecha.isoformat(), "hora": "09:00"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.viaje.refresh_from_db()
        self.assertEqual(self.viaje.hora.strftime("%H:%M"), "09:00")

    def test_novedad_se_guarda_aunque_notificar_falle(self):
        with mock.patch("notificaciones.eventos.notificar", side_effect=RuntimeError("boom")):
            r = self.http(self.e.cond_a).post("/api/novedad/", {"viaje_id": self.viaje.id, "tipo": "x", "detalle": "y"}, format="json")
        self.assertEqual(r.status_code, 201)

    def test_fcm_caido_no_rompe_el_aviso(self):
        DispositivoFCM.objects.create(usuario=self.e.cliente, token="tok")
        with mock.patch("notificaciones.fcm._iniciar", side_effect=RuntimeError("sin firebase")):
            self.assertEqual(self.decidir("aprobado").status_code, 200)
        self.assertEqual(self.de(self.e.cliente).count(), 1)  # el historial se guardó igual


try:
    import channels  # noqa: F401
    import daphne  # noqa: F401  (channels.testing lo necesita)
except ImportError:  # pragma: no cover - opcional en producción
    channels = None


@unittest.skipUnless(channels, "channels y daphne no están instalados")
class WebSocketTest(Base):
    """El panel solo recibe lo suyo: administrador autenticado, en su propio grupo."""

    def token(self, usuario):
        return Escenario.cliente_http(usuario)._credentials["HTTP_AUTHORIZATION"].split()[1]

    def test_token_de_admin_valido_y_de_otros_roles_no(self):
        from notificaciones.consumers import admin_del_token
        self.assertEqual(admin_del_token(self.token(self.e.admin_a)), self.e.admin_a)
        self.assertIsNone(admin_del_token(self.token(self.e.cond_a)))
        self.assertIsNone(admin_del_token(self.token(self.e.cliente)))
        self.assertIsNone(admin_del_token("token-falso"))

    def test_conexion_y_entrega_solo_al_grupo_propio(self):
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        from channels.testing import WebsocketCommunicator
        from notificaciones.routing import websocket_urlpatterns
        from channels.routing import URLRouter
        from notificaciones.ws import grupo_de

        app = URLRouter(websocket_urlpatterns)
        tok_a, tok_b = self.token(self.e.admin_a), self.token(self.e.admin_b)
        tok_c = self.token(self.e.cliente)
        # La validación del token ya se probó arriba contra la BD; aquí se aísla de ella porque el hilo de
        # database_sync_to_async no ve la transacción abierta de TestCase.
        quien = {tok_a: self.e.admin_a, tok_b: self.e.admin_b}
        parche = mock.patch("notificaciones.consumers.admin_del_token", side_effect=lambda t: quien.get(t))
        parche.start()
        self.addCleanup(parche.stop)

        async def escenario():
            sin = WebsocketCommunicator(app, "/ws/alertas/")
            self.assertFalse((await sin.connect())[0])  # sin token
            cliente = WebsocketCommunicator(app, f"/ws/alertas/?token={tok_c}")
            self.assertFalse((await cliente.connect())[0])  # rol sin permiso
            a = WebsocketCommunicator(app, f"/ws/alertas/?token={tok_a}")
            b = WebsocketCommunicator(app, f"/ws/alertas/?token={tok_b}")
            self.assertTrue((await a.connect())[0])
            self.assertTrue((await b.connect())[0])
            await get_channel_layer().group_send(grupo_de(self.e.admin_a.id), {"type": "alerta", "carga": {"titulo": "t", "mensaje": "m", "fecha": "f"}})
            self.assertEqual(await a.receive_json_from(), {"titulo": "t", "mensaje": "m", "fecha": "f"})
            self.assertTrue(await b.receive_nothing())  # el admin de otra agencia no recibe nada
            await a.disconnect()
            await b.disconnect()

        async_to_sync(escenario)()
