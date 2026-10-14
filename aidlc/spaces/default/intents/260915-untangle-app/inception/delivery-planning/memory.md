<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
- 2026-09-18T23:46:57Z — Se leyo "Bolt" como exactamente una unidad de trabajo, no como el agrupamiento por capas del PRD: el PRD llama "unit" a cada capa (Core, Policy RAG, Agents...), y esas capas se conservan como semanas del calendario, no como Bolts.
- 2026-09-18T23:46:57Z — Al escribir el plan se detecto que la opcion A de Q3 afirmaba que S2 y S1 son unidades enteras, y solo S1 lo es; se corrigio ante Miguel y en el archivo de preguntas antes de generar los artefactos, aunque no cambiaba su decision.
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->

## Deviations
- 2026-09-18T23:46:57Z — La etapa ofrece preguntar si varios Bolts pueden construirse en paralelo; no se pregunto, porque la practica afirmada ("una pieza completa a la vez") y el hecho de que haya un solo constructor lo responden. Se registro como decision con su razon en lugar de como pregunta.
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs
- 2026-09-18T23:46:57Z — Un Bolt por unidad (22) en vez de agrupar por capas (8, como el PRD): mas compuertas de aprobacion a cambio de que ninguna pieza quede a medias, que es la practica afirmada. El calendario del PRD se conserva agrupando Bolts por semana, no fusionandolos.
- 2026-09-18T23:46:57Z — Se descarto un modelo de puntaje formal (WSJF) y se escribio por que: con 90 aristas y un calendario aprobado, el puntaje no habria cambiado el orden y habria sido decoracion. Es una desviacion de la sugerencia de la etapa, que lo ofrece como heuristica.
- 2026-09-18T23:46:57Z — Las compuertas de evaluacion (U21) van antes del chat y la bandeja, aunque el mapa permitia ponerlas despues: la linea base v0 es parte de la compuerta del dia 30 y el juez necesita etiquetas humanas, que es la dependencia mas lenta.
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
- 2026-09-18T23:46:57Z — La compuerta del dia 30 exige 17 de 22 unidades en tres semanas y dos dias (unas cinco por semana) cuando el resto del plan avanza a unas dos y media. Miguel eligio mantener la fecha con la regla de corte; la senal esta escrita (Bolt 11 terminado al cerrar la semana 3). Vale revisarla al cerrar la semana 2, con dos Bolts de evidencia real de ritmo.
- 2026-09-18T23:46:57Z — El experimento de voz corre en la semana 2 y todavia no hay fecha ni responsable para las grabaciones de DS-5 en ingles, que la semana 6 necesita.
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
