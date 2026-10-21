from django.test import TestCase

from buses.models import Asiento
from reservas.models import AsientoReserva, GpsPunto, Reserva
from usuarios.pruebas import Escenario


class SillasRegresionTest(TestCase):
    """El flujo de sillas de la app sigue funcionando con permisos activos."""

    def setUp(self):
        self.e = Escenario()
        self.s1 = Asiento.objects.create(numero_asiento=1, tipo_bus=self.e.tipo_a)
        self.s2 = Asiento.objects.create(numero_asiento=2, tipo_bus=self.e.tipo_a)

    def reservar(self, c):
        r = c.post("/api/reserva/", {"fecha_reserva": "2026-10-20", "paquete_id": self.e.paq_a.id}, format="json")
        self.assertEqual(r.status_code, 201)
        return r.json()["id"]

    def test_flujo_completo(self):
        c1 = Escenario.cliente_http(self.e.cliente)
        c2 = Escenario.cliente_http(self.e.otro_cliente)
        # el mapa de sillas se puede leer
        lista = c1.get(f"/api/asiento/?tipo_bus_id={self.e.tipo_a.id}&paquete_id={self.e.paq_a.id}").json()
        self.assertEqual(len(lista), 2)
        r1 = self.reservar(c1)
        self.assertEqual(c1.post("/api/asientoreserva/", {"asiento_id": self.s1.id, "reserva_id": r1}, format="json").status_code, 200)
        r2 = self.reservar(c2)
        self.assertEqual(c2.post("/api/asientoreserva/", {"asiento_id": self.s1.id, "reserva_id": r2}, format="json").status_code, 409)
        # nadie usa la reserva de otro para tomar sillas
        self.assertEqual(c2.post("/api/asientoreserva/", {"asiento_id": self.s2.id, "reserva_id": r1}, format="json").status_code, 403)
        # el rollback de la app (borrar su propia reserva sin pago) sigue permitido
        self.assertEqual(c2.delete(f"/api/reserva/{r2}/").status_code, 200)
        self.assertFalse(Reserva.objects.filter(id=r2).exists())
        self.assertEqual(AsientoReserva.objects.count(), 1)


from django.utils import timezone

from buses.models import Bus_Conductor, Viaje
from pagos.models import Pago
from reservas.views import codigo_reserva


class AbordajeTest(TestCase):
    """Fase 5: solo aborda un pasajero de ESTE viaje con el último pago aprobado."""

    def setUp(self):
        self.e = Escenario()
        self.viaje = Viaje.objects.create(paquete=self.e.paq_a, bus=self.e.bus_a, fecha="2026-11-02", hora="06:30")
        self.otro_viaje = Viaje.objects.create(paquete=self.e.paq_b, bus=self.e.bus_b, fecha="2026-11-02", hora="06:30")
        Bus_Conductor.objects.create(bus=self.e.bus_a, conductor=self.e.cond_a)
        self.c = Escenario.cliente_http(self.e.cond_a)

    def reserva(self, pago=None, paquete=None):
        r = Reserva.objects.create(fecha_reserva=timezone.now(), usuario=self.e.cliente, paquete=paquete or self.e.paq_a)
        if pago:
            Pago.objects.create(precio=1, reserva=r, fecha_pago=timezone.now(), estado=pago)
        return r

    def abordar(self, codigo=None, reserva_id=None, estado="ABORDO", viaje=None):
        datos = {"estado": estado}
        if codigo:
            datos["codigo"] = codigo
        if reserva_id:
            datos["reserva_id"] = reserva_id
        return self.c.post(f"/api/viaje/{(viaje or self.viaje).id}/abordar/", datos, format="json")

    def test_pago_aprobado_aborda_una_sola_vez(self):
        r = self.reserva("aprobado")
        primero = self.abordar(codigo=codigo_reserva(r.id))
        self.assertEqual(primero.status_code, 200)
        self.assertEqual(primero.json()["estado"], "ABORDO")
        segundo = self.abordar(codigo=codigo_reserva(r.id))
        self.assertEqual(segundo.status_code, 200)
        self.assertTrue(segundo.json()["sin_cambios"])
        r.refresh_from_db()
        self.assertEqual((r.abordado, r.viaje_id), ("ABORDO", self.viaje.id))

    def test_pendiente_rechazado_o_sin_pago_no_abordan(self):
        for pago, motivo in (("pendiente", "pago_pendiente"), ("rechazado", "pago_rechazado"), (None, "sin_pago")):
            r = self.reserva(pago)
            res = self.abordar(codigo=codigo_reserva(r.id))
            self.assertEqual(res.status_code, 409, pago)
            self.assertEqual(res.json()["motivo"], motivo)
            r.refresh_from_db()
            self.assertEqual(r.abordado, "PENDIENTE")
        # el último pago manda: aprobado y luego rechazado = no aborda
        r = self.reserva("aprobado")
        Pago.objects.create(precio=1, reserva=r, fecha_pago=timezone.now(), estado="rechazado")
        self.assertEqual(self.abordar(reserva_id=r.id).status_code, 409)

    def test_qr_invalido_o_de_otro_viaje(self):
        r = self.reserva("aprobado")
        self.assertEqual(self.abordar(codigo=f"RT-{r.id}").status_code, 400)            # sin firma
        self.assertEqual(self.abordar(codigo=f"RT-{r.id}-00000000").status_code, 400)   # firma falsa
        self.assertEqual(self.abordar(codigo="cualquier cosa").status_code, 400)
        ajena = self.reserva("aprobado", paquete=self.e.paq_b)
        res = self.abordar(codigo=codigo_reserva(ajena.id))
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.json()["motivo"], "otro_viaje")
        self.assertEqual(self.abordar(reserva_id=999999).status_code, 404)

    def test_conductor_no_autorizado(self):
        r = self.reserva("aprobado", paquete=self.e.paq_b)
        self.assertEqual(self.abordar(codigo=codigo_reserva(r.id), viaje=self.otro_viaje).status_code, 403)
        b = Escenario.cliente_http(self.e.cond_b)  # tiene agencia B pero no el bus B asignado
        self.assertEqual(b.post(f"/api/viaje/{self.otro_viaje.id}/abordar/", {"reserva_id": r.id}, format="json").status_code, 403)
        self.assertEqual(b.get(f"/api/viaje/{self.viaje.id}/pasajeros/").status_code, 403)

    def test_lista_de_pasajeros_con_pago(self):
        self.reserva("aprobado"); self.reserva("pendiente"); self.reserva("aprobado", paquete=self.e.paq_b)
        lista = self.c.get(f"/api/viaje/{self.viaje.id}/pasajeros/").json()
        self.assertEqual(sorted(p["pago_estado"] for p in lista), ["aprobado", "pendiente"])
        self.assertEqual(sum(p["puede_abordar"] for p in lista), 1)

    def test_por_paquete_tambien_exige_pago_y_es_solo_personal(self):
        r = self.reserva("pendiente")
        admin = Escenario.cliente_http(self.e.admin_a)
        self.assertEqual(admin.post(f"/api/paquete/{self.e.paq_a.id}/abordar/", {"reserva_id": r.id}, format="json").status_code, 409)
        self.assertEqual(self.c.post(f"/api/paquete/{self.e.paq_a.id}/abordar/", {"reserva_id": r.id}, format="json").status_code, 403)

    def test_ausente_no_necesita_pago_y_viaje_completado_rechaza(self):
        r = self.reserva("pendiente")
        self.assertEqual(self.abordar(reserva_id=r.id, estado="AUSENTE").status_code, 200)
        self.assertEqual(self.abordar(reserva_id=r.id, estado="VOLANDO").status_code, 400)
        Viaje.objects.filter(id=self.viaje.id).update(estado="COMPLETADO")
        self.assertEqual(self.abordar(reserva_id=r.id, estado="AUSENTE").status_code, 409)


class GpsTest(TestCase):
    """Fase 6: solo el conductor del viaje en curso envía GPS; se ve solo dentro de la agencia."""

    def setUp(self):
        self.e = Escenario()
        Bus_Conductor.objects.create(bus=self.e.bus_a, conductor=self.e.cond_a)
        self.viaje = Viaje.objects.create(paquete=self.e.paq_a, bus=self.e.bus_a, fecha="2026-11-02", hora="06:30")
        self.c = Escenario.cliente_http(self.e.cond_a)

    def enviar(self, c=None, **extra):
        datos = {"viaje_id": self.viaje.id, "lat": "4.60971", "lng": "-74.08175", "velocidad": "42.5"}
        datos.update(extra)
        return (c or self.c).post("/api/gps/", datos, format="json")

    def test_solo_con_viaje_en_curso(self):
        self.assertEqual(self.enviar().status_code, 409)  # aún programado
        self.c.post(f"/api/viaje/{self.viaje.id}/iniciar/")
        self.assertEqual(self.enviar().status_code, 201)
        self.c.post(f"/api/viaje/{self.viaje.id}/finalizar/")
        fin = self.enviar()
        self.assertEqual(fin.status_code, 409)
        self.assertEqual(fin.json()["estado"], "COMPLETADO")
        self.assertEqual(GpsPunto.objects.count(), 1)

    def test_no_duplica_puntos_seguidos(self):
        self.c.post(f"/api/viaje/{self.viaje.id}/iniciar/")
        self.assertEqual(self.enviar().status_code, 201)
        segundo = self.enviar()
        self.assertEqual(segundo.status_code, 200)
        self.assertTrue(segundo.json()["ignorado"])
        self.assertEqual(GpsPunto.objects.count(), 1)

    def test_conductor_no_autorizado_y_datos_invalidos(self):
        self.c.post(f"/api/viaje/{self.viaje.id}/iniciar/")
        otro = self.e.usuario("cond.a3@rt.co", 3, self.e.ag_a)
        Bus_Conductor.objects.create(bus=self.e.bus_a, conductor=otro)  # mismo bus, pero no inició el viaje
        self.assertEqual(self.enviar(Escenario.cliente_http(otro)).status_code, 403)
        self.assertEqual(self.enviar(Escenario.cliente_http(self.e.cond_b)).status_code, 403)
        self.assertEqual(self.enviar(lat="abc").status_code, 400)
        self.assertEqual(self.enviar(lat="95").status_code, 400)

    def test_lectura_aislada_por_agencia(self):
        self.c.post(f"/api/viaje/{self.viaje.id}/iniciar/")
        self.enviar()
        admin_a = Escenario.cliente_http(self.e.admin_a).get("/api/gps/?ultimos=1").json()
        self.assertEqual(len(admin_a), 1)
        self.assertEqual(admin_a[0]["bus_id"], self.e.bus_a.id)
        self.assertEqual(admin_a[0]["placa"], "AAA111")
        self.assertEqual(Escenario.cliente_http(self.e.admin_b).get("/api/gps/?ultimos=1").json(), [])
        self.assertEqual(Escenario.cliente_http(self.e.admin_b).get(f"/api/gps/?viaje_id={self.viaje.id}").status_code, 403)
        self.assertEqual(Escenario.cliente_http(self.e.cliente).get(f"/api/gps/{self.e.paq_a.id}/").status_code, 403)
        Reserva.objects.create(fecha_reserva=timezone.now(), usuario=self.e.cliente, paquete=self.e.paq_a)
        self.assertEqual(len(Escenario.cliente_http(self.e.cliente).get(f"/api/gps/{self.e.paq_a.id}/").json()), 1)


from buses.models import ParadaCumplida
from paquetes.models import Itinerario
from reservas.models import ChatMensaje, Novedad


class AuxiliaresViajeTest(TestCase):
    """Fase 7: novedades, chat y paradas ligados al viaje correcto."""

    def setUp(self):
        self.e = Escenario()
        Bus_Conductor.objects.create(bus=self.e.bus_a, conductor=self.e.cond_a)
        self.viaje = Viaje.objects.create(paquete=self.e.paq_a, bus=self.e.bus_a, fecha="2026-11-02", hora="06:30")
        self.viaje2 = Viaje.objects.create(paquete=self.e.paq_a, bus=self.e.bus_a, fecha="2026-11-09", hora="06:30")
        self.c = Escenario.cliente_http(self.e.cond_a)

    def test_novedad_queda_con_su_viaje(self):
        r = self.c.post("/api/novedad/", {"viaje_id": self.viaje.id, "tipo": "falla", "detalle": "Llanta"}, format="json")
        self.assertEqual(r.status_code, 201)
        n = Novedad.objects.get()
        self.assertEqual((n.viaje_id, n.paquete_id), (self.viaje.id, self.e.paq_a.id))
        self.assertEqual(Escenario.cliente_http(self.e.cond_b).post(
            "/api/novedad/", {"viaje_id": self.viaje.id, "detalle": "x"}, format="json").status_code, 403)
        self.assertEqual(self.c.post("/api/novedad/", {"viaje_id": self.viaje.id, "detalle": ""}, format="json").status_code, 400)
        admin = Escenario.cliente_http(self.e.admin_a).get(f"/api/novedad/?viaje_id={self.viaje.id}").json()
        self.assertEqual(len(admin), 1)

    def test_chat_aislado_por_viaje(self):
        self.c.post("/api/chat/", {"viaje_id": self.viaje.id, "texto": "salida 1"}, format="json")
        self.c.post("/api/chat/", {"viaje_id": self.viaje2.id, "texto": "salida 2"}, format="json")
        textos = [m["texto"] for m in self.c.get(f"/api/chat/?viaje_id={self.viaje.id}").json()]
        self.assertEqual(textos, ["salida 1"])
        self.assertEqual(Escenario.cliente_http(self.e.cond_b).get(f"/api/chat/?viaje_id={self.viaje.id}").status_code, 403)
        self.assertEqual(ChatMensaje.objects.get(texto="salida 1").usuario_id, self.e.cond_a.id)

    def test_paradas_persistentes(self):
        it1 = Itinerario.objects.create(titulo="Parada 1", paquete=self.e.paq_a, dia="1", descripcion="", hora="07:00", lugar="A")
        it2 = Itinerario.objects.create(titulo="Parada 2", paquete=self.e.paq_a, dia="1", descripcion="", hora="09:00", lugar="B")
        ajeno = Itinerario.objects.create(titulo="X", paquete=self.e.paq_b, dia="1", descripcion="", hora="07:00", lugar="X")
        url = f"/api/viaje/{self.viaje.id}/paradas/"
        self.assertEqual(self.c.post(f"{url}{it1.id}/cumplir/").status_code, 409)  # viaje aún programado
        self.c.post(f"/api/viaje/{self.viaje.id}/iniciar/")
        self.assertEqual(self.c.post(f"{url}{it1.id}/cumplir/").status_code, 200)
        self.assertEqual(self.c.post(f"{url}{it1.id}/cumplir/").status_code, 200)  # repetido: sin duplicar
        self.assertEqual(ParadaCumplida.objects.count(), 1)
        self.assertEqual(self.c.post(f"{url}{ajeno.id}/cumplir/").status_code, 404)
        lista = Escenario.cliente_http(self.e.cond_a).get(url).json()  # "reabrir la app"
        self.assertEqual([(p["nombre"], p["cumplida"]) for p in lista], [("Parada 1", True), ("Parada 2", False)])
        self.assertEqual(Escenario.cliente_http(self.e.cond_b).get(url).status_code, 404)
