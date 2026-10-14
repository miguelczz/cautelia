# Especificación funcional — U9 `rules-decision`

Fuente de verdad de los flujos de U9. Los datos están en `entities.md` y las
decisiones en `rules.md`. Respuestas aplicadas:
- **Q1:** operadores cerrados, sin lenguaje de expresiones.
- **Q2:** gana la categoría más prudente y hay una regla por defecto.
- **Q3:** casos de DS-2 corridos por una sonda antes de que exista el chat.

## 1. Qué hace esta unidad

- **Carga** las reglas de cada aseguradora y las valida: el conteo, los
  operadores, la regla por defecto y las pruebas de cada regla.
- **Evalúa** un caso sin modelo y devuelve la categoría, las reglas disparadas,
  los insumos y la clave de explicación.
- **El nodo `decision`** guarda esa evaluación, la adjunta al caso y entrega el
  turno a `compliance`.

**Lo que U9 no hace, y quién lo hace:**
- Las reglas de elegibilidad y la banda de cotización: U19.
- Lo que la agente dice al cerrar: U10 ya tiene las frases en el catálogo, y
  U12 las conecta al grafo.
- El cierre y la resolución: los decide el nodo `compliance` de U10 tras su
  revisión.
- La vista del caso por enlace firmado: U14.
- La meta de derivaciones sobre DS-2 completo: U21.

## 2. Flujos

### F1 — Cargar las reglas de una aseguradora

1. U2 lee `rules/triage.yaml` con `RuleSet`.
2. U9 valida cada regla:
   - los operadores y los campos (BR1.2);
   - el conteo y la regla por defecto (BR1.1 y BR1.3);
   - y ejecuta las pruebas de cada regla (BR1.4).
3. Si algo falla, esa aseguradora no arranca y el error nombra la regla. Las
   demás siguen.

### F2 — Evaluar un caso

1. Se leen los campos del caso que usan las reglas (`required_inputs`).
2. Cada regla evalúa su condición con los operadores cerrados.
3. Se decide la categoría:
   - si alguna regla disparada toca dinero o cobertura, es `referral` (BR2.3);
   - si no, gana la más prudente (BR2.2);
   - si solo disparó la regla por defecto, es `standard_review`.
4. Se devuelven las reglas disparadas, los insumos que leyeron y la clave de
   explicación de la regla que decidió (BR2.4).

### F3 — Nodo `decision`

1. El grafo llega al nodo con el caso.
2. El nodo evalúa, guarda `RuleEvaluation` y marca `fired_rules` como adjunto
   del caso (C-12).
3. Devuelve `compliance` como siguiente nodo, por una función pura (BR3.1).
4. Si falla, aplica su política de fallo declarada como dato: un reintento y el
   texto de degradación.

## 3. Reglas (resumen derivado de `rules.md`)

| Familia | Reglas |
| --- | --- |
| Conjunto de reglas | BR1.1 a BR1.4 |
| Evaluación | BR2.1 a BR2.6 |
| Nodo | BR3.1 |
| Borrado | BR4.1 |

## 4. Decisiones de esta etapa

| # | Decisión | Por qué |
| --- | --- | --- |
| FD-U9-1 | Operadores cerrados, evaluados por código (Q1) | Sin dependencia nueva ni superficie de inyección |
| FD-U9-2 | La categoría más prudente gana; una regla de dinero fuerza la derivación; hay una regla por defecto (Q2) | FR6.2 y P1: ninguna categoría sin su regla, y ante la duda, una persona |
| FD-U9-3 | Casos de DS-2 con campos y categoría esperada, corridos por una sonda (Q3) | La rama evaluada exige el caso antes de la conducta; el chat llega en U13 |
| FD-U9-4 | Las explicaciones se chequean contra la lista de jerga del proyecto | AC1.15.2: lo que lee el asegurado no nombra reglas ni jerga |

## Sources

- `../../../inception/units-generation/unit-of-work.md` — sección U9.
- `../../../inception/user-stories/stories.md` — US1.15 y US1.17.
- `../../../inception/requirements-analysis/requirements.md` — FR6.1 a FR6.5.
- `../../../inception/domain-design/components.md` — RulesEngine y
  DecisionNode.
- `../../../inception/contract-design/contract-summary.md` — C-12, C-15, C-19 y
  C-25.
- `app/backend/src/untangle/tenancy/models.py` — `RuleSet` y `RuleDefinition`.

## Assumptions & Open Questions

- **Qué reglas concretas tiene cada aseguradora** se escribe en el plan de
  código. Siguen el PRD: heridos, terceros sin datos, montos, sospecha de fraude
  y conductor no listado derivan; lo simple y sin terceros de Sunmeadow cierra
  directo; Knotwell deriva siempre.
