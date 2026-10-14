# Decisiones de diseño — U16 `voice-call`

Esta unidad llegaba con **un contrato abierto**: C-29, el transporte de audio en
tiempo real, que `contract-summary.md` dejó "pendiente del experimento 1". El
experimento corrió (`scripts/experimento-1.py`) y U15 se construyó con su
resultado, así que aquí se cierra.

Ninguna de estas decisiones necesita a Miguel: son técnicas, y la norma del
proyecto es que la sesión principal recomienda y avanza. Las dos que sí son
suyas —cómo se ve la consola y qué se gasta midiendo en vivo— están al final,
marcadas.

---

## D1 — El transporte es un WebSocket propio con PCM, no LiveKit ni Pipecat

**Qué decidía el experimento 1 según ADR-009:** entre LiveKit Agents y Pipecat,
y con ello el proveedor de WebRTC.

**Lo que pasó:** el experimento eligió el camino directo. U15 no usa ninguno de
los dos: habla el WebSocket de Deepgram y el de Cartesia con `websockets`, sin
SDK, y deja los dos puertos de C-16 llenos. Un framework de orquestación de voz
encima duplicaría exactamente eso.

**Decisión.** El navegador manda audio al servidor por un **WebSocket del mismo
origen**, con PCM de 16 bits, mono, a 24 kHz —`SPEECH_AUDIO`, el único formato
del aplicativo— y recibe el audio sintetizado por el mismo socket. La captura y
la reproducción en el navegador van con `AudioWorklet`, que es API estándar y no
una dependencia.

**Qué se gana.** Cero dependencias nuevas en los dos lados. Cero cuentas de
proveedor nuevas, que es lo que exige la regla de gasto: un SFU de WebRTC
alojado es una suscripción, y autoalojarlo es un servicio más que mantener. El
formato no se convierte dos veces: `SPEECH_AUDIO` entra al socket y sale del
socket, y la conversión de la frontera vive donde `ports.py` ya dice que vive
("U16 convierte en la frontera de su transporte").

**Qué se pierde, dicho sin adornos.** WebRTC va sobre UDP y degrada perdiendo
paquetes; un WebSocket va sobre TCP y degrada **acumulando retraso**, porque
retransmite. En una red mala la llamada no se oye entrecortada: se atrasa. Para
una demostración que se enseña con conexión decente es un intercambio aceptable,
y el aviso honesto es que esto no es un softphone. Queda escrito aquí y en
ADR-009 para que nadie lo descubra midiendo.

**Qué deja de estar pendiente.** C-29 queda cerrado y el objeto `transport` de
C-08 toma forma: `{"kind": "websocket", "url": "...", "token": "..."}`.

## D2 — El proceso es el mismo

C-29 dejaba abierto "si el proceso de voz es el mismo o uno aparte". Con D1 no
hay librería que exija lo contrario: la ruta del WebSocket vive en la misma
aplicación FastAPI que el chat y la bandeja. Un segundo proceso se justificaría
por aislamiento de fallos o por escala, y ninguna de las dos aplica a una
demostración con una llamada por visitante al día.

## D3 — El token del socket viaja en el primer cuadro, no en la URL

El navegador no puede poner cabeceras en un `WebSocket`, así que la costumbre es
colgar el token de la cadena de consulta. No se hace: un token en una URL acaba
en los registros del servidor y en el historial del navegador.

**Decisión.** El socket se abre sin credencial en la URL; el **primer cuadro de
texto** es `{"type": "auth", "token": "..."}`, y el servidor cierra la conexión
si ese cuadro no llega válido dentro del plazo. La galleta del visitante ya
viaja en el apretón de manos por ser del mismo origen: el token no identifica al
visitante, ata el socket a **esa** llamada.

## D4 — El fin del habla lo decide U16, no el proveedor (PA-6)

`unit-of-work.md` asigna a esta unidad la definición de PA-6. El puerto
`SpeechToText` de C-16 entrega `Transcript` con `is_final` y nada más: no
publica el `speech_final` de Deepgram. Ampliar el puerto sería cambiar un
contrato del que U15 es dueña para un dato de un solo proveedor.

**Decisión.** El fin del habla es **un transcrito final seguido de un silencio
de `end_of_speech_ms`** sin transcrito nuevo. El temporizador es de U16, vive en
la configuración de la aseguradora y su valor de partida es 700 ms. La marca de
tiempo del evento es la del **último transcrito final recibido**, no la del
vencimiento del temporizador: el retraso de esperar el silencio es del detector
y no de la respuesta, y cargárselo a NFR1 mediría otra cosa.

AC1.23.5 pide publicar también la variante "última palabra audible": sale de
`WordHypothesis.end_s` del último final, y el reporte del hito lleva las dos
columnas con su nombre.

## D5 — La interrupción la corta el navegador, avisado por el servidor

NFR2 exige menos de 300 ms desde la marca de interrupción hasta que la síntesis
se detiene, medidos **en el cliente**. El servidor no puede retirar el audio que
ya mandó: en el momento en que detecta la interrupción, el navegador tiene
cientos de milisegundos encolados.

**Decisión.** Al detectar interrupción el servidor deja de sintetizar **y manda
un cuadro `stop_audio`**; el navegador vacía su cola de reproducción en cuanto
lo recibe. El presupuesto de NFR2 es entonces detección + un viaje de red + el
vaciado, y no la longitud de la cola.

## D6 — Ruido y eco: cancelación en el navegador más un piso de habla

AC1.24.3 exige que ni el ruido del carro ni la propia voz de la agente saliendo
por el altavoz de un portátil detengan la síntesis.

**Decisión.** Dos capas, y ninguna es un detector acústico propio:

1. El micrófono se pide con `echoCancellation`, `noiseSuppression` y
   `autoGainControl` activados. La cancelación de eco del navegador es la misma
   que usan las videollamadas y es lo que quita el altavoz del portátil.
2. La interrupción **no la dispara un parcial cualquiera**: exige un transcrito
   con al menos `barge_in_min_words` palabras (dos de partida) o una palabra con
   confianza sobre el umbral. Un ruido que el modelo transcribe como una sílaba
   suelta no calla a la agente.

## D7 — La retoma se ata al navegador, nunca a la póliza

AC1.27.3 es criterio `[bloquea]`: la póliza de ejemplo la comparten todos los
visitantes, así que identificarse con ella no puede abrir el caso de otro.

**Decisión.** La llamada busca caso abierto **solo** por el resumen de la clave
del visitante, igual que `chat.session.find_live`. El número de póliza no entra
nunca en esa búsqueda. La regla se escribe como BR6.3 y su prueba planta un caso
de otro navegador con la misma póliza.

## D8 — La consola vive en `pages/voice/`, no en `modules/voice/`

`unit-of-work.md` dice `app/frontend/src/modules/voice/`. Ese directorio no
existe: U6 fijó `pages/<pantalla>/` y U13, U14 y las demás lo siguieron. Se
sigue la convención construida, y la desviación queda aquí escrita.

---

## Lo que sí es de Miguel

### Q1 — Cómo se ve la consola de llamada

Es una pantalla que ve quien evalúa el producto, así que la decide él. La
recomendación está en `frontend-components.md` y se puede construir mientras
tanto: la consola reusa la base de U6 y el patrón de la página de chat, con un
botón grande de llamar, la transcripción redactada en vivo a dos columnas
(asegurada y agente) y un estado de llamada visible. No bloquea el trabajo del
servidor.

### Q2 — Medir la latencia contra los proveedores reales

NFR1, NFR2 y NFR3 son **metas de hito**, no de cada entrega, y medirlas de
verdad gasta. La unidad se construye y se prueba entera con el reconocedor y la
síntesis simulados; la medición en vivo es un comando a mano, como
`voice:contract-live` de U15, y no corre sin que Miguel lo diga.

## Sources

- `../../../inception/contract-design/contract-summary.md` — C-08, C-14, C-16, C-29
- `../../../inception/units-generation/unit-of-work.md` — U16 y sus notas
- `../../u15-speech-providers/code-generation/code-summary.md` — lo que dejó el motor de voz
- `app/backend/src/untangle/providers/ports.py` — `SPEECH_AUDIO`, `SpeechToText`, `TextToSpeech`
- `app/config/tenants/*/tenant.yaml` — el bloque `voice` de C-25

## Assumptions & Open Questions

None.
