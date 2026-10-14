# Decisiones de stack — U20 `demo-operations`

Versión corta: **ninguna tecnología nueva.**

| # | Qué | Por qué |
| --- | --- | --- |
| TECH-U20.1 | Las dos operaciones son comandos del archivo de tareas, como todo lo que ejecuta una persona o la tubería | Un solo archivo de tareas es el contrato entre lo local y la tubería |
| TECH-U20.2 | La orquestación del reinicio es una función pura sobre el `Protocol` que ya existe | Se prueba entera con dobles y sin base, incluido el camino del fallo, que contra una base de verdad habría que provocar rompiéndola |
| TECH-U20.3 | El aprovisionamiento invoca `corpus:ingest`, no escribe su propia ingesta | Ya está escrito en el comentario de esa tarea |
| TECH-U20.4 | `ResetRun` se guarda en la base, no en un archivo | Es un dato del proyecto que tiene que sobrevivir al propio reinicio y que una alerta consulta; un archivo en `tmp/` no sobreviviría y uno versionado ensuciaría cada commit |
| TECH-U20.5 | El disparador nocturno lo fija el intent `infra` | Ya estaba repartido así (PA-10) |

## Lo diferido a la pasada de publicación

**Nada se difiere: esta unidad *es* la pasada de publicación de la operación.** AC5.6.4
—que el reinicio devuelva los casos sembrados a su estado sembrado— estaba diferido aquí
desde U7 y se cierra en esta unidad.

## Sources

- `../functional-design/functional-design-questions.md` — FD-U20-1 a FD-U20-9
- El código: `server/composition.py`, `tenancy/models.py`, `mise.toml`

## Assumptions & Open Questions

None.
