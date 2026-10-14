# API Documentation — repositorio `untangle`

Artefacto 4 de 9. Superficies de API externas e internas de lo que existe en el commit `3736ad364d8d83526b2d7148e9d3ed8b76851757`. Conclusión: **no hay API**. La landing de `site/` no tiene backend, endpoints, formularios ni almacenamiento; sus únicas superficies son enlaces salientes, recursos de terceros y un contrato interno entre el HTML y el script. Las APIs del aplicativo no existen y se definen en `contract-design`.

## Superficies externas (salientes)

| Superficie | Tipo | Ubicación en `site/index.html` | Detalle |
| --- | --- | --- | --- |
| LinkedIn | Enlace de navegación (sin integración) | Constante `LINKEDIN_URL` (595); cinco anclas `.js-linkedin` reescritas al arrancar (741): nav (346), hero (372, 383), sección `#contact` (574); la FAQ (563) lo menciona en texto | `https://www.linkedin.com/in/miguelzuluaga/` abierto en pestaña nueva con `rel="noopener"`. Único canal de conversión. Sin OAuth, sin widget, sin píxel |
| Google Fonts | Recurso remoto (CSS y fuentes) | `preconnect` a `fonts.googleapis.com` y `fonts.gstatic.com` (17-18); `<link rel="stylesheet">` (19) | Familias Bricolage Grotesque (opsz 12..96, pesos 300 y 500), IBM Plex Sans (400, 500), JetBrains Mono (400), `display=swap`. Sin versión fijada ni self-hosting; pilas de respaldo declaradas en el CSS |
| Open Graph y Twitter Card | Metadatos consumidos por terceros al compartir la URL | `og:title`, `og:description`, `og:type`, `og:url`, `og:image` (11-15), `twitter:card` (16) | `og:url` e `og:image` absolutas y fijas a `https://untangle-ai.vercel.app/` (deuda TD-07 en `code-quality-assessment.md`) |

No hay ninguna petición saliente iniciada por script hacia otro origen: el único `fetch` del código es al mismo origen (tabla siguiente). Verificado por el desarrollador: sin scripts externos, sin analítica, sin píxeles, sin cookies, sin banner de consentimiento.

## Superficies internas

| Superficie | Tipo | Ubicación | Contrato |
| --- | --- | --- | --- |
| `assets/hero-scrub.mp4` | `fetch` al mismo origen | `loadHeroBlob` (854-878): `fetch(VIDEO_URL, {priority:'low', signal})` | Respuesta leída como `ReadableStream` para pintar un anillo de progreso (usa `Content-Length` o `VIDEO_BYTES = 5415961` como respaldo), convertida en Blob y asignada al `<video>` con `URL.createObjectURL`. Falla hacia el póster si `res.ok` es falso, si el watchdog de 20 s aborta o si el `<video>` emite `error` |
| `localStorage['untangle-lang']` | Estado persistente del visitante | Lectura en el arranque (1001), escritura en `applyLang` (791), ambas en `try/catch` | Valor `en` o `es`. Es el único dato que la landing guarda; no hay cookies ni `sessionStorage` |
| Atributos `data-i18n`, `data-i18n-html`, `data-i18n-aria`, `data-lang` | Contrato HTML ↔ script para el copy | HTML (323-589) y `applyLang` (777-793) | La clave debe existir en `I18N[lang]`; 118 de las 119 claves por idioma tienen un nodo consumidor (`hud1` no) |
| Atributos `data-entrance`, `data-a`, `data-b`, `data-ramp` | Contrato HTML ↔ script para las bandas del hero | Bandas `.band` del hero y `bands` (797) | Definen la ventana de progreso en la que cada banda es visible y su tipo de entrada (`drift`, `rise`, `weave`, `grid`) |
| Anclas de navegación por fragmento | URL interna | `#main` (skip link), `#top`, `#why`, `#how`, `#voice`, `#guardrails`, `#evals`, `#try`, `#faq`, `#contact` | Navegación con `scroll-behavior: smooth`; es la única "ruta" de la página. No hay router ni parámetros de consulta |

## Lo que la landing no expone (verificado)

- Sin endpoints HTTP propios: no hay servidor, funciones serverless ni `api/` (tampoco `vercel.json` que las declare).
- Sin formularios: ningún `<form>`, ningún `mailto:`, ningún teléfono; el contacto es solo el enlace a LinkedIn.
- Sin autenticación, sesiones ni cookies.
- Sin analítica ni seguimiento de terceros (la analítica de la landing es una dependencia pendiente de Miguel, PRD 13.4).
- Sin `robots.txt`, `sitemap.xml`, `manifest.json`, service worker ni página 404 personalizada en `site/` (el directorio versionado contiene solo `index.html`, `assets/`, la licencia y los dos archivos de ignore).
- Sin feeds, webhooks, SDKs ni claves embebidas: el único identificador en el código es la URL pública del perfil de LinkedIn.

## APIs del aplicativo (no existen todavía)

El PRD describe superficies que tendrán contrato cuando se construyan: chat público por tenant y vista de comparación (MOD-04, pantallas 2 y 3 de 9.5), bandeja del ajustador con aprobar o rechazar que reanuda el grafo (MOD-08, pantallas 4 y 5), dashboard de telemetría (MOD-10), reporte de evals como artefacto de CI (MOD-11), tokens simples con claim de tenant (MOD-09) y los contratos de entrada y salida de los cuatro nodos (F2.2). Ninguno tiene código, esquema ni especificación de endpoints en el repositorio; se diseñan en `contract-design` a partir de `domain-design` y no deben inferirse de la landing.
