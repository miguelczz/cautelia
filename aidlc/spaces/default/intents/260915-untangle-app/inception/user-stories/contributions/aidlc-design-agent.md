**Collaborator:** aidlc-design-agent

## Contribution

Revisión desde diseño (experiencia de uso y fidelidad de los perfiles) de
`stories.md`, `personas.md` y `user-stories-questions.md`, contrastados con
`requirements.md`, la guía de voz (`docs/pre_prb/voz-y-tono.md`) y el PRD v1.1
(secciones 3, 5, 6, 7, 9.3 a 9.5, 10, 11 y 12). Los hallazgos van ordenados por
impacto. Cada uno nombra las historias y los criterios afectados y trae el texto
propuesto en Dado / Cuando / Entonces, listo para integrar. Los identificadores
de historias y criterios nuevos son sugeridos: los asigna el líder.

Cinco hallazgos cambian una frase aprobada, un límite ya decidido o el alcance;
se proponen como decisiones nuevas para la tabla "Decisiones que fijan estas
historias", con el visto bueno de Miguel en la aprobación de la etapa, igual que
D8 a D11: cierre de la llamada pública por tiempo (hallazgo 2), promesa de
transferencia inmediata (4), emergencias en una superficie pública (5), destino
del enlace a la traza (8) y línea base de accesibilidad y teléfono (10).

### 1. La póliza de ejemplo compartida abre casos de otros visitantes

**Impacto: alto** (privacidad de personas reales; RT-4 corre siempre contra el
despliegue vivo).

En la demo pública todos los visitantes de una aseguradora usan la misma póliza
de ejemplo (`personas.md`; PRD F4.3; AC1.2.1). Seis criterios usan "me
identifico con la misma póliza" como llave para retomar un caso o recibir una
decisión: AC1.11.2, AC1.12.2, AC1.13.1, AC1.13.2, AC1.18.2 y AC1.21.3. En la
demo esa identidad la conoce cualquiera: el segundo visitante que se identifica
con la póliza de ejemplo recibiría la oferta de seguir el caso del primero ("Veo
que tenemos un caso abierto de hoy...") o el resumen de su decisión, y un número
de caso adivinado más la póliza de ejemplo abriría cualquier caso de visitante,
así que AC1.13.2 no protege nada. Choca con el PRD 9.3 (el visitante "no ve
casos de otros"), con la regla del proyecto que trata lo que entra por una
superficie pública como dato personal potencialmente real y con la práctica que
corre RT-4 contra el despliegue vivo en cada hito.

Propuesta: en las superficies públicas la llave para ver, retomar o recibir
noticias de un caso es la sesión del navegador que lo creó o el enlace firmado,
nunca la póliza de ejemplo sola. Añadir a "Convenciones" de `stories.md`: "En
las superficies públicas, identificarse dentro de la conversación no basta para
ver un caso: la llave es la sesión del navegador que lo creó o el enlace
firmado." Criterios:

- **AC1.12.5 — Póliza de ejemplo compartida** (nuevo)
  - Dado dos visitantes que usan la póliza de ejemplo de Stonecroft Mutual desde navegadores distintos, y el primero dejó un caso guardado
  - Cuando el segundo se identifica con esa póliza
  - Entonces la agente no le ofrece, no menciona ni resume el caso del primero
  - Y abre un caso nuevo
- **AC1.18.5 — Póliza de ejemplo compartida, por voz** (nuevo): el mismo criterio con dos llamadas desde navegadores distintos.
- **AC1.11.2** (corregir el Dado): "Dado un caso reportado por voz y ya decidido, creado desde este mismo navegador".
- **AC1.13.2** (reemplazar)
  - Dado un número de caso creado desde otro navegador
  - Cuando lo escribo en el chat, aunque me identifique con la póliza de ejemplo
  - Entonces el chat no muestra ningún dato del caso
  - Y responde con el mismo mensaje que para un número que no existe
- **AC1.2.6 — Póliza que no es de la demo** (nuevo)
  - Dado que escribo un número de póliza que no existe en la demostración, quizá el de mi póliza real
  - Cuando la agente responde
  - Entonces dice que la demostración solo usa pólizas de ejemplo y me señala la de la página
  - Y no repite el número que escribí

### 2. La llamada pública termina casi siempre en un callejón sin salida

**Impacto: alto** (M21, recorrido UC-5 y KPI "sesiones que cierran el ciclo" del
PRD 10.2).

Cuatro reglas de las historias, juntas, dejan al visitante sin salida:

- AC5.6.1 corta a los 3 minutos y guarda el caso, incompleto si no terminó.
- AC5.6.2 permite 1 llamada por visitante al día y AC5.9.1 borra los casos cada noche: volver a llamar para retomar (US1.18, US1.21 y el texto sustituto de D8) no está al alcance del visitante.
- AC3.5.3 no deja decidir un caso incompleto y AC3.7.1 solo entrega el enlace firmado a un caso derivado.
- El PRD 10.3 acepta hasta 14 turnos y 5 minutos para un reporte simple, y la apertura en español ocupa sola unas 53 palabras, cerca de 22 segundos a 145 palabras por minuto (guía, punto 2).

Lo esperable es que la mayoría de las llamadas públicas no terminen en 3
minutos: el visitante se queda con un caso a medias, sin enlace y sin forma de
terminarlo, y nunca llega a la bandeja. El límite es decisión de Miguel (Q1 de
Requirements Analysis) y no se discute aquí; lo que falta es diseñar para él.

Propuesta (decisión nueva, sugerida D12):

- **AC5.6.1** (reemplazar) — Cierre por tiempo que no deja el caso a medias
  - Dado una llamada en el enlace público
  - Cuando faltan 30 segundos para el límite
  - Entonces la agente lo dice en una frase ("Nos queda medio minuto de la demostración; voy a dejar su caso listo para un ajustador." / "We have about thirty seconds left in this demo; I'll get your case ready for an adjuster.")
  - Y al llegar al límite resume lo registrado, deriva el caso con el motivo "límite de la demostración" y su completitud, y termina la llamada con cortesía
  - Y la consola muestra el número de caso y el enlace firmado
- **AC3.5.3** (acotar): aplica a los casos en "esperando al asegurado"; un caso derivado por el límite de la demostración se puede decidir, y la vista muestra qué campos faltan.
- **AC5.6.6 — Reconexión tras un corte de red** (nuevo)
  - Dado que mi llamada se cortó por la red antes del límite
  - Cuando vuelvo a llamar desde el mismo navegador dentro de los 10 minutos siguientes
  - Entonces la llamada retoma el mismo caso desde el último bloque confirmado y dura solo el tiempo que me quedaba
  - Y no cuenta como mi llamada del día, aunque sí contra el tope diario del sitio
- **AC5.6.7 — Duración real medida** (nuevo)
  - Dado las grabaciones de reporte simple del golden set de audio (DS-5)
  - Cuando corre la evaluación del hito
  - Entonces el reporte publica la duración p50 y p95 de la llamada por idioma, junto al límite configurado del enlace público
- La cuenta regresiva visible y el escenario de prueba de la consola van en el hallazgo 6.

Si Miguel prefiere no derivar por tiempo, la alternativa honesta es que la
consola diga al cortar que el caso quedó incompleto y que en la demo no se puede
retomar ni decidir; entonces US1.18 y US1.21 deben aclarar que la reanudación
por voz se demuestra en local y en el video, no en el enlace público. Los 10
minutos de reconexión y los 30 segundos de aviso son valores de configuración.

### 3. En el chat la agente pide datos antes de preguntar si hay heridos

**Impacto: alto** (RT-8 bloquea; P11 y P12).

La guía (punto 4) fija el orden: seguridad → identidad y póliza → qué pasó →
cuándo y dónde → vehículo y conductor → otras partes → confirmación. La voz lo
cumple: la apertura termina en "¿todos están bien?" y AC1.15.1 sigue "el orden
de la guía". En el chat, en cambio, AC1.2.1 abre el caso al identificarse y
AC1.3.1 parte de "un caso abierto e identificado" para preguntar después por la
seguridad: el chat pide nombre y póliza antes de saber si alguien está herido.
Es lo que RT-8 prohíbe (emergencias antes de cualquier dato), lo que P11 (c)
prohíbe ("saltar la pregunta de seguridad") y una lógica distinta entre canales,
que P12 (c) prohíbe.

- **AC1.3.1** (reemplazar)
  - Dado que en el chat elijo reportar un siniestro
  - Cuando la agente empieza el reporte
  - Entonces su primera pregunta es si todos están bien y en un lugar seguro, antes de pedir nombre o póliza
  - Y después sigue el orden de la guía: identidad y póliza, qué pasó, cuándo y dónde, vehículo y conductor, otras partes y confirmación final
- **AC1.2.1** (ajustar): "Y asocia el caso a esa póliza" en lugar de "Y abre el caso asociado a esa póliza". El caso se abre al elegir reportar, para que la respuesta a la pregunta de seguridad quede registrada.
- **AC1.2.7 — Pregunta de cobertura sin reporte** (nuevo)
  - Dado que en el chat elijo preguntar por mi cobertura, sin reportar un siniestro
  - Cuando la agente empieza
  - Entonces pide identidad y póliza sin la pregunta de seguridad

### 4. "Le paso ya mismo" promete una transferencia que la demo no hace

**Impacto: alto** (P7 y la regla NEVER del proyecto: no prometer en la voz de la
agente una capacidad que no está construida).

AC1.7.1 fija "si necesita a una persona, le paso ya mismo"; AC1.19.1 cita la
apertura con "me dice y le paso"; la apertura en inglés de la guía (punto 6), que
alimenta el catálogo, dice "just say so and I'll connect you". Pero en la demo la
transferencia es simulada (PRD F3.9) y AC1.6.2 exige que la agente no diga que
está transfiriendo en ese momento. D8 y D9 aplicaron P7 a la devolución de
llamada y al plazo; falta aplicarlo a "ya mismo" y a "connect you". Las frases
propuestas conservan la calidez, dicen lo que pasa y resuelven de paso el género
de D10: en "se lo paso", "lo" es el caso, no quien llama.

Propuesta (decisión nueva, sugerida D13):

- **AC1.19.1**, apertura en español: "Hola, buenas. Le habla Valentina, la asistente de inteligencia artificial de Stonecroft Mutual. Esta llamada se graba para registrar bien su caso. Puedo ayudarle a reportar un siniestro o a resolver dudas sobre su póliza, y si en algún momento prefiere que una persona revise su caso, me dice y se lo paso. Para empezar, ¿todos están bien?"
- **AC1.14.2**, apertura en inglés completa (hoy cita solo las dos primeras frases): "Hi, this is Valentina, Sunmeadow Auto's AI assistant. This call is recorded so I can file your case correctly. I can help you report a claim or answer questions about your policy, and if at any point you'd rather have a person review your case, just say so. First, is everyone okay?"
- **AC1.7.1**: "No, soy una asistente de inteligencia artificial, pero le voy a ayudar con todo esto, y si prefiere que una persona revise su caso, se lo paso a un ajustador."
- **AC1.7.2** (fijar el texto: hoy el inglés es una paráfrasis y el español es literal, y P12 pide la misma fuerza de prueba en los dos idiomas): "No, I'm an AI assistant. I'll help you with all of this, and if you'd rather have a person review your case, I'll pass it to an adjuster."
- **AC1.14.3** (ampliar): la voz ofrece reportar un siniestro, resolver dudas sobre la póliza y que una persona revise el caso. Hoy omite las dudas de cobertura, que la voz atiende (US2.4) y el chat ofrece (AC1.1.3).
- **AC1.1.6 y AC1.14.6 — Aviso fijo de demostración** (nuevos, uno por superficie)
  - Dado el chat público o la consola de llamada
  - Cuando se muestra la página
  - Entonces un aviso visible en todo momento dice que es una demostración y que no hay personas atendiendo en vivo: un caso derivado se decide en la bandeja
  - Y la agente no necesita repetirlo en cada turno

### 5. La indicación de emergencia no sirve a una persona real en la demo pública

**Impacto: alto** (seguridad de personas).

AC1.5.1 indica "llamar al 911, el número de emergencias del Estado de Corvane".
Corvane no existe, y el chat y la voz públicos reciben personas reales (práctica
de despliegue "Superficie pública y datos reales"; regla del proyecto que trata
lo que entra por una superficie pública como potencialmente real). Quien tenga
una emergencia real desde Colombia (123) o Europa (112) no debe recibir una
instrucción de ficción ni creer que la demo puede enviar ayuda.

- **AC1.5.5 — Emergencia en la demo pública** (nuevo; decisión sugerida D14)
  - Dado que estoy en el chat público o en el enlace público de voz
  - Cuando la agente da la indicación de emergencia
  - Entonces dice que llame ya al número de emergencias de donde se encuentre y que la demostración no puede enviar ayuda ("Si alguien está herido de gravedad, llame ya al número de emergencias de donde se encuentre. Esta es una demostración y no puede enviar ayuda." / "If someone is seriously hurt, call your local emergency number now. This is a demo and can't send help.")
  - Y el 911 del Estado de Corvane queda, por configuración, para el despliegue local y los casos del golden set
- **AC1.5.3** no cambia: la compuerta comprueba que la indicación llega antes de cualquier dato, con cualquiera de los dos textos.

### 6. Consola de llamada: estados sin criterio y un perfil que no es el suyo

**Impacto: alto** (M21; es la pantalla con la que se graba el video, PRD MOD-03).

US1.14 está escrita "Como Ana", pero el selector de aseguradora, la póliza de
ejemplo en pantalla y los límites son del visitante, que según `personas.md` es
Jordan cuando prueba la demo. El PRD (MOD-03) fija cinco elementos de la
consola: botón de llamar, selector de aseguradora e idioma inicial,
transcripción en vivo, latencia del último turno y número de caso al cerrar. No
hay criterio para la latencia del último turno, el número de caso en pantalla,
colgar, los estados de conexión ni la disponibilidad antes de pedir el
micrófono; hoy los rechazos por límite (AC5.6.2, AC5.6.3 y AC5.8.3) llegan
después de pulsar llamar, cuando el visitante ya concedió el micrófono.

Propuesta: US1.14 conserva lo que es de Ana (llamar y oír la apertura, AC1.14.2
a AC1.14.5) y los mecanismos de la consola pasan a una historia nueva.

**US4.12 — Probar la voz en vivo sabiendo qué puedo hacer, cuánto tiempo tengo y dónde quedó mi caso** (ID sugerido)

**Como** Jordan, **quiero** una consola de llamada que antes de llamar me diga
qué puedo probar y cuánto dura, que me muestre en todo momento qué está pasando
y que al terminar me diga dónde quedó mi caso, **para** probar la voz en vivo
sin preparar un guion y sin quedarme sin salida.

- **Prioridad:** Must (M21, M12)
- **Realiza:** FR3.1, FR3.9, FR8.7, FR10.2. Origen: PRD MOD-03 (pantalla de la consola), P4 (c) y NFR19.
- **Módulos:** MOD-03, MOD-10, MOD-08
- **Construye sobre:** US1.14 (la conexión y la apertura)

- **AC4.12.1 — Disponibilidad antes del micrófono**
  - Dado que ya usé mi llamada del día, que el sitio llegó a sus 15 llamadas o que el gasto llegó al techo
  - Cuando abro la consola
  - Entonces el botón de llamar aparece deshabilitado con el motivo escrito y, si se conoce, cuándo vuelve a estar disponible
  - Y ofrece el chat y el video
  - Y el navegador no me pide permiso de micrófono
- **AC4.12.2 — Qué puedo probar**
  - Dado que la voz está disponible
  - Cuando abro la consola
  - Entonces antes de llamar veo la póliza de ejemplo de la aseguradora elegida, un escenario de prueba con datos ficticios para leer (lugar, hora, placa), la duración máxima de la llamada y qué se guarda de ella (el audio no; la transcripción redactada, hasta el reinicio nocturno)
  - Y al cambiar de aseguradora el idioma inicial pasa al idioma por defecto de esa aseguradora, salvo que yo lo haya elegido
- **AC4.12.3 — Estado de la llamada, siempre a la vista**
  - Dado una llamada en curso
  - Cuando cambia su estado
  - Entonces la consola lo dice en texto: conectando, en llamada, reconectando o terminada, con la causa del final (colgué, límite de tiempo, corte de red, servicio no disponible)
  - Y muestra el tiempo restante y un botón de colgar visible todo el tiempo
- **AC4.12.4 — Qué se dijo y quién lo dijo**
  - Dado una llamada en curso
  - Cuando hablamos
  - Entonces la transcripción en vivo muestra los turnos de los dos lados, cada uno con el nombre de quien habla escrito, no solo con un color
  - Y el estado de la agente aparece en texto: escuchando, hablando o revisando la póliza
- **AC4.12.5 — Latencia del último turno, verificable**
  - Dado que la agente termina de responder un turno
  - Cuando miro la consola
  - Entonces veo la latencia de ese turno con la etiqueta de lo que mide ("fin del habla → primer audio" / "end of speech → first audio")
  - Y el valor coincide con las marcas de ese turno en la traza
- **AC4.12.6 — Dónde quedó mi caso**
  - Dado que la llamada terminó, por cualquier causa
  - Cuando se muestra el cierre
  - Entonces veo el número de caso escrito, la completitud y el estado del caso
  - Y si quedó derivado, el enlace firmado con su hora de vencimiento; si no, por qué no y qué puedo hacer

Dos puntos para decidir al integrar:

- El mensaje del PRD 12.3 para la transcripción caída ("puede continuar por el chat con su número de caso") depende de S2, la primera en la regla de corte. Si S2 no se construye, la consola ofrece el chat sin prometer que retoma el caso, igual que AC1.13.5.
- Si la transcripción en vivo que ve el propio visitante va redactada, la placa aparece como una etiqueta mientras la agente la lee en voz alta y la confirmación en pantalla pierde sentido. La regla del proyecto nombra la transcripción parcial como punto de salida que se redacta, así que la decisión es de Miguel; el criterio debe decir cuál de las dos cosas pasa.

### 7. Entrada a la bandeja por enlace firmado: orientación, vencimiento y regreso

**Impacto: medio-alto** (UC-5: es el momento en que Jordan comprueba con sus
manos que una persona decide).

**a) Contradicción con Knotwell.** AC3.7.2 da "aprobar y rechazar" a todo caso;
AC3.6.3 dice que en Knotwell esas acciones no existen.

- **AC3.7.2** (reemplazar el Entonces): "Entonces entro directo a la vista de mi caso, con las acciones del rol de su aseguradora: aprobar o rechazar en Stonecroft Mutual y Sunmeadow Auto, marcar como enviado a la aseguradora en Knotwell".

**b) Quién decidió.** AC3.4.2 registra "quién decidió"; con el enlace, decide el
visitante. Si el historial o la explicación del caso (FR7.4) atribuyen esa
decisión a Diana, Marcus Webb o Priya Raman, la explicabilidad que Jordan revisa
es falsa.

- **AC3.7.6 — La decisión se atribuye a quien la tomó** (nuevo)
  - Dado que decido mi caso con el enlace firmado
  - Cuando se consultan el historial y la explicación del caso
  - Entonces la decisión figura como tomada por un visitante con enlace de demostración, con su hora
  - Y no aparece a nombre de ninguna persona de la bandeja

**c) El recorrido que la historia no cubre.** Para que US3.7 no pase de seis
criterios, conviene una historia nueva:

**US3.8 — Entrar a mi caso con el enlace sin perderme ni perder lo que escribí** (ID sugerido)

**Como** Jordan, **quiero** saber al entrar qué estoy viendo, hasta cuándo vale
el enlace y qué hacer después de decidir, **para** cerrar el ciclo aunque el
enlace venza o lo abra en el teléfono.

- **Prioridad:** Must (M11, M21)
- **Realiza:** FR8.7, FR8.5
- **Módulos:** MOD-08, MOD-09
- **Construye sobre:** US3.7 (el enlace y la decisión)

- **AC3.8.1 — Orientación al entrar**
  - Dado que abro el enlace firmado
  - Cuando carga la vista del caso
  - Entonces un aviso dice que reviso mi propio caso con permisos de ajustador de demostración y a qué hora vence el enlace, en mi hora local
  - Y la vista se abre sin cerrar la conversación donde recibí el enlace
- **AC3.8.2 — Después de decidir**
  - Dado que decido mi caso
  - Cuando confirmo
  - Entonces la vista muestra que el caso se reanudó, el mensaje que recibe el asegurado y un enlace para volver a la conversación
  - Y si el caso se creó por voz, muestra el resumen que la agente dará al volver a llamar
- **AC3.8.3 — El enlace vence a mitad de la decisión**
  - Dado que el enlace vence mientras escribo el comentario
  - Cuando confirmo
  - Entonces la decisión no se aplica y la vista dice que el enlace venció
  - Y el comentario que escribí sigue en pantalla para copiarlo
- **AC3.8.4 — Enlace vencido: qué hago ahora**
  - Dado un enlace vencido
  - Cuando lo abro
  - Entonces la página dice que venció, que el caso sigue guardado hasta el reinicio nocturno y cómo pedir un enlace nuevo en la misma conversación
  - Y el enlace nuevo vale otra hora y solo se entrega al navegador que creó el caso
- **AC3.8.5 — Mensajes que no revelan nada** (ajusta AC3.7.3 y AC5.9.4)
  - Dado un enlace manipulado, uno de un caso que no existe y uno emitido antes del reinicio nocturno
  - Cuando los abro
  - Entonces los dos primeros muestran el mismo mensaje de enlace no válido, sin confirmar si el caso existe
  - Y el tercero dice que los datos de la demostración se borran cada noche
- **AC3.8.6 — El token no se queda en la barra ni viaja a terceros**
  - Dado que abro el enlace firmado
  - Cuando carga la vista
  - Entonces la dirección visible ya no contiene el token
  - Y la página no envía el token a ningún tercero en la cabecera `Referer`

Si Miguel prefiere no renovar enlaces, AC3.8.4 dice que el enlace no se puede
renovar e invita a crear un caso nuevo: lo que no puede pasar es dejar al
visitante sin siguiente paso.

**d) El aviso al asegurado para las otras dos decisiones.** AC1.11.1 cubre solo
la aprobación.

- **AC1.11.5 — Rechazo** (nuevo)
  - Dado un caso reportado por chat que el ajustador rechaza con un comentario
  - Cuando aparece el aviso en la conversación
  - Entonces dice el resultado, el comentario y qué puede hacer el asegurado
  - Y AC3.4.3 dice en qué estado queda el caso: hoy "vuelve con su motivo" no dice a dónde vuelve
- **AC1.11.6 — Enviado a la aseguradora, en Knotwell** (nuevo)
  - Dado un caso de Knotwell marcado como enviado a la aseguradora
  - Cuando aparece el aviso en la conversación
  - Entonces dice que el caso se envió a la aseguradora que emitió la póliza, con el comentario
  - Y no promete que esa aseguradora vaya a contactar al asegurado, porque el traspaso real no existe (W1)

### 8. El enlace a la traza del chat público no tiene destino

**Impacto: medio-alto** (P7: un enlace muerto en la superficie que más se prueba;
privacidad).

AC2.1.1 (FR4.3, PRD F4.4 y UC-2) ofrece "un enlace a la traza de la respuesta"
en el chat. El PRD 9.5 sitúa el panel de telemetría en local y en el video. En el
despliegue público ese enlace llevaría a un servicio que no existe, a un inicio
de sesión o, peor, a un almacén de trazas abierto donde un visitante vería
conversaciones de otros cambiando un identificador. Además las trazas se
registran con segundos de retraso: abrirlo enseguida daría "no encontrado".

Propuesta (decisión nueva, sugerida D15; el cómo es de arquitectura, el
comportamiento observable es de la historia):

- **AC2.1.7 — Traza desde el chat público** (nuevo)
  - Dado una respuesta de cobertura en el chat público
  - Cuando abro su enlace a la traza
  - Entonces veo sin iniciar sesión la traza redactada de esa respuesta: nodos recorridos, cláusulas recuperadas y verificadas, latencia y costo
  - Y el enlace solo abre trazas de la conversación de mi navegador
- **AC2.1.8 — Traza todavía sin registrar** (nuevo)
  - Dado que abro el enlace antes de que la traza se registre
  - Cuando carga
  - Entonces veo que se está registrando y la página se actualiza sola
  - Y nunca un "no encontrado"

Si la decisión es no publicar trazas, el chat muestra el identificador de la
traza como texto, con la indicación de que se consulta corriendo el repositorio
en local, y no lo presenta como enlace.

### 9. Estados vacíos, de carga y de error sin criterio

**Impacto: medio.**

**Chat (US1.1, US1.11 y US5.7)**

- **AC1.1.7 — La demo se está despertando** (nuevo). Origen: PRD 12.2, fila "Hosting dormido o caído", que pide un mensaje de "despertando"; Taylor tiene 90 segundos y "si la primera pantalla falla, nadie llega a la profundidad" (`personas.md`).
  - Dado que el servicio está dormido
  - Cuando abro la página del chat
  - Entonces en menos de 3 segundos veo que la demo se está despertando, con el tiempo aproximado
  - Y si a los 60 segundos no responde, veo un mensaje honesto con el enlace al video
  - Los mismos dos estados valen para la consola y para la vista de caso por enlace. Exige que la página cargue aunque el servicio duerma: es una restricción para la decisión de hospedaje. Los 3 y 60 segundos son configuración.
- **AC5.7.5 — Cuota del modelo agotada o modelo sin respuesta** (nuevo). Origen: PRD 12.3 (primera fila) y la fila "Límite de tasa o cuota del LLM" del mapa de fallos. Es la falla más probable del chat en tier gratuito y ningún criterio la cubre: AC5.7.1 y AC5.7.2 son los límites propios, no la cuota del proveedor.
  - Dado que el proveedor del modelo del chat devuelve cuota agotada o no responde
  - Cuando envío un mensaje
  - Entonces tras un reintento veo un aviso honesto, sacado del catálogo y pasado por la guardia de salida, de que el chat no puede responder ahora
  - Y mi caso y el texto que escribí se conservan
- **AC5.7.6 — Mensaje demasiado largo** (nuevo; RT-13 por tamaño, porque AC5.7.3 solo cubre la cantidad)
  - Dado un mensaje más largo que el máximo configurado
  - Cuando intento enviarlo
  - Entonces la interfaz lo impide antes de enviarlo, con el conteo y el máximo a la vista
  - Y nada llega al proveedor del modelo
- **AC1.11.7 — Después del reinicio nocturno** (nuevo; complementa AC1.11.3)
  - Dado que conversé ayer y los datos de la demostración ya se reiniciaron
  - Cuando recargo la página del chat
  - Entonces empieza una conversación nueva con la divulgación completa
  - Y un aviso dice que las conversaciones de la demostración se borran cada noche
- **AC1.1.4** (ampliar): el selector muestra el idioma en que responde la agente, y elegir un idioma cambia las etiquetas de la página y el idioma de la agente desde su siguiente mensaje.
- La página de estado honesta del PRD 12.3 para la base de datos caída no tiene criterio en ninguna superficie; basta uno compartido en US5.10.

**Vista de comparación (US2.6)**

- **AC2.6.6 — Divulgación antes de la primera pregunta** (nuevo). P6 (a) pide la divulgación en el primer mensaje de chat, y esta vista invoca a la agente sin pasar por AC1.1.1.
  - Dado que abro la vista de comparación
  - Cuando carga
  - Entonces antes de la primera pregunta dice que responde una asistente de inteligencia artificial, que es una demostración con pólizas de ejemplo y qué póliza de ejemplo usa cada columna
  - Y la columna de Knotwell nombra la aseguradora que emitió su póliza de ejemplo
- **AC2.6.7 — Carga por columna y en el teléfono** (nuevo)
  - Dado que hago una pregunta
  - Cuando llegan las respuestas
  - Entonces cada columna muestra su propio estado de carga y aparece en cuanto está lista, sin esperar a las otras
  - Y a 360 px de ancho las tres se apilan con el nombre de la aseguradora visible en cada una, sin desplazamiento horizontal
- **AC2.6.8 — Antes de preguntar y fuera de propósito** (nuevo)
  - Dado que abro la vista sin haber preguntado nada
  - Cuando carga
  - Entonces sugiere dos o tres preguntas de ejemplo que muestran la diferencia entre pólizas, en el idioma de la página
  - Y si escribo un reporte de siniestro, explica que esta vista compara respuestas de cobertura y enlaza el chat de cada aseguradora
- **AC2.6.1** (precisar): las tres respuestas llegan en el idioma de la pregunta. **AC2.6.5** (precisar): si una pregunta cuenta como una o como tres contra los límites, porque consume tres llamadas al modelo.

**Bandeja (US3.1 a US3.5)**

- **AC3.1.6 — Lo urgente primero** (nuevo). El "para" de US3.1 es "atender primero lo urgente" y ningún criterio lo entrega.
  - Dado la cola sin filtros
  - Cuando abro la bandeja
  - Entonces los casos se ordenan por prioridad y, dentro de cada prioridad, por tiempo de espera, del más largo al más corto
- **AC3.1.7 — Filtros sin resultados** (nuevo)
  - Dado unos filtros que no coinciden con ningún caso
  - Cuando los aplico
  - Entonces veo que ningún caso coincide y una acción para quitar los filtros
- **AC3.1.5** (ampliar): la elección de idioma se conserva al abrir un caso, al volver a la lista y al recargar. Diana atiende en español y la interfaz abre en inglés; sin esto cambia el selector en cada pantalla.
- **AC3.2.1** (precisar): lo primero visible al abrir un caso es el motivo de la derivación, la categoría y la completitud, y las acciones de decidir quedan al alcance sin recorrer toda la evidencia, también en el teléfono. En la transcripción, cada valor redactado aparece como una etiqueta de su tipo ([placa], [cédula]) que indica el campo del caso donde quedó el valor.
- **AC3.4.1** (ampliar): "Y el campo del comentario dice que es obligatorio, sin perder la decisión elegida".
- **AC3.5.3** (ampliar, además del ajuste del hallazgo 2): "Y la vista dice por qué no se puede decidir y qué campos faltan".

### 10. Accesibilidad y teléfono: ningún criterio en las superficies públicas

**Impacto: medio-alto** (hoy cero criterios, y añadirlos después de construir la
interfaz cuesta mucho más que desde el primer commit).

Ni el PRD, ni `requirements.md`, ni las prácticas, ni las 59 historias tienen un
criterio de accesibilidad o de uso en pantalla de teléfono. Sin embargo,
`personas.md` dice que Camilo y Ana escriben desde el teléfono; el PRD (W8)
descarta la aplicación nativa porque "el chat web y la voz cubren la demo", así
que la web es el único camino desde un teléfono; Taylor llega desde LinkedIn; y
quien llama desde el teléfono recibe ahí el enlace firmado. Además el producto
es bilingüe: un lector de pantalla que lee un mensaje en español con voz inglesa
lo vuelve ininteligible.

Propuesta (decisión nueva, sugerida D16): una historia con línea base WCAG 2.1
AA proporcionada, cuyos criterios se comprueban con herramientas, como exige la
práctica del equipo ("comprobable por una herramienta o por un grep"), dentro de
`scripts/verify.sh`. Si Miguel la aprueba, `nfr-requirements` registra sus
objetivos medibles con su comando; si la rechaza o la reduce, queda en "Lo que
no se convierte en historia" con su razón, como pide la corrección aprendida en
Requirements Analysis.

**US1.24 — Usar el chat y la llamada desde el teléfono, con teclado o con lector de pantalla** (ID sugerido)

**Como** Camilo o Ana, **quiero** reportar el accidente o preguntar por mi póliza
desde mi teléfono, solo con el teclado o con un lector de pantalla, **para** no
depender de un computador ni de ver bien la pantalla en uno de mis peores días.

- **Prioridad:** Must (M10, M21), sujeta a D16
- **Realiza:** FR4.1, FR4.4, FR3.1. Origen: `personas.md`, PRD W8, P12 y la pauta WCAG 2.1 AA.
- **Módulos:** MOD-04, MOD-03, MOD-08
- **Construye sobre:** ninguna

- **AC1.24.1 — Revisión automática en cada entrega**
  - Dado el chat, la consola, la vista de comparación y la vista de caso por enlace, en español y en inglés
  - Cuando corre el guion de verificación con un analizador automático de accesibilidad
  - Entonces no hay hallazgos de severidad seria ni crítica
  - Y un hallazgo bloquea la entrega
- **AC1.24.2 — En el teléfono**
  - Dado un ancho de pantalla de 360 × 640 px
  - Cuando uso esas cuatro pantallas
  - Entonces no hay desplazamiento horizontal, y el campo de escribir y el botón de enviar siguen visibles con el teclado del teléfono abierto
  - Y llamar, colgar, enviar, expandir una cláusula, aprobar y rechazar miden al menos 44 × 44 px
- **AC1.24.3 — Solo con teclado**
  - Dado que no uso ratón ni pantalla táctil
  - Cuando completo un reporte en el chat, expando una cláusula, inicio y cuelgo una llamada y decido un caso por enlace
  - Entonces todo se hace con el teclado, con el foco visible, en orden lógico y sin quedar atrapado
  - Y ese recorrido es una prueba automatizada
- **AC1.24.4 — Lo que llega se anuncia una vez**
  - Dado un lector de pantalla
  - Cuando llega un mensaje de la agente, que se transmite palabra por palabra
  - Entonces se anuncia una sola vez, completo
  - Y los estados ("escribiendo", "revisando la póliza"), los límites, los errores y la cuenta regresiva de la llamada se anuncian como mensajes de estado; la cuenta regresiva, solo a los 60 y a los 30 segundos
- **AC1.24.5 — Cada texto en su idioma**
  - Dado un mensaje o un bloque en español dentro de una página en inglés, o al revés
  - Cuando un lector de pantalla lo lee
  - Entonces lo pronuncia en su idioma, porque cada mensaje y cada bloque declara el suyo, también en la bandeja en inglés con un caso en español
- **AC1.24.6 — Ni color ni movimiento solos**
  - Dado la prioridad, el estado del caso, el resultado de los controles y quién habla en la transcripción
  - Cuando los leo
  - Entonces se entienden por texto o por un icono con etiqueta, con contraste AA, y a 200 % de zoom no se pierde contenido
  - Y las animaciones de la voz se detienen si el sistema pide movimiento reducido

Dos complementos:

- **AC4.2.5 — Subtítulos del video** (nuevo)
  - Dado el video publicado
  - Cuando lo veo sin sonido
  - Entonces tiene subtítulos en inglés en todo el video, incluido el segmento en español
  - Y el README enlaza su transcripción
  - Razón: pauta WCAG de subtítulos, y Taylor, en Estados Unidos o Europa según el PRD 3.1, no tiene por qué entender el segmento en español ni poder poner sonido.
- La historia debe nombrar los navegadores donde se prueba (por ejemplo, las dos últimas versiones de Chrome, Safari y Firefox de escritorio, Safari en iOS y Chrome en Android); la lista la fija la decisión de arquitectura de la interfaz, pero sin ella "funciona en el teléfono" no es comprobable. Safari en iOS impone restricciones propias al micrófono y al audio: conviene que el spike de voz de la semana 1 lo incluya.

### 11. Frases de la agente y conducta de la voz: fidelidad a la guía y paridad

**Impacto: medio.**

**a) Una medida de longitud que no depende de la pantalla.** AC1.3.2 exige
"tres líneas o menos": tres líneas en escritorio son unas seis a 360 px, y no se
comprueba por código. Además choca con el primer mensaje (AC1.1.1 y AC1.1.3), la
confirmación por bloque (AC1.3.4) y el resumen de cierre (AC1.10.1).

- **AC1.3.2** (reemplazar el Entonces): "contiene una sola pregunta, tiene 25 palabras o menos (PRD 11.2, 'Relevancia: respuesta') y no lleva marcadores orales de la voz ('pues', 'listo'), salvo el primer mensaje, las confirmaciones por bloque, el resumen de cierre y el texto expandido de una cláusula".
- **AC1.15.6 y AC1.20.6 — Turnos cortos en la voz** (nuevos; hoy la voz no tiene criterio de longitud)
  - Dado cualquier turno de la agente en la llamada, salvo la apertura, las lecturas de confirmación y el cierre
  - Cuando se emite
  - Entonces tiene 25 palabras o menos y una sola pregunta (guía, punto 4)

**b) El inglés sin texto fijo donde el español lo tiene.** P12 pide la misma
fuerza de prueba en los dos idiomas; hoy varios criterios en inglés son
paráfrasis. Textos propuestos:

- **AC1.15.3**: "Sorry, I didn't catch that. Could you say it again?" (español en AC1.20.3: "Perdón, no le escuché bien, ¿me repite?").
- **AC1.16.2**, al ceder el turno: "Yes, go ahead." (español en AC1.21.1: "Sí, dígame.").
- **AC1.18.2**: "I see we have an open case from today. Shall we continue with it?" (español en AC1.21.3).
- **AC1.9.1**, en inglés: "Take your time, I'm here." (español: "Tómese su tiempo, aquí estoy").
- **AC1.7.2**: en el hallazgo 4.

**c) Una regla de la guía sin criterio: el nombre de pila en inglés** (guía,
punto 3, y punto 10 para el chat).

- **AC1.15.7 y su gemelo en US1.3 para el chat en inglés** (nuevos)
  - Dado una conversación en inglés en la que di mi nombre
  - Cuando la agente se dirige a mí
  - Entonces no usa mi nombre de pila hasta preguntar "May I call you [name]?" y recibir un sí

**d) Despedida y número de caso.** AC1.10.1 no cita la despedida de la guía
(punto 9): "Cualquier cosa me llama. Que esté muy bien." / "Call me anytime.
Take care." En el chat "me llama" es el canal equivocado, y en el enlace público
"Call me anytime" contradice la llamada por visitante al día.

- Chat: "Cualquier cosa, me escribe por aquí. Que esté muy bien." / "Message me here anytime. Take care."
- Voz en el enlace público: "Que esté muy bien." / "Take care."
- Número de caso: en voz, el nombre de la aseguradora seguido de los seis dígitos uno a uno ("Stonecroft, uno, dos, tres, cuatro, cinco, seis"), en lugar de deletrear el prefijo; el cero se dice "cero" / "zero", nunca "oh". En el chat y en la consola aparece escrito. Por lo mismo, en el chat AC1.2.1 muestra el número de póliza escrito y agrupado para leerlo, no "dígito a dígito".

**e) La divulgación del chat está incompleta.** P6 (a) pide divulgación de
inteligencia artificial y de grabación en el primer mensaje de chat; AC1.1.1
cubre la inteligencia artificial y la demo, no el registro de la conversación.

- **AC1.1.1** (ampliar): "Y dice que la conversación se guarda para registrar el caso y se borra cada noche, y pide no escribir datos personales reales".
- En la voz, "Esta llamada se graba" convive con NFR19 (en la demo pública el audio no se guarda): Jordan lee en el README que no se guarda audio y oye que se graba. Propuesta: mantener la frase hablada, que es el lado conservador de un control de cumplimiento, y que la consola diga qué se guarda (AC4.12.2). Cambiar el texto hablado por despliegue sería una decisión de Miguel.

**f) Silencios, eco y cambio de idioma.**

- **AC1.17.4 y AC1.21.2** (texto del sustituto de D8): la conversación queda guardada siempre, así que ofrecer "guardar el caso" suena a una acción que no hace falta. Propuesta: "Si prefiere, dejamos su caso guardado para seguir después, o se lo paso a un ajustador." / "If you'd like, I'll keep your case saved so you can continue later, or I can pass it to an adjuster." En el enlace público, "seguir después" solo es cierto con la reconexión del hallazgo 2.
- **AC1.17.6 y su gemelo en US1.21 — Tercer silencio** (nuevos)
  - Dado que sigo en silencio cinco segundos después de esa oferta
  - Cuando pasa ese tiempo
  - Entonces la agente se despide, deja el caso en "esperando al asegurado" y termina la llamada
  - Hoy AC1.17.4 acaba en la oferta y la llamada seguiría abierta consumiendo los 3 minutos.
- **AC1.16.5 y su gemelo en US1.21 — Sin audífonos** (nuevos; AC1.16.3 cubre el ruido del carro, no la propia voz de la agente)
  - Dado que llamo sin audífonos desde un portátil o un teléfono
  - Cuando la agente habla
  - Entonces su propia voz saliendo por el altavoz no se toma como interrupción
  - Es la situación más probable de un evaluador que prueba el enlace.
- **AC1.23.4** (reemplazar el Entonces): "la agente pregunta en el idioma que acabo de usar si prefiero seguir en él ('¿Prefiere que sigamos en español?' / 'Would you like to continue in English?')". Preguntar en el idioma actual no ayuda a quien cambió justamente porque se siente más cómodo en el otro.

**g) Mensajes de límite, techo y voz de respaldo sin contenido.** AC5.6.2,
AC5.6.3, AC5.7.1 y AC5.8.3 dicen "mensaje honesto" sin decir qué contiene.

- Criterio de contenido común: el mensaje dice el motivo, cuándo vuelve a estar disponible si se sabe, y ofrece el chat y el video.
- **AC5.8.3**: con D11 el techo es acumulado, así que el texto del PRD 12.3 ("alcanzó su presupuesto de este mes") deja de ser cierto. Propuesta: "La demostración de voz llegó a su presupuesto y no está recibiendo llamadas. El chat sigue disponible." / "The voice demo has reached its budget and isn't taking calls. The chat is still available." Sin mes y sin fecha de vuelta.
- **AC5.5.2**: el presupuesto de la voz principal sí es periódico y puede decirlo: "Voz de respaldo activa: la voz principal agotó su presupuesto de este periodo. La agente se comporta igual." / "Backup voice active: the main voice has used up its budget for this period. The assistant behaves the same."
- **AC5.6.2** cuando el límite por visitante se identifica por la red: un equipo que evalúa desde la misma oficina comparte una sola llamada. El mensaje debe decir "desde esta conexión" en lugar de "usted ya llamó". El mecanismo es de arquitectura; la honestidad del mensaje es de la historia.

**h) La voz de respaldo y la misma voz en los dos idiomas.** AC1.7.4 y AC1.19.2
exigen la misma voz en español y en inglés. Si la voz gratuita de respaldo
(US5.5) no conserva una sola identidad en los dos idiomas, esos criterios fallan
durante la degradación. Hay que decidir si la voz de respaldo también debe
hablar los dos idiomas con la misma voz, o si el aviso de AC5.5.2 dice que puede
sonar distinta en el otro idioma y AC1.19.2 aplica solo a la voz principal.

**i) El idioma del texto de la cláusula.** Ni el PRD ni `requirements.md` dicen
en qué idioma está escrito el corpus (F5.3 solo menciona embeddings
multilingües), y Stonecroft Mutual atiende en español. P2 (c) prohíbe presentar
una paráfrasis como texto literal de la cláusula.

- **AC2.1.9 — Idioma de la cláusula expandida** (nuevo; la decisión de fondo es de diseño de dominio y del corpus DS-1)
  - Dado una conversación en español
  - Cuando expando una cláusula citada
  - Entonces veo su texto en el idioma en que está escrita la póliza, con esa etiqueta
  - Y si existe versión en español, es la misma cláusula, con el mismo identificador y la misma versión
  - Y nunca se muestra una traducción automática como si fuera el texto literal

**j) "Tranquilo".** La guía (puntos 3 y 5) usa "Tranquilo, vamos paso a paso",
con el mismo problema de género que resolvió D10. Ninguna historia lo cita, pero
llegará al catálogo. Propuesta: "Con calma, vamos paso a paso." / "Let's take it
step by step."

### 12. Perfiles y beneficios

**Impacto: medio-bajo.**

**En `personas.md`:**

- La respuesta Q1 repartió al engineering manager del PRD 3.1 (10 minutos: alcance, decisiones de arquitectura, evidencia de producción, comunicación escrita) entre Jordan y Taylor, pero `personas.md` no lo dice, aunque sí lo dice del prospecto, del suscriptor y del visitante. La persona del sector seguros del mismo PRD 3.1 (ocasional, 10 minutos) no aparece en ningún sitio. Propuesta: una línea para cada una en la introducción, diciendo dónde quedan: el engineering manager, en las historias de Jordan (decisiones de arquitectura) y de Taylor (README y video); la persona del sector, en la validación del día 30 (S3), que va a Delivery Planning.
- Taylor dedica 90 segundos y US4.2 le da un video de 3 a 5 minutos: el "para" no cabe en su tiempo.
  - **AC4.2.6 — Lo esencial al principio** (nuevo)
    - Dado el video publicado
    - Cuando veo sus primeros 30 segundos
    - Entonces ya vi a la agente responder con una cláusula citada y el caso llegar a la bandeja
    - Y el README enlaza los capítulos del video con su minuto
- La frustración "Un servicio en español de segunda" es de Camilo; escrita para los dos, se aplica también a Ana, que habla inglés.

**"Para" que no expresan el beneficio del perfil, o que dicen algo que la agente
no puede decir:**

- **US2.2** "para no actuar sobre una cobertura que no existe": afirma que la cobertura no existe, que es una negación de cobertura que la agente nunca da (P1). Propuesta: "para no actuar sobre una respuesta que nadie puede respaldar con mi póliza".
- **US2.3** "para distinguir 'mi póliza no lo cubre' de 'hubo un problema'": el mismo problema, y además enseña al golden set que "no encuentro una cláusula" equivale a "no está cubierto". Propuesta: "para distinguir 'no encontré una cláusula sobre eso' de 'no pude revisar mi póliza ahora'".
- **US3.5** (Marcus Webb) "para saber qué falta si el asegurado vuelve": si el asegurado vuelve, lo retoma la agente, y en esta versión Marcus no devuelve llamadas. Propuesta: "para no decidir sobre un caso a medias ni perder de vista los que esperan al asegurado".
- **US3.6** (Priya Raman) "para que quede claro que la agencia coloca pólizas pero no decide siniestros": es lo que la demo le muestra a Jordan, no lo que gana Priya. Propuesta, desde su objetivo y su frustración en `personas.md`: "para pasar el siniestro a quien lo decide con todo lo capturado, sin que nadie espere de mí una decisión de cobertura que no me corresponde".
- **US1.19** (Camilo) "para sentir que me atiende alguien de acá": Camilo es asegurado en el Estado de Corvane y "de acá" supone que vive en Medellín. Propuesta: "para sentirme atendido en mi idioma y con calidez, sin que me engañen sobre qué es".
- **US1.14**: los mecanismos de la consola son de Jordan (hallazgo 6).

### 13. Operador: avisos sin canal

**Impacto: bajo.**

AC5.8.2 ("recibo una alerta"), AC5.9.5 ("queda una alerta") y AC5.10.3 ("recibo
un aviso") no dicen por dónde llega el aviso, así que no se pueden verificar, y
el objetivo de Miguel es que la demo siga viva "aunque él no esté mirando".
Propuesta para los tres: "Y la alerta llega por un canal que no exige abrir el
panel, configurado en un solo lugar, y una alerta de prueba confirma que llega".

## Positions

- AGREE: D6, el enlace abre solo la vista del caso y no la cola — mostrar la cola expondría casos de otros visitantes; la cola se demuestra en local y en el video.
- AGREE: D8, dejar de ofrecer la devolución de llamada — C3 no existe y ofrecerla viola P7 y la regla NEVER del proyecto.
- OBJECT: D8, el texto sustituto "retomarlo al volver a llamar" en el enlace público — con una llamada por visitante al día y el reinicio nocturno esa reanudación no está al alcance del visitante (hallazgo 2).
- AGREE: D9, sin plazo y sin llamada saliente — la guía (punto 7) prohíbe especular sobre tiempos y la demo no llama; en la voz pública la actualización se ve en la vista del caso (AC3.8.2).
- AGREE: D10, forma de cortesía con "le" — la propia guía ya la usa ("no le escuché bien", y "le paso a una persona" en el punto 8) y es corriente en Medellín; hay que extenderla a "Tranquilo" y quitar el "ya mismo" (hallazgos 4 y 11).
- AGREE: D11, techo acumulado de 5 USD en 90 días con alerta en 3 USD — lo fijan NFR15, D-015 y el cálculo de la respuesta Q8; el mensaje al visitante no debe hablar de "este mes" (hallazgo 11).
- OBJECT: la póliza de ejemplo como llave para retomar un caso o recibir su decisión en superficies públicas (AC1.11.2, AC1.12.2, AC1.13.1, AC1.13.2, AC1.18.2, AC1.21.3) — la conoce cualquier visitante y expone casos ajenos (RT-4, PRD 9.3).
- OBJECT: el orden del chat, identidad antes que seguridad (AC1.2.1, AC1.3.1) — contradice la guía y la voz, y pide datos antes de saber si hay heridos.
- OBJECT: "le paso ya mismo" e "I'll connect you" (AC1.7.1, AC1.19.1 y la apertura en inglés de la guía) — prometen una transferencia en vivo que la demo no hace.
- OBJECT: AC3.7.2, "aprobar y rechazar" para todo caso abierto por enlace — contradice AC3.6.3 en los casos de Knotwell.
- OBJECT: AC1.3.2, "tres líneas o menos" — depende del ancho de pantalla y no se comprueba por código; el PRD 11.2 ya fija 25 palabras.
- OBJECT: US2.2 y US2.3, beneficios escritos como "cobertura que no existe" y "mi póliza no lo cubre" — son negaciones de cobertura que la agente nunca puede dar (P1).
- OBJECT: ningún criterio de accesibilidad ni de uso en teléfono en el chat, la consola y la vista por enlace — la web es el único camino móvil del producto (W8) y el contexto declarado de Camilo y Ana.
