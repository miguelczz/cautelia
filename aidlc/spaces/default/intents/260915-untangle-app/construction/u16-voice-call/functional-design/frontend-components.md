# Componentes de interfaz — U16 `voice-call`

La consola de llamada: una pantalla donde no se escribe nada. Todo lo que hace
una persona aquí son dos gestos —llamar y colgar— y todo lo que ve es el estado
de la llamada y lo que se está diciendo.

Es también la pantalla más difícil de hacer honesta, porque una llamada tiene
estados que no se ven: el micrófono puede estar tomado y la agente sin oír, la
red puede estar retrasando el audio, la síntesis puede haberse detenido. La regla
de esta consola es que **cada uno de esos estados tiene su forma en pantalla**.

## Jerarquía

```
VoicePage
├── VoiceHeader              nombre de la aseguradora, selector de idioma, tema
├── DemoNotice               (de U6) esto es una demostración con pólizas de ejemplo
├── CallPanel
│   ├── CallButton           llamar / colgar, el único control grande
│   ├── CallState            escuchando · hablando · un momento · terminada
│   └── LevelMeter           que el micrófono está entrando de verdad
├── LiveTranscript
│   ├── TranscriptTurn[]     dos columnas: la asegurada y la agente
│   └── PartialLine          lo que se está diciendo ahora, en gris
└── CallNotice               permiso negado, voz apagada, límite, final
```

`VoiceHeader`, `DemoNotice`, `Button`, `InlineAlert` y el anunciador salen de U6
y de la página de chat; esta unidad añade `CallPanel`, `LiveTranscript` y
`CallNotice`.

## El botón es uno solo

No hay "conectar" y luego "hablar". Un botón grande que dice llamar, y que
mientras la llamada corre dice colgar. Las tres cosas que pasan al pulsarlo
—pedir el micrófono, abrir la sesión, abrir el socket— son una sola espera para
quien mira, con un indicador de progreso y sin pasos numerados.

El orden interno sí importa y es el de BR1.2: **primero el micrófono**. Si el
navegador lo niega, no se llegó a crear nada y la consola lo dice con la frase
del catálogo, más cómo dar el permiso, más el enlace al chat.

## Los cuatro estados, y por qué se ven

| Estado | Qué se ve | Por qué |
| --- | --- | --- |
| Escuchando | El medidor de nivel se mueve | Es la única prueba de que el micrófono entra. Sin él, una persona con el micrófono silenciado por el sistema habla dos minutos contra una pared |
| Hablando | La línea de la agente crece | Para saber que lo que se oye es la respuesta y no un eco |
| Un momento | La frase de espera, escrita | Es la misma `Waiting` que se sintetiza: se oye y se lee |
| Terminada | El motivo del final, del conjunto cerrado | Una llamada que se corta sin decir por qué es la peor pantalla posible |

El medidor de nivel se calcula **en el navegador**, con las mismas muestras que
se están mandando. No pide nada al servidor y no es telemetría: es un número que
ya está en la mano.

## La transcripción, redactada y en vivo

Dos columnas, la asegurada a un lado y la agente al otro, como en el chat. Lo
que llega por el socket ya viene redactado (BR7.2) y la consola **no redacta
nada**: si redactara, habría dos implementaciones de la misma regla y una se
quedaría atrás.

Los parciales se pintan en gris y se reemplazan cuando llega su final. Un parcial
nunca se guarda en el historial de la pantalla: se pinta y se sustituye.

## La interrupción se ve

Cuando llega `stop_audio`, la consola vacía la cola de reproducción y la línea de
la agente se marca como interrumpida. Verlo importa: sin marca, quien prueba la
demostración no distingue "la interrumpí" de "se cayó el audio".

## Audio en el navegador

Dos `AudioWorklet`, uno por sentido, y nada más.

- **Captura.** `getUserMedia` con `echoCancellation`, `noiseSuppression` y
  `autoGainControl` en `true` (BR4.2). El nodo remuestrea a 24 kHz, convierte a
  PCM de 16 bits y manda trozos de 20 ms por el socket.
- **Reproducción.** Una cola de muestras que el nodo consume a ritmo constante.
  `stop_audio` la vacía **entera** en el mismo instante, que es lo que pone la
  parada por debajo de 300 ms (BR4.3).

El `AudioContext` se crea dentro del gesto de pulsar el botón, porque Safari
—escritorio e iOS— no lo arranca fuera de uno. Es la misma razón por la que el
micrófono se pide ahí y no antes.

## Accesibilidad

La consola tiene un problema propio: su contenido principal es audio, y el
arnés del proyecto prueba pantallas.

- **Todo lo que se oye, se lee.** La transcripción en vivo es el equivalente
  textual de la llamada, incluida la apertura y las frases de espera.
- La región de la transcripción es una zona en vivo cortés; los cambios de
  estado de la llamada se anuncian por el anunciador de U6, que ya existe.
- El botón de llamar es alcanzable y operable con teclado, y su etiqueta cambia
  con el estado —no solo su color.
- El medidor de nivel es decorativo y está oculto para el lector de pantalla: lo
  que informa de verdad es el estado, que sí se anuncia.
- Ninguna información depende solo del color: los dos hablantes se distinguen por
  su posición y su etiqueta, no por su tinte.

## Lo que se reúsa de U6 y de U13

- El armazón, el selector de tema y el de idioma, el aviso de demostración, el
  botón, la alerta en línea y el anunciador.
- El patrón de `chat-copy.ts`: una tabla tipada de claves que el servidor manda y
  la pantalla resuelve. La consola tendrá su `voice-copy.ts` con la misma forma,
  y **entra al chequeo de frases** que ya comprueba que ninguna clave declarada
  por el servidor falte en la tabla del navegador.
- El patrón de `chat-events.ts`: un reductor puro del flujo de eventos, probado
  sin navegador.

## Lo que esta pantalla no tiene

- **Avisos de límite público** —los treinta segundos, la ventana de retoma, la
  voz de respaldo—: son de U17.
- **Cambio de idioma a mitad de llamada**: es de U18.
- **Reproducir lo que se dijo**: no hay audio guardado (BR7.1).

## Para Miguel

Esto es una recomendación, no una decisión tomada: la consola es una pantalla que
ve quien evalúa el producto, y esas las decide él. Lo de arriba se puede
construir mientras tanto y cambiar de aspecto después sin tocar el servidor,
porque lo único que cruza el socket son estados y claves.
