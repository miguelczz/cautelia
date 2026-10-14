# Diseño de rendimiento — U5 `provider-platform`

Dos presupuestos fijados y una regla que los sostiene: **15 ms en p95** para la
transacción que escribe el gasto facturable, **50 ms en p95** para las dos
consultas del camino de disponibilidad, y ninguna caché sobre el acumulado.

Lo que sigue es cómo se consiguen. Es corto porque el diseño consiste sobre todo
en **no hacer cosas**: no leer antes de escribir, no cachear lo que decide el
corte, y no poner en el camino del turno lo que no tiene que estar.

## La escritura facturable: una transacción, dos sentencias, ninguna lectura

```
BEGIN
  INSERT INTO spend_entry (...) VALUES (...)
  UPDATE budget_window
     SET billable_spent_usd = billable_spent_usd + :costo,
         recording_spent_usd = recording_spent_usd + :costo_de_grabacion,
         unmeasured_billable_calls = unmeasured_billable_calls + :no_medida
   WHERE window_start = :ventana
  RETURNING billable_spent_usd, alert_usd, cap_usd, alert_sent_at
COMMIT
```

Tres propiedades salen de esta forma, y ninguna es accidental:

- **No hay lectura previa**, así que no hay ventana entre leer y escribir. El
  motor serializa las escrituras sobre la misma fila por sí solo.
- **La sentencia devuelve el acumulado ya incrementado**, que es exactamente lo
  que hace falta para saber si *esta* llamada fue la que cruzó la alerta y le
  toca emitirla. Sin ese valor de vuelta habría que releer, y la relectura
  reabriría la carrera.
- **Las dos sentencias son una transacción.** Si la segunda falla, la primera no
  queda: el registro y el acumulado no se pueden separar.

La emisión de la alerta se decide **dentro** de la transacción y se marca
**dentro** de ella, por la misma razón que existe la marca: dos llamadas que
cruzaran a la vez emitirían dos alertas si la marca se escribiera fuera.

## El camino de consulta: dos lecturas por clave primaria

La disponibilidad de la voz tiene 300 ms en el contrato C-08 y esta unidad usa 50
de ellos. Dentro: el contador de cuota del día por su clave, el acumulado de la
ventana por la suya, y la aritmética del cupo en memoria. Nada recorre el
historial.

**Índices que lo sostienen.** El contador lleva clave única por (alcance, sujeto,
comienzo del periodo), que es también su forma natural de búsqueda. El acumulado
se busca por la fecha de comienzo de la ventana, que es su clave. El registro de
gasto no participa en este camino: sus índices —por fecha y por proveedor— sirven
al reporte, que corre cuando alguien lo pide.

**Sin caché, a propósito.** Cachear el acumulado ahorraría una lectura de fila
única y reintroduciría exactamente la ventana que la transacción cierra: dos
llamadas leerían la misma copia. El único dato que sí vive en memoria es la tabla
de precios, y eso se puede porque **no cambia sin un despliegue**.

## La tabla de precios, en memoria

Se carga una vez al arrancar desde configuración versionada. Calcular el costo de
una llamada es una búsqueda por (proveedor, modelo, tipo de unidad) y una
multiplicación decimal.

No se recarga en caliente, y eso es una decisión: cambiar un precio es un cambio
de código que dispara la compuerta de evaluaciones, porque mueve una cifra
publicada. Una recarga en caliente permitiría moverla sin que quedara en el
historial.

## La cola de lo no facturable

Lo que no se factura —el chat y las evaluaciones en plan gratuito— escribe su
fila fuera del camino de la respuesta.

- **Una cola acotada en el proceso**, drenada por una tarea del mismo proceso.
- **Al llenarse, la escritura pasa a síncrona.** Se paga latencia en el chat justo
  cuando la base va lenta; a cambio no se pierde ninguna fila. Una cifra de costo
  a la que le faltan llamadas no es una medición, y el costo por caso es una de
  las cinco que el proyecto publica.
- **Al apagarse el proceso**, la cola se drena antes de cerrar. Un apagado que
  descarta filas tendría el mismo efecto que descartarlas al llenarse.

## Los tiempos máximos hacia el proveedor

Cada adaptador lleva su tiempo máximo de conexión y de lectura, declarados **por
uso** en configuración versionada. Por uso y no global porque los usos tienen
paciencias distintas: el turno de voz no puede esperar lo que una corrida de
evaluaciones sí.

Lo que esta unidad **no** decide es cuántas veces se reintenta ni qué se responde
mientras tanto: eso es la política de fallo por nodo, que aplica el ejecutor común
de U12. Aquí solo se corta la espera y se traduce el error.

## Lo que esta unidad mantiene fuera del camino del turno

| Trabajo | Dónde corre | Por qué |
| --- | --- | --- |
| La fila de gasto no facturable | En la cola, fuera de la respuesta | Ningún techo depende de ella |
| El reporte de gasto | A petición | Recorre filas; nada del turno lo necesita |
| La exportación de trazas | Fuera de la respuesta, por lotes | Si falla, no se detiene nada (BR4.8) |
| El resumen de traza | Se crea vacío al salir la respuesta y se completa después | Lo que el visitante ve mientras tanto es "registrándose", que es una respuesta |

## Sources

- `../nfr-requirements/performance-requirements.md` — PERF-U5.1 a PERF-U5.4 y las
  tres metas de NFR14
- `../functional-design/functional-spec.md` — los flujos F1 a F6
- `../functional-design/rules.md` — BR3.2, BR4.3, BR4.5, BR4.6, BR6.1
- `<record>/inception/contract-design/contract-summary.md` — C-08 y C-17
- `nfr-design-questions.md` — Q2 y Q3

## Assumptions & Open Questions

- Los presupuestos de 15 ms y 50 ms se fijan sobre la base local en contenedor,
  que es donde corre la suite. Si el proveedor de base gestionada que elija el
  intent `infra` tuviera una latencia base mayor, los números se revisan allí con
  su medición, no se relajan aquí.
- El tamaño de la cola de lo no facturable se fija en la generación de código con
  una cifra y su razón; lo que esta etapa decide es la conducta al llenarse.
- El pool de conexiones lo dimensiona U2, dueña del punto único de sesión. Esta
  unidad no abre conexiones propias.
