"""u24_adjuster_0004_adjuster_run: la corrida del ajustador de IA sobre un caso.

Revision: u24_adjuster_0004_adjuster_run
Revision anterior: u24_adjuster_0003_cases_quota

## Por que existe

El ajustador de IA es un trabajo de fondo que decide un caso en varios pasos, y la pantalla del
visitante consulta cada tres segundos para mostrarlos llegando. Cada paso guarda su texto y sus
fuentes apenas termina; la decision y su explicacion se guardan **antes** de registrar el cierre
del caso (A5), porque la huella del recibo incluye el comentario y un texto generado de nuevo en
un reintento daria `RecycledKeyError`. Esta tabla es donde viven.

## Una fila por caso

La llave es `(tenant_id, case_id)`: un caso tiene una corrida, que se reabre en el reintento y no
se duplica. Dos arranques del mismo caso chocan en la llave y solo uno es dueno del trabajo.

## Cuatro estados y lo que cada uno exige

`running`, `decided`, `capped` (el tope diario de casos; espera al dia siguiente) y `failed`
(agoto sus intentos). Las restricciones atan los campos al estado --la decision y el resumen
existen exactamente cuando esta decidida, y el tipo de error solo cuando fallo-- para que una
fila no pueda decir «decidida» sin decision ni «fallida» con una explicacion.

## Llave compuesta hacia el caso y borrado con el

La llave hacia el caso es `(tenant_id, case_id)` y cae en cascada, igual que `case_triage_note`,
`rule_evaluation` y `quote_eligibility` (UG-3, la leccion de `u10_compliance_0002_tenant_fks`):
las llaves foraneas de PostgreSQL no pasan por las politicas de fila, asi que una llave de una
sola columna dejaria a una aseguradora colgar una corrida del caso de otra. Lleva la marca de dato
de visitante porque su texto sale de lo que una persona conto, y el reinicio nocturno tiene que
declararla.

## Reversible

`downgrade` borra la tabla: una corrida no es historial. La decision que tomo vive en el caso
(`case_change`), no aqui.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "u24_adjuster_0004_adjuster_run"
down_revision: str | None = "u24_adjuster_0003_cases_quota"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: La marca de dato de visitante (C-11), igual que en U4, U9, U14 y U19.
MARCA = "visitor-data"

ASEGURADORA = sa.String(31)
IDENTIFICADOR = sa.String(64)

TABLA = "adjuster_run"

_POLITICA = """
    CREATE POLICY tenant_isolation ON {tabla}
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
"""


def upgrade() -> None:
    op.create_table(
        TABLA,
        sa.Column("tenant_id", ASEGURADORA, primary_key=True),
        sa.Column("case_id", IDENTIFICADOR, primary_key=True),
        sa.Column("status", sa.Text(), nullable=False),
        # El intento en curso o el ultimo hecho, desde 1.
        sa.Column("attempt", sa.Integer(), nullable=False),
        # La lista de pasos con su texto y sus fuentes, en el orden en que terminaron.
        sa.Column("steps", postgresql.JSONB(), nullable=False, server_default="[]"),
        # Una de las tres acciones de la bandeja. Nula hasta que se decide.
        sa.Column("decision", sa.Text(), nullable=True),
        # La explicacion que ve el visitante. Nula hasta que se decide.
        sa.Column("summary", sa.Text(), nullable=True),
        # El identificador exacto del modelo, nunca un alias movil (BR1.4).
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("searches_used", sa.Integer(), nullable=False, server_default="0"),
        # El tipo de error de la frontera del proveedor, o el motivo propio del ajustador.
        sa.Column("error_kind", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["case_record.tenant_id", "case_record.case_id"],
            name="adjuster_run_del_caso",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "status IN ('running', 'decided', 'capped', 'failed')",
            name="adjuster_run_estado_valido",
        ),
        sa.CheckConstraint("attempt >= 1", name="adjuster_run_intento_positivo"),
        sa.CheckConstraint(
            "decision IS NULL OR decision IN ('approve', 'reject', 'mark_sent')",
            name="adjuster_run_decision_valida",
        ),
        sa.CheckConstraint(
            "(status = 'decided') = (decision IS NOT NULL)",
            name="adjuster_run_decision_solo_si_decidida",
        ),
        sa.CheckConstraint(
            "(status = 'decided') = (summary IS NOT NULL AND summary <> '')",
            name="adjuster_run_resumen_solo_si_decidida",
        ),
        sa.CheckConstraint(
            "error_kind IS NULL OR (status = 'failed' AND error_kind <> '')",
            name="adjuster_run_error_solo_si_fallida",
        ),
        sa.CheckConstraint("searches_used >= 0", name="adjuster_run_busquedas_no_negativas"),
        sa.CheckConstraint("jsonb_typeof(steps) = 'array'", name="adjuster_run_pasos_es_lista"),
        sa.CheckConstraint("model <> ''", name="adjuster_run_dice_el_modelo"),
    )
    op.execute(f"ALTER TABLE {TABLA} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {TABLA} FORCE ROW LEVEL SECURITY")
    op.execute(_POLITICA.format(tabla=TABLA))
    op.execute(
        f"COMMENT ON TABLE {TABLA} IS "
        f"'{MARCA}: la corrida del ajustador de IA sobre el caso de un visitante, con sus pasos y "
        "sus fuentes (C-11)'"
    )


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {TABLA}")
    op.drop_table(TABLA)
