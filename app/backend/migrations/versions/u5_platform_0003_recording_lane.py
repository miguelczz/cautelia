"""u5_platform_0003_recording_lane: el carril de grabacion, entero.

Revision: u5_platform_0003_recording_lane
Revision anterior: u5_platform_0002_call_release

La revision `0001` dejo el carril de grabacion a medias, y los dos huecos que
quedaban son la misma clase de fallo silencioso: una cifra que se publica sin
que nada diga que esta mal. Esta revision los cierra.

**1. Una llamada de grabacion no podia registrar su exceso.** La restriccion
`budget_window_grabacion_dentro_de_su_reserva` exigia
`recording_spent_usd <= COALESCE(recording_reserve_usd, 0)`, asi que con la
reserva agotada la fila de gasto **no se escribia**: la sentencia levantaba y la
transaccion entera se iba con ella. Eso enfrenta dos reglas aprobadas y manda
BR3.1:

- **BR4.5** acepta explicitamente el exceso --"el exceso posible es a lo sumo el
  de la llamada al proveedor que estaba en vuelo"--, porque el techo se consulta
  **antes** de llamar y el costo se registra **despues**.
- **BR3.1** exige que toda llamada deje su fila de gasto, sin excepcion,
  incluida la que fallo y la que no se pudo valorar.

Manda BR3.1 porque los dos errores no cuestan lo mismo: una fila de gasto
perdida falsea una cifra publicada y **no deja rastro de que falta**, mientras
que un restante que llega a cero y se queda ahi no falsea nada --el restante ya
se informa con piso en cero (`budget.recording_remaining`)--. O sea: el gasto
acumulado de un carril puede superar su reserva, y el **restante** es el que
nunca baja de cero.

Lo que **no** se quita, porque sigue siendo cierto: la reserva no puede ser
mayor que el techo (apartar mas de lo que hay dejaria el carril publico cerrado
desde el primer dia) y lo gastado en grabacion sigue estando **incluido** en el
acumulado facturable.

**2. El conteo de llamadas sin valorar no distinguia carril.** La fila contaba
cuantas llamadas facturables no se pudieron valorar, pero no de que carril
salieron. Por eso el corte por lo no valorado --la decision del 2026-09-21-- solo
podia alcanzar al carril publico: cerrar tambien la grabacion por una llamada que
pudo venir del enlace publico gastaria la reserva del video de la semana doce sin
que nadie la hubiera gastado (BR4.10). La consecuencia de que el conteo no
existiera es simetrica y tan fea como la que ya se arreglo: **una llamada de
grabacion sin valorar infla el restante de su carril sin que nada lo diga**.

`unmeasured_recording_calls` es al conteo lo que `recording_spent_usd` es al
acumulado: la parte del total que salio de ese carril. La fila ya guardaba lo
gastado de cada carril por separado, asi que la simetria existia y solo faltaba
esta mitad.

**Por que no lleva valor de arranque calculado.** La columna nace en cero para
las filas que ya existen, y eso es lo correcto y no una comodidad: de las
llamadas ya registradas sin valorar no se sabe de que carril salieron --es
justamente el dato que faltaba--, y repartirlas por conjetura escribiria un
numero inventado en la fila que decide el corte. Cero es la lectura honesta:
"de este carril no consta ninguna". El libro mayor si guarda el carril de cada
fila desde `0001`, asi que el dia que haga falta reconstruirlo se puede contar
de ahi; esta revision no lo hace porque ninguna fila anterior existe todavia en
un despliegue.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "u5_platform_0003_recording_lane"
down_revision: str | None = "u5_platform_0002_call_release"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: La restriccion que se va, escrita aqui una vez para que `upgrade` la borre y
#: `downgrade` la vuelva a poner con el mismo texto. Es la unica cadena que las
#: dos direcciones comparten: repetirla a mano es como una revision deja de ser
#: reversible sin que nadie lo note.
RESERVA_CONTIENE_EL_GASTO = "recording_spent_usd <= COALESCE(recording_reserve_usd, 0)"


def upgrade() -> None:
    # --- 1. El exceso de la llamada en vuelo, permitido (BR4.5, BR3.1) --------
    # Ver el encabezado: con esta restriccion puesta, una llamada de grabacion
    # con la reserva agotada no dejaba fila, y una fila de gasto perdida falsea
    # una cifra publicada sin dejar rastro de que falta.
    op.drop_constraint(
        "budget_window_grabacion_dentro_de_su_reserva", "budget_window", type_="check"
    )

    # --- 2. El conteo propio del carril de grabacion --------------------------
    op.add_column(
        "budget_window",
        sa.Column("unmeasured_recording_calls", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "budget_window_no_medidas_de_grabacion_no_negativas",
        "budget_window",
        "unmeasured_recording_calls >= 0",
    )
    # Las de grabacion son un **subconjunto** de las facturables sin valorar,
    # igual que su gasto es una parte del acumulado: es la gemela de
    # `budget_window_grabacion_dentro_del_acumulado`, aplicada al conteo.
    op.create_check_constraint(
        "budget_window_no_medidas_de_grabacion_dentro_del_total",
        "budget_window",
        "unmeasured_recording_calls <= unmeasured_billable_calls",
    )


def downgrade() -> None:
    """Deshace la revision entera. `mise run migrate:check` la corre en cada corrida.

    **Su limite, dicho.** Volver a poner la restriccion de la reserva falla si
    alguna fila ya la viola, que es exactamente el estado que esta revision
    permite. Contra la base virgen de `migrate:check` no hay filas y la bajada
    demuestra lo que tiene que demostrar; contra un despliegue con datos, bajar
    esta revision exige decidir antes que se hace con el exceso ya registrado, y
    esa decision no la puede tomar una migracion en silencio.
    """
    op.drop_constraint(
        "budget_window_no_medidas_de_grabacion_dentro_del_total", "budget_window", type_="check"
    )
    op.drop_constraint(
        "budget_window_no_medidas_de_grabacion_no_negativas", "budget_window", type_="check"
    )
    op.drop_column("budget_window", "unmeasured_recording_calls")
    op.create_check_constraint(
        "budget_window_grabacion_dentro_de_su_reserva",
        "budget_window",
        RESERVA_CONTIENE_EL_GASTO,
    )
