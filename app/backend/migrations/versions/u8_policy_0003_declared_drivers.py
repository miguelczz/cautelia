"""u8_policy_0003_declared_drivers: los conductores que declara una poliza emitida.

Revision: u8_policy_0003_declared_drivers
Revision anterior: u14_inbox_0002_triage_note

## Por que existe

El sexto campo de los que leen las reglas de triage, `unlisted_driver` ("el conductor del
siniestro no figura en la poliza"), no tenia con que compararse: la poliza emitida solo
guardaba al titular. Esta columna guarda los conductores que la poliza declara, el titular
primero, para que la derivacion los lea de la poliza del caso.

## Una columna con valor por omision, y el vacio significa algo

`drivers` es un arreglo JSON de `{"full_name": ...}`, `NOT NULL DEFAULT '[]'`. **Vacio es "la
poliza no declara conductores"**, no "no tiene ninguno": es lo que traen las filas ya
ingeridas, y quien compara a un conductor con la lista lee el vacio como "no se sabe" y deja el
insumo ausente, que es la salida segura (un insumo ausente no dispara, BR2.1 de U9). La
columna llega con su valor por omision para que la migracion no necesite tocar ninguna fila y
el codigo anterior siga leyendo la tabla igual.

Las filas ya ingeridas no se actualizan solas: `mise run corpus:ingest` vuelve a escribir cada
poliza por su llave natural (`ON CONFLICT (tenant_id, policy_number) DO UPDATE`) y con ella sus
conductores. No toca ninguna clausula ni vuelve a llamar al proveedor de embeddings, porque el
`content_hash` de cada clausula no cambio.

## Por que no dentro de `named_insured`

`named_insured` es la persona asegurada (`PersonaRef`) y `find_policy_by_national_id` filtra
sobre su `national_id`. Meter ahi una lista de otras personas habria mezclado dos cosas con
dos duenos y obligado a quien lee al titular a saber que hay mas dentro.

## Aditiva y reversible

No cambia ninguna columna existente, asi que el codigo anterior sigue funcionando con ella
(la vuelta atras del despliegue no baja migraciones). `downgrade` quita la columna y la
restriccion; los conductores se vuelven a escribir al reingerir.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "u8_policy_0003_declared_drivers"
down_revision: str | None = "u14_inbox_0002_triage_note"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Que sea un arreglo es lo unico que la base impone; el contenido lo valida el modelo de
#: `policy_rag.corpus`, igual que `endorsement_ids`.
RESTRICCION = "issued_policies_conductores_son_lista"


def upgrade() -> None:
    op.add_column(
        "issued_policies",
        sa.Column(
            "drivers",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.create_check_constraint(RESTRICCION, "issued_policies", "jsonb_typeof(drivers) = 'array'")


def downgrade() -> None:
    op.drop_constraint(RESTRICCION, "issued_policies", type_="check")
    op.drop_column("issued_policies", "drivers")
