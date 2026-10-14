## Review

**Reviewer:** aidlc-architecture-reviewer-agent
**Iteration:** 1
**Verdict:** READY
**Date:** 2026-09-20T22:25:07Z

### Herramientas de validación

| Herramienta | Resultado | Interpretación |
| --- | --- | --- |
| `python3 scripts/check-artifacts.py .../construction/u4-case-record` | `u4-case-record: sin hallazgos` (Total: 0) | Sin problemas estructurales detectados por el comprobador del proyecto. |
| `aidlc engine sensor fire traceability --stage functional-design --output-path .../traceability.json` | `"result":"passed"` | El sensor de trazabilidad no encuentra huecos de forma (IDs de `BRx.y` referenciados que no existen, unidades `Deferred` inexistentes, etc.). |

Ambas herramientas solo comprueban forma, no semántica: los dos hallazgos
mayores de abajo son coherencia semántica entre documentos, invisibles para
ellas.

### Comprobaciones cuantitativas hechas contra la fuente (no contra la prosa)

- **42 reglas en 7 familias** (BR1:8, BR2:8, BR3:9, BR4:6, BR5:4, BR6:4, BR7:3):
  contadas por script sobre el bloque `yaml` de `rules.md`; coincide exactamente
  con lo que afirma `rules.md` (encabezado) y `functional-spec.md` (§5).
- **Trece criterios**: US1.8 aporta 4 (AC1.8.1–4), US1.14 aporta 4 (AC1.14.1–4)
  y US4.10 aporta 5 (AC4.10.1–5) en `stories.md` = 13, y coincide con
  `upstream_ids` de `traceability.json`.
- **Siete campos centrales del siniestro, siete estados, cuatro resoluciones,
  tres tipos de registro**: coinciden literalmente entre FR1.1/FR1.4 de
  `requirements.md`, ADR-005 de `decisions.md` y `entities.md`/`rules.md`.
- **Tabla de transiciones vs. diagrama Mermaid**: las 12 filas de la tabla en
  `functional-spec.md` §2 aparecen una a una, con el mismo origen/destino, en el
  `stateDiagram-v2`. Los siete estados son alcanzables desde `open` y ningún
  estado no terminal queda sin salida; `closed` es el único terminal.

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Major | `aidlc/spaces/default/intents/260915-untangle-app/construction/u4-case-record/functional-design/traceability.json` > cobertura de `AC1.8.3`, cruzada con `entities.md` > `CaseParty` y `rules.md` > `BR2.2`/`BR2.4` | AC1.8.3 ("Placa confirmada") describe confirmar la placa del **otro vehículo** — un atributo de `CaseParty` (rol `other_vehicle`), no del campo `vehicle_and_driver` del `Case` (que es del vehículo del propio asegurado, según el FieldKey de BR1.4). `traceability.json` mapea AC1.8.3 a BR2.2/BR2.4, pero esas reglas declaran `applies_to: CaseField` y no existe ningún estado, evidencia ni marca de confirmación para los atributos de `CaseParty` en `entities.md` (sus únicos atributos son texto simple, sin `status` ni `evidence_*`). No hay ninguna regla en `rules.md` que gobierne cómo "la placa del otro vehículo" llega a estar confirmada ni cómo se distingue de un valor simplemente tecleado sin confirmar. | Añadir a `CaseParty` (o a un objeto de valor propio) un estado y una evidencia de confirmación equivalentes a los de `CaseField`, con su propia regla `BR1.x`/`BR2.x`, y corregir el destino de AC1.8.3 en `traceability.json` para que apunte a esa regla nueva en vez de a BR2.2/BR2.4. | New |
| R-02 | Major | `aidlc/spaces/default/intents/260915-untangle-app/inception/contract-design/contract-summary.md` > C-12 (`CaseView.record_type`) y C-05 (`record_type` de la cola de la bandeja), cruzado con `rules.md` > BR1.1 y la decisión FD-U4-5 de `functional-spec.md` §6 | La decisión FD-U4-5 de esta etapa fija el valor del enum como `coverage_inquiry` (siguiendo a ADR-005) y así lo escriben `entities.md` y `rules.md`. Pero el contrato C-12 —cuyo dueño es esta misma unidad U4— y el contrato C-05 (bandeja, U14) siguen declarando literalmente `Literal["claim", "coverage_question", "quote_request"]`. La sección 7 de `functional-spec.md` ("Lo que esta unidad pide a otras") no incluye ninguna petición de corregir C-12 ni avisa a U14 sobre C-05. Un desarrollador que implemente `case_record/api.py` siguiendo el contrato firmado (C-12) escribiría `coverage_question`, contradiciendo `rules.md`/`entities.md` de la misma unidad. | Añadir a la sección 7 (o a las decisiones) una acción explícita para corregir el literal `coverage_question` → `coverage_inquiry` en C-12 (que esta unidad posee) y avisar a U14 `inbox` de la misma corrección pendiente en C-05, antes de que Code Generation escriba código contra el contrato desactualizado. | New |
| R-03 | Minor | `aidlc/spaces/default/intents/260915-untangle-app/construction/u4-case-record/functional-design/functional-spec.md` > decisión FD-U4-8 y tabla de transiciones (fila T10) | ADR-005 fija literalmente: "**Única** vuelta atrás: de `derived` a `capturing`...". FD-U4-8 añade T10 (`awaiting_insured` → `derived`), que estructuralmente también es una arista hacia atrás (deshace T8), y la justifica con una lectura estrecha de "vuelta atrás" ("volver a poner el caso en manos de la persona para seguir capturando") que ADR-005 no formula explícitamente. Esta es exactamente el tipo de hueco con dos lecturas legítimas que la práctica del proyecto reserva para pregunta con opción recomendada, y no aparece en `functional-design-questions.md` entre las cuatro preguntas que sí se hicieron. La interpretación es defendible (T10 evita el atasco que AC1.14.4 exige en cero) y no rompe el modelo cerrado —T10 vive en la tabla versionada—, así que no bloquea la implementación, pero es una desviación sobre una decisión de arquitecto que valdría la pena confirmar explícitamente con Miguel o registrar como enmienda de ADR-005. | Confirmar con Miguel si T10 requiere una enmienda explícita de ADR-005 (como se hizo el 2026-09-17 con otras precisiones), o dejar constancia en `decisions.md` de que "única vuelta atrás" se limita al sentido de "retomar la captura" y no a toda arista hacia un estado anterior. | New |

### Summary

El documento es internamente consistente en sus cifras (42 reglas, 7 familias,
13 criterios, 7 estados/12 transiciones con diagrama fiel a la tabla) y las
herramientas de validación no encuentran huecos de forma. Los dos hallazgos
mayores son de coherencia semántica entre artefactos aprobados: un criterio de
aceptación (AC1.8.3) que el modelo de datos no puede satisfacer tal como está
descrito, y un valor de enum que el propio contrato que esta unidad posee (C-12)
sigue contradiciendo tras la decisión de esta etapa. Ninguno exige rediseñar la
unidad — ambos se resuelven añadiendo una regla y corrigiendo dos literales—,
así que el veredicto es READY con estas dos correcciones señaladas para la
compuerta.
