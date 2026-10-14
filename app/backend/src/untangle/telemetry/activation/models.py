"""Los tipos de la telemetria de activacion (U6, FD-U6-8).

Cuenta cuantas sesiones llegan a cada uno de tres hitos, **una vez por sesion**,
y no guarda nada que apunte a una persona. Dos tablas con dos vidas: el avance
de cada sesion, que es dato de visitante y se borra cada noche, y el conteo por
dia, aseguradora e hito, que sobrevive (BR8.1, BR8.2).

Este modulo es una hoja: no importa ninguna otra pieza de la activacion.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import Field

from untangle.base import Frozen


class ActivationMilestone(StrEnum):
    """Los tres hitos de una sesion (BR8.1, AC5.16.6).

    Lista cerrada, con la misma grafia que la restriccion de la tabla: un hito
    que no esta aqui no se puede escribir en el codigo ni entrar en la base.
    """

    #: El visitante mando su primer mensaje en el chat (lo informa U13).
    FIRST_MESSAGE = "first_message"
    #: La conversacion llego al tercer turno (lo informa U13).
    THIRD_TURN = "third_turn"
    #: El caso volvio decidido a la vista por enlace (lo informa U14).
    LOOP_CLOSED = "loop_closed"


class ActivationSource(StrEnum):
    """Quien produjo el trafico que informa el hito (BR8.4).

    Solo el de un visitante cuenta como sesion. El chequeo periodico y el
    corredor de evaluaciones recorren el mismo camino que un visitante, y si
    contaran, la cifra publicada mediria cuantas veces se probo la demo y no
    cuantas personas la usaron.
    """

    VISITOR = "visitor"
    HEALTH_CHECK = "health_check"
    EVAL_RUNNER = "eval_runner"


class MilestoneOutcome(StrEnum):
    """Que paso al informar un hito. Se devuelve; nunca se lanza (BR8.3)."""

    #: Primera vez en esta sesion: se guardo el avance y se sumo uno al dia.
    COUNTED = "counted"
    #: La sesion ya tenia ese hito: no paso nada, y es lo correcto.
    ALREADY_REACHED = "already_reached"
    #: El trafico no era de un visitante: no se registro nada (BR8.4).
    NOT_A_SESSION = "not_a_session"
    #: La escritura fallo. El turno siguio y quedo un evento con el motivo.
    FAILED = "failed"


class RecordFailure(StrEnum):
    """Por que no se pudo registrar un hito. Lista cerrada, para el evento (OBS-U6.4).

    Cuatro motivos y no un texto: el evento sale por el punto unico de eventos,
    y un mensaje de excepcion en crudo podria arrastrar lo que no debe.
    """

    #: La escritura no termino dentro de su presupuesto de tiempo.
    TIMEOUT = "timeout"
    #: La base no estaba configurada o no respondio.
    UNAVAILABLE = "unavailable"
    #: La base rechazo la fila: la sesion no es una clave de esa aseguradora, o
    #: la aseguradora no existe en la configuracion.
    REJECTED = "rejected"
    #: Cualquier otra cosa. Se nombra aparte para que no se esconda en las demas.
    UNEXPECTED = "unexpected"


class ActivationDailyCount(Frozen):
    """Una fila del conteo publicable: dia, aseguradora, hito y cuantas sesiones.

    Es **lo unico** de la activacion que tiene ruta de lectura (BR8.5): el avance
    por sesion no se lee desde fuera, solo se escribe y se borra.
    """

    tenant_id: str
    day: date
    milestone: ActivationMilestone
    count: int = Field(ge=0)
