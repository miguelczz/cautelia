"""u10_compliance_0001_tables: las tres tablas de los controles, con su aislamiento.

Revision: u10_compliance_0001_tables
Revision anterior: u6_web_0001_activation_tables

El plan la nombraba `u10_compliance_0001_compliance_tables`, y ese nombre no
cabe: `alembic_version.version_num` admite treinta y dos caracteres y aquel tiene
treinta y siete. Se acorta el identificador y el archivo con el, porque en todas
las revisiones del proyecto el nombre del archivo es el identificador.

Tres tablas, las tres colgadas de un caso y las tres dato de visitante (BR8.1):

- `disclosure_record`: que la apertura con la divulgacion salio, por que canal y
  en que idioma. Una por caso y canal (BR4.2).
- `guard_intervention`: cada frase que la guardia no dejo salir, con su
  categoria y su patron, **nunca con la frase** (BR1.6, SEC-U10.3).
- `compliance_review`: la revision completa de los cuatro controles. Una por
  caso y turno revisado, para que la reejecucion del nodo al reanudar no la
  duplique (BR6.3).

Tres decisiones cargan el peso de esta revision:

**1. Las tres cuelgan del caso con borrado en cascada** (CG-U10-3). "Se borran
con su caso" (NFR19.4) no depende asi de que ningun purgador recuerde el orden:
lo impone la forma de la base, igual que en las cuatro hijas de U4 y en el
resumen de traza de U5. Por la misma razon las tres se declaran en el purgador
del caso y no en uno propio: su `DELETE` es literalmente lo que las borra.

**2. Ninguna columna es texto libre** (BR8.2, NFR11.8). Toda columna de texto
lleva su tope escrito, y donde el valor tiene forma, una restriccion que la
impone: las claves del catalogo y los identificadores de patron no admiten
espacios, los enums son listas cerradas y los hallazgos de la revision son un
arreglo de codigos cerrados. Ningun nombre de columna contiene una entrada de la
lista versionada de nombres de dato personal.

**3. Las invariantes que el codigo comprueba, la base tambien.** Una
intervencion lleva categoria si y solo si la guardia pudo evaluar, y clave de
catalogo salvo si la frase se descarto; un control de la revision en falso lleva
exactamente su codigo entre los hallazgos. Es la red de abajo: el dia que una
ruta nueva escriba sin pasar por los tipos de `compliance/controls/models.py`,
la para la tabla.

Los conjuntos cerrados se escriben **literales** en sus restricciones, como en
la revision de U4: una migracion es un registro de lo que se le hizo a la base,
y si leyera el enum vivo, anadir un valor manana cambiaria el significado de lo
que esta revision dice haber hecho hoy.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "u10_compliance_0001_tables"
down_revision: str | None = "u6_web_0001_activation_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: La marca de dato de visitante. La prueba de completitud del registro de
#: purgadores le pregunta al catalogo que tablas la llevan y exige purgador para
#: cada una (C-11).
MARCA = "visitor-data"

#: Los topes, escritos una vez. El identificador de aseguradora son hasta
#: treinta y un caracteres (`TENANT_ID_PATTERN` de U2).
ASEGURADORA = sa.String(31)
IDENTIFICADOR = sa.String(64)
CLAVE_DE_CATALOGO = sa.String(96)
IDENTIFICADOR_DE_PATRON = sa.String(64)

#: Las formas, escritas una vez para las tres tablas.
FORMA_DE_CLAVE = r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$"
FORMA_DE_PATRON = r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+){2,4}$"

#: Los cuatro hallazgos posibles de la revision completa (BR5.1).
HALLAZGOS = "'disclosure_missing', 'human_route_missed', 'pii_found', 'attachment_missing'"

_POLITICA = """
    CREATE POLICY tenant_isolation ON {tabla}
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
"""


def _aislar(tabla: str, descripcion: str) -> None:
    """Habilita, fuerza y politiza el aislamiento, y escribe la marca.

    El texto de la politica esta a la vista en `_POLITICA`, tres lineas arriba,
    como en la revision de U4: quien lea esta revision ve el aislamiento completo
    sin salir del archivo. Lo unico que no se repite tres veces es la llamada.
    """
    op.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {tabla} FORCE ROW LEVEL SECURITY")
    op.execute(_POLITICA.format(tabla=tabla))
    op.execute(f"COMMENT ON TABLE {tabla} IS '{MARCA}: {descripcion} (C-11)'")


def upgrade() -> None:
    # --- La divulgacion -------------------------------------------------------
    op.create_table(
        "disclosure_record",
        sa.Column("disclosure_id", IDENTIFICADOR, primary_key=True),
        sa.Column("tenant_id", ASEGURADORA, nullable=False),
        sa.Column("case_id", IDENTIFICADOR, nullable=False),
        sa.Column("channel", sa.String(8), nullable=False),
        sa.Column("language", sa.String(2), nullable=False),
        # La clave de la apertura que salio, nunca su texto.
        sa.Column("catalog_key", CLAVE_DE_CATALOGO, nullable=False),
        sa.Column("disclosed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["case_record.case_id"],
            name="disclosure_record_del_caso",
            ondelete="CASCADE",
        ),
        # Registrarla dos veces no crea dos filas (BR4.2): el nodo se reejecuta
        # al reanudar, y un segundo registro del mismo caso y canal choca aqui.
        sa.UniqueConstraint("case_id", "channel", name="disclosure_record_una_por_canal"),
        sa.CheckConstraint("disclosure_id <> ''", name="disclosure_record_identificador"),
        sa.CheckConstraint("channel IN ('chat', 'voice')", name="disclosure_record_canal_valido"),
        sa.CheckConstraint("language IN ('es', 'en')", name="disclosure_record_idioma_valido"),
        sa.CheckConstraint(
            f"catalog_key ~ '{FORMA_DE_CLAVE}'", name="disclosure_record_clave_con_forma"
        ),
    )
    op.create_index(
        "disclosure_record_por_aseguradora", "disclosure_record", ["tenant_id", "case_id"]
    )
    _aislar("disclosure_record", "la divulgacion registrada en el caso de un visitante")

    # --- Las intervenciones de la guardia -------------------------------------
    op.create_table(
        "guard_intervention",
        sa.Column("intervention_id", IDENTIFICADOR, primary_key=True),
        sa.Column("tenant_id", ASEGURADORA, nullable=False),
        sa.Column("case_id", IDENTIFICADOR, nullable=False),
        # El turno cuya salida corrigio. La frase original no se guarda: lo que
        # si salio ya esta en ese turno de la transcripcion (BR1.6).
        sa.Column("turn_id", IDENTIFICADOR, nullable=False),
        sa.Column("category", sa.String(32), nullable=True),
        sa.Column("pattern_id", IDENTIFICADOR_DE_PATRON, nullable=True),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("catalog_key", CLAVE_DE_CATALOGO, nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["case_record.case_id"],
            name="guard_intervention_del_caso",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["turn_id"],
            ["case_transcript_turn.turn_id"],
            name="guard_intervention_de_su_turno",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("intervention_id <> ''", name="guard_intervention_identificador"),
        sa.CheckConstraint(
            "category IS NULL OR category IN ('coverage_promise', 'amount', 'fault', "
            "'legal_advice', 'humanity_claim', 'transfer_or_deadline', 'config_disclosure')",
            name="guard_intervention_categoria_valida",
        ),
        sa.CheckConstraint(
            "action IN ('substituted', 'dropped', 'not_evaluable')",
            name="guard_intervention_accion_valida",
        ),
        # Sin evaluacion no hay categoria que nombrar, y con evaluacion siempre
        # la hay (BR1.5). El patron va con su categoria (BR1.6).
        sa.CheckConstraint(
            "(action = 'not_evaluable') = (category IS NULL)",
            name="guard_intervention_categoria_si_se_evaluo",
        ),
        sa.CheckConstraint(
            "(category IS NULL) = (pattern_id IS NULL)",
            name="guard_intervention_patron_con_su_categoria",
        ),
        # Sale una clave del catalogo salvo cuando la frase se descarto (BR1.4).
        sa.CheckConstraint(
            "(action = 'dropped') = (catalog_key IS NULL)",
            name="guard_intervention_clave_salvo_descartada",
        ),
        sa.CheckConstraint(
            f"pattern_id IS NULL OR pattern_id ~ '{FORMA_DE_PATRON}'",
            name="guard_intervention_patron_con_forma",
        ),
        sa.CheckConstraint(
            f"catalog_key IS NULL OR catalog_key ~ '{FORMA_DE_CLAVE}'",
            name="guard_intervention_clave_con_forma",
        ),
    )
    op.create_index(
        "guard_intervention_por_aseguradora", "guard_intervention", ["tenant_id", "case_id"]
    )
    _aislar(
        "guard_intervention", "las frases que la guardia no dejo salir en el caso de un visitante"
    )

    # --- La revision completa -------------------------------------------------
    op.create_table(
        "compliance_review",
        sa.Column("review_id", IDENTIFICADOR, primary_key=True),
        sa.Column("tenant_id", ASEGURADORA, nullable=False),
        sa.Column("case_id", IDENTIFICADOR, nullable=False),
        sa.Column("disclosure_ok", sa.Boolean(), nullable=False),
        sa.Column("human_route_ok", sa.Boolean(), nullable=False),
        sa.Column("pii_ok", sa.Boolean(), nullable=False),
        sa.Column("explainability_ok", sa.Boolean(), nullable=False),
        # Codigos cerrados, nunca texto: un arreglo de hasta cuatro valores de
        # una lista fija (BR8.2).
        sa.Column(
            "findings",
            postgresql.ARRAY(sa.String(32)),
            nullable=False,
            server_default=sa.text("'{}'::varchar[]"),
        ),
        # El ultimo turno revisado: el de la derivacion si la hubo (BR5.2).
        sa.Column("reviewed_through_turn", IDENTIFICADOR, nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["case_record.case_id"],
            name="compliance_review_del_caso",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_through_turn"],
            ["case_transcript_turn.turn_id"],
            name="compliance_review_hasta_su_turno",
            ondelete="CASCADE",
        ),
        # Repetir la revision del mismo punto no crea otra fila (BR6.3).
        sa.UniqueConstraint(
            "case_id", "reviewed_through_turn", name="compliance_review_una_por_turno"
        ),
        sa.CheckConstraint("review_id <> ''", name="compliance_review_identificador"),
        sa.CheckConstraint(
            f"findings <@ ARRAY[{HALLAZGOS}]::varchar[]",
            name="compliance_review_hallazgos_validos",
        ),
        # Cada control en falso lleva exactamente su codigo, y en verdadero no
        # lo lleva: la marca y la lista no pueden decir cosas distintas (BR5.1).
        sa.CheckConstraint(
            "disclosure_ok = NOT ('disclosure_missing' = ANY (findings))",
            name="compliance_review_divulgacion_concuerda",
        ),
        sa.CheckConstraint(
            "human_route_ok = NOT ('human_route_missed' = ANY (findings))",
            name="compliance_review_ruta_concuerda",
        ),
        sa.CheckConstraint(
            "pii_ok = NOT ('pii_found' = ANY (findings))",
            name="compliance_review_datos_personales_concuerda",
        ),
        sa.CheckConstraint(
            "explainability_ok = NOT ('attachment_missing' = ANY (findings))",
            name="compliance_review_adjuntos_concuerda",
        ),
    )
    op.create_index(
        "compliance_review_por_aseguradora", "compliance_review", ["tenant_id", "case_id"]
    )
    _aislar("compliance_review", "la revision de los cuatro controles del caso de un visitante")


def downgrade() -> None:
    """Deshace la revision entera. Se prueba en cada corrida, no se supone.

    `mise run migrate:check` sube, baja y vuelve a subir contra una base virgen.
    """
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON compliance_review")
    op.drop_index("compliance_review_por_aseguradora", table_name="compliance_review")
    op.drop_table("compliance_review")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON guard_intervention")
    op.drop_index("guard_intervention_por_aseguradora", table_name="guard_intervention")
    op.drop_table("guard_intervention")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON disclosure_record")
    op.drop_index("disclosure_record_por_aseguradora", table_name="disclosure_record")
    op.drop_table("disclosure_record")
