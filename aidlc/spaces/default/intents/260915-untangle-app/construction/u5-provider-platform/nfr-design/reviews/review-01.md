## Review

**Reviewer:** aidlc-architecture-reviewer-agent
**Iteration:** 1
**Verdict:** NOT-READY
**Date:** 2026-09-21T04:17:25Z

### Herramientas de validación

| Herramienta | Resultado | Interpretación |
| --- | --- | --- |
| `python3 scripts/check-artifacts.py aidlc/spaces/default/intents/260915-untangle-app/construction/u5-provider-platform` | 8 hallazgos, todos por `mise run test:u5` (6 veces) y `mise run spend:report` (2 veces) citados sin existir en `mise.toml` | Confirmado como hueco temporal esperado. `u5-provider-platform/infrastructure-design/cicd-pipeline.md` todavía no existe (es la siguiente etapa de esta unidad) y es ahí donde se declaran las tareas nuevas de `mise.toml`. Contrastado contra U4 `case-record`, cuya `nfr-requirements/security-requirements.md` deja escrito literalmente "`mise run test:u4` no existe todavía. Lo crea la generación de código..." y cuyo `cicd-pipeline.md` sí existe hoy (etapa ya recorrida). El patrón es idéntico y no abro un hallazgo por cada cita. |
| `aidlc engine sensor fire traceability --stage nfr-design --output-path .../nfr-design/traceability.json` | No se pudo invocar `aidlc` en este entorno de revisión (el binario no está en el `PATH` de la sesión de revisión) | Sustituido por verificación manual: los doce identificadores de `upstream_ids` (NFR11.5, NFR11.6, NFR14.1–14.3, NFR15.1–15.6, NFR18.1) se contrastaron uno a uno contra `security-requirements.md`, `performance-requirements.md` y `reliability-requirements.md` de `../nfr-requirements/`. Los doce existen y ninguno falta. |

### Comprobaciones cuantitativas hechas contra la fuente (no contra la prosa)

- **Seis capas de seguridad** (`security-design.md`, tabla "Las seis capas"): se contaron las filas 1 a 6. Coincide.
- **Nueve piezas lógicas** (`logical-components.md`, tabla "Las nueve piezas"): se contaron las filas. Coincide.
- **Cinco reglas de dirección** (`logical-components.md`): se contaron las reglas 1 a 5. Coincide, y las cinco son consistentes con las cuatro reglas de dirección de `team.md` (convención 5): la regla 1 y 2 de U5 son la instancia concreta de la 5(b) ("el núcleo no importa proveedores... depende de un puerto propio"), y ninguna de las cinco contradice las dependencias declaradas en `components.md` para `ProviderGateway` (depende de `UsageBudget` sync y `Telemetry` async), `Telemetry` (depende de `UsageBudget` sync) y `UsageBudget` (solo depende de `TenantIdentity`). El diagrama de `logical-components.md` reproduce exactamente esa dirección: `adapters/gemini/` → `telemetry/spend/api.py` (reporta uso) y → `telemetry/traces/api.py` (emite tramo); `telemetry/traces/` lee costo de `telemetry/spend/` y no al revés, igual que en `components.md`.
- **Doce identificadores de `traceability.json`**: los doce (`NFR11.5`, `NFR11.6`, `NFR14.1-3`, `NFR15.1-6`, `NFR18.1`) se verificaron contra `../nfr-requirements/security-requirements.md`, `performance-requirements.md` y `reliability-requirements.md`. Los doce existen.
- **Dieciséis controles `SEC-U5.x`** citados como fuente en `security-design.md`: se contaron en `../nfr-requirements/security-requirements.md` (SEC-U5.1 a SEC-U5.16). Coincide en cantidad. Pero al mapear cada uno contra los ocho documentos de `nfr-design/` (ver hallazgo R-01), **SEC-U5.16 no tiene mecanismo de diseño en ningún documento**.
- **Siete decisiones `NFR-U5-x`**: se contaron en `security-requirements.md` (NFR-U5-1 a NFR-U5-7). Coincide.
- **300 ms / 50 ms** (`performance-design.md`): se verificó contra `inception/contract-design/contract-summary.md`, C-08, que fija `availability` en 300 ms. Coincide.
- **15 ms / 50 ms en p95**: se verificó contra `PERF-U5.1` y `PERF-U5.2` en `../nfr-requirements/performance-requirements.md`. Coincide.
- **Cifras del cortacircuitos** (cinco fallos consecutivos, treinta segundos): coinciden entre `nfr-design-questions.md` (Q1) y `reliability-design.md`.
- **`app/config/providers/` "hoy no existe"** (`logical-components.md`): verificado contra el repositorio vivo (`ls app/config/`) — en efecto no existe. Coincide con la afirmación.
- **La lista de exclusión de la aserción de aislamiento** (`security-design.md`, sección "La exclusión del aislamiento, y su aserción"; `SEC-U5.6`/`SEC-U5.7`): verificada contra `app/backend/pyproject.toml` (`[tool.untangle.rls] excluded`) y contra `app/backend/src/untangle/tenancy/rls_assertion.py`. Ver hallazgo R-02.
- **Campos de `BudgetWindow`** citados en `performance-design.md` (`billable_spent_usd`, `recording_spent_usd`, `unmeasured_billable_calls`, `alert_usd`, `cap_usd`, `alert_sent_at`, `window_start`): verificados uno a uno contra `../functional-design/entities.md`. Los siete existen con el mismo nombre.

### Findings

| ID | Severity | Location | Finding | Required action | Status |
| --- | --- | --- | --- | --- | --- |
| R-01 | Critical | aidlc/spaces/default/intents/260915-untangle-app/construction/u5-provider-platform/nfr-design/security-design.md | `SEC-U5.16` ("El texto de origen externo entra al proveedor como campo delimitado del estado tipado, nunca concatenado al prompt de sistema") no tiene mecanismo de diseño en ninguno de los ocho documentos de `nfr-design/`: no aparece en `security-design.md` (ni en las seis capas, ni en la tabla de pruebas, ni en "Lo que no diseña esta unidad"), ni en `logical-components.md` al describir `providers/adapters/gemini/` (la pieza que, según el propio `SEC-U5.16` de `../nfr-requirements/security-requirements.md`, es quien "arma la petición"), ni en `performance-design.md`, `reliability-design.md` u `observability-design.md`. Es además un control de la fila "Inyección" de la tabla STRIDE de `../nfr-requirements/security-requirements.md` (línea 37) y una regla `ALWAYS` de `project.md` ("mantener el texto de origen externo... fuera de la posición de instrucción del prompt"). Un desarrollador que construya `adapters/gemini/` a partir de este diseño no tiene ninguna guía sobre cómo separar el campo delimitado del prompt de sistema, ni sobre cómo se prueba esa posición. | Añadir a `security-design.md` (o a `logical-components.md`, como responsabilidad de `adapters/gemini/`) el mecanismo concreto que sostiene SEC-U5.16: la forma del objeto de petición que arma el adaptador, dónde vive el campo delimitado frente al prompt de sistema, y qué comprueba `mise run test:u5` sobre esa posición. | New |
| R-02 | Major | aidlc/spaces/default/intents/260915-untangle-app/construction/u5-provider-platform/nfr-design/security-design.md > sección "La exclusión del aislamiento, y su aserción" | El diseño describe el chequeo de columnas de `SEC-U5.7` ("Por cada tabla de la lista de exclusión, qué columnas tiene y de qué tipo... engancha dentro de `mise run rls:check`") como si extendiera la aserción viva citada en `Sources` (`app/backend/src/untangle/tenancy/rls_assertion.py`) de forma trivial. Pero esa aserción, tal como existe hoy: (a) su consulta `TABLAS_DEL_ESQUEMA` solo trae `table_name`, `row_security`, `force_row_security` y `tenant_policies` desde `pg_class`/`pg_policies` — ninguna información de columnas; (b) su función `evaluate()` hace `continue` (se salta por completo) cualquier tabla que esté en `excluded_tables()`. El chequeo de columnas que pide `SEC-U5.7` tiene polaridad **opuesta**: debe mirar precisamente las tablas que `evaluate()` hoy ignora, y necesita una consulta nueva (contra `information_schema.columns` o equivalente) y un modelo nuevo, ninguno de los cuales existe ni se menciona como trabajo nuevo en el diseño. Además, hoy `[tool.untangle.rls] excluded` en `app/backend/pyproject.toml` solo tiene una entrada (`alembic_version`); las tres tablas de dinero y cuotas que `SEC-U5.6` exige declarar ahí todavía no están, lo cual es razonable en esta etapa, pero el documento no lo señala como pendiente de la generación de código, a diferencia de cómo sí señala explícitamente otros huecos temporales (p. ej. `app/config/providers/` "hoy no existe"). | Aclarar en `security-design.md` que el chequeo de columnas es una consulta y un modelo nuevos añadidos a `rls_assertion.py` (no una reutilización directa de `evaluate()`/`read_tables()`), que se ejecutan sobre las tablas *excluidas* y no sobre las revisadas, y nombrar explícitamente que las tres entradas de `[tool.untangle.rls] excluded` llegan con la generación de código de esta unidad. | New |

### Summary

El diseño es sólido en su mayoría — los conteos, los contratos citados, las cifras de rendimiento y el reparto de dependencias resisten la comprobación cruzada contra el repositorio vivo y los documentos aguas arriba. Pero un control de seguridad marcado como "Inyección" en el modelo de amenazas (`SEC-U5.16`) queda sin ningún mecanismo de diseño, y el mecanismo que sí se describe para la exclusión de aislamiento (`SEC-U5.7`) no encaja con la arquitectura de la aserción viva tal como existe hoy en el repositorio. Ambos son necesarios antes de generar código sin volver a preguntar al arquitecto.

---

### Resolución (escrita por la conducción, 2026-09-21)

El veredicto queda como el revisor lo escribió: **NOT-READY**, con sus dos
hallazgos y su `Status: New`. **Los dos se reprodujeron contra la fuente y los
dos eran ciertos.**

| ID | ¿Era cierto? | Cómo se comprobó | Qué se hizo |
|---|---|---|---|
| R-01 | Sí, y era el hueco caro | `grep -rn "SEC-U5.16\|prompt de sistema\|inyect\|delimitado"` sobre los ocho archivos de `nfr-design/`: **cero resultados**. El control existía en los requisitos y no tenía ni una línea de diseño | `security-design.md` gana una **séptima capa** y su sección propia: la separación nativa que el proveedor ya ofrece entre instrucción de sistema y contenido; un tipo propio para el texto de origen externo que la función de la instrucción de sistema **no acepta**, así que pasárselo no compila; la instrucción sale del archivo de prompt versionado, sin concatenación en ejecución; y la prueba mira la petición armada, no la respuesta. Se escribe también lo que **no** hace: no impide que el modelo obedezca, solo que la instrucción inyectada llegue con rango de instrucción del sistema |
| R-02 | Sí | `rls_assertion.py`: `evaluate()` hace `continue` sobre las tablas de la lista de exclusión —justo las que este chequeo necesita mirar— y `TABLAS_DEL_ESQUEMA` no trae ninguna información de columnas | La sección de la aserción deja de presentarse como una extensión trivial: dice que hacen falta una segunda consulta al catálogo por las columnas, un modelo propio para su resultado, y un cambio en la evaluación para que una tabla excluida pase de "saltada" a "comprobada de otra manera". Y dice que ese trabajo cae sobre un archivo cuya dueña es U2 |

**La secuencia, otra vez.** Los dos arreglos se aplicaron después de registrar el
recibo. La razón es la de siempre en esta rejilla y ya está anotada dos veces: el
registrador rechaza un veredicto cuyos documentos cambiaron tras el despacho, y
la etapa admite una sola pasada. **Este recibo certifica los bytes que el revisor
leyó**, con los dos huecos dentro.

**Comprobaciones después de los arreglos** (ejecutadas): el sensor de
trazabilidad pasa; `check-artifacts.py` devuelve los mismos 8 hallazgos de
siempre, los de `mise run test:u5` y `mise run spend:report`, que el propio
revisor confirmó como el hueco temporal esperado; y la tabla de capas tiene ahora
siete filas, contadas, coincidiendo con el encabezado.
