"""u5_platform_0004_adjustment: el libro mayor admite un asiento de ajuste.

Revision: u5_platform_0004_adjustment
Revision anterior: u8_policy_0003_declared_drivers

El 2026-10-13 la consola de Anthropic mostraba 0,96 USD del mes y los libros del
proyecto y de produccion sumaban unos 0,71: lo que faltaba (unos 0,24 USD) eran
corridas de `mise run evals:entender` que escribieron su gasto en una base
desechable. El gasto fue real y no quedo en ningun libro; el techo tampoco lo vio.
Los comandos ya escriben directo en la base del proyecto, y esta revision da donde
anotar lo que ya paso: un **asiento de ajuste conciliado**.

Un ajuste no es una llamada y no se parece a una. No tiene unidades, ni modelo que
las haya contado, ni precio de lista: tiene un importe que dijo la consola del
proveedor y una nota de donde salio la cifra. Por eso esta revision toca cuatro
cosas, y las cuatro solo para el origen nuevo:

1. **`source` admite `reconciled_adjustment`.** Un valor mas en el conjunto cerrado.
2. **`note`, una columna de texto acotada a 200.** Es la unica columna de texto del
   libro y la unica cuya redaccion no es de un adaptador: la escribe quien opera el
   proyecto. Una restriccion la ata al origen nuevo, en las dos direcciones: un
   ajuste siempre lleva nota y ninguna otra fila puede llevarla, para que el libro
   no se vuelva un lugar donde cabe una frase (BR7.2).
3. **Las cuatro columnas de precio dejan de ir juntas, solo para un ajuste.** La
   regla de BR3.4 --precio, lista, fecha y costo, todas o ninguna-- existe para que
   una cifra se pueda reproducir desde la lista que la valoro. Un ajuste no salio
   de ninguna lista, y llenar tres columnas con valores inventados para que la
   restriccion pase seria afirmar un precio que nadie fijo. Lleva solo `cost_usd`.
4. **Un ajuste esta medido y no cuenta unidades.** Lo dice una restriccion, para
   que una fila de este origen no pueda ser "no medida" ni traer un recuento.

Solo amplia lo aceptado. `downgrade` se detiene si ya hay un ajuste, porque una
fila de gasto no se borra para que una migracion baje (BR3.1).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "u5_platform_0004_adjustment"
down_revision: str | None = "u8_policy_0003_declared_drivers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLA = "spend_entry"
ORIGEN = "spend_entry_origen_valido"
PRECIO = "spend_entry_precio_completo_o_ausente"
AJUSTE = "spend_entry_ajuste_con_su_importe"
NOTA = "spend_entry_nota_solo_en_ajustes"

#: Cuanto cabe en la nota. Acotada porque una tabla excluida del aislamiento no
#: admite texto sin tope (BR7.2).
LARGO_DE_LA_NOTA = 200

ORIGEN_ANTES = "source IN ('provider_reported', 'counted_locally')"
ORIGEN_AHORA = "source IN ('provider_reported', 'counted_locally', 'reconciled_adjustment')"

#: Las cuatro columnas de precio, todas o ninguna, segun el estado del costo.
PRECIO_ANTES = (
    "num_nonnulls(unit_price_usd, price_list_version, price_list_effective_date, "
    "cost_usd) = CASE WHEN cost_status = 'measured' THEN 4 ELSE 0 END"
)
#: Igual, salvo que un ajuste lleva exactamente una: el importe. Que esa una sea
#: `cost_usd` lo dice `AJUSTE_AHORA`.
PRECIO_AHORA = (
    "num_nonnulls(unit_price_usd, price_list_version, price_list_effective_date, "
    "cost_usd) = CASE WHEN source = 'reconciled_adjustment' THEN 1 "
    "WHEN cost_status = 'measured' THEN 4 ELSE 0 END"
)

AJUSTE_AHORA = (
    "source <> 'reconciled_adjustment' "
    "OR (cost_status = 'measured' AND cost_usd IS NOT NULL AND units = 0)"
)
NOTA_AHORA = "(source = 'reconciled_adjustment') = (note IS NOT NULL)"

_AJUSTES = sa.text("SELECT count(*) FROM spend_entry WHERE source = 'reconciled_adjustment'")


class AdjustmentsInLedgerError(RuntimeError):
    """Hay asientos de ajuste y la bajada los dejaria sin lugar donde existir."""


def upgrade() -> None:
    op.add_column(TABLA, sa.Column("note", sa.String(LARGO_DE_LA_NOTA), nullable=True))
    op.drop_constraint(ORIGEN, TABLA, type_="check")
    op.create_check_constraint(ORIGEN, TABLA, ORIGEN_AHORA)
    op.drop_constraint(PRECIO, TABLA, type_="check")
    op.create_check_constraint(PRECIO, TABLA, PRECIO_AHORA)
    op.create_check_constraint(AJUSTE, TABLA, AJUSTE_AHORA)
    op.create_check_constraint(NOTA, TABLA, NOTA_AHORA)


def downgrade() -> None:
    ajustes = op.get_bind().execute(_AJUSTES).scalar_one()
    if ajustes:
        msg = (
            f"{ajustes} fila(s) de '{TABLA}' son asientos de ajuste conciliado. La revision "
            "no borra el libro mayor: decida que hacer con ellas y vuelva a correrla"
        )
        raise AdjustmentsInLedgerError(msg)
    op.drop_constraint(NOTA, TABLA, type_="check")
    op.drop_constraint(AJUSTE, TABLA, type_="check")
    op.drop_constraint(PRECIO, TABLA, type_="check")
    op.create_check_constraint(PRECIO, TABLA, PRECIO_ANTES)
    op.drop_constraint(ORIGEN, TABLA, type_="check")
    op.create_check_constraint(ORIGEN, TABLA, ORIGEN_ANTES)
    op.drop_column(TABLA, "note")
