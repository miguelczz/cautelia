# Especificación funcional — U16 `voice-call`

La llamada de voz desde el navegador, sobre el mismo grafo que ya atiende el
chat. Esta unidad no tiene conversación propia: tiene **oídos, boca y reloj**. Lo
que la agente dice lo decide `handle_turn` igual que en el chat; lo que U16
añade es cuándo escuchar, cuándo hablar, cuándo callarse y qué hacer con el
silencio.

De ahí que sus tres metas no sean de contenido sino de tiempo: que del fin del
habla al primer audio pasen menos de 500 ms en la mitad de los turnos (NFR1),
que una interrupción calle a la agente en menos de 300 ms (NFR2) y que después
de una interrupción la conversación siga sin perder estado más del 10 % de las
veces (NFR3).

## Sources

- `../../../inception/units-generation/unit-of-work.md` — definición de U16, sus seis historias y sus dependencias
- `../../../inception/user-stories/stories.md` — US1.21, US1.22, US1.23, US1.24, US1.26, US1.27 con sus criterios
- `../../../inception/requirements-analysis/requirements.md` — FR3.1 a FR3.6, FR1.1, FR1.3, FR1.5, FR2.6, FR7.1, FR8.6, FR10.2, FR14.4, NFR1, NFR2, NFR3, NFR19
- `../../../inception/contract-design/contract-summary.md` — C-08 (llamada), C-14 (turno), C-16 (voz), C-25 (configuración), C-29 (transporte, que esta unidad cierra)
- `../../u15-speech-providers/code-generation/code-summary.md` — el motor de voz que ya existe
- `../../u13-chat/` — el mismo grafo por el otro canal, y el patrón de sesión de visitante
- `functional-design-questions.md` — las ocho decisiones de esta etapa

## Assumptions & Open Questions

None.

C-29 estaba abierto y se cierra en D1. Las dos preguntas que quedan para Miguel
—cómo se ve la consola y cuándo se mide en vivo— no bloquean nada: la primera
tiene recomendación construible y la segunda es un comando a mano.

---

## Flujo 1 — Conectar una llamada (US1.21)

El recorrido de Ana, que abre la consola de Sunmeadow Auto en inglés.

1. La consola pregunta `GET /tenants/{t}/voice/availability` **antes de mostrar
   el botón activo**. La respuesta trae si hay voz, con qué modo, los límites y,
   si lo hay, hasta cuándo se puede retomar un caso cortado.
2. Ana pulsa llamar. Lo primero que ocurre es **pedir el micrófono**, no abrir la
   sesión (BR1.2). El orden importa: si el navegador niega el permiso, no debe
   quedar un caso vacío en la bandeja.
3. Con el micrófono concedido, la consola hace `POST /tenants/{t}/voice/sessions`
   con el idioma y, si lo hay, el caso a retomar. Recibe `call_id`, el modo de
   voz, la duración máxima y el objeto `transport`.
4. La consola abre el WebSocket del mismo origen y manda como **primer cuadro**
   el token (BR1.4). El servidor lo valida, lo ata a esa llamada y responde
   `{"type":"state","value":"listening"}`.
5. Desde ese momento el navegador manda PCM de 20 ms y recibe audio y eventos.
   La transcripción en vivo aparece en la consola **ya redactada** (BR7.2).

**Micrófono negado.** No hay llamada y no hay caso: la consola explica cómo dar
el permiso y ofrece el chat, con texto del catálogo (BR1.2).

**Colgar.** Ana pulsa colgar; la consola manda `{"type":"hangup"}` y cierra. El
servidor cierra el caso en el estado que corresponda a lo capturado —completo si
lo está, `esperando al asegurado` si no— y el último cuadro que manda es
`{"type":"ended","reason":"hangup"}`, que es lo que la consola muestra como causa
del final (BR1.6).

**Navegadores.** La lista declarada de U6: las dos últimas versiones mayores de
Chrome, Edge, Firefox y Safari de escritorio, Safari en iOS y Chrome en Android.
`getUserMedia` exige origen seguro y un gesto de la persona en los tres, y
`AudioWorklet` está en todos desde hace varias versiones mayores; el paso 2 del
recorrido ya es ese gesto.

---

## Flujo 2 — La apertura (US1.22)

Conectada la llamada, **antes de cualquier pregunta**, la agente dice la apertura
de voz del catálogo. No es la del chat: dice además que la llamada queda
transcrita, y termina preguntando si hay heridos.

1. Se compone con las claves `voice.opening.*`, igual que `chat.opening.*`: la
   divulgación, las capacidades y, solo si la aseguradora tiene la cotización
   activa, la de cotizar (BR2.2).
2. Se sintetiza y se emite.
3. Cuando **termina de emitirse**, se registra la divulgación por el registro de
   U10 con su hora, su idioma y el canal `voice` (BR2.3). La hora es la del fin
   de la emisión y no la del comienzo, porque AC1.24.4 pide saber si alcanzó a
   completarse.
4. Si Ana interrumpió antes de que terminara, la apertura **se repite entera**
   antes de la primera pregunta (BR4.5). Media divulgación no es divulgación.

La apertura es compuerta dura: mientras no esté registrada, el manejador del
turno no atiende nada (BR2.1). Es la misma regla que ya cumple el chat.

---

## Flujo 3 — El turno hablado (US1.23)

El ciclo que se repite hasta que la llamada termina.

1. **Escuchar.** El PCM entrante va al puerto `SpeechToText`. Vuelven transcritos
   parciales y finales; los parciales pintan la consola, los finales se acumulan.
2. **Detectar el fin del habla.** Un transcrito final seguido de
   `end_of_speech_ms` sin nada nuevo cierra el turno de Ana (BR3.1). La marca de
   tiempo del evento es la del último final, no la del vencimiento (D4).
3. **Decidir si se entendió.** Si el texto acumulado está vacío, o la confianza
   mínima de sus palabras está bajo el umbral, no se anota nada y la agente pide
   que lo repita (BR3.4). A la tercera vez ofrece guardar el caso o pasarlo a un
   ajustador —nunca devolver la llamada—, y un turno bueno reinicia la cuenta.
4. **Pedir el turno al grafo.** Se arma `InboundTurn` con `channel="voice"` y el
   texto acumulado, y se consume `handle_turn`. Es el mismo contrato C-14 que usa
   el chat, con el mismo `case_id`.
5. **Hablar.** Cada evento del grafo se convierte en audio por el puerto
   `TextToSpeech` (BR3.6):
   - `Waiting` se sintetiza **de inmediato**, porque para eso lleva el texto ya
     resuelto y no solo la clave;
   - `PartialText` se sintetiza en el orden en que llega, para que la voz empiece
     antes de que la respuesta esté cerrada;
   - `FinalText` cierra el turno hablado;
   - `Handoff` y `TurnError` se dicen con su texto y terminan el turno.
6. **Marcar el primer audio.** El primer byte sintetizado del turno emite el
   evento de latencia que cierra NFR1 (BR8.1).

**Deletreo y confirmación (AC1.23.2).** Cuando un dato que se anota carácter a
carácter —la placa, el número de póliza— trae un carácter de la lista versionada
de confundibles o una palabra bajo el umbral de confianza, la agente lo lee con
`spell_for_readback` de U11 y **espera confirmación** antes de anotarlo (BR3.5).
Esta unidad es el primer consumidor de producción de esa tabla: existía desde
U11, con sus pruebas, y no la llamaba nadie.

**El cierre (AC1.23.4).** Cuando el caso está completo, la agente resume en tres
frases, dice qué sigue y dice el número de caso con el nombre de la aseguradora y
los seis dígitos **uno a uno**, con "zero" y nunca "oh" (BR3.7). La transcripción
guarda los seis dígitos separados, que es lo que la evaluación del hito compara.

---

## Flujo 4 — Interrumpir (US1.24)

Mientras la agente habla, U16 sigue escuchando.

1. Llega un transcrito de Ana con al menos `barge_in_min_words` palabras, o con
   una palabra sobre el umbral de confianza (BR4.1). Ruido de carro y eco del
   altavoz no llegan aquí: los quita la cancelación del navegador y los filtra
   ese piso (BR4.2).
2. U16 **deja de sintetizar** y manda `{"type":"stop_audio"}`.
3. El navegador **vacía su cola de reproducción** al recibirlo. La marca de
   parada se emite a la traza (BR8.2). Esto es lo que mide NFR2, y se mide en el
   cliente porque el audio encolado vive ahí.
4. La conversación sigue con lo que Ana dijo. Si estaba en mitad de una lectura
   de confirmación, la agente confirma **solo el dato corregido** y pasa a la
   pregunta siguiente; no vuelve a leer el bloque entero (BR4.4).
5. Si lo interrumpido era la apertura y no había terminado, se repite entera
   (BR4.5).

---

## Flujo 5 — Los silencios (US1.26)

Tres tiempos iguales, cada uno contado **desde que la agente termina de hablar**,
con la tolerancia que fija la configuración de la aseguradora (BR5.1).

| Silencio | Qué dice | Qué deja |
| --- | --- | --- |
| Primero | "Are you still there?" | La llamada sigue |
| Segundo | La oferta de guardar el caso o pasarlo a un ajustador | La llamada sigue |
| Tercero | La despedida | El caso en `esperando al asegurado` y la llamada terminada |

Ninguna de las tres ofrece devolver la llamada: la devolución es `C3` y no
existe, y el principio P7 prohíbe ofrecer lo que no está construido (BR5.3).

El reloj de silencio se **detiene mientras la agente habla** y se reinicia en
cuanto calla: si no, la propia respuesta de la agente contaría como silencio de
Ana.

---

## Flujo 6 — El corte y la retoma (US1.27)

**Cuando se corta.** El WebSocket se cierra sin `hangup`. El caso queda
`esperando al asegurado` con los campos confirmados hasta ahí y con
`resume_until`, y aparece así en la bandeja (BR6.1). No queda audio de ninguna
clase: nunca lo hubo (BR7.1).

**Cuando Ana vuelve a llamar.** Desde el mismo navegador:

1. La llamada busca caso abierto por el **resumen de la clave del visitante** y
   por nada más (BR6.3). La póliza de ejemplo no entra en la búsqueda: la
   comparten todos los visitantes, y buscarla abriría el caso de otro. Es el
   criterio `[bloquea]` AC1.27.3.
2. Encontrado, la agente dice **primero la apertura completa** y después ofrece
   continuar: "I see you have an open case. Shall we continue with it?" (BR6.2).
3. Si Ana acepta, la conversación sigue desde el último bloque confirmado, por la
   reanudación del punto de control que ya existe (U12).
4. Si Ana dice que llama por otro accidente, se abre un caso nuevo y el anterior
   queda intacto (BR6.4).
5. Si el caso ya estaba decidido, la agente resume la decisión y el comentario
   antes de preguntar si necesita algo más (BR6.5).

---

## El protocolo del socket (C-29, cerrado)

Un conjunto cerrado por cada sentido. Cerrarlo es lo que permite que el
comprobador de tipos obligue a cubrir todas las ramas al serializar, igual que
`TurnEvent` en C-14.

**Del navegador al servidor**

| Cuadro | Forma | Cuándo |
| --- | --- | --- |
| `auth` | texto | El primero, siempre. Lleva el token de C-08 |
| audio | binario | PCM16LE mono 24 kHz, trozos de 20 ms |
| `hangup` | texto | Al colgar |

**Del servidor al navegador**

| Cuadro | Forma | Qué dice |
| --- | --- | --- |
| `state` | texto | `connecting`, `listening`, `speaking`, `ended` |
| `transcript` | texto | Un trozo de transcripción **ya redactada**, con quién habló y si es final |
| audio | binario | PCM16LE mono 24 kHz de la síntesis |
| `stop_audio` | texto | Vacía la cola de reproducción ya (interrupción) |
| `case` | texto | El caso quedó atado: su identificador y su número |
| `notice` | texto | Una clave del catálogo: degradación, límite, voz apagada |
| `ended` | texto | `hangup`, `silence`, `max_duration`, `dropped`, `error` |

**Lo que el protocolo no lleva.** Ningún texto de interfaz: la consola resuelve
cada `copy_key` con el catálogo, igual que el chat. Y ningún audio hacia atrás:
lo que se dijo no se puede volver a pedir, porque no se guarda.

---

## Modelo de entidades (vista derivada)

`CallSession` es la única entidad propia de esta unidad. Los detalles están en
`entities.md`.

---

## Resumen de reglas (vista derivada)

38 reglas, repartidas en ocho familias: la conexión, la apertura, el turno
hablado, la interrupción, los silencios, la retoma, la privacidad y las trazas.
Tres llevan `[bloquea]`: la divulgación antes de cualquier pregunta, el caso
ajeno que no se abre y el audio que no se persiste. Están en `rules.md`.

---

## Lo que esta unidad no construye

- **Los límites públicos** —tres minutos, una llamada al día, aviso a los treinta
  segundos, ventana de retoma de quince minutos— y la elección entre voz
  principal y de respaldo: son de U17, que va en la pasada de publicación. U16
  deja la forma de C-08 y **lee** los límites que le den; hoy los sirve con los
  valores de la configuración de la aseguradora, sin carriles por visitante.
- **El español y el cambio de idioma**: U18. U16 construye todo en inglés y deja
  el idioma como dato, no como rama.
- **La conversación**: es del grafo (U12) y de sus nodos.
- **Los adaptadores de voz**: son de U15 y no se tocan.
