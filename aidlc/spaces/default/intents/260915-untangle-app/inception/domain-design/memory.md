<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->
- 2026-09-17T00:10:56Z — Cuatro preguntas en lugar de las cinco a ocho de la profundidad Standard: el PRD, los requisitos, las historias aprobadas, las prácticas y la regla escrita antes del experimento 2 resuelven el resto, y la regla del proyecto pide llevar a Miguel solo lo que tiene dos respuestas legítimas y cambia lo que ve quien evalúa, con opción recomendada.
- 2026-09-17T00:10:56Z — Los componentes siguen los módulos MOD-01 a MOD-15 del PRD, como exige la convención 2 de `team.md`; la landing de `site/` y sus nueve componentes del code knowledge base quedan fuera del catálogo porque no son parte del aplicativo.

- 2026-09-17T00:50:20Z — Los cuatro nodos se proponen como componentes propios y el runtime del grafo aparte (Opción A), leyendo la convención 3 de `team.md` (el token del nodo nombra el directorio del módulo); la elección final queda para la aprobación.
- 2026-09-17T00:50:20Z — US4.2 (video) y US4.3 (landing) se marcan N/A en la trazabilidad: son entregables de MOD-15, no componentes de código; US4.1 se asigna a Evaluation porque genera las secciones del README que se comprueban.
## Deviations
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->
- 2026-09-17T00:10:56Z — Domain Design fija también el lenguaje con sus herramientas y los proveedores, aunque la etapa deja el stack para etapas posteriores; `team.md` (Code Style) asigna a domain-design el ADR del lenguaje con runtime, gestor, lockfile y comprobador de tipos, `requirements.md` asigna aquí OQ2 y OQ3, y el plan pide cambiar D-015 en esta etapa con los datos de los experimentos.

- 2026-09-17T00:50:20Z — Se añadió Q5 como pregunta de seguimiento después de las cuatro respuestas: al escribir ADR-006 apareció que el chat público en el plan gratuito contradice las condiciones de datos de Gemini y la práctica de tratar lo que entra por superficies públicas como dato real, y ningún documento aprobado lo resolvía.
## Tradeoffs
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

- 2026-09-17T00:50:20Z — La recomendación de Q3 pasó de HTML servido por Python a React con TypeScript y Vite servido desde el mismo origen, tras investigar con los criterios de Miguel (buenas prácticas y que quien revisa reconozca un proyecto bien construido): el template oficial de FastAPI usa esa forma y las dos librerías de voz traen componentes de React; se acepta un segundo juego de herramientas desde el primer commit.
- 2026-09-17T00:50:20Z — Q5: Miguel eligió el plan gratuito de Gemini para el chat público con un aviso de no escribir datos reales, en lugar del plan de pago recomendado; queda como riesgo aceptado en ADR-006, porque las condiciones del plan gratuito permiten a Google usar y leer lo enviado y piden no enviar datos personales.
## Open questions
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
- 2026-09-17T00:50:20Z — AC5.16.4 pide una página de espera con la instancia dormida; servir la interfaz desde el mismo proceso que la API no la permite. Decide el intent infra si los archivos estáticos van en un hospedaje que no se duerme.
