"""u11_intake_0002_alt_version: una clase de entrada para la version que no se acepto.

Revision: u11_intake_0002_alt_version
Revision anterior: u11_intake_0001_reporter_party

## Por que

BR5.5 y FD-U11-7 dicen que el valor del caso es **el primero confirmado** y que
una version que lo contradice se anota aparte. La tanda 2 la anotaba con
`change_kind = 'field_set'`, que en el historial significa "el campo se fijo a
este valor" -- exactamente lo contrario de lo que paso. Quien leyera la linea de
tiempo del caso veria el segundo valor como el vigente.

Es el mismo argumento con el que `u4_case_0001_case_tables` justifico
`transition_rejected` y `close_rejected`: "un rechazo que no deja rastro es
indistinguible de un intento que nadie hizo". Leido al reves, una version que no
se acepto y se anota como aceptada es indistinguible de un cambio real.

## Las dos restricciones que se amplian

1. **`case_change_clase_valida`**: un quinto valor, `field_version_alternate`.
2. **`case_change_campo_con_su_clave`**: la clase nueva **tambien** nombra su
   campo. Una version alterna sin campo no diria de que dato es.

Ninguna fila existente cambia: no hay ninguna con la clase nueva todavia.

## Reversible

`downgrade` vuelve a poner las dos restricciones con el texto exacto de
`u4_case_0001_case_tables`. Baja **solo si no queda ninguna fila** con la clase
nueva -- si queda, la restriccion de vuelta la rechazaria a mitad de la
migracion y dejaria la base a medias; asi falla antes, diciendo cuantas hay.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "u11_intake_0002_alt_version"
down_revision: str | None = "u11_intake_0001_reporter_party"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLA = "case_change"
CLASE = "case_change_clase_valida"
CAMPO = "case_change_campo_con_su_clave"

#: Las dos versiones de cada restriccion, escritas una vez para que `upgrade` y
#: `downgrade` no puedan divergir. Las "de antes" son, caracter a caracter, las
#: de `u4_case_0001_case_tables`.
CLASE_ANTES = (
    "change_kind IN ('field_set', 'transition_applied', 'transition_rejected', 'close_rejected')"
)
CLASE_AHORA = (
    "change_kind IN ('field_set', 'field_version_alternate', 'transition_applied', "
    "'transition_rejected', 'close_rejected')"
)
CAMPO_ANTES = "change_kind <> 'field_set' OR field_key IS NOT NULL"
CAMPO_AHORA = "change_kind NOT IN ('field_set', 'field_version_alternate') OR field_key IS NOT NULL"


def upgrade() -> None:
    op.drop_constraint(CLASE, TABLA, type_="check")
    op.create_check_constraint(CLASE, TABLA, CLASE_AHORA)
    op.drop_constraint(CAMPO, TABLA, type_="check")
    op.create_check_constraint(CAMPO, TABLA, CAMPO_AHORA)


def downgrade() -> None:
    """El orden inverso, y se niega a borrar historial para poder bajar."""
    conexion = op.get_bind()
    quedan = conexion.execute(
        sa.text("SELECT count(*) FROM case_change WHERE change_kind = 'field_version_alternate'")
    ).scalar_one()
    if quedan:
        msg = (
            f"quedan {quedan} entrada(s) 'field_version_alternate' en el historial. "
            "Bajar esta revision las dejaria fuera de la restriccion, y el historial "
            "es de solo anexar (SEC-U4.11): no se borran para poder bajar"
        )
        raise RuntimeError(msg)
    op.drop_constraint(CAMPO, TABLA, type_="check")
    op.create_check_constraint(CAMPO, TABLA, CAMPO_ANTES)
    op.drop_constraint(CLASE, TABLA, type_="check")
    op.create_check_constraint(CLASE, TABLA, CLASE_ANTES)
