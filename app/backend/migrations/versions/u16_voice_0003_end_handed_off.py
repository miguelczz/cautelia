"""u16_voice_0003_end_handed_off: el septimo motivo de final de una llamada.

Revision: u16_voice_0003_end_handed_off
Revision anterior: u23_reply_0002_evals_chat

Cuando la persona pedia un ajustador por telefono, la llamada seguia abierta
hasta morir por silencio y su fila decia `silence`. Desde el 2026-10-11 la agente
se despide con el numero de caso y la llamada termina con su propio motivo: **el
caso paso a un ajustador**.

Cambio aditivo, igual que `u16_voice_0002_end_completed`: ninguna fila existente
deja de valer.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "u16_voice_0003_end_handed_off"
down_revision: str | None = "u23_reply_0002_evals_chat"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ANTERIOR = "('hangup', 'silence', 'max_duration', 'dropped', 'error', 'completed')"
_NUEVO = "('hangup', 'silence', 'max_duration', 'dropped', 'error', 'completed', 'handed_off')"
_RESTRICCION = "call_session_motivo_valido"


def upgrade() -> None:
    op.execute(f"ALTER TABLE call_session DROP CONSTRAINT {_RESTRICCION}")
    op.execute(
        f"ALTER TABLE call_session ADD CONSTRAINT {_RESTRICCION} "
        f"CHECK (end_reason IS NULL OR end_reason IN {_NUEVO})"
    )


def downgrade() -> None:
    """Primero se retiran las filas que usan el motivo nuevo, como en la 0002."""
    op.execute("DELETE FROM call_session WHERE end_reason = 'handed_off'")
    op.execute(f"ALTER TABLE call_session DROP CONSTRAINT {_RESTRICCION}")
    op.execute(
        f"ALTER TABLE call_session ADD CONSTRAINT {_RESTRICCION} "
        f"CHECK (end_reason IS NULL OR end_reason IN {_ANTERIOR})"
    )
