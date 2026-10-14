## Review

**Reviewer:** aidlc-architecture-reviewer-agent
**Iteration:** 1
**Verdict:** READY
**Date:** 2026-09-21T04:01:03Z

### Herramientas de validación

| Herramienta | Resultado | Interpretación |
| --- | --- | --- |
| `python3 scripts/check-artifacts.py .../construction/u5-provider-platform` | 8 hallazgos, los 8 sobre `mise run test:u5` y `mise run spend:report` | Comprobado contra el código del comprobador (`scripts/check-artifacts.py`, función `tareas_que_la_unidad_crea`): lee la tabla "## Las tareas nuevas del archivo de tareas" de `<unidad>/infrastructure-design/cicd-pipeline.md`, que en U5 todavía no existe. Comprobado también contra el precedente real de U4 (`u4-*/infrastructure-design/cicd-pipeline.md`, tabla con `test:u4` y otras dos tareas): una vez esa etapa corrió, `test:u4` dejó de aparecer como hallazgo del comprobador. Los ocho hallazgos de hoy son exactamente ese mismo hueco temporal en U5, ya anunciado en cada uno de los seis documentos afectados ("Los dos comandos que esta tabla cita... no existen todavía"). No abro hallazgo por ninguno de los 8. |
| `aidlc engine sensor fire traceability --stage nfr-requirements ...` | `"result":"passed"` | Los 21 NFR de `requirements-analysis` están cubiertos: 3 con estado `OK` (NFR11, NFR14, NFR15, las tres que `unit-of-work.md` asigna a U5) y 18 con `N/A` y su dueño real citado. Coincide con la tabla "Requisitos no funcionales por unidad" de `unit-of-work.md`. |

### Comprobaciones cuantitativas hechas contra la fuente (no contra la prosa)

- **Reserva de grabación:** 15 llamadas × 3 min = 45 min declarados; 45 min × 0,005 USD/min = 0,225 USD; 0,225 / 5,00 USD (techo de 90 días) = 4,5 %, que es "menos del 5 %" como afirma el documento. Los tres números (15, 3, 0,005) están tomados de FR3.9 y de D7/AC5.14.5 (`requirements.md` y `stories.md`), no del propio documento de U5.
- **Equivalencia NFR14 ↔ D7:** 0,005 USD/min × 4 min = 0,02 USD; coincide con el valor de NFR14 en `requirements-analysis/requirements.md` línea 227 ("voz menor o igual a 0,02 USD por llamada de cuatro minutos"). La equivalencia que `performance-requirements.md` afirma ("son el mismo número dicho dos veces") se sostiene.
- **Dependencias nuevas:** la tabla de `tech-stack-decisions.md` tiene 5 filas (`google-genai`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp` como runtime; `vcrpy`, `respx` como dev). La prosa dice "tres... de runtime y dos... de desarrollo": 3 + 2 = 5, coincide con el conteo de filas.
- **Controles `SEC-U5.x`:** la tabla "Controles" tiene 16 filas, `SEC-U5.1` a `SEC-U5.16` sin huecos ni repeticiones. Los 16 identificadores aparecen citados al menos una vez en la tabla "Qué puede salir mal" (STRIDE); ninguno queda huérfano.
- **Claves de proveedor declaradas:** grep sobre `.env.example` de hoy confirma exactamente una clave de proveedor (`UNTANGLE_EVALS_MODEL_API_KEY`) y dos de firma (`UNTANGLE_STAFF_CREDENTIAL_SIGNING_KEY`, `UNTANGLE_CASE_LINK_SIGNING_KEY`) — coincide con "hoy el aplicativo tiene una clave de proveedor... y dos de firma".
- **Lista de exclusión de aislamiento:** `app/backend/pyproject.toml` → `[tool.untangle.rls] excluded` tiene hoy exactamente 1 entrada (`alembic_version`), como afirma el documento ("hasta hoy esa lista tenía una sola entrada").
- **Módulos críticos:** `[tool.untangle.coverage] critical_modules` tiene hoy 3 entradas (`tenancy`, `compliance/redaction`, `case_record`); `providers` y `telemetry` no aparecen, lo que confirma "U5 no está en la lista afirmada de módulos críticos con piso propio".
- **Directorios vacíos:** `app/backend/src/untangle/providers/` y `.../telemetry/` contienen únicamente `__init__.py` de 0 líneas (5 archivos, todos vacíos), confirmando la afirmación sobre la cobertura pendiente.
- **`docker-compose.yml` y `settings.py`:** el perfil `traces` con Langfuse y su base existen y están anclados por huella digital (`@sha256:...`), y `settings.py` declara `traces_endpoint: str | None = None` con `traces_available` derivado — confirma "el endpoint de trazas ya opcional".
- **`mise.toml`:** de los comandos citados por los ocho documentos, solo `test:u5` y `spend:report` no existen hoy; el resto (`schema:check`, `env:check`, `rls:check`, `secrets`, `redaction:constructor`, `lint`) sí existen.
- **NFR11 sub-identificadores:** U3 ya usa `NFR11.1` a `NFR11.4` en su propio `security-requirements.md`; U5 usa `NFR11.5` y `NFR11.6`. No hay colisión de identificadores entre las dos unidades construidas hoy.

### Findings

| ID | Severity | Location | Finding | Required action | Status |
| --- | --- | --- | --- | --- | --- |
| R-01 | Major | `.../nfr-requirements/security-requirements.md` § "Las claves, en concreto" (PA-9) y `.../nfr-requirements-questions.md` Q1, frente a `inception/units-generation/unit-of-work.md` línea 1164 (`PA-9 \| ... \| nfr-requirements de U5 y U15`) e `inception/contract-design/contract-summary.md` línea 1701 (`C-17 \| ... (PA-9) \| nfr-requirements de U5 y U15`) | Los dos documentos aguas arriba asignan PA-9 conjuntamente a las etapas `nfr-requirements` de **dos** unidades, U5 y U15 (`speech-providers`, que añadirá sus propios proveedores de transcripción y síntesis con sus propias claves — `tech-stack-decisions.md` de U5 ya anticipa que "el adaptador de transcripción y el de síntesis los añade U15... con sus propias dependencias"). El documento de U5 resuelve PA-9 como si fuera la decisión completa y final del proyecto — fija la política (saldo prepagado sin recarga automática sustituye al tope duro; una alerta nunca cuenta como tope) y el mecanismo de comprobación (`PA-9.1`, `mise run schema:check` sobre "la tabla versionada de topes"), pero no dice en ningún sitio qué le queda pendiente a U15 sobre esa misma pregunta: si U15 hereda la política y solo añade filas a la tabla que U5 crea, o si U15 vuelve a abrir Q1 para sus propios proveedores de voz. Ninguna de las dos lecturas está escrita, y es exactamente el tipo de hueco que este mismo documento sí se ocupa de cerrar en otros puntos (por ejemplo, "el canal por el que sale la alerta... lo fija el intent `infra`", en `Assumptions & Open Questions`). | Añadir una entrada en `Assumptions & Open Questions` de `security-requirements.md` (o de `nfr-requirements-questions.md`) que diga explícitamente qué hereda U15 de esta decisión (la política y el esquema de la tabla de topes) y qué le queda por decidir en su propia etapa (si sus proveedores de voz ofrecen tope duro, y si no, cómo declara su fila siguiendo el mismo esquema). | New |
| R-02 | Minor | `.../nfr-requirements/security-requirements.md` § "Objetivos medibles", fila `PA-9.1` | El comando declarado (`mise run schema:check`) valida hoy contra JSON Schema y contra un puñado de comprobaciones Python a medida (`schema_check.py`: manifiesto de evals, catálogo de copy, reconocedores, configuración por aseguradora), pero el requisito de `PA-9.1` — "usos... cuya última comprobación tiene más de treinta días" — es una comprobación relativa a la fecha de hoy, no una propiedad estática del archivo, y no es algo que un JSON Schema pueda expresar por sí solo (un `format: date` valida forma, no vigencia). El documento no aclara que esta parte de `PA-9.1` necesitará lógica Python nueva dentro de `schema_check.py` (como ya tienen `_revisar_reconocedores` u otras funciones del mismo archivo), no solo una entrada de esquema. | Añadir una frase en la fila o en la sección de claves que aclare que la comprobación de vigencia (los treinta días) es lógica de aplicación añadida a `schema_check.py`, no una restricción de JSON Schema, para que quien implemente no intente expresarla como tal. | New |

### Summary

El documento principal (`security-requirements.md`) y sus seis acompañantes son coherentes entre sí, con el diseño funcional de U5, con los documentos aprobados de Incepción y con el estado real del repositorio: cada cifra que se pudo calcular (la reserva de grabación, la equivalencia NFR14/D7, el conteo de dependencias y de controles) cuadra, y cada afirmación sobre `mise.toml`, `pyproject.toml`, `docker-compose.yml`, `settings.py` y `.env.example` se sostuvo al leer el archivo citado. Los ocho hallazgos del comprobador de artefactos son el hueco temporal esperado y ya explicado (comandos que nacen con `infrastructure-design`, todavía sin escribir), confirmado contra el precedente de U4. El único hueco real es de reparto entre unidades: PA-9 está formalmente asignado a `nfr-requirements` de U5 **y** U15, y U5 lo resuelve sin dejar escrito qué le corresponde a U15 cuando llegue su turno — un patrón que el resto del documento sí sigue consistentemente para otros puntos que decide un intent o una unidad futura.

---

### Resolución (escrita por la conducción, 2026-09-21)

El veredicto queda como el revisor lo escribió: **READY**, con sus dos hallazgos
y su `Status: New`, que es el estado en que se encontraron. **Los dos se
reprodujeron contra la fuente y los dos eran ciertos.**

| ID | ¿Era cierto? | Cómo se comprobó | Qué se hizo |
|---|---|---|---|
| R-01 | Sí | `unit-of-work.md` línea 1164 y `contract-summary.md` línea 1701 asignan PA-9 a `nfr-requirements` de **U5 y U15**, en plural. `grep U15` sobre los ocho artefactos: la palabra solo aparecía en `tech-stack-decisions.md`, para decir que U15 añade sus adaptadores, nunca para repartir PA-9 | `security-requirements.md` gana un párrafo, "Qué hereda U15 y qué le queda por decidir": U15 hereda la política y el esquema —una alerta nunca cuenta como tope, el saldo prepagado lo sustituye, la tabla lleva la figura y la fecha con su compuerta de treinta días— y llena las filas de sus proveedores de voz, que son otros. `nfr-requirements-questions.md` lo dice también en Q1, donde se tomó la decisión |
| R-02 | Sí | `schema_check.py` valida archivos contra su esquema y contra un puñado de comprobaciones Python a medida. Una vigencia de treinta días se mide contra la fecha de hoy; `format: date` valida forma, no frescura | La fila `PA-9.1` ahora parte el objetivo en sus dos mitades y dice cuál es de esquema y cuál es lógica añadida a `schema_check.py`, para que quien lo implemente no intente expresarla como restricción de esquema |

**Una secuencia que conviene dejar escrita, porque es la segunda vez.** Los dos
arreglos se aplicaron **después** de registrar el recibo, no antes. La razón es
mecánica y ya costó una restauración en el diseño funcional de esta misma
unidad: el registrador rechaza un veredicto cuyos documentos cambiaron después
del despacho, y esta etapa admite una sola pasada, así que no hay forma de
arreglar entre el informe y el recibo. **Este recibo certifica los bytes que el
revisor leyó**, con los dos huecos dentro; los bytes de hoy son los arreglados, y
el control de cambios relajado lo hace visible como aviso en vez de esconderlo.

**Comprobaciones después de los arreglos** (ejecutadas, no leídas):

- `aidlc engine sensor fire traceability --stage nfr-requirements ...` →
  `"result":"passed"`.
- `python3 scripts/check-artifacts.py .../u5-provider-platform` → 8 hallazgos,
  los mismos ocho de antes y de la misma forma: `mise run test:u5` y
  `mise run spend:report` citados sin existir todavía. El propio revisor
  comprobó el mecanismo y el precedente de U4 y concluyó que es el hueco
  temporal esperado, que se cierra en `infrastructure-design`.
