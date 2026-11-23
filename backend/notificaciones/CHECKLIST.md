# Checklist de verificación manual — notificaciones

Repos: backend `RutaTourVS/backend`, Android `RutaT` (rama `rama-notificaciones`), panel `RutaTourFrontend/frontend/rutatour`
(el prototipo `guardAngular` también tiene la versión demo).

## 0. Preparación (una vez)
- [ ] Backend: `python manage.py migrate` (crea `notificaciones`, `preferencias_notificacion`, `dispositivos_fcm`). No toca tablas existentes.
- [ ] Backend: `pip install -r requirements.txt` (agrega `firebase-admin==7.8.0`).
- [ ] Backend: variable `FIREBASE_CREDENTIALS_FILE` = ruta del JSON de la cuenta de servicio de Firebase. Sin ella el push se omite y todo lo demás funciona.
- [ ] Android: en `local.properties` `firebase.appId`, `firebase.apiKey`, `firebase.projectId`, `firebase.senderId` (la app ya los lee).
- [ ] Datos: 2 agencias (A y B), cada una con su administrador, un conductor con bus asignado y un paquete con un viaje PROGRAMADO; un cliente con una reserva y un comprobante pendiente.
- [ ] Teléfono con sesión: cliente en uno, conductor en otro (o uno tras otro). Entrar a Inicio registra el token (`POST /dispositivo/`).

## 1. HU-M-50 · Centro de notificaciones (cliente y conductor)
- [ ] **50.1** Con avisos recibidos, campana de Inicio → lista del más reciente al más antiguo (título, 2 líneas de vista previa, fecha, punto de no leída).
- [ ] **50.2** Tocar un aviso abre el detalle (título, mensaje completo, fecha) y al volver ya no tiene punto de no leída; el badge de la campana baja.
- [ ] **50.3** Usuario sin avisos → "No tienes notificaciones".
- [ ] Más de 20 avisos: al bajar carga la siguiente página sin repetir. Pull-to-refresh actualiza.
- [ ] Sin internet: primera carga muestra error con Reintentar; con lista ya cargada, el refresco fallido deja la lista y avisa con barra.
- [ ] Un usuario no ve avisos de otro (probar con dos cuentas).

## 2. HU-M-51 · Preferencias
- [ ] **51.1** Centro → "Ajustes": cliente ve solo "Pago aprobado"; conductor solo "Cambio en un viaje asignado".
- [ ] **51.2** Cliente desactiva "Pago aprobado" y guarda → la agencia aprueba un comprobante → el cliente **no** recibe push **ni** aviso en el historial.
- [ ] **51.3** Guardar, cerrar la app por completo y reabrir → el interruptor sigue como se dejó.
- [ ] Guardar sin internet → mensaje de error con Reintentar; los interruptores quedan como estaban.
- [ ] Volver a activar y repetir el evento → vuelve a llegar.

## 3. HU-W-46 · Novedad reportada por conductor (panel web, administrador)
- [ ] **46.1** El conductor A guarda una novedad (Reporte de novedades) → el administrador de la agencia A ve la notificación en la campana del panel (con el WebSocket al instante; sin él, en máximo 30 s).
- [ ] **46.2** El administrador abre la notificación → `/admin/novedades/<id>` muestra la novedad y el viaje asociado (paquete, bus, conductor, salida, estado).
- [ ] **46.3** El conductor de la agencia B reporta → el administrador de A **no** recibe nada; abrir a mano `/admin/novedades/<id de B>` muestra "Esta novedad es de otra agencia".
- [ ] El badge de la campana cuenta las no leídas y baja al abrirlas; recargar la página no pierde avisos (historial).
- [ ] Superadministrador y roles no administrador no ven la campana.

## 4. HU-M-53 · Cambio en un viaje asignado (conductor)
- [ ] **53.1** El administrador cambia la **fecha**, la **hora** o una **parada** (lugar, día, hora) de un viaje del bus del conductor → el conductor recibe push y aviso.
- [ ] **53.2** El conductor abre el aviso → "Ver el viaje" muestra el viaje con los datos nuevos (se pide a la API, no se usa una copia).
- [ ] **53.3** Cambio en un viaje de otro bus/conductor → el conductor no recibe nada.
- [ ] Guardar un viaje sin cambiar fecha/hora, cambiar solo el bus, o editar solo la descripción de una parada → **no** hay aviso.

## 5. HU-M-11 · Comprobante aprobado (cliente)
- [ ] **11.1** La agencia aprueba el comprobante → el cliente recibe push (también con la app cerrada) y aviso en el historial.
- [ ] **11.2** Tocar el push (app cerrada) abre Inicio y enseguida el tiquete con el QR; desde el historial, "Ver mi tiquete" hace lo mismo.
- [ ] **11.3** La agencia rechaza un comprobante → el cliente **no** recibe este aviso.
- [ ] Aprobar un pago ya aprobado no duplica el aviso.

## 6. Push (Android)
- [ ] Android 13+: primera vez que entra a Inicio aparece la explicación y luego el permiso del sistema; si lo niega no vuelve a insistir.
- [ ] Push con la app en primer plano, en segundo plano y cerrada.
- [ ] Cerrar sesión borra el token (`DELETE /dispositivo/`): el teléfono deja de recibir avisos de esa cuenta; otra cuenta en el mismo teléfono recibe los suyos.
- [ ] El push del chat sigue funcionando como antes.

## 7. No se rompió nada (regresión)
- [ ] Backend: aprobar/rechazar pagos, editar y crear viajes, itinerario (crear/editar/borrar), `POST /novedad/` desde Android, `GET /novedad/` en Reportes del panel — todo responde igual que antes.
- [ ] Con `FIREBASE_CREDENTIALS_FILE` mal configurado o Firebase caído, esas operaciones siguen respondiendo 200/201 (la notificación se guarda igual; el error queda en el log).
- [ ] Panel: sidebar, búsqueda del topbar, Reportes, Tiquetes y cierre por inactividad siguen igual.
- [ ] Android: login, compra, subir comprobante, Mis viajes, chat y GPS del conductor siguen igual.

---

# Pendientes y mejoras futuras

## Antes de dar por cerrado
1. **WebSocket en producción (hoy no activo).** El código está (`consumers.py`, `routing.py`, `config/asgi.py`) pero es inerte: producción corre `gunicorn config.wsgi` (Dockerfile) y `channels` no está en `requirements.txt`. El panel funciona igual con sondeo cada 30 s. Para activarlo: agregar `channels`, `channels-redis` y `uvicorn[standard]` (o `daphne`), definir `REDIS_URL` en Render, y cambiar el `CMD` del Dockerfile a `uvicorn config.asgi:application --host 0.0.0.0 --port 8000` (o gunicorn con `uvicorn.workers.UvicornWorker`). Sin Redis y con más de un proceso, los avisos no llegan al panel.
2. **Credenciales de Firebase** (`FIREBASE_CREDENTIALS_FILE` en Render como secret file) — sin ellas no hay push.
3. **Probar contra MySQL real.** Las pruebas del backend corrieron en sqlite en memoria sin migraciones; correr `python manage.py test` en la BD de desarrollo, incluida la migración `notificaciones/0001_initial`.
4. **Probar en dispositivo** (push real, deep link con la app cerrada, permiso Android 13+) y en el panel contra el backend real.
5. **Fallos previos de la suite** (no causados por esto; idénticos en el código original en mi entorno): `MigracionDuplicadosTest`, `MigracionContrasenasTest`, `ConcurrenciaTest` (x2) y 4 de `usuarios.tests` que asumen el hasher real. Revisar en MySQL.
6. **Android: dependencia nueva** `androidx.swiperefreshlayout:1.1.0` (pull-to-refresh). Confirmar que se acepta.
7. **Commits:** ningún repo tiene commits de este trabajo. Backend está en `feature/HU-W-21-programar-viaje` (crear `rama-notificaciones`); panel en `main`; `guardAngular` en `main`.

## Decisiones tomadas (revisables)
- Preferencia desactivada → el aviso no se guarda, no se envía y no se emite (HU-M-51.2). Quien lo desactiva tampoco lo ve en el historial.
- Preferencias con botón **Guardar** (un PUT) en Android, no por interruptor.
- Cambio de **bus** por sí solo no notifica al conductor; si cambia el bus, el conductor anterior no se entera de que perdió el viaje.
- Los cambios de parada avisan a los conductores de los viajes no completados del paquete (las paradas son del paquete).
- Notificar nunca puede romper la operación de negocio: cualquier error se registra y se ignora.

## Mejoras futuras
- Aviso al conductor anterior cuando se le reasigna o quita un viaje, y al cliente cuando cambia su viaje.
- Notificación al cliente cuando se **rechaza** un comprobante (hoy deliberadamente no) y a la agencia cuando llega un comprobante nuevo.
- Marcar todo como leído (endpoint `POST /notificaciones/leer-todas/`) y borrar notificaciones antiguas (limpieza periódica).
- Preferencias para administradores en el panel (el backend ya las admite para `NOVEDAD_INCIDENTE`).
- Caché local (DataStore) de preferencias y último historial para verlos sin conexión en Android.
- Pruebas de UI (Espresso) del centro de notificaciones y preferencias.
- Cola de envío asíncrona (Celery o similar) para el push, en vez de enviarlo dentro de la petición.
- Código sin uso que quedó en Android: panel local de avisos (`AvisoAdapter`, `include_lista_avisos`, `Push.comoAvisos`); los pushes del chat siguen guardándose en el teléfono sin que nada los muestre.
- Panel: token del WebSocket vence a la hora (el siguiente sondeo/petición lo renueva y la reconexión usa el nuevo); un cierre explícito por 4401/4403 podría pedir renovar antes.
