"""u24_adjuster_0002_ai_actor: el historial del caso acepta al actor `adjuster_ai`.

Revision: u24_adjuster_0002_ai_actor
Revision anterior: u24_adjuster_0001_use_searches

Cuando el ajustador de IA decide un caso, el historial tiene que decir que lo decidio el, no
una persona con credencial (`staff`) ni la persona asegurada (`insured`): «quien decidio» es
una afirmacion que la pantalla le hace a quien evalua el producto. `case_change_actor_valido`
enumera los actores y es la unica restriccion que lo hace.

`case_change` es de solo anexar (SEC-U4.11), asi que `downgrade` se detiene si ya hay una
entrada del actor nuevo en vez de borrarla para poder bajar.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "u24_adjuster_0002_ai_actor"
down_revision: str | None = "u24_adjuster_0001_use_searches"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLA = "case_change"
ACTOR = "case_change_actor_valido"

ACTORES_ANTES = "actor_type IN ('insured', 'agent', 'staff', 'system')"
ACTORES_AHORA = "actor_type IN ('insured', 'agent', 'staff', 'system', 'adjuster_ai')"

_FILAS_NUEVAS = sa.text("SELECT count(*) FROM case_change WHERE actor_type = 'adjuster_ai'")


class AdjusterActorInHistoryError(RuntimeError):
    """El historial ya tiene entradas del actor que la bajada quitaria."""


def upgrade() -> None:
    op.drop_constraint(ACTOR, TABLA, type_="check")
    op.create_check_constraint(ACTOR, TABLA, ACTORES_AHORA)


def downgrade() -> None:
    quedan = op.get_bind().execute(_FILAS_NUEVAS).scalar_one()
    if quedan:
        msg = (
            f"quedan {quedan} entrada(s) del actor 'adjuster_ai' en el historial. Bajar esta "
            "revision las dejaria fuera de la restriccion, y el historial es de solo anexar "
            "(SEC-U4.11): no se borran para poder bajar"
        )
        raise AdjusterActorInHistoryError(msg)
    op.drop_constraint(ACTOR, TABLA, type_="check")
    op.create_check_constraint(ACTOR, TABLA, ACTORES_ANTES)
