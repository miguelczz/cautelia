# Mapa de historias por unidad — Untangle

Cada historia de `../user-stories/stories.md` con la unidad que la implementa,
las que cruzan unidades, el orden dentro de cada unidad y la verificación de que
ninguna historia ni ninguna unidad queda sin asignar. `traceability.json` tiene
la misma asignación.

**Fuentes consumidas.**

- **Componentes** (`../domain-design/components.md`): los 23 componentes, sus
  dependencias, la propiedad de cada entidad, las historias por componente y la
  opción A de los nodos.
- **Decisiones de arquitectura** (`../domain-design/decisions.md`): el monolito
  modular en un solo proceso (ADR-001), los dos lenguajes y el origen único
  (ADR-002), LangGraph (ADR-003), el ritmo de fondo sin broker (ADR-004), los
  proveedores y el experimento 1 (ADR-006 a ADR-009), la evaluación (ADR-014) y
  los adaptadores por uso (ADR-018), que fijan dónde se puede partir y dónde no.
- **Requisitos** (`../requirements-analysis/requirements.md`): los grupos FR1 a
  FR14, los NFR con su valor esperado y la pregunta abierta OQ4 de hospedaje.
- **Historias** (`../user-stories/stories.md`): las 87 historias con su
  prioridad, su rama anticipada, sus módulos, sus relaciones "Construye sobre",
  las cadenas que no se deben separar y las preguntas PA-1 a PA-13.
- **Prácticas del equipo** (`../practices-discovery/team-practices.md`, ya en
  `team.md`): la base sólida y después una pieza completa a la vez, la rama de
  pruebas por unidad, el primer commit con todo el andamiaje y las diez
  convenciones de estilo.
- **Plan de entrega del PRD** (`docs/specs/prd.md`, sección 13): las capas de
  texto, bandeja y chat, voz en inglés y voz en español, y la regla de corte
  S2, S1, C1, S5, S4.
- **Respuestas de esta etapa** (`units-generation-questions.md`): Q1 (A), Q2 (A)
  y la aprobación del plan.

## Historias por unidad

La columna `Rama` es la rama anticipada de cada historia en `stories.md`. La
rama que manda en Construcción es la de la unidad, en la tabla de unidades de
`unit-of-work.md` (decisión UG-12): una unidad evaluada puede tener historias
deterministas porque usa además la rama determinista para las capas que la
sostienen (`team.md`, Testing Posture).

| Historia | Título | Prioridad | Rama | Unit ID | Directory |
| --- | --- | --- | --- | --- | --- |
| US1.1 | Saber con quién hablo al abrir el chat | Must | evaluada | U13 | `u13-chat` |
| US1.2 | Que el chat me responda en mi idioma | Must | evaluada | U13 | `u13-chat` |
| US1.3 | Identificarme con mi póliza sin ver la de nadie más | Must | evaluada | U11 | `u11-intake` |
| US1.4 | Reportar en nombre de otra persona | Must | evaluada | U11 | `u11-intake` |
| US1.5 | Empezar por mi seguridad y contar lo que pasó una idea a la vez | Must | evaluada | U11 | `u11-intake` |
| US1.6 | Recibir primero la indicación de emergencia si hay heridos graves | Must | evaluada | U10 | `u10-compliance` |
| US1.7 | Confirmar cada bloque y corregir lo que quedó mal anotado | Must | evaluada | U11 | `u11-intake` |
| US1.8 | Registrar a las demás personas y vehículos del accidente | Must | evaluada | U4 | `u4-case-record` |
| US1.9 | Pedir que una persona revise mi caso en cualquier momento | Must | evaluada | U10 | `u10-compliance` |
| US1.10 | Que la agente nunca finja ser una persona | Must | evaluada | U10 | `u10-compliance` |
| US1.11 | No recibir promesas de cobertura, dinero ni culpa aunque insista | Must | evaluada | U10 | `u10-compliance` |
| US1.12 | Registrar dos versiones de lo que pasó sin que me acusen | Must | evaluada | U11 | `u11-intake` |
| US1.13 | Que me atiendan con calma si estoy alterado | Must | evaluada | U11 | `u11-intake` |
| US1.14 | Cerrar el reporte por chat con mi número de caso y sin plazos | Must | evaluada | U4 | `u4-case-record` |
| US1.15 | Saber qué sigue según las reglas de mi aseguradora | Must | evaluada | U9 | `u9-rules-decision` |
| US1.16 | Que mi caso no se cierre sin sus controles ni sus adjuntos | Must | evaluada | U10 | `u10-compliance` |
| US1.17 | Que un siniestro sencillo se registre sin esperar a un ajustador | Must | evaluada | U9 | `u9-rules-decision` |
| US1.18 | Enterarme en el chat de lo que decidió el ajustador | Must | determinista | U13 | `u13-chat` |
| US1.19 | Retomar un reporte por chat que dejé a medias | Must | determinista | U12 | `u12-graph-runtime` |
| US1.20 | Retomar por chat un caso que empecé por voz | Should | determinista | U13 | `u13-chat` |
| US1.21 | Conectar una llamada desde el navegador | Must | determinista | U16 | `u16-voice-call` |
| US1.22 | Oír primero con quién hablo y qué puede hacer, en inglés | Must | evaluada | U16 | `u16-voice-call` |
| US1.23 | Reportar el accidente hablando, en inglés | Must | evaluada | U16 | `u16-voice-call` |
| US1.24 | Interrumpir a la agente para corregir algo, en inglés | Must | evaluada | U16 | `u16-voice-call` |
| US1.25 | Que la conversación siga mientras se revisa mi póliza | Must | determinista | U12 | `u12-graph-runtime` |
| US1.26 | Que la agente note mis silencios, en inglés | Must | evaluada | U16 | `u16-voice-call` |
| US1.27 | Retomar una llamada que se cortó, en inglés | Must | determinista | U16 | `u16-voice-call` |
| US1.28 | Llamar en español y oír a Valentina con la misma voz | Must | evaluada | U18 | `u18-voice-spanish` |
| US1.29 | Reportar hablando en español con las mismas metas | Must | evaluada | U18 | `u18-voice-spanish` |
| US1.30 | Interrumpir, callar y retomar en español con las mismas metas | Must | evaluada | U18 | `u18-voice-spanish` |
| US1.31 | Cambiar de idioma a mitad de la llamada diciéndolo | Must | evaluada | U18 | `u18-voice-spanish` |
| US1.32 | Que la agente note sola que cambié de idioma | Should | evaluada | U18 | `u18-voice-spanish` |
| US1.33 | Usar el chat y la llamada desde el teléfono, con teclado o con lector de pantalla | Must | determinista | U6 | `u06-web-shell` |
| US2.1 | Recibir solo cláusulas de mi aseguradora y de mi póliza vigente | Must | evaluada | U8 | `u8-policy-rag` |
| US2.2 | Que ninguna cita llegue sin pasar por el verificador | Must | evaluada | U8 | `u8-policy-rag` |
| US2.3 | Ver la cita en el chat con su texto completo y el resumen de su traza | Must | determinista | U13 | `u13-chat` |
| US2.4 | Preguntar por cobertura a mitad del reporte y volver donde iba | Must | evaluada | U12 | `u12-graph-runtime` |
| US2.5 | Recibir "no encuentro una cláusula" en vez de una respuesta inventada | Must | evaluada | U8 | `u8-policy-rag` |
| US2.6 | Saber cuándo la agente no pudo revisar mi póliza | Must | evaluada | U8 | `u8-policy-rag` |
| US2.7 | Preguntar por cobertura en una llamada, en inglés | Must | evaluada | U8 | `u8-policy-rag` |
| US2.8 | Recibir la cláusula de la aseguradora que emitió mi póliza cuando soy cliente de la agencia | Must | evaluada | U8 | `u8-policy-rag` |
| US2.9 | Ver la misma pregunta respondida por las tres aseguradoras lado a lado | Should | determinista | U13 | `u13-chat` |
| US2.10 | Que la conversación no se rompa si el modelo o un proveedor no responde | Must | determinista | U12 | `u12-graph-runtime` |
| US3.1 | Ver la cola de casos de mi aseguradora con filtros | Must | evaluada | U14 | `u14-inbox` |
| US3.2 | Tener toda la evidencia de un caso en una pantalla | Must | evaluada | U14 | `u14-inbox` |
| US3.3 | Corregir un campo mal capturado dejando rastro | Must | determinista | U14 | `u14-inbox` |
| US3.4 | Aprobar o rechazar con comentario y que el caso siga solo | Must | determinista | U14 | `u14-inbox` |
| US3.5 | Ver los casos que esperan al asegurado | Must | determinista | U14 | `u14-inbox` |
| US3.6 | Marcar un caso como enviado a la aseguradora sin poder decidir cobertura | Must | evaluada | U14 | `u14-inbox` |
| US3.7 | Crear un caso en la demo y decidirlo yo mismo | Must | determinista | U14 | `u14-inbox` |
| US3.8 | Entrar a mi caso con el enlace sin perderme | Must | determinista | U14 | `u14-inbox` |
| US4.1 | Entender en 90 segundos qué hace el proyecto leyendo el README | Must | determinista | U22 | `u22-public-evidence` |
| US4.2 | Ver en un video corto la demo completa y saber de qué versión es | Must | determinista | N/A | — |
| US4.3 | Llegar desde la landing a lo que de verdad existe | Must | determinista | N/A | — |
| US4.4 | Clonar el repositorio y ver el reporte de evaluación en menos de 15 minutos | Must | evaluada | U1 | `u1-workspace` |
| US4.5 | Leer un reporte que muestra cada caso, cada idioma y cada regresión | Must | evaluada | U21 | `u21-eval-gates` |
| US4.6 | Contar los veredictos del juez solo mientras coincide con las personas | Must | evaluada | U21 | `u21-eval-gates` |
| US4.7 | Reproducir una conversación de prueba sin un modelo que simule al asegurado | Must | evaluada | U1 | `u1-workspace` |
| US4.8 | Seguir en la traza todo lo que pasó en un caso | Must | determinista | U5 | `u5-provider-platform` |
| US4.9 | Comprobar que el orquestador es código y no un modelo que decide | Must | determinista | U12 | `u12-graph-runtime` |
| US4.10 | Que el caso cambie de estado solo por las transiciones declaradas | Must | evaluada | U4 | `u4-case-record` |
| US4.11 | Comprobar que ninguna aseguradora lee datos de otra en la base de datos | Must | evaluada | U2 | `u2-tenancy` |
| US4.12 | Que los datos personales se redacten en un solo punto antes de salir | Must | evaluada | U3 | `u3-pii-redaction` |
| US4.13 | Que los reconocedores encuentren placas, cédulas, teléfonos y pólizas en los dos idiomas | Must | evaluada | U3 | `u3-pii-redaction` |
| US4.14 | Que un segundo detector distinto confirme que no se escapó nada | Must | evaluada | U21 | `u21-eval-gates` |
| US4.15 | Intentar romper el chat y ver que no obedece | Must | evaluada | U10 | `u10-compliance` |
| US4.16 | Ver las cinco cifras del sistema con su fecha y su commit | Must | determinista | U22 | `u22-public-evidence` |
| US4.17 | Entender en la consola qué pasa con mi llamada mientras pruebo la voz | Must | determinista | U17 | `u17-voice-public-link` |
| US5.1 | Aprovisionar una aseguradora editando solo configuración | Must | evaluada | U20 | `u20-demo-operations` |
| US5.2 | Ingerir el corpus con identificador y versión por cláusula | Must | evaluada | U8 | `u8-policy-rag` |
| US5.3 | Regenerar los datos sintéticos y obtener los mismos bytes | Must | determinista | U7 | `u7-synthetic-data` |
| US5.4 | Tener el corpus de Stonecroft Mutual con estructura de póliza real y texto propio | Must | determinista | U7 | `u7-synthetic-data` |
| US5.5 | Tener el corpus de Sunmeadow Auto y las pólizas de los clientes de Knotwell | Must | determinista | U7 | `u7-synthetic-data` |
| US5.6 | Sembrar un caso en cada estado para las pruebas | Must | determinista | U7 | `u7-synthetic-data` |
| US5.7 | Entrar a la bandeja con una credencial ligada a una aseguradora y un rol | Must | evaluada | U2 | `u2-tenancy` |
| US5.8 | Mantener el catálogo de textos con paridad entre español e inglés | Must | determinista | U1 | `u1-workspace` |
| US5.9 | Cambiar una regla y que la compuerta me diga qué rompí | Must | evaluada | U21 | `u21-eval-gates` |
| US5.10 | Cambiar de proveedor o de voz editando solo configuración | Must | determinista | U15 | `u15-speech-providers` |
| US5.11 | Que la voz siga con la voz de respaldo cuando se acaba el presupuesto | Must | determinista | U17 | `u17-voice-public-link` |
| US5.12 | Fijar los límites de la voz pública en la aplicación y en el proveedor | Must | determinista | U17 | `u17-voice-public-link` |
| US5.13 | Limitar el chat público para que nadie agote el presupuesto | Must | determinista | U13 | `u13-chat` |
| US5.14 | Ver el gasto y que la voz se corte sola al llegar al techo | Must | determinista | U5 | `u5-provider-platform` |
| US5.15 | Que los datos de los visitantes se borren cada noche | Must | determinista | U20 | `u20-demo-operations` |
| US5.16 | Que la demo esté despierta cuando alguien llega | Must | determinista | U6 | `u06-web-shell` |
| US6.1 | Pedir una cotización contando mis datos en la misma conversación | Should | evaluada | U19 | `u19-quote` |
| US6.2 | Saber si soy elegible sin recibir un precio | Should | evaluada | U19 | `u19-quote` |
| US6.3 | Decidir en la bandeja las solicitudes derivadas | Should | determinista | U19 | `u19-quote` |

## Orden de implementación dentro de cada unidad

El orden sigue las relaciones "Construye sobre" de las historias y deja primero lo
que las demás historias de la unidad reutilizan. Vale solo dentro de la unidad;
el orden entre unidades lo decide Delivery Planning.

### U1 — workspace

1. US4.4 — Clonar el repositorio y ver el reporte de evaluación en menos de 15 minutos. Construye sobre: ninguna.
2. US5.8 — Mantener el catálogo de textos con paridad entre español e inglés. Construye sobre: ninguna.
3. US4.7 — Reproducir una conversación de prueba sin un modelo que simule al asegurado. Construye sobre: ninguna.

### U2 — tenancy

1. US4.11 — Comprobar que ninguna aseguradora lee datos de otra en la base de datos. Construye sobre: ninguna.
2. US5.7 — Entrar a la bandeja con una credencial ligada a una aseguradora y un rol. Construye sobre: ninguna.

### U3 — pii-redaction

1. US4.12 — Que los datos personales se redacten en un solo punto antes de salir. Construye sobre: ninguna.
2. US4.13 — Que los reconocedores encuentren placas, cédulas, teléfonos y pólizas en los dos idiomas. Construye sobre: US4.12 (el punto único de salida).

### U4 — case-record

1. US4.10 — Que el caso cambie de estado solo por las transiciones declaradas. Construye sobre: ninguna.
2. US1.8 — Registrar a las demás personas y vehículos del accidente. Construye sobre: ninguna.
3. US1.14 — Cerrar el reporte por chat con mi número de caso y sin plazos. Construye sobre: ninguna (parte de un caso sembrado con los siete campos).

### U5 — provider-platform

1. US4.8 — Seguir en la traza todo lo que pasó en un caso. Construye sobre: ninguna.
2. US5.14 — Ver el gasto y que la voz se corte sola al llegar al techo. Construye sobre: US4.8 (la traza con costo).

### U6 — web-shell

1. US1.33 — Usar el chat y la llamada desde el teléfono, con teclado o con lector de pantalla. Construye sobre: ninguna.
2. US5.16 — Que la demo esté despierta cuando alguien llega. Construye sobre: ninguna.

### U7 — synthetic-data

1. US5.3 — Regenerar los datos sintéticos y obtener los mismos bytes. Construye sobre: ninguna.
2. US5.4 — Tener el corpus de Stonecroft Mutual con estructura de póliza real y texto propio. Construye sobre: US5.3 (el generador).
3. US5.5 — Tener el corpus de Sunmeadow Auto y las pólizas de los clientes de Knotwell. Construye sobre: US5.3 (el generador).
4. US5.6 — Sembrar un caso en cada estado para las pruebas. Construye sobre: US5.3 (el generador).

### U8 — policy-rag

1. US5.2 — Ingerir el corpus con identificador y versión por cláusula. Construye sobre: ninguna (parte de un corpus de prueba sembrado).
2. US2.1 — Recibir solo cláusulas de mi aseguradora y de mi póliza vigente. Construye sobre: US5.2 (la ingesta del corpus).
3. US2.8 — Recibir la cláusula de la aseguradora que emitió mi póliza cuando soy cliente de la agencia. Construye sobre: US2.1 (la recuperación filtrada).
4. US2.2 — Que ninguna cita llegue sin pasar por el verificador. Construye sobre: US2.1 (la recuperación filtrada).
5. US2.5 — Recibir "no encuentro una cláusula" en vez de una respuesta inventada. Construye sobre: US2.2 (la respuesta verificada).
6. US2.6 — Saber cuándo la agente no pudo revisar mi póliza. Construye sobre: ninguna.
7. US2.7 — Preguntar por cobertura en una llamada, en inglés. Construye sobre: US2.2 (la respuesta verificada) y US1.15 (las reglas).

### U9 — rules-decision

1. US1.15 — Saber qué sigue según las reglas de mi aseguradora. Construye sobre: ninguna.
2. US1.17 — Que un siniestro sencillo se registre sin esperar a un ajustador. Construye sobre: US1.15 (las reglas de la aseguradora).

### U10 — compliance

1. US1.10 — Que la agente nunca finja ser una persona. Construye sobre: ninguna.
2. US1.9 — Pedir que una persona revise mi caso en cualquier momento. Construye sobre: ninguna.
3. US1.6 — Recibir primero la indicación de emergencia si hay heridos graves. Construye sobre: ninguna.
4. US1.11 — No recibir promesas de cobertura, dinero ni culpa aunque insista. Construye sobre: ninguna.
5. US4.15 — Intentar romper el chat y ver que no obedece. Construye sobre: US1.11 (la guardia de salida).
6. US1.16 — Que mi caso no se cierre sin sus controles ni sus adjuntos. Construye sobre: ninguna.

### U11 — intake

1. US1.3 — Identificarme con mi póliza sin ver la de nadie más. Construye sobre: ninguna.
2. US1.5 — Empezar por mi seguridad y contar lo que pasó una idea a la vez. Construye sobre: ninguna.
3. US1.7 — Confirmar cada bloque y corregir lo que quedó mal anotado. Construye sobre: US1.5 (el orden de la captura).
4. US1.4 — Reportar en nombre de otra persona. Construye sobre: US1.15 (las reglas de la aseguradora).
5. US1.12 — Registrar dos versiones de lo que pasó sin que me acusen. Construye sobre: US1.15 (las reglas de la aseguradora).
6. US1.13 — Que me atiendan con calma si estoy alterado. Construye sobre: ninguna.

### U12 — graph-runtime

1. US4.9 — Comprobar que el orquestador es código y no un modelo que decide. Construye sobre: ninguna.
2. US1.19 — Retomar un reporte por chat que dejé a medias. Construye sobre: ninguna.
3. US1.25 — Que la conversación siga mientras se revisa mi póliza. Construye sobre: ninguna.
4. US2.4 — Preguntar por cobertura a mitad del reporte y volver donde iba. Construye sobre: US2.2 (la respuesta verificada).
5. US2.10 — Que la conversación no se rompa si el modelo o un proveedor no responde. Construye sobre: US1.11 (la guardia de salida).

### U13 — chat

1. US1.1 — Saber con quién hablo al abrir el chat. Construye sobre: ninguna.
2. US1.2 — Que el chat me responda en mi idioma. Construye sobre: ninguna.
3. US5.13 — Limitar el chat público para que nadie agote el presupuesto. Construye sobre: ninguna.
4. US1.18 — Enterarme en el chat de lo que decidió el ajustador. Construye sobre: US1.11 (la guardia de salida).
5. US2.3 — Ver la cita en el chat con su texto completo y el resumen de su traza. Construye sobre: US2.2 (la respuesta verificada).
6. US1.20 — Retomar por chat un caso que empecé por voz. Construye sobre: US1.19 (la reanudación desde el punto de control).
7. US2.9 — Ver la misma pregunta respondida por las tres aseguradoras lado a lado. Construye sobre: US2.2 y US2.8 (la respuesta verificada y la de la agencia).

### U14 — inbox

1. US3.1 — Ver la cola de casos de mi aseguradora con filtros. Construye sobre: US5.7 (las credenciales de la bandeja).
2. US3.2 — Tener toda la evidencia de un caso en una pantalla. Construye sobre: US1.16 (los adjuntos del caso).
3. US3.3 — Corregir un campo mal capturado dejando rastro. Construye sobre: ninguna.
4. US3.4 — Aprobar o rechazar con comentario y que el caso siga solo. Construye sobre: ninguna (parte de un caso pausado sembrado).
5. US3.5 — Ver los casos que esperan al asegurado. Construye sobre: ninguna (parte de casos incompletos sembrados).
6. US3.6 — Marcar un caso como enviado a la aseguradora sin poder decidir cobertura. Construye sobre: US1.15 (las reglas) y US5.7 (las credenciales).
7. US3.7 — Crear un caso en la demo y decidirlo yo mismo. Construye sobre: US3.4 (la decisión con comentario) y US3.6 (la acción de la agencia).
8. US3.8 — Entrar a mi caso con el enlace sin perderme. Construye sobre: US3.7 (el enlace y la decisión).

### U15 — speech-providers

1. US5.10 — Cambiar de proveedor o de voz editando solo configuración. Construye sobre: ninguna.

### U16 — voice-call

1. US1.21 — Conectar una llamada desde el navegador. Construye sobre: ninguna.
2. US1.22 — Oír primero con quién hablo y qué puede hacer, en inglés. Construye sobre: US1.21 (la conexión).
3. US1.24 — Interrumpir a la agente para corregir algo, en inglés. Construye sobre: US1.22 (la apertura).
4. US1.23 — Reportar el accidente hablando, en inglés. Construye sobre: US1.5 y US1.7 (el reporte por turnos, por otro canal).
5. US1.26 — Que la agente note mis silencios, en inglés. Construye sobre: ninguna.
6. US1.27 — Retomar una llamada que se cortó, en inglés. Construye sobre: US1.19 (la reanudación desde el punto de control).

### U17 — voice-public-link

1. US5.12 — Fijar los límites de la voz pública en la aplicación y en el proveedor. Construye sobre: ninguna.
2. US5.11 — Que la voz siga con la voz de respaldo cuando se acaba el presupuesto. Construye sobre: US5.10 (la interfaz de síntesis).
3. US4.17 — Entender en la consola qué pasa con mi llamada mientras pruebo la voz. Construye sobre: US1.21 (conectar una llamada).

### U18 — voice-spanish

1. US1.28 — Llamar en español y oír a Valentina con la misma voz. Construye sobre: US1.21, US1.22 y US1.24 (la conexión, la apertura y la interrupción).
2. US1.29 — Reportar hablando en español con las mismas metas. Construye sobre: US1.23 y US2.7 (el reporte y la pregunta de cobertura por voz).
3. US1.30 — Interrumpir, callar y retomar en español con las mismas metas. Construye sobre: US1.24, US1.26 y US1.27 (la misma conducta en inglés).
4. US1.31 — Cambiar de idioma a mitad de la llamada diciéndolo. Construye sobre: US1.23 y US1.29 (el reporte por voz en cada idioma).
5. US1.32 — Que la agente note sola que cambié de idioma. Construye sobre: US1.31 (el cambio de idioma pedido).

### U19 — quote

1. US6.1 — Pedir una cotización contando mis datos en la misma conversación. Construye sobre: US4.9 (el grafo).
2. US6.2 — Saber si soy elegible sin recibir un precio. Construye sobre: US6.1 (la solicitud) y US1.15 (las reglas).
3. US6.3 — Decidir en la bandeja las solicitudes derivadas. Construye sobre: US3.4 (decidir con comentario).

### U20 — demo-operations

1. US5.1 — Aprovisionar una aseguradora editando solo configuración. Construye sobre: ninguna.
2. US5.15 — Que los datos de los visitantes se borren cada noche. Construye sobre: US4.10 (el origen del caso).

### U21 — eval-gates

1. US4.5 — Leer un reporte que muestra cada caso, cada idioma y cada regresión. Construye sobre: US4.4 (el comando único).
2. US4.14 — Que un segundo detector distinto confirme que no se escapó nada. Construye sobre: US4.12 (el punto único de salida).
3. US4.6 — Contar los veredictos del juez solo mientras coincide con las personas. Construye sobre: US4.5 (el reporte).
4. US5.9 — Cambiar una regla y que la compuerta me diga qué rompí. Construye sobre: US4.5 (el reporte).

### U22 — public-evidence

1. US4.16 — Ver las cinco cifras del sistema con su fecha y su commit. Construye sobre: US4.5 (el reporte) y US4.8 (la traza).
2. US4.1 — Entender en 90 segundos qué hace el proyecto leyendo el README. Construye sobre: US4.5 (el reporte de evaluación).

## Historias que cruzan unidades

Historias cuya aceptación completa necesita otras unidades además de sus
dependencias directas. Cada unidad las implementa y las prueba con datos
sembrados; la verificación de punta a punta ocurre cuando existen las demás y
la registra Build and Test.

| Historia | Unidad | También necesita | Para qué |
| --- | --- | --- | --- |
| US1.4 | U11 `intake` | U9 `rules-decision` | la derivación de AC1.4.3 la produce el nodo de decisión de fondo, no la captura (corrección del 2026-09-19) |
| US1.8 | U4 `case-record` | U11 `intake` | captura de las partes en la conversación |
| US1.12 | U11 `intake` | U9 `rules-decision` | la derivación de AC1.12.3 la produce el nodo de decisión de fondo, no la captura (corrección del 2026-09-19) |
| US1.9 | U10 `compliance` | U12 `graph-runtime` | derivación en el turno siguiente |
| US1.9 | U10 `compliance` | U14 `inbox` | caso derivado en la bandeja |
| US1.14 | U4 `case-record` | U13 `chat` | cierre por chat con número de caso |
| US1.15 | U9 `rules-decision` | U12 `graph-runtime` | ejecución de fondo del nodo |
| US1.16 | U10 `compliance` | U12 `graph-runtime` | cierre o derivación desde el grafo |
| US1.17 | U9 `rules-decision` | U14 `inbox` | vista de solo lectura por enlace en cierre directo (D19) |
| US1.18 | U13 `chat` | U14 `inbox` | decisión que reanuda el caso |
| US1.19 | U12 `graph-runtime` | U13 `chat` | retoma por chat |
| US1.20 | U13 `chat` | U16 `voice-call` | caso creado por voz |
| US1.25 | U12 `graph-runtime` | U16 `voice-call` | frase de espera en la llamada |
| US1.33 | U6 `web-shell` | U13 `chat` | chat y comparación |
| US1.33 | U6 `web-shell` | U16 `voice-call` | consola |
| US1.33 | U6 `web-shell` | U14 `inbox` | vista de caso por enlace |
| US2.3 | U13 `chat` | U8 `policy-rag` | cita verificada |
| US2.6 | U8 `policy-rag` | U12 `graph-runtime` | política de fallo del nodo |
| US2.7 | U8 `policy-rag` | U16 `voice-call` | DS-5 por hito |
| US2.9 | U13 `chat` | U8 `policy-rag` | respuestas de las tres aseguradoras |
| US2.10 | U12 `graph-runtime` | U16 `voice-call` | degradación en la llamada |
| US3.7 | U14 `inbox` | U13 `chat` | enlace al cerrar en el chat |
| US3.7 | U14 `inbox` | U17 `voice-public-link` | enlace al cerrar en la consola |
| US3.8 | U14 `inbox` | U13 `chat` | enlace nuevo en la misma conversación |
| US4.1 | U22 `public-evidence` | todas las unidades | lo que el README declara construido |
| US4.4 | U1 `workspace` | U8 `policy-rag` | casos de DS-3 |
| US4.4 | U1 `workspace` | U13 `chat` | casos de DS-2 y DS-6 por el adaptador de texto |
| US4.4 | U1 `workspace` | U21 `eval-gates` | reporte completo |
| US4.5 | U21 `eval-gates` | unidades evaluadas | casos que reporta |
| US4.6 | U21 `eval-gates` | U13 `chat` | transcripciones de DS-2 que juzga |
| US4.7 | U1 `workspace` | U13 `chat` | casos de varios turnos por el adaptador de texto |
| US4.8 | U5 `provider-platform` | U12 `graph-runtime` | traza de un caso completo |
| US4.8 | U5 `provider-platform` | U13 `chat` | adaptador de texto |
| US4.8 | U5 `provider-platform` | U14 `inbox` | pausa y reanudación en la traza |
| US4.10 | U4 `case-record` | U12 `graph-runtime` | transiciones aplicadas por el runtime |
| US4.10 | U4 `case-record` | U17 `voice-public-link` | vuelta por límite de la demostración |
| US4.11 | U2 `tenancy` | U12 `graph-runtime` | tablas de puntos de control en la aserción |
| US4.11 | U2 `tenancy` | U8 `policy-rag` | recuperación sin cláusulas ajenas |
| US4.11 | U2 `tenancy` | U14 `inbox` | credencial ajena sin acceso |
| US4.12 | U3 `pii-redaction` | U5 `provider-platform` | trazas exportadas |
| US4.12 | U3 `pii-redaction` | U16 `voice-call` | transcripción en vivo de la consola |
| US4.14 | U21 `eval-gates` | U13 `chat` | trazas de la corrida de DS-2 y DS-6 |
| US4.15 | U10 `compliance` | U13 `chat` | DS-6 por el adaptador de texto |
| US4.16 | U22 `public-evidence` | voice-call y voice-spanish | latencias por idioma |
| US5.2 | U8 `policy-rag` | U20 `demo-operations` | comando de aprovisionamiento |
| US5.4 | U7 `synthetic-data` | U8 `policy-rag` | ingesta del corpus generado |
| US5.5 | U7 `synthetic-data` | U8 `policy-rag` | ingesta del corpus y de las pólizas generadas |
| US5.7 | U2 `tenancy` | U14 `inbox` | entrada a la bandeja con la credencial |
| US5.8 | U1 `workspace` | todas las unidades | cada una agrega sus claves en los dos idiomas |
| US5.10 | U15 `speech-providers` | U16 `voice-call` | la llamada siguiente usa la configuración nueva |
| US5.11 | U17 `voice-public-link` | U15 `speech-providers` | adaptador de la voz de respaldo |
| US5.14 | U5 `provider-platform` | U17 `voice-public-link` | rechazo de llamadas en el techo |
| US5.14 | U5 `provider-platform` | U22 `public-evidence` | panel de gasto |
| US5.14 | U5 `provider-platform` | U20 `demo-operations` | el acumulado sobrevive al reinicio |
| US5.15 | U20 `demo-operations` | case-record, graph-runtime, chat, inbox, policy-rag, rules-decision, compliance, voice-call, provider-platform y tenancy | cada dueño implementa su borrado |
| US5.16 | U6 `web-shell` | U13 `chat` | chequeo periódico |
| US5.16 | U6 `web-shell` | U14 `inbox` | chequeo periódico |
| US5.16 | U6 `web-shell` | U16 `voice-call` | chequeo periódico |

## Historias que cambian de dueño respecto de Domain Design

En `../domain-design/traceability.json` cada historia apunta a su componente
dueño. Casi todas quedan en la unidad que contiene ese componente, completo o en
parte. Estas tres pasan a otra unidad (decisión UG-11):

| Historia | Dueño en Domain Design | Unidad | Por qué |
| --- | --- | --- | --- |
| US3.8 | TenantIdentity | U14 `inbox` | casi todos sus criterios son del recorrido de la vista por enlace; U2 emite y valida el enlace |
| US5.12 | UsageBudget | U17 `voice-public-link` | los límites se aceptan en la llamada pública; UsageBudget solo aporta los contadores |
| US5.13 | UsageBudget | U13 `chat` | los límites se aceptan en el chat; UsageBudget solo aporta los contadores |

## Historias que no son de ninguna unidad

| Historia | Estado | Por qué |
| --- | --- | --- |
| US4.2 | N/A | Entregable de MOD-15 (video grabado), no conducta del sistema; se planifica en Delivery Planning y sus cifras salen del panel de U22 |
| US4.3 | N/A | Entregable de MOD-15 (landing de site/), fuera del aplicativo por D-005 y D-013; se planifica en Delivery Planning y enlaza lo que publican U13 (chat en vivo) y U22 (README) |

## Verificación de cobertura

- **Historias en `stories.md`:** 87 (81 Must y 6 Should).
- **Asignadas a una unidad:** 85, cada una a exactamente una unidad.
- **Sin unidad, con razón:** 2 (US4.2 y US4.3).
- **Unidades sin historias:** ninguna; las 22 tienen al menos una.
- **Should y regla de corte:** US1.20 (S2) y US2.9 (S5) en U13, US1.32 (S4) en U18 y US6.1 a US6.3 (S1) en U19.

| Unit ID | Directory | Historias | Must | Should | Evaluadas | Deterministas |
| --- | --- | --- | --- | --- | --- | --- |
| U1 | `u1-workspace` | 3 | 3 | 0 | 2 | 1 |
| U2 | `u2-tenancy` | 2 | 2 | 0 | 2 | 0 |
| U3 | `u3-pii-redaction` | 2 | 2 | 0 | 2 | 0 |
| U4 | `u4-case-record` | 3 | 3 | 0 | 3 | 0 |
| U5 | `u5-provider-platform` | 2 | 2 | 0 | 0 | 2 |
| U6 | `u06-web-shell` | 2 | 2 | 0 | 0 | 2 |
| U7 | `u7-synthetic-data` | 4 | 4 | 0 | 0 | 4 |
| U8 | `u8-policy-rag` | 7 | 7 | 0 | 7 | 0 |
| U9 | `u9-rules-decision` | 2 | 2 | 0 | 2 | 0 |
| U10 | `u10-compliance` | 6 | 6 | 0 | 6 | 0 |
| U11 | `u11-intake` | 6 | 6 | 0 | 6 | 0 |
| U12 | `u12-graph-runtime` | 5 | 5 | 0 | 1 | 4 |
| U13 | `u13-chat` | 7 | 5 | 2 | 2 | 5 |
| U14 | `u14-inbox` | 8 | 8 | 0 | 3 | 5 |
| U15 | `u15-speech-providers` | 1 | 1 | 0 | 0 | 1 |
| U16 | `u16-voice-call` | 6 | 6 | 0 | 4 | 2 |
| U17 | `u17-voice-public-link` | 3 | 3 | 0 | 0 | 3 |
| U18 | `u18-voice-spanish` | 5 | 4 | 1 | 5 | 0 |
| U19 | `u19-quote` | 3 | 0 | 3 | 2 | 1 |
| U20 | `u20-demo-operations` | 2 | 2 | 0 | 1 | 1 |
| U21 | `u21-eval-gates` | 4 | 4 | 0 | 4 | 0 |
| U22 | `u22-public-evidence` | 2 | 2 | 0 | 0 | 2 |
| **Total** | | **85** | **79** | **6** | **52** | **33** |
