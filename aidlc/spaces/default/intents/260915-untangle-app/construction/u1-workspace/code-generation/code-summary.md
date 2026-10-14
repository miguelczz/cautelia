# Resumen de la generación — U1 `workspace`

El primer commit de código del aplicativo. Los 26 pasos del plan aprobado están
hechos y la compuerta completa corre en verde.

## Lo que se midió, de verdad

Cifras tomadas de una corrida real el 2026-09-20, no estimadas.

| Qué | Resultado | Cómo se obtuvo |
| --- | --- | --- |
| Pruebas de Python | **66 pasan**, 0 fallan | `uv run --project app/backend pytest app/backend/tests -q` |
| Pruebas de TypeScript | **2 pasan**, 0 fallan | `pnpm --dir app/frontend exec vitest run` |
| Cobertura agregada | **90,05 %** (1882/2090 líneas), piso 80 % | `mise run cov` |
| Cobertura del backend | 90,04 % (1880/2088) | El mismo comando |
| Guion de verificación | **Los nueve pasos en verde** | `bash scripts/verify.sh` |
| Corredor sobre el subconjunto | 12 casos, 6 por idioma, 0 fallan, 0 no medidos | `mise run evals:run -- --subset smoke` |
| Del clon al reporte | **2 s con cachés calientes** | Clon limpio del repositorio y `mise install`, `deps:install`, `evals:run` |

**El número de los 2 segundos no es la medición de NFR21 y no se publica como
tal.** Prueba que el camino funciona de punta a punta desde un clon, que era el
criterio de terminado del Bolt; pero las herramientas ya estaban instaladas y las
cachés de `uv` y `pnpm` llenas. El número frío, que es el que la meta mide, lo
produce el trabajo semanal `fresh-clone.yml` sin caché. Hasta que ese trabajo
corra, **NFR21 no tiene valor medido** y así queda escrito.

Se escribieron **68 pruebas**, 24 más que las 44 que planeaba el plan. La
diferencia está sobre todo en el corredor y en los chequeos del catálogo, donde
cada regla acabó pidiendo su propio caso de error en lugar de compartirlo.

## Lo que quedó construido

### Andamiaje y herramientas

| Pieza | Dónde |
| --- | --- |
| Versiones ancladas y archivo de tareas | `mise.toml` |
| Proyecto Python: uv, Ruff con reglas `S`, mypy estricto, pytest con cobertura | `app/backend/pyproject.toml`, `uv.lock` |
| Proyecto TypeScript: pnpm, ESLint 10 plano, Prettier, Vitest | `app/frontend/package.json`, `pnpm-lock.yaml` |
| Contratos de importación | `app/backend/.importlinter` |
| Guion único de verificación, nueve pasos con sus dos banderas | `scripts/verify.sh` |
| Flujo de verificación (dos trabajos) y medición semanal | `.github/workflows/verify.yml`, `fresh-clone.yml` |
| Servicios locales anclados por huella, trazas en perfil aparte | `docker-compose.yml` |
| Plantilla de variables, solo nombres | `.env.example` |

### Comportamiento

| Pieza | Dónde |
| --- | --- |
| Catálogo de textos con `t()` y `keys_for()` | `app/backend/src/untangle/copy_catalog/api.py` |
| Los seis chequeos del catálogo | `.../copy_catalog/checks.py` |
| Módulo tipado de claves para la interfaz | `app/frontend/src/shared/copy/copy-keys.ts` |
| Modelos de las seis entidades | `.../evals/models.py` |
| Carga ordenada de casos y subconjuntos | `.../evals/loading.py` |
| Asegurado simulado por reglas | `.../evals/scripted_insured.py` |
| Corredor y su política de fallo en tres capas | `.../evals/runner/runner.py`, `failures.py` |
| Registro de objetivos y conductores | `.../evals/runner/api.py` |
| Reporte por caso, criterio e idioma | `.../evals/report.py` |
| Raíz de composición, configuración y salud | `.../server/composition.py` |
| Compuerta de cobertura agregada | `.../workspace/coverage_gate.py` |
| Chequeos de contenido | `.../evals/content_checks.py` |
| Subconjunto de arranque, 12 casos | `app/evals/subsets/smoke.yaml`, `app/evals/cases/ds8/` |

## Decisiones de implementación que conviene conocer

- **El árbol de los quince módulos nace vacío**, con sus `__init__.py` y sus
  contratos de importación ya escritos. Cada unidad siguiente añade su código
  dentro de un directorio que ya existe y ya está vigilado, en lugar de crear el
  directorio y la regla a la vez.
- **El registro estructurado sale a la salida estándar**, una línea por evento
  con el identificador de la corrida. Es lo que se lee en la tubería sin
  descargar el artefacto.
- **Los casos de arranque son de DS-8.** Ese conjunto era el de fixtures de
  aislamiento; los chequeos deterministas de U1 encajan ahí porque son casos de
  comprobación del sistema y no de conversación. El manifiesto lo declara.
- **`app/evals/reports/` está en el `.gitignore`.** Cada corrida escribe su
  reporte; son resultados, no fuente. La línea base, cuando exista, sí se
  versiona: la escribe U21 en otro sitio.

## Desviaciones y huecos, dichos

### SEC-U1.4 — un control que estaba escrito y no existía

**Cerrado el 2026-09-20.** Al ir a cerrar este control apareció algo peor que un
hueco: los dos ajustes de pnpm estaban escritos en `app/frontend/.npmrc`, **pnpm
12 no los leía, y no avisaba**. El archivo se veía bien y el control no existía.
Eran dos:

- `minimum-release-age` — la espera de tres días de SEC-U1.4.
- `ignore-scripts` — el bloqueo de scripts de instalación que exige ADR-002.

La causa: desde pnpm 10, los ajustes propios de pnpm viven en
`pnpm-workspace.yaml` y `.npmrc` se queda solo con lo compatible con npm. Un
ajuste de pnpm dejado ahí se ignora **en silencio**, sin advertencia.

| Cambio | Archivo |
| --- | --- |
| Los dos ajustes se movieron a donde pnpm sí los lee | `app/frontend/pnpm-workspace.yaml` |
| `.npmrc` se queda con lo compatible con npm y una nota de por qué | `app/frontend/.npmrc` |
| Chequeo que **le pregunta a cada gestor** qué valor tiene de verdad, en vez de leer el archivo donde se escribió | `.../workspace/supply_chain_check.py` |
| El chequeo entra en el paso 6 del guion, con sus cuatro pruebas | `scripts/verify.sh`, `mise.toml` |

**El control atrapó algo el mismo día que se encendió.** Con la espera ya activa,
`pnpm install` rechazó el lockfile: `prettier@3.9.8` se había publicado hacía
menos de 72 horas. Se rehizo la resolución con la política puesta y el resolutor
bajó a `prettier@3.9.7`, la más nueva con más de tres días. No se relajó nada: se
instaló lo que la regla permite.

**Una diferencia con el diseño, resuelta a favor de lo construido.**
`security-design.md` dice que la espera se configura "en el robot de dependencias
y en los dos gestores". La primera mitad no aplica: no corremos actualizaciones
automáticas de Dependabot —abrirían pull requests y trabajamos sin ellos—, así
que un ajuste ahí no tendría nada sobre lo que actuar. El control vive **solo en
los dos gestores**, y ahí sí es comprobable. El documento de diseño no se editó
porque su revisión está cerrada; la corrección queda aquí, que es donde
Construcción registra lo que encuentra.

**La lección, más allá de este control:** un ajuste de seguridad escrito en un
archivo que la herramienta no lee es peor que no tenerlo, porque nadie lo busca.
Por eso el chequeo nuevo no lee configuración: interroga a la herramienta.

### Diferencias menores respecto al plan

| Qué dijo el plan | Qué se hizo | Por qué |
| --- | --- | --- |
| 44 pruebas | 68 | Cada regla del catálogo y cada capa de la política de fallo acabó pidiendo su propio caso de error; las cuatro últimas son del chequeo de cadena de suministro |
| `smoke` con "casos deterministas" sin conjunto asignado | 12 casos bajo `DS-8` | Había que ponerlos en algún conjunto declarado; DS-8 es el de comprobaciones del sistema |

## Lo que sigue

`build-and-test` verifica y extiende lo que hay: la matriz de verificación con
cada objetivo medible y su comando. Y las dos cosas que esta unidad deja
pendientes por diseño, no por olvido: el valor frío de NFR21, que produce el
trabajo semanal, y los casos de conversación, que llegan con las unidades que
miden cada conducta.
