# Entidades — U8 `policy-rag`

U7 ya dejó el corpus escrito en `app/data/`: formularios, cláusulas con
identificador y versión, relaciones entre cláusulas y pólizas emitidas, todo
versionado y con su `manifest.json` de hashes. **U8 no redacta ese contenido: lo
ingiere.** Sus cinco primeras entidades son la forma que toma ese corpus dentro
de PostgreSQL, y las dos últimas son lo que el verificador escribe por caso.

Dos separaciones sostienen la unidad entera:

- **El corpus es del inquilino, no de la conversación.** Cada cláusula, cada
  póliza y cada entrada del índice llevan `tenant_id` y viven bajo la misma
  política de fila que el resto del aplicativo (BR1.7 de U2). No hay espacio de
  nombres aparte para lo vectorial porque no hay servicio de búsqueda aparte:
  el índice léxico y el vectorial viven en la misma base, con la misma sesión y
  el mismo aislamiento (ADR-010).
- **El nodo no escribe; el verificador sí.** `CitationCheck` y `CoverageAnswer`
  se guardan desde `CitationVerifier` con clave idempotente, porque LangGraph
  vuelve a ejecutar el nodo completo al reanudar tras `interrupt()`
  (ADR-003, enmienda del 2026-09-17).

## Lo que ya existe y no se rehace

| Ya existe | De quién | Qué hace U8 con ello |
| --- | --- | --- |
| `app/data/tenants/<t>/{forms,clauses,clause_relations,issued_policies}` | U7 (C-26) | Los lee y los ingiere; nunca los edita |
| `manifest.json` con el hash de cada archivo | U7 | Lo compara antes de ingerir y se niega si no casa |
| `Embedder` (`providers/ports.py`) | U5 (C-16) | Embeddings de ingesta y de consulta |
| Sesión con la aseguradora ya fijada | U2 (C-10) | Toda consulta pasa por ahí |
| `Case`, `TranscriptTurn` | U4 (C-12) | La respuesta de cobertura cuelga de un caso y de un turno |

## Entidades

```yaml
entities:

  - name: PolicyForm
    description: Un formulario del corpus de una aseguradora — el formulario base, un endoso o el documento de jurisdicción — con su versión y su idioma.
    stored_in: "Tabla policy_forms, con RLS por tenant_id"
    attributes:
      - { name: form_id, type: identifier, required: true, constraint: "Único junto con tenant_id y version. Por ejemplo STO-PAP-2026." }
      - { name: tenant_id, type: identifier, required: true, constraint: "La aseguradora cuyo corpus contiene este formulario. En Knotwell son las copias de las dos emisoras." }
      - { name: version, type: string, required: true, constraint: "Por ejemplo 2026.1. Un mismo form_id con dos versiones coexiste: la anterior es distractor (AC5.2.3)." }
      - { name: language, type: enum, required: true, allowed_values: [es, en], constraint: "El idioma en que está redactado el formulario, que es el de la emisora y no el de la conversación (FD-U8-1)." }
      - { name: issuer_label, type: string, required: true, constraint: "El nombre de la emisora tal como se muestra en la cita. En Knotwell no es Knotwell." }
      - { name: kind, type: enum, required: true, allowed_values: [base_form, endorsement, jurisdiction], constraint: "Se deduce del corpus: el base, los cinco endosos y el documento de jurisdicción del Estado de Corvane." }
      - { name: superseded_by, type: string, required: false, constraint: "La versión que lo reemplaza, si la hay. Vacío en la vigente." }

  - name: Clause
    description: Una cláusula del corpus. Es la unidad de cita y la unidad de fragmento: un fragmento del índice pertenece a exactamente una cláusula (AC5.2.1).
    stored_in: "Tabla clauses, con RLS por tenant_id"
    attributes:
      - { name: clause_id, type: identifier, required: true, unique: true, constraint: "Estable y único dentro de la aseguradora. Por ejemplo STO-PAP-2026-A.4.b. Es lo que se cita." }
      - { name: tenant_id, type: identifier, required: true }
      - { name: form_id, type: identifier, required: true, references: PolicyForm }
      - { name: form_version, type: string, required: true, references: PolicyForm }
      - { name: clause_key, type: string, required: true, constraint: "La clave estructural dentro del formulario, por ejemplo A.4.b." }
      - { name: part, type: string, required: true, constraint: "El nombre de la parte, por ejemplo Part A — Liability Coverage. Es lo que la voz nombra (AC2.7.1)." }
      - { name: language, type: enum, required: true, allowed_values: [es, en] }
      - { name: text, type: text, required: true, constraint: "Texto propio con estructura inspirada; nunca texto de cláusula de ISO ni de ACORD (P8, W6)." }
      - { name: is_distractor, type: boolean, required: true, constraint: "Declarado en el corpus. Se indexa igual: un distractor que no se indexa no distrae (AC2.1.2)." }
      - { name: issuer_label, type: string, required: true }

  - name: IssuedPolicy
    description: Una póliza emitida a una persona, con su formulario, su versión, sus endosos vigentes y su vigencia. Es el filtro que hace que una respuesta salga de la póliza de quien pregunta y de ninguna otra.
    stored_in: "Tabla issued_policies, con RLS por tenant_id"
    attributes:
      - { name: policy_id, type: identifier, required: true, unique: true, constraint: "El policy_number del corpus. Un mismo número puede existir en dos aseguradoras: es una colisión sembrada a propósito (POL-480915), y la RLS es lo que impide que se crucen." }
      - { name: tenant_id, type: identifier, required: true, constraint: "La aseguradora por la que entra la persona. En Knotwell es knotwell, aunque la emisora sea otra." }
      - { name: issuer_tenant, type: identifier, required: true, constraint: "Quién emitió la póliza. En Stonecroft y Sunmeadow coincide con tenant_id; en Knotwell no, y es lo que decide de qué corpus sale la cita (US2.8)." }
      - { name: form_id, type: identifier, required: true, references: PolicyForm }
      - { name: form_version, type: string, required: true, constraint: "La versión que esta póliza referencia. Las anteriores existen indexadas y no son vigentes para ella (AC5.2.3)." }
      - { name: endorsement_ids, type: "list of identifier", required: true, constraint: "Los endosos vigentes de esta póliza. Es la lista que el verificador recorre para BR3.5." }
      - { name: named_insured, type: string, required: true, constraint: "Dato de persona sembrada; se redacta antes de persistir en cualquier traza o reporte (M6)." }
      - { name: vehicles, type: "list of object", required: true }
      - { name: limits_and_deductibles, type: object, required: true, constraint: "Se guarda porque la póliza lo trae; U8 nunca lo dice en una respuesta (AC2.7.2)." }
      - { name: period_start, type: date, required: true }
      - { name: period_end, type: date, required: true, constraint: "Una póliza fuera de vigencia no recupera nada (BR2.2)." }

  - name: ClauseIndexEntry
    description: Lo que hace buscable una cláusula: su vector léxico y su embedding, atados al modelo con que se calcularon.
    stored_in: "Tabla clause_index, con RLS por tenant_id"
    attributes:
      - { name: clause_id, type: identifier, required: true, references: Clause, constraint: "Único junto con embedding_model." }
      - { name: tenant_id, type: identifier, required: true }
      - { name: embedding_model, type: string, required: true, constraint: "Identificador exacto del modelo, de la configuración versionada. Parte de la clave: cambiar de modelo no pisa el índice viejo, lo deja obsoleto y obliga a reconstruir (ADR-010)." }
      - { name: lexical_vector, type: tsvector, required: true, constraint: "La configuración de idioma del tsvector sale del idioma de la cláusula, no del de la conversación." }
      - { name: embedding, type: vector, required: true, constraint: "Dimensión de la configuración versionada. Búsqueda exacta, sin índice HNSW, mientras el corpus sea pequeño (ADR-010)." }
      - { name: content_hash, type: string, required: true, constraint: "Hash del texto indexado. Es lo que permite reingestar sin duplicar y reindexar solo lo que cambió (AC5.2.4)." }
      - { name: indexed_at, type: timestamp, required: true }

  - name: ClauseRelation
    description: Una arista entre dos cláusulas del mismo corpus. Es lo que convierte una cláusula recuperada en el conjunto que de verdad hay que leer.
    stored_in: "Tabla clause_relations, con RLS por tenant_id"
    attributes:
      - { name: relation_id, type: identifier, required: true, unique: true }
      - { name: tenant_id, type: identifier, required: true }
      - { name: from_clause, type: identifier, required: true, references: Clause }
      - { name: to_clause, type: identifier, required: true, references: Clause }
      - { name: relation, type: enum, required: true, allowed_values: [endorsement_modifies, defines, refers_to], constraint: "Los tres tipos que escribe el corpus de U7 (ADR-010). endorsement_modifies es el que sostiene BR3.5; hay cinco por emisora." }
      - { name: form_version, type: string, required: true, constraint: "La relación vale para una versión del formulario; una relación de la versión anterior no alcanza a una póliza de la nueva." }

  - name: CitationCheck
    description: La comprobación de una cita contra el corpus, con su resultado y sus motivos. Es el rastro que permite decir por qué una respuesta no salió.
    stored_in: "Tabla citation_checks, con RLS por tenant_id y FK compuesta (tenant_id, case_id)"
    attributes:
      - { name: check_id, type: identifier, required: true, unique: true }
      - { name: tenant_id, type: identifier, required: true }
      - { name: case_id, type: identifier, required: true, references: "Case (U4)" }
      - { name: clause_id, type: identifier, required: true, constraint: "No lleva clave foránea a clauses: una cita inventada apunta a una cláusula que no existe, y ese es justo el caso que hay que poder registrar (AC2.2.1)." }
      - { name: clause_version, type: string, required: false, constraint: "Vacío cuando la cláusula no existe." }
      - { name: claim_redacted, type: text, required: true, constraint: "Lo que la respuesta afirmaba, ya redactado (M6)." }
      - { name: outcome, type: enum, required: true, allowed_values: [verified, rejected, no_clause_found, unverifiable] }
      - { name: reasons, type: "list of string", required: true, constraint: "Claves de motivo de un conjunto cerrado, no prosa: son lo que el reporte por caso agrupa." }
      - { name: amended_by, type: "list of identifier", required: false, constraint: "Los endosos vigentes que modifican la cláusula citada. Se registra siempre que existan, haya pasado o no (enmienda del 2026-09-17, ADR-011)." }
      - { name: checked_at, type: timestamp, required: true }

  - name: CoverageAnswer
    description: La respuesta de cobertura de un turno, con su resultado y las comprobaciones de sus citas. La escribe el verificador, no el nodo.
    stored_in: "Tabla coverage_answers, con RLS por tenant_id y FK compuesta (tenant_id, case_id)"
    attributes:
      - { name: answer_id, type: identifier, required: true, unique: true }
      - { name: tenant_id, type: identifier, required: true }
      - { name: case_id, type: identifier, required: true, references: "Case (U4)" }
      - { name: turn_id, type: identifier, required: true, references: "TranscriptTurn (U4)" }
      - { name: idempotency_key, type: string, required: true, unique: true, constraint: "Derivada del caso y del turno: reanudar el grafo reejecuta el nodo y no puede duplicar la respuesta (ADR-003)." }
      - { name: question_redacted, type: text, required: true }
      - { name: outcome, type: enum, required: true, allowed_values: [verified, rejected, no_clause_found, unverifiable], constraint: "no_clause_found y unverifiable son dos valores distintos y nunca se colapsan (FR5.5, P2)." }
      - { name: citation_check_ids, type: "list of identifier", required: true, references: CitationCheck }
      - { name: answer_language, type: enum, required: true, allowed_values: [es, en], constraint: "El idioma de la conversación." }
      - { name: clause_language, type: enum, required: false, allowed_values: [es, en], constraint: "El idioma de las cláusulas citadas. Puede diferir de answer_language, y cuando difiere la respuesta lo dice (FD-U8-1)." }
      - { name: created_at, type: timestamp, required: true }

  - name: RetrievalProbe
    description: No es una entidad persistida: es la forma del resultado de una recuperación, que el nodo recibe y la traza registra. Se declara aquí porque su composición es lo que se mide en AC2.1.3.
    stored_in: "En memoria; se refleja como evento de traza con el nodo, la póliza y los identificadores recuperados"
    attributes:
      - { name: clause_ids, type: "list of identifier", required: true, constraint: "En el orden en que quedaron tras la fusión y el cierre por relaciones." }
      - { name: sources, type: "map clause_id → {lexical_rank, vector_rank, closure_of}", required: true, constraint: "De dónde vino cada una: es lo que permite saber si un fallo fue de recuperación léxica, vectorial o de cierre." }
      - { name: filtered_by, type: object, required: true, constraint: "tenant_id, issuer_tenant, form_id, form_version y endosos vigentes: los filtros aplicados ANTES de ordenar (BR2.1)." }
```

## Desviaciones frente al catálogo de componentes

El catálogo de `domain-design` bosquejó estas entidades antes de que U7
escribiera el corpus. Lo construido sigue al corpus real, que es el que existe:

| En el catálogo | En el corpus de U7 | Por qué manda el corpus |
| --- | --- | --- |
| `IssuedPolicy.issuer_tenant_id` | `issuer_tenant` | Es el nombre del campo en los archivos que U8 ingiere |
| `IssuedPolicy.endorsement_keys` | `endorsement_ids` | Idem |
| `IssuedPolicy.effective_from` / `effective_to` | `period_start` / `period_end` | Idem |
| `IssuedPolicy.national_id`, `phone`, `drivers`, `origin` | No existen | El corpus guarda `named_insured`, `vehicles` y `limits_and_deductibles`; los datos de contacto los captura U11 en el caso, no la póliza |
| `PolicyForm.effective_from` | No existe | La vigencia la fija la póliza, no el formulario |
| `ClauseIndexEntry` sin hash | `content_hash` añadido | Sin él no hay forma de cumplir AC5.2.4 ("reingestar sin duplicar") salvo reindexando todo |
| `CitationCheck` sin `amended_by` | Añadido | ADR-011 exige que la comprobación quede registrada con el endoso que modifica la cláusula |
| `ClauseRelation.src_clause_id` / `dst_clause_id` / `rel_type` | `from_clause` / `to_clause` / `relation` | Son los nombres del archivo que U8 ingiere |
| `rel_type: endorsement_amends` | `relation: endorsement_modifies` | Idem: el valor que el corpus escribe de verdad |
