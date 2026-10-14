# Resumen de código — U13 `chat`

El chat público: la conversación de un visitante con la agente de una aseguradora,
desde la divulgación hasta el aviso de lo que decidió un ajustador, con sus
pantallas y con el conductor que corre un caso de golden set por este mismo canal.

**86 archivos, 8.921 líneas, cuatro tandas.** 137 pruebas propias de la unidad,
2.256 del backend y 186 de la interfaz en verde; cobertura agregada 88,48 % sobre
un piso del 80 %; `scripts/verify.sh` los nueve pasos en verde.

## Lo que construyó

| Pieza | Dónde | Qué resuelve |
| --- | --- | --- |
| La conversación y sus límites | `chat/session.py`, `chat/limits.py` | Una conversación por navegador, con los cinco controles de entrada y sus frases (BR3.1, BR3.2) |
| La apertura con su divulgación | `chat/opening.py` | Va antes de cualquier texto del visitante, y sin su registro el caso no cierra (BR1.1, BR1.2) |
| El idioma del turno | `chat/language.py` | Dos detectores de umbral distinto; un "ok", un nombre propio o una placa no cambian el idioma (BR2.1, BR2.2) |
| El cable y su cola | `chat/stream.py`, `chat/wire.py` | Los eventos de C-14 en la forma de C-04, con su latido y sin perder lo encolado (REL-U13.1) |
| La entrega al grafo | `chat/delivery.py` | El puerto del grafo, la transcripción, el caso atado a su conversación y el resumen de traza abierto |
| La cita expandible | `chat/citation.py` | Identificador, versión y texto completo, leídos del corpus (BR4.1, BR4.2) |
| El resumen de traza | `chat/trace.py` | Sin credencial, solo del propio navegador, y "se está registrando" en vez de "no encontrado" (BR4.3, BR4.4) |
| El aviso del ajustador | `chat/notice.py` | El único texto que puede afirmar un resultado, y no se compone sin una firma (BR5.1, BR5.2) |
| Retomar un caso | `chat/resume.py` | Por número o por enlace firmado, con una sola vía de rechazo (BR6.1 a BR6.3) |
| Las dos rutas y la superficie | `chat/api.py` | El primer módulo montado por C-24, con su sonda que no llama al modelo ni gasta |
| Las pantallas | `app/frontend/src/pages/chat/`, `.../trace/` | La conversación, la cita expandible con su cláusula etiquetada y el resumen de traza |
| El conductor de texto | `evals/drivers/chat.py` | Corre un caso de golden set por el canal, que es lo que destraba el etiquetado de DS-7 |

## Las decisiones de la unidad

**El vocabulario de C-14 baja a un módulo hoja.** Consumir el contrato desde el
módulo del runtime arrastraba LangGraph a un canal por transitividad, y ADR-003
decide que solo esa unidad conoce el framework del grafo. Ahora es **cierto** que
cambiarlo no toca ningún canal, en vez de ser una intención escrita en un ADR.

**El puerto del grafo vive en `delivery`, no en las rutas.** Lo dijo un contrato
de importación antes que nadie: el conductor de evaluaciones también entrega
turnos por este canal, y pedirle el puerto al módulo de rutas le arrastraba el
framework web entero. El puerto es del canal, no de su superficie HTTP.

**El comentario del ajustador pasa por la guardia por su cuenta.** Empezó siendo
una exención del catálogo —el mecanismo existía y estaba vacío esperando
consumidor— y al medirlo se vio que eximía el texto entero: un "su póliza cubre
el choque y le vamos a pagar 900 dólares" escrito por el ajustador pasaba sin
intervención. La firma autoriza su decisión, no cualquier frase que escriba.

**El resumen de traza responde `200` con `null`, no `404`.** "No hay nada que
mostrar" es una respuesta válida a una pregunta válida. Con 404 el navegador
escribe un error en la consola de una página que funciona, y las tres causas —no
existe, es de otra conversación, es de otra aseguradora— siguen respondiendo
igual porque eso lo decide `by_trace`.

**Un conductor de canal puede tocar la base, y el corredor no.** El contrato que
lo prohibía traía escrita desde U2 la frase "el día que una unidad necesite base
dentro del subconjunto de arranque, este contrato fallará y obligará a decidirlo
a la vista". Llegó ese día. Se eximió `untangle.evals.drivers` y solo esa
carpeta: el camino del clon al reporte sigue sin base, porque ningún caso
conducido está en el subconjunto de arranque.

## Las fronteras que no construyó

- **La bandeja y la vista de caso por enlace** son de U14. Esta unidad muestra el
  aviso de lo que allí se decidió, no la decisión.
- **El transporte de voz** es de U16. El mismo caso puede venir de la voz (BR6.4),
  pero el canal no.
- **La vista de comparación** salió de esta unidad el 2026-09-28 y es U23.
- **Los límites configurados en el proveedor** se verifican pero no se configuran:
  eso es de la pasada de publicación.
- **El resumen de traza se queda en "registrándose".** Nadie llama a
  `record_trace`, que es quien lo pasa a "listo" con los nodos, la latencia y el
  costo; esos datos los tienen los tramos, que son de U5 y U12. Queda dicho y no
  escondido: un resumen marcado listo con los nodos vacíos afirmaría una
  completitud que no tiene.
- **Los once casos que le faltan a DS-2** siguen siendo el encargo reservado para
  la nube.

## Los defectos que encontró la revisión, tanda por tanda

Todos con las nueve compuertas automáticas en verde antes de que alguien mirara.

| Tanda | Defecto | Dónde estaba |
| --- | --- | --- |
| 1 | El límite diario no se probaba en su reinicio: la ventana se ensanchó a veintiséis años y las catorce pruebas siguieron verdes | En la prueba |
| 2 | `is` en vez de `==` con el enum de un módulo nativo: **toda** conversación en español se habría respondido en inglés | En el código |
| 2 | Un solo umbral para dos detectores que reparten confianza de forma distinta | En el código |
| 2 | El idioma se medía por caracteres: "Marcela Ríos" puntuaba 0,92 y cambiaba el idioma de la conversación | En el código |
| 2 | El flujo no decía nada al conectarse: una conexión viva y una colgada se veían igual durante quince segundos | En el código |
| 2 | La cola descartaba lo encolado al cerrarse: un turno que publicaba su respuesta y cerraba la perdía | En el código |
| 3 | La compuerta dura comprobaba ausencia en vez de identidad, y sin control positivo | En la prueba |
| 4 | La exención de la guardia eximía el comentario libre del ajustador | En el código |
| 4 | Tres de los cinco campos de cada cita salían vacíos en toda respuesta real | En la prueba (un doble con los cinco puestos) |
| 4 | La maquinaria del resumen de traza estaba entera y nadie la estrenaba | En el código |
| 4 | Las cinco claves de límite no existían en el catálogo | En el código |
| 4 | El 429 no estaba declarado en el contrato | En el contrato |
| 4 | El resumen de traza devolvía 404 y el esquema decía 200 | En el contrato |
| 4 | La lista de la conversación tenía un `div` dentro | En la pantalla |
| 4 | **La conversación nunca aprendía cuál era su caso** | En el código |
| 4 | Los cuatro casos nuevos nombraban tres campos que no existen | En los datos |

El de la tanda 4 marcado en negrita es el más caro de la unidad: sin él, el turno
siguiente volvía al grafo con `case_id` en nulo —cada mensaje una conversación
nueva—, la transcripción no se escribía y el resumen de traza no se abría. Nada
fallaba, porque el campo existía en la tabla y en el tipo. Lo encontró el
conductor de evaluaciones la primera vez que corrió una conversación entera.

## La costura del chat, arreglada el 2026-09-28

**El chat público no pudo atender a un solo visitante desde el día en que se
construyó.** Miguel lo encontró escribiendo "Hola" con el aplicativo delante; las
2.363 pruebas del proyecto estaban en verde. Tres defectos, uno detrás de otro, y
los tres **invisibles**: el `POST` respondía `202`, la excepción moría en una tarea
que nadie esperaba y la pantalla se quedaba muda.

| # | El defecto | Dónde estaba |
| --- | --- | --- |
| 1 | Nadie abría el caso del primer turno | U11 escribió `open_case` sin consumidor; U12 exige `case_id` y levanta; U13 entregaba `None` |
| 2 | Nadie enchufaba el runtime del grafo ni el cifrador | `install_runtime` y `crypto.install` sin un solo llamador en producción |
| 3 | El flujo de eventos salía **sin la galleta del visitante** | FastAPI no mezcla las cabeceras del `Response` inyectado en una `Response` devuelta tal cual |

El tercero es el que lo explica todo: un visitante nuevo abría su flujo escuchando
la conversación A, se iba sin galleta, y su primer mensaje abría la conversación B.
El flujo de A nunca oyó nada de B.

### Qué se cableó, y qué no

- **El caso nace en el canal** (`chat/case_opening.py`), que es la frontera que U12
  dejó escrita: el tipo de registro, el canal y el **origen** son datos del canal, y
  el origen decide qué borra el reinicio nocturno. El tipo lo decide el reconocedor
  determinista de U12 —el mismo del desvío de cobertura, no una copia— porque la
  categoría la deciden las reglas y no el modelo.
- `deliver` **pide el origen sin valor por omisión**: el chat público pasa
  `public_chat` y el conductor de evaluaciones `local_deployment`. Un valor por
  omisión habría hecho que el equivocado fuera el más fácil de escribir, y el
  equivocado aquí borra casos de personas o conserva para siempre los de una corrida.
- **El ritmo del turno, entero y real**: el nodo de captura de U11 con su extractor y
  su prompt versionado, el ejecutor común, los puntos de control cifrados y el
  almacén de pausas. El **de fondo** no: ver el cabo 1.8 de `PENDIENTES-MIGUEL.md`.
- **Ningún fallo se queda en silencio**, y son cuatro caminos: `deliver` publica la
  frase del catálogo y relanza; la tarea de la ruta recoge su excepción; el ritmo de
  fondo recoge la de la suya; y un mensaje que llega sin flujo abierto deja su evento
  en vez de descartarse callando.

### La forma de prueba que lo tapó

Un doble más permisivo que la pieza real. Todas las pruebas del canal enchufan un
`handle_turn` falso, y el falso aceptaba el turno sin caso —`del entrante`, sin
mirarlo— cuando el de verdad empieza con `if turn.case_id is None: raise`. Uno de
ellos **abría su propio caso**, que es justo lo que el real no hace.

Quedó escrito como forma 12 del catálogo de revisión, con su señal para buscarla (un
`del argumento` en la firma de un doble) y su compañera: **al menos una prueba tiene
que recorrer la costura con la pieza real**. La que la cierra corre en cada entrega y
no llama a ningún proveedor —el visitante pide hablar con una persona, la señal la
reconocen los patrones versionados y el turno deriva sin llegar al nodo que llama al
modelo—, y hay un paso de `mise run smoke` que hace lo mismo por el navegador.

## Lo que deja para otras unidades

- **U6**: el vocabulario de problemas de C-01 vive en `untangle.server`, que está
  por encima de las unidades en el contrato de capas, así que ninguna puede
  importarlo. Es el mismo problema que U6 ya resolvió para las superficies
  poniendo `surface_spec` en la raíz del paquete.
- **U5 y U12**: nadie une el rastro con su resumen de traza (`record_trace`).
- **U14**: el aviso del ajustador espera su decisión.
