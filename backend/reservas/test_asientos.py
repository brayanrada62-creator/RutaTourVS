"""Flujo de asientos (auditoría Fase 2): disponibilidad, reserva atómica, plazo de 1 hora,
pagos y aislamiento entre agencias. Cada prueba corresponde a un hallazgo (Hxx) del informe."""
import io
import threading
from datetime import timedelta

from django.db import connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from buses.models import Asiento, TipoBus, Viaje
from buses.views import hoy_colombia
from pagos.models import Pago
from reservas.models import AsientoReserva, Reserva
from usuarios.pruebas import Escenario


def png():
    """Imagen PNG mínima y válida para el comprobante."""
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buf, "PNG")
    buf.seek(0)
    buf.name = "comprobante.png"
    return buf


class Base:
    def preparar(self):
        self.e = Escenario()
        self.s1 = Asiento.objects.create(numero_asiento=1, tipo_bus=self.e.tipo_a)
        self.s2 = Asiento.objects.create(numero_asiento=2, tipo_bus=self.e.tipo_a)
        self.s3 = Asiento.objects.create(numero_asiento=3, tipo_bus=self.e.tipo_a)
        self.sb = Asiento.objects.create(numero_asiento=1, tipo_bus=self.e.tipo_b)
        hoy = hoy_colombia()
        self.v1 = Viaje.objects.create(paquete=self.e.paq_a, bus=self.e.bus_a, fecha=hoy + timedelta(days=5), hora="06:30")
        self.v2 = Viaje.objects.create(paquete=self.e.paq_a, bus=self.e.bus_a2, fecha=hoy + timedelta(days=12), hora="06:30")
        self.e.paq_a.precio = 100000
        self.e.paq_a.save()

    def reservar(self, c, sillas=(), viaje=None, **extra):
        datos = {"paquete_id": self.e.paq_a.id, "viaje_id": (viaje or self.v1).id,
                 "asientos": ",".join(str(s.id) for s in sillas)}
        datos.update(extra)
        return c.post("/api/reserva/", datos, format="json")

    def ocupadas(self, c, viaje=None):
        lista = c.get(f"/api/asiento/?viaje_id={(viaje or self.v1).id}").json()
        return sorted(a["numero_asiento"] for a in lista if a["ocupado"])

    def pagar(self, c, reserva_id):
        return c.post("/api/pago/", {"reserva_id": reserva_id, "referencia": "x", "comprobante": png()},
                      format="multipart")


class ReservaAtomicaTest(Base, TestCase):
    def setUp(self):
        self.preparar()
        self.c1 = Escenario.cliente_http(self.e.cliente)
        self.c2 = Escenario.cliente_http(self.e.otro_cliente)
        self.admin = Escenario.cliente_http(self.e.admin_a)

    def test_reserva_y_sillas_en_una_sola_peticion(self):
        r = self.reservar(self.c1, [self.s1, self.s2])
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["asientos"], "1,2")
        self.assertEqual(r.json()["viaje_id"], self.v1.id)                       # H07
        self.assertIsNotNone(r.json()["vence_en"])
        self.assertEqual(self.ocupadas(self.c2), [1, 2])

    def test_si_una_silla_esta_ocupada_no_se_guarda_nada(self):             # H15
        self.reservar(self.c1, [self.s2])
        antes = Reserva.objects.count()
        r = self.reservar(self.c2, [self.s1, self.s2, self.s3])
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["ocupadas"], [2])
        self.assertEqual(Reserva.objects.count(), antes)
        self.assertEqual(self.ocupadas(self.c2), [2])

    def test_misma_silla_en_otra_salida_si_se_puede(self):                  # H07
        self.assertEqual(self.reservar(self.c1, [self.s1]).status_code, 201)
        self.assertEqual(self.reservar(self.c2, [self.s1], viaje=self.v2).status_code, 201)

    def test_silla_de_otro_bus_400(self):                                    # H10
        self.assertEqual(self.reservar(self.c1, [self.sb]).status_code, 400)

    def test_reintento_con_la_misma_clave_no_duplica(self):                 # H15
        a = self.reservar(self.c1, [self.s1], clave_idempotencia="abc-1")
        b = self.reservar(self.c1, [self.s1], clave_idempotencia="abc-1")
        self.assertEqual((a.status_code, b.status_code), (201, 200))
        self.assertEqual(a.json()["id"], b.json()["id"])
        self.assertEqual(Reserva.objects.filter(usuario=self.e.cliente).count(), 1)

    def test_paquete_no_activo_400(self):                                    # H18
        self.e.paq_a.estado = "agotado"
        self.e.paq_a.save()
        self.assertEqual(self.reservar(self.c1, [self.s1]).status_code, 400)

    def test_sin_fecha_usa_la_del_servidor(self):                           # H18
        r = self.reservar(self.c1, [self.s1])
        self.assertEqual(r.status_code, 201)
        self.assertIsNotNone(Reserva.objects.get(id=r.json()["id"]).fecha_reserva)

    def test_flujo_antiguo_por_silla_sigue_funcionando(self):
        r = self.reservar(self.c1)
        rid = r.json()["id"]
        self.assertEqual(self.c1.post("/api/asientoreserva/", {"asiento_id": self.s1.id, "reserva_id": rid},
                                      format="json").status_code, 200)
        r2 = self.reservar(self.c2)
        self.assertEqual(self.c2.post("/api/asientoreserva/", {"asiento_id": self.s1.id, "reserva_id": r2.json()["id"]},
                                      format="json").status_code, 409)

    def test_admin_no_mueve_una_venta_a_silla_ocupada(self):                # H02
        self.reservar(self.c1, [self.s1])
        r2 = self.reservar(self.c2, [self.s2]).json()["id"]
        ar = AsientoReserva.objects.get(reserva_id=r2)
        r = self.admin.put(f"/api/asientoreserva/{ar.id}/", {"asiento_id": self.s1.id, "reserva_id": r2}, format="json")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(AsientoReserva.objects.filter(asiento=self.s1).count(), 1)
        # a una libre sí
        self.assertEqual(self.admin.put(f"/api/asientoreserva/{ar.id}/", {"asiento_id": self.s3.id, "reserva_id": r2},
                                        format="json").status_code, 200)

    def test_cancelar_libera_y_conserva_pagos(self):                         # H13
        rid = self.reservar(self.c1, [self.s1]).json()["id"]
        Pago.objects.create(precio=1, reserva_id=rid, fecha_pago=timezone.now(), estado="rechazado")
        self.assertEqual(self.c1.delete(f"/api/reserva/{rid}/").status_code, 200)
        self.assertEqual(Reserva.objects.get(id=rid).estado, "cancelada")
        self.assertEqual(Pago.objects.filter(reserva_id=rid).count(), 1)
        self.assertEqual(self.ocupadas(self.c2), [])

    def test_reserva_cancelada_no_se_reactiva(self):
        rid = self.reservar(self.c1, [self.s1]).json()["id"]
        self.c1.delete(f"/api/reserva/{rid}/")
        r = self.admin.put(f"/api/reserva/{rid}/", {"estado": "pendiente"}, format="json")
        self.assertEqual(r.status_code, 409)

    def test_estado_invalido_400(self):                                      # H17
        rid = self.reservar(self.c1, [self.s1]).json()["id"]
        self.assertEqual(self.admin.put(f"/api/reserva/{rid}/", {"estado": "Cancelado"}, format="json").status_code, 400)

    def test_asiento_sin_filtro_400(self):                                   # H19
        self.assertEqual(self.c1.get("/api/asiento/").status_code, 400)
        self.assertEqual(self.c1.get(f"/api/asiento/?paquete_id={self.e.paq_a.id}").status_code, 400)
        self.assertEqual(len(self.c1.get(f"/api/asiento/?tipo_bus_id={self.e.tipo_a.id}").json()), 3)


class PlazoTest(Base, TestCase):
    """Reglas: 1 hora sin comprobante; el plazo se detiene en revisión; rechazado da 1 hora más."""

    def setUp(self):
        self.preparar()
        self.c1 = Escenario.cliente_http(self.e.cliente)
        self.c2 = Escenario.cliente_http(self.e.otro_cliente)
        self.admin = Escenario.cliente_http(self.e.admin_a)

    def vencer(self, rid):
        Reserva.objects.filter(id=rid).update(vence_en=timezone.now() - timedelta(minutes=1))

    def test_plazo_de_una_hora(self):
        rid = self.reservar(self.c1, [self.s1]).json()["id"]
        falta = Reserva.objects.get(id=rid).vence_en - timezone.now()
        self.assertTrue(timedelta(minutes=59) < falta <= timedelta(minutes=60))

    def test_vencida_libera_la_silla_y_no_se_puede_pagar(self):              # H09
        rid = self.reservar(self.c1, [self.s1]).json()["id"]
        self.vencer(rid)
        self.assertEqual(self.ocupadas(self.c2), [])
        self.assertEqual(Reserva.objects.get(id=rid).estado, "vencida")
        self.assertEqual(self.pagar(self.c1, rid).status_code, 400)
        self.assertEqual(self.reservar(self.c2, [self.s1]).status_code, 201)

    def test_pago_en_revision_detiene_el_plazo(self):
        rid = self.reservar(self.c1, [self.s1]).json()["id"]
        self.assertEqual(self.pagar(self.c1, rid).status_code, 200)
        self.assertIsNone(Reserva.objects.get(id=rid).vence_en)
        self.assertEqual(self.ocupadas(self.c2), [1])

    def test_rechazo_da_una_hora_para_reenviar_y_luego_libera(self):         # H08
        rid = self.reservar(self.c1, [self.s1]).json()["id"]
        self.pagar(self.c1, rid)
        pago = Pago.objects.get(reserva_id=rid)
        r = self.admin.put(f"/api/pago/{pago.id}/", {"estado": "rechazado", "motivo_rechazo": "ilegible"}, format="json")
        self.assertEqual(r.status_code, 200)
        reserva = Reserva.objects.get(id=rid)
        self.assertTrue(timedelta(minutes=59) < reserva.vence_en - timezone.now() <= timedelta(minutes=60))
        self.assertEqual(self.ocupadas(self.c2), [1])                         # sigue guardada
        self.assertEqual(self.pagar(self.c1, rid).status_code, 200)           # reenvía
        self.assertIsNone(Reserva.objects.get(id=rid).vence_en)
        # rechazado otra vez y no reenvía: vence y libera
        nuevo = Pago.objects.filter(reserva_id=rid).order_by("-id").first()
        self.admin.put(f"/api/pago/{nuevo.id}/", {"estado": "rechazado"}, format="json")
        self.vencer(rid)
        self.assertEqual(self.ocupadas(self.c2), [])

    def test_aprobado_vende_y_queda_auditoria(self):                        # H20
        rid = self.reservar(self.c1, [self.s1]).json()["id"]
        self.pagar(self.c1, rid)
        pago = Pago.objects.get(reserva_id=rid)
        self.admin.put(f"/api/pago/{pago.id}/", {"estado": "aprobado"}, format="json")
        pago.refresh_from_db()
        self.assertEqual(pago.revisado_por_id, self.e.admin_a.id)
        self.assertIsNotNone(pago.revisado_en)
        self.assertEqual(self.c1.get(f"/api/reserva/{rid}/").json()["estado"], "pagada")
        self.assertEqual(self.admin.get(f"/api/pago/{pago.id}/").json()["revisado_por"], self.e.admin_a.nombre_completo)

    def test_no_se_aprueba_un_pago_de_reserva_vencida(self):
        rid = self.reservar(self.c1, [self.s1]).json()["id"]
        pago = Pago.objects.create(precio=1, reserva_id=rid, fecha_pago=timezone.now(), estado="rechazado")
        self.vencer(rid)
        r = self.admin.put(f"/api/pago/{pago.id}/", {"estado": "aprobado"}, format="json")
        self.assertEqual(r.status_code, 409)

    def test_precio_lo_calcula_el_servidor(self):                            # H01
        rid = self.reservar(self.c1, [self.s1, self.s2]).json()["id"]
        self.c1.post("/api/pago/", {"reserva_id": rid, "precio": "1.00", "comprobante": png()}, format="multipart")
        self.assertEqual(Pago.objects.get(reserva_id=rid).precio, 200000)

    def test_estado_de_pago_invalido_400(self):
        rid = self.reservar(self.c1, [self.s1]).json()["id"]
        self.pagar(self.c1, rid)
        pago = Pago.objects.get(reserva_id=rid)
        self.assertEqual(self.admin.put(f"/api/pago/{pago.id}/", {"estado": "Aprobado!"}, format="json").status_code, 400)


class AislamientoYMapaTest(Base, TestCase):
    def setUp(self):
        self.preparar()
        self.c1 = Escenario.cliente_http(self.e.cliente)
        self.admin_a = Escenario.cliente_http(self.e.admin_a)
        self.admin_b = Escenario.cliente_http(self.e.admin_b)

    def test_admin_de_otra_agencia_no_toca_sillas_ni_tipos(self):          # H04
        self.assertEqual(self.admin_b.put(f"/api/asiento/{self.s2.id}/", {"tipo_bus_id": self.e.tipo_a.id,
                                                                          "numero_asiento": 9}, format="json").status_code, 403)
        self.assertEqual(self.admin_b.post("/api/asiento/", {"tipo_bus_id": self.e.tipo_a.id, "numero_asiento": 9},
                                           format="json").status_code, 403)
        self.assertEqual(self.admin_b.delete(f"/api/asiento/{self.s1.id}/").status_code, 403)
        self.assertEqual(self.admin_b.delete(f"/api/tipobus/{self.e.tipo_a.id}/").status_code, 403)
        self.assertEqual(self.admin_b.post("/api/tipobus/", {"nombre": "X", "agencia_id": self.e.ag_a.id, "capacidad": 1,
                                                             "descripcion": ""}, format="json").status_code, 403)

    def test_silla_repetida_409_y_silla_vendida_no_se_borra(self):         # H16
        self.assertEqual(self.admin_a.post("/api/asiento/", {"tipo_bus_id": self.e.tipo_a.id, "numero_asiento": 1},
                                           format="json").status_code, 409)
        self.reservar(self.c1, [self.s1])
        self.assertEqual(self.admin_a.delete(f"/api/asiento/{self.s1.id}/").status_code, 409)

    def test_bus_con_tipo_de_otra_agencia_400(self):                         # H11
        datos = {"placa": "ZZZ999", "agencia_id": self.e.ag_a.id, "tipo_bus_id": self.e.tipo_b.id, "marca": "m",
                 "modelo": "m", "estado": "activo", "fecha_registro": "2026-10-28"}
        self.assertEqual(self.admin_a.post("/api/bus/", datos, format="json").status_code, 400)
        datos["tipo_bus_id"] = self.e.tipo_a.id
        self.assertEqual(self.admin_a.post("/api/bus/", datos, format="json").status_code, 200)

    def test_no_se_cambia_el_tipo_del_bus_de_una_salida_con_ventas(self):   # H03
        otro_tipo = TipoBus.objects.create(nombre="Grande", agencia=self.e.ag_a, capacidad=40, descripcion="")
        bus_g = Escenario.bus("GGG111", self.e.ag_a, otro_tipo)
        self.reservar(self.c1, [self.s1])
        r = self.admin_a.put(f"/api/viaje/{self.v1.id}/", {"bus_id": bus_g.id}, format="json")
        self.assertEqual(r.status_code, 409)
        # a un bus del mismo tipo sí (bus_a2 comparte tipo_a)
        r = self.admin_a.put(f"/api/viaje/{self.v1.id}/", {"bus_id": self.e.bus_a2.id, "hora": "09:00"}, format="json")
        self.assertEqual(r.status_code, 200)
        datos = {"placa": "AAA111", "agencia_id": self.e.ag_a.id, "tipo_bus_id": otro_tipo.id, "marca": "m",
                 "modelo": "m", "estado": "activo", "fecha_registro": "2026-10-28"}
        self.assertEqual(self.admin_a.put(f"/api/bus/{self.e.bus_a2.id}/", datos, format="json").status_code, 409)


class ConcurrenciaTest(Base, TransactionTestCase):
    """Peticiones simultáneas reales (cada hilo con su conexión a la base)."""

    def setUp(self):
        self.preparar()

    def carrera(self, funciones):
        barrera = threading.Barrier(len(funciones))
        resultados = [None] * len(funciones)

        def correr(i, f):
            try:
                barrera.wait()
                resultados[i] = f()
            finally:
                connections.close_all()

        hilos = [threading.Thread(target=correr, args=(i, f)) for i, f in enumerate(funciones)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        return resultados

    def test_dos_clientes_por_las_mismas_sillas(self):
        c1 = Escenario.cliente_http(self.e.cliente)
        c2 = Escenario.cliente_http(self.e.otro_cliente)
        for _ in range(5):
            Reserva.objects.update(estado="cancelada")
            res = self.carrera([lambda: self.reservar(c1, [self.s1, self.s2]).status_code,
                                lambda: self.reservar(c2, [self.s2, self.s3]).status_code])
            self.assertEqual(sorted(res), [201, 409])
            vendidas = AsientoReserva.objects.filter(reserva__estado="pendiente", asiento=self.s2).count()
            self.assertEqual(vendidas, 1)

    def test_pagos_simultaneos_dejan_uno_solo(self):                         # H14
        c1 = Escenario.cliente_http(self.e.cliente)
        rid = self.reservar(c1, [self.s1]).json()["id"]
        for _ in range(5):
            Pago.objects.filter(reserva_id=rid).delete()
            res = self.carrera([lambda: self.pagar(c1, rid).status_code] * 4)
            self.assertEqual(sorted(res), [200, 409, 409, 409])
            self.assertEqual(Pago.objects.filter(reserva_id=rid).count(), 1)
