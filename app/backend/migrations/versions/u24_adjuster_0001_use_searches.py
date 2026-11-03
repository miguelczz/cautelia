"""u24_adjuster_0001_use_searches: el libro mayor acepta el uso `adjuster` y la unidad `web_searches`.

Revision: u24_adjuster_0001_use_searches
Revision anterior: u10_compliance_0002_no_pii

El ajustador de IA (plan 09, fase 5, 2026-11-03) llama a Claude con su propia clave y usa la
herramienta de busqueda web del servidor, que se cobra **por busqueda** y no por token. Las dos
cosas son valores nuevos de dos enums cerrados que la base enumera en una restriccion cada uno:

- `spend_entry_uso_valido`: el uso `adjuster`. Sin el, cada fila de gasto del ajustador
  fallaria al anotarse y, como el libro traga esa excepcion a proposito, nadie se enteraria
  (la leccion de `u8_policy_0002_uso_corpus`).
- `spend_entry_unidad_valida`: la unidad `web_searches`.

Solo amplia lo aceptado. `downgrade` se detiene si alguna fila ya usa un valor nuevo, porque una
fila de gasto no se borra para que una migracion baje (BR3.1).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "u24_adjuster_0001_use_searches"
down_revision: str | None = "u10_compliance_0002_no_pii"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLA = "spend_entry"
USO = "spend_entry_uso_valido"
UNIDAD = "spend_entry_unidad_valida"

USOS_ANTES = "use IN ('voice', 'chat', 'evals', 'operations', 'corpus', 'chat_reply', 'evals_chat')"
USOS_AHORA = (
    "use IN ('voice', 'chat', 'evals', 'operations', 'corpus', 'chat_reply', 'evals_chat', "
    "'adjuster')"
)

UNIDADES_ANTES = (
    "unit_kind IN ('input_tokens', 'output_tokens', 'embedding_tokens', "
    "'audio_seconds', 'characters')"
)
UNIDADES_AHORA = (
    "unit_kind IN ('input_tokens', 'output_tokens', 'embedding_tokens', "
    "'audio_seconds', 'characters', 'web_searches')"
)

_FILAS_NUEVAS = sa.text(
    "SELECT count(*) FROM spend_entry WHERE use = 'adjuster' OR unit_kind = 'web_searches'"
)


class NewValuesInUseError(RuntimeError):
    """Hay filas de gasto con un valor que la bajada quitaria."""


def upgrade() -> None:
    op.drop_constraint(USO, TABLA, type_="check")
    op.create_check_constraint(USO, TABLA, USOS_AHORA)
    op.drop_constraint(UNIDAD, TABLA, type_="check")
    op.create_check_constraint(UNIDAD, TABLA, UNIDADES_AHORA)


def downgrade() -> None:
    filas = op.get_bind().execute(_FILAS_NUEVAS).scalar_one()
    if filas:
        msg = (
            f"{filas} fila(s) de '{TABLA}' usan el uso 'adjuster' o la unidad 'web_searches'. "
            "La revision no borra el libro mayor: decida que hacer con ellas y vuelva a correrla"
        )
        raise NewValuesInUseError(msg)
    op.drop_constraint(UNIDAD, TABLA, type_="check")
    op.create_check_constraint(UNIDAD, TABLA, UNIDADES_ANTES)
    op.drop_constraint(USO, TABLA, type_="check")
    op.create_check_constraint(USO, TABLA, USOS_ANTES)
