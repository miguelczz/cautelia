# Entidades — U7 `synthetic-data`

U7 no crea tablas: su salida son archivos versionados en `app/data/` (C-26), que
U8 ingiere y U20 usa para aprovisionar. Sus dos entidades propias son las del
catálogo de componentes:
- `SourceText`: el texto revisado del que sale todo.
- `GenerationManifest`: la prueba de que una salida corresponde a unas entradas
  y a una semilla.

Las demás entidades describen la **forma de los archivos** que produce, no filas
de una base. Los modelos de U8 (`PolicyForm`, `Clause`, `IssuedPolicy`,
`ClauseRelation`) se llenan desde ellos.

## Entidades

```yaml
entities:

  - name: DraftText
    description: >
      Un borrador que devuelve el comando de redacción (Q1). Vive en
      tmp/synthetic-drafts/, que git ignora, y ningún comando del generador lo
      lee. Existe para que el texto del modelo no llegue al corpus sin revisión.
    stored_in: "tmp/synthetic-drafts/<aseguradora>/<idioma>/<parte>.yaml (no versionado)"
    attributes:
      - { name: tenant_id, type: identifier, required: true, allowed_values: [stonecroft, sunmeadow] }
      - { name: language, type: Locale, required: true, allowed_values: [es, en] }
      - { name: part, type: enum, required: true, allowed_values: [agreement, definitions, part_a, part_b, part_c, part_d, part_e, part_f, endorsements, jurisdiction] }
      - { name: model, type: identifier, required: true, constraint: "Identificador exacto del modelo que redactó, nunca un alias." }
      - { name: prompt_version, type: string, required: true }
      - { name: clauses, type: "list of DraftClause", required: true }

  - name: SourceText
    description: >
      Un texto fuente revisado y versionado: la unidad de la que el generador
      compone el corpus. Hay uno por cláusula, endoso, documento de jurisdicción
      o bloque de datos ficticios. Sin marca de revisión, el generador lo rechaza.
    stored_in: "app/data/sources/<aseguradora>/<idioma>/<parte>.yaml"
    attributes:
      - { name: source_id, type: identifier, required: true, unique: true, constraint: "Estable; forma <FORM_ID>-<clause_key>, por ejemplo STO-PAP-2026-A.EXCL.3." }
      - { name: kind, type: enum, required: true, allowed_values: [clause, endorsement, jurisdiction, distractor, persona_pool, vehicle_pool, case_turns], constraint: "case_turns son los turnos cortos de los casos sembrados, escritos a mano (CG-U7-2, FD-U7-7)." }
      - { name: tenant_id, type: identifier, required: true, allowed_values: [stonecroft, sunmeadow], constraint: "Knotwell no tiene textos propios: sus copias salen de los de sus emisoras (BR4.2)." }
      - { name: language, type: Locale, required: true, allowed_values: [es, en] }
      - { name: clause_key, type: string, required: false, constraint: "Numeración estructural de la referencia (A.EXCL.3, D.INS.COLLISION); obligatoria si kind es clause, endorsement o distractor." }
      - { name: part, type: string, required: false, constraint: "Encabezado estructural de la parte, en el idioma del texto." }
      - { name: version, type: string, required: true, constraint: "Forma AAAA.n." }
      - { name: text, type: string, required: true, constraint: "Texto propio. Nunca texto de cláusula de ISO o ACORD (P8)." }
      - { name: distractor_of, type: identifier, required: false, constraint: "Obligatorio si kind es distractor: la cláusula con la que se confunde." }
      - { name: distractor_reason, type: enum, required: false, allowed_values: [superseded_version, near_duplicate] }
      - { name: reviewed_at, type: date, required: true }
      - { name: reviewed_by, type: enum, required: true, allowed_values: [conductor, miguel], constraint: "conductor = la revisión del agente contra la estructura y P8; miguel = la muestra humana (BR5.4)." }
      - { name: drafted_with, type: identifier, required: true, constraint: "Modelo que redactó el borrador, o 'hand' si se escribió a mano." }
    relationships:
      - { target: SourceText, cardinality: "0..1", direction: "Un distractor apunta a la cláusula con la que se confunde" }

  - name: GenerationManifest
    description: >
      El manifiesto de una generación (C-26). Con la misma semilla y las mismas
      entradas, sus bytes son los mismos. U8 lo compara antes de ingerir.
    stored_in: "app/data/manifest.json"
    attributes:
      - { name: manifest_version, type: integer, required: true }
      - { name: seed, type: integer, required: true, constraint: "20260916, la de DS-8, salvo decisión escrita." }
      - { name: generator_version, type: string, required: true }
      - { name: inputs, type: "map path → sha256", required: true, constraint: "Todos los SourceText y archivos de configuración leídos." }
      - { name: outputs, type: "map path → sha256", required: true, constraint: "Todos los archivos escritos bajo app/data/ salvo el propio manifiesto." }
      - { name: declared_differences, type: "list of DeclaredDifference", required: true }
      - { name: seeded_cases, type: "list of SeededCaseRef", required: true }
      - { name: review_samples, type: "list of ReviewSample", required: true }
    constraints:
      - "No lleva fecha de generación ni nada que dependa del reloj: rompería los bytes idénticos (BR1.1)."

  - name: DeclaredDifference
    description: Una diferencia puesta a propósito entre aseguradoras, que usan DS-3 y la vista de comparación (AC5.4.3).
    attributes:
      - { name: difference_id, type: identifier, required: true, unique: true }
      - { name: description, type: string, required: true }
      - { name: present_in, type: "list of form_id", required: true }
      - { name: absent_in, type: "list of form_id", required: true }

  - name: FormRecord
    description: Un formulario base o un endoso, tal como sale en forms/<form_id>.json (C-26).
    stored_in: "app/data/tenants/<aseguradora>/forms/<form_id>.json"
    attributes:
      - { name: form_id, type: identifier, required: true, unique: true, constraint: "STO-PAP-2026 y SUN-PAP-2026 para los base; los endosos con sufijo END-n." }
      - { name: form_kind, type: enum, required: true, allowed_values: [base, endorsement, jurisdiction] }
      - { name: form_version, type: string, required: true }
      - { name: issuer_tenant, type: identifier, required: true, allowed_values: [stonecroft, sunmeadow] }
      - { name: issuer_label, type: string, required: true }
      - { name: language, type: Locale, required: true }
      - { name: jurisdiction_ref, type: identifier, required: false, constraint: "Obligatorio en los base: el documento de Corvane." }
      - { name: clause_ids, type: "list of clause_id", required: true }

  - name: ClauseRecord
    description: Una cláusula, con la forma exacta de C-26.
    stored_in: "app/data/tenants/<aseguradora>/clauses/<form_id>.json"
    attributes:
      - { name: clause_id, type: identifier, required: true, unique: true, constraint: "Único dentro del espacio de la aseguradora; las copias de Knotwell repiten el de la emisora." }
      - { name: form_id, type: identifier, required: true, references: FormRecord }
      - { name: form_version, type: string, required: true }
      - { name: clause_key, type: string, required: true }
      - { name: part, type: string, required: true }
      - { name: language, type: Locale, required: true }
      - { name: text, type: string, required: true }
      - { name: is_distractor, type: boolean, required: true, default: false }
      - { name: issuer_label, type: string, required: true }

  - name: ClauseRelationRecord
    description: Una relación entre cláusulas (ADR-010, C-26).
    stored_in: "app/data/tenants/<aseguradora>/clause_relations.json"
    attributes:
      - { name: from_clause, type: identifier, required: true, references: ClauseRecord }
      - { name: to_clause, type: identifier, required: true, references: ClauseRecord }
      - { name: relation, type: enum, required: true, allowed_values: [endorsement_modifies, defines, refers_to] }

  - name: IssuedPolicyRecord
    description: Una póliza emitida, con declaraciones y endosos vigentes (FR5.2).
    stored_in: "app/data/tenants/<aseguradora>/issued_policies/<policy_id>.json"
    attributes:
      - { name: policy_number, type: string, required: true, constraint: "POL- y seis dígitos, sin iniciales (decisión del 2026-09-20). Dos aseguradoras pueden repetir número a propósito (DS-8)." }
      - { name: tenant_id, type: identifier, required: true }
      - { name: issuer_tenant, type: identifier, required: true, constraint: "En Knotwell, la emisora; en una emisora, ella misma (AC5.5.3)." }
      - { name: form_id, type: identifier, required: true, references: FormRecord }
      - { name: form_version, type: string, required: true, constraint: "Una póliza sin versión no valida (FR5.2)." }
      - { name: endorsement_ids, type: "list of form_id", required: true }
      - { name: period_start, type: date, required: true }
      - { name: period_end, type: date, required: true }
      - { name: named_insured, type: PersonaRef, required: true }
      - { name: vehicles, type: "list of VehicleRef", required: true }
      - { name: limits_and_deductibles, type: "map", required: true }

  - name: PersonaRef
    description: Una persona ficticia del conjunto sembrado. Alimenta los canarios del segundo detector (ADR-013).
    attributes:
      - { name: persona_id, type: identifier, required: true, unique: true }
      - { name: full_name, type: string, required: true }
      - { name: phone, type: string, required: true, constraint: "Rango 555-01XX, que no se asigna a nadie (ADR-016)." }
      - { name: national_id, type: string, required: true, constraint: "Cédula inventada: el generador la compone desde la semilla y nunca desde un registro. Tiene la forma que reconoce U3, para que la redacción la encuentre (FR12.3)." }
      - { name: email, type: string, required: true, constraint: "Dominio reservado example.com o example.org." }

  - name: VehicleRef
    description: Un vehículo ficticio.
    attributes:
      - { name: plate, type: string, required: true, constraint: "Placa inventada con el formato de cada idioma." }
      - { name: make_model_year, type: string, required: true }
      - { name: vin, type: string, required: true, constraint: "VIN de prueba que falla el dígito de control, para que nunca sea real." }

  - name: SeededCaseRecord
    description: Un caso sembrado (US5.6), listo para cargarse por la API de U4 con origen generator.
    stored_in: "app/data/tenants/<aseguradora>/cases/<case_key>.json"
    attributes:
      - { name: case_key, type: identifier, required: true, unique: true, constraint: "Estable, por ejemplo SEED/stonecroft/es/derived-human-request." }
      - { name: tenant_id, type: identifier, required: true }
      - { name: language, type: Locale, required: true }
      - { name: state, type: enum, required: true, allowed_values: [open, capturing, verifying, deciding, derived, awaiting_insured, closed] }
      - { name: resolution, type: enum, required: false, allowed_values: [registered, approved, rejected, sent_to_insurer], constraint: "Obligatoria si state es closed." }
      - { name: fields, type: map, required: true }
      - { name: transcript, type: "list of turn", required: true }
      - { name: used_by, type: "list of AC id", required: true, constraint: "Los criterios que parten de este caso (AC5.6.2); puede estar vacía si el caso solo cubre un estado." }

  - name: PersonalValueList
    description: >
      La lista de valores personales ficticios que el generador sembró, por tipo
      e idioma (BR7.2, FD-U7-8). Es una salida más del generador, con su hash en
      el manifiesto; la leen la prueba de redacción y los canarios de U21.
    stored_in: "app/data/personal_values.json"
    attributes:
      - { name: values, type: "list of {kind, language, value}", required: true, constraint: "kind en name, phone, national_id, email, plate, vin, policy_number." }

  - name: FingerprintSet
    description: Las huellas de los formularios de terceros (Q3). Solo hashes; el texto nunca entra al repositorio.
    stored_in: "app/config/content/third-party-shingles.json"
    attributes:
      - { name: shingle_size, type: integer, required: true, default: 8 }
      - { name: normalization, type: string, required: true, constraint: "Minúsculas, sin puntuación, espacios colapsados, sin los encabezados de la referencia." }
      - { name: sources, type: "list of {form, edition, publisher, retrieved_at, file_sha256}", required: true }
      - { name: hashes, type: "list of sha256", required: true }

  - name: ReviewSample
    description: La muestra que revisa Miguel (AC5.4.5, AC5.5.6).
    stored_in: "app/data/sources/reviews/<aseguradora>-<fecha>.yaml (entrada del generador, que la copia al manifiesto)"
    attributes:
      - { name: tenant_id, type: identifier, required: true, allowed_values: [stonecroft, sunmeadow] }
      - { name: sample_seed, type: integer, required: true }
      - { name: clause_ids, type: "list of clause_id", required: true, constraint: "Diez, elegidas con la semilla." }
      - { name: reviewed_on, type: date, required: false }
      - { name: commit, type: string, required: false }
      - { name: verdict, type: enum, required: false, allowed_values: [own_text_structure_ok, changes_requested] }
```

## Resumen

- **Entrada revisada:** `SourceText` y, antes de él, el borrador `DraftText`, que
  nunca se versiona.
- **Salida versionada (C-26):**
  - `FormRecord`, `ClauseRecord`, `ClauseRelationRecord` e
    `IssuedPolicyRecord`, que ingiere U8;
  - `SeededCaseRecord`, que se carga por la API de U4;
  - las colisiones de DS-8, que ya existen y ahora regenera el generador;
  - `PersonaRef` y `VehicleRef`, los valores ficticios que alimentan los
    canarios.
- **Prueba de origen:** `GenerationManifest`, con los hashes de entradas y
  salidas, las diferencias declaradas, los casos sembrados y las muestras de
  revisión.
- **Protección contra texto ajeno:** `FingerprintSet`, que solo guarda hashes.
