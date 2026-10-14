## Review

**Verdict:** NOT-READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-09-20T19:54:42Z
**Iteration:** 1

Revisión asesora de `security-design` de U3 `pii-redaction`, por lectura cruzada
contra `logical-components.md`, `traceability.json`, las dos etapas cerradas de
la misma unidad, C-13 y los ADR-004 y ADR-013.

El diseño tiene una base sólida —fallar cerrado, los dos relojes, la frontera
con U21 resuelta por archivo— y trazabilidad completa de sus veinte
identificadores. Pero contenía una contradicción interna comprobable en el
contrato de importación y dos huecos concretos: el chequeo que sostiene la
irreversibilidad no cubría todas las formas de producir el tipo, y el documento
no decía cómo la redacción del parcial cumple con una obligación ya aprobada.

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Critical | `logical-components.md` — "Qué puede importar qué" y el diagrama | El texto fijaba tres capas con `api` arriba y `streaming` en medio, y la regla "puede importar las de abajo y nunca las de arriba". Pero el mismo diagrama muestra `streaming` llamando a `api`, y el Flujo 2 del diseño funcional lo exige. La regla escrita y el flujo obligatorio no podían cumplirse a la vez: implementada al pie de la letra, el contrato habría bloqueado esa llamada. | Corregir el orden de capas para que la regla coincida con la llamada real. | Resolved |
| R-02 | Major | `security-design.md` — Capa 1; `rules.md` — BR1.8 | El chequeo que sostiene SEC-U3.2, SEC-U3.7 y SEC-U3.8 se describía como una búsqueda de la aparición de `Redacted(` fuera de `api.py`. Como el tipo se borra en tiempo de ejecución, `cast(Redacted, texto_sin_tapar)` produce un valor que el comprobador acepta sin invocar el constructor y sin coincidir con ese patrón. El documento afirmaba que la irreversibilidad la comprueba una herramienta, pero esa herramienta no cerraba la vía del `cast`. | Ampliar el chequeo para que falle también ante `cast` y ante cualquier otra forma de forzar el tipo. | Resolved |
| R-03 | Major | `security-design.md` — "Los dos relojes"; Flujo 2 | ADR-004 nombra la redacción por su nombre entre el trabajo de CPU que va a un hilo o a un pool, con semáforos por uso. La redacción del fragmento parcial ocurre dentro del turno de voz, que es justo el escenario que ese ADR señala, y el diseño no decía en ningún punto dónde se ejecuta esa llamada: trataba el presupuesto de 100 ms como si bastara con cronometrarla. | Decir cómo corre fuera del bucle de eventos conforme a ADR-004, y cómo se aplica el semáforo por uso. | Resolved |
| R-04 | Minor | `security-design.md` — Capa 4, filas SEC-U3.9 y SEC-U3.14 | Las dos filas repetían casi literalmente el texto del control de `security-requirements.md` sin añadir el cómo: qué campo transporta el identificador del reconocedor, o cómo se arma la descripción de la diferencia sin el valor. | Añadir el mecanismo concreto, igual que el resto de la Capa 3. | Resolved |

### Evidencia de resolución

**R-01.** El orden pasa a cuatro capas con `streaming` **arriba** de `api`, que
es lo que de verdad ocurre: `streaming` es un consumidor de la superficie que
vive dentro del mismo paquete, no una pieza interna por debajo de ella. Y
`sinks` sale de la escalera: en una capa habría tenido permiso para importar las
de abajo, así que recibe su propio contrato prohibido —no importa ninguna otra
pieza—, que es lo que impide que el registro se convierta en un séptimo punto de
salida encubierto. El diagrama y su texto alternativo se rehicieron con el mismo
orden.

**R-02.** El chequeo deja de buscar una llamada y pasa a buscar **producir el
tipo**, en sus tres formas: el constructor, `cast(Redacted, ...)` y una
anotación con `# type: ignore` al lado. Queda escrito por qué hacen falta las
tres: un control que solo cubre la forma obvia de saltárselo atrapa los
descuidos y no los atajos.

**R-03.** Sección nueva, "Dónde corre la redacción, que no es donde parecía": la
llamada va a un hilo del pool y no al bucle de eventos, con semáforo por uso
—voz, chat y fondo— para que una corrida de evaluaciones en segundo plano no se
quede con los hilos de una llamada en curso. Y se aclara qué significan los
100 ms: son de la pasada, no del turno, porque lo que el turno no puede
permitirse es quedarse bloqueado y eso lo resuelve el pool. Queda como decisión
NFRD-U3-6.

**R-04.** SEC-U3.9 nombra el campo `recognizer_id` y dice que el informe agrupa
**dos veces sobre la misma lista** de hallazgos, en vez de llevar dos recuentos
independientes que puedan divergir. SEC-U3.14 dice que el reporte **no recibe
los dos valores**: recibe el tipo, la longitud de cada uno y en qué posición
difieren, de modo que la comparación la hace quien tiene los valores y lo que
cruza es ya su resultado.
