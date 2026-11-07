from datetime import timedelta

from django.test import TestCase

from buses.models import Asiento, Viaje
from buses.views import hoy_colombia
from reservas.models import AsientoReserva, GpsPunto, Reserva
from usuarios.pruebas import Escenario


class SillasRegresionTest(TestCase):
    """El flujo de sillas de la app sigue funcionando con permisos activos."""

    def setUp(self):
        self.e = Escenario()
        self.s1 = Asiento.objects.create(numero_asiento=1, tipo_bus=self.e.tipo_a)
        self.s2 = Asiento.objects.create(numero_asiento=2, tipo_bus=self.e.tipo_a)
        self.salida = Viaje.objects.create(paquete=self.e.paq_a, bus=self.e.bus_a,
                                           fecha=hoy_colombia() + timedelta(days=7), hora="06:30")

    def reservar(self, c):
        r = c.post("/api/reserva/", {"fecha_reserva": "2026-10-20", "paquete_id": self.e.paq_a.id,
                                     "viaje_id": self.salida.id}, format="json")
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
        # RUT-52: el cliente ya no cancela por su cuenta (se comunica con la agencia); la agencia sí
        self.assertEqual(c2.delete(f"/api/reserva/{r2}/").status_code, 403)
        self.assertEqual(Reserva.objects.get(id=r2).estado, "pendiente")
        self.assertEqual(Escenario.cliente_http(self.e.admin_a).delete(f"/api/reserva/{r2}/").status_code, 200)
        self.assertEqual(Reserva.objects.get(id=r2).estado, "cancelada")
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

    def test_documento_de_quien_viaja(self):
        titular = self.reserva("aprobado")
        otra_persona = self.reserva("aprobado")
        otra_persona.pasajero_nombre, otra_persona.pasajero_documento = "Ana Pérez", "1234567"
        otra_persona.save()
        self.assertEqual(self.abordar(codigo=codigo_reserva(titular.id)).json()["documento"],
                         self.e.cliente.numero_documento)
        self.assertEqual(self.abordar(codigo=codigo_reserva(otra_persona.id)).json()["documento"], "1234567")
        rechazada = self.reserva("pendiente")
        self.assertEqual(self.abordar(codigo=codigo_reserva(rechazada.id)).json()["pasajero"]["documento"],
                         self.e.cliente.numero_documento)

    def test_por_paquete_tambien_exige_pago_y_es_solo_personal(self):
        r = self.reserva("pendiente")
        admin = Escenario.cliente_http(self.e.admin_a)
        self.assertEqual(admin.post(f"/api/paquete/{self.e.paq_a.id}/abordar/", {"reserva_id": r.id},
                                    format="json").status_code, 400)  # falta viaje_id
        self.assertEqual(admin.post(f"/api/paquete/{self.e.paq_a.id}/abordar/",
                                    {"reserva_id": r.id, "viaje_id": self.viaje.id}, format="json").status_code, 409)
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


class SalidasTest(TestCase):
    """Fase 2 (AND-007): el cliente elige la salida; las sillas se ocupan por salida."""

    def setUp(self):
        self.e = Escenario()
        hoy = hoy_colombia()
        self.e.paq_a.precio = 50000
        self.e.paq_a.save()
        self.v1 = Viaje.objects.create(paquete=self.e.paq_a, bus=self.e.bus_a, fecha=hoy + timedelta(days=7), hora="06:30")
        self.v2 = Viaje.objects.create(paquete=self.e.paq_a, bus=self.e.bus_a2, fecha=hoy + timedelta(days=7), hora="06:30")
        self.vieja = Viaje.objects.create(paquete=self.e.paq_a, bus=self.e.bus_a, fecha=hoy - timedelta(days=3), hora="06:30")
        self.completa = Viaje.objects.create(paquete=self.e.paq_a, bus=self.e.bus_a, fecha=hoy + timedelta(days=1),
                                             hora="07:00", estado=Viaje.COMPLETADO)
        self.vb = Viaje.objects.create(paquete=self.e.paq_b, bus=self.e.bus_b, fecha=hoy + timedelta(days=7), hora="06:30")
        self.s1 = Asiento.objects.create(numero_asiento=1, tipo_bus=self.e.tipo_a)
        self.s2 = Asiento.objects.create(numero_asiento=2, tipo_bus=self.e.tipo_a)
        self.sb = Asiento.objects.create(numero_asiento=1, tipo_bus=self.e.tipo_b)
        self.c = Escenario.cliente_http(self.e.cliente)
        self.c2 = Escenario.cliente_http(self.e.otro_cliente)

    def reservar(self, c, viaje, paquete=None):
        return c.post("/api/reserva/", {"fecha_reserva": "2026-10-27", "paquete_id": (paquete or self.e.paq_a).id,
                                        "viaje_id": viaje.id if viaje else None}, format="json")

    def ocupados(self, viaje):
        lista = self.c.get(f"/api/asiento/?viaje_id={viaje.id}").json()
        return {a["numero_asiento"] for a in lista if a["ocupado"]}

    def test_cliente_ve_salidas_programadas(self):
        ids = {v["id"] for v in self.c.get(f"/api/viaje/?paquete_id={self.e.paq_a.id}").json()}
        self.assertEqual(ids, {self.v1.id, self.v2.id})
        salida = self.c.get(f"/api/viaje/{self.v1.id}/").json()
        self.assertEqual((salida["hora"], salida["tipo_bus_id"]), ("06:30", self.e.tipo_a.id))

    def test_ve_la_salida_de_su_reserva_aunque_termine(self):
        Reserva.objects.create(fecha_reserva=timezone.now(), usuario=self.e.cliente, paquete=self.e.paq_a,
                               viaje=self.completa)
        ids = {v["id"] for v in self.c.get("/api/viaje/").json()}
        self.assertIn(self.completa.id, ids)
        self.assertNotIn(self.completa.id, {v["id"] for v in self.c2.get("/api/viaje/").json()})

    def test_ocupacion_por_salida(self):
        r1 = self.reservar(self.c, self.v1).json()["id"]
        self.assertEqual(self.c.post("/api/asientoreserva/", {"asiento_id": self.s1.id, "reserva_id": r1},
                                     format="json").status_code, 200)
        self.assertEqual(self.ocupados(self.v1), {1})
        self.assertEqual(self.ocupados(self.v2), set())
        # la misma silla en OTRA salida sí se puede reservar
        r2 = self.reservar(self.c2, self.v2).json()["id"]
        self.assertEqual(self.c2.post("/api/asientoreserva/", {"asiento_id": self.s1.id, "reserva_id": r2},
                                      format="json").status_code, 200)
        # en la misma salida, no
        r3 = self.reservar(self.c2, self.v1).json()["id"]
        self.assertEqual(self.c2.post("/api/asientoreserva/", {"asiento_id": self.s1.id, "reserva_id": r3},
                                      format="json").status_code, 409)
        # una reserva antigua sin salida bloquea su silla en todas las salidas del paquete
        vieja = Reserva.objects.create(fecha_reserva=timezone.now(), usuario=self.e.cliente, paquete=self.e.paq_a)
        AsientoReserva.objects.create(reserva=vieja, asiento=self.s2)
        self.assertEqual(self.ocupados(self.v1), {1, 2})
        self.assertEqual(self.ocupados(self.v2), {1, 2})

    def test_reserva_exige_salida_valida(self):
        self.assertEqual(self.reservar(self.c, None).status_code, 400)
        self.assertEqual(self.reservar(self.c, self.vb).status_code, 400)  # salida de otro paquete
        self.assertEqual(self.reservar(self.c, self.completa).status_code, 400)
        self.assertEqual(self.reservar(self.c, self.vieja).status_code, 400)
        ok = self.reservar(self.c, self.v1)
        self.assertEqual(ok.status_code, 201)
        self.assertEqual(ok.json()["viaje_id"], self.v1.id)
        self.assertEqual(Reserva.objects.get(id=ok.json()["id"]).viaje_id, self.v1.id)

    def test_silla_de_otro_bus_no_entra(self):
        r = self.reservar(self.c, self.v1).json()["id"]
        respuesta = self.c.post("/api/asientoreserva/", {"asiento_id": self.sb.id, "reserva_id": r}, format="json")
        self.assertEqual(respuesta.status_code, 400)

    def test_reserva_json_trae_salida_y_total(self):
        r = self.reservar(self.c, self.v1).json()["id"]
        for s in (self.s1, self.s2):
            self.c.post("/api/asientoreserva/", {"asiento_id": s.id, "reserva_id": r}, format="json")
        datos = self.c.get(f"/api/reserva/{r}/").json()
        self.assertEqual(datos["total"], "100000.00")
        self.assertEqual(datos["viaje_fecha"], self.v1.fecha.isoformat())
        self.assertEqual(datos["viaje_hora"], "06:30")
        self.assertEqual(datos["viaje_estado"], "PROGRAMADO")
        self.assertEqual(datos["placa"], "AAA111")
        self.assertEqual((datos["paquete"], datos["agencia_id"]), ("PA", self.e.ag_a.id))

    def test_reserva_sin_salida_sigue_visible(self):
        vieja = Reserva.objects.create(fecha_reserva=timezone.now(), usuario=self.e.cliente, paquete=self.e.paq_a)
        lista = self.c.get(f"/api/reserva/usuario/{self.e.cliente.id}/")
        self.assertEqual(lista.status_code, 200)
        datos = [x for x in lista.json() if x["id"] == vieja.id][0]
        self.assertIsNone(datos["viaje_id"])
        self.assertIsNone(datos["viaje_estado"])
        self.assertEqual(datos["total"], "0.00")


class ChatPorSalidaTest(TestCase):
    """Fase 2 (AND-011): chat por salida con autor; cada cliente ve lo suyo y lo del conductor."""

    def setUp(self):
        self.e = Escenario()
        hoy = hoy_colombia()
        self.v1 = Viaje.objects.create(paquete=self.e.paq_a, bus=self.e.bus_a, fecha=hoy + timedelta(days=2), hora="06:30")
        self.v2 = Viaje.objects.create(paquete=self.e.paq_a, bus=self.e.bus_a2, fecha=hoy + timedelta(days=2), hora="06:30")
        Bus_Conductor.objects.create(bus=self.e.bus_a, conductor=self.e.cond_a)
        self.tercero = self.e.usuario("tercero@rt.co", 4)
        for usuario, viaje in ((self.e.cliente, self.v1), (self.e.otro_cliente, self.v1), (self.tercero, self.v2)):
            Reserva.objects.create(fecha_reserva=timezone.now(), usuario=usuario, paquete=self.e.paq_a, viaje=viaje)
        self.cliente = Escenario.cliente_http(self.e.cliente)
        self.otro = Escenario.cliente_http(self.e.otro_cliente)
        self.conductor = Escenario.cliente_http(self.e.cond_a)

    def escribir(self, c, texto):
        r = c.post("/api/chat/", {"viaje_id": self.v1.id, "texto": texto}, format="json")
        self.assertEqual(r.status_code, 201)

    def test_chat_trae_autor(self):
        self.escribir(self.cliente, "hola")
        m = self.conductor.get(f"/api/chat/?viaje_id={self.v1.id}").json()[0]
        self.assertEqual((m["texto"], m["autor"], m["rol_id"], m["usuario_id"]),
                         ("hola", self.e.cliente.nombre_completo, 4, self.e.cliente.id))

    def test_cliente_no_ve_mensajes_de_otro_cliente(self):
        self.escribir(self.cliente, "mío")
        self.escribir(self.otro, "del otro")
        self.escribir(self.conductor, "salimos a las 6")
        textos = [m["texto"] for m in self.cliente.get(f"/api/chat/?viaje_id={self.v1.id}").json()]
        self.assertEqual(textos, ["mío", "salimos a las 6"])
        todos = [m["texto"] for m in self.conductor.get(f"/api/chat/?viaje_id={self.v1.id}").json()]
        self.assertEqual(todos, ["mío", "del otro", "salimos a las 6"])

    def test_cliente_de_otra_salida_no_ve_gps_ni_chat(self):
        de_v2 = Escenario.cliente_http(self.tercero)
        self.assertEqual(de_v2.get(f"/api/gps/?viaje_id={self.v1.id}").status_code, 403)
        self.assertEqual(de_v2.get(f"/api/chat/?viaje_id={self.v1.id}").status_code, 403)
        self.assertEqual(self.cliente.get(f"/api/gps/?viaje_id={self.v1.id}").status_code, 200)


class PasajeroTest(TestCase):
    """Fase 2 (AND-016): el pasajero puede ser otra persona; vacío = viaja el titular."""

    def setUp(self):
        self.e = Escenario()
        self.v = Viaje.objects.create(paquete=self.e.paq_a, bus=self.e.bus_a,
                                      fecha=hoy_colombia() + timedelta(days=3), hora="06:30")
        Bus_Conductor.objects.create(bus=self.e.bus_a, conductor=self.e.cond_a)
        self.c = Escenario.cliente_http(self.e.cliente)

    def reservar(self, nombre="", documento=""):
        return self.c.post("/api/reserva/", {"fecha_reserva": "2026-10-27", "paquete_id": self.e.paq_a.id,
                                             "viaje_id": self.v.id, "pasajero_nombre": nombre,
                                             "pasajero_documento": documento}, format="json")

    def test_reserva_con_otro_pasajero(self):
        r = self.reservar("Ana Pérez", "1234567")
        self.assertEqual(r.status_code, 201)
        self.assertEqual((r.json()["pasajero_nombre"], r.json()["pasajero_documento"]), ("Ana Pérez", "1234567"))
        guardada = Reserva.objects.get(id=r.json()["id"])
        self.assertEqual((guardada.pasajero_nombre, guardada.pasajero_documento), ("Ana Pérez", "1234567"))

    def test_sin_pasajero_viaja_el_titular(self):
        r = self.reservar()
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["pasajero_nombre"], "")

    def test_pasajero_invalido(self):
        self.assertEqual(self.reservar("Ana Pérez", "12ab567").status_code, 400)
        self.assertEqual(self.reservar("Ana Pérez", "").status_code, 400)
        self.assertEqual(self.reservar("A", "1234567").status_code, 400)
        self.assertEqual(self.reservar("Ana Pérez", "1234").status_code, 400)
        self.assertFalse(Reserva.objects.exists())

    def test_conductor_ve_nombre_del_pasajero(self):
        self.reservar("Ana Pérez", "1234567")
        self.reservar()
        nombres = {p["nombre"] for p in Escenario.cliente_http(self.e.cond_a).get(f"/api/viaje/{self.v.id}/pasajeros/").json()}
        self.assertEqual(nombres, {"Ana Pérez", self.e.cliente.nombre_completo})


class ReservaPorViajeTest(TestCase):
    """Sub-paso 1A: toda reserva nueva pertenece a una salida; dos salidas del mismo paquete no se cruzan."""

    def setUp(self):
        self.e = Escenario()
        hoy = hoy_colombia()
        self.v1 = Viaje.objects.create(paquete=self.e.paq_a, bus=self.e.bus_a, fecha=hoy + timedelta(days=3), hora="06:30")
        self.v2 = Viaje.objects.create(paquete=self.e.paq_a, bus=self.e.bus_a2, fecha=hoy + timedelta(days=4), hora="07:00")
        self.s1 = Asiento.objects.create(numero_asiento=1, tipo_bus=self.e.tipo_a)
        self.admin = Escenario.cliente_http(self.e.admin_a)

    def reserva(self, viaje, silla=None, pago=None):
        r = Reserva.objects.create(fecha_reserva=timezone.now(), usuario=self.e.cliente, paquete=self.e.paq_a, viaje=viaje)
        if silla:
            AsientoReserva.objects.create(reserva=r, asiento=silla)
        if pago:
            Pago.objects.create(precio=1, reserva=r, fecha_pago=timezone.now(), estado=pago)
        return r

    def test_personal_tambien_debe_indicar_salida(self):
        sin = self.admin.post("/api/reserva/", {"paquete_id": self.e.paq_a.id, "usuario_id": self.e.cliente.id},
                              format="json")
        self.assertEqual(sin.status_code, 400)
        con = self.admin.post("/api/reserva/", {"paquete_id": self.e.paq_a.id, "viaje_id": self.v2.id,
                                                "usuario_id": self.e.cliente.id}, format="json")
        self.assertEqual(con.status_code, 201)
        datos = con.json()
        self.assertEqual((datos["viaje_id"], datos["viaje_hora"], datos["paquete"], datos["cliente_nombre"]),
                         (self.v2.id, "07:00", "PA", self.e.cliente.nombre_completo))

    def test_filtro_por_viaje(self):
        r1, r2 = self.reserva(self.v1), self.reserva(self.v2)
        ids = [x["id"] for x in self.admin.get(f"/api/reserva/?viaje_id={self.v1.id}").json()]
        self.assertEqual(ids, [r1.id])
        self.assertNotIn(r2.id, ids)
        self.assertEqual(self.admin.get("/api/reserva/?viaje_id=abc").status_code, 400)
        # otra agencia no ve nada aunque conozca el id del viaje
        self.assertEqual(Escenario.cliente_http(self.e.admin_b).get(f"/api/reserva/?viaje_id={self.v1.id}").json(), [])

    def test_asignar_salida_a_reserva_antigua(self):
        vieja = self.reserva(None, silla=self.s1)
        r = self.admin.put(f"/api/reserva/{vieja.id}/", {"viaje_id": self.v1.id}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["viaje_id"], self.v1.id)
        # su silla ya no bloquea la otra salida
        lista = self.admin.get(f"/api/asiento/?viaje_id={self.v2.id}").json()
        self.assertFalse([a for a in lista if a["ocupado"]])
        # ya tiene salida y sillas: no se mueve
        self.assertEqual(self.admin.put(f"/api/reserva/{vieja.id}/", {"viaje_id": self.v2.id}, format="json").status_code, 409)

    def test_asignar_salida_con_silla_ocupada_da_409(self):
        self.reserva(self.v1, silla=self.s1)
        vieja = self.reserva(None, silla=self.s1)
        r = self.admin.put(f"/api/reserva/{vieja.id}/", {"viaje_id": self.v1.id}, format="json")
        self.assertEqual(r.status_code, 409)
        self.assertIsNone(Reserva.objects.get(id=vieja.id).viaje_id)
        otra = Viaje.objects.create(paquete=self.e.paq_b, bus=self.e.bus_b, fecha=self.v1.fecha, hora="06:30")
        self.assertEqual(self.admin.put(f"/api/reserva/{vieja.id}/", {"viaje_id": otra.id}, format="json").status_code, 400)

    def test_pasajeros_y_abordaje_por_paquete_no_mezclan_salidas(self):
        r1 = self.reserva(self.v1, pago="aprobado")
        r2 = self.reserva(self.v2, pago="aprobado")
        todos = self.admin.get(f"/api/paquete/{self.e.paq_a.id}/pasajeros/").json()
        self.assertEqual([(p["id"], p["viaje_id"]) for p in todos], [(r1.id, self.v1.id), (r2.id, self.v2.id)])
        solo_v1 = self.admin.get(f"/api/paquete/{self.e.paq_a.id}/pasajeros/?viaje_id={self.v1.id}").json()
        self.assertEqual([p["id"] for p in solo_v1], [r1.id])
        url = f"/api/paquete/{self.e.paq_a.id}/abordar/"
        otro = self.admin.post(url, {"reserva_id": r2.id, "viaje_id": self.v1.id}, format="json")
        self.assertEqual((otro.status_code, otro.json()["motivo"]), (409, "otro_viaje"))
        self.assertEqual(self.admin.post(url, {"reserva_id": r1.id, "viaje_id": self.v1.id}, format="json").status_code, 200)

    def test_viaje_con_reservas_no_se_borra(self):
        self.reserva(self.v1)
        self.assertEqual(self.admin.delete(f"/api/viaje/{self.v1.id}/").status_code, 409)


class ListaPasajerosAdminTest(TestCase):
    """RUT-52 (HU-W-29): el administrador ve los pasajeros con pago aprobado de los viajes de SU agencia."""

    def setUp(self):
        self.e = Escenario()
        self.v = Viaje.objects.create(paquete=self.e.paq_a, bus=self.e.bus_a,
                                      fecha=hoy_colombia() + timedelta(days=5), hora="07:00")
        self.otra_salida = Viaje.objects.create(paquete=self.e.paq_a, bus=self.e.bus_a2,
                                                fecha=hoy_colombia() + timedelta(days=5), hora="09:00")
        self.admin_a = Escenario.cliente_http(self.e.admin_a)
        self.url = f"/api/paquete/{self.e.paq_a.id}/pasajeros/?viaje_id={self.v.id}&pago=aprobado"
        self.aprobada = self.reserva(self.e.cliente, self.v, "aprobado")
        self.pendiente = self.reserva(self.e.otro_cliente, self.v, "pendiente")
        self.rechazada = self.reserva(self.e.otro_cliente, self.v, "rechazado")
        self.sin_pago = self.reserva(self.e.otro_cliente, self.v, None)
        self.de_otra_salida = self.reserva(self.e.cliente, self.otra_salida, "aprobado")

    def reserva(self, usuario, viaje, pago):
        r = Reserva.objects.create(fecha_reserva=timezone.now(), usuario=usuario, paquete=self.e.paq_a, viaje=viaje)
        if pago:
            Pago.objects.create(precio=1, reserva=r, fecha_pago=timezone.now(), estado=pago)
        return r

    def ids(self, respuesta):
        self.assertEqual(respuesta.status_code, 200)
        return {p["id"] for p in respuesta.json()}

    def test_solo_pasajeros_con_pago_aprobado_de_esa_salida(self):
        self.assertEqual(self.ids(self.admin_a.get(self.url)), {self.aprobada.id})

    def test_cuenta_el_ultimo_pago(self):
        # Un pago aprobado seguido de uno rechazado ya no puede abordar (misma regla que el abordaje).
        Pago.objects.create(precio=1, reserva=self.aprobada, fecha_pago=timezone.now(), estado="rechazado")
        Pago.objects.create(precio=1, reserva=self.pendiente, fecha_pago=timezone.now(), estado="aprobado")
        self.assertEqual(self.ids(self.admin_a.get(self.url)), {self.pendiente.id})

    def test_sin_filtro_sigue_trayendo_todas_las_vigentes(self):
        # La app del conductor no se rompe: sin ?pago= trae también pendientes y sin pago.
        conductor = Escenario.cliente_http(self.e.cond_a)
        Bus_Conductor.objects.create(bus=self.e.bus_a, conductor=self.e.cond_a)
        todas = {self.aprobada.id, self.pendiente.id, self.rechazada.id, self.sin_pago.id}
        self.assertEqual(self.ids(conductor.get(f"/api/viaje/{self.v.id}/pasajeros/")), todas)
        self.assertEqual(self.ids(conductor.get(f"/api/viaje/{self.v.id}/pasajeros/?pago=aprobado")),
                         {self.aprobada.id})

    def test_pago_invalido_400(self):
        r = self.admin_a.get(f"/api/paquete/{self.e.paq_a.id}/pasajeros/?pago=pendiente")
        self.assertEqual(r.status_code, 400)

    def test_admin_de_otra_agencia_403_sin_datos(self):
        admin_b = Escenario.cliente_http(self.e.admin_b)
        for url in (self.url, f"/api/viaje/{self.v.id}/pasajeros/?pago=aprobado"):
            r = admin_b.get(url)
            self.assertEqual(r.status_code, 403)
            self.assertNotIn("nombre", r.content.decode())

    def test_superadmin_ve_la_lista(self):
        sup = Escenario.cliente_http(self.e.super)
        self.assertEqual(self.ids(sup.get(self.url)), {self.aprobada.id})

    def test_reserva_cancelada_por_la_agencia_desaparece(self):
        self.assertEqual(self.admin_a.delete(f"/api/reserva/{self.aprobada.id}/").status_code, 200)
        self.assertEqual(self.ids(self.admin_a.get(self.url)), set())
        # Sus pagos se conservan para la auditoría.
        self.assertTrue(Pago.objects.filter(reserva=self.aprobada).exists())

    def test_cliente_no_cancela_ni_su_reserva_sin_pago(self):
        cliente = Escenario.cliente_http(self.e.otro_cliente)
        self.assertEqual(cliente.delete(f"/api/reserva/{self.sin_pago.id}/").status_code, 403)
        self.assertEqual(Reserva.objects.get(id=self.sin_pago.id).estado, "pendiente")

    def test_admin_de_otra_agencia_no_cancela(self):
        admin_b = Escenario.cliente_http(self.e.admin_b)
        self.assertEqual(admin_b.delete(f"/api/reserva/{self.aprobada.id}/").status_code, 403)
        self.assertEqual(Reserva.objects.get(id=self.aprobada.id).estado, "pendiente")


class ChatEstadoViajeTest(TestCase):
    """RUT-60 y RUT-62: chat grupal por salida; se escribe en PROGRAMADO y EN_CURSO, no en COMPLETADO."""

    def setUp(self):
        self.e = Escenario()
        self.v = Viaje.objects.create(paquete=self.e.paq_a, bus=self.e.bus_a,
                                      fecha=hoy_colombia() + timedelta(days=1), hora="06:30")
        self.otro_viaje = Viaje.objects.create(paquete=self.e.paq_a, bus=self.e.bus_a2,
                                               fecha=hoy_colombia() + timedelta(days=1), hora="06:30")
        Bus_Conductor.objects.create(bus=self.e.bus_a, conductor=self.e.cond_a)
        Reserva.objects.create(fecha_reserva=timezone.now(), usuario=self.e.cliente, paquete=self.e.paq_a, viaje=self.v)
        Reserva.objects.create(fecha_reserva=timezone.now(), usuario=self.e.otro_cliente, paquete=self.e.paq_a,
                               viaje=self.otro_viaje)
        self.cliente = Escenario.cliente_http(self.e.cliente)
        self.conductor = Escenario.cliente_http(self.e.cond_a)

    def enviar(self, c, viaje, texto="hola"):
        return c.post("/api/chat/", {"viaje_id": viaje.id, "texto": texto}, format="json")

    def poner(self, estado):
        Viaje.objects.filter(id=self.v.id).update(estado=estado)

    def test_cliente_y_conductor_escriben_programado_y_en_curso(self):
        for estado in (Viaje.PROGRAMADO, Viaje.EN_CURSO):
            self.poner(estado)
            self.assertEqual(self.enviar(self.cliente, self.v, f"cliente {estado}").status_code, 201)
            self.assertEqual(self.enviar(self.conductor, self.v, f"conductor {estado}").status_code, 201)
        # El mensaje del cliente queda asociado al paquete del viaje (criterio RUT-60).
        self.assertTrue(ChatMensaje.objects.filter(viaje=self.v, paquete=self.e.paq_a, usuario=self.e.cliente).exists())

    def test_conductor_ve_al_cliente_y_el_cliente_ve_al_conductor(self):
        self.enviar(self.cliente, self.v, "¿a qué hora salimos?")
        self.enviar(self.conductor, self.v, "a las 6:30")
        textos_conductor = [m["texto"] for m in self.conductor.get(f"/api/chat/?viaje_id={self.v.id}").json()]
        textos_cliente = [m["texto"] for m in self.cliente.get(f"/api/chat/?viaje_id={self.v.id}").json()]
        self.assertEqual(textos_conductor, ["¿a qué hora salimos?", "a las 6:30"])
        self.assertEqual(textos_cliente, ["¿a qué hora salimos?", "a las 6:30"])

    def test_viaje_completado_no_recibe_mensajes_pero_se_lee(self):
        self.enviar(self.cliente, self.v, "antes de llegar")
        self.poner(Viaje.COMPLETADO)
        for c in (self.cliente, self.conductor):
            r = self.enviar(c, self.v, "después")
            self.assertEqual(r.status_code, 409)
            self.assertEqual(r.json()["motivo"], "viaje_finalizado")
        self.assertEqual(ChatMensaje.objects.count(), 1)
        self.assertEqual(self.cliente.get(f"/api/chat/?viaje_id={self.v.id}").status_code, 200)

    def test_viaje_ajeno_403_y_no_guarda(self):
        # Conductor escribiendo en una salida de otro bus; cliente y admin de otra salida/agencia.
        self.assertEqual(self.enviar(self.conductor, self.otro_viaje).status_code, 403)
        self.assertEqual(self.enviar(self.cliente, self.otro_viaje).status_code, 403)
        self.assertEqual(self.enviar(Escenario.cliente_http(self.e.cond_b), self.v).status_code, 403)
        self.assertEqual(self.enviar(Escenario.cliente_http(self.e.admin_b), self.v).status_code, 403)
        self.assertEqual(ChatMensaje.objects.count(), 0)

    def test_403_antes_que_409(self):
        # A quien no es del viaje no se le revela que terminó.
        self.poner(Viaje.COMPLETADO)
        self.assertEqual(self.enviar(Escenario.cliente_http(self.e.cond_b), self.v).status_code, 403)

    def test_mensaje_vacio_400(self):
        self.assertEqual(self.enviar(self.conductor, self.v, "   ").status_code, 400)
        self.assertEqual(ChatMensaje.objects.count(), 0)

    def test_reserva_sin_salida_solo_lectura(self):
        r = self.cliente.post("/api/chat/", {"paquete_id": self.e.paq_a.id, "texto": "hola"}, format="json")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["motivo"], "sin_salida")
        self.assertEqual(self.cliente.get(f"/api/chat/?paquete_id={self.e.paq_a.id}").status_code, 200)
        self.assertEqual(ChatMensaje.objects.count(), 0)
