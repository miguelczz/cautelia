# Decisiones de arquitectura — Untangle

Registro de las decisiones de arquitectura de Domain Design. Cada una lleva su
contexto, la decisión, sus consecuencias (incluidas las de seguridad y
cumplimiento) y las alternativas rechazadas. Rigen desde la aprobación de esta
etapa; las que dependen de un experimento pendiente lo dicen en su estado.

**Fuentes consumidas.** Los requisitos (`../requirements-analysis/requirements.md`,
en especial las preguntas abiertas OQ2 y OQ3 y los NFR con valor esperado); las
historias (`../user-stories/stories.md`, con sus decisiones D7, D12, D17, D18,
D23 y D26 y las preguntas PA-1 a PA-11); el mapa del código existente
(`aidlc/spaces/default/codekb/untangle/architecture.md` y
`aidlc/spaces/default/codekb/untangle/component-inventory.md`, que confirman
que solo existe la landing de `site/` y ningún componente del aplicativo); las
prácticas del equipo (`../practices-discovery/team-practices.md`); el catálogo de
esta etapa (`components.md`); las respuestas Q1 a Q5
(`domain-design-questions.md`); y los resultados de los experimentos 02, 03 y 04
en `spikes/`.

## Índice

| ADR | Título | Estado |
| --- | --- | --- |
| ADR-001 | Monolito modular con 23 componentes y los nodos como componentes propios | Aceptada; enmendada el 2026-09-17 |
| ADR-002 | Python en el servidor y React con TypeScript en la interfaz | Aceptada; enmendada el 2026-09-17 |
| ADR-003 | LangGraph como runtime del grafo | Aceptada; enmendada el 2026-09-17 |
| ADR-004 | Llamadas en proceso y ritmo de fondo sin broker | Aceptada; enmendada el 2026-09-17 |
| ADR-005 | Estados del caso, retoma tras el límite y estado por campo | Aceptada; enmendada el 2026-09-17 |
| ADR-006 | Modelo de lenguaje y planes por uso (enmienda de D-015) | Aceptada; enmendada el 2026-09-17 |
| ADR-007 | Transcripción con Deepgram `nova-3` en modo `multi` | Aceptada |
| ADR-008 | Síntesis: Catalina de Cartesia provisional y voz de respaldo por elegir | Aceptada en parte; respaldo pendiente del experimento 1 |
| ADR-009 | Librería de voz pendiente del experimento 1 | Propuesta, pendiente del experimento 1; enmendada el 2026-09-17 |
| ADR-010 | Corpus por aseguradora en su idioma y recuperación híbrida en PostgreSQL | Aceptada; enmendada el 2026-09-17 |
| ADR-011 | Verificador exacto de citas con resultados cerrados | Aceptada; enmendada el 2026-09-17 |
| ADR-012 | Aislamiento por aseguradora e identidad | Aceptada; enmendada el 2026-09-17 |
| ADR-013 | Redacción en un punto único y segundo detector independiente | Aceptada; enmendada el 2026-09-17 |
| ADR-014 | Evaluación con corredor propio sobre pytest y juez propio calibrado | Aceptada; enmendada el 2026-09-17 |
| ADR-015 | Telemetría abierta y gasto controlado en la base del aplicativo | Aceptada; enmendada el 2026-09-17 |
| ADR-016 | Datos sintéticos deterministas desde textos fuente revisados | Aceptada |
| ADR-017 | Un solo catálogo de textos para servidor e interfaz | Aceptada |
| ADR-018 | Adaptadores de proveedores con interfaces propias y clientes por uso | Aceptada; enmendada el 2026-09-17 |
| ADR-019 | Protocolos de agentes y herramientas fuera del producto | Aceptada (2026-09-17) |
| ADR-020 | Defensa contra inyección por diseño y guardas del turno | Aceptada (2026-09-17) |
| ADR-021 | Tiempo real con SSE | Aceptada (2026-09-17) |

**Enmiendas del 2026-09-17.** Antes de Contract Design, Miguel pidió investigar
con fuentes cómo se construye el aplicativo
(`docs/reference/arquitectura-y-tecnologia.md` y sus cuatro anexos). Ninguna
enmienda reabre el monolito, Python con React, LangGraph, el trabajo de fondo sin
broker, PostgreSQL ni los adaptadores propios. Cada ADR enmendado lleva al final
su sección "Enmienda del 2026-09-17", y los que protegen una compuerta, su
"Confirmación" con la comprobación que los vigila. ADR-019 a ADR-021 son nuevos.

---

## ADR-001: Monolito modular con 23 componentes y los nodos como componentes propios

### Estado

Aceptada (2026-09-17). La ubicación de los nodos es la Opción A de
`components.md`, que Miguel confirma en la aprobación.

### Contexto

El PRD define quince módulos (MOD-01 a MOD-15) y una arquitectura funcional con
dos canales que entran al mismo grafo. Las prácticas exigen que cada módulo del
PRD sea un módulo del árbol, una sola grafía para los cuatro nodos, cuatro
reglas de dirección de dependencias y un conjunto de escritura por nodo. El
proyecto lo construye una sola persona en 90 días sobre hospedaje gratuito, y
Units Generation decide después cómo se agrupan los componentes para
desplegarse.

### Decisión

- El aplicativo se organiza como un monolito modular de 23 componentes en seis
  capas: superficie (WebClient), entradas (ChatChannel, VoiceChannel, Inbox),
  grafo (Orchestration y los cuatro nodos), dominio (CaseRecord, PolicyCorpus,
  CitationVerifier, RulesEngine, ComplianceControls), plataforma
  (TenantIdentity, PiiRedaction, Telemetry, UsageBudget, ProviderGateway,
  CopyCatalog) y herramientas (Evaluation, SyntheticData, DemoOperations). La
  enmienda del 2026-09-17 renombró "canales" como "entradas" y movió allí la
  bandeja, que antes figuraba en dominio.
- Los nodos `intake`, `policy_verification`, `decision` y `compliance` son
  componentes propios (IntakeNode, PolicyVerificationNode, DecisionNode,
  ComplianceNode) y Orchestration es solo el runtime del grafo.
- Los componentes de dominio no importan tipos del grafo, canales ni SDK de
  proveedores.
- Cuatro componentes no corresponden a un solo módulo del PRD y quedan
  justificados aquí: ProviderGateway (adaptadores de proveedores, ADR-018),
  CopyCatalog (un solo espacio de claves, ADR-017), DemoOperations
  (aprovisionamiento y reinicio nocturno sin crear ciclos) y WebClient (un solo
  artefacto con su propio lenguaje, ADR-002).
- El grafo de llamadas es acíclico. TenantIdentity, PiiRedaction y CopyCatalog
  son hojas sin dependencias.

### Consecuencias

- **Positivas:** cada dato tiene un dueño y cada golden set un componente que lo
  hace pasar; los nodos cambian con los prompts sin tocar el dominio; un
  evaluador encuentra el runtime del grafo aislado para comprobar P3.
- **Negativas:** 23 componentes y 83 dependencias (86 antes de la enmienda del
  2026-09-17) son mucho para una persona;
  Inbox y DemoOperations tienen muchas dependencias salientes; hace falta una
  composición que monte las rutas y conecte adaptadores, que no es un componente
  de dominio.
- **Seguridad y cumplimiento:** el punto único de sesión de base de datos y el
  punto único de redacción son hojas, así que ningún camino llega a la base de
  datos o a una salida sin pasar por ellos.

### Alternativas rechazadas

- **Nodos dentro de Orchestration:** mezcla el mecanismo del grafo con la
  captura, la cobertura, la decisión y el cierre, que cambian a ritmos
  distintos, y deja el conjunto de escritura como convención interna.
- **Cada nodo dentro de su módulo de dominio:** obliga al corpus, a las reglas y
  a los controles a importar el estado del grafo y a probarse con él.
- **Microservicios:** multiplican procesos que mantener despiertos en hospedaje
  gratuito y despliegues para una sola persona, con fronteras aún no probadas.
- **Capas técnicas (controladores, servicios, repositorios):** contradicen la
  convención de un módulo del PRD por módulo del árbol.

### Enmienda del 2026-09-17

Investigación previa a Contract Design, con fuentes en `docs/reference/arquitectura-y-tecnologia.md` y sus anexos.

- **Nombre del estilo:** monolito modular por componentes (*package by
  component*), con reglas de dependencia verificadas por herramienta; un flujo de
  trabajo determinista (LangGraph) en el centro; núcleo funcional en los módulos
  que deciden (transición, ciclo de vida del caso, reglas, verificador de citas,
  guardia de salida); puertos y adaptadores solo en las fronteras con proveedores
  y con la librería de voz. No se aplican anillos de Clean Architecture,
  microservicios, bus de eventos ni contenedor de inyección de dependencias.
- **"Dominio"** significa módulos de capacidad con su persistencia, no el anillo
  interior de Clean Architecture.
- **La bandeja pasa a la capa de entradas** (antes "canales"), junto al chat y
  la voz. Depende del runtime del grafo para reanudarlo, y esta decisión prohíbe
  que el dominio lo importe.
- **No es multiagente:** es una agente conversacional sobre un flujo de cuatro
  nodos cuyo ruteo decide el código. En código y ADR se dice "nodo", nunca
  "agente" (decisión de Miguel, que corrige la redacción de P1 en el PRD).
- **Contratos ejecutables.** Las reglas de dirección de dependencias (convención
  5 de `team.md`) se hacen cumplir con contratos de `import-linter` en
  `verify.sh`:
  - capas;
  - `protected`: solo la raíz de composición importa adaptadores y fábricas;
  - `forbidden`: los SDK solo en su adaptador, LangGraph solo en el runtime,
    capacidades y plataforma sin FastAPI, y el código de producción sin
    `untangle.evals`;
  - `independence` entre nodos;
  - `acyclic_siblings`.

  Tach se descarta porque su propio repositorio declara que ya no se mantiene.
- **API pública por módulo** en `api.py`, con los `__init__.py` vacíos. La
  privacidad estricta solo protege adaptadores, fábrica, driver de base de datos
  y salida de logs.
- **Raíz de composición** en `server/`, con inyección manual. Los nodos reciben
  sus puertos por *closure* y no importan LangGraph.

#### Confirmación

- `lint-imports` en `verify.sh` con los contratos anteriores.
- Grep en `verify.sh`: no existen carpetas `utils/`, `helpers/` ni `common/`, ni
  módulos `events` o `bus`.

---

## ADR-002: Python en el servidor y React con TypeScript en la interfaz

### Estado

Aceptada (2026-09-17), respuesta Q3 tras investigación.

### Contexto

La pregunta abierta OQ2 y las prácticas (Code Style) piden fijar lenguaje,
versión del runtime, gestor de dependencias con su lockfile y comprobador de
tipos. Las librerías centrales tienen su versión principal en Python: LangGraph,
Presidio y las dos librerías de voz candidatas. Para las pantallas, Miguel pidió
buenas prácticas y que quien revise el repositorio reconozca un proyecto bien
construido, sin interfaz sin framework. La investigación mostró que el template
oficial full-stack de FastAPI usa React, TypeScript, Vite, TanStack Router y
Query, Tailwind con shadcn/ui, cliente generado y Playwright, y compila la
interfaz dentro del backend; que Pipecat UI y los componentes de agentes de
LiveKit son de React sobre shadcn; que en State of JavaScript 2025 React es el
framework más usado y Vite tiene 98 % de satisfacción; y que el export estático
de Next.js desactiva server actions y rutas de servidor dinámicas.

### Decisión

- **Servidor:** Python 3.13; FastAPI (asíncrono, streaming por SSE y esquema
  OpenAPI); uv con `uv.lock` e instalación con `uv sync --locked`; Ruff como
  formatter y linter con las reglas de seguridad `S`; mypy en modo estricto con
  el plugin de Pydantic; pytest con cobertura (coverage.py); pip-audit para la
  auditoría de dependencias.
- **Interfaz:**
  - **Lenguaje y dependencias:** TypeScript estricto sobre Node 24 LTS; pnpm 12.x
    (enmienda del 2026-09-17; decía pnpm 10)
    con `pnpm-lock.yaml`, instalación con `pnpm install --frozen-lockfile` y los
    scripts de instalación de dependencias bloqueados salvo una lista permitida.
  - **Framework y datos:** React con Vite; TanStack Router para rutas y filtros
    de URL tipados y TanStack Query para datos y acciones.
  - **Componentes:** Tailwind CSS con shadcn/ui sobre primitivas accesibles,
    tematizado con los tokens aprobados y los modos claro y oscuro.
  - **API:** cliente tipado generado desde el esquema OpenAPI de FastAPI; el
    generador se fija al crear el andamiaje.
  - **Calidad:** ESLint 10 con configuración plana, typescript-eslint,
    eslint-plugin-security y reglas de accesibilidad de JSX; Prettier;
    `tsc --noEmit`; `pnpm audit`.
  - **Pruebas:** Vitest con Testing Library, y Playwright con axe para los
    recorridos y la línea base de accesibilidad.
- **Un solo prefijo:** servidor e interfaz viven bajo el prefijo único del
  aplicativo, cada herramienta con alcance a su subárbol, y el guion único de
  verificación corre las dos cadenas. El primer commit de código trae los dos
  andamiajes.
- **Entrega:** la interfaz se compila a archivos estáticos que se sirven desde
  el mismo origen que la API. Si en el despliegue público los sirve el propio
  proceso o un hospedaje estático que no se duerme (necesario para la página de
  espera de AC5.16.4) lo decide el intent `infra`; en los dos casos hay un solo
  proceso del aplicativo.

### Consecuencias

- **Positivas:** patrones reconocibles y documentados; tipos de extremo a
  extremo desde la API; componentes de voz listos para la consola; un solo
  proceso del aplicativo.
- **Negativas:**
  - Dos juegos de herramientas desde el primer commit.
  - El piso de cobertura del 80 % se agrega sobre Python y TypeScript;
    `nfr-requirements` fija el comando que lo calcula.
  - La cadena de dependencias de npm es una superficie más.
  - La maqueta aprobada se porta a componentes de React.
- **Seguridad y cumplimiento:** el mismo origen evita CORS y permite cookies
  `HttpOnly` y `SameSite` para la clave del visitante y los tokens; los secretos
  quedan solo en el servidor; pnpm 12.x, el lockfile congelado y la auditoría
  acotan el riesgo de la cadena de suministro; la política de seguridad de
  contenido se define en NFR Design.

### Alternativas rechazadas

- **HTML servido por Python con JavaScript liviano:** un solo lenguaje, pero sin
  un framework de interfaz reconocible, contra los criterios de Miguel.
- **Next.js con servidor propio:** un segundo proceso que mantener despierto,
  permisos comprobados en dos servidores, y su export estático pierde las
  capacidades que lo justifican.
- **React Router 7 en modo de una sola página:** prerenderiza la raíz al
  compilar y exige código seguro para servidor; TanStack Router tipa mejor los
  filtros de la bandeja.
- **Todo en TypeScript, servidor incluido:** perdería Presidio y la versión
  principal de las librerías de voz.

### Enmienda del 2026-09-17

Investigación previa a Contract Design, con fuentes en `docs/reference/arquitectura-y-tecnologia.md` y sus anexos.

- **Starlette ≥ 1.0.1** en el lockfile por CVE-2026-48710 (evasión de
  autorización por la cabecera Host), en el catálogo de vulnerabilidades
  explotadas de CISA desde el 2026-09-02.
- **pnpm en su versión mayor actual (12.x)** en lugar de 10: desde la 11 espera
  24 horas antes de instalar versiones recién publicadas. La compatibilidad con
  Node 24 se comprueba al crear el andamiaje.
- **Archivo de tareas y herramientas:** `mise.toml` en la raíz fija Python, uv,
  Node y pnpm y nombra las tareas; `mise run verify` invoca el guion único. La
  versión de `mise` se fija en CI. Alternativa documentada: `just`.
- **Repositorio:**
  - un proyecto uv (grupos `dev`, `evals` y `synthetic`) y uno pnpm, sin
    workspaces ni Nx, Turborepo o moon;
  - `app/contracts/` guarda `openapi.json` y los JSON Schema generados desde
    Pydantic, con chequeo de deriva por `git diff --exit-code`.
- **Cliente de la API:** `@hey-api/openapi-ts` en versión exacta con TanStack
  Query, importado solo desde `frontend/src/shared/api`; `eslint-plugin-boundaries`
  y `typescript-eslint` `strict-type-checked`.
- **Acceso a datos:** SQLAlchemy 2 asíncrono con psycopg 3 como único driver,
  porque el checkpointer de LangGraph ya lo exige, y Alembic con SQL explícito
  para RLS. Se rechazan:
  - asyncpg: obligaría a mantener dos drivers;
  - SQLModel: sigue en 0.0.x;
  - `alembic_utils`: sin versiones desde 2025.
- **Pruebas:**
  - Hypothesis, incluido el modo con estado.
  - testcontainers con imagen pgvector, conectando con el rol del aplicativo.
  - Schemathesis en proceso.
  - vcrpy y respx para los adaptadores.
  - mutmut por hito sobre reglas, verificador, transición y punto de sesión.
  - Playwright con axe en cuatro a seis recorridos, solo Chromium en CI.
- **Calidad:**
  - Ruff `C901`, `PLR09xx`, `ASYNC`, `BLE001` y `TID251`.
  - `deptry` y `knip` bloquean; `vulture` solo advierte.
  - Sin radon ni xenon.
- **Cadena de suministro:**
  - gitleaks como primer trabajo. La protección de inserción de GitHub no existe
    en repositorios privados de cuenta personal: se activa al publicar, con una
    pasada única de trufflehog `--only-verified`.
  - Actions fijadas por SHA con la política del repositorio, `permissions: {}`
    por defecto y zizmor.
  - Espera de versiones: Dependabot con `cooldown` de 7 días,
    `exclude-newer = "7 days"` en uv y `minimumReleaseAge` en pnpm.
  - SBOM CycloneDX sin firma por hito, para el registro de licencias.
- **Minutos de CI en privado:** 2.000 al mes, con bloqueo al agotarse.
  `concurrency` cancela las corridas anteriores, y los filtros de rutas nunca
  apagan la compuerta de evaluaciones.

#### Confirmación

- `uv.lock` con Starlette ≥ 1.0.1 y `pnpm-lock.yaml` con la versión fijada de
  pnpm.
- zizmor y el chequeo de deriva de contratos en `verify.sh`.

---

## ADR-003: LangGraph como runtime del grafo

### Estado

Aceptada (2026-09-17).

### Contexto

P3 exige que el orquestador sea código; M2 y M16 piden cuatro nodos con contrato,
puntos de control y pausa hacia una persona; el PRD nombra `interrupt()` y los
puntos de control en PostgreSQL, y el caso de uso UC-5 espera un ADR de LangGraph
frente a CrewAI. La pregunta abierta OQ3 incluye el framework del grafo, y PA-3
pregunta cómo se aplica el aislamiento por aseguradora a las tablas de puntos de
control.

### Decisión

- LangGraph con estado tipado. La transición es una función pura que lee campos
  del estado y devuelve un nombre de nodo de un conjunto cerrado; ningún cliente
  de modelo está en su cadena de llamadas.
- La política de fallo de cada nodo (tiempo máximo, un reintento, texto de
  degradación) es un dato que ejecuta un envoltorio común.
- Punto de control por caso en PostgreSQL, con `thread_id` formado por la
  aseguradora y el caso; `interrupt()` pausa hacia la bandeja y la reanudación
  entrega la decisión con su comentario. `HumanReviewRequest` refleja la pausa
  para la bandeja y para su retiro (ADR-005).
- **PA-3:** las tablas de puntos de control llevan la aseguradora con RLS y
  entran en la aserción de esquema. La enmienda del 2026-09-17 establece con
  evidencia que el checkpointer oficial trabaja en autocommit, fuera de la
  aseguradora fijada por transacción, y deja a Functional Design de U12 la
  elección entre un pool por aseguradora y un checkpointer propio
  transaccional.
- La versión queda fijada en el lockfile, y solo Orchestration importa LangGraph.

### Consecuencias

- **Positivas:** persistencia, pausa, reanudación y streaming resueltos;
  framework reconocible para quien evalúa.
- **Negativas:** acoplamiento al framework dentro de Orchestration; actualizar
  versiones exige correr la compuerta; PA-3 puede obligar a un checkpointer
  propio.
- **Seguridad y cumplimiento:** los puntos de control guardan datos personales en
  claro mientras la conversación está viva, con la misma protección que el caso:
  RLS, cifrado en reposo y borrado nocturno de los de visitantes.

### Alternativas rechazadas

Lista original; la enmienda del 2026-09-17 la reemplaza con razones verificadas
en 2026.

- **Máquina de estados propia:** más código para puntos de control y pausas
  durables, y menos reconocible.
- **CrewAI:** agentes con roles que delegan por decisión del modelo, contra P3.
- **Pydantic AI graphs o Burr:** ecosistemas más pequeños y no los que nombra el
  PRD.
- **Temporal:** flujos durables, pero un servidor más que mantener.

### Enmienda del 2026-09-17

Investigación previa a Contract Design, con fuentes en `docs/reference/arquitectura-y-tecnologia.md` y sus anexos.

- **Versiones mínimas:**
  - `langgraph` ≥ 1.0.10 (en la práctica 1.2.x) y `langgraph-checkpoint` ≥ 4.1.1,
    por CVE-2026-28277 y CVE-2026-48775;
  - `LANGGRAPH_STRICT_MSGPACK=true`;
  - `get_state_history()` nunca recibe filtros del usuario;
  - nada de lo que está en beta (`DeltaChannel`, streaming v3).
- **Política de fallo:** se traduce a los `timeout=` y `error_handler=` nativos de
  la 1.2. El ejecutor común no duplica lo que el framework ya hace.
- **Reejecución tras `interrupt()`:** al reanudar, LangGraph ejecuta el nodo
  completo desde el principio.
  - Lo que llama al modelo o escribe fuera del grafo antes de pausar va en un
    nodo anterior o queda en el estado.
  - Los nodos son puros, y la persistencia derivada usa claves idempotentes:
    `CoverageAnswer` la guarda CitationVerifier.
- **Transición sin framework:** la función de transición vive en un módulo que no
  importa LangGraph y se prueba por tabla.
- **PA-3 con evidencia:** el checkpointer oficial toma conexiones del pool en
  autocommit, así que la aseguradora fijada por transacción no lo cubre.
  Functional Design de U12 elige entre:
  - un pool por aseguradora que fija la variable de sesión al crear la conexión;
  - un checkpointer propio que envuelve cada operación en una transacción.

  En los dos casos: columna de aseguradora, RLS y `FORCE ROW LEVEL SECURITY`.
- **Interrupción del asegurado en voz:** el estado guarda solo lo que
  efectivamente sonó; el canal de voz notifica el texto truncado.
- **Marco citado:** *Building effective agents* de Anthropic y 12-factor agents.
  El diseño es un flujo con pasos de IA donde el código es dueño del control.
- **Alternativas reescritas con evidencia de 2026.** Reemplazan la lista
  anterior, que rechazaba Pydantic AI y Burr por "ecosistemas más pequeños" y "no
  los que nombra el PRD":
  - **Pydantic AI v2 con pydantic-graph:** sin persistencia de grafos en
    Postgres; la durabilidad se delega a un motor externo; ventana sin rupturas
    de tres meses.
  - **Google ADK 2.0:** acopla al proveedor del modelo y rompió compatibilidad en
    la 2.0.
  - **OpenAI Agents SDK:** anterior a 1.0; bucle de agente sin grafo tipado.
  - **Microsoft Agent Framework 1.0:** sin checkpoint en Postgres para Python.
  - **LlamaIndex Workflows:** modelo por eventos, menos legible para P3.
  - **CrewAI:** agentes que delegan por decisión del modelo, contra P3.
  - **Temporal y DBOS:** otro servidor, o un segundo modelo de durabilidad
    encima de los puntos de control.
  - **Máquina de estados propia:** reimplementa pausa, reanudación y streaming.

#### Confirmación

- Contrato `forbidden`: `untangle.orchestration.nodes` no importa `langgraph`.
- Prueba de pureza de los cuatro nodos, y prueba de doble reanudación sin filas
  duplicadas.
- Prueba de aislamiento de puntos de control entre aseguradoras.

---

## ADR-004: Llamadas en proceso y ritmo de fondo sin broker

### Estado

Aceptada (2026-09-17).

### Contexto

FR2.3 exige dos ritmos: el turno responde de inmediato y la verificación, las
reglas y la revisión completa trabajan de fondo. Las prácticas prohíben hacer ese
trabajo dentro del turno de voz. El hospedaje es gratuito y lo opera una persona.

### Decisión

- Los componentes se llaman en proceso por interfaces síncronas.
- El trabajo de fondo corre como tareas asíncronas del mismo proceso que lanza
  Orchestration: precarga de la verificación al identificarse la persona,
  evaluación de reglas y revisión completa al cierre.
- Su resultado entra al estado del caso por la actualización de estado del grafo
  antes del turno que lo necesita; si el turno llega antes, la agente dice la
  frase de espera del catálogo antes de dos segundos.
- Cada ejecución de fondo queda como `NodeRun`; si el proceso muere, la
  reanudación relanza lo pendiente desde el punto de control.
- No hay broker de mensajes ni worker aparte.

### Consecuencias

- **Positivas:** ningún servicio más que mantener despierto; todo se reproduce
  en local con un comando.
- **Negativas:** el trabajo de fondo compite por CPU con el turno de voz en el
  mismo proceso (se mide en el experimento 1 y en NFR); escalar horizontalmente
  obligaría a revisar esta decisión; las escrituras concurrentes al estado se
  diseñan en Functional Design, apoyadas en los conjuntos de escritura por nodo.
- **Seguridad y cumplimiento:** ningún dato sale del proceso por una cola; la
  redacción en el punto único no cambia.

### Alternativas rechazadas

- **Cola y worker (Redis con Celery o RQ):** un segundo servicio gratuito que
  mantener y operar.
- **Ramas paralelas del grafo dentro de la ejecución del turno:** el turno
  esperaría a que termine el paso completo.
- **Bus de eventos:** complejidad sin un segundo consumidor que lo justifique.

### Enmienda del 2026-09-17

Investigación previa a Contract Design, con fuentes en `docs/reference/arquitectura-y-tecnologia.md` y sus anexos.

- **Durabilidad del trabajo de fondo sin broker:**
  - **Registro pendiente:** el `NodeRun` se inserta en la misma transacción que
    la actualización que lo origina.
  - **Supervisor en proceso:** guarda referencias fuertes a las tareas (el event
    loop solo guarda referencias débiles) y registra su excepción.
  - **Arrendamiento con latido:** `NodeRun` lleva `lease_owner`,
    `lease_expires_at`, `heartbeat_at`, `attempt`, `max_attempts` e
    `idempotency_key`, y se reclama con `FOR UPDATE SKIP LOCKED`.
  - **Barrido al arrancar y periódico, por aseguradora:** relanza desde el
    checkpoint lo que tenga el arrendamiento vencido.
  - **Idempotencia del gasto:** `SpendEntry` es único por ejecución e intento.
  - **Agotamiento:** al superar los intentos, el resultado es `unverifiable` y el
    caso se deriva.
- **Durabilidad de LangGraph:** `async` en el turno, y `sync` en los pasos de
  fondo cuyo resultado ve una persona.
- **CPU fuera del event loop:** redacción, fusión y serialización grande van a un
  hilo o a un pool, con semáforos por uso (voz, chat y fondo).
- **Turno de voz:**
  - una sola llamada al modelo, en streaming y sin herramientas;
  - el turno entra por un punto que ejecuta solo `intake` y lee lo precargado
    sin tocar la base en frío;
  - la frase de espera se dispara por reloj.
- **Hospedaje:** algunos planes gratuitos reinician el servicio en cualquier
  momento o no dan CPU fuera de una petición. Los trabajos programados usan un
  disparador externo o se ponen al día al despertar, según decida el intent
  `infra`.
- **Alternativas añadidas:**
  - **Procrastinate** con worker en proceso: diferida, si el código propio pasa
    de unas 200 líneas.
  - **DBOS y Absurd:** duplican la durabilidad de LangGraph.
  - **PgQueuer y pgmq:** esquema o primitiva extra sin ganancia.
  - **Hatchet:** un servicio aparte.
  - **`BackgroundTasks` de FastAPI:** sin durabilidad.
- **Señales medibles para reconsiderar Redis:**
  - más de un proceso con estado caliente compartido, cuando el chequeo de
    límites en Postgres agregue más de 5 a 10 ms al p95 del turno;
  - la voz en un proceso que exija estado en submilisegundos;
  - contención de `LISTEN/NOTIFY`;
  - horas de cómputo del Postgres gratuito agotadas por contadores;
  - trabajos de fondo que el sondeo no despache a tiempo.

#### Confirmación

- Prueba que mata el proceso con `SIGKILL` a mitad de un trabajo de fondo: se
  relanza, termina una sola vez y el gasto no se duplica.
- Ruff `ASYNC` sin hallazgos, y latencia del turno medida en el experimento 1.

---

## ADR-005: Estados del caso, retoma tras el límite y estado por campo

### Estado

Aceptada (2026-09-17), respuesta Q2 (PA-5) y hallazgos de los experimentos 2 y 3.

### Contexto

FR1.4 y US4.10 piden un modelo de estados cerrado; D18 fija resoluciones y tipos
de registro. AC5.12.1 deriva el caso al llegar al límite de tres minutos y
AC5.12.2 permite retomarlo dentro de quince minutos. El experimento 2 mostró que
el modelo inventa "sin lesiones" y "0 otras partes" cuando nadie lo dijo, y el
experimento 3 mostró transcripciones que cambian una negación sobre lesiones o
quién manejaba.

### Decisión

- **Estados:** `open`, `capturing`, `verifying`, `deciding`, `derived`,
  `awaiting_insured` y `closed`, con la tabla de correspondencia con los términos
  del PRD junto al enum; resoluciones `registered`, `approved`, `rejected` y
  `sent_to_insurer`; tipos `claim`, `coverage_inquiry` y `quote_request`. Las
  transiciones viven en una sola tabla versionada y cualquier otra se rechaza con
  un evento.
- **Única vuelta atrás:** de `derived` a `capturing`, solo cuando el motivo es el
  límite de la demostración, dentro de los quince minutos desde el fin de la
  llamada, desde el mismo navegador y sin ninguna decisión iniciada. Orchestration
  retira la pausa. Si el caso ya se decidió, no se retoma y la agente cuenta la
  decisión (FR8.5).
- **Estado por campo:** `not_stated`, `stated` o `confirmed`, cada uno con el
  turno que lo respalda. Lesiones, conductor y lugar solo quedan `confirmed`
  después de la confirmación; "ninguno" y 0 solo existen si la persona lo dijo.
  La completitud cuenta según el tipo de registro.
- **Número de caso:** prefijo de la aseguradora y seis dígitos.

### Consecuencias

- **Positivas:** el ciclo de vida se prueba entero por código; ningún dato de
  seguridad se inventa; en cada momento el caso tiene un solo dueño.
- **Negativas:** la transición excepcional se prueba con reloj inyectado en los
  bordes de 14:59 y 15:01; la extracción debe devolver estado y evidencia, lo que
  alarga el prompt.
- **Seguridad y cumplimiento:** retomar exige la clave del navegador o el enlace
  firmado, y un caso ajeno responde igual que uno inexistente (RT-4).

### Alternativas rechazadas

- **El caso sigue en la bandeja mientras se retoma (Q2 B):** alguien podría
  decidirlo mientras la llamada agrega datos, y "derivado" dejaría de ser un
  estado cerrado a la captura.
- **Esperar al asegurado durante la ventana (Q2 C):** cambia AC5.12.1, ya
  aprobado, y la persona no recibe el enlace al colgar.
- **Campos libres sin estado:** es lo que dejó inventar valores en el experimento 2.

### Enmienda del 2026-09-17

Investigación previa a Contract Design, con fuentes en `docs/reference/arquitectura-y-tecnologia.md` y sus anexos.

- **Fuente de verdad:** el caso es la fuente de verdad del negocio. El checkpoint
  de LangGraph solo guarda la ejecución reanudable, y `HumanReviewRequest` y
  `NodeRun` la reflejan (factor 5 de 12-factor agents). Una prueba reanuda dos
  veces y comprueba que nada se duplica.
- **Tabla de transiciones:** su diagrama Mermaid se genera desde la tabla y se
  compara con el versionado. Las pruebas incluyen propiedades con Hypothesis:
  ninguna secuencia de eventos llega a un estado ilegal.

---

## ADR-006: Modelo de lenguaje y planes por uso (enmienda de D-015)

### Estado

Aceptada (2026-09-17), con los datos del experimento 2 y la respuesta Q5.

### Contexto

D-015 eligió `gemini-2.5-flash-lite` en plan de pago para la voz y el trabajo de
fondo, el plan gratuito para el chat y las evaluaciones, y un techo de 5 USD en 90
días con alerta en 3 USD. El experimento 2 encontró:

- `gemini-2.5-flash-lite` responde 404 a cuentas nuevas.
- `gemini-3.1-flash-lite` y `gemini-3.5-flash-lite` empatan en extracción: el
  100 % tras aclarar la instrucción, sobre los mismos casos, así que no es una
  medición independiente.
- En el plan gratuito, el primer token tarda en p50 entre 1,1 y 2,4 s con 3.1 y
  entre 1,0 y 1,6 s con 3.5, con colas de más de 10 s.
- Con prompts del tamaño que supuso D-015, cualquiera de los dos pasaría la meta
  de costo de D7 (0,005 USD por minuto de llamada para el modelo).

La regla escrita antes de correr elige el modelo más barato que no invente y
cumpla el tiempo, y si ninguno cumple, revisa el diseño del turno.

En Q5, Miguel eligió mantener el chat público en el plan gratuito con un aviso,
sabiendo lo que dicen las condiciones de la API de Gemini: en el plan gratuito
Google usa lo enviado para mejorar sus productos, personas pueden leerlo, y piden
no enviar información personal.

### Decisión

- **Modelo:** `gemini-3.1-flash-lite`, anclado por identificador exacto y con
  razonamiento mínimo, en configuración versionada. Lo usan la extracción, las
  respuestas, la segunda pasada del verificador y la revisión completa. El juez
  de las evaluaciones se ancla aparte y se calibra (ADR-014).
- **Planes y claves por uso:**
  - **Voz y su trabajo de fondo:** plan de pago con crédito prepagado sin
    recarga automática. Se activa solo cuando la voz se publique y el prepago lo
    decide Miguel en ese momento.
  - **Chat público y vista de comparación:** plan gratuito con proyecto y clave
    propios, incluidos los embeddings de sus preguntas (Q5).
  - **Evaluaciones y generación de datos:** plan gratuito con proyecto y clave
    propios, solo con datos sintéticos.
- **Aviso del chat público (Q5):**
  - **Cuándo:** antes de cualquier texto del visitante, el primer mensaje dice
    que es una demostración con pólizas de ejemplo y pide no escribir datos
    reales, porque el modelo corre en un plan gratuito que puede usar lo escrito
    para mejorar sus productos. El texto exacto va al catálogo en los dos idiomas.
  - **Cómo lo sostiene la agente:** nunca pide datos reales y sugiere los datos
    de la póliza de ejemplo.
- **Presupuesto del turno de voz:** como máximo unos 3.900 tokens de entrada por
  turno para cumplir D7 con 15 turnos cada tres minutos, sin contar el trabajo de
  fondo. La respuesta sale en streaming y, si falta un resultado de fondo, la
  frase de espera.
- **Latencia de la voz:** en el plan gratuito no se cumple. Se mide en el plan de
  pago dentro del experimento 1, con un gasto que decide Miguel. Si tampoco se
  cumple, primero se revisa el diseño del turno y después las alternativas que ya
  prevé D-015, como Groq; nunca se sube de modelo a ciegas.
- **Techo:** sigue en 5 USD en 90 días, con alerta en 3 USD. Con el tamaño de
  prompt que estimó D-015 alcanza para entre 105 y 160 llamadas de cuatro minutos
  con 3.1, en lugar de 400. La revisión del día 30 (OQ6) decide si sube.

### Consecuencias

- **Positivas:** el modelo más barato que cumplió la extracción; el chat público
  no gasta el techo.
- **Negativas:** la latencia de la voz sigue abierta; la cuota del plan gratuito
  puede frenar el chat con tráfico y activa el modo degradado de FR4.6; el techo
  cubre menos llamadas de las que supuso D-015.
- **Seguridad y cumplimiento:**
  - **Riesgo aceptado por Miguel en Q5:** lo que escriba un visitante en el chat
    público o en la comparación llega al plan gratuito de Gemini, donde Google
    puede usarlo y personas pueden leerlo. El aviso lo mitiga, pero depende de que
    el visitante lo respete.
  - **Excepción regional:** quien visita desde el Espacio Económico Europeo,
    Suiza o el Reino Unido recibe las condiciones del plan de pago.
  - **Honestidad (P7):** el README lo dice.
  - **Del lado del proyecto:** se mantienen la redacción antes de persistir y el
    borrado nocturno; lo que Google retenga queda fuera de su control.
  - **Voz:** el plan de pago no usa lo enviado para entrenar.

### Alternativas rechazadas

- **`gemini-2.5-flash-lite`:** no está disponible para cuentas nuevas.
- **`gemini-3.5-flash-lite`:** misma extracción, más caro (0,30 y 2,50 USD por
  millón de tokens de entrada y salida) y con la peor cola medida (30,5 s).
- **Claude Haiku 4.5:** descartado por costo desde D-015.
- **Modelo local:** el computador no lo sostiene (D-015).
- **Chat público en el plan de pago (Q5 A):** era la recomendación; Miguel no la
  eligió para no gastar el techo en el chat.
- **Chat gratuito redactando antes de enviar al modelo (Q5 C):** la agente no
  podría anotar placas, teléfonos ni cédulas escritos.

### Enmienda del 2026-09-17

Investigación previa a Contract Design, con fuentes en `docs/reference/arquitectura-y-tecnologia.md` y sus anexos.

- **Retiro del modelo:** Google anuncia el apagado de `gemini-3.1-flash-lite` el
  2027-05-07, con `gemini-3.5-flash-lite` como reemplazo. No afecta los 90 días.
- **Un proyecto por uso:** Gemini aplica los límites por proyecto y no por clave.
  Cada uso (voz, chat, evaluaciones y operación) vive en su propio proyecto con
  su clave.
- **Topes del proveedor:** solo existen en el plan de pago, son mensuales y
  reaccionan en ventanas de 10 minutos. El techo acumulado de 5 USD sigue siendo
  del aplicativo (ADR-015).
- **Caché:** la caché de contexto explícita no existe en el plan gratuito. Los
  prompts ponen primero lo estable para aprovechar la caché implícita en el plan
  de pago.

---

## ADR-007: Transcripción con Deepgram `nova-3` en modo `multi`

### Estado

Aceptada (2026-09-17), con los datos del experimento 3.

### Contexto

El riesgo R4 se dispara si la transcripción se equivoca en más del 15 % de las
palabras con acento paisa. El experimento 3, con la voz de Miguel en un cuarto
silencioso y leyendo frases, midió:

- **Error por palabra en español:** 5,6 % con `nova-3:multi` y 8,6 % con
  `nova-3:es` y `es-419`, que dieron transcripciones idénticas.
- **Datos dictados en español:** llegaron exactos, 8 de 8.
- **Errores que cambian el sentido:** una negación sobre lesiones con `es`, y
  quién manejaba con `multi`.
- **Inglés:** las cifras no son atribuibles al servicio porque el hablante no es
  nativo; hubo una K transcrita como Q en una placa.
- **Formato inteligente:** pegó la palabra dicha "dash" a un número de póliza.

PA-2 pregunta si hay confianza por palabra. Deepgram trae 200 USD de crédito, y
las fuentes públicas no coinciden en el precio de `multi` en streaming.

### Decisión

- **Modo:** Deepgram `nova-3` en modo `multi` para los dos idiomas, en
  streaming, con formato inteligente en los turnos de datos.
- **Confianza (PA-2):** la confianza por palabra decide cuándo pedir que se
  repita (AC1.23.3); Functional Design comprueba su forma en streaming.
- **Normalización:** limpia los separadores dichos dentro de los códigos; las
  letras confundibles se leen con palabra y los campos de seguridad se confirman
  en voz alta (ADR-005).
- **Clave y proveedor:** clave del uso voz, detrás de la interfaz de transcripción
  de ProviderGateway.
- **Precio y crédito:** el precio de lista se toma de la consola al construir el
  adaptador. Nunca se agrega tarjeta sin la decisión de Miguel, porque el plan de
  pago de Deepgram activa la recarga automática por defecto.

### Consecuencias

- **Positivas:** el menor error medido en español, detección de idioma sin
  selector y datos dictados exactos.
- **Negativas:** una sola voz, habla leída, cuarto silencioso y micrófono del Mac
  no cierran R4 para el acento en general (lo mide DS-5 por hito); `multi` puede
  costar más que el modo de un idioma.
- **Seguridad y cumplimiento:** el audio viaja a Deepgram y el aplicativo no lo
  guarda (NFR19); las transcripciones se redactan antes de persistirse; las voces
  de terceros en DS-5 requieren consentimiento.

### Alternativas rechazadas

- **`nova-3` con `es` o `es-419`:** más error y perdió una negación, sin
  detección automática de idioma.
- **Whisper en servidor propio:** sin GPU gratuita no alcanza la latencia.
- **Otros proveedores (AssemblyAI, Google):** no se midieron y exigirían otro
  experimento.

---

## ADR-008: Síntesis: Catalina de Cartesia provisional y voz de respaldo por elegir

### Estado

Aceptada la voz principal provisional (2026-09-17); la voz de respaldo queda
propuesta, pendiente del experimento 1.

### Contexto

D-016 pide una sola voz femenina paisa para los dos idiomas. El experimento 4
encontró:

- **ElevenLabs:** el plan gratuito rechaza por API las voces de su biblioteca
  (402).
- **Catalina de Cartesia (`es-CO`):** sacó 4,25 en "suena de Medellín" y 4,5 en
  "suena real", y en la comprobación del inglés conservó su identidad, con el
  audio de control de otra voz calificado con 1.
- **Límite:** escuchó una sola persona, y la regla pide tres personas de
  Medellín en la sesión de la semana 9 (S6).

FR3.8 y US5.11 exigen una voz de respaldo cuando se agota el presupuesto, con la
excepción de D17. Deepgram Aura-2 tiene voces en español con acento colombiano y
algunas cambian entre inglés y español. Kokoro es un modelo abierto que corre en
el propio servidor.

### Decisión

- **Voz principal:** Cartesia con el modelo `sonic-3.6` y la voz Catalina, en el
  plan gratuito, configurada por aseguradora.
- **Adopción provisional:** se confirma en la sesión de escucha de la semana 9.
  Si no pasa, se cambia por configuración: plan B (voz latinoamericana neutra),
  plan C (clon con consentimiento) o una voz paisa de ElevenLabs si Miguel decide
  pagarla.
- **Reserva:** la de cada llamada se calcula sobre los créditos mensuales de
  Cartesia (UsageBudget).
- **Voz de respaldo:** se elige en el experimento 1 entre Deepgram Aura-2 (mismo
  crédito que la transcripción y sin carga de CPU) y Kokoro en el propio servidor
  (gratis, pero compite por CPU con la agente).
- **Prueba de contrato:** las dos van detrás de la interfaz de síntesis con su
  prueba de formato y latencia.

### Consecuencias

- **Positivas:** voz principal sin costo y cambio de proveedor por configuración.
- **Negativas:** la calificación es de una sola persona; los 604 ms al primer byte
  se midieron por HTTP desde el Mac y no representan la llamada, que se mide por
  WebSocket desde el servidor en el experimento 1.
- **Seguridad y cumplimiento:** la licencia y la atribución de la voz se
  registran antes de publicar; el aplicativo no guarda audio.

### Alternativas rechazadas

- **Mariana de Cartesia:** no sonó paisa y en inglés sonó como otra persona.
- **Voces paisas de ElevenLabs:** exigen un plan de pago; es un gasto que decide
  Miguel frente al techo y a la regla de cero renovaciones.
- **Clon de voz:** requiere consentimiento y trabajo; queda como plan C.

---

### Enmienda del 2026-09-21 — lo que midió el experimento 1

Medido con `mise run experimento:1`, cinco vueltas, cola de cada tramo
(desde que termina la entrada hasta que empieza la salida), **en plan gratuito**:

| Tramo | Mínimo | Mediana |
| --- | --- | --- |
| Transcripción (Deepgram `nova-3` multi) | 128 ms | 168 ms |
| Modelo, primer token (Gemini `3.1-flash-lite`) | 2.111 ms | 4.568 ms |
| Voz principal, primer byte (Cartesia `sonic-3.6`) | 258 ms | 281 ms |
| Voz de respaldo, primer byte (Deepgram `aura-2-celeste-es`) | 345 ms | 609 ms |
| **Turno completo** | **2.530 ms** | **5.147 ms** |

**Lo que decide para esta ADR.** Cartesia queda confirmada como voz principal
también por latencia: su mediana es menos de la mitad que la de Aura-2 y además
es más estable. Aura-2 es viable como respaldo. **Kokoro sigue sin medir**, así
que la elección del respaldo está decidida en su mitad y no entera. Los 604 ms
que esta ADR registró antes eran por HTTP desde el Mac; por el camino real bajan
a 281 ms.

**Lo que decide para todo el canal de voz, y es lo más importante que salió.**
NFR1 pide del fin del habla al primer audio **p50 menor que 500 ms**. Solo la
transcripción y la voz, sin ningún modelo en medio, ya suman unos 449 ms de
mediana: el presupuesto entero. Así que **el modelo no puede estar entre el fin
del habla y el primer audio, en ningún plan**: incluso uno de pago tendría que
dar su primer token en unos 50 ms, y ningún modelo hospedado lo hace. El primer
audio tiene que salir de algo que no espera al modelo —una frase de espera ya
sintetizada, que es lo que `team.md` prevé en el manejador del turno—, y el
modelo contesta mientras esa frase suena. Esto no es una limitación del plan
gratuito: es una restricción de la arquitectura en cascada, y U16 se diseña
desde ahí.

**Lo que el plan gratuito sí empeora.** Un primer token de 2 a 16 segundos
—la dispersión entre corridas fue enorme— no lo tapa ninguna frase de espera.
Por eso esta ADR ya decía "en plan de pago", y ahora se sabe por qué. La cifra
de plan de pago queda pendiente.

**Un defecto del propio experimento, corregido antes de publicar.** La primera
versión daba 0 ms de transcripción —imposible por red— y cortaba la frase a la
mitad, porque paraba en el primer segmento final que encontraba en el búfer.
Ahora mide la llegada de la respuesta forzada con `Finalize`, que es lo que
Deepgram documenta, y la transcripción llega entera.

### Enmienda del 2026-09-21 — las dos mitades pendientes, cerradas por Miguel

**Voz principal: Catalina de Cartesia, definitiva.** Deja de ser provisional.
Miguel hizo dos escuchas a ciegas que confirmaron que suena de Medellín, y
comparó la voz con la que publica la página oficial de Cartesia: es la misma que
se eligió. En sus palabras: *"ya hice dos pruebas de Catalina, la escuché a
ciegas que efectivamente confirmamos que es la voz Paisa, así que no le veo
necesidad de hacer otra prueba"*. La sesión de escucha de la semana 9 que esta
ADR preveía para confirmarla ya no hace falta. El límite queda dicho: una sola
persona, en dos escuchas.

**Voz de respaldo: Aura-2 de Deepgram.** Decisión de Miguel sobre la
recomendación, el mismo día. Razones: ya está medida (609 ms de mediana del
último byte al primer audio, contra 281 ms de Cartesia); va con la misma cuenta
de Deepgram que la transcripción, así que no agrega proveedor ni clave; y no hay
nada que descargar ni que correr en el servidor. **Kokoro no se mide**: correr un
modelo de síntesis en un servidor gratuito sin GPU probablemente quedaría lejos
de la latencia que pide NFR1, y medirlo costaría tiempo para descartarlo casi
seguro. En español se midió la voz `aura-2-celeste-es`; el identificador por
idioma lo fija U15 en su configuración.

---

## ADR-009: Librería de voz pendiente del experimento 1

### Estado

Propuesta, pendiente del experimento 1 (respuesta Q4).

### Contexto

El PRD deja la elección entre LiveKit Agents y Pipecat. El experimento 1 mide la
integración con un grafo explícito, la parada ante interrupción en menos de
300 ms y una llamada de tres minutos en hospedaje gratuito (riesgos R10 y R2,
supuesto A1). Las dos tienen componentes de React sobre shadcn, así que WebClient
sirve con cualquiera.

### Decisión

- La frontera de VoiceChannel queda fija: el grafo no importa nada de la librería
  de voz, y la transcripción y la síntesis entran por las interfaces de
  ProviderGateway envueltas como complementos de la librería.
- El experimento 1 corre antes de construir la voz, que llega después del camino
  completo en texto, y decide con estos criterios:
  - Latencia del fin del habla al primer audio, en p50 y p95.
  - Parada ante interrupción.
  - Cero importaciones de la librería de voz en el grafo.
  - Cinco llamadas de tres minutos sin cortes.
  - Hospedaje que no se duerma a mitad de llamada ni permita gastar por encima
    del plan gratuito.
  - Tipo de transporte: relevo de audio gestionado o WebRTC directo.
  - Detección de turno en español.
- Si ninguna cierra en tres días, se aplica la mitigación de R10: un adaptador
  propio detrás de una interfaz de una sola función.
- El resultado actualiza esta decisión antes de construir la voz.

### Consecuencias

- **Positivas:** ni el diseño ni la base se frenan.
- **Negativas:** la estimación de la voz queda incierta hasta el experimento; el
  hospedaje de la voz (A1) sigue sin validar.
- **Seguridad y cumplimiento:** el proveedor de transporte ve el audio en tránsito;
  su clave va separada por uso y sus límites se configuran también en el
  proveedor.

### Alternativas rechazadas

- **Decidir ahora sin datos:** arriesga elegir un transporte que no funcione en
  hospedaje gratuito.
- **Correr el experimento ahora (Q4 B):** frena la etapa hasta tres días y exige
  abrir cuentas antes de que la voz haga falta.

### Enmienda del 2026-09-17

Investigación previa a Contract Design, con fuentes en `docs/reference/arquitectura-y-tecnologia.md` y sus anexos.

- **Speech-to-speech rechazado para la v1** (Gemini 3.8 Live, publicado el
  2026-09-15):
  - solo admite voces precargadas, así que no puede ser Catalina (P10);
  - entrega audio y el texto llega a la par, así que la guardia no lo revisa
    antes de que suene;
  - cuesta unas 4,6 veces la meta D7 solo en audio.

  Queda como experimento posterior a la v1: cascada frente a voz nativa sobre
  DS-5, publicado aunque la cascada pierda en latencia.
- **Consistencia ante interrupciones:** la librería elegida debe notificar el
  texto que efectivamente sonó (ADR-003).

---

## ADR-010: Corpus por aseguradora en su idioma y recuperación híbrida en PostgreSQL

### Estado

Aceptada (2026-09-17), respuesta Q1 (PA-1).

### Contexto

PA-1 pregunta en qué idioma escribe cada aseguradora sus pólizas; AC2.3.4 muestra
la cláusula en su idioma original con el resumen en el de la conversación. El PRD
pide un índice híbrido léxico y vectorial por aseguradora, con pgvector como
hipótesis, y M9 exige aislamiento. Hay preguntas en un idioma sobre pólizas
escritas en el otro.

### Decisión

- **Idioma:** Stonecroft Mutual escribe en español, Sunmeadow Auto en inglés y
  Knotwell guarda las copias de cada emisora en el idioma de la emisora,
  etiquetadas por emisora.
- **Fragmentos:** un fragmento por cláusula, con identificador estable y versión.
- **Índice:** PostgreSQL con pgvector para los embeddings y búsqueda de texto
  completo por idioma, fusionadas por rango recíproco. Los filtros por aseguradora
  (RLS) y por póliza emitida (formulario, versión y endosos) se aplican antes de
  ordenar.
- **Embeddings:**
  - **Modelo:** un modelo multilingüe de Gemini anclado por identificador exacto;
    el candidato es `gemini-embedding-001` truncado a 768 dimensiones.
  - **Claves:** la del uso operación para la ingesta y la del canal para las
    consultas.
  - **Cambio de modelo:** reconstruye el índice y pasa la compuerta de
    evaluación.

### Consecuencias

- **Positivas:** el mismo motor y el mismo mecanismo de aislamiento que el resto,
  así que la recuperación queda aislada por construcción; recuperación entre
  idiomas por embeddings; la mitad del texto que generar.
- **Negativas:** la búsqueda léxica no cruza idiomas, así que esas preguntas
  dependen del lado vectorial; los embeddings dependen de una API externa, con su
  latencia en el ritmo de fondo y no en el turno.
- **Seguridad y cumplimiento:**
  - **Corpus:** es sintético.
  - **Pólizas emitidas:** llevan datos personales ficticios, con RLS y cifrado.
  - **Chat público:** sus consultas pasan por el plan gratuito, con el riesgo que
    Miguel aceptó en ADR-006.

### Alternativas rechazadas

- **Pólizas bilingües (Q1 B):** el doble de texto y comprobar que las versiones
  digan lo mismo.
- **Todo en inglés (Q1 C):** quien habla español nunca ve una cláusula en su idioma.
- **Base vectorial dedicada (Qdrant, Pinecone):** un segundo mecanismo de
  aislamiento sin RLS y un servicio más.
- **Embeddings locales:** memoria y CPU en hospedaje gratuito.
- **Solo búsqueda léxica:** no recupera entre idiomas.

### Enmienda del 2026-09-17

Investigación previa a Contract Design, con fuentes en `docs/reference/arquitectura-y-tecnologia.md` y sus anexos.

- **Sin índice aproximado:**
  - Con unas pocas miles de cláusulas, la búsqueda vectorial es exacta dentro del
    conjunto filtrado, con índice B-tree sobre aseguradora, formulario y versión.
    Da recall perfecto y resultados deterministas para DS-3.
  - Con HNSW, el filtro y RLS se aplican después de recorrer el índice, y una
    consulta puede devolver menos cláusulas de las pedidas.
  - Se reabre si el p95 de la subconsulta supera 20 ms o hay más de 50.000 filas
    por aseguradora; entonces, índice parcial por aseguradora con
    `hnsw.iterative_scan = strict_order`.
- **Búsqueda de texto:** configuración por idioma de la fila, con `unaccent` y
  stemmer, y consultas con `websearch_to_tsquery`.
- **Fusión:** RRF con k = 60 y desempate estable por identificador de cláusula.
- **Contexto estructural sin modelo:** el generador antepone a cada cláusula
  aseguradora, formulario, versión, parte, sección, términos definidos y endoso
  que la modifica, en el texto que se embebe y en el que se indexa.
- **Embeddings:** vectores truncados a 768 y normalizados; `task_type` de
  documento y de consulta; pgvector ≥ 0.8.2.
- **Relaciones entre cláusulas:**
  - Entidad `ClauseRelation` de PolicyCorpus, con RLS, generada con el corpus. Tipos cerrados:
    `modifies_exclusion`, `reopens`, `restricts`, `replaces`,
    `defines_term_used_by` y `references`.
  - Tras la fusión, una consulta recursiva de profundidad 2, con detección de
    ciclos, agrega los endosos vigentes de la póliza emitida y las definiciones
    que la respuesta necesita.
  - Se llama "relaciones entre cláusulas", nunca "GraphRAG".
- **Caché de embeddings** en Postgres solo para textos curados (golden sets,
  preguntas sugeridas y corpus). Nunca de mensajes libres de visitantes, porque
  un embedding permite reconstruir el texto.
- **Medición en DS-3:**
  - recall@k y MRR por idioma;
  - cierre@k;
  - intrusión de distractores, que debe ser cero entre aseguradoras;
  - subconjunto entre idiomas;
  - ablación por hito.
- **Alternativas añadidas:**
  - **Bases de grafos y GraphRAG** (Neo4j, FalkorDB, Apache AGE, LightRAG,
    Microsoft GraphRAG): en QA legal ganan pocos puntos a cambio de mucho costo,
    suman un servicio sin RLS y sus planes gratuitos pausan o borran los datos.
  - **Extensiones BM25** (ParadeDB, `pg_textsearch`, VectorChord): licencia AGPL
    o retirada en Neon, y con RLS mezclan estadísticas entre aseguradoras.
  - **Reordenador local:** no cabe con holgura en una instancia gratuita y
    compite con la voz.
  - **Recuperación contextual generada por el modelo:** costo sin necesidad.
  - **Caché semántica de respuestas:** dos preguntas casi iguales pueden tener
    respuestas opuestas, y la respuesta cacheada se saltaría el verificador.
  - **Reordenador por API:** diferido, solo si DS-3 muestra la cláusula correcta
    en el top-20 pero fuera del top-k.

---

## ADR-011: Verificador exacto de citas con resultados cerrados

### Estado

Aceptada (2026-09-17).

### Contexto

P2 y M4 prohíben citar una cláusula inexistente; NFR6 exige cero citas
inexistentes y NFR5 al menos 95 % de precisión. Las prácticas piden distinguir
"no encuentro una cláusula que lo cubra" de "no pude verificar".

### Decisión

- CitationVerifier solo acepta identificadores del conjunto recuperado para esa
  respuesta.
- **Consulta exacta:** la cláusula existe, pertenece a la aseguradora y a la
  póliza (formulario, versión y endosos vigentes) y está vigente.
- **Respaldo:** una segunda pasada del modelo, limitada al texto de la cláusula,
  más reglas.
- **Resultado:** `verified`, `rejected`, `no_clause_found` o `unverifiable`. El
  último aparece cuando falla el proveedor o la base de datos y nunca se colapsa
  con `no_clause_found`.
- Cada comprobación se guarda (`CitationCheck`) y va a la traza.
- Una cita emitida sin resultado `verified` bloquea la entrega.

### Consecuencias

- **Positivas:** la compuerta se calcula por código, sin depender del juez.
- **Negativas:** una llamada al modelo por cláusula citada, en el ritmo de fondo;
  la comprobación de respaldo no es perfecta y la mide DS-3.
- **Seguridad y cumplimiento:** el texto de la cláusula entra como dato
  delimitado en la segunda pasada, contra la inyección indirecta (RT-2).

### Alternativas rechazadas

- **Confiar en las instrucciones del modelo:** no hay compuerta comprobable.
- **Umbral de similitud:** no prueba que el texto sostenga la afirmación.
- **Revisión humana de cada cita:** no escala y rompe la demo.

### Enmienda del 2026-09-17

Investigación previa a Contract Design, con fuentes en `docs/reference/arquitectura-y-tecnologia.md` y sus anexos.

- **Endosos que modifican la cita (decisión de Miguel):** además de existencia,
  pertenencia y vigencia, el verificador sigue las relaciones entre cláusulas
  (ADR-010). Si un endoso vigente de la póliza modifica la cláusula citada y la
  respuesta no lo considera, el resultado es `rejected` y el caso se deriva. Es
  una regla por código, sin juez.
- **Registro de la respuesta:** CitationVerifier guarda `CoverageAnswer` con clave
  idempotente por caso y turno. El nodo `policy_verification` queda puro.
- **A evaluar en Functional Design:** que el modelo elija identificadores de
  cláusula y la respuesta cite el texto literal desde la base con plantilla del
  catálogo, en lugar de parafrasear.

#### Confirmación

- Casos de DS-3 con una exclusión reabierta por un endoso: la respuesta que lo
  ignora sale `rejected`.
- mutmut por hito sobre el verificador.

---

## ADR-012: Aislamiento por aseguradora e identidad

### Estado

Aceptada (2026-09-17).

### Contexto

M9, FR9.1 a FR9.4 y el riesgo R8 exigen aislamiento en la base de datos; RT-4
prueba el acceso a un caso ajeno. D23 descarta publicar credenciales y FR8.7 da
al visitante un enlace firmado de una hora; D6 limita ese enlace a la vista del
caso. Las prácticas piden un punto único de sesión y una aserción de esquema.

### Decisión

- **Base de datos:**
  - **RLS:** en toda tabla del aplicativo, con la columna de aseguradora.
  - **Sesión:** TenantIdentity abre la única sesión y fija la aseguradora en la
    transacción antes de devolverla.
  - **Aserción:** una prueba falla si alguna tabla carece de RLS o de política,
    incluidas las de puntos de control (ADR-003).
  - **Rol:** el rol del aplicativo no puede saltarse RLS.
- **Credenciales:** tokens firmados con aseguradora y rol, generados por un guion
  para Miguel, el despliegue local y las pruebas; nunca se publican (D23).
- **Enlaces de visitante:** firmados, de una hora, ligados a un caso y a un modo
  de acceso (decidir o solo lectura), revocables y borrados cada noche.
- **Clave del navegador:** en una cookie `HttpOnly`, `Secure` y `SameSite`;
  limita chat, consola y resúmenes de traza a su dueño.
- **Casos ajenos:** responden igual que uno inexistente.
- **Configuración:** en carpetas versionadas por aseguradora; un chequeo prohíbe
  `tenant_id` literales fuera del cargador y las fixtures.

### Consecuencias

- **Positivas:** aislamiento en la base de datos y en el código, probado por
  DS-8.
- **Negativas:** toda consulta pasa por el punto de sesión (lo vigila una regla
  de importación); RLS exige cuidado en migraciones y en el pool de conexiones.
- **Seguridad y cumplimiento:** las claves de firma salen del entorno o de un
  gestor de secretos y se rotan si se filtran; un enlace nunca abre la lista.

### Alternativas rechazadas

- **Un esquema por aseguradora:** migraciones y conexiones multiplicadas.
- **Filtrar solo en el código:** un `WHERE` olvidado filtra datos.
- **Keycloak:** es un Could (C2) y un servicio más.
- **Credenciales de demo publicadas:** contradicen FR8.7 y D23.

### Enmienda del 2026-09-17

Investigación previa a Contract Design, con fuentes en `docs/reference/arquitectura-y-tecnologia.md` y sus anexos.

- **Roles:** el rol que migra es dueño de las tablas; el rol del aplicativo no es
  dueño y tiene `NOBYPASSRLS`. Toda tabla lleva `FORCE ROW LEVEL SECURITY`,
  porque sin eso el dueño se salta RLS.
- **Variable de aseguradora:** `set_config('app.tenant_id', …, true)` dentro de
  una transacción explícita. Las políticas usan
  `NULLIF(current_setting('app.tenant_id', true), '')` envuelto en
  `(select …)`, porque al terminar la transacción la variable vuelve a cadena
  vacía y no a `NULL`.
- **Aserción de esquema ampliada:** RLS habilitado y forzado, política presente y
  rol del aplicativo sin `BYPASSRLS`. Incluye las tablas de puntos de control,
  `ClauseRelation`, `QuotaCounter` e `InboxEvent`.
- **Pruebas de DS-8:**
  - Corren contra Postgres real con testcontainers, conectando con el rol del
    aplicativo: la imagen oficial crea un superusuario que pasaría las pruebas sin
    aislamiento.
  - Una prueba falla si una consulta del aplicativo corre en autocommit fuera del
    punto único.
- **Seguro por defecto:** una prueba recorre las rutas y falla si alguna no exige
  identidad y no está en la lista explícita de rutas públicas.

#### Confirmación

- Aserción de esquema y pruebas de DS-8 con el rol del aplicativo en
  `verify.sh`.

---

## ADR-013: Redacción en un punto único y segundo detector independiente

### Estado

Aceptada (2026-09-17).

### Contexto

M6, NFR11 y RT-14 exigen cero datos personales en trazas, logs y exportaciones.
Las prácticas piden dos detectores de mecanismos distintos, reconocedores propios
para placa, cédula, teléfono y número de póliza, y medir por idioma y por tipo de
entidad. D20 muestra en la consola cada dato personal como una etiqueta de su tipo.

### Decisión

- **PiiRedaction:**
  - **Detección:** Presidio con modelos de spaCy en español e inglés y
    reconocedores propios para placas, cédulas, teléfonos y números de póliza,
    con los formatos de los dos idiomas.
  - **Salida:** cada dato se reemplaza por una etiqueta de su tipo.
  - **Punto único:** es la única vía hacia la transcripción, los logs, las
    trazas, las exportaciones, el reporte de evaluación y la transcripción en vivo
    de la consola; esas salidas solo aceptan contenido ya redactado.
  - **Dependencias:** ni la red ni modelos de lenguaje.
- **Segundo detector en Evaluation, de otro mecanismo:**
  - **Canarios:** un escáner determinista busca en las exportaciones cada valor
    personal que el generador sintético conoce, exacto y normalizado.
  - **Formatos:** expresiones de formato independientes de las de Presidio.
  - **Reporte:** por idioma y por tipo de entidad, y cualquier hallazgo bloquea.

### Consecuencias

- **Positivas:** la compuerta no depende del código que verifica; los canarios no
  tienen falsos negativos sobre los datos sembrados.
- **Negativas:** los canarios no encuentran datos reales no sembrados del chat
  público (los cubren parcialmente los formatos y Presidio); los modelos de spaCy
  pesan en el despliegue; los reconocedores se mantienen.
- **Seguridad y cumplimiento:** los campos estructurados del caso quedan en claro
  bajo RLS y cifrado, porque la operación los necesita.

### Alternativas rechazadas

- **Un solo detector:** no hay verificación independiente.
- **Redacción con un modelo de lenguaje:** no determinista, lenta, con costo y
  enviando los datos personales al modelo.
- **Un segundo modelo de reconocimiento de entidades:** mismo mecanismo y fallos
  correlacionados.

### Enmienda del 2026-09-17

Investigación previa a Contract Design, con fuentes en `docs/reference/arquitectura-y-tecnologia.md` y sus anexos.

- **Contenido en trazas:** los atributos de contenido de OpenTelemetry se llenan
  solo después de redactar, nunca con la captura automática de una
  instrumentación de terceros (ADR-015).
- **Pruebas de los reconocedores:** Hypothesis genera placas, cédulas, teléfonos
  y números de póliza por formato e idioma, con espacios, guiones y mezcla de
  idiomas (RT-15).

#### Confirmación

- Los canarios del segundo detector corren sobre las trazas que CI exporta como
  artefacto; cualquier hallazgo bloquea.

---

## ADR-014: Evaluación con corredor propio sobre pytest y juez propio calibrado

### Estado

Aceptada (2026-09-17).

### Contexto

M8 y FR11 piden golden sets por caso, compuertas duras, regresión por caso,
calibración del juez contra DS-7 y corridas no comparables; las prácticas dejan
la herramienta (promptfoo o DeepEval) para un ADR de Incepción. El servidor va en
Python. PA-11 duda de que la corrida completa quepa en diez minutos en el plan
gratuito.

### Decisión

- **Corredor:** propio, sobre pytest y con un solo comando del archivo de tareas.
  Carga los golden sets desde sus archivos versionados, conduce las
  conversaciones por el adaptador de texto de ChatChannel con el respondedor por
  reglas, y fija temperatura, semilla, modelo y versiones de prompt.
- **Criterios de código y compuertas duras:** en código propio.
- **Criterios con juez:** juez propio con prompts versionados, calibrado con TPR
  y TNR por criterio e idioma (enmienda del 2026-09-17, que reemplaza las
  métricas de DeepEval).
- **Reporte:** generador propio con cada caso, criterio e idioma lado a lado, la
  diferencia contra la línea base, las etiquetas "no medida" e "inestable", la
  sección "Cómo falla" y las cinco cifras.
- **Duración (PA-11):** si la corrida completa no cabe en el plan gratuito o en
  diez minutos, corre un subconjunto declarado y reproducible que fija
  `nfr-requirements`.

### Consecuencias

- **Positivas:** la lógica de la compuerta es auditable en el repositorio, con
  herramientas reconocibles.
- **Negativas:** código propio de reporte que mantener; la versión y la telemetría
  de DeepEval requieren vigilancia; la cuota por minuto del plan gratuito puede
  alargar la corrida completa.
- **Seguridad y cumplimiento:** los datos de evaluación son sintéticos; las
  trazas exportadas pasan por el segundo detector; el juez recibe transcripciones
  redactadas.

### Alternativas rechazadas

- **promptfoo como corredor principal:** pensado para prompts de un turno; las
  conversaciones con respondedor por reglas y el grafo en proceso quedan
  forzadas.
- **DeepEval como compuerta completa:** su aprobado o fallido no expresa la
  regresión por caso, las corridas no comparables ni la calibración del juez.
- **Plataformas de evaluación gestionadas:** los datos salen del repositorio y
  tienen costo.

### Enmienda del 2026-09-17

Investigación previa a Contract Design, con fuentes en `docs/reference/arquitectura-y-tecnologia.md` y sus anexos. Decisión de Miguel. El título anterior terminaba en "y DeepEval para el
juez".

- **Juez propio**, detrás de la interfaz que esta decisión ya preveía: prompt
  versionado por criterio, salida estructurada de Gemini y parser, con pruebas.
  Se retira DeepEval:
  - 46 versiones en 2026 y una 4.0 reposicionada hacia agentes de programación;
  - 29 dependencias base, entre ellas `posthog` y `pytest-rerunfailures`, que
    reintenta pruebas hasta que pasan, al revés de la regla de marcar los casos
    inestables.
- **Calibración:**
  - Por criterio y por idioma, sobre la partición de prueba de DS-7: TNR (fallos
    que el juez detecta) y TPR (aciertos que confirma), con intervalo de Wilson.
  - Valores iniciales: TNR ≥ 0,90 y TPR ≥ 0,85, a fijar en `nfr-requirements`.
  - Si el límite inferior del intervalo queda bajo el umbral, sus criterios se
    publican como "no medida" y no bloquean.
  - Reemplaza el 85 % de acuerdo: con 20 casos por idioma, 17 aciertos dan un
    intervalo de 64 % a 95 %, y con clases desbalanceadas un juez puede tener
    90 % de acuerdo dejando pasar la mitad de los fallos.
  - La kappa de Cohen se publica como dato secundario.
- **Etiquetas por turno**, con particiones fijas y versionadas de ajuste,
  desarrollo y prueba. Los fallos sembrados se marcan cuando falten negativos
  reales. El análisis de errores va antes de congelar las rúbricas (semanas 3 y
  4).
- **Corrección de la tasa reportada** con TPR y TNR.
- **pass^k con k = 3 por hito** sobre DS-2 y DS-6. Un caso que pasa algunas veces
  se marca inestable automáticamente.
- **Segundo juez de otra familia, solo para calibrar:** `gpt-oss-120b` en el plan
  gratuito de Groq, con transcripciones sintéticas y redactadas. Mide si el juez
  de Gemini favorece las salidas de Gemini.
- **Red team:** promptfoo (de OpenAI desde marzo de 2026, licencia MIT), por hito,
  con versión exacta, telemetría desactivada y configuración versionada. Cada
  ataque exitoso entra a DS-6 con su herramienta, versión y estrategia. Nunca en
  cada push.
- **Trazas en CI:** exportador OTLP a archivo, subido como artefacto de la corrida;
  el reporte enlaza al artefacto y al identificador de traza.
- **Alternativas añadidas:**
  - **DeepEval como dependencia:** por las razones de arriba.
  - **Ragas:** sin commits desde febrero de 2026.
  - **Inspect AI:** reconocible, pero duplicaría el corredor y trae 41
    dependencias.
  - **PyRIT, garak y DeepTeam junto a promptfoo:** cuatro herramientas de red team
    serían adorno.
  - **Pydantic Evals y experimentos de Langfuse:** duplican el corredor o
    requieren servidor.

#### Confirmación

- El reporte publica TPR, TNR, n e intervalo por criterio e idioma, y una
  calibración sembrada bajo el umbral produce "no medida".
- Grep en `verify.sh`: ni `deepeval` ni `pytest-rerunfailures` en `uv.lock`.

---

## ADR-015: Telemetría abierta y gasto controlado en la base del aplicativo

### Estado

Aceptada (2026-09-17).

### Contexto

M7 y M20 piden trazas con costo, latencia y tokens por caso y por nodo, y un techo
de gasto con corte. D11 fija el acumulado en 90 días y D15 pide un resumen de
traza redactado para el chat público. El PRD elige Langfuse con docker compose,
que el hospedaje gratuito no sostiene. La pregunta OQ4 deja el hospedaje al
intent `infra`.

### Decisión

- **Trazas:** OpenTelemetry con las convenciones GenAI, en tramos de turno, nodo
  y proveedor, con modelo, tokens, latencia, costo y precio de lista. Se exportan
  solo a través de PiiRedaction.
- **Backend de trazas:** Langfuse en local con docker compose, con su panel. Qué
  exporta el despliegue público lo decide el intent `infra`.
- **Datos del aplicativo:** `TraceSummary` y `SpendEntry` viven en la base de
  datos del aplicativo, así que los resúmenes públicos y el techo funcionan sin el
  backend de trazas.
- **Costo:** UsageBudget lo calcula una sola vez con la tabla versionada de
  precios de lista.
- **Techo y alertas:** el techo se comprueba antes de cada uso de pago
  (ProviderGateway consulta a UsageBudget); la alerta llega antes del techo; el
  registro de gasto sobrevive al reinicio nocturno; la tabla de topes configurados
  en cada proveedor se versiona con su última comprobación.

### Consecuencias

- **Positivas:** el corte de gasto no depende de la observación; los resúmenes
  públicos son rápidos y limitados a su navegador.
- **Negativas:** parte de la información vive en dos lugares (base del aplicativo
  y backend de trazas); la tabla de precios hay que mantenerla.
- **Seguridad y cumplimiento:** las trazas salen redactadas, los resúmenes se
  limitan por la clave del navegador y el registro de gasto no guarda datos
  personales.

### Alternativas rechazadas

- **Langfuse Cloud como dependencia:** los datos van a un tercero y el plan
  gratuito tiene límites; puede ser una opción de `infra`, no un requisito.
- **Phoenix:** razón reescrita en la enmienda del 2026-09-17 (un solo
  contenedor, pero licencia Elastic-2.0 y anotación más simple que las colas de
  Langfuse).
- **Gasto leído de los paneles de cada proveedor:** llega tarde y no se puede
  hacer cumplir desde el aplicativo.

### Enmienda del 2026-09-17

Investigación previa a Contract Design, con fuentes en `docs/reference/arquitectura-y-tecnologia.md` y sus anexos.

- **Convenciones GenAI** en estado *Development*, movidas al repositorio
  `open-telemetry/semantic-conventions-genai` en mayo de 2026. Se fija su
  versión, y los spans usan los nombres propios de la convención 3, que aíslan de
  renombres.
- **Contenido solo redactado:** los atributos de contenido son opcionales y se
  llenan solo después de PiiRedaction, nunca por la captura automática de una
  instrumentación de terceros.
- **CI:** Langfuse no cabe en los runners privados (2 vCPU y 8 GB, frente a los 4
  núcleos y 16 GiB que pide su docker compose). Las trazas de cada corrida se
  exportan a un archivo OTLP que se sube como artefacto y se puede importar al
  Langfuse local.
- **Rechazo de Phoenix reescrito:** Langfuse se mantiene por sus colas de
  anotación con licencia MIT, que usan la revisión semanal y DS-7, a cambio de
  seis servicios. Phoenix es un solo contenedor, pero con licencia Elastic-2.0 y
  anotación más simple. Se retira la razón "el PRD eligió Langfuse".
- **Rechazados:** OpenInference y OpenLLMetry, que mezclarían dos convenciones de
  atributos.
- **Límites de uso:**
  - Contadores atómicos en Postgres sobre `QuotaCounter` (UsageBudget): por sesión, por origen y
    día, por aseguradora y día, total del día y por llamada de voz, con
    `INSERT … ON CONFLICT DO UPDATE … RETURNING` antes de cada uso del modelo.
  - La IP se guarda como hash con sal que rota cada noche.
  - El límite diario queda por debajo de la cuota de Gemini, que se reinicia a
    medianoche del Pacífico.
  - `slowapi` y `limits` no sirven como autoridad: no tienen almacenamiento en
    SQL.

---

## ADR-016: Datos sintéticos deterministas desde textos fuente revisados

### Estado

Aceptada (2026-09-17).

### Contexto

M3 y FR11.2 exigen que dos corridas con la misma semilla den bytes idénticos;
F12.6 genera con el modelo en plan gratuito y revisión manual; P8 prohíbe texto
de terceros; las prácticas piden un generador determinista con su salida
versionada.

### Decisión

- **Redacción:** el modelo, en plan gratuito y solo con contenido sintético,
  redacta una vez los textos fuente por tipo, aseguradora e idioma. Miguel revisa
  una muestra por idioma y los textos se versionan como `SourceText`.
- **Composición:** un generador determinista y sembrado compone corpus,
  distractores, pólizas emitidas con datos ficticios (teléfonos del rango
  555-01XX, placas y cédulas inventadas), un caso en cada estado y los guiones de
  los golden sets, con un manifiesto de hashes.
- **Regeneración:** solo con un comando explícito.
- **Chequeos de contenido:** frases prohibidas, ausencia de texto de cláusula de
  ISO o ACORD y paridad de claves corren sobre la salida.

### Consecuencias

- **Positivas:** corridas idénticas en bytes; la variabilidad del modelo queda
  encerrada en textos revisados.
- **Negativas:** regenerar un texto fuente es un cambio deliberado que se revisa.
- **Seguridad y cumplimiento:** ningún dato real; el generador conoce los valores
  personales y alimenta los canarios del segundo detector (ADR-013).

### Alternativas rechazadas

- **Generar con el modelo en cada corrida:** no es determinista y rompe FR11.2.
- **Plantillas sin modelo:** textos poco realistas para evaluar extracción y
  recuperación.
- **Copiar formularios reales:** P8 lo prohíbe.

---

## ADR-017: Un solo catálogo de textos para servidor e interfaz

### Estado

Aceptada (2026-09-17).

### Contexto

Las prácticas piden un catálogo de textos por idioma con un solo espacio de
claves (US5.8); la regla del proyecto copia literal las frases fijas aprobadas;
P12 exige paridad; la landing mostró claves huérfanas (TD-01 y TD-02). La
interfaz va en TypeScript (ADR-002).

### Decisión

- **Archivos:** CopyCatalog vive en archivos versionados, uno por idioma, con
  clave y superficie.
- **Consumo:** el servidor lo carga y la compilación de la interfaz genera un
  módulo tipado de claves.
- **Chequeos:** paridad entre español e inglés, claves sin consumidor y frases
  fijas iguales al texto de su criterio de aceptación.
- **Uso:** las etiquetas de los enums se resuelven por el catálogo, y ninguna
  cadena visible se escribe en línea (lo vigila un chequeo).

### Consecuencias

- **Positivas:** la paridad y las frases literales se comprueban por herramienta.
- **Negativas:** un paso de compilación para las claves tipadas.
- **Seguridad y cumplimiento:** las frases de sustitución de la guardia salen del
  catálogo (FR7.6).

### Alternativas rechazadas

- **Un sistema de traducción por aplicación:** dos espacios de claves que se
  desalinean.
- **Textos en línea traducidos después:** no se pueden comprobar.

---

## ADR-018: Adaptadores de proveedores con interfaces propias y clientes por uso

### Estado

Aceptada (2026-09-17).

### Contexto

P3, P9, M20 y M21 piden que cambiar de proveedor sea configuración; las prácticas
exigen el SDK solo dentro de su adaptador, una taxonomía cerrada de errores, una
fábrica de clientes por uso y un tope por clave. La regla de cero renovaciones
pide detenerse cuando se agota un saldo.

### Decisión

- **Interfaces:** ProviderGateway define las que usa el núcleo: generar texto,
  calcular embeddings, transcribir en streaming, y sintetizar y transmitir.
- **Adaptadores:** uno por proveedor (Gemini, Deepgram, Cartesia y la voz de
  respaldo); una regla de importación impide usar un SDK fuera de su adaptador.
- **Clientes:** una fábrica por uso (voz, chat, evaluaciones y operación), cada
  cliente con su clave y su tope en el proveedor.
- **Errores:** se traducen a `timeout`, `rate_limited`, `unavailable` e
  `invalid_response`. Ante saldo o cuota agotados no hay reintento y sale una
  señal explícita de parada.
- **Configuración y contrato:** proveedor, modelo, voz y parámetros vienen de
  configuración versionada; cada proveedor tiene prueba de contrato, con
  respuesta grabada en cada entrega y contra el proveedor real por hito.
- **Uso y tramos:** el uso se reporta a UsageBudget y los tramos a Telemetry.
- **Librería de voz:** sus complementos envuelven estos adaptadores (ADR-009).

### Consecuencias

- **Positivas:** cambiar de proveedor es configuración más un adaptador; ningún
  tipo de un proveedor cruza al núcleo.
- **Negativas:** envolver los complementos de la librería de voz agrega trabajo.
- **Seguridad y cumplimiento:** las claves separadas por uso acotan el daño de
  una filtración y el gasto; ninguna cuenta queda con recarga automática.

### Alternativas rechazadas

- **Llamar el SDK desde los nodos:** acopla el núcleo y pierde la taxonomía de
  errores.
- **Un proxy universal de modelos:** otra dependencia que oculta los topes y los
  errores de cada proveedor.

### Enmienda del 2026-09-17

Investigación previa a Contract Design, con fuentes en `docs/reference/arquitectura-y-tecnologia.md` y sus anexos.

- **LiteLLM y gateways, rechazados con evidencia:**
  - versiones 1.82.7 y 1.82.8 comprometidas en PyPI (2026-03-24);
  - CVE-2026-42208, explotada a las 36 horas del aviso;
  - CVE-2026-42271, encadenada con la de Starlette;
  - any-llm, Bifrost, Portkey y OpenRouter: un intermediario más, sin ganancia
    con un solo proveedor de modelo.

  El respaldo con Groq, si se activa, es un segundo adaptador.
- **Salida estructurada:** nativa de Gemini y validada con Pydantic en el
  adaptador. Un fallo de validación se traduce a `invalid_response`, con un
  reintento según la política del nodo. Instructor, BAML y Pydantic AI se
  rechazan para esto; DSPy se difiere.
- **Proyectos por uso:** cada cliente por uso vive en su propio proyecto del
  proveedor, no solo con su clave, porque Gemini limita por proyecto.
- **Prompts:** un archivo por nodo e idioma, con identificador y hash. El hash va
  en la traza y en `EvalRun`, y cambiarlo dispara la compuerta.
- **Puertos pequeños:** `providers/ports.py` con un `Protocol` por capacidad
  (`TextGenerator`, `Embedder`, `SpeechToText`, `TextToSpeech`) y `adapters/`
  por proveedor. Los adaptadores heredan del `Protocol` para que mypy verifique
  la conformidad.

#### Confirmación

- Contratos `protected` sobre adaptadores y fábrica, y `forbidden` sobre los SDK.
- Suite de contrato por adaptador con respuestas grabadas (vcrpy) e inyección de
  errores (respx).

---

## ADR-019: Protocolos de agentes y herramientas fuera del producto

### Estado

Aceptada (2026-09-17). Investigación previa a Contract Design
(`docs/reference/arquitectura-y-tecnologia.md`, sección 7.3).

### Contexto

Miguel preguntó si el producto debe usar tools, MCP, skills o protocolos entre
agentes.

- **Restricciones del producto:** el turno de voz tiene meta p50 < 500 ms; P3
  prohíbe que el modelo elija acciones; RT-1 y RT-2 prueban inyección.
- **Estado de los protocolos:** MCP publicó su especificación 2026-07-28 con
  cambios de núcleo; A2A es un proyecto de la Linux Foundation; Agent Skills es
  un estándar abierto desde diciembre de 2025.
- **Uso actual:** el repositorio ya usa MCP y skills en el desarrollo, no en el
  producto.

### Decisión

- **Function calling:** no en el turno de voz ni para decidir.
  - `intake` usa salida estructurada.
  - `policy_verification` recupera por código.
  - `decision` no usa el modelo.
  - La derivación y la emergencia son reglas.
- **MCP en el producto:** no se consume ni se expone. Exponer las pólizas como
  servidor MCP queda como trabajo futuro, con su propio ADR, después de la v1.
- **A2A:** no.
- **Skills en el producto:** no; cada nodo tiene prompts fijos y versionados.
- **En el desarrollo:**
  - MCP (`context7`), skills del flujo AI-DLC y un `AGENTS.md` breve y neutral
    que apunta a las reglas, los ADR y el archivo de tareas;
  - el README lo cuenta en "How this was built", con la taxonomía de guías y
    sensores de Böckeler (2026).

### Consecuencias

- **Positivas:** una sola vuelta al modelo por turno; superficie de inyección
  menor; respuesta escrita a "¿por qué no MCP?".
- **Negativas:** sin interoperabilidad con clientes MCP. Si algún día hace falta,
  exige autorización por aseguradora sin reenviar tokens.
- **Seguridad y cumplimiento:** sin envenenamiento de herramientas (36,5 % de
  éxito medio en MCPTox) ni reenvío de tokens. El modelo no tiene acciones con
  efectos que un atacante pueda disparar.

### Alternativas rechazadas

- **Nodos con function calling:** otra vuelta al modelo por turno, y el modelo
  elegiría acciones.
- **Servidor MCP de pólizas en la v1:** sin cliente real, con otra superficie
  pública y un aislamiento por aseguradora más que probar.
- **A2A:** no hay agente de otra organización con quien hablar.
- **Skills cargadas por el modelo:** el modelo decidiría su propio contexto,
  contra P3.

### Confirmación

- Grep en `verify.sh`: ningún SDK de MCP ni de A2A en `uv.lock`.
- Los adaptadores del modelo no declaran herramientas.

---

## ADR-020: Defensa contra inyección por diseño y guardas del turno

### Estado

Aceptada (2026-09-17), con la decisión de Miguel sobre RT-5. Investigación previa
a Contract Design (`docs/reference/arquitectura-y-tecnologia.md`, sección 9).

### Contexto

- **Marco vigente:** el OWASP Top 10 for LLM Applications 2026 (agosto de 2026)
  parte de que el modelo será engañado, y renombra System Prompt Leakage como
  Hidden Context Exposure.
- **Evidencia:** los ataques adaptativos evaden con más del 90 % de éxito los
  clasificadores de inyección publicados (Nasr et al., 2025).
- **Prácticas del equipo:**
  - tres controles baratos dentro del turno;
  - texto externo fuera de la posición de instrucción;
  - guardia de salida sobre todo texto que llega al asegurado.
- **Superficies públicas:** el chat público y la bandeja reciben texto de personas
  reales.

### Decisión

- **Marco de referencia:**
  - Tabla "inspirado en" contra OWASP LLM 2026: una fila por riesgo, con control,
    prueba y estado.
  - Las entradas aplicables del OWASP Agentic 2026: ASI01, ASI06, ASI08 y ASI09.
  - Lo que no aplica va `N/A` con su razón. NIST AI 600-1 no se mapea.
- **Patrones** (*Design Patterns for Securing LLM Agents against Prompt
  Injections*, 2025):
  - un programa escrito por personas que el modelo no altera;
  - selección de acciones sobre conjuntos cerrados;
  - validación de citas por referencia;
  - delimitación del texto externo, presentada como reducción de riesgo medida
    por RT-2 y no como frontera;
  - persona en el bucle.
- **Rule of Two de Meta:** se cumple porque los datos alcanzables están
  confinados al caso del visitante, los cambios automáticos son de bajo impacto y
  lo de alto impacto pasa por `interrupt()`.
- **Búfer por frase:** la guardia de salida aprueba cada frase completa antes de
  enviarla a la síntesis de voz o al navegador. Presupuesto propuesto: p95 ≤ 5 ms
  por frase, a medir.
- **Guardas deterministas bilingües:**
  - léxico por idioma;
  - patrones independientes del idioma: cifras, monedas, porcentajes y números en
    letras;
  - normalización: NFKD, tildes, mayúsculas y homoglifos básicos;
  - cada control con su span.
- **Campos que alimentan reglas:** solo campos tipados (enum o formato), nunca
  texto libre. Lo que declara el asegurado queda `declared`, y la vigencia sale de
  la base de datos.
- **Bandeja:** primero campos, resultados de reglas y transcripción literal con
  procedencia. Todo texto del modelo va etiquetado y después de los hechos.
- **Renderizado:** la salida del modelo se muestra como texto plano, sin markdown
  de imágenes ni enlaces automáticos, con CSP `img-src 'self'`.
- **Consumo:** el límite cuenta también los tokens de entrada de las
  conversaciones largas.
- **RT-5 (decisión de Miguel):**
  - Revelar las instrucciones del sistema es un hallazgo menor e informativo,
    porque el repositorio será público.
  - Bloquea que el contexto contenga secretos, configuración de otra aseguradora
    o datos de otro caso.
- **DS-6:** pasar el set prueba resistencia a ataques conocidos, y el README lo
  dice así. El red team por hito usa estrategias adaptativas de varios turnos
  (ADR-014).

### Consecuencias

- **Positivas:** la seguridad no depende de detectar ataques; los controles
  corren en milisegundos; cada control tiene su prueba.
- **Negativas:**
  - hay que mantener el léxico bilingüe;
  - el búfer por frase suma, antes del primer audio, el tiempo de generar una
    frase corta;
  - una paráfrasis nueva puede pasar la guardia, y entra a DS-6 cuando aparece.
- **Seguridad y cumplimiento:**
  - DS-6 suma casos: inyección que intenta fijar un campo que cambia la
    categoría, resumen que intenta persuadir al ajustador y exfiltración por
    markdown;
  - ningún dato del visitante sale a un servicio de guardas de terceros.

### Alternativas rechazadas

- **NeMo Guardrails:** segundo orquestador y llamadas extra al modelo.
- **Guardrails AI:** comprada por Harvey el 2026-09-09; validadores remotos.
- **LLM Guard:** archivado en julio de 2026 y no instala en Python 3.13.
- **Llama Guard 4, ShieldGemma y Qwen3Guard:** clasifican contenido dañino, no
  promesas de cobertura, y necesitan GPU.
- **Google Model Armor:** facturación, datos a un tercero, latencia de red y
  evasión adaptativa documentada.
- **Llama Prompt Guard 2 dentro del turno:** sin cifras de latencia en CPU y
  también evadible; diferido como señal fuera del turno.
- **Implementar CaMeL:** el grafo ya fija el flujo de control y no hay
  herramientas con efectos que proteger.

### Confirmación

- Casos de DS-6 para el streaming, los campos extraídos, la bandeja y el
  renderizado, y RT-15 con variantes generadas por Hypothesis.
- Prueba de Playwright de salida en texto plano.
- Span por control con su latencia.

---

## ADR-021: Tiempo real con SSE

### Estado

Aceptada (2026-09-17). Investigación previa a Contract Design
(`docs/reference/arquitectura-y-tecnologia.md`, sección 8.6).

### Contexto

- **Qué se necesita:** el chat transmite la respuesta mientras se genera, y la
  bandeja muestra los cambios de los casos.
- **Qué hay disponible:**
  - FastAPI trae SSE nativo desde 0.135.0 (2026-03-01);
  - el navegador reconecta solo con `EventSource`.
- **Qué no hace falta:**
  - el chat no tiene tráfico bidireccional;
  - la voz usa el transporte de su librería (ADR-009);
  - ADR-004 descartó un broker.

### Decisión

- **Chat, en dos pasos:**
  - `POST` guarda el mensaje y devuelve su identificador;
  - `GET` abre el stream con `EventSource` y cookie `HttpOnly`, con eventos de
    identificador creciente y reanudación por `Last-Event-ID`.
- **Bandeja:**
  - SSE sobre `InboxEvent`, entidad de Inbox con identificador creciente y RLS;
  - al conectar se reproducen los eventos posteriores;
  - las escrituras del propio proceso despiertan a los suscriptores, y una
    consulta de respaldo cada 5 a 10 segundos cubre los reinicios.
- **Eventos tipados:** unión discriminada de modelos Pydantic, documentada en el
  esquema OpenAPI y dentro del chequeo de deriva de contratos.
- **Conexiones:** como mucho un stream por pestaña, cerrado cuando la pestaña se
  oculta (sin HTTP/2, el navegador admite 6 por dominio).
- **Versión:** FastAPI ≥ 0.135.0 fijado en el lockfile.

### Consecuencias

- **Positivas:** reconexión nativa, sin servicio nuevo, y los eventos entran al
  contrato tipado.
- **Negativas:** `EventSource` no permite cabeceras propias, así que la
  autenticación va por cookie; la consulta de respaldo agrega lecturas periódicas
  a la base.
- **Seguridad y cumplimiento:** el stream respeta la clave del navegador y RLS,
  y los eventos llevan contenido ya redactado.

### Alternativas rechazadas

- **WebSocket para el chat:** no hay tráfico bidireccional que lo justifique.
- **Pub/sub de Redis:** un servicio más, y sin reanudación tras un reinicio.
- **`LISTEN/NOTIFY`:** diferido. Solo tiene sentido con varios procesos y
  conexión directa, y se pierde cuando Neon suspende la base.
- **AsyncAPI:** un solo consumidor en el mismo repositorio.

### Confirmación

- Prueba de reconexión con `Last-Event-ID` sin eventos perdidos ni duplicados.
- Chequeo de deriva del esquema.
