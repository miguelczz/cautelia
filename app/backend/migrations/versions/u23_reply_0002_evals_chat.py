"""u23_reply_0002_evals_chat: el libro mayor acepta el uso `evals_chat`.

Revision: u23_reply_0002_evals_chat
Revision anterior: u23_reply_0001_anthropic

Las evaluaciones de la comprension del chat (`mise run evals:entender`,
2026-10-08) llaman a Claude con su propia clave. Sin uso propio su gasto se
atribuia a `evals`, que es Gemini gratuito, y quedaba marcado como no facturable:
no contaba contra el techo aunque se pagara. La restriccion del libro mayor
enumera los usos, y una prueba de integracion falla si la base y la lista no
coinciden.

Solo amplia lo aceptado. `downgrade` se detiene si alguna fila ya usa el valor
nuevo, porque una fila de gasto no se borra para que una migracion baje (BR3.1).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "u23_reply_0002_evals_chat"
down_revision: str | None = "u23_reply_0001_anthropic"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLA = "spend_entry"
USO = "spend_entry_uso_valido"

USOS_ANTES = "use IN ('voice', 'chat', 'evals', 'operations', 'corpus', 'chat_reply')"
USOS_AHORA = "use IN ('voice', 'chat', 'evals', 'operations', 'corpus', 'chat_reply', 'evals_chat')"

_FILAS_NUEVAS = sa.text("SELECT count(*) FROM spend_entry WHERE use = 'evals_chat'")


class NewValuesInUseError(RuntimeError):
    """Hay filas de gasto con el valor que la bajada quitaria."""


def upgrade() -> None:
    op.drop_constraint(USO, TABLA, type_="check")
    op.create_check_constraint(USO, TABLA, USOS_AHORA)


def downgrade() -> None:
    filas = op.get_bind().execute(_FILAS_NUEVAS).scalar_one()
    if filas:
        msg = (
            f"{filas} fila(s) de '{TABLA}' usan 'evals_chat'. La revision no borra el "
            "libro mayor: decida que hacer con ellas y vuelva a correrla"
        )
        raise NewValuesInUseError(msg)
    op.drop_constraint(USO, TABLA, type_="check")
    op.create_check_constraint(USO, TABLA, USOS_ANTES)
