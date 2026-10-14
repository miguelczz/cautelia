# Encargo para una sesión en la nube — U22 `public-evidence`, tanda 3

Pega este archivo entero como primer mensaje de una **sesión nueva**. Es la última
tanda de U22.

---

## Antes de nada

```bash
uv tool install --force uv==0.12.16
mise run deps:install
```

## Qué se construye

Las **dos secciones del README que se generan solas** desde la línea base vigente, y
su chequeo.

Lee estos, en este orden, y no escribas nada antes:

1. `aidlc/spaces/default/intents/260915-untangle-app/construction/u22-public-evidence/functional-design/functional-spec.md` — el flujo 3
2. `.../functional-design/rules.md` — BR4.1 y BR4.2
3. `.../functional-design/functional-design-questions.md` — **FD-U22-9 decide la forma del README**
4. `.../code-generation/code-generation-plan.md` — la tanda 3 es la tuya
5. `.../code-generation/hallazgos-tanda-1.md` y `hallazgos-tanda-2.md` — lo que la revisión local corrigió, para no repetirlo

Y del código:

- `app/backend/src/untangle/evals/evidence/` — de aquí sale la lectura de la línea base; **no se duplica**
- `app/backend/src/untangle/evals/models.py` — `RootCause`, la taxonomía cerrada de nueve valores por la que se agrupa
- `app/backend/src/untangle/evals/gates/models.py` — `Baseline` y `CaseStatus`
- `app/backend/src/untangle/workspace/` — cómo está escrito otro chequeo del guion de verificación, con su salida y su código de retorno

## La forma del README, que ya está decidida (FD-U22-9)

**Hoy no existe ningún `README.md`.** Esta tanda lo crea, con:

- Un párrafo antes del primer encabezado de segundo nivel.
- Los ocho encabezados de segundo nivel, en el orden que fija AC4.1.1: **lo que
  hace, lo que no hace, cómo falla**, y después los cinco restantes de AC4.1.2.
- Las **dos** secciones generadas —"Cómo falla" y las cinco cifras— entre marcas
  claras, para que el generador sepa qué reemplazar sin tocar lo demás.
- Las **seis** narrativas con **una línea cada una** que diga que las escribe Miguel
  en la semana 11. No inventes su contenido: una sección con texto de relleno es
  peor que una que dice que falta.

El README va **en inglés con resumen en español** (D24).

## El chequeo

Un solo comando con dos modos, como los contratos generados:

- `readme:gen` reescribe las dos secciones desde la línea base vigente.
- `readme:check` falla si lo publicado no coincide con lo que produce esa línea
  base. **Entra en el guion de verificación** (`scripts/verify.sh`), en el paso de
  los chequeos de contenido.

**Sin línea base publicada** —que es el estado de hoy— las dos secciones dicen "no
medida" con su causa, y el chequeo compara contra eso: no se pone rojo por no haber
medido todavía. Esto es lo primero que hay que hacer funcionar, porque es el único
estado que puedes probar de verdad hoy.

## Las tres cosas que no se pueden hacer mal

1. **"Cómo falla" nombra los identificadores de los casos y cita el commit** (BR4.1).
   Una sección que dijera "algunos casos de citación fallan" no sirve para ir a
   mirar. Se agrupa por la taxonomía cerrada, no con una redacción por caso.
2. **El chequeo falla cuando difieren** (BR4.2). Y su mensaje nombra la sección,
   no solo "el README cambió".
3. **No se duplica la lectura de la línea base.** Ya existe en
   `evals/evidence/`: úsala. Un segundo lector es un segundo esquema que un día
   divergirá.

## Lo que no puedes correr, y qué hacer

En este entorno **no hay base de datos ni motor de contenedores**, así que
`scripts/verify.sh` entero y la suite con cobertura no corren. Las pruebas de esta
tanda **sí deberían correr** —la línea base se siembra escribiendo su archivo, como
en la tanda 1— y si alguna necesita base, escríbela igual y dilo.

Lo que tiene que quedar en verde aquí: `ruff format`, `ruff check`, `mypy`, los
contratos de importación, el catálogo de textos, los esquemas, la regeneración de
contratos, y `readme:check` sobre el README que acabas de generar.

## Antes de terminar

1. Corre todo lo de arriba, y `readme:gen` seguido de `readme:check` (tiene que
   pasar: lo que acabas de generar coincide consigo mismo).
2. **Rompe cada regla y comprueba que se cae una prueba.** En particular: manipula el
   README a mano y comprueba que `readme:check` falla nombrando la sección.
3. Escribe `hallazgos-tanda-3.md` en `code-generation/`, y además el
   **`code-summary.md` y el `source-manifest.json` de la unidad**, que son los dos
   archivos con los que U22 se da por cerrada. Sigue la forma de
   `../u18-voice-spanish/code-generation/code-summary.md`.
4. Commit **en tu rama**, nunca a `main`.

## Lo que no se toca

- El panel de cifras y el de gasto: son las tandas 1 y 2, y están cerradas.
- Las seis secciones narrativas del README: las escribe Miguel.
- El reporte de evaluación y la línea base: son de U21; aquí solo se leen.
