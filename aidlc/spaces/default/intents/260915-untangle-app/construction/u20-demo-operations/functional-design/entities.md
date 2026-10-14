# Entidades — U20 `demo-operations`

Esta unidad añade **una entidad de registro** y **un validador**. No añade purgadores,
no añade tablas de datos de visitante, y no decide qué se conserva.

## Lo que ya existe y se usa tal cual

| Qué | Dónde | Cómo lo usa esta unidad |
| --- | --- | --- |
| `VisitorDataPurger` (`Protocol`) | `tenancy/models.py` | Es el contrato que la orquestación recibe. Ya trae `name`, `tables`, `purge(older_than, dry_run)` |
| Los nueve purgadores registrados | `server/composition.py` | Se llaman en el orden del registro. **Cada uno lleva escrita al lado la razón de qué conserva** |
| La prueba de completitud del registro | Las pruebas de U2 | Le pregunta al catálogo de la base qué tablas llevan la marca de dato de visitante y falla si alguna no tiene purgador |
| `corpus:ingest` | `mise.toml` | La invoca el aprovisionamiento; su comentario ya lo dejó escrito |
| El chequeo de identificadores de aseguradora | `tenancy:literals` | Es lo que comprueba AC5.1.4 |

## `ResetRun` — el registro de una corrida del reinicio

| Campo | Qué es |
| --- | --- |
| `reset_run_id` | Identificador de la corrida |
| `started_at` / `finished_at` | Cuándo empezó y cuándo terminó |
| `outcome` | `succeeded`, `failed` o `partial`. Conjunto cerrado |
| `purgers` | Una fila por purgador: su nombre, qué borró y cuánto tardó |
| `failure` | Cuál purgador falló y con qué tipo de error, cuando lo hubo |

**`partial` existe a propósito y no es un lujo.** Un reinicio en el que siete purgadores
borraron y dos fallaron no es un éxito ni un fallo completo: es el estado que hay que
poder reportar, porque decide si el reintento repite todo o solo lo que falta. Colapsarlo
en `failed` haría que el reintento borrara de nuevo lo ya borrado; en `succeeded`,
dejaría datos con el contador de 24 horas reiniciado.

**El reloj de las 24 horas cuenta desde el último `succeeded`**, nunca desde el último
intento (BR3.2).

**`purgers` guarda lo que cada purgador dijo**, no un total. Un total no dice cuál dejó
de borrar el día que algo cambie.

## `TenantFolderReport` — lo que devuelve la validación del aprovisionamiento

| Campo | Qué es |
| --- | --- |
| `complete` | Si la carpeta tiene todo lo que hace falta |
| `missing` | Una fila por falta: **el archivo y el campo**, no un mensaje suelto |

**Se valida entera y se reportan todas las faltas**, no la primera: obligar a descubrir
un campo por corrida convierte dar de alta una aseguradora en cinco intentos.

## Lo que esta unidad no añade

- **Ningún purgador nuevo**, y ninguna sentencia de borrado.
- **Ninguna decisión sobre qué se conserva**: la declara el dueño de cada tabla.
- **Ninguna tabla de datos de visitante.**
- **El disparador nocturno**: es del intent `infra`.

## Sources

- `rules.md` — BR1.1 a BR3.2
- El código: `tenancy/models.py`, `server/composition.py`, `mise.toml`

## Assumptions & Open Questions

None.
