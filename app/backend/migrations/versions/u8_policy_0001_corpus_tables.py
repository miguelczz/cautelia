"""u8_policy_0001_corpus_tables: el corpus de polizas dentro de la base.

Revision: u8_policy_0001_corpus_tables
Revision anterior: u9_rules_0001_evaluation_table

Siete tablas, en el orden en que una pregunta las atraviesa (`entities.md`):

1. `policy_forms`, `clauses`, `clause_relations` -- el corpus de U7, ingerido.
2. `issued_policies` -- la poliza emitida que filtra la recuperacion.
3. `clause_index` -- lo que hace buscable una clausula (BR1.3, BR1.6, ADR-010).
4. `citation_checks`, `coverage_answers` -- lo que escribe el verificador por
   caso (BR4.1 a BR4.5); son dato de visitante y cuelgan de `case_record` con
   la llave compuesta `(tenant_id, case_id)` desde este primer commit, igual
   que hizo U9 con `rule_evaluation` (CG-U9-4, UG-3): el hueco por el que una
   fila de la aseguradora B apuntaria al caso de la aseguradora A no se abre
   para tener que cerrarlo despues.

**Las cinco primeras no son dato de visitante.** El corpus, sus relaciones, la
poliza emitida y el indice son dato de la aseguradora -- sintetico, de U7 --
y no de quien pregunta; solo `citation_checks` y `coverage_answers` llevan la
marca `visitor-data` y entran al contrato de borrado de U2 (BR4.5). Anadirlas
al purgador de `case_record` es trabajo del paso 6 de esta unidad (tanda 2),
donde nace `CitationVerifier`: aqui solo se crea el esquema.

**Nombres de columna: el corpus real manda sobre el boceto.** `entities.md`
documenta ya varias desviaciones frente al catalogo de `domain-design`
(`issuer_tenant`, `endorsement_ids`, `period_start`/`period_end`,
`from_clause`/`to_clause`/`relation`). Esta migracion encuentra tres mas al
leer los archivos reales de U7, con la misma regla -- gana el nombre del
archivo que se ingiere:

- `PolicyForm.kind` en el boceto es `form_kind` en el archivo, con valores
  `base`/`endorsement`/`jurisdiction` y no `base_form`/`endorsement`/
  `jurisdiction`.
- `PolicyForm.superseded_by` no existe en ningun formulario generado: qua
  version es vigente lo decide la poliza (BR1.4), nunca el formulario, y por
  eso esta columna no se crea.
- `ClauseRelation.form_version` tampoco existe en el archivo de relaciones
  (`{from_clause, relation, to_clause}` y nada mas): la version aplicable de
  una relacion es la de la clausula que senala, y se lee con un `JOIN` contra
  `clauses` en vez de duplicarse aqui sin fuente.

**El vector, sin paquete nuevo.** `TECH-U8.1` no trae ninguna dependencia de
ejecucion: la columna `embedding` se declara con SQL crudo
(`ALTER TABLE ... ADD COLUMN ... vector(...)`) en vez de con un tipo de
SQLAlchemy, porque el proyecto no instala el paquete `pgvector` de Python
(decision de alcance de `tech-stack-decisions.md`, "Assumptions & Open
Questions"). La extension misma la crea `scripts/db-init/02-pgvector-extension.sh`,
el mismo guion que montan el entorno local y la base efimera de las pruebas.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "u8_policy_0001_corpus_tables"
down_revision: str | None = "u9_rules_0001_evaluation_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: La marca de dato de visitante (C-11), igual que en U4, U9 y U10. Solo las
#: dos ultimas tablas la llevan.
MARCA = "visitor-data"

#: Los topes, escritos una vez, igual que en las migraciones anteriores.
ASEGURADORA = sa.String(31)
IDENTIFICADOR = sa.String(64)
CLAUSE_ID = sa.String(96)
FORM_ID = sa.String(48)
FORM_VERSION = sa.String(16)
POLICY_NUMBER = sa.String(32)
#: El identificador exacto del modelo de embeddings (BR1.6, TECH-U8.5): parte
#: de la clave del indice, nunca un alias movil.
EMBEDDING_MODEL = sa.String(64)

_POLITICA = """
    CREATE POLICY tenant_isolation ON {tabla}
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
"""


def _aislar(tabla: str, descripcion: str, *, visitor_data: bool = False) -> None:
    op.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {tabla} FORCE ROW LEVEL SECURITY")
    op.execute(_POLITICA.format(tabla=tabla))
    marca = f"{MARCA}: {descripcion} (C-11)" if visitor_data else descripcion
    op.execute(f"COMMENT ON TABLE {tabla} IS '{marca}'")


def upgrade() -> None:
    # --- El corpus de U7, ingerido (BR1.1 a BR1.4, BR1.7) ----------------------
    op.create_table(
        "policy_forms",
        sa.Column("tenant_id", ASEGURADORA, nullable=False),
        sa.Column("form_id", FORM_ID, nullable=False),
        sa.Column("form_version", FORM_VERSION, nullable=False),
        sa.Column("form_kind", sa.String(16), nullable=False),
        sa.Column("language", sa.String(2), nullable=False),
        sa.Column("issuer_label", sa.Text(), nullable=False),
        # Quien emitio el formulario. En una agencia coincide con la carpeta cuya
        # copia se esta ingiriendo, y nunca con el identificador de la agencia
        # misma: es lo que decide de que corpus sale una cita para su cliente
        # (BR2.5).
        sa.Column("issuer_tenant", ASEGURADORA, nullable=False),
        sa.Column("jurisdiction_ref", FORM_ID, nullable=True),
        sa.PrimaryKeyConstraint("tenant_id", "form_id", "form_version", name="policy_forms_pk"),
        sa.CheckConstraint(
            "form_kind IN ('base', 'endorsement', 'jurisdiction')",
            name="policy_forms_form_kind_valido",
        ),
        sa.CheckConstraint("language IN ('es', 'en')", name="policy_forms_idioma_valido"),
    )
    _aislar("policy_forms", "el formulario de un corpus de aseguradora, dato de la aseguradora")

    op.create_table(
        "clauses",
        sa.Column("tenant_id", ASEGURADORA, nullable=False),
        sa.Column("clause_id", CLAUSE_ID, nullable=False),
        sa.Column("clause_key", sa.String(64), nullable=False),
        sa.Column("form_id", FORM_ID, nullable=False),
        sa.Column("form_version", FORM_VERSION, nullable=False),
        sa.Column("part", sa.Text(), nullable=False),
        sa.Column("language", sa.String(2), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("is_distractor", sa.Boolean(), nullable=False),
        sa.Column("issuer_label", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("tenant_id", "clause_id", name="clauses_pk"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "form_id", "form_version"],
            ["policy_forms.tenant_id", "policy_forms.form_id", "policy_forms.form_version"],
            name="clauses_del_formulario",
        ),
        sa.CheckConstraint("clause_key <> ''", name="clauses_clave_no_vacia"),
        sa.CheckConstraint("part <> ''", name="clauses_parte_no_vacia"),
        sa.CheckConstraint("language IN ('es', 'en')", name="clauses_idioma_valido"),
    )
    op.create_index("clauses_por_formulario", "clauses", ["tenant_id", "form_id", "form_version"])
    _aislar("clauses", "una clausula del corpus de una aseguradora, dato de la aseguradora")

    op.create_table(
        "clause_relations",
        sa.Column("tenant_id", ASEGURADORA, nullable=False),
        # Generado a la ingesta, deterministico: no random (convencion del
        # equipo), y estable entre corridas para que reingestar sin cambios
        # produzca la misma fila (BR1.5).
        sa.Column("relation_id", sa.String(160), nullable=False),
        sa.Column("from_clause", CLAUSE_ID, nullable=False),
        sa.Column("to_clause", CLAUSE_ID, nullable=False),
        sa.Column("relation", sa.String(24), nullable=False),
        sa.PrimaryKeyConstraint("tenant_id", "relation_id", name="clause_relations_pk"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "from_clause"],
            ["clauses.tenant_id", "clauses.clause_id"],
            name="clause_relations_origen",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "to_clause"],
            ["clauses.tenant_id", "clauses.clause_id"],
            name="clause_relations_destino",
        ),
        sa.CheckConstraint(
            "relation IN ('endorsement_modifies', 'defines', 'refers_to')",
            name="clause_relations_tipo_valido",
        ),
    )
    op.create_index("clause_relations_por_origen", "clause_relations", ["tenant_id", "from_clause"])
    _aislar(
        "clause_relations",
        "una relacion entre dos clausulas del corpus, dato de la aseguradora",
    )

    # --- La poliza emitida (BR2.1 a BR2.6) -------------------------------------
    op.create_table(
        "issued_policies",
        sa.Column("tenant_id", ASEGURADORA, nullable=False),
        sa.Column("policy_number", POLICY_NUMBER, nullable=False),
        # Quien emitio la poliza. En una agencia decide de que corpus sale la
        # cita (BR2.5, US2.8); en una aseguradora que emite directo coincide
        # con tenant_id.
        sa.Column("issuer_tenant", ASEGURADORA, nullable=False),
        sa.Column("form_id", FORM_ID, nullable=False),
        sa.Column("form_version", FORM_VERSION, nullable=False),
        sa.Column("endorsement_ids", postgresql.JSONB(), nullable=False),
        # Dato de persona sembrada por U7 (P8): no es dato de visitante, y no
        # entra al contrato de borrado de U2 por la misma razon que el resto
        # del corpus.
        sa.Column("named_insured", postgresql.JSONB(), nullable=False),
        sa.Column("vehicles", postgresql.JSONB(), nullable=False),
        sa.Column("limits_and_deductibles", postgresql.JSONB(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("tenant_id", "policy_number", name="issued_policies_pk"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "form_id", "form_version"],
            ["policy_forms.tenant_id", "policy_forms.form_id", "policy_forms.form_version"],
            name="issued_policies_del_formulario",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(endorsement_ids) = 'array'",
            name="issued_policies_endosos_son_lista",
        ),
        sa.CheckConstraint("period_end > period_start", name="issued_policies_vigencia_valida"),
    )
    _aislar("issued_policies", "una poliza emitida, dato de la aseguradora")

    # --- Lo que hace buscable una clausula (BR1.3, BR1.5, BR1.6, ADR-010) ------
    op.create_table(
        "clause_index",
        sa.Column("tenant_id", ASEGURADORA, nullable=False),
        sa.Column("clause_id", CLAUSE_ID, nullable=False),
        sa.Column("embedding_model", EMBEDDING_MODEL, nullable=False),
        # `lexical_vector` y `embedding` se anaden aparte, en SQL crudo: la
        # segunda porque el proyecto no instala el paquete `pgvector` de
        # Python (ver docstring del modulo). La primera **no** es una columna
        # generada: PostgreSQL no admite una subconsulta contra otra tabla
        # dentro de `GENERATED ALWAYS AS`, y el idioma vive en `clauses`, no
        # aqui. La calcula la ingesta al escribir, con `to_tsvector(config,
        # texto)` en la misma sentencia (TECH-U8.4), leyendo el idioma de la
        # clausula que ya cargo.
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "tenant_id", "clause_id", "embedding_model", name="clause_index_pk"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "clause_id"],
            ["clauses.tenant_id", "clauses.clause_id"],
            name="clause_index_de_la_clausula",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("char_length(content_hash) = 64", name="clause_index_hash_sha256"),
    )
    op.execute("ALTER TABLE clause_index ADD COLUMN lexical_vector tsvector NOT NULL")
    # `vector` **sin dimension fija**, y la dimension comprobada en codigo contra
    # `providers.yaml` al escribir. Fijarla en la columna contradice las dos
    # decisiones que la rodean: el identificador del modelo es parte de la clave
    # (BR1.6) justamente para que dos modelos convivan en el indice, y con una
    # columna de 768 un modelo de otra dimension no cabe sin migracion; y ADR-006
    # pone la dimension en configuracion versionada, que pasa a ser un segundo
    # sitio donde vive el mismo dato si la columna tambien la declara. Aqui no se
    # pierde nada: FD-U8-6 no crea indice aproximado, que es lo unico que pgvector
    # exige dimensionar.
    op.execute("ALTER TABLE clause_index ADD COLUMN embedding vector NOT NULL")
    op.execute("CREATE INDEX clause_index_lexico ON clause_index USING gin (lexical_vector)")
    _aislar(
        "clause_index",
        "el vector lexico y el embedding de una clausula, dato de la aseguradora",
    )

    # --- Lo que escribe el verificador por caso (BR4.1 a BR4.5) ----------------
    # Dato de visitante desde su primer commit: llave compuesta hacia el caso
    # (tenant_id, case_id) para que una fila de la aseguradora B no pueda
    # apuntar al caso de la aseguradora A (CG-U9-4, UG-3). El purgador que las
    # cubre y su prueba llegan en el paso 6 de esta unidad (tanda 2), con
    # `CitationVerifier`: aqui solo nace el esquema.
    op.create_table(
        "citation_checks",
        sa.Column("check_id", IDENTIFICADOR, primary_key=True),
        sa.Column("tenant_id", ASEGURADORA, nullable=False),
        sa.Column("case_id", IDENTIFICADOR, nullable=False),
        # Sin clave foranea hacia `clauses`, a proposito: una cita inventada
        # apunta a una clausula que no existe, y ese es justo el caso que hay
        # que poder registrar (AC2.2.1, BR3.1).
        sa.Column("clause_id", CLAUSE_ID, nullable=False),
        sa.Column("clause_version", FORM_VERSION, nullable=True),
        sa.Column("claim_redacted", sa.Text(), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("reasons", postgresql.JSONB(), nullable=False),
        sa.Column("amended_by", postgresql.JSONB(), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["case_record.tenant_id", "case_record.case_id"],
            name="citation_checks_del_caso",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("check_id <> ''", name="citation_checks_identificador"),
        sa.CheckConstraint(
            "outcome IN ('verified', 'rejected', 'no_clause_found', 'unverifiable')",
            name="citation_checks_resultado_valido",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(reasons) = 'array'", name="citation_checks_motivos_son_lista"
        ),
    )
    op.create_index("citation_checks_por_caso", "citation_checks", ["tenant_id", "case_id"])
    _aislar(
        "citation_checks",
        "la comprobacion de una cita contra el corpus, del caso de un visitante",
        visitor_data=True,
    )

    # `coverage_answers` apunta a un turno, y la regla del proyecto exige que
    # toda llave foranea entre dos tablas aisladas lleve `tenant_id` en las dos
    # puntas: las llaves foraneas **no pasan por las politicas de fila**, asi
    # que sin la aseguradora una fila de una podria apuntar al turno de otra
    # (`rls_assertion`, U2). `case_transcript_turn` nacio con clave primaria
    # solo sobre `turn_id`, asi que la punta de destino necesita esta unicidad
    # para poder ser referenciada; es aditiva y no cambia nada de U4.
    op.create_unique_constraint(
        "case_transcript_turn_aseguradora_turno",
        "case_transcript_turn",
        ["tenant_id", "turn_id"],
    )

    op.create_table(
        "coverage_answers",
        sa.Column("answer_id", IDENTIFICADOR, primary_key=True),
        sa.Column("tenant_id", ASEGURADORA, nullable=False),
        sa.Column("case_id", IDENTIFICADOR, nullable=False),
        sa.Column("turn_id", IDENTIFICADOR, nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("question_redacted", sa.Text(), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("citation_check_ids", postgresql.JSONB(), nullable=False),
        sa.Column("answer_language", sa.String(2), nullable=False),
        sa.Column("clause_language", sa.String(2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["case_record.tenant_id", "case_record.case_id"],
            name="coverage_answers_del_caso",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "turn_id"],
            ["case_transcript_turn.tenant_id", "case_transcript_turn.turn_id"],
            name="coverage_answers_del_turno",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("idempotency_key", name="coverage_answers_clave_idempotente"),
        sa.CheckConstraint("answer_id <> ''", name="coverage_answers_identificador"),
        sa.CheckConstraint(
            "outcome IN ('verified', 'rejected', 'no_clause_found', 'unverifiable')",
            name="coverage_answers_resultado_valido",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(citation_check_ids) = 'array'",
            name="coverage_answers_citas_son_lista",
        ),
        sa.CheckConstraint(
            "answer_language IN ('es', 'en')", name="coverage_answers_idioma_valido"
        ),
    )
    op.create_index("coverage_answers_por_caso", "coverage_answers", ["tenant_id", "case_id"])
    _aislar(
        "coverage_answers",
        "la respuesta de cobertura de un turno, del caso de un visitante",
        visitor_data=True,
    )


def downgrade() -> None:
    """Deshace la revision entera. Se prueba en cada corrida, no se supone.

    `mise run migrate:check` sube, baja y vuelve a subir contra una base virgen.
    El orden es el inverso exacto de `upgrade()`, por las llaves foraneas.
    """
    for tabla, indices in (
        ("coverage_answers", ("coverage_answers_por_caso",)),
        ("citation_checks", ("citation_checks_por_caso",)),
        ("clause_index", ("clause_index_lexico",)),
        ("issued_policies", ()),
        ("clause_relations", ("clause_relations_por_origen",)),
        ("clauses", ("clauses_por_formulario",)),
        ("policy_forms", ()),
    ):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {tabla}")
        for indice in indices:
            op.drop_index(indice, table_name=tabla)
        op.drop_table(tabla)

    # Lo ultimo, porque `coverage_answers` la referenciaba: la unicidad aditiva
    # que esta revision le puso a la tabla de turnos de U4.
    op.drop_constraint(
        "case_transcript_turn_aseguradora_turno", "case_transcript_turn", type_="unique"
    )
