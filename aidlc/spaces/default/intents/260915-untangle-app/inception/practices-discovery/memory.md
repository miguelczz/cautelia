<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->
- 2026-09-16T13:37:17Z — Q2 se respondió fuera de las opciones y su lectura importa: Miguel rechaza el esqueleto delgado de punta a punta y pide una base sólida terminada y después componentes uno a uno, sin dejar ninguno a medias. Eso describe un recorrido por componente (unit-major), no por etapa, y es insumo directo de `delivery-planning` y del arranque de Construcción.
- 2026-09-16T13:57:10Z — Con `- **Methodology**: custom`, la línea de `- **Ordering**:` deja de ser una nota y pasa a ser el plan de pruebas completo que recibe la generación de código, capturado además en una sola línea. Lo detectó el especialista de calidad leyendo el código del framework, no por criterio; se reescribió con dos ramas cerradas y exhaustivas para que el código que ninguna evaluación mide también tenga orden afirmado.


## Deviations
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->
- 2026-09-16T13:57:10Z — El piso del 80 % de cobertura no se activa automáticamente para este tipo de flujo, aunque `org.md` lo enuncie: se escribió como obligación propia con comando y lista de exclusión. Sin eso habría sobrevivido solo como prosa.


## Tradeoffs
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->
- 2026-09-16T13:37:17Z — Q1: commit directo a la rama principal con GitHub Actions como compuerta, en vez del default de `org.md` (rama corta con pull request). Se acepta porque es la variante de tronco único sin rama intermedia y el equipo es una persona; el costo es que la compuerta corre después del aterrizaje, y se compensa con el guion de verificación local y el gancho previo al commit (Q7).
- 2026-09-16T13:44:38Z — Q7: Miguel eligió confiar solo en GitHub Actions, sin gancho previo al commit ni guion obligatorio en local, después de que se le presentara la consecuencia sobre el historial. Se acepta como su decisión; la mitigación compatible es poner el escaneo de secretos como primer trabajo del flujo, activar la protección de inserción del servidor si está disponible y rotar toda clave detectada.
- 2026-09-16T13:44:38Z — Q5: Miguel eligió publicar también un enlace en vivo de la voz (`C5`, clasificado como "podría" en el PRD por costo). Se acepta con condiciones duras: límite por visitante y por día configurado también en el proveedor, techo mensual con corte automático y modo degradado que deja vivo el chat.


## Open questions
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
- 2026-09-16T13:37:17Z — Verificar en la promoción que reemplazar `## Way of Working` con commit directo no sea rechazado como contradicción del default del espacio; si lo fuera, el camino es afirmarlo como especialización del proyecto y no como sustitución del default.
- 2026-09-16T13:44:38Z — El enlace en vivo de la voz mueve `C5` del "podría" a lo intencionado y choca con el tope de 5 USD (D-015, M20). `requirements-analysis` debe reconciliarlo con el PRD y decidir si el tope sube o si el límite por visitante se calibra para caber en los 5 USD.
- 2026-09-16T13:57:10Z — `- **Methodology**: custom` en la capa de equipo bloquea cualquier especialización futura de la posture de pruebas en la capa de proyecto que no sea también `custom`; la resolución se detendría con un conflicto. Tenerlo presente si una etapa posterior propone escribir ahí.
- 2026-09-16T13:57:10Z — `## Code Style` queda condicionada a que el ADR de lenguaje fije también versión del runtime, gestor de dependencias con formato de lockfile y comprobador de tipos; con solo el nombre del lenguaje, la sección queda a medias.

