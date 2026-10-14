# Component Inventory — repositorio `untangle`

Artefacto 5 de 9. Inventario completo de los componentes que existen en el commit `3736ad364d8d83526b2d7148e9d3ed8b76851757`. Los nueve encabezados de nivel 3 de este archivo son los nombres canónicos que usa `analyzed.components` en `reverse-engineering-timestamp.md` y los diagramas de `architecture.md`. Ubicación por rango de líneas en `code-structure.md`; deuda referenciada por identificador `TD-nn` de `code-quality-assessment.md`.

## Resumen del inventario

| Componente | Tipo | Ubicación | Salud |
| --- | --- | --- | --- |
| Landing Document Shell | Documento HTML, CSS y arranque del script | `site/index.html` 1-589, 594-598, 741, 1001-1008 | at-risk (mantenibilidad) |
| Hero Scrub Engine | Módulo JS de presentación | `site/index.html` 743-774, 796-909 | healthy |
| I18N Dictionary and Language Switcher | Diccionario y módulo JS | `site/index.html` 601-729, 776-794 | healthy |
| Section Reveal Observer | Módulo JS | `site/index.html` 911-922 | healthy |
| Signature Thread Renderer | Módulo JS y SVG | `site/index.html` 924-965 | healthy |
| Knot Hold Interaction | Módulo JS y SVG | `site/index.html` 967-987 | healthy |
| Reduced Motion Controller | Módulo JS y CSS | `site/index.html` 738, 886-887, 903-907, 989-999; CSS 134, 309-322 | healthy |
| Static Media Assets | Medios estáticos | `site/assets/` (6 archivos), `site/PHOSPHOR-LICENSE.txt` | healthy |
| Vercel Static Deployment | Mecanismo de entrega | `site/.vercelignore`, `site/.gitignore`, `site/.vercel/` (ignorado), `og:url` (14-15) | at-risk (proceso manual sin documentar) |

Escala de salud según la guía del arquitecto: `healthy` (cumple su responsabilidad y no acumula deuda que bloquee cambios), `at-risk` (funciona pero con deuda o acoplamiento que encarece el cambio), `degraded` (falla o requiere intervención). Ningún componente está `degraded`.

**Componentes del aplicativo Untangle: ninguno.** El PRD 9.4 define quince módulos (MOD-01 a MOD-15, resumidos en `business-overview.md`) que son la descomposición planeada, no componentes de este inventario; no tienen código en el repositorio.

## Componentes de la landing

### Landing Document Shell

- **Responsabilidad**: ser el documento completo que el navegador renderiza: metadatos y Open Graph, favicon SVG en `data:` URI, carga de Google Fonts, hoja de estilos inline (tokens de color y tipografía, layout de las nueve secciones, media queries), marcado semántico y accesible (skip link, `nav` con `aria-label`, `main`, secciones `#top` a `#contact`, `footer`), constantes de configuración, reescritura de las anclas `.js-linkedin` y la secuencia de arranque que compone los demás módulos (idioma guardado, `applyLang`, `measure`, `applyHeroMode`, `layoutThread`, `pinToFinalStates`).
- **Ubicación**: `site/index.html` líneas 1-589 (head, CSS, HTML), 594-598 (config), 741 (LinkedIn), 1001-1008 (boot).
- **Depende de**: Google Fonts (hoja remota), Static Media Assets (imágenes `<img>` en `#why` y `#evals`, fondos CSS en `#guardrails` y `#contact`, póster), todos los módulos de script (los arranca).
- **Usado por**: Vercel Static Deployment (es lo que se publica); todos los módulos (les provee el DOM, los ganchos `data-*` y las clases).
- **Salud**: at-risk. Funciona y su accesibilidad es buena (41 atributos `aria-*`, 3 `role`, teclado, `:focus-visible`, objetivos táctiles de 44 px), pero es un solo archivo de 1.011 líneas con copy duplicado respecto de `design-package.md`, contenido desalineado con el PRD y verificación manual (TD-01; TD-02 selectores `.hud`; TD-03 comentario "DEPLOY STEP"; TD-05; TD-06; TD-07 `og:url`).

### Hero Scrub Engine

- **Responsabilidad**: convertir el scroll dentro del hero de 600 vh en la posición del video y en la aparición de las bandas de texto: medición (`measure`, `heroProgress`), bucle `requestAnimationFrame` con lerp normalizado por `dt` que se detiene al converger, `requestSeek` con cola de un solo seek, carga del video como Blob en streaming con anillo de progreso (`loadHeroBlob`, `startBlobFetch`, respaldo `setTimeout` de 4 s si el póster no responde), `AbortController` con watchdog de 20 s y degradación al póster (`failVideo`), partición de titulares para las entradas (`splitEl`, `splitAll`), compuertas de modo estático (`GATES`, `MQLS`, `enableScrub`, `disableScrub`, `applyHeroMode`), observador de visibilidad del hero y `resize`.
- **Ubicación**: `site/index.html` 743-774 y 796-909; configuración en 594-598 (`VIDEO_URL`, `VIDEO_BYTES`, `POSTER_URL`).
- **Depende de**: Static Media Assets (`hero-scrub.mp4`, `hero-poster.jpg`), Reduced Motion Controller (`reduced` y `GATES` deciden si el scrub se activa), helpers compartidos (`clamp`, `smoothstep`, `rng`, `hash`), DOM del hero (`.hero`, `.stage`, `#hero`, `.poster`, `.ring`, `.band` con `data-a`, `data-b`, `data-ramp`, `data-entrance`).
- **Usado por**: I18N Dictionary and Language Switcher (llama a `splitAll`, reinicia `bands` y llama a `updateCaptions`), Landing Document Shell (arranque), Reduced Motion Controller (`applyHeroMode`).
- **Salud**: healthy. Manejo de errores completo para una landing; deuda menor: `VIDEO_BYTES` acoplado a mano al tamaño real del MP4 (TD-04) y comentario "the five gates" con dos compuertas (TD-03). Nota de rendimiento: los 5,4 MB se descargan completos en escritorio y en móvil vertical (decisión registrada en `design-package.md` §5).

### I18N Dictionary and Language Switcher

- **Responsabilidad**: contener el copy EN y ES de toda la página (diccionario `I18N`, 119 claves por idioma con paridad exacta) y aplicarlo: `applyLang` valida la clave (respaldo `en`), fija `<html lang>`, sustituye el texto de los nodos `data-i18n` (en los `.split` solo el `.sr`), `innerHTML` de `data-i18n-html`, `aria-label` de `data-i18n-aria`, `aria-pressed` de los botones del selector, vuelve a particionar los titulares, refresca los captions del hero y persiste la elección; resolución inicial por `localStorage` y luego `navigator.language`.
- **Ubicación**: `site/index.html` 601-729 (diccionario) y 776-794 (`applyLang` y enlace de los botones); arranque en 1001-1002.
- **Depende de**: DOM con atributos `data-i18n*` y el selector `.lang button[data-lang]` con `role="group"` (Landing Document Shell), Hero Scrub Engine (`splitAll`, `bands`, `updateCaptions`, `scrubOn`), `localStorage` (en `try/catch`).
- **Usado por**: Landing Document Shell (arranque), el visitante (botones EN/ES).
- **Salud**: healthy. Paridad de claves verificada; deuda: clave `hud1` sin consumidor en ambos idiomas (TD-02) y copy duplicado con `design-package.md`, de modo que la realineación D-013 debe aplicarse en dos sitios (TD-01).

### Section Reveal Observer

- **Responsabilidad**: animar la entrada de cada sección `.rv` y marcar qué secciones están vivas: un `IntersectionObserver` (umbral 0,12, `rootMargin` inferior de -6 %) añade `in` la primera vez y `done` 1.800 ms después, y alterna `live` mientras la sección intersecta; un listener de `visibilitychange` pone `paused` en `body` cuando la pestaña está oculta para detener las animaciones CSS.
- **Ubicación**: `site/index.html` 911-922.
- **Depende de**: DOM (secciones `.rv`, `body`), CSS que interpreta `in`, `done`, `live`, `paused`.
- **Usado por**: Reduced Motion Controller (`pinToFinalStates` fuerza `in` y `done` en todas las secciones).
- **Salud**: healthy. Sin deuda registrada.

### Signature Thread Renderer

- **Responsabilidad**: dibujar el hilo SVG "firma" que baja desde el final del hero hasta el final de la sección `#evals`: `layoutThread` construye el path (bucles enredados junto a las primeras secciones, luego ondas menores, luego una línea recta), fija `viewBox`, `strokeDasharray` y la altura del contenedor; `threadProgress` y `applyThread` avanzan `strokeDashoffset` y mueven la punta (`#threadTip`) según el scroll con un umbral de cambio de 0,0012; se recalcula en `resize`, tras `document.fonts.ready` y a los 600 ms del arranque.
- **Ubicación**: `site/index.html` 924-965.
- **Depende de**: DOM (`.below`, `#threadSvg`, `#threadPath`, `#threadTip`, `.s5`), Reduced Motion Controller (`reduced.matches` desactiva el dibujo por scroll; `threadPinned` lo fija en 1), Hero Scrub Engine (el listener de `resize` compartido llama a `layoutThread`).
- **Usado por**: Landing Document Shell (arranque), Reduced Motion Controller (`pinToFinalStates`, `unpinFinalStates`).
- **Salud**: healthy. `layoutThread` es una de las tres funciones largas del archivo; sin deuda funcional registrada.

### Knot Hold Interaction

- **Responsabilidad**: el momento interactivo "hold to untangle" de la sección `#try`: mantener presionado el botón del nudo (`#knotBtn`) avanza `holdP` a razón de 1/1.800 ms y soltar lo retrocede a 1/900 ms; el progreso se pinta con la variable CSS `--p`; al llegar a 1 fija `holdDone`, añade `untangled` a la sección y marca `aria-pressed="true"`. Soporta Pointer Events con `setPointerCapture` (en `try/catch`), solo botón principal, `pointercancel` y `pointerleave` como soltar, teclado (Espacio y Enter sin repetición) y bloquea el menú contextual.
- **Ubicación**: `site/index.html` 967-987.
- **Depende de**: DOM (`.s6`, `#knotBtn` con `aria-label` y `aria-describedby`), Reduced Motion Controller (`reduced.matches` impide iniciar; `pinToFinalStates` deja el nudo desatado), helper `clamp`.
- **Usado por**: Reduced Motion Controller (`pinToFinalStates` escribe `holdDone`, `holdP`, `--p`, `untangled`).
- **Salud**: healthy. Sin deuda registrada.

### Reduced Motion Controller

- **Responsabilidad**: respetar `prefers-reduced-motion` y las compuertas de modo estático en vivo y en ambas direcciones: `reduced` (`matchMedia`) consultado por el hilo y el nudo; `GATES` y `MQLS` (apaisado con puntero grueso y altura máxima de 560 px; movimiento reducido) con `applyHeroMode` que activa o desactiva el scrub y hace sólida la barra de navegación; `pinToFinalStates` fija el hilo en 1, marca todas las secciones `in` y `done` y deja el nudo desatado; `unpinFinalStates` revierte el hilo cuando el scrub vuelve; listener `change` que llama a `pinToFinalStates` o `applyHeroMode`. El CSS espeja las compuertas (media query 134) y el modo reducido (309-322).
- **Ubicación**: `site/index.html` 738, 886-887, 903-907, 989-999; CSS 134 y 309-322.
- **Depende de**: `matchMedia` con eventos `change`, Hero Scrub Engine (`enableScrub`, `disableScrub`), Section Reveal Observer, Signature Thread Renderer, Knot Hold Interaction (escribe su estado).
- **Usado por**: Landing Document Shell (arranque: `applyHeroMode` y `pinToFinalStates` si aplica), Hero Scrub Engine, Signature Thread Renderer, Knot Hold Interaction.
- **Salud**: healthy. Es el componente con mayor fan-out (toca cuatro módulos escribiendo su estado directamente); aceptable a esta escala, pero es el punto donde cualquier refactor a módulos separados debería introducir una interfaz.

### Static Media Assets

- **Responsabilidad**: los medios de la landing y la licencia del glifo inlineado, publicados tal cual.
- **Ubicación**: `site/assets/`, `site/PHOSPHOR-LICENSE.txt`; favicon SVG inline en `index.html` línea 9.
- **Depende de**: nada.
- **Usado por**: Landing Document Shell, Hero Scrub Engine, Vercel Static Deployment.
- **Salud**: healthy. Sin deuda funcional; el acoplamiento manual con `VIDEO_BYTES` se registra en el Hero Scrub Engine (TD-04).

| Archivo | Bytes | Uso |
| --- | --- | --- |
| `site/assets/hero-scrub.mp4` | 5.415.961 | Video del hero, cargado bajo demanda como Blob de baja prioridad (`VIDEO_BYTES` debe coincidir con este tamaño) |
| `site/assets/hero-poster.jpg` | 172.343 | Póster del hero (fijado desde JS en `initHeroOnce`) |
| `site/assets/hero-ending.jpg` | 91.030 | `og:image` y fondo de `#guardrails` |
| `site/assets/still-pull.jpg` | 174.310 | `<img loading="lazy">` en `#why` |
| `site/assets/still-row.jpg` | 390.564 | `<img loading="lazy">` en `#evals` |
| `site/assets/still-meet.jpg` | 223.771 | Fondo CSS de `#contact` |
| `site/PHOSPHOR-LICENSE.txt` | 1.071 | MIT, Phosphor Icons 2023, por el glifo "scribble-loop" usado como marca y favicon |

Total 6,3 MB; imágenes JPEG baseline de 1.920 px de ancho, sin variantes `srcset` ni `<picture>` (0 coincidencias), con `width` y `height` explícitos en los `<img>`.

### Vercel Static Deployment

- **Responsabilidad**: publicar `site/` como sitio estático en `https://untangle-ai.vercel.app/` mediante la CLI de Vercel ejecutada por el autor desde `site/`. No hay build, transformación ni configuración de plataforma en el repo: el proyecto enlazado vive en `site/.vercel/` (ignorado por git), `site/.vercelignore` excluye `.env.local` y `.gitignore`, y `site/.gitignore` excluye `.env.local` y `.vercel`. No existe `vercel.json` ni integración git → Vercel; un push a `main` no despliega.
- **Ubicación**: `site/.vercelignore`, `site/.gitignore`, `site/.vercel/` (no versionado, no leído); `og:url` y `og:image` en `index.html` 14-15 fijan el dominio.
- **Depende de**: Landing Document Shell y Static Media Assets (contenido a publicar), cuenta y CLI de Vercel del autor (fuera del repo).
- **Usado por**: el visitante (vía CDN) y las tarjetas de Open Graph.
- **Salud**: at-risk. Funciona, pero es un proceso manual sin README ni CI, con el comentario "DEPLOY STEP" obsoleto en el HTML (TD-03) y el dominio de Vercel fijo en los metadatos (TD-07); el intent `infra` (D-014) decidirá si la landing entra en el pipeline.

## Matriz de dependencias

Lectura: la fila depende de las columnas marcadas. Los terceros (Google Fonts, LinkedIn, Vercel) y el navegador no son componentes del repo y se listan en `dependencies.md`.

| Depende de → | Shell | Hero | I18N | Reveal | Thread | Knot | RMC | Assets | Deploy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Landing Document Shell | – | arranca | arranca | arranca | arranca | arranca | arranca | img, fondos, póster | – |
| Hero Scrub Engine | DOM y `data-*` | – | – | – | – | – | `reduced`, `GATES` | mp4, póster | – |
| I18N Dictionary and Language Switcher | DOM `data-i18n*` | `splitAll`, `bands`, `updateCaptions` | – | – | – | – | – | – | – |
| Section Reveal Observer | DOM `.rv` | – | – | – | – | – | – | – | – |
| Signature Thread Renderer | DOM SVG | `resize` compartido | – | – | – | – | `reduced`, `threadPinned` | – | – |
| Knot Hold Interaction | DOM `#knotBtn` | – | – | – | – | – | `reduced` | – | – |
| Reduced Motion Controller | `nav` | `enableScrub`, `disableScrub` | – | escribe `in`, `done` | escribe `threadPinned` | escribe `holdDone`, `--p` | – | – | – |
| Static Media Assets | – | – | – | – | – | – | – | – | – |
| Vercel Static Deployment | publica | – | – | – | – | – | – | publica | – |

No hay dependencias circulares entre módulos en el sentido de importaciones (todo es un ámbito léxico), pero sí acoplamiento bidireccional de estado entre Reduced Motion Controller y Hero, Thread y Knot; se documenta como el punto de corte si el archivo se divide.
