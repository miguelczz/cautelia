"""u12_graph_0001_runtime_tables: las tres tablas del runtime, con su aislamiento.

Revision: u12_graph_0001_runtime_tables
Revision anterior: u11_intake_0002_alt_version

Tres tablas --el punto de control, la pausa hacia la bandeja y la ejecucion de
nodo-- y las tres existen por la misma razon: **el proceso se puede morir a mitad
de una conversacion**. En el hospedaje gratuito se duerme y despierta, asi que
reanudar no es una funcion de emergencia: es el camino normal.

Las tres nacen con **las tres lineas de aislamiento escritas literales**, por la
misma razon que las de U2 y U4: una revision tiene que decir por si sola que
aislamiento dejo.

Cuatro decisiones cargan el peso de esta revision:

**1. La aseguradora es columna propia, no algo que se saque del hilo.** El
identificador de hilo de LangGraph es texto que el framework elige; llevar la
aseguradora dentro de el obligaria a parsear texto para aislar, y una politica de
fila que dependa de un `split` no es una politica de fila. La columna cuesta
dieciseis bytes por punto de control.

**2. El punto de control va cifrado, y cada fila lleva el identificador de la
clave que la cifro.** El estado serializado lleva dentro el texto de la persona;
una tabla del grafo no es menos sensible que la del caso por vivir en otro modulo
(BR6.3). El identificador por fila es lo que permite rotar la clave sin reescribir
el almacen ni dejar una ventana en la que los casos no se puedan reanudar, igual
que en `case_field` de U4.

**3. `node_run` lleva su clave de idempotencia con unicidad por aseguradora.** No
es un adorno de trazabilidad: es lo que impide que un relanzamiento tras la muerte
del proceso vuelva a pagarle al proveedor por un trabajo que ya se hizo (BR5.4).
La unicidad la impone la base, no el barrido: un barrido con un error de
concurrencia gastaria dos veces contra un tope de 5 USD, y nadie lo notaria hasta
que el tope se agotara.

**4. Las tres cuelgan del caso con llave compuesta y borrado en cascada.** La llave
lleva `(tenant_id, case_id)` desde el primer commit, que es la leccion que U8 pago
caro: una llave foranea solo por `case_id` **no pasa por las politicas de fila**,
asi que una fila de una aseguradora podria apuntar al caso de otra. Y la cascada es
lo que hace que el purgador del caso las borre sin que nadie recuerde el orden
(BR6.4, UG-3).

Los conjuntos cerrados se escriben **literales** en sus restricciones y no se
generan desde los enums de Python: una migracion es el registro historico de lo que
se le hizo a la base, y si leyera el enum vivo, anadir un valor manana cambiaria el
significado de lo que esta revision dice haber hecho ayer.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "u12_graph_0001_runtime_tables"
down_revision: str | None = "u11_intake_0002_alt_version"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: La marca de dato de visitante. Una prueba de U2 le pregunta al catalogo que
#: tablas la llevan y exige que cada una tenga purgador declarado.
MARCA = "visitor-data"

#: La unicidad de U10 sobre `(tenant_id, case_id)`, que es lo que hace posible la
#: llave compuesta hacia el caso.
CASO_UNICO = "case_record_aseguradora_y_caso"

_POLITICA = """
    CREATE POLICY tenant_isolation ON {tabla}
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
"""


def _aislar(tabla: str, descripcion: str) -> None:
    """Habilita, fuerza y politiza el aislamiento, y escribe la marca.

    El texto del aislamiento esta a la vista en `_POLITICA`, arriba; lo que esta
    funcion evita repetir tres veces es solo la llamada.
    """
    op.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {tabla} FORCE ROW LEVEL SECURITY")
    op.execute(_POLITICA.format(tabla=tabla))
    op.execute(f"COMMENT ON TABLE {tabla} IS '{MARCA}: {descripcion} (C-11)'")


def upgrade() -> None:
    # --- El punto de control --------------------------------------------------
    op.create_table(
        "graph_checkpoint",
        sa.Column("checkpoint_id", sa.Text(), primary_key=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("case_id", sa.Text(), nullable=False),
        # El hilo de LangGraph. Es el caso: un caso, una conversacion (BR3.1).
        sa.Column("thread_id", sa.Text(), nullable=False),
        # Monotono por hilo. Reanudar es leer el mayor.
        sa.Column("step", sa.Integer(), nullable=False),
        # El estado serializado y cifrado (BR6.3).
        sa.Column("payload", sa.LargeBinary(), nullable=False),
        sa.Column("sealed_key_id", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["case_record.tenant_id", "case_record.case_id"],
            name="graph_checkpoint_del_caso",
            ondelete="CASCADE",
        ),
        # Un paso por hilo y por aseguradora: dos escrituras del mismo paso son
        # la misma escritura intentada dos veces, no dos estados distintos.
        sa.UniqueConstraint("tenant_id", "thread_id", "step", name="graph_checkpoint_paso_unico"),
        sa.CheckConstraint("step >= 0", name="graph_checkpoint_paso_valido"),
    )
    # Reanudar es leer el mayor paso de un hilo, y esto es el indice que lo hace
    # sin recorrer la tabla. El orden descendente es el de la consulta.
    op.execute(
        "CREATE INDEX graph_checkpoint_ultimo ON graph_checkpoint (tenant_id, thread_id, step DESC)"
    )
    _aislar(
        "graph_checkpoint",
        "el estado del grafo de un caso de visitante, cifrado en reposo",
    )

    # --- La pausa hacia la bandeja --------------------------------------------
    op.create_table(
        "human_review_request",
        sa.Column("request_id", sa.Text(), primary_key=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("case_id", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["case_record.tenant_id", "case_record.case_id"],
            name="human_review_request_del_caso",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "reason IN ('compliance_referral', 'abuse', 'provider_failure', 'incomplete_capture')",
            name="human_review_request_motivo_valido",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'resolved', 'withdrawn')",
            name="human_review_request_estado_valido",
        ),
        # Una pausa decidida lleva su hora, y una que no se decidio no la lleva.
        # `resolved` y `withdrawn` no se colapsan: la primera dice que una persona
        # la decidio, y decir eso de una pausa que se retiro sola seria escribir
        # en el historial algo que no paso (BR4.4).
        sa.CheckConstraint(
            "(status = 'resolved') = (resolved_at IS NOT NULL)",
            name="human_review_request_resuelta_con_su_hora",
        ),
        sa.CheckConstraint(
            "(status = 'withdrawn') = (withdrawn_at IS NOT NULL)",
            name="human_review_request_retirada_con_su_hora",
        ),
    )
    # Una sola pausa viva por caso: dos pausas abiertas del mismo caso dejarian a
    # la bandeja con dos entradas para una decision.
    op.execute(
        "CREATE UNIQUE INDEX human_review_request_una_viva "
        "ON human_review_request (tenant_id, case_id) WHERE status = 'open'"
    )
    _aislar(
        "human_review_request",
        "la pausa hacia la bandeja del caso de un visitante, con su motivo",
    )

    # --- La ejecucion de nodo -------------------------------------------------
    op.create_table(
        "node_run",
        sa.Column("node_run_id", sa.Text(), primary_key=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("case_id", sa.Text(), nullable=False),
        sa.Column("node", sa.Text(), nullable=False),
        sa.Column("rhythm", sa.Text(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        # Copiado del NodeSpec al ejecutar, no leido despues: cambiar la politica
        # no reescribe la historia.
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False, server_default="running"),
        sa.Column("error_type", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        # BR5.4: derivada del caso, el nodo y la entrada; nunca del reloj ni de un
        # aleatorio. Es lo que impide pagar dos veces el mismo trabajo.
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("lease_owner", sa.Text(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["case_record.tenant_id", "case_record.case_id"],
            name="node_run_del_caso",
            ondelete="CASCADE",
        ),
        # La unicidad la impone la base y no el barrido: un barrido con un error de
        # concurrencia gastaria dos veces contra un tope de 5 USD, y nadie lo
        # notaria hasta que el tope se agotara.
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="node_run_trabajo_unico"),
        sa.CheckConstraint(
            "node IN ('intake', 'policy_verification', 'decision', 'compliance')",
            name="node_run_nodo_valido",
        ),
        sa.CheckConstraint("rhythm IN ('turn', 'background')", name="node_run_ritmo_valido"),
        # `degraded` es agoto los intentos y se emitio su texto; `abandoned` es el
        # arrendamiento vencio y otro proceso lo tomo. Nunca se colapsan: el
        # primero es una respuesta al asegurado y el segundo es una operacion.
        sa.CheckConstraint(
            "outcome IN ('running', 'succeeded', 'failed', 'degraded', 'abandoned')",
            name="node_run_desenlace_valido",
        ),
        # La taxonomia cerrada de la frontera del proveedor (convencion 8a). El
        # tipo del SDK nunca llega aqui.
        sa.CheckConstraint(
            "error_type IS NULL OR error_type IN ('timeout', 'rate_limited', "
            "'unavailable', 'invalid_response')",
            name="node_run_error_valido",
        ),
        # Un desenlace bueno no lleva error, y uno malo lo lleva: sin esto, una
        # fila podria decir que todo salio bien y traer un `timeout` al lado.
        sa.CheckConstraint(
            "(outcome IN ('failed', 'degraded')) = (error_type IS NOT NULL)",
            name="node_run_error_con_su_desenlace",
        ),
        sa.CheckConstraint(
            "attempt >= 1 AND attempt <= max_attempts", name="node_run_intento_valido"
        ),
        # Un arrendamiento tiene dueno y vencimiento, o no tiene ninguno de los
        # dos: un dueno sin vencimiento no se puede recuperar nunca (BR5.5).
        sa.CheckConstraint(
            "(lease_owner IS NULL) = (lease_expires_at IS NULL)",
            name="node_run_arrendamiento_completo",
        ),
    )
    # El barrido busca lo que quedo corriendo con su arrendamiento vencido.
    op.execute(
        "CREATE INDEX node_run_pendiente ON node_run (tenant_id, lease_expires_at) "
        "WHERE outcome = 'running'"
    )
    _aislar(
        "node_run",
        "una ejecucion de nodo del caso de un visitante, con su arrendamiento",
    )


def downgrade() -> None:
    """El orden inverso. Se prueba en cada corrida, no se supone."""
    op.drop_index("node_run_pendiente", table_name="node_run")
    op.drop_table("node_run")
    op.drop_index("human_review_request_una_viva", table_name="human_review_request")
    op.drop_table("human_review_request")
    op.drop_index("graph_checkpoint_ultimo", table_name="graph_checkpoint")
    op.drop_table("graph_checkpoint")
