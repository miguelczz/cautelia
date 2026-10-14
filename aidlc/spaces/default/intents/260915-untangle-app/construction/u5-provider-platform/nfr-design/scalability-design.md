# Diseño de escalabilidad — U5 `provider-platform`

El requisito ya dijo el tamaño real: quince llamadas de voz al día como techo del
carril público, un chat con límite por sesión y por día, y 5 USD en noventa días.
Este documento dice **dónde está el punto serializado, cómo se indexa lo que
crece, y qué se hace el día que alguno de esos números cambie**.

## El punto serializado, a propósito

Toda llamada facturable incrementa la misma fila. Eso serializa las escrituras
facturables del proyecto entero y es exactamente lo que compra la cota del
exceso: dos llamadas simultáneas no pueden pasar el techo cada una creyendo que
la otra no existe.

**Su costo, con número.** El carril público admite quince llamadas al día; un
turno de voz de tres minutos hace del orden de quince llamadas al modelo. En el
peor momento imaginable, eso son unas pocas escrituras por minuto contra una
fila. La contención no es un problema a esta escala y no se diseña contra ella.

**Lo que no se hace, y por qué.** Partir el acumulado en varias filas, o sumarlo
del historial, compraría concurrencia que nadie va a usar y vendería la única
garantía que el techo tiene. Si algún día hiciera falta —otro proyecto, otro
tráfico—, el camino correcto es un contador por partición con reconciliación, y
se dice aquí para que esa decisión se tome mirando un número.

**Lo no facturable no toca ese punto.** El chat en plan gratuito escribe en
diferido y no incrementa el acumulado, así que el único volumen que puede crecer
de verdad no pasa por la fila serializada.

## Índices, y qué consulta sirve cada uno

| Tabla | Índice | Qué consulta sirve |
| --- | --- | --- |
| `budget_window` | Clave primaria por comienzo de ventana | El estado del presupuesto y su incremento |
| `quota_counter` | Único por (alcance, sujeto, comienzo del periodo) | La consulta y el incremento de cuota, y el propio contrato de unicidad |
| `spend_entry` | Por fecha de ocurrencia | El reporte por mes y la ventana |
| `spend_entry` | Por (proveedor, fecha) | El reporte por proveedor |
| `spend_entry` | Por caso, parcial sobre las filas que nombran uno | El costo de un caso en la bandeja |

El índice por caso es **parcial** porque la columna es nula en todo lo que no
tiene aseguradora —evaluaciones, generación, operación— y en todo lo que perdió
su caso en el reinicio nocturno. Indexar nulos costaría espacio para responder
una consulta que nadie hace.

Ninguno de los tres índices de `spend_entry` está en el camino de un turno: los
tres sirven al reporte.

## Lo que crece, y hasta dónde

| Qué | Ritmo | Cota |
| --- | --- | --- |
| `spend_entry` | Una fila por llamada a proveedor | Ninguna. Es el histórico de costo y borrarlo perdería la cifra que se publica |
| `quota_counter` | Una fila por sujeto, alcance y periodo | El purgador nocturno se lleva los de visitante y de sesión; queda uno por día del sitio |
| `trace_summary` | Uno por respuesta del chat | El purgador nocturno se los lleva con su caso |
| `budget_window` | Una fila por ventana de noventa días | Cuatro filas al año |

**El único sin cota es el registro de gasto**, y se deja así. A este ritmo son
miles de filas en noventa días. Si algún día molestara, lo correcto es archivar
por ventana cerrada —no borrar—, y queda escrito aquí para que no sea una
sorpresa.

## Qué pasa si alguno de los números cambia

| Si cambia | Qué aguanta | Qué habría que rediseñar |
| --- | --- | --- |
| El techo sube de 5 USD | Todo | Nada; es un valor de la fila |
| El cupo diario del sitio sube a cientos | La fórmula y los índices | Nada hasta que la contención sobre la fila única se note, y entonces el contador por partición |
| El chat recibe tráfico de verdad | La cola diferida y los índices | El tamaño de la cola, que es un valor; y medir si la escritura diferida sigue fuera del camino |
| Aparece un cuarto uso de pago | La fábrica, el carril y la tabla de topes | Nada estructural: un uso más es una entrada más |
| El proyecto deja de ser una demostración | Casi nada de esta unidad | La fila única del acumulado es lo primero, y es lo que este documento nombra para que se sepa por dónde empezar |

## Sources

- `../nfr-requirements/scalability-requirements.md` — SCA-U5.1 a SCA-U5.4
- `../nfr-requirements/performance-requirements.md` — PERF-U5.1 a PERF-U5.4
- `../functional-design/entities.md` — las cuatro entidades guardadas con sus
  claves
- `../functional-design/rules.md` — BR4.6, BR5.6, BR7.5, BR7.6
- `<record>/inception/requirements-analysis/requirements.md` — FR3.9 con su
  enmienda del 2026-09-19, FR4.6, NFR15

## Assumptions & Open Questions

- El archivado del registro de gasto por ventana cerrada no se diseña ahora: no
  hay volumen que lo justifique. Queda nombrado como el camino correcto.
- El dimensionado del pool de conexiones es de U2, dueña del punto único de
  sesión.
