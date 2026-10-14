# Dependencies — repositorio `untangle`

Artefacto 7 de 9. Dependencias externas e internas en el commit `3736ad364d8d83526b2d7148e9d3ed8b76851757`. No existe ningún manifiesto de dependencias ni bundler: las dependencias de la landing son recursos remotos declarados en el HTML y un servicio de hosting; las del aplicativo no existen todavía.

## Dependencias externas de la landing

| Dependencia | Tipo | Momento | Versión o fijación | Evidencia | Riesgo si falla |
| --- | --- | --- | --- | --- | --- |
| Google Fonts (`fonts.googleapis.com`, `fonts.gstatic.com`) | Recurso remoto en tiempo de ejecución (CSS y fuentes) | Carga de la página | Sin versión; `display=swap` | `site/index.html` 17-19 | Caída a las pilas de respaldo del sistema; el layout del hilo se recalcula tras `document.fonts.ready`, con un `setTimeout` de 600 ms como red |
| LinkedIn (perfil del autor) | Enlace saliente | Clic del visitante | URL literal en `LINKEDIN_URL` (595) | `site/index.html` 595, 741 | Pierde el único canal de conversión; no afecta a la página |
| Vercel (plataforma y CDN) | Hosting en tiempo de ejecución; CLI en tiempo de despliegue | Siempre; despliegue manual | Plan y versión de CLI no registrados | `site/.vercelignore`, `site/.gitignore`, `site/.vercel/` (ignorado), `og:url` 14-15 | Sitio no disponible; el dominio `untangle-ai.vercel.app` está fijo en los metadatos Open Graph |
| Phosphor Icons | Código de terceros vendorizado (un glifo SVG inline) | Ninguno (inlineado) | MIT, 2023 | `site/PHOSPHOR-LICENSE.txt`, `site/index.html` 9 | Ninguno; obligación de mantener la licencia junto al glifo |
| Navegador del visitante | APIs de plataforma: `IntersectionObserver`, `AbortController`, `fetch` con streams, Pointer Events, `matchMedia`, `localStorage`, `requestAnimationFrame` | Ejecución | Sin polyfills ni detección de features salvo `document.fonts` y `try/catch` en `localStorage` y `setPointerCapture` | `site/index.html` 591-1009 | En navegadores antiguos el script puede fallar en el arranque; sin JS la página degrada mal (TD-05) |

No hay dependencias de tiempo de compilación: no existen `package.json`, lockfiles, `node_modules/` ni ningún paso de build.

## Dependencias internas

**Entre paquetes: ninguna.** El repositorio no tiene paquetes; `site/`, `docs/`, `design-package.md`, `.claude/` y `aidlc/` no se importan entre sí en ningún sentido de código.

**Entre componentes de la landing**: todos viven en el mismo ámbito léxico de `site/index.html`; la matriz de dependencias y el acoplamiento de estado entre módulos están en `component-inventory.md` ("Matriz de dependencias") y el diagrama en `architecture.md`.

**Acoplamientos manuales (no verificables por herramienta)**, que son las dependencias internas que de verdad importan al cambiar algo:

| Origen | Destino | Naturaleza | Registro |
| --- | --- | --- | --- |
| `design-package.md` §5 a §6 (copy EN/ES verbatim) | Diccionario `I18N` en `site/index.html` 601-729 | Duplicación manual; todo cambio de copy se aplica en dos sitios | TD-01 en `code-quality-assessment.md` |
| `VIDEO_BYTES = 5415961` (`site/index.html` 597) | Tamaño real de `site/assets/hero-scrub.mp4` | Constante mantenida a mano; hoy coincide | TD-04 |
| `og:url`, `og:image` (`site/index.html` 14-15) | Dominio de despliegue en Vercel | URL absolutas fijas; cambiar de dominio exige editar el HTML | TD-07 |
| Comentario "the five gates" (885) y `design-package.md` §4 ("400vh") | `GATES` (886, dos entradas) y hero construido a 600 vh | Documentación desactualizada respecto del código | TD-03 |
| Claves `data-i18n` del HTML | Claves de `I18N` | Contrato por nombre sin validación; 118 de 119 claves con consumidor | TD-02 |
| `docs/PLAN-AIDLC.md` y `docs/specs/prd.md` | Landing (`site/`) | La landing debe realinearse al PRD en las semanas 7 y 11 (D-013, M19) | TD-01 |

## Manifiestos y herramientas ausentes

Búsqueda en todo el repo salvo `.git/`, `review/` y `site/.vercel/` (verificada por el desarrollador): `package.json`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `tsconfig.json`, `requirements.txt`, `pyproject.toml`, `Makefile`, `Dockerfile`, `docker-compose*.yml`, `vercel.json`, `.eslintrc*`, `.prettierrc*`, `.editorconfig`, `.nvmrc`, `.python-version`, `.github/`, `.gitlab-ci.yml`, `.circleci/`, `.mcp.json` (mencionado por `.claude/CLAUDE.md` pero inexistente: el engine se configuró con `--mcp none`).

Los únicos archivos de configuración versionados son `.gitignore` (raíz), `site/.gitignore`, `site/.vercelignore` y `.claude/settings.json` (hooks y permisos del engine; según `docs/PLAN-AIDLC.md` 6.3 conserva `AWS_AIDLC_DEFAULT_SCOPE=classic` y ya no lleva variables de Bedrock).

## Dependencias del aplicativo (planeadas, no existentes)

No hay ninguna instalada. Las tecnologías decididas y las hipótesis, con su fuente, están en `technology-stack.md`. Además el PRD 13.4 registra dependencias externas **con fecha** que no son software: decisión de Miguel sobre el tope de la voz (semana 6), voluntarios para grabar inglés (semana 6), tres personas de Medellín para la prueba ciega (semana 6 o 9), dos o tres revisores del ICP A (15 de octubre), una persona del sector asegurador (30 de octubre), analítica de la landing (semana 10) y repositorio público o privado (semana 12); cada una con plan B declarado. Cada proveedor externo tiene sustituto declarado en el plan B de plataforma de `docs/pre_prb/pvb.md` §7 (Whisper por Deepgram, Kokoro o Chatterbox por Cartesia, LiveKit o Pipecat auto-hospedados, Postgres en Docker por Neon o Supabase, Langfuse self-host por su nube, tier gratuito de Gemini o Groq por el de pago).

## Riesgos de dependencia

1. **Fuentes sin fijar ni self-host**: un cambio en Google Fonts altera la tipografía sin ningún commit; mitigable descargando las fuentes a `site/assets/` con `font-display: swap`.
2. **Dominio de Vercel embebido**: adoptar un dominio propio exige editar `og:url` y `og:image` (el comentario "DEPLOY STEP", ya obsoleto, indica que el parche se hizo a mano).
3. **Sin lockfile posible**: al no haber manifiesto no hay reproducibilidad que proteger hoy; el aplicativo deberá introducirla desde el primer Bolt (lockfile del lenguaje elegido, versiones fijadas de proveedores y modelos, `docker compose` con imágenes etiquetadas).
4. **Proveedores de voz y LLM con tiers gratuitos** (R5 y R6 del PRD): el tope de 5 USD y la alerta en 3 USD son la única barrera de costo; el intent `infra` y M20 deben instrumentarla antes de la voz.
