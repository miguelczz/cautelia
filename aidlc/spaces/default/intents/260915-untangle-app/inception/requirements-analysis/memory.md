<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->
- 2026-09-16T14:26:01Z — El PRD v1.1 ya resuelve el alcance (15 módulos, 21 Must, 12 principios, métricas con umbral), así que esta etapa no re-descubre requisitos: los convierte en enunciados con criterio de aprobado o fallido y llena los huecos que impiden verificarlos. Las siete preguntas se limitan a esos huecos, casi todos abiertos por D-018 (enlace de voz en vivo).
- 2026-09-16T14:33:06Z — El acceso público a la bandeja se resuelve con un enlace firmado de una hora ligado al caso, en vez de credenciales publicadas. Eso convierte la excepción de secretos que las prácticas nombraban en algo más estrecho y, de paso, hace del aislamiento entre inquilinos algo que el visitante comprueba en vez de leer.


## Deviations
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->
- 2026-09-16T14:42:23Z — Al convertir el alcance en requisitos, las funcionalidades Should del PRD (continuidad de voz a chat, detección automática de idioma, comparación entre aseguradoras) se quedaron fuera sin aparecer tampoco en "Fuera de alcance" ni en preguntas abiertas: quedaron sin rastro, que es distinto de quedar excluidas a propósito. Detectado en la revisión.


## Tradeoffs
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->
- 2026-09-16T14:33:06Z — Contradicción detectada al cruzar respuestas: 15 llamadas diarias de 3 minutos cuestan unos 6,75 USD en 90 días, por encima del techo de 5 USD que Miguel mantuvo. Resuelta con su decisión: el techo es el control autoritativo y el límite diario solo reparte el consumo; saturado, el corte llega hacia el día 67 y la voz rechaza mientras el chat sigue. Queda como requisito verificable, no como supuesto.


## Open questions
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
- 2026-09-16T14:26:01Z — La analítica de la landing sigue sin decidir (PRD Segmento 10, dependencia con fecha en 13.4, semana 10). No bloquea los requisitos de hoy; se registra como pregunta abierta del artefacto.
- 2026-09-16T14:42:23Z — El costo por llamada se enuncia sobre cuatro minutos mientras el límite público de llamada son tres; los dos números vienen de fuentes distintas (el PRD y la respuesta de esta etapa) y conviene fijar una sola base de comparación.

