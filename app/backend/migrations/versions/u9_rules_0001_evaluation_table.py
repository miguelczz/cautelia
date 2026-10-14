"""u9_rules_0001_evaluation_table: la tabla del resultado de evaluar un caso.

Revision: u9_rules_0001_evaluation_table
Revision anterior: u15_speech_0001_provider_check

Una sola tabla, `rule_evaluation`: el resultado de aplicar el conjunto de reglas
de una aseguradora a un caso (`entities.md`). Cuelga del caso, es dato de
visitante y entra en el contrato de borrado (BR4.1).

**Llave compuesta desde el primer commit** (CG-U9-4). U10 tuvo que cerrar en
una segunda revision (`u10_compliance_0002_tenant_fks`) el hueco por el que una
fila de la aseguradora B podia apuntar al caso de la aseguradora A: las
comprobaciones de llave foranea de PostgreSQL no pasan por las politicas de
fila. Esta tabla nace ya con `(tenant_id, case_id)` apuntando al par unico
`case_record_aseguradora_y_caso` que esa revision dejo en `case_record`, sin
abrir el hueco para tener que cerrarlo despues (UG-3, la leccion de esa
migracion).

**Dos columnas JSON, con su forma impuesta.** `fired_rules` nunca esta vacia
--al menos la regla por defecto siempre dispara (BR1.3, BR2.4)--, y la base lo
comprueba con `jsonb_array_length`, no solo el tipo `RuleEvaluation`.
`inputs_snapshot` puede ser un mapa vacio: si solo disparo la regla por
defecto, ninguna condicion leyo ningun campo.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "u9_rules_0001_evaluation_table"
down_revision: str | None = "u15_speech_0001_provider_check"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: La marca de dato de visitante (C-11), igual que en U4 y U10.
MARCA = "visitor-data"

#: Los topes, escritos una vez (igual que `u10_compliance_0001_tables`).
ASEGURADORA = sa.String(31)
IDENTIFICADOR = sa.String(64)
CLAVE_DE_CATALOGO = sa.String(96)

#: La forma de una clave del catalogo (BR2.5): segmentos en minusculas separados
#: por puntos.
FORMA_DE_CLAVE = r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$"

_POLITICA = """
    CREATE POLICY tenant_isolation ON {tabla}
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
"""


def _aislar(tabla: str, descripcion: str) -> None:
    op.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {tabla} FORCE ROW LEVEL SECURITY")
    op.execute(_POLITICA.format(tabla=tabla))
    op.execute(f"COMMENT ON TABLE {tabla} IS '{MARCA}: {descripcion} (C-11)'")


def upgrade() -> None:
    op.create_table(
        "rule_evaluation",
        sa.Column("evaluation_id", IDENTIFICADOR, primary_key=True),
        sa.Column("tenant_id", ASEGURADORA, nullable=False),
        sa.Column("case_id", IDENTIFICADOR, nullable=False),
        sa.Column("ruleset_version", sa.String(32), nullable=False),
        sa.Column("category", sa.String(16), nullable=False),
        # Cada elemento: {"id": str, "version": int, "touches_money": bool}
        # (`FiredRule`, C-19). Nunca vacia (BR2.4).
        sa.Column("fired_rules", postgresql.JSONB(), nullable=False),
        # Solo los campos que leyeron las reglas disparadas, ya redactados por
        # U3 si llevan datos personales (`entities.md`). Puede ser un mapa
        # vacio: la regla por defecto no lee ningun campo.
        sa.Column("inputs_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("explanation_key", CLAVE_DE_CATALOGO, nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["case_record.tenant_id", "case_record.case_id"],
            name="rule_evaluation_del_caso",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("evaluation_id <> ''", name="rule_evaluation_identificador"),
        sa.CheckConstraint(
            "category IN ('direct_close', 'standard_review', 'referral')",
            name="rule_evaluation_categoria_valida",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(fired_rules) = 'array' AND jsonb_array_length(fired_rules) > 0",
            name="rule_evaluation_reglas_disparadas_no_vacias",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(inputs_snapshot) = 'object'",
            name="rule_evaluation_insumos_son_mapa",
        ),
        sa.CheckConstraint(
            f"explanation_key ~ '{FORMA_DE_CLAVE}'",
            name="rule_evaluation_clave_con_forma",
        ),
    )
    op.create_index("rule_evaluation_por_aseguradora", "rule_evaluation", ["tenant_id", "case_id"])
    _aislar("rule_evaluation", "el resultado de evaluar las reglas del caso de un visitante")


def downgrade() -> None:
    """Deshace la revision entera. Se prueba en cada corrida, no se supone.

    `mise run migrate:check` sube, baja y vuelve a subir contra una base virgen.
    """
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON rule_evaluation")
    op.drop_index("rule_evaluation_por_aseguradora", table_name="rule_evaluation")
    op.drop_table("rule_evaluation")
