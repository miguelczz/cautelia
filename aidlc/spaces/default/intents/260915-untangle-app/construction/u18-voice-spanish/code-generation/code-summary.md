# Resumen de código — U18 `voice-spanish`

La segunda capa de la voz: que el español **no sea un servicio de segunda**, que se
pueda cambiar de idioma a mitad de la llamada sin perder el caso, y que haya algo
honesto que decir cuando lo que llega no es ninguno de los dos idiomas.

**46 archivos, 2.593 líneas, tres tandas.** 94 pruebas propias en `mise run
test:u18`; 2.069 unitarias y las de integración de las cinco unidades que este
cambio alcanza en verde; formato, lint, tipos, contratos de importación,
identificadores literales, catálogo de textos, esquemas, contratos generados, el
productor único de la redacción y los chequeos de contenido, todos en verde en
local. La compuerta de GitHub Actions sobre `main` es la autoritativa.

Es la unidad **con menos código y más pruebas** del proyecto, y eso no es un
accidente del reparto: la mitad de lo que aporta es que lo ya construido se
comporte igual en el segundo idioma, y eso son pruebas y no código nuevo.

## Lo que construyó

| Tanda | Qué | Dónde |
| --- | --- | --- |
| 1 | El detector de idioma sube de `chat/` a módulo hoja, con su contrato de importación propio y una prueba sobre el repositorio real | `untangle/language.py` |
| 2 | La petición de cambio de idioma reconocida por código, la resolución del idioma de cada turno, el cambio escrito en la llamada, el segundo peldaño de la escalera y los dos eventos de traza | `voice/language_request.py`, `voice/call.py`, `voice/session.py`, `voice/retry.py`, `voice/latency.py`, `voice/loop.py` |
| 3 | El recorrido completo en español, el idioma de arranque opcional, el chequeo del registro del usted y el arreglo de la redacción | `server/voice_routes.py`, `compliance/redaction/api.py`, `orchestration/contracts.py`, `evals/content_checks.py` |

## Las tres decisiones que cambiaron algo fuera de la unidad

1. **El detector es uno solo, no dos.** Sube a módulo hoja en vez de copiarse,
   porque dos detectores con los mismos umbrales son dos números que divergen el
   día que alguien afine uno, en un proyecto que publica adherencia de idioma
   **por idioma**. Lo vigila un contrato de importación propio y una prueba que
   busca `LanguageDetectorBuilder` en todo el código fuente y exige que aparezca
   en un solo archivo.

2. **Una frase del catálogo no pasa por el detector de datos personales.** La
   guardia de salida sigue siendo el único punto de salida; lo que cambia es qué
   se le hace al texto. Decisión de Miguel del 2026-09-30, tras medir que el
   detector alteraba **7 de 131** frases del catálogo en español y **0 de 131** en
   inglés. `FinalText` gana un campo aditivo, `from_catalog`, porque el canal no
   puede mirar un texto y saber de dónde vino.

3. **El idioma de la llamada cambia; el del caso, no.** Si el caso siguiera al
   último turno, mover un caso de cola costaría decir dos palabras en el otro
   idioma, que es RT-10 con otra ropa. Es una de las dos reglas `[bloquea]` de la
   unidad y se comprueba en la base, no sobre el objeto en memoria.

## Lo que se midió

| Objetivo | Meta | Medido |
| --- | --- | --- |
| PERF-U18.1 — lo que reconocer el idioma añade al turno | p95 ≤ 15 ms | **p95 0,044 ms**, máximo 0,050 |
| PERF-U18.2 — del cambio pedido a la respuesta en el idioma nuevo | cero turnos de retraso | Cumplido: el turno de la petición llega al grafo ya en el idioma nuevo |

Las metas de punta a punta por idioma (NFR1, NFR2 y NFR3 en español) se miden
**por hito** sobre DS-5, que son grabaciones de personas reales que viven fuera del
repositorio. Sin ellas se declaran "no medidas", nunca se omiten.

## Lo que esta unidad no construye

- **La llamada base**: es U16. Aquí no se duplica ninguna pieza suya.
- **Los límites públicos y la voz de respaldo**: U17.
- **Las grabaciones de DS-5 en español**: semana 9, con consentimiento.
- **El acento de Catalina**: lo juzga la prueba ciega de la semana 9.
- **El registro del usted en lo que escribe el modelo**: el reporte de la corrida
  no guarda los turnos, así que no hay nada que recorrer; esa mitad es del juez.

## Los tres documentos de revisión

Uno por tanda, con lo que se rompió y qué se cayó: `hallazgos-tanda-1.md`,
`hallazgos-tanda-2.md` y `hallazgos-tanda-3.md`. Entre los tres, **dieciocho
roturas** y dos hallazgos que ninguna prueba nombraba hasta que se rompieron.
