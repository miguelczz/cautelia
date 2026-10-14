"""u12_graph_0002_checkpointer: lo que la interfaz del framework exige.

Revision: u12_graph_0002_checkpointer
Revision anterior: u12_graph_0001_runtime_tables

El paso 1 escribio `graph_checkpoint` pensando en la forma del punto de control
del PRD, antes de mirar de cerca la interfaz que hay que cumplir
(`BaseCheckpointSaver` de `langgraph-checkpoint`). Leida esa interfaz, faltan
tres cosas y esta revision las anade, sin tocar lo que el paso 1 ya dejo bien:

**1. El espacio de nombres del hilo y el punto de control padre.** LangGraph
identifica un punto de control por `(thread_id, checkpoint_ns, checkpoint_id)`,
no solo por hilo y paso, y cada uno declara de cual viene (`parent_checkpoint_id`)
para que `aget_tuple` pueda devolver la configuracion del padre. Este proyecto no
usa subgrafos, asi que `checkpoint_ns` sera siempre `''`; se anade igual porque la
interfaz la exige de todo checkpointer, no solo de los que tienen subgrafos.

**2. Las escrituras pendientes de un paso que todavia no se guardo como punto de
control.** Es lo que permite reanudar un turno que se interrumpio a mitad --por
ejemplo, hacia la bandeja-- sin perder lo que los nodos ya habian escrito antes
de la interrupcion. Nace como tabla propia, `graph_checkpoint_write`, con la
misma forma de aislamiento que las tres del paso 1: aseguradora propia, politica
de fila, `FORCE ROW LEVEL SECURITY`, y llave foranea **compuesta**
`(tenant_id, case_id)` hacia el caso con borrado en cascada -- la misma leccion de
U8 que el paso 1 ya aplico, y que no se vuelve a saltar aqui. No lleva llave hacia
`graph_checkpoint`: una escritura pendiente existe **antes** de que su punto de
control se guarde, asi que no hay fila que referenciar todavia.

**3. Los metadatos del punto de control.** `CheckpointMetadata` (origen, paso,
padres, identificador de corrida) es un dato mas que el framework pide guardar
junto al estado. Viaja **cifrado con el mismo cifrador del caso**, igual que el
estado: no es dato personal en la practica, pero esta unidad ya decidio (BR6.3)
que ninguna copia del punto de control se queda en claro, y tratarla distinto por
ser "solo metadatos" seria la clase de excepcion que un dia se usa para colar
algo que si importa.

**El paso y su unicidad, ampliados al espacio de nombres.** La restriccion y el
indice del paso 1 -- "un paso por hilo y por aseguradora" -- se ensanchan a "un
paso por hilo, por espacio de nombres y por aseguradora": dos subgrafos del mismo
hilo no comparten numeracion, aunque hoy no existan. Mismo nombre, forma nueva.

**Por que dos columnas de tipo junto a cada blob.** `payload_type` y
`metadata_type` guardan la etiqueta que el serializador del framework le pone a
lo que serializo (`serde.dumps_typed` devuelve un par tipo-y-bytes, no solo
bytes). Sin la etiqueta, leer de vuelta seria adivinar como decodificar.

Los conjuntos y las tres lineas de aislamiento se escriben **literales**, como en
el paso 1: por la misma razon, y no se repite aqui.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "u12_graph_0002_checkpointer"
down_revision: str | None = "u12_graph_0001_runtime_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: La marca de dato de visitante, igual que en el paso 1: el purgador del caso ya
#: la declara para esta tabla nueva (`case_record/purge.py`, tabla `graph_checkpoint_write`).
MARCA = "visitor-data"

#: La unicidad de U10 sobre `(tenant_id, case_id)`, la misma que usa el paso 1.
CASO_UNICO = "case_record_aseguradora_y_caso"

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
    # --- Lo que le faltaba a graph_checkpoint ----------------------------------
    op.add_column(
        "graph_checkpoint",
        # Siempre '' en este proyecto -- no hay subgrafos -- pero la interfaz la
        # exige de todo checkpointer.
        sa.Column("checkpoint_ns", sa.Text(), nullable=False, server_default=""),
    )
    op.alter_column("graph_checkpoint", "checkpoint_ns", server_default=None)
    op.add_column(
        "graph_checkpoint",
        # Nulo para el primer punto de control de un hilo; el resto encadena.
        sa.Column("parent_checkpoint_id", sa.Text(), nullable=True),
    )
    op.add_column("graph_checkpoint", sa.Column("payload_type", sa.Text(), nullable=False))
    op.add_column("graph_checkpoint", sa.Column("metadata_type", sa.Text(), nullable=False))
    op.add_column("graph_checkpoint", sa.Column("metadata", sa.LargeBinary(), nullable=False))

    # El paso 1 declaro "un paso por hilo y por aseguradora"; ahora es "por
    # espacio de nombres" tambien. Mismo nombre, restriccion mas ancha.
    op.drop_constraint("graph_checkpoint_paso_unico", "graph_checkpoint", type_="unique")
    op.create_unique_constraint(
        "graph_checkpoint_paso_unico",
        "graph_checkpoint",
        ["tenant_id", "thread_id", "checkpoint_ns", "step"],
    )
    op.drop_index("graph_checkpoint_ultimo", table_name="graph_checkpoint")
    op.execute(
        "CREATE INDEX graph_checkpoint_ultimo ON graph_checkpoint "
        "(tenant_id, thread_id, checkpoint_ns, step DESC)"
    )

    # --- La escritura pendiente -------------------------------------------------
    op.create_table(
        "graph_checkpoint_write",
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("case_id", sa.Text(), nullable=False),
        # El hilo y el espacio de nombres del punto de control al que esta
        # escritura queda pendiente. Sin llave hacia `graph_checkpoint`: la
        # escritura existe antes de que ese punto de control se guarde.
        sa.Column("thread_id", sa.Text(), nullable=False),
        sa.Column("checkpoint_ns", sa.Text(), nullable=False),
        sa.Column("checkpoint_id", sa.Text(), nullable=False),
        # Quien la escribio y en que orden. `idx` puede ser negativo: el
        # framework reserva indices negativos para sus canales especiales
        # (error, reintento programado, interrupcion, reanudacion), para que
        # nunca choquen con el indice de una escritura normal.
        sa.Column("task_id", sa.Text(), nullable=False),
        sa.Column("task_path", sa.Text(), nullable=False, server_default=""),
        sa.Column("idx", sa.Integer(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("value_type", sa.Text(), nullable=False),
        sa.Column("value", sa.LargeBinary(), nullable=False),
        sa.Column("sealed_key_id", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "tenant_id",
            "thread_id",
            "checkpoint_ns",
            "checkpoint_id",
            "task_id",
            "idx",
            name="graph_checkpoint_write_pkey",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["case_record.tenant_id", "case_record.case_id"],
            name="graph_checkpoint_write_del_caso",
            ondelete="CASCADE",
        ),
    )
    op.alter_column("graph_checkpoint_write", "task_path", server_default=None)
    _aislar(
        "graph_checkpoint_write",
        "una escritura pendiente del caso de un visitante, cifrada",
    )


def downgrade() -> None:
    """El orden inverso. Se prueba en cada corrida, no se supone."""
    op.drop_table("graph_checkpoint_write")

    op.drop_index("graph_checkpoint_ultimo", table_name="graph_checkpoint")
    op.execute(
        "CREATE INDEX graph_checkpoint_ultimo ON graph_checkpoint (tenant_id, thread_id, step DESC)"
    )
    op.drop_constraint("graph_checkpoint_paso_unico", "graph_checkpoint", type_="unique")
    op.create_unique_constraint(
        "graph_checkpoint_paso_unico", "graph_checkpoint", ["tenant_id", "thread_id", "step"]
    )

    op.drop_column("graph_checkpoint", "metadata")
    op.drop_column("graph_checkpoint", "metadata_type")
    op.drop_column("graph_checkpoint", "payload_type")
    op.drop_column("graph_checkpoint", "parent_checkpoint_id")
    op.drop_column("graph_checkpoint", "checkpoint_ns")
