"""La revision de cumplimiento deja de comprobar datos personales en la transcripcion.

Desde el 2026-10-30 la conversacion del caso se guarda tal como se escribio, por
decision de Miguel («nadie va a poner ningun supuesto dato real, quita eso»). El
control `pii_ok` comprobaba lo contrario --que la transcripcion guardada no tuviera
datos personales--, asi que todo caso en que la persona dijera su nombre habria
fallado la revision y no se habria podido cerrar (BR6.1 de U10). Se retira el
control; los datos personales se siguen tapando en logs, trazas, exportacion y
reporte de evaluaciones, que es donde los miden las compuertas duras.

Que hace:

1. Quita el hallazgo `pii_found` de las revisiones guardadas. La tabla tiene el
   aislamiento por fila forzado, asi que se fija cada aseguradora antes de tocar
   sus filas; la lista sale de las filas y de la configuracion, porque un rol que
   no es superusuario no ve ninguna fila sin aseguradora fijada.
2. Quita la restriccion que ataba `pii_ok` a ese hallazgo y la columna.

La restriccion `compliance_review_hallazgos_validos` sigue admitiendo `pii_found`:
ya no se escribe, y quitarlo de la lista no protege nada.

`downgrade` vuelve a crear la columna en verdadero para todas las filas, que es lo
que dice una revision sin el hallazgo.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from untangle.tenancy import config

revision: str = "u10_compliance_0002_no_pii"
down_revision: str | None = "u20_demo_0003_short_numbers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RESTRICCION = "compliance_review_datos_personales_concuerda"


def _aseguradoras(conexion: sa.Connection) -> list[str]:
    filas = conexion.execute(sa.text("SELECT DISTINCT tenant_id FROM compliance_review"))
    return sorted({fila[0] for fila in filas} | {t.tenant_id for t in config.load().available})


def upgrade() -> None:
    conexion = op.get_bind()
    for tenant_id in _aseguradoras(conexion):
        conexion.execute(sa.text("SELECT set_config('app.tenant_id', :t, true)"), {"t": tenant_id})
        conexion.execute(
            sa.text(
                """
                UPDATE compliance_review
                SET findings = array_remove(findings, 'pii_found'::varchar), pii_ok = true
                WHERE tenant_id = :t AND 'pii_found' = ANY (findings)
                """
            ),
            {"t": tenant_id},
        )
    conexion.execute(sa.text("SELECT set_config('app.tenant_id', '', true)"))
    op.drop_constraint(_RESTRICCION, "compliance_review", type_="check")
    op.drop_column("compliance_review", "pii_ok")


def downgrade() -> None:
    """El orden inverso. Se prueba en cada corrida, no se supone."""
    op.add_column(
        "compliance_review",
        sa.Column("pii_ok", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column("compliance_review", "pii_ok", server_default=None)
    op.create_check_constraint(
        _RESTRICCION, "compliance_review", "pii_ok = NOT ('pii_found' = ANY (findings))"
    )
