# Requisitos de rendimiento — U22 `public-evidence`

Versión corta. Esta unidad no está en el camino de ningún turno, así que no hereda
ningún presupuesto de latencia de la conversación. Lo que sí tiene es un
presupuesto propio, y existe por una razón concreta.

| Identificador | Qué mide | Meta | Cómo se obtiene su valor |
| --- | --- | --- | --- |
| PERF-U22.1 | Lo que tarda el servidor en armar las cinco cifras | **p95 ≤ 200 ms** | `mise run test:u22`, cronometrado |
| PERF-U22.2 | Lo que tarda el panel de gasto en armar sus cuatro vistas | **p95 ≤ 500 ms** | `mise run test:u22`, cronometrado |

**Por qué PERF-U22.1 y por qué ese número.** Las cinco cifras salen de un archivo
versionado que se lee entero. Doscientos milisegundos son holgados para leer y
resolver un JSON; si se pasa, no es que el archivo sea grande: es que alguien puso
una consulta a la base dentro del bucle de las cifras, y eso es lo que el número
está ahí para atrapar.

**PERF-U22.2 es más laxo a propósito**: sus cuatro vistas sí consultan la base, y
una de ellas agrega por mes sobre toda la ventana.

## Las metas que esta unidad **publica** pero no cumple

El panel muestra las latencias de la conversación (NFR1, NFR2) y el costo por
caso. Son metas de otras unidades: aquí solo se muestran, con su fecha y su
commit, y como "no medidas" mientras no se hayan medido por hito.
