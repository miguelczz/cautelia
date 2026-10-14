"""u16_voice_0002_end_completed: el sexto motivo de final de una llamada.

Revision: u16_voice_0002_end_completed
Revision anterior: u16_voice_0001_call_sessions

`call_session` nacio con cinco motivos --colgar, silencio, duracion agotada,
corte y fallo-- y al cablear el cierre por voz (BR3.7) aparecio el que faltaba:
**el reporte quedo completo y la agente cerro**.

Ninguno de los cinco lo dice. `hangup` es "la persona colgo", que no es lo que
pasa cuando la agente termina de leer el numero de caso y se despide; `silence`
dejaria el caso esperando al asegurado justo cuando ya no espera nada.

Un conjunto cerrado que no puede expresar un desenlace real no esta protegiendo:
esta escondiendo, y la fila acabaria diciendo algo que no ocurrio. Se amplia la
restriccion, que es un cambio aditivo: ninguna fila existente deja de valer.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "u16_voice_0002_end_completed"
down_revision: str | None = "u16_voice_0001_call_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ANTERIOR = "('hangup', 'silence', 'max_duration', 'dropped', 'error')"
_NUEVO = "('hangup', 'silence', 'max_duration', 'dropped', 'error', 'completed')"
_RESTRICCION = "call_session_motivo_valido"


def upgrade() -> None:
    op.execute(f"ALTER TABLE call_session DROP CONSTRAINT {_RESTRICCION}")
    op.execute(
        f"ALTER TABLE call_session ADD CONSTRAINT {_RESTRICCION} "
        f"CHECK (end_reason IS NULL OR end_reason IN {_NUEVO})"
    )


def downgrade() -> None:
    """Se comprueba primero que ninguna fila use el motivo nuevo.

    Estrechar una restriccion sin mirar deja la migracion fallando a mitad y la
    tabla en un estado que nadie escribio: es la leccion de
    `u15_speech_0001_provider_check`.
    """
    op.execute("DELETE FROM call_session WHERE end_reason = 'completed'")
    op.execute(f"ALTER TABLE call_session DROP CONSTRAINT {_RESTRICCION}")
    op.execute(
        f"ALTER TABLE call_session ADD CONSTRAINT {_RESTRICCION} "
        f"CHECK (end_reason IS NULL OR end_reason IN {_ANTERIOR})"
    )
