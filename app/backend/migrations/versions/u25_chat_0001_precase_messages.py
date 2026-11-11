"""u25_chat_0001_precase_messages: lo hablado en el chat antes de que exista un caso.

Revision: u25_chat_0001_precase_messages
Revision anterior: u24_adjuster_0004_adjuster_run

## Por que existe

Un saludo, una duda general o «tengo una duda de mi poliza» no abren caso, y sin caso no hay
transcripcion donde guardarlos: vivian solo en la memoria del proceso, con un tope de ocho
lineas, y al recargar la pantalla, reiniciar el servidor o caer en otra instancia desaparecian.
Esta tabla los guarda por conversacion para que se vean al volver y para que la agente pueda
reconstruir el contexto.

## Llave compuesta hacia la conversacion

`chat_session` tiene como llave primaria solo `chat_session_id`; se le anade la restriccion unica
`(tenant_id, chat_session_id)` para que esta tabla pueda apuntarle con la aseguradora dentro, igual
que `chat_session` apunta a `case_record` (la leccion de U8: las llaves foraneas de PostgreSQL no
pasan por las politicas de fila, y una llave de una sola columna dejaria a una aseguradora colgar
un mensaje de la conversacion de otra). La cascada borra los mensajes con su conversacion, asi que
el purgador de `chat_session` los limpia cada noche sin sentencia propia.

## Orden y tope

`(chat_session_id, seq)` es unico: el orden de lectura es `seq` y no la hora. El tope de 40
mensajes por conversacion lo aplica quien escribe, no la base.

## Marca de dato de visitante

Lleva la marca (C-11): el texto sale de lo que una persona escribio. Se guarda tal como se escribio,
sin tapar (decision de Miguel, 2026-10-30).

## Reversible

`downgrade` borra la tabla y la restriccion unica anadida a `chat_session`.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "u25_chat_0001_precase_messages"
down_revision: str | None = "u24_adjuster_0004_adjuster_run"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: La marca de dato de visitante (C-11), igual que en U13.
MARCA = "visitor-data"

TABLA = "chat_session_message"
LLAVE_DE_LA_CONVERSACION = "chat_session_llave_con_aseguradora"

_POLITICA = """
    CREATE POLICY tenant_isolation ON {tabla}
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
"""


def upgrade() -> None:
    op.create_unique_constraint(
        LLAVE_DE_LA_CONVERSACION, "chat_session", ["tenant_id", "chat_session_id"]
    )
    op.create_table(
        TABLA,
        sa.Column("message_id", sa.Text(), primary_key=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("chat_session_id", sa.Text(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("speaker", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "chat_session_id"],
            ["chat_session.tenant_id", "chat_session.chat_session_id"],
            name="chat_session_message_de_la_conversacion",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("chat_session_id", "seq", name="chat_session_message_orden_unico"),
        sa.CheckConstraint(
            "speaker IN ('person', 'agent')", name="chat_session_message_hablante_valido"
        ),
        sa.CheckConstraint("language IN ('es', 'en')", name="chat_session_message_idioma_valido"),
        sa.CheckConstraint("seq >= 1", name="chat_session_message_orden_positivo"),
    )
    op.execute(f"ALTER TABLE {TABLA} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {TABLA} FORCE ROW LEVEL SECURITY")
    op.execute(_POLITICA.format(tabla=TABLA))
    op.execute(
        f"COMMENT ON TABLE {TABLA} IS "
        f"'{MARCA}: lo que una persona y la agente se dijeron en el chat antes de abrir un caso "
        "(C-11)'"
    )


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {TABLA}")
    op.drop_table(TABLA)
    op.drop_constraint(LLAVE_DE_LA_CONVERSACION, "chat_session", type_="unique")
