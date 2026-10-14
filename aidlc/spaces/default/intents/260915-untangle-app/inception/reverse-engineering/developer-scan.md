# Developer Code Scan — repositorio `untangle`

**Etapa:** `reverse-engineering` (INCEPTION) · **Intent:** `260915-untangle-app` · **Espacio:** `default` · **Agente:** `aidlc-developer-agent` (enlace 1 de 2 de la cadena desarrollador → arquitecto).
**Fecha del escaneo:** 2026-09-15T21:34Z · **Commit escaneado:** `3736ad364d8d83526b2d7148e9d3ed8b76851757` (rama `main`, 2026-09-15T21:12:26Z, remoto privado `github.com/miguelczz/untangle`). Árbol de trabajo sin modificaciones sobre archivos versionados; único cambio no versionado: `aidlc/spaces/default/intents/` (el registro del flujo, creado por el engine a las 21:26:40Z).
**Amplitud:** escaneo completo (primer escaneo, no existe code knowledge base previo; `NO_STORE`). Rutas del snapshot pre-escaneo: `["./"]`.

**Conclusión en una frase (con evidencia abajo):** el repositorio **no contiene código de aplicación**. De los 381 archivos versionados, 292 son el engine y tooling de AI-DLC (`.claude/`), 69 son documentación de producto y metodología (`docs/`), 8 son la memoria del espacio AI-DLC (`aidlc/`), 10 son una landing estática ya publicada (`site/`) y 2 son `design-package.md` y `.gitignore`. No hay Python, ni servicios, ni `package.json`, ni pruebas, ni CI. El único código ejecutable orientado al producto es el script inline de `site/index.html` (418 líneas de JavaScript), que pertenece a la landing y queda fuera del alcance del aplicativo (D-013).

---

## Developer Code Scan Results

### Scan Coverage

- **Analyzed deeply** (leído y comprendido archivo por archivo):
  - `site/index.html` (1.011 líneas, 79.260 bytes): leído completo; CSS inline líneas 20-322, HTML líneas 323-589, JavaScript inline líneas 591-1009.
  - `site/.gitignore`, `site/.vercelignore`, `site/PHOSPHOR-LICENSE.txt`.
  - `site/assets/` (6 archivos: 5 JPEG 1920×1080/1086 y 1 MP4): inspeccionados por metadatos (`file`, tamaños); no se abrieron visualmente.
  - `design-package.md` (diseño y copy de la landing, 22.637 bytes): leído completo.
  - `docs/specs/prd.md` (PRD v1.0, 1.507 líneas, 161.456 bytes): leídos completos el Paso 0, los Segmentos 1 a 4 (introducción), 8 (MoSCoW), 9.1 a 9.3 y 9.5 a 9.6 (tenants, arquitectura funcional, roles, pantallas, trazabilidad), 12.1 (riesgos), 13 (plan 30/60/90) y el Cierre; el 9.4 se leyó por encabezados de módulo (`MOD-01` a `MOD-15`) más `MOD-01` completo; el resto (5, 6, 7, 10, 11, 12.2 a 12.4) solo por encabezados.
  - `docs/PLAN-AIDLC.md` (302 líneas): leído completo (estado, decisiones D-001 a D-017, mapa de etapas, registro de sesiones).
  - `docs/00-brief-untangle.md`, `docs/01-evaluacion-brief.md`, `docs/pre_prb/voz-y-tono.md`, `docs/pre_prb/overview.md`, `docs/reference/estructura-poliza-iso-pap.md`, `docs/reference/voz-proveedores.md`: leídos completos.
  - `docs/pre_prb/pvb.md`: leídas las secciones 4 (Producto) y 7 (Decisiones estratégicas, plan B, riesgos); el resto por encabezados.
  - `.gitignore` de la raíz: leído completo (bloque propio + bloque gestionado `AI-DLC:gitignore`).
  - Historial git: 8 commits, todos del 2026-09-15 entre 15:15 y 16:12 (-05:00), un solo autor; sin tags; `main` rastrea `origin/main`.
- **Skimmed only** (hojeado a granularidad de directorio o de encabezados; no analizado como código de aplicación):
  - `.claude/` (292 archivos versionados: 185 `.md`, 91 `.ts` con 141.343 líneas, 13 `.json`): engine AI-DLC 2.9.0 para Claude Code — `agents/` (14 agentes), `skills/` (43 skills `aidlc-*`), `tools/` (94 archivos), `hooks/` (18), `knowledge/`, `aidlc-common/` (conductor y protocolos), `scopes/` (11), `sensors/` (6), `rules/aidlc.md`, `settings.json` (hooks `aidlc engine hook …` en PreToolUse, PostToolUse, UserPromptSubmit, SessionStart/End, PreCompact, SubagentStop), `CLAUDE.md`. Es tooling del proceso, no del producto. Ignorado dentro de él: `.claude/skills/10k-websites/` (skill del loop creativo, gitignored).
  - `aidlc/` (8 archivos versionados): `spaces/default/memory/{org,team,project}.md`, `memory/phases/*.md` (4), `memory/templates/.gitkeep` (sin plantillas de artefacto: el sensor `required-sections` opera con su piso por defecto). No versionados por diseño: `active-space`, `.aidlc-clone-id`, `.aidlc-sessions/`, `spaces/default/intents/`.
  - `docs/pre_prb/{idea,critica,icp,mercado,respuestas_critica_pvb}.md`: por encabezados (`idea.md` 346 líneas con 71 fuentes; `critica.md` 321 líneas con 16 críticas C1-C16).
  - `docs/ai-dlc_guide/` (16 archivos, guía del equipo escrita para AI-DLC v0.1.5; el plan la declara pendiente de actualizar a 2.9.0), `docs/aidlc-framework-v0.1.5/` (33 archivos, reglas AWS v0.1.5, solo referencia), `docs/plantillas/` (4), `docs/ai-product-base.md` (1.240 líneas), `docs/prompts-especificacion.md`: por encabezados; son copias del kit de metodología, no especificación del producto.
- **No leídos ni inventariados** (artefactos de trabajo ignorados por git, por instrucción del encargo y D-006): `review/`, `10k-websites-skill.zip`, `site/.vercel/`, `.DS_Store`.

Bloque de alcance propuesto para `reverse-engineering-timestamp.md` (el arquitecto lo completa con `fingerprint` y ajusta `analyzed.components` para que coincida **literalmente** con los encabezados que escriba en `component-inventory.md`; `kind: full` es válido según el encargo porque el escaneo cubre `./` y lo no analizado a fondo es tooling del proceso o material ignorado, declarado en `shallow.paths`):

```yaml
kind: full
analyzed:
  paths:
    - ./
    - site/
    - site/assets/
    - design-package.md
    - docs/specs/prd.md
    - docs/PLAN-AIDLC.md
    - docs/00-brief-untangle.md
    - docs/01-evaluacion-brief.md
    - docs/pre_prb/voz-y-tono.md
    - docs/pre_prb/overview.md
    - docs/pre_prb/pvb.md
    - docs/reference/
    - .gitignore
  components:
    - Landing Document Shell
    - Hero Scrub Engine
    - I18N Dictionary and Language Switcher
    - Section Reveal Observer
    - Signature Thread Renderer
    - Knot Hold Interaction
    - Reduced Motion Controller
    - Static Media Assets
    - Vercel Static Deployment
shallow:
  paths:
    - .claude/
    - aidlc/
    - docs/ai-dlc_guide/
    - docs/aidlc-framework-v0.1.5/
    - docs/plantillas/
    - docs/ai-product-base.md
    - docs/prompts-especificacion.md
    - docs/pre_prb/idea.md
    - docs/pre_prb/critica.md
    - docs/pre_prb/icp.md
    - docs/pre_prb/mercado.md
    - docs/pre_prb/respuestas_critica_pvb.md
    - review/
    - site/.vercel/
```

### Packages Found

No existe ningún paquete en el sentido de un manifiesto de dependencias. Lo que hay, clasificado por propósito:

- `site/` — **landing estática de una sola página** — HTML/CSS/JavaScript vanilla (todo inline en `index.html`) — cara pública del proyecto, publicada en `https://untangle-ai.vercel.app/` (valor de `og:url`, línea 14). **Fuera del alcance del aplicativo** (D-005, D-013); se documenta como lo que es.
  - Estructura de la página (ids de sección, líneas): `#top` hero con video scrubbeado por scroll (351-389), `#why` S1 "Not another wrapper" (391), `#how` S2 diagrama SVG de arquitectura + 6 tarjetas de agentes (408), `#voice` S3 pipeline de voz y conversación guionizada (461), `#guardrails` S4 (493), `#evals` S5 (511), `#try` S6 interacción "hold to untangle" (532), `#faq` S7 con 5 `<details>` (554), `#contact` S8 CTA final (568), `<footer>` (580). Un solo CTA en toda la página: 5 anclas `.js-linkedin` reescritas por JS a la URL de LinkedIn (constante `LINKEDIN_URL`, línea 595).
  - Módulos lógicos del script (IIFE en modo estricto, líneas 591-1009): configuración (`LINKEDIN_URL`, `VIDEO_URL`, `VIDEO_BYTES`, `POSTER_URL`, 594-598); diccionario `I18N` EN/ES (601-729; 119 claves por idioma, paridad exacta EN↔ES verificada); helpers y RNG determinista por hash del texto (731-738); partición de titulares en palabras y caracteres para las entradas del hero (743-774); `applyLang` con persistencia en `localStorage['untangle-lang']` y `<html lang>` (776-793, 1001-1002; primera visita según `navigator.language`); motor del hero: medición, `requestAnimationFrame` con lerp normalizado por `dt`, `requestSeek` con cola de un solo seek, carga del video como Blob en streaming con anillo de progreso, `AbortController` con watchdog de 20 s y degradación a póster (`failVideo`) (795-882); compuertas `matchMedia` para el hero estático (884-902); `IntersectionObserver` para entradas de sección y estados `live`/`paused` (904-914); hilo SVG "firma" dibujado por `stroke-dashoffset` según el scroll (916-949); interacción del nudo con pointer events, captura de puntero y teclado (951-972); `prefers-reduced-motion` aplicado en vivo en ambas direcciones (974-985); arranque (987-1008).
  - Assets (`site/assets/`, 6,3 MB en total): `hero-scrub.mp4` 5.415.961 bytes (video del hero, cargado bajo demanda con `fetch(..., {priority:'low'})`), `hero-poster.jpg` 172 KB, `hero-ending.jpg` 91 KB (también imagen `og:image` y fondo de S4), `still-pull.jpg` 174 KB (S1, `loading="lazy"`), `still-row.jpg` 391 KB (S5, `loading="lazy"`), `still-meet.jpg` 224 KB (fondo CSS de S8). Todas las imágenes 1920 px de ancho, JPEG baseline.
  - Licencias: `site/PHOSPHOR-LICENSE.txt` (MIT, Phosphor Icons 2023) por el glifo "scribble-loop" inlineado como marca y favicon (SVG en `data:` URI, línea 9).
- `docs/` — **especificación del producto y kit de metodología** — Markdown en español (66 `.md`, 17.854 líneas, 1,1 MB) — no es código. Detalle en "Documentation Structure" más abajo.
- `design-package.md` — **paquete de diseño de la landing** — Markdown en inglés — premisa de marca, tokens de color, tipografías, mapa de bandas del hero, copy EN/ES verbatim de todas las secciones, plan de la capa vectorial y lista de ingeniería. Es la fuente del copy que hoy vive en `index.html`.
- `.claude/` y `aidlc/` — **tooling del flujo AI-DLC 2.9.0** — TypeScript y Markdown — engine, agentes, skills, hooks, sensores, memoria del espacio. No es código del producto y no se analiza como tal.
- **Aplicativo Untangle (grafo, agentes, RAG, voz, bandeja, evals):** **no existe todavía** en el repositorio. Ningún directorio de código fuente, ningún archivo `.py`, `.js`, `.ts` fuera de `.claude/tools/` (verificado con `git ls-files`: 0 archivos `.js/.mjs/.cjs/.jsx/.tsx/.py` versionados).

### Build System

- **Type**: ninguno para el producto. La landing no tiene bundler, minificador ni transpilador: `index.html` se sirve tal cual. El "build" es un despliegue estático de `site/` en Vercel mediante la CLI (no hay integración git→Vercel ni `vercel.json`; el proyecto enlazado vive en `site/.vercel/`, ignorado por git). El engine AI-DLC corre como binario nativo `aidlc` invocado por los hooks de `.claude/settings.json`; es tooling del proceso.
- **Config Files**:
  - `site/.vercelignore` (2 líneas: `.env.local`, `.gitignore`) y `site/.gitignore` (2 líneas: `.env.local`, `.vercel`).
  - `.gitignore` de la raíz: bloque propio (`review/`, `*.zip`, `.claude/skills/10k-websites/`, `site/.vercel/`, `.env*`, `.DS_Store`, y anticipa `__pycache__/`, `.venv/`, `node_modules/`, `dist/`, `.next/` "para la construcción") + bloque gestionado `AI-DLC:gitignore` (cursores y estado local del engine).
  - `.claude/settings.json` (hooks y permisos del engine; según `PLAN-AIDLC.md` 6.3 se retiraron las variables de Bedrock y queda `AWS_AIDLC_DEFAULT_SCOPE=classic`).
  - **Ausentes** (búsqueda en todo el repo salvo `.git`, `review/`, `site/.vercel/`): `package.json`, lockfiles, `tsconfig.json`, `requirements.txt`, `pyproject.toml`, `Makefile`, `Dockerfile`, `docker-compose*.yml`, `vercel.json`, `.eslintrc*`, `.prettierrc*`, `.editorconfig`, `.nvmrc`, `.python-version`, `.github/`, `.gitlab-ci.yml`, `.circleci/`, `.mcp.json` (mencionado por `.claude/CLAUDE.md` pero no existe: el engine se configuró con `--mcp none`).
- **Build Dependencies**: ninguna relación paquete → paquete. Dependencias en tiempo de ejecución de la landing: fuentes de Google (ver Frameworks & Libraries) y el video/imágenes del mismo origen.

### APIs Discovered

- **Internas**: ninguna. No hay servidor, endpoints, formularios ni backend. El único `fetch` es al mismo origen: `fetch('assets/hero-scrub.mp4', {priority:'low'})` (línea 857) para leer el video como stream y construir un Blob.
- **Externas (salientes, solo enlaces o recursos)**:
  - LinkedIn: `https://www.linkedin.com/in/miguelzuluaga/` (constante línea 595), inyectada en las 5 anclas `.js-linkedin` (nav 346, hero 372 y 383, S8 574; la FAQ 563 lo menciona en texto). Único canal de conversión; sin formulario, sin `mailto:`, sin teléfono.
  - Google Fonts: `https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,300;12..96,500&family=IBM+Plex+Sans:wght@400;500&family=JetBrains+Mono:wght@400&display=swap` (línea 19) con `preconnect` a `fonts.googleapis.com` y `fonts.gstatic.com` (17-18).
  - Open Graph: `og:url` y `og:image` absolutas a `https://untangle-ai.vercel.app/` (14-15); `twitter:card` `summary_large_image` (16).
- **Sin analítica ni terceros de seguimiento**: no hay scripts externos, píxeles, cookies ni consentimiento. El único estado persistente del visitante es `localStorage['untangle-lang']` (líneas 791 y 1001). El PRD (13.4) deja la analítica de la landing como dependencia TBD de Miguel.
- **Almacenamiento y datos**: ninguno.

### Frameworks & Libraries

- Ninguna librería JavaScript ni CSS. Vanilla ES5 con APIs modernas del navegador: `IntersectionObserver`, `AbortController`, `fetch` con `ReadableStream`, `URL.createObjectURL`, Pointer Events con `setPointerCapture`, `matchMedia` con `change`, `document.fonts.ready`, `performance.now`, `requestAnimationFrame`, `localStorage`. CSS: custom properties, `clamp()`, `aspect-ratio`, `mask-image`, `backdrop-filter`, `overflow-x: clip`, `100svh`, `scroll-behavior: smooth`, `prefers-reduced-motion`, `pointer: coarse`.
- Fuentes (Google Fonts, sin versión fijada): Bricolage Grotesque 300/500 (display), IBM Plex Sans 400/500 (cuerpo), JetBrains Mono 400 (etiquetas). Pilas de respaldo declaradas (`Georgia, serif`; `system-ui, sans-serif`; `ui-monospace, monospace`).
- Iconografía: Phosphor Icons "scribble-loop" (MIT, 2023), un solo glifo inlineado; los demás iconos son SVG propios inline.
- **Frameworks del aplicativo: ninguno instalado.** Los candidatos que la documentación fija como hipótesis pendientes de ADR en la etapa `domain-design` (2.6) son: LangGraph (grafo con `interrupt()` y checkpoints en Postgres), LiveKit Agents o Pipecat (voz), Deepgram Nova-3 (STT), Cartesia o ElevenLabs (TTS, D-016; Kokoro local para iteración), Gemini 2.5 Flash-Lite (LLM, D-015), Postgres + pgvector con RLS, Langfuse self-host + OpenTelemetry GenAI, Presidio (PII), promptfoo o DeepEval (evals). Fuente: `docs/pre_prb/pvb.md` §7 "Decisiones estratégicas", `docs/specs/prd.md` Paso 0 y Segmento 9.2, `docs/PLAN-AIDLC.md` paso 7 (2.6).

### Test Coverage

- **Test Directories**: ninguno (búsqueda de `tests/`, `test/`, `__tests__/`, `spec/`, `e2e/`, `evals/`, `*.test.*`, `*.spec.*`, `test_*.py` en todo el repo salvo `.git` y `review/`: 0 resultados).
- **Test Frameworks**: ninguno.
- **Coverage Config**: ausente.
- La landing se validó con compuertas manuales descritas en `design-package.md` §4, §8 y §9 ("flick test" a 120 y 360 px, auditoría de contraste del peor fotograma a 3.5:1, gate de copy de la "Phase 9" del skill: cero em dashes y cero palabras de relleno). Nada de eso está automatizado ni versionado como prueba.
- El PRD exige para el aplicativo (M8, M13, M15, MOD-11) golden sets en CI (60 casos de texto, 40 preguntas de citación, 20 grabaciones de audio) con regresión que bloquea el merge, más tests de aislamiento entre tenants (M9) y tests unitarios del motor de reglas (M5). Nada de eso existe aún; es el punto de partida para Practices Discovery y la posture de pruebas del scope `classic` (piso del 80 % de cobertura y CI antes de merge según `org.md`).

### Code Quality Indicators

- **Linting**: ninguna herramienta ni configuración (sin ESLint, Prettier, EditorConfig, Stylelint, HTMLHint). Estilo del `index.html`: minificado a mano en el CSS (una regla por línea), JavaScript compacto en una IIFE con `'use strict'`, sin variables globales filtradas, sin `console.*`, sin `TODO`/`FIXME`/`HACK` (verificado con grep sensible a mayúsculas; las coincidencias de "todo" son español). Nombres claros y cortos (`measure`, `heroProgress`, `requestSeek`, `applyLang`, `layoutThread`, `holdTick`); funciones en general menores de 30 líneas salvo `splitEl`, `loadHeroBlob` y `layoutThread`.
- **Manejo de errores**: presente donde importa en una landing: `try/catch` alrededor de `localStorage` (791, 1001) y de `setPointerCapture`; carga del video con watchdog de 20 s, `abort`, `res.ok` y evento `error` del `<video>` que degradan al póster (`failVideo`); `setTimeout(startBlobFetch, 4000)` como respaldo si el póster no responde. Coherente con "complete without the video" del paquete de diseño.
- **Accesibilidad** (buena para una landing): enlace "Skip to content" (325), `<main id="main" tabindex="-1">`, `nav aria-label="Primary"`, selector de idioma `role="group"` con `aria-pressed`, video `aria-hidden` y `tabindex="-1"` con `preload="none"`, imágenes decorativas con `alt=""` y dimensiones explícitas, diagrama SVG con `role="img"` y `<title>` referenciado por `aria-labelledby` más una lista `<ol class="flow-list">` como alternativa en pantallas estrechas, botón del nudo con `aria-label`, `aria-describedby` y soporte de teclado (Espacio/Enter, líneas 966-967), `:focus-visible` con el color de acento, objetivos táctiles de 44 px con `pointer: coarse`, `prefers-reduced-motion` respetado en CSS (302-322) y en JS en vivo, `<html lang>` actualizado al cambiar de idioma, texto para lectores de pantalla (`.sr`) separado del texto animado (`.vis`, `aria-hidden`). Conteo: 41 atributos `aria-*`, 3 `role`.
- **Rendimiento**: sin minificación ni bundling (79 KB de HTML, aceptable); tres familias tipográficas externas con pesos recortados y `preconnect`; el video de 5,4 MB no bloquea el primer render (se pide como Blob de baja prioridad tras el póster) pero se descarga completo en escritorio y también en móviles en vertical (decisión del 2026-09-14 registrada en `design-package.md` §5); dos imágenes con `loading="lazy"`; dos fondos CSS (91 KB y 224 KB) que se descargan siempre; animaciones pausadas en pestaña oculta (`visibilitychange`, 914) y hero de 600 vh con `requestAnimationFrame` que se detiene al converger. No hay presupuesto de rendimiento medido en el repo (Lighthouse, Web Vitals).
- **CI/CD**: ninguno. Despliegue manual con Vercel CLI desde `site/`. Sin ramas de trabajo, sin PRs, sin tags: 8 commits directos a `main` el mismo día.
- **Documentation**: sin `README.md` en la raíz ni en `site/`; el PRD (M17, UC-5) exige un README para el evaluador y lo pone en Must para el aplicativo. La documentación de producto en `docs/` es extensa, consistente, en español, con decisiones identificadas (D-001 a D-017 en el plan; Paso 0 decisiones 1 a 13 en el PRD), aprobaciones fechadas por segmento y fuentes citadas. `.claude/CLAUDE.md` es el texto genérico del engine con el marcador `# Project Name <!-- Replace with your project name -->` sin sustituir y con instrucciones de Bedrock y `.mcp.json` que no aplican a este proyecto (Bedrock retirado, MCP `none`, según el plan 6.3).

### Technical Debt Signals

Todas las señales están en la landing o en el andamiaje; ninguna en código de aplicación, porque no lo hay.

1. **Desalineación de contenido entre la landing y el PRD (conocida, D-013, M19).** La landing afirma lo que el PRD ya decidió de otra forma:
   - Seis agentes por dominio (Orchestrator, Intake, Quote, Underwriting, Claims (FNOL), Documents; `index.html` 430-455 y tarjetas `s2.a1`-`s2.a6`) frente a cuatro nodos por función sobre un grafo (Intake, Policy Verification, Decision, Compliance; PRD Paso 0 decisión 1, M2, MOD-02). "Documents" es Could (C1) y la landing lo presenta como agente.
   - "Turns a profile into a priced quote using the carrier's rating rules" (`s2.a3.p`) frente a elegibilidad + banda indicativa sin moneda (PRD Paso 0 decisión 4, D-012, S1).
   - "Underwriting: checks eligibility … drafts the referral" frente a "elegibilidad y derivación", sin decisión de suscripción (evaluación del brief, ajuste 8).
   - "Voice in real time. Answers in seconds." frente a latencia publicada p50 < 500 ms y p95 < 800 ms por idioma (PRD Paso 0 decisión 2, P4).
   - El diagrama y el copy no mencionan multi-tenant, citación verificada de cláusulas, ni el chat web en vivo, que son el diferenciador y dos de los tres entregables (PVB §4, PRD M4, M10).
   El PRD programa dos pasadas de realineación (semana 7 y semana 11, Segmento 13) y el copy verbatim vive duplicado en `design-package.md` y en el diccionario `I18N`; toda corrección debe hacerse en los dos sitios (riesgo de deriva).
2. **Código muerto en la landing:** clave `hud1` presente en ambos diccionarios (líneas 610 y 674) sin ningún elemento `data-i18n="hud1"` (118 claves usadas de 119); selectores `.hud` en CSS (líneas 118, 130, 137) sin ningún elemento con esa clase en el HTML. Restos de un elemento eliminado.
3. **Comentarios obsoletos:** "the five gates, identical to the CSS" (línea 885) cuando `GATES` tiene 2 entradas (y la media query CSS correspondiente, línea 136, también 2); "DEPLOY STEP: patch og:url and og:image with the live absolute URL before zipping" (línea 10) cuando los valores ya están parcheados; `design-package.md` §8 y S8 hablan de un marcador `<!-- LINKEDIN URL -->` que ya no existe (reemplazado por la constante). `design-package.md` §4 titula "hero: 400vh, scroll range 300vh" y en el mismo apartado registra que se subió a 600 vh (lo que está construido); el footer descrito como "Mark + year" no lleva año.
4. **Acoplamiento manual:** `VIDEO_BYTES = 5415961` (línea 597) debe mantenerse a mano igual al tamaño real del MP4; hoy coincide. Si el video se reemplaza y se olvida, el anillo de progreso miente cuando falte `Content-Length`.
5. **Degradación sin JavaScript pobre:** sin JS, las bandas del hero quedan en `opacity:0`, el póster no se aplica (se fija desde JS en `initHeroOnce`, línea ~846) y el hero es un rectángulo oscuro; las anclas del CTA apuntan a `#contact` con `target="_blank"` hasta que JS las reescribe. Aceptable para una landing de portafolio, pero es una decisión implícita, no documentada.
6. **Una sola fuente de 1.011 líneas** que mezcla CSS, HTML, dos diccionarios y JS. Sin build, lint, pruebas ni CI: cualquier cambio de copy (incluida la realineación D-013) se verifica a ojo. Si la realineación va a ser recurrente, conviene un chequeo mínimo automatizable (paridad de claves EN/ES, palabras prohibidas del gate de copy, enlaces).
7. **Dependencia de terceros sin fijar versión:** Google Fonts (CSS remoto) y la URL de LinkedIn embebida en el código. Si se adopta un dominio propio, `og:url`/`og:image` deben actualizarse (están fijos a `untangle-ai.vercel.app`).
8. **Detección de workspace del engine imprecisa por el material ignorado:** el evento `WORKSPACE_SCANNED` de la auditoría registra `Languages: JavaScript`, `Frameworks: Unknown`, `Build System: Unknown` y `Nested Root: review`. `review/` es un directorio de trabajo del loop creativo, ignorado por git (D-006), y no fue leído por este escaneo. Para el aplicativo no hay lenguaje elegido: el `.gitignore` anticipa Python y Node a la vez y el plan (paso 8) menciona `venv`; la elección real llega con los ADRs de 2.6.
9. **Andamiaje incompleto para lo que el PRD promete como Must:** sin README (M17), sin CI ni evals (M8), sin generador de datos sintéticos (M3, MOD-12), sin corpus (solo la estructura de referencia en `docs/reference/estructura-poliza-iso-pap.md`). No es deuda del código existente sino la lista de lo que Construcción debe crear desde cero.
10. **Documentación del engine desactualizada respecto al proyecto:** `.claude/CLAUDE.md` con marcador sin sustituir, referencias a Bedrock y `.mcp.json` que no aplican; `docs/ai-dlc_guide/` describe v0.1.5 y el plan la declara pendiente de reescritura capítulo a capítulo (D-001). Prioridad baja; no afecta al producto.

### Documentation Structure (docs/) — insumo para el business overview

Lo que está decidido y aprobado, con su ubicación, para que el arquitecto no lo reabra:

- **Qué es Untangle** (`docs/specs/prd.md` Segmento 1; `docs/pre_prb/pvb.md` §4): sistema de agentes de producción con evidencia verificable, demostrado en seguros de auto; convierte una llamada o un chat, en inglés o español, en un caso completo con cobertura verificada cláusula por cláusula, reglas explicables y una persona en cada decisión que importa. Proyecto de portafolio **funcional en su totalidad**; solo los datos son de prueba (brief, adenda punto 1).
- **Dos clientes** (PRD Segmento 3): ICP A, quien evalúa y contrata (reclutador técnico, engineering manager, staff engineer como veto holder); ICP B, la aseguradora ficticia y su asegurado (dan realismo y guían el diseño). Cada trade-off se resuelve a favor del ICP A.
- **Tenants sintéticos y jurisdicción** (PRD 9.1): `stonecroft` Stonecroft Mutual Insurance Company (conservadora, español por defecto, ajustadora Diana), `sunmeadow` Sunmeadow Auto Insurance (flexible, inglés por defecto), `knotwell` Knotwell Insurance Agency (agencia intermediaria, siempre deriva). Jurisdicción ficticia "Estado de Corvane" [por defecto; alternativas Vantera, Ellery]. Nombres verificados contra marcas reales el 2026-09-15.
- **Arquitectura funcional aprobada** (PRD 9.2, diagrama Mermaid): dos canales (voz y chat web) entran al mismo grafo por tenant; nodos Intake → Policy Verification → Decision → Compliance sobre estado tipado con checkpoints; Compliance hace `interrupt()` hacia la bandeja del ajustador, que reanuda; servicios de dominio: Caso, Corpus y RAG con citación verificada, Motor de reglas por tenant, Controles de cumplimiento y PII; plataforma: Tenants e identidad (RLS y tokens), Telemetría y costo (OTel y Langfuse), Evals (golden sets en CI), Generador de datos sintéticos; proveedores externos intercambiables STT, LLM, TTS. **El orquestador es código** (P3): rutas explícitas, el grafo corre sin voz (chat y evals primero).
- **Módulos** (PRD 9.4): MOD-01 Caso, MOD-02 Orquestación, MOD-03 Canal de voz, MOD-04 Chat web, MOD-05 Corpus y RAG, MOD-06 Motor de reglas, MOD-07 Cumplimiento (cuatro controles), MOD-08 Bandeja, MOD-09 Tenants e identidad, MOD-10 Telemetría y costo, MOD-11 Evals, MOD-12 Generador de datos sintéticos, MOD-13 Cotización (Should), MOD-14 Documentos (Could), MOD-15 Evidencia pública. Features `F<módulo>.<n>` trazadas a M/S/C (PRD 9.6). Roles y permisos en 9.3; diez pantallas/flujos en 9.5.
- **Alcance MoSCoW** (PRD Segmento 8): M1 a M20 no se cortan (caso, grafo, corpus, RAG, reglas, cumplimiento, telemetría, evals en CI, multi-tenant, chat en vivo, bandeja, voz EN y golden set de audio EN, voz ES y golden set ES, llamada cortada reanudable, README, video, landing realineada, tope de gasto); S1 a S6; C1 a C6; W1 a W9. Regla de corte: S2, S1, C1, S5, S4; el español se reduce, nunca se elimina.
- **Principios no negociables** P1 a P12 (PRD Segmento 6): personas deciden cobertura y dinero; ninguna cita sin cláusula existente; orquestador es código; dos latencias medidas; evals con fallos a la vista; cumplimiento como controles verificables ("inspirado en", nunca "cumple con"); diseño de expectativas; datos y texto limpios; costo cero salvo el LLM con tope; real pero honesta; una idea por turno; una sola agente en dos idiomas y dos canales.
- **Decisiones de coste y voz**: D-015 LLM Gemini 2.5 Flash-Lite de pago solo para voz y trabajo de fondo, tope 5 USD en 90 días con alerta en 3 USD, tier gratuito para desarrollo y evals en texto; D-016 una sola voz femenina paisa (Medellín) en ambos idiomas, elegida por prueba ciega, usada solo en evals de audio, demos y video; **pendiente de Miguel** subir el tope a ~20 USD si gana ElevenLabs (`docs/reference/voz-proveedores.md` §3).
- **Guía de voz y tono** (`docs/pre_prb/voz-y-tono.md`): agente "Valentina" [por defecto], divulgación de IA y grabación en la primera frase, usted cálido con marcadores paisas ligeros, una pregunta por turno, orden fijo de captura, confirmación en voz alta por bloque, lo que nunca dice (cobertura, dinero, culpa, consejo legal), interrupciones (< 300 ms), silencios, cierre y derivación, versión para chat, rúbrica de evaluación. Es insumo directo de `user-stories` (2.4), `refined-mockups` (2.5) y de la unit de voz (3.1).
- **Plan de entrega** (PRD Segmento 13): 90 días desde el 2026-09-16 con compuertas en los días 30, 60 y 90; Incepción comprimida en las semanas 1-2 con cuatro spikes de riesgo en paralelo (voz-grafo, Flash-Lite, WER español, voces paisas); units previstas y su orden: Core → Policy RAG → Agents → Evals y observabilidad → Bandeja y chat → Voz EN → Voz ES → Cotización; intent `infra` aparte para CI y despliegue (D-014).
- **Riesgos** (PRD 12.1): R1 demo-ware, R2 latencia de turno, R3 Flash-Lite insuficiente, R4 español degradado, R5 tiers gratuitos, R6 tope agotado, R7 cita inexistente en el chat público, R8 fuga entre tenants o PII en trazas, R9 parecer que se cumple o propiedad intelectual, R10 integración voz-grafo.
- **Abierto según la documentación**: verbatims del ICP A (validación del día 30); nombres del ajustador de Sunmeadow y del agente de Knotwell (se fijan en user stories); jurisdicción definitiva; tope de la voz (D-016); Keycloak (ADR); Linear (paso 8); analítica de la landing; repositorio público o privado al publicar (D-017).
- **Proceso**: `docs/PLAN-AIDLC.md` es la fuente de verdad del proceso (estado por paso, D-001 a D-017, mapa v0.1.5 → 2.9.0, registro de sesiones). La pre-incepción en `docs/pre_prb/` cubre lo que 2.9.0 llama Ideation (por eso el scope `classic` la salta). `docs/ai-dlc_guide/` y `docs/aidlc-framework-v0.1.5/` son referencia metodológica, no producto.

### Workspace Detection Reconciliation

| Campo del engine (`WORKSPACE_SCANNED`) | Valor registrado | Lo que muestra el escaneo |
| --- | --- | --- |
| Project Type | Brownfield | Correcto solo para la landing (`site/`); el aplicativo es greenfield. El plan lo define como "brownfield de marketing, greenfield de aplicación" (D-005). |
| Languages | JavaScript | El único JavaScript versionado es el script inline de `site/index.html` (418 líneas). No hay `.js` como archivo. El engine (`.claude/tools/`) es TypeScript, no del producto. Lenguaje del aplicativo: sin decidir (ADR 2.6; el `.gitignore` anticipa Python y Node). |
| Frameworks | Unknown | Correcto: ninguno. |
| Build System | Unknown | Correcto: ninguno; despliegue estático manual en Vercel. |
| Nested Root | review | Directorio de trabajo ignorado por git (D-006); no leído. No es raíz de código. |

---

## Handoff Summary

- **Intent-relevant finding**: el repositorio no tiene código de aplicación; el aplicativo descrito en `docs/specs/prd.md` (grafo de cuatro nodos, RAG con citación verificada, reglas por tenant, cumplimiento, bandeja, voz bilingüe, evals, telemetría, tres tenants) se construye desde cero. Evidencia: `git ls-files` = 381 archivos (292 `.claude/`, 69 `docs/`, 10 `site/`, 8 `aidlc/`, 2 raíz); 0 archivos `.py/.js/.ts` fuera de `.claude/tools/`; sin manifiestos, pruebas ni CI. El único código es `site/index.html` (1.011 líneas: 302 CSS, 268 HTML, 418 JS inline), una landing estática bilingüe EN/ES publicada en Vercel con un solo CTA a LinkedIn, sin backend, sin formularios, sin analítica, sin dependencias salvo Google Fonts. Debe documentarse como landing, **no** como fuente de la arquitectura del aplicativo (D-013): su contenido (seis agentes por dominio, "priced quote", "Documents agent", "Answers in seconds") contradice decisiones ya aprobadas en el PRD (cuatro nodos por función, elegibilidad sin moneda, Documents en Could, latencias p50/p95) y está programado para realinearse en las semanas 7 y 11 (M19).
- **Risks / follow-up**:
  1. El arquitecto debe construir `business-overview.md` y `architecture.md` a partir de `docs/` (PRD 9.2 trae el diagrama funcional aprobado en Mermaid) y describir la arquitectura de la landing por separado como sistema estático de una página; no derivar componentes del aplicativo del código de `site/`.
  2. `analyzed.components` del bloque de alcance debe copiarse **verbatim** de los encabezados que el arquitecto escriba en `component-inventory.md` (el rerun guard compara literalmente); los nueve nombres propuestos arriba son una sugerencia.
  3. `technology-stack.md` debe distinguir "stack de la landing" (vanilla, Google Fonts, Phosphor MIT, Vercel) de "stack del aplicativo" (sin decidir; hipótesis del PVB §7 y PRD 9.2 pendientes de ADR en `domain-design`), y `code-quality-assessment.md` debe registrar la ausencia total de linting, pruebas y CI como línea base para `practices-discovery` (posture por defecto del scope `classic`: test-after, piso de 80 % de cobertura y CI antes de merge, `org.md`).
  4. Practices Discovery y Requirements Analysis deben leer el `Nested Root: review` de la detección como ruido (directorio ignorado, no leído) y el `Languages: JavaScript` como propiedad de la landing, no del aplicativo.
  5. Fuentes de deriva a vigilar: el copy de la landing vive duplicado en `design-package.md` y en el diccionario `I18N` de `index.html`; `VIDEO_BYTES` acoplado a mano al tamaño del MP4; `og:url`/`og:image` fijos al dominio de Vercel; `.claude/CLAUDE.md` con marcador de nombre sin sustituir y referencias a Bedrock y `.mcp.json` que no aplican.
  6. Decisiones abiertas que la documentación deja para etapas posteriores y que ninguna etapa de Incepción debe reabrir sin motivo: tope de la voz (D-016, pendiente de Miguel), Keycloak (ADR), nombres de ajustador/agente de cuenta (user stories), jurisdicción definitiva (Corvane por defecto), analítica de la landing, repositorio público al publicar (D-017).
  7. Elementos que Construcción deberá crear desde cero antes de cualquier Bolt: manifiesto y toolchain del lenguaje elegido, `README.md`, generador de datos sintéticos y corpus de los tres tenants, golden sets, CI con evals, tests de aislamiento entre tenants.
