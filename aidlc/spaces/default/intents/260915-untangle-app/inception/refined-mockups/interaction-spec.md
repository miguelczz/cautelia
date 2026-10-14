# Especificación de interacción — Untangle

Cómo se comporta cada pantalla de `mockups.md`: los recorridos por perfil, los
estados y el teclado de cada componente, lo que se anuncia a un lector de
pantalla y el movimiento. Parte de las historias de
`../user-stories/stories.md`, de los requisitos de
`../requirements-analysis/requirements.md` y de las prácticas de
`../practices-discovery/team-practices.md`. No hay `wireframes.md` ni
`user-flow.md` previos (scope `classic`). Los componentes siguen la plantilla de
especificación del diseñador y los tokens de `design-system-mapping.md`.

## Uso sin contexto

Miguel pidió en la revisión de esta etapa que el aplicativo se pueda usar sin
ningún contexto: alguien que llega desde LinkedIn o desde el README, sin saber
qué es un siniestro, una traza o una bandeja, tiene que saber qué hacer en cada
pantalla y no poder equivocarse de forma cara. Se recorrieron las doce pantallas
con esa mirada. Cada fila dice qué confundía y qué cambió; los documentos y la
maqueta ya reflejan el cambio.

| ID | Pantalla | Qué confundía | Corrección |
| --- | --- | --- | --- |
| U-01 | M1 | Tres filas con dos botones cada una y cuatro enlaces más, sin decir por dónde empezar | "Cómo funciona" en tres pasos reales (cuenta lo que pasó, recibe el enlace, decide tu caso) y "Si es tu primera vez, empieza por el chat" |
| U-02 | M1, M2, M4 | Los datos de la póliza de ejemplo aparecen sin decir para qué | "Cuando Valentina te pida la póliza, usa estos datos" junto a cada póliza |
| U-03 | M1 | "Cifras", "Gasto" y "README" son jerga de proyecto | "Resultados medidos", "Costo de la demo" y "Cómo está hecho" |
| U-04 | Todas | "ES" y "EN" obligan a adivinar | Selector con los nombres completos "Español" y "English" |
| U-05 | M2 | Conversación nueva con el campo vacío: no se sabe qué escribir | Tres sugerencias tocables bajo el primer mensaje: reportar un choque, preguntar por el carro de alquiler y pedir una persona. Desaparecen tras el primer mensaje |
| U-06 | M2 | Desde el chat no hay forma de volver al inicio de la demo | Enlace "Inicio de la demo" en la cabecera |
| U-07 | M2, M4 | "Revisar mi caso en la bandeja": "bandeja" no significa nada para quien reporta | "Ver y decidir mi caso", el mismo nombre en el chat, la consola y la vista por enlace |
| U-08 | M3 | El panel no dice qué muestra antes de listar nodos | Una frase inicial: "Los pasos que siguió el sistema para responder, con el tiempo y el costo de cada uno" |
| U-09 | M4 | "Divulgación registrada", "De fondo" y "Del fin del habla al primer audio" son términos del sistema | "Valentina ya dijo que es una IA", "Trabajando en segundo plano" y "Tiempo de respuesta del último turno" |
| U-10 | M4 | Antes de llamar no queda claro qué decir | "Ideas para la llamada" con la póliza que hay que dictar |
| U-11 | M4 | "Colgar" termina de inmediato la única llamada del día | Se mantiene inmediato, porque detener una llamada nunca debe pedir confirmación, y la consola avisa antes de llamar que al colgar el caso queda guardado con su enlace |
| U-12 | M5 | "Cada pregunta cuenta como tres respuestas en los límites de la demo" | "Cada pregunta usa tres de tus respuestas disponibles hoy" |
| U-13 | M6, M7 | "Completitud" y "Categoría: derivación" | "Datos completos: 3 de 7" y "Motivo" |
| U-14 | M8 | Quien abre el enlace no sabe qué se espera de él | Orientación con tres pasos: revisa lo que Valentina registró, elige Aprobar o Rechazar, escribe el mensaje que verás con la decisión |
| U-15 | M7, M8 | "Regla que decidió", "Controles" y "Traza" no dicen qué contienen | "Regla que envió el caso a revisión", "Controles de cumplimiento" y "Pasos del sistema", cada uno con su resumen de una línea |
| U-16 | M8 | "Comentario para el asegurado" cuando el visitante es el asegurado | "Mensaje con la decisión (obligatorio)" y la ayuda "Lo verás en tu conversación junto a la decisión" |
| U-17 | M9 | "p50" y "p95" son estadística | "La mitad, en 1,1 s o menos" y "95 de cada 100, en 2,4 s o menos" |
| U-18 | M9 | "Completitud del primer aviso" y "Precisión de citación" | "Reportes con todos los datos" y "Citas correctas a la póliza", cada una con una frase que explica qué se midió |
| U-19 | M10 | "Modelo por minuto de llamada" | "Costo del modelo de lenguaje por minuto de llamada" |
| U-20 | Todas | El cambio brusco de oscuro a claro al pasar del inicio al chat cansa la vista | Modos claro y oscuro completos con selector de tema en todas las pantallas (ver `design-system-mapping.md`) |

Lo que ya prevenía errores y se conserva: la decisión exige un comentario y se
confirma en un segundo paso, el compositor dice por qué está deshabilitado, el
enlace muestra su hora de vencimiento desde que se abre y la voz no disponible
explica el motivo antes de pedir el micrófono.

## Recorridos

### F1 — Reportar un siniestro por chat

```text
Flujo: reportar un choque por chat
Perfil: Camilo, asegurado de Stonecroft Mutual, en español
Disparador: abre el chat desde el inicio de la demo
Pasos:
  1. Chat cargado -> lee la divulgación -> el compositor queda activo
  2. Compositor -> escribe "choqué en la autopista" -> la agente pregunta si todos están bien y seguros
  3. Conversación -> responde que sí -> la agente pide identidad y póliza
  4. Conversación -> da la póliza de ejemplo -> la agente la muestra agrupada y sigue con qué pasó
  5. Lectura de confirmación -> pulsa "Sí, es correcto" o escribe "sí" -> el bloque queda confirmado
  6. Resto de bloques -> responde una idea por turno -> la agente confirma cada bloque
  7. Cierre -> lee el resumen, el número de caso y qué sigue -> pulsa "Ver y decidir mi caso" si quedó derivado
Resultado: caso SMU-482913 derivado o cerrado, con enlace firmado de una hora
Caminos de error:
  - Heridos graves -> bloque de emergencia en ese mismo turno -> la agente ofrece seguir después
  - Pide una persona -> derivación en el turno siguiente -> el caso queda con prioridad alta
  - Cierra la pestaña -> caso en "esperando al asegurado" -> al volver desde el mismo navegador, "Veo que tiene un caso abierto. ¿Seguimos con ese?"
  - El modelo no responde -> un reintento y el mensaje de degradación -> el texto escrito sigue en el compositor
```

### F2 — Preguntar por cobertura y ver la evidencia

```text
Flujo: pregunta de cobertura con cita
Perfil: Ana, asegurada de Sunmeadow Auto, en inglés; Jordan al revisar la evidencia
Disparador: pregunta si le pagan un carro de alquiler
Pasos:
  1. Compositor -> envía la pregunta -> "Valentina está escribiendo"
  2. Respuesta -> lee la respuesta y la tarjeta de fuente -> ve identificador, versión y vigencia
  3. Tarjeta de fuente -> pulsa "Ver cláusula" -> el texto completo se expande dentro del mensaje
  4. Tarjeta de fuente -> pulsa "Cómo se llegó a esta respuesta" -> se abre el panel oscuro de la traza
  5. Panel de traza -> lee la ruta, las cláusulas y el costo -> cierra con Escape o con el botón
Resultado: la persona entiende qué cláusula respalda la respuesta; Jordan comprueba cómo se obtuvo
Caminos de error:
  - Sin cláusula -> "I can't find a clause in your policy about that, so I won't guess. I'll flag it for the adjuster." -> sin tarjeta de fuente
  - Verificación caída -> "No puedo revisar su póliza en este momento; le paso el caso a un ajustador." -> caso derivado
  - Traza aún sin registrar -> "La traza se está registrando" -> el panel se actualiza solo
```

### F3 — Probar la voz pública de principio a fin

```text
Flujo: llamada pública
Perfil: Jordan, jugando a ser Ana
Disparador: pulsa "Llamar" en el inicio o en la consola
Pasos:
  1. Consola antes de llamar -> lee disponibilidad, límites y qué probar -> pulsa "Llamar"
  2. Permiso del micrófono -> lo concede -> "Conectando la llamada"
  3. Llamada -> oye la apertura -> la consola marca "Valentina ya dijo que es una IA"
  4. Llamada -> reporta y la interrumpe -> la agente se calla y la transcripción lo refleja
  5. "Qué está pasando" -> ve el estado, la latencia del turno y los bloques confirmados
  6. Aviso de 30 segundos -> termina la llamada o llega al límite -> final de llamada con el caso
  7. Final -> pulsa "Ver y decidir mi caso" o "Pasar mi caso a un ajustador ahora"
Resultado: caso con enlace firmado, o 15 minutos para retomar
Caminos de error:
  - Micrófono denegado -> cómo dar el permiso y enlace al chat -> no se abre un caso vacío
  - Ya usó su llamada del día -> rechazo con la causa antes de pedir el micrófono -> enlace al chat
  - Techo de gasto -> "La demostración de voz llegó a su presupuesto y no está recibiendo llamadas. El chat sigue disponible." -> enlace al chat
  - Corte -> final con 15 minutos para volver -> botón para pasar a un ajustador
```

### F4 — Decidir el propio caso con el enlace

```text
Flujo: decisión por enlace firmado
Perfil: Jordan
Disparador: pulsa el enlace al cerrar el chat o la llamada
Pasos:
  1. Vista por enlace -> lee la orientación y la hora de vencimiento -> revisa la evidencia
  2. Encabezado -> pulsa "Aprobar" -> se abre el formulario en línea
  3. Formulario -> escribe el comentario y confirma -> "Listo: el caso se reanudó y quedó aprobado."
  4. Después de decidir -> pulsa "Volver a la conversación" -> ve el aviso de la decisión en el chat o la consola
Resultado: la decisión queda en el historial como "Visitante con enlace de demostración"
Caminos de error:
  - Sin comentario -> error bajo el campo -> la decisión elegida se conserva
  - Vence mientras escribe -> la decisión no se aplica -> el comentario queda para copiarlo
  - Enlace vencido o no válido -> página de estado -> cómo pedir otro
```

### F5 — Decidir un caso en la bandeja

```text
Flujo: decisión con credencial
Perfil: Diana, ajustadora de Stonecroft Mutual
Disparador: entra a la bandeja
Pasos:
  1. Lista -> filtra por idioma español y prioridad alta -> ve los casos ordenados
  2. Fila -> abre el caso -> encabezado con motivo, categoría y completitud
  3. Secciones -> revisa campos, transcripción, cláusula, regla y controles
  4. Campo mal capturado -> pulsa "Corregir", escribe y guarda -> el historial registra el cambio
  5. Encabezado -> "Aprobar" con comentario -> el caso pasa a cerrado con resolución aprobado
Resultado: el asegurado ve la decisión en su canal
Caminos de error:
  - Otra persona decidió antes -> aviso con la decisión existente -> la acción no se aplica
  - Caso esperando al asegurado -> sin acciones, con los campos que faltan
  - Valor inválido en la corrección -> error del catálogo que nombra el formato -> el valor anterior se conserva
```

### F6 — Marcar un caso como enviado a la aseguradora

```text
Flujo: acción de la agencia
Perfil: Priya Raman, agente de cuenta de Knotwell
Disparador: abre un caso de la bandeja de Knotwell
Pasos:
  1. Vista de caso -> ve la aseguradora emisora y sus cláusulas -> la única acción es "Marcar como enviado a la aseguradora"
  2. Formulario -> escribe el comentario y confirma -> el caso queda cerrado con resolución enviado a la aseguradora
Resultado: el asegurado ve que su caso se envió a la emisora, sin promesa de contacto
Caminos de error:
  - Sin comentario -> error bajo el campo
```

### F7 — Comparar las tres aseguradoras

```text
Flujo: comparación
Perfil: Jordan
Disparador: "Comparar las tres respuestas" en el inicio
Pasos:
  1. Comparación -> elige una pregunta sugerida o escribe la suya -> tres columnas con carga propia
  2. Columnas -> cada respuesta aparece cuando está lista -> con sus cláusulas o "no encuentro una cláusula"
  3. Columna -> "Ver cláusula" -> se expande en la columna
Resultado: tres respuestas distintas, cada diferencia explicada por su cláusula
Caminos de error:
  - Una aseguradora falla -> esa columna dice que no pudo revisar la póliza -> "Intentar de nuevo"
  - Escribe un reporte de siniestro -> la vista explica que compara coberturas -> enlaza el chat de cada aseguradora
```

### F8 — Llegar a un límite o a una falla

```text
Flujo: degradación honesta
Perfil: cualquier visitante
Disparador: un límite de la demo o una falla de un proveedor
Pasos:
  1. Chat -> supera el límite de mensajes -> compositor deshabilitado con cuándo puede seguir
  2. Consola -> el sitio llegó a sus llamadas del día -> rechazo antes del micrófono con enlace al chat
  3. Llamada -> se agota el presupuesto de la voz principal -> la llamada siguiente usa la voz de respaldo y la consola lo avisa
  4. Base de datos caída -> página "Servicio no disponible" sin detalles técnicos
Resultado: nadie ve un error genérico ni pierde lo que ya contó
```

### F9 — Retomar por chat un caso empezado por voz

```text
Flujo: retomar por chat (Should S2)
Perfil: Ana, que colgó a mitad del reporte y ya no puede hablar
Disparador: abre el chat de Sunmeadow Auto desde el mismo navegador
Pasos:
  1. Chat -> escribe el número de caso SMA-731045 -> la agente pide la póliza
  2. Conversación -> da la póliza de ejemplo -> la agente retoma y pide solo lo que falta
  3. Conversación -> cada turno anterior aparece con la marca "por voz" y los nuevos con "por chat"
Resultado: un único caso con los dos canales en orden
Caminos de error:
  - Número de un caso creado desde otro navegador -> la misma respuesta que ante un número que no existe
  - Número de otra aseguradora -> la misma respuesta que ante un número que no existe
```

## Componentes

### DemoNotice

| Campo | Valor |
| --- | --- |
| Componente | `DemoNotice` |
| Descripción | Aviso fijo de que es una demostración con pólizas de ejemplo y sin personas en vivo |
| Categoría | Retroalimentación |

| Estado | Descripción | Disparador |
| --- | --- | --- |
| Por defecto | Una línea bajo la cabecera | Carga de la página |
| Compacto | Una línea corta con "Más información" | Desplazamiento en teléfono |
| Expandido | El texto completo | "Más información" |

| Prop | Tipo | Requerido | Por defecto | Descripción |
| --- | --- | --- | --- | --- |
| `messageKey` | string | sí | — | Clave del catálogo del aviso |
| `theme` | `light` o `dark` | sí | — | Tema de la superficie |

| Pantalla | Comportamiento |
| --- | --- |
| Teléfono | Pasa a compacto al desplazarse; nunca desaparece |
| Tableta y escritorio | Línea completa fija bajo la cabecera |

| Requisito | Implementación |
| --- | --- |
| Rol | `region` con nombre "Aviso de demostración" |
| Teclado | "Más información" es un botón alcanzable con Tab |
| Contraste | Texto secundario del tema, 4,5:1 o más |
| Lector de pantalla | Se lee en el orden natural tras la cabecera; no es región en vivo |

```text
<DemoNotice messageKey="demo.notice.chat" theme="light" />
```

### LanguageSelector

| Campo | Valor |
| --- | --- |
| Componente | `LanguageSelector` |
| Descripción | Cambia el idioma de la página y de la agente; muestra el idioma en que responde la agente |
| Categoría | Navegación |

| Estado | Descripción | Disparador |
| --- | --- | --- |
| Por defecto | Idioma actual visible | Carga |
| Foco | Anillo de foco | Tab |
| Abierto | Lista de dos idiomas | Enter, Espacio o clic |
| Sincronizado | Cambia solo cuando la agente cambia de idioma | Mensaje en otro idioma |

| Prop | Tipo | Requerido | Por defecto | Descripción |
| --- | --- | --- | --- | --- |
| `value` | `es` o `en` | sí | Idioma por defecto de la superficie | Idioma actual |
| `persist` | boolean | no | false | Recordar la elección (bandeja) |

| Pantalla | Comportamiento |
| --- | --- |
| Teléfono | Botón compacto con el código del idioma |
| Escritorio | Segmento con los dos idiomas visibles |

| Requisito | Implementación |
| --- | --- |
| Rol | Grupo de botones de alternancia con `aria-pressed`, o selector nativo |
| Teclado | Tab para entrar; flechas entre opciones; Enter para elegir |
| Etiqueta | "Idioma" visible o como nombre accesible |
| Lector de pantalla | Anuncia "Idioma: español" al cambiar, una vez |
| Foco | Se queda en el selector tras cambiar |

```text
<LanguageSelector value="es" persist={false} />
```

### ThemeToggle

| Campo | Valor |
| --- | --- |
| Componente | `ThemeToggle` |
| Descripción | Selector de modo claro u oscuro, en la barra superior de todas las pantallas |
| Categoría | Navegación |

| Estado | Descripción | Disparador |
| --- | --- | --- |
| Del dispositivo | Primera visita: sigue la preferencia del sistema | Carga sin elección guardada |
| Claro | Todas las pantallas en modo claro | Elección de la persona |
| Oscuro | Todas las pantallas en modo oscuro | Elección de la persona |

| Requisito | Implementación |
| --- | --- |
| Rol | Grupo de dos botones con `aria-pressed`, con texto "Claro" y "Oscuro" e ícono decorativo |
| Persistencia | La elección se guarda en el navegador y se aplica antes de pintar la página |
| Movimiento | Sin transición: el cambio es inmediato |
| Foco | Se queda en el botón pulsado |

```text
<ThemeToggle value="dark" />
```

### MessageBubble

| Campo | Valor |
| --- | --- |
| Componente | `MessageBubble` |
| Descripción | Mensaje de la agente, de la persona o del sistema en el chat |
| Categoría | Presentación |

| Estado | Descripción | Disparador |
| --- | --- | --- |
| Transmitiendo | El texto crece palabra a palabra | Respuesta en curso |
| Completo | Texto final con hora | Fin de la respuesta |
| Error | Mensaje de degradación del catálogo | Falla del proveedor |
| Pendiente de envío | Mensaje de la persona atenuado hasta confirmar | Envío en curso |
| No enviado | Texto de error y "Reintentar" | Falla de red |

| Prop | Tipo | Requerido | Por defecto | Descripción |
| --- | --- | --- | --- | --- |
| `author` | `agent`, `person` o `system` | sí | — | Quién habla |
| `lang` | `es` o `en` | sí | — | Idioma del mensaje, se declara en el elemento |
| `streaming` | boolean | no | false | Si la respuesta sigue llegando |
| `attachments` | lista | no | — | Tarjetas de fuente, lectura de confirmación, cierre |

| Pantalla | Comportamiento |
| --- | --- |
| Teléfono | Hasta el 88 % del ancho |
| Escritorio | Hasta 62 caracteres de medida dentro de una conversación de 720 px |

| Requisito | Implementación |
| --- | --- |
| Rol | Lista de mensajes con `role="log"`; cada mensaje es un `article` con el autor como nombre |
| Lector de pantalla | El mensaje se anuncia completo una sola vez al terminar de transmitirse |
| Idioma | Atributo `lang` por mensaje (AC1.33.5) |
| Contraste | Texto principal del tema sobre la burbuja, 4,5:1 o más |

```text
<MessageBubble author="agent" lang="es" streaming attachments={[sourceCard]} />
```

### ConfirmationReadback

| Campo | Valor |
| --- | --- |
| Componente | `ConfirmationReadback` |
| Descripción | Lectura de lo anotado al cerrar un bloque, con respuestas rápidas |
| Categoría | Entrada |

| Estado | Descripción | Disparador |
| --- | --- | --- |
| Esperando | "Anotado: ... ¿Correcto?" con "Sí, es correcto" y "Corregir" | Cierre de bloque |
| Confirmado | Las respuestas rápidas desaparecen; el mensaje de la persona queda en el registro | Sí |
| Corrigiendo | La agente pregunta qué corregir | Corregir |

| Prop | Tipo | Requerido | Por defecto | Descripción |
| --- | --- | --- | --- | --- |
| `blockKey` | string | sí | — | Bloque del caso que se confirma |
| `readbackText` | string | sí | — | Texto que leyó la agente |

| Pantalla | Comportamiento |
| --- | --- |
| Teléfono | Respuestas rápidas en fila de ancho completo, 44 px de alto |
| Escritorio | Respuestas rápidas alineadas bajo la burbuja |

| Requisito | Implementación |
| --- | --- |
| Rol | Botones nativos; escribir "sí" en el compositor equivale a pulsar |
| Teclado | Tab llega a las respuestas rápidas tras el último mensaje |
| Foco | Tras responder, el foco vuelve al compositor |

```text
<ConfirmationReadback blockKey="place" readbackText="Anotado: autopista sur, salida 14..." />
```

### SourceCard

| Campo | Valor |
| --- | --- |
| Componente | `SourceCard` |
| Descripción | Cláusula citada con identificador, versión, vigencia, texto expandible y acceso a la traza |
| Categoría | Presentación |

| Estado | Descripción | Disparador |
| --- | --- | --- |
| Por defecto | Nombre legible, identificador y versión en mono, "vigente" | Respuesta con cita |
| Expandido | Texto completo de la cláusula con medida de 70 caracteres | "Ver cláusula" |
| Otro idioma | Etiqueta "Texto original en inglés" y la explicación marcada como resumen | Cláusula en otro idioma |
| Sin traza | "Cómo se llegó a esta respuesta" deshabilitado con "La traza se está registrando" | Traza en curso |

| Prop | Tipo | Requerido | Por defecto | Descripción |
| --- | --- | --- | --- | --- |
| `clauseId` | string | sí | — | Identificador estable |
| `version` | string | sí | — | Versión vigente |
| `title` | string | sí | — | Nombre legible de la cláusula |
| `sourceLang` | `es` o `en` | sí | — | Idioma original del texto |
| `traceHref` | string | no | — | Enlace al resumen de la traza |

| Pantalla | Comportamiento |
| --- | --- |
| Teléfono | Botones apilados, 44 px de alto |
| Escritorio | Botones en línea |

| Requisito | Implementación |
| --- | --- |
| Rol | "Ver cláusula" es un disclosure con `aria-expanded` y `aria-controls` |
| Teclado | Enter o Espacio expanden; el texto expandido sigue al botón en el orden de Tab |
| Idioma | El texto de la cláusula declara su `lang` |
| Lector de pantalla | El identificador se lee con su nombre: "Cláusula SMU-PAP-D-3.2, versión 2026.1, vigente" |

```text
<SourceCard clauseId="SMU-PAP-D-3.2" version="2026.1" title="Gastos de transporte" sourceLang="es" traceHref="#trace-8f2c" />
```

### TracePanel

| Campo | Valor |
| --- | --- |
| Componente | `TracePanel` |
| Descripción | Resumen redactado de la traza de una respuesta, en el modo de tema elegido |
| Categoría | Presentación |

| Estado | Descripción | Disparador |
| --- | --- | --- |
| Cargando | Esqueleto de la ruta | Apertura |
| Registrándose | "La traza se está registrando" y actualización automática | Traza aún no escrita |
| Completo | Ruta, cláusulas, latencia total y costo | Traza disponible |
| No disponible | Mismo mensaje que para un identificador inexistente | Respuesta de otro navegador |

| Prop | Tipo | Requerido | Por defecto | Descripción |
| --- | --- | --- | --- | --- |
| `answerId` | string | sí | — | Respuesta de este navegador |
| `open` | boolean | sí | false | Visible o no |

| Pantalla | Comportamiento |
| --- | --- |
| Teléfono | Hoja inferior al 92 % del alto, se cierra deslizando hacia abajo o con el botón |
| Escritorio | Panel lateral de 440 px sobre el chat, que queda visible |

| Requisito | Implementación |
| --- | --- |
| Rol | `dialog` no modal en escritorio con título; modal en teléfono |
| Teclado | Escape cierra; Tab recorre el panel |
| Foco | Al abrir, va al título del panel; al cerrar, vuelve al botón que lo abrió |
| Lector de pantalla | Anuncia el título; los nodos se leen como lista ordenada con latencia |

```text
<TracePanel answerId="a-8f2c" open />
```

### Composer

| Campo | Valor |
| --- | --- |
| Componente | `Composer` |
| Descripción | Campo de texto y botón de enviar del chat y de la comparación |
| Categoría | Entrada |

| Estado | Descripción | Disparador |
| --- | --- | --- |
| Por defecto | Campo con ayuda de teclado | Carga |
| Enviando | Botón deshabilitado con "Enviando" | Envío |
| Límite alcanzado | Campo deshabilitado con el motivo y cuándo seguir | Límite de la demo |
| Texto demasiado largo | Contador y mensaje del catálogo | Supera el máximo |
| Degradado | Texto conservado tras una falla | Falla del proveedor |

| Prop | Tipo | Requerido | Por defecto | Descripción |
| --- | --- | --- | --- | --- |
| `maxLength` | number | sí | Configuración | Largo máximo |
| `disabledReasonKey` | string | no | — | Clave del motivo cuando está deshabilitado |

| Pantalla | Comportamiento |
| --- | --- |
| Teléfono | Fijo abajo y visible con el teclado abierto (AC1.33.2) |
| Escritorio | Fijo al pie de la conversación |

| Requisito | Implementación |
| --- | --- |
| Rol | `textarea` con etiqueta "Escriba su mensaje" |
| Teclado | Enter envía; Mayús + Enter agrega línea |
| Error | El motivo se asocia al campo con `aria-describedby` |

```text
<Composer maxLength={600} disabledReasonKey="limits.session.reached" />
```

### EmergencyNotice

| Campo | Valor |
| --- | --- |
| Componente | `EmergencyNotice` |
| Descripción | Indicación de llamar a emergencias antes de cualquier dato |
| Categoría | Retroalimentación |

| Estado | Descripción | Disparador |
| --- | --- | --- |
| Público | Número de emergencias de donde se encuentre y aviso de demostración | Heridos graves en superficie pública |
| Local | 911 y oferta de seguir después | Despliegue local |

| Requisito | Implementación |
| --- | --- |
| Rol | `alert`, que se anuncia de inmediato |
| Aspecto | Contorno de error completo e ícono con texto; nunca solo color |
| Foco | No roba el foco; queda primero en el orden de lectura del turno |

```text
<EmergencyNotice variant="public" />
```

### CaseClosureSummary

| Campo | Valor |
| --- | --- |
| Componente | `CaseClosureSummary` |
| Descripción | Resumen del reporte, número de caso, qué sigue y enlace firmado |
| Categoría | Presentación |

| Estado | Descripción | Disparador |
| --- | --- | --- |
| Derivado | "Un ajustador revisa su caso..." y botón al enlace con hora de vencimiento | Caso derivado |
| Cierre directo | Frase fija del cierre directo y enlace de solo lectura | Cierre directo |
| Enlace vencido | "El enlace venció" y cómo pedir otro | Pasó la hora |

| Requisito | Implementación |
| --- | --- |
| Número de caso | Mono, con nombre accesible "Caso SMU cuatro ocho dos nueve uno tres" legible dígito a dígito |
| Enlace | Botón real con la hora de vencimiento asociada con `aria-describedby` |

```text
<CaseClosureSummary caseNumber="SMU-482913" outcome="derived" expiresAt="18:42" />
```

### CallAvailability y CallControlBar

| Campo | Valor |
| --- | --- |
| Componente | `CallAvailability`, `CallControlBar` |
| Descripción | Disponibilidad de la voz antes de llamar; estado, tiempo restante y colgar durante la llamada |
| Categoría | Retroalimentación y entrada |

| Estado | Descripción | Disparador |
| --- | --- | --- |
| Disponible | "Llamar" activo con los límites en texto | Consulta al cargar |
| No disponible | Motivo del catálogo y enlace al chat | Llamada del día usada, tope del sitio, techo, configuración rota |
| Conectando | "Conectando la llamada" y "Cancelar" | Llamar |
| En curso | Tiempo restante en mono y "Colgar" | Conexión lista |
| Últimos 30 segundos | Aviso en línea con color de aviso y texto | Faltan 30 segundos |
| Terminada | Final de la llamada con la causa | Colgar, corte o límite |

| Pantalla | Comportamiento |
| --- | --- |
| Teléfono | Barra fija abajo con tiempo y "Colgar" de 48 px de alto |
| Escritorio | Barra fija al pie de la consola |

| Requisito | Implementación |
| --- | --- |
| Teclado | "Llamar" y "Colgar" alcanzables con Tab y activables con Enter o Espacio |
| Lector de pantalla | El tiempo restante no se anuncia cada segundo: se anuncia a los 60 y a los 30 segundos (AC1.33.4) |
| Contraste | "Colgar" en color de error con texto, no solo ícono |

```text
<CallControlBar remainingSeconds={134} state="in-call" />
```

### TranscriptLine y PiiTag

| Campo | Valor |
| --- | --- |
| Componente | `TranscriptLine`, `PiiTag` |
| Descripción | Turno de la transcripción con quién habla, hora y datos personales como etiquetas |
| Categoría | Presentación |

| Estado | Descripción | Disparador |
| --- | --- | --- |
| Parcial | Texto secundario con "escuchando" | Reconocimiento en curso |
| Final | Texto principal con hora | Cierre del turno |
| Divulgación | Marca "Valentina ya dijo que es una IA" con hora | Apertura completa |

| Requisito | Implementación |
| --- | --- |
| Quién habla | Etiqueta de texto "Valentina" o "Tú"; nunca solo color o posición |
| Datos personales | `PiiTag` muestra "[teléfono]" y se lee "teléfono redactado" |
| Lector de pantalla | Solo los turnos finales entran a la región en vivo; los parciales no se anuncian |

```text
<TranscriptLine speaker="person" time="0:15" final>Yes. You can reach me at <PiiTag type="phone" /></TranscriptLine>
```

### AgentStateIndicator

| Estado | Texto | Aspecto |
| --- | --- | --- |
| Escuchando | "Escuchando" | Punto en color de texto secundario |
| Pensando | "Pensando" | Punto con pulso lento |
| Hablando | "Hablando" | Punto en cobre |
| Revisando la póliza | "Revisando la póliza" | Punto índigo; trabajo de fondo |

El estado se anuncia como mensaje de estado solo cuando cambia y como máximo una
vez cada dos segundos; con movimiento reducido el pulso se reemplaza por el
texto sin animación.

### CaseThread

| Campo | Valor |
| --- | --- |
| Componente | `CaseThread` |
| Descripción | Hilo vertical con los siete campos del caso o los nodos de la traza |
| Categoría | Presentación |

| Estado del nodo | Aspecto | Texto accesible |
| --- | --- | --- |
| Pendiente | Aro fino | "pendiente" |
| En curso | Aro en cobre | "en curso" |
| Confirmado | Punto relleno en cobre con marca | "confirmado" |
| Trabajo de fondo | Segmento índigo | "revisando de fondo" |

| Prop | Tipo | Requerido | Por defecto | Descripción |
| --- | --- | --- | --- | --- |
| `nodes` | lista | sí | — | Nombre legible, estado y dato opcional (latencia) |
| `variant` | `case` o `trace` | sí | — | Campos del caso o ruta de la traza |

| Requisito | Implementación |
| --- | --- |
| Rol | Lista ordenada; cada nodo con su estado en texto |
| Movimiento | Al confirmarse, el punto se llena en 240 ms; con movimiento reducido cambia sin animación |
| Contraste | Línea del hilo 11,8:1; aros de pendiente con borde de control, 3:1 o más |

```text
<CaseThread variant="case" nodes={caseBlocks} />
```

### ComparisonColumn

| Estado | Descripción | Disparador |
| --- | --- | --- |
| Cargando | Esqueleto propio de la columna | Pregunta enviada |
| Con respuesta | Respuesta y tarjetas de fuente | Respuesta lista |
| Sin cláusula | "No encuentro una cláusula" | Resultado sin cláusula |
| Falla | "No pude revisar esta póliza en este momento" e "Intentar de nuevo" | Verificación caída |

En escritorio son tres columnas con divisores finos; en teléfono se apilan con el
nombre de la aseguradora visible al inicio de cada una. Cada columna es una
región con el nombre de su aseguradora y declara su idioma de respuesta.

### FilterBar y CaseTable

| Estado | Descripción | Disparador |
| --- | --- | --- |
| Cargando | Filas esqueleto con cabecera visible | Carga |
| Con casos | Filas ordenadas por prioridad y espera | Datos |
| Sin resultados | "Ningún caso coincide con estos filtros." y "Quitar filtros" | Filtros sin coincidencias |
| Vacía | Texto propio de la pestaña | Estado sin casos |

| Requisito | Implementación |
| --- | --- |
| Rol | Tabla real con encabezados; la fila entera enlaza al caso con el número como texto del enlace |
| Teclado | Tab recorre filtros y enlaces de fila; las flechas no mueven la selección, para no animar acciones repetidas |
| Prioridad | Texto y un ícono, nunca solo color |
| Filtros | Selectores nativos con etiqueta visible; el recuento de casos se anuncia al filtrar |

### CaseHeader y DecisionForm

| Campo | Valor |
| --- | --- |
| Componente | `CaseHeader`, `DecisionForm` |
| Descripción | Encabezado fijo con motivo, categoría, completitud y acciones; formulario de decisión en línea |
| Categoría | Navegación y entrada |

| Estado | Descripción | Disparador |
| --- | --- | --- |
| Decidible | Acciones según registro y rol | Caso derivado |
| Esperando al asegurado | Sin acciones; motivo y campos que faltan | Estado |
| Formulario abierto | Acción elegida, comentario obligatorio, confirmar y cancelar | Pulsa una acción |
| Error de validación | "Escriba un comentario: el asegurado lo recibe con la decisión." | Confirma sin comentario |
| Enviando | Confirmar deshabilitado con "Guardando" | Confirmar |
| Decidido | Resolución con autor y hora | Éxito |
| Conflicto | "Diana ya decidió este caso a las 4:31 p. m." | Otra persona decidió antes |
| Enlace vencido | Comentario conservado y "Copiar comentario" | Vence durante la decisión |

| Pantalla | Comportamiento |
| --- | --- |
| Teléfono | Encabezado compacto con número, estado y acciones; el formulario empuja la evidencia hacia abajo |
| Escritorio | Encabezado fijo de ancho completo; formulario bajo el encabezado |

| Requisito | Implementación |
| --- | --- |
| Rol | `form` con título "Aprobar el caso" |
| Teclado | Al abrir, el foco va al comentario; Escape cancela y devuelve el foco a la acción |
| Error | Mensaje asociado al campo y anunciado; el foco vuelve al campo |
| Resultado | El resultado se anuncia como mensaje de estado y el foco va al título del resultado |

```text
<DecisionForm action="approve" recordType="claim" role="adjuster" commentRequired />
```

### EvidenceSection y FieldCorrection

| Estado | Descripción | Disparador |
| --- | --- | --- |
| Plegada | Título con resumen de una línea ("Controles: 4 de 4 cumplidos") | Por defecto, salvo campos y transcripción |
| Desplegada | Contenido completo | Enter, Espacio o clic |
| Corrigiendo un campo | Campo editable con guardar y cancelar | "Corregir" |
| Corrección inválida | Error del catálogo que nombra el formato | Guardar con valor inválido |
| Corregido | Nuevo valor e "Historial: 1 cambio" | Guardar |

Los encabezados de sección son botones dentro de encabezados de nivel 2 con
`aria-expanded`; la corrección lleva la etiqueta del campo y su formato esperado
antes de escribir.

### LinkOrientation

Banda superior de la vista por enlace. Estados: orientación al entrar (propio
caso, permisos de demostración, hora de vencimiento en hora local), después de
decidir (qué ve el asegurado y volver a la conversación) y solo lectura (cierre
sin ajustador y la regla que lo permitió). Es una región con nombre; la hora se
escribe con la zona del navegador.

### MetricFigure y SpendCeiling

| Estado | Descripción | Disparador |
| --- | --- | --- |
| Medida | Cifra por idioma, fecha, commit, conjunto y "Ver reporte" | Corrida publicada |
| No medida | "No medida" con su causa | Sin corrida o hito futuro |
| Techo cerca | Barra con la marca de alerta superada y texto de aviso | Gasto de 3 USD o más |
| Techo alcanzado | Estado de voz cortada con el mensaje del catálogo | Gasto de 5 USD |

Las cifras usan dígitos tabulares; la barra del techo es un `meter` con valor,
mínimo y máximo, y su texto dice el valor, nunca solo el relleno.

### StatusPage

Una sola plantilla con título, explicación y una acción. "Despertando" se
actualiza sola cada cinco segundos y a los 60 pasa a "No disponible"; el hilo que
avanza es decorativo (`aria-hidden`) y el estado se lee en el título.

## Movimiento y microinteracciones

| Interacción | Propósito | Duración | Curva | Con movimiento reducido |
| --- | --- | --- | --- | --- |
| Botón presionado | Confirmar que se escuchó | 120 ms, escala 0,97 | `motion.ease.out` | Sin escala |
| Encima y foco | Mostrar lo interactivo | 160 ms, color | `motion.ease.out` | Igual |
| Expandir cláusula o sección | Mostrar qué se abrió | 200 ms, altura por filas de rejilla y opacidad | `motion.ease.out` | Aparece sin transición de altura |
| Panel de traza y hoja inferior | Mantener el contexto espacial | 260 ms, desplazamiento | `motion.ease.drawer` | Aparición por opacidad de 160 ms |
| Mensaje nuevo | Evitar un salto brusco | 160 ms de opacidad | `motion.ease.out` | Igual |
| Transmisión de la respuesta | Mostrar que la agente responde | Palabra a palabra, sin animación extra | — | Igual |
| Nodo del hilo confirmado | Estado del caso | 240 ms de relleno | `motion.ease.out` | Cambio inmediato |
| Estado de la agente | Mostrar que escucha o piensa | Pulso de 1,6 s solo en "Pensando" | Lineal | Sin pulso |
| Aviso de 30 segundos | Llamar la atención una vez | 160 ms de opacidad | `motion.ease.out` | Igual |
| Cambio de modo claro u oscuro | Cambiar sin golpe visual | Inmediato, sin transición | — | Igual |

Sin animaciones al cargar las páginas del aplicativo, sin entradas escalonadas por
sección y sin animar acciones de teclado repetidas. Los efectos de encima se
activan solo con puntero fino.

## Teclado y foco por pantalla

| Pantalla | Orden de Tab | Atajos | Foco inicial |
| --- | --- | --- | --- |
| Inicio | Saltar al contenido, navegación, idioma, tema, cómo funciona, filas de aseguradoras, comparar | — | Enlace "Saltar al contenido" |
| Chat | Saltar, inicio de la demo, idioma, tema, aviso, póliza de ejemplo, conversación, sugerencias, compositor | Enter envía | Compositor tras la divulgación |
| Traza | Cerrar, ruta, cláusulas | Escape cierra | Título del panel |
| Consola | Selectores, Llamar; en curso: Colgar, pestañas en teléfono, transcripción | — | "Llamar" |
| Comparación | Pregunta, sugerencias, columnas en orden | Enter envía | Campo de pregunta |
| Bandeja | Idioma, pestañas de estado, filtros, filas | — | Título "Casos" |
| Vista de caso | Volver, acciones, secciones, campos | Escape cierra el formulario | Título del caso |
| Vista por enlace | Orientación, volver a la conversación, acciones, secciones | — | Texto de orientación |

Nunca hay trampas de foco salvo en la hoja inferior modal del teléfono, que se
cierra con Escape o con su botón.

## Anuncios para lectores de pantalla

| Evento | Tipo | Cuándo |
| --- | --- | --- |
| Respuesta de la agente | Región en vivo cortés | Una vez, completa, al terminar de transmitirse |
| "Revisando la póliza" y estados de carga | Mensaje de estado | Al empezar y al terminar |
| Límite alcanzado, errores del chat | Mensaje de estado | Al ocurrir |
| Emergencia | Alerta | De inmediato |
| Cuenta regresiva de la llamada | Mensaje de estado | A los 60 y a los 30 segundos |
| Resultado de filtrar la bandeja | Mensaje de estado | "12 casos" al aplicar filtros |
| Decisión guardada o rechazada | Mensaje de estado | Al terminar el guardado |

## Comportamiento responsivo

| Punto de quiebre | Chat | Consola | Bandeja y caso | Comparación |
| --- | --- | --- | --- | --- |
| Desde 360 px | Una columna; póliza plegada arriba; compositor fijo | Pestañas y barra de control fija | Lista de filas; encabezado compacto | Columnas apiladas |
| Desde 768 px | Una columna más ancha; póliza visible arriba | Pestañas o dos zonas según ancho | Tabla con columnas esenciales | Columnas apiladas |
| Desde 1024 px | Dos columnas: póliza y conversación | Dos zonas lado a lado | Tabla completa; campos y transcripción lado a lado | Tres columnas |

Nada se desplaza en horizontal en 360 px ni a 200 % de zoom; solo una tabla
ancha, dentro de su propio contenedor, puede desplazarse en horizontal en la
bandeja.

## Reglas de texto en la interfaz

- Todo texto sale del catálogo por idioma, con paridad de claves.
- Ninguna etiqueta de una pantalla de visitante usa jerga del sistema (bandeja,
  traza, divulgación, p50) sin decir en palabras simples qué es (U-01 a U-20).
- Frases en tipo oración; sin etiquetas en mayúsculas sobre los títulos.
- Cada acción conserva su nombre en todo el recorrido: "Aprobar" abre "Aprobar el
  caso" y termina en "quedó aprobado".
- Los errores dicen qué pasó y cómo seguir; no se disculpan ni muestran códigos.
- Los tiempos y montos van con su unidad y su zona horaria o moneda.
- Nada en la interfaz promete plazos, llamadas salientes ni transferencias en
  vivo.
