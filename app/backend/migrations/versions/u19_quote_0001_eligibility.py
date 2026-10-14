"""u19_quote_0001_eligibility: donde queda el resultado de evaluar una solicitud.

Revision: u19_quote_0001_eligibility
Revision anterior: u4_case_0002_derived_turn

**Por que una tabla y no una columna de `rule_evaluation`.** Las dos guardan el
resultado de aplicar un conjunto de reglas a un caso, y ahi se acaba el parecido:
el triage devuelve una **categoria** de tres valores y la elegibilidad devuelve
una **salida** y una **banda de riesgo**, que son dos ejes. Meterlas en la misma
columna obligaria a relajar la restriccion que hoy la acota a las tres categorias
de triage, y entonces esa columna significaria dos cosas segun la fila: el defecto
que el proyecto ya escribio como "la distincion que llega al dato y muere en la
pantalla", al reves.

**Por que existe, y que cerraba su ausencia.** `compose_eligibility_reply` esta
escrita y probada desde U19 y **nadie la llama** en el camino real: su unico
consumidor es el corredor de evaluaciones. La razon no era pereza, era que la
salida no tenia donde quedarse: el estado del grafo solo admite campos que declare
un `NodeSpec` (BR1.5), y la elegibilidad no es un nodo --la transicion esta cerrada
sobre los cuatro nombres del PRD, y anadir un quinto romperia la convencion 3 del
equipo, que exige una sola grafia para esos cuatro--. Asi que se guarda, y el turno
la lee, igual que ya lee la respuesta de cobertura.

Cuelga del caso, es dato de visitante y entra en el contrato de borrado (BR4.1).
Llave compuesta desde el primer commit (UG-3, la leccion de
`u10_compliance_0002_tenant_fks`): una fila de la aseguradora B no puede apuntar al
caso de la A, porque las llaves foraneas de PostgreSQL no pasan por las politicas
de fila.

**Una fila por caso, no un historial.** La elegibilidad de una solicitud se evalua
cuando sus cuatro bloques quedan capturados (BR2.5); si el visitante corrige un
campo y se vuelve a evaluar, lo que vale es lo ultimo, y un historial de intentos
invitaria a que la bandeja mostrara uno viejo. Lo que si queda en la traza es cada
corrida, con su instante.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "u19_quote_0001_eligibility"
down_revision: str | None = "u4_case_0002_derived_turn"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: La marca de dato de visitante (C-11), igual que en U4, U9 y U10. Es lo que hace
#: que el contrato de borrado del reinicio nocturno la encuentre: la comprobacion de
#: completitud recorre el catalogo buscando esta marca, asi que una tabla sin ella
#: no se barre **y nadie lo nota**.
MARCA = "visitor-data"

ASEGURADORA = sa.String(31)
IDENTIFICADOR = sa.String(64)
CLAVE_DE_CATALOGO = sa.String(96)

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
        "quote_eligibility",
        # La llave es el caso: una fila por solicitud, la ultima evaluacion.
        sa.Column("tenant_id", ASEGURADORA, primary_key=True),
        sa.Column("case_id", IDENTIFICADOR, primary_key=True),
        sa.Column("ruleset_version", sa.String(32), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("band", sa.String(24), nullable=False),
        # Los identificadores de las reglas que decidieron la salida (`deciding_rules`
        # de `EligibilityOutcome`). Nunca vacia: con nada disparado entra la regla por
        # defecto, asi que siempre hay al menos una.
        sa.Column("deciding_rules", postgresql.JSONB(), nullable=False),
        sa.Column("explanation_key", CLAVE_DE_CATALOGO, nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["case_record.tenant_id", "case_record.case_id"],
            name="quote_eligibility_del_caso",
            ondelete="CASCADE",
        ),
        # Los valores son los de `EligibilityOutcomeKind` y `RiskBand`. Se repiten
        # aqui a proposito: una restriccion en la base es lo unico que sigue siendo
        # cierto cuando alguien escribe por fuera del aplicativo.
        sa.CheckConstraint(
            "outcome IN ('eligible', 'not_eligible', 'referred')",
            name="quote_eligibility_salida_valida",
        ),
        sa.CheckConstraint(
            "band IN ('standard_risk', 'elevated_risk', 'pending_review', 'outside_appetite')",
            name="quote_eligibility_banda_valida",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(deciding_rules) = 'array' AND jsonb_array_length(deciding_rules) > 0",
            name="quote_eligibility_reglas_no_vacias",
        ),
        sa.CheckConstraint(
            f"explanation_key ~ '{FORMA_DE_CLAVE}'",
            name="quote_eligibility_clave_con_forma",
        ),
    )
    _aislar("quote_eligibility", "la elegibilidad de la solicitud de cotizacion de un visitante")


def downgrade() -> None:
    """Deshace la revision entera. Se prueba en cada corrida, no se supone.

    `mise run migrate:check` sube, baja y vuelve a subir contra una base virgen.
    """
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON quote_eligibility")
    op.drop_table("quote_eligibility")
