# Decisiones de stack — U12 `graph-runtime`

| ID | Decisión | Por qué |
| --- | --- | --- |
| TECH-U12.1 | **LangGraph, con su versión fijada en el lockfile, y solo esta unidad lo importa** | ADR-003. Un contrato de `import-linter` lo comprueba: el día que un nodo o un canal lo importe, el grafo deja de ser sustituible y la promesa de que el orquestador es nuestro código se vuelve difícil de sostener |
| TECH-U12.2 | **La pieza de puntos de control va envuelta**: sus operaciones corren dentro de una transacción tomada del punto único de sesión | Decisión de Miguel del 2026-09-27 (Q1), que resuelve PA-3. Su riesgo y su salida están escritos en FD-U12-3: si esa pieza no tolera que otro maneje sus transacciones, se escribe la nuestra, no se abre un segundo camino a la base |
| TECH-U12.3 | **El trabajo de fondo son tareas asíncronas del mismo proceso, sin broker** | ADR-004. Un broker es otra pieza que desplegar, vigilar y pagar, para un proyecto de un proceso único con tope de gasto. Lo que el broker daría —que el trabajo no se pierda— lo dan el arrendamiento, el latido y la clave de idempotencia, que sí hay que escribir |
| TECH-U12.4 | **El trabajo de CPU va fuera del bucle de eventos** | ADR-004, enmienda del 2026-09-17. La redacción y los chequeos de forma son síncronos y corren en cada turno; dejarlos en el bucle bloquea las otras conversaciones, y en un proceso único eso son todos los visitantes a la vez |
| TECH-U12.5 | **Una sola llamada al modelo por turno** | PERF-U12.6. Con 794 ms de los 800 para la cadena de proveedores, dos no caben ni con el proveedor respondiendo perfecto |
| TECH-U12.6 | **C-15 gana un campo aditivo**: quién cuenta los reintentos, con "el ejecutor" por omisión | FD-U12-2. La alternativa era un `if` por nombre de nodo en el ejecutor común, que es la rama que la convención 9 del equipo prohíbe. La política de fallo ya era dato; esto es una línea más del mismo dato |
| TECH-U12.7 | **Ninguna dependencia de ejecución nueva además de LangGraph** | Lo demás ya está en el árbol: el mapeador, el driver, el cifrador y el catálogo |

## Dónde vive el código

`app/backend/src/untangle/orchestration/`, todo menos `nodes/`, que es de las
cuatro unidades de los nodos. El `state.py` que hoy tiene solo `NodeSpec` —puesto
ahí por U10 para que U12 lo encontrara donde el contrato dice— se completa aquí con
el estado tipado, su composición y el ejecutor.

La migración de las tres tablas va en `app/backend/migrations/versions/`, encadenada
a la cabeza actual.

## Comandos nuevos

| Comando | Qué corre |
| --- | --- |
| `mise run test:u12` (tarea nueva, la crea esta unidad) | Las pruebas de esta unidad, incluidas las cronometradas de PERF-U12.2 a PERF-U12.4 y las de fallos, reinicios y arrendamientos vencidos |

`mise run migrate:check`, `mise run rls:check` y `mise run verify` ya existen y
crecen por dentro con las tres tablas de esta unidad, sin volverse comandos nuevos.

## Sources

- `../../../inception/domain-design/components.md` — ADR-003, ADR-004 y sus
  enmiendas.
- `../functional-design/functional-spec.md` — FD-U12-2 y FD-U12-3.
- `../../../inception/contract-design/contract-summary.md` — C-14 y C-15, con la
  enmienda del 2026-09-27.
- `../../../../codekb/untangle/technology-stack.md` — el escaneo de pre-incepción
  anotaba el framework del grafo como **hipótesis**, con la nota de que lo decidido
  era el comportamiento y no la librería. ADR-003 lo confirmó en Incepción, y esta
  etapa es donde esa confirmación se paga: TECH-U12.2 acepta escribir código propio
  alrededor de su pieza de puntos de control antes que abrir un segundo camino a la
  base, que es exactamente la clase de trabajo que esa nota anticipaba.

## Assumptions & Open Questions

- **[Assumption]** LangGraph sigue siendo la elección correcta. Si al envolver su
  checkpointer resulta que hay que reescribirlo, lo que queda de él es el grafo y
  las interrupciones; el día que eso también haya que reescribirlo, la decisión de
  usarlo se revisa con lo que se haya aprendido y no antes.
