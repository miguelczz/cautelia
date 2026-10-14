# Reglas de negocio — U4 `case-record`

Cuarenta y dos reglas hacen del caso una fuente de verdad y no un montón de
campos. Se agrupan en siete familias: el esquema por tipo de registro, el estado de cada
campo con su evidencia, el modelo cerrado de estados, el número legible con su
canal y su origen, el historial, la transcripción con los adjuntos del cierre, y
el aislamiento con el borrado de datos de visitante.

## Reglas

El bloque siguiente es la fuente de verdad; la tabla resumen que va después se
deriva de él.

```yaml
rules:

  # --- BR1: esquema por tipo de registro -------------------------------------

  - id: BR1.1
    statement: >
      Un caso es de uno de tres tipos de registro, y solo de uno: siniestro,
      consulta de cobertura o solicitud de cotización. Crear un caso con un tipo
      que no está en esa lista se rechaza.
    category: constraint
    applies_to: Case
    trigger: "Al crear el caso."
    logic: >
      SI el tipo de registro pedido no es `claim`, `coverage_inquiry` ni
      `quote_request` ENTONCES el caso no se crea.
    violation: "Se rechaza la creación nombrando el tipo pedido y los tres válidos."
    source: FR1.1, ADR-005

  - id: BR1.2
    statement: >
      El tipo de registro no cambia después de crearse.
    category: constraint
    applies_to: Case
    trigger: "En cualquier escritura sobre el caso."
    logic: >
      SI se pide cambiar el tipo de registro ENTONCES se rechaza.
    violation: "Se rechaza dejando entrada en el historial."
    source: FR1.3, AC4.10.3

  - id: BR1.3
    statement: >
      Qué campos tiene cada tipo de registro, y qué bloque de la conversación
      alimenta cada uno, vive en un archivo versionado. No es una rama de código
      ni una lista repartida entre módulos.
    category: policy
    applies_to: "Esquema del caso"
    trigger: "Al arrancar y al calcular la completitud."
    logic: >
      SI el esquema versionado no declara el campo pedido para el tipo del caso
      ENTONCES el campo no se puede escribir.
    violation: "Se rechaza la escritura nombrando el campo y el tipo de registro."
    source: FR1.1, FR1.3, U4 (Contiene)

  - id: BR1.4
    statement: >
      El siniestro declara siete campos centrales: identidad y póliza, fecha y
      hora, lugar, descripción, vehículo y conductor, otras partes, y lesiones.
    category: constraint
    applies_to: "Esquema del caso"
    trigger: "Al validar el esquema."
    logic: >
      SI el esquema del siniestro no declara exactamente esos siete campos
      ENTONCES el arranque falla nombrando la diferencia.
    violation: "El aplicativo no arranca. Un esquema a medias publica una completitud que miente."
    source: FR1.1

  - id: BR1.5
    statement: >
      La consulta de cobertura declara dos campos: identidad y póliza, y la
      pregunta que se hizo. No lleva la pregunta de seguridad ni los campos del
      accidente.
    category: constraint
    applies_to: "Esquema del caso"
    trigger: "Al validar el esquema."
    logic: >
      SI el esquema de la consulta de cobertura declara campos del accidente
      ENTONCES el arranque falla.
    violation: "El aplicativo no arranca."
    source: AC1.3.6, AC2.4.3

  - id: BR1.6
    statement: >
      La solicitud de cotización existe como tipo pero su lista de campos la
      aporta U19 `quote`. Mientras esté vacía, no se puede crear un caso de ese
      tipo.
    category: constraint
    applies_to: "Esquema del caso"
    trigger: "Al crear un caso de tipo solicitud de cotización."
    logic: >
      SI el esquema versionado no declara ningún campo para el tipo pedido
      ENTONCES el caso no se crea.
    violation: >
      Se rechaza la creación diciendo qué unidad aporta ese esquema. Es preferible
      a crear un caso cuya completitud sería 0/0 y que por tanto podría cerrarse
      sin haber capturado nada.
    source: U4 (No contiene), FR13

  - id: BR1.7
    statement: >
      Los lesionados, los testigos, los otros conductores y los otros vehículos
      se guardan como partes del caso, con su rol, y el caso se recupera con
      todas ellas.
    category: constraint
    applies_to: CaseParty
    trigger: "Al guardar y al recuperar el caso."
    logic: >
      SI el caso tiene N partes ENTONCES recuperarlo devuelve las N con todos sus
      atributos.
    violation: "La recuperación falla en vez de devolver un caso incompleto en silencio."
    source: FR1.2, AC1.8.1

  - id: BR1.8
    statement: >
      Un atributo de una parte que no se sabe queda vacío y se trata como dato
      pendiente. Nunca se rellena con un valor supuesto.
    category: validation
    applies_to: CaseParty
    trigger: "Al registrar o actualizar una parte."
    logic: >
      SI no se dijo el valor de un atributo de la parte ENTONCES queda vacío, y
      un atributo vacío no cuenta como completo.
    violation: "Se rechaza escribir un valor que nadie dijo."
    source: AC1.8.2

  # --- BR2: estado del campo, evidencia y completitud -------------------------

  - id: BR2.1
    statement: >
      Cada campo del caso está en uno de tres estados: no dicho, dicho, o
      confirmado en voz alta.
    category: constraint
    applies_to: CaseField
    trigger: "En cualquier escritura del campo."
    logic: >
      SI el estado pedido no es `not_stated`, `stated` ni `confirmed` ENTONCES se
      rechaza.
    violation: "Se rechaza la escritura."
    source: FR1.3, ADR-005

  - id: BR2.2
    statement: >
      Lesiones, lugar, y vehículo y conductor solo llegan a confirmado después
      de la lectura de confirmación. Los otros cuatro campos del siniestro
      pueden quedarse en dicho.
    category: constraint
    applies_to: CaseField
    trigger: "Al marcar un campo como confirmado."
    logic: >
      SI el campo es `injuries`, `location` o `vehicle_and_driver` Y no hay
      lectura de confirmación ni corrección de la bandeja ENTONCES el campo no
      llega a `confirmed`.
    violation: "Se rechaza el cambio de estado y el campo se queda en `stated`."
    source: FR1.3, ADR-005

  - id: BR2.3
    statement: >
      "Ninguno" y cero solo existen si la persona los dijo. Un campo que nadie
      tocó nunca vale "ninguno" por omisión.
    category: validation
    applies_to: CaseField
    trigger: "Al escribir el valor de un campo."
    logic: >
      SI se pide escribir un valor negativo explícito ("ninguno", "cero") sin
      evidencia que lo respalde ENTONCES se rechaza.
    violation: >
      Se rechaza la escritura. Es la regla que impide repetir el hallazgo del
      experimento 2, donde el modelo inventaba "sin lesiones" sin que nadie lo
      dijera.
    source: ADR-005, AC1.8.4

  - id: BR2.4
    statement: >
      Todo campo en dicho o confirmado lleva exactamente una evidencia: el turno
      en el que se dijo, o la entrada del historial si lo escribió una persona.
      Un campo no dicho no lleva ninguna.
    category: constraint
    applies_to: CaseField
    trigger: "Al escribir el valor o el estado de un campo."
    logic: >
      SI el estado es `stated` o `confirmed` Y no hay exactamente una evidencia
      ENTONCES se rechaza la escritura.
    violation: "Se rechaza. Un valor sin evidencia no se distingue de uno inventado."
    source: FR1.3, ADR-005, Q3 del diseño funcional

  - id: BR2.5
    statement: >
      Un campo que corrige una persona desde la bandeja queda confirmado, y su
      evidencia es la entrada del historial con el nombre de quien lo escribió.
    category: policy
    applies_to: CaseField
    trigger: "Al corregir un campo desde la bandeja."
    logic: >
      SI una persona de la aseguradora escribe el valor de un campo ENTONCES el
      campo queda `confirmed`, su evidencia es la entrada del historial y su
      marca de confirmación en voz alta queda vacía.
    violation: "No aplica: es la conducta, no una prohibición."
    source: FR1.6, Q3 del diseño funcional

  - id: BR2.6
    statement: >
      Un campo cuenta como completo cuando alcanza el estado que ese campo
      exige: confirmado para lesiones, lugar, y vehículo y conductor; dicho para
      los demás.
    category: calculation
    applies_to: Completeness
    trigger: "Al calcular la completitud."
    logic: >
      SI el campo exige confirmación ENTONCES cuenta solo con estado
      `confirmed`; SI NO, cuenta con `stated` o `confirmed`.
    violation: "No aplica: es el cálculo."
    source: FR1.3, Q2 del diseño funcional

  - id: BR2.7
    statement: >
      La completitud se calcula sobre los campos del tipo de registro del caso,
      no sobre una lista fija. Un siniestro con cinco de sus siete campos da
      exactamente 5/7.
    category: calculation
    applies_to: Completeness
    trigger: "Al calcular la completitud."
    logic: >
      SI el caso es de tipo T ENTONCES el denominador es el número de campos que
      el esquema versionado declara para T.
    violation: "No aplica: es el cálculo."
    source: FR1.3, AC4.10.3

  - id: BR2.8
    statement: >
      La completitud se publica por campo y total. No se guarda como un número
      suelto que alguien pueda escribir a mano.
    category: constraint
    applies_to: Completeness
    trigger: "Al leer el caso."
    logic: >
      SI se consulta la completitud ENTONCES se deriva de los campos en ese
      momento.
    violation: "No aplica: es la conducta."
    source: FR1.3

  # --- BR3: modelo cerrado de estados ----------------------------------------

  - id: BR3.1
    statement: >
      El caso vive en uno de siete estados: abierto, en captura, en
      verificación, en decisión, derivado, esperando al asegurado, y cerrado.
    category: constraint
    applies_to: Case
    trigger: "En cualquier transición."
    logic: >
      SI el estado pedido no está en los siete ENTONCES se rechaza.
    violation: "Se rechaza dejando entrada en el historial."
    source: FR1.4, ADR-005

  - id: BR3.2
    statement: >
      Las transiciones permitidas viven en una sola tabla versionada. Toda
      transición que no esté en esa tabla se rechaza, el caso no cambia y queda
      una entrada con el intento.
    category: constraint
    applies_to: Case
    trigger: "Al aplicar una transición."
    logic: >
      SI la pareja (estado actual, estado pedido) no está en la tabla ENTONCES
      el caso no cambia y se escribe una entrada de tipo transición rechazada con
      los dos estados.
    violation: >
      Se lanza un error propio que el llamador no captura para seguir adelante.
      Es la regla que sostiene "ningún caso llega a cerrado por un camino que
      nadie diseñó".
    source: FR1.4, AC4.10.1

  - id: BR3.3
    statement: >
      La única vuelta atrás es de derivado a en captura, y solo con las cuatro
      condiciones a la vez: el motivo es el límite de la demostración, no han
      pasado quince minutos desde el fin de la llamada, es el mismo navegador, y
      no se ha iniciado ninguna decisión.
    category: constraint
    applies_to: Case
    trigger: "Al pedir la vuelta de derivado a en captura."
    logic: >
      SI motivo = `demo_limit` Y transcurrido <= 15 minutos Y el navegador es el
      mismo Y no hay decisión iniciada ENTONCES la transición se aplica; SI NO,
      se rechaza dejando entrada.
    violation: >
      Se rechaza. Si el caso ya se decidió no se retoma, y la agente cuenta la
      decisión en vez de volver a capturar.
    source: ADR-005, AC5.12.2, FR8.5

  - id: BR3.4
    statement: >
      Un caso cerrado lleva exactamente una resolución del conjunto cerrado:
      registrado, aprobado, rechazado o enviado a la aseguradora.
    category: constraint
    applies_to: Case
    trigger: "Al cerrar el caso."
    logic: >
      SI el estado pasa a `closed` sin exactamente una resolución del conjunto
      ENTONCES se rechaza el cierre.
    violation: "Se rechaza dejando entrada."
    source: AC4.10.2, D18

  - id: BR3.5
    statement: >
      Un caso que no está cerrado no lleva resolución.
    category: constraint
    applies_to: Case
    trigger: "En cualquier escritura del caso."
    logic: >
      SI el estado no es `closed` Y hay resolución ENTONCES se rechaza.
    violation: "Se rechaza la escritura."
    source: AC4.10.2

  - id: BR3.6
    statement: >
      La etiqueta que lee una persona sale del catálogo de textos en su idioma.
      Ninguna pantalla, transcripción ni exportación imprime el valor del enum.
    category: policy
    applies_to: "Case.state, Case.resolution, Case.record_type, Case.derivation_reason"
    trigger: "Al mostrar el caso a una persona."
    logic: >
      SI se va a mostrar un estado, una resolución, un tipo de registro o un
      motivo de derivación ENTONCES se resuelve por su clave en el catálogo, en
      el idioma de la conversación.
    violation: "El chequeo de claves sin consumidor y el de paridad lo detectan."
    source: AC4.10.2, convención 4 del equipo

  - id: BR3.7
    statement: >
      El motivo de derivación es un conjunto cerrado y versionado: límite de la
      demostración, solicitud de persona, y regla de la aseguradora. Derivar sin
      un motivo de esa lista se rechaza.
    category: constraint
    applies_to: Case
    trigger: "Al derivar el caso."
    logic: >
      SI el estado pasa a `derived` sin un motivo de la lista ENTONCES se
      rechaza.
    violation: >
      Se rechaza. Un motivo en texto libre haría que la regla de la vuelta atrás
      leyera una cadena que nadie controla, y el modelo dejaría de ser cerrado.
      Añadir un cuarto motivo es un cambio a esta lista, igual que a la tabla de
      transiciones.
    source: ADR-005, AC1.9.1, FR6.1

  - id: BR3.8
    statement: >
      Un caso derivado porque la persona pidió hablar con alguien lleva
      prioridad alta.
    category: policy
    applies_to: Case
    trigger: "Al derivar con motivo solicitud de persona."
    logic: >
      SI el motivo de derivación es `person_requested` ENTONCES la prioridad
      queda en `high`.
    violation: "No aplica: es la conducta."
    source: AC1.9.1

  - id: BR3.9
    statement: >
      Un caso derivado conserva todo lo capturado: sus campos con su estado, sus
      partes y su transcripción hasta ese momento.
    category: constraint
    applies_to: Case
    trigger: "Al derivar el caso."
    logic: >
      SI el caso se deriva ENTONCES ningún campo, parte ni turno se borra ni se
      reinicia.
    violation: "No aplica: es la conducta. Se comprueba recuperando el caso derivado."
    source: AC1.9.4

  # --- BR4: número de caso, canal y origen -----------------------------------

  - id: BR4.1
    statement: >
      El número de caso es el prefijo de tres letras de la aseguradora, un guion
      y seis dígitos. El prefijo vive en la configuración de la aseguradora.
    category: constraint
    applies_to: CaseNumber
    trigger: "Al crear el caso."
    logic: >
      SI la configuración de la aseguradora no declara su prefijo de tres letras
      ENTONCES el arranque falla nombrándola.
    violation: >
      El aplicativo no arranca. Escribir el prefijo en el código sería una rama
      por aseguradora, que el proyecto prohíbe.
    source: FR1.5, ADR-005, Q1 del diseño funcional

  - id: BR4.2
    statement: >
      Los tres prefijos de la demostración son STO para Stonecroft Mutual, SUN
      para Sunmeadow Auto y KNO para Knotwell Insurance Agency.
    category: constraint
    applies_to: "Configuración de la aseguradora"
    trigger: "Al validar la configuración."
    logic: >
      SI dos aseguradoras declaran el mismo prefijo ENTONCES el arranque falla.
    violation: >
      El aplicativo no arranca. Se eligieron tres letras que no se confunden al
      dictarse, en lugar de las de las maquetas (SMU y SMA), que se diferencian
      en una sola letra y nombran aseguradoras distintas.
    source: Q1 del diseño funcional, FR1.5

  - id: BR4.3
    statement: >
      El número de caso es único dentro de la aseguradora, no se reutiliza, y no
      cambia nunca después de crearse.
    category: constraint
    applies_to: Case
    trigger: "Al crear el caso y en cualquier escritura posterior."
    logic: >
      SI el número ya existe en esa aseguradora, o SI se pide cambiarlo ENTONCES
      se rechaza.
    violation: >
      Se rechaza. Es el número que la persona anotó y con el que retoma su caso;
      cambiarlo la deja sin forma de volver.
    source: FR1.5, AC1.20.1

  - id: BR4.4
    statement: >
      El caso registra el canal por el que nació, voz o chat, y cada turno
      registra el suyo. Un caso empezado por voz y retomado por chat conserva
      voz como canal del caso.
    category: constraint
    applies_to: "Case, TranscriptTurn"
    trigger: "Al crear el caso y al anexar cada turno."
    logic: >
      SI el canal pedido no es `voice` ni `chat` ENTONCES se rechaza.
    violation: "Se rechaza la escritura."
    source: AC4.10.4, AC1.20.4

  - id: BR4.5
    statement: >
      El caso registra su origen, que es uno de cuatro: chat público, consola
      pública de la voz, despliegue local, o generador de datos sintéticos.
    category: constraint
    applies_to: Case
    trigger: "Al crear el caso."
    logic: >
      SI el origen pedido no está en los cuatro ENTONCES el caso no se crea.
    violation: "Se rechaza la creación."
    source: AC4.10.4

  - id: BR4.6
    statement: >
      Un caso de origen chat público o consola pública es dato de visitante. Los
      de despliegue local y generador no lo son.
    category: policy
    applies_to: Case
    trigger: "En el reinicio nocturno."
    logic: >
      SI el origen es `public_chat` o `public_voice_console` ENTONCES el caso y
      todo lo que cuelga de él se borra en el reinicio; SI NO, se conserva.
    violation: >
      No aplica: es la conducta. Comprobarla es lo que mantiene acotada la
      retención de la superficie pública.
    source: AC4.10.4, NFR19, FR12.6

  # --- BR5: historial de cambios ---------------------------------------------

  - id: BR5.1
    statement: >
      Todo cambio de un campo deja una entrada con qué campo cambió, de qué
      valor a cuál, quién lo hizo, cuándo y desde qué canal.
    category: constraint
    applies_to: CaseChange
    trigger: "Al escribir el valor de un campo."
    logic: >
      SI se escribe un campo ENTONCES se anexa una entrada de tipo cambio de
      campo con esos cinco datos.
    violation: "La escritura falla si no se pudo anexar la entrada. Un cambio sin rastro no es un cambio: es una pérdida."
    source: FR1.6

  - id: BR5.2
    statement: >
      Un cambio hecho con credencial apunta a la persona de la bandeja que lo
      hizo. Uno hecho por la agente o por el sistema apunta a su tipo de actor,
      sin persona.
    category: constraint
    applies_to: CaseChange
    trigger: "Al anexar una entrada del historial."
    logic: >
      SI el tipo de actor es `staff` Y no hay identificador de la persona
      ENTONCES se rechaza la entrada.
    violation: "Se rechaza. Una corrección sin autor no se puede auditar."
    source: FR1.6, catálogo de componentes

  - id: BR5.3
    statement: >
      El historial es de solo anexar: una entrada no se edita ni se borra.
    category: constraint
    applies_to: CaseChange
    trigger: "En cualquier escritura sobre el historial."
    logic: >
      SI se pide editar o borrar una entrada ENTONCES se rechaza.
    violation: >
      Se rechaza. El borrado del reinicio nocturno es la única excepción, y borra
      el caso entero, no una entrada suelta.
    source: FR1.6, NFR19

  - id: BR5.4
    statement: >
      Un intento de transición rechazado y un cierre rechazado por falta de un
      adjunto también dejan entrada, aunque el caso no cambie.
    category: constraint
    applies_to: CaseChange
    trigger: "Al rechazar una transición o un cierre."
    logic: >
      SI una transición o un cierre se rechaza ENTONCES se anexa una entrada de
      su tipo con el detalle de lo que se intentó.
    violation: >
      No aplica: es la conducta. Sin ella, un rechazo sería invisible y nadie
      sabría que alguien lo intentó.
    source: AC4.10.1, FR1.7

  # --- BR6: transcripción y adjuntos del cierre ------------------------------

  - id: BR6.1
    statement: >
      La transcripción guarda el turno ya redactado. Guardar texto sin redactar
      no es un error de ejecución: no se puede expresar.
    category: constraint
    applies_to: TranscriptTurn
    trigger: "Al anexar un turno."
    logic: >
      SI el texto del turno no es del tipo redactado ENTONCES no compila.
    violation: >
      El chequeo de tipos falla antes de ejecutar. Es la diferencia entre una
      regla que se comprueba y una que se recuerda.
    source: C-12, C-13, M6

  - id: BR6.2
    statement: >
      Cada turno guarda quién habló, por qué canal, en qué idioma, cuándo empezó
      y terminó, y si fue interrumpido.
    category: constraint
    applies_to: TranscriptTurn
    trigger: "Al anexar un turno."
    logic: >
      SI falta cualquiera de los datos obligatorios del turno ENTONCES se
      rechaza.
    violation: "Se rechaza el anexado."
    source: FR1.7, catálogo de componentes

  - id: BR6.3
    statement: >
      Cerrar un caso exige los cinco adjuntos: transcripción, cláusulas citadas,
      reglas disparadas, identificador de traza y resultado de los controles. Un
      adjunto vacío cuenta como presente; uno no evaluado, no.
    category: constraint
    applies_to: ClosingEvidence
    trigger: "Al cerrar el caso."
    logic: >
      SI alguno de los cinco adjuntos está en `not_evaluated` ENTONCES el cierre
      se rechaza; SI todos están en `present` o `empty` ENTONCES el cierre
      procede.
    violation: >
      Se rechaza dejando entrada con el adjunto que faltaba. La distinción entre
      vacío y no evaluado es la misma que el equipo ya mantiene entre "no hay
      cláusula" y "no pude verificar": colapsarlas dejaría cerrar casos que nadie
      revisó.
    source: FR1.7, Q4 del diseño funcional, convención 8c del equipo

  - id: BR6.4
    statement: >
      La evidencia de cierre se guarda con el caso y no cambia después. Un caso
      cerrado expone qué se comprobó al cerrarlo.
    category: constraint
    applies_to: Case
    trigger: "Al cerrar el caso y en cualquier escritura posterior."
    logic: >
      SI el caso ya tiene evidencia de cierre Y se pide cambiarla ENTONCES se
      rechaza.
    violation: "Se rechaza la escritura."
    source: FR1.7

  # --- BR7: aislamiento y datos de visitante ---------------------------------

  - id: BR7.1
    statement: >
      Cada caso pertenece a una sola aseguradora y toda consulta sobre él pasa
      por el punto único de sesión que la fija. Esta unidad no abre ninguna
      conexión propia.
    category: authorization
    applies_to: "Todas las entidades de la unidad"
    trigger: "En cualquier lectura o escritura."
    logic: >
      SI se pide una conexión fuera del punto único de U2 ENTONCES la regla de
      importación falla.
    violation: "El linter y la regla de importación fallan antes de ejecutar."
    source: FR9.1, M9, convención 7 del equipo

  - id: BR7.2
    statement: >
      Las cinco tablas de esta unidad llevan la marca de dato de visitante y su
      purgador, para que el reinicio nocturno borre los casos de origen público
      con todo lo que cuelga de ellos.
    category: policy
    applies_to: "Todas las entidades de la unidad"
    trigger: "En la aserción de esquema y en el reinicio nocturno."
    logic: >
      SI una tabla de esta unidad lleva la marca y no tiene purgador registrado
      ENTONCES la prueba de U2 falla.
    violation: >
      La prueba falla nombrando la tabla. Es lo que impide que una tabla nueva
      quede fuera del borrado sin que nadie lo note.
    source: C-11, NFR19, UG-3

  - id: BR7.3
    statement: >
      Pedir un caso de otra aseguradora responde igual que pedir uno que no
      existe: no se distingue el "no está" del "no es suyo".
    category: authorization
    applies_to: Case
    trigger: "Al consultar un caso por su identificador o por su número."
    logic: >
      SI el caso no existe, o existe en otra aseguradora ENTONCES la respuesta es
      la misma.
    violation: >
      No aplica: es la conducta. Distinguirlas confirmaría a quien sondea que el
      caso existe, que es el escenario RT-4.
    source: ADR-005, RT-4, NFR10
```

## Resumen

| ID | Regla | Categoría | Fuente |
| --- | --- | --- | --- |
| BR1.1 | Tres tipos de registro y solo tres | constraint | FR1.1, ADR-005 |
| BR1.2 | El tipo de registro no cambia | constraint | FR1.3, AC4.10.3 |
| BR1.3 | El esquema por tipo vive en archivo versionado | policy | FR1.1, FR1.3 |
| BR1.4 | El siniestro declara sus siete campos centrales | constraint | FR1.1 |
| BR1.5 | La consulta de cobertura declara dos campos | constraint | AC1.3.6, AC2.4.3 |
| BR1.6 | Sin campos declarados no se crea el caso | constraint | U4, FR13 |
| BR1.7 | Las partes se guardan y se recuperan íntegras | constraint | FR1.2, AC1.8.1 |
| BR1.8 | Un atributo que no se sabe queda pendiente | validation | AC1.8.2 |
| BR2.1 | Tres estados por campo | constraint | FR1.3, ADR-005 |
| BR2.2 | Lesiones, lugar y conductor exigen confirmación | constraint | FR1.3, ADR-005 |
| BR2.3 | "Ninguno" y cero solo si alguien los dijo | validation | ADR-005, AC1.8.4 |
| BR2.4 | Todo campo dicho lleva exactamente una evidencia | constraint | FR1.3, Q3 |
| BR2.5 | Corrección de la bandeja deja el campo confirmado | policy | FR1.6, Q3 |
| BR2.6 | Completo es el estado que ese campo exige | calculation | FR1.3, Q2 |
| BR2.7 | La completitud se cuenta según el tipo de registro | calculation | FR1.3, AC4.10.3 |
| BR2.8 | La completitud se deriva, no se guarda | constraint | FR1.3 |
| BR3.1 | Siete estados y solo siete | constraint | FR1.4, ADR-005 |
| BR3.2 | Transición no declarada se rechaza dejando evento | constraint | FR1.4, AC4.10.1 |
| BR3.3 | Única vuelta atrás, con cuatro condiciones a la vez | constraint | ADR-005, AC5.12.2 |
| BR3.4 | Cerrado lleva exactamente una resolución | constraint | AC4.10.2, D18 |
| BR3.5 | No cerrado no lleva resolución | constraint | AC4.10.2 |
| BR3.6 | La etiqueta sale del catálogo, nunca del enum | policy | AC4.10.2 |
| BR3.7 | El motivo de derivación es conjunto cerrado | constraint | ADR-005, AC1.9.1 |
| BR3.8 | Solicitud de persona deriva con prioridad alta | policy | AC1.9.1 |
| BR3.9 | Derivar no pierde nada de lo capturado | constraint | AC1.9.4 |
| BR4.1 | Prefijo de tres letras desde la configuración | constraint | FR1.5, Q1 |
| BR4.2 | Los tres prefijos son STO, SUN y KNO | constraint | Q1, FR1.5 |
| BR4.3 | El número es único, no se reutiliza y no cambia | constraint | FR1.5, AC1.20.1 |
| BR4.4 | Canal del caso y canal de cada turno | constraint | AC4.10.4, AC1.20.4 |
| BR4.5 | El origen es uno de cuatro | constraint | AC4.10.4 |
| BR4.6 | Origen público es dato de visitante | policy | AC4.10.4, NFR19 |
| BR5.1 | Todo cambio de campo deja su entrada | constraint | FR1.6 |
| BR5.2 | Un cambio con credencial apunta a su persona | constraint | FR1.6 |
| BR5.3 | El historial es de solo anexar | constraint | FR1.6, NFR19 |
| BR5.4 | Los rechazos también dejan entrada | constraint | AC4.10.1, FR1.7 |
| BR6.1 | La transcripción guarda texto ya redactado | constraint | C-12, C-13 |
| BR6.2 | Cada turno guarda sus datos obligatorios | constraint | FR1.7 |
| BR6.3 | Cerrar exige los cinco adjuntos; vacío cuenta | constraint | FR1.7, Q4 |
| BR6.4 | La evidencia de cierre se guarda y no cambia | constraint | FR1.7 |
| BR7.1 | Toda consulta pasa por el punto único de sesión | authorization | FR9.1, M9 |
| BR7.2 | Las cinco tablas llevan marca y purgador | policy | C-11, UG-3 |
| BR7.3 | Un caso ajeno responde como uno inexistente | authorization | RT-4, NFR10 |
