# Plan AIDLC para Untangle

**Fuente de verdad del proceso de definición y construcción del aplicativo.**
Se actualiza al cerrar cada paso (estado, salida, decisiones, lecciones). Si una sesión nueva arranca, se lee este archivo primero.

- Proyecto: Untangle, sistema multiagente de IA para seguros (cotización, suscripción y FNOL) con voz en tiempo real.
- Brief del autor: [00-brief-untangle.md](00-brief-untangle.md) (documento fuente de toda la pre-incepción).
- Landing ya publicada: `site/` (untangle-ai.vercel.app), diseño en [`design-package.md`](../design-package.md). La landing es la cara del producto; el aplicativo se define a partir de aquí.
- Metodología: AIDLC de AWS, versión personalizada del equipo (kit "Agentify IAOps Documentos" en Drive, copiado a `docs/`).
- Última actualización: 2026-09-15 (sesión 1, Claude Code).

---

## 1. Estado de avance

| Fase | Paso | Descripción | Estado | Salida |
|---|---|---|---|---|
| 0 | 0.1 | Recopilar kit del Drive, curso y repo AWS | Hecho | `docs/` (este árbol) |
| 0 | 0.2 | Guardar brief del autor | Hecho | `docs/00-brief-untangle.md` |
| 0 | 0.3 | Plan documentado | Hecho | este archivo |
| 0 | 0.4 | Evaluación del brief y ajustes propuestos | Hecho, aprobado por Miguel | `docs/01-evaluacion-brief.md` |
| 0 | 0.5 | Adenda del autor al brief (aclaraciones y decisiones) | Hecho | `docs/00-brief-untangle.md`, sección "Adenda" |
| 1 | 1 | Deep research sobre la idea | Hecho, pendiente de aprobación (71 fuentes, 14 decisiones para el PVB) | `docs/pre_prb/idea.md` |
| 1 | 2 | Deep research con posición crítica | Hecho, pendiente de aprobación (16 críticas, 12 cambios propuestos a la idea) | `docs/pre_prb/critica.md` |
| 1 | 3 | Pre-PRB con plantillas (overview, icp, mercado, pvb) | Hecho, pendiente de aprobación (PVB v1.0 con posiciones marcadas [propuesta]) | `docs/pre_prb/{overview,icp,mercado,pvb}.md` |
| 1 | 4 | Crítica del PVB con `ai-product-base.md` | Hecho: 9 puntos aceptados por Miguel; PVB v1.1 producido | `docs/pre_prb/respuestas_critica_pvb.md` + `pvb.md` v1.1 |
| 1 | 5 | PRD por co-creación (Prompt 1) | Completado: PRD v1.0 con Paso 0 y 13 segmentos aprobados (2026-09-15) | `docs/specs/prd.md` |
| 1 | 5a | Guía de voz y tono de la agente (insumo para PRD 6 y 7, Incepción 2.4 y 2.5, Construcción 3.1) | Hecho, aprobada por Miguel con sus valores por defecto (nombre Valentina, marcadores ligeros, ritmo, frases) | `docs/pre_prb/voz-y-tono.md` |
| 1 | 5b | Investigación: misma voz paisa en español e inglés y proveedores | Hecho: viable en ElevenLabs (biblioteca con voces de Medellín, pero no por API en el gratuito) y Cartesia (voces colombianas, gratuito con API); plan D-016 con prueba ciega en semana 1 | `docs/reference/voz-proveedores.md` |
| 2 | 6 | Instalar framework AIDLC en la raíz e iniciar Incepción | Completado (2026-09-15): binario 2.9.0, `aidlc config --harness claude --mcp none`, Bedrock retirado, hooks activos, `aidlc doctor` limpio, intent `260915-untangle-app` creado con `/aidlc classic` y el PRD | `.claude/` (engine 2.9.0), `aidlc/spaces/default/`, `docs/specs/prd.md` |
| 2 | 7 | Incepción: requisitos, stories, planning, diseño, units | Completado (2026-09-18): 2.1 Reverse Engineering, 2.2 Practices Discovery, 2.3 Requirements Analysis, 2.4 User Stories y 2.5 Refined Mockups aprobadas (2026-09-16), 2.6 Domain Design y 2.7 Units Generation aprobadas (2026-09-17; prácticas y aprendizajes en `memory/team.md` y `memory/project.md`). Spikes 02, 03 y 04 corridos en `spikes/`; el 01 (voz y grafo) corre antes de construir la voz. Investigación técnica previa a Contract Design (2026-09-17, D-019) con enmiendas de Domain Design y Units Generation. 2.8 Contract Design y 2.9 Delivery Planning aprobadas (2026-09-18). **Incepción cerrada:** las 9 etapas aprobadas y la verificación de frontera Incepción → Construcción en verde. Siguiente: Construcción, unidad por unidad, empezando por U1 `workspace` | `aidlc-docs/inception/*` |
| 3 | 8 | Setup operativo: herramientas fijadas, guion de verificación y flujo de GitHub Actions, sin herramienta externa de tickets (D-020) | **Completado (2026-09-19)**, en el mismo commit que el primer código de aplicación como exige la práctica: `mise.toml` con versiones ancladas y archivo de tareas, `scripts/verify.sh` con sus nueve pasos, y los dos flujos de GitHub Actions (verificación con el escaneo de secretos como primer trabajo, y medición semanal de clon en frío) | `mise.toml`, `scripts/verify.sh`, `.github/workflows/`, `CLAUDE.md` de code gen |
| 3 | 9 | Construcción por Unit (loop) | **En curso**, recorrido `unit-major` y propiedad `solo`. **3 de 22 unidades**: U1 `workspace` terminada (commit `de4d518`), U2 `tenancy` terminada (`f408158`), U3 `pii-redaction` con sus cuatro etapas de diseño cerradas y su código en curso. Siguiente: U4 `case-record`, U5 `provider-platform` y U6 `web-shell`, que es la primera interfaz navegable | código + `aidlc-docs/construction/*` |
| 4 | 10 | Operaciones y demo | Pendiente | despliegue, video demo 3-5 min |

Regla: un paso se marca "Hecho" solo cuando su salida existe en la ruta indicada y Miguel la aprobó.

---

## 2. Decisiones tomadas

| ID | Decisión | Razón |
|---|---|---|
| D-001 | Usar AIDLC **2.9.0**, la versión actual de AWS (binario `aidlc`, `/aidlc` en Claude Code, 5 fases y 33 etapas, perfiles de workflow), y actualizar la guía del equipo a esa versión | Decisión de Miguel el 2026-09-15: la guía (v0.1.5) tiene más de seis meses. La v0.1.5 queda en `docs/aidlc-framework-v0.1.5/` solo como referencia para el mapa de equivalencias. Consecuencias: instalador nativo, quitar Bedrock de `.claude/settings.json` para usar la sesión normal de Claude Code, aprobar hooks, y reescribir la guía capítulo a capítulo a medida que ejecutamos cada fase con 2.9.0 (igual que la original nació de la experiencia de ExpertIA). |
| D-002 | La carpeta `untangle/` es el workspace root de AIDLC y será la raíz del repo git | Lección LL-037 de ExpertIA (guía 01, sección 1.6): engine, `aidlc/` y el código deben vivir en la misma raíz. La landing queda en `site/` dentro del mismo repo. **Confirmado por Miguel (2026-09-15):** `git init` hecho en `untangle/`, rama `main`, primer commit `36d09cd`. |
| D-003 | Toda la pre-incepción se escribe en español; el código, los nombres técnicos y los tokens literales del framework en inglés. **Enmienda (2026-09-15):** los artefactos AIDLC también van en español, por la regla de idioma de conversación del engine y decisión de Miguel; quedó registrada en `aidlc/spaces/default/memory/project.md` (Corrections) | Coherente con el kit (plantillas y prompts en español) y con el público objetivo del portafolio (empleadores internacionales). |
| D-004 | Los documentos de entrada se nombran igual que en el kit: `pre_prb/` con `idea.md`, `critica.md`, `overview.md`, `icp.md`, `mercado.md`, `pvb.md` | Los prompts del kit referencian esos nombres literalmente. |
| D-005 | La landing (`site/`) está fuera del alcance de Incepción. Se declara al framework como "brownfield de marketing, greenfield de aplicación" | Evita que Workspace Detection intente hacer ingeniería inversa de una página estática. |
| D-006 | La carpeta `review/`, el zip de la skill y los raws de la landing no se versionan | Son artefactos de trabajo del loop creativo, no del producto. Entra en `.gitignore` al hacer `git init`. |
| D-007 | Producto de seguro único: **auto**. El camino pulido es FNOL de auto; cotización con elegibilidad es el segundo flujo, delgado | Caso canónico del sector, formularios ACORD públicos, coincide con la demo de la landing. Aprobado por Miguel. |
| D-008 | El deep research (pasos 1 y 2) se ejecuta desde Claude Code con búsqueda web y fuentes citadas | Aprobado por Miguel. |
| D-009 | Voz bilingüe: inglés y español, ambos obligatorios (selección al inicio de la llamada o dos configuraciones) | Empleadores internacionales y mercado hispano. Condiciona la elección de proveedores STT/TTS y los golden sets (uno por idioma). |
| D-010 | Los 12 ajustes de `01-evaluacion-brief.md` son lineamientos aprobados | Aprobado por Miguel. La landing y el brief se alinean al aplicativo, no al revés. |
| D-011 | Costo cero: tier gratuito o self-host en todo; donde no exista opción gratuita, la mejor opción documentada con su costo. Enmendada por D-015 para el LLM | Restricción del autor. Se resuelve en Application Design con una tabla de costos por componente en los ADRs; el deep research levanta el panorama de tiers gratuitos. |
| D-012 | Sin tarifas reales. La cotización produce elegibilidad y, si acaso, un valor indicativo por reglas sintéticas declaradas ficticias | Proyecto demostrativo; evita pricing actuarial y sobreventa. Aclaración de Miguel. |
| D-013 | La landing se realinea al aplicativo cuando la arquitectura quede aprobada (después de Incepción) | La landing fue una base hecha con un tutorial. El aplicativo define la verdad; la landing la refleja. |
| D-014 | Perfil de workflow 2.9.0: `classic` para el intent principal (Incepción y Construcción hasta Build & Test, espejo de la ceremonia v1 que documenta la guía) y un segundo intent `infra` para CI, despliegue y observabilidad | La pre-incepción ya cubre lo que 2.9.0 llama Ideation. Alternativa: `mvp` si se quieren Feasibility y Rough Mockups formales. Se confirma en el paso 6. |
| D-015 | El LLM se paga: **Gemini 2.5 Flash-Lite** en tier de pago (0,10/0,40 USD por millón de tokens de entrada/salida) para voz y trabajo de fondo. **Tope de 5 USD en los 90 días, alerta en 3 USD.** Desarrollo y evals en texto con el tier gratuito de Gemini (proyecto y clave separados). Si un nodo falla en las evals, sube solo ese nodo a 3.1 Flash-Lite (0,25/1,50); Groq como alternativa si la latencia medida lo exige; Claude Haiku 4.5 (1/5) descartado por costo salvo necesidad demostrada | Decisión de Miguel el 2026-09-15: el modelo local es demasiado exigente para el computador; el proyecto es demostrativo y no justifica más gasto. Una llamada de 4 minutos cuesta alrededor de 1 centavo con 2.5 Flash-Lite, así que 5 USD equivalen a unas 400 llamadas. El tier de pago no usa los datos para entrenar. La latencia se mide en el esqueleto (semana 1). |
| D-016 | Voz de la agente: una sola voz femenina paisa (Medellín) para español e inglés, elegida por prueba ciega en la semana 1 entre las voces de Medellín de ElevenLabs, las `es-CO` de Cartesia y, si hay voluntaria con consentimiento, un clon con Chatterbox. Regla: la voz paisa solo en evals de audio, demos y video; la iteración diaria con TTS barato (Kokoro local o voz genérica). Si gana Cartesia: tier gratuito por API, costo cero. Si gana ElevenLabs: Starter 6 USD al mes durante dos meses (unos 12 USD), lo que exige subir el tope de D-015 a unos 20 USD; **pendiente de Miguel** | Decisiones de Miguel (2026-09-15): mujer, paisa, IA declarada en la primera frase, exactamente la misma voz en ambos idiomas, usted cálido. Investigación en `docs/reference/voz-proveedores.md`: ambos proveedores conservan identidad y acento al cambiar de idioma; los tiers gratuitos dan unos 10 a 27 minutos de voz al mes, suficientes para evals y video, no para iterar. |
| D-017 | Repositorio **privado** en GitHub, nombre `untangle`, bajo la cuenta personal **miguelczz** (no issiagent) | Decisión de Miguel (2026-09-15). Es su portafolio; se hace público cuando el README y las evals estén listos. Creado el 2026-09-15: `https://github.com/miguelczz/untangle`, remoto `origin`. Ojo: el gh CLI de la máquina tiene dos cuentas (issiagent y miguelczz); antes de cualquier operación en GitHub verificar que la activa sea miguelczz. |
| D-018 | **El enlace en vivo de la voz es obligatorio** (M21, promovido desde `C5`), con la voz paisa como configuración inicial y arquitectura desacoplada: proveedor, voz y límites viven en configuración, no en código | Decisión de Miguel (2026-09-16): un componente central mostrado solo en video no es evidencia verificable. El tope de 5 USD no era el obstáculo (equivale a unas 400 llamadas; el modelo cuesta ~1 centavo por llamada y la transcripción sale del crédito de Deepgram); el renglón caro es la voz paisa. En vez de decidir de antemano, se arranca con ella y la telemetría de costo por llamada y por proveedor decide después si se bajan límites, se sube el presupuesto o se cambia de voz, sin tocar código. Recogido en el PRD v1.1 (Adenda del Cierre, M21, F3.7, F3.13). Riesgo abierto: transporte de voz en hospedaje gratuito, spike de la semana 1. |
| D-019 | **Investigación técnica antes de Contract Design**: la base se mantiene (monolito modular por componentes, Python con FastAPI, React con TypeScript, LangGraph, PostgreSQL para todo, sin Redis ni Celery) y se rechazan por escrito FalkorDB y GraphRAG, LiteLLM, MCP y A2A en el producto, guardas de ML en el turno, speech-to-speech y multiagente. Cuatro decisiones de Miguel, todas en la opción recomendada: juez propio calibrado con TPR y TNR (sin DeepEval ni el 85 % de acuerdo), el verificador rechaza citas que ignoran un endoso vigente, el sistema se presenta como flujo y no como multiagente, y revelar las instrucciones del sistema deja de bloquear salvo que traiga datos sensibles. `mise` fija las herramientas y reemplaza instalar `uv` y subir pnpm a mano; pnpm pasa a su versión actual (12.x) y Starlette ≥ 1.0.1 | Pedido de Miguel (2026-09-17): no avanzar a Construcción sin estudiar con fuentes arquitectura, patrones, principios, monorepo, contratos y tecnologías de IA, porque cambiarlo después sería costoso. Cuatro investigaciones con más de 300 fuentes fechadas y verificación propia de lo que cambia decisiones. Detalle en `docs/reference/arquitectura-y-tecnologia.md` y sus anexos; enmiendas en ADR-001 a ADR-006, ADR-009 a ADR-015 y ADR-018, y ADR nuevos 019 a 021 |
| D-020 | **No usamos Linear ni ninguna otra herramienta externa de tickets.** El control del trabajo vive en el registro del flujo AIDLC (`unit-of-work.md`, `stories.md`, `aidlc-state.md`) y en este plan; la compuerta y la trazabilidad de cada cambio las da GitHub Actions sobre `main` | Decisión de Miguel (2026-09-18): "no lo usaremos, con el ci de github actions basta". Coherente con las prácticas afirmadas en 2.2 (commit directo a `main`, sin rama corta ni pull request) y con un equipo de una persona: un segundo tablero duplicaría el estado sin añadir información. Consecuencia: el paso 8 pierde el montaje de Linear y la convención de commits `UNT-123`; la trazabilidad historia ↔ commit se apoya en los identificadores del propio registro (`US4.6`, `U12`) escritos en el mensaje del commit |
| D-021 | **Runner propio como reserva de la integración continua**, y apagado antes de hacer público el repositorio | Idea de Miguel del 2026-09-19: en otro proyecto suyo un runner propio releva a GitHub cuando se agotan los minutos gratis, y el servicio nunca para. Se adopta como reserva, no como ejecutor principal. Tres condiciones: se apaga antes de publicar el repositorio (con el repositorio público, un fork puede ejecutar código arbitrario en esa máquina), la máquina tiene que estar despierta, y el trabajo semanal que mide los 15 minutos se queda en los runners de GitHub porque necesita una máquina limpia. |
| D-022 | **La visibilidad final del repositorio vuelve a estar abierta** | El 2026-09-19 Miguel dijo estar considerando seriamente dejarlo privado de forma permanente, compartido por invitación, porque no le ve la gracia a publicarlo. Sustituye la suposición de D-017 de que se publica en la semana 12. Arrastra cuatro consecuencias registradas en OQ5: si queda privado, el escaneo de secretos y la protección de inserción de GitHub nunca estarán disponibles (verificado el 2026-09-19: en un repositorio privado de cuenta personal son producto de pago) y el escaneo propio es el único; la revisión de licencias deja de ser condición de publicación; el escaneo del historial completo pierde su disparador y necesita otro; y el runner propio de D-021 deja de tener que apagarse. |

---

## 3. Preguntas resueltas y abiertas

Resueltas por Miguel el 2026-09-15: framework (D-001), deep research desde aquí (D-008), producto auto (D-007), voz bilingüe (D-009), ajustes aceptados (D-010), costo cero (D-011), sin tarifas (D-012), landing como base a realinear (D-013).

Abiertas, ninguna bloquea el paso 1:

1. **Raíz del repo** (D-002): **resuelta**, `untangle/` es la raíz del repo git desde el 2026-09-15.
2. **Linear**: **resuelta** el 2026-09-18, no se usa (D-020).
3. **Keycloak**: reutilizar la experiencia previa o simplificar (ajuste 10). Se decide como ADR en Application Design.
4. **Cuenta de Drive**: el conector de esta sesión y la carpeta estaban en cuentas personales distintas de Miguel. No hace falta ya; si agregas material nuevo al Drive, compártelo con la cuenta del conector.

---

## 4. Fase 1: Pre-Incepción (pasos 1 a 5)

Objetivo: pasar de la idea al PRD con evidencia, crítica y decisiones explícitas. Todo ocurre en `docs/`. Nada de código.

### Paso 1. Deep research sobre la idea

- Insumo: `00-brief-untangle.md` + `design-package.md` (copy y promesas de la landing) + decisión del producto de seguro (pregunta 4).
- Qué produce: `docs/pre_prb/idea.md`. Informe largo (referencia: 30 KB en Pipe) con fuentes citadas. Cubre: estado del arte de agentes de voz en seguros (FNOL, cotización, suscripción), frameworks (LangGraph vs CrewAI; LiveKit Agents vs Pipecat), proveedores STT/TTS de baja latencia y sus cifras de latencia, observabilidad (Langfuse vs Arize Phoenix), RAG con citación de cláusulas, estándares del sector (ACORD, formularios FNOL), multi-tenant, competidores y proyectos de referencia, qué evalúan los empleadores en un portafolio de agentes.
- Criterio de done: cada afirmación técnica o de mercado tiene fuente; distingue explícitamente "existe hoy" de "aspiración"; termina con una lista de decisiones que el PVB deberá tomar.
- Ejemplo de referencia: `/Users/miguelczz/Proyectos/Pipe/docs/docs/pre_prb/idea.md`.

### Paso 2. Deep research con posición crítica

- Insumo: `idea.md` + brief.
- Qué produce: `docs/pre_prb/critica.md`. Un informe que ataca la idea: riesgos técnicos (latencia real de voz, detección de fin de turno, interrupciones, alucinación de coberturas), riesgos de credibilidad ante alguien del sector, riesgos de sobreventa de cumplimiento, dónde el proyecto puede parecer "otro wrapper", costos, qué partes son commodity en 12 meses.
- Criterio de done: cada crítica viene con severidad y una mitigación posible; no es una lista de elogios.
- Ejemplo: `/Users/miguelczz/Proyectos/Pipe/docs/docs/critica.md`.

### Paso 3. Pre-PRB con plantillas

- Insumo: `idea.md`, `critica.md`, brief, plantillas en `docs/plantillas/`.
- Prompt del kit (adaptado a este proyecto):

  > Dirígete a la carpeta `docs`, usa los archivos de la carpeta `plantillas` y crea los nuevos archivos usando `idea.md` y `critica.md` que se encuentran en la carpeta `pre_prb`; allí mismo crea los nuevos files acorde a lo que indican dichas plantillas.

- Qué produce, en este orden: `overview.md` (análisis profundo), `icp.md` (perfil de cliente ideal; aquí el "cliente" es doble: la aseguradora simulada como tenant y el evaluador técnico como audiencia real del portafolio), `mercado.md` (justificación del proyecto), y por último `pvb.md` (Product Vision Board v1.0, basado en los cuatro anteriores).
- Nota: las plantillas de overview, mercado y pvb son ejemplos completos de otro dominio (AIOps telecom), no plantillas con corchetes. Se toma su estructura de secciones, no su contenido.
- Criterio de done: el PVB tiene las 8 secciones (visión, usuarios, necesidades, producto, valor, diferenciación, contexto estratégico, roadmap 90 días) y el JTBD.
- Ejemplo: `/Users/miguelczz/Proyectos/Pipe/docs/docs/pre_prb/` y `/Users/miguelczz/Proyectos/ISSI HR/issi_pre_inception/docs/pre_prd/`.

### Paso 4. Posición crítica sobre el PVB

- Insumo: `pvb.md` + `docs/ai-product-base.md` (marco "De la idea al Product Vision Board para productos agénticos": paradigma, moats, economía, 4D method, checklist de 5 preguntas incómodas).
- Prompt del kit:

  > Ahora quiero que tomes como referencia el archivo `docs/ai-product-base.md` y lo uses para adoptar una posición crítica sobre el PVB que hemos construido (`docs/pre_prb/pvb.md`). Vamos analizando punto por punto.

- Modo: punto por punto, con pausa para que Miguel responda cada crítica.
- Qué produce: `docs/pre_prb/respuestas_critica_pvb.md` (crítica, pregunta incómoda, respuesta, ajuste propuesto por sección) y `pvb.md` actualizado a v1.1.
- Ejemplo: `/Users/miguelczz/Proyectos/ISSI HR/issi_pre_inception/docs/pre_prd/respuestas_critica_pvb.md`.

### Paso 5. PRD por co-creación

- Insumo: todos los archivos de `docs/pre_prb/` + brief + `design-package.md`.
- Prompt: Prompt 1 de `docs/prompts-especificacion.md` ("Head of Product + AI/Agent Architect"). Empieza por el Paso 0 (análisis de conflictos entre documentos) y luego 13 segmentos, uno a la vez con aprobación.
- Qué produce: `docs/specs/prd.md`. Los 13 segmentos: one-liner y JTBD, contexto y problema, ICP, UVP y matriz 2x2, top 5 casos de uso, principios no negociables, user journeys (incluye escalado a humano), MoSCoW, módulos y features con diagrama, métricas, plan de evaluación del agente, riesgos, plan 30/60/90.
- Criterio de done: los 13 segmentos aprobados y consolidados; el PRD nombra explícitamente datos sintéticos, alcance y lo que no se afirma en cumplimiento.
- Ejemplo: `/Users/miguelczz/Proyectos/ISSI HR/issi/docs/specs/prd/`.

---

## 5. Fase 2: Incepción AIDLC 2.9.0 (pasos 6 y 7)

Fuentes: repo `awslabs/aidlc-workflows` 2.9.0 (`docs/guide/01-getting-started.md`, `03-spaces-and-intents.md`, `04-phases-and-stages.md`, `workflow-profiles.md`, `18-install-and-lifecycle.md`). La guía del equipo (`docs/ai-dlc_guide/01` a `03`) describe la v0.1.5; sirve para el "qué" de cada etapa, no para el "cómo". El mapa de equivalencias está en 5.3.

### Paso 6. Instalar AIDLC 2.9.0 en la raíz e iniciar el intent

6.1 **Instalar el binario** (lo corre Miguel en su terminal; instala un ejecutable nativo, no requiere Bun ni Node):

```bash
curl -fsSL https://github.com/awslabs/aidlc-workflows/releases/latest/download/install.sh | sh
```

```bash
aidlc version
```

6.2 **Configurar el proyecto** desde `untangle/`. Escribe el engine en `.claude/` (hooks, skill `/aidlc`, statusline, `settings.json`) y crea el workspace neutral `aidlc/`. Conserva lo que ya existe en `.claude/skills/`. Sin MCP de AWS (costo cero y no los necesitamos):

```bash
aidlc config --harness claude --mcp none
```

6.3 **Proveedor**: el `settings.json` que escribe AIDLC trae Bedrock por defecto (`CLAUDE_CODE_USE_BEDROCK=1` y modelos `global.anthropic.*`). En el asistente de `aidlc config` elegir proveedor `unchanged`; si aun así quedan las variables, quitarlas de `.claude/settings.json` y de `settings.local.json` para que Claude Code use la sesión normal. Verificar con:

```bash
aidlc doctor
```

6.4 **Hooks**: aprobar los hooks del proyecto en Claude Code (`/hooks`) y reiniciar Claude Code. Repetir `aidlc doctor` hasta que no reporte problemas. **Lo que pasó (2026-09-15):** en la app de escritorio los hooks quedaron activos sin pasar por `/hooks` (el doctor los reporta disparándose en la sesión). El binario quedó en `~/.local/bin`, fuera del PATH de los hooks; se resolvió con un enlace `/opt/homebrew/bin/aidlc -> ~/.local/bin/aidlc` (carpeta del usuario, sin sudo). El asistente de `aidlc config` se evitó con banderas: `aidlc config --harness claude --mcp none --yes`. El `.gitignore` no puede contener la palabra AIDLC fuera del bloque gestionado, o `config` lo reporta como conflicto. Nota: el engine engancha cada llamada a herramienta (PreToolUse, PostToolUse, Stop); el workflow solo corre en una sesión abierta en `untangle/` con esos hooks activos.

6.5 **Git**: `git init` en `untangle/`, `.gitignore` con `review/`, `*.zip`, `site/.vercel/`, `.env*` (el config agrega los cursores `aidlc/active-space` y `active-intent`). Repo en GitHub apuntando a esta carpeta. Se versiona `aidlc/` completo salvo los cursores. **Hecho el 2026-09-15 (adelantado a petición de Miguel):** `git init -b main`, `.gitignore` (además excluye `.claude/skills/10k-websites/` y `.DS_Store`) y primer commit `36d09cd` con 81 archivos. Repo privado creado y `main` subido a `https://github.com/miguelczz/untangle` (D-017).

6.6 **Conocimiento del espacio**: el PRD y el brief se pueden referenciar por ruta directa (Markdown). Si algún insumo es PDF o Word, va en `aidlc/spaces/default/knowledge/documents/` y se indexa con `/aidlc knowledge onboard <ruta>`.

6.7 **Iniciar el intent principal** con el perfil `classic` (D-014) y el PRD como documento de entrada:

```text
/aidlc classic Read ./docs/specs/prd.md and build what it describes. Directrices: site/ es la landing ya publicada y queda fuera del alcance del aplicativo (se realinea al final, D-013); producto único auto con FNOL como camino pulido y cotización delgada; voz bilingüe inglés y español con una sola voz (D-016); datos 100% sintéticos con los tres tenants del Segmento 9; costo cero salvo el LLM de pago con tope de 5 USD (D-015); el orquestador es código, no un agente con prompt; el grafo corre sin voz (chat y evals primero); la guía de voz y tono en docs/pre_prb/voz-y-tono.md es insumo de las stories y de la unit de voz.
```

6.8 **Segundo intent** cuando Construcción cierre: `/aidlc infra ...` para CI, despliegue, observabilidad en producción y la demo publicada.

Checklist antes de 6.7:

- [x] `aidlc doctor` limpio (0 problemas, 2 avisos informativos, 2026-09-15).
- [x] `.claude/settings.json` sin variables de Bedrock (retiradas el 2026-09-15; queda `AWS_AIDLC_DEFAULT_SCOPE=classic`).
- [x] `git remote -v` apunta al repo correcto y `.git/` está en `untangle/` (hecho el 2026-09-15).
- [x] `docs/specs/prd.md` aprobado (paso 5, PRD v1.0 del 2026-09-15).

### Paso 7. Etapas de Incepción en 2.9.0

Con `classic`: Initialization (automática) y las nueve etapas de Inception, una aprobación humana por etapa. Cada etapa produce artefactos en `aidlc/spaces/default/intents/<YYMMDD>-untangle/inception/<etapa>/`.

| Etapa | Qué hace | Nuestra decisión previa |
|---|---|---|
| 0.1 a 0.3 Initialization | Crea el intent, detecta workspace, escribe `aidlc-state.md` y `audit/` | Se detectará brownfield por `site/`; declarar en el prompt que la landing está fuera de alcance |
| 2.1 Reverse Engineering | Solo brownfield; pipeline developer → architect | Pedir que se limite a documentar `site/` como landing estática y no derivar arquitectura de ahí |
| 2.2 Practices Discovery | Descubre prácticas del equipo y las promueve a `memory/team.md` y `project.md` | Cargar aquí los principios del curso: verify antes de done, estado externalizado, reglas MANDATORY con check |
| 2.3 Requirements Analysis | `requirements.md` con preguntas de verificación | Profundidad Standard (la del perfil); pedir Comprehensive si el engine lo permite por la combinación voz + multiagente + multi-tenant |
| 2.4 User Stories | `personas.md`, `stories.md` (mob de product, design, developer, quality) | Personas: asegurado que llama (EN y ES), ajustador humano, admin del tenant, evaluador técnico (audiencia de la demo) |
| 2.5 Refined Mockups | Mockups e interaction spec | Bandeja del ajustador y vista de caso con trazas y cláusulas citadas; el dashboard de observabilidad es el de la herramienta elegida |
| 2.6 Domain Design | `components.md`, `decisions.md` (ADRs) | ADRs esperados: LangGraph vs CrewAI vs otros; LiveKit vs Pipecat; proveedores STT/TTS bilingües; Langfuse vs Phoenix; vector store; multi-tenant (RLS); estado compartido voz/chat; cada uno con tabla de costo cero |
| 2.7 Units Generation | `unit-of-work.md`, DAG de dependencias, story map | Units probables: Core (tenants, auth, estado del caso), Policy RAG, Agents (intake, verificación, decisión, cumplimiento sobre el grafo), Voice layer, Adjuster inbox, Evals y observabilidad |
| 2.8 Contract Design | `contract-summary.md` | Contratos: voz ↔ grafo, agentes ↔ RAG, grafo ↔ bandeja, esquema del caso (ACORD 2) |
| 2.9 Delivery Planning | `bolt-plan.md`, secuencia, riesgos, dependencias externas | Esqueleto andante en texto primero (ajuste 9); voz después |

Validación con usuarios reales (guía 02, 4.5): aquí los "usuarios" son evaluadores técnicos; se puede validar personas y stories con 2-3 personas del sector antes de Construcción.

### 5.3 Mapa de equivalencias v0.1.5 (guía del equipo) → 2.9.0

| v0.1.5 (lo que dice la guía) | 2.9.0 (lo que corre) |
|---|---|
| `core-workflow.md` como `CLAUDE.md` + `.aidlc-rule-details/` | Engine en `.claude/` instalado por `aidlc config`; skill `/aidlc`; reglas del método en `aidlc/spaces/default/memory/` |
| `aidlc-docs/` con `aidlc-state.md` y `audit.md` en la raíz | `aidlc/spaces/default/intents/<YYMMDD>-<label>/` con `aidlc-state.md` y `audit/` por intent |
| Un solo workflow por proyecto | Muchos intents por espacio (`intents.json`, `/aidlc intent list`) |
| Workspace Detection (actividad cero) | 0.1 a 0.3 Initialization, automáticas |
| Requirements Analysis | 2.3 Requirements Analysis |
| User Stories | 2.4 User Stories (mob) |
| Reverse Engineering | 2.1 Reverse Engineering (pipeline de dos pasos) |
| Workflow Planning | Perfil de workflow (`classic`, `mvp`, `feature`...) + 2.9 Delivery Planning |
| Application Design | 2.6 Domain Design + 2.8 Contract Design |
| Units Generation | 2.7 Units Generation |
| No existía | 1.1 a 1.7 Ideation (cubierto por nuestra pre-incepción), 2.2 Practices Discovery, 2.5 Refined Mockups |
| Functional Design, NFR Requirements, NFR Design, Infrastructure Design, Code Generation, Build and Test | 3.1 a 3.6, por Unit, igual |
| No existía | 3.7 CI Pipeline y 4.1 a 4.7 Operation (intent `infra` o `feature`) |
| Preguntas en archivo con `[Answer]:` | Modos de interacción: Guide Me, Edit File, Chat (guía 07 del repo) |
| Extensión de seguridad (15 reglas, capítulo 09) | Agente `aidlc-devsecops-agent` con STRIDE y sensores; revisar equivalencia al llegar |
| Harness propio (capítulo 12, 16 gates) | Hooks y sensores del engine (`aidlc-linter`, `traceability`, `required-sections`...) más lo nuestro en `scripts/` |

La guía del equipo se actualiza capítulo a capítulo al terminar cada fase, registrando lo que realmente pasó con 2.9.0 en Untangle (paso 6a en la tabla de avance cuando se cree).

---

## 6. Fase 3: Construcción (pasos 8 y 9)

Guía: `04-construction-prep.md`, `05-construction-design.md`, `06-construction-units-codegen.md`, `07-pre-codegen-strategy.md`, `08-setup-operativo.md`, `09-security-validation.md`, `10-build-test-cierre.md`.

### Paso 8. Setup operativo (antes de generar código)

Del capítulo 08, adaptado a las prácticas afirmadas en 2.2 Practices Discovery y a D-019 y D-020:
herramientas fijadas con `mise` (Python, uv, Node, pnpm 12.x), primer commit del aplicativo con manifiesto,
lockfile con hashes, formatter, linter y tipos con su alcance declarado y el árbol por módulo bajo `app/`,
guion único `scripts/verify.sh`, flujo de GitHub Actions con el escaneo de secretos como primer trabajo, y el
`CLAUDE.md` de code generation (playbook: qué leer al iniciar, contratos entre módulos, granularidad, compuerta
antes de commit). **No** hay proyecto en Linear, ni ramas por unidad o historia, ni pull request, ni gancho previo
al commit obligatorio: el trabajo entra directo a `main` y la compuerta es GitHub Actions.

Prompt de referencia (imagen del autor, fase construcción):

> Planifica la construcción de este proyecto tomando como referencia la fase 1 de `docs/ai-dlc_guide/01-inception-setup.md`. Prerrequisitos: (1) ruta del PVB `docs/pre_prb/pvb.md`; (2) ya estamos en un folder nuevo, asegura la lección aprendida de la documentación (LL-037); (3) repo de GitHub: `<url>`; (4) vamos a crear este proyecto en Linear para llevar el control.

Nota: el punto (4) del prompt de referencia no aplica en Untangle; el control del trabajo vive en el registro del flujo (D-020).

### Paso 9. Loop por Unit

Por cada Unit, en orden de dependencias: Functional Design, NFR Requirements, NFR Design, Infrastructure Design, Code Generation, Build and Test. Checkpoints de seguridad entre Units (capítulo 09). Cierre formal con Build & Test, auditoría de compliance y aprobación (capítulo 10).

### Orden de construcción de las unidades restantes (decisión del 2026-09-21)

**Por qué se decide ahora.** El plan Max de Claude vence y el trabajo continúa en
Pro, con aproximadamente una quinta parte de capacidad. Medido sobre la sesión
del 2026-09-20: cerrar U3, correr las cuatro etapas de diseño de U4 y construir
tres de sus nueve bloques de código consumió el 26 % del límite semanal en unas
ocho horas, y una sola investigación en abanico —ya desactivada— fue 7,17
millones de tokens de ese total. A ese ritmo, terminar las 22 unidades no cabe
en el calendario. El orden deja de ser una preferencia y pasa a ser la decisión
que determina qué queda construido si hay que parar.

**Criterio de Miguel:** terminar U4, seguir con U5 y U6 para tener **algo visual
y funcional**, y después las unidades más pesadas en orden descendente.

**Cómo se ordenó.** El criterio de "más pesadas primero" no se puede aplicar
solo: las dependencias mandan, y una unidad pesada que no tiene sus insumos no
se puede construir. El orden es por tanto **topológico primero y por peso
después**, con tres ajustes cuya razón se escribe abajo. Se validó con el grafo
de `unit-of-work.md`: ninguna unidad corre antes que sus dependencias.

| # | Unidad | Comp. | Por qué en ese sitio |
| --- | --- | --- | --- |
| 1 | U4 `case-record` | L | En construcción. De ella cuelgan nueve unidades |
| 2 | U5 `provider-platform` | L | Es L, no pequeña. Pero U6 depende de ella, así que no se puede saltar para llegar antes a lo visual |
| 3 | U15 `speech-providers` | M | Ajuste 4 del 2026-09-21: adelantada por decisión de Miguel. Solo le falta U5, y es lo máximo de voz alcanzable antes de que venza Max (ver abajo) |
| 4 | U6 `web-shell` | L | **El componente visual.** Lleva además la pantalla de diagnóstico (ver abajo) |
| 5 | U7 `synthetic-data` | L | Sin corpus no hay nada que mostrar ni que evaluar |
| 6 | U9 `rules-decision` | M | Ajuste 1: adelantada pese a ser M porque desbloquea cinco unidades, más que cualquier L disponible |
| 7 | U21 `eval-gates` | L | Ajuste 2: adelantada. Solo necesita U1, U3, U5, U7 y U9, y es una de las dos piezas que más muestran madurez de ingeniería |
| 8 | U22 `public-evidence` | M | Ajuste 3: adelantada. Es el README y los paneles, o sea **la cara que lee quien evalúa el repositorio**. Dejarla al final significaba quedarse sin cara pública si había que parar |
| 9 | U8 `policy-rag` | XL | La pieza técnica que más distingue: citas verificadas con compuerta dura |
| 10 | U10 `compliance` | L | Los controles del turno y el cierre |
| 11 | U11 `intake` | L | La extracción con estado y evidencia |
| 12 | U12 `graph-runtime` | L | El grafo que une los nodos |
| 13 | U13 `chat` | XL | El chat público sobre el grafo |
| 14 | U14 `inbox` | XL | La bandeja: la decisión la firma una persona |
| 15 | U20 `demo-operations` | M | El reinicio nocturno y la siembra |
| 16 | U19 `quote` | M | Flujo delgado, clasificado `Should` |
| 17 | U16 `voice-call` | XL | Bloque de voz: candidato a corte |
| 18 | U18 `voice-spanish` | L | Bloque de voz: candidato a corte |
| 19 | U17 `voice-public-link` | M | Bloque de voz: candidato a corte |

**El punto de publicación temprana.** Con los ocho primeros terminados, el
repositorio ya se puede enseñar: una aplicación web navegable, con datos
sintéticos regenerables, reglas versionadas, compuertas de evaluación que
publican números medidos y un README que dice exactamente qué hay y qué no. Ese
es el corte natural si la capacidad se agota.

**La pantalla de diagnóstico de U6.** U6 por sí sola es la base visual —sistema
de diseño, temas, rutas, páginas de estado— y no hace nada del producto. Para
que el componente visual sea además **funcional**, U6 incorpora una pantalla de
diagnóstico interna que ejercita con datos reales lo ya construido: crear un
caso y ver su completitud y sus transiciones, probar la redacción sobre un
texto, y comprobar el aislamiento entre aseguradoras. Resuelve con un sí la
pregunta que estaba anotada como pendiente para U6 desde el diseño de U3.

**El bloque de voz queda como candidato a corte, no cortado.** Son cuatro
unidades (U15 a U18), las más caras del resto, y el PRD ya las tenía en su orden
de corte con el tope de gasto de D-015 apretándolas. La decisión de cortarlas es
de Miguel y **no está tomada**: hasta que lo esté, siguen en el orden.

**Ajuste 4 (2026-09-21): U15 `speech-providers` se adelanta al puesto 3.** Miguel
pidió alcanzar a tener el componente de voz antes de que venza el plan Max. El
mapa de dependencias dice lo que eso cuesta de verdad, y la cifra decidió:

| Qué se quiere | Qué hace falta antes |
| --- | --- |
| U15 `speech-providers`: los adaptadores de transcripción y síntesis | Solo U5. Tamaño M |
| U16 `voice-call`: una llamada que alguien pueda usar en el navegador | Nueve unidades (U5, U6, U7, U8, U9, U10, U11, U12 y U15), dos de ellas del tamaño más grande, y U16 es otra XL |

Una llamada funcional antes de que venza Max no la sostienen los números: U4
sola, que es una L, ocupó buena parte de una sesión. Lo que sí se alcanza es
U15, que deja el código de voz existente y probado —proveedores elegidos,
contrato de streaming, conducta ante un corte— mientras todavía hay capacidad
para revisar esas decisiones. Desplaza el punto de publicación en una unidad M y
no toca nada más del orden. Decisión de Miguel del 2026-09-21.

**Recorte de proceso, con evidencia.** El revisor cuesta unos 190 mil tokens por
pasada y corre en cinco etapas por unidad. En U4 encontró dos defectos reales en
diseño funcional y, en las otras tres etapas, esencialmente recuentos mal
escritos, que `scripts/check-artifacts.py` puede detectar si se le enseña ese
caso. A partir de U5 el revisor corre en **diseño funcional y generación de
código**, y las tres etapas intermedias se apoyan en el comprobador.

### Disciplina del curso de orquestación aplicada aquí

Del curso "Orquestación de Trabajo para Ingeniería Agéntica" (`/Users/miguelczz/Estudio/Orquestación Agéntica/Curso/`), los cinco principios que gobiernan la construcción:

1. **Externalizar contexto**: `aidlc-state.md`, `audit.md` y este plan son la memoria; nada vive solo en el chat. Al cerrar sesión se actualiza el estado.
2. **Descomponer trabajo**: las Units y las stories son la unidad de trabajo, y su estado vive en el registro del flujo (`unit-of-work.md`, `stories.md`, `aidlc-state.md`) y en este plan, sin herramienta externa de tickets (D-020).
3. **Especializar**: sub-agentes y skills por Unit cuando se repita un flujo tres veces (capítulo 13; evitar "skill explosion").
4. **Verificación = generación**: un `scripts/verify.sh` (tests, typecheck, lint, build) obligatorio antes de declarar done; regla MANDATORY en el `CLAUDE.md` de code gen.
5. **Legibilidad del repo**: README que asume cero contexto, `docs/conventions.md`, estructura predecible.

Jerarquía de prevención (guía 00): ADR (documenta) < lección aprendida (diagnostica) < regla MANDATORY + check en harness (previene). Cuando un error se repita tres veces, se convierte en regla con check.

---

## 7. Fase 4: Operaciones y demo (paso 10)

Guía: `11-operations.md`, `12-harness-engineering.md`, `13-skills-agents.md`. Entregable final del brief: video o demo en vivo de 3 a 5 minutos (llamada de voz completa, dashboard de observabilidad, cláusula citada), README con arquitectura y diagrama de agentes, declaración explícita de datos sintéticos y alcance. La landing ya apunta a esa demo ("See it run").

---

## 8. Mapa de recursos

| Recurso | Ruta | Uso |
|---|---|---|
| Brief del autor | `docs/00-brief-untangle.md` | Insumo raíz |
| Diseño y copy de la landing | `design-package.md` | Promesas públicas del producto |
| Plantillas pre-PRB | `docs/plantillas/` | Paso 3 |
| Marco de crítica de productos agénticos | `docs/ai-product-base.md` | Paso 4 |
| Prompt de PRD | `docs/prompts-especificacion.md` | Paso 5 |
| Guía paso a paso del equipo (14 archivos) | `docs/ai-dlc_guide/` | Fases 2 a 4 |
| Guía de harness, skills y agentes | `docs/ai-dlc_guide/GUIA_HARNESS_SKILLS_AGENTES.md` | Fase 3 y 4 |
| Framework AIDLC v0.1.5 (AWS) | `docs/aidlc-framework-v0.1.5/` | Paso 6 |
| Repo AWS actual (2.9.0), clon de lectura | scratchpad de la sesión, `github.com/awslabs/aidlc-workflows` | Referencia de la evolución del framework |
| Ejemplo completo Pipe | `/Users/miguelczz/Proyectos/Pipe/docs/docs/` | Pre-PRB de referencia |
| Ejemplo completo ISSI HR | `/Users/miguelczz/Proyectos/ISSI HR/issi_pre_inception/docs/` y `/Users/miguelczz/Proyectos/ISSI HR/issi/docs/` | Respuestas a la crítica y PRD de referencia |
| Curso de orquestación agéntica | `/Users/miguelczz/Estudio/Orquestación Agéntica/Curso/` | Disciplina de construcción |
| Kit original en Drive | `Agentify IAOps Documentos` (carpeta compartida) | Origen; ya copiado |

---

## 9. Glosario mínimo

- **AIDLC**: AI-Driven Development Life Cycle, metodología de AWS en tres fases (Incepción, Construcción, Operaciones).
- **PVB**: Product Vision Board, visión de producto en una página (visión, usuarios, necesidades, producto, valor).
- **Pre-PRB**: carpeta con los documentos previos al PVB (idea, crítica, overview, ICP, mercado). El nombre viene del kit.
- **PRD**: Product Requirements Document, especificación funcional y de producto.
- **ICP**: Ideal Customer Profile, perfil del cliente ideal.
- **JTBD**: Jobs To Be Done, "cuando [situación], quiero [motivación], para [resultado]".
- **HITL**: Human In The Loop, una persona en cada decisión que importa.
- **ADR**: Architecture Decision Record, registro de una decisión de arquitectura con opciones y consecuencias.
- **Unit**: unidad de trabajo de AIDLC, equivalente a un bounded context de DDD.
- **FNOL**: First Notice of Loss, primer aviso de siniestro.
- **ACORD**: estándar de formularios y datos de la industria aseguradora.
- **RAG**: Retrieval-Augmented Generation, el agente responde citando documentos recuperados.
- **STT / TTS**: voz a texto y texto a voz.

---

## 10. Registro de sesiones

| Fecha | Sesión | Qué pasó |
|---|---|---|
| 2026-09-15 | 1 (Claude Code) | Se leyó el curso, el Drive (vía Chrome del autor y conector), el repo AWS (2.9.0 y tag v0.1.5), y los ejemplos locales Pipe e ISSI HR. Se copió el kit a `docs/`. Se escribió este plan y la evaluación del brief. Miguel aprobó los ajustes y resolvió las preguntas (D-007 a D-014); se cambió D-001 a 2.9.0 y se reescribió el paso 6. Se ejecutaron los pasos 1 (`idea.md`, 71 fuentes), 2 (`critica.md`, 16 críticas) y 3 (`overview`, `icp`, `mercado`, `pvb` v1.0). Se dejó `docs/reference/estructura-poliza-iso-pap.md` para el corpus. Miguel decidió pagar un LLM barato (D-015: Gemini 2.5 Flash-Lite, tope 5 USD, alerta 3) y aceptó los 9 puntos de la crítica; se produjo el PVB v1.1 con el mapa de 15 componentes demostrables. Siguiente: paso 5, PRD. |
| 2026-09-15 | 2 (Claude Code) | PRD: segmentos 1 a 8 aprobados; guía de voz y tono e investigación de proveedores (D-016); segmento 9 redactado con los tenants ficticios Stonecroft Mutual, Sunmeadow Auto y Knotwell Insurance Agency (nombres verificados) y jurisdicción Estado de Corvane. Miguel pidió commit y push: se inicializó el repo en `untangle/` (D-002 confirmado), primer commit `36d09cd`; Miguel inició sesión en gh como miguelczz y se creó el repo privado `miguelczz/untangle` con `main` subido (D-017). Siguiente: aprobación del segmento 9, segmento 10. |
| 2026-09-15 | 3 (Claude Code) | Segmentos 9 a 13 del PRD aprobados uno a uno (módulos y tenants ficticios; métricas; plan de evaluación; riesgos y FTCEM; plan 30/60/90 con fechas desde el 2026-09-16). PRD consolidado como v1.0 con índice y cierre. Siguiente: paso 6, instalar AIDLC 2.9.0 en la raíz e iniciar `/aidlc classic` con el PRD. |
| 2026-09-15 | 4 (Claude Code) | Paso 6: Miguel instaló el binario 2.9.0; se configuró el harness Claude sin MCP, se retiró Bedrock, se enlazó `aidlc` en `/opt/homebrew/bin`, `aidlc doctor` limpio; engine (`.claude/`) y workspace (`aidlc/spaces/default`) en el repo (commit `a2f2e36`). Siguiente: 6.7, iniciar `/aidlc classic` con el PRD. |
| 2026-09-15 | 5 (Claude Code) | Paso 6.7: `/aidlc classic` con el PRD creó el intent `260915-untangle-app` (18 etapas, profundidad Standard). Etapa 2.1 Reverse Engineering: el desarrollador escaneó el repo (no hay código de aplicación; `site/` es la landing) y el arquitecto publicó los nueve documentos del code knowledge base; dos aprendizajes guardados en `project.md` (alcance de escaneos; artefactos AIDLC en español). Miguel aprobó la etapa. Flujo detenido antes de 2.2 Practices Discovery porque Miguel cambia a Opus por el límite semanal de Fable; se retoma con `/aidlc --resume` en una sesión abierta en `untangle/`. Trampas vistas: `learnings surface` falla si falta `runtime-graph.json` (arreglo: `aidlc engine runtime compile`); una respuesta en `Other` a una pregunta del flujo se relee y se re-presenta. |
| 2026-09-16 | 6 (Claude Code, Opus 5) | Etapa 2.2 Practices Discovery: borrador del lead, tres revisiones ciegas (calidad, desarrollo, seguridad) y entrevista de ocho preguntas con Miguel. Prácticas afirmadas y promovidas: commit directo a `main` con GitHub Actions como compuerta; base sólida y después un componente completo a la vez; caso de evaluación antes del comportamiento que mide y pruebas unitarias junto a su capa; 80% agregado con piso en piezas críticas; chat, bandeja y enlace de voz en vivo con límites duros; obligación de tooling sin nombrar herramienta hasta el ADR de lenguaje; regresión contada por casos en conjuntos pequeños. Tres aprendizajes guardados en `project.md`. Tras la etapa, Miguel decidió D-018 (enlace de voz obligatorio con arquitectura desacoplada) y se produjo el PRD v1.1. Siguiente: 2.3 Requirements Analysis. |
| 2026-09-16 | 7 (Claude Code, Opus 5) | Etapa 2.3 Requirements Analysis: 84 requisitos funcionales en 14 grupos, 21 no funcionales con umbral y forma de medirlos, 9 restricciones, 6 supuestos y 6 preguntas abiertas. La entrevista fijó el enlace de voz: llamadas de 3 minutos, 15 al día en todo el sitio, voz de respaldo gratuita al agotarse el presupuesto de la voz paisa, techo de 5 USD con revisión el día 30, sin audio persistido y enlace firmado de una hora para decidir el propio caso. Revisión advisory NOT-READY con tres hallazgos aprobados como riesgo aceptado y resueltos en 2.4. Un aprendizaje en `project.md`. Siguiente: 2.4 User Stories. |
| 2026-09-16 | 8 (Claude Code, Opus 5) | Etapa 2.4 User Stories en modo mob (diseño, desarrollo y calidad) con diez preguntas a Miguel, todas en la opción recomendada. Resultado: seis perfiles ficticios, 87 historias (81 Must, 6 Should) con 417 criterios en Dado / Cuando / Entonces, 25 decisiones que resuelven contradicciones entre PRD, requisitos y prácticas (13 con visto bueno de Miguel), matriz de los 15 escenarios de red-team y trazabilidad completa (NFR18 diferido a `nfr-requirements`). La primera revisión salió READY con tres hallazgos menores; Miguel pidió además una revisión de lógica de negocio, de la que salieron cinco cambios: todo ocurre dentro del aplicativo, la voz no promete otra llamada, la consola deja pasar un caso incompleto a un ajustador, el cierre directo tiene frase fija y la voz de respaldo se decide antes de cada llamada. La segunda revisión salió READY sin hallazgos. Once aprendizajes en `project.md`. En paralelo se prepararon los spikes de la semana 1 en `spikes/` (Flash-Lite, transcripción en español, voces paisas y plan del grafo de voz). Riesgos anotados para Delivery Planning: volumen de 81 historias Must frente a 90 días, y costo de un plan de pago para la voz paisa frente al techo. Siguiente: 2.5 Refined Mockups. |
| 2026-09-16 | 9 (Claude Code, Opus 5) | Etapa 2.5 Refined Mockups en modo guiado con nueve preguntas. Resultado: sistema de diseño con tokens propios y contraste medido, doce pantallas (M1 a M12) en escritorio y teléfono con sus estados, especificación de interacción con nueve recorridos, lista de accesibilidad y una maqueta navegable en HTML publicada como página privada y copiada en `refined-mockups/maqueta/`. A pedido de Miguel se borró la regla que impedía usar la landing como insumo, se instalaron cuatro skills de diseño solo en Markdown y se decidió reemplazar el concepto del nudo de la landing por uno literal del mundo de seguros (trabajo aparte). La primera revisión salió READY con R-01 (la apertura decía que la llamada se graba y el audio no se guarda) y R-02 (retomar por chat un caso de voz). En la aprobación Miguel pidió modos claro y oscuro completos con selector, una revisión de uso para alguien sin contexto (veinte correcciones) y la apertura "queda transcrita" (D26 en `stories.md`). La segunda revisión salió READY sin hallazgos nuevos. Seis aprendizajes en `project.md`, entre ellos los modos de tema y la política de cero renovaciones en cuentas de proveedores. En paralelo: configuración de claves (formato AQ. de Google, clave restringida de ElevenLabs), scripts que se detienen cuando se acaba una cuota, y resultado del spike 02: `gemini-2.5-flash-lite` está cerrado a cuentas nuevas, así que D-015 cambia en Domain Design. Con la instrucción de extracción aclarada, la cuarta corrida del spike 02 dio 100 % de campos y cero valores inventados con 3.1 y 3.5 (sobre los mismos casos, no es medición independiente); ninguno cumple el tiempo del turno en el plan gratuito, y con prompts del tamaño que supuso D-015 los dos pasarían la meta de costo NFR14. Spike 04: el plan gratuito de ElevenLabs no deja usar sus voces paisas por API (402, sin cobro); se sintetizaron las dos voces `es-CO` de Cartesia y hay una página de escucha a ciegas. Escucha con una persona (Miguel): Catalina (Cartesia) pasa la regla y, en una segunda escucha con un audio de control, conserva su identidad en inglés. Spike 03 con la voz de Miguel: en español, 5,6 % de error por palabra con `nova-3:multi` y 8,6 % con `nova-3:es`, sin disparar R4, y los datos dictados llegaron exactos (8 de 8); pero hubo errores que cambian el sentido (una negación sobre lesiones, quién manejaba), así que esos campos se confirman en voz alta. Siguiente: 2.6 Domain Design con los resultados de los spikes 02, 03 y 04. |
| 2026-09-17 | 9 (Claude Code, Opus 5) | Etapa 2.6 Domain Design en modo guiado con cinco preguntas, una de seguimiento. Resultado: `components.md` con 23 componentes en seis capas (86 dependencias sin ciclos, 39 entidades con un solo dueño, los cuatro nodos como componentes propios), `decisions.md` con 18 ADR y `traceability.json` con las 87 historias (85 con componente, video y landing N/A). Decisiones de Miguel: pólizas en el idioma de cada aseguradora (PA-1); un caso derivado por el límite de tres minutos vuelve a captura si se retoma a tiempo (PA-5); pantallas en React con TypeScript y Vite servidas desde el mismo origen, tras investigar con sus criterios de buenas prácticas y de lo que ve quien evalúa; la librería de voz se decide con el spike 01 antes de construir la voz; y el chat público en el plan gratuito de Gemini con aviso de no escribir datos reales, como riesgo aceptado (ADR-006), en lugar del plan de pago recomendado. Enmienda de D-015: `gemini-3.1-flash-lite`. Proveedores: Deepgram `nova-3` en `multi`, Catalina de Cartesia provisional hasta la escucha de la semana 9, voz de respaldo por elegir en el spike 01. Stack: Python 3.13 con FastAPI, uv, Ruff y mypy; TypeScript con Node 24, pnpm, React, Vite, TanStack y shadcn/ui; LangGraph y PostgreSQL con pgvector. Revisión de arquitectura READY con dos observaciones menores aceptadas (R-01, dependencias de DemoOperations e Inbox, pasa a Units Generation). Cinco aprendizajes en `project.md`. Siguiente: 2.7 Units Generation. |
| 2026-09-17 | 10 (Claude Code, Opus 5) | Etapa 2.7 Units Generation en modo guiado con dos preguntas (tamaño de las unidades y lugar de las pantallas), ambas en la opción recomendada, y aprobación del plan antes de generar. Resultado: 22 unidades por capacidad (4 `service`, 10 `library`, 1 `ui`, 7 sin tipo), mapa de dependencias sin ciclos con 90 aristas y raíz única en U1 `workspace`, 85 historias asignadas y 2 N/A (video y landing), 16 unidades evaluadas y 6 deterministas, tabla de NFR1 a NFR21 por unidad, 39 entidades por unidad y árbol del código bajo `app/`. Vistos buenos de Miguel: reinicio nocturno por contrato de borrado que implementa cada dueño (resuelve R-01 de Domain Design) y evaluación en tres unidades con conductores registrados por los canales. Primera revisión READY con dos hallazgos menores; en la compuerta Miguel pidió una revisión detallada, que encontró además el límite de voz por conexión mal copiado, metas de evaluación sin documento en `nfr-requirements` y entidades de evaluación sin dueño por unidad; se corrigió todo y la segunda revisión salió READY sin hallazgos. Ocho aprendizajes en `project.md`, incluidas las tres correcciones de PA-13 (techo acumulado de 90 días, ninguna credencial publicada y tres controles baratos dentro del turno). Para empezar Construcción faltan 2.8 Contract Design, 2.9 Delivery Planning, instalar `uv`, subir pnpm a la versión 10, claves de Gemini por uso y actualizar el paso 8 del plan a las prácticas afirmadas (commits directos a `main`, sin pre-commit obligatorio; confirmar si se usa Linear). |
| 2026-09-17 | 11 (Claude Code, Opus 5) | Antes de arrancar 2.8 Contract Design, Miguel pidió investigar cómo se construye el aplicativo: si LangGraph es lo correcto y la latencia de pasar por varios nodos, tools, MCP, skills, harness, FalkorDB, RAG, LiteLLM, seguridad, multiagente, multimodal, jueces, Redis, Celery, Playwright, estilo de arquitectura, patrones, grafos, SOLID/DRY/YAGNI, monorepo y contratos. Cuatro investigaciones en paralelo (más de 300 fuentes fechadas) y verificación propia de las afirmaciones que cambian decisiones: CVE-2026-48710 de Starlette, versiones maliciosas de LiteLLM, límites de Gemini por proyecto, OWASP LLM 2026, LLM Guard archivado, dependencias de DeepEval y pnpm 12. Resultado en `docs/reference/arquitectura-y-tecnologia.md` con cuatro anexos. Hallazgos que se corrigieron antes de Construcción: la bandeja rompía la regla de capas, un nodo escribía en la base de datos aunque LangGraph lo vuelve a ejecutar al reanudar, el checkpointer en autocommit no queda cubierto por la aseguradora fijada por transacción, las pruebas de aislamiento con superusuario pasarían sin aislamiento, Gemini limita por proyecto y la guardia de salida llegaba tarde con streaming. Cuatro decisiones de Miguel, todas en la recomendada (D-019). Enmiendas en `decisions.md` (catorce ADR y tres nuevos), `components.md` (83 dependencias), `unit-of-work.md` (UG-4, UG-10, U1, U7, U8, U21), `stories.md` (US2.2, US4.6, US4.15), `requirements.md` (FR5.4), PRD (adenda v1.2), `team.md` y `project.md` (regla del juez). Prerrequisitos de Construcción actualizados: instalar `mise`, que fija Python, uv, Node y pnpm. A pedido de Miguel, revisión independiente de las enmiendas antes de Contract Design: cinco hallazgos (textos originales de ADR-001, ADR-002 y ADR-003 que contradecían su enmienda, la nota de PA-3 en U12 y las entidades `InboxEvent` y `ClauseRelation` que faltaban en el catálogo, que pasa a 41 entidades), corregidos y verificados sin hallazgos nuevos; sensores y los 8 diagramas de los documentos cambiados en verde. Siguiente: 2.8 Contract Design. |
| 2026-09-18 | 12 (Claude Code, Opus 5) | Cierre de los pendientes previos a 2.8 Contract Design: se verificó que las cinco correcciones de la revisión independiente quedaron aplicadas (commit `c91794f`), con sensores, los ocho diagramas y `aidlc doctor` en verde, y se explicó que el aviso de etapas modificadas es esperado por las enmiendas de D-019 y no bloquea con el control de cambios `relaxed`. Miguel resolvió la última pregunta abierta del plan: no se usa Linear ni ninguna otra herramienta externa de tickets, basta la integración continua de GitHub Actions (D-020); el paso 8 se reescribió a las prácticas afirmadas (herramientas fijadas con `mise`, primer commit con andamiaje completo, `scripts/verify.sh`, flujo de GitHub Actions con el escaneo de secretos primero, sin ramas por historia ni pull request ni gancho previo al commit). Siguiente: 2.8 Contract Design. |
| 2026-09-18 | 13 (Claude Code, Opus 5) | Etapa 2.8 Contract Design en modo guiado con siete preguntas. Resultado: `contract-summary.md` con 30 contratos en cuatro familias (9 de la API HTTP y sus streams, 15 de las fronteras dentro del proceso, 4 de archivos versionados y 1 pendiente del experimento 1), cada uno con lo que cruza, el mecanismo, su dueño y qué pasa cuando falla; 31 bloques de especificación validados (OpenAPI, `Protocol` de Python, YAML y JSON), 8 reglas de propiedad y 10 preguntas abiertas atadas a la unidad que bloquean. Decisiones de Miguel: errores en `problem+json` (RFC 9457), modelos propios de solo lectura entre módulos, YAML para lo que escribe una persona y JSON para lo que escribe una máquina, cookie `HttpOnly` para los tres tipos de credencial, clave de idempotencia del cliente en las tres escrituras que importan, y un flujo de eventos tipados entre canal y grafo. Después de la primera revisión Miguel quitó el prefijo de versión: la API queda en `/api`, con solo cambios aditivos y el disparador de versionar cuando aparezca un consumidor fuera del repositorio. Primera revisión NOT-READY con cuatro hallazgos, todos corregidos: la captura faltaba como consumidor del motor de reglas (se añadió con una función que declara qué campos leen las reglas), el punto de integración de migraciones no tenía contrato (se añadió C-30 con la regla de que la revisión que crea una tabla trae su aislamiento en la misma revisión), los puertos de proveedor nombraban la unidad equivocada, y la regla de propiedad se contradecía con siete contratos de dueño compartido. Segunda revisión READY sin hallazgos nuevos. Cinco aprendizajes en `project.md`. Commit `f227c64`. Siguiente: 2.9 Delivery Planning. |
| 2026-09-18 | 14 (Claude Code, Opus 5) | Etapa 2.9 Delivery Planning en modo guiado con cinco preguntas, y con ella **Incepción cerrada**. Resultado: 22 Bolts, uno por unidad de trabajo, en el orden por capas del PRD y dentro de las 90 aristas del mapa, cada uno con su semana, su criterio de terminado, qué prueba y qué se puede enseñar; calendario de 12 semanas con las tres compuertas del PRD; seis riesgos con su señal temprana; cinco dependencias bloqueantes, ocho con fecha y tres del intent `infra`, cada una con su plan B; y la verificación de frontera Incepción → Construcción con veredicto PASA. Decisiones de Miguel: orden por capas, el experimento de voz corre en la semana 2 en paralelo con los primeros Bolts, se mantiene la fecha del día 30 con la regla de corte como válvula, una sola sesión construye unidad por unidad con su aprobación en cada etapa, y las tres preocupaciones a atender temprano son la voz, la calidad de las respuestas y el costo. El plan dice el ritmo sin adornos: los Bolts 1 a 17 exigen unas cinco unidades por semana frente a las dos y media del resto, y la señal que dispara la regla de corte es el Bolt 11 terminado al cerrar la semana 3. Corrección hecha ante Miguel antes de generar: S2 y S5 son historias dentro del Bolt del chat, no unidades enteras; el primer Bolt que la regla de corte elimina es la cotización. Se registró el recorrido de Construcción como `unit-major` y la propiedad como `solo`. Dos aprendizajes en `project.md`. Commit `937a680`. Siguiente: Construcción 3.1 Functional Design de U1 `workspace`. |
| 2026-09-19 | 15 (Claude Code, Opus 5) | Construcción de U1 `workspace`, las cuatro etapas de diseño: 3.1 diseño funcional (6 entidades, 21 reglas, 3 flujos), 3.2 requisitos no funcionales (NFR18 como número ponderado, NFR21 con presupuesto por paso), 3.3 diseño no funcional (6 documentos; la revisión encontró que la taxonomía de errores del proveedor y las causas de "no medido" eran dos vocabularios sin traducción, y al escribirla apareció que una respuesta ilegible es un fallo de calidad y no un caso no medido) y 3.4 infraestructura (sin despliegue: entorno local con Docker, tubería de dos trabajos, imágenes ancladas por huella, `main` en rojo se revierte a los 30 minutos, aviso por las notificaciones de GitHub). Verificado contra el archivo: el `.gitignore` ya exceptúa `.env.example`, que los requisitos daban como pendiente. Después, a pedido de Miguel, **revisión estricta de lógica de todo el proyecto** (requisitos, 87 historias, 23 componentes, 21 ADR, 22 unidades con sus aristas, contratos y plan de Bolts). La parte mecánica salió limpia; aparecieron seis problemas de lógica, todos corregidos en esta sesión: (1) la meta de los 15 minutos no la podía ejecutar quien clona sin cuenta de proveedor, así que el subconjunto de arranque pasa a ser solo de casos que no llaman a un modelo, con causa nueva `provider_key_missing` y BR1.2 enmendada; (2) la arista U11 `intake` → U9 `rules-decision` era falsa y contradecía el catálogo de componentes, la regla del turno y UG-8, así que se retiró (89 aristas) y las dos historias pasan a verificación de punta a punta; (3) el cupo diario de la voz pasa a derivarse del presupuesto restante, con reserva para el video, porque el corte proyectado al día 67 dejaba la voz apagada antes del video final y de la publicación (FR3.9 enmendada, FR3.11 nueva); (4) B12 prometía una línea base v0 que no podía producir sin conductor de canal, así que se mueve al cierre de B14 (DP-10); (5) el README narrativo no tenía dueño ni definición de terminado, y pasa a ser trabajo nombrado en la semana 11 por decisión de Miguel de no escribir documentos que después toca actualizar (DP-9); (6) la vista por enlace firmado declara que muestra la vista del ajustador como recurso de demostración, para que no se lea como un fallo de control de acceso (FR8.9 nueva). Dos decisiones nuevas: D-021 runner propio como reserva y D-022 visibilidad del repositorio otra vez abierta. Siguiente: Construcción 3.5 Code Generation de U1, que necesita `mise` instalado. |
| 2026-09-20 | 16 (Claude Code, Opus 5) | **U1 terminada, U2 terminada y U3 diseñada.** U1 `workspace` cerró su generación de código (26 pasos; 68 pruebas, los nueve pasos del guion en verde) y después apareció SEC-U1.4: dos ajustes de seguridad de pnpm estaban escritos en un archivo que el gestor no leía, así que el control no existía; se movieron a donde sí se leen y entró un chequeo que le **pregunta a cada gestor** qué valor tiene de verdad (`de4d518`). U2 `tenancy` completa: las dos tablas nacen con su aislamiento habilitado, forzado y su política escritos literales en la misma revisión; rol del aplicativo sin privilegio de salto creado por el mismo guion que monta el entorno local y la base efímera; credencial de bandeja de doce horas y enlace de caso de una hora con dos claves separadas por uso; y tres chequeos nuevos que interrogan al catálogo vivo en vez de leer el archivo donde se escribió la intención. Medido: 142 pruebas, 86,43 % de cobertura agregada, 92,30 % en `tenancy`, nueve pasos en verde en 19,3 s (`f408158`). Al construirla aparecieron **dos defectos de U1 que solo U2 podía destapar**: el runner de pruebas corría en modo síncrono —ninguna prueba `async` habría funcionado— y la cobertura medía con los archivos de prueba dentro, así que **la cifra que U1 publicó (90,05 %) no era la real: era 85,83 %**, medida volviendo a su commit con la puerta del proyecto. El piso se cumplía de las dos formas; lo que falló fue el número publicado. `main` se puso en rojo una vez, por el escaneo de secretos marcando resúmenes sintéticos de la fixture de aislamiento: ninguna clave real, nada que rotar, y el arreglo dejó una excepción acotada al archivo y a sus dos campos, comprobada plantando un token de prueba que sí se detecta. De ahí salió además un hueco del guion: escaneaba commits, así que un archivo nuevo era invisible en local y solo aparecía en la tubería; ahora escanea también los archivos sin seguimiento (`ecaff2f`, `da6dcfb`). Decisiones de Miguel: **una sola forma para el número de póliza** (`POL-` y seis dígitos, sin iniciales de aseguradora, porque el visitante lo teclea y lo dice en voz alta, y porque sin iniciales una agencia puede tener como ejemplo una póliza de otra), y **la redacción entra a la lista de módulos críticos** del piso de cobertura, que pasa de cuatro a cinco. U3 `pii-redaction` cerró sus cuatro etapas de diseño; el revisor encontró **17 defectos en ellas**, los 17 míos, y clasificados por causa 13 eran de dos clases que una máquina detecta: afirmar algo sin comprobarlo contra su fuente, y contradecirse dentro del mismo documento. De ahí `scripts/check-artifacts.py`, que corre antes de cerrar cada etapa (`b736bb5`). Siguiente: la generación de código de U3, y después U4, U5 y U6. |
