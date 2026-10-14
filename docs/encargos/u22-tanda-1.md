# Encargo para una sesión en la nube — U22 `public-evidence`, tanda 1

Pega este archivo entero como primer mensaje de una **sesión nueva** de la nube.
No se comparte la memoria de la sesión local: todo lo decidido está escrito en el
repositorio y este encargo dice dónde.

---

## Antes de nada

```bash
uv tool install --force uv==0.12.16
uv sync --locked --project app/backend --all-groups
```

El `uv` de fábrica (0.8.17) reescribe el lockfile; el que fija el proyecto lo
entiende. Si `mise` está disponible en este entorno, úsalo y corre `mise run <tarea>`
en vez de los comandos a mano; si no, los comandos equivalentes están en
`docs/reference/sesiones-en-la-nube.md`.

## Qué se construye

La primera tanda de U22: **las cinco cifras públicas del sistema y su panel**. No
toca la base de datos: lee un archivo versionado.

Lee, en este orden, y no empieces a escribir antes de haberlos leído:

1. `aidlc/spaces/default/intents/260915-untangle-app/construction/u22-public-evidence/functional-design/functional-spec.md`
2. `.../functional-design/rules.md` — las doce reglas, dos con `[bloquea]`
3. `.../functional-design/entities.md` — `MetricsSnapshot` y `Figure`
4. `.../nfr-requirements/security-requirements.md` — SEC-U22.1 es la que importa
5. `.../code-generation/code-generation-plan.md` — la tanda 1 es la tuya

Y estos del código, que son de lo que se lee:

- `app/backend/src/untangle/evals/gates/models.py` — `Baseline`
- `app/backend/src/untangle/paths.py` — `current_baseline_path()`
- `app/frontend/src/pages/status/` — una pantalla ya construida, para el estilo

## Las cinco cifras y de dónde sale cada una

| Cifra | De dónde | Hoy |
| --- | --- | --- |
| Completitud del caso | Tasa por criterio de la línea base | No medida: no hay línea base |
| Precisión de citación | Tasa por criterio de la línea base | No medida: no hay línea base |
| Latencias | Los eventos de traza de la voz y del chat | No medidas: se miden por hito |
| Costo por caso | El registro de gasto | **No la construyas en esta tanda**: es de la tanda 2, que consulta la base |
| Casos por aseguradora | Recuento en la base | **No la construyas en esta tanda**, por lo mismo |

En esta tanda las cinco aparecen; las dos últimas salen "no medida" con la causa
"se construye en la tanda 2". Es literal: no inventes una consulta a la base.

## Las cuatro cosas que no se pueden hacer mal

1. **Ninguna cifra en cero donde lo cierto es "no medida"** (BR1.2, `[bloquea]`).
   Un cero afirma que se midió. `not_measured_cause` es obligatorio cuando el
   estado es `not_measured`.
2. **Ningún identificador de caso en la respuesta del servidor** (BR2.1, SEC-U22.1,
   `[bloquea]`). El recuento por aseguradora es cuántos, no cuáles. La prueba mira
   **la respuesta del servidor**, no lo que dibuja la pantalla: devolver la lista y
   contarla en el navegador pasaría la cifra y filtraría la lista entera.
3. **Nunca un promedio de los dos idiomas** (BR1.4). Lado a lado, siempre.
4. **Ninguna cadena visible escrita en línea.** Todo texto sale del catálogo por
   idioma, en `app/config/copy/es.yaml` y `en.yaml`, con su clave. Hay un chequeo
   que lo hace cumplir.

## Cómo se prueba

Lee `aidlc/.../u18-voice-spanish/code-generation/unit-test-instructions.md` para el
estilo, y `docs/reference/como-se-revisa-el-codigo.md` antes de darte por
terminado. Las pruebas de esta tanda no necesitan base de datos: la línea base se
siembra escribiendo un archivo temporal.

Lo que hay que probar está en la tanda 1 del plan. Dos que conviene subrayar:

- Con una línea base sembrada, **las dos cifras que le corresponden se llenan y las
  otras tres siguen sin medir**. Una prueba que solo mire el caso sin línea base no
  distingue "lee bien" de "no lee".
- El recuento por aseguradora **no trae ningún identificador sembrado**. Siembra
  casos con identificadores reconocibles y exige que ninguno aparezca en la
  respuesta.

## Antes de terminar

1. Corre las pruebas de la tanda y los chequeos: formato, lint, tipos, contratos de
   importación, catálogo de textos.
2. **Rompe cada regla que dices cumplir y comprueba que se cae una prueba.** Si no
   se cae ninguna, la prueba está escrita a la medida del código: se corrige la
   prueba. Un `ImportError` no cuenta como rotura.
3. Escribe `hallazgos-tanda-1.md` en la carpeta `code-generation/` de la unidad con
   lo que rompiste y qué se cayó.
4. Commit **en tu rama**, nunca a `main`. La sesión local revisa y lo lleva a `main`.

## Lo que no se toca

- La base de datos, las evaluaciones y `scripts/verify.sh`: no corren en este
  entorno.
- El reporte de evaluación y la línea base: son de U21, aquí solo se leen.
- El panel de gasto y el README: son las tandas 2 y 3, y se construyen en local.
