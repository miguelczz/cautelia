# Investigación 4 — Arquitectura, patrones, principios, monorepo y contratos

Fecha: 2026-09-17. Alcance: estilo de arquitectura, patrones de diseño, principios,
monorepo y contratos entre módulos de Untangle. Quedan fuera (los cubren otras
investigaciones): runtime de IA, datos/RAG/colas, seguridad/evals/pruebas.

Leído del diseño aprobado: `decisions.md` (ADR-001 a ADR-004, ADR-017, ADR-018),
`components.md` (catálogo, tabla resumen y justificación), `team.md` (Code Style y
sus diez convenciones) y `unit-of-work.md` (tabla de unidades, UG-1 a UG-14 y
"Árbol del código").

Las referencias `[S#]` apuntan a la lista de fuentes del final. Lo que no pude
verificar va marcado **(no verificado)**.

---

## 0. Lo que encontré al leer el diseño aprobado

El objetivo es cuestionar el diseño, no confirmarlo. Estas incoherencias salen de
los propios documentos aprobados, antes de cualquier fuente externa. Todas se
pueden detectar con herramientas, así que conviene arreglarlas antes del primer
commit de U1, cuando cuesta poco.

| # | Hallazgo | Evidencia en los documentos | Por qué importa ante un Staff |
| --- | --- | --- | --- |
| H1 | **Inbox está en la capa "dominio", pero depende del grafo.** | ADR-001 pone Inbox en dominio y dice que "los componentes de dominio no importan tipos del grafo"; la tabla resumen de `components.md` le da a Inbox dependencias hacia `Orchestration` (reanuda el grafo) y `PolicyVerificationNode`. | La primera regla que un revisor comprueba ya la rompe el diseño. Inbox es una **entrada** (una persona controla el sistema desde ahí), igual que el chat y la voz. |
| H2 | **Un nodo del grafo es dueño de una tabla y escribe en la base de datos.** | `PolicyVerificationNode` es dueño de `CoverageAnswer` y depende de `TenantIdentity` "para guardar las respuestas de cobertura". | Al reanudar tras `interrupt()`, LangGraph vuelve a ejecutar el nodo **desde el principio** [S22]: sin idempotencia, las filas se duplican. Además rompe el "reductor sin estado" de 12-factor agents [S19]. |
| H3 | **La capa "dominio" incluye persistencia.** | `CaseRecord` depende de la sesión de base de datos de `TenantIdentity`. | Es correcto en un monolito *package by component* [S11], pero un evaluador que lea "dominio" pensando en Clean Architecture [S15] lo verá como una violación. Hay que nombrar el estilo con precisión (sección 1). |
| H4 | **UG-4 hace que el código de producción importe la herramienta de evaluación.** | "El chat (U13) y la llamada (U16) registran sus conductores en el corredor". | El canal de chat, que atiende a personas reales, quedaría importando `untangle.evals`. La dirección correcta es la contraria: el conductor vive en `evals/drivers/` e importa la API pública del chat. Se conserva el objetivo de UG-4 (el corredor existe desde U1). |
| H5 | **El árbol de UG-10 mezcla capas dentro de un mismo paquete.** | `compliance/redaction` (plataforma, hoja) convive con `compliance/controls` (dominio); `orchestration/nodes/*` cuelga del runtime; `telemetry/spend` es UsageBudget. | No es grave, pero obliga a escribir los contratos por subpaquete. Si se protege LangGraph "solo para `untangle.orchestration`", los nodos (que son descendientes) heredan el permiso de importarlo y pueden rutear con `Command(goto=...)` [S23], contra P3. |
| H6 | **Los `__init__.py` vacíos (UG-10) chocan con la costumbre "API pública en `__init__` con `__all__`".** | "Los archivos `__init__.py` de los paquetes quedan vacíos". | Hace falta otro lugar visible para la API pública: un `api.py` por módulo (sección 7). |
| H7 | **Trabajo de CPU en el mismo *event loop* que la voz.** | ADR-004: el trabajo de fondo corre en el mismo proceso; la redacción con Presidio y spaCy se aplica "antes de persistir" cada turno. | El NER de spaCy es trabajo de CPU: si corre en el *event loop*, frena el turno de voz. Hace falta un *bulkhead* (hilo o pool aparte, con semáforos). Lo señalo para quien investiga el runtime; aquí solo propongo el patrón. |
| H8 | **El catálogo de dependencias ya no coincide con lo aprobado después.** | `components.md` sigue listando `DemoOperations` → 13 componentes y `Evaluation` → `ChatChannel` y `VoiceChannel`, que UG-3 y UG-4 invirtieron. | La fuente ejecutable de las dependencias debe ser el contrato de `import-linter` y no la prosa, o el catálogo sigue desactualizándose. |

---

## 1. Estilo de arquitectura

### Hallazgos

- **Monolito modular.** Grzybek lo define como un sistema con una sola unidad de
  despliegue, diseñado con principios de modularidad: módulos independientes,
  organizados por capacidad de negocio y con contrato bien definido [S5]. Para
  hacer cumplir la arquitectura propone, en orden, compilador, análisis estático,
  pruebas de arquitectura y revisión de código, y deja la revisión humana como
  última línea [S6]. Shopify eligió el monolito modular para ganar modularidad
  "sin aumentar las unidades de despliegue" [S7]. Aprendió que las interfaces
  públicas no bastan si el grafo de dependencias es denso o tiene ciclos [S8], y
  en 2024 retiró los chequeos de privacidad de Packwerk porque llevaban a mover
  archivos sin mejorar las APIs; se quedó con el chequeo de dependencias [S9].
  Fowler recomienda no empezar con microservicios aunque se crea que el sistema
  crecerá [S10].
- **Package by component (Simon Brown).** Cada componente agrupa su lógica de
  negocio **y su persistencia** detrás de una interfaz pública [S11]. Es
  exactamente lo que hace el catálogo (CaseRecord trae su esquema, sus estados y su
  tabla), así que H3 no es un error: es este estilo, y hay que decirlo con este
  nombre.
- **Chris Richardson** sostiene que "monolito modular" describe la estructura
  interna y no un estilo, y prefiere hablar de arquitectura de componentes
  orientada a dominio [S16]. Sus patrones: módulo de dominio con API tipo fachada
  estable [S17].
- **Hexagonal (Cockburn).** La intención es que la aplicación pueda ser
  controlada igual por usuarios, programas, pruebas o scripts. No prescribe capas
  internas, y el número de puertos importa poco [S12]. Clean Architecture y Onion
  añaden la regla de que las dependencias apuntan hacia dentro, en anillos [S15].
- **Vertical Slice (Bogard).** Minimiza el acoplamiento entre *slices* y lo
  maximiza dentro de cada uno. Elimina repositorios y servicios compartidos y exige
  un equipo con soltura en refactorización [S13].
- **Functional core, imperative shell (Bernhardt, 2012).** Núcleo puro que se
  prueba sin dobles de prueba, rodeado de una cáscara imperativa delgada con E/S
  [S14].
- **Cosmic Python.** Repository, Unit of Work, capa de servicio y bus de mensajes
  valen la pena para dominios con complejidad real; "si tu app es un CRUD simple
  no necesitas modelo de dominio ni repositorio" [S1]. Los patrones se adoptan de
  forma incremental y no hace falta usarlos todos [S4].

### Evaluación frente a Untangle

| Estilo | ¿Encaja? | Dónde sí | Dónde no |
| --- | --- | --- | --- |
| Monolito modular / *package by component* | **Sí, estilo principal** | Todo el backend: un proceso, 23 componentes (ADR-001, ADR-004) | — |
| Hexagonal (puertos y adaptadores) | **Solo en las fronteras** | `providers` (LLM, embeddings, STT, TTS; ADR-018); `voice` como adaptador de entrada sobre la librería de voz; el `Driver` del corredor de evals; el checkpointer (LangGraph ya define la interfaz) | Tenancy, CaseRecord, reglas y citas: poner un puerto delante de PostgreSQL permitiría probar RLS con un repositorio falso en memoria, justo la compuerta dura que **debe** probarse contra PostgreSQL real (M9). |
| Clean / Onion (anillos por módulo) | **No** | — | 17 módulos × `domain/application/adapters` son unas 50 carpetas de ceremonia para una persona; es la sobreingeniería que castiga un evaluador. |
| Functional core, imperative shell | **Sí, en los módulos donde se decide** | La transición del grafo (ya es pura por P3), la tabla de estados del caso, la evaluación de reglas, el verificador de citas, la guardia de salida, la completitud por campo | La E/S (sesión, SDK, streaming) queda en la cáscara: `store.py`, adaptadores y rutas. |
| DDD táctico | **Selectivo** | *Aggregate* `Case` (invariantes: transiciones, una sola resolución, cierre con evidencia); *value objects* congelados (`CaseNumber`, `TenantId`, `ClauseRef`); lenguaje ubicuo (convención 3) | Sin fábricas, sin eventos de dominio con despachador, sin repositorio genérico por entidad. |
| Vertical Slice | **Parcial, solo en entradas y frontend** | Un endpoint = una función de caso de uso dentro de `inbox`, `chat` y `voice`; `frontend/src/modules/<feature>` | No como estilo principal: reglas, citas y redacción son núcleo compartido por diseño. |
| Microservicios | **No** | — | Ya rechazado en ADR-001 y respaldado por [S10] y [S7]. |

### Recomendación

**Nombre para el ADR y el README:** *"Monolito modular por componentes, con reglas
de dependencia verificadas por herramienta; un flujo de trabajo determinista
(LangGraph) en el centro; núcleo funcional en los módulos que deciden; puertos y
adaptadores solo en las fronteras con proveedores externos."*

Versión corta en inglés para el README (4 frases; es la que lee un EM):

> Untangle is a modular monolith: one deployable, organized as package-by-component
> modules whose dependency rules are enforced in CI by import-linter. At its center
> is a deterministic LangGraph workflow, not an autonomous agent: code decides every
> transition. Decision logic (rules, citation checks, case lifecycle) is a pure
> functional core; I/O lives in thin shells. Ports & adapters appear only where the
> outside world is swappable (LLM, speech, voice transport); we deliberately did not
> apply Clean Architecture rings, microservices, an event bus or a DI container.

La última frase ("deliberately did not") es la defensa contra la acusación de
sobreingeniería **y** de currículum inflado: muestra criterio, no solo patrones.

**Cambio en ADR-001 (H1 y H3):** reclasificar Inbox a la capa de **entradas**
(con chat y voz) y aclarar que "dominio" significa "módulos de capacidad con su
persistencia", no el anillo de Clean Architecture. Opcionalmente, renombrar las
capas a `entrypoints / workflow / capabilities / platform / tools` para que no
arrastren esa connotación. Cambiar solo la definición es suficiente y cuesta
menos.

---

## 2. Arquitectura para sistemas de agentes de IA

### Hallazgos

- **Anthropic, "Building effective agents" (2024-12-19)** distingue *workflows*
  (caminos de código predefinidos) de *agents* (el LLM dirige su propio proceso).
  Recomienda empezar con las APIs directamente, porque los frameworks esconden
  prompts y respuestas. Sus patrones son prompt chaining, routing,
  parallelization, orchestrator-workers y evaluator-optimizer, y sus principios,
  simplicidad, transparencia y una interfaz agente-herramienta bien documentada
  [S18].
- **Microsoft (ms.date 2026-02-12)** pide "usar el nivel de complejidad más bajo
  que cumpla los requisitos", describe la orquestación secuencial como *pipes and
  filters* con el siguiente paso decidido de forma determinista, y desaconseja el
  patrón *handoff* cuando el ruteo es determinista y basado en reglas [S20].
- **Google Cloud (actualizado 2026-05-28)** separa los patrones deterministas
  (sequential, parallel, loop) de los dirigidos por el LLM (coordinator,
  hierarchical, swarm, ReAct), e incluye *human-in-the-loop* y *custom logic*
  para ramificar en código [S21].
- **12-factor agents (HumanLayer, 2025-04-03; repositorio con licencia Apache 2.0
  / CC BY-SA 4.0).** Doce factores más un apéndice (factor 13). Su tesis: los
  buenos agentes son sobre todo código determinista con pasos de LLM puestos en el
  lugar justo [S19].
- **LangGraph** permite que un nodo rutee con `Command(goto=...)` o con aristas
  condicionales, y pide no mezclar los dos en un mismo nodo [S23]. Las funciones
  de nodo pueden ser funciones normales que devuelven diccionarios, sin importar
  LangGraph [S23]. Tras `interrupt()` el nodo se reejecuta completo, así que sus
  efectos laterales deben ser idempotentes [S22].

### Dónde cae Untangle

Untangle es un **workflow**, no un agente: *prompt chaining* (intake →
policy_verification → decision → compliance), *routing* por código (función
pura), *parallelization* en el ritmo de fondo (precarga), un verificador
determinista en vez de un evaluator-optimizer con LLM, y *human-in-the-loop* con
`interrupt()`. En la taxonomía de Google es **custom logic + human-in-the-loop**;
en la de Microsoft, **orquestación secuencial determinista**. El README debería
decirlo con esas palabras, porque es exactamente la respuesta que busca un Head
of AI.

### Mapeo con 12-factor agents

| Factor | Estado en el diseño | Brecha | Acción comprobable |
| --- | --- | --- | --- |
| 1. Lenguaje natural → llamadas a herramientas | Intake extrae campos estructurados; P3 prohíbe que el texto libre dirija acciones | — | La salida del LLM siempre se parsea con un modelo Pydantic `extra="forbid"`; `invalid_response` es un valor. |
| 2. Ser dueño de los prompts | `team.md`: prompts y rúbricas versionados | Falta fijar dónde y cómo se identifican | Un archivo por nodo e idioma bajo configuración versionada, con `prompt_version` registrado en la traza y en `EvalRun`. |
| 3. Ser dueño de la ventana de contexto | Mandated: el texto externo va delimitado, nunca en posición de instrucción | Falta un punto único y probable | Una función pura `build_context(state) -> messages` por nodo, con prueba de *snapshot*. |
| 4. Herramientas = salidas estructuradas | Categoría y derivación por reglas, no por el modelo | — | — |
| 5. Unificar estado de ejecución y de negocio | **Brecha**: checkpoint de LangGraph + `CaseRecord` + `HumanReviewRequest`/`NodeRun` como espejos | Tres lugares con estado del mismo caso | Decisión explícita en ADR-005: el caso es la fuente de verdad del negocio y el checkpoint solo es ejecución reanudable. Escrituras idempotentes con clave natural y una prueba de reconciliación (reanudar dos veces no duplica nada). |
| 6. Lanzar, pausar y reanudar con APIs simples | `interrupt()` y reanudación desde la bandeja | La API pública del grafo no está nombrada | `orchestration/api.py` con tres funciones: `start_case`, `get_status`, `resume(decision)`; `resume` idempotente mediante actualización condicional (`WHERE status='pending'`). |
| 7. Contactar humanos con llamadas a herramientas | `HumanReviewRequest` tipado | — | — |
| 8. Ser dueño del flujo de control | Transición pura (P3, convención 5c) | LangGraph permite `Command(goto)` desde un nodo | Contrato `forbidden`: `untangle.orchestration.nodes` no importa `langgraph`. Los nodos son funciones normales [S23]. |
| 9. Compactar errores en el contexto | Taxonomía cerrada, `NodeRun`, un reintento | No hay bucle de autocorrección (bien, por diseño) | Si se reintenta un parseo fallido, pasar el error de validación compacto, nunca la traza completa. |
| 10. Agentes pequeños y enfocados | Cuatro nodos con un paso de LLM acotado | — | — |
| 11. Disparar desde cualquier lugar | Chat, voz y bandeja entran al mismo grafo | — | — |
| 12. Agente como reductor sin estado | Convención 6: el nodo devuelve una actualización parcial | **Brecha H2**: un nodo con escrituras a base de datos | Nodo puro que devuelve la actualización; la persistencia la hace el dominio con clave idempotente `(case_id, turn_id, node)`. Prueba de pureza: copiar el estado, ejecutar el nodo con puertos falsos y afirmar que la entrada no cambió. |
| 13. Precargar el contexto | ADR-004: precarga de la verificación al identificarse la persona | — | — |

**Recomendación:** citar Anthropic [S18] y 12-factor agents [S19] en ADR-003 como
marco, y cerrar las brechas de los factores 5, 8 y 12 con los contratos y pruebas
de la tabla. Las tres son baratas y muy visibles para un Staff.

---

## 3. Patrones de diseño que aplican

| Patrón | Dónde aplica en Untangle | Cuándo NO usarlo aquí | Cómo se verifica |
| --- | --- | --- | --- |
| **Adapter / Port** | `providers/ports.py` con `typing.Protocol` pequeños (`TextGenerator`, `Embedder`, `SpeechToText`, `TextToSpeech`) y adaptadores por proveedor; `Driver` del corredor; contrato de borrado de UG-3 | Delante de PostgreSQL en módulos críticos de RLS (ver sección 1); interfaces con una sola implementación y sin necesidad de doble de prueba | `import-linter` `protected`: solo `untangle.server` importa `untangle.providers.adapters`; los adaptadores heredan explícitamente del Protocol para que mypy verifique la conformidad [S40]; prueba de contrato compartida sobre respuestas grabadas (ADR-018) |
| **Strategy** | Política de fallo por nodo como dato (ADR-003); elección de voz principal o de respaldo; subconjunto declarado de evals | Como jerarquía de clases: basta un `dataclass` o una función | mypy strict |
| **Factory** | "Un cliente por uso" (ADR-018), construido solo en la raíz de composición | Fábricas genéricas o registros dinámicos por nombre en cadena de texto | `protected` sobre `providers.factory` |
| **Repository** | Un `store.py` concreto por módulo con las consultas SQL de ese dueño | `BaseRepository[T]` genérico o puertos abstractos para cada tabla [S1] | Contrato: solo `store.py` importa el driver o el ORM; `acyclic_siblings` |
| **Unit of Work** | **El punto único de sesión ya es la unidad de trabajo**: `async with tenant_session(tenant_id)` abre la transacción, fija el tenant con `set_config('app.tenant_id', ..., true)` (local a la transacción, así no se filtra entre conexiones del pool [S56]) y hace commit o rollback | Una clase UoW propia encima de la sesión del ORM: Cosmic Python reconoce que en proyectos pequeños basta la del ORM [S2] | `protected`: nadie más importa el driver; prueba de que fuera de `tenant_session` no hay sesión |
| **Máquina de estados explícita** | Ciclo de vida del caso: tabla `dict[(State, Event), State]` + función pura + pruebas por tabla; diagrama Mermaid generado desde la tabla | Librerías de máquinas de estado; mezclarla con el grafo de LangGraph (son dos máquinas distintas: conversación y negocio) | mypy `--enable-error-code exhaustive-match` [S42]; prueba de que el diagrama generado es igual al versionado |
| **Pipeline / Chain of Responsibility** | Redacción (reconocedores en cadena); guardia de salida (checks ordenados que devuelven `Pass` o `Replace(catalog_key)` y cortan en el primero que interviene) | Cadenas configurables en tiempo de ejecución: el orden es código | Prueba por eslabón y prueba de orden |
| **Decorator / wrapper** | Ejecutor común de política de fallo; spans de telemetría alrededor de nodos y adaptadores | Decoradores que cambian la firma o esconden reintentos dentro del dominio | Ruff `BLE001` y `S110`: los nodos no capturan excepciones genéricas |
| **Observer / eventos de dominio** | **No por ahora**: la bandeja **lee** la base de datos (consulta con refresco o SSE desde la consulta). `CaseChange` es historial de auditoría, no un bus | Bus en memoria o señales: ADR-004 ya rechazó el bus "sin un segundo consumidor" | Contrato: no existe módulo `events` ni `bus` (grep) |
| **Specification / Interpreter** | Motor de reglas: reglas como **datos** versionados (YAML validado por Pydantic) con un conjunto cerrado de operadores y una función pura que devuelve categoría + reglas disparadas | Clases `Specification` componibles; motores de reglas generales o con encadenamiento hacia delante. Fowler advierte del flujo implícito y pide contexto estrecho [S51] | JSON Schema de las reglas + prueba unitaria por regla (Mandated) |
| **Retry + backoff + timeout** | En los adaptadores: `asyncio.timeout` + un reintento (ADR-003). `rate_limited` no se reintenta dentro del turno de voz; en el ritmo de fondo respeta `Retry-After` | Reintentos ante cuota agotada (ADR-018 ya lo prohíbe) | Prueba con puerto falso que falla N veces |
| **Circuit breaker** | **No como librería.** El corte de UsageBudget ya funciona como interruptor manual del gasto | Microsoft lo desaconseja cuando los algoritmos de reintento conocidos bastan y añade complejidad innecesaria [S52]; `aiobreaker` no publica desde 2021 | — |
| **Bulkhead** | **Sí, barato y necesario (H7):** `asyncio.Semaphore` por uso (voz, chat, fondo) y trabajo de CPU (redacción) fuera del *event loop* | Pools de procesos por componente | Ruff `ASYNC2xx` (llamadas bloqueantes en funciones async) [S43]; medición en el experimento 1 |
| **Idempotencia** | Reanudar con la decisión, enviar mensaje de chat, escrituras de nodos: **claves naturales + actualizaciones condicionales** | Un almacén de `Idempotency-Key` genérico: el borrador IETF sigue en borrador (draft-07, 2025-10-15, expirado el 2026-04-18) [S55] y aquí no hay clientes externos | Prueba: doble `resume` → una sola `AdjusterDecision` |
| **Transactional outbox** | **No.** Resuelve escribir en la base de datos y publicar a un broker [S54], y ADR-004 no tiene broker | — | — |
| **Result / errores como valores** | Resultados de negocio como uniones cerradas (`Verified \| NoClause \| CouldNotVerify`), con `dataclass(frozen=True)` + `match`; excepciones solo para bugs y dentro de los adaptadores, traducidas a `ProviderError(kind)` | La librería `returns` (activa, 0.29.0) introduce un estilo monádico ajeno a Python idiomático, que un revisor lee como sobreingeniería | mypy `exhaustive-match` [S42] |
| **Inyección de dependencias** | Manual: raíz de composición en `server/`; los nodos reciben sus puertos por *closure* al construir el grafo (Cosmic Python, cap. 13 [S3]); FastAPI `Depends` solo como getter fino sobre `app.state`; pruebas con `app.dependency_overrides` [S57] | Contenedores (dishka 1.10.1, dependency-injector 4.49.1; los dos mantenidos [S58]): Cosmic Python los justifica solo con cadenas de DI profundas [S3]. `context_schema` de LangGraph [S23] obligaría a los nodos a importar tipos de LangGraph (contra H5) | `protected`: solo `server` importa adaptadores y fábricas |

### Antipatrones a evitar (con su chequeo)

1. Carpetas `utils/`, `helpers/` o `common/` como cajón de sastre → grep en `verify.sh`: `find app -type d -name 'utils' -o -name 'helpers' -o -name 'common'` debe salir vacío.
2. Un LLM que decide la ruta (`Command(goto=...)` en nodos) → contrato `forbidden` sobre `langgraph`.
3. Nodos que capturan su propio fallo → Ruff `BLE001`, `S110`, `TRY300`.
4. Estado compartido mutado en el lugar → prueba de pureza de nodos; Ruff `B006` y `RUF012`.
5. Mocks de la base de datos en módulos de RLS → aserción de esquema + pruebas contra PostgreSQL real (ya en Mandated).
6. Módulos "dios" con muchas dependencias salientes (Inbox, DemoOperations) → `acyclic_siblings` + revisar el *fan-out* en la revisión de la unidad.
7. Un paquete de uv por módulo, contenedor de DI, bus de eventos, AsyncAPI, Pact, Nx o Turborepo: complejidad sin un segundo consumidor que la pida.
8. Nombres `*Manager`, `*Handler`, `*Service` genéricos → convención de nombres por grep (opcional).

---

## 4. Principios: significado aquí y cómo se verifican

Regla del equipo: una convención que no comprueba una herramienta o un grep no
cuenta. Por eso la última columna dice honestamente cuándo **no** se puede.

| Principio | Qué significa en Untangle (una frase) | Herramienta o grep que lo verifica | ¿Verificable? |
| --- | --- | --- | --- |
| **S** — responsabilidad única | Cada componente tiene la lista de responsabilidades del catálogo y cambia por una sola razón | Proxies: Ruff `C901`, `PLR0911/0912/0913/0915/0917`, `PLR0904`; nada mide la "razón de cambio" | **Parcial.** Se sostiene con el catálogo y la justificación por componente; decirlo así en el README |
| **O** — abierto/cerrado | Nuevo proveedor = adaptador + configuración; nueva regla = archivo de datos, sin tocar el núcleo | `import-linter`: el dominio no importa adaptadores; prueba de que el motor carga reglas de un directorio | **Parcial** (se verifica la consecuencia) |
| **L** — sustitución de Liskov | Todo adaptador cumple el mismo contrato que su puerto | Adaptadores heredan explícitamente del `Protocol` (mypy verifica) [S40] + suite de contrato parametrizada | **Sí** |
| **I** — segregación de interfaces | Puertos pequeños por capacidad, no un `ProviderGateway` gordo | mypy + revisión; grep de métodos por `Protocol` (≤ 3) | **Parcial** |
| **D** — inversión de dependencias | El núcleo depende de `ports`; solo la raíz de composición conoce los adaptadores | `import-linter` `layers` + `protected` + `forbidden` con `include_external_packages` [S24] | **Sí** |
| **DRY vs WET/AHA, regla de tres** | Duplicar hasta la tercera aparición; "duplicación es más barata que la abstracción equivocada" (Metz [S50]); AHA (Dodds [S50]) | No hay detector confiable que deba bloquear (Ruff no tiene `duplicate-code`) | **No.** Se declara como criterio de revisión, sin falsa automatización. Excepción comprobable: los textos visibles, por el catálogo único (ADR-017) |
| **YAGNI** | No se construye lo que ninguna historia de las 85 pide | Consecuencias medibles: `vulture` 2.16 (código muerto; advertencia, por falsos positivos con rutas y validadores), `deptry` 0.25.1 (dependencias sin uso), `knip` 6.36.0 (TS: archivos, exports y dependencias sin uso) [S46][S47] | **Parcial** |
| **KISS** | Funciones cortas y planas; sin frameworks donde basta una función | Ruff `C901` (max-complexity 10) y `PLR09xx`; ESLint `complexity`, `max-depth`, `max-params`. **No usar radon/xenon**: radon no publica desde 2023-03 y xenon desde 2024-10 [S47]; Ruff lo cubre | **Sí** (proxy) |
| **Separación de responsabilidades** | Entradas, flujo de trabajo, capacidades, plataforma y herramientas no se mezclan | `import-linter` (backend); `eslint-plugin-boundaries` 7.2.0 (frontend) [S44] | **Sí** |
| **Ley de Demeter** | No encadenar `a.b.c.d` a través de módulos | Ruff `SLF001` (acceso a miembros privados) cubre una parte; no hay regla general | **No** (solo revisión) |
| **Composición sobre herencia** | Herencia solo de `BaseModel`, `Protocol`, `Exception` y `Enum` | Grep/AST opcional en `verify.sh` que liste las clases base permitidas | **Sí, con un script de 20 líneas** (opcional; puede ser excesivo) |
| **Fallar rápido** | La app no arranca con configuración inválida; ningún `except` genérico | `pydantic-settings` validado en `create_app` + prueba; Ruff `BLE001`, `S110`, `TRY`; mypy strict | **Sí** |
| **Parse, don't validate** (King [S49]) | Toda frontera (HTTP, archivos, salida del LLM, respuesta del proveedor) produce un modelo tipado; dentro no circulan `dict` ni `Any` | Pydantic `ConfigDict(strict=True, extra="forbid", frozen=True)` en modelos internos (ojo: con entrada JSON, strict acepta fechas como cadena [S41]); Ruff `ANN401`; mypy strict; `FAST002` | **Sí** |
| **Inmutabilidad** | Estado, valores y eventos congelados; el nodo devuelve una actualización y no muta | `frozen=True`; prueba de pureza de nodos; Ruff `B006` y `RUF012` | **Sí** |
| **CQS** | Las funciones de consulta no escriben; los `GET` no cambian estado | Sin herramienta directa. Proxy: los `GET` no importan funciones de escritura de `store.py` (difícil de expresar) | **No** (revisión + pruebas de endpoints) |
| **12-factor app** (abierto en 2024 [S66]) | Configuración en el entorno, servicios de respaldo por URL, logs a stdout, paridad dev/prod con Docker Compose, cierre limpio en el *lifespan* | Prueba de que los campos de `Settings` coinciden con los nombres de `.env.example`; escaneo de secretos (otra investigación) | **Sí** |
| **Mínimo privilegio** | El rol de la app no es dueño de las tablas ni tiene `BYPASSRLS`, o las tablas llevan `FORCE ROW LEVEL SECURITY`, porque dueños y roles con `BYPASSRLS` saltan RLS [S56] | Extender la aserción de esquema: `rolbypassrls = false` y `relforcerowsecurity` o dueño distinto | **Sí** (señalar a quien investiga seguridad) |
| **Seguro por defecto** | Toda ruta exige principal, salvo una lista explícita de públicas | Prueba que recorre `app.routes` y falla si una ruta no tiene la dependencia de auth ni está en la lista | **Sí** |

---

## 5. Monorepo

### Hallazgos

- **uv workspaces:** "uv can't ensure that packages don't import dependencies
  declared by another workspace member", y no sirven si los miembros quieren
  entornos separados [S27]. **Partir el backend en un paquete por módulo no crea
  fronteras reales en Python:** todo queda en el mismo entorno virtual. Da ~20
  `pyproject.toml` que mantener sin ganancia de aislamiento.
- **Herramientas de fronteras en Python, estado a 2026-09:**

| Herramienta | Última versión | Estado | Veredicto |
| --- | --- | --- | --- |
| `import-linter` | 2.15 (2026-09-04) [S24] | Activo; contratos `layers` (con `containers`, `exhaustive`, `\|` independientes y `:` no independientes), `forbidden` (incluye paquetes externos), `protected`, `independence`, `acyclic_siblings`; `drawgraph` desde 2.10 (2026-02-06); su autor, David Seddon, escribe el caso de estudio del epílogo de Cosmic Python [S4] | **Recomendado** |
| Tach | 0.35.1 (2026-09-14) en `tach-org/tach` | Gauge dejó de mantenerlo (2025-06-03, según un blog de terceros [S25]); el repositorio sigue en otra organización con parches de seguridad, y el issue #850 dice que "ya no se mantiene" y que su API cerrada `app.gauge.sh` podría apagarse [S25] | **Evitar**: futuro incierto, justo lo que un evaluador mira. Gobernanza exacta **(no verificado)** |
| PyTestArch | 4.0.1 (2025-08-08) | Activo pero lento | Redundante con import-linter |
| pytest-archon | 0.0.7 (2025-09-19) | Pre-1.0 | Redundante |
| `grimp` | 3.17 (2026-09-04) [S68] | Motor de import-linter | Solo si hace falta una prueba de arquitectura a medida (sección 7) |

- **Ejecutores de tareas, estado a 2026-09:** `just` 1.58.0 (2026-08-03) [S29];
  `mise` v2026.9.10 (2026-09-16), con tareas y además versiones de herramientas;
  sus tareas de monorepo ya no son experimentales [S28]; Taskfile v3.53.1;
  poethepoet 0.48.0 (vive en `pyproject.toml`, solo Python); Nx 22.7.12,
  Turborepo 2.10.13 y moon 2.5.5 están orientados a grafos de construcción con
  caché en muchos paquetes JS [S67] (fuentes comparativas secundarias y de calidad
  baja; el juicio de "excesivo" es mío, basado en que aquí hay un solo proyecto
  por lenguaje).

### Recomendación

```text
app/
  backend/            UN proyecto uv (un pyproject, un uv.lock); fronteras con import-linter
  frontend/           UN proyecto pnpm (sin pnpm-workspace mientras no exista un paquete TS compartido)
  contracts/          artefactos GENERADOS y versionados: openapi.json, schemas/*.schema.json
  config/  data/  evals/
mise.toml             versiones de Python, uv, Node y pnpm + tareas con nombre (archivo de tareas único)
scripts/verify.sh     compuerta única y ordenada (team.md); `mise run verify` lo invoca
```

- **Un proyecto uv con grupos de dependencias** (`dev`, `evals` para DeepEval,
  `synthetic` para el generador), de modo que la imagen de ejecución no cargue
  dependencias de evaluación. Menos superficie de cadena de suministro, alineado
  con Mandated. Soporte de `[dependency-groups]` en uv: **no re-verificado en esta
  sesión**.
- **Ejecutor de tareas: `mise`.** Razón: la regla Mandated exige "toolchain
  fijado" y NFR21 pide pasar de clonar a ver el reporte en menos de 15 minutos en
  una máquina limpia. `mise install && mise run verify` fija Python, Node, pnpm y uv
  en un archivo y expone las tareas con nombre [S28]. **Alternativa: `just`**, más
  reconocible para un evaluador, pero deja las versiones repartidas en
  `.python-version`, `.nvmrc` y `packageManager`. Riesgo de `mise`: publica con
  mucha frecuencia (calver), así que hay que fijar su versión en CI. No usar el
  modo monorepo de mise: basta un `mise.toml` en la raíz con `dir = "app/frontend"`
  por tarea.
- **Nx, Turborepo y moon: excesivos.** Resuelven caché y grafos de tareas entre
  decenas de paquetes JS; aquí hay dos proyectos. Un evaluador lo leería como
  elección de currículum.
- **`app/contracts/`** hace visible el contrato entre backend y frontend y permite
  una comprobación de deriva con `git diff --exit-code` (sección 6).

---

## 6. Contratos

### Hallazgos

- **Template oficial full-stack de FastAPI:** usa `@hey-api/openapi-ts` 0.97.3
  (script `generate-client`), TanStack Router y Query, Biome como linter y
  Playwright; release 0.12.0 del 12 de agosto [S30]. Nota: el template usa **Biome,
  no ESLint**. ADR-002 elige ESLint, y es la elección correcta para fronteras,
  porque `eslint-plugin-boundaries` solo existe para ESLint.
- **Hey API** va por 0.99.0 (2026-06-22); es pre-1.0 con cambios incompatibles
  entre versiones menores y pide fijar la versión exacta [S31]. Tiene plugins de
  TanStack Query y Zod.
- **openapi-typescript + openapi-fetch:** `openapi-fetch` y `openapi-react-query`
  pasaron a **modo mantenimiento** sin nuevas funciones (discusión #2559,
  2025-12-29) [S32]. Descartados.
- **orval** 8.33.0 (2026-09-13), activo, con mocks MSW [S33]: alternativa válida,
  pero se aleja del template que ADR-002 usa como referencia reconocible.
- **SSE en FastAPI:** `EventSourceResponse` desde 0.135.0 (PR fusionado el
  2026-03-01); con `AsyncIterable[Model]` documenta los eventos [S34], y la
  discusión #15102 (2026-03-12) muestra `itemSchema` bajo `text/event-stream`
  dentro del documento 3.1.0 [S34]. `itemSchema` es el mecanismo de OpenAPI 3.2.0
  (2025-09-19) para medios secuenciales como SSE [S35]. **Que Hey API genere tipos
  de eventos desde `itemSchema`: (no verificado).**
- **AsyncAPI** 3.1.0 (2026-01-31) [S36]: maduro, pero pensado para arquitecturas
  de eventos con varios productores y consumidores.
- **Pact** no es adecuado, entre otros casos, para APIs públicas o cuando no se
  controla la respuesta del proveedor; brilla con equipos distintos que colaboran
  [S37].
- **Detección de cambios incompatibles:** `oasdiff` v1.32.1 (2026-09-15) [S38].
- **Fitness functions:** "cualquier mecanismo que dé una evaluación objetiva de la
  integridad de una característica de la arquitectura" (Building Evolutionary
  Architectures, 2.ª ed., 2022) [S39].

### Recomendación

| Contrato | Mecanismo | Chequeo en `verify.sh` | ¿Excesivo? |
| --- | --- | --- | --- |
| HTTP backend → frontend | FastAPI → `app/contracts/openapi.json` → `@hey-api/openapi-ts` **en versión exacta** con el plugin de TanStack Query; el cliente generado solo se importa desde `frontend/src/shared/api` | Regenerar esquema y cliente + `git diff --exit-code` + `tsc --noEmit` | No |
| Eventos SSE (chat, estado del caso) | Modelos Pydantic en una unión discriminada + `AsyncIterable[Event]` → `itemSchema` | Mismo diff; si Hey API no tipa el stream, exportar la unión como componente del esquema y tiparla en `shared/api` | No |
| Archivos versionados (casos de golden set, configuración de tenant, reglas, catálogo de textos, proveedores) | Modelos Pydantic como fuente → `model_json_schema()` → `app/contracts/schemas/*.schema.json`; editores con `$schema` | Diff del esquema + prueba pytest que carga **cada** archivo con su modelo estricto (sin `check-jsonschema`: una herramienta menos) | No |
| Contratos en proceso | `typing.Protocol` en `ports.py` / `api.py`; adaptadores heredan del Protocol | mypy strict + suite de contrato compartida (ADR-018) | No |
| Dependencias entre módulos | `import-linter` en `pyproject.toml` | `lint-imports` | No |
| Transporte de voz (WebRTC/WS) | Lo define la librería elegida en el experimento 1 | Prueba de humo de la llamada | **AsyncAPI: sí, excesivo** (un solo consumidor, protocolo ajeno) |
| Consumidor-proveedor | — | — | **Pact: excesivo** (mismo repositorio, un consumidor) [S37] |
| Cambios incompatibles | Política escrita: "API interna sin versionar; el contrato es el commit; backend y cliente cambian en el mismo commit" | `oasdiff` **solo** el día que exista un consumidor externo | Hoy, YAGNI |
| Fuzzing del esquema propio | Schemathesis 4.27.3 [S70] | Opcional; corresponde a la investigación de pruebas | Opcional |

**Funciones de aptitud (fitness functions) que sostienen los contratos en el
tiempo**, todas dentro de `verify.sh`:

1. Contratos de `import-linter` (capas, `protected`, `forbidden`, `acyclic_siblings`).
2. Deriva de OpenAPI, cliente y JSON Schema (`git diff --exit-code`).
3. Aserción de esquema RLS (ya aprobada) + `rolbypassrls`/`FORCE`.
4. Rutas seguras por defecto (prueba sobre `app.routes`).
5. Pureza de nodos (prueba genérica sobre los cuatro nodos).
6. Diagramas generados desde el código: la tabla de estados del caso → Mermaid, y
   el grafo de LangGraph con `get_graph()` (la documentación muestra
   `draw_mermaid_png()` [S23]; la variante en texto se da por hecha, **(no
   verificado)**), comparados con los versionados. Es la respuesta concreta a
   "tener los grafos en mente": hay tres grafos (dependencias de módulos, flujo de
   LangGraph y ciclo de vida del caso) y los tres se pueden comprobar.
7. Cada ADR nuevo lleva una sección **"Confirmación"** (MADR 4.0.0 [S59]) que
   nombra la función de aptitud que lo vigila.

### Borrador de contratos de `import-linter` (backend)

Es un borrador: los nombres exactos salen del árbol final de U1. Refleja UG-3,
UG-4 (con H4) y H1.

```toml
[tool.importlinter]
root_package = "untangle"
include_external_packages = true

[[tool.importlinter.contracts]]
name = "Capas: entradas > flujo > capacidades > plataforma"
type = "layers"
layers = [
  "untangle.server",
  "untangle.demo_operations : untangle.evals",
  "untangle.chat | untangle.voice | untangle.inbox",
  "untangle.orchestration",
  "untangle.compliance.controls",
  "untangle.case_record | untangle.policy_rag | untangle.rules",
  "untangle.providers",
  "untangle.telemetry",
  "untangle.tenancy | untangle.compliance.redaction | untangle.copy_catalog",
]

[[tool.importlinter.contracts]]
name = "Solo la raíz de composición conoce adaptadores y fábricas"
type = "protected"
protected_modules = ["untangle.providers.adapters", "untangle.providers.factory"]
allowed_importers = ["untangle.server"]

[[tool.importlinter.contracts]]
name = "SDK solo dentro de su adaptador; LangGraph solo en el runtime"
type = "forbidden"
source_modules = ["untangle.orchestration.nodes", "untangle.case_record", "untangle.policy_rag", "untangle.rules", "untangle.compliance", "untangle.chat", "untangle.inbox"]
forbidden_modules = ["langgraph", "google.genai", "deepgram", "cartesia"]
allow_indirect_imports = true   # inbox -> orchestration.api -> graph -> langgraph es legítimo

[[tool.importlinter.contracts]]
name = "Capacidades y plataforma no conocen la web"
type = "forbidden"
source_modules = ["untangle.orchestration", "untangle.case_record", "untangle.policy_rag", "untangle.rules", "untangle.compliance", "untangle.tenancy", "untangle.telemetry", "untangle.providers.ports"]
forbidden_modules = ["fastapi", "starlette"]
allow_indirect_imports = true

[[tool.importlinter.contracts]]
name = "Los nodos no se importan entre sí"
type = "independence"
modules = ["untangle.orchestration.nodes.*"]

[[tool.importlinter.contracts]]
name = "Sin ciclos entre módulos hermanos"
type = "acyclic_siblings"
ancestors = ["untangle"]
```

Los nombres de los paquetes de SDK (`google.genai`, `deepgram`, `cartesia`) son
ilustrativos y se confirman al instalar cada SDK. Ojo con un detalle verificado:
los contratos `forbidden` revisan por defecto también las importaciones
**indirectas** [S24]. Sin `allow_indirect_imports = true`, la bandeja rompería el
contrato por importar la API del runtime, que a su vez importa LangGraph. Los
contratos `layers` e `independence` siempre revisan cadenas indirectas, que es lo
que se quiere ahí. También implica que las dependencias de autenticación de
FastAPI viven en `server/` o en las entradas, no en `tenancy`. La convención 5 de
`team.md` ("cuatro reglas de dirección") pasa a ser **este archivo**.

---

## 7. Organización del código dentro de un módulo

### Recomendación: plano por defecto, con subcarpetas solo con motivo

```text
untangle/case_record/
  __init__.py      vacío (UG-10)
  api.py           API pública: lo único que otros módulos importan
  model.py         tipos congelados, enums y tabla enum → término del PRD (convención 4)
  lifecycle.py     tabla de transiciones y funciones puras (núcleo funcional)
  store.py         SQL; recibe la sesión de tenancy (cáscara imperativa)
  routes.py        SOLO en módulos de entrada (chat, voice, inbox, evals.evidence, demo_operations)

untangle/providers/
  __init__.py
  ports.py         Protocols pequeños + ProviderError(kind: timeout | rate_limited | unavailable | invalid_response)
  factory.py       clientes por uso (voz, chat, evals, operación); protegido
  adapters/gemini/  adapters/deepgram/  adapters/cartesia/   único lugar con SDK

untangle/orchestration/
  api.py           start_case, get_status, resume
  state.py         estado tipado + conjuntos de escritura (lo único que importan los nodos del runtime)
  graph.py         build_graph(deps) y transición pura; único import de langgraph
  failure_policy.py
  nodes/intake/node.py  ...   funciones normales: make_intake_node(ports) -> Callable[[State], Update]

untangle/server/   raíz de composición
  app.py           create_app(settings); lifespan construye Services y lo guarda en app.state
  wiring.py        dataclass Services(...) con adaptadores por uso; build_graph(...)
  deps.py          getters finos para Depends; en pruebas, dependency_overrides [S57]
```

- **API pública con `api.py`, no con `__init__`** (resuelve H6). La privacidad de
  todo lo demás **no** se impone con contratos por módulo: Shopify retiró esos
  chequeos por su poco valor [S9]. Se protege solo lo que tiene riesgo real:
  adaptadores, fábrica, driver de base de datos y sumideros de logs (Ruff `TID251`
  prohíbe `logging`/`print` fuera del sumidero de redacción, con `per-file-ignores`
  para ese módulo [S43]). Si Miguel quiere hacer cumplir "solo `api.py`" en todo el
  árbol, basta una prueba de 20 líneas con `grimp` [S68]. Es opcional y está en el
  límite de lo excesivo.
- **Dónde vive la raíz de composición:** `untangle/server/`, como ya dice U1. Es
  el único módulo que puede importarlo todo y ocupa la capa superior del contrato.
- **Inyección de dependencias:** manual (sección 3). Ni `Depends` para lógica de
  dominio ni contenedor. Los nodos reciben puertos por *closure*, lo que mantiene
  a LangGraph fuera de ellos y hace trivial la prueba de pureza.
- **Frontend:** `src/routes/` (rutas de TanStack, delgadas),
  `src/modules/<feature>/` y `src/shared/{ui,api,copy}`. Con
  `eslint-plugin-boundaries`: `modules/*` solo importa `shared`; ningún módulo
  importa a otro; `shared` no importa módulos; el cliente generado solo pasa por
  `shared/api`. Además `knip` y `typescript-eslint` `strict-type-checked` con
  `switch-exhaustiveness-check` y `no-floating-promises` [S48].
  `dependency-cruiser` 18.3.1 [S45] es alternativa, pero añade otra herramienta
  cuando ESLint ya está en ADR-002.

---

## 8. Documentación que señala seniority (proporcional)

### Hallazgos

- **ADR:** Nygard (2011) propone Título, Contexto, Decisión, Estado y
  Consecuencias [S60]. MADR 4.0.0 (2024-09-17) añade opciones consideradas,
  drivers y una sección opcional **"Confirmation"**: cómo se confirmará que la
  implementación cumple la decisión, por ejemplo con herramientas de pruebas de
  arquitectura [S59].
- **C4:** el diagrama de componentes es opcional ("solo si aporta valor") y
  conviene automatizarlo si va a durar [S61]. En Mermaid, C4 sigue siendo
  **experimental** [S62], mientras que GitHub renderiza Mermaid de forma nativa
  desde 2022 [S62]. Structurizr anunció el fin de su servicio en la nube y un
  "vNext" con modelo *open core* [S63] (fechas exactas **(no verificado)**).
- **arc42** tiene doce secciones "adaptables" y un *canvas* de una página [S64].
- **AGENTS.md** es un formato abierto, custodiado por la Agentic AI Foundation de
  la Linux Foundation, con archivos anidados por subproyecto [S65]. Si Claude Code
  lo lee: **(no verificado)**; el repositorio ya usa `CLAUDE.md`.

### Recomendación

1. **README en inglés (D24) organizado por audiencia:**
   - **90 s:** qué es, demo, 3 cifras de la línea base con su fecha y commit, un
     diagrama.
   - **10 min:** "Architecture at a glance" con el párrafo de la sección 1, el
     índice de ADR con título y decisión en una línea (en inglés) y "What we
     deliberately didn't build".
   - **60 min:** "How it fails" (ya planeado), "How the rules are enforced" (lista
     de funciones de aptitud con el comando) y el mapa de carpetas.
2. **Diagramas:** Mermaid `flowchart` (no la sintaxis C4 experimental) con dos
   niveles C4: contexto y contenedores (navegador, proceso único, PostgreSQL,
   Langfuse, proveedores). Añadir un **único** diagrama de componentes del backend
   (las 5 capas), más los dos diagramas generados (grafo de LangGraph y ciclo de
   vida del caso). Structurizr es excesivo.
3. **ADR:** mantener el formato actual, que ya cumple la regla de fase, y añadir
   **"Confirmación"** de MADR a los ADR nuevos y a ADR-001, ADR-003, ADR-012,
   ADR-013 y ADR-018, cada uno enlazado a su contrato o prueba. Es el cambio más
   barato con más señal para un Staff.
4. **Idioma:** los ADR completos están en español dentro de `aidlc/` (convención
   4). Para un EM o Staff que no lee español, el índice en inglés del README y los
   resúmenes de una línea bastan sin tocar la convención. Si Miguel quiere más
   alcance, que decida si publica ADR en inglés en `docs/adr/`: **decisión suya,
   no la tomo aquí**.
5. **arc42-lite:** no hace falta la plantilla. El README ya cubre las secciones 1,
   3, 4, 5, 8, 9 y 11 (objetivos, contexto, estrategia, bloques, conceptos
   transversales, decisiones, riesgos).
6. **AGENTS.md:** opcional y corto (comandos de `mise`, dónde están los contratos),
   sin repetir `team.md`, para no crear una segunda fuente que se desactualice.

---

## Tabla final de recomendaciones

| Tema | Recomendación | Razón | Herramienta que lo verifica | ¿Cambia un ADR aprobado o una convención? |
| --- | --- | --- | --- | --- |
| Estilo | "Monolito modular por componentes + flujo determinista + núcleo funcional + puertos solo en fronteras", dicho así en ADR-001 y README | Nombra con precisión lo ya aprobado y evita que "dominio" se lea como anillo de Clean Architecture (H3) | `import-linter` `layers` | **ADR-001: addendum de redacción** |
| Capa de Inbox | Mover Inbox de dominio a entradas | Hoy contradice ADR-001 (H1) | `import-linter` `layers` | **Sí, ADR-001 y catálogo** |
| Nodos con datos | Nodos puros; `CoverageAnswer` persistida por el dominio con clave idempotente, o bien idempotencia obligatoria si se mantiene la propiedad | Reejecución tras `interrupt()` [S22]; factor 12 [S19] (H2) | Prueba de pureza; prueba de doble reanudación | **Sí, propiedad de entidad en `components.md` (decide Miguel)** |
| Conductores de evals | Viven en `evals/drivers/` e importan la API del canal | El código de producción no importa evals (H4) | `forbidden`: canales ↛ `untangle.evals` | **Sí, mecanismo de UG-4 (no su objetivo)** |
| LangGraph en nodos | Nodos sin `langgraph`; ruteo solo por la transición pura | Factor 8; `Command(goto)` existe [S23] (H5) | `forbidden` `langgraph` desde `nodes` | No (hace cumplir P3 y ADR-003) |
| API de módulo | `api.py` por módulo; `__init__` vacío; privacidad estricta solo en adaptadores, fábrica, driver y sumideros | Packwerk retiró la privacidad general [S9] (H6) | `protected`; Ruff `TID251` | **Convención nueva en UG-10** |
| Contratos de dependencias | `import-linter` como fuente ejecutable (borrador en §6) | Activo (2.15); Tach en limbo [S24][S25] (H8) | `lint-imports` en `verify.sh` | **Convención 5 de `team.md` pasa a ser el archivo de contratos** |
| Cliente HTTP | `@hey-api/openapi-ts` en versión exacta + TanStack Query; deriva por diff | Lo usa el template oficial; openapi-fetch está en mantenimiento [S30][S31][S32] | `git diff --exit-code` + `tsc` | No (llena el hueco de ADR-002) |
| SSE / AsyncAPI | SSE tipado con `itemSchema`; sin AsyncAPI | Un solo consumidor [S34][S35] | Diff de OpenAPI | No |
| Pact / oasdiff | No, por ahora | Mismo repositorio y un consumidor [S37] | — | No |
| Archivos de datos | Pydantic → JSON Schema versionado + carga estricta de cada archivo | "Parse, don't validate" [S49][S41] | pytest + diff | No |
| Errores | Uniones cerradas congeladas + `match`; excepciones solo en adaptadores | Distingue "no hay cláusula" de "no pude verificar" (Mandated) | mypy `exhaustive-match` [S42] | No |
| Resiliencia | Timeout + 1 reintento + *bulkhead* con semáforos y CPU fuera del *event loop*; sin circuit breaker ni outbox | [S52][S54]; H7 | Ruff `ASYNC`; experimento 1 | No (precisa ADR-004) |
| DI | Manual, raíz de composición en `server/`, *closures* para nodos | [S3]; los contenedores añaden conceptos | `protected` | No |
| Unidad de trabajo | El punto único de sesión es la UoW, con `set_config(..., true)` | [S2][S56] | Aserción de esquema + prueba | No (precisa ADR-012) |
| Monorepo | Un proyecto uv + un proyecto pnpm; sin uv workspaces; sin Nx/Turbo/moon | uv no aísla imports [S27] | — | No |
| Archivo de tareas | `mise.toml` (herramientas + tareas); alternativa `just` | Toolchain fijado y NFR21 [S28][S29] | `mise run verify` en CI | No (llena hueco de UG-10) |
| Complejidad | Ruff `C901`/`PLR09xx`; sin radon/xenon | radon sin releases desde 2023 [S47] | Ruff | No |
| Código y dependencias sin uso | `deptry`, `knip` (bloqueantes); `vulture` (advertencia) | YAGNI medible [S46][S47] | `verify.sh` | No |
| Frontend | `eslint-plugin-boundaries` + `strict-type-checked` | Mantiene ESLint de ADR-002 [S44][S48] | ESLint | No |
| Seguro por defecto / mínimo privilegio | Prueba de rutas con auth; aserción de `BYPASSRLS`/`FORCE` | [S56] | pytest | No (extiende la aserción aprobada) |
| ADR | Añadir "Confirmación" (MADR 4) con enlace a la función de aptitud | [S59] | Revisión + enlace a la prueba | **Sí, plantilla de ADR (aditiva)** |
| Diagramas | Mermaid `flowchart` C4 (contexto y contenedores) + grafo y estados generados | C4 en Mermaid es experimental [S62]; componentes opcionales [S61] | Diff de diagramas generados | No |

## Qué cambia en lo aprobado (resumen)

1. **ADR-001:** Inbox pasa a la capa de entradas; addendum que nombra el estilo y
   define "dominio" como módulos de capacidad con persistencia.
2. **`components.md`:** propiedad de `CoverageAnswer` (o idempotencia obligatoria
   del nodo), y actualizar las dependencias ya invertidas por UG-3 y UG-4.
3. **UG-4:** los conductores viven en `evals/drivers/`, no en los canales.
4. **UG-10 (árbol):** `api.py` por módulo, `providers/ports.py` separado de
   `adapters/`, `orchestration/state.py` como único import de los nodos,
   `app/contracts/`, `mise.toml`.
5. **Convención 5 de `team.md`:** las reglas de dirección quedan expresadas como
   contratos de `import-linter`, más tres nuevas: producción ↛ evals; capacidades y
   plataforma ↛ fastapi; `acyclic_siblings`.
6. **Plantilla de ADR:** sección "Confirmación" (aditiva, compatible con la regla
   de fase de Incepción).

Nada de esto reabre la elección de monolito, Python + React, LangGraph, el ritmo
sin broker ni los adaptadores por uso.

## No verificado en esta investigación

- Que Hey API genere tipos de eventos SSE a partir de `itemSchema`.
- Gobernanza exacta de Tach tras la salida de Gauge (hay releases de 2026, pero un issue afirma que no se mantiene).
- Soporte de `[dependency-groups]` en uv (conocido, no re-verificado hoy).
- `get_graph().draw_mermaid()` en texto (la documentación muestra `draw_mermaid_png()`).
- Formato de salida de `import-linter drawgraph`.
- Fechas exactas del fin del servicio en la nube de Structurizr y de vNext.
- Si Claude Code lee `AGENTS.md`.
- Si el checkpointer de LangGraph puede escribir en la misma transacción que el caso (PA-3; lo resuelve Functional Design de U12).
- Fecha de graduación de las tareas de monorepo de mise (fuente secundaria: 2026-06-13).

## Fuentes

- [S1] Percival y Gregory, *Architecture Patterns with Python* (O'Reilly, 2020; repositorio del libro v1.0, 2020-04-29), cap. 2 Repository — https://www.cosmicpython.com/book/chapter_02_repository.html
- [S2] Íd., cap. 6 Unit of Work — https://www.cosmicpython.com/book/chapter_06_uow.html
- [S3] Íd., cap. 13 Dependency Injection — https://www.cosmicpython.com/book/chapter_13_dependency_injection.html
- [S4] Íd., epílogo — https://www.cosmicpython.com/book/epilogue_1_how_to_get_there_from_here.html
- [S5] Kamil Grzybek, "Modular Monolith: A Primer", 2019-12-02 — https://www.kamilgrzybek.com/blog/posts/modular-monolith-primer
- [S6] Kamil Grzybek, "Modular Monolith: Architecture Enforcement", 2020-03-22 — https://www.kamilgrzybek.com/blog/posts/modular-monolith-architecture-enforcement
- [S7] Kirsten Westeinde (Shopify), "Deconstructing the Monolith", 2019-02-21 — https://shopify.engineering/deconstructing-monolith-designing-software-maximizes-developer-productivity
- [S8] Philip Müller (Shopify), "Under Deconstruction: The State of Shopify's Monolith", 2020-09-16 — https://shopify.engineering/shopify-monolith
- [S9] McGibbon y Salzberg, "A Packwerk Retrospective", 2024-01-26 — https://railsatscale.com/2024-01-26-a-packwerk-retrospective/
- [S10] Martin Fowler, "MonolithFirst", 2015-06-03 — https://martinfowler.com/bliki/MonolithFirst.html
- [S11] Simon Brown, "Modular monolith and package by component" (2016, republicado) — https://simonbrown.je/modular-monolith/
- [S12] Alistair Cockburn, "Hexagonal architecture", 2005-09-04 — https://alistair.cockburn.us/hexagonal-architecture/
- [S13] Jimmy Bogard, "Vertical Slice Architecture", 2018-04-19 — https://www.jimmybogard.com/vertical-slice-architecture/
- [S14] Gary Bernhardt, "Functional Core, Imperative Shell", 2012-07-12 — https://www.destroyallsoftware.com/screencasts/catalog/functional-core-imperative-shell
- [S15] Robert C. Martin, "The Clean Architecture", 2012-08-13 — https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html
- [S16] Chris Richardson, "How modular can your monolith go? Part 7", 2024-05-13 — https://microservices.io/post/architecture/2024/05/13/how-modular-can-your-monolith-go-part-7-no-such-thing-as-a-modular-monolith.html
- [S17] Chris Richardson, "Architectural patterns for modular monoliths that enable fast flow", 2024-09-09 — https://microservices.io/post/architecture/2024/09/09/modular-monolith-patterns-for-fast-flow.html
- [S18] Anthropic (Erik S. y Barry Zhang), "Building effective agents", 2024-12-19 — https://www.anthropic.com/engineering/building-effective-agents
- [S19] HumanLayer (Dex Horthy), "12 Factor Agents", 2025-04-03 — https://www.humanlayer.dev/blog/12-factor-agents ; repositorio — https://github.com/humanlayer/12-factor-agents
- [S20] Microsoft, "AI agent orchestration patterns", ms.date 2026-02-12 — https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns
- [S21] Google Cloud, "Choose a design pattern for your agentic AI system", actualizado 2026-05-28 — https://docs.cloud.google.com/architecture/choose-design-pattern-agentic-ai-system
- [S22] LangGraph, Interrupts (consultado 2026-09-17; langgraph 1.2.11, 2026-08-11) — https://docs.langchain.com/oss/python/langgraph/interrupts
- [S23] LangGraph, Graph API y Use the graph API (consultado 2026-09-17) — https://docs.langchain.com/oss/python/langgraph/graph-api ; https://docs.langchain.com/oss/python/langgraph/use-graph-api
- [S24] import-linter, release notes (2.15, 2026-09-04) y tipos de contrato — https://import-linter.readthedocs.io/en/stable/release_notes/ ; https://import-linter.readthedocs.io/en/stable/contract_types/layers/ ; https://import-linter.readthedocs.io/en/stable/contract_types/forbidden/ ; https://import-linter.readthedocs.io/en/stable/contract_types/protected/ ; https://import-linter.readthedocs.io/en/stable/contract_types/acyclic_siblings/
- [S25] Tach: repositorio `tach-org/tach` (0.35.1, 2026-09-14) — https://github.com/tach-org/tach ; issue #850 — https://github.com/tach-org/tach/issues/850 ; Cory Donnelly, "First Thoughts on Tach" (nota del 2025-06-03) — https://corydonnelly.com/python/first-thoughts-on-tach/
- [S26] PyTestArch 4.0.1 (2025-08-08) — https://github.com/zyskarch/pytestarch ; pytest-archon 0.0.7 (2025-09-19) — https://github.com/jwbargsten/pytest-archon
- [S27] uv, Workspaces (consultado 2026-09-17) — https://docs.astral.sh/uv/concepts/projects/workspaces/
- [S28] mise, Monorepo Tasks (consultado 2026-09-17; v2026.9.10, 2026-09-16) — https://mise.jdx.dev/tasks/monorepo.html
- [S29] just, releases (1.58.0, 2026-08-03) — https://github.com/casey/just/releases
- [S30] FastAPI full-stack template: `frontend/package.json` y releases (0.12.0, 12 de agosto) — https://github.com/fastapi/full-stack-fastapi-template
- [S31] Hey API, Get started (npm 0.99.0, 2026-06-22) — https://heyapi.dev/openapi-ts/get-started
- [S32] openapi-typescript, "2026 Roadmap", discusión #2559, 2025-12-29 — https://github.com/openapi-ts/openapi-typescript/discussions/2559
- [S33] orval (npm 8.33.0, 2026-09-13) — https://orval.dev/
- [S34] FastAPI, Server-Sent Events — https://fastapi.tiangolo.com/tutorial/server-sent-events/ ; PR #15030 (fusionado 2026-03-01) — https://github.com/fastapi/fastapi/pull/15030 ; discusión #15102 (2026-03-12) — https://github.com/fastapi/fastapi/discussions/15102
- [S35] OpenAPI Specification 3.2.0, 2025-09-19 — https://spec.openapis.org/oas/v3.2.0.html
- [S36] AsyncAPI spec, releases (v3.1.0, 2026-01-31) — https://github.com/asyncapi/spec/releases
- [S37] Pact, "What is Pact good for?" (pact-python 3.4.1, 2026-09-17) — https://docs.pact.io/getting_started/what_is_pact_good_for
- [S38] oasdiff (v1.32.1, 2026-09-15) — https://github.com/oasdiff/oasdiff
- [S39] Ford, Parsons, Kua y Sadalage, *Building Evolutionary Architectures*, 2.ª ed. (O'Reilly, 2022) — https://www.thoughtworks.com/insights/books/building-evolutionaryarchitectures-second-edition
- [S40] Python typing spec, Protocols — https://typing.python.org/en/latest/spec/protocol.html
- [S41] Pydantic, Strict Mode (pydantic 2.13.5, 2026-08-28) — https://pydantic.dev/docs/validation/latest/concepts/strict_mode/
- [S42] mypy 2.3.1, códigos de error opcionales (`exhaustive-match`) — https://mypy.readthedocs.io/en/stable/error_code_list2.html
- [S43] Ruff, reglas (consultado 2026-09-17) — https://docs.astral.sh/ruff/rules/ ; TID251 — https://docs.astral.sh/ruff/rules/banned-api/ ; PLC2701 (preview) — https://docs.astral.sh/ruff/rules/import-private-name/
- [S44] eslint-plugin-boundaries (7.2.0, 2026-08-09) — https://github.com/javierbrea/eslint-plugin-boundaries
- [S45] dependency-cruiser (18.3.1, 2026-09-14) — https://github.com/sverweij/dependency-cruiser
- [S46] knip (6.36.0, 2026-09-16) — https://knip.dev/
- [S47] deptry 0.25.1 (2026-03-18) — https://deptry.com/ ; vulture 2.16 (2026-03-25) — https://pypi.org/project/vulture/ ; radon 6.0.1 (2023-03-26) — https://pypi.org/project/radon/ ; xenon 0.9.3 (2024-10-21) — https://pypi.org/project/xenon/
- [S48] typescript-eslint, Shared Configs — https://typescript-eslint.io/users/configs/ ; https://typescript-eslint.io/rules/switch-exhaustiveness-check/
- [S49] Alexis King, "Parse, don't validate", 2019-11-05 — https://lexi-lambda.github.io/blog/2019/11/05/parse-don-t-validate/
- [S50] Sandi Metz, "The Wrong Abstraction", 2016-01-20 — https://sandimetz.com/blog/2016/1/20/the-wrong-abstraction ; Kent C. Dodds, "AHA Programming", 2020-06-22 — https://kentcdodds.com/blog/aha-programming
- [S51] Martin Fowler, "RulesEngine", 2009-01-07 — https://martinfowler.com/bliki/RulesEngine.html
- [S52] Microsoft, Circuit Breaker pattern, ms.date 2025-02-05 — https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker
- [S53] stamina (26.1.0, 2026-04-13) — https://stamina.hynek.me/en/stable/ ; tenacity 9.1.4 (2026-02-07); pybreaker 1.4.1 (2025-09-21); aiobreaker 1.2.0 (2021-05-17), en PyPI
- [S54] Chris Richardson, "Pattern: Transactional outbox" (sin fecha visible) — https://microservices.io/patterns/data/transactional-outbox.html
- [S55] IETF, draft-ietf-httpapi-idempotency-key-header-07, 2025-10-15 (expira 2026-04-18) — https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/
- [S56] PostgreSQL (current), Row Security Policies y `set_config` — https://www.postgresql.org/docs/current/ddl-rowsecurity.html ; https://www.postgresql.org/docs/current/functions-admin.html
- [S57] FastAPI, Testing Dependencies with Overrides (fastapi 0.141.1, 2026-07-29) — https://fastapi.tiangolo.com/advanced/testing-dependencies/
- [S58] dishka 1.10.1 (2026-04-25) — https://github.com/reagento/dishka ; dependency-injector 4.49.1 (2026-06-18) — https://python-dependency-injector.ets-labs.org/ ; svcs 26.2.0 (2026-08-24) — https://svcs.hynek.me/
- [S59] MADR 4.0.0, 2024-09-17 — https://adr.github.io/madr/
- [S60] Michael Nygard, "Documenting Architecture Decisions", 2011-11-15 — https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions
- [S61] C4 model, Component diagram — https://c4model.com/diagrams/component
- [S62] Mermaid, C4 Diagrams (experimental) — https://mermaid.js.org/syntax/c4.html ; GitHub Blog, Mermaid en Markdown, 2022-02-14 — https://github.blog/developer-skills/github/include-diagrams-markdown-files-mermaid/
- [S63] Structurizr (build 2026.07.03; anuncios de vNext y fin del servicio en la nube en Patreon, fechas no verificadas) — https://structurizr.com/ ; https://www.patreon.com/posts/introducing-146923136
- [S64] arc42, Overview — https://arc42.org/overview
- [S65] AGENTS.md — https://agents.md/ ; Linux Foundation, anuncio de la Agentic AI Foundation — https://www.linuxfoundation.org/press/linux-foundation-announces-the-formation-of-the-agentic-ai-foundation
- [S66] Twelve-Factor App, anuncio de código abierto (noviembre de 2024) — https://12factor.net/blog/open-source-announcement
- [S67] Nx 22.7.12 (2026-09-10), Turborepo v2.10.13 (2026-09-14), moon v2.5.5 (2026-09-15), releases en GitHub; comparación de Nx — https://nx.dev/docs/kb/nx-vs-turborepo (fuente interesada)
- [S68] grimp 3.17 (2026-09-04) — https://pypi.org/project/grimp/
- [S69] ESLint v10.0.0 — https://eslint.org/blog/2026/02/eslint-v10.0.0-released/
- [S70] Schemathesis (4.27.3, 2026-09-17) — https://schemathesis.readthedocs.io/
