# Correcciones del 2026-10-12

Lo que Miguel pidió el 2026-10-12 tras probar la demo local (once capturas), una fila
por corrección, con lo que se encontró al investigarla. Es la lista de trabajo: una fila
no se marca hecha hasta que se vio funcionando.

**Reglas que Miguel puso ese día y mandan sobre todas las filas**

- Anotar cada corrección en detalle y no perder ninguna. Corregir después de anotar.
- No gastar de más en pruebas con modelo: casi un dólar se fue en evaluaciones.
- No calentar la Mac: nada pesado mientras la usa.
- Hacer lo necesario y no más: sin rondas de revisión que no agreguen valor.
- Antes de modificar el chat, analizar bien por qué responde como responde (sección 3).

**Estado.** ⏳ pendiente · 🔨 en curso · ✅ hecho y visto · 🙋 espera una decisión de Miguel.

**Cómo se comprobó.** «Reproducido» quiere decir que el fallo se volvió a provocar por el
camino real: una llamada simulada (un guion habla con voz sintetizada, sin micrófono) y
una conversación de chat simulada. «Leído» quiere decir que la causa sale del código o
de la base local, sin correr nada.

## 1. La llamada

| ID | Qué pasó, en palabras de Miguel | Qué se encontró | Qué se hace | Estado |
| --- | --- | --- | --- | --- |
| L1 | «Lo único que hice fue parar un segundo, siguió hablando y se colgó» («Algo falló en la llamada») | **Reproducido.** La muletilla agregada el 2026-10-12 pide la respuesta en una tarea aparte; al terminar o interrumpirse el turno, el rastro de la llamada se cierra desde otra tarea y eso lanza un error (`ValueError`, variable de contexto de otra tarea). **Toda llamada con muletilla moría al primer turno largo.** Las pruebas no lo vieron porque el doble del grafo no abre rastro | Dejar la respuesta en la tarea de la llamada y mover a una tarea aparte solo la muletilla. Prueba con un grafo que abre y cierra contexto como el de verdad | ✅ comprobado con una llamada simulada: ya no se cae, ni al interrumpir |
| L2 | La agente toma el turno cuando uno hace una pausa a mitad de frase | **Reproducido.** «Hola, quería consultar sobre» + 1,3 s de pausa: el turno se cerró a los 0,7 s. La frase tiene cuatro palabras y eso la hace pasar por «respuesta corta», aunque termine en «sobre» | Esperar según cómo termina la frase: con punto, 0,7 s; sin punto, más; terminada en una palabra que pide continuación («sobre», «de», «que», «y», «para»…), bastante más. Esperar no cuesta: mientras la persona calla no se gasta modelo | ✅ comprobado con una llamada simulada: la señal de «empezó a hablar» del reconocedor llega a los 0,3 s y el turno ya no se cierra en la pausa; la frase partida se oyó entera, como un solo turno |
| L3 | La agente pregunta «¿Hubo alguien herido?» a quien llama a consultar | **Reproducido.** La llamada nace como reporte de accidente y el primer turno se clasifica por palabras; «quería consultar sobre» no encaja en ninguna y sigue como reporte | Con una primera frase que no dice a qué llama, preguntar en qué se le ayuda; el motivo lo entiende el modelo, no una lista de palabras (ver sección 3) | ⏳ |
| L4 | «Obvio se debe bajar de verdad la espera de cada respuesta» | Hoy: ~0,4 s del reconocedor + 0,7 s de tolerancia + ~1,2 s entendiendo + ~0,3 s arrancando la voz | Empezar a entender en cuanto llega la frase, sin esperar la tolerancia (se descarta si la persona sigue); decir la respuesta por frases según se va generando. La muletilla queda apagada hasta que L1 esté arreglado y Miguel la oiga | 🔨 medido en una llamada simulada: 4,0 s desde que el reconocedor cierra la frase hasta que suena la respuesta (0,7 de tolerancia, ~2,0 el modelo, 0,8 arrancando la voz). En curso: dejar abierta la conexión con la voz durante la llamada (hoy se abre una por frase). Después del camino B: adelantar la llamada al modelo y decir la respuesta según se genera |
| L5 | (lo encontré al investigar) | Cuando una llamada falla, el registro solo guarda el tipo de error, no dónde ocurrió: sin eso hubo que reproducirla | Guardar también el archivo y la línea, como ya hace el chat | ✅ |
| L6 | Cambio de idioma a mitad de llamada | Miguel: «me gustaría tenerlo pero creo que es mejor no aplicarlo de momento» | No se construye ahora | — |
| L7 | «Cada llamada cuesta plata y no quiero quedarme 3 semanas arreglando esto» | Hasta hoy los arreglos de la llamada se comprobaban con dobles y la primera prueba real la hacía Miguel | Queda una **llamada simulada** como herramienta (`mise run voice:simular`): la corro yo antes de pedirle a Miguel que llame. Cuesta 2 o 3 centavos | ✅ `mise run voice:simular`, con dos guiones versionados |

## 2. El chat

| ID | Qué pasó, en palabras de Miguel | Qué se encontró | Qué se hace | Estado |
| --- | --- | --- | --- | --- |
| C1 | «Le di el nombre y la póliza y me dio dos respuestas… dice que en un momento me responde cuando eso no tiene lógica, además nunca más dijo nada» | **Reproducido.** En una consulta de póliza, al quedar identificada la póliza el código dice «Déjame revisar tu póliza; te respondo en un momento» dando por hecho que la pregunta ya se hizo. Si la persona entró por el botón «Preguntar por mi póliza», no hay pregunta: no se revisa nada y nunca llega respuesta | Sin pregunta, preguntar qué quiere saber. «Te respondo en un momento» solo se dice cuando la revisión de verdad arrancó | ✅ comprobado con una conversación simulada: una sola respuesta, que pregunta qué quiere saber |
| C2 | «Al regresar a esa página de chat se borraron mensajes por sí solos» | **Sin reproducir todavía.** En la prueba de Miguel el turno mostró dos textos («¿Qué quieres saber de tu póliza?…» y «Gracias, ya tengo lo que necesito…») y la base guardó solo el segundo; al volver se ve lo de la base. En mi conversación simulada salió uno solo. Es la misma jugada que C1 y se busca al arreglarla | Lo que se muestra es lo que se guarda: un solo texto por turno, y una prueba que lo exija | ✅ la segunda burbuja era un aviso del fondo que no se guardaba; ahora todo aviso se guarda antes de publicarse |
| C3 | Tras «Que lo revise un ajustador»: «Tuve un problema para responder eso» | **Reproducido.** El caso sí se pasó al ajustador y la respuesta correcta quedó guardada. El servidor manda la clave de una frase que la pantalla no conoce, y la pantalla cae en la frase de error | Agregar la frase; y que el servidor mande también el texto, para que una clave nueva nunca vuelva a verse como error | ✅ comprobado: el evento lleva su texto. También faltaba la frase de cierre por insultos |
| C4 | «Ni siquiera entiende o recuerda de qué le estoy hablando» («quiero reportar eso que te acabo de mencionar como un accidente» → «¿Qué quieres saber de tu póliza?») | **Reproducido.** La conversación quedó atada al tipo con que empezó (consulta) y no hay camino para pasar a reporte. Quien redacta no ve la conversación, solo el último mensaje | Camino B de la sección 4, decidido por Miguel el 2026-10-12 | ✅ en código: abre el reporte y lleva nombre y póliza (conversación simulada). Falta que Miguel lo vea, y que el reporte nuevo recuerde lo ya contado (`07`, «Lo que falta») |
| C5 | «Siguen apareciendo censurados datos que he dicho en 4 ocasiones que no quiero que se censuren» («Soy [NOMBRE 1], mi póliza es [PÓLIZA 1]» en «Ver mi caso») | **Leído.** El chat ya devuelve a su burbuja lo que este navegador escribió y vio; la página del caso propio no usa ese mecanismo y muestra lo guardado, que por regla del proyecto va tapado en la base | En **toda** pantalla propia (chat, llamada, «Ver mi caso», Casos) se muestra el texto como se escribió y se vio en este navegador. La base sigue tapada. Se quita la nota que explica las etiquetas | ✅ en el código, falta verlo en pantalla. Queda un resto: en una llamada, lo que dijo la agente llega ya tapado del servidor y no se puede destapar (se resuelve con el camino B) |
| C6 | (lo encontré al investigar) «Queria saber si cubre…» quedó guardado como «[NOMBRE 1] saber si cubre…» | **Reproducido.** El detector toma «Queria», sin tilde y al inicio, por un nombre | Reconocedor: una palabra que es verbo corriente no es nombre; caso de prueba con esta frase | ✅ comprobado: «Queria saber…» se guarda sin etiqueta |
| C7 | «Estaba copiando algo en el chat y se borró al salir de la página… debe existir permanencia de datos para ese input» | El cuadro de escribir no guarda borrador | Guardar el borrador por aseguradora en este navegador y devolverlo al volver; se limpia al enviar o al reiniciar | ✅ en el código, falta verlo |
| C8 | «Mientras revisabas la póliza debe existir un loader… no que esté en blanco» | Tras «Déjame revisar tu póliza» no hay nada en pantalla hasta que llega la respuesta (12 s en la prueba) | Indicador de «revisando la póliza» en la conversación mientras la revisión está en curso | ✅ en el código, falta verlo. Si se recarga la página durante la espera, el indicador no vuelve (la respuesta sí llega) |
| C9 | «No me demoré nada en dar el veredicto como ajustador y eso es lo que me responde» («El enlace venció mientras escribías») | **Leído, causa probable.** El enlace no había vencido (valía hasta una hora después). La ruta de decidir vuelve a exigir la credencial de la bandeja si el navegador guarda una vieja, aunque el enlace del caso sea válido; el rechazo se muestra como «enlace vencido» | Decidir con quien de verdad entró (enlace o credencial), igual que ya se arregló para ver el caso; y no llamar «vencido» a lo que no lo es | ✅ con prueba por la ruta: una credencial vieja de la bandeja ya no impide decidir con el enlace |
| C10 | «El tema del caso sigue con números que no se entienden» | El caso se titula por su código («Tu reporte KNO-965815», y dice «reporte» aunque sea una consulta); en el chat sale «N.° KNO-965815» | Título por lo que es («Tu consulta de póliza», «Tu reporte de accidente»); el código pasa a un renglón pequeño que diga para qué sirve («Número de tu caso, por si llamas»). Interpretación mía: si Miguel quería otra cosa, se ajusta | ✅ en el código, falta verlo |

## 3. Textos y estilos

| ID | Dónde | Qué pidió | Qué se hace | Estado |
| --- | --- | --- | --- | --- |
| E1 | Ventana «Pensamiento de Valeria» | «Quiero que quede redactado el texto de manera impersonal» (hoy: «Cuando me cuentes algo, aquí verás cómo lo pienso») | Redacción impersonal en toda la ventana, en los dos idiomas | ✅ en el código, falta verlo |
| E2 | Comparar | Quitar la póliza del encabezado de cada aseguradora («si es necesario que se ponga antes de las cláusulas»); quitar «asistente de IA» de «Responde Valeria, asistente de IA» | Encabezado: «Responde Valeria». La póliza pasa a un renglón pequeño justo encima de las cláusulas | ✅ en el código, falta verlo. Que responden asistentes de IA se dice una sola vez, en el aviso junto al cuadro de texto |
| E3a | Página del caso, bloques «Regla disparada», «Controles de cumplimiento», «Cómo se respondió» | «No sé qué es el sentido de esos cuadros… es una estupidez tener algo ahí que no se está utilizando» | Decir cada cosa en palabras (qué regla y qué significa; qué se revisó y qué se encontró) y **quitar** lo que no tiene dato («No medido») | ✅ en el código, falta verlo |
| E3b | La misma página | «Todos los objetos alineados a la izquierda respetando el espacio que ya tiene el título… ese texto debe correr un poco hacia la derecha» | El contenido de cada tarjeta abierta se alinea con su título | ✅ en el código, falta verlo. Los tres bloques del final ya no se pliegan: en una frase no escondían nada |
| E3c | La misma página | «Que todo el contenido se alargue hacia los laterales al menos un poco» | Columna más ancha | ✅ en el código, falta verlo (de 42 a 52 rem) |
| E4a | Telemetría, panel «En qué se va» | Quitar los textos «plan gratuito» y «+ N consultas»: «genera espacio innecesario… a la gente solo le importa lo que se está consumiendo» | Se quitan del panel izquierdo; «Lectura de pólizas» muestra solo su cifra | ✅ en el código, falta verlo |
| E4b | Telemetría, panel «Quién cobra» | El texto «+ 761 consultas · plan gratuito» va por encima de los dólares | Se sube ese renglón sobre la cifra | ✅ en el código, falta verlo |

De las capturas salen además dos cosas que no pidió pero se ven mal: en Comparar hay
cláusulas rotuladas «Endosos» y en inglés. Son respuestas guardadas antes del arreglo de
anoche; una pregunta nueva ya sale bien. Se limpia lo guardado con el formato viejo.

## 4. Análisis del chat: por qué responde así

**Cómo está hecho hoy.** La conversación no la lleva el modelo. La lleva un guion escrito
en código: por cada mensaje, el código decide en qué «bloque» va el caso, qué dato falta
y qué frase del catálogo toca. El modelo (Claude Haiku) se usa para dos trabajos pequeños
y separados:

1. **Entender un mensaje**: saca los datos y la intención, mirando solo ese mensaje y la
   lista de datos pendientes.
2. **Decir con otras palabras** la frase que el código ya eligió. Recibe el último mensaje
   y esa frase; no ve la conversación.

Después, el código revisa lo que el modelo escribió con una docena de comprobaciones
(que no agregue preguntas, cifras, la palabra «cobertura», su nombre, «anotado»…) y, si
alguna falla, descarta el texto y pone la frase fija.

**Por qué eso da respuestas sin coherencia.**

- *El guion no previó el camino.* Cada flujo que nadie escribió termina en una frase que
  no viene al caso: entrar por «Preguntar por mi póliza» (C1), pedir un ajustador en una
  consulta (C3), pasar de consulta a reporte (C4), llamar para consultar (L3). Cada uno se
  ha ido tapando con una excepción fechada; el archivo que lleva el turno tiene más de
  1.700 líneas de ramas así.
- *El modelo no tiene con qué razonar.* No ve lo que se habló antes ni el estado del caso;
  no puede «recordar de qué le hablan» porque no se le cuenta.
- *Las reglas le quitan lo que hace bien.* La instrucción de redacción trae tres pasos y
  doce prohibiciones para reescribir una frase. Con tan poco margen, el modelo o repite la
  frase o se sale y se le descarta: en las conversaciones de anoche, entre una de cada
  diez y una de cada tres respuestas cayeron a la frase fija, según la conversación.
- *Dos llamadas al modelo por turno* (entender y redactar) que no se hablan entre sí: una
  entiende sin saber qué se va a decir, la otra dice sin saber qué se entendió más allá de
  una lista de valores.

No es un problema del modelo. Es que se le está usando como corrector de estilo de un
guion, y el guion es el que conversa.

**Qué se puede hacer.**

- **A. Seguir como está y corregir caso por caso.** Las filas C1 a C3 y C5 a C10 se
  arreglan así en una sesión. C4 y L3 vuelven a aparecer con el siguiente camino que nadie
  previó. Es lo que se ha hecho estas semanas.
- **B. Que el modelo lleve la conversación, con el código de guardia** (lo que recomiendo).
  En cada turno el modelo recibe la conversación completa y el estado del caso, y contesta
  él. Para actuar usa un conjunto cerrado de acciones que el código valida antes de
  ejecutar: anotar datos, consultar la póliza, pasar a un ajustador, abrir otro caso,
  cerrar el reporte. Lo que no cambia, porque lo sostiene el código y no el modelo:
  - nada que afirme cobertura, montos o culpa sale sin pasar la guardia de salida;
  - una cita solo sale si la cláusula se recuperó y se verificó;
  - la decisión la firma un ajustador;
  - los datos personales se tapan antes de guardar;
  - lo que escribe la persona entra como dato, nunca como instrucción.

  Con B desaparecen de una vez los fallos de «no entiende / no recuerda / frase que no
  viene al caso», y la instrucción del modelo pasa de doce prohibiciones a decirle quién
  es, qué puede hacer y qué nunca. Costo por turno parecido al de hoy (una llamada en vez
  de dos). Para la llamada es el mismo cerebro, y permite decir la respuesta por frases
  mientras se genera, que es lo que de verdad baja la espera (L4).

  Lo que cuesta: unas dos sesiones de trabajo, y enmendar una decisión de Miguel del
  2026-10-07 («el código decide qué se dice; el modelo solo cómo»). Por eso es decisión
  suya. Las evaluaciones de conversación que ya existen (18 conversaciones reales con
  ataques) sirven para comprobar que B no pierde ninguna garantía.

**Decisión de Miguel, 2026-10-12: camino B.** «Me voy por tus recomendaciones… aplicar la
lógica de negocio para saber qué es mejor y verdaderamente qué es lo correcto». Queda
escrita en `aidlc/spaces/default/memory/project.md`. El diseño está en
`07-el-modelo-lleva-la-conversacion.md`.

## 5. Orden de trabajo

1. **Lo que rompe una prueba hoy, sin esperar decisión:** L1, L2, L5, C1, C2, C3, C9.
2. **Lo que Miguel ha pedido más de una vez:** C5 (datos sin tapar en pantalla propia),
   C10.
3. **Textos y estilos** (a un agente con Sonnet): E1, E2, E3, E4, C7, C8.
4. **El fondo del chat y de la llamada** (según lo que Miguel decida en la sección 4):
   C4, L3, L4.

Cómo se comprueba cada tanda, sin gastar de más ni calentar la Mac: pruebas del módulo
tocado; una llamada simulada y una conversación simulada por tanda (menos de 5 centavos);
y Miguel prueba solo cuando eso ya pasó.

## 6. Preguntas de Miguel de ese día

- **¿Mientras la agente espera se gastan tokens?** No. El modelo cobra por cada turno que
  se le manda, no por el tiempo. Mientras la persona piensa o calla solo corre el
  reconocedor de voz, que cobra por minuto de llamada (centavos). La prisa era solo para
  que se sintiera natural; por eso L2 puede esperar más sin costo.
- **¿Qué pasa al acabarse los 3.000 minutos de GitHub?** Las revisiones dejan de correr
  hasta que empiece el mes; no se cobra nada, salvo que la cuenta tenga un presupuesto de
  gasto por encima de cero (GitHub → Settings → Billing and plans → Budgets and alerts).
- **¿Con qué se reemplaza GitHub Actions sin usar la Mac?** Con nada: el gasto vino de
  subir varias veces por noche a 37 minutos cada una. **Decisión de Miguel, 2026-10-12:**
  se sigue en los servidores de GitHub, con una subida al día como mucho. Acortar la
  corrida queda como mejora posterior, medida.

## 7. Correcciones del 2026-10-13

| # | Lo que dijo Miguel | Causa | Qué se hizo | Estado |
| --- | --- | --- | --- | --- |
| V1 | «No quiero esa verificación, ni liviana, ni completa ni de ninguna forma… quita anotaciones o puntos que indiquen ejecutarla» | La regla del proyecto y el procedimiento de revisión mandaban correr la suite y `scripts/verify.sh` al cerrar cada tanda, y mis notas la dejaban como paso pendiente | Se quitó de `aidlc/spaces/default/memory/project.md` (Code Style), de `.claude/skills/revisar-tanda/SKILL.md` y de `07-el-modelo-lleva-la-conversacion.md`. Lo que verifica es GitHub Actions | ✅ |
| V2 | Los textos antes de llamar: «no se diga tanta cosa», dos renglones centrados | Tres datos en una fila y una recomendación de audífonos debajo | Un renglón con la duración y las llamadas al día, y otro con «Llamada en español.» («Call in English.»). Se retiró la frase de los audífonos del catálogo | ✅ en código, falta verlo |
| V3 | «Debemos solucionar el tema de que la agente no se escuche a sí misma, no es solo un tema de tener audífonos… que no pase el error de ninguna manera» | La única defensa era la cancelación de eco del navegador. Cuando no alcanza, el reconocedor transcribe a la agente y la llamada tomaba esas palabras por las de la persona: cualquier trozo de dos palabras cortaba a la agente y después se atendía como turno | Segunda barrera en el servidor (`voice/own_voice.py`): lo oído mientras la agente suena, y que es lo que la agente está diciendo, se quita antes de que nadie decida nada con ello; lo que la persona diga pegado al eco se conserva. No calla el micrófono: interrumpir con otras palabras sigue funcionando | ✅ con pruebas; falta oírlo en una llamada |

**Lo que V3 no cubre.** Un eco tan deformado que ya no se parece a la frase de la agente
sigue dependiendo del navegador. Y una respuesta de una palabra que coincida con las
últimas palabras de la pregunta, dicha en los 0,8 s siguientes al final estimado, se toma
por eco y hay que repetirla. Si en llamadas reales se ve cualquiera de las dos, el paso
siguiente es que el navegador avise cuándo empieza y termina de sonar cada frase, para
dejar de estimarlo.

### Lo demás del 2026-10-13 (pedido de Miguel: cerrar lo pendiente y las dos opcionales)

| # | Qué | Cómo quedó | Comprobado |
| --- | --- | --- | --- |
| V4 | La voz principal falla a mitad de llamada | Cualquier fallo del proveedor pasa a la voz de respaldo para esa frase y las siguientes (5 minutos; el cupo agotado sigue en una hora), con su evento | Pruebas con dobles; sin oírlo |
| V5 | Lo que dice la agente se veía tapado en la pantalla de quien llama | La pantalla recibe el texto sin tapar; lo guardado y los registros siguen tapados. Si una frase que va a sonar trae una etiqueta, suena una palabra neutra («ese lugar») y nunca la etiqueta | Pruebas; sin verlo en una llamada |
| V6 | Cambiar de idioma a mitad de la llamada | Por petición («in English», «en español», o el nombre del idioma a secas): la agente lo confirma y sigue en el otro idioma, con el reconocedor reabierto en ese idioma. Automático tras dos turnos seguidos: construido y encendido, pero con el reconocedor de un solo idioma casi nunca dispara | **Llamada simulada por el camino real**: cambia y entiende el inglés después del cambio |
| C11 | El reporte no recordaba lo hablado antes de cambiar de tema | Cada caso guarda de cuál viene; el modelo y la pantalla leen la conversación entera | Conversación simulada: abre el reporte ya con lo que se contó |
| C12 | Retomar por chat un caso empezado por voz | Escribir el número de caso en el chat de la misma aseguradora y desde el mismo navegador ata la conversación a ese caso. Cualquier otro número recibe una sola respuesta, sin decir por qué | Pruebas, incluidas las dos de seguridad; sin recorrerlo en el navegador |
| C13 | Rótulo de las cláusulas en el idioma de la póliza | Al recargar el chat y en la bandeja, «Ver mi caso» y «Casos» el nombre de la parte sigue el idioma de la pantalla | Pruebas |
| C14 | «Tengo una duda de mi póliza» se guardaba como la pregunta; preguntar si algo estaba cubierto abría un reporte; antes de abrir caso la agente no recordaba el mensaje anterior | Instrucción precisada, guarda en código y memoria del intercambio previo al caso | Comprensión 20 de 20 por idioma (dos casos nuevos, vistos fallar antes); conversación simulada |
| V7 | La espera antes de cada respuesta en la llamada | La llamada empieza a entender la frase en cuanto llega su final, mientras corre la pausa de 0,7 s, y la voz usa una sola conexión por llamada | **Llamada simulada por el camino real**, mismos cuatro turnos: del fin del habla al primer audio, 4,1 · 2,9 · 3,7 · 3,7 s antes y 2,0 · 3,7 · 2,7 · 2,4 s después (media de 3,6 a 2,7 s). El primer trozo de voz pasó de 0,3–0,8 s a 0,2 s. Lo que queda es el tiempo del modelo (1,7 a 2,3 s por turno; en uno pasó de 3,5 s y el turno siguió por reglas). Bajarlo más pide que la respuesta se empiece a decir mientras el modelo la escribe |
| X1 | El estado del caso bloqueaba ocho tipos al leerse de vuelta (decisión, reglas, revisión, lectura de confirmación) | Declarados, y una prueba recorre lo que cada nodo puede escribir | Prueba que cae al quitar uno |

**Incidente del 2026-10-13.** La subida de la mañana dejó `main` en rojo por dos cosas, con
el resto en verde: un error de tipos (una variable reasignada después de comprobarla) y una
prueba de pantalla que leía el reloj dos veces. Se subió solo el arreglo.

**Sin decidir.** Si el reconocedor vuelve a escuchar los dos idiomas a la vez (lo que haría
fiable el cambio automático, a cambio de volver a leer frases poco claras como portugués), y
si el enlace firmado del caso debe servir también para seguir por chat.

