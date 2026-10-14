# Tubería y entorno — U3 `pii-redaction`

Qué cambia en el guion de verificación, cómo entran los modelos de lenguaje y
qué le cuesta todo eso a la corrida. Esta unidad no despliega nada: es una
biblioteca embebida en el proceso único.

**Fuentes consumidas.** `../nfr-design/security-design.md` y
`../nfr-design/logical-components.md`,
`../nfr-requirements/security-requirements.md` y `tech-stack-decisions.md`,
`../functional-design/functional-spec.md`,
`../../../inception/contract-design/contract-summary.md` (C-13) y
`../../../inception/domain-design/components.md`.

## Cómo entran los modelos, que no es como Presidio lo documenta

La forma que documenta spaCy —y que Presidio repite en todos sus ejemplos— es
`python -m spacy download es_core_news_md`. **Esa forma está prohibida aquí**, y
no por gusto: es una resolución libre que descarga lo que haya en ese momento,
sin lockfile y sin hash. La práctica afirmada del equipo dice que la instalación
usa el modo reproducible del gestor, *"el que falla si el lockfile no coincide,
nunca una resolución libre"*.

**Rige:** los dos modelos entran como **dependencias fijadas por URL**, con su
versión exacta y su hash en el lockfile, igual que cualquier otra dependencia.
Las ruedas existen como recursos de versión publicados por el propio proyecto:

| Rueda | Tamaño exacto |
| --- | --- |
| `es_core_news_md-3.8.0-py3-none-any.whl` | 40,3 MB |
| `en_core_web_md-3.8.0-py3-none-any.whl` | 31,9 MB |

Cifras consultadas a la API de versiones de `explosion/spacy-models`, no
estimadas.

**La forma exacta en el manifiesto**, porque hoy no hay ningún precedente de
dependencia fijada por URL en este proyecto y la generación de código no debería
tener que inventarla:

```toml
# app/backend/pyproject.toml
[project.optional-dependencies]
models = [
  "es-core-news-md @ https://github.com/explosion/spacy-models/releases/download/es_core_news_md-3.8.0/es_core_news_md-3.8.0-py3-none-any.whl",
  "en-core-web-md @ https://github.com/explosion/spacy-models/releases/download/en_core_web_md-3.8.0/en_core_web_md-3.8.0-py3-none-any.whl",
]
```

Es la referencia directa de PEP 508, que `uv` resuelve y **anota en `uv.lock`
con su hash**. A partir de ahí, `uv sync --locked` falla si la rueda cambia, que
es exactamente la propiedad que la práctica del equipo exige y que
`spacy download` no da.

## Por qué van en un **extra** y no en el juego principal

Aquí hay un choque real, y esta es la decisión que lo resuelve.

`mise run bootstrap` es el camino del clon al reporte, y su segundo paso,
`deps:install`, corre `uv sync --locked --all-groups`. Si los modelos fueran
dependencias normales o de grupo, **cada clon limpio se descargaría 72 MB**
antes de poder ver el primer reporte — y ese tiempo es exactamente lo que mide
`NFR21`, que U1 publica y que el trabajo semanal de clon en frío cronometra.

Comprobado en la propia herramienta: `--all-groups` y `--all-extras` son
banderas distintas, así que **un extra no lo instala `deps:install`**.

**Rige este reparto:**

| Qué | Dónde vive | Quién lo instala |
| --- | --- | --- |
| `presidio-analyzer`, `presidio-anonymizer` | Dependencias normales | `deps:install`. Son pequeñas y el módulo no carga sin ellas |
| Los dos modelos de spaCy | Un **extra** llamado `models` | `mise run models:install`, y el paso que los necesita |

Es el mismo reparto que U2 hizo con la base de datos: el camino de arranque no
la necesita, y `services:up` existe como tarea propia para lo que sí.

**Y cuando falten, el fallo tiene que ser legible.** Un `ImportError` de spaCy a
mitad de una prueba no le dice a nadie qué hacer. El cargador del módulo
comprueba que los dos modelos estén presentes y, si no, falla nombrándolos y
nombrando el comando: `mise run models:install`.

## Qué cambia en el guion de verificación

Sigue teniendo **nueve pasos**. Cambian dos.

| Paso | Qué cambia |
| --- | --- |
| **antes del 5/9** | Una línea nueva en `scripts/verify.sh`, inmediatamente antes de `paso "5/9 pruebas deterministas"`: `mise run models:install`. **No es un paso del guion**: el guion sigue teniendo nueve. Es la preparación de uno, como lo es levantar la base efímera para las pruebas de U2 |
| **5/9 pruebas deterministas** | `mise run cov` corre también las pruebas de U3, así que **necesita los modelos** ya instalados por la línea anterior |
| **6/9 aserciones de esquema** | Entran `redaction:constructor` y `redaction:report`, junto a los siete que ya están |

**Va en el guion y no en el flujo de GitHub Actions**, por la regla del equipo:
la tubería invoca el guion y no mantiene su propia lista de pasos. Va en el
guion y no en `deps:install` porque `deps:install` lo corre también
`bootstrap`, y ahí es justo donde no queremos los 72 MB.

**`test:u3` no entra al guion**, igual que `test:u1` y `test:u2`: es el comando
acotado que se corre a mano, y la compuerta ya ejecuta esas mismas pruebas en el
paso 5. Meterlo también en el 6 las correría dos veces.

### Las tareas nuevas del archivo de tareas

| Tarea | Qué hace |
| --- | --- |
| `models:install` | `uv sync --locked --extra models`. Reproducible como todo lo demás |
| `test:u3` | Las pruebas acotadas a la unidad |
| `redaction:constructor` | El análisis estático: quién produce el tipo y quién guarda un valor junto a su etiqueta |
| `redaction:report` | El informe por idioma, por tipo y por reconocedor, con la cifra del respaldo aparte |

## Qué cuesta, y qué no se estima aquí

| Qué | Cuándo se paga | Cuánto |
| --- | --- | --- |
| Descarga de las dos ruedas | Una vez por máquina en local; **en cada corrida de la tubería** mientras no exista el paso de caché de INF-U3-6 | 72,2 MB, medido |
| Carga de los dos modelos en memoria | Una vez por proceso, al arrancar | **Se mide en la primera corrida verde de la generación de código** |
| La pasada de redacción sobre un texto | Cada llamada | Presupuesto de 100 ms (NFR11.3); el valor real, igual |
| Efecto sobre el arranque en frío de `NFR21` | Cada clon limpio | **Ninguno por diseño**, porque el extra no entra en `deps:install`. Lo confirma el trabajo semanal, que es quien mide esa cifra |

Ninguna de las tres cifras pendientes se estima en este documento. Se miden
cuando el código exista y entran en el resumen de la generación, como cualquier
otro número de este proyecto.

## El despliegue

- **Los modelos viajan con el despliegue**, como dice la ficha de la unidad. No
  se descargan en el arranque: un servicio que se duerme y despierta cada noche
  no puede depender de una descarga para poder redactar.
- **Si los modelos no están al arrancar, el proceso no arranca** (NFRD-U3-2). Un
  aplicativo vivo con la redacción muerta parece que funciona.
- **No hay servicio nuevo, ni puerto, ni variable de entorno nueva.** Esta
  unidad no habla con nada fuera del proceso, y el contrato de importación lo
  hace cumplir.

## La caché de la tubería: lo que hay y lo que no

Una versión anterior de este documento afirmaba que el flujo ya cachea las
dependencias de `uv` y que por eso una corrida normal no descargaría los 72 MB.
**Es falso**, y lo encontró la revisión.

Comprobado en el código fuente de la acción que el flujo usa: cachea
**únicamente el directorio de `mise`** —las herramientas que instala— y no
`~/.cache/uv`, que es donde caerían las ruedas de spaCy. El flujo tampoco
declara ningún otro paso de caché.

**Rige, entonces:** hoy **cada corrida de la tubería descarga los 72 MB**. Si se
quiere evitar, hace falta un paso explícito de caché sobre `~/.cache/uv`,
con la clave del lockfile. Queda propuesto como decisión INF-U3-6 y **no se da
por hecho**, porque una afirmación de tubería que ningún archivo sostiene es
justo lo que obliga a un desarrollador a volver a preguntar.

El trabajo semanal de clon en frío es la excepción a propósito: declara
`cache: false` explícitamente, porque su razón de ser es medir cuánto tarda
alguien que llega por primera vez.

## Decisiones de esta etapa

| # | Decisión | Por qué |
| --- | --- | --- |
| INF-U3-1 | Los modelos entran como dependencias fijadas por URL con su hash, no con `spacy download` | La forma documentada por spaCy y por Presidio es una resolución libre, y la práctica del equipo exige instalación reproducible que falle si el lockfile no coincide |
| INF-U3-2 | Viven en un extra, no en el juego principal ni en un grupo | `deps:install` usa `--all-groups`, que no incluye extras. Así el camino del clon al reporte no se descarga 72 MB y `NFR21` no empeora por esta unidad |
| INF-U3-3 | Si faltan, el cargador falla nombrando los modelos y el comando | Un `ImportError` de spaCy a mitad de una prueba no le dice a nadie qué hacer |
| INF-U3-4 | Los modelos viajan con el despliegue, no se descargan al arrancar | El hospedaje gratuito duerme y despierta el servicio; depender de una descarga para poder redactar es depender de la red en el peor momento |
| INF-U3-6 | La caché de `~/.cache/uv` se propone como paso explícito, y hasta entonces se asume que cada corrida descarga los 72 MB | La acción que usa el flujo cachea solo el directorio de `mise`, comprobado en su código fuente. Afirmar un ahorro que ningún archivo sostiene es peor que no tenerlo |
| INF-U3-7 | La instalación del extra va en el guion de verificación, no en el flujo ni en `deps:install` | La tubería invoca el guion y no mantiene su propia lista; y `deps:install` lo corre `bootstrap`, que es donde no queremos los 72 MB |
| INF-U3-5 | Las tres cifras pendientes no se estiman | Se miden en la primera corrida verde de la generación de código, como todas las demás de este proyecto |
