## Review

**Verdict:** NOT-READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-09-20T20:12:00Z
**Iteration:** 1

Revisión asesora de `cicd-pipeline` de U3 `pii-redaction`, cotejada contra el
estado real de la tubería: `mise.toml`, `scripts/verify.sh`,
`.github/workflows/verify.yml`, `.github/workflows/fresh-clone.yml` y
`app/backend/pyproject.toml`, además de las tres etapas cerradas de la unidad.

El reparto de los modelos en un extra está bien razonado y la decisión de no
usar `spacy download` es sólida. Pero el documento afirmaba **dos mecanismos de
tubería que no existen en ningún archivo del repositorio**, y ninguno de los dos
venía con la línea de comando que los haría ciertos. Esa brecha entre lo
afirmado y lo verificable es justo lo que obliga a un desarrollador a volver a
preguntar antes de implementar.

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Critical | `cicd-pipeline.md` — fila del paso 5/9 | El documento decía que el paso 5 necesita los modelos y que "el guion instala el extra antes de este paso". Comprobado: ni `mise.toml`, ni `scripts/verify.sh`, ni `verify.yml` contienen llamada alguna a `models:install` o a `uv sync --extra models`. Tal como está la tubería, el paso 5 correría sin los modelos, rompiendo la prueba de RT-15 que la trazabilidad marca como cubierta por ese mismo paso. | Nombrar la línea exacta y dónde va, con la misma precisión que ya tiene la fila del paso 6. | Resolved |
| R-02 | Major | `cicd-pipeline.md` — "La caché de la tubería" | La afirmación de que el flujo ya cachea las dependencias de `uv` y que por eso una corrida normal no descarga los 72 MB no está respaldada. El flujo invoca la acción de `mise` sin parámetro de caché, y el alcance de esa acción es el directorio de herramientas de `mise`, no `~/.cache/uv`. Ninguno de los dos documentos de tubería anteriores establece ese hecho tampoco. | Verificar contra la documentación o el código de la acción y corregir la afirmación, o añadir el paso de caché explícito antes de dar por buena la cifra. | Resolved |
| R-03 | Minor | `cicd-pipeline.md` — "Cómo entran los modelos" | Fijar las ruedas por URL con su hash es correcto en principio, pero el documento no mostraba la forma concreta de declararlo, y hoy el manifiesto no tiene ninguna sección de dependencias opcionales ni precedente de dependencia por URL que sirva de plantilla. | Añadir el fragmento de manifiesto esperado para que la generación de código no invente la sintaxis. | Resolved |

### Evidencia de resolución

**R-01.** La tabla nombra ahora la línea exacta y su sitio:
`mise run models:install` en `scripts/verify.sh`, inmediatamente antes de
`paso "5/9 pruebas deterministas"`. Se aclara que **no es un paso del guion** —el
guion sigue teniendo nueve— sino la preparación de uno, igual que levantar la
base efímera para las pruebas de U2. Y se dice por qué va ahí y no en los otros
dos sitios posibles: en el flujo no, porque la tubería invoca el guion y no
mantiene su propia lista; en `deps:install` tampoco, porque esa tarea la corre
`bootstrap`, que es exactamente donde no queremos los 72 MB. Queda como decisión
INF-U3-7.

**R-02.** La afirmación era falsa y se dice así. Comprobado en el código fuente
de la acción: solo cachea el directorio de `mise`, no `~/.cache/uv`. El
documento declara ahora que **hoy cada corrida de la tubería descarga los
72 MB**, y propone el paso explícito de caché como decisión INF-U3-6, sin darlo
por hecho. La tabla de costes se corrigió en consecuencia.

**R-03.** Se añade el fragmento exacto del manifiesto, con las dos referencias
directas de PEP 508 y la explicación de por qué esa forma sí cumple: `uv` las
resuelve y anota su hash en el lockfile, de modo que `uv sync --locked` falla si
la rueda cambia. Que es la propiedad que `spacy download` no da.
