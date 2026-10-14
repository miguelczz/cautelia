"""u14_inbox_0001_tables: las dos tablas de la bandeja.

U14 guarda **muy poco**, y eso es el diseno y no una carencia. El caso, sus
campos, su transcripcion y su historial son de U4; las citas de U8; la regla
disparada de U9; el resultado de los controles de U10; el resumen de traza de
U5. La bandeja reune y muestra lo que esas unidades ya guardan. El dia que
guardara su propia copia de cualquiera de ellas habria dos versiones de la
verdad y una forma de que discrepen.

Lo suyo son dos cosas que ninguna otra unidad tiene donde poner.

`inbox_event` es el aviso de que un caso cambio, que viaja por el flujo a la cola
y a la vista abiertas (C-06). **Se guarda y no solo se emite**: el navegador que
se reconecta manda `Last-Event-ID` y el servidor reproduce lo posterior
(ADR-021), y eso exige que los eventos existan despues de haberse entregado.

`decision_receipt` es el recibo de una escritura idempotente --una decision o una
correccion de campo--. C-05 promete que repetir la misma clave devuelve **la
primera** y no crea otra. Es **una sola tabla para las dos escrituras** porque es
un solo mecanismo; dos serian dos sitios donde arreglar el mismo fallo.

## El identificador del evento crece **por aseguradora**, no globalmente

Es el `id:` del cable y la posicion desde la que se reanuda. Con un contador
global, la secuencia que ve un inquilino tendria huecos --los numeros que se
llevaron los eventos de otras-- y un navegador que pidiera desde el ultimo hueco
recibiria eventos de otra aseguradora o ninguno. De ahi la llave compuesta
`(tenant_id, event_id)`: la aseguradora es parte de la identidad del evento y no
una columna mas que se compara despues.

## `request_digest` no es una optimizacion

Es lo que distingue "la misma peticion otra vez" de "otra peticion con la clave
reciclada". La primera devuelve el resultado guardado; la segunda es un
conflicto, porque devolverle a alguien el resultado de una peticion que no hizo
es peor que fallar.

## Cual lleva la marca de dato de visitante

`inbox_event` si: su resumen sale de lo que dijo una persona, ya redactado al
**escribirse** y no al leerse (BR6.3). Un evento guardado con texto sin redactar
es un punto de salida sin redaccion aunque nadie lo lea todavia.

`decision_receipt` no: lo que guarda es la huella de una peticion y la referencia
de lo que se escribio, ningun texto de nadie. Se va con su caso por la cascada,
que es lo correcto, pero no es dato de visitante y marcarlo como tal diria algo
que no es.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "u14_inbox_0001_tables"
down_revision: str | None = "u13_chat_0002_disclosed_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: La marca de dato de visitante. Solo `inbox_event` la lleva; ver el docstring.
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
    # --- El aviso de que un caso cambio ---------------------------------------
    op.create_table(
        "inbox_event",
        sa.Column("tenant_id", sa.Text(), primary_key=True),
        # Creciente por aseguradora: es parte de la llave, no una columna suelta.
        sa.Column("event_id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("case_id", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        # Ya redactado al escribirse (BR6.3, M6).
        sa.Column("summary_redacted", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        # La llave compuesta con la aseguradora dentro, como en todo el proyecto:
        # una de una sola columna dejaria a una aseguradora nombrar el caso de
        # otra. Es la leccion que U8 encontro de verdad.
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["case_record.tenant_id", "case_record.case_id"],
            name="inbox_event_del_caso",
            ondelete="CASCADE",
        ),
        # Conjunto cerrado, el mismo que la union de C-06. Un cuarto tipo es un
        # cambio de contrato, no un valor mas.
        sa.CheckConstraint(
            "kind IN ('case_created', 'case_updated', 'case_decided')",
            name="inbox_event_tipo_valido",
        ),
        sa.CheckConstraint("event_id > 0", name="inbox_event_identificador_positivo"),
    )
    # La reanudacion pide "lo posterior a este identificador, en orden": el indice
    # es esa consulta y no una previsión.
    op.execute("CREATE INDEX inbox_event_por_reanudar ON inbox_event (tenant_id, event_id)")
    _aislar(
        "inbox_event",
        "el aviso de que un caso cambio, con su resumen ya redactado",
    )

    # --- El recibo de una escritura idempotente -------------------------------
    op.create_table(
        "decision_receipt",
        sa.Column("receipt_id", sa.Text(), primary_key=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("case_id", sa.Text(), nullable=False),
        # La huella de lo que se pidio: lo que separa la repeticion legitima de
        # la clave reciclada. Ver el docstring.
        sa.Column("request_digest", sa.Text(), nullable=False),
        sa.Column("result_ref", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["case_record.tenant_id", "case_record.case_id"],
            name="decision_receipt_del_caso",
            ondelete="CASCADE",
        ),
        # La promesa de C-05 vive aqui, en la base, y no en el codigo que escribe:
        # dos peticiones a la vez con la misma clave chocan contra esto y una
        # pierde, que es lo que hace que la segunda decision no exista.
        sa.UniqueConstraint(
            "tenant_id",
            "operation",
            "idempotency_key",
            name="decision_receipt_clave_unica",
        ),
        sa.CheckConstraint(
            "operation IN ('decision', 'field_correction')",
            name="decision_receipt_operacion_valida",
        ),
    )
    _aislar(
        "decision_receipt",
        "el recibo de una decision o una correccion idempotente de la bandeja",
        marcar=False,
    )


def downgrade() -> None:
    op.drop_table("decision_receipt")
    op.execute("DROP INDEX IF EXISTS inbox_event_por_reanudar")
    op.drop_table("inbox_event")
