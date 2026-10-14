# Plan: la conversación que convence en cinco minutos

Decisiones de Miguel del 2026-10-06 sobre `diseno-conversacion-y-llamada.md`, en
el orden en que se construyen. Cada punto se cierra con su golden set, su prueba
en producción y una línea aquí. Lo que cambia de criterios aprobados queda
escrito como decisión de Miguel, con fecha.

## Decisiones que cambian criterios aprobados

- **Sin lecturas de confirmación por bloque.** Lo que la persona dice se guarda
  sin «¿es correcto?» (reemplaza BR3.1 y FD-U11-8 de U11 para la captura). La
  lectura de vuelta queda solo en el resumen final, y en la voz para los códigos
  deletreados (placa, póliza), donde oír mal es lo normal.
- **La corrección reemplaza el valor.** «Perdón, no eran dos sino tres» cambia el
  dato vigente y conserva el anterior en el historial del caso, que ya es de solo
  anexar; la agente dice «Corregido: tres heridos». Reemplaza la mitad de BR5.5
  (RT-7) que decía que la segunda versión nunca reemplaza: el ajustador sigue
  viendo las dos versiones, lo que cambia es cuál manda.
- **Recorrido rápido.** Un siniestro necesita cuatro datos para que el ajustador
  lo vea (heridos, póliza con titular, qué pasó, cuándo y dónde); vehículo y
  otras partes se ofrecen en una sola pregunta al final y son opcionales. La
  completitud publicada pasa a medir sobre esos cuatro.
- **La agente reconoce al titular.** Con una póliza válida, la agente busca el
  titular y los vehículos en el corpus y los confirma en una frase; esto funde
  identidad y vehículo en un paso.
- **El idioma lo decide la pantalla**, salvo señal clara en el mensaje.

## El orden y el estado

| # | Qué | Qué ve la persona | Estado |
| --- | --- | --- | --- |
| P6 | El reloj de silencio de la llamada arranca cuando termina de sonar la frase | La apertura no se interrumpe sola; «Escuchando» aparece al terminar | en producción desde `e4f3c0f` |
| P5 | El caso visible desde el chat, a medida que avanza | Bajo el título: «Caso KNO-000124 · 2 de 4 datos · Ver mi caso» desde el primer mensaje; la agente lo dice al terminar | en producción desde `e4f3c0f` |
| P1 | Reiniciar conversación | Botón arriba a la derecha, confirmación en línea, conversación nueva con apertura | en producción desde `e4f3c0f` |
| P2 | El idioma lo decide la pantalla | «Te respondo en español · cambia el idioma arriba»; «Hola» se contesta en el idioma del selector | en producción desde `e4f3c0f` |
| P3 | La póliza a un toque y el titular | Ficha «Usar la póliza de ejemplo · POL-200341 →» cuando la pide; «Encontré la póliza … a nombre de … con un …. ¿Es usted?» | en producción desde `e4f3c0f` |
| P4 | Recorrido rápido sin lecturas, con corrección | Cuatro datos y una oferta; «Corregido: tres heridos» | en producción desde `0d65ae4` (2026-10-06); ver la nota de abajo |

## Cómo quedó P4 (2026-10-06)

- **Nada se lee de vuelta.** Ningún campo del siniestro exige confirmación: lo
  dicho se guarda y cuenta en el acto. Los siete campos pasan a cinco obligatorios
  (identidad y póliza, qué pasó, cuándo, dónde, heridos) y dos opcionales (vehículo
  y conductor, otras personas). El avance que ve la persona cuenta solo los
  obligatorios: «3 de 5 datos».
- **El cierre deriva el caso en el mismo turno.** Con el último obligatorio, la
  agente dice «Listo: su caso STO-123456 queda con un ajustador y puede verlo con el
  enlace de arriba» y el caso pasa a la bandeja ahí mismo, no cuando la persona
  contesta la oferta. La frase es verdad cuando se dice: quien cierre la pestaña
  deja un caso que llega a alguien. Hasta hoy un siniestro completo nunca salía de
  «capturando» y la cola excluye ese estado.
- **Lo opcional se ofrece una vez**: «¿Quiere agregar el vehículo y el conductor,
  las otras personas, o lo dejamos para el ajustador?». Un sí explícito pide el
  primer bloque; un dato lo anota y sigue con el que quede; cualquier otra cosa
  cierra. **«No, así está bien» aquí declina** (ante una lectura confirmaba; la
  misma frase significa lo contrario según la pregunta, y el código las distingue).
- **Quien sigue escribiendo después del cierre** oye dónde está su caso, y lo que
  diga con forma de dato se anota igual. Antes, un mensaje a un caso ya derivado
  rompía el nodo (no tenía pregunta para «hecho»).
- **La corrección**: «perdón, no eran dos sino tres» reemplaza el dato y la agente
  dice «Corregido: tres heridos.» antes de seguir, sin volver a preguntar.
- **La guardia de salida ya conoce el número del propio caso**: sin eso, la frase de
  cierre salía como «No puedo compartir esa información» (lo cazó la prueba de
  integración, no la unitaria).
- **Golden sets**: `intake-readback-leading-no` sale (medía la lectura que ya no
  existe y no fallaba) y entran `intake-fast-closing` e `intake-correction`, en los
  dos idiomas; DS-2 queda en 60 archivos, 30 por idioma.

## La captura sin modelo donde se puede (2026-10-07)

El modelo del plan gratuito tarda entre 0,7 y 40 s por llamada, y eso rompía la
conversación («Perdón, no alcancé a procesar») y la llamada (1,6 s de presupuesto).
Desde hoy la agente guarda **por regla** lo que contesta una pregunta de un solo
dato, reparte «cuándo y dónde» por señales de fecha y de lugar, y solo llama al modelo
para respuestas largas, correcciones o textos sin señal, con 4 s de espera y el dato
pendiente como red si vence. El extractor, cuando se llama, recibe la pregunta que la
agente acababa de hacer. Detalle y medición en `docs/PENDIENTES-MIGUEL.md` («La mañana
del 7 de octubre»).

## De dónde salen los datos del titular (pregunta de Miguel)

Cada aseguradora ficticia tiene pólizas emitidas en
`app/data/tenants/<aseguradora>/issued_policies/POL-xxxxxx.json`, generadas por el
generador sintético (U7) con semilla fija: número, formulario y endosos, límites y
deducibles, **titular** (nombre, cédula, teléfono y correo inventados) y
**vehículos** (marca, modelo, año, placa y VIN inventados). Las tres pólizas de
ejemplo que muestra el inicio son tres de esas filas. Cuando la persona da la
póliza, la agente lee esa fila y dice lo que hay; no inventa nada y no pregunta
lo que ya sabe. Lo que la gente responde de verdad es «sí» o «no»: si dice que no
es ella, la agente pregunta el nombre y sigue como tercero que reporta.

## Lo que no entra en esta tanda

Variar la forma de las preguntas, hablar de tú cuando te hablan de tú, y el
nombre de pila en español. Y el icono de la marca, que se queda.
