# Entidades — U9 `rules-decision`

- **Configuración:** las reglas viven versionadas en
  `app/config/tenants/<aseguradora>/rules/triage.yaml` (C-25), con el modelo
  `RuleSet` que ya dejó U2.
- **Tabla propia:** U9 guarda una sola cosa, `rule_evaluation`, el resultado de
  aplicar las reglas a un caso. Tiene aislamiento por aseguradora y entra en el
  contrato de borrado de U2.

## Entidades

```yaml
entities:

  - name: RuleDefinition
    description: Una regla versionada de una aseguradora (C-25). Ya existe en tenancy/models.py; U9 le agrega la validación de sus condiciones.
    stored_in: "app/config/tenants/<aseguradora>/rules/triage.yaml"
    attributes:
      - { name: id, type: identifier, required: true, unique: true, constraint: "Prefijo de la aseguradora y número, por ejemplo STO-R-003." }
      - { name: version, type: integer, required: true, min: 1 }
      - { name: when, type: Condition, required: true, constraint: "Operadores cerrados: equals, in, present, absent, gte, lte; combinadores all, any, not; o always: true en la regla por defecto y en la de la agencia (Q1, Q2, BR1.3)." }
      - { name: then.category, type: enum, required: true, allowed_values: [direct_close, standard_review, referral] }
      - { name: then.touches_money, type: boolean, required: true, default: false, constraint: "Marca de cobertura o dinero: si dispara, la categoría es referral (AC1.15.4)." }
      - { name: then.explanation_key, type: identifier, required: true, constraint: "Clave del catálogo de copy, en los dos idiomas, sin identificadores de regla ni jerga." }
      - { name: tests, type: "list of {given, expect}", required: true, constraint: "Al menos uno por regla (M5)." }

  - name: RuleSet
    description: El archivo de reglas de una aseguradora.
    attributes:
      - { name: ruleset_version, type: string, required: true }
      - { name: rules, type: "list of RuleDefinition", required: true, constraint: "Entre 10 y 20 reglas (AC1.15.1), exactamente una por defecto." }

  - name: RuleEvaluation
    description: El resultado de evaluar un caso. Se guarda y se adjunta al caso (fired_rules de U4).
    stored_in: "tabla rule_evaluation, con aislamiento por aseguradora"
    attributes:
      - { name: evaluation_id, type: uuid, required: true, unique: true }
      - { name: tenant_id, type: identifier, required: true }
      - { name: case_id, type: uuid, required: true, references: "Case (U4), llave compuesta con tenant_id" }
      - { name: ruleset_version, type: string, required: true }
      - { name: category, type: enum, required: true, allowed_values: [direct_close, standard_review, referral] }
      - { name: fired_rules, type: "list of {id, version, touches_money}", required: true, constraint: "Nunca vacía: al menos la regla por defecto." }
      - { name: inputs_snapshot, type: "map field → value", required: true, constraint: "Solo los campos que leyeron las reglas disparadas, ya redactados por U3 si llevan datos personales." }
      - { name: explanation_key, type: identifier, required: true }
      - { name: evaluated_at, type: timestamp, required: true }
```

## Resumen

- **Reglas:** `RuleDefinition` y `RuleSet` son configuración versionada. U9 les
  agrega la validación de condiciones, el conteo y la regla por defecto.
- **Resultado:** `RuleEvaluation` es la única fila que U9 escribe. La categoría
  viene siempre con sus reglas disparadas, sus insumos y su clave de explicación.
