# Plan de generación de código — U6 `web-shell`

Lo que se construye: la base de la interfaz (sistema de diseño en dos modos,
idioma, cliente de la API, inicio, siete páginas de estado, arnés de
accesibilidad) y la parte servida del proceso (salud, directorio del sitio,
cabeceras de seguridad, errores con la forma de C-01, estáticos desde el mismo
origen) más la telemetría de activación.

Fuentes: `../functional-design/` (44 reglas, flujos F1 a F10),
`../nfr-requirements/` (objetivos medibles), contratos C-01, C-02, C-21, C-24,
C-25 y C-28, y las maquetas M1 y M11.

**Modo ligero (DP-12).** Esta unidad no pasa por NFR Design ni por
Infrastructure Design. Las dos decisiones que esas etapas debían tomar para U6
se toman aquí, en la sección "Decisiones de este plan", y quedan aprobadas con
el plan.

## Decisiones de este plan

| # | Decisión | Por qué |
| --- | --- | --- |
| CG-U6-1 | El paso que aplica el modo antes de pintar es un archivo propio, pequeño y bloqueante en la cabecera (`/theme-boot.js`), no un script en línea | La política de contenido queda en `script-src 'self'` sin excepciones ni huellas que regenerar. Cumple SEC-U6.1 (sin `unsafe-inline`) por un camino más simple que el que describía `security-requirements.md`, que autorizaba el script en línea por su huella; el costo es una petición más en la carga, de menos de 1 KB |
| CG-U6-2 | Política de seguridad de contenido: `default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'` | Era de NFR Design (ADR-002). Todo desde el propio origen (SEC-U6.2). El arnés falla con cualquier violación registrada en la consola |
| CG-U6-3 | El resto del conjunto de cabeceras: `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` que niega cámara, micrófono, geolocalización y pagos, y `Strict-Transport-Security` solo cuando la petición llega por HTTPS | SEC-U6.1. El micrófono lo abrirá U16 en este mismo conjunto |
| CG-U6-4 | `brand` y `character_key` entran **opcionales** a `TenantConfig`, sin subir `config_version` | Hallazgo R-02 de la revisión del diseño funcional: C-25 exige que una clave nueva llegue opcional y con valor por defecto. Sin marca, la fila usa los tokens de Untangle y no dibuja monograma; sin carácter, omite esa línea (BR4.2). Las tres aseguradoras la traen igual |
| CG-U6-5 | Los estáticos compilados viven en `app/frontend/dist/` y el proceso los sirve si el directorio existe; sin compilar, las rutas de la interfaz responden la página de servicio no disponible de la API | Era de Infrastructure Design. El arranque del camino de los 15 minutos (NFR21) no necesita compilar la interfaz |
| CG-U6-6 | Los enlaces externos (`readme_url`, `video_url`) se leen del entorno como variables opcionales, declaradas en `.env.example` sin valor | BR4.4: sin variable no hay enlace |
| CG-U6-7 | La capacidad nueva de la raíz de composición se llama `surfaces`, igual que las tres que ya existen (`router`, `purgers`, `eval_targets`) | F8: montar una superficie no toca ningún archivo de U6 (SCALE-U6.1) |
| CG-U6-8 | El `/health` de U1 se retira y su prueba de integración pasa a `/api/health/live` y `/api/health/ready` | FD-U6-6 |

## Pasos

La unidad es de la **rama determinista**: cada capa se implementa y a
continuación se escriben y corren sus pruebas, antes de pasar a la siguiente.
Historias: US1.33 (accesibilidad y teléfono) y US5.16 (demo despierta).

### Bloque A — Estructura y pruebas listas

- [x] **Step 1 — Estructura y configuración de producción.** Andamiaje de Vite
  y React en `app/frontend/` (`index.html`, `src/main.tsx`, `src/app/`,
  `src/pages/`, `src/shared/`), configuración de Tailwind con los tokens, y los
  módulos vacíos del servidor: `server/web.py`, `server/problems.py`,
  `server/security_headers.py`, `server/health.py`, `server/site.py`,
  `server/surfaces.py` y el paquete `telemetry/activation/`. Dependencias nuevas
  de `tech-stack-decisions.md` en `package.json` y `pnpm-lock.yaml`, con la
  lista permitida de scripts de instalación. (US1.33, US5.16)
- [x] **Step 2 — Pruebas ejecutables antes de la primera prueba.** Tareas nuevas
  en `mise.toml`: `test:u6`, `a11y`, `web:build`, `browsers:install` y
  `activation:report`; configuración de Playwright en `app/frontend/e2e/`;
  Vitest con `jsdom`. Se comprueba que `mise run test:u6` corre (con cero
  pruebas propias todavía) y se deja el comando exacto en
  `unit-test-instructions.md`.

### Bloque B — Datos (capa 1)

- [x] **Step 3 — Tablas de activación.** Migración
  `u6_web_0001_activation_tables.py`: `activation_progress` (aseguradora,
  resumen de la clave del navegador, hito, hora; única por las tres primeras) y
  `activation_daily` (aseguradora, día, hito, conteo; única por las tres
  primeras). Las dos con aislamiento forzado y su política; solo el avance lleva
  la marca de dato de visitante. (BR8.1, BR8.2, NFR10.5, NFR19.3)
- [x] **Step 4 — Pruebas de la capa de datos.** `mise run rls:check` en verde;
  una prueba de aislamiento por tabla; la prueba de columnas prohibidas contra
  `personal_data_column_names` (NFR11.7); las restricciones de unicidad.

### Bloque C — Acceso a datos (capa 2)

- [x] **Step 5 — Repositorio de activación.** En una transacción por la sesión
  única de U2: inserta el avance si no existía y, solo entonces, suma uno al
  conteo del día. (BR8.1)
- [x] **Step 6 — Pruebas del repositorio.** Tres registros del mismo hito dan un
  solo conteo; dos aseguradoras no se ven; el purgador borra el avance y deja el
  conteo. (BR8.1, BR8.2)

### Bloque D — Lógica (capa 3)

- [x] **Step 7 — Servicio de activación.** `record_milestone` que no registra
  nada para el chequeo periódico ni para el corredor (BR8.4), que ante un fallo
  emite el evento en la traza y devuelve sin lanzar (BR8.3); purgador en el
  registro de la raíz de composición (BR8.2); comando `activation:report` con
  el conteo por día, aseguradora e hito (OBS-U6.3, BR8.5).
- [x] **Step 8 — Superficies, salud y directorio.** `SurfaceSpec` con la lista
  cerrada de siete superficies (sin la cotización), la capacidad `surfaces` en
  la raíz de composición que impide arrancar si falta la sonda (BR5.2); salud
  de vivo y de listo con sondas en paralelo y tiempo máximo por sonda, 503 solo
  sin base o sin configuración (BR5.1, BR5.3, NFR16.2); `checks.providers` con
  nombres de uso y conteo (FD-U6-6); directorio del sitio con las aseguradoras,
  las superficies públicas montadas y los enlaces configurados (BR4.1, BR4.2,
  BR4.4).
- [x] **Step 9 — Configuración de aseguradoras.** `brand` y `character_key`
  opcionales en `TenantConfig` (CG-U6-4); los tres `tenant.yaml` con su acento
  por modo y su monograma; `tenant.schema.json` regenerado con
  `mise run contracts:gen`. (BR1.6)
- [x] **Step 10 — Pruebas de la lógica.** De cinco a ocho por componente:
  activación, registro de superficies (con sonda, sin sonda, montaje sin tocar
  U6), salud (base caída, configuración ausente, sonda lenta, sonda que lanza,
  puertos de proveedor espiados), directorio (sin superficies, con una, sin
  enlaces, sin marca). (NFR16.2, NFR16.4, NFR16.6, SCALE-U6.1, SCALE-U6.3,
  REL-U6.4, SEC-U6.3, SEC-U6.9)

### Bloque E — API y proceso servido (capa 4)

- [x] **Step 11 — Rutas y conducta del proceso.** `/api/health/live`,
  `/api/health/ready` y `/api/site`; errores de la API como
  `application/problem+json` con `code` y `trace_id`, incluido `internal` sin
  detalle y `not_found` para cualquier ruta desconocida bajo `/api` (BR6.1,
  BR6.4); cabecera de traza en toda respuesta; cabeceras de seguridad de
  CG-U6-2 y CG-U6-3 en toda respuesta (BR6.2); estáticos desde el mismo origen
  con caché larga para los archivos con huella y sin caché para la página de
  entrada (BR6.3); retorno a la aplicación para las rutas de la interfaz
  (CG-U6-5); variables opcionales de enlaces (CG-U6-6); se retira `/health`
  (CG-U6-8).
- [x] **Step 12 — Esquema y cliente generado.** `app/contracts/openapi.json`
  generado desde FastAPI y el cliente de TypeScript con `@hey-api/openapi-ts` en
  `app/frontend/src/shared/api/`, los dos dentro de `mise run contracts:gen` y
  de la comprobación de deriva. (BR3.1, TECH-U6.2)
- [x] **Step 13 — Pruebas de la API.** Cabeceras en las tres ramas y en los
  errores (SEC-U6.1), forma de los errores (SEC-U6.4, BR6.4), `/api` desconocido
  como JSON, retorno a la aplicación, cabeceras de caché, traza en toda
  respuesta (OBS-U6.2), salud de listo en 1 segundo en p95 (NFR16.4) y la
  prueba de integración de U1 migrada a la salud nueva.

### Bloque F — Interfaz (capa 5)

- [x] **Step 14 — Tokens y modo.** Tokens de color de los dos modos como
  variables de CSS, tipografía, espaciado, movimiento y capas de
  `design-system-mapping.md`; acento de aseguradora inyectado desde su
  configuración; fuentes servidas desde el propio origen (FD-U6-4); el paso de
  modo antes de pintar (CG-U6-1). (BR1.1 a BR1.6)
- [x] **Step 15 — Proveedores y cliente.** Modo, idioma con `t()` tipado sobre
  el catálogo (BR2.1 a BR2.4), caché de datos solo en memoria (BR3.5),
  anunciador único (BR7.5), traducción de errores por una sola tabla con rama
  por defecto (BR3.2 a BR3.4) y la máquina de estados de la espera (sección 2.1
  del diseño funcional, BR5.4).
- [x] **Step 16 — Primitivas.** Las nueve primitivas generadas con shadcn/ui y
  tematizadas con los tokens, con sus siete estados y 44 × 44 cuando son
  táctiles; íconos de Phosphor y los tres monogramas. (BR7.3, BR7.7)
- [x] **Step 17 — Marco y pantallas.** `AppShell` con el enlace para saltar al
  contenido, la barra superior, los selectores de idioma y de modo y la
  navegación de superficies montadas; `HomePage` con sus cuatro estados;
  `StatusPage` con sus siete tipos; `DemoNotice` para las unidades de canal;
  rutas `/`, `/status/$kind` y "no encontrada". (BR2.5, BR4.1 a BR4.5, BR5.5 a
  BR5.7, BR7.4)
- [x] **Step 18 — Textos.** Todas las claves nuevas en `es.yaml` y `en.yaml`,
  con paridad y consumidor, y el módulo tipado de claves regenerado. (BR2.3,
  NFR20.1)
- [x] **Step 19 — Pruebas de componentes.** Resolución del modo y
  almacenamiento ilegible (BR1.1, BR1.4, REL-U6.2), idioma inicial (BR2.1,
  BR2.2), idioma por bloque (BR2.4), traducción de todos los códigos de C-01 más
  `unknown` (REL-U6.1), la espera con reloj simulado (NFR16.5), el inicio en sus
  cuatro estados sin datos inventados, las siete páginas en los dos idiomas, el
  anunciador que dice una sola vez lo transmitido, y el almacenamiento que solo
  guarda preferencias.
- [x] **Step 20 — Arnés de accesibilidad.** Registro de pantallas visitables
  con su prueba de completitud contra el enrutador (BR7.1); en Chromium, para
  cada pantalla en los dos idiomas y los dos modos: analizador automático con
  hallazgos serios o críticos como fallo en pantallas de visitante (BR7.2),
  360 × 640 sin desplazamiento horizontal y controles de 44 × 44 (BR7.3),
  recorrido con teclado (BR7.4), movimiento reducido (BR7.6), cero peticiones a
  terceros (SEC-U6.2), almacenamiento solo con preferencias (SEC-U6.5); en
  Firefox y WebKit, la prueba de dibujo. Escenarios de tiempo en el perfil de
  teléfono: página de espera en menos de 3 s con 200 KB o menos antes de ella
  (NFR16.3, PERF-U6.1) e inicio en 4 s o menos (PERF-U6.2). El paso publica su
  duración (PERF-U6.3).

### Bloque G — Entorno y compuertas

- [x] **Step 21 — Guion de verificación y flujo.** El paso 5 de
  `scripts/verify.sh` agrega `mise run a11y` después de las pruebas, sin cambiar
  el número de pasos; el flujo de GitHub Actions instala los navegadores con
  `mise run browsers:install`, fuera de `bootstrap` (NFR21.3).
- [x] **Step 22 — Dependencias y licencias.** `app/frontend/DEPENDENCIES.md` con
  una línea por dependencia (qué hace, por qué no alcanza la plataforma,
  licencia, y la de cada fuente aparte) y la comprobación nueva en
  `mise run supply:check` que falla nombrando la que falte (TECH-U6.1);
  `mise run audit` en verde (SEC-U6.7).
- [x] **Step 23 — Cobertura.** La configuración de Vitest mide el código nuevo;
  `mise run cov` en 80 % o más agregado, sin exclusiones nuevas (NFR18.4).
- [x] **Step 24 — Guion completo.** `scripts/verify.sh` en verde de punta a
  punta en local.

### Bloque H — Documentación y trazabilidad

- [ ] **Step 25 — Resumen, manifiesto y trazabilidad.** `code-summary.md`,
  `source-manifest.json` con cada ruta creada, cambiada o generada, y
  `traceability.json` con los doce criterios, las 44 reglas y los objetivos
  medibles de U6, cada `OK` apuntando a un archivo que existe.

## Qué no entra

- Las pantallas de cada capacidad (U13, U14, U16, U17, U22) y su registro en el
  arnés.
- La consulta de disponibilidad de la voz en el inicio (hallazgo R-04 del diseño
  funcional): la agrega U16 o U17 sobre la acción "Llamar".
- El chequeo cada cinco minutos, su alerta y el hospedaje (intent `infra`).

## Testing Contract

```json
{
  "version": 1,
  "methodology": "custom",
  "source": "team",
  "ordering": "Clasifica cada unidad en una de dos ramas y no dejes ninguna sin rama. Rama evaluada: toda unidad cuyo comportamiento observable aparece en la tabla de criterios de PRD 11.2 o que realiza uno de M1, M4, M5, M6, M8, M9, M13 o M15; para ella se escribe o se extiende primero su caso de golden set (DS-2, DS-3, DS-5, DS-6) con su identificador estable, su criterio de aceptación y su veredicto esperado, se corre y se comprueba que falla, se implementa, y se vuelve a correr hasta que pase. Rama determinista: toda unidad restante sin excepción, recorrida capa por capa en el orden Data model / database behavior, Repository / data access, Business logic, API / endpoint, Frontend behavior; se implementa la capa y a continuación se escriben y corren las pruebas de esa capa antes de pasar a la siguiente. Una unidad de la rama evaluada usa además la rama determinista para las capas que la sostienen. El runner de pruebas, la configuración de cobertura y el corredor de evals se dejan instalados y ejecutables antes del primer caso de cualquiera de las dos ramas, porque no existe ninguno que verificar.",
  "scope": "classic",
  "test_strategy": "standard",
  "project_type": "brownfield",
  "applicable_notes": [
    {
      "layer": "org",
      "text": "We treat tests as a first-class deliverable in every Bolt. The specific\nmethodology (TDD, BDD, ATDD, or classic test-after) is affirmed at\npractices-discovery and recorded in `team.md` under this heading with explicit\n`Methodology` and `Ordering` fields; Code Generation resolves those fields\nindependently from coverage, tooling, and scope notes.\n\nWhen no posture has been affirmed, our default per scope is:\n- **Methodology**: test-after\n- **Ordering**: implement each applicable testable layer, then write and run\n  that layer's tests.\n- `mvp`, `enterprise`, `feature`, `infra`, `classic` add an 80% line-coverage\n  floor and CI execution before merge.\n- `bugfix`, `security-patch` add a targeted regression for the specific\n  bug/vulnerability and require the existing suite to remain green.\n- `express` uses the Minimal strategy: requirement-driven unit tests (one per\n  requirement, with a happy-path floor per component); existing tests remain\n  green.\n- `poc`, `refactor`, `workshop` add no extra new-test floor and require the\n  existing suite to remain green.\n\nThe active `Test Strategy` still applies in every scope and determines test\nvolume/types. Scope floors are additive; they never reduce or replace the\nselected strategy.\n\nBuild and Test verifies defined coverage floors and affirmed quality targets;\nthey may not be weakened to make a step pass.\n\nAffirm a stricter posture in `team.md` if the team commits to one."
    },
    {
      "layer": "team",
      "text": "- **Methodology**: custom\n- **Ordering**: Clasifica cada unidad en una de dos ramas y no dejes ninguna sin rama. Rama evaluada: toda unidad cuyo comportamiento observable aparece en la tabla de criterios de PRD 11.2 o que realiza uno de M1, M4, M5, M6, M8, M9, M13 o M15; para ella se escribe o se extiende primero su caso de golden set (DS-2, DS-3, DS-5, DS-6) con su identificador estable, su criterio de aceptación y su veredicto esperado, se corre y se comprueba que falla, se implementa, y se vuelve a correr hasta que pase. Rama determinista: toda unidad restante sin excepción, recorrida capa por capa en el orden Data model / database behavior, Repository / data access, Business logic, API / endpoint, Frontend behavior; se implementa la capa y a continuación se escriben y corren las pruebas de esa capa antes de pasar a la siguiente. Una unidad de la rama evaluada usa además la rama determinista para las capas que la sostienen. El runner de pruebas, la configuración de cobertura y el corredor de evals se dejan instalados y ejecutables antes del primer caso de cualquiera de las dos ramas, porque no existe ninguno que verificar.\n\nLa metodología es `custom` porque la cadencia es mixta a propósito, y decir\n`tdd` o `test-after` a secas sería falso. Lo que el PRD evalúa (extracción,\ncitación, adherencia a la guía de voz, conducta adversarial) se define **antes**\nde implementarlo, porque está prohibido publicar una métrica sin su golden set\n(P5) y porque un ataque de red-team exitoso se convierte en caso de DS-6 que\ndebe pasar. El código determinista que sostiene esos comportamientos se prueba\npor capa, con la prueba escrita junto a la capa y no semanas después.\n\n**Punto de partida.** No existe ningún runner de pruebas, ninguna configuración\nde cobertura y ningún corredor de evals: la línea base es cero. El flujo declara\n`Project Type: Brownfield` porque la landing existe, pero **el aplicativo es\ngreenfield y su andamiaje se crea, no se verifica**. El primer Bolt que toque\ncódigo de aplicación deja instalados y ejecutables, antes de su primera prueba,\nel runner del lenguaje, la configuración de cobertura y el corredor de evals de\nun solo comando (M17), y registra ese comando exacto en el README.\n\n**Piso de cobertura.** 80 % de líneas **agregado** sobre el código del\naplicativo, con piso del 80 % también en los módulos críticos: motor de reglas,\nverificador de citas, aislamiento por tenant, esquema del caso y **redacción de\ndatos personales** (esta última añadida por decisión de Miguel el 2026-09-20:\nsu compuerta detiene la entrega con un solo hallazgo y su fallo es silencioso,\nporque una redacción rota no rompe ninguna pantalla ni levanta ningún error). La interfaz y\nlos adaptadores de proveedor pueden quedar por debajo mientras el agregado se\ncumpla. La medición se hace con la herramienta de cobertura del lenguaje\nelegido, con un umbral configurado en el manifiesto que **haga fallar el\ncomando** cuando no se alcanza, y ese comando es el mismo que corren\n`build-and-test` y el flujo de GitHub Actions. Se excluyen del cálculo, mediante\nuna **lista de exclusión versionada** en la configuración: la landing (`site/`,\nfuera del alcance por D-005 y D-013), el corpus y los datasets generados, y las\nmigraciones. El piso es obligación propia del equipo, con su comando y su lista;\nno se apoya en que el scope lo active, y no se baja para que un paso pase.\n\n**Datos de prueba.** Los casos de los golden sets viven versionados en el\nrepositorio como archivos de datos, **un archivo por caso**, con identificador\nestable (`DS-2/es/017`), nunca generados en tiempo de corrida. El generador\nsintético (MOD-12) es determinista y sembrado: su salida (corpus DS-1, fixtures\nDS-8) se regenera solo con un comando explícito y el resultado se commitea, de\nmodo que dos corridas del mismo commit vean el mismo corpus. Los identificadores\nson la moneda de todo el sistema: el reporte por caso, el diff contra la línea\nbase, la sección \"Cómo falla\" del README y los casos nacidos de un red-team o\ndel muestreo del chat en vivo los usan sin traducción.\n\n**Forma de las pruebas.** Cada prueba es independiente del orden de ejecución y\nde estado compartido, y se puede correr sola. Cada prueba afirma un\ncomportamiento, no una implementación: se prueba lo que el requisito exige, no\ncómo se codificó. Ninguna prueba pasa con independencia de la implementación.\nCada caso de red-team exitoso entra a DS-6 con el identificador `RT-<n>` en su\nnombre, y el hallazgo no se cierra hasta que ese caso pase (PRD 11.4).\n\n**Pruebas deterministas no negociables**, cada una atada a un Must:\n\n- Motor de reglas por tenant: reglas versionadas, cada una con su test unitario (M5).\n- Verificador exacto de citas: existencia, pertenencia al tenant y a la póliza, vigencia (M4, P2).\n- Aislamiento entre tenants: RLS en la base de datos **y** punto único de adquisición de sesión que fija el `tenant_id` antes de devolverla, con fixtures que provocan colisiones detectables y una aserción sobre el esquema que falla si alguna tabla del aplicativo carece de RLS o de política (M9, F9.1, F9.4, DS-8).\n- Redacción de PII en cada punto de salida, con un segundo detector de **mecanismo distinto** al primero y reconocedores propios para placa, cédula, teléfono y número de póliza en los dos idiomas; se mide por idioma y por tipo de entidad, nunca como promedio (M6, RT-14, RT-15, P12).\n- Esquema del caso: JSON válido, y solo se citan identificadores recuperados (M1).\n- Chequeos de contenido con identificador estable (frases prohibidas, ausencia de texto de cláusula de ISO o ACORD, paridad de claves EN↔ES), para que aparezcan en el reporte por caso y en el diff contra la línea base como cualquier otra prueba.\n\n**Golden sets en cada corrida del flujo**: DS-2 (60 conversaciones de texto, 30\npor idioma), DS-3 (40 preguntas de citación con distractores) y DS-6\n(adversarial). Corren en el tier gratuito del LLM, con duración objetivo de 10\nminutos o menos, y producen un reporte por caso, por criterio y por idioma, con\nenlace a su traza.\n\n**Compuertas duras** (`[bloquea]` en PRD 11.2): cero citas inexistentes; cero\nturnos que afirmen cobertura, montos o culpa, o den consejo legal; cero\nhallazgos de seguridad (PII en trazas, fuga entre tenants, adversarial). Son\npasa o falla por caso y un solo fallo detiene la entrega. Cada criterio\n`[bloquea]` y cada umbral cuantificado del Segmento 10 se registra además como\nobjetivo medible en `nfr-requirements`, con identificador estable, valor\nesperado y el comando que produce su valor real, para que aparezca como fila\npropia en la `## Target Verification Matrix` de `build-and-test`; ningún\ncriterio `[bloquea]` se cierra con `N/A`.\n\n**Tipos de prueba obligatorios pese a la estrategia.** La estrategia activa es\n`Standard` (cinco a ocho pruebas por componente; unitarias más integración en\nlas fronteras). Además, y con independencia de la estrategia, `build-and-test`\ngenera instrucciones de prueba de **seguridad** (aislamiento entre tenants,\nredacción de PII en cada punto de salida, casos adversariales de DS-6) y de\n**rendimiento** (latencias de turno y de parada sobre DS-5, duración de la\ncorrida de evals), porque el PRD las marca como compuertas duras y como umbrales\npublicables, no como aspiraciones.\n\n**Definición de regresión.** Bloquea la entrega: (a) cualquier compuerta dura en\nrojo, sin excepción ni promedio; (b) en métricas de **denominador grande**\n—extracción por campo, fidelidad de la lectura de confirmación, latencias— una\ncaída mayor de 2 puntos porcentuales frente a la línea base versionada sin\nexplicación escrita; (c) en métricas de **nivel de caso** sobre DS-2, DS-3 y\nDS-6, donde el denominador por idioma es pequeño, **cualquier caso que pase a\nfallar** sin explicación escrita. La explicación nombra los identificadores de\nlos casos que cambiaron y su causa raíz según la taxonomía del PRD 11.3; una\nexplicación que no nombre casos no cuenta como explicación.\n\nEl umbral porcentual se reserva para el denominador grande porque en los\nconjuntos pequeños no distingue señal de ruido:\n\n| Dataset | Casos por idioma | Cuánto mueve un caso |\n| --- | --- | --- |\n| DS-2 (golden set de texto) | 30 | 3,3 pp |\n| DS-3 (citación) | 20 | 5,0 pp |\n| DS-6 (adversarial, v0) | 10 | 10,0 pp |\n\n**Determinismo de la corrida.** La corrida de evals fija todo lo que se pueda\nfijar: temperatura en 0 y semilla fija donde el proveedor lo permita, versión\ndel modelo anclada por identificador exacto (nunca un alias móvil), prompts y\nrúbricas versionados en el repositorio, y el respondedor del asegurado por\nreglas indexado por campo del PRD 11.1. Cuando un caso siga siendo inestable\nentre corridas idénticas, se marca como inestable con su identificador en un\narchivo versionado, deja de contar para la compuerta, se reporta aparte con esa\netiqueta y su estabilización se abre como trabajo; nunca se borra del set (P5).\n\n**Compuerta en rojo por causa ajena al cambio.** Cuando la compuerta se pone\nroja por una caída del proveedor, un cambio de versión del modelo o una cuota\nagotada, se registra la causa y el identificador de la corrida, la corrida se\nmarca como **no comparable** y se repite; si sigue roja, bloquea. **El umbral no\nse toca nunca** y la marca queda en el registro. Una compuerta que no se pudo\nejecutar se declara \"no medida\" en el reporte, nunca se omite.\n\n**Juez descalibrado.** Los veredictos del juez (LLM) solo cuentan mientras sus\ndos tasas contra las etiquetas humanas de DS-7, la de fallos que detecta (TNR) y\nla de aciertos que confirma (TPR), medidas por criterio y por idioma sobre la\npartición de prueba y con intervalo de confianza, estén en el umbral que fija\n`nfr-requirements` (decisión de Miguel del 2026-09-17, que reemplaza el 85 % de\nacuerdo; ADR-014). Si caen por debajo, o si cambia el modelo del juez o la\nrúbrica sin recalibrar, sus\nveredictos dejan de contar: los criterios que dependen de él se reportan como\n\"no medida\" con esa causa, no bloquean, y la recalibración se abre como trabajo\ncon fecha. Las compuertas duras juzgadas por código —citas inexistentes,\naislamiento, PII en trazas, esquema— no dependen del juez y siguen bloqueando.\n\n**Presupuesto de la corrida.** La corrida de evals de texto tiene un objetivo de\n10 minutos y su duración se mide y se publica como métrica desde la línea base\nv0 (Segmento 10.5). El corredor admite ejecutar un subconjunto declarado y\nreproducible; si la corrida completa deja de caber en el presupuesto o en los\nlímites del tier gratuito, la compuerta corre ese subconjunto declarado —nunca\nse apaga— y la corrida completa pasa a ser obligatoria por hito y antes de\npublicar cualquier línea base.\n\n**Dónde corre la compuerta.** El ejecutor autoritativo es el flujo de GitHub\nActions sobre `main`, invocando el guion único de verificación. Dentro de este\nintent, la etapa `build-and-test` ejecuta ese mismo comando. Las prácticas no\ncambian cuando cambia el ejecutor: solo cambia quién lo dispara.\n\n**Lo que no corre en cada corrida**: los golden sets de audio (DS-5, 20\ngrabaciones) corren por hito, no por cambio, porque el costo de voz está topado\ny las grabaciones dependen de terceros.\n\n**Paridad por idioma**: los mismos casos, las mismas métricas y las mismas metas\nen español e inglés; el reporte muestra los dos lados a lado y nunca un promedio\ncombinado (P12).\n\n**Herramientas**: el runner de pruebas del lenguaje elegido, más un corredor de\nevals propio con un juez propio calibrado para la compuerta (decisión de Miguel\ndel 2026-09-17, ADR-014; reemplaza \"`promptfoo` o `DeepEval`\"), `promptfoo` solo\npara red-teaming por hito y Langfuse para la anotación humana. El corredor de evals se\ninvoca con un solo comando y ese comando está en el archivo de tareas y en el\nREADME (M17)."
    },
    {
      "layer": "project",
      "text": "- Los criterios de aceptación se escriben en Gherkin con las palabras clave en español (Dado / Cuando / Entonces / Y), cada paso empieza con la palabra clave sin coma y ningún \"Dado\" depende de lo que dejó otro criterio: es el formato Given/When/Then de la regla de fase, Gherkin lo reconoce y las pruebas se automatizan sin traducirlo. (learned 2026-09-16) \n\n- Las unidades que realizan M8 sin conducta propia que evaluar (corredor de evaluaciones, reporte, respondedor simulado y compuerta) siguen en la rama evaluada, pero su caso previo es una corrida de casos ya existentes de DS-2, DS-3 o DS-6 que se comprueba que falla antes de implementarlas: no se inventa un caso de golden set artificial, y lo declaran en su campo Rama. (learned 2026-09-16) \n\n- Todo escenario de red-team (RT-1 a RT-15) necesita al menos un criterio verificable en el canal de texto, porque DS-6 corre por el adaptador de texto en cada entrega; un escenario cubierto solo en la voz queda fuera de esa compuerta y se comprueba solo por hito. (learned 2026-09-16) \n\n- Las pruebas de límites de gasto y de cuota no consumen el presupuesto que protegen: el tope en el proveedor se comprueba con una clave de prueba de tope mínimo y la aplicación detenida, y el techo de gasto con un acumulado forzado en pruebas, nunca llevando una clave real hasta su tope. (learned 2026-09-16) \n\n- La primera unidad de la rama evaluada que realiza M8 sin conducta propia (el corredor de evaluaciones) no tiene casos existentes que correr: se construye con la rama determinista y su caso previo es la primera corrida de los casos que escriban las unidades siguientes; nunca se inventa un caso de golden set para ella. Decisión de Units Generation (U1), 2026-09-17. (learned 2026-09-17)"
    }
  ],
  "obligations": {
    "strategy": "standard",
    "strategy_volume": [
      "Five to eight tests per component.",
      "Unit tests plus integration tests for key boundaries.",
      "Add E2E, performance, or security tests when requirements demand them."
    ],
    "scope_floor": [
      "Keep the existing test suite green.",
      "This scope adds no extra new-test floor beyond the selected test strategy."
    ],
    "combination_rule": "Apply every selected-strategy obligation and every scope-floor obligation; neither replaces the other, and a targeted scope regression may add the narrowest necessary test type beyond the strategy default."
  },
  "plan_profile": {
    "methodology": "custom",
    "runner_step": "Verify the existing test runner/configuration and record the exact unit-scoped command.",
    "runner_ready_before_first_test": true,
    "testable_layers": [
      "Data model / database behavior",
      "Repository / data access",
      "Business logic",
      "API / endpoint",
      "Frontend behavior"
    ],
    "steps": [
      "Project structure and production configuration skeleton.",
      "Verify the existing test runner/configuration and record the exact unit-scoped command.",
      "Custom ordering - Clasifica cada unidad en una de dos ramas y no dejes ninguna sin rama. Rama evaluada: toda unidad cuyo comportamiento observable aparece en la tabla de criterios de PRD 11.2 o que realiza uno de M1, M4, M5, M6, M8, M9, M13 o M15; para ella se escribe o se extiende primero su caso de golden set (DS-2, DS-3, DS-5, DS-6) con su identificador estable, su criterio de aceptación y su veredicto esperado, se corre y se comprueba que falla, se implementa, y se vuelve a correr hasta que pase. Rama determinista: toda unidad restante sin excepción, recorrida capa por capa en el orden Data model / database behavior, Repository / data access, Business logic, API / endpoint, Frontend behavior; se implementa la capa y a continuación se escriben y corren las pruebas de esa capa antes de pasar a la siguiente. Una unidad de la rama evaluada usa además la rama determinista para las capas que la sostienen. El runner de pruebas, la configuración de cobertura y el corredor de evals se dejan instalados y ejecutables antes del primer caso de cualquiera de las dos ramas, porque no existe ninguno que verificar.",
      "Implementation and tests - preserve that exact ordering; do not convert it to layer-local TDD.",
      "Environment/build configuration.",
      "Documentation and traceability."
    ]
  },
  "input_sha256": "sha256:0226cf570c9568fe6fa1de61b29a94e7b0709fc04b42d102e273b1d2645d69a9",
  "contract_sha256": "sha256:6373b3c2e4592ca33a8ad34e18f87d9ef32d8f0a12fc3ba68ba53a709c613250"
}
```
