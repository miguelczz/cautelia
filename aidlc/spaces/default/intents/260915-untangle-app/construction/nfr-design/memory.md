<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
- 2026-09-20T19:55:00Z — U3: las respuestas de la etapa anterior llegaron sin ambiguedad ni contradiccion, asi que esta etapa no abrio preguntas nuevas. La unica decision abierta de la unidad --si la redaccion entra en la lista de modulos criticos del piso de cobertura-- ya esta escalada a Miguel desde `nfr-requirements` y no se vuelve a preguntar.
2026-09-19T02:40:00Z — la revisión encontró que la taxonomía de errores del proveedor y el enum de causas de "no medido" son dos vocabularios distintos que nadie traducía; la traducción reveló que `invalid_response` no es un caso no medido sino un fallo de calidad, que es la misma línea que el proyecto traza entre "no hay cláusula" y "no pude verificar".
2026-09-19T02:15:00Z — "el escaneo de secretos es el primer trabajo" y "el flujo invoca el guion único" solo se cumplen a la vez si el primer trabajo invoca el guion acotado a ese paso; se aplicó sin preguntar por ser lectura de práctica afirmada.
2026-09-19T02:15:00Z — el subconjunto del arranque y el de la compuerta son dos listas distintas: la primera se elige por velocidad y la declara U1, la segunda por cobertura y la declara U21 (PA-11).
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->

## Deviations
- 2026-09-20T19:55:00Z — U3: el diseno declara explicitamente que el tipo `Redacted` NO garantiza nada por si solo y que el control es un chequeo de analisis estatico. C-13 presenta el tipo como el mecanismo; aqui se escribe la mitad que faltaba en vez de repetir la afirmacion del contrato.
2026-09-19T02:15:00Z — la etapa pide patrones de caché, escalado y circuito; U1 no atiende tráfico, así que esos documentos registran por qué no aplican en lugar de inventar un patrón. El único patrón de resiliencia real es el corte por cuota del corredor.
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs
- 2026-09-20T19:55:00Z — U3: un motor con los dos modelos residentes cuesta 71 MB de memoria permanente y los ahorra en cada llamada. Se prefiere a reconfigurar el motor por llamada porque reconfigurarlo reintroduce la posibilidad de que corra un solo juego de reconocedores, que es exactamente el agujero de RT-15.
- 2026-09-20T19:55:00Z — U3: si los modelos no cargan, el proceso no arranca. Es mas fuerte que lo que exige C-13, que solo pide fallar cerrado en la llamada. La razon: un aplicativo vivo con la redaccion muerta parece que funciona, y ese es el peor estado posible para un control cuyo fallo no se manifiesta.
2026-09-19T02:15:00Z — el guion corre todos los pasos menos el escaneo de secretos, que corta en el acto: se paga algo más de tiempo de corrida a cambio de que un cambio se arregle en una vuelta y no en cinco.
2026-09-19T02:15:00Z — un reintento para lo pasajero y cero para la cuota: la asimetría existe porque una cuota agotada no es un fallo pasajero y reintentarla gasta lo mismo que protege.
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
- 2026-09-20T19:55:00Z — U3: cuantos milisegundos cuesta de verdad la pasada de redaccion con los modelos `md` no se sabra hasta la primera corrida verde de la generacion de codigo. NFR11.3 fija 100 ms; si no se alcanza, se escribe por que y no se baja el umbral.
2026-09-19T02:40:00Z — distinguir una cuota agotada de una tasa momentánea necesita un dato más en la frontera del proveedor, que es de U5 `provider-platform`; U1 deja escrito qué hace mientras no exista y cuánto cuesta no tenerlo.
2026-09-19T02:15:00Z — las cuatro respuestas llegaron como opciones limpias, sin "depende" ni contradicción entre ellas; no hay preguntas de seguimiento que abrir.
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->

## Interpretations

- 2026-09-20T16:15:53Z — U2: la duplicacion de la politica de aislamiento en cada migracion es deliberada y se documenta como tal. Veintiuna unidades van a copiar un patron de tres lineas; la alternativa (una funcion compartida) ahorraria escritura pero haria que leer una migracion ya no dijera que aislamiento dejo, y que cambiar la funcion alterara en silencio tablas escritas meses antes. Decision Q1 de Miguel.
- 2026-09-20T16:15:53Z — U2: se distingue explicitamente "la asercion falla" de "la asercion no se puede ejecutar". El segundo caso —base caida al arrancar— no lo cubria ningun control, y la respuesta es no arrancar. Es la misma distincion que el proyecto exige entre "no hay clausula" y "no pude verificar", aplicada al arranque. Decision Q2 de Miguel.

## Tradeoffs

- 2026-09-20T16:15:53Z — U2: el diseno de seguridad cita explicitamente `correcciones-tras-revision.md` de la etapa anterior como autoritativo donde contradiga a los documentos congelados. Es feo tener dos archivos donde deberia haber uno, y se prefirio a la alternativa: arrastrar hacia la generacion de codigo tres comandos que no existen y un objetivo medible sin respaldo.

## Interpretations

- 2026-09-20T23:25:00Z — U4: la postura ante el fallo del cifrado es asimétrica a propósito. Al arrancar sin clave, cerrado: el proceso no arranca, porque un modo degradado que guarde en claro "mientras tanto" es exactamente cómo un dato personal acaba sin cifrar sin que nadie lo decida. Al leer una fila que no se descifra, visible: el caso se abre con el campo marcado. La razón de la diferencia es que al arrancar el fallo afecta a lo que todavía no ha pasado, y al leer el caso ya existe y alguien tiene que decidirlo.
- 2026-09-20T23:25:00Z — U4: se escribe en el propio documento contra qué **no** protege el cifrado (quien tenga el proceso y su variable de entorno tiene la clave). No es una nota de humildad: un control que se cree más fuerte de lo que es acaba sustituyendo a los que sí harían falta, y la tabla de tres filas lo deja donde se ve.

## Tradeoffs

- 2026-09-20T23:25:00Z — U4: siete piezas en vez de menos. Cuesta más archivos; a cambio seis de las siete se prueban sin levantar la base —`models.py` no importa nada del módulo, `rules.py` es puro y `crypto.py` no importa el repositorio—, que es lo que hace alcanzable el piso del 80 % probando lógica en vez de orquestando contenedores.
- 2026-09-20T23:25:00Z — U4: la columna del identificador de clave por fila cuesta un campo más en cada tabla con dato cifrado. A cambio, rotar deja de ser la elección entre no rotar nunca y reescribir el almacén de golpe.

## Open questions

- 2026-09-20T23:25:00Z — U4: el tipo sellado necesita su propio análisis estático, del mismo estilo que `redaction:constructor` de U3, para que nadie fabrique un valor cifrado fuera de `crypto.py`. La tarea se declara en `infrastructure-design` de esta unidad y se encadena dentro del paso 6 del guion; si no se declara allí, la capa 1 del diseño queda sin comprobación y vuelve a ser disciplina.
- 2026-09-20T23:32:00Z — U4, hallazgo R-01 de la revisión, comprobado y real: escribí "siete operaciones" y "siete unidades que consumen esta" cuando el contrato C-12 declara **seis** operaciones (`create_case`, `get_case`, `apply_transition`, `set_field`, `append_turn`, `record_change`) y **ocho** consumidoras (U8, U9, U10, U11, U12, U14, U19, U20). Contados por mí con un comando, no a ojo. Corregido en `logical-components.md` antes de registrar el recibo. El mismo "siete" aparece en el archivo de preguntas del diseño funcional, que no se toca porque es el registro de lo que se le preguntó a Miguel y el error no cambia la pregunta. Es la tercera vez en el proyecto que un recuento escrito a ojo sale mal: la regla sigue siendo contar con un comando y pegar la cifra, nunca escribirla de memoria.
- 2026-09-20T23:35:00Z — U4, mecánica aprendida a golpes: con `review_class: advisory` **no se puede arreglar nada entre el despacho del revisor y el registro del recibo**. El registrador rechaza el veredicto con "its output documents changed after review iteration 1 started", y `--retry-pending` no rebasa la línea base. El aviso de Change Control `relaxed` que aparece al **abrir** la solicitud tolera cambios anteriores, pero no los de dentro de la ventana. Consecuencia práctica: la única ventana para arreglar es **antes** de despachar, así que conviene apurar los propios comprobadores ahí. Intenté corregir el recuento, el registrador lo rechazó, revertí el byte exacto y registré; la corrección viaja a la compuerta con las de `functional-design`.

## Interpretations

- 2026-09-21T04:15:00Z — U5: la linea que reparte los mecanismos de resiliencia entre esta unidad y el ejecutor de nodos de U12 se pudo enunciar en una frase: **lo que depende del proveedor es del adaptador; lo que depende del nodo es del ejecutor**. De ahi sale que el cortacircuitos vive aqui (la salud de Gemini es una sola para los cuatro nodos) y el reintento alli (lo que tolera la captura no es lo que tolera el turno de voz). Sin esa frase, la practica afirmada --"la politica de fallo de cada nodo es un dato aplicada por un ejecutor comun"-- se podia leer como que aqui no va ningun mecanismo, y entonces un proveedor caido costaria cuatro tiempos maximos por turno.
- 2026-09-21T04:15:00Z — U5: `invalid_response` **no** cuenta para abrir el cortacircuitos, y los otros tres si. No es un detalle: una respuesta que no valida es un problema del contenido, no de la salud del proveedor, y contarla abriria el circuito por un prompt mal escrito, apagando un proveedor sano.

## Deviations

- 2026-09-21T04:15:00Z — U5: no se pudo registrar el `QUESTION_ANSWERED` de esta etapa. El motor exige un turno humano nuevo entre la decision registrada y su respuesta, y Miguel ya habia gastado el suyo en la etapa anterior. Las cuatro respuestas estan escritas en `nfr-design-questions.md` con su razon; la fila del registro se anade en cuanto llegue su siguiente mensaje. Queda anotado para no dar por hecho que la delegacion permanente sustituye al turno: el motor cuenta turnos, no permisos.

## Tradeoffs

- 2026-09-21T04:15:00Z — U5: la cola del registro diferido pasa a sincrona al llenarse en vez de descartar filas. Eso paga latencia en el chat justo en el peor momento --la base va lenta y ademas el chat espera--, y a cambio ninguna fila se pierde. Se eligio asi porque el costo por caso es una de las cinco cifras publicadas y una cifra a la que le faltan llamadas no es una medicion, es una estimacion con un asterisco.
- 2026-09-21T04:15:00Z — U5: el acumulado se incrementa sin leerlo antes, con una sola sentencia que devuelve el valor nuevo. Cuesta que la logica de "quien emite la alerta" quede dentro de una condicion sobre el valor devuelto en vez de en un `if` legible arriba; a cambio no existe la ventana entre leer y escribir, que es donde vive la carrera.

## Open questions

- 2026-09-21T04:15:00Z — U5: el ejecutor comun de politicas de fallo por nodo es de U12 y todavia no existe. Este diseno declara que espera de el --que aplique su politica sobre los cuatro tipos de error, incluido el `unavailable` que devuelve un circuito abierto-- y no lo disena. Confirmarlo al llegar a U12.
- 2026-09-21T04:15:00Z — U5: la version exacta de las convenciones `gen_ai.*` se ancla en la generacion de codigo. Estan en estado de desarrollo, asi que no anclarla dejaria que un cambio del estandar moviera los nombres de los atributos sin avisar, y esos nombres son la lista cerrada que impide que un tramo lleve texto.

- 2026-09-21T04:22:00Z — U5, hallazgo R-01 del revisor, comprobado y real: `SEC-U5.16` --el texto de origen externo nunca concatenado al prompt de sistema, que es lo que prueban RT-1, RT-2 y RT-5-- estaba en los requisitos de la etapa anterior y **no tenia ni una linea de diseno** en los ocho documentos de esta. `grep` sobre los ocho: cero resultados. Leccion mecanica, y es de las utiles: al escribir el diseno, recorrer la lista de controles de la etapa anterior **uno por uno** y marcar cual tiene mecanismo, en vez de diseñar por categorias y confiar en que ninguna se cayo entre dos.
- 2026-09-21T04:22:00Z — U5, hallazgo R-02: la asercion de columnas se presento como un crecimiento trivial de `rls:check`, y no lo es: `evaluate()` **salta** las tablas excluidas, que son justo las que hay que mirar, y la consulta no trae columnas. Leccion: al decir "este comando crece", abrir el archivo y comprobar que lo que se le pide esta al alcance de lo que hoy consulta.
- 2026-09-21T04:22:00Z — U5, mecanica del registro: pasar acentos graves dentro de un argumento de linea de comandos hace que el shell intente ejecutar lo que hay dentro. La fila `QUESTION_ANSWERED` de esta etapa perdio la palabra `invalid_response` por eso. El texto completo esta en `nfr-design-questions.md` y en `reliability-design.md`, que son los artefactos autoritativos. Para las unidades que faltan: en `--details` y `--decision`, nada de acentos graves.

- 2026-09-21T04:40:00Z — U5, error mio detectado en la etapa siguiente: `logical-components.md` de esta etapa dice que U5 "es la primera unidad del proyecto que ofrece **tres** contratos en vez de uno". **Es falso**: contando la columna de dueno de la tabla de contratos, U1 y U2 ofrecen cinco cada una y U5 empata en tercer puesto con U6 y U14. La frase de `infrastructure-specification.md` se escribio ya corregida; la de este documento queda pendiente de la compuerta de la unidad, porque la etapa esta cerrada y su artefacto es su registro permanente. Leccion: un superlativo ("la primera", "la unica", "la mas") es una cifra disfrazada y se cuenta antes de escribirlo, igual que las otras.
