## Review

**Verdict:** NOT-READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-09-21T02:46:10Z
**Iteration:** 1

Revisión asesora de `code-generation` de U4 `case-record`: los 13 archivos con
código del módulo, los dos chequeos de `workspace/`, la revisión de migración,
las pruebas de `tests/unit/case_record/` y `tests/integration/u4/`, los dos YAML
del esquema y el catálogo de textos, contra `code-generation-plan.md`,
`code-summary.md`, `traceability.json`, `functional-design/rules.md` y
`nfr-requirements/security-requirements.md`. Comprobado en vivo: `mise run
test:u4` (147 pasan en la versión despachada), `mise run test` (467), `mise run
cov` (agregado 87,41 %, `case_record` 93,70 %), `case:constructor`,
`case:transitions` (12 transiciones, el diagrama coincide), `types`, `lint`,
`migrate:check`, `rls:check` (7 tablas con política y el rol sin poder saltarse
ninguna), `copy:check` y `check-artifacts.py` (0 hallazgos). Ninguna de las 131
funciones de prueba es tautológica, y las cifras del resumen son ciertas una por
una.

**El veredicto es NOT-READY** y se deja escrito tal cual, sin lavarlo: la
afirmación de que las 42 reglas están impuestas no se sostenía. Dos de las
marcadas `OK` no tenían imposición en el archivo que la trazabilidad señala, y
se comprobó ejecutando. La más seria es BR2.2: un campo que exige lectura de
confirmación llegaba a `confirmed` sin ella y la completitud lo contaba. Además,
el punto único de cifrado tenía cuatro vías de escape que su propio chequeo no
miraba, y las dos operaciones que escriben caso e historial lo hacían en
transacciones separadas.

Nada de esto comprometía el aislamiento por aseguradora, la redacción ni el
disparador de solo anexar, que están bien cerrados y con prueba viva. Los once
hallazgos quedaron **resueltos antes de cerrar la etapa**, cada uno verificado
ejecutando antes de tocar nada y con su prueba nueva; la evidencia está debajo
de la tabla.

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Major | `case_record/fields.py` — `validate_field` | BR2.2 marcada `OK` y nada rechazaba que `injuries`, `location` o `vehicle_and_driver` llegaran a `confirmed` sin lectura de confirmación ni evidencia de bandeja. Comprobado ejecutando: el modelo se construye, `validate_field` devuelve el campo y la completitud lo cuenta. `fields.py` imponía el umbral de completitud, que es BR2.6, no BR2.2 | Rechazar `confirmed` en un campo con `requires_readback` que no traiga `confirmed_aloud_at` ni `evidence_change_id`, con su prueba | Resolved |
| R-02 | Major | `case_record/api.py` — `set_field`, `apply_transition` | Cada llamada al repositorio abría su propia transacción, así que un fallo del anexado dejaba un campo escrito sin entrada en el historial, que es lo que BR5.1 llama una pérdida. En la transición la asimetría era la inversa: un fallo del `UPDATE` dejaba un `transition_applied` de algo que no ocurrió | Envolver la pareja escritura-más-entrada en una sola transacción y probar que el primer paso se revierte | Resolved |
| R-03 | Major | `workspace/case_constructor.py` — `_firma_silenciada`, `visit_Call` | Cuatro escapes verificados sobre árboles sintéticos: argumento solo por palabra clave, solo posicional, de resto variable, y llamada al constructor por alias de importación. El último fabrica un sellado real en claro que el repositorio escribiría en la columna cifrada | Recorrer las cinco posiciones de argumento y resolver los alias de importación; aplicar lo mismo al chequeo hermano de U3 | Resolved |
| R-04 | Major | `case_record/repository.py` — `ACTUALIZAR_CASO` | BR6.4 marcada `OK` y el `UPDATE` reescribía `closing_evidence` sin guardia. Hoy nadie llega ahí porque `closed` es terminal, pero eso es ausencia de camino y no rechazo, y vive en otro archivo | Dejar la evidencia fuera del `UPDATE` una vez escrita, o poner la guardia en la sentencia | Resolved |
| R-05 | Major | `case_record/rules.py` — `TransitionContext` | Las cuatro condiciones de T12 se evaluaban sobre datos que aporta enteros quien llama. U4 es dueño de `case_change`, donde vive la entrada que dice cuándo entró en `derived`, y no la leía | Derivar la marca dentro de U4 desde su propio historial y documentar en C-12 qué queda a cargo del consumidor | Resolved |
| R-06 | Major | `contract-summary.md` — C-12, frente a `case_record/api.py` | Las seis firmas de C-12 divergen de lo implementado y la divergencia no estaba registrada. El proyecto sí tiene ritual para esto: FD-U4-5 registró la corrección de `coverage_question` en el propio contrato | Enmendar C-12 con las firmas reales y su razón | Resolved |
| R-07 | Minor | `case_record/api.py` — superficie pública | BR7.3 se dispara al consultar por identificador **o por número**, y la superficie no ofrecía la consulta por número. La verificación que declara SEC-U4.14 tampoco tenía prueba | Añadir la consulta por número con su prueba de aislamiento, o diferir esa mitad con su dueño | Resolved |
| R-08 | Minor | `case_record/api.py` — docstring del módulo | El docstring decía seis operaciones y `__all__` exportaba siete. Es la clase de comentario que `team.md` nombra como deuda TD-03 | Corregir el docstring nombrando el cierre y su razón | Resolved |
| R-09 | Minor | `case_record/crypto.py` — `active()` | El mensaje manda a `Cipher.from_environment()`, que no existe: el constructor es `from_settings`. Es lo que va a leer quien arranque el proceso sin cifrador | Cambiar el mensaje al nombre real | Resolved |
| R-10 | Minor | `tests/integration/u4/test_api.py` — la prueba de la superficie | Comparaba contra cuatro nombres literales, así que un `amend_change` la pasaría sin cambiar nada del código: afirmaba una convención de nombres y no la conducta que SEC-U4.11 promete | Comprobar la conducta, o apoyarse en la prueba del disparador, que sí la comprueba | Resolved |
| R-11 | Minor | `case_record/api.py` — `set_field` | Nada rechazaba fijar un campo de un caso ya cerrado, así que la evidencia congelada seguiría atestiguando algo que ya no es (BR6.4, NFR-U4-9) | Decidirlo explícitamente: rechazarlo con su prueba, o escribirlo como hueco conocido | Resolved |

### Evidencia de resolución

**R-01.** `validate_field` rechaza `confirmed` en un campo que exige lectura y no
trae ni la marca de lectura ni evidencia de bandeja. Cuatro pruebas nuevas en
`test_fields.py` cubren los cuatro casos: confirmado sin lectura (rechazado),
con lectura (pasa), corregido desde la bandeja (pasa, por BR2.5), y un campo que
no exige lectura (pasa). La regla rompió una prueba propia que construía
`location` confirmado sin lectura, que era el mismo defecto en los datos.

**R-02.** El repositorio acepta una sesión ya abierta, y `api.set_field`,
`apply_transition` y `close_case` abren una y la pasan a las dos operaciones.
Dos pruebas nuevas provocan el fallo del segundo paso y comprueban que el
primero se revirtió: cero campos escritos, cero entradas en el historial.

**R-03.** Los dos chequeos recorren ahora `posonlyargs`, `args`, `kwonlyargs`,
`vararg` y `kwarg`, y resuelven los alias de importación del tipo en cada
archivo antes de comparar nombres. Cuatro casos parametrizados en
`test_constructor_check.py` plantan las cuatro vías; las cuatro se atrapan.

**R-04.** `ACTUALIZAR_CASO` usa `COALESCE`, así que la evidencia que ya estaba se
conserva y la nueva solo entra si no había ninguna.

**R-05.** `history.derived_at` saca del propio historial la última entrada de
transición a `derived`, y `api.apply_transition` la usa cuando el consumidor no
la aporta. Dos pruebas nuevas: una lleva el caso a derivado y lee la marca sin
pasarla, otra comprueba que sin historial de derivación no hay ventana.

**R-06.** C-12 lleva una enmienda fechada con las seis firmas reales, su razón
una por una, y las dos operaciones de más con la suya.

**R-07.** `get_case_by_number` en la superficie, con dos pruebas: el caso se
encuentra por su número, y un número de otra aseguradora responde igual que uno
inexistente. La prueba que declara la superficie exacta falló al aparecer la
operación nueva, que es lo que existe para hacer.

**R-08.** El docstring dice ocho y nombra las dos que no son de C-12 con su
razón.

**R-09.** El mensaje dice `install(Cipher.from_settings(opciones))`.

**R-10.** La prueba busca por lo que hace: cualquier nombre exportado que
contenga `change` y empiece por un verbo de modificación. La conducta de verdad
la comprueba el disparador de la base, en `test_migration.py`.

**R-11.** `set_field` levanta `CaseClosedError` sobre un caso cerrado.

### Estado tras la resolución

`mise run test:u4` 161 pasan, `mise run test` 481, cobertura agregada 87,47 % y
93,73 % en el módulo del caso, y `scripts/verify.sh` en verde los nueve pasos.
