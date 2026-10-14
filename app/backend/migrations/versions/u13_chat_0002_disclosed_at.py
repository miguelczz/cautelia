"""u13_chat_0002_disclosed_at: cuando salio la apertura en esta conversacion.

Aditiva. La escribe la tanda 1 al atar la compuerta dura BR1.1: ningun texto del
visitante se procesa antes de que la apertura haya salido, y **lo que lo hace
comprobable es una fila, no una promesa**.

**Por que aqui y no en `disclosure_record`.** U10 ya registra la divulgacion por
caso, y ese registro sigue siendo el que impide cerrar un caso sin ella (BR6.1 de
U10). Pero la apertura del chat sale **antes de que exista ningun caso** --al cargar
la pagina, antes de que haya nada que registrar-- y una conversacion puede no llegar
nunca a abrir uno. Sin esta columna no habria donde anotar que salio, y la compuerta
dependeria de que nadie se saltara el orden.

Las dos anotaciones conviven y no se pisan: esta dice que la conversacion la vio, la
de U10 dice que el caso la tiene.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "u13_chat_0002_disclosed_at"
down_revision: str | None = "u13_chat_0001_session_limits"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nula mientras no ha salido, y mientras sea nula ningun mensaje se atiende.
    op.add_column(
        "chat_session",
        sa.Column("disclosed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_session", "disclosed_at")
