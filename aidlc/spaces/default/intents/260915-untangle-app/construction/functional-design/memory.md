<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
- 2026-09-20T19:05:00Z — U3: la plantilla pide maquina de estados, pero nada en esta unidad tiene ciclo de vida: entra texto, sale texto tapado, no queda nada. Se dice explicitamente en `functional-spec.md` en vez de omitirlo, porque una maquina inventada seria ruido que alguien intentaria implementar.
- 2026-09-20T19:05:00Z — U3: AC4.12.4 exige redactar tambien los nombres del corpus sintetico, asi que el conjunto de tipos incluye los del detector de base (nombre, correo, lugar) y no solo los cuatro propios del dominio. Consecuencia declarada: el nombre del asegurado sale tapado en la transcripcion y en claro en los campos del caso, que es AC4.12.1 y no una inconsistencia.
- 2026-09-19T00:22:18Z — Se leyo el andamiaje del primer commit (manifiesto, lockfile, herramientas, guion de verificacion, arbol de modulos) como criterio de terminado del Bolt y no como flujo de negocio: no tiene entidades ni reglas que disenar, y ya esta especificado en `bolt-plan.md`.
- 2026-09-19T00:22:18Z — Se modelaron `ScriptAnswer` y `SubsetDefinition` como entidades del diseno aunque viven en archivos versionados y no en tablas: sin ellas, el guion por campo y la reproducibilidad del subconjunto no tendrian forma declarada.
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->

## Deviations
- 2026-09-20T19:05:00Z — U3: la opcion elegida en Q1 se aplico con una precision. La opcion planteaba resolver el idioma de la etiqueta al mostrarla; rige en cambio escribirla en el idioma de la conversacion y guardarla ya escrita, porque un renglon de log o una traza exportada se leen fuera del aplicativo, sin catalogo que resolver.
- 2026-09-19T00:22:18Z — U1 no tiene interfaz, pero al ser una unidad sin tipo recibe la matriz completa de diseno y por tanto `frontend-components.md`. Se escribio declarando que no hay pantallas y documentando la unica superficie que U1 entrega a la interfaz: el modulo tipado de claves del catalogo.
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs
- 2026-09-20T19:05:00Z — U3: la consola retrasa el fragmento parcial en vez de mostrarlo y taparlo despues (FD-U3-6). Se acepta que la transcripcion en vivo vaya por detras de la voz mientras se dicta un dato; lo contrario ya enseño el numero, y la captura de pantalla lo conserva.
- 2026-09-20T19:05:00Z — U3: la regla de respaldo por contexto tapara alguna vez un numero que no hacia falta tapar, y eso se ve en la transcripcion. Se acepta a cambio de cubrir el formato que nadie previo, y se cuenta aparte para que no esconda un reconocedor roto.
- 2026-09-19T00:22:18Z — U1: subconjunto de la corrida como lista versionada de identificadores en vez de selector por ejes. Cuesta mantenerla al agregar casos, y a cambio dos corridas del mismo commit son identicas por construccion, que es justo lo que pide AC4.4.4.
- 2026-09-19T00:22:18Z — U1: claves del catalogo siempre literales, sin familias construidas en ejecucion. Mas repeticion en el codigo a cambio de que el chequeo de claves sin consumidor sea exacto y no necesite lista de excepciones.
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
- 2026-09-20T19:05:00Z — U3: que cuenta como 'frase de contexto declarada' para la regla de respaldo se fija en nfr-requirements con su lista versionada; aqui solo se declara que existe.
- 2026-09-19T00:22:18Z — U1 (u1-workspace): el respondedor simulado lee el campo que el turno declara, asi que el contrato de turno de C-14 tiene que exponer ese dato. Confirmarlo al disenar U11 (captura) y U12 (runtime), o el conductor de texto no podra emparejar.
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->

## Interpretations

- 2026-09-20T15:44:05Z — U2: `VisitorKey` recibe columna de aseguradora, que el catálogo no le daba; su identidad pasa a ser la pareja (aseguradora, resumen de la clave). FR9.1 exige que toda tabla lleve el identificador de aseguradora con su política, y sin ese campo la clave de navegador habría quedado como la única tabla del aplicativo fuera de la aserción de aislamiento. Efecto secundario deseable: el mismo navegador que visita dos demostraciones tiene una fila por aseguradora y una no ve la otra.
- 2026-09-20T15:44:05Z — U2: la aseguradora vive en su carpeta de configuración y no en una tabla. FR9.3 pide que añadir una cuarta sea añadir una carpeta; una tabla obligaría además a una migración y a sembrar datos. Consecuencia: U2 solo crea dos tablas (enlaces de caso y claves de navegador), y las dos llevan su columna de aseguradora, así que no queda ninguna tabla fuera de la aserción.

## Deviations

- 2026-09-20T15:44:05Z — U2: no se escribe `frontend-components.md`. La unidad está declarada de tipo `library` y el contrato de la etapa asigna ese artefacto solo a las unidades de tipo `ui`. No es un olvido: las pantallas que consumen estos contratos pertenecen a U14 y a U6.

## Tradeoffs

- 2026-09-20T15:44:05Z — U2: once de las veintisiete reglas quedan en el arreglo inverso de la trazabilidad, contra tres en U1. La causa no es debilidad del mapeo sino el reparto de propiedad: U2 es dueña de los contratos del enlace firmado (C-07), del borrado de datos de visitante (C-11), de la configuración por aseguradora (C-25) y de las migraciones (C-30), mientras que los criterios de aceptación que los ejercitan viven en las historias de la bandeja (U14) y del reinicio (U20). Se prefirió declararlas con su razón antes que inventarles un criterio de U2 que no existe.
- 2026-09-20T15:44:05Z — U2: la aserción de aislamiento lee el catálogo vivo de PostgreSQL en vez de una lista declarada. Cuesta una consulta al catálogo y una lista de exclusión versionada; a cambio, una tabla que cree cualquier unidad futura queda cubierta el día que nace. Es la misma lección del fallo de cadena de suministro de esta semana: un control se comprueba interrogando a la herramienta, no leyendo el archivo donde se escribió.

## Open questions

- 2026-09-20T15:44:05Z — U2: el aislamiento de las tablas de puntos de control del grafo sigue abierto por diseño; el contrato C-10 lo asigna a U12, que elegirá entre un pool por aseguradora y un almacén propio con transacción. La aserción de U2 las cubrirá sin cambiar en los dos casos, pero conviene confirmarlo cuando U12 llegue.

- 2026-09-20T15:55:00Z — U2, corrección tras la revisión: la pregunta Q3 se presentó a Miguel como decisión nueva cuando CD-5 de Contract Design, una de las siete que él mismo respondió, ya decía "el enlace firmado se canjea una vez". El revisor lo marcó Critical y tenía razón. Se le volvió a preguntar con CD-5 delante y confirmó que esa frase describe el transporte —un canje por carga de pantalla— y no un token de un solo uso; la aclaración quedó escrita en `contract-summary.md`, en la fila CD-5 y en C-07. Lección: antes de declarar una decisión "abierta", buscarla en las tablas de decisiones de las etapas anteriores, no solo en el texto de los contratos.
- 2026-09-20T15:56:00Z — U2: intenté editar `functional-spec.md` después de la revisión y el hook de congelación lo rechazó, con razón. El error previo fue mío por partida doble: la revisión es de clase asesora, y su protocolo dice que el veredicto no dispara arreglo ni re-revisión —el recibo se registra y los hallazgos se llevan al humano en la compuerta—. No hacía falta tocar el documento. Para la próxima: con `review_class: advisory`, registrar el recibo y seguir.
- 2026-09-20T15:57:00Z — Decisión de Miguel para las 21 unidades restantes: correr solo las etapas de diseño que apliquen según la condición declarada de cada una, en vez de las cuatro siempre. Antes de cada unidad se declaran en dos líneas cuáles corren y cuáles se saltan, con su razón. Para U2 la evaluación honesta es que las tres restantes aplican, porque es la unidad de seguridad: sus cuatro criterios `[bloquea]` obligan a `nfr-requirements`, y el rol de base de datos sin privilegio de salto es exactamente el tipo de decisión de infraestructura que, si no se diseña, produce una suite verde que no mide nada.

## Interpretations

- 2026-09-20T22:30:00Z — U4: "única vuelta atrás" de ADR-005 se lee como volver a poner el caso en manos de la persona para seguir capturando, no como cualquier arista hacia un estado anterior de la lista de FR1.4. Sin esa lectura, la vuelta de `awaiting_insured` a `derived` quedaría prohibida y un caso que espera un dato del asegurado no podría decidirse nunca, que es justo la cifra que AC1.14.4 quiere en cero. Queda escrita como decisión FD-U4-8; el revisor la marcó Minor por no haberla llevado como pregunta.
- 2026-09-20T22:30:00Z — U4: `derivation_reason` se cierra como enum versionado de tres valores en lugar de dejarlo en texto libre, porque la regla de la vuelta atrás **lo lee**. Un modelo declarado cerrado cuya condición depende de una cadena que nadie controla no es cerrado. Añadir un cuarto motivo es un cambio a esa lista, igual que a la tabla de transiciones.

## Deviations

- 2026-09-20T22:30:00Z — U4: no se ofreció la pregunta de modo de interacción del §3 (guiado / editar el archivo / chat) y se fue directo al modo guiado. Miguel ha respondido por el widget estructurado en las cuatro etapas anteriores y ha pedido ritmo; la pregunta le costaría un clic sin aportar información. Queda anotado como desviación, no como olvido.
- 2026-09-20T22:30:00Z — U4: `aidlc engine review-brief context` devuelve `aidlc-review-brief.ts does not export main(argv)`. Es un defecto del framework, no de los argumentos. En esta unidad no costó nada porque es la iteración 1 y no hay hallazgos previos que arrastrar, pero en una unidad con segunda iteración sí costaría: hay que volver a comprobarlo antes de una revisión con hallazgos previos.

## Tradeoffs

- 2026-09-20T22:30:00Z — U4: 22 de las 42 reglas quedan en el arreglo inverso de la trazabilidad. La causa es el reparto de propiedad, igual que en U2: U4 es dueña del esquema del caso (C-12), del purgador (C-11) y del número legible, mientras que los criterios que los ejercitan viven en las historias de la captura (U11), de la bandeja (U14), del reinicio (U20) y de las compuertas de evaluación (U21). Se prefirió declararlas con su razón antes que inventarles un criterio de U4 que no existe.

## Open questions

- 2026-09-20T22:30:00Z — U4: el momento del "fin de la llamada" que arranca los quince minutos de la vuelta atrás lo aporta quien deriva por límite de la demostración; esta unidad lo guarda y lo compara, no lo mide. Confirmarlo al diseñar U17 `voice-public-link`.
- 2026-09-20T22:30:00Z — U4, hallazgo R-01 del revisor, comprobado y real: `CaseParty.plate` no tiene estado ni evidencia de confirmación, pero AC1.8.3 exige leer en voz alta la placa del otro vehículo y esperar el sí. La trazabilidad lo mapeaba a BR2.2 y BR2.4, que gobiernan `CaseField` y no `CaseParty`. El arreglo está escrito pero el documento quedó congelado por la revisión; pendiente del Request Changes de Miguel.
- 2026-09-20T22:32:00Z — U4, pendiente con dueño y momento: Miguel pidió los tres arreglos de la revisión (estado y evidencia de confirmación para la placa del otro vehículo con su regla propia y el destino corregido en la trazabilidad; el aviso a U14 por la grafía del contrato en la sección 7; y la enmienda de ADR-005 sobre qué significa "única vuelta atrás"). **No se pudieron aplicar en el momento**: el guardián de congelación solo se levanta con un rechazo registrado en la compuerta, y bajo iteración por unidad la compuerta de `functional-design` llega al final de la rejilla. Se aplican allí, con Request Changes, revisión nueva y aprobación. El segundo arreglo ya está hecho en la parte no congelada: `contract-summary.md` tiene las dos apariciones corregidas con su razón escrita al lado. Lección mecánica: con `review_class: advisory` e iteración por unidad, todo lo que se quiera arreglar hay que verlo **antes** de registrar el recibo; después el documento queda cerrado hasta el final de la unidad.

## Interpretations

- 2026-09-21T03:25:00Z — U5: el techo de gasto y el aislamiento por aseguradora chocan aqui por primera vez en el proyecto. El techo es uno solo (5 USD del proyecto, no de Stonecroft) y AC5.14.1 pide agregaciones por proveedor y por mes, que cruzan todas las aseguradoras; una tabla con politica no se puede sumar entera. Se resolvio sacando las tres tablas de dinero y cuotas del aislamiento, con su razon en la lista de exclusion, y cobrando esa exclusion con una asercion nueva: ninguna tabla excluida puede tener columnas de texto libre ni de dato personal, comprobado contra el catalogo vivo igual que la de U2. La exclusion y la asercion nacen en el mismo commit, asi que la primera nunca existe sola.
- 2026-09-21T03:25:00Z — U5: se anadio una cuarta entidad que el catalogo de `domain-design` no listaba, `BudgetWindow`. La razon no es comodidad: el corte tiene dos requisitos que sumar el historial no cumple —funcionar aunque la observacion falle (C-17) y ser una decision que dos llamadas simultaneas no puedan tomar las dos—. Una fila unica se bloquea; una suma no.

## Deviations

- 2026-09-21T03:25:00Z — U5: no se ofrecio la pregunta de modo de interaccion del §3 y las seis preguntas se respondieron con la opcion recomendada. Miguel lo pidio explicitamente en su turno ("procede con U5 [...] sin tanta preguntadera, me voy por las recomendaciones que haces"). Queda anotado como delegacion registrada, no como omision: cada respuesta lleva escrita su razon antes del `[Answer]`, para que se pueda discutir despues.
- 2026-09-21T03:25:00Z — U5: no se escribe `frontend-components.md`. La unidad es de tipo `service` y el contrato de la etapa asigna ese artefacto solo a las de tipo `ui`. Las pantallas de gasto son de U22 y el resumen de traza lo dibuja U13.

## Tradeoffs

- 2026-09-21T03:25:00Z — U5: el techo se consulta antes de la llamada y el costo se registra despues, asi que el techo se puede sobrepasar por el costo de una llamada. La alternativa —reservar un estimado y conciliar— nunca se pasa y exige una tabla de reservas y una conciliacion por llamada. A las cifras de este proyecto el exceso maximo es menor que un centavo, asi que se acepta y se declara como BR4.5 en vez de esconderse.
- 2026-09-21T03:25:00Z — U5: 37 de las 50 reglas quedan en el arreglo inverso de la trazabilidad -- 40 de 53 cuando se aplique el arreglo de la revision --, la proporcion mas alta hasta ahora (U4: 22 de 42). La causa es que U5 tiene solo dos historias propias y es dueña de tres contratos (C-16, C-17, C-23) que consumen quince unidades: los criterios que ejercitan sus reglas viven en las historias de la voz (U16, U17), del chat (U13), del reinicio (U20) y de las compuertas (U21). Se prefirio declararlas con su razon antes que inventarles un criterio de U5 que no existe.

## Open questions

- 2026-09-21T03:25:00Z — U5: la reserva por llamada que divide el presupuesto para sacar el cupo diario del sitio depende del precio del minuto de la voz principal, que hoy no esta medido (lo fija el experimento 1). Vive como valor de configuracion con el precio de lista publicado y su prueba usa un valor sembrado. Confirmarlo al disenar U15 y U16.
- 2026-09-21T03:25:00Z — U5: la espera antes de declarar `lost` un resumen de traza no la fija ningun documento aprobado. Se propone tratarla como presupuesto de latencia en `nfr-requirements` de esta unidad.
- 2026-09-21T03:25:00Z — U5: el sensor de trazabilidad exige que la unidad que aparece en la tercera columna del mapa de historias cubra los criterios de esa historia. U5 aparece ahi para US4.12 (trazas exportadas), que es de U3. Se cubrieron los tres criterios que si son de esta unidad con BR6.5 y se marcaron N/A los dos que no (consola de voz, U16; reporte de evaluaciones, U21). Leccion mecanica para las unidades que siguen: antes de escribir `traceability.json`, mirar la tabla de historias que atraviesan unidades, no solo la columna de dueña.

- 2026-09-21T03:45:00Z — U5, leccion mecanica del ciclo de revision: con `review_class: advisory` y `reviewer_max_iterations: 1`, un veredicto NOT-READY es **terminal** y congela los documentos igual que un READY (`.claude/hooks/aidlc-review-freeze.ts`, comentario de cabecera). El registrador ademas rechaza un veredicto cuyos documentos cambiaron despues del despacho, y el despacho de una segunda pasada se rechaza por presupuesto agotado. Quedan exactamente dos momentos para arreglar: **antes** de despachar, o **despues** de un Request Changes del humano. Aqui se intento el tercero -- arreglar entre el informe y el recibo -- y costo restaurar cuatro archivos y una pregunta a Miguel. Para las unidades que faltan: correr el comprobador de coherencia semantica propio ANTES del despacho, no despues.
- 2026-09-21T03:45:00Z — U5, hallazgo R-03 del revisor, comprobado y real: FR3.11 (enmienda del 2026-09-19, la misma fecha que FR3.9 que si se cito) exige una reserva intocable del presupuesto de voz para grabar el video final y la sesion de escucha, y que una llamada marcada como grabacion se siga atendiendo con el cupo publico agotado. U5 es la dueña de todo el mecanismo de presupuesto y no la mencionaba en ninguna parte. El arreglo esta escrito y comprobado -- segundo carril en `SpendEntry`, dos columnas en `BudgetWindow`, reglas BR4.9 y BR4.10, decisiones FD-U5-11 a FD-U5-13 -- y se aplica con el Request Changes. Leccion: al citar una enmienda de una fecha, leer **todas** las de esa fecha, no solo la que se buscaba.

## Interpretations

- 2026-09-21T14:20:00Z — U6: la regla de project.md que prohibe prometer una capacidad no construida se leyo como regla de construccion y no de redaccion. U6 llega antes que cualquier canal, asi que el inicio muestra solo las acciones de superficies que el servidor declara montadas (Q1, BR4.1). La misma lectura alcanzo a la frase de M1 sobre el borrado nocturno: la agrega U20 cuando el reinicio exista.
- 2026-09-21T14:20:00Z — U6: "sesion" en AC5.16.6 se leyo como la clave del navegador de U2, que ya es por aseguradora y se borra cada noche (Q3), para no crear un identificador nuevo del navegador.

## Deviations

- 2026-09-21T14:20:00Z — U6: la telemetria de activacion se ubica en `telemetry/activation/` (MOD-10), fuera de las dos ubicaciones que el catalogo de unidades lista para U6 (`app/frontend/src/shared/` y `server/`). US5.16 nombra MOD-10 y la raiz de composicion no debe tener logica de dominio (FD-U6-8).
- 2026-09-21T14:20:00Z — U6: el `/health` de U1 se retira a favor de `/api/health/live` y `/api/health/ready` de C-02; sus indicadores de diagnostico pasan a `checks.providers` (FD-U6-6). Solo una prueba de integracion de U1 lo usa.

## Tradeoffs

- 2026-09-21T14:20:00Z — U6: el arnes recorre cada pantalla en los dos modos y los dos idiomas, lo que cuadruplica el recorrido por pantalla frente a uno solo. Se acepta porque el contraste se mide contra el fondo de cada modo y los dos son modos completos (FD-U6-7); el presupuesto de tiempo lo fija nfr-requirements.
- 2026-09-21T14:20:00Z — U6: 22 de las 44 reglas quedan en el arreglo inverso de la trazabilidad. U6 tiene dos historias propias y es dueña de convenciones (C-01, C-02, C-28) que ejercitan las historias de las pantallas que llegan despues; se declaran con su razon en vez de inventarles un criterio.

## Open questions

- 2026-09-21T14:20:00Z — U6: PA-4, la lista de navegadores declarados, necesita el dato de WebRTC en el navegador que el experimento 1 no midio. Se resuelve en nfr-requirements de esta unidad; si el dato sigue sin existir, se declara con esa razon.
- 2026-09-21T14:20:00Z — U6: la unidad se renombro `u06-web-shell` el 2026-09-21 por decision de Miguel, para que la herramienta del flujo la entregue antes que U10 y U15 (bolt-plan.md, DP-11). Vigilar si algun sensor de trazabilidad deja de reconocer U6 por el cero.
- 2026-09-21T14:45:00Z — U6, revision asesora READY con cuatro hallazgos. Los documentos revisados no se tocan despues del veredicto (leccion de U5); cada hallazgo se lleva asi a las etapas siguientes y se muestra en la compuerta:
  - R-01 (mayor): AC5.16.4 figura como OK, pero los enlaces al README y al video no existen y BR4.4 los omite. Es cobertura parcial: la pagina y su conducta son de U6; los enlaces llegan con la decision de publicar (semana 12) y el video (US4.2). Se declara asi en la matriz de verificacion de nfr-requirements.
  - R-02 (mayor): FD-U6-5 hace obligatorios `brand` y `character_key` y C-25 exige que una clave nueva llegue opcional y con valor por defecto. Se resuelve en la generacion de codigo como pide C-25: los dos campos entran opcionales, y su ausencia se trata como BR4.2 ya lo dice (sin marca la fila usa los tokens de Untangle y sin monograma; sin caracter la fila omite esa linea).
  - R-03 (menor): la seccion 7 pide a U17 montar una superficie, pero U17 extiende `voice_console` de U16 y no tiene surface_id propio. U17 no monta superficie nueva.
  - R-04 (menor): M1 consulta la disponibilidad de la voz al cargar el inicio, con dos estados mas. Es conducta de U16 y U17 sobre la accion "Llamar" que U6 ya dibuja solo si la superficie esta montada; se difiere a ellas.

## Interpretations

- 2026-09-21T17:30:00Z — U10: la pregunta "¿usted es una persona?" se leyo como parte de la familia de peticion de persona, no como un cuarto control del turno, para respetar D22 (solo tres controles baratos). C-20 gana `detect_identity_question` y `delimit_untrusted` como cambio aditivo de su dueño (FD-U10-4).

## Deviations

- 2026-09-21T17:30:00Z — U10: primera unidad bajo DP-14 (el nucleo ahora). La mitad de AC4.15.4 que corre DS-6 contra el despliegue publico queda en la pasada de publicacion; AC1.10.4 (insinuaciones, juez) queda en U21.

## Tradeoffs

- 2026-09-21T17:30:00Z — U10: reglas deterministas en vez de un clasificador con modelo para los controles del turno (Q1). Se paga con paráfrasis que un modelo entenderia mejor; se compensa con los dos idiomas sobre cada frase y con que cada fallo encontrado se vuelve patron y caso.

## Open questions

- 2026-09-21T17:30:00Z — U10: la configuracion por aseguradora de cumplimiento (`app/config/tenants/<t>/compliance/`) no se crea porque ningun criterio la pide; si U12 o U14 encuentran una diferencia entre aseguradoras, ahi nace.
- 2026-09-21T18:00:00Z — U10, enmienda de BR3.2 durante la generacion de codigo: la negacion ("todos estamos bien") apagaba la emergencia aunque en el mismo turno hubiera un herido grave nombrado. Ahora la emergencia gana si aparece un herido; la negacion solo apaga la alarma sin herido. AC1.6.5 sigue cumpliendose: sus negativos no nombran heridos.

## Interpretations

- 2026-09-27T01:08:52Z — U8: AC2.1.4 esta escrito sobre la premisa de un indice vectorial que vive fuera de las tablas con politica de aislamiento, y pide por eso un espacio de nombres por aseguradora. ADR-010 ya decidio lo contrario (pgvector dentro de PostgreSQL, sin servicio de busqueda aparte), asi que el criterio se satisface con lo que su premisa buscaba: RLS sobre `clause_index` y una prueba de aislamiento propia sobre la busqueda vectorial, no solo sobre las tablas de texto (FD-U8-4).
- 2026-09-27T01:08:52Z — U8: el catalogo de `domain-design` bosquejo las siete entidades antes de que U7 escribiera el corpus. Donde los nombres difieren manda el corpus real, porque es el que U8 ingiere: `issuer_tenant`, `endorsement_ids`, `period_start`/`period_end`. La tabla de desviaciones esta en `entities.md`.

## Deviations

- 2026-09-27T01:08:52Z — U8: `ClauseIndexEntry` gana `content_hash` y `CitationCheck` gana `amended_by`, ninguno en el catalogo de componentes. Sin el primero no hay forma de cumplir AC5.2.4 ("reingestar sin duplicar") salvo reindexando todo; el segundo lo exige ADR-011, que pide que la comprobacion quede registrada con el endoso que modifica la clausula.
- 2026-09-27T01:08:52Z — U8: DS-3 todavia no existe en `app/evals/cases/` (estan DS-2, DS-6 y DS-8). Los 40 casos son alcance de esta unidad y se escriben antes del codigo, como exige la rama evaluada.

## Tradeoffs

- 2026-09-27T01:08:52Z — U8: busqueda vectorial exacta, sin indice HNSW (FD-U8-6, ADR-010). Se paga con una busqueda lineal sobre ~104 clausulas por corpus; se gana no mantener ni afinar una estructura aproximada. El umbral que lo haria necesario queda escrito al lado para que la decision no se herede en silencio.
- 2026-09-27T01:08:52Z — U8: la clausula con instrucciones de AC2.2.4 vive como fixture fuera de `app/data/`, en un inquilino de prueba efimero (FD-U8-3). Se paga con una ruta de ingesta mas que probar; se gana que el corpus que se publica no contenga una trampa.

## Open questions

- 2026-09-27T01:08:52Z — U8: el corpus real resulto ser de un solo idioma por aseguradora (Stonecroft 104 clausulas en espanol, Sunmeadow 103 en ingles, Knotwell copias de las dos), mientras `default_language` de cada inquilino es "el idioma con el que se abre, no una restriccion". Que hace la agente cuando la pregunta y la poliza estan en idiomas distintos no lo decide ningun documento anterior: fue a Miguel como Q1 del diseno funcional y la respondio el 2026-09-26 con la opcion A: la clausula se muestra en el idioma en que esta escrita, la respuesta y el resumen van en el idioma de la conversacion, y cuando difieren la agente lo dice con una clave del catalogo. Cierra la pregunta y fija FD-U8-1.
- 2026-09-27T01:12:36Z — U8: de la respuesta a Q1 sale trabajo concreto que la generacion de codigo tiene que recoger: una clave nueva del catalogo en los dos idiomas para el aviso de idioma cruzado, y dos parejas de DS-3 que prueben la combinacion (pregunta en ingles contra Stonecroft y en espanol contra Sunmeadow).

## Interpretations

- 2026-09-27T06:20:39Z — U11: el catalogo de componentes le da `entities: []` al nodo de captura, y eso no es un hueco sino la decision: el estado de la conversacion no existe como tal, se deduce del caso en cada turno. Por eso AC1.5.2 pide leer el bloque preguntado del estado, y por eso reanudar tras interrupt() no necesita nada mas (ADR-003).
- 2026-09-27T06:20:39Z — U11: la responsabilidad "confirmar lesiones, conductor y lugar antes de anotarlos" se lee como una exigencia sobre **la lectura del bloque** --que los nombre uno por uno en vez de resumirlos-- y no como una lectura aparte por campo. Decision de Miguel del 2026-09-27 (Q2): una lectura propia por campo costaria tres turnos sobre una meta de catorce.

## Deviations

- 2026-09-27T06:20:39Z — U11: el nodo no detecta la emergencia. D22 fija que dentro del turno corren solo tres controles baratos y que son de U10; U11 respeta la senal rompiendo su orden. Un segundo detector aqui seria otro sitio donde arreglar el mismo fallo.

## Tradeoffs

- 2026-09-27T06:20:39Z — U11: la normalizacion de fechas, placas, polizas, cedulas y telefonos se aplica en codigo despues del modelo, no en el prompt. Se paga con reglas que hay que escribir y mantener; se gana que dos corridas del mismo commit escriban el mismo valor, sin lo cual la exactitud por campo de AC1.7.5 no es reproducible.

## Open questions

- 2026-09-27T06:20:39Z — U11: de la decision de Miguel en Q1 (el valor del caso es el primero confirmado, y la version que lo contradice se anota aparte) sale una obligacion que **no es de esta unidad**: la regla que deriva por contradiccion tiene que mirar que exista una version alternativa, no el valor del campo. Es una linea en el conjunto de reglas de cada aseguradora, y es de U9 --o de U19, que extiende ese conjunto--. U11 deja el dato escrito con su turno y su hora para que se pueda leer.

<!-- U14 `inbox`, diseño funcional del 2026-09-28 -->

## Interpretations

- 2026-09-28T19:30:00Z — U14: la bandeja guarda dos entidades y nada mas --el aviso en vivo y el recibo de idempotencia--. Todo lo que muestra es de la unidad que lo produjo (U4, U8, U9, U10, U5) y se pide al mostrarlo: una copia seria una segunda verdad y una forma de que discrepen.
- 2026-09-28T19:30:00Z — U14: el orden de la cola lo decide el servidor y no la pantalla, porque dos personas mirando la misma cola tienen que ver lo mismo. La prioridad de una solicitud de persona es dato de la configuracion de la aseguradora, no una rama del codigo.

## Deviations

- 2026-09-28T19:30:00Z — U14: C-05 declara una tercera decision (`request_more`) que ninguna historia describe, ningun criterio ejercita y ninguna de las cuatro resoluciones de U4 recoge. Se deja fuera con su razon escrita (BR4.7) por decision de Miguel del 2026-09-28, en vez de inventarle conducta. Añadirla despues es un cambio aditivo del contrato.
- 2026-09-28T19:30:00Z — U14: la vista del visitante con enlace es una pantalla propia y no la del ajustador con un interruptor (decision de Miguel, 2026-09-28). La regla U-07 de interaction-spec.md prohibe la jerga del sistema en pantallas de visitante, y sostener dos juegos de etiquetas sobre una sola pantalla es como un dia se cruza uno.

## Tradeoffs

- 2026-09-28T19:30:00Z — U14: tres bloques de evidencia abiertos y tres plegados (decision de Miguel, 2026-09-28). Se paga con un clic para ver regla, controles y traza; se gana que la pagina quepa en un telefono y que decidir en menos de tres minutos sea posible. La condicion que lo hace honesto: cada bloque plegado muestra su resultado en el titular, asi que plegar oculta el detalle y nunca el dato.
- 2026-09-28T19:30:00Z — U14: encabezado pegajoso en vez de barra de accion fija abajo (decision de Miguel, 2026-09-28). Se paga con altura de pantalla en el telefono; se gana que el 'por que llego' y el 'que hago' se vean juntos, que es como el criterio los nombra.

## Open questions

- 2026-09-28T19:30:00Z — U14: la vista de caso por enlace entra en la linea base de accesibilidad y la de credencial no (D25). Al construirla hay que declarar las tres rutas en el registro del arnes, marcando cual bloquea por hallazgo serio y cual solo reporta.
- 2026-09-28T19:30:00Z — U14: AC3.2.5 --decidir un caso en menos de tres minutos-- se mide con cronometro en la validacion del dia 30, no con una prueba. Queda como objetivo humano en nfr-requirements con su fecha y su commit, nunca cerrado con N/A.
