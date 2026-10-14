# Entidades — U1 `workspace`

El modelo de datos de la unidad base: el catálogo de textos y el registro de las
corridas de evaluación. Es una descripción lógica, independiente de la
tecnología: no dice tipos de base de datos ni nombres de tabla.

**Fuentes consumidas.** `../../../inception/units-generation/unit-of-work.md`
(U1 crea `CopyEntry`, `GoldenCase`, `EvalRun` y `CaseResult`),
`../../../inception/units-generation/unit-of-work-story-map.md` (US4.4, US5.8 y
US4.7), `../../../inception/requirements-analysis/requirements.md` (FR11.1 y
FR11.3), `../../../inception/domain-design/components.md` (los atributos que fija
la tabla de propiedad de entidades) y
`../../../inception/contract-design/contract-summary.md` (C-21 catálogo, C-22
registro de objetivos y conductores, C-27 casos y líneas base).

Dos entidades las **completa U21** más adelante: `EvalRun.comparable` con su
causa, y `CaseResult.root_cause`. U1 las crea con esos campos ya presentes para
que el corredor no tenga que cambiar de forma después.

**Lo que este diseño añade a la lista aprobada en Domain Design**, cada campo con
la regla que lo obliga: `CopyEntry.decision` (BR3.5), `GoldenCase.tenant` y
`GoldenCase.channel` (el caso corre contra una aseguradora y por un canal),
`EvalRun.duration_seconds` (BR1.8) y `EvalRun.subset_declared` (BR1.6),
`CaseResult.not_measured_cause` (BR1.4) y `CaseResult.off_script_turns` (BR2.2).
Se añaden además dos entidades que el catálogo no nombraba porque viven en
archivos y no en tablas: `ScriptAnswer` (el guion por campo que exige la decisión
Q1) y `SubsetDefinition` (la lista versionada que exige la decisión Q2). Ninguna
contradice el catálogo: lo precisan donde una conducta acordada necesitaba un
dato que no tenía nombre.

## Modelo

```yaml
entities:
  - name: CopyEntry
    description: >
      Una frase que lee una persona, en un idioma. El catálogo es la única
      fuente de texto visible del sistema; ningún módulo escribe texto en línea.
    identifier: [key, locale]
    attributes:
      - name: key
        type: string
        required: true
        constraints: >
          Jerárquica con puntos y siempre literal en el código
          (`voice.opening.disclosure`). Nunca se construye concatenando en
          tiempo de ejecución, porque eso impediría comprobar si tiene
          consumidor.
      - name: locale
        type: enum
        allowed_values: [es, en]
        required: true
      - name: text
        type: string
        required: true
      - name: version
        type: integer
        required: true
        default: 1
        constraints: Entero que sube en uno cada vez que la frase cambia.
      - name: decision
        type: string
        required: false
        constraints: >
          Identificador de la decisión que cambió la frase (por ejemplo `D26`).
          Obligatorio cuando `version` es mayor que 1.
      - name: surface
        type: enum
        allowed_values: [voice, chat, inbox, panel, system]
        required: true
        constraints: Dónde se muestra la frase; agrupa el catálogo por consumidor.
    entity_constraints:
      - Cada `key` existe en los dos idiomas; una sin pareja es un fallo del chequeo.
      - Cada `key` tiene al menos un consumidor literal en el código.
      - Ninguna frase contiene una forma de la lista versionada de formas prohibidas.
    relationships: []

  - name: GoldenCase
    description: >
      Un caso de prueba versionado, uno por archivo, con el guion del asegurado
      simulado y lo que se espera que el sistema produzca.
    identifier: [case_key]
    attributes:
      - name: case_key
        type: string
        required: true
        unique: true
        constraints: >
          Identificador estable con la forma `<dataset>/<idioma>/<secuencia>`,
          por ejemplo `DS-2/es/017`. Es la moneda de todo el sistema: el
          reporte, el diff contra la línea base y la sección "Cómo falla" lo
          usan sin traducir.
      - name: dataset
        type: enum
        allowed_values: [DS-1, DS-2, DS-3, DS-4, DS-5, DS-6, DS-7, DS-8]
        required: true
      - name: language
        type: enum
        allowed_values: [es, en]
        required: true
      - name: tenant
        type: string
        required: false
        constraints: >
          Aseguradora contra la que corre el caso. Obligatoria en los conjuntos
          de conversación y de aislamiento, porque la conducta esperada depende
          de las reglas y del corpus de esa aseguradora; ausente en los casos que
          no tocan una aseguradora.
      - name: channel
        type: enum
        allowed_values: [chat, voice]
        required: false
        constraints: Qué conductor ejecuta el caso; ausente en los conjuntos que no son conversación.
      - name: axes
        type: list of string
        required: false
        constraints: Etiquetas del caso (por ejemplo `correcciones`, `emocion`); describen, no seleccionan.
      - name: script
        type: list of ScriptAnswer
        required: true
        constraints: >
          Las respuestas del asegurado simulado, **indexadas por campo**. Precisa
          el ejemplo de C-27, que mostraba una lista plana de turnos: la decisión
          Q1 de este diseño exige emparejar por campo, así que el guion deja de
          ser una secuencia y pasa a ser un índice. U1 es dueño de este formato
          (C-27), así que el ejemplo del contrato se actualiza con él.
      - name: expected_record
        type: map
        required: true
        constraints: El estado y los campos que el caso debe producir.
      - name: expected_verdicts
        type: map
        required: false
        constraints: El veredicto esperado por criterio de evaluación.
    entity_constraints:
      - Vive como un archivo versionado en el repositorio; nunca se genera en tiempo de corrida.
      - Un conjunto declarado como no construido lo dice con su razón, y sus casos no existen.
    relationships:
      - with: CaseResult
        cardinality: one-to-many
        direction: Un caso produce un resultado por corrida.

  - name: ScriptAnswer
    description: >
      Una respuesta del asegurado simulado, atada al campo que la provoca. Es
      parte del archivo del caso, no una entidad con vida propia.
    identifier: [case_key, field_key, sequence]
    attributes:
      - name: field_key
        type: string
        required: true
        constraints: El campo del caso que esta respuesta contesta (`incident.location`).
      - name: sequence
        type: integer
        required: true
        default: 1
        constraints: >
          Orden dentro del mismo campo. La secuencia 1 es la primera respuesta;
          las siguientes son correcciones que se entregan una sola vez.
      - name: text
        type: string
        required: true
      - name: kind
        type: enum
        allowed_values: [answer, correction]
        required: true
        default: answer
    entity_constraints:
      - Dos respuestas del mismo campo no comparten `sequence`.
    relationships:
      - with: GoldenCase
        cardinality: many-to-one
        direction: Cada respuesta pertenece a un caso.

  - name: SubsetDefinition
    description: >
      La lista nombrada de casos que corre una corrida parcial. Vive como
      archivo versionado, no como tabla: su reproducibilidad depende de estar en
      el mismo commit que los casos.
    identifier: [name]
    attributes:
      - name: name
        type: string
        required: true
        unique: true
        constraints: Nombre corto del subconjunto (`smoke`, `gate`).
      - name: case_keys
        type: list of string
        required: true
        constraints: Identificadores de caso, uno por línea, en orden estable.
      - name: reason
        type: string
        required: true
        constraints: Por qué existe este subconjunto.
    entity_constraints:
      - Todo `case_key` de la lista existe como archivo de caso; uno que no exista detiene la corrida.
    relationships:
      - with: EvalRun
        cardinality: one-to-many
        direction: Una definición puede usarse en muchas corridas.

  - name: EvalRun
    description: Una ejecución del corredor de evaluaciones.
    identifier: [run_id]
    attributes:
      - name: run_id
        type: string
        required: true
        unique: true
      - name: commit_sha
        type: string
        required: true
      - name: subset
        type: string
        required: false
        constraints: Nombre de la definición de subconjunto; ausente en una corrida completa.
      - name: model_ids
        type: map
        required: true
        constraints: >
          Identificador exacto del modelo por uso, nunca un alias móvil, más el
          hash del prompt de cada nodo.
      - name: comparable
        type: boolean
        required: true
        default: true
        constraints: Falso cuando la corrida no se puede comparar contra la línea base.
      - name: non_comparable_cause
        type: enum
        allowed_values: [provider_unavailable, provider_timeout, quota_exhausted, model_changed, not_measured_cases]
        required: false
        constraints: Obligatorio cuando `comparable` es falso.
      - name: subset_declared
        type: boolean
        required: true
        default: false
        constraints: Lo que el reporte declara al lector; verdadero cuando `subset` está presente.
      - name: duration_seconds
        type: integer
        required: true
        constraints: Se mide siempre y se publica en el reporte.
      - name: started_at
        type: timestamp
        required: true
      - name: finished_at
        type: timestamp
        required: false
    entity_constraints:
      - Una corrida con al menos un resultado `not_measured` tiene `comparable` en falso.
    relationships:
      - with: CaseResult
        cardinality: one-to-many
        direction: Una corrida produce un resultado por caso ejecutado.

  - name: CaseResult
    description: El veredicto de un caso dentro de una corrida.
    identifier: [result_id]
    attributes:
      - name: result_id
        type: string
        required: true
        unique: true
      - name: run_id
        type: string
        required: true
        references: EvalRun.run_id
      - name: case_key
        type: string
        required: true
        references: GoldenCase.case_key
      - name: status
        type: enum
        allowed_values: [passed, failed, not_measured]
        required: true
        constraints: >
          `not_measured` es el caso que no se pudo ejecutar por causa externa;
          nunca se cuenta como `failed`. U21 añade más adelante la marca de caso
          inestable, que se reporta aparte.
      - name: not_measured_cause
        type: enum
        allowed_values: [provider_unavailable, provider_timeout, quota_exhausted, budget_exhausted, runner_timeout, provider_key_missing]
        required: false
        constraints: >
          Obligatorio cuando `status` es `not_measured`. `provider_key_missing`
          se añadió el 2026-09-19: es el caso que no se ejecutó porque la clave
          del proveedor no está en el entorno, y existe para que el subconjunto
          de arranque corra sin clave dejando dicho, caso por caso, qué no se
          midió (BR1.2 enmendada).
      - name: criteria_results
        type: map
        required: false
        constraints: Veredicto por criterio de evaluación.
      - name: off_script_turns
        type: integer
        required: true
        default: 0
        constraints: Turnos en los que el respondedor no tenía respuesta para el campo preguntado.
      - name: root_cause
        type: string
        required: false
        constraints: Causa raíz según la taxonomía del PRD; la completa U21.
      - name: trace_ref
        type: string
        required: false
        constraints: Enlace a la traza; ausente cuando el backend de trazas no estaba corriendo.
    entity_constraints:
      - Un resultado `failed` sin criterio fallido es inválido.
      - Un resultado `not_measured` siempre trae su causa.
    relationships:
      - with: EvalRun
        cardinality: many-to-one
        direction: Cada resultado pertenece a una corrida.
      - with: GoldenCase
        cardinality: many-to-one
        direction: Cada resultado evalúa un caso.
```

## Resumen

Seis entidades en dos grupos que no se tocan entre sí:

| Entidad | Para qué está | Dónde vive |
| --- | --- | --- |
| `CopyEntry` | Toda frase que lee una persona, en los dos idiomas | Archivos de catálogo versionados, cargados al arrancar |
| `GoldenCase` | Un caso de prueba con su guion y lo que se espera | Un archivo por caso, versionado |
| `ScriptAnswer` | Una respuesta del asegurado simulado, atada a su campo | Dentro del archivo del caso |
| `SubsetDefinition` | Qué casos corre una corrida parcial | Archivo versionado |
| `EvalRun` | Una ejecución del corredor | Registro de la corrida |
| `CaseResult` | El veredicto de un caso en esa corrida | Registro de la corrida |

Lo que **no** está aquí y llega con U21: la línea base contra la que se compara,
la calibración del juez y la marca de caso inestable. U1 deja los campos que esas
piezas rellenan (`comparable`, `non_comparable_cause`, `root_cause`) para que el
corredor no cambie de forma cuando lleguen.
