"""u4_case_0003_continues_case: de que caso viene un caso.

Revision: u4_case_0003_continues_case
Revision anterior: u16_voice_0004_end_saved

Cuando la persona cambia de tema en el chat -- consultaba su poliza y dice «quiero reportar
eso como un accidente»-- se abre un caso nuevo y la conversacion pasa a el. La conversacion
solo apunta a un caso, y lo que el modelo ve como historia y lo que la pantalla recupera al
recargar salian del caso nuevo solamente: la agente no sabia que era «eso».

La decision es **guardar de que caso viene cada caso y leer la conversacion a traves de la
cadena**, no copiar turnos: copiarlos duplicaria las respuestas y dejaria sin sus clausulas
las de cobertura, que las encuentra por el caso que las dijo.

**La llave es compuesta con la aseguradora**, como todas las de este esquema desde
`u10_compliance_0002_tenant_fks`: una llave de una sola columna dejaria que una cadena
cruzara de aseguradora, porque el motor comprueba las llaves por encima de las politicas de
fila. Se apoya en el par unico `case_record_aseguradora_y_caso` que esa revision ya dejo.

**Borrar el caso anterior no puede impedirse ni dejar filas colgando.** El reinicio nocturno
y el borrado de los casos de visitantes eliminan casos sin mirar si otro viene de ellos, y
una llave que lo rechazara dejaria la demostracion sin poder limpiarse. Por eso la accion es
`SET NULL (continues_case_id)` y no `SET NULL` a secas: con la aseguradora dentro de la llave,
anular las dos columnas fallaria contra `tenant_id NOT NULL`, y la lista de columnas -- de
PostgreSQL 15 en adelante; la base es 17-- anula solo la que corresponde. El caso que
quedaba despues empieza una cadena nueva: lo unico que se pierde es el enlace, no el caso.

**Admite nulo, y el nulo significa algo**: casi todos los casos no vienen de ninguno. La
comprobacion impide que un caso se continue a si mismo; un ciclo mas largo no puede
formarse, porque el enlace se escribe al crear el caso y apunta siempre a uno anterior.

Sin indice sobre la columna a proposito: la cadena se recorre hacia atras, por la llave
primaria, y el unico recorrido en el otro sentido es el que hace el motor al borrar un caso,
sobre una tabla que el reinicio nocturno mantiene pequena.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "u4_case_0003_continues_case"
down_revision: str | None = "u16_voice_0004_end_saved"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LLAVE = "case_record_continua_a"
SIN_BUCLE = "case_record_no_se_continua_a_si_mismo"


def upgrade() -> None:
    op.execute("ALTER TABLE case_record ADD COLUMN continues_case_id text")
    op.execute(
        f"ALTER TABLE case_record ADD CONSTRAINT {SIN_BUCLE} "
        "CHECK (continues_case_id IS NULL OR continues_case_id <> case_id)"
    )
    op.execute(
        f"ALTER TABLE case_record ADD CONSTRAINT {LLAVE} "
        "FOREIGN KEY (tenant_id, continues_case_id) "
        "REFERENCES case_record (tenant_id, case_id) "
        "ON DELETE SET NULL (continues_case_id)"
    )


def downgrade() -> None:
    """Quita el enlace y la columna. Los casos no se tocan: solo dejan de saber de donde vienen.

    `mise run migrate:check` sube, baja y vuelve a subir contra una base virgen.
    """
    op.execute(f"ALTER TABLE case_record DROP CONSTRAINT {LLAVE}")
    op.execute(f"ALTER TABLE case_record DROP CONSTRAINT {SIN_BUCLE}")
    op.execute("ALTER TABLE case_record DROP COLUMN continues_case_id")
