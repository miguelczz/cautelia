"""u20_demo_0003_short_numbers: el numero de caso pasa a `AP-29`.

Revision: u20_demo_0003_short_numbers
Revision anterior: u5_platform_0004_adjustment

Miguel pidio el 2026-10-30 un numero que se pueda decir y recordar: las dos
iniciales de la empresa y un contador por aseguradora (`SA-1`, `AP-29`, `AC-7`), en
vez de tres letras y seis digitos al azar (`SUN-063911`). El codigo ya acuna la forma
nueva; esta revision pone la base de acuerdo con el, en cuatro pasos:

1. **Las dos restricciones de forma se reemplazan**: la de `case_record.case_number`
   (`^[A-Z]{2}-[1-9][0-9]{0,5}$`) y la de `case_number_issued.serial`
   (`^[1-9][0-9]{0,5}$`). Se sueltan antes de tocar las filas y se vuelven a poner al
   final, para que ninguna fila pase por una forma que la restriccion vigente rechace.
2. **Cada caso existente se renumera**, por aseguradora, en el orden `created_at,
   case_id`: `<prefijo nuevo>-<numero de fila>`. El prefijo nuevo sale de la
   configuracion de la aseguradora (`untangle.tenancy.config`); una aseguradora que ya
   no esta en la configuracion conserva las dos primeras letras de su prefijo anterior,
   que es lo unico que se puede decir de ella sin inventar. El numero viejo que la
   agente haya dicho dentro de la transcripcion del caso se reemplaza por el nuevo.
3. **El libro de emitidos se reconstruye** con los seriales ya renumerados. Los viejos
   no sirven: tienen ceros a la izquierda y no caben en la forma nueva.
4. **Las filas se leen y se escriben con el aislamiento puesto**: las tablas llevan el
   aislamiento forzado, asi que sin fijar `app.tenant_id` antes de cada aseguradora la
   consulta no ve ninguna fila y la revision "termina" sin haber renumerado nada.

## Esto rompe BR4.3 una vez, a proposito

BR4.3 dice que el numero de un caso no cambia nunca, porque cambiarlo deja sin forma
de volver a quien lo anoto. Esta revision lo cambia, una sola vez y por decision de
Miguel del 2026-10-30. Quien tenga anotado un numero viejo no podra retomar su caso por
el con la forma nueva; el acceso del navegador y el enlace firmado no dependen del
numero y siguen valiendo.

Por eso conviene desplegarla **justo despues del reinicio nocturno**: los casos de los
visitantes ya se borraron y casi no queda nada que renumerar ni nadie con un numero
anotado. Los casos que si existen despues del reinicio son los de ejemplo.

## Bajar

`downgrade` devuelve la forma de seis digitos rellenando con ceros a la izquierda, y
al prefijo de dos letras le anade una `X` para volver a tener tres: el prefijo de tres
letras original no se puede recuperar. Los casos nuevos no se pueden devolver a su
numero al azar; se devuelve solo lo que la forma exige.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from untangle.tenancy import config

revision: str = "u20_demo_0003_short_numbers"
down_revision: str | None = "u5_platform_0004_adjustment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FORMA_NUEVA_CASO = "case_number ~ '^[A-Z]{2}-[1-9][0-9]{0,5}$'"
_FORMA_VIEJA_CASO = "case_number ~ '^[A-Z]{3}-[0-9]{6}$'"
_FORMA_NUEVA_SERIAL = "serial ~ '^[1-9][0-9]{0,5}$'"
_FORMA_VIEJA_SERIAL = "serial ~ '^[0-9]{6}$'"


def _fijar_aseguradora(conexion: sa.Connection, tenant_id: str) -> None:
    conexion.execute(sa.text("SELECT set_config('app.tenant_id', :t, true)"), {"t": tenant_id})


def _prefijos_nuevos() -> dict[str, str]:
    return {t.tenant_id: t.case_number_prefix for t in config.load().available}


def upgrade() -> None:
    op.drop_constraint("case_record_numero_con_forma", "case_record", type_="check")
    op.drop_constraint("case_number_issued_seis_digitos", "case_number_issued", type_="check")

    conexion = op.get_bind()
    nuevos = _prefijos_nuevos()
    # Hace falta mirar el libro ademas de los casos: una aseguradora sin casos vivos
    # puede tener seriales emitidos, y esos tambien tienen que salir antes de la forma
    # nueva.
    aseguradoras: list[str] = []
    for tabla in ("case_record", "case_number_issued"):
        # Sin aislamiento puesto, con el aislamiento forzado esto no ve ninguna fila si
        # el rol no es superusuario: por eso la lista sale de la configuracion tambien.
        for fila in conexion.execute(sa.text(f"SELECT DISTINCT tenant_id FROM {tabla}")):  # noqa: S608 -- tupla fija
            aseguradoras.append(fila[0])
    aseguradoras = sorted({*aseguradoras, *nuevos})

    for tenant_id in aseguradoras:
        _fijar_aseguradora(conexion, tenant_id)
        viejo = conexion.execute(
            sa.text("SELECT substr(case_number, 1, 2) FROM case_record ORDER BY created_at LIMIT 1")
        ).scalar()
        prefijo = nuevos.get(tenant_id) or viejo
        if prefijo is not None:
            conexion.execute(
                sa.text(
                    """
                    CREATE TEMPORARY TABLE _renumeracion ON COMMIT DROP AS
                    SELECT case_id,
                           case_number AS viejo,
                           :prefijo || '-' || (row_number() OVER (ORDER BY created_at, case_id))::text
                               AS nuevo
                    FROM case_record
                    """
                ),
                {"prefijo": prefijo},
            )
            conexion.execute(
                sa.text(
                    """
                    UPDATE case_transcript_turn AS t
                    SET text_redacted = replace(t.text_redacted, r.viejo, r.nuevo)
                    FROM _renumeracion AS r
                    WHERE t.case_id = r.case_id AND position(r.viejo IN t.text_redacted) > 0
                    """
                )
            )
            conexion.execute(
                sa.text(
                    """
                    UPDATE case_record AS c SET case_number = r.nuevo
                    FROM _renumeracion AS r WHERE c.case_id = r.case_id
                    """
                )
            )
            conexion.execute(sa.text("DROP TABLE _renumeracion"))
        conexion.execute(sa.text("DELETE FROM case_number_issued"))
        conexion.execute(
            sa.text(
                """
                INSERT INTO case_number_issued (tenant_id, serial, issued_at)
                SELECT tenant_id, split_part(case_number, '-', 2), created_at FROM case_record
                ON CONFLICT DO NOTHING
                """
            )
        )

    conexion.execute(sa.text("SELECT set_config('app.tenant_id', '', true)"))
    op.create_check_constraint("case_record_numero_con_forma", "case_record", _FORMA_NUEVA_CASO)
    op.create_check_constraint(
        "case_number_issued_seis_digitos", "case_number_issued", _FORMA_NUEVA_SERIAL
    )


def downgrade() -> None:
    """Devuelve la forma de seis digitos. Se prueba en cada corrida, no se supone."""
    op.drop_constraint("case_record_numero_con_forma", "case_record", type_="check")
    op.drop_constraint("case_number_issued_seis_digitos", "case_number_issued", type_="check")

    conexion = op.get_bind()
    aseguradoras: set[str] = set(_prefijos_nuevos())
    for tabla in ("case_record", "case_number_issued"):
        for fila in conexion.execute(sa.text(f"SELECT DISTINCT tenant_id FROM {tabla}")):  # noqa: S608 -- tupla fija
            aseguradoras.add(fila[0])

    for tenant_id in sorted(aseguradoras):
        _fijar_aseguradora(conexion, tenant_id)
        conexion.execute(
            sa.text(
                """
                UPDATE case_record
                SET case_number = split_part(case_number, '-', 1) || 'X-'
                    || lpad(split_part(case_number, '-', 2), 6, '0')
                """
            )
        )
        conexion.execute(sa.text("UPDATE case_number_issued SET serial = lpad(serial, 6, '0')"))

    conexion.execute(sa.text("SELECT set_config('app.tenant_id', '', true)"))
    op.create_check_constraint("case_record_numero_con_forma", "case_record", _FORMA_VIEJA_CASO)
    op.create_check_constraint(
        "case_number_issued_seis_digitos", "case_number_issued", _FORMA_VIEJA_SERIAL
    )
