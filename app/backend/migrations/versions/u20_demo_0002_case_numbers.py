"""u20_demo_0002_case_numbers: el libro de numeros de caso ya emitidos.

Revision: u20_demo_0002_case_numbers
Revision anterior: u20_demo_0001_reset_runs

**BR2.5 no se podia cumplir, y por dos razones distintas.**

La primera es que no habia memoria. El numero de caso se acuna al azar en un
espacio de un millon por aseguradora y se comprueba contra **los que existen**;
el reinicio nocturno borra los casos del visitante, asi que a la manana siguiente
todos los numeros de anoche vuelven a estar libres. Un numero repetido hace que
el numero deje de identificar un caso: quien lo anoto y vuelve con el estaria
hablando de otro.

La segunda es que la comprobacion **no podia coincidir**. El repositorio
devolvia la columna entera --`STO-123456`-- y el acunador comparaba el serial
--`123456`--, asi que `serial not in taken` era verdad siempre. Dos formas del
mismo dato, una en cada lado de una frontera, y ninguna prueba las cruzaba: las
del acunador le pasaban seriales a mano y pasaban.

Esta tabla es la memoria, y el cambio que la acompana arregla la comparacion.

## Por que **no** es dato de visitante, dicho con sus limites

No lleva la marca y no tiene purgador, a proposito: si la tuviera, el reinicio se
la llevaria cada noche y BR2.5 volveria a ser imposible.

Lo que guarda es un serial de seis digitos y su aseguradora. No nombra a nadie,
no se puede atar a ninguna persona --el caso que lo llevaba ya no existe-- y no
dice nada de lo que paso. Lo que **si** revela es cuantos casos ha tenido la
demostracion, que es un recuento que el panel publico ya publica.

El compromiso queda escrito aqui porque es el unico sitio donde se puede leer
entero: o un serial sin dueno sobrevive a la noche, o los numeros se repiten. Se
eligio lo primero.

## Aislada como cualquier tabla con aseguradora

Lleva su columna, su aislamiento habilitado y forzado, y su politica: los
seriales de una aseguradora no se ven desde otra. La unicidad es **dentro** de la
aseguradora, que es lo que BR4.3 de U4 dice --dos aseguradoras pueden compartir
serial porque su prefijo las separa-- y lo que la clave primaria compuesta hace
cumplir.

**Se siembra con lo que ya existe.** Los casos vivos en el momento de subir esta
revision ya tienen numero, y sus seriales entran aqui: sin ese sembrado, el libro
nace vacio y el primer numero acunado podria chocar con uno que esta en pantalla.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "u20_demo_0002_case_numbers"
down_revision: str | None = "u20_demo_0001_reset_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "case_number_issued",
        sa.Column("tenant_id", sa.String(32), primary_key=True),
        # Seis digitos, como los acuna U4. Acotado y sin texto libre: aqui no cabe
        # nada que una persona haya dicho.
        sa.Column("serial", sa.String(6), primary_key=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("serial ~ '^[0-9]{6}$'", name="case_number_issued_seis_digitos"),
    )
    op.execute("ALTER TABLE case_number_issued ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE case_number_issued FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON case_number_issued
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
        """
    )
    # **Sin la marca de dato de visitante**, y la razon entera esta en el
    # encabezado: con ella, el reinicio nocturno se llevaria la memoria que esta
    # tabla existe para conservar.
    op.execute(
        "COMMENT ON TABLE case_number_issued IS "
        "'los seriales de numero de caso ya emitidos por cada aseguradora; "
        "sobrevive al reinicio nocturno para que ninguno se repita (BR2.5 de U20)'"
    )

    # Lo que ya existe entra al libro. `split_part` parte `STO-123456` por el
    # guion y se queda con el serial, que es la forma en la que el acunador
    # compara.
    op.execute(
        """
        INSERT INTO case_number_issued (tenant_id, serial, issued_at)
        SELECT tenant_id, split_part(case_number, '-', 2), created_at
        FROM case_record
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    """El orden inverso. Se prueba en cada corrida, no se supone."""
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON case_number_issued")
    op.drop_table("case_number_issued")
