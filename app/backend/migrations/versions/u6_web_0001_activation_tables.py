"""u6_web_0001_activation_tables: las dos tablas de la activacion, con su aislamiento.

Revision: u6_web_0001_activation_tables
Revision anterior: u5_platform_0003_recording_lane

La telemetria de activacion cuenta cuantas sesiones llegan a cada uno de tres
hitos --primer mensaje, tercer turno y ciclo cerrado en la bandeja-- sin guardar
nada que apunte a una persona (BR8.1, BR8.2). Para contar cada hito **una sola
vez por sesion** hace falta recordar que sesiones ya lo alcanzaron; para publicar
la cifra hace falta un conteo que sobreviva a la noche. Son dos cosas con dos
vidas distintas, y por eso dos tablas:

- `activation_progress` es **dato de visitante**: una fila por sesion y hito,
  donde la sesion es la clave del navegador de U2 --su resumen, nunca la clave--
  (FD-U6-3). Lleva la marca, y el purgador de U6 la vacia en el reinicio
  nocturno.
- `activation_daily` es lo que sobrevive: cuantas sesiones alcanzaron cada hito,
  por dia y por aseguradora. No tiene ninguna columna que apunte a una persona
  ni a un navegador, y por eso no lleva la marca.

**Las dos van aisladas por aseguradora** (NFR10.5). La del conteo tambien: es de
una aseguradora, y ninguna tiene por que ver cuantas visitas recibio otra.

**Ninguna columna es texto libre.** Todas las de texto llevan su tope escrito y,
donde el valor tiene forma, una restriccion que la impone: el resumen de la clave
son sesenta y cuatro digitos hexadecimales y el hito es uno de tres. Es lo que
comprueba NFR11.7 contra el catalogo vivo, con la misma lista versionada de
nombres de dato personal que usa U5.

**Las lineas de aislamiento estan escritas literales, una por tabla**, como en la
revision de U2: una revision tiene que decir por si sola que aislamiento dejo.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "u6_web_0001_activation_tables"
down_revision: str | None = "u5_platform_0003_recording_lane"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: El tope de la columna de aseguradora: el identificador son hasta treinta y un
#: caracteres (`TENANT_ID_PATTERN` de U2). Un tope aqui y no `text` es lo que la
#: deja fuera de "texto libre" (NFR11.7).
ASEGURADORA = sa.String(31)

#: Los tres hitos, escritos una vez para las dos restricciones.
HITOS = "'first_message', 'third_turn', 'loop_closed'"


def upgrade() -> None:
    # --- El avance de cada sesion: dato de visitante ---------------------------
    op.create_table(
        "activation_progress",
        sa.Column("tenant_id", ASEGURADORA, nullable=False),
        # El resumen de la clave del navegador que U2 ya guarda, nunca la clave.
        # Nada aqui identifica a una persona (FD-U6-3).
        sa.Column("visitor_key_hash", sa.String(64), nullable=False),
        sa.Column("milestone", sa.String(16), nullable=False),
        sa.Column("reached_at", sa.DateTime(timezone=True), nullable=False),
        # La identidad es la terna: el segundo intento de registrar el mismo hito
        # en la misma sesion choca aqui y no cuenta (BR8.1).
        sa.PrimaryKeyConstraint(
            "tenant_id", "visitor_key_hash", "milestone", name="activation_progress_pk"
        ),
        # La sesion es una clave de navegador **de esa aseguradora** que U2 ya
        # reconocio: sin esta referencia, un resumen inventado contaria como una
        # sesion. La cascada hace que el borrado nocturno de las claves se lleve
        # tambien su avance, en vez de dejar filas que no apuntan a nada.
        sa.ForeignKeyConstraint(
            ["tenant_id", "visitor_key_hash"],
            ["visitor_key.tenant_id", "visitor_key.visitor_key_hash"],
            name="activation_progress_de_su_clave",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "visitor_key_hash ~ '^[0-9a-f]{64}$'",
            name="activation_progress_resumen_de_clave",
        ),
        sa.CheckConstraint(
            f"milestone IN ({HITOS})",
            name="activation_progress_hito_valido",
        ),
    )
    op.execute("ALTER TABLE activation_progress ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE activation_progress FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON activation_progress
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
        """
    )
    # La marca de dato de visitante, en la misma revision que crea la tabla: la
    # prueba de completitud del registro de purgadores le pregunta al catalogo
    # que tablas la llevan y exige que cada una tenga purgador (C-11, BR8.2).
    op.execute(
        "COMMENT ON TABLE activation_progress IS "
        "'visitor-data: hitos de activacion ya alcanzados por una sesion (C-11, BR8.2)'"
    )

    # --- El conteo diario: lo que sobrevive a la noche -------------------------
    op.create_table(
        "activation_daily",
        sa.Column("tenant_id", ASEGURADORA, nullable=False),
        # Dia en UTC. Un dia local distinto por aseguradora partiria la misma
        # noche en dos filas segun quien mire.
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("milestone", sa.String(16), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("tenant_id", "day", "milestone", name="activation_daily_pk"),
        sa.CheckConstraint(f"milestone IN ({HITOS})", name="activation_daily_hito_valido"),
        sa.CheckConstraint("count >= 0", name="activation_daily_conteo_no_negativo"),
    )
    op.execute("ALTER TABLE activation_daily ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE activation_daily FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON activation_daily
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
        """
    )
    # Sin la marca, a proposito: esta tabla no apunta a nadie y es la cifra que
    # tiene que sobrevivir al reinicio (BR8.2). El comentario lo dice para quien
    # lea el catalogo, sin empezar por la marca.
    op.execute(
        "COMMENT ON TABLE activation_daily IS "
        "'Conteo diario de activacion por aseguradora e hito; no apunta a ninguna "
        "sesion y sobrevive al reinicio nocturno (BR8.2)'"
    )


def downgrade() -> None:
    """Deshace la revision entera. Se prueba en cada corrida, no se supone.

    `mise run migrate:check` sube, baja y vuelve a subir contra una base virgen.
    """
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON activation_daily")
    op.drop_table("activation_daily")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON activation_progress")
    op.drop_table("activation_progress")
