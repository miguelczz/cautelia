# Requisitos de rendimiento — U8 `policy-rag`

Dos cosas se miden aquí: lo que cuesta buscar y lo que cuesta indexar. La
tercera —cuánto puede tardar el nodo antes de degradar— **no se fija en esta
unidad**, y eso está dicho a propósito más abajo.

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| PERF-U8.1 | Llamadas al proveedor de embeddings en una reingesta sin cambios en el corpus (AC5.2.4) | **Exactamente 0** | Tarea nueva `mise run test:u8` |
| PERF-U8.2 | Cláusulas reindexadas cuando cambia una sola cláusula (AC5.2.4) | **Exactamente 1** | Tarea nueva `mise run test:u8` |
| PERF-U8.3 | Duración de `retrieve` sin la llamada al proveedor, p50 y p95, sobre las 40 preguntas de DS-3 | **Se publica desde la primera corrida**; el umbral que bloquea lo fija U12 con la política de fallo del nodo | `mise run evals:gate` |
| PERF-U8.4 | Duración de la ingesta completa de los tres corpus, y número de llamadas al proveedor que hace | **Se publica desde la primera corrida**, sin umbral | Tarea nueva `mise run corpus:ingest` |
| NFR17.1 | Aporte de U8 a la corrida de evaluación de texto (NFR17, dueña U21: 10 minutos o menos en total) | El subconjunto de DS-3 cabe en el presupuesto de la corrida | `mise run evals:gate` |

## Por qué PERF-U8.3 se publica y no bloquea

El tiempo máximo del nodo antes de degradar es **dato de la política de fallo**,
y esa política la aplica el ejecutor común de U12 `graph-runtime`, que todavía
no existe (convención 8, BR5.2). Fijar aquí un número sería inventarlo: no sale
de ningún documento aprobado ni de ninguna medición. Lo que sí se puede hacer
hoy, y se hace, es **medirlo y publicarlo** desde la primera corrida, para que
cuando U12 fije su umbral lo fije contra un número real y no contra una
intuición.

Lo mismo vale para PERF-U8.4: la ingesta la corre una persona o el
aprovisionamiento, no un turno, así que su duración se publica para saber si
algún día molesta.

## Restricción de recursos

- **Las llamadas de embeddings no tienen precio publicado.** `gemini-embedding-001`
  salió de la página de precios de Google, y U5 dejó escrito que sus llamadas se
  registran como **no medidas** y nunca como cero, con su conteo aparte. U8 es
  quien las consume, así que esa consecuencia aterriza aquí: el costo por caso
  de una pregunta de cobertura se publica con el hueco declarado, no con un cero
  que lo esconda.
- **La ingesta no corre al arrancar** (FD-U8-5). Un arranque que indexa es un
  arranque que llama al proveedor sin que nadie lo pidiera, y con el tope de
  5 USD en 90 días eso no es una molestia sino un riesgo.
- **La búsqueda vectorial es exacta, sin índice aproximado** (FD-U8-6): con 104
  cláusulas por corpus, el costo de mantener un índice HNSW no se paga con nada
  medible.

## Sources

- `../functional-design/rules.md` — BR1.5, BR1.6, BR2.3, BR5.2.
- `../functional-design/functional-spec.md` — FD-U8-5 y FD-U8-6.
- `../../../inception/units-generation/unit-of-work.md` — tabla de metas: NFR17
  es de U21; NFR4 (latencia del chat) es de U13.
- `app/config/providers/prices.yaml` — la nota sobre el modelo de embeddings sin
  precio, que U5 escribió señalando a U8.

## Assumptions & Open Questions

- **[Q]** ¿Quién fija el tiempo máximo de `policy_verification` antes de
  degradar? Se asigna a U12 `graph-runtime`, que es la dueña del ejecutor de
  nodos y de las políticas de fallo. U8 entrega la medición; si U12 descubre que
  el número real no cabe en su presupuesto, el ajuste es de recuperación y
  vuelve aquí.
