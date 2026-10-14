<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
- 2026-09-18T23:03:42Z — Se leyo "publico o externo" como consumidor fuera del proceso del aplicativo: la interfaz web compilada cuenta como externa aunque viva en el mismo repositorio, porque se despliega como artefacto aparte y consume la API por HTTP.
- 2026-09-18T23:03:42Z — La pregunta Q1 volvio a presentarse porque Miguel respondio delegando en la recomendacion ("usa la que mas se recomiende"); el protocolo pide una eleccion explicita, asi que se explico la razon y se pidio la confirmacion en vez de auto-responder.
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->

## Deviations
- 2026-09-18T23:03:42Z — La etapa sugiere un bloque AsyncAPI para los contratos por eventos; ADR-021 rechazo AsyncAPI por escrito (un solo consumidor, mismo repositorio), asi que los eventos de SSE se especifican como union discriminada dentro del esquema OpenAPI y entran al chequeo de deriva.
- 2026-09-18T23:03:42Z — La etapa pide un bloque de especificacion por frontera; en las fronteras dentro del proceso el formato apropiado no es OpenAPI sino la firma del `api.py` del modulo, asi que esos contratos se escriben como bloques de `Protocol` y firmas de Python.
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs
- 2026-09-18T23:03:42Z — Prefijo `/api/v1` con un solo consumidor en el mismo repositorio: cuesta casi nada hoy y evita tocar todas las rutas despues; la alternativa sin prefijo era mas honesta con la realidad actual pero mas cara el dia que haga falta.
- 2026-09-18T23:03:42Z — Un contrato por superficie ofrecida (29) en vez de uno por arista del mapa (90): menos documento y una sola copia autoritativa, a cambio de que el lector tenga que cruzar con `unit-of-work-dependency.md` para ver quien consume que.
- 2026-09-18T23:03:42Z — Las escrituras idempotentes se acotaron a tres rutas (mensaje, decision, correccion) en vez de a toda la API: cubren los casos reales de doble envio sin obligar a guardar respuestas de cada GET.
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
- 2026-09-18T23:03:42Z — El transporte de audio (C-29) queda como contrato declarado pero incompleto hasta el experimento 1; la forma del objeto `transport` de C-08 depende de esa eleccion. Conviene revisarlo antes de que U16 empiece.
- 2026-09-18T23:03:42Z — El canje del enlace firmado por fragmento de URL (C-07) supone que la interfaz es una sola pagina que puede leer `location.hash`; si alguna vez se sirve la vista de caso como pagina renderizada en servidor, el mecanismo cambia.
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
