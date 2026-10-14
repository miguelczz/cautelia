# Reglas de negocio — U9 `rules-decision`

Son 12 reglas en cuatro familias: el conjunto de reglas, la evaluación, el nodo
`decision` y el borrado.

## Reglas

El bloque siguiente es la fuente de verdad; la tabla resumen se deriva de él.

```yaml
rules:

  - id: BR1.1
    statement: Cada aseguradora tiene entre 10 y 20 reglas versionadas, cada una con al menos una prueba.
    category: validation
    applies_to: "rules/triage.yaml de las tres aseguradoras"
    trigger: "Al cargar la configuración y en schema:check."
    logic: "SI una aseguradora tiene menos de 10 o más de 20 reglas, o una regla no trae prueba ENTONCES la carga falla nombrando la aseguradora y la regla."
    violation: "Esa aseguradora no arranca; las demás siguen (C-19, C-25)."
    source: AC1.15.1, FR6.1

  - id: BR1.2
    statement: Las condiciones usan solo el conjunto cerrado de operadores, sobre campos que existen en el esquema del caso.
    category: validation
    applies_to: "RuleDefinition.when"
    trigger: "Al cargar."
    logic: "SI una condición usa un operador fuera de equals, in, present, absent, gte, lte, all, any, not, o un campo que el esquema del caso no tiene ENTONCES la carga falla con el identificador de la regla."
    violation: "Error de carga con la regla y la clave rota."
    source: Q1, C-19

  - id: BR1.3
    statement: Cada conjunto trae exactamente una regla por defecto, que siempre dispara con revisión estándar; otra regla que dispare siempre solo puede derivar.
    category: validation
    applies_to: "RuleSet"
    trigger: "Al cargar."
    logic: "SI no hay exactamente una regla con always: true y categoría standard_review, o una regla con always: true tiene una categoría distinta de standard_review y referral ENTONCES la carga falla. Enmendada en la generación de código (2026-09-21): la regla de la agencia (BR2.6) también usa always: true, porque cualquier otra condición depende de que un campo esté lleno."
    violation: "Error de carga con la regla que falla."
    source: Q2, FR6.2, BR2.6

  - id: BR1.4
    statement: Cada regla pasa sus propias pruebas al cargar el conjunto en las pruebas y en schema:check.
    category: validation
    applies_to: "RuleDefinition.tests"
    trigger: "En test:u9 y schema:check."
    logic: "Para cada prueba de cada regla, evaluar la regla sola sobre given debe dar expect."
    violation: "La prueba nombra la regla y el caso."
    source: AC1.15.1, M5

  - id: BR2.1
    statement: La evaluación es determinista y no invoca ningún modelo.
    category: constraint
    applies_to: "rules/ y orchestration/nodes/decision/"
    trigger: "Siempre."
    logic: "El paquete rules no importa providers ni ningún cliente de modelo; la misma entrada da la misma salida."
    violation: "El contrato de importación falla; la prueba de determinismo falla."
    source: AC1.15.3, FR6.3

  - id: BR2.2
    statement: Cuando disparan varias reglas gana la categoría más prudente.
    category: calculation
    applies_to: "evaluate"
    trigger: "En cada evaluación."
    logic: "referral sobre standard_review sobre direct_close. La regla por defecto aporta standard_review solo si ninguna otra regla disparó, y solo entonces aparece en fired_rules."
    violation: "La prueba de precedencia falla."
    source: Q2, FR6.2

  - id: BR2.3
    statement: Una regla de cobertura o dinero que dispara fuerza la derivación.
    category: policy
    applies_to: "evaluate"
    trigger: "En cada evaluación."
    logic: "SI alguna regla disparada tiene touches_money ENTONCES la categoría es referral, sin importar las demás."
    violation: "Compuerta dura: ningún caso con una regla de dinero sale como cierre directo (AC1.17.3)."
    source: AC1.15.4, AC1.17.3, P1

  - id: BR2.4
    statement: Toda evaluación trae sus reglas disparadas, sus insumos y una clave de explicación.
    category: validation
    applies_to: "RuleEvaluationView"
    trigger: "En cada evaluación."
    logic: "fired_rules nunca está vacía; inputs_snapshot trae solo los campos que leyeron las reglas disparadas; explanation_key es la de la regla que decidió la categoría."
    violation: "La prueba falla."
    source: AC1.15.2, FR6.2

  - id: BR2.5
    statement: Los textos de explicación no nombran identificadores de regla ni términos de la lista de jerga.
    category: validation
    applies_to: "Claves de explicación en el catálogo de copy, en los dos idiomas"
    trigger: "En copy:check o content:check."
    logic: "SI un texto de explicación contiene un identificador de regla o un término de la lista de jerga (FNOL, tenant, endoso sin explicar) ENTONCES el chequeo falla."
    violation: "El chequeo nombra la clave."
    source: AC1.15.2

  - id: BR2.6
    statement: La agencia deriva siempre por una regla de su archivo, sin rama de código.
    category: policy
    applies_to: "rules/triage.yaml de Knotwell"
    trigger: "Siempre."
    logic: "Knotwell trae una regla con always: true y categoría referral (BR1.3). El código no conoce aseguradoras: tenancy:literals y la prueba de que el código de decisión no contiene identificadores de aseguradora lo comprueban."
    violation: "tenancy:literals falla."
    source: FR6.4

  - id: BR3.1
    statement: El nodo decision evalúa, guarda la evaluación y la adjunta al caso, y devuelve el siguiente nodo por una función pura.
    category: policy
    applies_to: "orchestration/nodes/decision"
    trigger: "Cuando el grafo llega al nodo."
    logic: "Llama a evaluate, guarda RuleEvaluation, marca fired_rules como adjunto del caso y devuelve compliance como siguiente nodo. Sin modelo; con su NodeSpec de tiempo máximo, un reintento y texto de degradación (política de fallo como dato)."
    violation: "Las pruebas del nodo fallan."
    source: AC1.17.1, C-15, project.md (política de fallo como dato)

  - id: BR4.1
    statement: Las evaluaciones de casos de visitantes se borran con su caso.
    category: policy
    applies_to: "tabla rule_evaluation"
    trigger: "En el borrado de U2."
    logic: "La tabla tiene política de aislamiento, llave compuesta hacia el caso y entra en el contrato de borrado, con su prueba (UG-3)."
    violation: "rls:check o la prueba de borrado fallan."
    source: UG-3, M9
```

## Resumen

| ID | Regla |
| --- | --- |
| BR1.1 | Entre 10 y 20 reglas, cada una con su prueba |
| BR1.2 | Operadores cerrados sobre campos del caso |
| BR1.3 | Exactamente una regla por defecto |
| BR1.4 | Cada regla pasa sus pruebas |
| BR2.1 | Determinista y sin modelo |
| BR2.2 | Gana la categoría más prudente |
| BR2.3 | Dinero o cobertura: siempre derivación |
| BR2.4 | Reglas disparadas, insumos y explicación siempre |
| BR2.5 | Explicaciones sin identificadores ni jerga |
| BR2.6 | La agencia deriva por regla |
| BR3.1 | El nodo evalúa, guarda y pasa a compliance |
| BR4.1 | Borrado con su caso |
