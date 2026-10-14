"""u23_reply_0001_anthropic: el libro mayor acepta Anthropic y el uso `chat_reply`.

Revision: u23_reply_0001_anthropic
Revision anterior: u19_quote_0001_eligibility

La redaccion natural del chat (decision de Miguel del 2026-10-07) llama a Claude
Haiku 5.5 con su propia clave y su propio saldo prepagado, y su gasto se registra
como el de cualquier otra llamada: con su proveedor, su uso y su precio de lista.
Las dos restricciones del libro mayor enumeran los valores de `ProviderName` y de
`Use`, y una prueba de integracion falla si la base y las listas no coinciden.

Solo amplia lo aceptado: ninguna fila existente cambia. `downgrade` vuelve a las
listas anteriores y se detiene si alguna fila ya usa uno de los valores nuevos,
porque una fila de gasto no se borra para que una migracion baje (BR3.1).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "u23_reply_0001_anthropic"
down_revision: str | None = "u19_quote_0001_eligibility"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLA = "spend_entry"
PROVEEDOR = "spend_entry_proveedor_valido"
USO = "spend_entry_uso_valido"

PROVEEDORES_ANTES = "provider IN ('gemini', 'deepgram', 'cartesia')"
PROVEEDORES_AHORA = "provider IN ('gemini', 'deepgram', 'cartesia', 'anthropic')"
USOS_ANTES = "use IN ('voice', 'chat', 'evals', 'operations', 'corpus')"
USOS_AHORA = "use IN ('voice', 'chat', 'evals', 'operations', 'corpus', 'chat_reply')"

_FILAS_NUEVAS = sa.text(
    "SELECT count(*) FROM spend_entry WHERE provider = 'anthropic' OR use = 'chat_reply'"
)


class NewValuesInUseError(RuntimeError):
    """Hay filas de gasto con los valores que la bajada quitaria."""


def upgrade() -> None:
    op.drop_constraint(PROVEEDOR, TABLA, type_="check")
    op.create_check_constraint(PROVEEDOR, TABLA, PROVEEDORES_AHORA)
    op.drop_constraint(USO, TABLA, type_="check")
    op.create_check_constraint(USO, TABLA, USOS_AHORA)


def downgrade() -> None:
    filas = op.get_bind().execute(_FILAS_NUEVAS).scalar_one()
    if filas:
        msg = (
            f"{filas} fila(s) de '{TABLA}' usan Anthropic o el uso 'chat_reply'. La "
            "revision no borra el libro mayor: decida que hacer con ellas y vuelva a correrla"
        )
        raise NewValuesInUseError(msg)
    op.drop_constraint(USO, TABLA, type_="check")
    op.create_check_constraint(USO, TABLA, USOS_ANTES)
    op.drop_constraint(PROVEEDOR, TABLA, type_="check")
    op.create_check_constraint(PROVEEDOR, TABLA, PROVEEDORES_ANTES)
