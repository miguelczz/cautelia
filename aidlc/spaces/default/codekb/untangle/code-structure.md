# Code Structure — repositorio `untangle`

Artefacto 3 de 9. Organización del repositorio en el commit `3736ad364d8d83526b2d7148e9d3ed8b76851757`, clasificación de archivos, mapa interno de `site/index.html` y patrones de código observados. Las responsabilidades de cada componente están en `component-inventory.md`; este artefacto registra dónde vive cada cosa.

## Organización del repositorio

Un solo repositorio git (`untangle`, raíz del workspace de AI-DLC por D-002), sin submódulos, sin paquetes ni workspaces. 381 archivos versionados según `git ls-files` (conteo del desarrollador):

```text
untangle/
├── .gitignore                 # bloque propio (D-006, Vercel, secretos, Python/Node anticipados) + bloque gestionado AI-DLC:gitignore
├── design-package.md          # diseño y copy EN/ES de la landing (fuente del diccionario I18N)
├── site/                      # landing estática publicada (10 archivos versionados)
│   ├── index.html             # 1.011 líneas: CSS, HTML y JS inline
│   ├── assets/                # 5 JPEG + 1 MP4 (6,3 MB)
│   ├── PHOSPHOR-LICENSE.txt   # MIT, Phosphor Icons (glifo scribble-loop inlineado)
│   ├── .gitignore             # .env.local, .vercel
│   ├── .vercelignore          # .env.local, .gitignore
│   └── .vercel/               # proyecto enlazado de Vercel (ignorado por git, no leído)
├── docs/                      # especificación del producto y kit de metodología (69 archivos)
├── .claude/                   # engine y tooling de AI-DLC 2.9.0 (292 archivos)
├── aidlc/                     # memoria del espacio AI-DLC (8 archivos versionados) + registro del intent (no versionado)
├── review/                    # artefactos de trabajo del loop creativo (ignorado, no leído)
└── 10k-websites-skill.zip     # skill del loop creativo (ignorado, no leído)
```

| Área | Archivos versionados | Clase | Analizado en profundidad |
| --- | --- | --- | --- |
| `site/` | 10 | Código de presentación (landing) | Sí |
| `design-package.md` | 1 | Documentación de diseño de la landing | Sí |
| `docs/` | 69 | Documentación de producto (especificación) y kit de metodología | Parcial: PRD, plan, brief, evaluación, voz y tono, overview, PVB (§4 y §7) y `docs/reference/` a fondo; el resto por encabezados |
| `.claude/` | 292 | Tooling del proceso (engine AI-DLC) | No: hojeado a granularidad de directorio |
| `aidlc/` | 8 | Memoria del espacio y registro del flujo | No: hojeado |
| `.gitignore` | 1 | Configuración | Sí |

No existe ningún directorio de código del aplicativo (`src/`, `app/`, `packages/`, `services/`), ningún archivo `.py`, `.js`, `.ts`, `.mjs`, `.cjs`, `.jsx` o `.tsx` versionado fuera de `.claude/`, y ningún manifiesto de dependencias (lista completa de ausencias en `dependencies.md`).

## `site/`: mapa interno de `index.html`

Un único documento de 1.011 líneas y 79.260 bytes. Bloques por rango de líneas (verificados en el commit escaneado):

| Líneas | Bloque | Contenido |
| --- | --- | --- |
| 1-19 | `<head>` | Metadatos, descripción, `theme-color`, favicon SVG en `data:` URI (línea 9), comentario "DEPLOY STEP" obsoleto (10), Open Graph con `og:url` y `og:image` absolutas (14-15), `twitter:card` (16), `preconnect` y hoja de Google Fonts (17-19) |
| 20-322 | CSS inline | Custom properties de color y tipografía, reglas minificadas a mano (una regla por línea), media query de modo estático (134) y de `prefers-reduced-motion` (309-322), selectores `.hud` sin uso (118, 130, 137) |
| 323-589 | HTML | Skip link (325), `nav` con selector de idioma y ancla LinkedIn (328-349), `main` (350) con el hero `#top` (351-389) y las secciones `#why` (391), `#how` (408), `#voice` (461), `#guardrails` (493), `#evals` (511), `#try` (532), `#faq` (554), `#contact` (568); `footer` (580) |
| 591-1009 | JavaScript inline | IIFE en modo estricto; submódulos en la tabla siguiente |

Submódulos del script, en el orden del archivo (los nombres de componente son los de `component-inventory.md`):

| Líneas | Comentario de sección en el código | Componente |
| --- | --- | --- |
| 594-598 | `config` (`LINKEDIN_URL`, `VIDEO_URL`, `VIDEO_BYTES`, `POSTER_URL`) | Hero Scrub Engine y Landing Document Shell |
| 601-729 | `copy`: diccionario `I18N`, primero EN y luego ES, 119 claves por idioma (la clave `hud1` está en 610 y 674) | I18N Dictionary and Language Switcher |
| 731-738 | `helpers`: `$`, `$$`, `clamp`, `smoothstep`, `rng`, `hash`, `reduced` | Compartidos; `reduced` pertenece a Reduced Motion Controller |
| 741 | `linkedin`: reescritura de `.js-linkedin` | Landing Document Shell |
| 743-774 | `text splitting`: `splitEl`, `splitAll` | Hero Scrub Engine (entradas de las bandas) |
| 776-794 | `i18n`: `applyLang` y el enlace de los botones | I18N Dictionary and Language Switcher |
| 796-909 | `hero engine`: medición, progreso, seek, carga del Blob, `failVideo`, `GATES`, `applyHeroMode`, observador del hero, `resize` | Hero Scrub Engine |
| 911-922 | `section entrances and living elements`: `IntersectionObserver` y `visibilitychange` | Section Reveal Observer |
| 924-965 | `the signature thread`: `layoutThread`, `threadProgress`, `applyThread`, `drawThread` | Signature Thread Renderer |
| 967-987 | `the interactive moment`: `holdTick`, `holdStart`, `holdEnd`, listeners | Knot Hold Interaction |
| 989-999 | `reduced motion, live in both directions`: `pinToFinalStates`, `unpinFinalStates`, listener `change` | Reduced Motion Controller |
| 1001-1008 | `boot`: idioma guardado, `applyLang`, `measure`, `applyHeroMode`, `layoutThread`, `pinToFinalStates` | Landing Document Shell (arranque) |

## Patrones de código observados en la landing

- **IIFE con `'use strict'` y cero globales**: todo el estado es léxico del módulo; los submódulos se comunican por variables compartidas (`lang`, `scrubOn`, `bands`, `reduced`, `threadPinned`, `holdDone`) y por clases CSS en el DOM, no por interfaces.
- **Contrato declarativo HTML ↔ JS por atributos `data-*`**: `data-i18n`, `data-i18n-html`, `data-i18n-aria` (copy), `data-lang` (selector), `data-entrance`, `data-a`, `data-b`, `data-ramp` (bandas del hero), y clases gancho `.js-linkedin`, `.split`, `.rv`, `.band`.
- **Texto para lectores de pantalla separado del texto animado**: cada titular animado lleva un `.sr` (fuente de verdad del texto) y un `.vis` (partición en `span.w` y `span.c` con variables CSS `--th`, `--jx`, `--jy`); la partición usa un RNG determinista sembrado por hash del texto, por lo que la animación es reproducible por idioma.
- **Estado de animación en variables CSS** (`--p` del nudo, `--th` de las entradas) y en clases de estado (`in`, `done`, `live`, `paused`, `solid`, `untangled`): el JS calcula, el CSS pinta.
- **Bucles `requestAnimationFrame` que se apagan solos** al converger (hero) o al llegar a 0 o 1 (nudo), y `passive: true` en los listeners de scroll.
- **Degradación explícita**: `try/catch` en `localStorage` y `setPointerCapture`; `AbortController` con watchdog; `failVideo`; compuertas `matchMedia` evaluadas en vivo.
- **Estilo**: CSS minificado a mano en una regla por línea; JS compacto, nombres cortos y descriptivos, funciones en general menores de 30 líneas (excepciones: `splitEl`, `loadHeroBlob`, `layoutThread`); sin `console.*`, sin `TODO`/`FIXME`.
- **Sin herramienta de estilo**: no hay formatter ni linter que fije estas convenciones (`code-quality-assessment.md`).

## `docs/`: documentación del producto y kit de metodología

66 archivos Markdown en español (17.854 líneas, 1,1 MB) dentro de 69 archivos. No es código. Clasificación:

| Ruta | Clase | Contenido | Uso en el flujo |
| --- | --- | --- | --- |
| `docs/specs/prd.md` | Especificación del producto | PRD v1.0, 1.507 líneas: Paso 0, Segmentos 1-13, Cierre | Fuente del alcance del aplicativo (`business-overview.md`) |
| `docs/PLAN-AIDLC.md` | Plan del proceso | Estado por paso, D-001 a D-017, mapa v0.1.5 → 2.9.0, registro de sesiones | Fuente de verdad del proceso |
| `docs/00-brief-untangle.md`, `docs/01-evaluacion-brief.md` | Brief y evaluación | Brief original con adenda; 12 ajustes aprobados (D-010) | Origen de las decisiones |
| `docs/pre_prb/` (8 archivos) | Pre-incepción | `idea.md`, `critica.md` (C1-C16), `icp.md`, `mercado.md`, `overview.md`, `pvb.md`, `respuestas_critica_pvb.md`, `voz-y-tono.md` | Cubre lo que 2.9.0 llama Ideation (por eso `classic` la salta); la guía de voz es insumo de user stories y de la unit de voz |
| `docs/reference/` (2 archivos) | Referencia de dominio | Estructura de póliza ISO PP 00 01; investigación de proveedores de voz | Insumo del corpus sintético y de D-016 |
| `docs/ai-dlc_guide/` (16) | Guía del equipo | Escrita para AI-DLC v0.1.5; pendiente de actualizar a 2.9.0 (D-001) | Referencia metodológica, no producto |
| `docs/aidlc-framework-v0.1.5/` (33) | Copia de reglas AWS v0.1.5 | Solo referencia | No producto |
| `docs/plantillas/` (4), `docs/ai-product-base.md`, `docs/prompts-especificacion.md` | Kit de metodología | Plantillas y prompts de especificación | No producto |

## `.claude/` y `aidlc/`: tooling del proceso

| Ruta | Clase | Contenido | Nota |
| --- | --- | --- | --- |
| `.claude/agents/` (14), `.claude/skills/` (43 skills `aidlc-*`), `.claude/tools/` (94), `.claude/hooks/` (18), `.claude/knowledge/`, `.claude/aidlc-common/`, `.claude/scopes/` (11), `.claude/sensors/` (6), `.claude/rules/aidlc.md`, `.claude/settings.json`, `.claude/CLAUDE.md` | Engine AI-DLC 2.9.0 para Claude Code (185 `.md`, 91 `.ts`, 13 `.json`) | Agentes, skills, herramientas TypeScript, hooks del ciclo de vida, conocimiento por agente, scopes y sensores | Tooling del proceso; no se analiza como código del producto. `.claude/skills/10k-websites/` está ignorado por git |
| `aidlc/spaces/default/memory/{org,team,project}.md`, `memory/phases/*.md` (4), `memory/templates/.gitkeep` | Memoria del espacio | Reglas org/team/project y por fase; sin plantillas de artefacto (el sensor `required-sections` opera con su piso por defecto) | Versionado |
| `aidlc/active-space`, `aidlc/.aidlc-clone-id`, `aidlc/.aidlc-sessions/`, `aidlc/spaces/default/intents/` | Cursores y registro del flujo | Estado del intent `260915-untangle-app`, auditoría por clon, artefactos por etapa | No versionados por diseño (bloque `AI-DLC:gitignore`), salvo lo que ese bloque declara committed |

## Convenciones de nombres y organización

- Directorios en minúsculas; documentación en español con nombres en español o numerados (`00-brief-untangle.md`, `01-evaluacion-brief.md`); el paquete de diseño y el código de la landing en inglés (D-003).
- Identificadores estables en la documentación: `D-<nnn>` (decisiones del plan), `M<n>`, `S<n>`, `C<n>`, `W<n>` (MoSCoW), `P<n>` (principios), `MOD-<nn>` y `F<módulo>.<n>` (módulos y features), `R<n>` (riesgos), `C<n>` en `critica.md` (críticas), `UC-<n>` (casos de uso).
- Ids de sección de la landing en inglés y en minúsculas (`#top`, `#why`, `#how`, `#voice`, `#guardrails`, `#evals`, `#try`, `#faq`, `#contact`); claves del diccionario `I18N` con prefijo de sección (`s2.a1`, `s8.cta`).
- No hay convención de código del aplicativo todavía: la elige `practices-discovery` junto con el lenguaje (ADR en `domain-design`).
