# Entidades — U4 `case-record`

El registro del caso es la **fuente de verdad del negocio**. El punto de control
del grafo (U12) guarda la ejecución reanudable, no el caso; si los dos se
contradijeran, manda el caso (enmienda de ADR-005).

Cinco entidades se guardan —el caso, sus campos, sus partes, su transcripción y
su historial— y siete objetos de valor no se guardan: existen para que un valor
inválido no se pueda escribir, no para ocupar una tabla.

El bloque siguiente es la fuente de verdad; el resumen que va después se deriva
de él.

```yaml
entities:

  # --- Lo que se guarda ------------------------------------------------------

  - name: Case
    description: >
      Un siniestro, una consulta de cobertura o una solicitud de cotización de
      una sola aseguradora. Es la raíz: campos, partes, turnos y cambios
      cuelgan de aquí y no existen sin él.
    identifier: case_id
    attributes:
      - name: case_id
        type: identifier
        required: true
        unique: true
        constraint: "Opaco. No se deriva del número de caso ni lo reemplaza."
      - name: tenant_id
        type: identifier
        required: true
        references: "Tenant (U2 `tenancy`)"
        constraint: "Toda lectura y escritura pasa por el punto único de sesión que ya lo fijó (BR7.1)."
      - name: case_number
        type: CaseNumber
        required: true
        unique: "dentro de la aseguradora"
        constraint: "Inmutable desde que se crea el caso (BR4.3)."
      - name: record_type
        type: RecordType
        required: true
        allowed_values: [claim, coverage_inquiry, quote_request]
        constraint: "Inmutable. Cambiar de tipo cambiaría la lista de campos y con ella la completitud ya publicada."
      - name: state
        type: CaseState
        required: true
        default: open
        allowed_values: [open, capturing, verifying, deciding, derived, awaiting_insured, closed]
      - name: resolution
        type: Resolution
        required: false
        allowed_values: [registered, approved, rejected, sent_to_insurer]
        constraint: "Exactamente una cuando el estado es `closed`; ninguna en cualquier otro estado (BR3.4, BR3.5)."
      - name: channel
        type: Channel
        required: true
        allowed_values: [voice, chat]
        constraint: "El canal por el que nació el caso. Un caso de voz retomado por chat conserva `voice` aquí; el canal de cada turno vive en el turno."
      - name: origin
        type: Origin
        required: true
        allowed_values: [public_chat, public_voice_console, local_deployment, generator]
        constraint: "`public_chat` y `public_voice_console` son dato de visitante y los borra el reinicio nocturno (BR7.2)."
      - name: language
        type: Language
        required: true
        allowed_values: [es, en]
        constraint: "El idioma con el que se abrió. Puede cambiar si la persona cambia de idioma; cada turno guarda el suyo."
      - name: policy_ref
        type: identifier
        required: false
        references: "IssuedPolicy (U8 `policy-rag`)"
        constraint: "A lo sumo una, la que se confirmó al identificarse. Nula mientras no se haya identificado."
      - name: derivation_reason
        type: DerivationReason
        required: false
        allowed_values: [demo_limit, person_requested, rule]
        constraint: "Obligatoria cuando el estado es `derived`; nula en cualquier otro estado (BR3.7)."
      - name: priority
        type: Priority
        required: true
        default: normal
        allowed_values: [normal, high]
        constraint: "`high` cuando el motivo de derivación es `person_requested` (BR3.8)."
      - name: completeness
        type: Completeness
        required: true
        constraint: "Derivada de los campos del caso. No se escribe a mano ni se guarda como número suelto (BR2.8)."
      - name: closing_evidence
        type: ClosingEvidence
        required: false
        constraint: "Nula mientras el caso no esté cerrado; una vez escrita no cambia. Es lo que el caso comprobó al cerrarse (BR6.3)."
      - name: created_at
        type: timestamp
        required: true
      - name: updated_at
        type: timestamp
        required: true
      - name: closed_at
        type: timestamp
        required: false
        constraint: "No nula si y solo si el estado es `closed`."
    constraints:
      - "Un caso cerrado lleva resolución, `closed_at` y evidencia de cierre, las tres o ninguna."
      - "Un caso derivado lleva motivo de derivación."
      - "El número de caso no cambia nunca."
    relationships:
      - target: CaseField
        cardinality: "1 a N"
        direction: "el caso tiene sus campos"
      - target: CaseParty
        cardinality: "1 a N"
        direction: "el caso tiene sus partes"
      - target: TranscriptTurn
        cardinality: "1 a N"
        direction: "el caso tiene su transcripción"
      - target: CaseChange
        cardinality: "1 a N"
        direction: "el caso tiene su historial"
      - target: "Tenant (U2)"
        cardinality: "N a 1"
        direction: "cada caso pertenece a una sola aseguradora"
      - target: "IssuedPolicy (U8)"
        cardinality: "N a 0..1"
        direction: "cada caso se asocia a lo sumo a una póliza emitida"

  - name: CaseField
    description: >
      Un campo del caso con lo que se dijo, cuán seguro está y **qué lo
      respalda**. La evidencia es la mitad del punto: sin ella, "sin lesiones"
      y "nadie preguntó por las lesiones" serían el mismo dato.
    identifier: "case_id + field_key"
    attributes:
      - name: case_id
        type: identifier
        required: true
        references: Case
      - name: field_key
        type: FieldKey
        required: true
        constraint: "Uno de los campos que el esquema versionado declara para el tipo de registro del caso (BR1.3)."
      - name: value
        type: text
        required: false
        constraint: "Nulo cuando el estado es `not_stated`. Un campo sin valor nunca vale 'ninguno' por omisión (BR2.3)."
      - name: status
        type: FieldStatus
        required: true
        default: not_stated
        allowed_values: [not_stated, stated, confirmed]
      - name: evidence_turn_id
        type: identifier
        required: false
        references: TranscriptTurn
        constraint: "El turno en el que la persona lo dijo."
      - name: evidence_change_id
        type: identifier
        required: false
        references: CaseChange
        constraint: "La entrada del historial cuando el valor lo escribió una persona desde la bandeja (BR2.5)."
      - name: confirmed_aloud_at
        type: timestamp
        required: false
        constraint: "No nulo si y solo si el estado es `confirmed` y el valor vino de la conversación."
      - name: updated_at
        type: timestamp
        required: true
    constraints:
      - "Con estado `stated` o `confirmed`, exactamente una de las dos evidencias es no nula; con `not_stated`, las dos son nulas (BR2.4)."
      - "`injuries`, `location` y `vehicle_and_driver` solo llegan a `confirmed` con la lectura de confirmación o con una corrección de la bandeja (BR2.2)."

  - name: CaseParty
    description: >
      Una persona o un vehículo más del accidente: lesionado, testigo, otro
      conductor u otro vehículo. Es el grupo repetible, y admite datos que
      faltan sin inventarlos.
    identifier: party_id
    attributes:
      - name: party_id
        type: identifier
        required: true
        unique: true
      - name: case_id
        type: identifier
        required: true
        references: Case
      - name: role
        type: PartyRole
        required: true
        allowed_values: [injured, witness, other_driver, other_vehicle]
      - name: name
        type: text
        required: false
      - name: contact
        type: text
        required: false
      - name: injury_status
        type: text
        required: false
      - name: vehicle_description
        type: text
        required: false
      - name: plate
        type: text
        required: false
      - name: statement_version
        type: text
        required: false
        constraint: "La versión de lo que pasó según esta parte. Se guardan las dos versiones sin juzgar."
    constraints:
      - "Un atributo nulo es un dato pendiente, nunca un valor supuesto (BR1.6)."
      - "Un caso sin partes y un caso donde la persona dijo que no hubo otras partes son distintos: el segundo lo registra el campo `other_parties` en estado `confirmed` con valor 'ninguno' (BR2.3)."

  - name: TranscriptTurn
    description: >
      Un turno de la conversación, guardado **ya redactado**. Es la evidencia de
      los campos y el primero de los cinco adjuntos del cierre.
    identifier: turn_id
    attributes:
      - name: turn_id
        type: identifier
        required: true
        unique: true
      - name: case_id
        type: identifier
        required: true
        references: Case
      - name: speaker
        type: Speaker
        required: true
        allowed_values: [insured, agent, staff]
      - name: channel
        type: Channel
        required: true
        allowed_values: [voice, chat]
        constraint: "El canal de este turno. Un caso empezado por voz y retomado por chat tiene turnos de los dos."
      - name: language
        type: Language
        required: true
        allowed_values: [es, en]
      - name: text_redacted
        type: Redacted
        required: true
        constraint: "Texto que ya pasó por la redacción de U3 (C-13). Guardar texto sin redactar no es un error de ejecución: no compila (BR6.1)."
      - name: started_at
        type: timestamp
        required: true
      - name: ended_at
        type: timestamp
        required: false
      - name: interrupted
        type: boolean
        required: true
        default: false
    constraints:
      - "Solo anexar: un turno guardado no se edita ni se borra fuera del reinicio nocturno."

  - name: CaseChange
    description: >
      Una entrada del historial: qué cambió, de qué a qué, quién, cuándo y desde
      qué canal. También guarda los intentos **rechazados**, que es donde se ve
      lo que alguien trató de hacer y el modelo no dejó.
    identifier: change_id
    attributes:
      - name: change_id
        type: identifier
        required: true
        unique: true
      - name: case_id
        type: identifier
        required: true
        references: Case
      - name: change_kind
        type: ChangeKind
        required: true
        allowed_values: [field_set, transition_applied, transition_rejected, close_rejected]
      - name: field_key
        type: FieldKey
        required: false
        constraint: "Presente en `field_set`; nulo en los otros tres."
      - name: previous_value
        type: text
        required: false
      - name: new_value
        type: text
        required: false
      - name: actor_type
        type: ActorType
        required: true
        allowed_values: [insured, agent, staff, system]
      - name: actor_id
        type: identifier
        required: false
        references: "StaffPrincipal (U2 `tenancy`)"
        constraint: "Presente cuando el tipo de actor es `staff`; así una corrección apunta a la persona que la hizo."
      - name: channel
        type: Channel
        required: false
        allowed_values: [voice, chat]
        constraint: "Nulo cuando el cambio no vino de una conversación, como una corrección de la bandeja."
      - name: detail
        type: text
        required: false
        constraint: "En un rechazo, qué se intentó: el estado de origen y el de destino, o el adjunto que faltaba."
      - name: changed_at
        type: timestamp
        required: true
    constraints:
      - "Solo anexar: una entrada no se edita ni se borra (BR5.3)."
      - "Un intento de transición o de cierre rechazado deja entrada aunque el caso no cambie (BR5.4, BR3.2)."

  # --- Objetos de valor: no se guardan como tabla propia ----------------------

  - name: CaseNumber
    description: "El número legible: tres letras de la aseguradora, un guion y seis dígitos."
    persisted: false
    attributes:
      - name: prefix
        type: text
        required: true
        constraint: "Tres letras mayúsculas. Sale de la configuración de la aseguradora, no de una tabla en el código (BR4.1)."
      - name: serial
        type: text
        required: true
        constraint: "Seis dígitos, con ceros a la izquierda."
    constraints:
      - "Los tres prefijos de la demostración son `STO` (Stonecroft Mutual), `SUN` (Sunmeadow Auto) y `KNO` (Knotwell Insurance Agency), elegidos para no confundirse entre sí al dictarse."

  - name: Completeness
    description: "La completitud del caso, por campo y total, calculada según el tipo de registro."
    persisted: false
    attributes:
      - name: per_field
        type: "mapa de FieldKey a booleano"
        required: true
      - name: complete
        type: integer
        required: true
        min: 0
      - name: total
        type: integer
        required: true
        min: 0
        constraint: "El número de campos que el esquema declara para el tipo del caso."
    constraints:
      - "Un campo cuenta como completo cuando alcanza el estado que su propio campo exige (BR2.6)."

  - name: ClosingEvidence
    description: "Lo que el caso comprobó al cerrarse: los cinco adjuntos de FR1.7, cada uno con su estado."
    persisted: false
    attributes:
      - name: transcript
        type: AttachmentState
        required: true
      - name: cited_clauses
        type: AttachmentState
        required: true
      - name: fired_rules
        type: AttachmentState
        required: true
      - name: trace_id
        type: AttachmentState
        required: true
      - name: control_results
        type: AttachmentState
        required: true

  - name: AttachmentState
    description: >
      El estado de un adjunto. Los tres valores no se colapsan nunca: `empty`
      dice que se miró y no había nada, `not_evaluated` dice que no se miró.
    persisted: false
    attributes:
      - name: kind
        type: text
        required: true
        allowed_values: [present, empty, not_evaluated]
      - name: reference
        type: text
        required: false
        constraint: "Presente cuando el estado es `present`: el identificador por el que se recupera el adjunto de su dueño."

  - name: FieldKey
    description: "La clave de un campo del caso, declarada en el esquema versionado por tipo de registro."
    persisted: false
    constraints:
      - "Siniestro: `identity_and_policy`, `incident_datetime`, `location`, `description`, `vehicle_and_driver`, `other_parties`, `injuries` (FR1.1)."
      - "Consulta de cobertura: `identity_and_policy`, `question_asked`."
      - "Solicitud de cotización: sin campos declarados hasta que los aporte U19 `quote`."

  - name: Actor
    description: "Quién hace un cambio: el asegurado, la agente, una persona de la bandeja o el sistema."
    persisted: false
    attributes:
      - name: actor_type
        type: text
        required: true
        allowed_values: [insured, agent, staff, system]
      - name: actor_id
        type: identifier
        required: false

  - name: Transition
    description: "Una fila de la tabla versionada de transiciones: de qué estado a qué estado y con qué condición."
    persisted: false
    attributes:
      - name: from_state
        type: CaseState
        required: true
      - name: to_state
        type: CaseState
        required: true
      - name: condition
        type: text
        required: false
        constraint: "Vacía en las transiciones sin condición; la única con condiciones es `derived` a `capturing` (BR3.3)."
    constraints:
      - "La tabla vive en un archivo versionado. El diagrama del ciclo de vida se genera desde ella y se compara con el versionado; si divergen, falla (enmienda de ADR-005)."
```

## El conjunto en palabras

**Cinco cosas se guardan.** El **caso** es la raíz y lleva lo que lo identifica
—su número legible, su aseguradora, su tipo, su estado— más lo que se decidió
sobre él. De él cuelgan sus **campos** (qué se dijo y cuán seguro está), sus
**partes** (los demás lesionados, testigos, conductores y vehículos), su
**transcripción** (los turnos, ya redactados) y su **historial** (todo lo que
cambió, y también lo que alguien intentó y el modelo rechazó).

**Siete cosas no se guardan** y existen para que un valor inválido no pueda
escribirse: el número de caso con su forma, la completitud con su cuenta, la
evidencia de cierre con sus cinco adjuntos, el estado de un adjunto con sus tres
valores que nunca se colapsan, la clave de campo, el actor y la fila de la tabla
de transiciones.

**Tres detalles cargan casi todo el peso del diseño:**

1. **Un campo lleva su evidencia, y son dos clases.** El turno en el que la
   persona lo dijo, o la entrada del historial si lo escribió un ajustador desde
   la bandeja. Exactamente una de las dos, y ninguna si el campo no se ha dicho.
   Sin esto, "la persona dijo que no hubo lesionados" y "nadie preguntó" serían
   indistinguibles, que es el error que el experimento 2 encontró.

2. **El estado de un adjunto tiene tres valores, no dos.** "Se miró y no había
   reglas que dispararan" no es lo mismo que "las reglas no se evaluaron". Es la
   misma distinción que el equipo ya obliga a mantener entre "no hay cláusula" y
   "no pude verificar", y colapsarla contaminaría una cifra publicada con fallos
   de infraestructura.

3. **El historial guarda los rechazos.** Una transición que el modelo no permite
   no deja el caso intacto y en silencio: deja escrito qué se intentó. Es lo que
   convierte "ningún caso llega a cerrado por un camino que nadie diseñó" en algo
   que se puede mirar en vez de suponer.

## Lo que esta etapa añadió al catálogo, y por qué

El catálogo de componentes describe cinco entidades con sus atributos. Tres
cosas se precisan aquí, y ninguna cambia una decisión anterior:

| Añadido | Dónde | Por qué |
| --- | --- | --- |
| `evidence_change_id` en el campo | `CaseField` | El catálogo daba al campo un único `evidence_turn_id`. Un campo corregido desde la bandeja no tiene turno, y la respuesta Q3 de esta etapa lo deja `confirmed`: sin este atributo, quedaría confirmado sin nada que lo respalde. |
| `closing_evidence` en el caso | `Case` | FR1.7 exige que un caso derivado **exponga** los cinco adjuntos y que falte cualquiera impida cerrar. Comprobándolos solo en el momento del cierre, después nadie podría decir qué se comprobó. |
| `change_kind` y `detail` en el historial | `CaseChange` | El catálogo modelaba el historial como cambios de campo. AC4.10.1 exige además dejar un evento cuando se rechaza una transición, y ese evento no tiene campo, valor anterior ni valor nuevo. |

Dos más viven fuera de esta unidad y se piden a sus dueños:

- **`case_number_prefix`** en la configuración de cada aseguradora (U2 `tenancy`,
  contrato C-25), con los valores `STO`, `SUN` y `KNO`. El prefijo es dato de la
  aseguradora; escribirlo en el código sería exactamente la ramificación por
  inquilino que el proyecto prohíbe.
- **Etiquetas del catálogo de textos** (U1 `workspace`) para los siete estados,
  las cuatro resoluciones, los tres tipos de registro y los tres motivos de
  derivación, en los dos idiomas. Ninguna pantalla imprime el valor del enum.
