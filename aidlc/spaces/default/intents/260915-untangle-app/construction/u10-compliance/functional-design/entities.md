# Entidades — U10 `compliance`

Tres entidades se guardan, las tres colgadas de un caso: la divulgación
registrada, cada intervención de la guardia y la revisión completa al cierre.
Las tres son **dato de visitante**: llevan la aseguradora con su política, la
marca de dato de visitante y se borran con su caso. Ninguna guarda texto libre de
la persona ni del modelo; lo que dijo cada uno ya vive, redactado, en la
transcripción de U4.

Lo demás son objetos de valor que no se guardan: los conjuntos de patrones
versionados, el resultado de la guardia y las señales de los controles del turno.

## Entidades

```yaml
entities:

  # --- Lo que se guarda --------------------------------------------------------

  - name: DisclosureRecord
    description: >
      Que la apertura con la divulgación de inteligencia artificial salió, en qué
      canal, en qué idioma y cuándo (FR7.1). Una por caso y canal: un caso de voz
      retomado por chat lleva dos.
    identifier: disclosure_id
    attributes:
      - { name: disclosure_id, type: identifier, required: true, unique: true }
      - { name: tenant_id, type: TenantId, required: true, references: "Tenant (U2)" }
      - { name: case_id, type: identifier, required: true, references: "Case (U4)" }
      - { name: channel, type: enum, required: true, allowed_values: [chat, voice] }
      - { name: language, type: Locale, required: true, allowed_values: [es, en] }
      - { name: catalog_key, type: CopyKey, required: true, constraint: "La clave de la apertura que salió, no su texto." }
      - { name: disclosed_at, type: timestamp, required: true }
    constraints:
      - "Única por (case_id, channel): registrarla dos veces no crea dos filas (BR4.2)."
    relationships:
      - { target: Case, cardinality: "n a 1", direction: "DisclosureRecord pertenece a Case" }

  - name: GuardIntervention
    description: >
      Una frase que la guardia no dejó salir y qué salió en su lugar. Guarda la
      categoría y el patrón que la detectó, **no la frase original**: la frase
      podría contener lo que el visitante dijo y lo que sí salió ya está en la
      transcripción.
    identifier: intervention_id
    attributes:
      - { name: intervention_id, type: identifier, required: true, unique: true }
      - { name: tenant_id, type: TenantId, required: true, references: "Tenant (U2)" }
      - { name: case_id, type: identifier, required: true, references: "Case (U4)" }
      - { name: turn_id, type: identifier, required: true, references: "TranscriptTurn (U4)" }
      - name: category
        type: enum
        required: true
        allowed_values: [coverage_promise, amount, fault, legal_advice, humanity_claim, transfer_or_deadline, config_disclosure]
      - { name: pattern_id, type: string, required: true, constraint: "Identificador estable del patrón, por ejemplo guard.es.coverage_promise.003." }
      - { name: action, type: enum, required: true, allowed_values: [substituted, dropped, not_evaluable] }
      - { name: catalog_key, type: CopyKey, required: false, constraint: "La frase permitida que salió; nula cuando la frase se descartó." }
      - { name: occurred_at, type: timestamp, required: true }
    relationships:
      - { target: Case, cardinality: "n a 1", direction: "GuardIntervention pertenece a Case" }
      - { target: TranscriptTurn, cardinality: "n a 1", direction: "GuardIntervention corrige la salida de un turno" }

  - name: ComplianceReview
    description: >
      La revisión completa de los cuatro controles sobre la conversación, hecha
      al cierre o en la derivación (FR7.7). Su resultado se adjunta al caso.
    identifier: review_id
    attributes:
      - { name: review_id, type: identifier, required: true, unique: true }
      - { name: tenant_id, type: TenantId, required: true, references: "Tenant (U2)" }
      - { name: case_id, type: identifier, required: true, references: "Case (U4)" }
      - { name: disclosure_ok, type: boolean, required: true }
      - { name: human_route_ok, type: boolean, required: true }
      - { name: pii_ok, type: boolean, required: true }
      - { name: explainability_ok, type: boolean, required: true }
      - name: findings
        type: "list ComplianceFinding"
        required: true
        constraint: "Lista cerrada de códigos, nunca texto libre; vacía si todo pasó."
      - { name: reviewed_through_turn, type: identifier, required: true, constraint: "Último turno revisado: el de la derivación si la hubo (AC1.16.4)." }
      - { name: reviewed_at, type: timestamp, required: true }
    constraints:
      - "Única por (case_id, reviewed_through_turn): repetir la revisión del mismo punto no crea otra fila."
    relationships:
      - { target: Case, cardinality: "n a 1", direction: "ComplianceReview se adjunta a Case" }

  # --- Lo que no se guarda ------------------------------------------------------

  - name: PatternSet
    description: >
      Los patrones versionados de un idioma para una categoría de la guardia, la
      petición de persona, la pregunta de identidad o la emergencia, con sus
      patrones negativos. Viven como datos en el repositorio, no en el código.
    identifier: "(language, family, version)"
    attributes:
      - { name: language, type: Locale, required: true, allowed_values: [es, en] }
      - { name: family, type: enum, required: true, allowed_values: [guard, human_request, identity_question, emergency] }
      - { name: version, type: string, required: true }
      - { name: patterns, type: "list Pattern (id, category, expresión sobre texto normalizado)", required: true }
      - { name: negations, type: "list Pattern", required: false, constraint: "Solo en emergencia: 'todos estamos bien', 'fue un golpecito'." }

  - name: GuardResult
    description: Lo que devuelve la guardia por cada frase.
    attributes:
      - { name: text_out, type: string, required: false, constraint: "La frase original, la permitida del catálogo, o nula si se descartó." }
      - { name: interventions, type: "list GuardIntervention sin persistir", required: true }
      - { name: evaluated, type: boolean, required: true, constraint: "Falso solo cuando falló la evaluación; entonces text_out es la clave de degradación (BR1.5)." }

  - name: TurnSignals
    description: Las señales de los controles del turno sobre lo que dijo la persona.
    attributes:
      - { name: human_request, type: boolean, required: true }
      - { name: identity_question, type: boolean, required: true }
      - { name: emergency, type: boolean, required: true }

  - name: ComplianceFinding
    description: Un control que no pasó, con su código cerrado.
    attributes:
      - name: code
        type: enum
        required: true
        allowed_values: [disclosure_missing, human_route_missed, pii_found, attachment_missing]
      - { name: detail_key, type: CopyKey, required: true, constraint: "Qué falta, dicho por el catálogo para la bandeja." }

  - name: ClosureDecision
    description: Lo que el nodo `compliance` devuelve al runtime.
    attributes:
      - { name: outcome, type: enum, required: true, allowed_values: [close, refer, refused] }
      - name: reason_code
        type: enum
        required: false
        allowed_values: [rule, compliance, human_request, emergency, limit, unverifiable]
        constraint: "La lista cerrada de C-04 (TurnHandoff). Obligatoria en refer."
      - { name: missing, type: "list ComplianceFinding", required: false, constraint: "Obligatoria en refused: qué falta para cerrar (AC1.16.1)." }
```

## Resumen

| Entidad | Se guarda | Para qué |
| --- | --- | --- |
| `DisclosureRecord` | Sí, dato de visitante | Probar que la agente dijo que es una IA (FR7.1) |
| `GuardIntervention` | Sí, dato de visitante | Rastro de cada frase que no salió, sin su texto |
| `ComplianceReview` | Sí, dato de visitante | Los cuatro controles al cierre (FR7.7) |
| `PatternSet` | En el repositorio | Patrones versionados por idioma |
| `GuardResult`, `TurnSignals` | No | Resultados de los controles del turno |
| `ComplianceFinding`, `ClosureDecision` | No | Qué falta y qué decide el nodo de cierre |
