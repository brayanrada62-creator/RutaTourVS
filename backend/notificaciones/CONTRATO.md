# Contrato de API de notificaciones

Todos los endpoints exigen `Authorization: Bearer <token>` y filtran por el usuario del token.
Base: `/api/`. Tipos (`tipo`): `PAGO_APROBADO` (cliente), `CAMBIO_VIAJE` (conductor), `NOVEDAD_INCIDENTE` y `PAGO_PENDIENTE` (administrador).

## Decisiones
- Si el destinatario desactivó el tipo, el aviso **no se guarda, no se envía por push y no se emite por WebSocket**.
- Sin fila en `preferencias_notificacion` el tipo está activo.
- Un tipo solo se entrega al rol que lo puede recibir (`TIPOS_POR_ROL` en `servicio.py`).
- `referencia_tipo`: `compra` (id de la reserva), `viaje` (id del viaje), `novedad` (id de la novedad), `pago` (id del pago, con `reserva_id` en `datos`).

## GET /notificaciones/?page=1&page_size=12[&leida=false]
Orden: más reciente primero. Sin `page` devuelve la lista sin paginar.
```json
{"count": 2, "results": [{
  "id": 41, "tipo": "PAGO_APROBADO", "titulo": "Pago aprobado",
  "mensaje": "Tu pago de Cartagena fue aprobado. Tu compra está confirmada y ya puedes ver tu tiquete con el QR.",
  "fecha_creacion": "2026-11-21T15:04:05.123456Z", "leida": false,
  "referencia_id": 87, "referencia_tipo": "compra", "datos": {"pago_id": 12, "paquete": "Cartagena"}}]}
```

## GET /notificaciones/{id}/
Mismo objeto que arriba. `404` si no es del usuario.

## PATCH /notificaciones/{id}/leida/
Devuelve la notificación con `"leida": true`. `404` si no es del usuario.

## GET /notificaciones/no-leidas/count/
```json
{"count": 3}
```

## GET /notificaciones/preferencias/
Solo los tipos aplicables al rol.
```json
[{"tipo": "PAGO_APROBADO", "nombre": "Pago aprobado", "activa": true}]
```

## PUT /notificaciones/preferencias/
Cuerpo (también se acepta `{"preferencias": [...]}`). `400` si el tipo no es de su rol o `activa` no es booleano.
```json
[{"tipo": "PAGO_APROBADO", "activa": false}]
```
Respuesta: la misma lista de `GET` ya actualizada.

## POST /dispositivo/  (alias: POST /dispositivos/fcm/)
Registra o actualiza el token. Si el token existía en otro usuario (mismo teléfono) pasa al usuario actual.
```json
{"token": "fcm-token...", "plataforma": "android"}
```
→ `{"mensaje": "Dispositivo registrado"}`

## DELETE /dispositivo/  (alias: DELETE /dispositivos/fcm/)
Al cerrar sesión. Solo borra tokens del propio usuario. Cuerpo `{"token": "..."}`.

## Novedades (existentes, `reservas`)
- `POST /novedad/` `{viaje_id, tipo, detalle}` — al guardarla un **conductor**, avisa a los administradores de la agencia de la novedad.
- `GET /novedad/?viaje_id=` — lista de la agencia del administrador.
- `GET /novedad/{id}/` — **nuevo**: detalle con `viaje_id`, `paquete`, `placa`, `conductor`. `403` si es de otra agencia.

## Payload FCM
Solo `data` (todo texto), prioridad alta, para que `MensajesPush.onMessageReceived` corra con la app cerrada.
```json
{"notificacion_id": "41", "tipo": "PAGO_APROBADO", "referencia_id": "87", "referencia_tipo": "compra",
 "titulo": "Pago aprobado", "cuerpo": "Tu pago de Cartagena fue aprobado. ..."}
```

## Payload WebSocket (administrador)
Grupo `notif_usuario_<id>`; incluye `titulo`, `mensaje`, `fecha` (compatibles con `alertas$`) y los campos de la notificación.

## Cuándo se dispara cada tipo
| Tipo | Punto | Regla |
|---|---|---|
| PAGO_PENDIENTE | `POST /pago/` | Después de confirmar un comprobante nuevo del cliente, a los administradores de la agencia de la reserva |
| PAGO_APROBADO | `PUT /pago/{id}/` (y `POST /pago/` creado ya aprobado) | Solo al pasar a `aprobado`; `rechazado` no avisa; aprobar dos veces avisa una |
| CAMBIO_VIAJE | `PUT /viaje/{id}/` | Solo si cambia `fecha` u `hora`; el cambio de bus solo no avisa |
| CAMBIO_VIAJE | `POST/PUT/DELETE /itinerario/` | Solo si cambia parada (paquete, título, día, hora, lugar); a conductores de viajes no completados del paquete |
| NOVEDAD_INCIDENTE | `POST /novedad/` por un conductor | Solo administradores (rol 2) de la agencia de la novedad |

## Configuración
`FIREBASE_CREDENTIALS_FILE` (JSON de cuenta de servicio) + `pip install firebase-admin`. Sin ello el push se omite y el historial funciona igual.
