from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from usuarios.pruebas import Escenario

from usuarios.models import Agencia, Rol, Usuario, UsuarioAgencia
from buses.models import Bus, Bus_Conductor, TipoBus


class BusConductorFase1Test(TestCase):
    def setUp(self):
        self.e = Escenario()
        self.c = Escenario.cliente_http(self.e.admin_a)

    def test_listar_ya_no_da_500(self):
        self.assertEqual(self.c.get("/api/bus-conductor/").status_code, 200)

    def test_asignar_y_consultar_por_conductor(self):
        r = self.c.post("/api/bus-conductor/", {"bus_id": self.e.bus_a.id, "conductor_id": self.e.cond_a.id}, format="json")
        self.assertEqual(r.status_code, 201)
        lista = self.c.get(f"/api/bus-conductor/?conductor_id={self.e.cond_a.id}").json()
        self.assertEqual(len(lista), 1)
        self.assertEqual(lista[0]["placa"], "AAA111")
        self.assertEqual(self.c.get(f"/api/bus-conductor/?conductor_id={self.e.cliente.id}").json(), [])

    def test_no_duplica(self):
        datos = {"bus_id": self.e.bus_a.id, "conductor_id": self.e.cond_a.id}
        self.assertEqual(self.c.post("/api/bus-conductor/", datos, format="json").status_code, 201)
        self.assertEqual(self.c.post("/api/bus-conductor/", datos, format="json").status_code, 200)
        self.assertEqual(Bus_Conductor.objects.count(), 1)

    def test_valida_agencia_rol_y_existencia(self):
        s = Escenario.cliente_http(self.e.super)
        otra = s.post("/api/bus-conductor/", {"bus_id": self.e.bus_b.id, "conductor_id": self.e.cond_a.id}, format="json")
        self.assertEqual(otra.status_code, 400)
        no_conductor = s.post("/api/bus-conductor/", {"bus_id": self.e.bus_a.id, "conductor_id": self.e.cliente.id}, format="json")
        self.assertEqual(no_conductor.status_code, 400)
        self.assertEqual(s.post("/api/bus-conductor/", {"bus_id": 999, "conductor_id": self.e.cond_a.id}, format="json").status_code, 404)
        self.assertEqual(s.get("/api/bus-conductor/?conductor_id=abc").status_code, 400)

    def test_detalle_404(self):
        self.assertEqual(self.c.get("/api/bus-conductor/999/").status_code, 404)
        self.assertEqual(self.c.delete("/api/bus-conductor/999/").status_code, 404)
        self.assertEqual(self.c.get("/api/bus/999/").status_code, 404)
        self.assertEqual(self.c.get("/api/reserva/999/").status_code, 404)

    def test_abordar_inexistente_404(self):
        r = self.c.post(f"/api/paquete/{self.e.paq_a.id}/abordar/", {"reserva_id": 999999}, format="json")
        self.assertEqual(r.status_code, 404)


class MigracionDuplicadosTest(TransactionTestCase):
    """La migración 0004 borra filas repetidas antes de crear la restricción única."""

    def test_migracion_quita_duplicados(self):
        ejecutor = MigrationExecutor(connection)
        ejecutor.migrate([("buses", "0003_remove_bus_conductor_alter_asiento_id_alter_bus_id_and_more")])
        viejas = ejecutor.loader.project_state(
            [("buses", "0003_remove_bus_conductor_alter_asiento_id_alter_bus_id_and_more")]).apps
        BC = viejas.get_model("buses", "Bus_Conductor")
        e = Escenario()
        bus = viejas.get_model("buses", "Bus").objects.get(id=e.bus_a.id)
        u = viejas.get_model("usuarios", "Usuario").objects.only("id").get(id=e.cond_a.id)
        for _ in range(3):
            BC.objects.create(bus=bus, conductor=u)
        ejecutor = MigrationExecutor(connection)
        ejecutor.loader.build_graph()
        ejecutor.migrate([("buses", "0004_bus_conductor_unico")])
        nuevas = ejecutor.loader.project_state([("buses", "0004_bus_conductor_unico")]).apps
        self.assertEqual(nuevas.get_model("buses", "Bus_Conductor").objects.count(), 1)


from buses.models import Viaje


class ViajesPorBusTest(TestCase):
    """Fase 3: el conductor hereda los viajes del bus que tiene asignado."""

    def setUp(self):
        self.e = Escenario()
        self.admin = Escenario.cliente_http(self.e.admin_a)

    def programar(self, bus, fecha="2026-11-02", hora="06:30", paquete=None):
        r = self.admin.post("/api/viaje/", {"paquete_id": (paquete or self.e.paq_a).id, "bus_id": bus.id,
                                            "fecha": fecha, "hora": hora}, format="json")
        return r

    def test_sin_bus_no_ve_viajes(self):
        self.assertEqual(self.programar(self.e.bus_a).status_code, 201)
        c = Escenario.cliente_http(self.e.cond_a)
        self.assertEqual(c.get("/api/viaje/").json(), [])

    def test_solo_ve_los_de_su_bus(self):
        v1 = self.programar(self.e.bus_a).json()
        self.programar(self.e.bus_a2, hora="08:00")
        self.admin.post("/api/bus-conductor/", {"bus_id": self.e.bus_a.id, "conductor_id": self.e.cond_a.id}, format="json")
        c = Escenario.cliente_http(self.e.cond_a)
        lista = c.get("/api/viaje/").json()
        self.assertEqual([v["id"] for v in lista], [v1["id"]])
        self.assertEqual(lista[0]["placa"], "AAA111")
        self.assertEqual(lista[0]["estado"], "PROGRAMADO")
        otro = Viaje.objects.exclude(id=v1["id"]).first()
        self.assertEqual(c.get(f"/api/viaje/{otro.id}/").status_code, 404)

    def test_cambiar_de_bus_reemplaza_sin_duplicar(self):
        self.programar(self.e.bus_a)
        v2 = self.programar(self.e.bus_a2, hora="08:00").json()
        for bus in (self.e.bus_a, self.e.bus_a2, self.e.bus_a2):
            self.admin.post("/api/bus-conductor/", {"bus_id": bus.id, "conductor_id": self.e.cond_a.id}, format="json")
        self.assertEqual(list(Bus_Conductor.objects.filter(conductor=self.e.cond_a).values_list("bus_id", flat=True)),
                         [self.e.bus_a2.id])
        c = Escenario.cliente_http(self.e.cond_a)
        self.assertEqual([v["id"] for v in c.get("/api/viaje/").json()], [v2["id"]])

    def test_no_cambia_de_bus_con_viaje_en_curso(self):
        v = self.programar(self.e.bus_a).json()
        self.admin.post("/api/bus-conductor/", {"bus_id": self.e.bus_a.id, "conductor_id": self.e.cond_a.id}, format="json")
        Viaje.objects.filter(id=v["id"]).update(estado="EN_CURSO", conductor=self.e.cond_a)
        r = self.admin.post("/api/bus-conductor/", {"bus_id": self.e.bus_a2.id, "conductor_id": self.e.cond_a.id}, format="json")
        self.assertEqual(r.status_code, 409)
        self.assertTrue(Bus_Conductor.objects.filter(conductor=self.e.cond_a, bus=self.e.bus_a).exists())

    def test_validaciones_de_programacion(self):
        self.assertEqual(self.programar(self.e.bus_b).status_code, 400)          # bus de otra agencia
        self.assertEqual(self.programar(self.e.bus_a, fecha="2026-13-40").status_code, 400)
        self.assertEqual(self.programar(self.e.bus_a).status_code, 201)
        self.assertEqual(self.programar(self.e.bus_a).status_code, 409)          # misma hora, mismo bus
        b = Escenario.cliente_http(self.e.admin_b)
        r = b.post("/api/viaje/", {"paquete_id": self.e.paq_a.id, "bus_id": self.e.bus_a.id,
                                   "fecha": "2026-11-03", "hora": "06:30"}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(b.get("/api/viaje/").json(), [])
        cond = Escenario.cliente_http(self.e.cond_a)
        self.assertEqual(cond.post("/api/viaje/", {"paquete_id": self.e.paq_a.id, "bus_id": self.e.bus_a.id,
                                                   "fecha": "2026-11-05", "hora": "06:30"}, format="json").status_code, 403)

    def test_bus_con_viajes_no_se_borra(self):
        self.programar(self.e.bus_a)
        self.assertEqual(self.admin.delete(f"/api/bus/{self.e.bus_a.id}/").status_code, 409)


class EstadosViajeTest(TestCase):
    """Fase 4: iniciar y finalizar se guardan en la BD y validan transiciones."""

    def setUp(self):
        self.e = Escenario()
        admin = Escenario.cliente_http(self.e.admin_a)
        self.v = admin.post("/api/viaje/", {"paquete_id": self.e.paq_a.id, "bus_id": self.e.bus_a.id,
                                            "fecha": "2026-11-02", "hora": "06:30"}, format="json").json()
        self.v2 = admin.post("/api/viaje/", {"paquete_id": self.e.paq_a.id, "bus_id": self.e.bus_a.id,
                                             "fecha": "2026-11-03", "hora": "06:30"}, format="json").json()
        self.otro = admin.post("/api/viaje/", {"paquete_id": self.e.paq_a.id, "bus_id": self.e.bus_a2.id,
                                               "fecha": "2026-11-02", "hora": "06:30"}, format="json").json()
        admin.post("/api/bus-conductor/", {"bus_id": self.e.bus_a.id, "conductor_id": self.e.cond_a.id}, format="json")
        self.c = Escenario.cliente_http(self.e.cond_a)

    def test_ciclo_persistente(self):
        r = self.c.post(f"/api/viaje/{self.v['id']}/iniciar/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["estado"], "EN_CURSO")
        # "cerrar la app y volver": una consulta nueva trae el estado guardado
        self.assertEqual(Escenario.cliente_http(self.e.cond_a).get(f"/api/viaje/{self.v['id']}/").json()["estado"], "EN_CURSO")
        self.assertEqual(Viaje.objects.get(id=self.v["id"]).conductor_id, self.e.cond_a.id)
        self.assertEqual(self.c.post(f"/api/viaje/{self.v['id']}/finalizar/").json()["estado"], "COMPLETADO")
        self.assertIsNotNone(Viaje.objects.get(id=self.v["id"]).finalizado_en)

    def test_transiciones_invalidas_y_repetidas(self):
        self.assertEqual(self.c.post(f"/api/viaje/{self.v['id']}/finalizar/").status_code, 409)  # aún programado
        self.assertEqual(self.c.post(f"/api/viaje/{self.v['id']}/iniciar/").status_code, 200)
        repetido = self.c.post(f"/api/viaje/{self.v['id']}/iniciar/")
        self.assertEqual(repetido.status_code, 409)
        self.assertEqual(repetido.json()["viaje"]["estado"], "EN_CURSO")
        self.assertEqual(self.c.post(f"/api/viaje/{self.v2['id']}/iniciar/").status_code, 409)  # otro en curso
        self.assertEqual(self.c.post(f"/api/viaje/{self.v['id']}/finalizar/").status_code, 200)
        self.assertEqual(self.c.post(f"/api/viaje/{self.v['id']}/finalizar/").status_code, 409)
        self.assertEqual(self.c.post(f"/api/viaje/{self.v['id']}/iniciar/").status_code, 409)

    def test_no_inicia_viajes_de_otro_bus_ni_otra_agencia(self):
        self.assertEqual(self.c.post(f"/api/viaje/{self.otro['id']}/iniciar/").status_code, 403)
        b = Escenario.cliente_http(self.e.cond_b)
        self.assertEqual(b.post(f"/api/viaje/{self.v['id']}/iniciar/").status_code, 403)
        self.assertEqual(Viaje.objects.get(id=self.v["id"]).estado, "PROGRAMADO")

    def test_editar_solo_programado(self):
        admin = Escenario.cliente_http(self.e.admin_a)
        self.c.post(f"/api/viaje/{self.v['id']}/iniciar/")
        self.assertEqual(admin.put(f"/api/viaje/{self.v['id']}/", {"hora": "09:00"}, format="json").status_code, 409)
        self.assertEqual(admin.delete(f"/api/viaje/{self.v['id']}/").status_code, 409)


import threading

from django.db import connections
from django.test import TransactionTestCase


class InicioSimultaneoTest(TransactionTestCase):
    """Dos teléfonos (o dos toques) inician el mismo viaje a la vez: solo uno lo logra."""

    def test_un_solo_inicio(self):
        e = Escenario()
        admin = Escenario.cliente_http(e.admin_a)
        v = admin.post("/api/viaje/", {"paquete_id": e.paq_a.id, "bus_id": e.bus_a.id,
                                       "fecha": "2026-11-02", "hora": "06:30"}, format="json").json()
        segundo = e.usuario("cond.a2@rt.co", 3, e.ag_a)
        Bus_Conductor.objects.create(bus=e.bus_a, conductor=e.cond_a)
        Bus_Conductor.objects.create(bus=e.bus_a, conductor=segundo)
        clientes = [Escenario.cliente_http(e.cond_a), Escenario.cliente_http(segundo)]
        codigos, barrera = [], threading.Barrier(2)

        def iniciar(c):
            barrera.wait()
            codigos.append(c.post(f"/api/viaje/{v['id']}/iniciar/").status_code)
            connections.close_all()

        hilos = [threading.Thread(target=iniciar, args=(c,)) for c in clientes]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        self.assertEqual(sorted(codigos), [200, 409])
        self.assertEqual(Viaje.objects.get(id=v["id"]).estado, "EN_CURSO")
