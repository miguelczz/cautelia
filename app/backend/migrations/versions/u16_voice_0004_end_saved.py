"""u16_voice_0004_end_saved: el octavo motivo de final de una llamada.

Revision: u16_voice_0004_end_saved
Revision anterior: u16_voice_0003_end_handed_off

Cuando la persona contesta "guardalo" a la oferta de dejar el caso guardado o
pasarlo a un ajustador, la llamada se despide y termina con su propio motivo. No es
`silence` ni `dropped`: es la unica despedida deliberada que deja el caso
retomable, y la fila tiene que decirlo para que el aviso de la consola y la ventana
de retoma cuenten lo que paso.

Cambio aditivo, igual que `u16_voice_0003_end_handed_off`: ninguna fila existente
deja de valer.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "u16_voice_0004_end_saved"
down_revision: str | None = "u16_voice_0003_end_handed_off"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ANTERIOR = "('hangup', 'silence', 'max_duration', 'dropped', 'error', 'completed', 'handed_off')"
_NUEVO = (
    "('hangup', 'silence', 'max_duration', 'dropped', 'error', 'completed', 'handed_off', 'saved')"
)
_RESTRICCION = "call_session_motivo_valido"


def upgrade() -> None:
    op.execute(f"ALTER TABLE call_session DROP CONSTRAINT {_RESTRICCION}")
    op.execute(
        f"ALTER TABLE call_session ADD CONSTRAINT {_RESTRICCION} "
        f"CHECK (end_reason IS NULL OR end_reason IN {_NUEVO})"
    )


def downgrade() -> None:
    """Primero se retiran las filas que usan el motivo nuevo, como en la 0003."""
    op.execute("DELETE FROM call_session WHERE end_reason = 'saved'")
    op.execute(f"ALTER TABLE call_session DROP CONSTRAINT {_RESTRICCION}")
    op.execute(
        f"ALTER TABLE call_session ADD CONSTRAINT {_RESTRICCION} "
        f"CHECK (end_reason IS NULL OR end_reason IN {_ANTERIOR})"
    )
