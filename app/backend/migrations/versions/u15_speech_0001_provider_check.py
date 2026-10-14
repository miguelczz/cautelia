"""u15_speech_0001_provider_check: el libro mayor deja de aceptar `fallback_tts`.

Revision: u15_speech_0001_provider_check
Revision anterior: u10_compliance_0002_tenant_fks

## Por que

La revision `u5_platform_0001_spend_tables` enumero en
`spend_entry_proveedor_valido` los cuatro valores que tenia entonces
`ProviderName`, y uno de ellos, `fallback_tts`, era un lugar reservado: U5 no
sabia todavia quien daria la voz de respaldo. La enmienda del 2026-09-21 de
ADR-008 se la dio a **Deepgram** (Aura-2), y el adaptador de U15 registra su
gasto con ese proveedor y el modelo `aura-2`. Desde entonces `fallback_tts` no
describe nada construido: ningun adaptador lo escribe y ninguna fila de precio
lo nombra. Dejarlo aceptado en la base es dejar abierta una puerta a una fila de
gasto que ninguna tabla de precios sabe valorar.

## Lo que comprueba antes de cambiar nada

Que **ninguna fila** lo use. Si alguna lo usara, la revision **se detiene** y no
toca el libro mayor: una fila de gasto no se borra ni se reescribe para que una
migracion pase, porque es la fuente de una cifra publicada (BR3.1). Lo que habria
que hacer entonces es decidir a quien atribuir esa fila, y esa es una decision de
una persona, no de una revision.

## Reversible

`downgrade` vuelve a poner la restriccion con los cuatro valores, con el mismo
texto que escribio `u5_platform_0001`. `mise run migrate:check` sube, baja y
vuelve a subir contra una base virgen en cada corrida del guion.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "u15_speech_0001_provider_check"
down_revision: str | None = "u10_compliance_0002_tenant_fks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RESTRICCION = "spend_entry_proveedor_valido"
TABLA = "spend_entry"
RETIRADO = "fallback_tts"

#: Las dos versiones de la restriccion, escritas una vez para que `upgrade` y
#: `downgrade` no puedan divergir. La de antes es, caracter a caracter, la de
#: `u5_platform_0001_spend_tables`.
PROVEEDORES_ANTES = "provider IN ('gemini', 'deepgram', 'cartesia', 'fallback_tts')"
PROVEEDORES_AHORA = "provider IN ('gemini', 'deepgram', 'cartesia')"

_FILAS_CON_EL_RETIRADO = sa.text("SELECT count(*) FROM spend_entry WHERE provider = :retirado")


class RetiredProviderInUseError(RuntimeError):
    """Hay filas de gasto con el proveedor que se retira: la revision no sigue."""


def upgrade() -> None:
    filas = op.get_bind().execute(_FILAS_CON_EL_RETIRADO, {"retirado": RETIRADO}).scalar_one()
    if filas:
        msg = (
            f"{filas} fila(s) de '{TABLA}' usan el proveedor '{RETIRADO}', que se retira. "
            "La revision no borra ni reescribe el libro mayor: decida a que proveedor "
            "atribuirlas y vuelva a correrla"
        )
        raise RetiredProviderInUseError(msg)
    op.drop_constraint(RESTRICCION, TABLA, type_="check")
    op.create_check_constraint(RESTRICCION, TABLA, PROVEEDORES_AHORA)


def downgrade() -> None:
    op.drop_constraint(RESTRICCION, TABLA, type_="check")
    op.create_check_constraint(RESTRICCION, TABLA, PROVEEDORES_ANTES)
