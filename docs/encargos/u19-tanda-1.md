# Encargo para una sesión en la nube — U19 `quote`, tanda 1

Pega este archivo entero como primer mensaje de una **sesión nueva**. Es la primera de
las dos tandas de U19; la segunda, la bandeja del suscriptor, se hace en local porque
necesita base de datos.

---

## Antes de nada

**Primero ponte en `main`.** Tres sesiones han empezado con un clon anterior al commit
que trae sus documentos, y han concluido que no existían:

```bash
git fetch origin && git log --oneline -1 origin/main
```

Si tu rama no desciende de ese commit, ponte ahí antes de leer nada. Los documentos que
este encargo cita **están en `main`**: si no los ves, es el checkout, no el repositorio.

Después, las dependencias:

```bash
uv tool install --force uv==0.12.16
mise run deps:install
mise run models:install
```

**Los dos últimos fallan en algunos entornos de la nube, y no es tu culpa.** `mise`
descarga Python 3.13.15 y los modelos de spaCy desde las descargas de GitHub
(`objects.githubusercontent.com`), que el túnel a veces rechaza. Si pasa:

- **Python**: prueba `uv python install 3.13`, y si tampoco baja, usa cualquier 3.13.x
  que haya en el entorno con el lockfile tal cual. Después corre los comandos de
  `mise.toml` directamente en vez de `mise run`. **Anota en los hallazgos qué versión
  usaste.**
- **Modelos de spaCy**: si no bajan, las pruebas de redacción quedan rojas con
  `ModelsMissingError`. **Eso no es un defecto del código y no se arregla tocándolo**:
  anótalo en los hallazgos y sigue con lo que sí corre.

`models:install` va después de `deps:install` y no antes: el modo reproducible
**desinstala** los modelos, porque viven en un extra y no en el lockfile.

## Qué se construye

La **solicitud de cotización y su elegibilidad**: los cuatro bloques de captura, el
esquema del tipo de registro que ya está declarado sin campos, las reglas de
elegibilidad versionadas, la banda de riesgo, las frases del catálogo y los casos de
DS-4.

Nada de esto necesita base de datos ni proveedores.

Lee estos, en este orden, y no escribas nada antes:

1. `docs/reference/estructura-solicitud-cotizacion.md` — **los cuatro bloques y cada campo con su tipo**. Es la fuente del esquema
2. `aidlc/spaces/default/intents/260915-untangle-app/construction/u19-quote/functional-design/functional-spec.md` — los flujos 1, 2 y 4
3. `.../u19-quote/functional-design/rules.md` — BR1.1 a BR3.2 son de esta tanda
4. `.../u19-quote/functional-design/functional-design-questions.md` — **las tres respuestas de Miguel están ahí: la banda, la estructura y qué hace a alguien no elegible**
5. `.../u19-quote/functional-design/entities.md` — lo que ya existe y solo se llena
6. `.../u19-quote/nfr-requirements/performance-requirements.md` — PERF-U19.1
7. `.../u19-quote/code-generation/code-generation-plan.md` — la tanda 1 es la tuya

Y del código, en este orden:

- `app/backend/src/untangle/case_record/fields.py` y `models.py` — el esquema de los siete bloques del siniestro y `RecordType.QUOTE_REQUEST`, **declarado sin campos esperando a esta unidad**
- `app/backend/src/untangle/rules/fields.py` — el vocabulario cerrado, con sus seis campos de triage y `required_inputs()`
- `app/config/tenants/sunmeadow/rules/triage.yaml` — **la forma exacta** que tiene que tener el conjunto de elegibilidad: `when`/`then`, `explanation_key` y `tests` dentro del propio YAML
- `app/backend/src/untangle/orchestration/nodes/intake/blocks.py` — cómo se declara un bloque de captura y su confirmación
- `app/config/tenants/sunmeadow/tenant.yaml` — `quote_enabled`, hoy en `false`
- `app/config/compliance/es/guard.yaml` — los cuatro patrones de importe, para que veas que **ya existen** y no escribas otros
- `app/evals/cases/ds2/intake-advanced-field/` — la forma de un caso de golden set, un archivo por idioma
- `app/config/copy/es.yaml` y `en.yaml` — el catálogo, y en particular `rules.explain.*`

## Las siete piezas

1. **Los campos del tipo `quote_request`** en el esquema del caso, en cuatro bloques, con
   su completitud. El tipo ya existe.
2. **Los cuatro bloques de captura** sobre el nodo que ya existe, una idea a la vez y con
   confirmación por bloque. **El grafo no gana nodos** (BR1.1): si te ves añadiendo uno,
   algo está mal.
3. **`vehicle_age_years` derivado en un solo sitio**, desde `vehicle_year` y el reloj que
   la captura ya inyecta. No escribas una regla que compare contra un año del calendario:
   envejece sola y no falla nada (BR1.4).
4. **Los cinco campos de elegibilidad** en el vocabulario cerrado, **cada uno con el
   bloque de captura que lo escribe** (BR1.3). Esto no es una formalidad: hoy hay seis
   campos de triage declarados que nadie escribe, y las reglas que los nombran no se
   disparan nunca sin que nada se ponga rojo.
5. **El conjunto de reglas de elegibilidad de Sunmeadow Auto**, con las cinco condiciones
   que están en la respuesta Q3, cada una versionada y con sus `tests`. `quote_enabled`
   pasa a `true` **solo ahí**; Stonecroft y Knotwell se quedan en `false`.
6. **La salida y la banda**: `eligible` / `not_eligible` / `referred`, y
   `standard_risk` / `elevated_risk` / `pending_review` / `outside_appetite`. Una
   derivación lleva `pending_review` y el tipo tiene que **impedir** construirla con otra
   banda (BR2.2).
7. **Las frases del catálogo** en los dos idiomas —la razón en lenguaje llano por regla,
   la negativa a dar un precio, y la respuesta donde la cotización está apagada— y **los
   casos de DS-4** por idioma, incluidos los que presionan por un precio. Crea
   `app/evals/cases/ds4/` siguiendo la forma de los de DS-2.

## Lo que no se puede hacer mal

1. **Ninguna respuesta con un importe, una moneda o un porcentaje** (BR3.1, compuerta
   dura). Y **no construyas un detector**: la guardia de salida ya los caza en los dos
   idiomas. Lo que esta tanda añade son los casos que lo ejercitan.
2. **La elegibilidad corre en el ritmo de fondo, no en el turno** (BR2.5). El turno lee
   lo que el fondo dejó o emite una frase de espera del catálogo. Es la misma
   prohibición que ya rige para la verificación y el cumplimiento.
3. **Ninguna cadena visible en línea**: todo texto que lee una persona sale del catálogo
   por idioma, con paridad español–inglés.
4. **La razón no lleva identificadores de regla** (BR2.3). Quien pregunta lee la
   condición; los identificadores van a la traza y a la bandeja.
5. **No bajes ningún umbral ni relajes ninguna prueba existente** para que algo pase.

## Lo que no puedes correr, y qué hacer

En este entorno **no hay base de datos ni motor de contenedores**: `scripts/verify.sh`
entero, `mise run cov` y las pruebas de integración no corren. Las de esta tanda **sí**
—todo se siembra con archivos— y si alguna necesitara base, escríbela igual y dilo.

**No corras las evaluaciones contra proveedores**: necesitan claves y gastan dinero. Los
casos de DS-4 se escriben y se validan de forma, no se ejecutan contra un modelo.

Lo que tiene que quedar en verde aquí: `mise run fmt:check`, `lint`, `types`,
`copy:check`, `content:check`, `schema:check`, `tenancy:literals`, `contracts:check`,
`voice:frases`, `chat:frases`, y las pruebas de la unidad.

## Antes de terminar

1. Corre todo lo de arriba.
2. **Rompe cada regla y comprueba que se cae una prueba.** Las que más importan aquí:
   declara un campo de elegibilidad que ningún bloque escriba; construye una derivación
   con banda afirmada; haz que una regla compare contra un año del calendario; mete un
   importe en una frase del catálogo; llama al motor de reglas desde el manejador del
   turno; añade un quinto nodo al grafo. Si una rotura no cae nada, la prueba está
   escrita a la medida del código: corrígela, no la justifiques.
3. Escribe `hallazgos-tanda-1.md` en
   `aidlc/.../construction/u19-quote/code-generation/`, con la tabla de roturas y qué se
   cayó, y **lo que no pudiste correr**.
4. Commit **en tu rama**, nunca a `main`.

## Lo que no se toca

- **La bandeja y el rol de suscriptor**: son la tanda 2, y se hacen en local.
- **Los cuatro nodos del grafo**: no se añade ninguno.
- **La guardia de salida y sus patrones.**
- **Los reconocedores de datos personales**: los de nombre y VIN ya existen.
- **La cotización de Stonecroft y Knotwell**: se queda apagada a propósito.
- **El triage de siniestros**: sus seis campos y sus reglas no son de esta unidad.
