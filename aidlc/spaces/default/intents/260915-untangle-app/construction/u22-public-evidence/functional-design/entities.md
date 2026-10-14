# Entidades — U22 `public-evidence`

Una sola, y no guarda nada: `MetricsSnapshot` es la **vista de lectura** de la
línea base vigente, con las cinco cifras ya resueltas y con el estado de cada una.

Que no persista es la decisión: si el panel guardara su propia copia de las cifras,
habría dos verdades y un día discreparían. La línea base es el archivo versionado;
esto es cómo se lee.

## `MetricsSnapshot`

| Campo | Qué es | De dónde |
| --- | --- | --- |
| `baseline_id` | La línea base de la que sale todo, o nulo si no hay ninguna | `Baseline.baseline_id` |
| `commit_sha` | El commit que la produjo | `Baseline.commit_sha` |
| `published_at` | Cuándo se publicó | `Baseline.published_at` |
| `run_id` | La corrida, para enlazar su reporte | `Baseline.run_id` |
| `figures` | Las cinco cifras, cada una con su estado | Ver abajo |

### `Figure` — una de las cinco

| Campo | Qué es |
| --- | --- |
| `key` | Cuál de las cinco: completitud, citación, latencias, costo por caso, casos por aseguradora |
| `state` | `measured` o `not_measured` |
| `not_measured_cause` | Por qué no se midió. **Obligatorio** cuando el estado es `not_measured` |
| `by_language` | El valor por idioma, español e inglés por separado. Vacío cuando no aplica |
| `detail` | Para las latencias: entre qué eventos, sobre qué conjunto, p50 y p95 |

**`not_measured_cause` es obligatorio y no un campo más.** Es lo que convierte
"no medida" en una afirmación comprobable en vez de un hueco; sin él, BR1.2 se
cumpliría de forma y no de fondo.

**`by_language` es un mapa y no dos campos sueltos**, para que añadir un tercer
idioma no obligue a tocar el tipo, y **nunca lleva una entrada "combinado"**: no
existe promedio de los dos (BR1.4).

## `LastRunDigest` — el resumen de la última corrida completa

La entidad que FD-U22-10 añade. Es un archivo versionado en `app/evals/last-run.json`,
escrito por el comando que publica la línea base, y la **única** fuente de "Cómo
falla".

| Campo | Qué es | De dónde |
| --- | --- | --- |
| `run_id` | La corrida de la que sale | `EvalRunHeader.run_id` |
| `commit_sha` | El commit en el que corrió | `EvalRunHeader.commit_sha` |
| `produced_at` | Cuándo se escribió | El reloj, al escribirlo |
| `case_verdicts` | El veredicto de cada caso de la corrida completa | Las filas del reporte |
| `root_causes` | La causa raíz de los casos que la traen | `CaseResult.root_cause` |
| `not_measured_causes` | Por qué no se midió cada caso no medido | `CaseResult.not_measured_cause` |
| `subset` | **Siempre nulo**, y ahí está su valor: el escritor copia el subconjunto del reporte y el tipo lo rechaza | `EvalRunHeader.subset` |

**Por qué no es una línea base.** Una línea base es una corrida **verde** y sirve para
comparar (BR2.1 la rechaza con un caso en rojo). Este resumen es la foto de la última
corrida completa tal como salió, y sirve para **contar cómo falla**. Confundirlos
dejaría a la compuerta comparando contra una corrida roja.

**Cuatro cosas que el tipo impide.** Una causa raíz de un caso que el resumen no
trae. Una causa de no medida de un caso que sí se midió. Un caso no medido sin su
causa, que es la misma regla que ya tiene el reporte (OBS-U1.3). Y un resumen que
declare subconjunto, que haría falsa toda proporción publicada (BR4.3).

**El campo `subset` existe para poder rechazarlo, y es la diferencia entre una regla
y un deseo.** El diseño lo había dejado en seis campos, confiando en que el único
escritor es el comando que nunca corre un subconjunto. La tanda 4 lo añadió y tenía
razón: `build_digest` **copia** el subconjunto del reporte, así que el día que alguien
enganche esta escritura a una corrida parcial, la construcción falla nombrando la
regla en vez de escribir un resumen de 74 casos que la sección publicaría como si
fueran 100. Sin el campo, `extra="forbid"` rechazaría un archivo escrito a mano con
la clave, pero no protegería del escritor, que es de donde viene el riesgo.

**`Baseline.root_causes` se retira.** Lo añadió la tanda 3 para esta sección y ninguna
ruta de producción puede llenarlo, porque la causa raíz solo se pone en casos fallidos
y `publish()` los rechaza. Un campo que nadie puede llenar es una trampa, no una
opción.

## Lo que esta unidad no añade

- **Ninguna tabla.** El panel de gasto lee las consultas que ya existen
  (`spend_by_case`, `spend_by_provider`, `spend_by_month`, `load_window`) y el
  recuento de casos por aseguradora sale de la base con una consulta de conteo.
- **Ningún registro propio de latencias.** Los eventos de traza que las producen
  ya los emiten la voz y el chat; mientras no se midan por hito, la cifra es "no
  medida" con esa causa.

## Sources

- `rules.md` — BR1.1 a BR1.5, BR2.1, BR4.1 a BR4.3
- El código: `evals/gates/models.py` (`Baseline`), `telemetry/spend/repository.py`

## Assumptions & Open Questions

None.
