# Code Quality Assessment — repositorio `untangle`

Artefacto 8 de 9. Línea base de calidad del commit `3736ad364d8d83526b2d7148e9d3ed8b76851757`: pruebas, linting, CI/CD, documentación y deuda técnica. Es el punto de partida de `practices-discovery` (siguiente etapa) y de la posture de pruebas del scope `classic`.

## Línea base en una tabla

| Dimensión | Estado | Evidencia |
| --- | --- | --- |
| Pruebas automatizadas | Ninguna (0 directorios, 0 archivos, 0 frameworks, sin configuración de cobertura) | Búsqueda de `tests/`, `test/`, `__tests__/`, `spec/`, `e2e/`, `evals/`, `*.test.*`, `*.spec.*`, `test_*.py`: 0 resultados |
| Cobertura de código | No medible (sin pruebas) | – |
| Linting y formato | Ninguno (sin ESLint, Prettier, Stylelint, HTMLHint ni EditorConfig) | Ausencias en `dependencies.md` |
| CI/CD | Ninguno; despliegue manual con la CLI de Vercel; 8 commits directos a `main` el 2026-09-15, sin ramas, PRs ni tags | Historial git; `site/.vercel/` ignorado |
| README | Ausente en la raíz y en `site/` | El PRD lo exige como Must (M17) para el aplicativo |
| Documentación de producto | Extensa y consistente (`docs/`, 66 `.md`, en español, con decisiones e IDs estables) | `docs/specs/prd.md`, `docs/PLAN-AIDLC.md` |
| Documentación del código | Comentarios de sección en `index.html`; tres de ellos obsoletos | TD-03 |
| Rendimiento medido | Sin presupuesto ni medición en el repo (Lighthouse, Web Vitals) | – |
| Accesibilidad | Buena en la landing (41 `aria-*`, 3 `role`, skip link, teclado, `prefers-reduced-motion`), sin pruebas que la protejan | `component-inventory.md` |
| Seguridad | Sin secretos en el repo (`.env*` ignorados); sin dependencias ejecutables de terceros; `rel="noopener"` en las anclas externas | `.gitignore`, `site/index.html` |

## Pruebas

- **Landing**: cero pruebas automatizadas. La validación fue manual y está descrita en `design-package.md` §4, §8 y §9: "flick test" a 120 y 360 px, auditoría de contraste del peor fotograma a 3,5:1, y el gate de copy de la "Phase 9" del skill (cero em dashes y cero palabras de relleno). Nada de eso está versionado como prueba ni es repetible por una máquina.
- **Aplicativo**: no existe, y el PRD ya fija su régimen de pruebas: golden sets en CI con regresión que bloquea el merge (M8: 60 casos de texto, 30 por idioma, y 40 preguntas de citación con distractores; M13 y M15: 10 grabaciones de audio por idioma con latencia de turno p50 y p95), tests unitarios del motor de reglas (M5), tests de aislamiento entre tenants en CI (M9) y evals con fallos a la vista (P5). Es el insumo directo de la Test Strategy `Standard` del intent.
- **Posture por defecto aplicable** (`aidlc/spaces/default/memory/org.md`, "Testing Posture", scope `classic`): metodología test-after, piso del 80 % de cobertura de líneas y ejecución en CI antes del merge; `practices-discovery` puede afirmar una posture más estricta pero no una más laxa.

## Linting y formato

No hay ninguna herramienta ni configuración. El estilo del `index.html` es consistente por disciplina del autor, no por tooling: CSS minificado a mano en una regla por línea; JavaScript compacto en una IIFE con `'use strict'`, sin globales filtradas, sin `console.*`, sin `TODO`, `FIXME` ni `HACK`; nombres cortos y claros; funciones en general menores de 30 líneas salvo `splitEl`, `loadHeroBlob` y `layoutThread`. Según `org.md` ("Code Style") el framework difiere a la configuración del proyecto, que hoy no existe; la elección de formatter y linter llega con el lenguaje del aplicativo (ADR en `domain-design`, afirmación en `practices-discovery`).

## CI/CD y despliegue

Sin pipelines (`.github/`, `.gitlab-ci.yml`, `.circleci/` ausentes). La landing se publica a mano con la CLI de Vercel desde `site/` (secuencia en `architecture.md`, "Despliegue manual a Vercel"); no hay integración git → Vercel, `vercel.json` ni entornos de preview. El flujo de trabajo del espacio (`org.md`, "Way of Working" y "Deployment") pide trunk-based con ramas cortas, squash-merge y despliegue a staging en el merge: nada de eso está montado; D-014 lo asigna a un segundo intent `infra`.

## Calidad de la documentación

- **Producto**: alta. El PRD (1.507 líneas) tiene decisiones fechadas y aprobadas por segmento, identificadores estables (M/S/C/W, P1 a P12, MOD-nn, `F<módulo>.<n>`, R1 a R10, UC-n) y fuentes citadas; el plan (`docs/PLAN-AIDLC.md`) lleva D-001 a D-017 con justificación y un registro de sesiones. La pre-incepción (`docs/pre_prb/`) cubre lo que 2.9.0 llama Ideation.
- **Landing**: `design-package.md` documenta premisa, tokens, tipografía, mapa de bandas, copy y lista de ingeniería, pero contiene afirmaciones desactualizadas respecto del código construido (TD-03).
- **Proceso**: `.claude/CLAUDE.md` es el texto genérico del engine con el marcador `# Project Name <!-- Replace with your project name -->` sin sustituir y con instrucciones de Bedrock y `.mcp.json` que no aplican al proyecto (Bedrock retirado y MCP `none`, plan 6.3); `docs/ai-dlc_guide/` describe v0.1.5 y está pendiente de reescritura (D-001). Prioridad baja: no afecta al producto (TD-10).
- **Ausente**: README (M17), ADRs (el PRD los exige en el README), diagrama del grafo, tabla principio → control → evidencia.

## Calidad del código de la landing (lo que está bien)

Manejo de errores donde importa (`try/catch` en `localStorage` y `setPointerCapture`; carga del video con `AbortController`, watchdog de 20 s, `res.ok`, evento `error` y degradación al póster; `setTimeout(startBlobFetch, 4000)` como respaldo). Accesibilidad cuidada (detalle en `component-inventory.md`, Landing Document Shell). Rendimiento razonable sin tooling: 79 KB de HTML, fuentes con pesos recortados y `preconnect`, video de 5,4 MB pedido como Blob de baja prioridad tras el póster, dos imágenes `loading="lazy"`, animaciones pausadas en pestaña oculta y bucles `requestAnimationFrame` que se detienen al converger. Puntos débiles: el video se descarga completo también en móvil vertical, dos fondos CSS (91 KB y 224 KB) se descargan siempre y no hay medición.

## Deuda técnica

Todas las señales están en la landing o en el andamiaje del proceso; ninguna en código de aplicación, porque no lo hay. Severidad: alta (bloquea o distorsiona una decisión del flujo), media (encarece un cambio previsto), baja (cosmética o de prioridad diferida).

| ID | Señal | Ubicación | Severidad | Recomendación y dueño |
| --- | --- | --- | --- | --- |
| TD-01 | Contenido de la landing desalineado con el PRD: seis agentes por dominio frente a cuatro nodos por función; "priced quote" frente a elegibilidad sin moneda; Underwriting que "drafts the referral" frente a elegibilidad y derivación sin decisión de suscripción; "Answers in seconds" frente a p50 < 500 ms y p95 < 800 ms; sin mención a multi-tenant, citación verificada ni chat en vivo. El copy vive duplicado en `design-package.md` y en el diccionario `I18N` | `site/index.html` 430-455 y claves `s2.a1` a `s2.a6`, `s2.a3.p`; `design-package.md` §6 | Media (conocida y programada) | Realinear en dos pasadas, semanas 7 y 11 (D-013, M19), corrigiendo ambas fuentes o eliminando la copia del paquete de diseño. Hasta entonces, ninguna etapa de Incepción usa la landing como insumo de diseño |
| TD-02 | Código muerto: clave `hud1` en ambos diccionarios sin ningún `data-i18n="hud1"` (118 de 119 claves con consumidor); selectores `.hud` en CSS sin ningún elemento con esa clase | `site/index.html` 610, 674 (claves); 118, 130, 137 (CSS) | Baja | Eliminar en la realineación; añadir al chequeo de paridad de claves |
| TD-03 | Comentarios y documentación obsoletos: "the five gates, identical to the CSS" con `GATES` de dos entradas; "DEPLOY STEP: patch og:url and og:image…" cuando ya están parcheados; `design-package.md` §8 y S8 hablan de un marcador `<!-- LINKEDIN URL -->` que ya no existe; §4 titula "hero: 400vh, scroll range 300vh" y registra en el mismo apartado la subida a 600 vh; el footer descrito como "Mark + year" no lleva año | `site/index.html` 10, 885; `design-package.md` §4, §6 (S8 y Footer), §8 | Baja | Corregir en la realineación; mantener `design-package.md` como descripción de lo construido o retirarlo |
| TD-04 | `VIDEO_BYTES = 5415961` debe mantenerse a mano igual al tamaño del MP4; si se reemplaza el video y se olvida, el anillo de progreso miente cuando falte `Content-Length` | `site/index.html` 597 | Baja | Derivar del `Content-Length` con respaldo generado, o documentar el paso en un README de `site/` |
| TD-05 | Degradación sin JavaScript pobre: bandas del hero en `opacity:0`, póster fijado solo desde JS (`initHeroOnce`), hero como rectángulo oscuro; anclas del CTA apuntando a `#contact` con `target="_blank"` hasta que JS las reescribe. Decisión implícita, no documentada | `site/index.html` 351-389, 346, 372, 383, 574, 847 | Baja | Fijar `poster` y `href` en el HTML; documentar la decisión si se mantiene |
| TD-06 | Una sola fuente de 1.011 líneas que mezcla CSS, HTML, dos diccionarios y JS, sin build, lint, pruebas ni CI: todo cambio (incluida la realineación) se verifica a ojo | `site/index.html` | Media | Antes de la primera realineación, un chequeo mínimo automatizable: paridad EN↔ES, claves sin uso, palabras prohibidas del gate de copy, enlaces, `og:url` |
| TD-07 | Terceros y URLs sin fijar: Google Fonts por CSS remoto sin versión; `LINKEDIN_URL` embebida; `og:url` y `og:image` fijos a `https://untangle-ai.vercel.app/` | `site/index.html` 14-15, 19, 595 | Baja | Self-host de fuentes; parametrizar el dominio al adoptar uno propio |
| TD-08 | Detección de workspace del engine imprecisa: `Languages: JavaScript` (solo el script inline de la landing), `Nested Root: review` (directorio ignorado por git, D-006, no leído). El lenguaje del aplicativo no está elegido: el `.gitignore` anticipa Python y Node a la vez | Evento `WORKSPACE_SCANNED` de la auditoría; `.gitignore` | Alta para el flujo (no para el código) | `practices-discovery` y `requirements-analysis` leen `Nested Root: review` como ruido y `Languages: JavaScript` como propiedad de la landing; la elección real llega con los ADR de `domain-design` |
| TD-09 | Andamiaje ausente para lo que el PRD promete como Must: README (M17), CI y evals (M8), generador de datos sintéticos (M3, MOD-12), corpus de los tres tenants (solo la estructura de referencia en `docs/reference/estructura-poliza-iso-pap.md`), tests de aislamiento (M9), tests del motor de reglas (M5), manifiesto y toolchain del lenguaje | Raíz del repositorio | Alta para Construcción (no es deuda del código existente) | Lista de lo que Construcción crea desde cero antes de cualquier Bolt: manifiesto y toolchain, `README.md`, generador y corpus, golden sets, CI con evals, tests de aislamiento |
| TD-10 | Documentación del engine desactualizada: `.claude/CLAUDE.md` con el marcador `# Project Name <!-- Replace with your project name -->` sin sustituir y referencias a Bedrock y `.mcp.json` que no aplican; `docs/ai-dlc_guide/` describe v0.1.5 | `.claude/CLAUDE.md` línea 12; `docs/ai-dlc_guide/` | Baja | Sustituir el marcador y podar las instrucciones que no aplican; reescribir la guía capítulo a capítulo (D-001) |

## Implicaciones para `practices-discovery` y Construcción

1. **Línea base cero**: no hay prácticas de código afirmadas ni herramientas de las que inferirlas; `practices-discovery` parte de los defaults de `org.md` (trunk-based, squash-merge, test-after con piso del 80 % y CI antes del merge, deploy on merge a staging con gate manual a producción) y de lo que el PRD ya exige (golden sets en CI que bloquean el merge, tests de aislamiento, tests unitarios de reglas).
2. **El lenguaje decide el tooling**: formatter, linter, runner de pruebas y estructura de paquetes dependen del ADR de lenguaje (Python o Node según las pistas del `.gitignore`); las prácticas deben afirmarse en términos que sobrevivan a esa decisión o esperar a ella.
3. **La landing no entra en el piso de cobertura**: por D-005 y D-013 está fuera del alcance del aplicativo; su único chequeo razonable es el mínimo automatizable de TD-06, y su despliegue lo decide el intent `infra` (D-014).
4. **Reconciliación de la detección** (TD-08): Project Type `Brownfield` es correcto solo para `site/`; el aplicativo es greenfield. `Frameworks: Unknown` y `Build System: Unknown` son correctos.
5. **Deuda que no debe crecer**: cualquier artefacto nuevo del aplicativo nace con manifiesto, lockfile, README, pruebas y CI desde el primer Bolt; el repositorio no tiene nada que heredar.
