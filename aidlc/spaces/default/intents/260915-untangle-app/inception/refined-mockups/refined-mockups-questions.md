# Plan de maquetas y preguntas — Refined Mockups

Esta etapa convierte las 87 historias de `../user-stories/stories.md` y los
requisitos de `../requirements-analysis/requirements.md` en maquetas de cada
pantalla, la especificación de sus interacciones y estados, el mapeo a un
sistema de diseño y la lista de accesibilidad. El scope `classic` no tiene la
etapa de maquetas preliminares (Rough Mockups), así que no hay bocetos previos:
las pantallas se diseñan directamente desde las historias y los requisitos, sin
inventar lo que ningún documento dice.

Antes de dibujar hay ocho decisiones que cambian la forma de las pantallas. Lo
demás ya lo fijan etapas anteriores y se resume primero para no volver a
preguntarlo. Cada pregunta lleva su recomendación con la razón; responde
escribiendo la letra en el `[Answer]:` correspondiente.

---

## Plan

### Pantallas que se van a diseñar

| Pantalla | Quién la usa | Historias |
| --- | --- | --- |
| Chat público de cada aseguradora | Camilo, Ana y quien juega a ser asegurado | US1.1 a US1.20, US1.33, US2.1 a US2.8, US2.10, US5.13 |
| Consola de llamada | Ana, Camilo y Jordan | US1.21 a US1.33, US2.7, US4.17, US5.11, US5.12, US5.14 |
| Vista de comparación entre aseguradoras | Jordan | US2.9 |
| Resumen de la traza de una respuesta | Jordan | US2.3 |
| Bandeja: lista de casos | Diana, Marcus Webb y Priya Raman | US3.1, US3.5, US6.3 |
| Vista de caso con credencial | Diana, Marcus Webb y Priya Raman | US3.2 a US3.6 |
| Vista de caso por enlace firmado, para decidir o solo lectura | Jordan | US3.7, US3.8, US1.17 |
| Panel de cifras | Jordan y Taylor | US4.16 |
| Panel de gasto | Miguel | US5.14 |
| Páginas de estado: la demo está despertando, no disponible, enlace vencido, página no encontrada | Todos | US5.16, US3.8, US1.1, US2.10 |

El README, el video y la landing (US4.1 a US4.3) no son pantallas del
aplicativo y no entran en esta etapa.

### Lo que ya está decidido y no se pregunta

- **Idiomas.** El chat responde en el idioma del mensaje, con selector visible
  (FR4.4). La bandeja es bilingüe, con inglés por defecto y la elección
  recordada (respuesta Q6 de User Stories). Todo texto sale del catálogo por
  idioma.
- **Accesibilidad.** Línea base Must inspirada en WCAG 2.1 AA y comprobada por
  herramientas en las cuatro pantallas a las que llega un visitante: chat,
  consola, vista de comparación y vista de caso por enlace. Pantallas de 360 px
  sin desplazamiento horizontal, recorrido completo con teclado, objetivos
  táctiles de 44 px o más, mensajes que se anuncian una sola vez y respeto por el
  movimiento reducido (respuesta Q9 y decisión D25 de User Stories).
- **Resumen de traza.** Lo genera el aplicativo, sin iniciar sesión y solo para
  las respuestas del propio navegador (respuesta Q8 de User Stories).
- **Datos personales en pantalla.** La transcripción de la consola muestra cada
  dato personal como una etiqueta de su tipo (D20). El panel de cifras solo
  muestra recuentos.
- **Enlace firmado.** Abre solo la vista del caso del visitante, nunca la lista
  de la aseguradora (D6), dura una hora y en cierre directo es de solo lectura
  (D19).
- **Lo que dice la agente.** Divulgación antes de todo, sin plazos, sin llamadas
  salientes, sin transferencias en vivo y sin promesas de cobertura (D8, D9,
  D13). La decisión del ajustador aparece en la conversación o en la consola.
- **Límites de la demo.** Llamada de tres minutos con aviso a los 30 segundos,
  quince minutos para retomar y botón para pasar el caso a un ajustador
  (respuesta Q7 y D12).
- **Etiquetas de acción según el tipo de registro.** Aprobar o rechazar se lee
  bien en un siniestro, pero no en una consulta de cobertura. La bandeja nombra
  las acciones según el tipo de registro, siempre con el catálogo: por ejemplo,
  "Confirmar cobertura" y "No cubierto" en una consulta. Se resuelve aquí sin
  preguntar porque no cambia ningún estado del caso.

---

## Q1 — Por dónde entra un visitante a la demo

Hoy cada aseguradora tiene su página de chat (FR4.1), y además existen la
consola de llamada, la vista de comparación y el panel de cifras. Falta decidir
la puerta de entrada: de ella depende lo primero que ven Jordan y Taylor al
llegar desde el README o desde LinkedIn.

- `A.` Una página de inicio de la demo que presenta las tres aseguradoras ficticias con su póliza de ejemplo, dice qué se puede probar y lleva al chat, a la llamada, a la comparación y al panel de cifras.
- `B.` Sin página de inicio: el README y la landing enlazan directo a cada pantalla.
- `C.` Una sola pantalla con selector de aseguradora y pestañas para chat, llamada y comparación.
- `X. Other (please specify)`

**Recomendación: A.** Quien evalúa necesita saber en segundos qué puede probar,
y la póliza de ejemplo y el aviso de demostración necesitan un lugar visible
antes de empezar. B dispersa la experiencia en enlaces sueltos; C mete tres
canales en una pantalla que se vuelve densa en el teléfono.

[Answer]: A

---

## Q2 — Identidad visual del aplicativo

La primera versión de esta pregunta ofrecía una base visual propia, separada de
la landing, por una regla del proyecto que prohibía usar la landing como insumo
de diseño. Miguel respondió que todo debe quedar alineado con la landing, pidió
borrar esa regla (se borró de `project.md`) y abrió la conversación sobre la
landing que sigue en Q2b. La pregunta se replanteó así: las páginas de chat
representan a aseguradoras ficticias, mientras que la bandeja, la consola y los
paneles son de Untangle, y la landing ya fija la paleta (cobre e índigo sobre
casi negro), la tipografía y el hilo que corre con el scroll.

- `A.` Un sistema visual con dos temas. La identidad de la landing en tema oscuro para el inicio, la consola, la bandeja, la traza y los paneles. Las páginas de cada aseguradora en tema claro de lectura, con el acento de su marca ficticia y la firma "con Untangle". El hilo como motivo funcional y sin fotos de cuerdas dentro del aplicativo.
- `B.` Todo el aplicativo en el tema oscuro de la landing, también las páginas de las aseguradoras, cada una con su acento.
- `C.` Reinventar la identidad antes de diseñar, con un concepto visual e imágenes nuevas, y alinear después la landing y el aplicativo.
- `X. Other (please specify)`

**Recomendación: A.** Alinea el aplicativo con la landing sin llevar al chat de
una persona estresada la estética de una página de marketing: quien lee
cláusulas necesita una superficie clara, y cada aseguradora se reconoce por su
acento, también en la comparación lado a lado. El cobre sobre blanco no llega al
contraste mínimo (2,7:1), así que en el tema claro no se usa como texto.

[Answer]: A

Precisión de Miguel: le gusta la opción A y se mantiene lo que plantea sea cual sea el estilo final; la pregunta de si se reinventan la animación y las imágenes de la landing se resolvió aparte, en Q2b.
---

## Q2b — Si la animación del héroe y las imágenes de nudos encajan con aseguradoras

Miguel está de acuerdo con la marca: el hilo que corre a la izquierda con el
scroll, la paleta y la tipografía. Su duda es si un nudo de cuerda es coherente
con el mundo de las aseguradoras. La revisión del sitio encontró que la
metáfora funciona (un siniestro se vive como un enredo y ordenarlo es lo que
hace el primer aviso), pero que la historia de las imágenes termina mal para una
aseguradora: el video acaba en hebras sueltas y la imagen del cierre muestra dos
cuerdas deshilachadas, que en seguros se lee como ruptura.

- `A.` Mantener el nudo y regenerar con Higgsfield dos o tres piezas con la misma estética, para que la historia termine en protección: los hilos se trenzan en una cuerda firme y la imagen deshilachada pasa a ser un empalme limpio.
- `B.` Dejar la animación y las imágenes como están, porque el texto ya ancla la metáfora al siniestro.
- `C.` Cambiar el nudo por imágenes literales del mundo de seguros (vía, carro, documento que se ordena), conservando la paleta, la tipografía y el hilo lateral.
- `X. Other (please specify)`

**Recomendación: A.** Conserva una idea propia que evita los clichés visuales de
seguros y corrige solo las piezas que contradicen la protección. C es coherente
de forma más directa, pero cambia la identidad visual de la landing y exige
producir el concepto nuevo.

[Answer]: C

Precisión de Miguel: "Creo que es mejor cambiar de diseño por uno que encaje mejor la temática, por ejemplo lo que es en el punto C lo veo coherente y creo que va a ser la mejor opción". Se conservan la paleta, la tipografía y el hilo que corre a la izquierda con el scroll; cambian la animación del héroe y las imágenes de nudos. El rediseño de la landing es trabajo aparte de esta etapa: el aplicativo no usa esas imágenes.
---

## Q3 — Cómo se ve una respuesta con cláusula citada en el chat

Cada cita muestra su identificador, su versión, el texto completo expandible y
el enlace al resumen de la traza (US2.3). La forma decide cuánto ruido ve la
persona asegurada frente a cuánta evidencia tiene a mano quien evalúa.

- `A.` Debajo de la respuesta, una tarjeta de fuente con identificador y versión. "Ver cláusula" la expande dentro del mismo mensaje, y "Cómo se llegó a esta respuesta" abre el resumen de la traza en un panel lateral, que en el teléfono sube desde abajo.
- `B.` La cláusula y el resumen de la traza se expanden los dos dentro del mensaje.
- `C.` Un panel fijo de fuentes junto a la conversación, que acumula todas las cláusulas citadas.
- `X. Other (please specify)`

**Recomendación: A.** La persona asegurada lee una respuesta limpia, y quien
evalúa abre la evidencia con un toque sin perder el hilo. En 360 px, el panel que
sube desde abajo evita el desplazamiento horizontal. B alarga los mensajes hasta
perder la conversación; C le quita ancho al chat en el teléfono.

[Answer]: A

---

## Q4 — Qué muestra la consola mientras dura la llamada

La consola es la pantalla que más mira Jordan (US4.17): estado de la llamada,
tiempo restante, transcripción con quién habla, estado de la agente y latencia
del último turno. Los datos personales se muestran como etiquetas (D20).

- `A.` Dos zonas. La conversación, con la transcripción y los controles de la llamada, y "Qué está pasando", con el estado de la agente, la latencia del último turno, los bloques del caso ya confirmados marcados sin sus valores y el trabajo de fondo en curso, como la revisión de la póliza. En el teléfono, las dos zonas son pestañas y los controles quedan fijos abajo.
- `B.` Una sola columna al estilo de una llamada, con los detalles técnicos plegados bajo "Ver detalles".
- `C.` Una pantalla de llamada simple para quien juega a ser asegurado y un modo evaluador que se activa aparte.
- `X. Other (please specify)`

**Recomendación: A.** Muestra sin explicaciones que la agente responde mientras
revisa la póliza de fondo, que es lo que un ingeniero quiere comprobar. Como no
muestra valores del caso, no choca con la redacción. B esconde justo la
evidencia; C duplica pantallas y pruebas.

[Answer]: A

---

## Q5 — Cómo se organiza la vista de caso para decidir

La misma vista la usan Diana, Marcus Webb y Priya Raman con credencial, y Jordan
con el enlace firmado, a veces desde el teléfono (US3.2, US3.7 y US3.8). Lo
primero visible debe ser el motivo, la categoría, la completitud y las acciones
de decisión.

- `A.` Un encabezado fijo con motivo, categoría, completitud y acciones. Debajo, la evidencia en secciones plegables en el orden en que se decide: campos, transcripción, cláusulas, regla, controles y traza. En escritorio, campos y transcripción lado a lado.
- `B.` Un encabezado con las acciones y la evidencia en pestañas, una por bloque.
- `C.` Todo desplegado en una página larga con un índice lateral.
- `X. Other (please specify)`

**Recomendación: A.** Las acciones nunca quedan lejos, las secciones plegables
funcionan igual con teclado, con lector de pantalla y en 360 px, y el orden sigue
la pregunta del ajustador: por qué me llegó y qué necesito ver para decidir. Las
pestañas esconden evidencia que conviene ver junta; la página larga aleja las
acciones en el teléfono.

[Answer]: A

---

## Q6 — Sobre qué base de componentes se diseña

El framework de la interfaz todavía no existe: lo fija la decisión de
arquitectura del lenguaje en Domain Design (restricción C8). Aun así, el mapeo a
un sistema de diseño es un entregable de esta etapa.

- `A.` Tokens propios (color, tipografía, espaciado, radios) y componentes con nombres genéricos (botón, tarjeta de fuente, burbuja de mensaje, encabezado de caso), cada uno con sus estados y su accesibilidad. Domain Design los mapea a la librería que elija.
- `B.` Elegir ya una librería concreta de componentes y diseñar sobre ella, lo que condiciona la decisión de arquitectura de la interfaz.
- `C.` Sin sistema de diseño: estilos definidos pantalla por pantalla.
- `X. Other (please specify)`

**Recomendación: A.** No adelanta una decisión que el flujo reserva a Domain
Design y deja listo el contrato visual que cualquier librería debe cumplir. B
invierte el orden de las decisiones; C rompe la consistencia entre pantallas y
multiplica el trabajo de accesibilidad.

[Answer]: A

---

## Q7 — Dónde viven el panel de cifras y el panel de gasto

Las cinco cifras del sistema son públicas (FR10.5). El gasto por caso, por
proveedor y por mes, con el acumulado de la ventana de 90 días (FR10.3), es
operación de Miguel. El visor completo de trazas corre solo en local.

- `A.` El panel de cifras como página pública del aplicativo, y el panel de gasto como página privada a la que solo entra Miguel con una credencial de operador.
- `B.` Los dos paneles públicos, con los montos de gasto visibles para cualquiera.
- `C.` El panel de cifras público y el gasto solo por línea de comandos.
- `X. Other (please specify)`

**Recomendación: A.** Las cifras son evidencia para quien evalúa, incluido el
costo por caso. El gasto en dólares es operación personal y no le suma a la
evidencia. Una página privada permite revisarlo desde el teléfono cuando llega la
alerta, cosa que la línea de comandos no permite. Implica un rol de operador en
las credenciales de US5.7.

[Answer]: B

---

## Q8 — Cómo quieres revisar las maquetas

Los entregables del flujo son documentos Markdown: maquetas de cada pantalla en
esquema, especificación de interacciones y estados, mapeo al sistema de diseño y
lista de accesibilidad. Ver una pantalla es más fácil que leer su descripción.

- `A.` Los documentos Markdown y, además, una maqueta navegable en HTML de las pantallas principales, publicada como página privada para revisarla en el navegador o en el teléfono.
- `B.` Solo los documentos Markdown con los esquemas de cada pantalla.
- `C.` Solo la maqueta navegable, con los documentos mínimos que exige el flujo.
- `X. Other (please specify)`

**Recomendación: A.** Es una etapa visual: aprobar una pantalla viéndola es más
rápido y destapa problemas que un esquema esconde, como un botón que queda fuera
de la vista en el teléfono. La maqueta es material de revisión, no código del
aplicativo. B obliga a imaginar las pantallas; C deja sin especificar los
estados y la accesibilidad que Construcción necesita.

[Answer]: A

---

## Registro de modo de interacción

[Answer]: Guide me
