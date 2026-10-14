# Encargo para una sesión en la nube — U22 `public-evidence`, tanda 4

Pega este archivo entero como primer mensaje de una **sesión nueva**. Es la última
tanda de U22, y es corta.

---

## Antes de nada

```bash
uv tool install --force uv==0.12.16
mise run deps:install
mise run models:install
```

El último comando importa: `deps:install` **desinstala** los modelos de spaCy, y sin
ellos decenas de pruebas se ponen rojas con `ModelsMissingError` que parecen código
roto.

## Por qué existe esta tanda

La tanda 3 dejó «Cómo falla» leyendo la **línea base vigente**, que es lo que decía el
diseño. Y el diseño estaba mal: `publish()` rechaza publicar una línea base con un
solo caso en rojo (BR2.1, y hace bien), así que una línea base publicada **nunca**
trae fallos. La sección diría siempre «No case failed», y hoy el reporte tiene 42 de
100 casos que fallan porque la conducta que miden todavía no existe.

El criterio aprobado (AC4.1.3) dice «el último reporte de evaluación». Esta tanda
construye eso: un resumen versionado de la última corrida completa, que existe aunque
la corrida esté en rojo.

## Qué se construye

Lee estos, en este orden, y no escribas nada antes:

1. `aidlc/spaces/default/intents/260915-untangle-app/construction/u22-public-evidence/functional-design/entities.md` — **`LastRunDigest` está especificado ahí, campo por campo**
2. `.../functional-design/rules.md` — BR4.1 (corregida) y BR4.3
3. `.../functional-design/functional-design-questions.md` — **FD-U22-10 es la decisión que manda**
4. `.../functional-design/functional-spec.md` — el flujo 3
5. `.../code-generation/hallazgos-tanda-3.md` — la sección «La revisión local», al final: dice qué se corrigió y por qué

Y del código, en este orden:

- `app/backend/src/untangle/evals/gates/models.py` — `Baseline` y sus validadores. **El resumen se escribe con la misma forma**: campos con `Field`, validadores `model_validator(mode="after")` con el mensaje que nombra lo que está mal
- `app/backend/src/untangle/evals/gates/loading.py` — `load_baseline`, `load_current_baseline` y `publish_baseline`. El resumen se lee y se escribe **igual**
- `app/backend/src/untangle/evals/gates/baseline_cli.py` — el comando entero son 50 líneas; aquí se enchufa la escritura
- `app/backend/src/untangle/evals/models.py` — `CaseResult`, `CaseStatus`, `RootCause`, `NotMeasuredCause` y `CASE_KEY_PATTERN`
- `app/backend/src/untangle/evals/evidence/readme.py` — `render_how_it_fails` y `render_sections`, que es lo que cambia
- `app/backend/src/untangle/workspace/readme_check.py` — el comando de dos modos, que ahora carga dos fuentes
- `app/backend/src/untangle/paths.py` — `baselines_dir` y `current_baseline_path`, al lado de las cuales va la ruta nueva

## Las cuatro piezas

### 1. `LastRunDigest`

En `evals/gates/models.py`, al lado de `Baseline`. Los campos están en `entities.md`:
`run_id`, `commit_sha`, `produced_at`, `case_verdicts`, `root_causes` y
`not_measured_causes`.

Tres cosas que **el tipo** tiene que impedir, no quien lo construye:

- una causa raíz de un caso que el resumen no trae (igual que el validador que
  `Baseline` ya tiene para `root_causes`);
- una causa de no medida de un caso que el resumen no trae, **o que no está en estado
  `not_measured`**;
- un caso en `not_measured` sin su causa. Es la misma regla que ya tiene `CaseResult`
  (OBS-U1.3), y el resumen no puede relajarla.

Los identificadores de caso se validan con `CASE_KEY_PATTERN`, como en `Baseline`.

### 2. Escribirlo, siempre

`paths.last_run_digest_path()` devuelve `app/evals/last-run.json` — **versionado**,
al lado de `app/evals/baselines/`. No en `tmp/`: ahí viven los artefactos que se
regeneran en cada corrida del guion de verificación, y este no es uno (léete el
docstring de `paths.reports_dir`, que cuenta la compuerta que costó ponerlo ahí).

`evals:baseline` (`evals/gates/baseline_cli.py`) corre la corrida completa y luego
publica. El cambio es de tres líneas: **escribe el resumen antes de intentar
publicar**, y el código de retorno no cambia. Si la publicación se rechaza porque hay
casos en rojo, el comando sigue devolviendo 1 —eso no se toca— pero el resumen ya
quedó escrito, que es justo el caso que importa (BR4.3).

**No lo escribe `evals:gate`.** Ese corre un subconjunto en cada entrega, y un resumen
de 74 casos haría falsa cualquier proporción que la sección publique.

### 3. «Cómo falla» lee el resumen

En `evals/evidence/readme.py`:

- `render_how_it_fails` recibe el resumen, no la línea base. Cita **su** commit y
  **su** corrida.
- Los casos no medidos siguen aparte y **nunca** se cuentan como fallos (OBS-U1.3),
  y ahora cada uno lleva su causa, que el resumen sí guarda.
- `render_sections` recibe las dos fuentes: la línea base para las cifras y el resumen
  para los fallos. **Las cifras no cambian en nada.**
- Sin resumen, la sección dice «no medida» con su causa, y el chequeo compara contra
  eso: no se pone rojo por no haber corrido todavía la corrida completa. Este es el
  estado de hoy y es el primero que hay que hacer funcionar.

`workspace/readme_check.py` carga las dos fuentes. Sigue siendo el único que lee y
escribe el archivo; `readme.py` sigue siendo puro.

### 4. Retirar `Baseline.root_causes`

La tanda 3 lo añadió para esta sección y **ninguna ruta de producción puede
llenarlo**: la causa raíz solo se pone en casos fallidos y `publish()` los rechaza.
Quítalo del modelo, quita su validador, y quita de `build_baseline` la línea que lo
llena. La prueba que lo cubría en `tests/unit/evals/gates/test_baseline.py` se
convierte en la del resumen.

## Lo que no se puede hacer mal

1. **El resumen no es una línea base.** Una línea base es una corrida verde y sirve
   para comparar; el resumen es la foto de la última corrida completa tal como salió,
   y sirve para contar cómo falla. La compuerta sigue comparando contra la línea base
   y nada más.
2. **«Cómo falla» nombra identificadores y cita commit** (BR4.1). Se agrupa por la
   taxonomía cerrada de nueve valores, en su orden, no con una redacción por caso.
3. **Nada se mide dos veces.** No hay un segundo lector de la línea base ni un segundo
   lector del reporte.
4. **No bajes ningún umbral ni relajes ninguna prueba existente** para que algo pase.

## Lo que no puedes correr, y qué hacer

En este entorno **no hay base de datos ni motor de contenedores**: `scripts/verify.sh`
entero, `mise run cov` y las pruebas de integración no corren. Las de esta tanda **sí**
—el resumen y la línea base se siembran escribiendo sus archivos— y si alguna
necesitara base, escríbela igual y dilo.

Tampoco corras la corrida completa de evaluaciones: necesita claves de proveedor y
gasta dinero. La escritura del resumen se prueba con un reporte construido en la
prueba, no corriendo el corredor.

Lo que tiene que quedar en verde aquí: `mise run fmt:check`, `lint`, `types`,
`copy:check`, `content:check`, `schema:check`, `contracts:check`, `readme:gen` seguido
de `readme:check`, y `mise run test:u22` sin la parte de integración.

## Antes de terminar

1. Corre todo lo de arriba.
2. **Rompe cada regla y comprueba que se cae una prueba.** Las que más importan aquí:
   que el resumen **no** se escriba cuando la corrida está en rojo; que la sección
   cuente los no medidos entre los fallos; que cite el commit de la línea base en vez
   del del resumen; que un resumen con subconjunto se pueda construir. Si una rotura
   no cae nada, la prueba está escrita a la medida del código: corrígela.
3. Escribe `hallazgos-tanda-4.md` en `code-generation/`, con la tabla de roturas y lo
   que se cayó, y **actualiza** `code-summary.md` y `source-manifest.json`, que son los
   dos archivos con los que U22 se cierra.
4. Commit **en tu rama**, nunca a `main`.

## Lo que no se toca

- El panel de cifras y el de gasto: tandas 1 y 2, cerradas.
- Las cinco cifras del README: las deja la tanda 3 y siguen saliendo de la línea base.
- Las seis secciones narrativas del README: las escribe Miguel en la semana 11.
- El corredor de evaluaciones, el juez y la lógica de la compuerta: son de U21. De U21
  solo se tocan `baseline_cli.py`, `gates/models.py` y `gates/loading.py`, y está
  escrito arriba por qué.
