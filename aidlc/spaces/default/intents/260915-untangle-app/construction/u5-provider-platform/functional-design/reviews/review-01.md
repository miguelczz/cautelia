## Review

**Reviewer:** aidlc-architecture-reviewer-agent
**Iteration:** 1
**Verdict:** NOT-READY
**Date:** 2026-09-21T03:28:47Z

### Herramientas de validación

| Herramienta | Resultado | Interpretación |
| --- | --- | --- |
| `python3 scripts/check-artifacts.py .../construction/u5-provider-platform` | `u5-provider-platform: sin hallazgos` (Total: 0) | Ningún chequeo estructural automático (secciones, escapes, referencias sueltas) marcó nada. No cubre coherencia semántica entre documentos ni contra el código vivo, que es lo que reporto abajo. |
| `aidlc engine sensor fire traceability --stage functional-design --output-path .../traceability.json` | `"result":"passed"` | El sensor de trazabilidad valida forma (IDs bien formados, cobertura declarada) pero no verifica que el contenido de la regla de destino sea coherente con la entidad que dice gobernar; los hallazgos R-02 y R-04 sobreviven a este passed. |

### Comprobaciones cuantitativas hechas contra la fuente (no contra la prosa)

- **Reglas por familia**: conté los bloques `- id: BR` dentro del YAML de `rules.md`. BR1=7 (BR1.1–BR1.7), BR2=5 (BR2.1–BR2.5), BR3=8 (BR3.1–BR3.8), BR4=8 (BR4.1–BR4.8), BR5=9 (BR5.1–BR5.9), BR6=7 (BR6.1–BR6.7), BR7=6 (BR7.1–BR7.6). Total 50. Coincide exactamente con la tabla resumen de `rules.md` y con la de `functional-spec.md` §5.
- **Entidades guardadas**: conté los bloques bajo `# --- Lo que se guarda ---` en `entities.md`: `SpendEntry`, `QuotaCounter`, `BudgetWindow`, `TraceSummary` = 4. Coincide con la tabla "Resumen" del mismo archivo.
- **Objetos de valor**: conté los bloques bajo `# --- Lo que no se guarda ---`: `Use`, `PriceEntry`, `Money`, `SpendTotal`, `BudgetState`, `QuotaDecision`, `CallReserve`, `VoiceMode`, `PromptRef`, `GenerationResult`, `UsageReport`, `ProviderError`, `BudgetExhausted`, `ProviderCap`, `NodeTiming` = 15. Coincide con lo afirmado.
- **Decisiones FD-U5**: conté las filas de la tabla en `functional-spec.md` §6: FD-U5-1 a FD-U5-10 = 10. Coincide.
- **Criterios aguas arriba**: conté `upstream_ids` en `traceability.json`: 5 (AC4.8.*) + 5 (AC4.12.*) + 6 (AC5.14.*) = 16. Coincide con `coverage` (16 entradas 1:1).
- **Reglas en el arreglo inverso**: conté los objetos de `reverse` en `traceability.json` = 37 (BR1: 7, BR2: 4, BR3: 4, BR4: 5, BR5: 9, BR6: 3, BR7: 5). Coincide con lo afirmado. Verifiqué además que la unión de las reglas cubiertas en `coverage` (15 reglas únicas: BR6.1–BR6.5, BR3.2, BR3.3, BR3.6, BR3.7, BR3.8, BR2.5, BR4.3, BR4.4, BR4.7, BR7.5) con las 37 de `reverse` (2 solapadas: BR6.5 y BR3.6) suma exactamente 50: ninguna de las 50 reglas queda sin mención en `traceability.json`.
- **Lista de exclusión de aislamiento vigente**: leí `app/backend/pyproject.toml` líneas 184-187 — `[tool.untangle.rls] excluded` tiene una sola entrada (`alembic_version`). Coincide con lo que Q1 y `entities.md`/`rules.md` afirman ("hoy tiene una sola entrada").
- **Comportamiento de `evaluate()` en `rls_assertion.py`**: leí el código — para una tabla en la lista de exclusión, la función simplemente hace `continue` (línea ~112 de `rls_assertion.py`); no existe ningún chequeo de columnas de texto libre ni de dato personal sobre tablas excluidas. La "aserción nueva" que FD-U5-1/BR7.2 prometen no existe todavía en el código — consistente con que esto es diseño funcional para trabajo futuro, pero ver R-04 sobre si, tal como está redactada, es implementable.

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Major | `aidlc/.../construction/u5-provider-platform/functional-design/rules.md` BR3.4 (`applies_to: "SpendEntry, TraceSummary, Money"`) vs `entities.md` entidades `TraceSummary` y `Money` | BR3.4 dice: "SI el estado es `measured` ENTONCES el precio unitario, la versión de la lista, su fecha y el costo están los cuatro presentes" y declara que aplica a `SpendEntry, TraceSummary, Money`. Pero `entities.md` define `TraceSummary` con solo dos columnas de costo (`cost_usd`, `cost_status`) y `Money` con solo dos atributos (`amount_usd`, `status`); ninguna de las dos tiene `unit_price_usd`, `price_list_version` ni `price_list_effective_date`. La invariante de "los cuatro presentes" solo puede cumplirse literalmente para `SpendEntry`. | Acotar el `applies_to` de BR3.4 a `SpendEntry` (o a las cuatro columnas de precio), y escribir una regla distinta — con la invariante real de dos columnas (`cost` + `status`) — para `TraceSummary` y `Money`, o explicar por qué el mismo enunciado debe leerse de forma distinta según la entidad. | New |
| R-02 | Major | `aidlc/.../construction/u5-provider-platform/functional-design/functional-spec.md` §4, bloque `TRACE_SUMMARY` del diagrama `mermaid erDiagram`, frente a `entities.md` entidad `TraceSummary` | `entities.md` declara `nodes` como atributo de `TraceSummary` (`type: list of NodeTiming, required: true`, con su propia restricción sobre el estado `recording`). El bloque `TRACE_SUMMARY { ... }` del diagrama ER derivado en `functional-spec.md` §4 no incluye ese campo (lista: `trace_id, tenant_id, case_id, visitor_key_hash, turn_ref, clauses_retrieved, clauses_verified, latency_ms, cost_usd, cost_status, status, created_at` — 12 de los 13 atributos reales). La prosa que sigue al diagrama menciona que "`NodeTiming` vive dentro del resumen de traza", pero no repara el atributo faltante en el bloque tabular del diagrama. | Añadir `nodes` (con su tipo, p. ej. `NodeTiming[]` o una nota de "colección anidada") al bloque `TRACE_SUMMARY` del diagrama, para que la vista derivada tenga fila a fila los mismos atributos que `entities.md`. | New |
| R-03 | Major | `aidlc/spaces/default/intents/260915-untangle-app/inception/requirements-analysis/requirements.md` línea 86 (FR3.11) frente a toda la unidad U5 (`entities.md` `BudgetWindow`, `rules.md` BR4.1–BR4.8, `functional-spec.md` §2.1 y §7) | FR3.11 —enmendada el mismo 2026-09-19 que FR3.9, a la que `functional-design-questions.md` Q4 cita explícitamente— exige: "El presupuesto de voz reserva una porción intocable para grabar el video final y para la sesión de escucha, que el enlace público no puede consumir", y que "con el cupo público agotado, una llamada marcada como grabación sigue atendiéndose hasta agotar su reserva". `BudgetWindow` (única fila, `cap_usd`/`billable_spent_usd` globales) y BR4.4 ("Alcanzado el techo, la voz rechaza las llamadas nuevas... y el chat sigue") no dejan espacio para una reserva separada e intocable ni para una excepción por "llamada marcada como grabación": el modelo de datos y las reglas de esta unidad tratan el corte como binario y único. Ningún archivo de U5 menciona FR3.11, ni siquiera en la sección "Assumptions & Open Questions" de `functional-spec.md`, que sí registra otros huecos vecinos de FR3.9 (la reserva por llamada, el canal de alerta, el corte del reinicio). | Añadir a `entities.md`/`rules.md` una segunda reserva presupuestaria (o un campo de "reserva intocable" en `BudgetWindow`) y una regla que permita que una llamada marcada como grabación se sirva aun con `exhausted`, consumiendo esa reserva y no el cupo público; si se decide diferir esto a `nfr-requirements` o a otra unidad, dejarlo escrito como pregunta abierta en vez de en silencio. | New |
| R-04 | Major | `aidlc/.../construction/u5-provider-platform/functional-design/rules.md` BR7.2, contrastada con `app/backend/src/untangle/tenancy/rls_assertion.py` y el resto del repositorio | BR7.2 exige que la aserción nueva falle si una tabla excluida tiene "una columna de tipo texto sin restringir, o con un nombre de la lista de datos personales". No existe en ningún artefacto de U5 ni en el código (`grep` sobre `app/backend/src/untangle` no encontró ninguna "lista de datos personales" con nombres de columna) una definición de qué lista es esa, dónde vive, ni cómo se compara un nombre de columna contra ella (coincidencia exacta, subcadena, insensible a mayúsculas). Los reconocedores de PII existentes (`compliance/redaction/recognizers`) detectan **valores** en texto libre, no nombres de columna de esquema, así que no son la misma lista sin más trabajo de diseño. A diferencia de otros huecos de esta etapa (PA-9, el canal de alerta, la reserva por llamada), este no está declarado como pregunta abierta. | Definir en `entities.md` o `rules.md` dónde vive la lista de nombres de columna considerados dato personal (archivo de configuración versionado, con qué entradas) y la regla de comparación exacta, o mover el punto a "Assumptions & Open Questions" si se decide en `nfr-requirements`. | New |
| R-05 | Minor | `aidlc/.../construction/u5-provider-platform/functional-design/rules.md` BR4.5 (`violation`), frente a D7/AC5.14.5 (`stories.md`) y FR3.9 (`requirements.md`) | BR4.5 afirma en su campo `violation`: "a estas cifras, el exceso máximo es menor que un centavo". Pero D7/AC5.14.5 fijan el costo del modelo en 0,005 USD por minuto, y FR3.9 fija el límite de 3 minutos por llamada: solo el modelo de una llamada al límite ya cuesta 0,015 USD (1,5 centavos), antes de sumar transcripción y síntesis, que AC5.14.5 declara explícitamente "sin meta". La cifra de "menos de un centavo" no se sostiene con los números que la misma unidad y sus historias ya fijan. | Corregir la cifra citada en la `violation` de BR4.5 (o quitarla si no se puede acotar con precisión), dejando la lógica central de la regla (consultar antes, registrar después) intacta. | New |

### Summary

El diseño está bien numerado y bien trazado —las cinco comprobaciones cuantitativas cuadran exactamente, y la lista de exclusión de aislamiento vigente en el código coincide con lo que el diseño describe—, pero tiene cuatro problemas de coherencia semántica que un desarrollador no podría resolver sin volver a preguntar al arquitecto: una regla (BR3.4) que impone una invariante de cuatro columnas a dos entidades que no las tienen, un campo requerido (`TraceSummary.nodes`) que se pierde entre `entities.md` y el diagrama derivado, un requisito aprobado y enmendado el mismo día que Q4 (FR3.11, la reserva intocable para el video final) que esta unidad no menciona en ninguna parte pese a ser justamente la unidad dueña del presupuesto, y una regla de aislamiento (BR7.2) que depende de una lista que no existe en ningún lado del repositorio ni del diseño.

---

### Resolución (escrita por la conducción, 2026-09-21)

El veredicto se deja como el revisor lo escribió: **NOT-READY**. La tabla de
hallazgos también queda tal cual, con su `Status: New`, que es el estado en que
se encontraron.

**Los cinco se reprodujeron contra la fuente y los cinco eran ciertos.**

Un detalle de secuencia que conviene dejar escrito, porque se va a repetir. El
arreglo se escribió antes de registrar el recibo, y el registrador lo rechazó
con razón: un veredicto no se puede atar a unos documentos que cambiaron después
de despacharse. Los cuatro archivos se devolvieron a los bytes que el revisor
leyó, el veredicto quedó registrado tal cual —NOT-READY— y solo después, con el
Request Changes de Miguel ("Aplica los cinco arreglos de la revisión, empezando
por la reserva de grabación de FR3.11.", 2026-09-21), se volvió a aplicar el
arreglo. **Este recibo certifica los bytes con los cinco defectos dentro**, que
es exactamente lo que el revisor leyó; los bytes de hoy son los arreglados, y el
control de cambios relajado lo hace visible como aviso en vez de esconderlo.

La tabla siguiente es qué se comprobó de cada hallazgo y qué se aplicó.

| ID | ¿Era cierto? | Cómo se comprobó | Qué se hizo |
|---|---|---|---|
| R-01 | Sí | `entities.md` declara `TraceSummary` con dos columnas de costo (`cost_usd`, `cost_status`) y `Money` con dos atributos (`amount_usd`, `status`); ninguna tiene las cuatro columnas de precio que BR3.4 exigía | BR3.4 se acota a `SpendEntry`. La invariante común —cantidad presente exactamente cuando el estado es `measured`— pasa a una regla propia, **BR3.9**, que aplica a las tres formas. El cierre de `rules.md` se reescribió para que la pareja que se lee junta sea BR3.9 + BR3.5 |
| R-02 | Sí | El bloque `TRACE_SUMMARY` del diagrama ER tenía 12 de los 13 atributos de `entities.md`: faltaba `nodes` | Se añadió `list nodes "NodeTiming, requerido; vacia solo en recording"`. De paso se añadieron al diagrama las columnas nuevas de R-03 (`lane`, `recording_reserve_usd`, `recording_spent_usd`), que si no habrían nacido ya desalineadas |
| R-03 | Sí, y es el hallazgo caro | `sed -n '86p' requirements.md` devuelve FR3.11 con su enmienda del 2026-09-19, la misma fecha que FR3.9, que Q4 sí cita. `grep FR3.11` sobre los cinco artefactos de U5: cero apariciones | Se añadió el segundo carril de presupuesto: `SpendEntry.lane`, `BudgetWindow.recording_reserve_usd` y `recording_spent_usd`, las reglas **BR4.9** (la reserva que el enlace público no puede tocar) y **BR4.10** (solo la marca quien tiene credencial), el ciclo de vida de §2.1 reescrito sobre el presupuesto **público**, BR5.6 y F6 dividiendo el resto público y no el total, BR4.4 acotada al enlace público, y las decisiones FD-U5-11 y FD-U5-12. **Cuánto vale** la reserva queda declarado como pregunta abierta para `nfr-requirements`: FR3.11 dice que existe y para qué, no cuánto, y no se inventa una cifra |
| R-04 | Sí | `grep -rn "lista de datos personales"` sobre `app/backend/src` y sobre los artefactos de U5: la lista no existe en ningún lado | BR7.2 ahora dice dónde vive (el manifiesto `app/backend/pyproject.toml`, al lado de la lista de exclusión que paga), cómo se compara (subcadena sin distinguir mayúsculas sobre el nombre de la columna), y con qué catorce entradas arranca. Se añadió la petición a U2 en §7 y la decisión FD-U5-13 |
| R-05 | Sí | D7 fija 0,005 USD por minuto de modelo y FR3.9 fija 3 minutos por llamada: 0,015 USD solo de modelo, antes de transcripción y síntesis. "Menos de un centavo" no se sostiene | Se quitó la cifra. BR4.5 ahora acota el exceso a **la llamada al proveedor que estaba en vuelo** —que es lo que de verdad acota— y remite la cota numérica a `nfr-requirements`, cuando los precios por minuto estén medidos |

**Comprobaciones sobre la versión arreglada** (todas ejecutadas, no leídas, y
repetidas después de volver a aplicarla):

- `rules.md`: 53 reglas, BR1=7 BR2=5 BR3=9 BR4=10 BR5=9 BR6=7 BR7=6. Las dos
  tablas resumen —la de `rules.md` y la de `functional-spec.md` §5— se
  actualizaron a esas cifras, y la frase de cabecera dejó de decir que la
  familia más grande es la de las cuotas, porque ahora es la del techo.
- `traceability.json`: 16 criterios aguas arriba, 40 reglas en el arreglo
  inverso, unión exacta de 53 sin reglas huérfanas ni destinos inexistentes,
  comprobado por script contra los identificadores reales de `rules.md`.
- `functional-spec.md`: 13 decisiones FD-U5, y la prosa de §6 corregida para
  decir seis delegadas, siete de la etapa y tres nacidas de esta revisión.
- `entities.md`: 4 entidades guardadas y 15 objetos de valor, sin cambio.
- `python3 scripts/check-artifacts.py ...` → `Total: 0`.
- `aidlc engine sensor fire traceability ...` → `"result":"passed"`.

**Lección mecánica, para las diecisiete unidades que faltan.** Con
`review_class: advisory` y una sola pasada, el veredicto NOT-READY es terminal y
congela los documentos igual que un READY. Eso deja exactamente dos momentos
para arreglar: **antes** de despachar la revisión, o **después** de un Request
Changes del humano. No hay un tercero entre el informe del revisor y el
registro del recibo, que es donde se intentó aquí: el registrador lo cierra. En
U4 pasó lo mismo por otra puerta y quedó anotado; esta vez el costo fue una
restauración de cuatro archivos y una pregunta a Miguel.
