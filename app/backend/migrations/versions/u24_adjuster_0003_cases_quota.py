"""u24_adjuster_0003_cases_quota: el cupo diario de casos del ajustador de IA.

Revision: u24_adjuster_0003_cases_quota
Revision anterior: u24_adjuster_0002_ai_actor

El tope diario de casos que decide el ajustador (`adjuster_cases_site_day`, por defecto 20) se
cuenta en `quota_counter`, el mismo cupo que ya protege el chat y la voz. Es del sitio entero,
como `voice_calls_site_day`, y por eso dos restricciones cambian:

- `quota_counter_alcance_valido`: acepta el alcance nuevo.
- `quota_counter_sitio_sin_dueno`: «un alcance del sitio lleva el sujeto `site`, y ningun otro
  lo lleva» deja de nombrar un solo alcance y nombra los dos.

`downgrade` borra las filas del alcance nuevo: un contador de un dia no es historial, y la
restriccion de vuelta las rechazaria.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "u24_adjuster_0003_cases_quota"
down_revision: str | None = "u24_adjuster_0002_ai_actor"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLA = "quota_counter"
ALCANCE = "quota_counter_alcance_valido"
SITIO = "quota_counter_sitio_sin_dueno"

ALCANCES_ANTES = (
    "scope IN ('chat_messages_session', 'chat_messages_day', "
    "'voice_calls_visitor_day', 'voice_calls_site_day')"
)
ALCANCES_AHORA = (
    "scope IN ('chat_messages_session', 'chat_messages_day', "
    "'voice_calls_visitor_day', 'voice_calls_site_day', 'adjuster_cases_site_day')"
)
SITIO_ANTES = "(scope = 'voice_calls_site_day') = (subject_key = 'site')"
SITIO_AHORA = (
    "(scope IN ('voice_calls_site_day', 'adjuster_cases_site_day')) = (subject_key = 'site')"
)


def _cambiar(nombre: str, condicion: str) -> None:
    op.drop_constraint(nombre, TABLA, type_="check")
    op.create_check_constraint(nombre, TABLA, condicion)


def upgrade() -> None:
    _cambiar(ALCANCE, ALCANCES_AHORA)
    _cambiar(SITIO, SITIO_AHORA)


def downgrade() -> None:
    op.execute("DELETE FROM quota_counter WHERE scope = 'adjuster_cases_site_day'")
    _cambiar(SITIO, SITIO_ANTES)
    _cambiar(ALCANCE, ALCANCES_ANTES)
