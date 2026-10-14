# Requisitos de seguridad — U21 `eval-gates`

U21 es la unidad que audita a las demás. Lo que protege: que ningún dato
personal sobreviva en lo que se publica, que el segundo detector sea de verdad
independiente del primero, y que una compuerta que no se pudo medir no se lea
como una compuerta en verde.

**Comandos nuevos de esta unidad** (tareas nuevas que crea la generación de
código): `mise run evals:gate`, `mise run evals:baseline` y
`mise run evals:calibrate`. Los demás existen hoy.

## Modelo de amenazas

| Amenaza | Qué podría pasar | Control | Requisito |
| --- | --- | --- | --- |
| Dato personal en lo publicado | Un teléfono sobrevive en una traza, un log o el propio reporte y se publica | Segundo detector sobre las salidas ya redactadas | SEC-U21.1 |
| Detector que no detecta | El segundo detector comparte mecanismo con el primero y hereda su punto ciego | Mecanismo declarado, sin biblioteca compartida, con canario sembrado | SEC-U21.2 |
| Compuerta apagada en silencio | Una métrica que no se pudo medir se lee como verde | "No medida" con su causa, y código de salida distinto de cero en las duras | SEC-U21.3 |
| Juez inflado | Un juez descalibrado sostiene una métrica publicada | TPR y TNR con intervalo, por criterio e idioma | SEC-U21.4 |
| Umbral movido | Un umbral se baja para que una entrega pase | Los umbrales viven en este documento y en el código, nunca en una bandera | SEC-U21.5 |

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| SEC-U21.1 | Hallazgos del segundo detector en trazas, logs, exportaciones y el reporte de la corrida, por idioma y por tipo de entidad (AC4.14.2, `[bloquea]`) | **Exactamente 0** | Tarea nueva `mise run evals:gate` |
| SEC-U21.2 | Reconocedores o bibliotecas compartidas entre los dos detectores, y canarios sembrados que el segundo no encuentra (AC4.14.1, AC4.14.4) | **Exactamente 0** en los dos | `mise run lint` (contrato de importación) y tarea nueva `mise run test:u21` |
| SEC-U21.3 | Compuertas duras en rojo que no terminan con código distinto de cero, y métricas omitidas del reporte (AC4.5.3, AC4.5.5) | **Exactamente 0** | Tarea nueva `mise run evals:gate` |
| SEC-U21.4 | Criterios cuyos veredictos del juez cuentan con el límite inferior del intervalo de TPR o de TNR por debajo de **0,80**, por criterio e idioma (AC4.6.1) | **Exactamente 0** | Tarea nueva `mise run evals:calibrate` |
| SEC-U21.5 | Umbrales leídos de una bandera de línea de comandos en vez de la configuración versionada | **Exactamente 0** | Tarea nueva `mise run test:u21` |
| NFR11.6 | Datos personales en el reporte publicado, medidos por el segundo detector (NFR11, dueña U3) | **Exactamente 0** | Tarea nueva `mise run evals:gate` |

## Sources

- `../functional-design/rules.md` — BR3.1 a BR4.2.
- `../../../inception/user-stories/stories.md` — US4.6 y US4.14.
- `../../../inception/requirements-analysis/requirements.md` — NFR11.
- `aidlc/spaces/default/memory/team.md` — juez descalibrado y compuerta en rojo
  por causa externa.

## Assumptions & Open Questions

- **[assumption]** El umbral de 0,80 sobre el límite inferior del intervalo es la
  decisión FD-U21-4 de esta unidad; si una recalibración futura lo cambia, se
  cambia aquí y no en una bandera.
