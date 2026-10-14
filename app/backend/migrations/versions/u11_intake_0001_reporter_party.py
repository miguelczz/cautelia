"""u11_intake_0001_reporter_party: un quinto rol para quien reporta, y su relacion.

Revision: u11_intake_0001_reporter_party
Revision anterior: u8_policy_0002_uso_corpus

## Por que

FD-U11-5 decia que U11 no podia crear "ninguna entidad ni migracion", y esa
version dejaba AC1.4.1 sin donde aterrizar: el criterio pide registrar a quien
reporta por otro **con su relacion con el asegurado**, y `case_party` no tenia
ni un rol que significara "quien reporta" ni una columna para la relacion. La
correccion del 2026-09-27 (revision de la tanda 1, `entities.md`,
`functional-spec.md`) dice que U11 no crea entidades nuevas, pero si puede
**ampliar las de U4 de forma aditiva** cuando un criterio aprobado lo exige.
Esta revision es esa ampliacion, y nada mas: ninguna fila existente cambia y
ninguna operacion cambia de firma.

## Las dos columnas

1. **Un quinto valor en `case_party_rol_valido`**: `reporter`. Antes de esta
   revision, quien reportaba por otro se registraba con `witness` -- un apano
   documentado en `identity.py` -- porque no existia un rol que dijera lo que
   de verdad era. `reporter` no es sinonimo de `witness`: un testigo puede no
   haber visto nada y un reportante puede ser el propio lesionado hablando por
   quien no puede.
2. **`relation`, columna de texto, anulable.** La relacion con el asegurado es
   texto que dicta la persona ("vecino", "hijo del asegurado"), y por eso pasa
   por el punto unico de redaccion de U3 antes de persistirse (M6, el mismo
   principio de BR4.3 en U8) -- **no** se cifra: sigue el precedente de
   `injury_status` y `vehicle_description`, las otras dos columnas de texto
   libre de esta tabla que tampoco entran en `case_party_clave_con_valor`. Una
   relacion ya redactada no necesita ademas un cifrado que solo protegeria un
   texto del que los datos personales ya se quitaron.

## Lo que NO toca

`case_party_clave_con_valor` sigue comparando solo `name`, `contact` y `plate`:
esos tres son los que se cifran, y `relation` se une a `injury_status` y
`vehicle_description` en el lado de fuera de esa cuenta.

## Reversible

`downgrade` vuelve a poner la restriccion con los cuatro valores de antes, con
el mismo texto que escribio `u4_case_0001_case_tables`, y quita la columna.
`mise run migrate:check` sube, baja y vuelve a subir contra una base virgen en
cada corrida del guion.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "u11_intake_0001_reporter_party"
down_revision: str | None = "u8_policy_0002_uso_corpus"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RESTRICCION = "case_party_rol_valido"
TABLA = "case_party"

#: Las dos versiones de la restriccion, escritas una vez para que `upgrade` y
#: `downgrade` no puedan divergir. La de antes es, caracter a caracter, la de
#: `u4_case_0001_case_tables`.
ROLES_ANTES = "role IN ('injured', 'witness', 'other_driver', 'other_vehicle')"
ROLES_AHORA = "role IN ('injured', 'witness', 'other_driver', 'other_vehicle', 'reporter')"


def upgrade() -> None:
    op.drop_constraint(RESTRICCION, TABLA, type_="check")
    op.create_check_constraint(RESTRICCION, TABLA, ROLES_AHORA)
    op.add_column(TABLA, sa.Column("relation", sa.Text(), nullable=True))


def downgrade() -> None:
    """El orden inverso. Se prueba en cada corrida, no se supone."""
    op.drop_column(TABLA, "relation")
    op.drop_constraint(RESTRICCION, TABLA, type_="check")
    op.create_check_constraint(RESTRICCION, TABLA, ROLES_ANTES)
