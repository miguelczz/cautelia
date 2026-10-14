# Reglas de negocio — U11 `intake`

Veinticinco reglas en cinco familias, en el orden en que una conversación las
atraviesa: quién eres, qué extraigo de lo que dijiste, en qué orden pregunto y
cómo confirmo, qué rompe ese orden, y cómo te trato.

Cinco son **compuerta dura** —BR1.2, BR1.4, BR2.3, BR4.1 y BR5.6—: corresponden a un
criterio `[bloquea]` del PRD 11.2 y un solo fallo detiene la entrega.

## Reglas

El bloque siguiente es la fuente de verdad; la tabla resumen se deriva de él.

```yaml
rules:

  - id: BR1.1
    statement: El caso se abre en el primer turno, antes de pedir nada.
    category: policy
    applies_to: "Case (U4)"
    trigger: "Cuando la persona elige reportar un siniestro o preguntar por su poliza."
    logic: "Reportar abre el caso con tipo siniestro en el turno de la pregunta de seguridad, para poder registrar la respuesta; preguntar por cobertura lo abre con tipo consulta y sin pregunta de seguridad."
    violation: "Las pruebas de AC1.5.1 y AC1.3.6 fallan."
    source: AC1.5.1, AC1.3.6, FR1.1

  - id: BR1.2
    statement: Una poliza que no es de este inquilino responde igual que una que no existe.
    category: security
    applies_to: "La identificacion"
    trigger: "Cuando el numero dado existe solo en otra aseguradora."
    logic: "Misma respuesta, mismo estado y misma rama de codigo que un numero inexistente. U8 ya devuelve lo mismo en los dos casos --su regla de poliza ajena-- y esta regla es no deshacerlo al componer el turno."
    violation: "Compuerta dura: la prueba de AC1.3.2 detiene la entrega."
    source: AC1.3.2, NFR10, M9

  - id: BR1.3
    statement: Un numero que no es de la demostracion se dice sin repetirlo.
    category: policy
    applies_to: "La identificacion"
    trigger: "Cuando el numero no existe en ninguna aseguradora de la demo."
    logic: "La agente explica que la demostracion solo usa polizas de ejemplo y senala la de la pagina, y no devuelve el numero que la persona escribio: repetirlo es escribir un dato de un tercero en la transcripcion."
    violation: "La prueba de AC1.3.3 falla."
    source: AC1.3.3, M10

  - id: BR1.4
    statement: El caso de otra persona no existe para quien pregunta.
    category: security
    applies_to: "Toda peticion sobre un caso"
    trigger: "Cuando se pide ver un caso o los datos de otro asegurado."
    logic: "No se revela nada, ni siquiera que el caso existe, y se ofrece ayuda solo con el caso propio."
    violation: "Compuerta dura: RT-4 de DS-6 detiene la entrega."
    source: AC1.3.4, RT-4, NFR12.2

  - id: BR1.5
    statement: Quien reporta por otro queda registrado como tercero, con su relacion.
    category: policy
    applies_to: "CaseParty (U4)"
    trigger: "Cuando la persona dice que reporta por otra."
    logic: "Se anota como tercero que reporta con su relacion con el asegurado, y **no se confirma ningun dato de la poliza mas alla de los que esa persona aporta**: confirmarle datos que no dio seria revelarselos."
    violation: "La prueba de AC1.4.2 falla, y RT-9 de DS-6 con ella."
    source: AC1.4.1, AC1.4.2, RT-9

  - id: BR1.6
    statement: Un numero incompleto se vuelve a pedir, nunca se completa adivinando.
    category: validation
    applies_to: "La identificacion"
    trigger: "Cuando el numero de poliza no tiene los digitos que debe."
    logic: "Se pide repetirlo. No se busca el numero mas parecido ni se rellena el digito que falta: acertar por casualidad asociaria el caso a la poliza de otra persona."
    violation: "La prueba de AC1.3.5 falla."
    source: AC1.3.5

  - id: BR2.1
    statement: Solo se extrae lo dicho en el turno.
    category: constraint
    applies_to: "La extraccion"
    trigger: "En cada turno de la persona."
    logic: "El modelo extrae de ese turno y no completa con lo que suele ir junto. Un campo que la persona no dijo no se escribe, aunque sea deducible."
    violation: "La exactitud de extraccion de AC1.7.5 cae, y el caso afirma algo que nadie dijo."
    source: AC1.7.5, M1, FR1.3

  - id: BR2.2
    statement: Todo campo escrito lleva el turno del que salio.
    category: constraint
    applies_to: "CaseField (U4)"
    trigger: "Al escribir un campo."
    logic: "La evidencia es el identificador del turno y lo que la persona dijo, ya redactado. Sin evidencia no se escribe: es lo que permite comparar la lectura de confirmacion contra lo dicho (AC1.7.4) y lo que hace auditable la extraccion."
    violation: "La prueba de evidencia falla, y AC1.7.4 no se puede medir."
    source: AC1.7.4, FR1.3, M1

  - id: BR2.3
    statement: El texto de la persona entra como dato delimitado, nunca en posicion de instruccion.
    category: security
    applies_to: "El prompt de extraccion y el de redaccion"
    trigger: "Siempre."
    logic: "Entra como campo delimitado del estado tipado, jamas concatenado al prompt de sistema. Una frase que diga 'ignora las reglas' no cambia nada de lo que el sistema hace."
    violation: "Compuerta dura: RT-1 y RT-2 de DS-6 detienen la entrega."
    source: RT-1, RT-2, NFR12.2

  - id: BR2.4
    statement: Lo dictado se normaliza con reglas versionadas, no con el criterio del modelo.
    category: calculation
    applies_to: "Fechas relativas, placas, polizas, cedulas y telefonos"
    trigger: "Al extraer un valor de esos tipos."
    logic: "Las reglas viven en configuracion versionada y se aplican en codigo. Incluyen limpiar los separadores dichos que la transcripcion pega a los codigos ('be de seis' -> 'BD6'). Que normalice el modelo haria que dos corridas del mismo commit escribieran cosas distintas."
    violation: "La exactitud por campo de AC1.7.5 cae y deja de ser reproducible."
    source: AC1.7.5, FR1.3

  - id: BR2.5
    statement: Las letras confundibles se deletrean con una palabra.
    category: policy
    applies_to: "La lectura de un codigo"
    trigger: "Al leer de vuelta una placa, una poliza o una cedula."
    logic: "Las letras que se confunden al oido se deletrean con una palabra de la tabla versionada. Es del canal de voz, pero la tabla y la composicion son de aqui, para que el texto y la voz lean lo mismo."
    violation: "La prueba de deletreo falla."
    source: FR1.3, guia de voz

  - id: BR3.1
    statement: Un bloque cuenta como confirmado solo tras un si.
    category: policy
    applies_to: "CaseField (U4)"
    trigger: "Al cerrar un bloque."
    logic: "Se lee lo anotado y se pregunta si es correcto. Hasta el si, el bloque queda a la espera y sus campos no cuentan para la completitud. Un no abre la correccion y se vuelve a leer el bloque corregido."
    violation: "Las pruebas de AC1.7.1 y AC1.7.2 fallan."
    source: AC1.7.1, AC1.7.2, FR1.3

  - id: BR3.2
    statement: El bloque que toca se deduce del caso, no de un contador propio.
    category: constraint
    applies_to: "IntakeTurnResult.next_block"
    trigger: "En cada turno."
    logic: "Se lee del estado que campos estan confirmados y de ahi sale el siguiente bloque, en el orden fijo: seguridad, identidad y poliza, que paso, cuando y donde, vehiculo y conductor, otras partes, confirmacion final. Un contador propio se desincronizaria al reanudar tras interrupt()."
    violation: "La prueba de AC1.5.2 falla, que lee el bloque preguntado del estado."
    source: AC1.5.2, ADR-003

  - id: BR3.3
    statement: Un dato adelantado no se vuelve a preguntar.
    category: policy
    applies_to: "El orden de las preguntas"
    trigger: "Cuando un campo de un bloque posterior ya se extrajo."
    logic: "Al llegar ese bloque se pide solo lo que falta. Volver a preguntar lo que la persona ya conto es la queja que esta historia existe para evitar."
    violation: "La prueba de AC1.5.4 falla."
    source: AC1.5.4, FR4.2

  - id: BR3.4
    statement: Una idea por turno, veinticinco palabras o menos.
    category: constraint
    applies_to: "Todo turno de la agente"
    trigger: "Al emitir, salvo el primer mensaje, las lecturas de confirmacion, el resumen de cierre y el texto de una clausula."
    logic: "Una sola pregunta y veinticinco palabras o menos; en el chat, sin marcadores orales de la voz. Lo juzga el codigo, no el juez, asi que se publica aunque el juez este descalibrado."
    violation: "La prueba de AC1.5.3 falla."
    source: AC1.5.3, AC1.13.5

  - id: BR3.5
    statement: Lesiones, conductor y lugar se confirman antes de anotarse.
    category: policy
    applies_to: "Esos tres campos"
    trigger: "Al extraerlos."
    logic: "No basta la confirmacion del bloque: estos tres se leen de vuelta antes de quedar escritos, porque son los que mueven la categoria del caso y el error se arrastra hasta la bandeja."
    violation: "La prueba de confirmacion previa falla."
    source: "unit-of-work.md, responsabilidades de U11"

  - id: BR3.6
    statement: El nombre de pila se pide antes de usarse.
    category: policy
    applies_to: "Como se dirige la agente a la persona"
    trigger: "En ingles, cuando la persona dio su nombre."
    logic: "No se usa el nombre de pila hasta preguntar si puede llamarla asi y recibir un si."
    violation: "La prueba de AC1.5.5 falla."
    source: AC1.5.5, guia de voz

  - id: BR4.1
    statement: La emergencia rompe el orden en el mismo turno.
    category: policy
    applies_to: "El orden de la captura"
    trigger: "Cuando el control barato de emergencia de U10 levanta la senal, al empezar o a mitad del reporte."
    logic: "La captura deja su orden y el turno sale con la indicacion de emergencia antes de pedir cualquier dato, y ofrece seguir despues. La senal la levanta U10 dentro del turno (D22); U11 no la detecta, la respeta."
    violation: "Compuerta dura: AC1.6.1 y AC1.6.2 detienen la entrega."
    source: AC1.6.1, AC1.6.2, RT-8, D22

  - id: BR4.2
    statement: Una pregunta de cobertura a mitad del reporte no descarrila la captura.
    category: policy
    applies_to: "El orden de la captura"
    trigger: "Cuando la persona pregunta por su cobertura mientras reporta."
    logic: "La respuesta de cobertura la produce el nodo de U8 en el ritmo de fondo; la captura retoma el bloque donde iba, sin volver a preguntar lo ya confirmado (BR3.2 lo hace posible)."
    violation: "El eje de DS-2 de pregunta de cobertura durante el reporte falla."
    source: US2.4, AC1.5.4

  - id: BR5.1
    statement: Todo texto sale del catalogo por idioma.
    category: constraint
    applies_to: "Toda frase que llega a una persona"
    trigger: "Siempre."
    logic: "Apertura con divulgacion, preguntas, lecturas, frases de calma y de cierre: por clave, con paridad entre los dos idiomas. Ninguna cadena visible se escribe en linea."
    violation: "El chequeo de paridad del catalogo falla."
    source: M6, P12, F7.5

  - id: BR5.2
    statement: Se reconoce primero y se pregunta despues.
    category: policy
    applies_to: "El turno que sigue a una senal de emocion"
    trigger: "Cuando la persona responde con miedo, llanto o enojo."
    logic: "Una sola frase de reconocimiento del catalogo, y despues una sola pregunta. Nunca dos preguntas ni una pregunta sola."
    violation: "El eje de emocion de DS-2 falla y la rubrica de estilo cae."
    source: AC1.13.1, P11

  - id: BR5.3
    statement: Hay un registro prohibido, y lo juzga el codigo.
    category: constraint
    applies_to: "Todo turno de la agente"
    trigger: "Al emitir."
    logic: "Ninguna frase de la lista versionada que culpa o minimiza, ninguna forma con genero de esa lista, y en espanol ni 'mija', ni 'mijo', ni 'parce', ni '¿que mas?', ni groserias, ni dos o mas diminutivos de la lista. Es una comprobacion de codigo sobre el texto ya compuesto, no un criterio del juez."
    violation: "Las pruebas de AC1.13.2 y AC1.13.4 fallan."
    source: AC1.13.2, AC1.13.4, P11

  - id: BR5.4
    statement: Al segundo insulto se ofrece una persona; al tercero se cierra la sesion.
    category: policy
    applies_to: "La sesion"
    trigger: "Cuando la persona insulta a la agente."
    logic: "El numero de insultos que dispara cada paso lo fija la configuracion, no el codigo. Al llegar al primero se usa la frase de calma y se ofrece que una persona revise el caso, sin reproches; al siguiente, la frase de cierre por abuso, la sesion termina y el caso queda en 'esperando al asegurado' con ese motivo."
    violation: "La prueba de AC1.13.3 falla."
    source: AC1.13.3, RT-11

  - id: BR5.5
    statement: Dos versiones de lo que paso se guardan las dos, sin juzgar.
    category: policy
    applies_to: "CaseField (U4)"
    trigger: "Cuando la persona da un valor que contradice uno ya confirmado."
    logic: "Se guardan las dos versiones, cada una con su turno y su hora. La agente no acusa, no aconseja y no cambia de tono: la contradiccion la resuelve la regla de la aseguradora en el ritmo de fondo, no la captura."
    violation: "RT-7 de DS-6 falla."
    source: AC1.12.1, AC1.12.2, RT-7

  - id: BR5.6
    statement: La captura nunca afirma cobertura, monto ni culpa.
    category: security
    applies_to: "Todo turno de la agente"
    trigger: "Siempre."
    logic: "Ni siquiera para tranquilizar. La cobertura la responde U8 con una cita verificada, los montos los confirma un ajustador y la culpa no la decide nadie aqui. La guardia de salida de U10 es la red; esta regla es no llegar a ella."
    violation: "Compuerta dura de PRD 11.2: cero turnos que afirmen cobertura, montos o culpa."
    source: P1, M11, "unit-of-work.md, responsabilidades de U11"
```

## Resumen

| Regla | En una línea |
| --- | --- |
| BR1.1 | El caso se abre en el primer turno |
| BR1.2 | Una póliza ajena responde igual que una inexistente |
| BR1.3 | Un número que no es de la demo no se repite |
| BR1.4 | El caso de otra persona no existe para quien pregunta |
| BR1.5 | Quien reporta por otro queda como tercero, y no se le confirma nada |
| BR1.6 | Un número incompleto se vuelve a pedir, no se adivina |
| BR2.1 | Solo se extrae lo dicho en el turno |
| BR2.2 | Todo campo lleva el turno del que salió |
| BR2.3 | El texto de la persona es dato, nunca instrucción |
| BR2.4 | Lo dictado se normaliza con reglas versionadas |
| BR2.5 | Las letras confundibles se deletrean |
| BR3.1 | Un bloque se confirma solo tras un sí |
| BR3.2 | El bloque que toca se deduce del caso |
| BR3.3 | Un dato adelantado no se vuelve a preguntar |
| BR3.4 | Una idea por turno, 25 palabras o menos |
| BR3.5 | Lesiones, conductor y lugar se confirman antes de anotarse |
| BR3.6 | El nombre de pila se pide antes de usarse |
| BR4.1 | La emergencia rompe el orden en el mismo turno |
| BR4.2 | Una pregunta de cobertura no descarrila la captura |
| BR5.1 | Todo texto sale del catálogo, en los dos idiomas |
| BR5.2 | Se reconoce primero y se pregunta después |
| BR5.3 | Hay un registro prohibido, y lo juzga el código |
| BR5.4 | Al segundo insulto se ofrece una persona; al tercero se cierra |
| BR5.5 | Dos versiones se guardan las dos, sin juzgar |
| BR5.6 | La captura nunca afirma cobertura, monto ni culpa |
