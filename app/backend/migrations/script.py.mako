"""${message}

Revision: ${up_revision}
Revision anterior: ${down_revision | comma,n}
Fecha: ${create_date}

Regla dura (C-30, BR1.10): si esta revision crea una tabla del aplicativo, trae
aqui mismo su columna `tenant_id`, `ENABLE ROW LEVEL SECURITY`, `FORCE ROW LEVEL
SECURITY` y su politica de aseguradora. No existe una revision posterior "que
agrega el aislamiento". `mise run rls:check` lo comprueba contra el catalogo
vivo y `mise run migrate:check` corre subir, bajar y volver a subir.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = ${repr(up_revision)}
down_revision: str | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
