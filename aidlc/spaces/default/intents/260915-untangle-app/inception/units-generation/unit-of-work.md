# Unidades de trabajo — Untangle

Las piezas que Construcción diseña, programa y prueba una a la vez. Cada unidad
dice qué componentes y qué historias contiene, qué tipo de pieza es, cómo se
despliega, cuánto pesa y qué restricciones arrastra. Las dependencias entre
unidades están en `unit-of-work-dependency.md` y la asignación de cada historia,
en `unit-of-work-story-map.md`. Esta etapa no decide en qué orden se construyen
las unidades ni cuál es su camino crítico: eso lo decide Delivery Planning.

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

## Resumen

- **23 unidades** por capacidad (Q1), con las pantallas dentro de la capacidad que muestran y una unidad común para la base de la interfaz (Q2). Eran 22 hasta el 2026-09-28, cuando US2.9 salió de U13 y nació U23 `comparison-view`; la cifra se corrigió el 2026-09-29 al notar que la prosa decía 22 y la tabla listaba 23.
- **Tipos:** 4 `service`, 10 `library`, 1 `ui` y 7 sin tipo, porque mezclan servidor y pantallas, andamiaje y código, o librería con metas propias de la corrida.
- **Rama de pruebas:** 16 unidades evaluadas y 6 deterministas (decisión UG-12).
- **Complejidad relativa:** 7 M, 11 L y 4 XL; ninguna S: hasta la unidad de una sola historia (U15) integra tres proveedores con sus pruebas de contrato.
- **Historias:** 85 asignadas, una sola vez cada una, y 2 que no son de ninguna unidad (US4.2 y US4.3, entregables de MOD-15).
- **Despliegue:** un solo proceso del aplicativo con la interfaz servida desde el mismo origen (ADR-001, ADR-002 y ADR-004). Ninguna unidad se despliega por separado; las herramientas (generador, compuertas) corren por comando en local y en GitHub Actions.
- **Cómo leer los números:** `U1` a `U22` son identificadores estables, no un orden de construcción.

## Tabla de unidades

| Unit ID | Directory | Unidad | Tipo | Complejidad | Rama | Historias | Despliegue |
| --- | --- | --- | --- | --- | --- | --- | --- |
| U1 | `u1-workspace` | workspace: Base del repositorio, catálogo de textos y corredor de evaluaciones | sin tipo | L | evaluada | 3 (3 Must) | Repositorio y tubería; raíz de composición embebida |
| U2 | `u2-tenancy` | tenancy: Aseguradoras e identidad | `library` | L | evaluada | 2 (2 Must) | Embebida en el proceso único |
| U3 | `u3-pii-redaction` | pii-redaction: Redacción de datos personales | `library` | M | evaluada | 2 (2 Must) | Embebida en el proceso único |
| U4 | `u4-case-record` | case-record: Registro del caso | `library` | L | evaluada | 3 (3 Must) | Embebida en el proceso único |
| U5 | `u5-provider-platform` | provider-platform: Proveedores de modelo, gasto y trazas | `service` | L | determinista | 2 (2 Must) | Embebida en el proceso único |
| U6 | `u06-web-shell` | web-shell: Base de la aplicación web y del proceso servido | sin tipo | L | determinista | 2 (2 Must) | Embebida y pantallas desde el mismo origen (compartido) |
| U7 | `u7-synthetic-data` | synthetic-data: Generador de datos sintéticos | `library` | L | determinista | 4 (4 Must) | Herramienta por comando; salida versionada |
| U8 | `u8-policy-rag` | policy-rag: Pólizas, recuperación y citas verificadas | `library` | XL | evaluada | 7 (7 Must) | Embebida en el proceso único |
| U9 | `u9-rules-decision` | rules-decision: Motor de reglas y nodo de decisión | `library` | M | evaluada | 2 (2 Must) | Embebida en el proceso único |
| U10 | `u10-compliance` | compliance: Controles de cumplimiento y nodo de cierre | `library` | L | evaluada | 6 (6 Must) | Embebida en el proceso único |
| U11 | `u11-intake` | intake: Nodo de captura | `library` | L | evaluada | 6 (6 Must) | Embebida en el proceso único |
| U12 | `u12-graph-runtime` | graph-runtime: Runtime del grafo | `service` | L | evaluada | 5 (5 Must) | Embebida en el proceso único |
| U13 | `u13-chat` | chat: Chat público | sin tipo | XL | evaluada | 6 (5 Must, 1 Should) | Embebida y pantallas desde el mismo origen (compartido) |
| U14 | `u14-inbox` | inbox: Bandeja y vistas de caso | sin tipo | XL | evaluada | 8 (8 Must) | Embebida y pantallas desde el mismo origen (compartido) |
| U15 | `u15-speech-providers` | speech-providers: Adaptadores de transcripción y síntesis | `library` | M | determinista | 1 (1 Must) | Embebida en el proceso único |
| U16 | `u16-voice-call` | voice-call: Llamada de voz desde el navegador | sin tipo | XL | evaluada | 6 (6 Must) | Embebida y pantallas desde el mismo origen (compartido) |
| U17 | `u17-voice-public-link` | voice-public-link: Enlace público de la voz | sin tipo | M | determinista | 3 (3 Must) | Embebida y pantallas desde el mismo origen (compartido) |
| U18 | `u18-voice-spanish` | voice-spanish: Voz en español y cambio de idioma | `service` | L | evaluada | 5 (4 Must, 1 Should) | Embebida en el proceso único |
| U19 | `u19-quote` | quote: Cotización con elegibilidad | `library` | M | evaluada | 3 (0 Must, 3 Should) | Embebida en el proceso único |
| U20 | `u20-demo-operations` | demo-operations: Operación de la demo | `service` | M | evaluada | 2 (2 Must) | Comando y tarea nocturna (embebida) |
| U21 | `u21-eval-gates` | eval-gates: Compuertas y reporte de evaluación | sin tipo | L | evaluada | 4 (4 Must) | Herramienta en local y en la tubería |
| U22 | `u22-public-evidence` | public-evidence: Evidencia pública: panel de cifras, panel de gasto y README | `ui` | M | determinista | 2 (2 Must) | Paneles servidos desde el mismo origen (compartido) |
| U23 | `u23-comparison-view` | comparison-view: Vista de comparación entre aseguradoras | sin tipo | M | evaluada | 1 (1 Should) | Pantalla servida desde el mismo origen (compartido) |

## Decisiones de esta etapa

Las marcadas **(visto bueno)** cambian algo aprobado en Domain Design; Miguel
las aprobó al aprobar el plan de esta etapa, antes de generar los documentos.

| # | Decisión | Qué se decidió | Por qué |
| --- | --- | --- | --- |
| UG-1 | Tamaño de las unidades | 23 unidades por capacidad, de 1 a 8 historias cada una. Siguen los componentes de Domain Design, juntan los que siempre se construyen y se prueban juntos y separan lo que los documentos aprobados obligan a hacer en momentos distintos. | Respuesta Q1 (A) |
| UG-2 | Dónde van las pantallas | Cada pantalla con la capacidad que muestra y una unidad común para la base de la interfaz (U6). Las unidades que mezclan servidor y pantallas quedan sin tipo y reciben la matriz completa de diseño. | Respuesta Q2 (A) |
| UG-3 | Reinicio nocturno por contrato de borrado **(visto bueno)** | U2 declara en un solo lugar qué es un dato de visitante (origen y clave del navegador) y el contrato de borrado; cada dueño lo implementa con su prueba; U20 lo ejecuta y registra `ResetRun`. DemoOperations deja de depender de trece componentes. Resuelve el hallazgo R-01 del revisor de Domain Design. | El reinicio debe funcionar antes de publicar el chat (`team.md`, Deployment) y la voz llega después; con la lista de dependencias del catálogo, U20 no podría terminarse hasta que existiera la voz. Se conservan la definición única y el registro único que pedía la razón aprobada del catálogo, pero cambia su mecanismo |
| UG-4 | Evaluation en tres unidades y conductores de los canales en `evals/drivers/` **(visto bueno; enmendada el 2026-09-17)** | El corredor de un comando y el respondedor viven en U1; el reporte con regresión, el juez, el segundo detector y la compuerta de reglas en U21; el panel de cifras y el README en U22. El chat (U13) y la llamada (U16) construyen sus conductores en `evals/drivers/`, que importan la API pública del canal, y el corredor los descubre por registro (enmienda del 2026-09-17). | La práctica de pruebas exige el corredor ejecutable antes del primer caso de cualquier rama, y DS-5 corre por hito después de la voz (FR11.7). La primera versión ponía el registro en los canales; la enmienda conserva el objetivo y hace verificable con `import-linter` que el código de producción nunca importe `untangle.evals` (ADR-001) |
| UG-5 | ProviderGateway en dos unidades | Modelo y embeddings en U5; transcripción y síntesis en U15. | La voz de respaldo se elige en el experimento 1 (ADR-008) y la voz llega después del camino en texto; los adaptadores de modelo hacen falta desde el generador de datos |
| UG-6 | VoiceChannel en tres unidades | La llamada (U16), el enlace público con sus límites y presupuesto (U17) y la capa en español con el cambio de idioma (U18). | Las historias de voz se escribieron por idioma porque se entregan en capas distintas (convención de User Stories), y el enlace público es un Must propio (M21) con límites que se prueban aparte de la llamada |
| UG-7 | Cotización como unidad propia | U19 extiende captura, esquema del caso, reglas y bandeja con el tipo `quote_request`. | Should S1, segunda en la regla de corte del PRD: así se quita sin tocar trabajo Must; Domain Design no le dio componente propio |
| UG-8 | Qué significa una dependencia | "A depende de B" cuando A importa la interfaz de B o necesita datos o herramientas de B para probarse con datos sembrados. La aceptación de punta a punta que cruza unidades se verifica en Build and Test y se lista en el mapa de historias. | Sin esta regla, las verificaciones de punta a punta crearían ciclos (el chat y la bandeja se necesitan mutuamente para US3.7 y US1.18) |
| UG-9 | Tipo de cada unidad | `service` para lo que corre en el proceso con metas propias de latencia, disponibilidad o confiabilidad; `library` para lógica sin tiempo de ejecución propio; `ui` para superficies de pantalla; sin tipo las que mezclan servidor y pantallas, empaquetado y librería, o librería con metas propias de la corrida (U21). | El aplicativo es un solo proceso (ADR-001 y ADR-004), así que "servicio desplegado" se lee como comportamiento en ejecución con metas propias; así cada unidad recibe los documentos de diseño que de verdad le sirven |
| UG-10 | Árbol del código | Prefijo único `app/` con `backend/` (Python) y `frontend/` (TypeScript), un directorio por módulo del PRD con nombre en inglés y los nodos bajo `orchestration/nodes/<token>/`. Enmienda del 2026-09-17: `api.py` por módulo, `providers/ports.py` con `adapters/`, `orchestration/state.py`, `evals/drivers/`, `app/contracts/` y `mise.toml`. Detalle en la sección "Árbol del código". | `components.md` dice que "cada módulo del PRD tiene su directorio, que fija Units Generation"; aplica las convenciones 1 a 4 de `team.md` y los dos proyectos de ADR-002 |
| UG-11 | Tres historias cambian de dueño | US5.12 pasa a U17, US5.13 a U13 y US3.8 a U14. | Sus criterios se aceptan en esas unidades; el componente dueño de Domain Design solo aporta un mecanismo |
| UG-12 | Rama de pruebas por unidad | Confirmada en la tabla de unidades: 16 evaluadas y 6 deterministas. U1 queda evaluada sin caso previo propio porque todavía no existe ningún caso. | Convención de User Stories: la rama la confirma Units Generation por unidad; práctica de pruebas de `team.md` |
| UG-13 | Dónde se registra cada requisito no funcional | Cada requisito de NFR1 a NFR21 tiene una sola unidad donde se registra, según la tabla "Requisitos no funcionales por unidad". Las compuertas duras de seguridad van en `security-requirements.md` de la unidad que las implementa; las metas de calidad que miden las evaluaciones y la duración de la corrida van en U21, que por eso queda sin tipo. | La regla del proyecto exige registrar cada meta medible en `nfr-requirements`, y una unidad `library` solo produce en esa etapa los documentos de seguridad y de stack: sin la tabla, metas como la precisión de las citas no tendrían documento. Una sola unidad por meta evita filas duplicadas en la matriz de Build and Test |
| UG-14 | Entidades por unidad | Cada unidad crea las entidades de sus componentes según `components.md`; las siete de Evaluation se reparten entre U1, U21 y U22, como indica la tabla "Entidades por unidad". | Evaluation queda en tres unidades (UG-4) y el Functional Design de cada una necesita saber qué entidades le tocan |

## Unidades

### U1 — workspace: Base del repositorio, catálogo de textos y corredor de evaluaciones

El primer commit de código del aplicativo: los dos andamiajes, el guion único de verificación, el flujo de GitHub Actions, la raíz de composición del servidor, el catálogo de textos con sus chequeos y el corredor de evaluaciones de un comando.

- **Directorio de Construcción:** `u1-workspace`
- **Tipo:** sin tipo. Mezcla empaquetado (andamiaje, flujo de verificación, servicios locales) con librería (catálogo de textos y corredor); ningún tipo solo le queda bien, así que recibe la matriz completa de diseño.
- **Complejidad relativa:** L
- **Rama de pruebas:** evaluada. Realiza M8 sin conducta propia (corredor y respondedor). Como es la primera unidad y todavía no hay casos de DS-2, DS-3 ni DS-6, su caso previo es la primera corrida de los casos que escriban las unidades siguientes; hasta entonces el corredor se sostiene con la rama determinista y casos de prueba que no pertenecen a ningún golden set.
- **Despliegue:** Artefactos del repositorio y del flujo de GitHub Actions; la raíz de composición corre embebida en el proceso único del aplicativo; el corredor es un comando del archivo de tareas, en local y en la tubería.
- **Componentes:** CopyCatalog (completo); Evaluation (parte: corredor de un comando, formato y carga de los casos por archivo, registro de objetivos y conductores, veredicto por caso y respondedor del asegurado por reglas).
- **Historias:** US4.4, US5.8, US4.7.
- **Depende de:** ninguna unidad. Es la única raíz del mapa de dependencias.

**Contiene**

- Manifiestos y lockfiles de Python (uv) y de TypeScript (pnpm), con formatter, linter con reglas de seguridad, tipos, pruebas y cobertura con su alcance declarado al prefijo `app/`
- Archivo de tareas en la raíz, `scripts/verify.sh` en el orden de `team.md` y el flujo de GitHub Actions que lo invoca, con el escaneo de secretos como primer trabajo
- Servicios locales (PostgreSQL con pgvector y Langfuse) y `.env.example` con nombres de variables
- Árbol de módulos vacío, reglas de importación comprobables por herramienta y chequeos de contenido con su lista de exclusiones versionada
- Raíz de composición del servidor: fábrica de la aplicación, configuración y endpoint de salud
- CopyCatalog completo y el corredor de evaluaciones con el respondedor por reglas

**No contiene**

- Reporte con regresión contra la línea base, juez calibrado y segundo detector (U21)
- Base visual de la interfaz y comportamiento del proceso servido (U6)

**Responsabilidades**

- Dejar ejecutables, antes del primer caso de cualquier rama, el runner de pruebas, la cobertura y el corredor de evaluaciones
- Sostener la paridad de claves entre español e inglés y las claves sin consumidor
- Correr los casos de golden set por archivo con identificador estable y devolver un código distinto de cero ante un fallo
- Responder como asegurado simulado, por reglas indexadas por campo, en los casos de varios turnos

**Notas de implementación y restricciones**

- Todo lo que lista la práctica de estilo entra en el **mismo primer commit** que el primer archivo de código (`team.md`, Code Style); los dos andamiajes llegan juntos (ADR-002).
- El comando que agrega la cobertura de Python y de TypeScript lo fija `nfr-requirements` de esta unidad (pendiente de ADR-002), con la lista de exclusión versionada: `site/`, corpus y datasets generados, migraciones.
- Las reglas de importación nacen aquí y cada unidad agrega su módulo: SDK de proveedor solo en su adaptador, ninguna conexión fuera del punto único de sesión, el núcleo no importa canales, ningún cliente de modelo en la cadena de la transición.
- El corredor no llama al modelo: el juez vive en U21. Cada unidad evaluada registra sus objetivos de prueba; los conductores de los canales viven en `evals/drivers/` y los construyen U13 (texto) y U16 (audio de DS-5), de modo que el código de producción no importa `untangle.evals` (UG-4, enmienda del 2026-09-17).
- Los contratos de `import-linter` nacen aquí con las capas y reglas de ADR-001 (enmienda del 2026-09-17), y cada unidad agrega su módulo al contrato.
- Cada unidad agrega sus rutas a la raíz de composición cuando se construye; la raíz no importa unidades que todavía no existen.
- Escaneo de secretos con gitleaks como primer trabajo del flujo y negación `!.env.example` en el `.gitignore` (`team.md`, Secretos). La protección de inserción de GitHub no existe en repositorios privados de cuenta personal: se activa al publicar el repositorio (ADR-002, enmienda del 2026-09-17).

**Dónde vive en el código**

- `app/backend/src/untangle/server/` (raíz de composición)
- `app/backend/src/untangle/copy_catalog/`
- `app/backend/src/untangle/evals/runner/`
- `app/config/copy/`
- `app/evals/` (casos por archivo)
- `scripts/verify.sh`, `.github/workflows/`, archivo de tareas y servicios locales en la raíz

### U2 — tenancy: Aseguradoras e identidad

Configuración versionada por aseguradora, punto único de sesión con la aseguradora fijada, RLS con su aserción de esquema, credenciales firmadas, enlaces de un caso, clave del navegador y la definición de qué es un dato de visitante.

- **Directorio de Construcción:** `u2-tenancy`
- **Tipo:** `library`. Lógica de aislamiento, configuración e identidad que usan las demás unidades dentro del proceso, sin un tiempo de ejecución propio.
- **Complejidad relativa:** L
- **Rama de pruebas:** evaluada. Realiza M9; sus casos previos son RT-4 de DS-6 y las colisiones de DS-8.
- **Despliegue:** Embebida en el proceso único del aplicativo.
- **Componentes:** TenantIdentity (completo, más el contrato de borrado de datos de visitante de la decisión UG-3).
- **Historias:** US4.11, US5.7.
- **Depende de:** U1 `workspace` (andamiaje, corredor y reglas de importación).
- **Datos de visitante:** define el contrato de borrado (UG-3) y lo implementa para sus claves de navegador y enlaces firmados, con su prueba.

**Contiene**

- Cargador y validación de las carpetas de configuración por aseguradora
- Punto único de sesión de base de datos, políticas RLS y la aserción que falla si una tabla carece de ellas
- Tokens firmados por aseguradora y rol, enlaces firmados de una hora y la clave del navegador en cookie
- Definición de dato de visitante (origen y clave del navegador) y el contrato de borrado que implementa cada dueño

**No contiene**

- El reinicio nocturno que ejecuta el contrato (U20)
- Las vistas de la bandeja que abren los enlaces (U14)

**Responsabilidades**

- Aislar cada consulta por aseguradora en la base de datos y no solo en el código
- Emitir y validar credenciales y enlaces, y responder igual ante un caso ajeno que ante uno inexistente
- Declarar en un solo lugar qué dato es de un visitante

**Notas de implementación y restricciones**

- Módulo crítico con piso de cobertura del 80 % propio (`team.md`).
- El rol del aplicativo no puede saltarse RLS; la aserción de esquema incluye las tablas que agreguen las demás unidades, incluidas las de puntos de control (PA-3, que resuelve U12).
- Las credenciales se generan con un guion para Miguel, el despliegue local y las pruebas, y nunca se publican (D23).
- Un chequeo prohíbe `tenant_id` literales fuera del cargador y de las fixtures.

**Dónde vive en el código**

- `app/backend/src/untangle/tenancy/`
- `app/config/tenants/<aseguradora>/`

### U3 — pii-redaction: Redacción de datos personales

Presidio con reconocedores propios para placa, cédula, teléfono y número de póliza en los dos idiomas, como única vía hacia transcripción, logs, trazas, exportaciones, reporte y transcripción en vivo.

- **Directorio de Construcción:** `u3-pii-redaction`
- **Tipo:** `library`. Detector sin red ni modelo que las demás unidades usan como único camino hacia una salida.
- **Complejidad relativa:** M
- **Rama de pruebas:** evaluada. Realiza M6; sus casos previos son RT-14 y RT-15 de DS-6, medidos por idioma y por tipo de entidad.
- **Despliegue:** Embebida en el proceso único; los modelos de spaCy en español e inglés viajan con el despliegue.
- **Componentes:** PiiRedaction (completo).
- **Historias:** US4.12, US4.13.
- **Depende de:** U1 `workspace` (andamiaje y corredor).

**Contiene**

- Reconocedores por idioma y por tipo de entidad
- El punto único de redacción y los tipos de salida que solo aceptan contenido redactado

**No contiene**

- El segundo detector, de otro mecanismo, que vive en U21 y no importa esta unidad

**Responsabilidades**

- Reemplazar cada dato personal por una etiqueta de su tipo
- Hacer imposible por construcción una salida sin redacción

**Notas de implementación y restricciones**

- No depende de la red ni de modelos de lenguaje (ADR-013).
- La medición se publica por idioma y por tipo de entidad, nunca como promedio.

**Dónde vive en el código**

- `app/backend/src/untangle/compliance/redaction/`

### U4 — case-record: Registro del caso

Esquema por tipo de registro, estado y evidencia por campo, completitud, modelo cerrado de estados, número legible, historial de cambios y transcripción redactada.

- **Directorio de Construcción:** `u4-case-record`
- **Tipo:** `library`. Esquema, estados e historial del caso, usados por nodos, bandeja y operación dentro del proceso.
- **Complejidad relativa:** L
- **Rama de pruebas:** evaluada. Realiza M1; sus casos previos son de DS-2 con el estado y la resolución finales en el registro esperado.
- **Despliegue:** Embebida en el proceso único.
- **Componentes:** CaseRecord (completo, salvo el esquema de la solicitud de cotización, que agrega U19).
- **Historias:** US4.10, US1.8, US1.14.
- **Depende de:** U1 `workspace` (andamiaje y corredor); U2 `tenancy` (punto único de sesión y RLS); U3 `pii-redaction` (redacta cada turno antes de guardarlo).
- **Datos de visitante:** guarda datos de visitantes, así que implementa el contrato de borrado de U2 con su prueba (UG-3).

**Contiene**

- Esquema de siniestro y de consulta de cobertura con la correspondencia entre bloques y campos en un archivo versionado
- Estado por campo `not_stated`, `stated` o `confirmed` con el turno que lo respalda
- Tabla versionada de transiciones con la única vuelta de `derived` a `capturing`
- Número de caso, historial de cambios y cierre solo con la evidencia de los adjuntos

**No contiene**

- Aplicar las transiciones del grafo (U12)
- El esquema de la solicitud de cotización (U19)

**Responsabilidades**

- Ser la fuente de verdad del caso
- Rechazar toda transición no declarada dejando un evento

**Notas de implementación y restricciones**

- Módulo crítico con piso de cobertura del 80 % propio.
- La vuelta de `derived` a `capturing` se prueba con reloj inyectado en 14:59 y 15:01 (ADR-005).
- El mecanismo de cifrado en reposo lo fija `nfr-requirements` (PA-8).

**Dónde vive en el código**

- `app/backend/src/untangle/case_record/`

### U5 — provider-platform: Proveedores de modelo, gasto y trazas

Todo lo que cuesta dinero o sale a un proveedor de modelo: la llamada, su costo con precio de lista, el techo con corte, las cuotas de la demo y la traza con las convenciones GenAI.

- **Directorio de Construcción:** `u5-provider-platform`
- **Tipo:** `service`. Corre el corte de gasto, los límites de proveedor y la exportación de trazas del proceso, con metas propias de confiabilidad y de observabilidad.
- **Complejidad relativa:** L
- **Rama de pruebas:** determinista. Sus historias no realizan M1, M4, M5, M6, M8, M9, M13 ni M15.
- **Despliegue:** Embebida en el proceso único; Langfuse corre en local con los servicios del repositorio y el destino público de las trazas lo decide el intent `infra`.
- **Componentes:** ProviderGateway (parte: interfaces de generar texto y de embeddings, adaptador de Gemini, fábrica de clientes por uso, taxonomía de errores y pruebas de contrato); UsageBudget (completo); Telemetry (completo en el servidor; las pantallas de gasto y cifras están en U22 y el resumen de traza del chat en U13).
- **Historias:** US4.8, US5.14.
- **Depende de:** U1 `workspace` (andamiaje y reglas de importación); U2 `tenancy` (sesión para el registro de gasto y los resúmenes de traza); U3 `pii-redaction` (la exportación de trazas pasa por la redacción).
- **Datos de visitante:** guarda datos de visitantes, así que implementa el contrato de borrado de U2 con su prueba (UG-3).

**Contiene**

- Adaptador de Gemini (`gemini-3.1-flash-lite` y `gemini-embedding-001` a 768 dimensiones) detrás de interfaces propias
- Fábrica de clientes por uso (voz, chat, evaluaciones y operación) con su clave y su tope
- Registro de gasto con tabla versionada de precios, alerta en 3 USD y techo de 5 USD en la ventana de 90 días desde el 2026-09-16
- Contadores de cuota con reloj y zona horaria configurables, reserva de la voz principal y tabla de topes configurados en cada proveedor
- Trazas OpenTelemetry por turno, nodo y proveedor, y resúmenes de traza por navegador

**No contiene**

- Transcripción y síntesis (U15)
- Paneles de gasto y de cifras (U22)

**Responsabilidades**

- Detenerse sin reintentar ante saldo o cuota agotados
- Registrar costo "no medido" cuando falta el precio, nunca cero
- Mantener el corte de gasto aunque falle la observación

**Notas de implementación y restricciones**

- Planes y claves por uso de ADR-006: chat público, evaluaciones y generación en plan gratuito; voz en plan de pago prepagado sin recarga automática, activado solo cuando la voz se publique.
- Qué sustituye el tope por clave donde el proveedor no lo tiene (PA-9) lo fija `nfr-requirements`.
- Las pruebas de límites no consumen el presupuesto que protegen: clave de prueba de tope mínimo y acumulado forzado (`project.md`).
- El registro de gasto no guarda datos personales y sobrevive al reinicio nocturno.

**Dónde vive en el código**

- `app/backend/src/untangle/providers/` (adaptador de modelo y fábrica)
- `app/backend/src/untangle/telemetry/traces/` y `telemetry/spend/`
- `app/config/providers/`

### U6 — web-shell: Base de la aplicación web y del proceso servido

Lo común a todas las pantallas y lo que el proceso servido hace por ellas: tokens y temas de las maquetas aprobadas, cliente de la API, selector de idioma, inicio, páginas de estado y la revisión de accesibilidad que usan las unidades con pantallas.

- **Directorio de Construcción:** `u06-web-shell`
- **Tipo:** sin tipo. Une la parte servida del proceso (origen único, cabeceras, salud, páginas de espera) con la base de la interfaz; ningún tipo solo le queda bien.
- **Complejidad relativa:** L
- **Rama de pruebas:** determinista. Sus historias son deterministas (D16 y NFR16).
- **Despliegue:** Archivos estáticos compilados y servidos desde el mismo origen que la API (compartido); la parte servida corre embebida en el proceso único.
- **Componentes:** WebClient (parte: sistema de diseño, modos claro y oscuro, navegación, cliente tipado de la API, textos por idioma, página de inicio, páginas de estado y arnés de accesibilidad); Composición del servidor (parte servida: archivos estáticos desde el mismo origen, cabeceras de seguridad y endpoints para el chequeo periódico).
- **Historias:** US1.33, US5.16.
- **Depende de:** U1 `workspace` (andamiaje de TypeScript, catálogo y raíz de composición); U2 `tenancy` (salud de la base de datos y política de la cookie del navegador); U5 `provider-platform` (telemetría de activación sin datos personales).

**Contiene**

- Sistema de diseño portado de la maqueta aprobada con Tailwind y shadcn/ui, y modos claro y oscuro con selector
- Rutas y datos con TanStack Router y Query, cliente tipado generado desde OpenAPI y módulo tipado de claves del catálogo
- Página de inicio y páginas de estado: la demo está despertando, no disponible, enlace vencido y página no encontrada
- Arnés de accesibilidad (axe, recorrido con teclado y 360 × 640 px) que corre cada pantalla visitable
- Cabeceras de seguridad, archivos estáticos desde el mismo origen y endpoints de salud para el chequeo periódico

**No contiene**

- Las pantallas de cada capacidad (U13, U14, U16, U17, U22)

**Responsabilidades**

- Que ninguna pantalla imponga su tema ni salte de un modo al otro
- Mostrar la página de espera en menos de 3 segundos con la instancia dormida

**Notas de implementación y restricciones**

- El cobre de la marca nunca va como texto sobre fondo claro; ahí se usa la tinta #9A4F12 (`project.md`).
- La página de espera exige servir los estáticos desde un hospedaje que no se duerme: lo decide el intent `infra` (OQ4); el origen del chequeo periódico y el canal de alertas también (PA-10).
- La lista de navegadores declarados (PA-4) se fija en `nfr-requirements` de esta unidad con el dato de WebRTC del experimento 1.
- La política de seguridad de contenido se define en NFR Design (ADR-002). El navegador no guarda datos de casos más allá de la sesión.

**Dónde vive en el código**

- `app/frontend/src/shared/`
- `app/backend/src/untangle/server/` (parte servida)

### U7 — synthetic-data: Generador de datos sintéticos

Textos fuente redactados una vez y revisados a mano, y composición determinista y sembrada de corpus, pólizas emitidas, casos en cada estado, fixtures de aislamiento y guiones de golden sets.

- **Directorio de Construcción:** `u7-synthetic-data`
- **Tipo:** `library`. Generador que se invoca por comando y produce datos versionados; no corre en el proceso servido.
- **Complejidad relativa:** L
- **Rama de pruebas:** determinista. Sus historias son deterministas (M3 no está entre los Must de la rama evaluada).
- **Despliegue:** Herramienta de línea de comandos; su salida se versiona en el repositorio y no se despliega.
- **Componentes:** SyntheticData (completo).
- **Historias:** US5.3, US5.4, US5.5, US5.6.
- **Depende de:** U1 `workspace` (chequeos de contenido y comando del archivo de tareas); U2 `tenancy` (carpetas de configuración por aseguradora); U4 `case-record` (esquema de los casos sembrados); U5 `provider-platform` (redacción única de los textos fuente con el modelo en plan gratuito).

**Contiene**

- Textos fuente por tipo, aseguradora e idioma
- Composición determinista con manifiesto de hashes
- Relaciones entre cláusulas (`clause_relation`) y encabezado estructural de cada cláusula, generados junto al corpus (ADR-010, enmienda del 2026-09-17)
- Corpus de Stonecroft Mutual en español, de Sunmeadow Auto en inglés y copias de Knotwell en el idioma de cada emisora
- Un caso en cada estado, DS-8 con colisiones a propósito y valores personales ficticios que alimentan los canarios

**No contiene**

- La ingesta del corpus en la base (U8)
- El aprovisionamiento de una aseguradora (U20)

**Responsabilidades**

- Producir bytes idénticos con la misma semilla
- Regenerar solo con un comando explícito

**Notas de implementación y restricciones**

- Miguel revisa una muestra de textos fuente por idioma: es una dependencia humana de la unidad.
- La salida pasa los chequeos de contenido: estructura inspirada, nunca texto de cláusula de ISO o ACORD (P8).
- Los formatos de archivo del corpus y de los casos los fija Contract Design.

**Dónde vive en el código**

- `app/backend/src/untangle/synthetic_data/`
- `app/data/` (salida versionada)

### U8 — policy-rag: Pólizas, recuperación y citas verificadas

Ingesta con una cláusula por fragmento, índice híbrido por aseguradora, verificador exacto de citas y el nodo que responde cobertura solo con cláusulas verificadas.

- **Directorio de Construcción:** `u8-policy-rag`
- **Tipo:** `library`. Corpus, verificador y nodo de cobertura: lógica usada por el grafo dentro del proceso.
- **Complejidad relativa:** XL
- **Rama de pruebas:** evaluada. Realiza M4 y M9; sus casos previos son de DS-3 con distractores y las preguntas sin cláusula.
- **Despliegue:** Embebida en el proceso único; el índice vive en PostgreSQL con pgvector.
- **Componentes:** PolicyCorpus (completo); CitationVerifier (completo); PolicyVerificationNode (completo).
- **Historias:** US5.2, US2.1, US2.8, US2.2, US2.5, US2.6, US2.7.
- **Depende de:** U1 `workspace` (catálogo y corredor); U2 `tenancy` (sesión, RLS y carpeta del corpus); U4 `case-record` (respuestas y comprobaciones pertenecen a un caso); U5 `provider-platform` (embeddings y segunda pasada del modelo); U7 `synthetic-data` (corpus DS-1 y pólizas emitidas para los casos de DS-3).
- **Datos de visitante:** guarda datos de visitantes, así que implementa el contrato de borrado de U2 con su prueba (UG-3).

**Contiene**

- Ingesta de formularios, endosos, jurisdicción y distractores, y pólizas emitidas con sus declaraciones
- Índice léxico y vectorial fusionado por rango recíproco, filtrado por aseguradora y póliza antes de ordenar
- Verificador con resultados `verified`, `rejected`, `no_clause_found` y `unverifiable`, que rechaza la cita cuando un endoso vigente modifica la cláusula citada y la respuesta no lo considera (ADR-011, enmienda del 2026-09-17)
- Cierre por relaciones entre cláusulas tras la fusión: endosos vigentes de la póliza y definiciones que la respuesta necesita (ADR-010)
- Registro idempotente de `CoverageAnswer` por caso y turno en CitationVerifier
- Nodo `policy_verification` puro, con la forma de la cita por canal e idioma

**No contiene**

- La ejecución de fondo y la precarga del nodo (U12)
- La cita expandible en pantalla (U13)

**Responsabilidades**

- Nunca devolver una cláusula de otra aseguradora
- Distinguir "no encuentro una cláusula" de "no pude verificar"
- Bloquear la entrega ante una cita emitida sin `verified`

**Notas de implementación y restricciones**

- CitationVerifier es módulo crítico con piso de cobertura del 80 % propio.
- El texto recuperado entra como dato delimitado, nunca como instrucción (RT-2).
- Cambiar el modelo de embeddings reconstruye el índice y pasa la compuerta de evaluación (ADR-010).
- El código del nodo vive en el directorio de su token (convención 3) aunque se construya en esta unidad.
- El nodo no escribe en la base de datos: LangGraph lo vuelve a ejecutar completo al reanudar tras `interrupt()`, así que la persistencia la hace CitationVerifier con clave idempotente (ADR-003, enmienda del 2026-09-17).
- La búsqueda vectorial es exacta, sin índice HNSW, mientras el corpus sea pequeño (ADR-010).

**Dónde vive en el código**

- `app/backend/src/untangle/policy_rag/corpus/` y `policy_rag/citations/`
- `app/backend/src/untangle/orchestration/nodes/policy_verification/`

### U9 — rules-decision: Motor de reglas y nodo de decisión

Entre 10 y 20 reglas versionadas por aseguradora, cada una con su prueba, evaluadas sin el modelo, y el nodo que escribe la categoría con sus reglas disparadas.

- **Directorio de Construcción:** `u9-rules-decision`
- **Tipo:** `library`. Evaluación determinista de reglas y el nodo que la invoca, sin tiempo de ejecución propio.
- **Complejidad relativa:** M
- **Rama de pruebas:** evaluada. Realiza M5; sus casos previos son de DS-2 con la categoría y la derivación esperadas por aseguradora.
- **Despliegue:** Embebida en el proceso único; las reglas viven en la configuración versionada de cada aseguradora.
- **Componentes:** RulesEngine (completo, salvo las reglas de elegibilidad y la banda de cotización, que agrega U19); DecisionNode (completo).
- **Historias:** US1.15, US1.17.
- **Depende de:** U1 `workspace` (corredor y claves de explicación del catálogo); U2 `tenancy` (reglas por aseguradora y sesión); U4 `case-record` (el nodo escribe la categoría y su explicación en el caso).
- **Datos de visitante:** guarda datos de visitantes, así que implementa el contrato de borrado de U2 con su prueba (UG-3).

**Contiene**

- Carga y validación de reglas versionadas
- Evaluación con categoría, reglas disparadas, insumos y clave de explicación
- Nodo `decision`

**No contiene**

- Elegibilidad y banda de cotización (U19)

**Responsabilidades**

- Que ninguna categoría pase por el modelo
- Que la agencia derive siempre por su regla, sin rama de código

**Notas de implementación y restricciones**

- RulesEngine es módulo crítico con piso de cobertura del 80 % propio.
- Un cambio en los archivos de reglas dispara la compuerta de evaluación (U21, US5.9).

**Dónde vive en el código**

- `app/backend/src/untangle/rules/`
- `app/backend/src/untangle/orchestration/nodes/decision/`
- `app/config/tenants/<aseguradora>/rules/`

### U10 — compliance: Controles de cumplimiento y nodo de cierre

Los tres controles baratos del turno (guardia de salida, petición de persona y emergencia), el registro de la divulgación, la revisión completa al cierre y el nodo que cierra o deriva con su motivo.

- **Directorio de Construcción:** `u10-compliance`
- **Tipo:** `library`. Controles que se prueban sin grafo y el nodo que cierra o deriva, usados dentro del proceso.
- **Complejidad relativa:** L
- **Rama de pruebas:** evaluada. Realiza M6; sus casos previos son de DS-2 (petición de persona, heridos graves, emoción) y de DS-6 (RT-1, RT-2, RT-3, RT-5, RT-6, RT-8, RT-15).
- **Despliegue:** Embebida en el proceso único.
- **Componentes:** ComplianceControls (completo); ComplianceNode (completo).
- **Historias:** US1.10, US1.9, US1.6, US1.11, US4.15, US1.16.
- **Depende de:** U1 `workspace` (catálogo de frases permitidas y corredor); U2 `tenancy` (políticas por aseguradora y sesión); U3 `pii-redaction` (comprueba que lo exportable esté redactado); U4 `case-record` (lee la conversación y cierra o deriva el caso); U5 `provider-platform` (clasificación de la revisión completa cuando las reglas no bastan).
- **Datos de visitante:** guarda datos de visitantes, así que implementa el contrato de borrado de U2 con su prueba (UG-3).

**Contiene**

- Guardia de salida con sustitución por frase del catálogo
- Detección de petición de persona en cualquier idioma y de emergencia
- Registro de la divulgación y revisión de los cuatro controles al cierre
- Nodo `compliance`

**No contiene**

- El punto único de salida que aplica los controles en cada turno (U12)

**Responsabilidades**

- Que ninguna salida afirme cobertura, montos ni culpa sin pasar por la bandeja
- Que el texto de la persona entre como dato delimitado

**Notas de implementación y restricciones**

- El presupuesto de latencia de cada control del turno (PA-7) lo fija `nfr-requirements` de U12, que es donde se aplican.
- En las superficies públicas la indicación de emergencia dice que es una demostración y no puede enviar ayuda (D14).
- La regla del proyecto que prohíbe trabajo de cumplimiento en el turno quedó desactualizada por D22 (PA-13).

**Dónde vive en el código**

- `app/backend/src/untangle/compliance/controls/`
- `app/backend/src/untangle/orchestration/nodes/compliance/`
- `app/config/tenants/<aseguradora>/compliance/`

### U11 — intake: Nodo de captura

Identifica a la persona contra la póliza emitida, extrae solo lo dicho con su evidencia, normaliza lo dictado, pregunta en el orden fijo de la guía y lee la confirmación de cada bloque.

- **Directorio de Construcción:** `u11-intake`
- **Tipo:** `library`. Nodo con contrato de entrada y salida que se prueba sin el grafo.
- **Complejidad relativa:** L
- **Rama de pruebas:** evaluada. Realiza M1; sus casos previos son de DS-2 (orden del relato, correcciones, emoción) y de DS-6 (RT-4, RT-7, RT-9, RT-11).
- **Despliegue:** Embebida en el proceso único.
- **Componentes:** IntakeNode (completo, salvo la captura de la solicitud de cotización, que agrega U19).
- **Historias:** US1.3, US1.5, US1.7, US1.4, US1.12, US1.13.
- **Depende de:** U1 `workspace` (catálogo de preguntas y lecturas, y corredor); U4 `case-record` (lee y escribe campos, partes y confirmaciones); U5 `provider-platform` (extracción y redacción con el modelo); U8 `policy-rag` (busca la póliza emitida para identificar a la persona). **No depende de U9 `rules-decision`** (corrección del 2026-09-19): la captura corre dentro del turno y las reglas corren de fondo; la derivación que piden US1.4 y US1.12 la produce el nodo de decisión después, y su aceptación se verifica de punta a punta.

**Contiene**

- Identificación sin revelar datos ajenos
- Extracción con estado por campo y normalización de fechas, placas, pólizas, cédulas y teléfonos
- Orden de preguntas, confirmación por bloque y deletreo de letras confundibles
- Dos versiones de lo que pasó y trato con calma

**No contiene**

- La conversación por canal (U13 y U16)
- La cotización (U19)

**Responsabilidades**

- Confirmar lesiones, conductor y lugar antes de anotarlos
- Nunca afirmar cobertura, montos ni culpa

**Notas de implementación y restricciones**

- Presupuesto de unos 3.900 tokens de entrada por turno de voz (ADR-006); prompts versionados en el repositorio.
- El texto de la persona entra como campo delimitado, nunca en la posición de instrucción.
- La rúbrica de estilo de AC1.13.5 se registra como objetivo medible en `nfr-requirements` (PA-12).

**Dónde vive en el código**

- `app/backend/src/untangle/orchestration/nodes/intake/`

### U12 — graph-runtime: Runtime del grafo

LangGraph con estado tipado, transición pura con enumeración cerrada, ejecutor común de la política de fallo, dos ritmos con precarga y frase de espera, puntos de control, pausa hacia la bandeja y punto único de salida.

- **Directorio de Construcción:** `u12-graph-runtime`
- **Tipo:** `service`. Lleva los dos ritmos, los puntos de control y la reanudación del proceso, con metas propias de latencia y confiabilidad.
- **Complejidad relativa:** L
- **Rama de pruebas:** evaluada. Realiza M4 con US2.4; su caso previo es el eje de DS-2 con pregunta de cobertura durante el reporte. El resto se prueba por la rama determinista con fallos y retardos inyectados.
- **Despliegue:** Embebido en el proceso único; el trabajo de fondo corre como tareas asíncronas del mismo proceso, sin broker (ADR-004).
- **Componentes:** Orchestration (completo).
- **Historias:** US4.9, US1.19, US1.25, US2.4, US2.10.
- **Depende de:** U1 `workspace` (frases de espera y de degradación, y corredor); U2 `tenancy` (sesión para puntos de control y configuración); U4 `case-record` (crea el caso y aplica transiciones); U5 `provider-platform` (tramos por turno y por nodo); U8 `policy-rag` (nodo `policy_verification`); U9 `rules-decision` (nodo `decision`); U10 `compliance` (nodo `compliance` y controles en el punto único de salida); U11 `intake` (nodo `intake`).
- **Datos de visitante:** guarda datos de visitantes, así que implementa el contrato de borrado de U2 con su prueba (UG-3).

**Contiene**

- Estado tipado compuesto desde los contratos que declara cada nodo
- Función de transición pura y ejecutor de la política de fallo
- Ritmo del turno y ritmo de fondo con `NodeRun` y relanzamiento tras la muerte del proceso
- Puntos de control por caso, `interrupt()` hacia la bandeja, reanudación y retiro de la pausa
- Punto único de salida con los tres controles del turno, también para degradación y error
- La interfaz de turnos que usan los canales

**No contiene**

- Los nodos (U8, U9, U10, U11)
- El transporte de cada canal (U13 y U16)

**Responsabilidades**

- Que el turno nunca espere al trabajo de fondo
- Que ningún cliente de modelo esté en la cadena de la transición
- Reanudar sin repetir preguntas confirmadas

**Notas de implementación y restricciones**

- Solo esta unidad importa LangGraph, con versión fijada en el lockfile (ADR-003).
- PA-3: el checkpointer oficial de LangGraph toma conexiones en autocommit, así que la aseguradora fijada por transacción en el punto único de sesión no lo cubre. Functional Design de esta unidad elige entre un pool por aseguradora que fija la variable de sesión y un checkpointer propio que envuelve cada operación en una transacción; en los dos casos, columna de aseguradora, RLS y `FORCE ROW LEVEL SECURITY`, con una prueba que intenta leer un checkpoint de otra aseguradora (ADR-003, enmienda del 2026-09-17).
- `NodeRun` lleva arrendamiento con latido y un barrido al arrancar relanza lo pendiente sin duplicar gasto; el turno de voz hace una sola llamada al modelo y el trabajo de CPU va fuera del event loop (ADR-004, enmienda del 2026-09-17).
- PA-7, presupuesto de latencia de los tres controles del turno, en `nfr-requirements` de esta unidad.
- Las escrituras concurrentes al estado se diseñan en Functional Design, apoyadas en los conjuntos de escritura por nodo (ADR-004).

**Dónde vive en el código**

- `app/backend/src/untangle/orchestration/` (salvo `nodes/`)

### U13 — chat: Chat público y vista de comparación

La conversación de texto sobre el mismo grafo, con divulgación y aviso de no escribir datos reales antes de cualquier texto del visitante, límites con modo degradado, retoma por navegador, decisiones del ajustador, comparación entre aseguradoras y el conductor de texto de las evaluaciones.

- **Directorio de Construcción:** `u13-chat`
- **Tipo:** sin tipo. Canal servido con metas de latencia y sus pantallas; mezcla servicio e interfaz.
- **Complejidad relativa:** XL
- **Rama de pruebas:** evaluada. Realiza M6 y la adherencia de idioma del PRD 11.2; sus casos previos son de DS-2 por el canal chat y RT-10 de DS-6.
- **Despliegue:** Endpoints con streaming embebidos en el proceso único y pantallas compiladas servidas desde el mismo origen.
- **Componentes:** ChatChannel (completo); WebClient (parte: página de chat por aseguradora, cita expandible con resumen de traza y vista de comparación).
- **Historias:** US1.1, US1.2, US5.13, US1.18, US2.3, US1.20.
- **Enmienda del 2026-09-28 (decisión de Miguel, Q1 del diseño funcional de U13):**
  US2.9 sale de esta unidad y pasa a **U23 `comparison-view`**, declarada después de
  U14. La razón no fue el tiempo: la vista de comparación convence cuando hay casos
  reales detrás, y hasta que exista la bandeja solo hay tres pólizas de ejemplo que
  comparar. U13 pasa de siete historias a seis, y de dos Should a uno.
- **Depende de:** U1 `workspace` (conductor de texto para el corredor y catálogo); U2 `tenancy` (clave del navegador, póliza de ejemplo y sesión); U5 `provider-platform` (límites de mensajes y resúmenes de traza); U6 `web-shell` (base visual y cliente de la API); U12 `graph-runtime` (entrega turnos y recibe salidas).
- **Datos de visitante:** guarda datos de visitantes, así que implementa el contrato de borrado de U2 con su prueba (UG-3).

**Contiene**

- Streaming por SSE, sesión del chat y retoma solo con la sesión del navegador o el enlace firmado
- Límites por sesión y por día con mensaje honesto
- Pantalla de chat con selector de idioma, cita expandible y resumen de traza
- Vista de comparación con la misma pregunta en las tres aseguradoras
- Conductor de texto que registra en el corredor de evaluaciones

**No contiene**

- El grafo (U12)
- La vista de caso por enlace (U14)

**Responsabilidades**

- Responder igual ante un caso ajeno que ante uno inexistente
- Mostrar en superficies públicas solo recuentos, nunca números de casos de visitantes

**Notas de implementación y restricciones**

- El aviso de no escribir datos reales va antes de cualquier texto del visitante porque el chat público usa el plan gratuito (ADR-006, riesgo aceptado en Q5 de Domain Design).
- US1.20 (Should S2) es la historia que la regla de corte del PRD puede quitar de esta unidad. US2.9 (Should S5) ya salió: es de U23 desde el 2026-09-28.
- Desde esta unidad, los casos de conversación de DS-2 y DS-6 corren por el adaptador de texto del canal (ADR-014).

**Dónde vive en el código**

- `app/backend/src/untangle/chat/`
- `app/frontend/src/modules/chat/`

### U14 — inbox: Bandeja y vistas de caso

La persona en el ciclo: cola por aseguradora con filtros, vista con toda la evidencia, corrección con rastro, decisión con comentario que reanuda el grafo y acceso de un visitante a su propio caso por enlace firmado.

- **Directorio de Construcción:** `u14-inbox`
- **Tipo:** sin tipo. Endpoints de la bandeja con permisos y sus pantallas; mezcla servicio e interfaz.
- **Complejidad relativa:** XL
- **Rama de pruebas:** evaluada. Realiza M9, M6 y M5; sus casos previos son RT-4 de DS-6 con colisiones de DS-8, un caso derivado de DS-2 con su explicación y casos de Knotwell de DS-2.
- **Despliegue:** Endpoints embebidos en el proceso único y pantallas compiladas servidas desde el mismo origen.
- **Componentes:** Inbox (completo, salvo la decisión de solicitudes de cotización, que agrega U19); WebClient (parte: lista de casos, vista de caso con credencial y vista de caso por enlace).
- **Historias:** US3.1, US3.2, US3.3, US3.4, US3.5, US3.6, US3.7, US3.8.
- **Depende de:** U1 `workspace` (catálogo y corredor); U2 `tenancy` (credenciales, enlaces firmados y sesión); U4 `case-record` (lista, vista y corrección); U5 `provider-platform` (traza por nodo con costo y latencia); U6 `web-shell` (base visual y cliente de la API); U7 `synthetic-data` (un caso sembrado en cada estado); U8 `policy-rag` (citas verificadas y respuestas de cobertura); U9 `rules-decision` (evaluación de reglas con sus insumos); U10 `compliance` (resultado de los controles); U12 `graph-runtime` (reanuda el grafo con la decisión).
- **Datos de visitante:** guarda datos de visitantes, así que implementa el contrato de borrado de U2 con su prueba (UG-3).

**Contiene**

- Cola con filtros por estado, canal, idioma y prioridad, incluidos los casos que esperan al asegurado
- Vista de caso con completitud, transcripción, cláusulas, regla, controles y traza
- Corrección de campos y decisión con comentario obligatorio
- Actualización en tiempo real de la cola y de la vista de caso por SSE sobre `InboxEvent`, con reanudación por `Last-Event-ID` (ADR-021)
- Acción única de la agencia y recorrido completo del enlace firmado

**No contiene**

- La emisión y validación de enlaces y credenciales (U2)
- El enlace que entrega el chat o la consola al cerrar (U13 y U17)

**Responsabilidades**

- Que una credencial nunca vea casos de otra aseguradora
- Que un enlace abra solo su caso y nunca la lista (D6)

**Notas de implementación y restricciones**

- Interfaz bilingüe con selector, en inglés por defecto (D5); acciones rotuladas por tipo de registro (Refined Mockups).
- La vista de caso por enlace entra en la línea base de accesibilidad; la lista y la vista con credencial no (D25).
- El token del enlace sale de la dirección visible, de la cabecera `Referer` y de los registros (AC3.8.6).

**Dónde vive en el código**

- `app/backend/src/untangle/inbox/`
- `app/frontend/src/modules/inbox/`

### U15 — speech-providers: Adaptadores de transcripción y síntesis

Deepgram `nova-3` en modo `multi`, Cartesia `sonic-3.6` con Catalina y la voz de respaldo, cada uno detrás de su interfaz con prueba de formato y de latencia.

- **Directorio de Construcción:** `u15-speech-providers`
- **Tipo:** `library`. Adaptadores detrás de interfaces propias, sin tiempo de ejecución propio.
- **Complejidad relativa:** M
- **Rama de pruebas:** determinista. US5.10 es determinista.
- **Despliegue:** Embebida en el proceso único, o en el proceso de la voz si el experimento 1 lo exige.
- **Componentes:** ProviderGateway (parte: interfaces de transcribir en streaming y de sintetizar y transmitir, adaptadores de Deepgram, Cartesia y la voz de respaldo, y sus pruebas de contrato).
- **Historias:** US5.10.
- **Depende de:** U1 `workspace` (reglas de importación y comando de pruebas de contrato); U5 `provider-platform` (fábrica por uso, taxonomía de errores, registro de uso y techo).

**Contiene**

- Adaptador de transcripción con confianza por palabra
- Adaptador de síntesis principal y adaptador de la voz de respaldo
- Configuración de voz por aseguradora y su validación

**No contiene**

- La llamada que usa estos adaptadores (U16)

**Responsabilidades**

- Que cambiar proveedor, voz o modelo sea solo configuración
- Que una configuración rota apague la voz y deje vivo el chat

**Notas de implementación y restricciones**

- Espera al experimento 1: la voz de respaldo se elige ahí entre Deepgram Aura-2 y Kokoro (ADR-008).
- El precio de lista de `multi` en streaming se toma de la consola al construir el adaptador (ADR-007); nunca se agrega tarjeta sin la decisión de Miguel.
- La forma de la confianza por palabra en streaming se comprueba en Functional Design (PA-2, ADR-007).
- Se registran licencia y atribución de cada voz antes de publicar.

**Dónde vive en el código**

- `app/backend/src/untangle/providers/` (adaptadores de voz)
- `app/config/tenants/<aseguradora>/voice/`

### U16 — voice-call: Llamada de voz desde el navegador

La llamada completa por el navegador sobre el mismo grafo: conexión, apertura con divulgación, reporte hablado, parada ante interrupción en menos de 300 ms, silencios, retoma tras corte y eventos de latencia.

- **Directorio de Construcción:** `u16-voice-call`
- **Tipo:** sin tipo. Canal en tiempo real con metas de latencia y su consola; mezcla servicio e interfaz.
- **Complejidad relativa:** XL
- **Rama de pruebas:** evaluada. Realiza M13 y M6; sus casos previos son grabaciones de DS-5 en inglés, y lo que no cabe en DS-5 va con el reconocedor simulado.
- **Despliegue:** Embebida en el proceso único, o en un proceso de voz si la librería elegida lo exige (lo decide el experimento 1); la consola se sirve desde el mismo origen.
- **Componentes:** VoiceChannel (parte: sesión de llamada, audio a turnos, detección de turno, interrupciones, silencios, retoma tras corte, eventos de latencia y conductor de audio de DS-5); WebClient (parte: consola de llamada).
- **Historias:** US1.21, US1.22, US1.24, US1.23, US1.26, US1.27.
- **Depende de:** U1 `workspace` (conductor de audio para el corredor y catálogo); U2 `tenancy` (configuración de voz, clave del navegador y sesión); U5 `provider-platform` (eventos de latencia y registro de uso); U6 `web-shell` (base visual de la consola); U12 `graph-runtime` (entrega turnos y emite por el punto único de salida); U15 `speech-providers` (transcripción y síntesis en streaming).
- **Datos de visitante:** guarda datos de visitantes, así que implementa el contrato de borrado de U2 con su prueba (UG-3).

**Contiene**

- Integración con la librería de voz elegida y su transporte
- Detección de fin de turno, interrupción y retoma sin repetir
- Frases de silencio del catálogo y retoma de llamadas cortadas
- Consola con transcripción redactada y estado de la llamada
- Conductor de audio que registra en el corredor para DS-5 por hito

**No contiene**

- Límites públicos, voz de respaldo por presupuesto y avisos de la consola (U17)
- La capa en español y el cambio de idioma (U18)

**Responsabilidades**

- Que el grafo no importe nada de la librería de voz
- No guardar audio (NFR19)

**Notas de implementación y restricciones**

- Espera al experimento 1, que elige entre LiveKit Agents y Pipecat y actualiza ADR-009 antes de empezar.
- La definición del fin del habla (PA-6) la fija `nfr-requirements` de esta unidad; la latencia en plan de pago se mide con un gasto que decide Miguel (ADR-006).
- La apertura dice que la llamada queda transcrita, copiada literal de su criterio (D26).
- Las grabaciones de DS-5 son de personas reales: quedan fuera del repositorio y con consentimiento (D21).

**Dónde vive en el código**

- `app/backend/src/untangle/voice/`
- `app/frontend/src/modules/voice/`

### U17 — voice-public-link: Enlace público de la voz

Lo que hace publicable la voz: 3 minutos por llamada, 1 llamada al día desde la misma conexión y 15 en el sitio, aviso a los 30 segundos, derivación al límite con retoma en 15 minutos, voz de respaldo decidida antes de cada llamada y una consola que explica todo eso.

- **Directorio de Construcción:** `u17-voice-public-link`
- **Tipo:** sin tipo. Límites y presupuesto de la llamada pública con sus avisos en la consola; mezcla servicio e interfaz.
- **Complejidad relativa:** M
- **Rama de pruebas:** determinista. Sus historias son deterministas, con reloj inyectado y acumulados forzados.
- **Despliegue:** Embebida con la llamada; los mismos límites se configuran también en cada proveedor.
- **Componentes:** VoiceChannel (parte: límites de la llamada pública y ventana de retoma, elección de la voz antes de cada llamada y rechazo en el techo); WebClient (parte: avisos de límites, disponibilidad, voz de respaldo y enlace del caso en la consola).
- **Historias:** US5.12, US5.11, US4.17.
- **Depende de:** U1 `workspace` (catálogo); U2 `tenancy` (clave del navegador); U5 `provider-platform` (cuotas, reserva de la voz principal y techo); U16 `voice-call` (la llamada y su consola).
- **Orden de entrega:** se construye en la pasada de publicación, después de U18 `voice-spanish` (DP-14 de `bolt-plan.md`). No es una dependencia técnica: no usa nada de U18.

**Contiene**

- Límites en la aplicación y en el proveedor
- Elección de la voz principal o de respaldo según la reserva
- Avisos de la consola antes del micrófono

**No contiene**

- La llamada en sí (U16)

**Responsabilidades**

- Nunca cambiar de voz por presupuesto a mitad de llamada
- Rechazar llamadas nuevas en el techo con el mensaje del catálogo

**Notas de implementación y restricciones**

- Los topes en el proveedor se prueban con una clave de tope mínimo y la aplicación detenida, nunca agotando una clave real (`project.md`).
- La llamada del día se cuenta por conexión y la consola dice "desde esta conexión"; la retoma dentro de 15 minutos se reconoce por el mismo navegador; el techo de gasto no depende de ninguno de los dos, porque un visitante puede cambiar de navegador o de red (AC5.12.2, AC5.12.3 y AC5.12.6).
- La voz pública solo se publica con compuertas duras en verde y el checklist del segundo día (`team.md`, Deployment).
- La excepción de voz distinta por idioma en modo de respaldo se avisa en la consola (D17).

**Dónde vive en el código**

- `app/backend/src/untangle/voice/` (límites públicos)
- `app/frontend/src/modules/voice/` (avisos)

### U18 — voice-spanish: Voz en español y cambio de idioma

La segunda capa de la voz: la misma conducta y las mismas metas en español, con la misma voz, el cambio de idioma a mitad de llamada y la detección automática del cambio.

- **Directorio de Construcción:** `u18-voice-spanish`
- **Tipo:** `service`. Comportamiento en tiempo de ejecución de la llamada con las mismas metas de latencia por idioma.
- **Complejidad relativa:** L
- **Rama de pruebas:** evaluada. Realiza M15 y M6; sus casos previos son grabaciones de DS-5 en español con al menos tres voces paisas.
- **Despliegue:** Embebida con la llamada.
- **Componentes:** VoiceChannel (parte: apertura y conversación en español con la misma voz, cambio de idioma pedido y detección automática).
- **Historias:** US1.28, US1.29, US1.30, US1.31, US1.32.
- **Depende de:** U1 `workspace` (catálogo y corredor); U16 `voice-call` (la llamada, la interrupción y la retoma que se repiten en español).

**Contiene**

- Apertura y reporte en español con metas iguales
- Cambio de idioma pedido en los dos sentidos
- Detección automática del idioma mixto

**No contiene**

- La llamada base (U16)

**Responsabilidades**

- Reportar las metas por idioma, nunca como promedio

**Notas de implementación y restricciones**

- US1.32 (Should S4) es la última historia en la regla de corte del PRD.
- Catalina es provisional hasta la sesión de escucha de la semana 9 con tres personas de Medellín; si no pasa, se cambia por configuración (ADR-008).

**Dónde vive en el código**

- `app/backend/src/untangle/voice/` (idioma)

### U19 — quote: Cotización con elegibilidad

El flujo delgado de cotización sobre los mismos nodos: elegible, no elegible o derivación al suscriptor, con banda indicativa y sin importe.

- **Directorio de Construcción:** `u19-quote`
- **Tipo:** `library`. Extiende nodos, reglas y esquema existentes sin tiempo de ejecución propio.
- **Complejidad relativa:** M
- **Rama de pruebas:** evaluada. Su comportamiento está en la tabla del PRD 11.2 (extracción, reglas y alcance); sus casos previos son de DS-4 por idioma.
- **Despliegue:** Embebida en el proceso único.
- **Componentes:** IntakeNode (parte: captura de la solicitud); CaseRecord (parte: esquema y completitud de `quote_request`); RulesEngine (parte: reglas de elegibilidad y banda indicativa); DecisionNode (parte: categoría de cotización); Inbox (parte: decisión de solicitudes derivadas).
- **Historias:** US6.1, US6.2, US6.3.
- **Depende de:** U1 `workspace` (corredor); U4 `case-record` (tipo de registro `quote_request`); U7 `synthetic-data` (casos de DS-4); U9 `rules-decision` (reglas de elegibilidad); U11 `intake` (captura en la misma conversación); U12 `graph-runtime` (sin nodos nuevos); U14 `inbox` (decisión con comentario).

**Contiene**

- Captura de la solicitud en la misma conversación
- Reglas de elegibilidad y banda sin moneda
- Decisión de solicitudes derivadas en la bandeja

**No contiene**

- Tarifas o precios actuariales (fuera de alcance)

**Responsabilidades**

- Que ninguna respuesta contenga un importe
- Que el grafo no gane nodos

**Notas de implementación y restricciones**

- Should S1: segunda en la regla de corte del PRD; separarla en su unidad permite quitarla sin tocar trabajo Must.
- La agente ofrece cotizar solo si la aseguradora la tiene activa en su configuración (D4).

**Dónde vive en el código**

- Sin directorio propio: MOD-13 no tiene componente (Domain Design); sus piezas viven en los módulos dueños con el tipo de registro `quote_request`

### U20 — demo-operations: Operación de la demo

Aprovisionar una aseguradora desde su carpeta con un comando y borrar cada noche los datos de visitantes ejecutando el contrato de borrado de cada dueño, conservando el registro de gasto y dejando un registro de cada reinicio.

- **Directorio de Construcción:** `u20-demo-operations`
- **Tipo:** `service`. Operación programada con metas de confiabilidad y registro de cada corrida.
- **Complejidad relativa:** M
- **Rama de pruebas:** evaluada. US5.1 realiza M9; su caso previo es la batería de DS-8 también contra una cuarta aseguradora de prueba que no se publica.
- **Despliegue:** Comando de aprovisionamiento en el archivo de tareas y tarea nocturna cuyo disparador fija el intent `infra` (PA-10).
- **Componentes:** DemoOperations (completo, con el reinicio que ejecuta el contrato de borrado de la decisión UG-3).
- **Historias:** US5.1, US5.15.
- **Depende de:** U1 `workspace` (comando del archivo de tareas y corredor); U2 `tenancy` (configuración por aseguradora y contrato de borrado); U4 `case-record` (siembra de casos); U7 `synthetic-data` (fixtures y casos sembrados); U8 `policy-rag` (ingesta del corpus al aprovisionar).
- **Orden de entrega:** se construye en la pasada de publicación, después de U18 `voice-spanish` (DP-14 de `bolt-plan.md`). No es una dependencia técnica: no usa nada de U18.

**Contiene**

- Aprovisionamiento con ingesta del corpus
- Siembra de un caso en cada estado
- Reinicio nocturno por el contrato de borrado y `ResetRun`

**No contiene**

- El borrado de cada tabla, que implementa su dueño

**Responsabilidades**

- Que tras el reinicio no quede ningún dato de visitante, tampoco en el backend de trazas
- Que el registro de gasto sobreviva

**Notas de implementación y restricciones**

- El reinicio tiene que funcionar antes de publicar cualquier superficie pública (`team.md`, Deployment); por eso ejecuta el contrato y no conoce a cada dueño.
- Cada unidad dueña de datos de visitante trae su implementación del contrato y su prueba de borrado.

**Dónde vive en el código**

- `app/backend/src/untangle/demo_operations/`

### U21 — eval-gates: Compuertas y reporte de evaluación

Lo que convierte las corridas en compuerta: regresión por caso en los conjuntos pequeños, corridas no comparables y casos inestables, juez que solo cuenta calibrado, segundo detector independiente y reporte con los dos idiomas lado a lado.

- **Directorio de Construcción:** `u21-eval-gates`
- **Tipo:** sin tipo. Librería de compuertas que corre en la tubería sin tiempo de ejecución servido, pero con metas propias de la corrida (duración, determinismo, casos inestables y corridas no comparables) y con el registro de las metas de evaluación (UG-13); ningún tipo solo le queda bien, así que recibe la matriz completa de diseño.
- **Complejidad relativa:** L
- **Rama de pruebas:** evaluada. Realiza M8 sin conducta propia y M6 con el segundo detector; su caso previo es una corrida de casos ya existentes de DS-2, DS-3 y DS-6 que se comprueba que falla (`project.md`).
- **Despliegue:** Corre en local y en el flujo de GitHub Actions; no se despliega.
- **Componentes:** Evaluation (parte: reporte por caso, criterio e idioma con regresión contra la línea base, juez calibrado, segundo detector de datos personales y compuerta ante cambios de reglas).
- **Historias:** US4.5, US4.14, US4.6, US5.9.
- **Depende de:** U1 `workspace` (corredor de evaluaciones); U3 `pii-redaction` (lee su configuración versionada de reconocedores para comprobar que el segundo detector no comparte mecanismo ni reconocedores con el primero, AC4.14.1; la lee **como archivo** y no importa el módulo, porque compartir biblioteca rompería su independencia); U5 `provider-platform` (modelo juez y trazas exportadas); U7 `synthetic-data` (valores personales sembrados para los canarios); U9 `rules-decision` (la compuerta ante cambios de reglas se prueba con reglas reales).

**Contiene**

- Reporte por caso, criterio e idioma con diferencia contra la línea base
- Calibración del juez contra DS-7
- Segundo detector con canarios y formatos propios
- Compuerta cuando cambian los archivos de reglas

**No contiene**

- Panel de cifras y secciones del README (U22)

**Responsabilidades**

- Nunca promediar idiomas
- Declarar "no medida" una compuerta que no pudo correr

**Notas de implementación y restricciones**

- El segundo detector no importa U3: su mecanismo es distinto (ADR-013).
- Juez propio con prompts versionados por criterio, calibrado con TPR y TNR por criterio e idioma sobre la partición de prueba de DS-7 y con intervalo; pass^k por hito; red team con promptfoo por hito (ADR-014, enmienda del 2026-09-17 por decisión de Miguel).
- El subconjunto declarado si la corrida completa no cabe en 10 minutos o en el plan gratuito lo fija `nfr-requirements` (PA-11).
- Las etiquetas humanas de DS-7 las pone Miguel: dependencia humana de la unidad.
- Registra en su `nfr-requirements` las metas de NFR5, NFR7, NFR8, NFR13, NFR17 y NFR20, cada una con el comando de evaluación que produce su valor real (UG-13).

**Dónde vive en el código**

- `app/backend/src/untangle/evals/gates/`
- `app/evals/` (líneas base)

### U22 — public-evidence: Evidencia pública: panel de cifras, panel de gasto y README

Las cinco cifras con su fecha y su commit, el panel de gasto y las secciones del README que se generan desde el último reporte.

- **Directorio de Construcción:** `u22-public-evidence`
- **Tipo:** `ui`. Superficies de lectura para quien evalúa y para Miguel; la generación de secciones del README es un comando pequeño.
- **Complejidad relativa:** M
- **Rama de pruebas:** determinista. Sus historias son deterministas.
- **Despliegue:** Paneles compilados y servidos desde el mismo origen; las secciones del README se generan con un comando y se versionan.
- **Componentes:** Evaluation (parte: cinco cifras publicadas y secciones generadas del README); WebClient (parte: panel de cifras y panel de gasto).
- **Historias:** US4.16, US4.1.
- **Depende de:** U1 `workspace` (comando del archivo de tareas); U5 `provider-platform` (costos y trazas del panel de gasto); U6 `web-shell` (base visual de los paneles); U21 `eval-gates` (reporte del que salen las cifras y "Cómo falla").
- **Orden de entrega:** se construye en la pasada de publicación, después de U18 `voice-spanish` (DP-14 de `bolt-plan.md`). No es una dependencia técnica: no usa nada de U18.

**Contiene**

- Panel de cifras
- Panel de gasto por caso, proveedor, mes y ventana de 90 días
- Secciones generadas del README, incluida "Cómo falla"

**No contiene**

- El video y la landing, que no son unidades (US4.2 y US4.3)

**Responsabilidades**

- Mostrar solo recuentos y distribuciones, nunca identificadores de casos de visitantes
- No prometer capacidades que no están construidas (P7)

**Notas de implementación y restricciones**

- El README va en inglés con resumen en español (D24).

**Dónde vive en el código**

- `app/backend/src/untangle/evals/evidence/`
- `app/frontend/src/modules/evals/` y `app/frontend/src/modules/telemetry/`

### U23 — comparison-view: Vista de comparación entre aseguradoras

La misma pregunta de cobertura respondida por las tres aseguradoras lado a lado, cada
columna con sus cláusulas citadas y su propio estado de carga.

- **Directorio de Construcción:** `u23-comparison-view`
- **Tipo:** sin tipo. Una pantalla y el fan-out que la alimenta.
- **Complejidad relativa:** M
- **Rama de pruebas:** evaluada. Su compuerta dura se mide sobre las trazas de las tres columnas.
- **Despliegue:** Pantalla compilada servida desde el mismo origen.
- **Componentes:** WebClient (parte: vista de comparación).
- **Historias:** US2.9.
- **Depende de:** U13 `chat` (la respuesta de cobertura con su cita, que esta vista reúne); U14 `inbox` (los casos reales que le dan sentido); U8 `policy-rag` (el corpus por aseguradora).
- **Datos de visitante:** la pregunta del visitante entra por esta vista, así que implementa el contrato de borrado de U2 con su prueba (UG-3).

**Contiene**

- La divulgación y qué póliza de ejemplo usa cada columna, antes de la primera pregunta
- Tres respuestas en el idioma de la pregunta, cada una con sus cláusulas o con "no encuentro una cláusula"
- **Compuerta dura:** cada columna recupera solo del corpus de su aseguradora
- Carga por columna con fallo aislado, y la diferencia explicada por una cláusula citada

**No contiene**

- La conversación de chat (U13)
- La bandeja (U14)

**Origen**

Nace el 2026-09-28 de la decisión de Miguel en Q1 del diseño funcional de U13: la
vista salía del alcance de esa unidad porque convence cuando hay casos reales detrás.
Su semilla de reglas —cinco— quedó escrita en el archivo de preguntas de ese diseño.

## Reglas comunes a todas las unidades

Ninguna unidad queda a medias (práctica de Walking Skeleton). Además de sus
historias, una unidad no está terminada sin:

- Sus capas probadas según su rama y con el piso de cobertura del 80 % agregado; los módulos críticos (U2, U3, U4, U8 y U9) con su propio piso.
- Sus textos visibles como claves del catálogo en español y en inglés, sin cadenas en línea.
- Su módulo agregado a las reglas de importación y sus rutas montadas en la raíz de composición, si expone alguna.
- Sus tablas con política RLS y su prueba de aislamiento, y su implementación del contrato de borrado si guarda datos de visitantes.
- Sus objetivos de evaluación registrados en el corredor, si es de la rama evaluada.
- Sus metas medibles registradas en `nfr-requirements` con identificador, valor esperado y comando, en la unidad que indica la tabla "Requisitos no funcionales por unidad", para la matriz de Build and Test.

## Requisitos no funcionales por unidad

Cada requisito no funcional de `../requirements-analysis/requirements.md` se
registra una sola vez, en la unidad de la columna "Se registra en", para que
tenga una sola fila en la `## Target Verification Matrix` de Build and Test; las
demás unidades lo citan por su identificador (UG-13). El documento es el que esa
unidad produce en `nfr-requirements` según su tipo.

| NFR | Qué mide y valor esperado | Se registra en | Documento | También lo verifican |
| --- | --- | --- | --- | --- |
| NFR1 | Latencia del turno de voz, del fin del habla al primer audio: p50 menor que 500 ms y p95 menor que 800 ms, por idioma | U16 | `performance-requirements.md` | U18 (mismas metas en español) |
| NFR2 | Parada ante interrupción: menor que 300 ms | U16 | `performance-requirements.md` | U18 |
| NFR3 | Recuperación tras interrupción sin perder estado: mayor que 90 % | U16 | `reliability-requirements.md` | U18 |
| NFR4 | Latencia del chat, del envío a la primera palabra: p95 menor que 3 s | U13 | `performance-requirements.md` | — |
| NFR5 | Precisión de citación: 95 % o más | U21 | `reliability-requirements.md` | U8 (implementa la conducta) |
| NFR6 | Citas inexistentes: exactamente 0 (compuerta dura) | U8 | `security-requirements.md` | U21 (compuerta por caso) |
| NFR7 | Completitud del primer aviso en los siete campos: 95 % o más | U21 | `reliability-requirements.md` | U11 y U4 |
| NFR8 | Exactitud de extracción: 95 % o más por campo | U21 | `reliability-requirements.md` | U11 |
| NFR9 | Respuestas fuera de alcance: exactamente 0 (compuerta dura) | U10 | `security-requirements.md` | U21 |
| NFR10 | Fuga entre aseguradoras: 0 cláusulas ajenas y 100 % de pruebas de aislamiento en verde (compuerta dura) | U2 | `security-requirements.md` | U21 (DS-8), U8 y U14 |
| NFR11 | Datos personales en trazas, logs y exportaciones: 0 hallazgos (compuerta dura) | U3 | `security-requirements.md` | U21 (segundo detector) y U5 |
| NFR12 | Resistencia a los quince escenarios de red-team: 0 respuestas que obedezcan una instrucción inyectada (compuerta dura según `team.md`) | U10 | `security-requirements.md` | U21 (DS-6), U11 y U13 |
| NFR13 | Derivaciones: 100 % correctas y 10 % o menos innecesarias | U21 | `reliability-requirements.md` | U9 |
| NFR14 | Costo por caso exitoso, publicado por versión; voz de 0,02 USD o menos por llamada de cuatro minutos, con la meta del modelo de D7 | U5 | `performance-requirements.md` (restricción de recursos) | U16 (llamadas de DS-5) |
| NFR15 | Gasto acumulado: 5 USD o menos en 90 días, con alerta en 3 USD | U5 | `reliability-requirements.md` | U17 (corte de la voz) |
| NFR16 | Disponibilidad mensual del enlace en vivo: 95 % o más | U6 | `reliability-requirements.md` | Intent `infra` (chequeo periódico) |
| NFR17 | Duración de la corrida de evaluación de texto: 10 minutos o menos | U21 | `performance-requirements.md` | U1 (corredor) |
| NFR18 | Cobertura de líneas: 80 % o más agregado y en los cinco módulos críticos | U1 | `tech-stack-decisions.md` (comando y umbral) | U2, U3, U4, U8 y U9 (pisos propios) |
| NFR19 | Retención de la demo pública: el audio no se persiste y la transcripción redactada se borra cada noche | U20 | `security-requirements.md` | U16 (no guarda audio) y U4 |
| NFR20 | Paridad por idioma: mismas metas en español e inglés, sin meta reducida | U21 | `reliability-requirements.md` | U18 y U13 |
| NFR21 | De clonar el repositorio a ver el reporte de evaluación: menos de 15 minutos en máquina limpia | U1 | `performance-requirements.md` | U21 (reporte) |

## Entidades por unidad

Cada unidad crea las tablas de las entidades de sus componentes, con el dueño que
fija `../domain-design/components.md`. Las siete entidades de Evaluation se
reparten entre las tres unidades que la construyen (UG-14); las unidades que
extienden un componente de otra unidad no crean entidades nuevas.

| Unit ID | Entidades que crea | Nota |
| --- | --- | --- |
| U1 | `CopyEntry`; `GoldenCase`, `EvalRun`, `CaseResult` | El corredor registra cada corrida y cada resultado por caso |
| U2 | `Tenant`, `StaffPrincipal`, `CaseAccessLink`, `VisitorKey` | — |
| U3 | — | Redacta sin guardar datos |
| U4 | `Case`, `CaseField`, `CaseParty`, `TranscriptTurn`, `CaseChange` | — |
| U5 | `SpendEntry`, `QuotaCounter`, `TraceSummary` | — |
| U6 | — | — |
| U7 | `SourceText`, `GenerationManifest` | — |
| U8 | `PolicyForm`, `Clause`, `IssuedPolicy`, `ClauseIndexEntry`, `ClauseRelation`, `CitationCheck`, `CoverageAnswer` | `ClauseRelation` y el cambio de dueño de `CoverageAnswer` a CitationVerifier vienen de la enmienda del 2026-09-17 |
| U9 | `RuleEvaluation` | — |
| U10 | `DisclosureRecord`, `GuardIntervention`, `ComplianceReview` | — |
| U11 | — | Escribe en las entidades del caso de U4 |
| U12 | `GraphCheckpoint`, `HumanReviewRequest`, `NodeRun` | — |
| U13 | `ChatSession`, `ChatRateWindow` | — |
| U23 | — | — |
| U14 | `AdjusterDecision`, `InboxEvent` | `InboxEvent` alimenta la bandeja en tiempo real por SSE (ADR-021, enmienda del 2026-09-17) |
| U15 | — | — |
| U16 | `CallSession` | — |
| U17 | — | Usa `CallSession.resume_until` de U16 y `QuotaCounter` de U5 |
| U18 | — | — |
| U19 | — | Agrega el tipo `quote_request` a `Case` y sus campos en `CaseField`, de U4 |
| U20 | `ResetRun` | — |
| U21 | `Baseline`, `JudgeCalibration`, `UnstableCase` | Completa `EvalRun.comparable` y `CaseResult.root_cause`, de U1 |
| U22 | `MetricsSnapshot` | — |

## Árbol del código

`../domain-design/components.md` deja a esta etapa fijar el directorio de cada
módulo del PRD ("cada módulo del PRD tiene su directorio, que fija Units
Generation"). Aplica la convención 1 (un solo prefijo), la 2 (un módulo
del PRD, un directorio con su nombre), la 3 (una sola grafía para los nodos) y
la 4 (identificadores en inglés) de `team.md`, con los dos proyectos de ADR-002.

```text
app/                               prefijo único del aplicativo; toda herramienta declara este alcance
  backend/                         proyecto Python (uv, uv.lock)
    src/untangle/
      server/                      raíz de composición (U1) y parte servida (U6)
      tenancy/                     MOD-09 (U2)
      case_record/                 MOD-01 (U4)
      orchestration/               MOD-02: runtime del grafo (U12); api.py, state.py, graph.py
        nodes/
          intake/                  nodo intake (U11)
          policy_verification/     nodo policy_verification (U8)
          decision/                nodo decision (U9)
          compliance/              nodo compliance (U10)
      voice/                       MOD-03 (U16, U17, U18)
      chat/                        MOD-04 (U13)
      policy_rag/                  MOD-05: corpus/ y citations/ (U8)
      rules/                       MOD-06 (U9)
      compliance/                  MOD-07: controls/ (U10) y redaction/ (U3)
      inbox/                       MOD-08 (U14)
      telemetry/                   MOD-10: traces/ y spend/ (U5)
      evals/                       MOD-11: runner/ (U1), drivers/ (U13, U16), gates/ (U21) y evidence/ (U22)
      synthetic_data/              MOD-12 (U7)
      providers/                   ports.py, factory.py y adapters/<proveedor>/ (U5 y U15; ADR-018)
      copy_catalog/                catálogo de textos (U1; ADR-017)
      demo_operations/             operación de la demo (U20)
    tests/                         misma forma que src/, por módulo
    migrations/                    una sola historia; cada unidad agrega las de sus tablas
  frontend/                        proyecto TypeScript (pnpm, pnpm-lock.yaml)
    src/shared/                    base visual, cliente de la API y textos (U6)
    src/modules/                   chat/ (U13), inbox/ (U14), voice/ (U16, U17), evals/ y telemetry/ (U22)
  contracts/                       openapi.json y schemas/ generados desde el código y versionados (U1, U6)
  config/                          configuración versionada
    tenants/<aseguradora>/         aseguradora (U2), reglas (U9), políticas (U10) y voz (U15)
    copy/                          catálogo por idioma (U1)
    providers/                     proveedores, modelos y precios (U5 y U15)
  data/                            salida versionada del generador (U7)
  evals/                           casos de golden set, uno por archivo, y líneas base (U1 y U21)
mise.toml                          versiones de herramientas y archivo de tareas (U1; ADR-002)
scripts/verify.sh                  guion único de verificación (U1)
.github/workflows/                 flujo de verificación que invoca el guion (U1)
```

- Los archivos `__init__.py` de los paquetes quedan vacíos, para que importar
  `compliance.redaction` no cargue los controles ni cree importaciones circulares.
  La API pública de cada módulo vive en su `api.py` (ADR-001, enmienda del
  2026-09-17).
- MOD-13 no tiene directorio propio: Domain Design no le dio componente, así que
  sus piezas viven en los módulos dueños con el tipo de registro `quote_request`.
  MOD-14 es Could y MOD-15 son entregables fuera del árbol (README en la raíz,
  landing en `site/`).
- El archivo de tareas es `mise.toml` (ADR-002, enmienda del 2026-09-17); la
  forma exacta de los archivos de casos, corpus y configuración se fija en
  Contract Design.

## Preguntas abiertas que pasan a Construcción

| Pregunta | Qué falta | Dónde se resuelve |
| --- | --- | --- |
| Experimento 1 | Librería de voz y transporte (ADR-009) y voz de respaldo (ADR-008) | U15 y U16 no empiezan sin su resultado; también aporta el dato de WebRTC para PA-4 en U6 |
| PA-2 | Forma de la confianza por palabra de Deepgram en streaming | Functional Design de U15 |
| PA-3 | Aislamiento de las tablas de puntos de control | Functional Design de U12 |
| PA-4 | Navegadores declarados | `nfr-requirements` de U6 |
| PA-6 | Definición exacta del fin del habla | `nfr-requirements` de U16 |
| PA-7 | Presupuesto de latencia de los tres controles del turno | `nfr-requirements` de U12 |
| PA-8 | Cifrado en reposo de campos del caso y puntos de control | `nfr-requirements` de U4 y U12 |
| PA-9 | Qué sustituye el tope por clave donde el proveedor no lo tiene | `nfr-requirements` de U5 y U15 |
| PA-10 | Origen del chequeo periódico y del disparador nocturno, y canal de alertas | Intent `infra`; U6 y U20 dejan los endpoints y el comando |
| PA-11 | Subconjunto declarado de la corrida de evaluaciones | `nfr-requirements` de U21 |
| PA-12 | Rúbrica de estilo como objetivo medible | `nfr-requirements` de U21, con la conducta en U11 |
| PA-13 | Textos de las reglas desactualizados (D11, D22 y D23) | Ritual de aprendizajes de esta etapa |
| OQ4 | Hospedaje, incluida la página de espera con la instancia dormida | Intent `infra` |
| Cobertura con dos lenguajes | Comando que agrega Python y TypeScript | `nfr-requirements` de U1 |

## Lo que no es unidad

- **US4.2 (video) y US4.3 (landing):** entregables de MOD-15, no conducta del
  sistema; los planifica Delivery Planning (`traceability.json` los marca N/A).
- **Validación del día 30 (S3) y prueba ciega de la voz (S6):** actividades con
  personas, no conducta del sistema; van a Delivery Planning (`project.md`).
- **Experimentos de la semana 1 y el experimento 1:** decisiones con datos; su
  resultado entra como configuración o como actualización de ADR-008 y ADR-009.
- **Tubería de despliegue, entornos y observabilidad de plataforma:** intent
  `infra`, que invoca el mismo guion de verificación (`team.md`, Deployment).
