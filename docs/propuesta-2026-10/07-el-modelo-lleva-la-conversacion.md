# El modelo lleva la conversación

Decisión de Miguel del 2026-10-12 (camino B de `06-correcciones-2026-10-12.md`). Este
documento dice qué cambia, qué no cambia y cómo se construye.

## En una frase

Hoy el código elige una frase y el modelo la reescribe sin ver la conversación. Desde
ahora **el modelo ve la conversación y el estado del caso, y responde él**; el código
sigue validando todo lo que el modelo propone y sigue siendo el único que cambia el caso.

## Qué cambia

| | Antes | Ahora |
| --- | --- | --- |
| Llamadas al modelo por turno | Dos: entender y reescribir | Una: entender y responder |
| Qué ve el modelo | El último mensaje y la lista de datos que faltan | La conversación, el estado del caso, lo que falta y el mensaje |
| Quién escribe la respuesta | Una frase del catálogo, reescrita | El modelo, en el mismo formulario cerrado donde anota |
| Cambiar de tema (de consulta a reporte) | No existía en el chat | El modelo lo dice en `wants` y el código abre el caso nuevo |
| Reglas sobre el texto del modelo | Una docena de comprobaciones que descartaban hasta un tercio de las respuestas | La guardia de salida, y dos comprobaciones de coherencia |

## Qué no cambia (lo sostiene el código)

- **La guardia de salida** revisa toda respuesta antes de que llegue a la persona: nada de
  cobertura, montos, culpa, consejo legal, promesas de contacto ni configuración.
- **Los datos se validan contra el esquema del caso** antes de guardarse, igual que hoy
  (`extraction.extract_fields`, `fields.validate_field`), y se tapan antes de persistir.
- **Las transiciones las decide el código.** El modelo propone con un valor de una lista
  cerrada (`wants`, `answer`); ninguna transición sale de texto libre.
- **Una cita solo sale de una cláusula recuperada y verificada.** La respuesta de
  cobertura la sigue componiendo el camino de fondo, no esta llamada.
- **La decisión la firma un ajustador**, y la categoría y la derivación al cerrar las
  deciden las reglas.
- **Los hitos los dice el código, con frases fijas:** la apertura con su divulgación, la
  derivación a un ajustador, el cierre de un reporte con su número, la lectura final de
  una cotización, los límites y los errores.
- **Lo de fuera entra como dato delimitado**, nunca en la instrucción.
- **Si el modelo falla, tarda o la guardia descarta su respuesta**, sale la frase del
  catálogo que el recorrido por reglas ya sabe componer. Ese recorrido no se borra: es
  el modo degradado.

## Cómo queda un turno

1. Controles baratos de entrada, como hoy (petición de ajustador, pregunta de identidad,
   emergencia). Siguen siendo patrones, sin modelo.
2. **Una llamada al modelo** con la instrucción `conversation` y, como datos delimitados:
   fecha, canal, idioma, nombre de la agente, aseguradora, si cotiza, tipo y estado del
   caso, si la póliza ya está identificada, si hay una respuesta en camino, datos
   anotados, datos que faltan en orden, las últimas doce intervenciones y el mensaje.
   Devuelve el formulario de siempre (`wants`, `items`, `answer`, `person_question`,
   `asks_about_coverage`) **más `reply`**.
3. El código aplica lo entendido por el camino que ya existe: valida y guarda los datos,
   resuelve la lectura, lanza la revisión de la póliza si la pidió, deriva si pidió un
   ajustador, cierra si el reporte quedó completo.
4. **Qué texto sale:**
   - si el turno es un hito (derivación, cierre, lectura de la cotización, error, límite):
     la frase fija, como hoy;
   - si el código rechazó alguno de los datos que el modelo anotó: la frase del catálogo,
     porque la respuesta del modelo se escribió contando con ellos;
   - en cualquier otro caso: `reply`, pasado por la guardia. Si la guardia lo sustituye,
     la frase del catálogo.
5. Lo que sale es lo que se guarda en la transcripción.

## Cambiar de tema

Si hay un caso y `wants` pide otra cosa de las tres que abren caso (`report_accident`,
`policy_question`, `quote`) y el tipo no coincide con el del caso, el código abre un caso
nuevo de ese tipo —si la aseguradora lo ofrece—, lo deja atado a la conversación y copia
la identidad y la póliza ya dadas, para que la persona no las repita. El caso anterior
queda como estaba. Preguntar por cobertura en mitad de un reporte no abre nada: sigue
siendo el reporte, como hoy.

Sin caso todavía (primer mensaje), la misma llamada decide: saludo o duda general se
contestan con `reply` sin abrir caso; lo demás abre el caso del tipo que corresponde.

## La llamada

El mismo turno. Lo que se dice es `reply`, si pasa la guardia. En una llamada hay una
regla más: lo que se sintetiza es siempre texto ya pasado por el redactor de datos
personales, y **si el redactor tapa algo en `reply`, sale la frase del catálogo**: la
agente nunca dice una etiqueta en voz alta, ni por un dato de verdad ni por una palabra
corriente que el detector confunda. Las respuestas de una o
dos palabras siguen por reglas, que es instantáneo. Después de este cambio, y medido con
la llamada simulada, se adelanta la llamada al modelo a cuando llega la frase, sin esperar
la tolerancia de fin de habla: si la persona sigue hablando, se descarta.

## Qué se retira

- La segunda llamada (`natural_reply.say_naturally`) y su instrucción `intake_reply`.
- Las comprobaciones sobre el texto reescrito (`acceptable` y las que se le fueron
  sumando). Se conservan las dos que cuidan a la persona y no dependen del modelo: sin
  enlaces ni correos, y sin el nombre de la agente si no lo preguntaron.
- La instrucción `intake_understanding`, que pasa a ser `conversation`.

## Cómo se comprueba

- Pruebas sin modelo: un modelo doble que devuelve el formulario; se comprueba qué texto
  sale en cada rama del punto 4, el cambio de tema y el modo degradado.
- Con modelo, una sola vez por tanda y diciendo el costo antes:
  - las 18 situaciones de comprensión (medio centavo): tienen que seguir en 18 de 18;
  - las 18 conversaciones reales con ataques y cotización (unos 5 centavos): siguen
    exigiendo que la guardia no deje pasar nada y que cada caso termine donde debe;
  - la conversación de Miguel del 2026-10-12 (consulta, pregunta, ajustador, «quiero
    reportar eso como un accidente»), repetida como conversación simulada.

## Costo

Una llamada por turno en vez de dos. La llamada lleva más contexto (la conversación), así
que cada una cuesta algo más: en total, parecido a hoy. La instrucción va en caché.

## Estado al cierre del 2026-10-12

Construido en el chat y en la llamada (`0c68cf6`, `f484824`, `28f2e65`), sin subir a GitHub.

**Comprobado contra el modelo** (2,2 centavos en total):

- Las 18 situaciones de comprensión: 18 de 18 en español y en inglés. La primera corrida
  dio 17 de 18 y mostró dos errores de la instrucción nueva, ya corregidos: en inglés pedía
  anotar los valores en español, y faltaba el ejemplo de «soy yo, pero manejaba mi hijo».
- La conversación de Miguel (consulta, pregunta, ajustador, «quiero reportar eso como un
  accidente»): abre el reporte, lleva el nombre y la póliza, y el reporte se cierra con su
  número. Mostró un error, ya corregido: en el turno que cambia de tema el modelo contestaba
  mirando el caso anterior («como el caso ya está con el ajustador…»). Ese turno dice ahora
  la frase del catálogo del caso nuevo, igual que el primer mensaje.

**Dónde habla el modelo y dónde no.** En esa conversación solo un turno de siete dijo lo que
escribió el modelo; los demás eran hitos (póliza encontrada, espera de la revisión,
derivación, cierre) y dicen su frase fija, como manda este diseño. El modelo se oye donde
el chat sonaba a contestadora: mientras se reciben los datos de un reporte contado por
partes o de una cotización, en el saludo y en las dudas generales.

**Lo que falta.**

- ~~**Que el caso nuevo recuerde la conversación anterior.**~~ **Hecho el 2026-10-13.** Cada
  caso guarda de cuál viene (`case_record.continues_case_id`, llave compuesta con la
  aseguradora, `ON DELETE SET NULL (continues_case_id)` para que el reinicio nocturno no
  quede impedido) y la conversación se lee a través de la cadena
  (`case_record.api.conversation_transcript`, con tope de diez saltos): la historia que ve el
  modelo y la que recupera la pantalla incluyen los casos anteriores, y las respuestas de
  cobertura conservan sus cláusulas porque no se copian turnos. La bandeja, «Ver mi caso» y
  «Casos» siguen leyendo cada caso por separado. Pendiente: que el caso nuevo diga en
  pantalla de cuál viene (ver el informe de la tanda), y que «tu caso» del tablero público
  siga marcando el caso anterior.
- Las 18 conversaciones reales (unos 5 centavos, con el visto bueno de Miguel). La línea
  base de evaluaciones guarda las huellas de las instrucciones retiradas y puede pedir una
  nueva; lo dirá GitHub Actions al subir.
- En la llamada: medir con una llamada simulada, y adelantar la llamada al modelo.


## Retomar por chat un caso que empezó por voz (2026-10-13)

US1.20. Escribir en el chat el número de un caso (de cualquier aseguradora cargada; un número de
póliza no cuenta) lo reconoce el código **antes de entregarle el mensaje al modelo o al grafo**, con
o sin caso en la conversación. Si el caso es de este navegador —por una conversación de chat o, si
`voice_to_chat_continuity` está encendido en la aseguradora, por una llamada— y sigue en captura, la
conversación se ata a ese mismo caso y la agente dice solo lo que falta; el turno y su respuesta se
guardan con canal `chat`. Cualquier otro número (inexistente, de otro navegador, de otra
aseguradora) recibe una sola respuesta que no dice el motivo. Con la continuidad apagada esa
respuesta explica que un caso se retoma por el canal donde empezó. La consola de voz solo ofrece el
chat cuando el servidor lo confirma (`CallOutcome.chat_continuation`).

Pendiente: el enlace firmado del caso como segunda puerta (AC1.20.1) necesita una ruta que lo canjee
desde el chat y un botón en la página del caso; no se hizo en esta tanda.
