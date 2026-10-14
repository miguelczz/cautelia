# Technology Stack — repositorio `untangle`

Artefacto 6 de 9. Lenguajes, frameworks y librerías presentes en el commit `3736ad364d8d83526b2d7148e9d3ed8b76851757`, con versión cuando existe y con su ausencia declarada cuando no. Se separan tres stacks: el de la landing (existe), el del aplicativo (no existe; parte decidido por el PRD, parte hipótesis pendiente de ADR) y el tooling del proceso.

## Stack de la landing (existente)

| Capa | Tecnología | Versión | Evidencia |
| --- | --- | --- | --- |
| Marcado | HTML5 semántico | n/a | `site/index.html` 1-19, 323-589 |
| Estilos | CSS3 inline: custom properties, `clamp()`, `aspect-ratio`, `mask-image`, `backdrop-filter`, `overflow-x: clip`, `100svh`, `scroll-behavior: smooth`, `prefers-reduced-motion`, `pointer: coarse` | n/a (sin preprocesador) | `site/index.html` 20-322 |
| Script | JavaScript vanilla, sintaxis ES5 (`var`, funciones) sobre APIs modernas del navegador: `IntersectionObserver`, `AbortController`, `fetch` con `ReadableStream`, `URL.createObjectURL`, Pointer Events con `setPointerCapture`, `matchMedia` con `change`, `document.fonts.ready`, `performance.now`, `requestAnimationFrame`, `localStorage` | n/a (sin transpilador ni bundler) | `site/index.html` 591-1009 |
| Librerías JS y CSS | Ninguna | – | Verificado por el desarrollador: cero `<script src>`, cero frameworks |
| Tipografía | Google Fonts: Bricolage Grotesque (opsz 12..96, pesos 300 y 500), IBM Plex Sans (400, 500), JetBrains Mono (400) | Sin versión fijada (CSS remoto `css2`) | `site/index.html` 17-19; respaldos `Georgia, serif`, `system-ui, sans-serif`, `ui-monospace, monospace` |
| Iconografía | Phosphor Icons, glifo "scribble-loop" inlineado como SVG (marca y favicon); los demás iconos son SVG propios inline | Licencia MIT 2023 (`site/PHOSPHOR-LICENSE.txt`) | `site/index.html` 9 |
| Medios | JPEG baseline de 1.920 px; un MP4 (códec no registrado por el escaneo) | – | `site/assets/` (inventario en `component-inventory.md`) |
| Hosting y entrega | Vercel, sitio estático servido por su CDN | Plan y versión de la CLI no registrados en el repo | `site/.vercelignore`, `site/.vercel/` (ignorado); `og:url` |
| Build, lint, test | Ninguno | – | Sin `package.json`, `vercel.json`, ESLint, Prettier, Stylelint ni HTMLHint (`dependencies.md`) |

## Stack del aplicativo (por construir)

No hay ningún paquete instalado ni manifiesto. Lo que sigue es el estado de las decisiones tecnológicas según `docs/specs/prd.md` (Paso 0, Segmento 8 y 9.2), `docs/pre_prb/pvb.md` §7 y `docs/PLAN-AIDLC.md`. **Decidida** significa fijada por un Must del PRD o por una decisión D-nnn aprobada; **Hipótesis** significa candidato que la documentación nombra y que un ADR de `domain-design` (2.6) debe confirmar o reemplazar.

| Área | Tecnología | Estado | Fuente y condición |
| --- | --- | --- | --- |
| LLM | Gemini 2.5 Flash-Lite, tier de pago solo para voz y trabajo de fondo; tier gratuito para desarrollo y evals en texto; tope 5 USD en 90 días, alerta en 3 USD | Decidida | D-015, P9, M20. PVB §7 admite 3.1 Flash-Lite solo para un nodo que falle en evals y Groq si la latencia medida lo exige |
| Base de datos | Postgres con Row Level Security por `tenant_id` en todas las tablas; checkpoints del grafo en Postgres | Decidida | M2, M9, F2.4 |
| Vector store | pgvector dentro del mismo Postgres ("un solo mecanismo de aislamiento") | Hipótesis | PVB §7; el PRD Paso 0 deja embeddings y vector store como ADR de Incepción |
| Redacción de PII | Presidio en trazas y logs | Decidida | M6 (control 3 de MOD-07) |
| Telemetría | OpenTelemetry con convenciones semánticas GenAI; Langfuse self-host; dashboard visible | Decidida por M7 | M7 nombra Langfuse self-host; el PRD Paso 0 lista "Langfuse o Phoenix" como ADR informativo, así que el ADR debe confirmar Langfuse, no reabrirlo |
| Framework del grafo | LangGraph (grafo explícito, checkpoints, `interrupt()`) | Hipótesis | PVB §7: "se confirma como ADR en Incepción"; lo decidido es el comportamiento (P3, F2.1 a F2.5), no la librería |
| Framework de voz | LiveKit Agents o Pipecat | Hipótesis | PVB §7 y PRD Paso 0: ADR con criterios de integración con el grafo y costo; el grafo no depende del framework de voz |
| STT | Deepgram Nova-3 (plan B: Whisper) | Hipótesis | PVB §7, plan B de plataforma; el requisito es WER aceptable en español (spike de riesgo, R4) |
| TTS | Cartesia (voces `es-CO`, gratuito con API) o ElevenLabs (voces de Medellín, no por API en el gratuito); Kokoro local para iteración; plan B Kokoro o Chatterbox | Hipótesis condicionada por D-016 | `docs/reference/voz-proveedores.md` §3; prueba ciega en la semana 1; si gana ElevenLabs, Miguel decide si sube el tope a unos 20 USD (dependencia con fecha en PRD 13.4) |
| Evals | promptfoo o DeepEval en CI; golden sets propios (60 casos de texto, 40 preguntas de citación, 20 grabaciones) | Hipótesis (herramienta); Decidida (comportamiento) | PVB §7; M8, M13, M15 y MOD-11 fijan los golden sets y que la regresión bloquee el merge |
| Identidad | Tokens simples con claim de tenant en la v1; Keycloak en Could | Decidida (v1); Hipótesis (Keycloak) | M9; PRD Paso 0 conflicto 6; ADR pendiente |
| Lenguaje del aplicativo | Sin decidir. El `.gitignore` anticipa Python (`__pycache__/`, `.venv/`) y Node (`node_modules/`, `dist/`, `.next/`); el plan (paso 8) menciona `venv` | Hipótesis | ADR de `domain-design`; condiciona formatter, linter y toolchain de `practices-discovery` |
| Ejecución local | `docker compose` para dashboard y telemetría en local | Hipótesis (mención) | PRD 9.5 pantalla 6; Postgres en Docker como plan B de Neon o Supabase (PVB §7) |
| Hosting del chat y la bandeja | Tier gratuito sin proveedor fijado; la landing sigue en Vercel | Hipótesis | PRD 9.5 pantallas 2 a 5; intent `infra` (D-014) |
| Corpus de referencia | Estructura ISO PP 00 01 y formularios ACORD como estructura, texto original | Decidida | M3, PVB §7 (propiedad intelectual), `docs/reference/estructura-poliza-iso-pap.md` |

Los cuatro spikes de riesgo de las semanas 1 y 2 (voz-grafo, Flash-Lite, WER en español, voces paisas; PRD 13.1) son los que convierten estas hipótesis en ADR.

## Tooling del proceso

| Herramienta | Versión | Evidencia | Uso |
| --- | --- | --- | --- |
| AI-DLC (AWS) | 2.9.0; binario nativo `aidlc` invocado por los hooks de `.claude/settings.json` | `.claude/` (185 `.md`, 91 `.ts`, 13 `.json`), D-001 | Orquestación del ciclo de vida; `AWS_AIDLC_DEFAULT_SCOPE=classic`; Bedrock retirado y MCP `none` según `docs/PLAN-AIDLC.md` 6.3 |
| Claude Code | No registrada | `.claude/CLAUDE.md`, `.claude/settings.json` | Harness de los agentes |
| git | No registrada | 8 commits en `main`, remoto privado `github.com/miguelczz/untangle` (D-017) | Control de versiones sin ramas ni tags |
| Vercel CLI | No registrada | Despliegue manual desde `site/` | Publicación de la landing |
| Guía del equipo | Escrita para AI-DLC v0.1.5 | `docs/ai-dlc_guide/`, `docs/aidlc-framework-v0.1.5/` | Referencia, pendiente de actualizar (D-001) |

## Ausencias declaradas

Sin runtime de Node ni de Python fijado (`.nvmrc` y `.python-version` ausentes), sin manifiestos, sin lockfiles, sin contenedores, sin CI, sin linters ni formatters. La lista exhaustiva de archivos buscados y ausentes está en `dependencies.md`; sus implicaciones para `practices-discovery` en `code-quality-assessment.md`.
