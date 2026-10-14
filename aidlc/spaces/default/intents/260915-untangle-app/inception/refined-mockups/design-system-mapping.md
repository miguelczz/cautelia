# Sistema de diseño — Untangle

Tokens, temas y componentes con los que se dibujan todas las pantallas del
aplicativo. Sale de las respuestas de `refined-mockups-questions.md` (Q2, Q2b y
Q6), de las historias de `../user-stories/stories.md`, de los requisitos de
`../requirements-analysis/requirements.md` y de las prácticas de estilo de
`../practices-discovery/team-practices.md`, en especial el catálogo de textos
por idioma y la paridad de claves. No hay `wireframes.md` ni `user-flow.md`
previos: el scope `classic` no ejecuta Rough Mockups.

El sistema no nombra una librería de componentes. Esa elección es de la
decisión de arquitectura de la interfaz en Domain Design (restricción C8). Aquí
queda el contrato visual que cualquier librería debe cumplir y, al final, los
criterios para elegirla.

## Principios

1. **La marca vive en los detalles.** El aplicativo es una herramienta para
   trabajar, no una página para convencer. La identidad de la landing llega por
   la paleta, la tipografía y el hilo; no hay fotos ni ilustraciones decorativas
   dentro del aplicativo.
2. **Un solo momento audaz: el hilo del caso.** Una línea que se llena a medida
   que se confirman los bloques del caso. Aparece en la consola, en la vista de
   caso y en la traza, y es el mismo hilo que recorre la landing. Todo lo demás
   es sobrio.
3. **Dos modos completos que elige la persona.** Claro y oscuro existen en
   todas las pantallas y se cambian con un selector de tema. Ninguna pantalla
   impone su modo y ninguna navegación salta de uno al otro, porque el cambio
   brusco de oscuro a claro cansa la vista (decisión de Miguel en la revisión de
   esta etapa, que reemplaza el tema por superficie de Q2).
4. **Cada texto sale del catálogo.** Frases en tipo oración, sin etiquetas en
   mayúsculas sobre los títulos, con el mismo nombre de una acción en todo el
   recorrido.
5. **La monoespaciada es para datos.** Identificadores de caso y de cláusula,
   latencias, costos, horas y versiones. Nunca como disfraz de "técnico".
6. **Estados completos.** Cada componente interactivo tiene por defecto, encima,
   foco, activo, deshabilitado, cargando y error; cada lista, su vacío.
7. **El movimiento explica un cambio.** Menos de 300 ms, curvas propias, sin
   coreografías de carga y con alternativa para movimiento reducido.
8. **Se entiende sin contexto.** Quien llega sin saber nada del proyecto sabe
   qué hacer en cada pantalla: las acciones dicen lo que pasa, los datos de
   ejemplo dicen para qué sirven y ninguna etiqueta usa jerga del sistema.

## Modos de tema

Claro y oscuro son dos modos completos del aplicativo, no temas asignados a
cada pantalla. La primera visita usa el modo del dispositivo; desde ahí la
persona lo cambia con el selector de tema, presente en la barra superior de
todas las pantallas, y su elección se recuerda en ese navegador. Cambiar de
pantalla nunca cambia el modo.

| Regla | Detalle |
| --- | --- |
| Un solo modo a la vez | El chat de la aseguradora, el panel de la traza que se abre sobre él, la consola, la bandeja, los paneles y las páginas de estado usan el mismo modo |
| Identidad sin cambiar de modo | La aseguradora se reconoce por su monograma, su nombre, la firma "con Untangle" y su acento, que existe en los dos modos |
| Sin transición animada | El cambio de modo es inmediato: animar todos los colores a la vez es justo el golpe visual que se quiere evitar |
| Sin salto al cargar | El modo se aplica antes de pintar la página, para que no parpadee el modo contrario |

## Tokens de color

Todos los contrastes están medidos contra el fondo base y la superficie elevada
de su tema. Un texto necesita 4,5:1 y un borde de control o un gráfico
necesario, 3:1.

### Modo oscuro

| Token | Valor | Uso | Contraste |
| --- | --- | --- | --- |
| `color.dark.canvas` | `#0B0B12` | Fondo base, el mismo de la landing | — |
| `color.dark.canvasDeep` | `#07070C` | Barras fijas y pie | — |
| `color.dark.surface` | `#13131D` | Superficies elevadas: secciones, paneles, tablas | — |
| `color.dark.surfaceRaised` | `#1B1B28` | Filas seleccionadas, campos de texto | — |
| `color.dark.hairline` | `#2A2A3C` | Divisores decorativos, nunca como único límite de un control | — |
| `color.dark.controlBorder` | `#66667F` | Borde de campos, selectores y botones secundarios | 3,52 / 3,31 |
| `color.dark.textPrimary` | `#F0ECE6` | Texto principal | 16,67 / 15,67 |
| `color.dark.textSecondary` | `#A9A7B3` | Texto de apoyo | 8,28 / 7,79 |
| `color.dark.textTertiary` | `#8B8997` | Marcas de tiempo, notas | 5,72 / 5,38 |
| `color.dark.accent` | `#E0873A` | Acción principal, selección actual, foco, nodo confirmado del hilo | 7,19 / 6,76 |
| `color.dark.accentHover` | `#F0A35C` | Encima de la acción principal | — |
| `color.dark.inkOnAccent` | `#120B06` | Texto sobre el cobre | 7,15 |
| `color.dark.indigo` | `#4A57E0` | Solo gráficos grandes: trabajo de fondo en el hilo, degradado del hilo | 3,48 / 3,28 |
| `color.dark.indigoText` | `#9CA4F4` | Enlaces y texto informativo | 8,43 / 7,93 |
| `color.dark.thread` | `#E9C29A` | Línea del hilo | 11,81 |
| `color.dark.success` | `#7CC49A` | Control aprobado, bloque confirmado en listas | 9,54 / 8,98 |
| `color.dark.warning` | `#E3C25C` | Avisos: límite cerca, voz de respaldo | 11,33 / 10,66 |
| `color.dark.danger` | `#F28B82` | Errores, emergencia, colgar | 8,21 / 7,72 |

### Modo claro

Blanco neutro frío, no crema: la combinación crema más acento terracota es un
patrón típico de diseño generado. El cobre de la marca sobre blanco no pasa el
contraste (2,73:1), así que en el modo claro la marca usa su tinta oscura
`#9A4F12` para texto, foco y botón principal, y el cobre no aparece como texto.

| Token | Valor | Uso | Contraste |
| --- | --- | --- | --- |
| `color.light.page` | `#F5F6F8` | Fondo de la página | — |
| `color.light.surface` | `#FFFFFF` | Conversación, tarjetas de fuente, compositor | — |
| `color.light.surfaceSunken` | `#EEF0F3` | Mensajes de la persona, cita expandida | — |
| `color.light.hairline` | `#E1E4E9` | Divisores decorativos | — |
| `color.light.controlBorder` | `#7A808D` | Borde de campos y botones secundarios | 3,96 / 3,66 |
| `color.light.canvasDeep` | `#FFFFFF` | Barras fijas y pie | — |
| `color.light.text` | `#15161D` | Texto principal | 18,04 / 16,68 |
| `color.light.textSecondary` | `#525866` | Texto de apoyo | 7,13 / 6,59 |
| `color.light.textTertiary` | `#5F6573` | Marcas de tiempo, notas | 5,84 / 5,40 |
| `color.light.link` | `#4A57E0` | Enlaces e información | 5,63 |
| `color.light.untangleInk` | `#9A4F12` | Marca en claro: firma "con Untangle", botón principal de Untangle con texto blanco (6,00), foco, selección actual y nodo confirmado del hilo | 6,00 / 5,55 |
| `color.light.untangleInkHover` | `#7F410F` | Encima del botón principal de Untangle | — |
| `color.light.indigo` | `#4A57E0` | Gráficos: trabajo de fondo en el hilo | 5,63 |
| `color.light.thread` | `#B8753A` | Línea del hilo | 3,72 / 3,40 |
| `color.light.success` | `#22704A` | Confirmaciones | 6,03 / 5,57 |
| `color.light.warning` | `#8A5A00` | Avisos | 5,93 / 5,48 |
| `color.light.danger` | `#B3372E` | Errores y emergencia | 6,00 / 5,54 |

### Aseguradoras ficticias

Cada aseguradora tiene un acento para el modo claro, que también sirve de fondo
de su botón principal con texto blanco, y una variante para el modo oscuro, que
es fondo de su botón principal con la tinta `#0B0B12` (8,53, 10,78 y 9,06). Su
marca mínima es un monograma geométrico sencillo y el nombre escrito en IBM Plex
Sans, sin logotipos ilustrados.

| Aseguradora | Carácter | `accent` (modo claro) | Blanco sobre el acento | `accentOnDark` (modo oscuro) | Contraste sobre el fondo oscuro | Monograma |
| --- | --- | --- | --- | --- | --- | --- |
| Stonecroft Mutual | Conservadora, español por defecto | `#2C5F68` | 7,13 | `#7DB4BD` | 8,53 | Arco de piedra |
| Sunmeadow Auto | Flexible, inglés por defecto | `#3A6B2A` | 6,33 | `#A3CC86` | 10,78 | Horizonte con sol |
| Knotwell Insurance Agency | Agencia que coloca pólizas de las dos | `#6B3E8E` | 7,76 | `#C4A3E4` | 9,06 | Dos anillos enlazados |

El acento de una aseguradora solo marca su identidad (cabecera, botón
principal, foco y enlace activo). Los estados semánticos usan siempre los tokens
de éxito, aviso y error, para que un verde de Sunmeadow Auto nunca se lea como
"aprobado".

## Tipografía

Las tres familias de la landing, con licencia SIL Open Font License.

| Token | Familia | Uso |
| --- | --- | --- |
| `font.display` | Bricolage Grotesque, pesos 300 y 500 | Solo el título del inicio y las cifras grandes de los paneles |
| `font.body` | IBM Plex Sans, pesos 400 y 500 | Toda la interfaz: títulos de sección, botones, etiquetas, mensajes, cláusulas |
| `font.mono` | JetBrains Mono, peso 400 | Datos: identificadores, latencias, costos, horas, versiones, tokens de nodo |

Escala fija en rem, sin tamaños fluidos dentro de la interfaz, con razón de 1,2
entre pasos:

| Token | Tamaño | Alto de línea | Uso |
| --- | --- | --- | --- |
| `type.caption` | 0,75 rem (12 px) | 1,4 | Horas, notas de pie, datos secundarios en mono |
| `type.small` | 0,875 rem (14 px) | 1,45 | Etiquetas de campo, texto de tabla, ayudas |
| `type.body` | 1 rem (16 px) | 1,55 | Mensajes, cláusulas, texto corriente |
| `type.lead` | 1,2 rem (19,2 px) | 1,4 | Motivo de derivación, respuesta de comparación |
| `type.title` | 1,44 rem (23 px) | 1,25 | Título de pantalla y de sección |
| `type.figure` | 2,5 rem (40 px) | 1,1 | Cifras de los paneles, en `font.display` 300 |
| `type.display` | 3 rem (48 px) | 1,05 | Título del inicio, en `font.display` 300 |

Reglas: medida máxima de 70 caracteres en cláusulas y mensajes largos; cifras con
dígitos tabulares; tracking mínimo de -0,02 em en `type.display`; nunca
mayúsculas sostenidas para etiquetas.

## Espaciado, forma y profundidad

| Token | Valores |
| --- | --- |
| `space` | 4, 8, 12, 16, 24, 32, 48, 64 px |
| `radius.control` | 8 px: campos, selectores, etiquetas |
| `radius.surface` | 12 px: secciones, paneles, tarjetas de fuente, hoja inferior |
| `radius.bubble` | 16 px, con 4 px en la esquina que apunta al autor |
| `radius.pill` | 999 px: botones, como en la landing |
| `border.hairline` | 1 px |
| `border.focus` | Anillo de 2 px con separación de 2 px, en `accent` (oscuro) o acento de la aseguradora (claro) |
| `elevation.dark` | Por color de superficie; el panel de traza y la hoja inferior añaden `0 16px 40px rgba(0,0,0,.5)` |
| `elevation.light` | `0 1px 2px rgba(21,22,29,.06), 0 8px 24px rgba(21,22,29,.08)` para el compositor fijo y los menús |

Prohibidos por el sistema: bordes laterales de color de más de 1 px, sombras
duras sin desenfoque, vidrio o desenfoque decorativo y texto con degradado.

## Movimiento

| Token | Valor | Uso |
| --- | --- | --- |
| `motion.ease.out` | `cubic-bezier(0.23, 1, 0.32, 1)` | Entradas y cambios de estado |
| `motion.ease.inOut` | `cubic-bezier(0.77, 0, 0.175, 1)` | Movimientos dentro de la pantalla |
| `motion.ease.drawer` | `cubic-bezier(0.32, 0.72, 0, 1)` | Panel de traza y hoja inferior |
| `motion.duration.press` | 120 ms | Botón presionado, escala 0,97 |
| `motion.duration.state` | 160 ms | Encima, color, foco |
| `motion.duration.expand` | 200 ms | Cláusula y secciones plegables |
| `motion.duration.sheet` | 260 ms | Panel lateral y hoja inferior |
| `motion.duration.threadFill` | 240 ms | Nodo del hilo que se confirma |
| Cambio de modo | Inmediato, sin transición | Evitar el golpe visual de animar todos los colores |

Con movimiento reducido se quitan los desplazamientos y las escalas; quedan los
cambios de opacidad y de color de hasta 160 ms. Las acciones de teclado repetidas
(moverse por filas, cambiar de pestaña) no se animan. Las transiciones son de CSS
y se pueden interrumpir.

## Pantalla y capas

| Token | Valor |
| --- | --- |
| `breakpoint.phone` | Desde 360 px, una columna |
| `breakpoint.tablet` | 768 px |
| `breakpoint.desktop` | 1024 px |
| `breakpoint.wide` | 1280 px; el contenido no pasa de 1200 px |
| `width.conversation` | 720 px como máximo |
| `width.sheet` | 440 px en escritorio; en teléfono, hoja al 92 % del alto |
| `target.min` | 44 × 44 px para todo control táctil |
| `z.sticky` | 10: cabeceras y barras de control fijas |
| `z.notice` | 20: aviso fijo de demostración |
| `z.sheet` | 30: panel de traza y hoja inferior |
| `z.toast` | 40: avisos transitorios, que se usan poco |

## Íconos

Phosphor Icons, peso regular, licencia MIT (ya registrada en
`site/PHOSPHOR-LICENSE.txt`). Tamaños de 16, 20 y 24 px, del color del texto al
que acompañan. Un ícono nunca sustituye una etiqueta de texto en una acción, y
ningún carácter Unicode ni emoji hace de ícono.

## Inventario de componentes

Nombres genéricos que Domain Design mapea a la librería elegida. La
especificación de estados, teclado y anuncios de cada uno está en
`interaction-spec.md`.

| Componente | Categoría | Pantallas | Historias |
| --- | --- | --- | --- |
| `DemoNotice` | Retroalimentación | Chat, consola, comparación, vista por enlace | US1.1, US3.8 |
| `LanguageSelector` | Navegación | Todas las pantallas, con los nombres completos "Español" y "English" | US1.2, US3.1 |
| `ThemeToggle` | Navegación | Todas las pantallas, junto al selector de idioma | Decisión de Miguel en la revisión de esta etapa |
| `InsurerHeader` | Navegación | Chat, comparación | US1.1, US2.9 |
| `SamplePolicyCard` | Presentación | Inicio, chat, consola | US1.3, US4.17 |
| `MessageBubble` | Presentación | Chat | US1.5 a US1.19 |
| `DisclosureMessage` | Presentación | Chat | US1.1 |
| `ConfirmationReadback` | Entrada | Chat | US1.7, US1.8 |
| `SourceCard` | Presentación | Chat, comparación, vista de caso | US2.2, US2.3, US2.8, US3.2 |
| `TracePanel` | Presentación | Chat | US2.3 |
| `DecisionNotice` | Retroalimentación | Chat, consola | US1.18, US3.7 |
| `SystemNotice` | Retroalimentación | Chat, consola | US2.10, US5.13, US5.15 |
| `EmergencyNotice` | Retroalimentación | Chat, consola | US1.6 |
| `Composer` | Entrada | Chat, comparación | US1.2, US5.13 |
| `CaseClosureSummary` | Presentación | Chat, consola | US1.14, US1.17, US3.7 |
| `CallAvailability` | Retroalimentación | Consola | US4.17, US5.12, US5.14 |
| `CallControlBar` | Entrada | Consola | US1.21, US4.17 |
| `TranscriptLine` | Presentación | Consola, vista de caso | US4.17, US3.2 |
| `PiiTag` | Presentación | Consola, vista de caso, traza | US4.12 |
| `AgentStateIndicator` | Retroalimentación | Consola | US4.17, US1.25 |
| `LatencyReadout` | Presentación | Consola, traza, paneles | US4.17, US4.16 |
| `CaseThread` | Presentación | Consola, bandeja, vista de caso, traza | US4.17, US1.7, US4.8 |
| `ComparisonColumn` | Presentación | Comparación | US2.9 |
| `FilterBar` | Entrada | Bandeja | US3.1 |
| `CaseTable` | Presentación | Bandeja | US3.1, US3.5 |
| `CaseHeader` | Navegación | Vista de caso | US3.2, US3.4 |
| `DecisionForm` | Entrada | Vista de caso | US3.4, US3.6, US6.3 |
| `EvidenceSection` | Presentación | Vista de caso | US3.2 |
| `FieldCorrection` | Entrada | Vista de caso | US3.3 |
| `LinkOrientation` | Retroalimentación | Vista por enlace | US3.8, US1.17 |
| `MetricFigure` | Presentación | Panel de cifras | US4.16 |
| `SpendCeiling` | Presentación | Panel de gasto | US5.14 |
| `StatusPage` | Retroalimentación | Páginas de estado | US5.16, US3.8, US2.10 |
| `Button`, `Input`, `Textarea`, `Select`, `Tag`, `Disclosure`, `Tabs`, `Skeleton`, `InlineAlert` | Primitivas | Todas | US1.33 |

## Reglas contra el diseño genérico

Tomadas de las skills de diseño instaladas (`frontend-design`, `impeccable`,
`emil-design-eng`) y aplicadas como reglas de revisión de cada pantalla:

- Ninguna etiqueta en mayúsculas sobre un título. El título dice lo que es.
- Ninguna numeración 01, 02, 03 salvo que el contenido sea una secuencia real,
  como los pasos del hilo del caso.
- Ninguna rejilla de tarjetas idénticas como estructura de pantalla. Las
  aseguradoras del inicio son filas con información distinta, no tres tarjetas
  iguales.
- Ninguna cifra grande con etiqueta pequeña y acento como plantilla: las cifras
  del panel llevan su fecha, su commit y su método.
- Ninguna cadena de metadatos unida con puntos medios ni flechas añadidas al
  texto de enlaces y botones.
- Ninguna coreografía de entrada por sección ni al cargar.
- Ningún modal para lo que se puede resolver en línea: la decisión del ajustador
  se escribe debajo del encabezado del caso, sin tapar la evidencia.
- La monoespaciada solo acompaña datos reales.

## Criterios para elegir la librería en Domain Design

- Primitivas accesibles sin estilo impuesto: diálogo, hoja lateral, plegable,
  pestañas, selector, región de anuncios.
- Tokens como variables de CSS con dos temas y sobrescritura por aseguradora
  desde su configuración, sin condiciones por aseguradora en el código
  (`project.md`).
- Ningún componente se entrega con su aspecto por defecto.
- Licencia compatible con publicar el repositorio y registro de la atribución.
- Peso inicial que no comprometa la página de espera de menos de 3 segundos
  (US5.16).

## Licencias de recursos

| Recurso | Licencia | Dónde se registra |
| --- | --- | --- |
| Bricolage Grotesque | SIL Open Font License 1.1 | Registro de licencias del aplicativo |
| IBM Plex Sans | SIL Open Font License 1.1 | Registro de licencias del aplicativo |
| JetBrains Mono | SIL Open Font License 1.1 | Registro de licencias del aplicativo |
| Phosphor Icons | MIT | `site/PHOSPHOR-LICENSE.txt` y registro del aplicativo |
