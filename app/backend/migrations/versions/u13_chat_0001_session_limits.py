"""u13_chat_0001_session_limits: la conversacion del navegador y sus contadores.

Dos tablas, y la diferencia entre ellas es a proposito.

`chat_session` **es** dato de visitante: lleva el resumen de la clave de su
navegador y apunta a su caso. Lleva la marca, su politica de fila y su purgador.

`chat_rate_window` son contadores. Sigue el precedente que U5 y U6 ya fijaron para
sus tablas de cuota: **no lleva la marca** --no es dato de visitante, es aritmetica
del sitio-- pero si tiene filas que apuntan a un visitante, las de ambito `origin`,
y esas las borra su purgador cada noche. La fila del ambito `site_day` se conserva:
no apunta a nadie y es la cifra que el panel publico de U22 necesita que sobreviva.

**Por que el resumen de la clave y no la clave** (SEC-U13.4): la clave del navegador
es lo unico que ata una conversacion a una persona. Guardandola en claro, un volcado
de la base sirve para hacerse pasar por cualquier visitante; guardando su resumen, no.
Es la misma forma que U2 ya usa para sus enlaces firmados.

**Una sola conversacion viva por navegador y aseguradora**, con un indice unico
parcial, igual que `human_review_request_una_viva` de U12: dos conversaciones abiertas
del mismo navegador dejarian la retoma sin saber cual retomar. Cerrada una, otra puede
abrirse.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "u13_chat_0001_session_limits"
down_revision: str | None = "u12_graph_0002_checkpointer"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: La marca de dato de visitante. Solo `chat_session` la lleva; ver el docstring.
MARCA = "visitor-data"

_POLITICA = """
    CREATE POLICY tenant_isolation ON {tabla}
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
"""


def _aislar(tabla: str, descripcion: str, *, marcar: bool = True) -> None:
    """Habilita, fuerza y politiza el aislamiento; marca solo si es de visitante."""
    op.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {tabla} FORCE ROW LEVEL SECURITY")
    op.execute(_POLITICA.format(tabla=tabla))
    prefijo = f"{MARCA}: " if marcar else ""
    op.execute(f"COMMENT ON TABLE {tabla} IS '{prefijo}{descripcion} (C-11)'")


def upgrade() -> None:
    # --- La conversacion de un navegador --------------------------------------
    op.create_table(
        "chat_session",
        sa.Column("chat_session_id", sa.Text(), primary_key=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        # El resumen, nunca la clave (SEC-U13.4).
        sa.Column("visitor_key_digest", sa.Text(), nullable=False),
        # Nulo antes de que haya algo que registrar: una conversacion existe
        # desde el primer mensaje, y el caso solo cuando hace falta.
        sa.Column("case_id", sa.Text(), nullable=True),
        # El idioma en que responde la agente **ahora** (BR2.1). Vive aqui y no
        # en el navegador para que el selector no pueda mostrar una cosa
        # mientras pasa otra.
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("origin_digest", sa.Text(), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        # La llave compuesta, con la aseguradora dentro: una de una sola columna
        # dejaria a una aseguradora nombrar el caso de otra. Es la leccion que
        # U8 encontro de verdad y que no se vuelve a abrir.
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["case_record.tenant_id", "case_record.case_id"],
            name="chat_session_del_caso",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("language IN ('es', 'en')", name="chat_session_idioma_valido"),
        sa.CheckConstraint("message_count >= 0", name="chat_session_conteo_valido"),
    )
    # Una sola conversacion viva por navegador y aseguradora.
    op.execute(
        "CREATE UNIQUE INDEX chat_session_una_viva ON chat_session "
        "(tenant_id, visitor_key_digest) WHERE closed_at IS NULL"
    )
    _aislar(
        "chat_session",
        "la conversacion de chat de un visitante, con el resumen de la clave de su navegador",
    )

    # --- Los contadores de los limites ----------------------------------------
    op.create_table(
        "chat_rate_window",
        sa.Column("tenant_id", sa.Text(), primary_key=True),
        # Conjunto cerrado escrito literalmente, como el resto del proyecto.
        sa.Column("scope", sa.Text(), primary_key=True),
        sa.Column("scope_key", sa.Text(), primary_key=True),
        # El inicio de la ventana, para que reiniciar sea comparar y no borrar.
        sa.Column("window_start", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint(
            "scope IN ('origin', 'site_day')", name="chat_rate_window_ambito_valido"
        ),
        sa.CheckConstraint("count >= 0", name="chat_rate_window_conteo_valido"),
    )
    _aislar(
        "chat_rate_window",
        "contadores de los limites del chat por origen y por dia del sitio",
        marcar=False,
    )


def downgrade() -> None:
    op.drop_table("chat_rate_window")
    op.execute("DROP INDEX IF EXISTS chat_session_una_viva")
    op.drop_table("chat_session")
