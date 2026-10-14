"""u5_platform_0002_call_release: la llamada en el libro mayor y su cierre.

Revision: u5_platform_0002_call_release
Revision anterior: u5_platform_0001_spend_tables

Lo que falta para que BR5.5 se pueda cumplir, que son dos cosas y no una.

**1. El libro mayor no sabia de que llamada era cada fila.** F4 le pregunta al
registro de gasto si **esa sesion** dejo alguna fila de audio con unidades
mayores que cero, y el registro no podia responder esa pregunta: `case_ref` no
alcanza, porque un caso puede tener mas de una llamada y la fila de un dia
anterior contestaria por la de hoy --y contestaria "si", que es la direccion que
le quita el dia al visitante--. `call_ref` es el identificador que C-17 ya nombra
en `reserve_primary_voice(call_id)`: no es un dato inventado, es el que hasta
ahora no se guardaba. Va **sin clave foranea**, porque la tabla de la llamada es
de U16 y todavia no existe; y aunque existiera, un gasto que desapareciera con su
llamada tendria el mismo problema que BR7.5 resuelve para el caso.

**2. Devolver el cupo dos veces regala un cupo.** U16 cierra la sesion "siempre,
tambien cuando la llamada se cae" (`functional-spec.md` §7), asi que el doble
cierre es el caso normal y no el raro. La guarda `count > 0` basta para el
contador del visitante cuando su limite es uno, pero **no** para el del sitio,
cuyo conteo es grande: sin marca, el segundo cierre le devolveria al sitio un
cupo que si se gasto. `voice_call_release` es esa marca, una fila por llamada, y
su clave primaria es lo que hace idempotente la operacion: el segundo cierre
choca con ella y no hace nada.

**Por que es una cuarta tabla excluida del aislamiento, y no una tercera.**
BR7.1 nombra tres tablas del dinero y las cuotas; esta es la cuarta y la
desviacion se declara aqui en vez de heredarse. Es dato del proyecto por la misma
razon que las otras tres --el cupo del sitio no es de ninguna aseguradora, y el
del visitante se cuenta por navegador-- y entra en `[tool.untangle.rls] excluded`
con su razon escrita. Paga lo que BR7.2 cobra: sus tres columnas son un
identificador acotado, un booleano y una marca de tiempo, y ninguna de las tres
coincide con la lista versionada de nombres de dato personal.

**Lo que a proposito NO guarda.** Ni el sujeto de la cuota ni el periodo. La
marca solo tiene que poder decir "esta llamada ya se cerro"; guardar de quien era
seria guardar un dato de visitante para responder una pregunta que no lo
necesita. El reinicio nocturno se lleva estas filas igual que se lleva los
contadores del visitante (BR7.6): una marca que nadie va a volver a consultar no
tiene por que sobrevivir a la noche.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "u5_platform_0002_call_release"
down_revision: str | None = "u5_platform_0001_spend_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- La llamada, en el libro mayor ----------------------------------------
    # Acotada como todo el texto de una tabla excluida del aislamiento: una
    # columna sin tope es donde un dia cabe una frase, y estaria en la unica
    # tabla del aplicativo que nadie filtra por aseguradora (BR7.2).
    op.add_column("spend_entry", sa.Column("call_ref", sa.String(64), nullable=True))
    # El indice es de la consulta de BR5.5, que corre al cerrar **cada** llamada:
    # sin el, preguntar si una sesion dejo audio recorreria el libro mayor
    # entero, y ese libro crece con cada llamada a cada proveedor.
    op.create_index("spend_entry_por_llamada", "spend_entry", ["call_ref", "unit_kind"])

    # --- La marca del cierre --------------------------------------------------
    op.create_table(
        "voice_call_release",
        # La llamada. Es la clave primaria y es **todo** el mecanismo de
        # idempotencia: el segundo cierre de la misma llamada choca contra ella.
        sa.Column("call_ref", sa.String(64), primary_key=True),
        # Que se decidio. Se guarda aunque el segundo cierre no lo use para nada:
        # una marca que solo dijera "ya se cerro" no dejaria ver, el dia que las
        # cifras no cuadren, cuantas llamadas devolvieron su cupo.
        sa.Column("released", sa.Boolean(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute(
        "COMMENT ON TABLE voice_call_release IS "
        "'dato del proyecto: una fila por llamada cerrada, para que devolver el "
        "cupo dos veces no devuelva dos cupos (BR5.5, BR7.1)'"
    )


def downgrade() -> None:
    """El orden inverso. Se prueba en cada corrida, no se supone."""
    op.drop_table("voice_call_release")
    op.drop_index("spend_entry_por_llamada", table_name="spend_entry")
    op.drop_column("spend_entry", "call_ref")
