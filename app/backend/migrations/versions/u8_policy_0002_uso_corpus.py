"""u8_policy_0002_uso_corpus: dos cosas que U8 dejo torcidas.

Revision: u8_policy_0002_uso_corpus
Revision anterior: u8_policy_0001_corpus_tables

Las dos salieron de correr la ingesta de verdad y de mirar el esquema despues,
no de ninguna prueba: las dos son invisibles para las compuertas.

## 1. El uso `corpus` no cabia en el libro mayor del gasto

`spend_entry` nacio con `use IN ('voice', 'chat', 'evals', 'operations')`, que
eran los cuatro usos que existian. La tanda 3 de U8 anadio el quinto --`corpus`,
el de los embeddings, con su propia clave-- y no toco esta restriccion, asi que
**cada llamada de embeddings fallaba al anotarse** con `IntegrityError`.

Nadie se entero, y ese es el punto: `_escribir_diferida` traga la excepcion a
proposito, porque una fila del libro mayor que falla no puede tumbar el turno
que la genero. Lo correcto para el turno era exactamente lo que escondia el
fallo. Se vio en la salida de la ingesta real, una linea por cada llamada.

Lo que costaba: el costo por caso de una pregunta de cobertura salia sin sus
filas de embeddings, es decir **por debajo del real**, que es justo lo que el
comentario de `record_non_billable` dice que no puede pasar.

## 2. Una unicidad duplicada, que puse yo

U8 le anadio a `case_transcript_turn` una unicidad sobre `(tenant_id, turn_id)`
para poder apuntarle con llave compuesta... y U10 ya le habia anadido esa misma
unicidad, con otro nombre, en `u10_compliance_0002_tenant_fks`. La tabla acabo
con dos restricciones identicas y dos indices que mantener.

Se quita la mia y se deja la de U10, que es la primera. La llave foranea de
`coverage_answers` no se toca: apunta al par, y el par lo sigue garantizando la
que queda.
"""

from __future__ import annotations

from alembic import op

revision = "u8_policy_0002_uso_corpus"
down_revision = "u8_policy_0001_corpus_tables"
branch_labels = None
depends_on = None

#: Los cinco usos de `base.Use`. Si alguna vez aparece un sexto, esta linea y el
#: enum tienen que moverse juntos, y esta migracion es el recordatorio de que
#: son dos sitios.
USOS = ("voice", "chat", "evals", "operations", "corpus")

#: La que U8 anadio de mas. La de U10 --`case_transcript_turn_aseguradora_y_turno`--
#: se queda.
UNICIDAD_DUPLICADA = "case_transcript_turn_aseguradora_turno"


def upgrade() -> None:
    op.drop_constraint("spend_entry_uso_valido", "spend_entry", type_="check")
    valores = ", ".join(f"'{uso}'" for uso in USOS)
    op.create_check_constraint("spend_entry_uso_valido", "spend_entry", f"use IN ({valores})")

    op.drop_constraint(UNICIDAD_DUPLICADA, "case_transcript_turn", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint(
        UNICIDAD_DUPLICADA, "case_transcript_turn", ["tenant_id", "turn_id"]
    )

    op.drop_constraint("spend_entry_uso_valido", "spend_entry", type_="check")
    anteriores = ", ".join(f"'{uso}'" for uso in USOS if uso != "corpus")
    op.create_check_constraint("spend_entry_uso_valido", "spend_entry", f"use IN ({anteriores})")
