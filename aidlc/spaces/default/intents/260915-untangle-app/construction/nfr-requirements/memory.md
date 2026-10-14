<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
- 2026-09-20T19:45:00Z — U3: NFR11 mide lo que se escapa (cero hallazgos del segundo detector), no lo que se atrapa. Hacia falta ademas un objetivo propio que midiera la deteccion, o un reconocedor roto solo se veria el dia que algo se filtrara. De ahi NFR11.1, al 100 % pero solo sobre casos sembrados: un reconocedor que falla en su propio caso sembrado esta roto, no imperfecto.
- 2026-09-19T01:26:35Z — NFR17 se leyo como aplicable a U1 en calidad de medidor: la tabla de Units Generation la registra en U21, pero anota que U1 (el corredor) tambien la verifica, asi que aparece en la trazabilidad con esa distincion escrita.
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->

## Deviations
- 2026-09-20T19:45:00Z — U3: Presidio documenta `en_core_web_lg` como su modelo por defecto y se eligio `md`. La razon es medida y esta escrita: de `sm` a `lg` cuesta 923 MB entre los dos idiomas y compra menos de 1,3 puntos de acierto, sobre un despliegue que se duerme y reinicia cada noche. La documentacion de Presidio no da ninguna razon de acierto frente a tamano para su eleccion.
- 2026-09-20T19:45:00Z — U3: `sm` se descarto por algo que las cifras de acierto no muestran: los modelos `sm` de spaCy no traen vectores de palabra y los `md` si. Los bancos de prueba usan nombres frecuentes; el chat publico recibe nombres que el modelo nunca vio.
- 2026-09-19T01:26:35Z — Los controles de seguridad de U1 (cadena de suministro, secretos, permisos de la tuberia) no heredan un NFR de Incepcion porque ninguno los numero: nacen de reglas afirmadas del equipo y del proyecto. Se les dio identificador propio (SEC-U1.x) y se declararon en `reverse` de la trazabilidad, en vez de forzar una herencia que no existe.
- 2026-09-19T01:26:35Z — U1 no tiene disponibilidad ni carga concurrente que medir. En vez de inventar un porcentaje de disponibilidad, confiabilidad y escalabilidad se escribieron sobre lo que si crece y si se puede medir: determinismo, degradacion honesta y crecimiento del conjunto de casos.
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs
- 2026-09-20T19:45:00Z — U3: el techo de la regla de respaldo (1 de cada 10) no detiene la entrega. Tapar de mas es el lado seguro del error; lo que se compra midiendolo es la senal de que un reconocedor se rompio o de que falta uno para un formato frecuente.
- 2026-09-20T19:45:00Z — U3: el objetivo de retraso que pidio Miguel se partio en dos porque como estaba era inalcanzable por construccion. Un tope unico de 300 ms mezclaba lo que cuesta nuestro codigo (controlable) con lo que tarda una persona en dictar un telefono (no controlable), y solo se podria cumplir ensenando digitos. Rigen 100 ms de coste propio y 1 s antes de avisar, de los tres limites de respuesta de Nielsen.
- 2026-09-19T01:26:35Z — U1: cobertura como un solo numero ponderado por lineas en vez de dos umbrales por lenguaje. Se gana "el numero" del proyecto, que es el que se publica; se pierde que un lenguaje no pueda compensar al otro, y por eso el piso por modulo critico deja de ser opcional.
- 2026-09-19T01:26:35Z — U1: el escaneo del historial completo corre por hito y no en cada corrida. Ahorra minutos de integracion continua a cambio de una ventana en la que una clave vieja no se mira; se cierra con la pasada obligatoria antes de publicar.
- 2026-09-19T01:26:35Z — U1: en la tuberia el reporte se publica como artefacto y no se registra en base. La compuerta deja de depender de infraestructura, a costa de que el historial completo solo exista en local.
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
- 2026-09-20T19:45:00Z — U3: la redaccion es compuerta dura y NO esta en la lista de modulos criticos del piso de cobertura de `team.md`. Cambiar esa lista es cambiar una practica afirmada y pasa por Miguel; queda declarado en `security-requirements.md` para que se decida a la vista.
- 2026-09-20T19:45:00Z — U3: el comprobador de trazabilidad resuelve los NFR del proyecto entero sin acotar por unidad, asi que exige declarar los 19 ajenos. El archivo de U2 tiene el mismo hueco y falla con 17 hallazgos; su etapa esta cerrada y no se toca.
- 2026-09-19T01:26:35Z — U1: el piso por modulo critico (NFR18.2) no aplica todavia porque los cuatro modulos criticos llegan con U2, U4, U8 y U9. Hay que comprobar al construir esas unidades que el comando de cobertura ya tiene su umbral por modulo y no solo el agregado.
- 2026-09-19T01:26:35Z — U1: la meta de 15 minutos incluye descargas. Conviene medirla de verdad en cuanto exista el andamiaje, porque si no se alcanza hay que publicar el tiempo real con su causa y eso conviene saberlo temprano, no en la semana 11.
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->

## Interpretations

- 2026-09-20T16:01:36Z — U2: el piso de cobertura por modulo critico se identifica como `NFR18.2`, no como un `NFR18.1` nuevo. U1 ya reservo `NFR18.1` para el agregado y dejo `NFR18.2` declarado como "hoy no aplica porque los modulos criticos llegan con U2, U4, U8 y U9". Reutilizar `NFR18.1` con otro significado habria colisionado en la matriz de verificacion final, donde las filas de las 22 unidades se juntan.
- 2026-09-20T16:01:36Z — U2: de `NFR12` solo se cubre la parte de RT-4 (acceso a un caso o poliza ajena). El enunciado de NFR12 habla de no obedecer instrucciones inyectadas, que es trabajo de U10 y U21. Se declara asi en la trazabilidad en vez de marcarlo cubierto entero, porque U2 no puede verificar la parte de inyeccion.

## Tradeoffs

- 2026-09-20T16:01:36Z — U2: tres de los catorce controles interrogan a la herramienta viva en vez de leer el archivo donde se escribio el ajuste: la asercion pregunta al catalogo de la base que tablas hay, el chequeo del rol pregunta que privilegios tiene el rol vivo, y la separacion de claves se comprueba probando que una no valida lo de la otra. Cuesta mas que leer configuracion; es la leccion del 2026-09-20 aplicada antes de que vuelva a morder.
- 2026-09-20T16:01:36Z — Alcance reducido por tipo de unidad: al estar U2 declarada `library`, el contrato de la etapa solo pide requisitos de seguridad y decisiones de stack. No se escriben los de rendimiento, escalabilidad, fiabilidad y observabilidad, que `produces_kinds` asigna a las unidades `service`. Es la primera vez en el proyecto que el tipo de unidad recorta artefactos, y conviene decirlo en voz alta para que no se lea como un olvido.

## Deviations

- 2026-09-20T16:11:05Z — U2: las tres correcciones que instruyo Miguel tras la revision no pudieron entrar en `security-requirements.md` ni en `tech-stack-decisions.md`, congelados por el recibo de revision. Las dos vias de desbloqueo que ofrece el framework no aplican bajo iteracion por unidad: pedir cambios exige una etapa activa y esta figura como pendiente; reiniciar la etapa exige un salto que marcaria `functional-design` como saltada para las veintiuna unidades restantes. Se escribieron en `correcciones-tras-revision.md`, que no es artefacto declarado de la etapa y por tanto no altera lo que la revision certifico. Mismo patron que SEC-U1.4 en U1.

## Open questions

- 2026-09-20T16:11:05Z — Hueco del framework que conviene confirmar: bajo `Construction Iteration: unit-major`, una etapa por unidad puede tener revision final y documentos congelados mientras el flujo la sigue viendo `pending`, de modo que ninguna de las dos vias de desbloqueo del hook `review-freeze` es ejecutable. Paso dos veces en la misma sesion (diseno funcional y requisitos de calidad de U2). Si vuelve a pasar en U3, vale la pena decidir si la respuesta permanente es escribir siempre el archivo de correcciones o cambiar la clase de revision de estas etapas.

## Interpretations

- 2026-09-20T23:10:00Z — U4: PA-8 se registra como objetivo medible con su propio identificador de Incepción en vez de inventarle un `NFRx.y`. La tabla de requisitos no funcionales de Incepción no contiene ningún requisito de cifrado en reposo —el revisor de calidad ya lo había señalado como hueco—, así que colgarlo de un NFR existente habría creado trazabilidad falsa. `PA-8` es el identificador que `unit-of-work.md` y el contrato C-12 ya usan para esta decisión.
- 2026-09-20T23:10:00Z — U4: se declara NFR10.4 aunque U4 no figura en la columna de verificadores de NFR10. La razón es que BR7.3 —un caso ajeno responde igual que uno inexistente— solo la puede medir quien posee casos, y U2, que es la dueña, no los posee. Hay precedente exacto: U2 declaró NFR12.1 acotado a "solo la parte de RT-4" siendo U10 el dueño de NFR12. Comprobado leyendo su `traceability.json`, no de memoria.

## Deviations

- 2026-09-20T23:10:00Z — U4: la etapa produce tres artefactos y no siete. La unidad es de tipo `library` y el contrato de la etapa asigna `performance-requirements.md`, `scalability-requirements.md`, `reliability-requirements.md` y `observability-requirements.md` solo a las de tipo `service` o `ui`. Es el mismo reparto que tuvieron U2 y U3.
- 2026-09-20T23:10:00Z — U4: el cuerpo de esta etapa se investigó con cuatro agentes en paralelo más un refutador por afirmación, 64 en total. De 59 afirmaciones citadas, 16 quedaron refutadas al comprobarlas contra su archivo: una de cada cuatro. El dato importa para calibrar: un informe de agente sin refutación adversarial habría metido esas dieciséis en el documento. El costo también importa —7,17 millones de tokens— y por eso el resto de la unidad se hace leyendo archivos, por decisión de Miguel del 2026-09-20.

## Tradeoffs

- 2026-09-20T23:10:00Z — U4: el cifrado del lado del aplicativo deja las columnas cifradas sin poder filtrarse ni ordenarse en SQL. Se acepta porque ninguna consulta aprobada lo necesita hoy, y queda escrito como condición de reapertura en lugar de como excepción. La alternativa, cifrar dentro de la base, evitaba ese costo pero llevaba la clave hasta el proceso del que se quiere proteger el dato.
- 2026-09-20T23:10:00Z — U4: dos de los siete objetivos medibles se declaran hoy como "no medida" porque DS-2 está `built: false`. Es lo que la práctica afirmada exige —declararlos con su comando y reportar la causa, nunca cerrarlos con N/A— y el costo es que la matriz de verificación arranca con dos filas sin número.

## Open questions

- 2026-09-20T23:10:00Z — U4: `mise run test:u4` no existe todavía y el comprobador de artefactos lo marca. Es de calendario, no defecto: la tarea se declara en la tabla de tareas nuevas de `infrastructure-design/cicd-pipeline.md` de esta misma unidad, que aún no ha corrido. U3 pasó por lo mismo. Comprobar que el hallazgo desaparece al cerrar esa etapa.
- 2026-09-20T23:10:00Z — U4: la asimetría del catálogo de componentes sigue abierta y es de U12. El almacén del caso figura "con RLS y cifrado en reposo" y el de los puntos de control solo "con RLS", pese a que PA-8 cubre los dos. U4 decide su mitad y deja la diferencia señalada; conviene mirarla al diseñar U12 en vez de heredarla sin verla.
- 2026-09-20T23:10:00Z — U4: contra qué adversario protege PA-8 no lo declara ningún artefacto aprobado. El documento lo resuelve diciendo explícitamente contra qué protege y contra qué no (protege contra quien alcance el almacén sin el proceso; no protege contra quien tenga el proceso y su variable de entorno), pero un modelo de amenaza escrito ayudaría a U12 y al intent `infra`.
- 2026-09-20T23:20:00Z — U4, sobre los dos hallazgos de la revisión: los dos son falsos y los dos por un defecto mío de mecánica, no del revisor. R-01 dice que el precedente de U2 (declarar NFR12.1 siendo U10 el dueño de NFR12) no se sostiene; sí se sostiene, y está literal en el `traceability.json` de U2, pero el guardián de alcance le bloqueó ese archivo pese a que lo incluí en la lista de excepciones del registro de despacho. **La lista de excepciones no cubre rutas de `construction/<otra-unidad>/`**: hay que comprobar si el guardián admite esa excepción antes de volver a apoyarse en ella, o pegar la cita en el propio encargo. R-02 dice que no pudo confirmar que el registro de puntos de salida declare `case_transcript` con U4 como dueña; sí lo declara, en `sinks.py:76-78`, que es código del aplicativo y no una unidad hermana: el revisor se autolimitó porque **mi encargo no le dijo que el código de `app/` estaba en su alcance**. Lección para el próximo encargo: nombrar explícitamente que el código del aplicativo es leíble, y pegar en el texto la cita de cualquier archivo hermano en que se apoye una afirmación.

## Interpretations

- 2026-09-21T04:00:00Z — U5: NFR14 y la decision D7 son el mismo numero dicho dos veces. NFR14 pide "0,02 USD o menos por llamada de cuatro minutos" y D7 pide "0,005 USD o menos por minuto de modelo": 0,005 x 4 = 0,02. De ahi se sigue algo que no estaba escrito en ninguna parte y que conviene no descubrir al final: **la meta de NFR14 cubre el modelo y nada mas**; la transcripcion y la sintesis se publican aparte y sin meta, como D7 dice literalmente. Queda escrito al principio de `performance-requirements.md` para que nadie mezcle las tres cifras en una.
- 2026-09-21T04:00:00Z — U5: PA-9 tenia mas investigacion hecha de la que parecia. `docs/reference/arquitectura-y-tecnologia.md` ya habia medido que los topes de gasto de Gemini solo existen en el plan de pago, son mensuales y reaccionan en ventanas de diez minutos, es decir, no expresan el techo acumulado de 5 USD en noventa dias. La respuesta a PA-9 no fue inventar una figura: fue nombrar la que hay (saldo prepagado sin recarga automatica), negarse a contar una alerta de presupuesto como tope, y exigir la fecha de la ultima comprobacion.

## Deviations

- 2026-09-21T04:00:00Z — U5: las metas de Incepcion se registran cada una en **un solo** documento de la unidad, el que la tabla de metas de `unit-of-work.md` nombra: NFR11 en seguridad, NFR14 en rendimiento, NFR15 en confiabilidad. La primera version las repetia en dos documentos, lo que habria producido dos filas de la matriz de verificacion para una sola meta, contra UG-13. Donde faltan, el documento dice donde estan en vez de callarlo.
- 2026-09-21T04:00:00Z — U5: `scripts/check-artifacts.py` deja ocho hallazgos, todos de la misma forma: `mise run test:u5` y `mise run spend:report` citados sin que existan en `mise.toml`. **No es un defecto de esta etapa**: el comprobador lee las tareas nuevas de `<unidad>/infrastructure-design/cicd-pipeline.md`, que en la rejilla de la unidad llega despues. U4 tuvo exactamente los mismos y se cerraron ahi. Queda escrito para que la marca no se lea como olvido ni se silencie.

## Tradeoffs

- 2026-09-21T04:00:00Z — U5: el registro del gasto es sincrono para lo facturable y diferido para lo demas. Lo sincrono cuesta latencia en el camino de la voz, que es la meta mas dura del proyecto; a cambio, es lo unico que mantiene acotado el exceso sobre el techo en el costo de una sola llamada. Se pago donde hay dinero y no donde no lo hay.
- 2026-09-21T04:00:00Z — U5: la fila unica del acumulado serializa todas las escrituras facturables del proyecto. Es un cuello de botella a proposito: con quince llamadas diarias como techo del carril publico, la contencion maxima son unas pocas escrituras por minuto, y cambiarla por sumas o particiones venderia la unica garantia que el techo tiene.

## Open questions

- 2026-09-21T04:00:00Z — U5: si `providers` y `telemetry` deben entrar a la lista afirmada de modulos criticos con piso propio de cobertura es decision de Miguel, con el precedente del 2026-09-20 (la redaccion entro por tener fallo silencioso). Queda escrito en `security-requirements.md` como observacion y **no** como requisito: decidirlo aqui seria decidir por el.
- 2026-09-21T04:00:00Z — U5: cuanto vale la reserva de grabacion se fijo en 45 minutos de llamada y no en dolares, porque el precio por minuto de la voz lo mide el experimento 1. El numero de minutos sale de FR14.2 (el video muestra la escena de la llamada, el proyecto es bilingue, una escena utilizable exige varias tomas) y de la sesion de escucha. Confirmarlo al disenar U15 y U16, que son quienes saben cuantas tomas hacen falta.

## Interpretations

- 2026-09-21T15:00:00Z — U6: PA-4 pedia fijar los navegadores "con el dato de WebRTC del experimento 1", y ese dato no existe. Se leyo como una condicion de la unidad que abre el microfono: U6 no usa WebRTC, declara su lista y la condicion pasa con su nombre a nfr-requirements de U16 (Q1).
- 2026-09-21T15:00:00Z — U6: "menos de 3 segundos" de AC5.16.4 se leyo en un telefono de gama media con red lenta emulados, no en escritorio (Q2); de ahi el presupuesto de 200 KB antes de la pagina de espera.

## Deviations

- 2026-09-21T15:00:00Z — U6: el registro de licencias que cita el sistema de diseño no existe como archivo; en Python la licencia va en un comentario junto a cada dependencia. Como el manifiesto de la interfaz es JSON, se crea `app/frontend/DEPENDENCIES.md` con la misma linea por dependencia (TECH-U6.1).

## Tradeoffs

- 2026-09-21T15:00:00Z — U6: accesibilidad completa solo en Chromium y prueba de dibujo en Firefox y WebKit, en vez de todo en los tres motores (Q1). El analizador revisa el documento, que no cambia por motor; triplicarlo gastaria el presupuesto de 4 minutos del arnes (Q3) sin encontrar mas.
- 2026-09-21T15:00:00Z — U6: el cliente generado de la API cuenta en la cobertura (NFR18.4). Excluirlo agrandaria la lista de exclusion, que es relajar el piso; si algun dia baja el agregado, se lleva a Miguel.

## Open questions

- 2026-09-21T15:00:00Z — U6: los comandos `test:u6`, `a11y` y `activation:report` los marca el comprobador de artefactos hasta que el diseño de infraestructura de U6 los declare; la marca es correcta, como en U5.
- 2026-09-21T15:20:00Z — U6, revision asesora READY con dos hallazgos, llevados asi a las etapas siguientes y a la compuerta sin tocar los documentos revisados:
  - R-01 (mayor): NFR10.5, NFR11.7, NFR18.4, NFR19.3, NFR20.1 y NFR21.3 usan subidentificadores de metas registradas por otras unidades (UG-13 las quiere con una sola fila en la matriz). Se leen como aportes de U6 a esas metas, no como filas nuevas: en build-and-test cada una se agrega bajo la fila de su unidad duena.
  - R-02 (menor): el registro de purgadores vive en la raiz de composicion de U1 (C-24), no en U2; la prueba de completitud la aporta U2, el registro es de U1.

## Interpretations

- 2026-09-21T17:40:00Z — U10: NFR9 y NFR12 se partieron en lo que U10 mide sola sobre frases de prueba (NFR9.1, NFR12.2, en cada entrega) y lo que necesita el grafo y el chat (NFR9.2, no medida hasta U12 y U13) o el despliegue publico (NFR12.3, pasada de publicacion). NFR12.1 no se reutiliza porque U2 lo retiro.

## Open questions

- 2026-09-21T17:40:00Z — U10: `test:u10` lo marca el comprobador de artefactos hasta que la generacion de codigo lo cree; la marca es correcta.

## Interpretations

- 2026-09-27T01:17:59Z — U8: la tabla de metas le da NFR6 (citas inexistentes, compuerta dura) a esta unidad y la pone como verificadora de NFR5, NFR10, NFR17, NFR18 y NFR20. Cada una de esas cinco se declara aqui con un identificador propio (NFR5.1, NFR10.1, NFR17.1, NFR18.1, NFR20.1) para que el objetivo del dueno no se duplique y la matriz de build-and-test no cuente dos veces lo mismo.

## Deviations

- 2026-09-27T01:17:59Z — U8: NFR10.1 mide la fuga entre aseguradoras sobre la busqueda **vectorial** por separado. Es lo que queda de AC2.1.4 despues de FD-U8-4: el criterio pedia un espacio de nombres para un indice que aqui no vive fuera de la base, asi que se conserva lo que buscaba --aislamiento comprobado en el indice-- y no su letra.

## Tradeoffs

- 2026-09-27T01:17:59Z — U8: PERF-U8.3 (latencia de la recuperacion) se publica desde la primera corrida pero **no bloquea**. El tiempo maximo del nodo antes de degradar es dato de la politica de fallo, y esa politica la aplica el ejecutor comun de U12, que todavia no existe. Fijar aqui un numero seria inventarlo. Se paga con una meta menos en esta entrega; se gana que U12 fije su umbral contra una medicion real.

## Open questions

- 2026-09-27T01:17:59Z — U8: las llamadas al proveedor de embeddings **no tienen precio publicado**. U5 dejo escrito en `prices.yaml` que `gemini-embedding-001` salio de la pagina de precios de Google y que sus llamadas se registran como no medidas, nunca como cero, senalando explicitamente a U8 como consumidora. La consecuencia aterriza aqui: el costo por caso de una pregunta de cobertura se publica con el hueco declarado. Se cierra cuando Google publique el precio o cuando se cambie de modelo, que de todos modos reconstruye el indice.
- 2026-09-27T01:17:59Z — U8: REL-U8.1 y NFR5.1 no se pueden medir hasta que existan los 40 casos de DS-3, que son alcance de esta misma unidad. Hasta la primera corrida completa se publican como "no medida" con esa causa.

## Interpretations

- 2026-09-27T06:23:23Z — U11: es la unidad con mas metas del hito del proyecto y **ninguna es suya**: NFR7, NFR8, NFR13 y NFR20 son de U21 y U11 las realiza con su conducta; NFR4 es de U13, NFR12 de U10 y NFR14 de U5. Cada una se declara aqui con identificador propio (NFR7.2, NFR8.2, NFR13.3, NFR20.2...) para que la matriz de verificacion no cuente dos veces lo mismo.

## Deviations

- 2026-09-27T06:23:23Z — U11 no lleva piso de cobertura propio: no esta en la lista de cinco modulos criticos de `team.md` y esa lista se amplia por decision de Miguel, no por analogia. Se apunta al agregado del 80 %.

## Tradeoffs

- 2026-09-27T06:23:23Z — U11: cuatro de los criterios de estilo (una pregunta por turno, 25 palabras, marcadores orales, registro prohibido) los juzga el **codigo** sobre el texto ya compuesto, y solo el tono queda para el juez. Se paga con listas versionadas que hay que mantener; se gana que esa mitad de la rubrica se publique aunque el juez este descalibrado, que es lo que AC1.13.5 pide explicitamente.

## Open questions

- 2026-09-27T06:23:23Z — U11: cuantas llamadas al modelo caben en un turno se asigna a U12, que lleva el presupuesto del turno y los dos ritmos. U11 publica la medicion (PERF-U11.2) y se ajusta. Los 3.900 tokens de ADR-006 si tienen numero y se comprueban contando el prompt, no estimandolo.
- 2026-09-27T06:23:23Z — U11: `app/config/prompts/` existe hoy solo con su README. U11 es la primera unidad que escribe ahi, asi que la forma del archivo --nombre, idioma, version-- la fija esta unidad y U12 la hereda.
