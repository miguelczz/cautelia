"""u16_voice_0001_call_sessions: la tabla de una llamada de voz.

Revision: u16_voice_0001_call_sessions
Revision anterior: u14_inbox_0001_tables

Una sola tabla, `call_session`: lo que queda escrito de una llamada
(`entities.md` de U16). Es dato de visitante y entra en el contrato de borrado
(BR7.3, UG-3).

**Ninguna columna de audio, y es la regla y no un olvido** (BR7.1, NFR19). No hay
ruta, no hay identificador de grabacion y no hay muestras. Anadir una exigiria
otra revision, que es exactamente la friccion que se quiere.

**Llave compuesta desde el primer commit** (la leccion de `u9_rules_0001`). La
llave foranea es `(tenant_id, case_id)` contra el par unico de `case_record`, no
`case_id` solo: las comprobaciones de llave foranea de PostgreSQL **no pasan por
las politicas de fila**, asi que con una llave simple una llamada de la
aseguradora B podria apuntar al caso de la aseguradora A. U10 tuvo que cerrar ese
hueco en una segunda revision; esta tabla nace sin abrirlo.

**El indice es por `(tenant_id, visitor_key_digest)`** porque es por donde se
busca al retomar (BR6.3), y por ningun otro sitio: buscar por poliza abriria el
caso de otro visitante, y una tabla sin indice por poliza es una forma barata de
que nadie lo intente por descuido.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "u16_voice_0001_call_sessions"
down_revision: str | None = "u14_inbox_0001_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: La marca de dato de visitante (C-11), igual que en U4, U9, U10 y U14.
MARCA = "visitor-data"

#: Los topes, escritos una vez (igual que `u9_rules_0001_evaluation_table`).
ASEGURADORA = sa.String(31)
IDENTIFICADOR = sa.String(64)
RESUMEN = sa.String(64)

_POLITICA = """
    CREATE POLICY tenant_isolation ON {tabla}
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
"""


def _aislar(tabla: str, descripcion: str) -> None:
    op.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {tabla} FORCE ROW LEVEL SECURITY")
    op.execute(_POLITICA.format(tabla=tabla))
    op.execute(f"COMMENT ON TABLE {tabla} IS '{MARCA}: {descripcion} (C-11)'")


def upgrade() -> None:
    op.create_table(
        "call_session",
        sa.Column("call_id", IDENTIFICADOR, primary_key=True),
        sa.Column("tenant_id", ASEGURADORA, nullable=False),
        sa.Column("case_id", IDENTIFICADOR, nullable=True),
        # El resumen de la clave del navegador, nunca la clave (U2).
        sa.Column("visitor_key_digest", RESUMEN, nullable=False),
        sa.Column("language", sa.String(2), nullable=False),
        sa.Column("voice_mode", sa.String(8), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_reason", sa.String(16), nullable=True),
        sa.Column("resume_until", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["case_record.tenant_id", "case_record.case_id"],
            name="call_session_del_caso",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("call_id <> ''", name="call_session_identificador"),
        sa.CheckConstraint("visitor_key_digest <> ''", name="call_session_navegador"),
        sa.CheckConstraint("language IN ('es', 'en')", name="call_session_idioma_valido"),
        sa.CheckConstraint(
            "voice_mode IN ('primary', 'fallback')",
            name="call_session_modo_de_voz_valido",
        ),
        sa.CheckConstraint(
            "state IN ('connecting', 'live', 'ended')",
            name="call_session_estado_valido",
        ),
        sa.CheckConstraint(
            "end_reason IS NULL OR end_reason IN "
            "('hangup', 'silence', 'max_duration', 'dropped', 'error')",
            name="call_session_motivo_valido",
        ),
        # Terminada es terminada: el estado y el motivo no se separan (BR1.6). Sin
        # esto una fila podria decir `ended` sin decir por que, que es justo lo que
        # la consola y la bandeja no saben leer.
        sa.CheckConstraint(
            "(state = 'ended') = (end_reason IS NOT NULL AND ended_at IS NOT NULL)",
            name="call_session_terminada_con_motivo",
        ),
    )
    # Por donde se busca al retomar (BR6.3), y por ningun otro sitio.
    op.create_index(
        "call_session_por_navegador",
        "call_session",
        ["tenant_id", "visitor_key_digest"],
    )
    _aislar("call_session", "la llamada de voz de un visitante")


def downgrade() -> None:
    """Deshace la revision entera. Se prueba en cada corrida, no se supone.

    `mise run migrate:check` sube, baja y vuelve a subir contra una base virgen.
    """
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON call_session")
    op.drop_index("call_session_por_navegador", table_name="call_session")
    op.drop_table("call_session")
