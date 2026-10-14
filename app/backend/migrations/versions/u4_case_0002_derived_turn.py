"""u4_case_0002_derived_turn: en que turno se derivo el caso.

Revision: u4_case_0002_derived_turn
Revision anterior: u20_demo_0002_case_numbers

**La revision de cumplimiento no se puede acotar sin este dato.** Uno de sus
cuatro controles es que toda peticion de persona se derive en el turno siguiente
(BR5.1 de U10), y para eso necesita saber **en que turno** salio la frase de
derivacion. El caso sabia que se derivo y por que; no sabia cuando en la
conversacion.

Las dos formas de adivinarlo son peores que no revisar, y por eso esta columna
existe en vez de una heuristica: con el ultimo turno, la revision **absolveria**
una derivacion que llego tarde; sin nada, **acusaria** de no haber derivado a un
caso que si se derivo. Un hallazgo falso en una compuerta de cumplimiento es peor
que una compuerta que declara no haber corrido.

**Por que vive en el caso y no en la pausa.** La pausa se resuelve cuando la
decision aterriza, y no toda derivacion abre una: el dato tiene que sobrevivir a
la pausa y lo leen dos consumidores --la revision y quien audite el caso--. Va
donde ya vive el motivo de la derivacion, y lo escribe la misma transicion, que
es la puerta unica por la que pasa toda derivacion.

**Admite nulo, y el nulo significa algo.** Hay derivaciones que no ocurren en un
turno de la conversacion: el boton de pasar a una persona de la consola de voz, y
la que decide una persona en la bandeja. Ahi no hay frase que acotar, y la
revision lo trata como lo que es --no hay turno de derivacion-- en vez de
inventar uno.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "u4_case_0002_derived_turn"
down_revision: str | None = "u20_demo_0002_case_numbers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Sin clave foranea hacia el turno a proposito: la transcripcion se borra con
    # el caso por cascada, asi que una foranea no anadiria ninguna garantia que la
    # cascada no tenga ya, y obligaria a ordenar las dos escrituras del mismo
    # turno. Lo que si hay es la comprobacion de la revision, que falla si el
    # turno que se le pide acotar no esta en la transcripcion.
    op.add_column("case_record", sa.Column("derived_turn_id", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("case_record", "derived_turn_id")
