# Lista de accesibilidad — Untangle

Línea base de accesibilidad de las pantallas de `mockups.md`, inspirada en WCAG
2.1 AA y comprobada por herramientas. Nunca se presenta como cumplimiento de una
norma. Sale de la respuesta Q9 y de las decisiones D16 y D25 de
`../user-stories/stories.md` (historias US1.33 y US4.2), de los requisitos de
`../requirements-analysis/requirements.md` y de la práctica de
`../practices-discovery/team-practices.md` que exige que toda convención sea
comprobable por una herramienta. No hay `wireframes.md` ni `user-flow.md` previos
(scope `classic`).

## Alcance

| Pantalla | Línea base | Cómo entra |
| --- | --- | --- |
| Chat de cada aseguradora (M2) | Sí | US1.33, D25 |
| Consola de llamada (M4) | Sí | US1.33, D25 |
| Vista de comparación (M5) | Sí | US1.33, D25 |
| Vista de caso por enlace (M8) | Sí | US1.33, D25 |
| Inicio de la demo (M1) | Sí, por diseño | Pantalla pública nueva de la respuesta Q1; se aplica el criterio de D25 ("pantallas a las que llega un visitante") |
| Resumen de la traza (M3) | Sí, por diseño | Se abre desde el chat público |
| Panel de cifras (M9) y panel de gasto (M10) | Sí, por diseño | Públicos por la respuesta Q7 |
| Páginas de estado (M11) | Sí, por diseño | Las ve cualquier visitante |
| Bandeja y vista de caso con credencial (M6, M7) | Fuera de la línea base (D25) | Comparten componentes y tokens con M8, así que heredan contraste, teclado y anuncios |

Las pantallas marcadas "por diseño" cumplen esta lista en las maquetas, pero la
verificación automática de AC1.33.1 nombra solo las cuatro primeras. Queda
anotado al final para que `nfr-requirements` y `build-and-test` las sumen al
comando.

## 1. Contraste

Medido sobre los tokens de `design-system-mapping.md`, en los dos modos: cada
pantalla existe en claro y en oscuro. Texto normal 4,5:1; texto grande, bordes de
control y gráficos necesarios, 3:1.

| Par | Tema | Contraste | Requisito | Resultado |
| --- | --- | --- | --- | --- |
| Texto principal sobre fondo | Oscuro | 16,67 | 4,5 | Cumple |
| Texto secundario sobre fondo | Oscuro | 8,28 | 4,5 | Cumple |
| Texto terciario sobre superficie | Oscuro | 5,38 | 4,5 | Cumple |
| Cobre sobre fondo (acciones, foco) | Oscuro | 7,19 | 4,5 | Cumple |
| Texto sobre botón cobre | Oscuro | 7,15 | 4,5 | Cumple |
| Índigo de enlaces sobre fondo | Oscuro | 8,43 | 4,5 | Cumple |
| Índigo gráfico (solo gráficos grandes) | Oscuro | 3,48 | 3 | Cumple como gráfico; prohibido como texto |
| Borde de control sobre superficie | Oscuro | 3,31 | 3 | Cumple |
| Éxito, aviso y error sobre superficie | Oscuro | 8,98, 10,66 y 7,72 | 4,5 | Cumple |
| Texto sobre fondo de página | Claro | 16,68 | 4,5 | Cumple |
| Texto secundario sobre fondo de página | Claro | 6,59 | 4,5 | Cumple |
| Enlace índigo sobre blanco | Claro | 5,63 | 4,5 | Cumple |
| Borde de control sobre fondo de página | Claro | 3,66 | 3 | Cumple |
| Blanco sobre acento de Stonecroft Mutual, Sunmeadow Auto y Knotwell | Claro | 7,13, 6,33 y 7,76 | 4,5 | Cumple |
| Acentos oscuros de las aseguradoras sobre fondo | Oscuro | 8,53, 10,78 y 9,06 | 4,5 | Cumple |
| Tinta de marca `#9A4F12` sobre blanco y sobre el fondo de página (texto, foco, selección) | Claro | 6,00 y 5,55 | 4,5 | Cumple |
| Blanco sobre el botón principal de Untangle `#9A4F12` | Claro | 6,00 | 4,5 | Cumple |
| Texto terciario `#5F6573` sobre blanco y sobre el fondo de página | Claro | 5,84 y 5,40 | 4,5 | Cumple |
| Línea del hilo `#B8753A` sobre blanco y sobre el fondo de página | Claro | 3,72 y 3,40 | 3 | Cumple como gráfico |
| Tinta `#0B0B12` sobre el botón de cada aseguradora en oscuro | Oscuro | 8,53, 10,78 y 9,06 | 4,5 | Cumple |
| Cobre sobre blanco | Claro | 2,73 | 4,5 | No cumple: el cobre no se usa como texto en el modo claro; la marca usa `#9A4F12` |

- [ ] Ningún estado, prioridad, resultado de control ni hablante se comunica solo
      con color: siempre hay texto o un ícono con etiqueta (AC1.33.6).
- [ ] El foco visible es un anillo de 2 px con separación, 3:1 o más contra lo que
      lo rodea, en todos los controles.
- [ ] El selector de tema está en todas las pantallas, con texto "Claro" y
      "Oscuro", `aria-pressed` y sin transición animada al cambiar.
- [ ] Cambiar de pantalla nunca cambia el modo, y el modo se aplica antes de
      pintar la página, sin parpadeo del modo contrario.
- [ ] Las pantallas de visitante no usan jerga del sistema sin explicarla en
      palabras simples (`interaction-spec.md`, "Uso sin contexto").

## 2. Teclado y foco

| Criterio | Pantallas | Historia | Verificación |
| --- | --- | --- | --- |
| Todo se hace con teclado: reportar por chat, expandir una cláusula, llamar, colgar, decidir por enlace | M2, M3, M4, M8 | AC1.33.3 | Recorrido automatizado de extremo a extremo solo con teclado |
| Orden de foco lógico, igual al visual | Todas | AC1.33.3 | Recorrido automatizado y revisión de la tabla de foco de `interaction-spec.md` |
| Sin trampas de foco; la hoja inferior del teléfono se cierra con Escape | M3 | AC1.33.3 | Prueba de teclado |
| Enlace "Saltar al contenido" como primer elemento enfocable | M1, M2, M4, M5, M9, M10 | Buena práctica de la línea base | Analizador automático |
| El foco vuelve al disparador al cerrar el panel de traza o cancelar una decisión | M3, M7, M8 | AC1.33.3 | Prueba de componente |
| Las acciones de teclado repetidas no se animan | Todas | Regla de movimiento | Revisión de estilos |

## 3. Lectores de pantalla y anuncios

| Criterio | Pantallas | Historia | Verificación |
| --- | --- | --- | --- |
| La respuesta de la agente se anuncia una sola vez, completa, al terminar | M2, M5 | AC1.33.4 | Prueba con lector de pantalla por hito |
| Los estados ("revisando la póliza"), los límites y los errores se anuncian como mensajes de estado | M2, M4 | AC1.33.4 | Prueba de componente y lector de pantalla |
| La cuenta regresiva se anuncia solo a los 60 y a los 30 segundos | M4 | AC1.33.4 | Prueba de componente con reloj inyectado |
| La emergencia se anuncia como alerta, de inmediato | M2, M4 | AC1.6.1 | Prueba de componente |
| Cada mensaje de la conversación es un artículo con su autor; la lista es un registro | M2 | AC1.33.4 | Analizador automático y revisión |
| Los datos personales se leen como "teléfono redactado", no como corchetes | M4, M3 | D20 | Prueba de componente |
| Encabezados en orden, un solo título por pantalla, regiones con nombre | Todas | AC1.33.1 | Analizador automático |
| El hilo decorativo de "despertando" está oculto para lectores y el estado se lee en el título | M11 | AC1.33.6 | Revisión |

## 4. Idioma de cada texto

- [ ] La página declara su idioma y cambia al usar el selector (AC1.2.2).
- [ ] Cada mensaje, cláusula y bloque declara el suyo, también un caso en español
      dentro de la bandeja en inglés (AC1.33.5).
- [ ] La cláusula en su idioma original lleva la etiqueta del idioma y la
      explicación marcada como resumen (AC2.3.4).
- [ ] Cada columna de la comparación declara el idioma de su respuesta.

## 5. Teléfono, zoom y objetivos táctiles

| Criterio | Pantallas | Historia | Verificación |
| --- | --- | --- | --- |
| Sin desplazamiento horizontal en 360 × 640 px | M1 a M5, M8 a M11 | AC1.33.2 | Prueba visual automatizada a 360 px |
| El compositor y "Enviar" siguen visibles con el teclado del teléfono abierto | M2, M5 | AC1.33.2 | Prueba en navegador móvil emulado y en un teléfono real por hito |
| Llamar, colgar, enviar, expandir una cláusula, aprobar y rechazar miden 44 × 44 px o más | M2, M4, M5, M8 | AC1.33.2 | Medición automatizada de los controles |
| A 200 % de zoom no se pierde contenido | Todas las de la línea base | AC1.33.6 | Prueba visual a 200 % |
| La tabla ancha de la bandeja se desplaza dentro de su contenedor, no la página | M6 | Por diseño | Revisión |

## 6. Movimiento

- [ ] Con movimiento reducido no hay desplazamientos ni escalas; quedan cambios de
      opacidad y color de hasta 160 ms (AC1.33.6).
- [ ] Las animaciones de la voz (pulso de "Pensando") se detienen con movimiento
      reducido.
- [ ] Nada parpadea más de tres veces por segundo.
- [ ] No hay animaciones al cargar las pantallas del aplicativo.

## 7. Formularios, errores y confirmaciones

| Criterio | Pantallas | Historia | Verificación |
| --- | --- | --- | --- |
| Cada campo tiene etiqueta visible; nunca solo marcador de posición | M2, M5, M6, M7, M8 | Buena práctica de la línea base | Analizador automático |
| El comentario obligatorio se marca antes de escribir y su error dice qué hacer | M7, M8 | AC3.4.1 | Prueba de componente |
| El error de una corrección nombra el campo y el formato esperado, y conserva el valor anterior | M7 | AC3.3.3 | Prueba de componente |
| Los errores se asocian a su campo y se anuncian; el foco vuelve al campo | M7, M8 | AC1.33.4 | Prueba de componente |
| Si el enlace vence durante la decisión, el comentario escrito no se pierde | M8 | AC3.8.3 | Prueba con reloj inyectado |

## 8. Tiempo

- [ ] La llamada pública tiene un límite de tiempo real de tres minutos, propio de
      una conversación en vivo: se muestra antes de llamar, se ve durante la
      llamada y se avisa a los 30 segundos (US5.12, AC4.17.1).
- [ ] El enlace firmado muestra su hora de vencimiento en hora local desde que se
      abre (AC3.8.1).
- [ ] La página de espera no exige ninguna acción: se actualiza sola y dice qué
      hacer si no despierta (AC5.16.4).

## 9. Medios

- [ ] El video tiene subtítulos sincronizados en inglés y en español, incluido el
      segmento hablado en español (AC4.2.5).
- [ ] El README enlaza la transcripción del video en texto (AC4.2.5).
- [ ] La consola no reproduce audio sin una acción de la persona: la llamada
      empieza al pulsar "Llamar".

## 10. Contenido no textual

- [ ] Los íconos que acompañan texto son decorativos; un botón de solo ícono (como
      cerrar el panel) tiene nombre accesible.
- [ ] El monograma de cada aseguradora lleva el nombre de la aseguradora como
      texto visible al lado.
- [ ] El hilo del caso comunica su estado en texto ("confirmado", "pendiente"),
      no solo con el relleno.
- [ ] Las cifras de los paneles se leen con su unidad, su idioma y su fecha.

## 11. Cómo se verifica

| Verificación | Herramienta | Cuándo | Historia |
| --- | --- | --- | --- |
| Analizador automático de accesibilidad sin hallazgos serios ni críticos, en español y en inglés | Analizador de reglas de accesibilidad dentro del guion de verificación | Cada entrega | AC1.33.1 |
| Recorrido solo con teclado | Prueba automatizada de extremo a extremo | Cada entrega | AC1.33.3 |
| 360 px y 200 % de zoom | Prueba visual automatizada | Cada entrega | AC1.33.2, AC1.33.6 |
| Anuncios del lector de pantalla | Revisión manual con VoiceOver y NVDA, registrada con fecha y commit | Por hito | AC1.33.4 |
| Contraste de tokens | Cálculo automatizado sobre el archivo de tokens | Cada cambio de tokens | AC1.33.6 |
| Subtítulos del video | Revisión humana registrada | Al publicar el video | AC4.2.5 |

La herramienta concreta la fija la decisión de arquitectura de la interfaz; el
comando queda en el archivo de tareas y lo invoca el guion único de verificación
(`team.md`).

## 12. Pendientes para etapas siguientes

- Las pantallas públicas nuevas (inicio, resumen de la traza, panel de cifras,
  panel de gasto y páginas de estado) deben sumarse a la verificación automática
  de AC1.33.1, que hoy nombra solo cuatro pantallas. Lo registran
  `nfr-requirements` y `build-and-test`.
- El protocolo de la revisión manual con lector de pantalla (qué recorridos, con
  qué lectores y en qué navegadores) se escribe en `build-and-test`, junto con la
  lista de navegadores declarados (PA-4 de User Stories).
