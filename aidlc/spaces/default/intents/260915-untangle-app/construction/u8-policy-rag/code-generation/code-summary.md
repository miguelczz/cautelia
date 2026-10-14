# Resumen del código — U8 `policy-rag`

U8 es la unidad que hace que una cita signifique algo. Deja construido:

- **El corpus dentro de la base.** Siete tablas con aislamiento por aseguradora,
  y una ingesta que compara el manifiesto antes de leer nada, valida el corpus
  entero antes de escribir, y reindexa solo lo que cambió.
- **La recuperación filtrada.** Filtra por aseguradora y póliza **antes** de
  puntuar, fusiona léxico y vectorial por rango recíproco, y cierra por
  relaciones sin que el cierre cuente para la métrica.
- **El verificador exacto.** Cuatro comprobaciones por consulta y sin modelo,
  más la que rechaza una cita que un endoso vigente modifica. Una sola cita sin
  `verified` detiene la respuesta entera.
- **El nodo `policy_verification`**, puro y cerrado, con su política de fallo y
  la forma de la cita por canal.
- **Los 40 casos de DS-3**, escritos antes del código, con la prueba que
  comprueba contra el corpus real que cada identificador esperado existe.

Se construyó en tres tandas, las tres escritas en sesiones de la nube con
Sonnet y revisadas aquí.

## Resultados

| Compuerta | Resultado |
| --- | --- |
| `mise run test:u8` | 172 pruebas en verde, incluidas 22 de integración |
| `mise run cov` | 88,14 % agregado; `policy_rag/citations` **98,89 %** como módulo crítico |
| `mise run rls:check` | 21 tablas con política, 20 llaves foráneas entre tablas aisladas |
| `mise run migrate:check` | Sube, baja y vuelve a subir contra una base virgen |
| `mise run evals:gate -- --subset smoke` | 52 casos, 0 fallos |
| `mise run evals:run` (completa) | 100 casos: 56 pasan, 42 fallan por `not_built`, 2 no medidos |
| `scripts/verify.sh` | Los nueve pasos en verde |

## Lo que salió de la revisión

Cada tanda pasó todas las compuertas que la nube podía correr y trajo algo que
solo se ve con base de datos o con el proveedor de verdad. Esto es lo que la
revisión encontró, en orden de gravedad.

**1. Una llave foránea sin aseguradora.** `coverage_answers` apuntaba al turno
solo por `turn_id`. Las llaves foráneas no pasan por las políticas de fila, así
que una respuesta de una aseguradora podía apuntar al turno de otra — el agujero
exacto que el aislamiento existe para cerrar, en la unidad cuya compuerta dura es
que no haya fuga entre aseguradoras. Lo encontró la aserción de aislamiento que
U2 construyó. Se arregló con llave compuesta, lo que obligó a añadirle a la tabla
de turnos de U4 una unicidad sobre `(tenant_id, turn_id)`, aditiva.

**2. La ingesta no podía funcionar con ninguna clave.** Mandaba todas las
cláusulas de una aseguradora en una sola llamada —104 y 207— y el proveedor
admite cien por lote. El adaptador traducía ese `400` a `invalid_response`, así
que el mensaje no decía nada útil. Ahora va por lotes, con el tamaño fijado en la
raíz de composición y su medición escrita al lado.

**3. Y aun por lotes, nunca habría terminado.** Los vectores se guardaban en
memoria hasta el final, así que un `429` en la cláusula 200 tiraba las 199
anteriores; volver a pedirlas gasta justo la cuota que se acabó. Ahora cada lote
se escribe en cuanto vuelve, y la comparación de hashes que BR1.5 ya exigía hace
que la siguiente corrida pida solo lo que falta.

**4. La columna del vector nacía fijada a 768 dimensiones**, lo que contradice
que el identificador del modelo sea parte de la clave del índice: un modelo de
otra dimensión no cabría sin migración. La dimensión se comprueba ahora en
código, que es donde ADR-006 la puso.

**5. Los casos de distractor no nombraban el distractor**, así que AC2.1.2 —"esa
cláusula no se recupera ni se cita"— no tenía contra qué comprobarse, y esos seis
casos eran indistinguibles de una pregunta corriente.

**6. La corrida completa de evaluaciones se caía** en vez de reportar los 40
casos de DS-3 fallando. Un caso que tumba la corrida no se ha visto fallar, se ha
visto explotar.

**7. Cuatro pruebas de integración que nunca se habían ejecutado** traían sus
propios errores: vectores de consulta de otra dimensión, un cierre por relaciones
que el fixture no dejaba observar, y un evento escuchado con `capsys`, que no ve
el punto único de salida porque este se queda con la referencia a la salida
estándar al importarse.

La lección que se repite desde U9: **el modo ligero pasa todo lo automático y
cada tanda trae un defecto que solo ve la revisión.** Lo nuevo de U8 es de dónde
salieron: tres de los siete solo aparecen con una base de datos delante, y dos
más solo en la primera llamada real al proveedor.

## Decisiones y desviaciones registradas

| Qué | Por qué se acepta |
| --- | --- |
| `RootCause` gana un noveno valor, `not_built`, que no viene del PRD | Decisión de Miguel del 2026-09-27. Los ocho del PRD describen cómo falla un sistema construido; un caso previo falla porque la conducta no existe, y marcarlo `infrastructure` contaría como fallo del producto algo que no lo es (BR3.4) |
| El nodo consume sus propios `attempts`, y es el único de los cuatro | Tras agotarlos todavía tiene que escribir el `CoverageAnswer` con `unverifiable`, que es el valor distinguible que BR3.4 exige y que nadie más sabe escribir. Queda escrito en el propio nodo que U12 tiene que decidir de qué lado se cuenta, o serían cuatro llamadas en vez de dos |
| El nodo no redacta la respuesta: recibe las citas propuestas y hace su propia recuperación autoritativa | Verificar contra lo que uno mismo recuperó es exactamente lo que BR3.1 exige. Decisión tomada y reportada por la tanda 3 |
| El cierre por relaciones da **un solo salto** | Hoy no existe ninguna cadena de endosos en el corpus —cero en las tres aseguradoras, comprobado— así que la compuerta de BR3.5 está completa. Un endoso que modificara la cláusula de otro endoso no se vería; queda escrito |
| AC2.1.4 se satisface con RLS sobre `clause_index` y no con un espacio de nombres | Su premisa —un índice fuera de las tablas aisladas— no se cumple aquí: ADR-010 puso pgvector dentro de la base (FD-U8-4) |

## Lo que queda abierto, con dueño

- **Los 40 casos de DS-3 fallan**, con causa `not_built`. Corren por un conductor
  de chat que vive en `evals/drivers/` y lo construye **U13**. U8 deja la
  conducta y el medidor; falta el cable.
- **La comprobación de respaldo se publica como "no medida"** hasta que estén
  etiquetadas las 40 transcripciones de DS-7: es de **Miguel**, con
  `mise run evals:label`. Hoy ese comando no tiene cola que leer, que es un cabo
  suelto de U21 sin dueño asignado.
- **La ingesta real está a 100 de 414 cláusulas.** No es un fallo: es la cuota
  diaria del plan gratuito. Está probada de punta a punta contra el proveedor de
  verdad y se retoma sola en cada corrida.
- **El libro mayor del gasto falla al anotar** las llamadas de este uso
  (`IntegrityError` en cada una). Es de **U5**, y no afecta a la ingesta.
- **El umbral de tiempo del nodo antes de degradar** lo fija **U12** desde la
  medición que U8 publica (PERF-U8.3).

## Lo que U8 no hace, y quién lo hace

- La ejecución de fondo y la precarga del nodo: **U12 `graph-runtime`**.
- La cita expandible en pantalla: **U13 `chat`**.
- El contenido del corpus: **U7 `synthetic-data`**.
- La medición contra el despliegue vivo: la pasada de publicación.
