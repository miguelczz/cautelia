# Reglas — U16 `voice-call`

38 reglas, repartidas en ocho familias: la conexión, la apertura, el turno
hablado, la interrupción, los silencios, la retoma, la privacidad y las trazas.

Tres llevan `[bloquea]`. Una es de divulgación —nada se pregunta antes de decir
qué es esto—, otra es de aislamiento —la póliza de ejemplo no abre el caso de
otro visitante— y la tercera es de retención: el audio no se guarda en ningún
punto del camino.

```yaml
rules:
  # --- La conexión (US1.21) ---------------------------------------------------
  - id: BR1.1
    statement: La consola pregunta por la disponibilidad antes de ofrecer el botón de llamar.
    category: policy
    applies_to: "La pantalla de llamada, antes de cualquier acción"
    trigger: "Al abrir la consola y al volver a ella."
    logic: >
      Ofrecer un botón que va a fallar es peor que no ofrecerlo. La respuesta de
      disponibilidad trae si hay voz, con qué motivo no la hay, con qué modo se
      hablaría y los límites; con eso la consola dibuja el estado real. U17
      llenará esos límites con los carriles públicos; hoy salen de la
      configuración de la aseguradora.
    violation: "La prueba de AC1.21.1 falla."
    source: AC1.21.1, C-08, FR3.1

  - id: BR1.2
    statement: El micrófono se pide antes de abrir la sesión, y un permiso negado no crea caso.
    category: constraint
    applies_to: "El arranque de una llamada"
    trigger: "Al pulsar llamar."
    logic: >
      El orden es la regla, no un detalle: si la sesión se abriera primero, un
      permiso negado dejaría un caso vacío en la bandeja de una ajustadora. Con
      este orden, negar el micrófono no produce nada en el servidor y la consola
      explica cómo darlo y ofrece el chat, con texto del catálogo.
    violation: "La prueba de AC1.21.2 falla: queda una fila de caso."
    source: AC1.21.2, FR3.1

  - id: BR1.3
    statement: El transporte es un WebSocket del mismo origen con PCM de 16 bits, mono, a 24 kHz.
    category: constraint
    applies_to: "El audio entre el navegador y el servidor"
    trigger: "Toda la llamada."
    logic: >
      Cierra C-29 (decisión D1). Es el mismo `SPEECH_AUDIO` que ya cruza los
      puertos de voz, así que el audio no se convierte dos veces y la única
      conversión de formato vive en la frontera del transporte, que es donde
      `ports.py` dice que vive.
    violation: "La prueba de contrato del transporte falla al recibir otro formato."
    source: C-29, D1, `SPEECH_AUDIO` de `providers/ports.py`

  - id: BR1.4
    statement: El token del socket viaja en el primer cuadro de texto, nunca en la URL.
    category: constraint
    applies_to: "La apertura del WebSocket"
    trigger: "Al conectar."
    logic: >
      Un token en la cadena de consulta acaba en los registros del servidor y en
      el historial del navegador. El socket se abre sin credencial, el primer
      cuadro es el `auth`, y el servidor cierra la conexión si no llega válido
      dentro del plazo. El token ata el socket a esa llamada; a quién pertenece
      ya lo dice la galleta del visitante en el apretón de manos.
    violation: "La prueba planta un token en la URL y la conexión se rechaza."
    source: D3, C-08, C-29

  - id: BR1.5
    statement: Un socket sin llamada viva, con token vencido o de otra llamada, se cierra sin decir cuál de las tres cosas fue.
    category: constraint
    applies_to: "La validación del cuadro de autenticación"
    trigger: "Al recibir el primer cuadro."
    logic: >
      Distinguir los tres motivos en la respuesta le diría a quien prueba tokens
      cuál acertó a medias. La consola muestra un solo texto y el motivo exacto
      queda en la traza del servidor.
    violation: "La prueba de los tres casos ve respuestas distinguibles."
    source: AC1.21.1, C-08

  - id: BR1.6
    statement: Toda llamada termina con un motivo del conjunto cerrado, y el caso queda en el estado que corresponde a lo capturado.
    category: policy
    applies_to: "El final de una llamada, por cualquier camino"
    trigger: "Al colgar, al agotar la duración, al tercer silencio, al cortarse o al fallar."
    logic: >
      Seis motivos y ninguno más: `hangup`, `silence`, `max_duration`,
      `dropped`, `error` y `completed`. Eran cinco hasta que el cierre por voz
      encontró el que faltaba, y esa es la razón por la que un conjunto cerrado
      se revisa cuando se usa. Una llamada que termina sin motivo es una llamada
      que la consola no puede explicar y una fila de la bandeja que nadie sabe
      leer.
      El estado del caso no lo inventa la voz: lo decide lo capturado, igual que
      en el chat.
    violation: "La prueba de AC1.21.3 falla, o el conjunto cerrado deja de cubrirse."
    source: AC1.21.3, FR3.1

  # --- La apertura (US1.22) ---------------------------------------------------
  - id: BR2.1
    statement: "[bloquea] Ninguna pregunta se hace antes de que la divulgación esté emitida y registrada."
    category: validation
    applies_to: "Todo turno de una llamada"
    trigger: "Antes de entregar cualquier turno al grafo."
    logic: >
      Es la misma compuerta que ya cumple el chat (BR1.1 de U13), por la misma
      razón: es la condición para que lo que entre después se pueda tratar como
      dato de demostración y no como una captura silenciosa. En voz pesa más,
      porque hablar es más fácil que escribir y la persona no ve una pantalla
      que se lo recuerde.
    violation: "La prueba entrega un turno con la apertura a medias y no falla."
    source: AC1.22.1, FR7.1, FR14.4, M6

  - id: BR2.2
    statement: La apertura se compone de claves del catálogo y ofrece cotizar solo si la aseguradora lo tiene activo.
    category: policy
    applies_to: "El primer mensaje de una llamada"
    trigger: "Al conectar."
    logic: >
      Tres claves compuestas, no un texto con un `if` dentro: una rama por
      aseguradora en el texto es lo que prohíbe la convención 9. Las claves de
      voz son propias y no las del chat, porque la apertura hablada dice además
      que la llamada queda transcrita y termina preguntando si hay heridos.
    violation: "La prueba de AC1.22.2 falla en una de las dos aseguradoras sembradas."
    source: AC1.22.1, AC1.22.2, FR3.2, BR1.3 de U13

  - id: BR2.3
    statement: La divulgación se registra con la hora en que terminó de emitirse, su idioma y el canal voz.
    category: policy
    applies_to: "El registro de divulgación de U10"
    trigger: "Al terminar de sonar la apertura."
    logic: >
      La hora es la del final y no la del principio porque AC1.24.4 necesita
      saber si alcanzó a completarse: una apertura interrumpida a la mitad no
      tiene hora de fin, y por eso se repite. El registro es de U10 y esta unidad
      lo llama, no lo reescribe.
    violation: "La prueba de AC1.24.4 no puede distinguir una apertura completa de una cortada."
    source: AC1.22.1, AC1.24.4, FR7.1

  - id: BR2.4
    statement: La apertura se emite una sola vez por caso aunque la llamada se retome.
    category: policy
    applies_to: "Una llamada que continúa un caso abierto"
    trigger: "Al retomar."
    logic: >
      Se dice entera otra vez —la persona la tiene que oír en cada llamada— pero
      el registro no se duplica: U10 ya devuelve si esta fue la que quedó, y una
      segunda no es un error.
    violation: "La prueba de AC1.27.2 ve dos registros de divulgación para un caso."
    source: AC1.27.2, AC1.27.5

  # --- El turno hablado (US1.23) ----------------------------------------------
  - id: BR3.1
    statement: El fin del habla es un transcrito final seguido de `end_of_speech_ms` sin nada nuevo, y su marca de tiempo es la del último final.
    category: calculation
    applies_to: "La detección de turno"
    trigger: "Con cada transcrito recibido."
    logic: >
      Es la definición de PA-6, que `unit-of-work.md` asigna a esta unidad
      (decisión D4). La marca es la del último final y no la del vencimiento del
      temporizador porque el tiempo de esperar el silencio es del detector y no
      de la respuesta: cargárselo a NFR1 mediría otra cosa. El valor vive en la
      configuración de la aseguradora y parte en 700 ms.
    violation: "La prueba con un guion de tiempos ve la marca en el vencimiento."
    source: AC1.23.5, PA-6, NFR1

  - id: BR3.2
    statement: El turno se arma con `channel="voice"` y se entrega por el mismo contrato C-14 que usa el chat.
    category: constraint
    applies_to: "La llamada al grafo"
    trigger: "Al cerrarse el turno de la persona."
    logic: >
      El canal no tiene conversación propia. Que los dos canales pasen por
      `handle_turn` es lo que hace cierto AC1.23.1 —el mismo guion deja los
      mismos campos— y lo que impide que la voz acabe con su propia lógica de
      captura, que es como se desincronizan dos canales.
    violation: "La prueba de AC1.23.1 ve campos distintos entre chat y voz con el mismo guion."
    source: AC1.23.1, C-14, FR1.1

  - id: BR3.3
    statement: El módulo de voz no importa nada del framework del grafo ni SDK de proveedor.
    category: constraint
    applies_to: "Los imports de `untangle.voice`"
    trigger: "En cada corrida del lint."
    logic: >
      Consume `orchestration.contracts` (los tipos de C-14) y
      `providers.ports` (los puertos de C-16), y nada más de esos dos mundos.
      Se comprueba con un contrato de `import-linter`, no con disciplina: es la
      regla 5 del equipo y la razón por la que cambiar de framework de grafo no
      toca ningún canal.
    violation: "El contrato de importación se pone rojo."
    source: ADR-003, ADR-018, convención 5 de `team.md`

  - id: BR3.4
    statement: Una transcripción vacía o bajo el umbral de confianza no anota nada y pide que se repita; a la tercera ofrece guardar el caso o pasarlo a un ajustador.
    category: policy
    applies_to: "El turno de la persona"
    trigger: "Al cerrarse un turno."
    logic: >
      La escalera tiene tres peldaños y un turno bueno la reinicia. La oferta de
      la tercera vez no incluye devolver la llamada: la devolución es `C3`, no
      existe, y P7 prohíbe ofrecer lo que no está construido (decisión D8 de
      User Stories).
    violation: "La prueba con el reconocedor simulado ve un campo anotado, o la oferta de devolver la llamada."
    source: AC1.23.3, FR2.6, P7

  - id: BR3.5
    statement: Un carácter confundible o una palabra bajo el umbral se lee con la tabla de deletreo y se espera confirmación antes de anotar.
    category: policy
    applies_to: "Los datos que se dictan carácter a carácter"
    trigger: "Al anotar placa o número de póliza por voz."
    logic: >
      La tabla es `spell_for_readback` de U11, versionada y con sus pruebas desde
      entonces. Esta unidad es su **primer consumidor de producción**: existía
      construida y documentada sin que nadie la llamara, que es la forma de
      defecto que más ha costado en este proyecto. Anotar sin confirmar sería
      guardar una placa que nadie dijo.
    violation: "La prueba de AC1.23.2 ve la placa anotada sin lectura ni confirmación."
    source: AC1.23.2, FR1.3, la tabla de deletreo de U11

  - id: BR3.6
    statement: Cada evento del grafo tiene su forma hablada, y la frase de espera se sintetiza de inmediato.
    category: policy
    applies_to: "Los cinco eventos de C-14"
    trigger: "Al recibirlos del grafo."
    logic: >
      `Waiting` lleva el texto ya resuelto —a diferencia del flujo del chat, que
      manda solo la clave— precisamente para que la voz lo diga sin otra ida y
      vuelta. `PartialText` se sintetiza en orden para que la voz empiece antes
      de que la respuesta esté cerrada; `FinalText`, `Handoff` y `TurnError`
      cierran el turno hablado. Los cinco, o el comprobador de tipos se queja.
    violation: "Un sexto evento entra sin que su rama hablada exista."
    source: C-14, AC1.25.3, BR2.4 de U12

  - id: BR3.7
    statement: El cierre dice el número de caso con el nombre de la aseguradora y los seis dígitos uno a uno, con "zero" y nunca "oh".
    category: policy
    applies_to: "El cierre de un reporte completo por voz"
    trigger: "Al cerrar el caso."
    logic: >
      Un número dictado de corrido no se anota bien al otro lado del teléfono, y
      "oh" por cero es la confusión clásica. Es la decisión D2 de User Stories.
      La transcripción guarda los dígitos separados porque es lo que la
      evaluación del hito compara.
    violation: "La prueba de AC1.23.4 ve el número de corrido, o un 'oh'."
    source: AC1.23.4, FR1.5, D2

  - id: BR3.8
    statement: Ningún texto se sintetiza sin haber pasado por el punto único de salida.
    category: validation
    applies_to: "Todo lo que la agente dice"
    trigger: "Antes de cada llamada a la síntesis."
    logic: >
      El puerto `TextToSpeech` recibe `Redacted` y no `str`, así que la regla ya
      es de tipos y no de disciplina: un puerto que aceptara texto crudo sería un
      punto de salida sin redacción. Vale también para los caminos de
      degradación y de error, que es donde se suele olvidar.
    violation: "El comprobador de tipos falla, que es el punto."
    source: M6, F7.5, C-16, regla de `project.md`

  # --- La interrupción (US1.24) -----------------------------------------------
  - id: BR4.1
    statement: Una interrupción exige al menos `barge_in_min_words` palabras o una palabra sobre el umbral de confianza.
    category: calculation
    applies_to: "El habla de la persona mientras la agente habla"
    trigger: "Con cada transcrito recibido durante la síntesis."
    logic: >
      Un parcial cualquiera no puede callar a la agente: el ruido de un carro se
      transcribe a veces como una sílaba suelta. El piso parte en dos palabras y
      vive en la configuración. Es la segunda capa de la defensa; la primera es
      la cancelación del navegador (BR4.2).
    violation: "La prueba de AC1.24.3 ve la síntesis detenida por ruido."
    source: AC1.24.3, D6, NFR2

  - id: BR4.2
    statement: El micrófono se pide con cancelación de eco, supresión de ruido y control de ganancia activados.
    category: constraint
    applies_to: "La captura en el navegador"
    trigger: "Al pedir el micrófono."
    logic: >
      Es lo que impide que la propia voz de la agente, saliendo por el altavoz de
      un portátil sin audífonos, entre otra vez por el micrófono y se lea como
      interrupción. No se construye un detector acústico propio: la cancelación
      del navegador es la misma que usan las videollamadas.
    violation: "La prueba de la consola ve las restricciones del micrófono sin esas tres."
    source: AC1.24.3, D6

  - id: BR4.3
    statement: Al detectar interrupción el servidor deja de sintetizar y manda `stop_audio`; el navegador vacía su cola al recibirlo.
    category: policy
    applies_to: "La parada por interrupción"
    trigger: "Al confirmarse una interrupción."
    logic: >
      El servidor no puede retirar el audio que ya mandó: en ese momento el
      navegador tiene cientos de milisegundos encolados. Sin el cuadro, la agente
      seguiría oyéndose medio segundo después de callarse, y NFR2 mide
      exactamente eso, en el cliente.
    violation: "La prueba del cliente mide la parada por encima de 300 ms."
    source: AC1.24.1, NFR2, D5

  - id: BR4.4
    statement: Tras una corrección, la agente confirma solo el dato corregido y sigue; no vuelve a leer el bloque entero.
    category: policy
    applies_to: "La retoma después de una interrupción"
    trigger: "Al continuar el turno."
    logic: >
      Volver a leer todo es lo que hace que interrumpir no sirva de nada: la
      persona corrige un dato y tiene que oír otra vez los cuatro que ya estaban
      bien. Lo que sostiene la regla es el estado del caso, que ya sabe qué
      quedó confirmado.
    violation: "La prueba de AC1.24.2 oye el bloque completo otra vez."
    source: AC1.24.2, NFR3

  - id: BR4.5
    statement: Una apertura interrumpida antes de terminar se repite entera antes de la primera pregunta.
    category: validation
    applies_to: "La apertura"
    trigger: "Al ceder el turno durante la apertura."
    logic: >
      Media divulgación no es divulgación: si no llegó a decir que la llamada
      queda transcrita, no está dicho. Se sabe porque la hora de fin de emisión
      no se registró (BR2.3).
    violation: "La prueba de AC1.24.4 pasa a la pregunta con la apertura a medias."
    source: AC1.24.4, BR2.1

  # --- Los silencios (US1.26) -------------------------------------------------
  - id: BR5.1
    statement: El reloj de silencio cuenta desde que la agente termina de hablar y se detiene mientras habla.
    category: calculation
    applies_to: "La detección de silencio"
    trigger: "Toda la llamada."
    logic: >
      Si el reloj corriera mientras la agente habla, su propia respuesta contaría
      como silencio de la persona y la llamada se cerraría sola. La tolerancia es
      dato de la aseguradora y parte en cinco segundos.
    violation: "La prueba de AC1.26.1 dispara el primer silencio durante la respuesta."
    source: AC1.26.1, FR3.5

  - id: BR5.2
    statement: Los tres silencios dicen sus frases en orden, y el tercero termina la llamada dejando el caso esperando al asegurado.
    category: policy
    applies_to: "La escalera de silencios"
    trigger: "Al vencer cada tolerancia."
    logic: >
      El orden es parte del criterio y de la medición del hito: el 100 % de los
      casos de silencio de DS-5 tiene que recibir las tres en secuencia. El
      tercero no cuelga en seco: se despide.
    violation: "La prueba de AC1.26.2 y AC1.26.3 ve otro orden o un corte sin despedida."
    source: AC1.26.1, AC1.26.2, AC1.26.3, AC1.26.4

  - id: BR5.3
    statement: Ninguna frase de silencio ofrece devolver la llamada.
    category: constraint
    applies_to: "Las frases de la escalera de silencios"
    trigger: "Al emitirlas."
    logic: >
      La devolución de llamada es `C3` y no existe. La oferta correcta es guardar
      el caso para seguir después o pasarlo a un ajustador, que es la decisión D8
      de User Stories. Se comprueba sobre el catálogo, no sobre el código.
    violation: "El chequeo de contenido encuentra la promesa en una clave de voz."
    source: AC1.26.2, D8, P7

  # --- El corte y la retoma (US1.27) ------------------------------------------
  - id: BR6.1
    statement: Un socket que se cierra sin colgar deja el caso esperando al asegurado, con lo confirmado y con `resume_until`.
    category: policy
    applies_to: "El cierre inesperado de la conexión"
    trigger: "Al cerrarse el socket sin cuadro de colgar."
    logic: >
      Un corte no es un final: es una pausa. El caso guarda lo que ya estaba
      confirmado y aparece así en la bandeja, que es lo que permite retomarlo y
      lo que impide que una ajustadora lo lea como abandonado.
    violation: "La prueba de AC1.27.1 ve el caso en otro estado."
    source: AC1.27.1, FR3.6, FR8.6

  - id: BR6.2
    statement: Al retomar, la agente dice primero la apertura completa y después ofrece continuar.
    category: policy
    applies_to: "Una llamada que encuentra caso abierto"
    trigger: "Al conectar con caso encontrado."
    logic: >
      La divulgación va primero siempre (BR2.1): saltarla porque "ya la oyó la
      vez pasada" es exactamente el atajo que la compuerta existe para impedir.
      Después viene la oferta, y solo después la conversación.
    violation: "La prueba de AC1.27.2 oye la oferta antes que la apertura."
    source: AC1.27.2, AC1.27.5, BR2.1

  - id: BR6.3
    statement: "[bloquea] El caso abierto se busca solo por el resumen de la clave del visitante, nunca por el número de póliza."
    category: validation
    applies_to: "La búsqueda de caso al retomar"
    trigger: "Al conectar una llamada."
    logic: >
      La póliza de ejemplo la comparten todos los visitantes de esa aseguradora.
      Buscar por ella significaría que decir en voz alta un número público abre
      el caso de otra persona: nombre, dirección, lo que contó del accidente. Es
      la misma clave que usa `chat.session.find_live` y por la misma razón.
    violation: "La prueba de AC1.27.3 ve el caso de otro navegador ofrecido o mencionado."
    source: AC1.27.3, FR8.6, M9

  - id: BR6.4
    statement: Decir que se llama por otro accidente abre un caso nuevo y deja el anterior intacto.
    category: policy
    applies_to: "La oferta de continuar"
    trigger: "Al responder que no a la oferta."
    logic: >
      Una persona puede tener dos accidentes. El caso anterior no se cierra ni se
      toca: sigue esperando al asegurado y sigue en la bandeja.
    violation: "La prueba de AC1.27.4 ve el caso anterior modificado."
    source: AC1.27.4

  - id: BR6.5
    statement: Un caso ya decidido se resume —decisión y comentario— antes de preguntar si hace falta algo más.
    category: policy
    applies_to: "Una retoma sobre un caso decidido"
    trigger: "Al conectar con caso decidido."
    logic: >
      La persona llama para saber qué pasó. Preguntarle en qué se le puede
      ayudar antes de contárselo es la forma más segura de que lo pregunte ella.
      El texto sale de las claves de decisión del catálogo, no se compone aquí.
    violation: "La prueba de AC1.27.5 oye la pregunta antes del resumen."
    source: AC1.27.5, D1 de User Stories

  # --- La privacidad (NFR19, M6) ----------------------------------------------
  - id: BR7.1
    statement: "[bloquea] El audio no se persiste en ningún punto: ni el que entra, ni el que sale, ni en memoria más allá del trozo que se está procesando."
    category: constraint
    applies_to: "Todo el camino del audio"
    trigger: "Toda la llamada."
    logic: >
      Es NFR19 y es lo que hace defendible una demostración pública con voz: lo
      que queda del paso de una persona es su transcripción redactada, que además
      se borra cada noche. Un búfer que crece "para depurar" es exactamente lo
      que esta regla prohíbe.
    violation: "La prueba recorre el módulo buscando escritura de audio a disco o acumulación sin techo."
    source: NFR19, M10, FR7.3

  - id: BR7.2
    statement: La transcripción que llega a la consola va redactada, parciales incluidos.
    category: validation
    applies_to: "Los cuadros de transcripción del socket"
    trigger: "Al emitir cada trozo."
    logic: >
      El punto de salida es el mismo del resto del aplicativo. Los parciales
      cuentan: un número de teléfono redactado en el final pero visible durante
      medio segundo en un parcial ya salió a la pantalla, y en una demostración
      que se graba, a la grabación.
    violation: "La prueba manda un parcial con un teléfono y lo ve entero en el socket."
    source: M6, F7.3, RT-14, NFR19

  - id: BR7.3
    statement: La llamada implementa el contrato de borrado de U2 con su prueba.
    category: constraint
    applies_to: "Los datos de visitante que guarda esta unidad"
    trigger: "En el borrado nocturno."
    logic: >
      La unidad guarda datos de visitante —la sesión de llamada y su
      transcripción—, así que le aplica UG-3: quien guarda, borra, y lo prueba.
    violation: "La prueba del borrado deja filas de llamada."
    source: UG-3, NFR19, M10

  # --- Las trazas y la latencia (FR10.2) --------------------------------------
  - id: BR8.1
    statement: Cada turno emite el evento de fin del habla y el de primer audio, con sus marcas.
    category: policy
    applies_to: "La traza del turno de voz"
    trigger: "En cada turno hablado."
    logic: >
      Son los dos extremos de NFR1 y el reporte del hito los nombra por su
      nombre. Sin ellos la meta de latencia no se puede medir, y una meta que no
      se mide no existe.
    violation: "La prueba de un turno no encuentra los dos eventos en la traza."
    source: FR10.2, NFR1, AC1.23.5

  - id: BR8.2
    statement: Cada interrupción deja su marca de parada en la traza.
    category: policy
    applies_to: "La traza de una interrupción"
    trigger: "Al confirmarse una interrupción."
    logic: >
      Es lo que AC1.24.5 exige explícitamente: la traza de cada interrupción
      tiene su marca de parada. Sin ella, NFR2 se mediría con un cronómetro a
      mano.
    violation: "La prueba de una interrupción no encuentra la marca."
    source: AC1.24.5, NFR2, FR10.2

  - id: BR8.3
    statement: Cada recuperación tras corte deja su marca, enlazada al caso original.
    category: policy
    applies_to: "La traza de una retoma"
    trigger: "Al retomar un caso cortado."
    logic: >
      El enlace al caso original es lo que permite contar la recuperación de
      NFR3 y lo que AC1.27.6 pide nombrado. Una marca sin enlace no distingue
      una retoma de una llamada nueva.
    violation: "La prueba de AC1.27.6 no puede enlazar la marca con el caso."
    source: AC1.27.6, NFR3, FR10.2

  - id: BR8.4
    statement: Ningún evento de traza lleva texto sin redactar.
    category: validation
    applies_to: "Los cuatro eventos de latencia y los de error"
    trigger: "Al emitirlos."
    logic: >
      Los eventos de latencia llevan tiempos, no contenido, y los de error llevan
      el tipo y el intento. Es ADR-013: contenido en trazas solo después de
      redactar, y RT-14 es la fuga que esta regla cierra.
    violation: "La prueba de redacción en trazas encuentra texto crudo."
    source: ADR-013, RT-14, M6
```

## Resumen

| Familia | Reglas | Cuántas bloquean |
| --- | --- | --- |
| La conexión | BR1.1 – BR1.6 | — |
| La apertura | BR2.1 – BR2.4 | BR2.1 |
| El turno hablado | BR3.1 – BR3.8 | — |
| La interrupción | BR4.1 – BR4.5 | — |
| Los silencios | BR5.1 – BR5.3 | — |
| El corte y la retoma | BR6.1 – BR6.5 | BR6.3 |
| La privacidad | BR7.1 – BR7.3 | BR7.1 |
| Las trazas | BR8.1 – BR8.4 | — |

38 reglas, tres de ellas `[bloquea]`.
