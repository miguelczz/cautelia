## Review

**Verdict:** READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-09-20T16:29:51Z
**Iteration:** 1

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Major | `cicd-pipeline.md` > "Dónde no hay base de datos" (decisión Q1) | La decisión Q1 —que `mise run bootstrap` (y por tanto `evals:run -- --subset smoke`) sigue sin tocar la base de datos— descansa en un supuesto que ningún documento deja escrito: que "el proceso" cuyo arranque `security-design.md` (Capa 1, "Al arrancar el proceso, la aserción es una condición de arranque") y `functional-spec.md` (Flujo 2 y Flujo 6, "Corre... al arrancar el proceso") condicionan a que `assert_rls_complete()` pase, es el proceso servidor (la raíz de composición de C-21/C-24), y no también el punto de entrada de `evals:run`. Hoy `app/backend/src/untangle/evals/cli.py` no importa `tenancy` ni pasa por esa raíz de composición, así que el subconjunto `smoke` es en efecto independiente del arranque del servidor — pero eso es un hecho del código actual de U1, no algo que `cicd-pipeline.md` o el diseño de U2 declaren como frontera. Como C-21/C-24 exigen un único punto de registro en la raíz de composición para todo lo que arranca, nada impide que la generación de código de U2 cablee la aserción de arranque ahí mismo y que un punto de entrada compartido futuro (o un cambio en cómo `evals:run` resuelve la configuración por aseguradora) vuelva a enganchar `evals:run` a esa comprobación, rompiendo en silencio la cifra publicada de NFR21 que esta misma decisión dice proteger. | Añadir una frase explícita en `cicd-pipeline.md` (o en `security-design.md`) que declare que la aserción de arranque de `assert_rls_complete()` cuelga exclusivamente de la raíz de composición del proceso servidor y no del punto de entrada de `evals:run`, y que la generación de código de U2 no debe engancharla a ningún otro punto de entrada sin revisar antes esta decisión Q1. | New |
| R-02 | Minor | `traceability.json` > cobertura de `SEC-U2.5`; `cicd-pipeline.md` > "Variables de entorno nuevas" | `nfr-design/correcciones-tras-revision.md` (R-01, autoritativo sobre `security-design.md` congelado) exige que `SEC-U2.5` se compruebe con **dos** comandos — `env:check` (existencia y lectura correcta de las dos variables) **y** `test:u2` (que una clave no valide lo firmado por la otra, la única prueba real de separación) —, pero la entrada de cobertura de `SEC-U2.5` en `traceability.json` y la sección "Variables de entorno nuevas" de `cicd-pipeline.md` solo mencionan `env:check`. El control queda igualmente ejecutado porque `test:u2` corre como parte de la suite, pero la trazabilidad de esta unidad documenta solo la mitad de lo que el propio corrector marcó como imprescindible. | Añadir `test:u2` a la cobertura de `SEC-U2.5` en `traceability.json` y nombrar la prueba de rechazo cruzado en la sección "Variables de entorno nuevas" de `cicd-pipeline.md`, para que la trazabilidad refleje las dos mitades que `correcciones-tras-revision.md` exige. | New |
| R-03 | Minor | `cicd-pipeline.md` > "Lo que esto le cuesta a la corrida" | El documento enmarca el costo nuevo en singular — "el arranque de un contenedor de PostgreSQL" — pero el diseño introduce al menos tres comandos que necesitan base en la misma corrida del paso 6/paso 5 (`cov`/`test:u2`, `rls:check`, `migrate:check`), y no dice si comparten una sola base efímera o si cada uno levanta la suya. La decisión de medir en vez de estimar sigue siendo correcta y no se ve afectada (NFR21 no cubre `verify.sh`), pero la cifra que "la primera corrida verde" va a medir corresponde a un número de arranques de contenedor que el documento no acota, lo que puede sorprender cuando se compare esa cifra con la expectativa implícita de "un contenedor". | Aclarar en `cicd-pipeline.md` si `rls:check`, `migrate:check` y las pruebas de integración de `cov`/`test:u2` comparten una base efímera o levantan una cada uno, para que la cifra medida en la primera corrida verde se pueda interpretar sin ambigüedad. | New |

### Validation Tool Results

No se listan herramientas de validación específicas en la definición de la etapa para `infrastructure-design`; la verificación se hizo por lectura cruzada contra los artefactos de aguas arriba y contra el estado real del repositorio (`mise.toml`, `scripts/verify.sh`, `.github/workflows/verify.yml`, `docker-compose.yml`, `app/backend/src/untangle/evals/cli.py`).

| Comprobación | Resultado | Interpretación |
|---|---|---|
| Cita literal de C-10 sobre testcontainers | Confirmada | `contract-summary.md` dice textualmente "las pruebas con testcontainers se conectan con ese rol y no con el superusuario"; la afirmación central de `cicd-pipeline.md` es exacta |
| "El guion sigue teniendo nueve pasos" | Confirmada | `scripts/verify.sh` numera sus pasos 1/9 a 9/9 sin cambios |
| "Dos trabajos" en el flujo de GitHub Actions | Confirmada | `.github/workflows/verify.yml` define exactamente `secrets` y `verify` |
| Paso 6 ya agrupa `schema:check`, `contracts:check`, `env:check`, `supply:check` | Confirmada | Línea `paso "6/9..."` de `scripts/verify.sh` invoca los cuatro en ese orden |
| Imagen anclada por huella en el entorno local | Confirmada | `docker-compose.yml` fija `pgvector/pgvector@sha256:...`, no una etiqueta |
| Independencia real de `evals:run --subset smoke` respecto al arranque del servidor | Confirmada para el código actual de U1, pero no declarada como frontera de diseño | Ver hallazgo R-01 |

### Summary

Las afirmaciones verificables de `cicd-pipeline.md` sobre el estado real del repositorio y sobre el contrato C-10 son exactas, y las dos decisiones (Q1, Q2) están razonadas y consistentes con las prácticas del equipo. La reserva principal es que la pieza que sostiene a Q1 — que el arranque del proceso servidor y el punto de entrada de `evals:run` son caminos separados — es hoy cierta por cómo está escrito el código de U1, pero el documento no la declara como una restricción de diseño que la generación de código de U2 deba respetar, dejando la protección de NFR21 apoyada en un supuesto no escrito.
