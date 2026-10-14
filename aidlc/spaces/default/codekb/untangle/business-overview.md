# Business Overview — repositorio `untangle`

Artefacto 1 de 9 del code knowledge base del repositorio `untangle` (rama `main`, commit `3736ad364d8d83526b2d7148e9d3ed8b76851757`), sintetizado en la etapa `reverse-engineering` del intent `260915-untangle-app` a partir de la entrega del desarrollador (`aidlc/spaces/default/intents/260915-untangle-app/inception/reverse-engineering/developer-scan.md`). Fecha, commit y alcance exacto en `reverse-engineering-timestamp.md`.

## Resumen ejecutivo

Untangle es un proyecto de portafolio del autor (Miguel): un sistema de agentes de IA "de producción, con evidencia verificable", demostrado en seguros de auto. Convierte una llamada o un chat, en inglés o en español, en un caso estructurado con la cobertura verificada cláusula por cláusula, reglas explicables y una persona en cada decisión que importa. El cliente real del producto no es una aseguradora sino quien evalúa y contrata al autor (ICP A); la aseguradora ficticia y su asegurado (ICP B) existen para dar realismo al diseño.

El repositorio contiene hoy dos realidades distintas que este code knowledge base mantiene separadas en todos sus artefactos:

| Realidad | Qué es | Dónde vive | Estado al commit escaneado |
| --- | --- | --- | --- |
| La landing | Página estática de una sola vista, bilingüe EN/ES, publicada en `https://untangle-ai.vercel.app/` | `site/` (10 archivos) y `design-package.md` | Existe y está publicada. Fuera del alcance del aplicativo (D-005, D-013); se realinea al final (M19) |
| El aplicativo Untangle | Grafo de cuatro nodos, RAG con citación verificada, motor de reglas por tenant, cumplimiento, bandeja, voz bilingüe, evals y telemetría para tres tenants sintéticos | Solo como especificación en `docs/specs/prd.md` y documentos de `docs/` | No existe ningún código: 0 archivos `.py`, `.js` o `.ts` fuera del tooling de `.claude/`, sin manifiestos, pruebas ni CI |

La detección automática del engine (`Languages: JavaScript`, `Frameworks: Unknown`, `Build System: Unknown`) describe solo el script inline de la landing, no el producto; el plan lo formula como "brownfield de marketing, greenfield de aplicación" (D-005; reconciliación completa en `code-quality-assessment.md`, TD-08).

## Lo que existe hoy: la landing (`site/`)

**Propósito de negocio.** Cara pública del proyecto ante empleadores y evaluadores técnicos: presenta la idea, explica cómo funcionaría el sistema y lleva a un único canal de conversión, el perfil de LinkedIn del autor. No vende nada, no captura datos y no tiene analítica (el PRD 13.4 deja la analítica de la landing como dependencia pendiente de Miguel).

**Funcionalidad clave visible para el visitante** (detalle técnico en `component-inventory.md`):

- Hero de 600 vh con un video que avanza al ritmo del scroll y bandas de texto que entran y salen; degradación a póster estático cuando el video falla, en teléfonos apaisados de poca altura o con `prefers-reduced-motion`.
- Ocho secciones narrativas: por qué existe (`#why`), cómo funciona con un diagrama SVG y seis tarjetas de agentes (`#how`), voz en tiempo real con una conversación guionizada (`#voice`), guardarraíles (`#guardrails`), evals y trazas (`#evals`), el momento interactivo "hold to untangle" (`#try`), FAQ con cinco preguntas (`#faq`) y llamada final a la acción (`#contact`).
- Idioma EN/ES conmutable en la barra de navegación, con la elección recordada en el navegador y detección inicial por idioma del navegador.
- Un solo CTA en toda la página: cinco anclas que llevan al perfil de LinkedIn del autor en pestaña nueva. Sin formulario, sin correo, sin teléfono.

**Estado de su contenido.** El copy afirma cosas que el PRD ya decidió de otra manera (seis agentes por dominio en lugar de cuatro nodos por función, "priced quote" en lugar de elegibilidad sin moneda, un agente de Documentos que el PRD deja en Could, "answers in seconds" en lugar de latencias p50/p95 publicadas, y ninguna mención a multi-tenant, citación verificada ni chat en vivo). Es una desalineación conocida y programada: D-013 y M19 fijan dos pasadas de realineación en las semanas 7 y 11 del plan (PRD Segmento 13). Hasta entonces la landing **no** es fuente de verdad del producto y **no** se deriva de ella la arquitectura del aplicativo. Registro de la deuda asociada en `code-quality-assessment.md` (TD-01).

## Lo que se va a construir: el aplicativo Untangle

Todo lo que sigue proviene de `docs/specs/prd.md` (PRD v1.0, segmentos aprobados por Miguel el 2026-09-15) y de `docs/PLAN-AIDLC.md`; se resume sin copiar y se enlaza por ruta y por identificador para que las etapas siguientes lo consulten en la fuente.

### Dominio y producto

- **Dominio**: seguro de auto personal, con una jurisdicción ficticia ("Estado de Corvane" por defecto; alternativas Vantera y Ellery) cuyas reglas viven en un documento del corpus y nunca citan leyes reales (PRD 9.1).
- **Producto único** (D-007): el primer aviso de siniestro (FNOL) por voz es el camino pulido; la cotización con elegibilidad es el segundo flujo, delgado, sin tarifas reales ni moneda (D-012).
- **Una sola agente, dos idiomas, dos canales** (P12): la misma agente conversacional ("Valentina" por defecto, guía en `docs/pre_prb/voz-y-tono.md`) atiende voz y chat web en inglés y español, con una sola voz femenina paisa elegida por prueba ciega (D-016).
- **Datos 100 % sintéticos**: corpus, pólizas, reglas y casos se generan en el repositorio (M3, MOD-12); ningún texto de terceros (PVB §7, propiedad intelectual).
- **Costo cero salvo el LLM** (P9, D-015): Gemini 2.5 Flash-Lite en tier de pago solo para voz y trabajo de fondo, tope de 5 USD en 90 días con alerta en 3 USD; tier gratuito para desarrollo y evals en texto.

### Clientes (PRD Segmento 3)

| ICP | Quién | Qué necesita del producto |
| --- | --- | --- |
| A (cliente real) | Reclutador técnico, engineering manager, staff engineer como veto holder | Evidencia verificable de que el autor sabe construir agentes de producción: repo ejecutable, evals con fallos a la vista, trazas, README honesto |
| B (ficticio) | La aseguradora y su asegurado | Realismo del dominio: un caso completo, cobertura citada, derivación a una persona |

Cada trade-off se resuelve a favor del ICP A.

### Tenants sintéticos (PRD 9.1)

| `tenant_id` | Nombre comercial | Tipo | Postura | Idioma por defecto | Persona de la bandeja |
| --- | --- | --- | --- | --- | --- |
| `stonecroft` | Stonecroft Mutual Insurance Company | Aseguradora mutual regional de auto | Conservadora: deducibles altos, exclusiones amplias, derivación frecuente | Español | Diana, ajustadora |
| `sunmeadow` | Sunmeadow Auto Insurance | Aseguradora directa de auto | Flexible: deducibles bajos, endosos que reabren exclusiones, cierre directo frecuente | Inglés | Ajustador con nombre pendiente (se fija en user stories) |
| `knotwell` | Knotwell Insurance Agency | Agencia independiente que coloca pólizas de las dos anteriores | Intermediaria: nunca cierra un siniestro, siempre deriva a la emisora | Inglés | Agente de cuenta con nombre pendiente |

Los nombres se verificaron contra marcas reales el 2026-09-15; el `tenant_id` es un slug técnico que no cambia aunque cambie el nombre comercial.

### Arquitectura funcional aprobada (PRD 9.2)

Dos canales (voz y chat web) entran al mismo grafo por tenant; el grafo recorre cuatro nodos, **Intake → Policy Verification → Decision → Compliance**, sobre un estado tipado con checkpoints en Postgres; Compliance pausa el grafo con `interrupt()` hacia la bandeja del ajustador, que lo reanuda con la decisión humana. El orquestador es código, no un agente con prompt (P3), y el grafo corre sin voz (chat y evals primero). El diagrama planeado, marcado como no existente, está en `architecture.md`, sección "Arquitectura objetivo según el PRD".

### Módulos (PRD 9.4)

| Módulo | Nombre | Prioridad |
| --- | --- | --- |
| MOD-01 | Caso (registro estructurado) | Must |
| MOD-02 | Orquestación (grafo y nodos) | Must |
| MOD-03 | Canal de voz | Must |
| MOD-04 | Chat web | Must |
| MOD-05 | Corpus y RAG con citación verificada | Must |
| MOD-06 | Motor de reglas por tenant | Must |
| MOD-07 | Cumplimiento (cuatro controles) | Must |
| MOD-08 | Bandeja del ajustador | Must |
| MOD-09 | Tenants e identidad | Must |
| MOD-10 | Telemetría y costo | Must |
| MOD-11 | Evals | Must |
| MOD-12 | Generador de datos sintéticos | Must |
| MOD-13 | Cotización con elegibilidad | Should |
| MOD-14 | Documentos al caso | Could |
| MOD-15 | Evidencia pública (README, video, landing realineada) | Must |

Las features se identifican como `F<módulo>.<n>` y se trazan a M/S/C en PRD 9.6; roles y permisos en 9.3; diez pantallas y flujos en 9.5 (la landing es la pantalla 10, en Vercel).

### Alcance MoSCoW (PRD Segmento 8)

Veinte Must que no se cortan, agrupados por capa: núcleo en texto (M1 caso, M2 grafo, M3 corpus sintético, M4 RAG con citación verificada, M5 reglas, M6 cumplimiento, M7 telemetría, M8 evals en CI, M9 multi-tenant, M16 llamada cortada reanudable, M20 tope de gasto), superficies humanas (M10 chat web en vivo, M11 bandeja), voz (M12 inglés, M13 golden set de audio EN, M14 español, M15 golden set ES) y evidencia pública (M17 README, M18 video, M19 landing realineada). Además seis Should (S1 a S6, entre ellos la cotización S1 y la vista de comparación entre tenants S5), seis Could (C1 a C6, entre ellos Documentos C1, enlace público de voz C5 y Keycloak) y nueve Won't (W1 a W9, entre ellos el traspaso real entre tenants W1). Regla de corte si falta tiempo: S2, S1, C1, S5, S4; el español se reduce, nunca se elimina.

### Principios no negociables (PRD Segmento 6)

P1 las personas deciden cobertura y dinero; P2 ninguna cita sin cláusula existente; P3 el orquestador es código; P4 dos latencias medidas y publicadas (turno p50 < 500 ms y p95 < 800 ms por idioma; decisión aparte); P5 evals con fallos a la vista; P6 cumplimiento como controles verificables ("inspirado en", nunca "cumple con"); P7 diseño de expectativas; P8 datos y texto limpios; P9 costo cero salvo el LLM con tope; P10 real pero honesta; P11 una idea por turno y confirmación en voz alta; P12 una sola agente en dos idiomas y dos canales.

### Decisiones de proceso y producto (`docs/PLAN-AIDLC.md`, D-001 a D-017)

| ID | Decisión (resumen) |
| --- | --- |
| D-001 | Usar AI-DLC 2.9.0 (binario `aidlc`) y actualizar la guía del equipo desde v0.1.5 |
| D-002 | `untangle/` es el workspace root de AI-DLC y la raíz del repo git; la landing vive en `site/` dentro del mismo repo |
| D-003 | Pre-incepción en español; código, nombres técnicos y artefactos AI-DLC en inglés (los artefactos de este flujo siguen la línea `Conversation language` que el orquestador fija en cada encargo, hoy español) |
| D-004 | Documentos de entrada nombrados como en el kit (`docs/pre_prb/`) |
| D-005 | La landing queda fuera de Incepción: "brownfield de marketing, greenfield de aplicación" |
| D-006 | `review/`, el zip de la skill y los raws de la landing no se versionan |
| D-007 | Producto único auto: FNOL pulido, cotización delgada |
| D-008 | Deep research ejecutado desde Claude Code con fuentes citadas |
| D-009 | Voz bilingüe inglés y español, ambos obligatorios |
| D-010 | Los 12 ajustes de `docs/01-evaluacion-brief.md` son lineamientos aprobados; landing y brief se alinean al aplicativo |
| D-011 | Costo cero (tier gratuito o self-host), enmendada por D-015 para el LLM |
| D-012 | Sin tarifas reales: la cotización produce elegibilidad y, si acaso, un valor indicativo por reglas sintéticas |
| D-013 | La landing se realinea al aplicativo cuando la arquitectura quede aprobada (después de Incepción) |
| D-014 | Perfil `classic` para el intent principal y un segundo intent `infra` para CI, despliegue y observabilidad |
| D-015 | LLM Gemini 2.5 Flash-Lite de pago solo para voz y fondo; tope 5 USD en 90 días, alerta en 3 USD |
| D-016 | Una sola voz femenina paisa (Medellín) para ambos idiomas, elegida por prueba ciega; tope de la voz pendiente de Miguel |
| D-017 | Repositorio privado `github.com/miguelczz/untangle`; público cuando README y evals estén listos |

El PRD añade en su Paso 0 trece decisiones de reconciliación entre documentos (nodos por función, latencias, sin score del modelo, elegibilidad sin moneda, continuidad voz a chat como Should, tres tenants, jurisdicción ficticia, siete campos centrales del caso, README en inglés con resumen en español, chat en vivo obligatorio, Documentos en Could, tamaño de los golden sets).

### Plan de entrega y riesgos (PRD Segmentos 12 y 13)

Noventa días desde el 2026-09-16 con compuertas en los días 30, 60 y 90; Incepción comprimida en las semanas 1 y 2 con cuatro spikes de riesgo en paralelo (voz-grafo, Flash-Lite, WER en español, voces paisas). Orden previsto de units: Core → Policy RAG → Agents → Evals y observabilidad → Bandeja y chat → Voz EN → Voz ES → Cotización; CI y despliegue en el intent `infra` (D-014). Diez riesgos identificados (R1 demo-ware, R2 latencia de turno, R3 Flash-Lite insuficiente, R4 español degradado, R5 tiers gratuitos, R6 tope agotado, R7 cita inexistente en el chat público, R8 fuga entre tenants o PII en trazas, R9 parecer que se cumple o propiedad intelectual, R10 integración voz-grafo).

### Decisiones abiertas que la documentación deja para etapas posteriores

Verbatims del ICP A (día 30); nombres del ajustador de Sunmeadow y del agente de Knotwell (user stories); jurisdicción definitiva (Corvane por defecto); tope de la voz si gana ElevenLabs (D-016, `docs/reference/voz-proveedores.md` §3); Keycloak (ADR); analítica de la landing; repositorio público al publicar (D-017); y los ADR de tecnología listados en `technology-stack.md`. Ninguna etapa de Incepción debería reabrirlas sin motivo.

## Estado del aplicativo en el repositorio

No hay código del aplicativo ni andamiaje: sin directorio de código fuente, sin manifiesto de dependencias, sin README, sin pruebas, sin CI, sin generador de datos ni corpus (solo la estructura de referencia en `docs/reference/estructura-poliza-iso-pap.md`). La lista de lo que Construcción debe crear desde cero está en `code-quality-assessment.md` (TD-09) y el stack decidido frente al hipotético en `technology-stack.md`.

## Referencias

| Tema | Ruta |
| --- | --- |
| PRD v1.0 (fuente del alcance del aplicativo) | `docs/specs/prd.md` |
| Plan del proceso, decisiones D-001 a D-017, registro de sesiones | `docs/PLAN-AIDLC.md` |
| Brief original y su evaluación (12 ajustes, D-010) | `docs/00-brief-untangle.md`, `docs/01-evaluacion-brief.md` |
| Pre-incepción (idea, crítica, ICP, mercado, PVB, overview) | `docs/pre_prb/` |
| Guía de voz y tono de la agente | `docs/pre_prb/voz-y-tono.md` |
| Estructura de póliza de referencia (ISO PP 00 01) y proveedores de voz | `docs/reference/estructura-poliza-iso-pap.md`, `docs/reference/voz-proveedores.md` |
| Diseño y copy de la landing | `design-package.md` |
| Entrega del desarrollador (escaneo) | `aidlc/spaces/default/intents/260915-untangle-app/inception/reverse-engineering/developer-scan.md` |
