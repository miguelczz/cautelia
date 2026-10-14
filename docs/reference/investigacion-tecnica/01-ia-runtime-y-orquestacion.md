# Investigación 1 — Runtime de IA y orquestación

Fecha de corte: 2026-09-17. Alcance: runtime del grafo, latencia, multiagente frente a workflow, herramientas y protocolos (MCP, A2A), skills y harness engineering, gateway de modelos, salida estructurada y prompts, multimodal. Fuera de alcance: datos/RAG/colas, seguridad/evals/pruebas, arquitectura de software/monorepo (otros investigadores).

Etiquetas de evidencia usadas en todo el documento:

- **[P]** fuente primaria leída (documentación oficial, notas de versión, PyPI, blog del autor, paper).
- **[S]** fuente secundaria (blog de terceros, proveedor que vende una alternativa, agregador); se usa solo cuando no hubo primaria.
- **[NV]** no verificado: no se pudo confirmar en una fuente primaria.

Postura: se revisa el diseño aprobado buscando dónde falla, no confirmándolo. Cada recomendación se ata a las restricciones: una persona, 90 días, hospedaje gratuito que se duerme, techo de 5 USD, `gemini-3.1-flash-lite`, turno de voz con meta p50 < 500 ms y p95 < 800 ms, y evaluadores que castigan lo que se agrega para adornar el CV.

---

## Resumen ejecutivo

1. **LangGraph sigue siendo defendible y se mantiene (ADR-003)**, pero el ADR necesita una enmienda: versiones mínimas por tres CVE de 2026 en la carga de puntos de control, modo estricto de deserialización, la semántica de `interrupt()` (el nodo se re-ejecuta completo al reanudar), las primitivas nativas de LangGraph 1.2 para tiempo máximo y manejo de error por nodo, y una ruta concreta y verificable para PA-3 con el checkpointer oficial. Las razones con que el ADR rechaza Pydantic AI ("ecosistema más pequeño", "no lo nombra el PRD") son débiles ante un Staff Engineer y conviene reemplazarlas por las reales.
2. **La latencia del turno no la pone el grafo, la pone el modelo.** El sobrecosto medido de LangGraph está en el orden de 10–15 ms por consulta; el primer token de Gemini Flash-Lite se midió en segundos (experimento 2: p50 1,1–2,4 s en plan gratuito; Artificial Analysis: 5,63 s con carga de 10k tokens). La meta p50 < 500 ms es, con la evidencia disponible, muy probablemente inalcanzable en cascada con ese modelo; hay que tratarla como hipótesis del experimento 1 y preparar el diseño del turno para una sola llamada al modelo, en streaming, sin llamadas a herramientas y sin guardia LLM dentro del turno.
3. **El diseño no es multiagente y no debe llamarse así.** Es un workflow determinista con pasos LLM (en la taxonomía de Anthropic), con un solo escritor por campo del estado, trabajo de fondo precargado y una persona en el bucle. Las fuentes de 2026 (Anthropic, Cognition, MAST) respaldan exactamente eso; llamarlo "multiagente" es la objeción que el PRD dice querer desactivar.
4. **MCP y A2A fuera del runtime; Agent Skills y harness engineering solo en el desarrollo.** Exponer la consulta de pólizas como servidor MCP sería lo más "resume-driven" de todo el alcance.
5. **LiteLLM: rechazar y documentarlo.** En 2026 tuvo un paquete de PyPI comprometido (24-03-2026), una inyección SQL pre-autenticación explotada a las 36 h (CVE-2026-42208) y una ejecución remota sin credenciales encadenada con un fallo de Starlette (CVE-2026-42271 + CVE-2026-48710). ADR-018 queda reforzado. Hallazgo colateral: **CVE-2026-48710 afecta a Starlette < 1.0.1, la base de FastAPI** (ADR-002).
6. **Speech-to-speech (Gemini 3.8 Live, publicado hace dos días) se rechaza para la v1**: solo voces precargadas (rompe la voz paisa única de P10), salida solo en audio con la transcripción llegando junto al audio (la guardia de salida no puede leer el texto antes de que suene) y costo de audio unas 4,6 veces la meta D7 antes de contar el contexto. La extracción de documentos (C1) se difiere.

---

## 1. ¿Sigue siendo LangGraph el runtime correcto (septiembre de 2026)?

### Hallazgos

**Estado de LangGraph.**

- Versión 1.0 el 2025-10-20; 1.1 el 2026-03-10 (streaming e invocación tipados con `version="v2"`, opt-in y declarada compatible hacia atrás); 1.2 el 2026-05-12; última 1.2.11 el 2026-08-11 [P, changelog y PyPI]. No hay anuncio de 2.0 en el changelog [P].
- 1.2 agrega **tiempo máximo por nodo** (`timeout=` con `TimeoutPolicy`, `NodeTimeoutError`), **manejador de error por nodo** (`error_handler=`, tras agotar reintentos), apagado ordenado con puntos de control reanudables, y dos piezas en beta: `DeltaChannel` y streaming de eventos v3 [P].
- El paquete de puntos de control sí tuvo saltos mayores: `langgraph-checkpoint` 3.0.0 (2025-10-20) → 4.0.0 (2026-01-12, desactiva por defecto el respaldo a pickle) → 4.2.0 (2026-08-07); `langgraph-checkpoint-postgres` 3.1.2 (2026-08-07) [P, PyPI; S para el detalle de 4.0].
- **Seguridad (2026):**
  - CVE-2026-28277: deserialización msgpack insegura en `langgraph` ≤ 1.0.9, corregida en 1.0.10 [P, GitHub Advisory].
  - CVE-2026-48775 (2026-05-22): `JsonPlusSerializer` podía reconstruir objetos arbitrarios en `langgraph-checkpoint` < 4.1.1 [P].
  - Check Point Research (2026-06-11) encadenó inyección SQL en los checkpointers de SQLite y Redis con esa deserialización hasta ejecución remota; **el checkpointer de PostgreSQL no estaba afectado**; recomiendan no exponer los filtros de `get_state_history()` a usuarios [P].
  - La página de PyPI del checkpointer de Postgres recomienda `LANGGRAPH_STRICT_MSGPACK=true` o una lista explícita `allowed_msgpack_modules` [P].
- **Semántica de `interrupt()`**: al reanudar, "el runtime reinicia el nodo completo desde el principio"; los efectos laterales antes de `interrupt()` deben ser idempotentes; no se envuelve `interrupt()` en un `try/except` genérico; varios `interrupt()` en un nodo se emparejan por posición [P, docs de interrupts].
- **Durabilidad**: tres modos, `exit`, `async`, `sync`, de menos a más durable y de menos a más sobrecosto [P, referencia `Durability`]. El valor por defecto no aparece en la referencia leída [NV].
- **PA-3 (tenant y RLS en las tablas de puntos de control)**, leyendo el código fuente del checkpointer de Postgres [P, `base.py` en `main`]:
  - Tablas `checkpoints`, `checkpoint_blobs`, `checkpoint_writes` (y `checkpoint_migrations`), con claves primarias sin tenant, nombres **sin esquema calificado**.
  - Todos los `INSERT ... ON CONFLICT` usan **lista explícita de columnas**, así que una columna nueva `tenant_id` con `DEFAULT` tomado de la sesión no rompe las escrituras.
  - Hay un issue abierto (2026-03-30, #7345) pidiendo un parámetro de esquema para multi-tenant; sin respuesta visible del equipo [P].
  - En PostgreSQL, el dueño de la tabla omite RLS salvo `FORCE ROW LEVEL SECURITY`, y los roles superusuario o `BYPASSRLS` siempre la omiten [P, docs PostgreSQL 18].
  - Conclusión: PA-3 parece **resoluble con el checkpointer oficial** (columna `tenant_id` con `DEFAULT current_setting(...)`, política RLS, `FORCE ROW LEVEL SECURITY`, rol de aplicación que no es dueño, y el saver construido por petición sobre la conexión que entrega el punto único de sesión). Es una **hipótesis a probar** con una prueba de integración de aislamiento en Functional Design, no un hecho: falta comprobar cómo interactúa el `autocommit=True` que exige el saver con la forma en que el punto único fija el tenant, y que futuras migraciones del paquete no choquen.
- **Crítica a los checkpointers en general** (Diagrid, 2026-02-25, proveedor de Dapr, sesgo declarado) [S]: un checkpoint guarda estado pero no detecta el fallo ni reanuda solo; alguien tiene que relanzar lo que quedó a medias. Esto toca directamente a ADR-004 ("si el proceso muere, la reanudación relanza lo pendiente"): en hospedaje gratuito que se duerme, ese relanzamiento tiene que existir como código explícito al arrancar.
- **Voz + grafo con estado**: el ejemplo oficial `langchain-ai/pipecat-langgraph-example` sirve chat y voz desde el mismo grafo, pero en voz el grafo va **sin estado**: el contexto de Pipecat es la fuente de verdad y el especialista activo se recupera del transcript en cada turno "para que las interrupciones nunca corrompan el estado de ruteo" [P, README]. Con un grafo con puntos de control por turno (nuestro caso, F2.4), una interrupción del asegurado deja el estado guardado con una respuesta que la persona no terminó de oír. No invalida LangGraph, pero es un requisito de diseño que hoy no está escrito.

**Alternativas.**

| Candidata | Estado verificado | Transición por código sobre estado tipado | Checkpoint en PostgreSQL con RLS | Pausa humana y reanudación | Cadencia y cambios que rompen | Encaje con Untangle |
| --- | --- | --- | --- | --- | --- | --- |
| **LangGraph** | 1.2.11 (2026-08-11) [P] | Sí (aristas condicionales con función pura) | Oficial; PA-3 viable con columna + RLS (hipótesis) | `interrupt()` + `Command(resume=...)` [P] | 1.x sin rupturas declaradas; checkpoint pasó de 3 a 4 en enero [P] | Bueno; superficie usada pequeña |
| **Pydantic AI v2 + pydantic-graph** | Pydantic AI 2.0 el 2026-06-23; 2.44.0 el 2026-09-17; ventana sin rupturas bajó de 6 a 3 meses [P] | Sí (aristas por tipo de retorno); API "beta" de grafo con builder [P] | Persistencia de grafo: memoria, archivo y ABC; Postgres "planeado" [S, DeepWiki; issue #3697 abierto] | `InterruptNode`/`iter_from_persistence` en grafos; en agentes, deferred tools; durabilidad delegada a Temporal, DBOS, Prefect o Restate [P] | Muy alta (varias versiones por semana) [P] | Obligaría a escribir la persistencia Postgres o a sumar un motor durable |
| **Google ADK 2.0 (Python)** | GA 2026-05-19; 2.9.1 el 2026-09-15 [P] | Sí, "Workflow Runtime" con grafo; también YAML [P] | `DatabaseSessionService` con PostgreSQL [S]; el cambio de esquema de eventos de 2.0 exige migrar almacenamiento propio [P] | `RequestInput` y reanudación durable desde la sesión [S]; crítica: la confirmación de herramientas no soporta los servicios de sesión de producción [S, Medium] | Nueve versiones menores en cuatro meses; rupturas en 2.0 [P] | Acopla al ecosistema Gemini/Google, contra P3/M21 (proveedor intercambiable) |
| **OpenAI Agents SDK** | 0.22.2 (2026-09-09), pre-1.0 [P] | No hay grafo tipado; bucle de agente con handoffs | Sesiones; `RunState` serializable que uno guarda donde quiera [P] | Aprobación de herramientas con `RunState` [P] | Pre-1.0 | Modelo mental de agente autónomo, contra P3 |
| **Microsoft Agent Framework** | 1.0 GA 2026-04-03 [P] | Sí, workflows por supersteps [P] | Python: memoria, archivo y Cosmos DB; **sin Postgres** oficial; pickle restringido [P, docs 2026-09-16] | Sí, con puntos de control [P] | Rupturas menores en Python 1.13.0 en el orden de checkpoints [P] | Sin Postgres; centro de gravedad Azure |
| **LlamaIndex Workflows** | 2.24.0 (2026-09-16) [P] | Por eventos y pasos, no por función de transición | Durabilidad vía `llama-agents-server` [S] | Eventos inyectados [S] | Alta | Modelo por eventos menos legible para P3 |
| **Temporal** | Servidor MIT; Cloud desde 100 USD/mes, sin plan gratuito de producción [S] | Código de workflow | Su propia base | Señales | Estable | Un servicio más que mantener despierto (ya rechazado) |
| **DBOS Transact** | MIT, librería sobre Postgres o SQLite, **recuperación automática** al reiniciar, `DBOS.recv()` para esperar a una persona [P, GitHub] | Código Python | Tablas propias en la misma base | Sí | Activa (novedades de junio de 2026) [P] | Resolvería el relanzamiento de ADR-004 sin broker, pero suma un segundo concepto de orquestación |
| **Máquina de estados propia** | — | Sí, total | Tablas propias con RLS desde el día uno | A implementar | Cero dependencias | "Own your control flow" (12-factor #8); cuesta puntos de control, pausa, streaming y reanudación |

**Reconocimiento en vacantes.** Análisis de 1.135 avisos de un tablero especializado en agentes (marzo–mayo de 2026): LangChain en 392, **LangGraph en 256 (22,6 %)**, LlamaIndex 150, CrewAI 106, AutoGen 74; **más de la mitad no nombra ningún framework**, los que lo nombran pagan una mediana ~20k USD menor, y lo que se repite es "evals y números operativos"; MCP aparece en 17–24 % [S, DEV Community, 2026-09-09]. Descargas: `langgraph` 50,3 M en 30 días, `pydantic-ai` 7,1 M [S, pepy.tech; incluye instalaciones transitivas]. Lectura: LangGraph es reconocible, pero **nombrar un framework no es la señal que se paga**; la señal es evals y operación.

### Recomendación

**`adoptar en el runtime` LangGraph**, con enmienda a ADR-003:

1. **Versiones mínimas** en el lockfile: `langgraph` ≥ 1.0.10 (en la práctica 1.2.x), `langgraph-checkpoint` ≥ 4.1.1, y `LANGGRAPH_STRICT_MSGPACK=true` o lista explícita de módulos permitidos. `get_state_history()` nunca recibe filtros del usuario.
2. **No usar lo que está en beta** (`DeltaChannel`, streaming v3). Sí usar `timeout=` y `error_handler=` de 1.2 **detrás** de la política de fallo declarada como dato: el "ejecutor común" de las prácticas se vuelve una fábrica que traduce la política a primitivas nativas, en lugar de un envoltorio propio que duplica lo que el framework ya hace.
3. **Separar efectos laterales de `interrupt()`**: todo lo que llama al modelo o escribe fuera del grafo antes de pausar hacia la bandeja va en un nodo propio anterior, o su resultado queda en el estado; si no, reanudar re-ejecuta la llamada al LLM (costo doble y resultado distinto).
4. **PA-3**: primero probar la ruta con el checkpointer oficial (columna `tenant_id` con `DEFAULT`, RLS, `FORCE ROW LEVEL SECURITY`, rol no dueño, saver por petición sobre la conexión del punto único) con una prueba que intente leer un checkpoint de otra aseguradora; checkpointer propio solo si esa prueba falla.
5. **La función de transición no importa LangGraph**: vive en un módulo puro que se prueba sin el framework. Eso convierte "¿y si LangGraph desaparece?" en una respuesta de una línea y desactiva la sospecha de framework por moda.
6. **Reescribir las alternativas rechazadas** con las razones verificables: Pydantic AI (sin persistencia Postgres de grafos; durabilidad delegada a un motor externo; ventana de rupturas de 3 meses), Google ADK 2.0 (acopla al proveedor del modelo; rupturas de 2.0), OpenAI Agents SDK (pre-1.0, bucle de agente), Microsoft Agent Framework (sin Postgres en Python), máquina propia (costo de reimplementar pausa y reanudación). Quitar "no los que nombra el PRD" como razón.
7. **Relanzamiento explícito al arrancar** (ADR-004): barrido de `NodeRun` pendientes y de hilos pausados por fallo, porque un checkpoint no se reanuda solo. `DBOS Transact`: `diferir (trabajo futuro)` como alternativa documentada si ese barrido crece.
8. **Voz**: escribir como requisito que, ante una interrupción del asegurado, el estado del caso guarda solo lo que efectivamente sonó (el canal de voz notifica el texto truncado y el grafo lo refleja), o que el turno de voz no escribe la respuesta en el estado hasta que termina de sonar.

---

## 2. Latencia: ¿pasar por varios nodos hace lento cada intercambio?

### Hallazgos

**Cuánto pesa el framework.**

- Benchmark de AIMultiple (100 consultas × 100 corridas, GPT-4.1-mini, mismo retriever): sobrecosto de orquestación ~14 ms por consulta para LangGraph, ~10 ms LangChain, ~6 ms LlamaIndex, ~3,5 ms DSPy; concluyen que la orquestación es "una porción pequeña" frente a los tokens y la E/S [S; la página muestra fechas inconsistentes: "2026-08-31, actualizado 2026-01-29"].
- No se encontró una medición primaria del sobrecosto de escribir un checkpoint en Postgres por paso [NV]. Es E/S de red: con una base gratuita remota cada escritura síncrona es una ida y vuelta completa, y una base que escala a cero agrega arranque en frío (Neon gratuito: se suspende a los 5 min, 300–800 ms para reactivar [S]).

**Cuánto pesa el modelo.**

- Experimento 2 del proyecto (ADR-006): primer token p50 1,1–2,4 s con `gemini-3.1-flash-lite` en plan gratuito, colas > 10 s.
- Artificial Analysis, Gemini 3.1 Flash-Lite en AI Studio: **TTFT 5,63 s**, 298 tokens/s de salida; la página lo marca como deprecado y recomienda 3.5 Flash-Lite [P, página del proveedor de benchmark; sin fecha visible]. Su metodología usa 10k tokens de entrada desde marzo de 2026, más que el presupuesto de ~3.900 tokens del turno [S, MarkTechPost 2026-08-30]. En la misma tabla: Gemini 3.5 Flash con razonamiento mínimo 0,90 s; Claude 4.5 Haiku 0,84 s; `gpt-oss-120b` en Cerebras 0,49 s; en Baseten 0,23 s [S].
- Google: `gemini-3.1-flash-lite` (GA 2026-05-07) se apaga el **2027-05-07**, reemplazo `gemini-3.5-flash-lite` (GA 2026-07-21) [P, página de deprecaciones, 2026-09-16]. No afecta los 90 días, pero conviene escribir la fecha.
- **Caché implícita**: activada por defecto desde Gemini 2.5; mínimos de 4.096 tokens para la familia 3.5–3.8 Flash; **3.1 Flash-Lite no aparece en la tabla** [P, docs 2026-09-02]. Un hilo del foro oficial reporta que desde ~2026-06-30 la caché implícita de 3.1 Flash-Lite dejó de aplicar el descuento aunque la respuesta dice que hubo tokens en caché, sin resolución pública [P, foro de Google, jul–ago 2026]. Con prompts de ~3.900 tokens el turno queda por debajo del mínimo aun si funcionara.

**Presupuestos de referencia de la industria (todos [S]).**

- Meta habitual de ~800 ms de mediana voz a voz; guías de 2026 hablan de 600–1.200 ms típicos para cascada y sub-500 ms "alcanzable pero con traspaso agresivo de parciales" (Future AGI, 2026-04-09, proveedor).
- LiveKit Agents: sesión por defecto ~1,2–1,4 s p95, bajando a ~500–650 ms p95 con optimizaciones (según un blog de terceros, no LiveKit) [S]. LiveKit mismo (2026-04-13) no da cifras por etapa y recomienda observar qué etapa domina, colocar el agente cerca del modelo, modelos más rápidos en la etapa dominante y sonidos de espera [P].

**Patrones vigentes de "rápido/lento".**

- **Talker–Reasoner** (Christakopoulou et al., Google DeepMind, arXiv 2410.08328): un agente conversa y otro razona en segundo plano [P]. LiveKit lo documentó para voz el 2026-04-01: el agente principal "nunca bloquea" y delega a un subagente con una herramienta asíncrona [P].
- **VoiceAgentRAG** (arXiv 2603.02206, 2026-03-02): un "Slow Thinker" predice temas y precarga fragmentos en una caché semántica; el "Fast Talker" solo lee de la caché. Resultado: 75 % de aciertos (79 % desde el turno 2), recuperación de 110,4 ms a 0,35 ms promedio [P].
- **12-factor agents**, factor 13: "pre-fetch all the context you might need" [P].
- **Generación preventiva** sobre transcripciones parciales (`preemptive_generation` en LiveKit) y **audio de espera pre-sintetizado** disparado cuando empieza una operación lenta [S].
- Gemini 3.8 Live anuncia llamadas a funciones asíncronas mientras sigue hablando [P, blog de Google 2026-09-15] (ver sección 8).

### Dónde el diseño todavía puede ser lento

El diseño aprobado ya es un patrón rápido/lento: Intake en el turno; verificación, reglas y revisión completa de fondo con precarga y frase de espera (P4, F2.3, ADR-004). El número de nodos **no** suma latencia al turno mientras eso se cumpla. Lo que sí la suma:

1. **Cualquier segunda llamada al modelo dentro del turno.** Una llamada de extracción más otra de respuesta, una llamada a herramienta (el modelo emite la llamada, se ejecuta y se vuelve a llamar al modelo) o una guardia de salida hecha con LLM duplican el TTFT, que ya es la etapa dominante. Regla propuesta: **como máximo una llamada al LLM por turno de voz, en streaming, sin herramientas**.
2. **La guardia de salida** tiene que ser código (reglas, patrones, catálogo) y trabajar por frase: retiene la primera frase hasta validarla y la entrega al TTS. Su costo es el tiempo de generar una frase corta, no otra llamada.
3. **Escrituras síncronas a Postgres en el camino del turno.** Usar durabilidad `async` en el turno (o persistir al cierre del turno) y medirlo; mantener la base despierta (el ping del checklist del segundo día ya lo cubre) o elegir un plan sin escala a cero para la demo de voz.
4. **Trabajo de CPU en el mismo bucle asyncio.** ADR-004 corre el fondo como tareas asíncronas en el mismo proceso que el audio. Las tareas asíncronas no aíslan CPU: NER de Presidio (~24 ms por petición con spaCy en un M2 Pro [S]), fusión RRF, serialización de estado grande o JSON de puntos de control bloquean el event loop y producen cortes de audio. Mandar lo CPU-intensivo a `asyncio.to_thread`/un pool de procesos, o separar el worker de voz del de fondo, y medirlo en el experimento 1.
5. **Invocar el grafo completo por turno.** El turno de voz debe entrar a un punto que ejecute solo Intake y devuelva; no un `invoke` que también recorra `policy_verification` y `decision`.
6. **Redacción antes de persistir dentro del turno.** Puede ocurrir después de que empiece el audio: la regla exige redactar antes de persistir, no antes de hablar.
7. **Frases fijas sintetizadas en cada llamada.** Divulgación, apertura, frases de espera y de derivación son literales del catálogo: se pueden pre-sintetizar por voz e idioma con un comando y reproducir sin TTS en vivo (menos latencia y menos gasto). Verificar que los términos del proveedor de TTS permitan guardar el audio generado [NV].
8. **Arranque en frío del worker de voz** en hospedaje gratuito (riesgo A1 ya registrado).
9. **Colas de latencia del proveedor** (> 10 s medidas): la frase de espera tiene que dispararse por reloj (p. ej. a 1,5–2 s sin primer token), no por evento del modelo.

### Recomendación

- `adoptar en el runtime`: la regla "una sola llamada al LLM por turno, en streaming, sin herramientas ni guardia LLM"; durabilidad `async` en el turno; trabajo CPU fuera del event loop; frases fijas pre-sintetizadas; frase de espera por temporizador. Todo medible en el experimento 1 y en la matriz de NFR.
- `adoptar en el runtime`: precarga de fondo al identificarse el asegurado (ya decidida) nombrada en el README como patrón talker–reasoner / "pre-fetch", aclarando que el "reasoner" es código, recuperación y reglas, no un segundo LLM.
- `rechazar y documentarlo en un ADR`: un segundo LLM "reasoner" que corre en paralelo al turno (duplica gasto, sin necesidad: el trabajo lento ya es determinista).
- `diferir (trabajo futuro)`: caché semántica de recuperación estilo VoiceAgentRAG (útil solo si la precarga por póliza no alcanza; medirla primero) y generación preventiva sobre parciales (depende de la librería que gane el experimento 1).
- **Honestidad de la meta**: mantener p50 < 500 ms como meta publicada, pero escribir en NFR que la evidencia externa apunta a 600–1.200 ms típicos en cascada y a TTFT de Flash-Lite en segundos, y publicar el número real por idioma aunque no cumpla (P4, P7). Si no cumple, ADR-006 ya prevé revisar el turno antes que el modelo.

---

## 3. Multiagente frente a workflow

### Hallazgos

- **Anthropic, "Building effective agents"** (2024-12-19, Erik Schluntz y Barry Zhang) [P]: los *workflows* orquestan LLMs y herramientas por rutas de código predefinidas; los *agentes* dirigen dinámicamente su propio proceso. Patrones de workflow: encadenamiento de prompts, ruteo, paralelización, orquestador-trabajadores, evaluador-optimizador. Consejo: empezar por la API directa y entender lo que hace el framework.
- **Anthropic, "When to use multi-agent systems (and when not to)"** (2026-01-23) [P]: tres situaciones donde varios agentes superan a uno (protección de contexto, paralelización, especialización); consumen **3–10× más tokens**; empezar con un agente bien diseñado; dividir por contexto y no por tipo de tarea, porque las divisiones "planificar/implementar/probar" crean traspasos con pérdida.
- **Anthropic, "How we built our multi-agent research system"** (2025-06-13) [P]: un agente usa ~4× los tokens de un chat y un sistema multiagente ~15×; rinde en investigación muy paralelizable y rinde mal cuando todos los agentes necesitan el mismo contexto o hay muchas dependencias entre partes.
- **Cognition, "Don't Build Multi-Agents"** (2025-06, Walden Yan) y **"Multi-Agents: What's Actually Working"** (2026-04-22) [P]: se mantienen los principios de compartir contexto y de **escrituras de un solo hilo**; funcionan hoy los esquemas donde los agentes extra "aportan inteligencia, no acciones" (bucle revisor de código con contexto limpio, "smart friend" consultor, map-reduce con gestor); siguen sin funcionar los enjambres de escritores paralelos.
- **MAST, "Why Do Multi-Agent LLM Systems Fail?"** (Cemri et al., arXiv 2503.13657, marzo de 2025, revisado 2025-10-26; NeurIPS 2025 Datasets & Benchmarks) [P]: 1.600+ trazas de 7 frameworks, 14 modos de fallo en 3 categorías (diseño/especificación del sistema, desalineación entre agentes, verificación de la tarea), kappa 0,88; mejores modelos solos no los corrigen, hacen falta cambios estructurales.
- **LangChain, "How and when to build multi-agent systems"** (2025-06-16, Harrison Chase) [P]: la ingeniería de contexto es lo central; los sistemas de lectura son más prácticos que los de escritura; LangGraph se ofrece como orquestación de bajo nivel para workflows y agentes.
- **12-factor agents** (HumanLayer) [P]: la mayoría de las funciones de IA en producción son software determinista con puntos LLM estratégicos; factores 5 (unificar estado de ejecución y de negocio), 6 (lanzar/pausar/reanudar con APIs simples), 7 (contactar personas como herramienta), 8 (ser dueño del flujo de control), 10 (agentes pequeños y enfocados), 12 (agente como reductor sin estado).

### Diagnóstico honesto del diseño

Contando qué hace cada nodo según el PRD (MOD-02) y ADR-006:

| Nodo | ¿LLM decide algo? | Qué es en la taxonomía de Anthropic |
| --- | --- | --- |
| Intake | Extrae campos y redacta la siguiente frase; el orden de preguntas lo fija la guía | Paso LLM dentro de un workflow |
| Policy Verification | Recupera por código; el LLM hace una segunda pasada que el verificador exacto acota | Paso LLM acotado por un verificador determinista |
| Decision | No: motor de reglas | No es un agente; es código |
| Compliance | Controles por código; la revisión completa usa el modelo y solo puede derivar o corregir con catálogo | Revisor ("aporta inteligencia, no acciones") |
| Transiciones | Función pura sobre el estado | Ruteo por código |

**No es multiagente.** Es un workflow determinista con pasos LLM, un único escritor por campo del estado (convención 6 de `team.md`, que es el principio de "escrituras de un solo hilo" de Cognition), trabajo de fondo precargado, verificación determinista y una persona que firma. Llamarlo "cuatro agentes" contradice P3 y es exactamente la objeción "¿por qué multiagente si es un flujo secuencial?" del ICP.

Inconsistencia a corregir: el PRD P1 dice "Los agentes capturan, verifican con cita, aplican reglas y derivan", y la respuesta a la objeción en 3.1 habla de "separación de responsabilidades" como si defendiera un multiagente. Además, un sistema multiagente real costaría 3–10× tokens según Anthropic, incompatible con 5 USD en 90 días.

### Recomendación

`adoptar en el runtime` el nombre y el argumento, no un cambio de arquitectura:

- **Nombre** en README, landing y video: "un agente conversacional (la agente, una sola voz) sobre un workflow de cuatro nodos; el ruteo es código; dos nodos usan el modelo, uno es reglas y uno es un revisor que solo puede bloquear o derivar". En el código y los ADR, "nodo", nunca "agente" para Intake/Policy Verification/Decision/Compliance.
- **Sección del README "¿Por qué no es multiagente?"**, con tres párrafos: (1) la distinción de Anthropic y los 3–10× tokens frente al techo de gasto; (2) cada categoría de MAST mapeada a su control concreto: especificación → contrato de entrada/salida y conjunto de escritura por nodo; desalineación → estado tipado único con un escritor por campo; verificación → verificador exacto de citas y compuertas duras; (3) Cognition 2026: el único rol "multi" que existe, la revisión de Compliance, es del tipo que funciona (aporta inteligencia, no escribe el caso).
- Corregir la palabra "agentes" de P1 en el PRD y el glosario la próxima vez que se toque el PRD, o declarar en el README que el PRD usa "agentes" en sentido coloquial. No requiere ADR nuevo; sí una nota en ADR-001 o en el glosario.
- `rechazar y documentarlo en un ADR` cualquier supervisor LLM que elija nodo o delegue (ya prohibido por las reglas del proyecto; conviene citar las fuentes de arriba en ADR-003 para que el rechazo no parezca dogma).

---

## 4. Herramientas (function calling), MCP y A2A

### Hallazgos

- **MCP**: la especificación vigente es la **2026-07-28** [P, blog oficial]: núcleo sin estado (se eliminan las sesiones de protocolo y `Mcp-Session-Id`), "Multi Round-Trip Requests", enrutamiento por cabeceras, listas cacheables, endurecimiento de autorización (validación de emisor RFC 9207; Dynamic Client Registration deprecado en favor de Client ID Metadata Documents), marco de extensiones (Tasks, MCP Apps) y deprecación de Roots, Sampling, Logging y HTTP+SSE con al menos 12 meses de salida. La versión anterior era 2025-11-25. Gobernanza: MCP fue donado a la Agentic AI Foundation de la Linux Foundation el 2025-12-09 [P]. SDK: > 500 M descargas mensuales entre los SDK Tier 1 [P, cifra del propio proyecto].
- **Buenas prácticas oficiales de seguridad** (borrador vigente) [P]: confused deputy en proxies OAuth con client ID estático (consentimiento por cliente obligatorio), **token passthrough prohibido** (un servidor MCP no acepta tokens no emitidos para él), SSRF en el descubrimiento OAuth, secuestro de manejadores de estado, compromiso de servidores locales, validación de URLs de autorización, ataques de mezcla y minimización de alcances.
- **Envenenamiento de herramientas** (tool poisoning): no está en esa página oficial; lo codifica OWASP como MCP03:2025 [P, OWASP MCP Top 10]. Invariant Labs mostró la prueba de concepto en abril de 2025 [S]. MCPTox (AAAI 2026): 353 herramientas reales de 45 servidores, 20 modelos, **36,5 % de éxito promedio** del ataque [S, resumen; paper arXiv 2508.14925].
- **A2A**: proyecto de la Linux Foundation desde junio de 2025; más de 150 organizaciones al primer año [P, nota de la Linux Foundation]; versión 1.0.1 en mayo de 2026 [S, Wikipedia; NV en primaria].
- **Starlette CVE-2026-48710 ("BadHost")**, relevante para todo servidor FastAPI: bypass de autorización por cabecera Host malformada en Starlette 0.8.3–1.0.0, corregido en 1.0.1 [S, varios avisos incluido el CCB de Bélgica]. Se usó para volver pre-autenticado un fallo de LiteLLM (sección 6).
- **Salida estructurada frente a herramientas**: 12-factor #4 "tools are just structured outputs" [P]. En Gemini 3 se pueden combinar salida estructurada y function calling [P, docs de structured output].
- **MCP en tiempo de desarrollo** ya existe en el repo: `.mcp.json` declara `context7` y servidores de AWS para el asistente de código (CLAUDE.md del proyecto). Eso es herramienta de desarrollo, no producto.

### Recomendación

- **Function calling en los nodos:** `rechazar y documentarlo en un ADR` en el turno de voz y para toda decisión o acción. Intake usa salida estructurada con esquema; Policy Verification llama a la recuperación por código; Decision no usa el modelo; la derivación a persona y la detección de emergencia son reglas. Razones: latencia (cada llamada a herramienta agrega otra vuelta al modelo), P3 (el modelo no elige acciones) y la superficie de inyección (RT-1, RT-2, RT-5). Única excepción razonable a futuro: ninguna en la v1.
- **Consumir servidores MCP en el runtime:** `rechazar y documentarlo en un ADR`. No hay herramienta externa que el producto necesite; sumaría tool poisoning y una especificación que acaba de cambiar su núcleo.
- **Exponer la consulta de pólizas como servidor MCP de solo lectura:** `diferir (trabajo futuro)` con aviso explícito de **alto riesgo resume-driven**. Aunque MCP aparece en 17–24 % de las vacantes [S], un Staff Engineer preguntará quién es el cliente y por qué un servidor de pólizas de una aseguradora se ofrece a un LLM arbitrario; exigiría autorización por tenant sin token passthrough, pruebas de aislamiento propias y una superficie pública más, con cero valor para el asegurado ni para la ajustadora. Si algún día se hace, que sea después de la v1, sobre datos sintéticos, fuera del alcance publicado y con su ADR.
- **A2A:** `rechazar y documentarlo en un ADR`. No hay un segundo agente de otra organización con el que hablar.
- **MCP en desarrollo:** `adoptar solo en desarrollo/pruebas`, documentado en una línea en la guía de contribución ("el asistente de código usa context7 para documentación; el producto no usa MCP").
- Un solo ADR corto, "Protocolos de agentes y herramientas", cubre las cuatro decisiones y responde por adelantado la pregunta "¿por qué no MCP?".
- Hallazgo para ADR-002 y para el investigador de seguridad: fijar Starlette ≥ 1.0.1 en el lockfile.

---

## 5. "Skills" y "harness engineering"

### Hallazgos

- **Agent Skills**: Anthropic lo publicó como estándar abierto el 2025-12-18 en agentskills.io [S, varias fuentes; la fecha no aparece en la página del estándar]. Una skill es una carpeta con `SKILL.md` (al menos `name` y `description`), instrucciones y recursos opcionales, cargada por **divulgación progresiva** (descubrimiento por nombre y descripción, activación al coincidir con la tarea, ejecución) [P]. La vitrina oficial lista decenas de clientes, casi todos agentes de código (Claude Code, Codex, Cursor, Gemini CLI, GitHub Copilot, VS Code, Junie, OpenHands, Kiro) y algunos runtimes (Spring AI, Letta) [P].
- **En runtimes de producto**: LangChain Deep Agents y la CLI de deepagents soportan skills [S]; Pydantic AI v2 (2026-06-23) introdujo "capabilities" y un "Harness" de primera parte (memoria, guardarraíles, gestión de contexto, sistema de archivos) [P]. Son piezas para agentes abiertos que eligen qué cargar.
- **Harness engineering**:
  - OpenAI, "Harness engineering: leveraging Codex in an agent-first world" (Ryan Lopopolo, 2026-02-11) [S, la página de OpenAI devolvió 403; resumen de terceros]: repositorio como sistema de registro, `AGENTS.md` corto (~100 líneas) como mapa y no enciclopedia, reglas de arquitectura aplicadas mecánicamente con linters propios, tareas de limpieza continuas.
  - Martin Fowler / Birgitta Böckeler, "Harness engineering for coding agent users" (2026-04-02) [P]: el harness son **guías** (feedforward: AGENTS.md, skills, reglas) y **sensores** (feedback: pruebas, linters, chequeos de tipos, revisión por IA), cada uno computacional o inferencial. Se aplica al **desarrollo**, no al runtime del producto.
- **AGENTS.md**: publicado por OpenAI en agosto de 2025 y donado a la Agentic AI Foundation el 2025-12-09; > 60.000 proyectos según el anuncio [P, nota de la Linux Foundation].

### Relevancia para Untangle

- **Runtime:** el producto no se beneficia de skills. Los nodos tienen prompts fijos y pequeños por contrato (~3.900 tokens por turno), el ruteo es código y no hay un agente abierto que deba decidir qué instrucciones cargar. Meter skills en el runtime sería introducir decisión del modelo sobre su propio contexto, contra P3, para adornar.
- **Desarrollo:** el proyecto ya practica harness engineering sin llamarlo así: flujo AI-DLC en `.claude/`, sensores y compuertas, reglas de `team.md` ("toda convención comprobable por una herramienta o por un grep"), reglas de importación, guion único de verificación. Es un buen argumento para evaluadores, siempre que se cuente con precisión.

### Recomendación

- **Skills en el runtime:** `rechazar y documentarlo en un ADR` (una línea dentro del ADR de protocolos de la sección 4).
- **Skills y harness en el desarrollo:** `adoptar solo en desarrollo/pruebas`, contado honestamente:
  - Agregar un `AGENTS.md` breve en la raíz que apunte a CLAUDE.md, a los ADR y al archivo de tareas, porque CLAUDE.md es específico de un proveedor y AGENTS.md es el estándar neutral.
  - Una sección corta en la documentación, "Cómo se construyó", que diga qué guías y qué sensores gobiernan al asistente de código, qué revisó una persona y qué no, y que enlace al guion de verificación como el sensor principal. Usar la taxonomía guías/sensores de Böckeler, que un evaluador senior reconoce.
  - No presentar el harness como característica del producto ni como "agentes" del sistema.

---

## 6. Gateway de modelos

### Hallazgos

**LiteLLM en 2026.**

- **Compromiso de PyPI (2026-03-24)** [P, comunicado oficial; P, Datadog Security Labs]: versiones 1.82.7 y 1.82.8 publicadas por el grupo TeamPCP con credenciales del mantenedor obtenidas tras comprometer Trivy en la cadena de CI de LiteLLM. Unos 40 minutos en PyPI antes de la cuarentena. 1.82.8 traía un `litellm_init.pth` que **se ejecutaba en cada arranque de Python aunque no se importara LiteLLM**; 1.82.7 escondía el código en `proxy_server.py`. Robaba variables de entorno, llaves SSH, credenciales de nube, tokens de Kubernetes y secretos de CI. Los usuarios de la imagen Docker del proxy no quedaron afectados (dependencias fijadas); quienes instalaron con `pip` sin fijar versión, sí. Versión limpia 1.83.0 el 2026-03-30 con sumas SHA-256 publicadas.
- **CVE-2026-42208** (aviso oficial 2026-04-29) [P]: inyección SQL pre-autenticación en la validación de claves del proxy, v1.81.16–1.83.6, CVSS 9,3; **explotada ~36 h después del aviso** [S, Sysdig, The Hacker News]. El aviso se refiere al proxy, no al SDK.
- **CVE-2026-42271** (Horizon3, 2026-06-01) [P]: inyección de comandos en endpoints de prueba MCP del proxy (1.74.2–1.83.6); encadenada con **Starlette CVE-2026-48710** se vuelve ejecución remota sin credenciales, CVSS 10,0; corregida en LiteLLM 1.83.7 con Starlette ≥ 1.0.1.

**Alternativas.**

- **Mozilla any-llm** 1.0 (2025-11-04): interfaz única que usa los SDK oficiales de cada proveedor por debajo [P, blog de Mozilla.ai]. Es la opción de SDK más limpia, pero para un solo proveedor LLM agrega una dependencia sin ganancia.
- **Bifrost** (Maxim AI, Go): proxy con ~11 µs de sobrecosto a 5.000 RPS según su propio benchmark [S, del proveedor]. **Portkey**: gateway abierto con gobierno y analítica concentrados en planes pagos [S]. **OpenRouter**: servicio de terceros que vería el tráfico [NV sobre sus condiciones vigentes]. Todos son un servicio o un intermediario más.
- **Abstracción de modelos de Pydantic AI**: "cada modelo a un cambio de string" [P]; duplicaría ProviderGateway y traería el framework completo.
- **Propios adaptadores (ADR-018)**: el SDK oficial de Gemini dentro de un adaptador, fábrica por uso, taxonomía cerrada de errores, topes por clave.

### Recomendación

- **LiteLLM (SDK y proxy):** `rechazar y documentarlo en un ADR`. No por moda contraria: por tres incidentes verificables en seis meses, dos de ellos críticos en el proxy y uno de cadena de suministro que alcanzaba incluso sin importar el paquete. Es el ejemplo perfecto para justificar en el README la regla de lockfile con hashes e instalación reproducible.
- **Propios adaptadores:** `adoptar en el runtime` (ADR-018 se mantiene). Añadir a su sección de alternativas: LiteLLM con los incidentes, any-llm (válido, innecesario con un proveedor), Pydantic AI (duplica la interfaz), gateways proxy (otro servicio; ocultan topes y errores por proveedor).
- **Si se activa el respaldo con Groq u otro proveedor** (ADR-006), se implementa como segundo adaptador detrás de la misma interfaz, no como gateway.
- **Flag resume-driven:** poner un gateway proxy (Bifrost, Portkey, LiteLLM Proxy) en un proyecto con un solo proveedor LLM y una persona.

---

## 7. Salida estructurada y prompts

### Hallazgos

- **Gemini structured output** (docs actualizadas 2026-09-02) [P]: con esquema JSON la salida es **JSON sintácticamente válido**, y la documentación pide validar los valores en la aplicación (la corrección semántica no está garantizada). Soporta un subconjunto de JSON Schema (tipos, `properties`, `required`, `additionalProperties`, `enum`, `format` de fecha, `minimum`/`maximum`, `items`, `prefixItems`, `minItems`/`maxItems`, `title`, `description`); permite definir el esquema con `model_json_schema()` de Pydantic; soporta streaming en fragmentos de JSON parcial; en Gemini 3 se combina con function calling y otras herramientas. Google anunció soporte de JSON Schema con orden implícito de propiedades [P, blog de Google, fecha no verificada en la página].
- **Pydantic AI**: modos `ToolOutput` (por defecto), `NativeOutput` y `PromptedOutput`; validadores con `ModelRetry` y presupuesto de reintentos; streaming de salida parcialmente validada; Gemini 3 soporta `NativeOutput` junto con herramientas [P].
- **Instructor**: activo, 1.14–1.15 a inicios de 2026 [S].
- **BAML**: lenguaje propio con generación de clientes y "schema-aligned parsing" [P, sitio de BoundaryML; la afirmación de que SAP con GPT-3.5 supera a GPT-4o con structured outputs es del propio proveedor].
- **DSPy**: 3.3.x con optimizador GEPA integrado [P, PyPI y docs]. Optimizar prompts exige muchas llamadas al modelo.

### Recomendación

- **Salida estructurada nativa de Gemini + validación con Pydantic dentro del adaptador:** `adoptar en el runtime`. Una violación de esquema o de validación se traduce a `invalid_response`, con un único reintento conforme a la política de fallo del nodo, y después degradación honesta. El esquema de extracción de Intake deja cada campo opcional con estado por campo (ADR-005), para que el modelo no invente un valor por obligación del esquema. Esto cabe en ADR-018 como detalle, sin ADR nuevo.
- **Pregunta de diseño abierta para Functional Design y el experimento 1** (no decidida aquí): en voz, la frase a decir necesita streaming de texto al TTS y la extracción necesita JSON. Opciones: (a) una sola llamada con esquema donde el campo de la frase va primero y se transmite el JSON parcial al TTS; (b) la frase en texto libre en el turno y la extracción en segundo plano después; (c) dos llamadas. La (c) duplica TTFT y gasto; la (a) es la que respeta "una llamada por turno" pero es la más compleja; hay que medirla.
- **Instructor, BAML, Pydantic AI para la salida:** `rechazar y documentarlo en un ADR` (una línea en ADR-018): el soporte nativo del proveedor más Pydantic ya da lo que ofrecen; BAML agrega un lenguaje y generación de código (riesgo resume-driven).
- **DSPy/GEPA:** `diferir (trabajo futuro)`. Optimizar prompts contra DS-2 consume cuota y tokens y produce prompts menos legibles para quien lee el repo; fuera de los 90 días. Flag resume-driven si se agrega "para mostrar".
- **Versionado de prompts:** `adoptar en el runtime` lo que ya dicen las reglas, precisado: un archivo por prompt por nodo en el repositorio, con identificador y hash; el hash va como atributo en el tramo de la traza y en el reporte de evals; cambiar el archivo dispara la compuerta. El repositorio es la fuente de verdad; la gestión de prompts de Langfuse, si se usa, solo como espejo de lectura (`rechazar` como fuente).

---

## 8. Multimodal

### Hallazgos

**Speech-to-speech de Google.**

- **Gemini 3.8 Live** y **3.8 Live Extended Thinking**, publicados el **2026-09-15** (hace dos días) [P, blog de Google; P, página de deprecaciones]: speech-to-speech nativo, llamadas a funciones asíncronas mientras sigue hablando, 97+ idiomas con "consistencia de acento", contexto visual. Precio: 0,005 USD/min de audio de entrada y 0,018 USD/min de salida [P]; sin plan gratuito mencionado [P]. Equivale a 3 y 12 USD por millón de tokens [S, MarkTechPost]. No se encontró si el contexto acumulado se factura aparte por turno [NV].
- **Voces**: solo voces precargadas configurables por `prebuiltVoiceConfig`; no hay voz personalizada ni clonada [S, varias fuentes y un feature request abierto en `adk-docs`]. Los modelos de audio nativo eligen el idioma solos y no aceptan fijar código de idioma [P, Live guide].
- **Salida**: los modelos de audio nativo **solo admiten modalidad AUDIO**; el texto se obtiene activando la transcripción de salida, que llega en los mismos eventos que el audio [P, Live guide, 2026-09-16]. Sesiones de solo audio limitadas a 15 minutos; contexto de 128k tokens [P].
- Tarjeta del modelo: conocimiento hasta enero de 2025; declara alucinaciones como limitación; no habla de voces personalizadas [P].
- Debate cascada frente a S2S [S, todos con sesgo de proveedor]: S2S gana en tiempo al primer audio (300–500 ms típico frente a 600–1.200 ms, Future AGI); la cascada gana en observabilidad, auditoría y control de texto antes del audio (Deepgram, que vende cascada); S2S por tokens puede costar varias veces lo teórico por reenviar el historial (Deepgram).

**Contraste con las restricciones del proyecto.**

| Requisito | Cascada aprobada | Gemini 3.8 Live |
| --- | --- | --- |
| P10: una voz paisa idéntica en ES y EN (Cartesia Catalina, ADR-008) | Sí | No: solo voces precargadas |
| Guardia de salida dentro del turno (P1, P2, F7.5): texto aprobado antes de sonar | Sí, por frase antes del TTS | No: el modelo genera audio directo; la transcripción llega con el audio |
| P3: el grafo no depende del framework de voz; el modelo no decide acciones | Sí | Tensión: la herramienta asíncrona la invoca el modelo |
| D7: 0,005 USD por minuto de llamada para el modelo | Por medir | Solo audio: 0,023 USD/min ≈ 4,6× la meta, antes del contexto |
| Techo 5 USD / 90 días | Por medir | ~217 minutos de audio en total con todo el techo |
| Madurez | Componentes con meses de uso | Dos días publicado |
| Trazas por etapa (M7, M13) | STT, LLM, TTS separados | Una caja |

**Documentos e imágenes (C1, MOD-14).**

- Gemini acepta PDF de hasta 50 MB o 1.000 páginas; **258 tokens por página**; extracción a esquema estructurado [P, docs 2026-09-04]. Técnicamente cabe en el adaptador existente con el mismo esquema y la misma validación.
- C1 es el tercero en el orden de corte del PRD (S2, S1, C1, S5, S4). En plan gratuito, lo que sube un visitante iría a Google con las condiciones de uso que ADR-006 ya aceptó solo para texto con aviso.

### Recomendación

- **Gemini Live / speech-to-speech para la v1:** `rechazar y documentarlo en un ADR` (enmienda de ADR-009 o ADR corto propio). Razones verificables: rompe P10 (sin voz propia), impide la guardia de salida antes del audio, cuesta ~4,6× la meta D7 solo en audio, y tiene dos días de vida.
- **S2S como comparación:** `diferir (trabajo futuro)`: después de la v1, un experimento acotado "cascada frente a S2S" con la misma batería DS-5, publicado aunque la cascada pierda en latencia, sería un buen contenido de evaluación honesta; no ahora.
- **Carga de documentos sintéticos (C1):** `diferir (trabajo futuro)`. Cuando entre, usar el mismo adaptador y esquema, solo documentos sintéticos de la demo, aviso explícito, revisión de la ajustadora antes de escribir en el caso, y un golden set propio antes de publicar cualquier métrica (P5).
- **Flag resume-driven:** agregar voz nativa o visión "porque salió la semana pasada".

---

## Señales de "resume-driven" detectadas en el alcance

| Idea | Por qué castigaría un evaluador | Veredicto |
| --- | --- | --- |
| Llamar "multiagente" a los cuatro nodos | Es un workflow; el ICP ya anticipa la objeción | No hacerlo |
| Servidor MCP de pólizas | Sin cliente real; suma superficie de ataque y aislamiento por tenant | Diferir con aviso |
| A2A | Sin segundo agente externo | Rechazar |
| Segundo LLM "reasoner" en paralelo al turno | El trabajo lento ya es determinista; duplica gasto | Rechazar |
| Skills en el runtime | Nodos con prompts fijos; contra P3 | Rechazar |
| Gateway proxy (LiteLLM Proxy, Bifrost, Portkey) | Un proveedor, una persona; incidentes de LiteLLM | Rechazar |
| BAML, Instructor, DSPy/GEPA | Duplican lo nativo o gastan el techo | Rechazar / diferir |
| Temporal o DBOS "por durabilidad" | Otro concepto de orquestación sin problema medido | Diferir DBOS |
| Gemini 3.8 Live | Rompe P10 y la guardia; dos días de vida | Rechazar v1 |
| Funciones beta de LangGraph (DeltaChannel, streaming v3) | Riesgo de cambio sin beneficio en esta escala | No usar |

LangGraph en sí **no** es resume-driven si se usa por lo que resuelve (puntos de control, `interrupt()`, streaming), solo dentro de Orchestration y con la función de transición independiente del framework.

---

## Tabla final de recomendaciones

| Tecnología | Recomendación | Razón | ¿Cambia un ADR aprobado? |
| --- | --- | --- | --- |
| LangGraph 1.2.x + checkpointer Postgres oficial | adoptar en el runtime | Resuelve checkpoints, `interrupt()` y streaming; 1.x estable; reconocido (22,6 % de avisos que nombran framework) | Sí: enmienda de ADR-003 (versiones por CVE, msgpack estricto, `interrupt()` re-ejecuta el nodo, timeout/error_handler nativos, ruta PA-3, razones de rechazo) |
| Funciones beta de LangGraph (DeltaChannel, streaming v3) | rechazar y documentarlo en un ADR | Beta; sin necesidad a esta escala | Sí, una línea en ADR-003 |
| Pydantic AI v2 / pydantic-graph | rechazar y documentarlo en un ADR | Sin persistencia Postgres de grafos; durabilidad vía motor externo; ventana de rupturas de 3 meses; duplica ProviderGateway | Sí: reemplazar la razón actual en ADR-003 y añadir a ADR-018 |
| Google ADK 2.0 | rechazar y documentarlo en un ADR | Acopla al proveedor del modelo; rupturas de 2.0; cadencia alta | Sí: añadir a alternativas de ADR-003 |
| OpenAI Agents SDK | rechazar y documentarlo en un ADR | Pre-1.0; bucle de agente, sin grafo tipado | Sí: alternativas de ADR-003 |
| Microsoft Agent Framework 1.0 | rechazar y documentarlo en un ADR | Sin checkpoint Postgres en Python | Sí: alternativas de ADR-003 |
| LlamaIndex Workflows | rechazar y documentarlo en un ADR | Modelo por eventos menos legible para P3; durabilidad vía servidor aparte | Sí: alternativas de ADR-003 |
| Temporal | rechazar y documentarlo en un ADR | Servidor adicional; sin plan gratuito en la nube | No (ya rechazado) |
| DBOS Transact | diferir (trabajo futuro) | Recuperación automática sobre la misma Postgres, pero segundo concepto de orquestación | Sí: ADR-004 debe exigir barrido de relanzamiento al arrancar y citar DBOS como alternativa |
| Máquina de estados propia | rechazar y documentarlo en un ADR | Reimplementa pausa y reanudación; se conserva la transición pura sin framework | No (ya rechazada); reforzar razón |
| Regla "una llamada LLM por turno, streaming, sin herramientas" | adoptar en el runtime | El TTFT del modelo domina; el grafo pesa milisegundos | Sí: precisión en ADR-004/ADR-006 o NFR |
| Trabajo CPU fuera del event loop | adoptar en el runtime | asyncio no aísla CPU; cortes de audio | Sí: ADR-004 |
| Frases fijas pre-sintetizadas | adoptar en el runtime | Menos latencia y gasto; verificar términos del TTS | No; Functional Design |
| Caché semántica estilo VoiceAgentRAG | diferir (trabajo futuro) | Solo si la precarga por póliza no alcanza | No |
| Segundo LLM "reasoner" | rechazar y documentarlo en un ADR | El fondo ya es determinista; duplica gasto | No; README |
| Nombre "workflow con pasos LLM", no "multiagente" | adoptar en el runtime (README, código, landing) | Anthropic, Cognition, MAST; 3–10× tokens incompatibles con el techo | No; nota en ADR-001/glosario y corrección de P1 del PRD |
| Function calling en nodos | rechazar y documentarlo en un ADR | Latencia, P3, superficie de inyección | Sí: ADR nuevo corto de protocolos y herramientas |
| MCP en el runtime (consumir) | rechazar y documentarlo en un ADR | Sin necesidad; tool poisoning; spec recién cambiada | Sí: mismo ADR nuevo |
| Servidor MCP de pólizas (exponer) | diferir (trabajo futuro) | Alto riesgo resume-driven; exige authz por tenant | Sí: mismo ADR nuevo |
| MCP en desarrollo (context7, etc.) | adoptar solo en desarrollo/pruebas | Ya en uso por el asistente de código | No |
| A2A | rechazar y documentarlo en un ADR | Sin agente externo | Sí: mismo ADR nuevo |
| Agent Skills en el runtime | rechazar y documentarlo en un ADR | Prompts fijos por nodo; contra P3 | Sí: mismo ADR nuevo |
| Agent Skills, AGENTS.md y harness engineering | adoptar solo en desarrollo/pruebas | Ya se practica; contarlo con guías/sensores | No |
| LiteLLM (SDK y proxy) | rechazar y documentarlo en un ADR | PyPI comprometido (2026-03-24), CVE-2026-42208 explotado, CVE-2026-42271 + BadHost | Sí: añadir evidencia a ADR-018 |
| any-llm, Bifrost, Portkey, OpenRouter | rechazar y documentarlo en un ADR | Un proveedor LLM; otro servicio o intermediario | Sí: alternativas de ADR-018 |
| Adaptadores propios | adoptar en el runtime | Topes y errores por proveedor visibles | No (se refuerza ADR-018) |
| Starlette ≥ 1.0.1 | adoptar en el runtime | CVE-2026-48710 afecta a FastAPI | Sí: fijar en ADR-002/lockfile |
| Structured output nativo de Gemini + Pydantic | adoptar en el runtime | JSON válido garantizado; validación semántica propia | Sí: detalle en ADR-018 |
| Instructor, BAML | rechazar y documentarlo en un ADR | Duplican lo nativo; BAML suma lenguaje | Sí: una línea en ADR-018 |
| DSPy / GEPA | diferir (trabajo futuro) | Gasta cuota; prompts menos legibles | No |
| Prompts versionados en repo con hash en trazas | adoptar en el runtime | Reproducibilidad y compuerta de evals | No (precisa reglas vigentes) |
| Gemini 3.8 Live (speech-to-speech) | rechazar y documentarlo en un ADR | Rompe P10 y la guardia; ~4,6× D7; dos días de vida | Sí: enmienda de ADR-009 |
| Comparación cascada vs S2S | diferir (trabajo futuro) | Buen contenido honesto tras la v1 | No |
| Extracción de documentos (C1) con Gemini | diferir (trabajo futuro) | Cabe en el adaptador; C1 se corta antes que S5/S4 | No |
| `gemini-3.1-flash-lite` | adoptar en el runtime (sin cambio) | Apagado anunciado 2027-05-07, después del proyecto; caché implícita no fiable | Sí, menor: anotar fecha de retiro y caché en ADR-006 |

## ADR que deberían cambiar

1. **ADR-003 (LangGraph)**: enmienda, no reemplazo. Versiones mínimas por CVE-2026-28277 y CVE-2026-48775 y deserialización estricta; semántica de re-ejecución de `interrupt()`; `timeout=`/`error_handler=` nativos detrás de la política como dato; evitar betas; ruta PA-3 con el checkpointer oficial como primera opción verificable; requisito de consistencia del estado ante interrupción de voz; alternativas rechazadas reescritas con evidencia de 2026.
2. **ADR-004 (fondo sin broker)**: barrido explícito de relanzamiento al arrancar (un checkpoint no reanuda solo); CPU fuera del event loop; durabilidad `async` en el turno; DBOS como alternativa diferida.
3. **ADR-009 (librería de voz)**: rechazo explícito de speech-to-speech para la v1 con las razones verificadas.
4. **ADR-018 (adaptadores)**: evidencia de LiteLLM; any-llm, Pydantic AI y gateways proxy en alternativas; salida estructurada nativa con validación Pydantic traducida a `invalid_response`.
5. **ADR-002 (stack)**: fijar Starlette ≥ 1.0.1 (a coordinar con el investigador de seguridad).
6. **ADR-006 (modelo)**: nota menor sobre retiro 2027-05-07 y caché implícita.
7. **ADR nuevo, corto**: "Protocolos de agentes y herramientas fuera del runtime" (function calling, MCP consumir/exponer, A2A, skills).
8. **Fuera de ADR**: README con "¿Por qué no es multiagente?" y corrección de "agentes" en P1 del PRD.

---

## Fuentes

Formato: título — autor/sitio — fecha de publicación o actualización — URL. "s/f" = sin fecha visible.

### Runtime y orquestación

- LangGraph changelog — LangChain Docs — entradas 2025-10-20, 2026-03-10, 2026-05-12 — https://docs.langchain.com/oss/python/releases/changelog
- langgraph (PyPI) — 1.2.11, 2026-08-11 — https://pypi.org/project/langgraph/
- langgraph-checkpoint (PyPI) — 4.2.0, 2026-08-07 — https://pypi.org/project/langgraph-checkpoint/
- langgraph-checkpoint-postgres (PyPI) — 3.1.2, 2026-08-07 — https://pypi.org/project/langgraph-checkpoint-postgres/
- `base.py` del checkpointer de Postgres — GitHub langchain-ai/langgraph, rama main — consultado 2026-09-17 — https://github.com/langchain-ai/langgraph/blob/main/libs/checkpoint-postgres/langgraph/checkpoint/postgres/base.py
- Issue #7345 "Configurable PostgreSQL schema" — GitHub — 2026-03-30 — https://github.com/langchain-ai/langgraph/issues/7345
- CVE-2026-28277 — GitHub Advisory GHSA-g48c-2wqr-h844 — 2026 — https://github.com/advisories/GHSA-g48c-2wqr-h844
- CVE-2026-48775 — GitHub Advisory GHSA-fjqc-hq36-qh5p — 2026-05-22 — https://github.com/advisories/GHSA-fjqc-hq36-qh5p
- From SQLi to RCE: Exploiting LangGraph's Checkpointer — Check Point Research — 2026-06-11 — https://research.checkpoint.com/2026/from-sqli-to-rce-exploiting-langgraphs-checkpointer/
- Interrupts — LangChain Docs — s/f — https://docs.langchain.com/oss/python/langgraph/interrupts
- Durability — LangChain Reference — s/f — https://reference.langchain.com/python/langgraph/types/Durability
- Why Checkpoints Aren't Durable Execution — Yaron Schneider, Diagrid (proveedor) — 2026-02-25 — https://www.diagrid.io/blog/checkpoints-are-not-durable-execution-why-langgraph-crewai-google-adk-and-others-fall-short-for-production-agent-workflows
- pipecat-langgraph-example — LangChain — s/f — https://github.com/langchain-ai/pipecat-langgraph-example
- Building a Voice AI Agent with Policy Guardrails Using Twilio, Pipecat, and LangGraph — WebRTC.ventures — 2026-01-22 — https://webrtc.ventures/2026/01/building-a-voice-ai-agent-with-policy-guardrails-using-twilio-pipecat-and-langgraph/
- LangChain integration guide (LLMAdapter) — LiveKit Docs — s/f — https://docs.livekit.io/agents/models/llm/langchain/
- pydantic-ai (PyPI) — 2.44.0, 2026-09-17 — https://pypi.org/project/pydantic-ai/
- Pydantic AI v2: capabilities, a leaner core, and the Harness — Pydantic — 2026-06-23 — https://pydantic.dev/articles/pydantic-ai-v2
- Durable Execution overview — Pydantic Docs — s/f — https://pydantic.dev/docs/ai/integrations/durable_execution/overview/
- pydantic-graph (PyPI) — 2.44.0, 2026-09-17 — https://pypi.org/project/pydantic-graph/
- Graph Persistence — DeepWiki (secundaria) — s/f — https://deepwiki.com/pydantic/pydantic-ai/10.2-graph-persistence-and-mermaid-visualization
- Issue #3697 "Does Temporal handle Beta Graph resumability…" — GitHub — s/f — https://github.com/pydantic/pydantic-ai/issues/3697
- Welcome to ADK 2.0 — Google — GA Python 2026-05-19 — https://adk.dev/2.0/
- google-adk (PyPI) — 2.9.1, 2026-09-15 — https://pypi.org/project/google-adk/
- Why Google ADK's Human-in-the-Loop Story Has a Production Gap — Gary Thomas George, Medium (secundaria) — s/f — https://garythomasgeorge.medium.com/why-google-adks-human-in-the-loop-story-has-a-production-gap-and-one-way-it-could-be-fixed-66aabef33a32
- Microsoft Agent Framework Version 1.0 — Microsoft DevBlogs — 2026-04-03 — https://devblogs.microsoft.com/agent-framework/microsoft-agent-framework-version-1-0/
- Workflows – Checkpoints — Microsoft Learn — 2026-09-16 — https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints
- openai-agents (PyPI) — 0.22.2, 2026-09-09 — https://pypi.org/project/openai-agents/
- Human-in-the-loop — OpenAI Agents SDK docs — s/f — https://openai.github.io/openai-agents-python/human_in_the_loop/
- llama-index-workflows (PyPI) — 2.24.0, 2026-09-16 — https://pypi.org/project/llama-index-workflows/
- dbos-transact-py — DBOS, GitHub — s/f — https://github.com/dbos-inc/dbos-transact-py
- Temporal pricing — Temporal — s/f — https://temporal.io/pricing
- Row Security Policies — PostgreSQL 18 docs — s/f — https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- What AI Engineer Job Ads Actually Screen For — John Lee, DEV Community (secundaria) — 2026-09-09 — https://dev.to/johnonlee/what-ai-engineer-job-ads-actually-screen-for-53lf
- langgraph / pydantic-ai downloads — pepy.tech — consultado 2026-09-17 — https://pepy.tech/projects/langgraph , https://pepy.tech/projects/pydantic-ai

### Latencia y voz

- RAG Frameworks benchmark — AIMultiple (secundaria; fechas inconsistentes en la página) — https://aimultiple.com/rag-frameworks
- Gemini 3.1 Flash-Lite providers — Artificial Analysis — s/f — https://artificialanalysis.ai/models/gemini-3-1-flash-lite-preview/providers
- Lowest-Latency Inference APIs for Voice and Realtime Agents — MarkTechPost (secundaria) — 2026-08-30 — https://www.marktechpost.com/2026/08/30/lowest-latency-inference-apis-for-voice-and-realtime-agents-a-time-to-first-token-ttft-first-benchmark/
- Gemini deprecations — Google AI for Developers — 2026-09-16 — https://ai.google.dev/gemini-api/docs/deprecations
- Context caching — Google AI for Developers — 2026-09-02 — https://ai.google.dev/gemini-api/docs/caching
- Gemini-3.1-flash-lite: implicit cache stopped applying cost savings — Google AI Developers Forum — jul–ago 2026 — https://discuss.ai.google.dev/t/gemini-3-1-flash-lite-implicit-cache-stopped-applying-cost-savings-june-30-2026/173779
- The talker-reasoner pattern for voice agents — LiveKit — 2026-04-01 — https://livekit.com/blog/talker-reasoner-pattern-voice-agents
- Understand and Improve Voice Agent Latency — LiveKit — 2026-04-13 — https://livekit.com/blog/understand-and-improve-agent-latency
- Agents Thinking Fast and Slow: A Talker-Reasoner Architecture — Christakopoulou et al. — arXiv 2410.08328 (oct. 2024) — https://arxiv.org/abs/2410.08328
- VoiceAgentRAG — Qiu et al. — arXiv 2603.02206 (2026-03-02) — https://arxiv.org/html/2603.02206
- How to Optimize LiveKit Voice Agent Latency in 2026 — Future AGI (secundaria, proveedor) — 2026 — https://futureagi.com/blog/how-to-optimize-livekit-latency-2026/
- Cascaded Voice AI vs Speech-to-Speech: The 2026 Architecture Decision — Future AGI (proveedor) — 2026-04-09, act. 2026-05-19 — https://futureagi.com/blog/cascaded-voice-ai-vs-speech-to-speech-2026/
- NLP analyzer latency — Presidio discussion #1097 (secundaria) — s/f — https://github.com/microsoft/presidio/discussions/1097
- Connection latency and timeouts — Neon Docs — s/f — https://neon.com/docs/connect/connection-latency

### Multiagente

- Building effective agents — Erik Schluntz y Barry Zhang, Anthropic — 2024-12-19 — https://www.anthropic.com/engineering/building-effective-agents
- When to use multi-agent systems (and when not to) — Anthropic — 2026-01-23 — https://claude.com/blog/building-multi-agent-systems-when-and-how-to-use-them
- How we built our multi-agent research system — Anthropic — 2025-06-13 — https://www.anthropic.com/engineering/multi-agent-research-system
- Don't Build Multi-Agents — Walden Yan, Cognition — junio de 2025 — https://cognition.com/blog/dont-build-multi-agents
- Multi-Agents: What's Actually Working — Walden Yan, Cognition — 2026-04-22 — https://cognition.com/blog/multi-agents-working
- Why Do Multi-Agent LLM Systems Fail? — Cemri et al. — arXiv 2503.13657 (2025-03-17, rev. 2025-10-26); NeurIPS 2025 — https://arxiv.org/abs/2503.13657
- How and when to build multi-agent systems — Harrison Chase, LangChain — 2025-06-16 — https://www.langchain.com/blog/how-and-when-to-build-multi-agent-systems
- 12-factor agents — HumanLayer — s/f — https://github.com/humanlayer/12-factor-agents

### Herramientas, MCP, A2A, skills, harness

- The 2026-07-28 Specification — MCP Blog — 2026-07-28 — https://blog.modelcontextprotocol.io/posts/2026-07-28/
- Key Changes 2026-07-28 — MCP — https://modelcontextprotocol.io/specification/2026-07-28/changelog
- Security Best Practices (draft) — MCP — s/f — https://modelcontextprotocol.io/specification/draft/basic/security_best_practices
- MCP03:2025 Tool Poisoning — OWASP MCP Top 10 — 2025 — https://owasp.org/www-project-mcp-top-10/2025/MCP03-2025%E2%80%93Tool-Poisoning
- MCPTox — arXiv 2508.14925 — 2025 — https://arxiv.org/pdf/2508.14925
- A2A surpasses 150 organizations — Linux Foundation — 2026 — https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year
- Agent2Agent — Wikipedia (secundaria) — https://en.wikipedia.org/wiki/Agent2Agent
- Formation of the Agentic AI Foundation (MCP, goose, AGENTS.md) — Linux Foundation — 2025-12-09 — https://www.linuxfoundation.org/press/linux-foundation-announces-the-formation-of-the-agentic-ai-foundation
- Agent Skills Overview — agentskills.io — s/f — https://agentskills.io/home
- Agent Skills — Simon Willison (secundaria) — 2025-12-19 — https://simonwillison.net/2025/Dec/19/agent-skills/
- Harness engineering for coding agent users — Birgitta Böckeler, martinfowler.com — 2026-04-02 — https://martinfowler.com/articles/harness-engineering.html
- Harness engineering: leveraging Codex in an agent-first world — Ryan Lopopolo, OpenAI — 2026-02-11 (primaria devolvió 403) — https://openai.com/index/harness-engineering/ ; resumen: https://businessdatasolutions.github.io/ai-wiki/sources/2026-02-11-lopopolo-codex-harness-engineering
- Customize Deep Agents (skills) — LangChain Docs (secundaria para el soporte de skills) — s/f — https://docs.langchain.com/oss/python/deepagents/customization
- CVE-2026-48710 (BadHost) — CCB Bélgica — 2026 — https://ccb.belgium.be/advisories/warning-vulnerability-starlette-framework-and-related-frameworks-fastapi-exposes

### Gateway

- Security Update: Suspected Supply Chain Incident — LiteLLM — 2026-03 — https://docs.litellm.ai/blog/security-update-march-2026
- LiteLLM and Telnyx compromised on PyPI — Datadog Security Labs — 2026-03-24/27 — https://securitylabs.datadoghq.com/articles/litellm-compromised-pypi-teampcp-supply-chain-campaign/
- Security Update: CVE-2026-42208 in LiteLLM Proxy — LiteLLM — 2026-04-29 — https://docs.litellm.ai/blog/cve-2026-42208-litellm-proxy-sql-injection
- CVE-2026-42208 exploited within 36 hours — Sysdig — 2026 — https://www.sysdig.com/blog/cve-2026-42208-targeted-sql-injection-against-litellms-authentication-path-discovered-36-hours-following-vulnerability-disclosure
- CVE-2026-42271 chained with CVE-2026-48710 — Horizon3.ai — 2026-06-01 — https://horizon3.ai/attack-research/vulnerabilities/cve-2026-42271-chained-with-cve-2026-48710/
- Run Any LLM from One API: Introducing any-llm 1.0 — Mozilla.ai — 2025-11-04 — https://blog.mozilla.ai/run-any-llm-with-a-single-api-introducing-any-llm-v1-0/
- Bifrost — Maxim AI, GitHub (cifras del proveedor) — s/f — https://github.com/maximhq/bifrost

### Salida estructurada y prompts

- Structured outputs — Google AI for Developers — 2026-09-02 — https://ai.google.dev/gemini-api/docs/structured-output
- Google announces support for JSON Schema and implicit property ordering — Google — fecha no verificada — https://blog.google/innovation-and-ai/technology/developers-tools/gemini-api-structured-outputs/
- Output — Pydantic AI Docs — s/f — https://pydantic.dev/docs/ai/core-concepts/output/
- Instructor — 567 Labs — 2026 — https://python.useinstructor.com/
- BAML — BoundaryML — s/f — https://boundaryml.com/
- dspy (PyPI) y GEPA — Stanford NLP — 2026 — https://pypi.org/project/dspy/ , https://dspy.ai/api/optimizers/GEPA/overview/

### Multimodal

- Build real-time voice applications with Gemini 3.8 Live and 3.5 Transcribe — Google — 2026-09-15 — https://blog.google/innovation-and-ai/technology/developers-tools/build-real-time-voice-applications-gemini-audio/
- Gemini 3.8 Audio model card — Google DeepMind — septiembre de 2026 — https://deepmind.google/models/model-cards/gemini-3-8-audio/
- Google Releases Gemini 3.8 Live — MarkTechPost (secundaria) — 2026-09-15 — https://www.marktechpost.com/2026/09/15/google-releases-gemini-3-8-live-and-3-8-live-extended-thinking-for-production-grade-voice-agents/
- Live API capabilities guide — Google AI for Developers — 2026-09-16 — https://ai.google.dev/gemini-api/docs/live-guide
- Live API overview — Google AI for Developers — 2026-09-15 — https://ai.google.dev/gemini-api/docs/live
- Feature request: custom voice support in Gemini Live — google/adk-docs #487 (secundaria) — s/f — https://github.com/google/adk-docs/issues/487
- Speech-to-Speech vs Cascade — Deepgram (proveedor de cascada) — 2026 — https://deepgram.com/learn/speech-to-speech-vs-cascade-voice-agent-architecture
- Document understanding — Google AI for Developers — 2026-09-04 — https://ai.google.dev/gemini-api/docs/document-processing

### Documentos del proyecto leídos

- `/Users/miguelczz/Proyectos/untangle/aidlc/spaces/default/intents/260915-untangle-app/inception/domain-design/decisions.md` (ADR-003, 004, 006, 009, 014, 015, 016, 017, 018)
- `/Users/miguelczz/Proyectos/untangle/docs/specs/prd.md` (Segmentos 3.1, 6, 9.2, MOD-02, MOD-03, MOD-13, MOD-14)
