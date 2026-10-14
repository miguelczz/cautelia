# Hallazgos — U22 `public-evidence`, tanda 4 (el resumen de la última corrida)

Escrito en la sesión de la nube. `mise` no pudo descargar Python 3.13.15 (el túnel lo
rechazó); se usó el 3.13.14 del sistema con `uv sync --frozen --all-groups` y los
comandos de `mise.toml` se corrieron directamente, con las mismas versiones de
dependencias del lockfile. **No se instalaron los modelos de spaCy** (descarga por URL
de GitHub, bloqueada): ninguna prueba de esta tanda los necesita, y `mise run
models:install` sigue pendiente para quien corra la suite completa.

## Qué se construyó

- **`LastRunDigest`** (`evals/gates/models.py`, junto a `Baseline`): `run_id`,
  `commit_sha`, `produced_at`, `case_verdicts`, `root_causes`, `not_measured_causes`, y
  un `subset` que **solo puede ser `None`**. El campo existe para que el tipo pueda
  rechazar la declaración de subconjunto (`entities.md`: «un resumen que declare
  subconjunto»); `entities.md` no lo lista entre los seis campos y se añade por eso.
  Cinco validadores: corrida completa, forma del identificador, causa raíz de un caso
  que el resumen trae, causa de no medido de un caso que trae **y que está en
  `not_measured`**, y todo caso `not_measured` con su causa (OBS-U1.3).
- **`paths.last_run_digest_path()`** → `app/evals/last-run.json` (todavía no existe; lo crea la primera corrida completa), versionado, junto a
  `baselines/` y no en `tmp/`.
- **`build_digest`** (`gates/baseline.py`), **`load_last_run_digest`** y
  **`save_last_run_digest`** (`gates/loading.py`), con el mismo patrón que la línea
  base: ausente es `None`, roto se nombra.
- **`evals:baseline`** escribe el resumen **antes** de intentar publicar. El código de
  retorno no cambia: una corrida en rojo sigue devolviendo 1, pero el resumen ya quedó.
  `evals:gate` no lo escribe.
- **«Cómo falla»** lee el resumen: cita **su** commit y **su** corrida, y cada caso no
  medido lleva su causa (`CASE_NOT_MEASURED_TEXT`, tabla cerrada con su prueba de que no
  falta ninguna clave). `render_sections`, `regenerate` y `check` reciben las dos
  fuentes; las cifras no cambian.
- **`readme_check`** carga las dos fuentes y sigue siendo el único que toca el archivo.
  Sin resumen, la sección dice «no medida» con su causa: es el estado de hoy y el
  README del repositorio se regeneró a él.
- **`schema:check`** valida `last-run.json` si existe, como ya hace con las líneas base.
- **`Baseline.root_causes` se retiró**, con su validador y la línea de `build_baseline`
  que lo llenaba. La prueba que lo cubría ahora afirma que el campo **no existe**.

## Un detalle que conviene saber

Hay **dos enums llamados `NotMeasuredCause`**: el de una cifra (`evals.evidence.models`,
seis valores) y el de un caso (`evals.models`, siete). Son taxonomías distintas y cada
una tiene su tabla de frases; `readme.py` importa la del caso con alias para no
confundirlas.

## La revisión: doce roturas

Cada regla nueva se rompió una a una sobre el código y se anotó qué se cayó.

| Regla | Rotura | Qué se cayó |
| --- | --- | --- |
| BR4.3 | Escribir el resumen solo si se publica (no en rojo) | `test_una_corrida_en_rojo_deja_el_resumen_y_sigue_devolviendo_uno` |
| OBS-U1.3 | Contar los no medidos entre los fallos | `test_como_falla_agrupa_por_causa_raiz_…` (y `5 of 6` queda vetado por su prueba) |
| BR4.1 | Citar el commit de la línea base en vez del del resumen | `test_como_falla_cita_el_commit_del_resumen_y_no_el_de_la_linea_base` |
| BR4.3 | Un resumen con subconjunto se puede construir | `test_un_resumen_que_declara_subconjunto_no_valida` |
| BR4.3 | El constructor oculta el subconjunto de la corrida | `test_construirlo_desde_un_subconjunto_se_rechaza` |
| tipo | Causa raíz de un caso ajeno | `test_una_causa_raiz_de_un_caso_que_el_resumen_no_trae_no_valida` |
| tipo | Causa de no medido de un caso que sí se midió | `test_una_causa_de_no_medido_de_un_caso_que_si_se_midio_no_valida` |
| OBS-U1.3 | Un no medido sin su causa | `test_un_caso_no_medido_sin_su_causa_no_valida` |
| BR4.2 | El chequeo no lee el resumen | tres pruebas de `test_readme_check.py` |
| BR4.1 | Toda causa de no medido dibujada igual | `test_la_causa_de_cada_no_medido_es_la_suya_y_no_una_para_todos` |
| FD-U22-10 | El resumen vive en `tmp/` | `test_el_resumen_vive_junto_a_las_lineas_base_y_no_en_tmp` |
| BR4.3 | El comando pasa un subconjunto al corredor / el resumen pierde las causas raíz | `test_una_corrida_en_rojo_deja_el_resumen_…` |

Ninguna rotura dejó todo en verde. Una trampa evitada de la tanda 3: el commit del
resumen en las pruebas es **distinto** del de la línea base a propósito, porque con el
mismo la rotura «citar el de la línea base» no habría caído nada.

## Lo que corrió

Formato, `ruff`, `lint-imports` (36 contratos), `mypy`, `copy:check`, `content:check`,
`schema:check`, generación de contratos (sin deriva: ni el esquema OpenAPI ni los
contratos cambian), `readme:gen` seguido de `readme:check`, y el tramo de Python de
`test:u22` sin la parte de integración: 257 pruebas de `evals`, `workspace` y las dos
rutas web, en verde.

La suite de unidad completa da **91 fallos y 234 errores** que **no son de esta tanda**:
son `ModelsMissingError` (sin modelos de spaCy) y pruebas que piden base de datos. Sin
mis cambios, el mismo entorno da 92 fallos y los mismos 234 errores; con ellos pasan 20
pruebas más. Quien corra la suite con `mise run models:install` hecho no los verá.

**No corrió** `scripts/verify.sh` entero, `mise run cov` ni la integración de U22
(no hay base ni motor de contenedores), ni `vitest`: la tanda no toca la interfaz. La
suite completa, que necesita los modelos de spaCy, queda para la compuerta de GitHub
Actions.

## Lo que queda abierto

Nada de esta unidad. El comando `evals:baseline` real —el que escribe el primer
`last-run.json` con los 100 casos— necesita claves de proveedor y dinero, y es de la
sesión local: hasta entonces el README dice «no medida», que es lo cierto.

---

## La revisión local de la tanda 4

Escrita en la sesión local el 2026-09-30. Se corrieron las pruebas de la unidad (334
unitarias entre `evals`, `workspace` y las dos rutas), las once compuertas baratas,
y `readme:check` **por `mise`**. Y se rompieron cinco reglas más que las doce de
arriba.

### Las cinco roturas propias

| Rotura | Qué se cayó |
| --- | --- |
| El resumen no copia el subconjunto del reporte, lo fija en nulo | `test_construirlo_desde_un_subconjunto_se_rechaza` |
| Los casos no medidos pierden su causa y queda solo la lista | dos pruebas del generador |
| El resumen se escribe **después** de publicar | `test_una_corrida_en_rojo_deja_el_resumen_y_sigue_devolviendo_uno` |
| Falta una causa de la taxonomía cerrada en la tabla de frases | `test_toda_causa_cerrada_tiene_su_frase` |
| Un resumen roto se lee como «no hay ninguno» en vez de nombrarse | dos pruebas, una del resumen y una del chequeo |

Las cinco cayeron. No hubo ninguna corrección de prueba en esta revisión, que es la
primera tanda de U22 en la que eso pasa.

### El campo que el diseño no había pedido, y que estaba bien añadir

`entities.md` listaba seis campos y la tanda puso siete: `subset`, que **solo puede ser
nulo**. Visto de lejos parece un campo sin información, y de cerca es lo contrario.

El diseño confiaba en que el único escritor del resumen es `evals:baseline`, que nunca
corre un subconjunto. La tanda no confió: `build_digest` **copia** el subconjunto del
reporte, así que el día que alguien enganche esta escritura a una corrida parcial, la
construcción falla nombrando BR4.3 en vez de escribir un resumen de 74 casos que la
sección publicaría como si fueran 100. `extra="forbid"` habría rechazado un archivo
escrito a mano con esa clave, pero no protege del escritor, que es de donde viene el
riesgo.

Es la diferencia entre una regla y un deseo, y el diseño tenía un deseo. `entities.md`
queda corregido con el séptimo campo y con esta razón.

### Otra cosa que la revisión miró y decidió dejar

El validador rechaza una causa de no medida en un caso que sí se midió, pero **no**
rechaza una causa raíz en un caso que pasó. La asimetría es correcta y conviene que
quede escrita: la primera contradice el estado del caso en algo que la sección lee; la
segunda es inerte, porque «Cómo falla» agrupa solo los fallidos. Un validador de más
que no protege de nada es una regla que un día estorba.

### Lo que sigue sin poder medirse, y no es un defecto

`app/evals/last-run.json` **todavía no existe**, y no existirá hasta que Miguel corra
`mise run evals:baseline`, que necesita claves de proveedor y gasta dinero. Hasta
entonces «Cómo falla» dice «no medida» con su causa, el chequeo compara contra eso y
no se pone rojo. Ese es el estado correcto de hoy, y el README lo dice con esas
palabras.

**Con eso U22 queda cerrada**: cuatro tandas, sus dos archivos de cierre y el chequeo
del README dentro del guion de verificación.
