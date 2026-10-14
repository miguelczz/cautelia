# Resumen de código — U16 `voice-call`

La llamada de voz desde el navegador: la agente escucha, entiende, responde,
calla cuando la interrumpen y guarda el caso si la llamada se corta. Sobre el
mismo grafo que ya atiende el chat, así que el mismo guion contado por voz deja
los mismos campos.

**104 archivos, 10.150 líneas, seis tandas.** 257 pruebas propias del servidor y
33 del navegador en verde; formato, lint, tipos, los 35 contratos de importación,
los identificadores literales, los contratos generados y los cuatro chequeos de
contenido en verde en local; la compuerta de GitHub Actions sobre `main` es la
autoritativa.

Esta unidad **cierra C-29**, el último contrato que la fase de incepción había
dejado abierto.

**Tres cosas faltaban al escribir este resumen la primera vez**, y se arreglaron
antes de darlo por cerrado. Las tres eran de la misma clase --algo declarado sin
nadie que lo produjera-- y se encontraron al preguntar qué faltaba para cerrar,
no revisando el código:

1. `PERF-U16.1` --lo que esta unidad añade entre el fin del habla y el primer
   audio, ≤ 60 ms-- estaba declarada con su comando y **nadie la medía**. Ya se
   mide: **p95 3,9 ms** sobre veinte turnos, y la cifra se imprime en cada corrida
   y no solo cuando falla.
2. `PERF-U16.2` --del cuadro `stop_audio` a la orden de vaciar, ≤ 50 ms-- igual, y
   además medía menos de lo que su nombre decía: lo que pasa dentro del
   `AudioWorklet` corre en el hilo de audio y el documento de pruebas no lo tiene.
   Ahora se mide lo que el navegador controla, **y el orden**: la orden de vaciar
   sale antes de que la pantalla se entere.
3. La tarea de hito que la unidad declaró, `evals:voice`, **no existía**: lo
   construido se llama `voice:call-live` y corre una grabación, no el conjunto.
   Los dos hechos quedan escritos y el corredor del conjunto, diferido con las
   grabaciones.

Los tres quedan en la enmienda del 2026-09-29 de
`../nfr-requirements/performance-requirements.md`, y lo diferido en
`pasada-de-publicacion.md`.

## Lo que construyó

| Pieza | Dónde | Qué resuelve |
| --- | --- | --- |
| La fila de la llamada | `voice/models.py`, `voice/session.py`, dos migraciones | Una llamada por navegador, con seis motivos de final y **sin un solo campo de audio** (BR1.6, BR7.1) |
| El token del socket | `voice/tokens.py` | Vive un minuto, viaja en el primer cuadro y nunca en la URL; las cuatro formas de token malo responden igual (BR1.4, BR1.5) |
| El protocolo | `voice/wire.py` | Dos vocabularios cerrados, uno por sentido; el control en texto y el audio en binario (C-29) |
| La apertura | `voice/opening.py` | Va antes de cualquier pregunta y se registra con la hora del **fin** de la emisión (BR2.1 a BR2.4) |
| El fin del habla | `voice/turn_detection.py` | Un final seguido de silencio, con la marca del último final y no la del vencimiento (BR3.1, D4) |
| Los silencios | `voice/silence.py` | Tres peldaños; el tercero se despide antes de colgar y ninguno ofrece devolver la llamada (BR5.1 a BR5.3) |
| No haber entendido | `voice/retry.py` | Transcripción vacía o bajo el umbral: no se anota nada y se pide que lo repita (BR3.4) |
| La interrupción | `voice/barge_in.py` | El piso de palabras y de confianza que separa una corrección del eco del altavoz (BR4.1, BR4.2) |
| El deletreo | `voice/readback.py`, `voice/case_number.py` | Un código dudoso se lee de vuelta antes de anotarlo; el número de caso se dice dígito a dígito, con "zero" y nunca "oh" (BR3.5, BR3.7) |
| El cierre y la retoma | `voice/closing.py`, `voice/resume.py`, `voice/notice.py` | El reporte completo se despide con su número; un corte deja el caso retomable y al volver se ofrece continuar (BR6.1 a BR6.5) |
| El ritmo de la llamada | `voice/loop.py` | El único sitio con el socket, el reconocedor y la síntesis a la vez: quién habla, quién escucha y quién calla |
| Las cuatro latencias | `voice/latency.py` | Tiempos e identificadores, nunca contenido: sin ellos NFR1, NFR2 y NFR3 no se pueden medir (BR8.1 a BR8.4) |
| Las tres rutas y el socket | `server/voice_routes.py` | C-08 con el objeto `transport` ya concreto, y el apretón de manos de C-29 |
| La consola | `app/frontend/src/pages/voice/` | Dos gestos, cuatro estados con forma en pantalla y la transcripción en vivo ya redactada |
| Los dos nodos de audio | `app/frontend/public/voice-*-worklet.js` | Captura a PCM de 20 ms con su medidor de nivel, y una cola de reproducción que se vacía entera |
| El conductor de DS-5 | `evals/drivers/voice.py` | Mete una grabación por el mismo transporte por el que entra un navegador |
| El chequeo de avisos | `workspace/voice_phrases.py` | Que toda clave que el servidor manda por el socket, la consola sepa decirla |

## Las decisiones de la unidad

**C-29 se cierra con un WebSocket del mismo origen, no con WebRTC.** PCM de 16
bits mono a 24 kHz —el único formato del aplicativo— con `AudioWorklet` en el
navegador. Cero dependencias nuevas y cero cuentas nuevas. El costo está escrito
y no escondido: WebRTC va sobre UDP y se degrada **perdiendo paquetes**; un
WebSocket va sobre TCP y se degrada **acumulando retraso**. En una red mala la
llamada no suena entrecortada: se atrasa. Por eso la cola de audio está acotada a
cinco segundos.

**El fin del habla lo define esta unidad, no el proveedor.** El puerto entrega
`Transcript` con `is_final` y nada más; ampliarlo para el `speech_final` de un
proveedor concreto cambiaría un contrato que U15 posee. La marca del evento es la
del **último final**, no la del vencimiento del temporizador: la espera del
silencio es del detector y cargarla a NFR1 mediría otra cosa.

**La interrupción mira la mejor palabra y el "no le entendí" mira la peor.** No es
una inconsistencia: buscan cosas opuestas. Una busca una señal clara de que
alguien habló; la otra, si lo que se oyó se puede dar por bueno.

**La retoma se busca solo por el resumen de la clave del navegador.** La póliza de
ejemplo es pública y la comparten todos los visitantes: buscar por ella
significaría que decir un número público en voz alta abre el caso de otra
persona. La firma de `find_resumable` no admite una póliza, y hay una prueba
sobre esa firma. Es el criterio `[bloquea]` AC1.27.3.

**El conjunto de motivos de final creció a seis al cablear el cierre.** Tenía
cinco y ninguno decía "el reporte quedó completo y la agente se despidió".
`hangup` es "la persona colgó" y `silence` dejaría el caso esperando justo cuando
ya no espera nada. Un conjunto cerrado que no puede expresar un desenlace real no
está protegiendo: está escondiendo.

**El ciclo de la llamada bajó de la raíz a la unidad.** Nació en
`untangle.server` porque recibía la plataforma de voz entera. Al reducir esa
dependencia a un puerto de cuatro líneas dejó de haber razón para tenerlo arriba,
y apareció una para bajarlo: el corredor de evaluaciones está debajo y no podía
alcanzarlo. Un ritmo de llamada que las evaluaciones no pueden ejecutar es un
ritmo que solo se mide en producción.

**Tres desviaciones de C-08, escritas en la cabecera de las rutas.** La ruta sigue
la forma de las nueve ya construidas; el cuerpo de abrir **no admite `case_id`**,
porque aceptarlo dejaría que quien llama nombre un caso ajeno; y los carriles
diarios salen nulos, porque hoy no los aplica nadie y un número que nada hace
cumplir es una promesa.

## Lo que esta unidad encontró

**La regla que solo vive en el tipo.** BR3.8 —nada se sintetiza sin redactar—
descansaba en que el puerto de síntesis recibe `Redacted` y no `str`. Una línea,
`return text  # type: ignore[return-value]`, la desactivó entera: el comprobador
de tipos siguió en verde sobre 594 archivos, 123 pruebas siguieron pasando, y la
agente habría dicho la placa de alguien en voz alta. Un tipo es una compuerta
**con interruptor**, y el interruptor cabe en un comentario. Se cerró con dos
pruebas de conducta que miran el texto que de verdad saldría por el altavoz, y
entró al catálogo de revisión como su **forma 9**.

**La pieza construida sin llamador, dos veces más.** `spell_for_readback` llevaba
desde U11 versionada y probada sin que nadie la usara en producción; U16 fue su
primer consumidor. Y en el código de esta misma unidad, `readback`, `closing` y
`case_number` se llamaban solo entre ellos: un lazo cerrado sin puerta de
entrada. Cablearlos produjo dos correcciones de diseño que no se ven en papel.

**Tres defectos que solo aparecieron al cablear.** Una apertura interrumpida que
se repetía sin final —con el proceso vivo y sin un error en ningún registro—, la
frase con la que alguien interrumpe que no llegaba a la consola, y los cuadros de
control saliendo en binario, que es lo único que los separa del audio en el cable.

**Un arnés de revisión que daba falsos positivos.** El guion de romper y correr de
la última tanda invocaba a `vitest` con un reportero inexistente: salía en rojo
siempre y las siete roturas se anotaron como comprobadas sin que ninguna lo
estuviera. Una de ellas —la cancelación de eco del micrófono— no tenía ninguna
prueba. Es la aserción que no distingue, aplicada al instrumento en vez de al
código.

## Las fronteras que no construyó

- **Los límites públicos** —tres minutos, una llamada al día, aviso a los treinta
  segundos, ventana de retoma— y la elección entre voz principal y de respaldo
  son de U17. Esta unidad deja la forma de C-08 y **lee** lo que le den.
- **El español y el cambio de idioma** son de U18. Todo se construyó en inglés y
  el idioma queda como dato, no como rama.
- **La conversación** es del grafo y de sus nodos: esta unidad tiene oídos, boca y
  reloj, no opinión.
- **Los adaptadores de voz** son de U15 y se consumen tal cual.
- **DS-5 no existe todavía.** Las veinte grabaciones son de personas reales, viven
  fuera del repositorio y llegan en las semanas 6 y 9. Lo construido es el
  conductor que las meterá por el transporte, no las grabaciones.
- **Que nadie confirme los campos del caso** (PENDIENTES 1.12) no lo arregla esta
  unidad, y la consecuencia en voz es la misma que en el chat: la agente vuelve a
  preguntar lo ya contestado. Lo que U16 **sí** hizo fue no construir un segundo
  camino de confirmación propio: el día que se arregle, la voz lo hereda sin
  tocarse.

## Sources

- `code-generation-plan.md` y las seis `hallazgos-tanda-N.md`
- `../functional-design/` — el diseño funcional, las 38 reglas y las entidades
- `../nfr-requirements/` — los cinco documentos de calidad de la unidad
- `../../../inception/contract-design/contract-summary.md` — C-08, C-14, C-16, C-25, C-29

## Assumptions & Open Questions

None.
