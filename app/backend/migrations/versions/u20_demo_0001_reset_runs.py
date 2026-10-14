"""u20_demo_0001_reset_runs: el registro de cada corrida del reinicio nocturno.

Revision: u20_demo_0001_reset_runs
Revision anterior: u16_voice_0002_end_completed

Dos tablas, y las dos son **dato del proyecto**: una corrida del reinicio no es
de ninguna aseguradora --barre las tres-- y lo que guarda no apunta a ninguna
persona. Son la unica parte del aplicativo que tiene que sobrevivir **al propio
reinicio**, porque de ellas sale la respuesta a la pregunta de BR3.2: cuanto hace
que no hay un reinicio exitoso.

**Por que en la base y no en un archivo** (TECH-U20.4). Un archivo en `tmp/` no
sobrevive al despliegue que es justo cuando hay que saber si la demo esta limpia,
y uno versionado ensuciaria cada commit con el resultado de una corrida nocturna.

**Por que dos tablas y no una con un campo compuesto.** La fila por purgador es
la entidad que `entities.md` pide --"`purgers` guarda lo que cada purgador dijo,
no un total"-- y un total no dice cual dejo de borrar el dia que algo cambie.
Meterlas como `jsonb` en una sola tabla seria texto libre en una tabla excluida
del aislamiento, que es exactamente lo que BR7.2 cobra por la exclusion.

**La quinta y la sexta tabla excluidas del aislamiento**, declaradas en
`[tool.untangle.rls] excluded` con su razon. Pagan lo que esa exclusion cobra:
cada columna es un identificador acotado, un entero, una marca de tiempo o un
valor de un conjunto cerrado; ninguna es texto sin tope y ninguna coincide con la
lista versionada de nombres de dato personal.

**Lo que las restricciones hacen imposible**, y es lo mismo que el tipo ya impide
en memoria: una corrida que termina antes de empezar, un resultado fuera del
conjunto cerrado, una fila de purgador que fallo y aun asi declara cuanto borro,
y una que no fallo y no lo declara. Que la regla viva en los dos sitios no es
duplicarla por gusto: el tipo protege al que escribe por la API y la restriccion
protege de un `INSERT` a mano, que es como se arregla una noche a las dos.

**No se purga a si misma.** El reinicio nocturno no borra estas filas: una fila
por noche no crece, y borrarlas dejaria el contador de 24 horas sin memoria justo
despues de cada corrida, que es el estado en el que las superficies cierran.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "u20_demo_0001_reset_runs"
down_revision: str | None = "u16_voice_0002_end_completed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- La corrida -----------------------------------------------------------
    op.create_table(
        "reset_run",
        sa.Column("reset_run_id", sa.String(64), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        # El conjunto cerrado de tres, con `partial` entre los dos extremos: no es
        # un lujo, es el estado que decide si el reintento repite todo o solo lo
        # que falta (`entities.md`).
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('succeeded', 'failed', 'partial')", name="reset_run_resultado_valido"
        ),
        sa.CheckConstraint("finished_at >= started_at", name="reset_run_termina_despues"),
    )
    # El indice de la unica consulta caliente: cual fue el ultimo reinicio
    # **exitoso**, que es la que corre cada vez que una superficie publica decide
    # si acepta un caso nuevo (BR3.2).
    op.create_index("reset_run_ultimo_exito", "reset_run", ["outcome", "finished_at"])
    op.execute(
        "COMMENT ON TABLE reset_run IS "
        "'dato del proyecto: una fila por corrida del reinicio nocturno, de donde "
        "sale el contador de 24 horas de BR3.2'"
    )

    # --- Lo que dijo cada purgador -------------------------------------------
    op.create_table(
        "reset_run_purger",
        sa.Column(
            "reset_run_id",
            sa.String(64),
            sa.ForeignKey("reset_run.reset_run_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        # La clave compuesta es tambien la regla "un purgador aparece una sola
        # vez" de `ResetRun`, puesta donde un `INSERT` a mano tampoco la pueda
        # saltar.
        sa.Column("purger", sa.String(64), primary_key=True),
        # El orden en el que se llamo. Se guarda porque el registro de la raiz es
        # una tupla escrita a mano y su orden es parte de lo que se reviso: sin
        # esta columna, leer la corrida no diria en que orden corrio.
        sa.Column("call_order", sa.Integer(), nullable=False),
        # Nulos cuando el purgador fallo: **no se sabe** cuanto borro, y un cero
        # diria que no habia nada.
        sa.Column("deleted", sa.Integer(), nullable=True),
        sa.Column("kept", sa.Integer(), nullable=True),
        # Milisegundos y no segundos con decimales: es la resolucion que la
        # alerta necesita, y un entero no arrastra la aritmetica del punto
        # flotante por el registro.
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        # El **nombre del tipo** de la excepcion, nunca su mensaje: un mensaje de
        # error de base puede llevar un valor dentro, y esta fila sale en los logs.
        sa.Column("error_type", sa.String(64), nullable=True),
        sa.CheckConstraint("call_order >= 0", name="reset_run_purger_orden_no_negativo"),
        sa.CheckConstraint("duration_ms >= 0", name="reset_run_purger_duracion_no_negativa"),
        sa.CheckConstraint(
            "(error_type IS NULL AND deleted IS NOT NULL AND kept IS NOT NULL) "
            "OR (error_type IS NOT NULL AND deleted IS NULL AND kept IS NULL)",
            name="reset_run_purger_fallo_no_declara_cuanto",
        ),
    )
    op.execute(
        "COMMENT ON TABLE reset_run_purger IS "
        "'dato del proyecto: lo que dijo cada purgador en una corrida, una fila "
        "por purgador y nunca un total (entities.md de U20)'"
    )


def downgrade() -> None:
    """El orden inverso. Se prueba en cada corrida, no se supone."""
    op.drop_table("reset_run_purger")
    op.drop_index("reset_run_ultimo_exito", table_name="reset_run")
    op.drop_table("reset_run")
