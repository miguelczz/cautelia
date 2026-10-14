# Resumen del código — U12 `graph-runtime`

U12 es la unidad que **ejecuta** a las otras. Deja construido:

- **La transición en código, cerrada y pura.** Recibe solo campos del estado
  tipado y devuelve uno de cuatro nombres de nodo. Ningún texto —del asegurado o
  del modelo— puede elegir la ruta, y un contrato de importación impide que
  LangGraph, un canal o el SDK de un proveedor aparezcan en su cadena de
  llamadas.
- **El estado tipado que se compone al arrancar.** Los campos salen de los
  conjuntos de escritura de los cuatro nodos, y **el proceso no arranca** si dos
  declaran el mismo campo. Eso es cierto en producción, no solo en la prueba:
  la raíz de composición importa el módulo, y hay una prueba que lo vigila.
- **La pieza propia de puntos de control.** La del framework trae sus tablas, sin
  columna de aseguradora y con el estado en claro. Esta implementa la misma
  interfaz sobre tablas propias: la aseguradora viaja en cada llamada y **si no
  llega, falla cerrado**; el estado, los metadatos y cada escritura pendiente van
  cifrados por la misma puerta que usa U4.
- **La política de fallo como dato.** Tiempo máximo, intentos, texto de
  degradación y quién cuenta los reintentos salen del `NodeSpec`. El módulo del
  ejecutor **no sabe qué nodos existen** —no importa ninguno de los cuatro—, y esa
  ausencia es lo que hace la regla comprobable. En el ritmo del turno el plazo es
  de la ejecución completa, no de cada intento: quien espera es la persona.
- **Los dos ritmos.** El turno responde y lanza el fondo sin esperarlo; dentro del
  turno corren solo los tres controles baratos, y el arrendamiento con latido más
  el barrido al arrancar retoman lo que un proceso muerto dejó a medias.
- **La pausa hacia la bandeja y la reanudación.** Una sola pausa viva por caso, y
  la impone el índice de la base, no una comprobación en Python. Retirar deja
  `withdrawn`, nunca `resolved`. La sesión abandonada abre la pausa con su motivo
  y **no toca el caso**: no se cierra ni se categoriza porque alguien se fue.
- **El punto único de salida y la interfaz del turno.** `handle_turn`,
  `resume_case` y `preload` con la forma de C-14; el flujo termina siempre en
  `FinalText`, `Handoff` o `TurnError`, y todos pasan por la guardia —también el
  camino de error.
- **La sonda genérica de conversación**, que recorre el guion de un caso del
  golden set por los nodos reales. Es la pieza con la que se escriben los once
  casos que le faltan a DS-2; esta unidad aporta dos (34 → 38).

Se construyó en siete tandas, escritas por el agente desarrollador con Sonnet y
revisadas aquí.

Los contratos que realiza son C-14 (la interfaz del turno), C-15 (lo que declara
un nodo) y C-12, C-20, C-23, C-25 y C-26 hacia las unidades que consume, tal como
los fija `contract-summary.md`; su alcance y su tipo `service` salen de
`unit-of-work.md`. Las etapas `nfr-design` e `infrastructure-design` no corren en
este proyecto desde el 2026-09-21 (modo ligero), así que lo que ellas fijarían se
decidió en el plan de esta unidad y en sus requisitos de calidad.

## Resultados

| Compuerta | Resultado |
| --- | --- |
| `mise run test:u12` | 126 pruebas en verde, 45 de ellas de integración con base real |
| `mise run cov` | 88 % agregado; los cinco módulos críticos entre 89,44 % y 98,89 % |
| `scripts/verify.sh` | 9 de 9 en verde |
| Compuerta dura BR3.4 | En verde, cerrada por sus dos mitades (estado y texto) |

## La compuerta dura, y cómo se cerró

BR3.4 es la única `[bloquea]` de la unidad: dos navegadores con la misma póliza
de ejemplo, y al segundo no se le ofrece ni se le revela el caso del primero.

Está cerrada **por construcción y no por comprobación**: ni `resume_state` ni el
punto de control tienen un parámetro de póliza. No es que se abstengan de filtrar
por póliza; es que no tienen el dato con el que podrían. Con las tres pólizas de
ejemplo siendo públicas a propósito (F8.7), esa ausencia en la firma es lo que
hace la regla imposible de romper por descuido.

Se verifica por sus dos mitades, y las dos se vieron caer:

- **En estado**: el `ResumeState` del segundo navegador es idéntico campo por
  campo al de una sesión sin relación. Cae si la búsqueda mira la póliza, y cae
  también si la búsqueda de la pausa devuelve la de cualquier caso de la
  aseguradora.
- **En texto**: la respuesta que el segundo navegador recibe de `handle_turn` es
  idéntica —tipo de evento y texto— a la de un caso sin ninguna relación. La
  primera versión de esta prueba solo comprobaba que no se filtrara la cita, y eso
  no es lo que la regla pide: **la filtración no es el dato, es la distinción**.
  Recibir algo distinto de lo que recibe un desconocido ya dice que por esa póliza
  hay un caso abierto, aunque la frase sea inofensiva. Cae si la frase de espera
  lleva cualquier rastro del caso.

## Lo que esta unidad decidió, con su razón

- **La pieza de puntos de control se escribe, no se envuelve** (FD-U12-3). La
  oficial guarda el estado en claro y sin columna de aseguradora; envolverla
  dejaba el aislamiento y el cifrado apoyados en la forma interna de tablas
  ajenas que una actualización puede cambiar sin avisar.
- **`retries_owned_by` entra a C-15** (FD-U12-2). `policy_verification` cuenta sus
  propios reintentos porque tras agotarlos todavía tiene que escribir su valor
  `unverifiable`, que nadie más sabe escribir. Sin este dato el ejecutor haría
  cuatro llamadas al proveedor en vez de dos, y la alternativa era un `if` por
  nombre de nodo, que la convención 9 del equipo prohíbe.
- **El plazo del ritmo del turno es de la ejecución completa.** El razonamiento
  que fijó los 1.600 ms lo hizo como el doble de la meta p95 y no contempló el
  reintento: con el plazo por intento, un proveedor lento daba 3.200 ms en el
  camino del turno. No se cambió ningún número aprobado; se precisó qué significa
  "antes de degradar".
- **La frase de espera tiene una clave por canal.** Su criterio (AC1.25.3) se mide
  en la voz, pero el camino del turno sirve también al chat, así que el texto
  aprobado vive bajo dos claves con su superficie correcta en vez de emitirse por
  una que no le corresponde.

## Fronteras declaradas, no silenciadas

- **Los tres nodos de fondo entran como dobles deterministas** en las pruebas del
  turno; `intake` es la clase real de U11. Cablear `policy_verification`,
  `decision` y `compliance` de verdad es integración de proveedor y de datos de
  aseguradora, que por UG-8 se verifica en las comprobaciones de punta a punta de
  Build and Test y no agrega dependencia a esta unidad.
- **La transcripción durable queda fuera.** La tabla de fronteras solo le pide a
  esta unidad crear el caso y aplicarle las transiciones. En consecuencia, el
  conteo de insultos vive en memoria del proceso y **se reinicia con él**: un
  visitante que reconecta vuelve a empezar la cuenta. No es un defecto de este
  paso, es una frontera, y queda anotada con dueño en `docs/PENDIENTES-MIGUEL.md`.
- **La carrera al numerar el paso de un punto de control** no usa bloqueo
  explícito: dos escrituras concurrentes al mismo hilo chocan contra la
  restricción única en vez de fallar en silencio. El diseño de la unidad es un
  turno activo por caso a la vez; queda anotado por si deja de serlo.

## Enmienda del 2026-09-28: el runtime, enchufado

La frontera que esta unidad declaró —"cablear `policy_verification`, `decision` y
`compliance` de verdad... se verifica en las comprobaciones de punta a punta de Build
and Test"— era correcta, pero **nadie llamaba a `install_runtime` en producción**, así
que el chat no podía atender ni un turno con caso. Se descubrió arreglando el defecto
que lo tapaba, que es lo que pasa cuando un fallo no se ve: esconde al siguiente.

- La **raíz de composición** construye e instala el runtime del **ritmo del turno**:
  el nodo `intake` real de U11 con su extractor y su prompt versionado, el ejecutor con
  su almacén en base, los puntos de control cifrados y el almacén de pausas.
- `GraphRuntime.background_graph` pasó a admitir `None`, **sin valor por omisión**. Es
  la forma de decir en el tipo que un despliegue puede tener un ritmo cableado y el
  otro no. Sin él, `preload` devuelve `False` y emite su evento, y el desvío de
  cobertura responde con la frase de degradación del catálogo en vez de una de espera
  que no cierra el turno. `resume_case` tampoco levanta, y por una razón concreta: la
  pausa que retira es un `interrupt()` de LangGraph y **solo el grafo de fondo lo
  abre**, así que sin él ningún caso puede estar pausado así; levantar haría devolver
  un `500` a una decisión de la bandeja ya registrada y válida. Lo que no vale es no
  hacer nada en silencio, y de eso se encarga su evento.
- `launch_background` **recoge la excepción** de la tarea que lanza y deja su evento.
  Antes moría sin rastro, que contradice la regla propia del proyecto: todo fallo deja
  un valor distinguible en el caso y un evento en la traza.
- Medido contra el proveedor de verdad, el plazo de 1.600 ms del nodo de captura
  —el doble de la meta p95 **de la voz**— queda corto para el chat: la llamada real
  tarda entre 2.892 y 5.300 ms, así que toda captura se degrada. Es una decisión de
  umbral y está en `PENDIENTES-MIGUEL.md` (1.7), no tocada.

## Lo que la revisión encontró, tanda por tanda

Cada tanda pasó todas las compuertas automáticas y trajo un defecto que solo vio
la revisión. **Cinco de los seis estaban en la prueba, no en el código**: escrita
a la medida de lo que el código hacía en vez del criterio que debía comprobar.

| Tanda | Lo que traía |
| --- | --- |
| 2 | La sentencia de las escrituras pendientes se elegía mirando el lote entero: un nodo que interrumpía después de haber escrito algo perdía en silencio el motivo nuevo de la pausa al reintentarse. Ninguna prueba recorría esa rama |
| 2 | La prueba de aislamiento se apoyaba en una consulta directa desde la otra aseguradora, que es la política de fila que la tanda 1 ya probaba, no la pieza |
| 4 | La prueba que vigila "ninguna rama por nombre de nodo" solo miraba los operandos de primer nivel: un nombre dentro de un conjunto pasaba entera |
| 4 | La prueba de la clave de degradación afirmaba contra el mismo literal que la fábrica de pruebas pone por omisión, así que un valor en duro pasaba igual |
| 4 | La línea que hace que el proceso no arranque con dos nodos en choque se podía borrar sin que nada fallara |
| 5 | El contrato de importación del ritmo del turno permitía los saltos: un módulo puente de una línea llegaba a la verificación de póliza con todo en verde |
| 6 | La prueba de la compuerta dura decía cerrar "texto y estado" y solo cerraba el estado |
| 7 | La mitad en texto de la compuerta comprobaba que no se filtrara la cita, no que la respuesta fuera idéntica |

Cada arreglo se verificó rompiendo la conducta y viendo caer exactamente la
prueba que la vigila, y ninguna otra.
