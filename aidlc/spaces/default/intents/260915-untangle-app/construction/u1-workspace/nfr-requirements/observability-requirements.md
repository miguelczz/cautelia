# Requisitos de observabilidad — U1 `workspace`

Lo que una corrida deja para que alguien entienda qué pasó, sin leer el código.

**Fuentes consumidas.** `../functional-design/functional-spec.md` (Flujo 1, pasos
4 a 7), `../functional-design/rules.md` (BR1.3, BR1.4, BR1.5, BR1.8, BR2.2),
`../../../inception/requirements-analysis/requirements.md` (FR11.3 y FR11.6),
`../../../inception/contract-design/contract-summary.md` (C-23, la telemetría, y
C-27, el reporte) y `../../../../codekb/untangle/technology-stack.md`.

## Qué registra una corrida

| ID | Qué se registra | Dónde | Por qué |
| --- | --- | --- | --- |
| OBS-U1.1 | Commit, identificadores exactos de modelo, hash de cada prompt, subconjunto y duración | En la corrida | Sin esto, dos corridas no se pueden comparar |
| OBS-U1.2 | Por caso: estado, criterios, desvíos del guion y enlace de traza | En el resultado del caso | Es el nivel al que se lee una regresión |
| OBS-U1.3 | Causa de cada caso no medido, de una lista cerrada | En el resultado del caso | Distingue un fallo de infraestructura de uno de calidad |
| OBS-U1.4 | Los dos idiomas lado a lado, nunca un promedio combinado | En el reporte | Principio P12 |

## Dónde sobrevive

Decisión Q4 de esta etapa:

- **En la tubería**: el reporte y el resumen por caso se publican como
  **artefacto de la corrida**, con su commit y su fecha. La compuerta no necesita
  base de datos, así que un fallo de infraestructura no se convierte en fallo de
  entrega.
- **En local**: además se guarda el registro en la base, que es lo que permite
  consultar el historial sin abrir artefactos uno por uno.
- **El diff contra la línea base** se hace entre archivos versionados, no entre
  filas de una base.

## Qué no observa esta unidad

Las trazas por turno, nodo y proveedor son de U5, y el panel de cifras es de U22.
U1 solo enlaza la traza de cada caso cuando existe, y marca el enlace como no
disponible cuando no (BR1.3).

## Alertas

Ninguna en esta unidad. No hay nada corriendo en producción que alertar: la señal
es el código de salida de la corrida y el estado del flujo sobre `main`. Un
`main` en rojo es un incidente por la práctica del equipo, no por una alerta que
configure U1.
