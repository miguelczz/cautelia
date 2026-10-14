# Reglas — U14 `inbox`

Treinta y tres reglas en seis familias: la cola, la vista de caso, la corrección,
la decisión, el acceso por enlace y el aviso en vivo.

Tres llevan `[bloquea]` y las tres son de aislamiento: una credencial nunca ve
casos de otra aseguradora, un enlace abre solo su caso y nunca la lista, y una
firma alterada se responde igual que un caso que no existe.

```yaml
rules:
  # --- La cola (US3.1, US3.5) -------------------------------------------------
  - id: BR1.1
    statement: La cola ordena por prioridad y, dentro de cada prioridad, por espera más larga primero.
    category: policy
    applies_to: "La lista de casos de una aseguradora"
    trigger: "Al pedir la cola, con o sin filtros."
    logic: >
      El orden lo decide el servidor y no la pantalla: dos personas mirando la
      misma cola tienen que ver lo mismo. Una solicitud de persona cuenta como
      prioridad alta (AC3.1.2), y eso es dato de la configuración de la
      aseguradora, no una rama del código.
    violation: "La prueba de AC3.1.1 falla."
    source: AC3.1.1, AC3.1.2, FR8.1

  - id: BR1.2
    statement: Cada fila muestra completitud, categoría, canal, idioma, prioridad y tiempo de espera.
    category: constraint
    applies_to: "Una fila de la cola"
    trigger: "Al dibujar la lista."
    logic: >
      Los seis datos van en la fila porque son con lo que se decide cuál abrir.
      Ninguno es texto libre del asegurado, así que la fila no necesita
      redacción: lo que lleva son enums, números y horas.
    violation: "La prueba de AC3.1.1 falla."
    source: AC3.1.1, FR8.1

  - id: BR1.3
    statement: Un filtro sin resultados lo dice y ofrece quitarlos.
    category: policy
    applies_to: "La cola filtrada"
    trigger: "Cuando ninguna fila coincide."
    logic: >
      Una lista vacía sin explicación se lee como una bandeja vacía, que es lo
      contrario de lo que pasó. Se dice que ningún caso coincide y se ofrece la
      acción de quitar los filtros.
    violation: "La prueba de AC3.1.2 falla."
    source: AC3.1.2

  - id: BR1.4
    statement: "[bloquea] Una credencial nunca ve casos de otra aseguradora, ni por la interfaz ni por la API."
    category: security
    applies_to: "Toda consulta de la bandeja"
    trigger: "En cada petición con credencial."
    logic: >
      La aseguradora sale de la credencial y **nunca de la dirección**: una
      credencial de Sunmeadow pidiendo la bandeja de Stonecroft se rechaza sin
      devolver ningún dato. Lo impone además la política de fila, que es la
      segunda capa: el punto único de sesión fija la aseguradora antes de
      devolver la conexión.
    violation: "La prueba de AC3.1.3 o la de AC3.1.4 falla, o el conjunto DS-8 encuentra una colisión."
    source: AC3.1.3, AC3.1.4, FR9.4, NFR10, M9

  - id: BR1.5
    statement: Los casos que esperan al asegurado aparecen en la cola con su completitud y su último bloque confirmado.
    category: policy
    applies_to: "La cola"
    trigger: "Cuando un caso está en 'esperando al asegurado'."
    logic: >
      Un caso a medias que no aparece es un caso perdido. Se muestra con lo que
      se alcanzó a capturar y dónde se quedó, y deja de aparecer así en cuanto
      el asegurado lo retoma y lo completa.
    violation: "La prueba de AC3.5.1 o la de AC3.5.4 falla."
    source: AC3.5.1, AC3.5.4, FR8.6

  - id: BR1.6
    statement: La interfaz abre en inglés, recuerda el idioma elegido, y el contenido del caso no se traduce.
    category: policy
    applies_to: "Las pantallas de la bandeja"
    trigger: "Al elegir idioma en el selector."
    logic: >
      Las etiquetas siguen en el idioma elegido al abrir un caso, volver y
      recargar. Lo que el asegurado dijo se queda **en su idioma**: traducir una
      transcripción sería mostrar palabras que nadie dijo.
    violation: "La prueba de AC3.1.5 falla."
    source: AC3.1.5, D5

  # --- La vista de caso (US3.2) ----------------------------------------------
  - id: BR2.1
    statement: Lo primero visible es el motivo de la derivación, la categoría y la completitud, con las acciones de decidir al alcance.
    category: policy
    applies_to: "La vista de caso"
    trigger: "Al abrir un caso."
    logic: >
      Los cuatro viajan juntos en un encabezado que se queda arriba al
      desplazar (decisión de Miguel, 2026-09-28). Mantiene junto el *por qué
      llegó* y el *qué hago*, que es la pareja que el criterio nombra en la
      misma frase; una barra de acción abajo deja ver el botón sin ver el
      motivo.
    violation: "La prueba de AC3.2.1 falla."
    source: AC3.2.1, FR8.2

  - id: BR2.2
    statement: La vista muestra los seis bloques de evidencia, tres abiertos y tres plegados con su titular a la vista.
    category: constraint
    applies_to: "La vista de caso"
    trigger: "Al abrir un caso."
    logic: >
      Completitud por campo, transcripción y cláusulas citadas se ven de
      entrada; regla disparada, resultado de los cuatro controles y resumen de
      traza se abren al pulsarlos (decisión de Miguel, 2026-09-28). **El titular
      de un bloque plegado muestra su resultado** --"cuatro controles en verde",
      "1,8 s · 0,003 USD"--: plegar no puede esconder el dato, solo su detalle.
    violation: "La prueba de AC3.2.2 falla, o un bloque plegado no dice su resultado."
    source: AC3.2.2, AC3.2.5, FR8.2

  - id: BR2.3
    statement: En la transcripción, cada dato personal aparece como una etiqueta de su tipo que nombra el campo del caso donde quedó el valor.
    category: security
    applies_to: "El bloque de transcripción"
    trigger: "Al mostrar un turno."
    logic: >
      La transcripción llega ya redactada de U3 y la bandeja no la destapa. La
      etiqueta dice de qué tipo era y en qué campo del caso está el valor
      completo, para que corregirlo sea posible sin leerlo en la conversación.
    violation: "La prueba de AC3.2.2 falla, o el reporte de redacción encuentra un dato personal en la vista."
    source: AC3.2.2, M6

  - id: BR2.4
    statement: La explicación responde qué se preguntó, qué se citó, qué regla se disparó, quién decidió y cuándo.
    category: policy
    applies_to: "La vista de caso"
    trigger: "Siempre."
    logic: >
      En un caso sin decidir, "quién decidió" dice **pendiente de decisión** y no
      queda en blanco: un campo vacío se lee como un dato que se perdió.
    violation: "La prueba de AC3.2.3 falla."
    source: AC3.2.3, FR7.4

  - id: BR2.5
    statement: >
      'Sin cláusula' y 'no pude verificar' se muestran con etiquetas distintas.
    category: constraint
    applies_to: "El bloque de cláusulas"
    trigger: "Al mostrar una respuesta de cobertura."
    logic: >
      Son dos valores distintos en el estado, en la traza y en el reporte de
      evaluaciones, y lo son también aquí. Colapsarlos en la pantalla
      contaminaría con fallos de infraestructura una respuesta que sí se verificó.
    violation: "La prueba de AC3.2.4 falla."
    source: AC3.2.4, PRD 12.3

  - id: BR2.6
    statement: La aseguradora que emitió la póliza se ve en el caso, y las cláusulas citadas son de esa emisora.
    category: business_logic
    applies_to: "La vista de caso de una agencia"
    trigger: "Cuando la aseguradora del caso es una agencia."
    logic: >
      En una agencia, quien emite la póliza no es quien atiende el caso. Sin ese
      dato a la vista, las cláusulas citadas parecen de la agencia.
    violation: "La prueba de AC3.6.4 falla."
    source: AC3.6.4, FR6.4

  # --- La corrección de campos (US3.3) ---------------------------------------
  - id: BR3.1
    statement: Una corrección registra el valor anterior, el nuevo, quién, cuándo y el canal bandeja.
    category: constraint
    applies_to: "La corrección de un campo"
    trigger: "Al guardar un valor corregido."
    logic: >
      Lo escribe U4, que es dueño del historial; la bandeja aporta el actor y el
      canal. El campo y su entrada de historial van en una sola transacción, que
      es una propiedad que U4 ya garantiza.
    violation: "La prueba de AC3.3.1 falla."
    source: AC3.3.1, FR8.3, FR1.6

  - id: BR3.2
    statement: Corregir un campo no cambia la transcripción.
    category: constraint
    applies_to: "La transcripción del caso"
    trigger: "Después de una corrección."
    logic: >
      La transcripción sigue mostrando lo que se dijo, redactado. Corregir es
      arreglar un error de captura, no reescribir lo que dijo una persona.
    violation: "La prueba de AC3.3.2 falla."
    source: AC3.3.2

  - id: BR3.3
    statement: Un valor inválido se rechaza nombrando el campo y el formato esperado, y conserva el anterior.
    category: validation
    applies_to: "La corrección de un campo"
    trigger: "Cuando el valor no cumple el formato del campo."
    logic: >
      La validación es la de U4 --la bandeja no escribe una segunda-- y el
      mensaje sale del catálogo por idioma. Conservar el valor anterior es lo que
      impide que un intento fallido borre un dato bueno.
    violation: "La prueba de AC3.3.3 falla."
    source: AC3.3.3

  - id: BR3.4
    statement: Un caso cerrado no admite correcciones, ni por la interfaz ni por la API.
    category: authorization
    applies_to: "La corrección de un campo"
    trigger: "Cuando el caso está cerrado."
    logic: >
      Un caso cerrado expone la evidencia que se comprobó **al cerrarlo**. Si sus
      campos pudieran cambiar después, esa evidencia seguiría atestiguando algo
      que ya no es. La pantalla no ofrece la acción y la petición directa se
      rechaza: lo segundo es lo que de verdad lo impide.
    violation: "La prueba de AC3.3.4 falla."
    source: AC3.3.4, y la regla de U4 que congela un caso cerrado

  # --- La decisión (US3.4, US3.6) --------------------------------------------
  - id: BR4.1
    statement: Toda decisión exige comentario, y sin él se rechaza sin perder lo elegido.
    category: validation
    applies_to: "La decisión de un caso"
    trigger: "Al confirmar aprobar, rechazar o enviar a la aseguradora."
    logic: >
      El comentario es lo que hace auditable la decisión. Al rechazarla, la
      decisión elegida y el texto escrito siguen en pantalla: perder lo escrito
      por un error de validación es la forma más barata de que alguien decida sin
      comentario a la segunda.
    violation: "La prueba de AC3.4.1 falla."
    source: AC3.4.1, FR8.4

  - id: BR4.2
    statement: Aprobar o rechazar reanuda el grafo desde su punto de control y cierra el caso con su resolución.
    category: business_logic
    applies_to: "La decisión de un caso derivado"
    trigger: "Al confirmar con comentario."
    logic: >
      La reanudación la hace U12 por su contrato; la bandeja entrega la decisión
      y su comentario y **no espera** a que el grafo termine: la respuesta es
      `202` y el trabajo sigue de fondo. El caso registra quién decidió, cuándo y
      con qué comentario.
    violation: "La prueba de AC3.4.2 o la de AC3.4.3 falla."
    source: AC3.4.2, AC3.4.3, FR2.5

  - id: BR4.3
    statement: Un caso derivado con completitud parcial se puede decidir; uno que espera al asegurado, no.
    category: authorization
    applies_to: "Las acciones de decidir"
    trigger: "Al abrir un caso."
    logic: >
      Son dos situaciones distintas y se tratan distinto: derivado por solicitud
      de persona con 3/7 se decide y su completitud se muestra tal cual;
      "esperando al asegurado" no se decide, la vista dice por qué y qué campos
      faltan, y la petición directa se rechaza sin cambiar el caso.
    violation: "La prueba de AC3.4.4 o la de AC3.5.3 falla."
    source: AC3.4.4, AC3.5.3

  - id: BR4.4
    statement: Dos personas no deciden el mismo caso; la segunda ve la decisión que ya existe y su acción no se aplica.
    category: constraint
    applies_to: "La decisión de un caso"
    trigger: "Cuando el caso ya tiene resolución."
    logic: >
      Lo decide el estado del caso y no un bloqueo de pantalla: dos pestañas
      abiertas son el caso normal. Y una decisión repetida con la misma clave de
      idempotencia devuelve **la primera**, sin crear otra ni fallar.
    violation: "La prueba de AC3.4.5 falla, o repetir la clave crea una segunda decisión."
    source: AC3.4.5, C-05

  - id: BR4.5
    statement: Las acciones disponibles las decide la política de la aseguradora, no el código.
    category: authorization
    applies_to: "Las acciones de la vista de caso"
    trigger: "Al abrir un caso."
    logic: >
      Una agencia ve "marcar como enviado a la aseguradora" y no ve aprobar ni
      rechazar; una aseguradora que emite ve aprobar y rechazar. Sale de la
      carpeta de configuración de la aseguradora, y el código de decisión no
      contiene ninguna condición escrita para una aseguradora concreta. Una
      petición directa para aprobar con una credencial de agencia se rechaza sin
      cambiar el caso.
    violation: "La prueba de AC3.6.3 o la de AC3.6.2 falla, o aparece un identificador de aseguradora literal en el código."
    source: AC3.6.2, AC3.6.3, FR6.4

  - id: BR4.6
    statement: Marcar como enviado cierra el caso con esa resolución y no promete ningún contacto.
    category: compliance
    applies_to: "La acción de la agencia"
    trigger: "Al confirmar el envío."
    logic: >
      El traspaso real no existe en esta versión (W1). El caso queda cerrado con
      resolución 'enviado a la aseguradora', sigue en la agencia y no aparece en
      la bandeja de la emisora. Nada de lo que ve el asegurado promete que la
      emisora lo llame.
    violation: "La prueba de AC3.6.5 falla, o el texto promete un contacto."
    source: AC3.6.5, W1

  - id: BR4.7
    statement: La tercera decisión del contrato no se construye en esta unidad.
    category: constraint
    applies_to: "El contrato C-05"
    trigger: "Al implementar la ruta de decisión."
    logic: >
      C-05 declara `request_more` y ninguna historia la describe, ningún criterio
      la ejercita y ninguna de las cuatro resoluciones de U4 le corresponde.
      Construirla sería inventar su conducta. Un caso que necesita más
      información ya tiene camino probado: queda en 'esperando al asegurado' y el
      asegurado lo retoma. El contrato se enmienda con esta razón y añadirla
      después es un cambio aditivo (decisión de Miguel, 2026-09-28).
    violation: "La ruta acepta `request_more`."
    source: C-05, AC3.5.3, AC3.5.4

  # --- El acceso por enlace firmado (US3.7, US3.8) ----------------------------
  - id: BR5.1
    statement: "[bloquea] Un enlace firmado abre su caso y nunca la lista de la aseguradora."
    category: security
    applies_to: "El acceso del visitante"
    trigger: "Al canjear un enlace."
    logic: >
      La sesión que deja el canje autoriza **un caso**, no una aseguradora. Con
      ella, la cola responde igual que a quien no tiene credencial. Mostrar la
      lista expondría casos de otros visitantes.
    violation: "La prueba de AC3.7.2 falla, o la cola responde algo con una sesión de caso."
    source: AC3.7.2, D6, FR8.7

  - id: BR5.2
    statement: "[bloquea] Una firma alterada y un caso que no existe se responden igual."
    category: security
    applies_to: "El canje de un enlace"
    trigger: "Cuando la firma no valida, el caso no existe o el enlace venció antes del reinicio."
    logic: >
      El mismo mensaje de enlace no válido, sin confirmar si el caso existe. Un
      mensaje distinto para cada causa le dice a quien prueba enlaces cuál de sus
      intentos acertó el identificador. El enlace emitido antes del reinicio
      nocturno sí dice su causa propia --los datos de la demostración se borran
      cada noche-- porque ahí no hay nada que confirmar: el caso ya no existe
      para nadie.
    violation: "La prueba de AC3.7.3 o la de AC3.8.5 falla."
    source: AC3.7.3, AC3.8.5

  - id: BR5.3
    statement: El enlace vale una hora, y el borde se comprueba a los dos lados.
    category: constraint
    applies_to: "El canje de un enlace"
    trigger: "Al abrirlo."
    logic: >
      A los 59 minutos 59 segundos da acceso; a los 60 minutos 1 segundo dice que
      caducó y no deja ver ni decidir. El reloj entra por argumento, que es lo
      que permite probar los dos bordes sin esperar una hora.
    violation: "La prueba de AC3.7.4 falla."
    source: AC3.7.4

  - id: BR5.4
    statement: Si el enlace vence mientras se escribe el comentario, la decisión no se aplica y el comentario sigue en pantalla.
    category: policy
    applies_to: "La decisión desde un enlace"
    trigger: "Cuando la sesión del enlace venció al confirmar."
    logic: >
      Se dice que venció y **el texto escrito se conserva para copiarlo**.
      Perderlo convierte un vencimiento en trabajo perdido, y quien lo sufre es
      justo quien estaba terminando de decidir.
    violation: "La prueba de AC3.8.3 falla."
    source: AC3.8.3

  - id: BR5.5
    statement: La decisión tomada con un enlace se atribuye a un visitante de demostración, nunca a una persona de la aseguradora.
    category: security
    applies_to: "El historial y la explicación del caso"
    trigger: "Al registrar una decisión desde un enlace."
    logic: >
      El actor sale de la sesión con la que se decidió. Atribuirla a una persona
      de la bandeja falsificaría el registro de quién decidió, que es
      exactamente lo que la explicación existe para responder.
    violation: "La prueba de AC3.7.5 falla."
    source: AC3.7.5

  - id: BR5.6
    statement: El token no queda en la dirección visible, ni viaja en `Referer`, ni aparece en ningún registro.
    category: security
    applies_to: "El canje del enlace"
    trigger: "Al cargar la vista."
    logic: >
      El canje cambia el token por una cookie de caso y limpia la dirección; la
      página declara la política de referente que impide mandarlo a terceros. Un
      token en un registro es un enlace que cualquiera que lea ese registro puede
      usar durante su hora.
    violation: "La prueba de AC3.8.6 falla, o el token aparece en un registro."
    source: AC3.8.6

  - id: BR5.7
    statement: Un enlace vencido dice qué pasó, que el caso sigue guardado y cómo pedir uno nuevo.
    category: policy
    applies_to: "La pantalla del enlace vencido"
    trigger: "Al abrir un enlace vencido de un caso que sigue guardado."
    logic: >
      El enlace nuevo vale otra hora y **solo se entrega al navegador que creó el
      caso**: entregarlo a quien abrió un enlace vencido convertiría el
      vencimiento en un trámite.
    violation: "La prueba de AC3.8.4 falla."
    source: AC3.8.4

  # --- El aviso en vivo (C-06) ------------------------------------------------
  - id: BR6.1
    statement: La cola y la vista abiertas se actualizan solas por el flujo de eventos.
    category: policy
    applies_to: "Las pantallas abiertas"
    trigger: "Cuando un caso de la aseguradora cambia."
    logic: >
      Un evento por cambio, con su identificador creciente por aseguradora. La
      pantalla aplica el cambio sobre lo que ya tiene en vez de volver a pedirlo
      todo.
    violation: "La prueba del flujo falla."
    source: C-06, ADR-021

  - id: BR6.2
    statement: Una reconexión reanuda desde `Last-Event-ID` y no pierde lo ocurrido mientras estuvo caída.
    category: constraint
    applies_to: "El flujo de la bandeja"
    trigger: "Al reconectar."
    logic: >
      El servidor reproduce lo posterior a ese identificador. Sin esto, una
      reconexión deja la cola mostrando un estado viejo sin que nadie lo note,
      que es peor que no actualizarse.
    violation: "La prueba de reanudación falla."
    source: C-06, ADR-021

  - id: BR6.3
    statement: El resumen de un evento va redactado al escribirse.
    category: security
    applies_to: "InboxEvent"
    trigger: "Al emitir un evento."
    logic: >
      Se redacta al escribir y no al leer. Un evento guardado con texto sin
      redactar es un punto de salida sin redacción, aunque nadie lo lea todavía.
    violation: "El reporte de redacción encuentra un dato personal en la tabla de eventos."
    source: C-06, M6
```

## Resumen

| Regla | Qué asegura |
| --- | --- |
| BR1.1 – BR1.6 | La cola: orden, contenido de la fila, filtros sin resultados, aislamiento `[bloquea]`, casos a medias visibles, idioma |
| BR2.1 – BR2.6 | La vista: qué se ve primero, seis bloques (tres y tres), transcripción etiquetada, explicación completa, dos resultados distintos, emisora a la vista |
| BR3.1 – BR3.4 | La corrección: rastro, transcripción intacta, validación con su mensaje, caso cerrado inmutable |
| BR4.1 – BR4.7 | La decisión: comentario obligatorio, reanudación, qué se puede decidir, dos personas, acciones por configuración, sin promesa de contacto, y la tercera acción que no se construye |
| BR5.1 – BR5.7 | El enlace: solo su caso `[bloquea]`, una sola vía de rechazo `[bloquea]`, la hora por los dos bordes, el comentario que no se pierde, la atribución, el token que no se filtra, el vencido con salida |
| BR6.1 – BR6.3 | El aviso en vivo: se actualiza solo, reanuda sin perder, y va redactado |
