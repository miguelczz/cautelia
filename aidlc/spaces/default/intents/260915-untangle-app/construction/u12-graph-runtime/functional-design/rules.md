# Reglas de negocio — U12 `graph-runtime`

U12 es la unidad que hace que los cuatro nodos sean un sistema. No añade
conducta de cara al asegurado: añade **el orden en que la conducta ocurre**, y
lo que pasa cuando algo de ese orden falla.

Seis familias. La primera es la promesa que el proyecto entero hace sobre sí
mismo —que el orquestador es código y no un modelo con texto libre— y las cinco
siguientes son lo que hace falta para que esa promesa sobreviva a un reinicio, a
un proveedor caído y a una conversación abandonada a mitad.

## Reglas

```yaml
rules:

  - id: BR1.1
    statement: El grafo se arma desde las especificaciones de los nodos, no desde una lista escrita a mano.
    category: constraint
    applies_to: "La composicion del grafo"
    trigger: "Al arrancar el proceso."
    logic: "Los nodos son exactamente cuatro --intake, policy_verification, decision, compliance-- y lo que el grafo sabe de cada uno sale de su NodeSpec: que lee, que escribe, en que ritmo corre y su politica de fallo. Una lista paralela se desincroniza con el primer nodo que cambie su conjunto de escritura, y nadie se enteraria hasta que un campo dejara de escribirse."
    violation: "La prueba de AC4.9.1 falla, que lista los nodos del grafo y comprueba que cada uno declara su contrato."
    source: AC4.9.1, FR2.1, M2

  - id: BR1.2
    statement: La transicion es una funcion pura que devuelve un nombre de nodo de un conjunto cerrado.
    category: constraint
    applies_to: "La funcion de transicion"
    trigger: "Despues de cada nodo."
    logic: "Recibe solo campos del estado tipado y devuelve un valor de NodeName. Ningun cliente de modelo, ningun canal y ningun SDK de proveedor aparece en su cadena de llamadas, y eso lo comprueba una regla de importacion y no la disciplina de quien escribe."
    violation: "La prueba de AC4.9.2 falla, o el contrato de import-linter se rompe."
    source: AC4.9.2, FR2.1, M2

  - id: BR1.3
    statement: Un texto del modelo nunca elige la ruta.
    category: security
    applies_to: "La funcion de transicion"
    trigger: "Cuando la respuesta del modelo contiene algo que parece una instruccion de ruta."
    logic: "La ruta la fijan los campos del estado. Un turno sembrado en el que el modelo devuelve 'ir a decision' o 'aprobar este caso' produce la misma transicion que el mismo estado sin ese texto. Es la forma que toma RT-1 dentro del orquestador: la inyeccion no necesita convencer a una persona, le basta convencer a un enrutador."
    violation: "La prueba de AC4.9.3 falla."
    source: AC4.9.3, RT-1, P3

  - id: BR1.4
    statement: El texto de la persona viaja como campo del estado, nunca como instruccion.
    category: security
    applies_to: "GraphState"
    trigger: "En cada turno."
    logic: "Entra en un campo delimitado del estado tipado y de ahi lo toma el nodo que lo necesite. El runtime no arma prompts: los arman los nodos, y ninguno concatena ese campo a su instruccion de sistema."
    violation: "La prueba de AC4.9.3 falla; y la de los nodos, que ya existe en cada unidad."
    source: AC4.9.3, RT-1, RT-2, ADR-020

  - id: BR1.5
    statement: Dos nodos no escriben el mismo campo, y la composicion falla al arrancar si lo intentan.
    category: constraint
    applies_to: "GraphState"
    trigger: "Al componer el estado tipado."
    logic: "Cada nodo cambia solo los campos de su conjunto de escritura, a traves de su valor de retorno; el runtime no muta el estado en el lugar. Si dos NodeSpec declaran el mismo campo, el proceso **no arranca**: un choque descubierto en produccion es un campo que un nodo le pisa a otro a mitad de una conversacion, y eso no deja rastro."
    violation: "La prueba de AC4.9.5 falla."
    source: AC4.9.5, FR2.2, convencion 6

  - id: BR1.6
    statement: Un solo grafo para los dos canales, con el mismo registro final.
    category: constraint
    applies_to: "El grafo"
    trigger: "Cuando el mismo caso corre por texto y por voz."
    logic: "El nucleo no importa canales: los canales le entregan turnos por C-14 y reciben eventos. Un caso sembrado de DS-2 que corre por el adaptador de texto y por el de voz con el reconocedor simulado produce el mismo registro final."
    violation: "La prueba de AC4.9.4 falla, o el contrato de import-linter que prohibe que el nucleo importe un canal."
    source: AC4.9.4, FR2.6, M2

  - id: BR2.1
    statement: La precarga del trabajo de fondo arranca al confirmarse la identidad.
    category: policy
    applies_to: "El ritmo de fondo"
    trigger: "Cuando la captura confirma la poliza."
    logic: "La verificacion de poliza empieza antes de que exista una pregunta de cobertura, y su tramo aparece en la traza como de fondo. Esperar a la pregunta para empezar es lo que obliga a dejar a la persona en silencio mientras se busca."
    violation: "La prueba de AC1.25.1 falla."
    source: AC1.25.1, FR2.3, M12

  - id: BR2.2
    statement: El turno nunca espera al trabajo de fondo.
    category: constraint
    applies_to: "El ritmo del turno"
    trigger: "Siempre."
    logic: "Con la verificacion retrasada a proposito, el turno siguiente se compone y sale igual. El turno lee lo que el estado ya tiene; si lo que necesita no llego, emite la frase de espera (BR2.4), nunca se bloquea."
    violation: "La prueba de AC1.25.2 falla, con el retardo inyectado."
    source: AC1.25.2, FR2.3, P4

  - id: BR2.3
    statement: Dentro del turno solo corren los tres controles baratos.
    category: constraint
    applies_to: "El manejador del turno"
    trigger: "En cada turno."
    logic: "La guardia de salida, la deteccion de peticion de persona y la de emergencia, cada una con su presupuesto de latencia declarado. Nunca la verificacion de poliza, ni las reglas, ni la revision completa de cumplimiento: los tres son del ritmo de fondo (D22). Se comprueba analizando la cadena de llamadas, no leyendo el codigo."
    violation: "La prueba de AC1.25.4 falla."
    source: AC1.25.4, D22, P4, R2

  - id: BR2.4
    statement: Si el turno necesita un resultado que no llego, dice la frase de espera antes de dos segundos de silencio.
    category: policy
    applies_to: "El ritmo del turno"
    trigger: "Cuando una pregunta de cobertura llega y la verificacion todavia corre."
    logic: "La frase sale del catalogo por idioma y el reloj se mide del fin del habla al primer audio. Dos segundos no es una preferencia de estilo: es el punto en el que una persona al telefono cree que la llamada se cayo."
    violation: "La prueba de AC1.25.3 falla; y la latencia publicada de esta unidad lo muestra."
    source: AC1.25.3, FR2.3, M12

  - id: BR2.5
    statement: Todo texto hacia la persona sale por el punto unico de salida.
    category: security
    applies_to: "Cada evento de C-14"
    trigger: "Siempre, incluidos los caminos de degradacion y de error."
    logic: "El punto unico aplica los tres controles del turno (C-20) y emite desde el catalogo. Un camino de error que escribiera directo al canal seria un punto de salida nuevo sin guardia, que es lo que la regla del proyecto hace imposible por construccion y no detectable por disciplina."
    violation: "La prueba de AC2.10.1 falla --el mensaje de degradacion tiene que venir pasado por la guardia-- y el chequeo de puntos de salida de U3."
    source: AC2.10.1, FR7.6, M6, P6

  - id: BR3.1
    statement: Hay un punto de control por caso despues de cada turno.
    category: constraint
    applies_to: "GraphCheckpoint"
    trigger: "Al terminar cada turno."
    logic: "Un caso es un hilo del grafo. El punto de control se escribe despues del turno y no durante: escribirlo a mitad guardaria un estado que ningun turno produjo."
    violation: "La prueba de AC1.19.4 falla."
    source: AC1.19.4, FR2.4, M16

  - id: BR3.2
    statement: Reanudar no vuelve a preguntar lo confirmado.
    category: policy
    applies_to: "La reanudacion"
    trigger: "Cuando la persona vuelve, o cuando el proceso se reinicia."
    logic: "Se lee el ultimo punto de control del caso y se sigue desde ahi. El bloque que toca lo deduce la captura de la completitud del caso (BR3.2 de U11), asi que reanudar no necesita nada mas que el punto de control: no hay un contador que reconciliar."
    violation: "Las pruebas de AC1.19.2 y AC1.19.4 fallan."
    source: AC1.19.2, AC1.19.4, ADR-003

  - id: BR3.3
    statement: Una sesion abandonada deja el caso esperando al asegurado, con su motivo, y sin decidir nada.
    category: policy
    applies_to: "Case (U4)"
    trigger: "Cuando la conexion se cierra o pasan los minutos de inactividad que fija la configuracion."
    logic: "El caso queda en 'esperando al asegurado' con su completitud real y el motivo en la traza. **No se aplica ninguna categoria ni revision de cierre sobre datos incompletos**: decidir sobre la mitad de un reporte es peor que no decidir, porque produce una decision con aspecto de completa."
    violation: "La prueba de AC1.19.1 falla."
    source: AC1.19.1, FR1.4, FR7.1

  - id: BR3.4
    statement: La poliza de ejemplo no abre el caso de otra persona.
    category: security
    applies_to: "La reanudacion"
    trigger: "Cuando dos navegadores distintos se identifican con la misma poliza de ejemplo."
    logic: "El caso se ofrece por el origen que lo creo, no por la poliza. Al segundo navegador no se le ofrece ni se le revela el caso del primero, y la respuesta es **identica, en texto y en estado**, a la de una sesion sin casos abiertos: una respuesta distinta ya dice que existe algo. Las tres polizas de ejemplo son publicas a proposito (F8.7), asi que esta es la unica cosa que separa un caso de un visitante del de otro."
    violation: "Compuerta dura: AC1.19.3 detiene la entrega."
    source: AC1.19.3, RT-4, M9, F8.7

  - id: BR3.5
    statement: Un numero de caso de otro canal no se promete.
    category: policy
    applies_to: "La reanudacion por chat"
    trigger: "Cuando alguien escribe en el chat un numero de caso y la continuidad entre canales no esta activa."
    logic: "El chat explica como retomarlo por el canal donde empezo, sin prometer que puede retomarlo aqui. Prometer y no poder es la forma mas cara de fallar: la persona vuelve a contar el accidente."
    violation: "La prueba de AC1.19.5 falla."
    source: AC1.19.5, P7

  - id: BR4.1
    statement: La pausa hacia la bandeja lleva su motivo, del conjunto cerrado.
    category: policy
    applies_to: "HumanReviewRequest"
    trigger: "Cuando cumplimiento deriva, cuando la captura cierra por abuso, cuando un proveedor agota su politica o cuando la captura queda incompleta."
    logic: "Se pausa el grafo con interrupt() y se abre la solicitud con su motivo. Una bandeja que recibe casos sin motivo obliga a quien la atiende a reconstruir por que llegaron."
    violation: "La prueba de la pausa y su motivo falla."
    source: AC2.4.3, M11, P1

  - id: BR4.2
    statement: Una pregunta de cobertura a mitad del reporte no descarrila la captura.
    category: policy
    applies_to: "El orden de la captura"
    trigger: "Cuando la persona pregunta por su cobertura mientras reporta."
    logic: "El turno responde con la cita verificada que el ritmo de fondo ya dejo en el estado, aclara que la cobertura la confirma un ajustador, y el bloque preguntado en el turno siguiente --leido del estado-- es el que estaba pendiente. El desvio no escribe ningun campo de la captura, y por eso volver no necesita recordar nada."
    violation: "El eje de DS-2 de pregunta de cobertura durante el reporte falla."
    source: AC2.4.1, FR4.2, M4

  - id: BR4.3
    statement: Dos preguntas de cobertura seguidas vuelven una sola vez al bloque pendiente.
    category: policy
    applies_to: "El orden de la captura"
    trigger: "Cuando llegan dos preguntas de cobertura seguidas."
    logic: "Cada una se responde y el bloque pendiente sigue siendo el mismo. Volver dos veces significaria repetir la pregunta del bloque, que es la queja que US1.5 existe para evitar."
    violation: "La prueba de AC2.4.2 falla."
    source: AC2.4.2, FR4.2

  - id: BR4.4
    statement: Una pausa se retira cuando la persona vuelve dentro de su ventana.
    category: policy
    applies_to: "HumanReviewRequest"
    trigger: "Cuando una llamada cortada por el limite de la demostracion se retoma dentro de su ventana."
    logic: "La solicitud queda `withdrawn` con su hora, y el caso sigue. `withdrawn` y `resolved` no se colapsan: la segunda dice que una persona la decidio, y decir eso de una pausa que se retiro sola es escribir en el historial algo que no paso."
    violation: "La prueba del retiro de la pausa falla."
    source: AC2.4.3, F8.5

  - id: BR5.1
    statement: La politica de fallo de cada nodo es dato, y la aplica un ejecutor comun.
    category: constraint
    applies_to: "El ejecutor de nodos"
    trigger: "En cada ejecucion de nodo."
    logic: "Tiempo maximo, intentos y texto de degradacion salen del NodeSpec. Un nodo no captura su propio fallo para seguir adelante: deja subir la excepcion. El ejecutor **no ramifica por nombre de nodo**; toda diferencia entre nodos viaja en su especificacion (FD-U12-2)."
    violation: "La prueba con fallos inyectados falla, o aparece un `if` por nombre de nodo en el ejecutor."
    source: AC2.10.1, FR2.7, convencion 8b

  - id: BR5.2
    statement: Un reintento, y despues el texto de degradacion del catalogo pasado por la guardia.
    category: policy
    applies_to: "El ejecutor de nodos"
    trigger: "Cuando un nodo agota su politica."
    logic: "Uno y no mas. Despues se emite la clave de degradacion que el nodo declara, por el punto unico de salida, y el turno se cierra con TurnError: el turno nunca queda abierto en silencio."
    violation: "Las pruebas de AC2.10.1 y AC2.10.2 fallan."
    source: AC2.10.1, AC2.10.2, PRD 12.3

  - id: BR5.3
    statement: Un fallo conserva el caso y lo que la persona escribio, y deja doble rastro.
    category: policy
    applies_to: "El caso y la traza"
    trigger: "Cuando algo falla a mitad de la conversacion."
    logic: "El caso y el texto del turno se conservan; la traza registra el nodo, el tipo de error de la taxonomia cerrada y el intento. Doble rastro: un valor distinguible en el caso y un evento en la traza. Perder lo que la persona ya conto por un fallo que no es suyo es el unico desenlace inaceptable."
    violation: "La prueba de AC2.10.1 falla."
    source: AC2.10.1, FR2.7, PRD 12.2

  - id: BR5.4
    statement: Un relanzamiento no vuelve a gastar el proveedor por un trabajo que ya se hizo.
    category: constraint
    applies_to: "NodeRun"
    trigger: "Cuando el proceso muere y otro retoma el trabajo pendiente."
    logic: "Cada ejecucion lleva clave de idempotencia derivada del caso, el nodo y su entrada --nunca del reloj ni de un aleatorio-- y el barrido al arrancar relanza lo pendiente por esa clave. Sin ella, cada reinicio del hospedaje gratuito se paga otra vez contra un tope de 5 USD."
    violation: "La prueba del barrido falla, o el gasto registrado duplica el trabajo."
    source: ADR-004, M20, D-015

  - id: BR5.5
    statement: Un arrendamiento sin latido se considera muerto y otro proceso lo toma.
    category: constraint
    applies_to: "NodeRun"
    trigger: "Cuando el arrendamiento de una ejecucion vence."
    logic: "El proceso que ejecuta renueva su latido; el barrido toma lo vencido y lo marca `abandoned`, distinto de `degraded`. Sin latido, un arrendamiento vencido es indistinguible de un proceso vivo que va lento, y el barrido tendria que elegir entre duplicar trabajo o dejarlo colgado para siempre."
    violation: "La prueba del arrendamiento vencido falla."
    source: ADR-004

  - id: BR5.6
    statement: La base caida se ve como pagina de estado, sin detalles tecnicos.
    category: security
    applies_to: "Las tres superficies"
    trigger: "Cuando la base de datos no esta disponible."
    logic: "El chat, la bandeja y la consola muestran la pagina de estado del catalogo. Ningun detalle tecnico del error llega a una superficie publica: un mensaje de error de base de datos dice el nombre del servidor, del esquema y a veces de la consulta."
    violation: "La prueba de AC2.10.5 falla."
    source: AC2.10.5, P6

  - id: BR6.1
    statement: Las tres tablas de esta unidad llevan aseguradora, aislamiento habilitado y forzado, y su prueba.
    category: security
    applies_to: "graph_checkpoint, human_review_request, node_run"
    trigger: "Siempre."
    logic: "Columna de aseguradora propia, politica de fila, FORCE ROW LEVEL SECURITY y una prueba que intenta leer una fila de otra aseguradora. El punto de control es el caso mas delicado del proyecto en esto, porque lo escribe el checkpointer del framework y no el codigo del aplicativo (FD-U12-3)."
    violation: "La asercion de esquema falla, o la prueba de aislamiento pasa cuando no deberia."
    source: PA-3, M9, F9.1, F9.4

  - id: BR6.2
    statement: Hay un tramo por turno y uno por nodo, con su costo, su latencia y sus tokens.
    category: constraint
    applies_to: "La traza"
    trigger: "En cada turno y en cada ejecucion de nodo."
    logic: "El tramo lleva el nombre del nodo con la misma grafia que el modulo y el reporte (convencion 3), el modelo y el precio de lista usados. Es lo que hace que una latencia publicada tenga de donde salir."
    violation: "La prueba de la traza por nodo falla."
    source: M7, M20, P9

  - id: BR6.3
    statement: El punto de control va cifrado en reposo, con el mismo cifrador del caso.
    category: security
    applies_to: "GraphCheckpoint.payload"
    trigger: "Al escribir cada punto de control."
    logic: "El estado serializado lleva dentro el texto de la persona. Una tabla del grafo no es menos sensible que la del caso por vivir en otro modulo, y dejarla en claro seria guardar sin cifrar justo la copia que nadie mira."
    violation: "La asercion de esquema falla; la prueba que lee la fila en claro pasa cuando no deberia."
    source: M10, F7.3, R7

  - id: BR6.4
    statement: Los datos de visitante de esta unidad se borran con el contrato de borrado de U2.
    category: policy
    applies_to: "Las tres tablas"
    trigger: "En el reinicio nocturno y cuando se borra un caso de visitante."
    logic: "Los puntos de control, las pausas y las ejecuciones de nodo de un caso de visitante se borran con el caso. Una unidad que guarda datos de visitante y no implementa ese contrato deja copias que nadie recuerda (UG-3)."
    violation: "La prueba del contrato de borrado falla."
    source: UG-3, M10, R7
```

## Resumen

| Regla | En una línea |
| --- | --- |
| BR1.1 | El grafo se arma desde las especificaciones de los nodos |
| BR1.2 | La transición es pura y devuelve uno de cuatro nombres |
| BR1.3 | Un texto del modelo nunca elige la ruta |
| BR1.4 | El texto de la persona es dato del estado, nunca instrucción |
| BR1.5 | Dos nodos no escriben el mismo campo, y el proceso no arranca si lo intentan |
| BR1.6 | Un grafo, dos canales, el mismo registro final |
| BR2.1 | La precarga arranca al confirmarse la identidad |
| BR2.2 | El turno nunca espera al trabajo de fondo |
| BR2.3 | Dentro del turno solo corren los tres controles baratos |
| BR2.4 | Frase de espera antes de dos segundos de silencio |
| BR2.5 | Todo texto sale por el punto único de salida |
| BR3.1 | Un punto de control por caso después de cada turno |
| BR3.2 | Reanudar no vuelve a preguntar lo confirmado |
| BR3.3 | La sesión abandonada no decide nada sobre datos incompletos |
| BR3.4 | La póliza de ejemplo no abre el caso de otra persona |
| BR3.5 | Un número de caso de otro canal no se promete |
| BR4.1 | La pausa hacia la bandeja lleva su motivo |
| BR4.2 | Una pregunta de cobertura no descarrila la captura |
| BR4.3 | Dos preguntas seguidas vuelven una sola vez |
| BR4.4 | Una pausa se retira cuando la persona vuelve en su ventana |
| BR5.1 | La política de fallo es dato, y el ejecutor no ramifica por nodo |
| BR5.2 | Un reintento, y después el texto de degradación por la guardia |
| BR5.3 | Un fallo conserva el caso y deja doble rastro |
| BR5.4 | Un relanzamiento no gasta dos veces |
| BR5.5 | Un arrendamiento sin latido se considera muerto |
| BR5.6 | La base caída se ve como página de estado |
| BR6.1 | Las tres tablas llevan aislamiento, habilitado y forzado |
| BR6.2 | Un tramo por turno y por nodo |
| BR6.3 | El punto de control va cifrado en reposo |
| BR6.4 | Los datos de visitante se borran con el contrato de U2 |
