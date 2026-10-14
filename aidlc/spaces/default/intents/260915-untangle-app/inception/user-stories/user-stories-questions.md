# Plan de historias y preguntas — User Stories

Esta etapa convierte los 84 requisitos funcionales y los 21 no funcionales de
`../requirements-analysis/requirements.md` en historias de usuario
verificables. Antes de escribirlas hay seis decisiones que cambian qué historias
existen y cómo se parten. El resto del plan ya lo fijan el PRD, las prácticas
afirmadas y la etapa anterior; se resume primero para que no se vuelva a
preguntar.

Cada pregunta lleva su recomendación con la razón. Responde escribiendo la letra
en el `[Answer]:` correspondiente.

---

## Plan

### Formato de cada historia

- "Como [persona], quiero [objetivo], para [beneficio]", con identificador
  estable `US{épica}.{n}` (por ejemplo `US1.3`).
- Criterios de aceptación en Dado / Cuando / Entonces, las palabras clave de
  Gherkin en español, cada uno con identificador `AC{épica}.{n}.{m}`. Cada
  historia tiene al menos un camino feliz y un camino de error o de borde.
- Prioridad MoSCoW heredada del PRD: una historia es Must si realiza un Must
  (M1 a M21) y Should si realiza un Should (S1, S2, S4, S5). La frontera del MVP
  la fija Delivery Planning.
- Cumplimiento de INVEST anotado por historia, con sus dependencias explícitas.
- Cada historia nombra los requisitos que realiza (`FR`, `NFR`) y los módulos
  que toca (`MOD-01` a `MOD-15`), para que Units Generation las agrupe por
  componente, que es como Construcción recorre el trabajo.
- Los requisitos no funcionales que una persona percibe (latencias, citación,
  retención, paridad de idiomas, tiempo desde clonar hasta el reporte) entran
  como criterios de la historia que los entrega. Los que solo mide el equipo
  (cobertura de líneas) quedan diferidos a la etapa de requisitos no
  funcionales, con ese destino escrito.

### Lo que ya está decidido y no se pregunta

- Personas de la bandeja: Diana en Stonecroft Mutual, Marcus Webb en Sunmeadow
  Auto y Priya Raman en Knotwell Insurance Agency; jurisdicción ficticia del
  Estado de Corvane (entrevista de Requirements Analysis, Q7).
- Frases exactas de la agente: salen de `docs/pre_prb/voz-y-tono.md` y se citan,
  no se reescriben.
- Enlace de voz público con 3 minutos por llamada, 1 llamada por visitante al
  día y 15 al día en el sitio; voz de respaldo gratuita al agotar el presupuesto
  de la voz paisa; techo de 5 USD con revisión en el día 30; ningún audio
  persistido; el caso del visitante vive hasta el reinicio nocturno; enlace
  firmado de una hora ligado solo a su caso (Q1 a Q8 de esa misma entrevista).

### Cómo se resuelven las tres observaciones que aprobaste como riesgo

- **Funcionalidades Should que desaparecieron de los requisitos** (continuidad
  voz a chat, detección automática de idioma y vista de comparación entre
  aseguradoras): se deciden en la pregunta Q5.
- **La agente nunca finge ser una persona**: entra como historia Must con
  criterios en los dos idiomas y su caso adversarial, a partir del principio P10
  y de la guía de voz, que ya fija la respuesta en español: "No, soy una
  asistente de inteligencia artificial, pero la voy a ayudar con todo esto, y si
  necesita a una persona la paso ya mismo." La versión en inglés sale del
  catálogo de textos con paridad comprobada.
- **Costo por llamada**: el objetivo de 0,02 USD (NFR14) está escrito para una
  llamada de cuatro minutos, y el enlace público corta a los tres (FR3.9). El
  criterio se expresa por minuto de llamada, 0,005 USD, que es la misma meta y
  ya no depende de la duración: una llamada de tres minutos queda en 0,015 USD o
  menos. La etapa de requisitos no funcionales lo registra como objetivo medible
  con ese mismo valor.

### Lo que no se convierte en historia, y dónde queda

- La validación del día 30 con personas del perfil de quien contrata (S3) y la
  prueba ciega de la voz paisa (S6) son actividades del proyecto, no
  comportamiento del sistema: se planifican en Delivery Planning.
- La revisión semanal de la cola de anotación, el red-team por hito y la
  revisión de gasto del día 30 son rituales del operador: también van a Delivery
  Planning.
- Las funcionalidades Could (C1 documentos al caso, C2 Keycloak, C3 devolución
  automática de llamadas, C4 interfaz de administración, C6 métricas de voz por
  proveedor) y las Won't (W1 a W9) quedan listadas al final de las historias con
  su razón, sin criterios.

### Contradicciones que las historias resuelven en lugar de heredar

- El journey 7.1 del PRD cierra con "le llega una actualización hoy por mensaje
  de texto", pero no hay mensajes de texto en el alcance: la actualización llega
  por el canal del caso (FR8.5). Las historias usan FR8.5.
- El mismo journey dicta un número de caso de cinco dígitos; el requisito fija
  prefijo de la aseguradora más seis dígitos (FR1.5). Las historias usan FR1.5.
- El PRD 9.3 dice que el administrador cambia la configuración "mediante un pull
  request"; la práctica afirmada son commits directos a `main` con GitHub
  Actions como compuerta. Las historias usan la práctica.
- La apertura de la guía de voz ofrece "cotizar un seguro". Si la cotización
  (S1) no se construye, ofrecerla prometería algo que no existe (principio P7):
  la historia de la apertura lleva ese criterio.
- El idioma de la interfaz de la bandeja: se decide en la pregunta Q6.

---

## Q1 — Qué personas escriben las historias

El PRD nombra ocho roles (sección 9.3) y tres compradores del lado de quien
contrata (sección 3.1): el reclutador técnico, que dedica 90 segundos; el
engineering manager, que dedica 10 minutos; y el staff engineer, que dedica de 30
a 60 minutos y puede vetar. Cada persona con historias propias añade trabajo de
revisión; cada persona que se funde con otra pierde un punto de vista.

- `A.` Seis personas: el asegurado (Camilo en español, Ana en inglés), el ajustador (Diana y Marcus Webb), la agente de cuenta de la agencia (Priya Raman), el staff engineer que evalúa, el reclutador técnico y Miguel como operador, que absorbe al administrador de la aseguradora. El visitante del enlace público se escribe como el staff engineer cuando prueba la demo; el suscriptor y el prospecto aparecen solo dentro de las historias de cotización.
- `B.` Nueve personas: una por cada rol del PRD 9.3 más el reclutador técnico. Más fiel al PRD, con historias casi iguales repetidas entre roles parecidos.
- `C.` Cuatro personas: asegurado, ajustador (que incluye a la agente de cuenta), un solo evaluador para reclutador y staff engineer, y operador.
- `X. Other (please specify)`

**Recomendación: A.** Separa lo que de verdad se comporta distinto. La agente de
cuenta nunca decide cobertura: fundirla con el ajustador escondería justo la
regla que la agencia existe para demostrar. El reclutador mira 90 segundos de
superficie y el staff engineer clona el repositorio: un solo evaluador mezclaría
dos pruebas opuestas. El engineering manager queda cubierto entre los dos, porque
lee las mismas decisiones de arquitectura que el staff engineer revisa. Y el
administrador de la aseguradora no tiene interfaz en esta versión: edita
archivos, que es lo que hace el operador.

**Aclaración tras la primera presentación.** Aquí "persona" no es alguien
que participa en el proyecto: es un tipo de usuario ficticio desde cuyo punto
de vista se escribe cada historia. Miguel es la única persona del proyecto y
pidió que los perfiles los defina yo; lo que se le pregunta es cuántos, porque
eso cambia cuántas historias se escriben.

[Answer]: A

---

## Q2 — Cómo se agrupan las historias

Construcción recorre el trabajo por componente: primero una base sólida y
después una pieza completa a la vez. La forma de agrupar las historias
condiciona cuánto le cuesta a Units Generation convertirlas en esas piezas.

- `A.` Épicas por recorrido de una persona: reportar un siniestro, preguntar por cobertura, decidir en la bandeja, verificar la evidencia, operar la demo y cotizar. Cada historia es una rebanada de punta a punta y lleva etiquetados los módulos que toca, para que Units Generation las agrupe por componente.
- `B.` Épicas por módulo del PRD (MOD-01 a MOD-15): calca el recorrido por componente, pero produce historias técnicas del tipo "como sistema quiero", que no dicen para quién es el valor.
- `C.` Épicas por capa del plan de entrega (texto, bandeja y chat, voz en inglés, voz en español, cotización): calca el calendario, pero parte un mismo recorrido en varias épicas.
- `X. Other (please specify)`

**Recomendación: A.** Las historias existen para decir quién recibe el valor;
los módulos ya están en el PRD y el orden lo fija Delivery Planning. Con la
etiqueta de módulo en cada historia, Units Generation tiene lo que necesita sin
que las historias se vuelvan técnicas.

[Answer]: A

---

## Q3 — Qué tan grande es cada historia

Con 84 requisitos funcionales hay que fijar el tamaño. Una historia demasiado
grande no se puede probar ni entregar sola; una demasiado pequeña deja de tener
valor propio.

- `A.` De uno a tres días de trabajo, con tres a seis criterios cada una: del orden de 45 a 60 historias.
- `B.` Una historia por caso de uso y por caso borde del PRD: del orden de 15 a 20 historias, con diez o más criterios cada una.
- `C.` Una historia por requisito funcional: 84 historias, trazabilidad uno a uno y mucha fragmentación.
- `X. Other (please specify)`

**Recomendación: A.** Es el tamaño que INVEST pide (pequeña y comprobable) y el
que deja a Delivery Planning margen para aplicar la regla de corte sin partir
historias a la mitad. B produce historias que no caben en un componente; C
produce historias sin valor propio, como "la placa se dicta dígito a dígito"
sola.

[Answer]: A

---

## Q4 — Los dos idiomas dentro de las historias

El español y el inglés tienen las mismas metas (principio P12), pero no se
entregan a la vez: la voz en inglés llega en las semanas 5 a 7 y la voz en
español en la semana 9 (Must M12 y M14). Si el tiempo aprieta, el español se
reduce, nunca se corta.

- `A.` En texto, chat y bandeja, un solo juego de criterios que vale para los dos idiomas, con ejemplos por idioma solo donde el comportamiento cambia. En voz, historias separadas para inglés y para español, porque se entregan en capas distintas.
- `B.` Un solo juego de criterios para los dos idiomas en todo, incluida la voz.
- `C.` Historias separadas por idioma en todo, también en texto, chat y bandeja.
- `X. Other (please specify)`

**Recomendación: A.** El texto se evalúa en los dos idiomas desde la línea base
de la semana 3, así que separarlo duplicaría historias sin ganar nada. La voz sí
llega en dos entregas: con historias separadas, la voz en inglés se termina y se
aprueba sin esperar al español, que es lo que pide el recorrido por componente.
Las historias de voz en español repiten la conducta y añaden lo propio: la
apertura exacta, el usted cálido con marcadores paisas ligeros y el dictado de
cédulas.

[Answer]: A

---

## Q5 — Las tres funcionalidades Should que desaparecieron de los requisitos

La revisión de Requirements Analysis encontró tres funcionalidades que el PRD
clasifica como Should y que no quedaron ni en los requisitos ni fuera del
alcance: la continuidad voz a chat (S2: retomar por chat, con el número de caso,
un caso empezado por voz), la detección automática de idioma (S4: la agente
cambia de idioma sin que se lo pidan) y la vista de comparación entre
aseguradoras (S5: la misma pregunta respondida por las tres, lado a lado).
Aprobaste esa revisión aceptando el riesgo; aquí se cierra.

- `A.` Escribirlas como historias Should completas, con criterios y con su lugar en la regla de corte del PRD (S2 es la primera que se corta; S5 y S4, las últimas). Delivery Planning decide si entran.
- `B.` Registrarlas como fuera de esta versión, con su razón y sin criterios.
- `C.` Escribir solo la vista de comparación (S5), que es barata si el chat existe, y dejar S2 y S4 fuera de esta versión.
- `X. Other (please specify)`

**Recomendación: A.** El PRD aprobado las clasificó como Should y ya tiene la
regla que decide cuándo se cortan. Escribirlas no obliga a construirlas: deja
escrito qué significa "terminada" para cada una, así que si el tiempo alcanza no
hay que volver a Incepción. Recortarlas aquí sería tomar la decisión de Delivery
Planning dos etapas antes y sin el calendario a la vista.

[Answer]: A

---

## Q6 — En qué idioma está la interfaz de la bandeja

Dos documentos aprobados dicen cosas distintas. El PRD (módulo de la bandeja,
MOD-08) fija la interfaz en inglés, porque la audiencia es quien contrata, con el
contenido del caso en el idioma del asegurado. Las prácticas de código afirmadas
en Practices Discovery ponen las etiquetas de la bandeja en el catálogo de
textos por idioma y comprueban que cada etiqueta exista en español y en inglés:
con la bandeja solo en inglés, esa comprobación arrancaría en rojo. Además,
Diana, la ajustadora de Stonecroft Mutual, atiende en español.

- `A.` Bilingüe con selector y en inglés por defecto: quien contrata la ve en inglés, Diana y el visitante hispanohablante la cambian, y la comprobación de paridad se cumple sin excepciones.
- `B.` Solo en inglés, como fija el PRD: la comprobación de paridad excluye las etiquetas de la bandeja, con la razón escrita en su lista de exclusiones.
- `C.` En el idioma por defecto de cada aseguradora y sin selector: Stonecroft en español; Sunmeadow y Knotwell en inglés.
- `X. Other (please specify)`

**Recomendación: A.** Resuelve la contradicción sin sacar a nadie del chequeo. B
es legítima, porque la lista de exclusiones existe para eso, pero deja fuera de
la comprobación justo la pantalla que un evaluador abre en vivo. El costo de A es
traducir unas decenas de etiquetas, y el inglés por defecto conserva lo que el
PRD buscaba.

[Answer]: A

---

## Registro de modo de interacción

[Answer]: Guide me

---

## Decisiones que surgieron en la revisión del equipo

Diseño, desarrollo y calidad revisaron el borrador por separado. Casi todo lo que
encontraron se corrige sin preguntarte, porque lo exige un principio, una regla
afirmada o un requisito aprobado: por ejemplo, que la póliza de ejemplo
compartida no permita ver el caso de otro visitante, o que el chat pregunte por
heridos antes de pedir la póliza. Estas cuatro, en cambio, tienen dos respuestas
legítimas y cambian lo que ve quien prueba la demo.

## Q7 — La llamada pública de tres minutos

El PRD estima que un reporte simple por voz toma hasta cinco minutos y catorce
turnos (sección 10.3). El enlace público corta a los tres y admite una llamada
por visitante al día (FR3.9). Así, lo más probable es que casi todas las
llamadas públicas se corten a medias, sin enlace para decidir el caso en la
bandeja y sin forma de retomarlo: el visitante nunca ve el ciclo completo por
voz.

- `A.` Mantener tres minutos y diseñar para ellos: aviso a los treinta segundos del final; al llegar al límite, la agente resume y pasa el caso a un ajustador con el motivo "límite de la demostración", y la consola entrega el enlace para decidirlo. Además, volver a llamar dentro de los quince minutos siguientes para retomar el mismo caso no cuenta como la llamada del día, aunque sí contra las quince llamadas del sitio y contra el techo de gasto.
- `B.` Subir la llamada a cinco minutos y bajar el tope del sitio a nueve llamadas al día: los mismos 45 minutos diarios de voz y el mismo gasto máximo, y el reporte suele terminar dentro de la llamada.
- `C.` Dejar todo como está y decir en la consola, al cortar, que en la demo pública la llamada no se puede retomar ni decidir; la reanudación se muestra en local y en el video.
- `X. Other (please specify)`

**Recomendación: A.** Conserva los límites que elegiste y convierte el final más
probable, una llamada cortada, en algo que el evaluador puede usar: un caso que
decide en la bandeja. B es buena alternativa si la medición del golden set de
audio muestra que el reporte típico pasa de tres minutos, y se adopta después
cambiando configuración.

[Answer]: A

---

## Q8 — El enlace "ver la traza" en el chat público

El PRD promete que junto a cada cita del chat se puede abrir la traza de la
respuesta (F4.4, caso de uso UC-2). Pero el visor de trazas corre solo en local
(PRD 9.5); publicarlo exige más infraestructura y abre una puerta a las
conversaciones de otros visitantes.

- `A.` Un resumen de la traza que genera el propio aplicativo, sin iniciar sesión y solo para las respuestas de ese navegador, con los datos personales redactados: qué nodos corrieron, qué cláusulas se recuperaron y verificaron, latencia y costo. El visor completo sigue en local y en el video.
- `B.` Sin enlace: el chat muestra el identificador de la traza y explica que se consulta corriendo el repositorio en local.
- `C.` Publicar el visor completo de trazas en línea, en solo lectura para la demo.
- `X. Other (please specify)`

**Recomendación: A.** Cumple la promesa en la superficie que más prueba el
evaluador, sin publicar un sistema más ni exponer conversaciones ajenas. B es
honesta pero quita evidencia justo donde más pesa; C suma infraestructura y
superficie de ataque.

[Answer]: A

---

## Q9 — Accesibilidad y uso desde el teléfono

Ni el PRD, ni los requisitos, ni las historias tienen un solo criterio de
accesibilidad o de uso en pantalla de teléfono. Pero quien reporta un accidente
lo hace desde el teléfono, la reclutadora llega desde LinkedIn y el enlace para
decidir el caso se abre donde se recibió. Añadirlo después de construir la
interfaz cuesta mucho más que desde el primer commit.

- `A.` Must, con una línea base que comprueban herramientas en cada entrega: analizador automático de accesibilidad sin hallazgos serios, pantallas de 360 px de ancho sin desplazamiento horizontal, todo el recorrido con teclado y subtítulos en el video. Se describe como "inspirada en WCAG 2.1 AA", nunca como cumplimiento.
- `B.` Should, dentro de la regla de corte.
- `C.` Fuera de esta versión, escrito con su razón.
- `X. Other (please specify)`

**Recomendación: A.** Es proporcionada: no promete una certificación, solo lo que
una herramienta comprueba. Y es una señal de oficio visible para quien evalúa.

[Answer]: A

---

## Q10 — La voz de respaldo en los dos idiomas

Cuando se agota el presupuesto de la voz paisa, la demo sigue con una voz
gratuita de respaldo (FR3.8). El principio P10 exige la misma voz y el mismo
acento en español y en inglés, pero las voces gratuitas suelen ser distintas en
cada idioma.

- `A.` Excepción escrita solo para el modo de respaldo: la voz puede sonar distinta en cada idioma y la consola lo avisa; la regla de una sola voz aplica siempre a la voz principal.
- `B.` Exigir también a la voz de respaldo una sola identidad en los dos idiomas, aunque eso limite las opciones gratuitas o obligue a pagar.
- `C.` Sin voz de respaldo: al agotarse el presupuesto de la voz paisa, la voz rechaza llamadas con un mensaje honesto y el chat sigue.
- `X. Other (please specify)`

**Recomendación: A.** Mantiene viva la demo, como elegiste en Requirements
Analysis (Q2), y es honesta. El principio protege la identidad de la agente en la
experiencia normal; el modo de respaldo es excepcional y se declara.

[Answer]: A
