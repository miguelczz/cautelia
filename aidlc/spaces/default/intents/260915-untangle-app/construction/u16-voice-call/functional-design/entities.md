# Entidades — U16 `voice-call`

Una sola entidad propia, `CallSession`, que es la que `components.md` le asigna a
esta unidad. Todo lo demás que la llamada maneja o es de otro dueño —el caso, la
traza, la configuración de voz— o no es una entidad, y el porqué está al final.

---

## `CallSession` — una llamada

La fila que existe mientras dura una llamada y sobrevive para explicarla después.
Es el equivalente de `ChatSession` en el otro canal, y comparte con ella la forma
de identificar al visitante.

| Campo | Tipo | Qué es |
| --- | --- | --- |
| `call_id` | texto | El identificador de la llamada. Lo emite el servidor al crear la sesión |
| `tenant_id` | aseguradora | Quién atiende. Lo fija la sesión, no la pantalla |
| `case_id` | texto o nulo | El caso que la llamada abrió o retomó. Nulo hasta que hay uno |
| `visitor_key_digest` | texto | El resumen de la clave del visitante, el mismo que usa el chat |
| `language` | idioma | El idioma de la llamada. Dato, nunca rama de código |
| `voice_mode` | `primary` o `fallback` | Se fija al crear la sesión y no cambia a mitad |
| `state` | estado de llamada | Dónde está: ver abajo |
| `started_at` | instante | Cuándo se creó la sesión |
| `ended_at` | instante o nulo | Cuándo terminó. Nulo mientras vive |
| `end_reason` | motivo o nulo | Uno de los cinco del conjunto cerrado |
| `resume_until` | instante o nulo | Hasta cuándo se puede retomar tras un corte |

**Lo que no lleva, a propósito.**

- **Ningún audio, ni una referencia a audio.** BR7.1: no hay archivo, no hay
  ruta, no hay identificador de grabación. Si el campo no existe, nadie lo llena
  "temporalmente".
- **Ninguna transcripción.** La transcripción redactada es del caso (U4) y de la
  traza (U5); la llamada no guarda una segunda copia. Dos copias de lo mismo se
  desincronizan, y la que se olvida de borrar es siempre la segunda.
- **Ningún límite de visitante.** Los carriles públicos son de U17. `CallSession`
  guarda lo que pasó, no lo que estaba permitido.

### Los estados de una llamada

Un conjunto cerrado de cinco, y la entidad no admite otro.

| Estado | Qué significa | A dónde va |
| --- | --- | --- |
| `connecting` | La sesión existe; el socket todavía no se autenticó | `live` o `ended` |
| `live` | El socket está autenticado y la llamada corre | `ended` |
| `ended` | Terminó por cualquiera de los seis motivos | — |

Tres, no cinco: `speaking` y `listening` son estado de la **conversación** y
viven en memoria mientras la llamada corre, no en la fila. Se mandan por el
socket para que la consola los dibuje, y no se persisten porque nadie los
consulta después.

### Los seis motivos de final

`hangup` (colgó), `silence` (el tercer silencio), `max_duration` (se agotó el
tiempo), `dropped` (se cortó la conexión), `error` (falló algo del camino) y
`completed` (el reporte quedó completo y la agente cerró).

Cerrado a propósito: la consola tiene una frase por cada uno y la bandeja una
lectura, y un séptimo no puede entrar sin que las dos se enteren.

**`completed` se añadió al cablear el cierre**, no al diseñar la entidad, y
merece decirse porque es la razón por la que un conjunto cerrado se revisa
cuando se usa. Eran cinco y ninguno decía esto: `hangup` es "la persona colgó",
que no es lo que pasa cuando la agente termina de leer el número de caso y se
despide, y `silence` dejaría el caso esperando al asegurado justo cuando ya no
espera nada. Un conjunto cerrado que no puede expresar un desenlace real no está
protegiendo: está escondiendo, y la fila acabaría diciendo algo que no ocurrió.

---

## Lo que no es una entidad, y por qué

- **El turno de voz.** Es un tramo de la conversación y su registro es del caso y
  de la traza, que ya existen. Una entidad `VoiceTurn` sería una tercera copia de
  lo mismo.
- **La interrupción.** Es un evento de traza (BR8.2), no una fila. Lo que se
  necesita de ella es su marca de tiempo, y la traza es donde viven las marcas.
- **El detector de turno y el de silencio.** Son relojes, no datos. Viven en
  memoria mientras la llamada corre y mueren con ella.
- **El token del socket.** Es una credencial de vida corta ligada al `call_id`,
  y se valida sin guardarse: lo que se guarda de una credencial es la forma de
  robarla.
- **La cola de audio del navegador.** Vive en el navegador y se vacía con
  `stop_audio`. No cruza la frontera.

---

## Lo que se consume y no se define aquí

| Qué | De quién | Para qué |
| --- | --- | --- |
| `InboundTurn`, `TurnEvent` y sus cinco ramas | U12 (C-14) | Hablar con el grafo |
| `SpeechToText`, `TextToSpeech`, `Transcript`, `VoiceRef`, `SPEECH_AUDIO` | U5 y U15 (C-16) | Oír y hablar |
| El bloque `voice` de la aseguradora | U2 y U15 (C-25) | Qué voz, qué modelo, qué idioma |
| La clave del visitante y su resumen | U2 | Saber que es el mismo navegador |
| El registro de divulgación | U10 | Dejar constancia de la apertura |
| La tabla de deletreo | U11 | Leer los caracteres confundibles |
| El punto único de salida | U3 | Redactar antes de hablar y antes de mostrar |

## Resumen

Una entidad, tres estados, seis motivos de final. Lo que no está aquí está en el
caso, en la traza o en la configuración, y esa es la razón por la que una llamada
que termina no deja nada que haya que borrar aparte de su propia fila.
