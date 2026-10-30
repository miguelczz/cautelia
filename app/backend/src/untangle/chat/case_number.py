"""El numero de caso escrito en el chat, y lo que se le contesta (US1.19, US1.20).

**Lo reconoce el codigo, antes de cualquier modelo.** Escribir «AP-29» no se le pregunta a
quien entiende el mensaje: es un patron, como la peticion de un ajustador o la emergencia, y la
decision de atar la conversacion a ese caso es de las comprobaciones de dueno de
`chat.resume`, no de una interpretacion.

**Solo cuenta un prefijo que alguna aseguradora cargada use.** Un numero de poliza tiene la
forma parecida --letras, guion, cifras-- y la persona lo escribe mientras se identifica: tratar
`POL-23` como un numero de caso la dejaria sin atender. No se confunden porque el prefijo de un
caso es de dos letras y se reconoce solo si es el de una aseguradora cargada, y `\b` no deja
leer `OL-23` dentro de `POL-23`. Y son los prefijos de **todas**
las aseguradoras, no solo el de la que conversa: un numero de otra aseguradora tiene que recibir
la misma respuesta que uno que no existe (AC1.20.3), y esa respuesta solo puede darse si el chat
lo reconoce como numero de caso.

Las frases salen del catalogo (convencion 4). Ninguna nombra el motivo por el que un numero no
se retoma: hacia fuera hay una sola respuesta por cada configuracion, y dos frases distintas para
«no existe» y «es de otro navegador» serian la distincion que las dos compuertas duras prohiben.
"""

from __future__ import annotations

import re
from functools import lru_cache

from untangle.base import Locale
from untangle.case_record import api as casos
from untangle.case_record.models import CaseState
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey
from untangle.orchestration import closing_plan
from untangle.orchestration.nodes.intake import blocks, composition
from untangle.tenancy import config as tenancy_config

#: El caso se retomo y la agente sigue con lo que falta.
CONTINUED = CopyKey("chat.resume.continued")
#: El caso se retomo y no queda nada que preguntar: se pregunta que quiere agregar.
CONTINUED_OPEN = CopyKey("chat.resume.continued_open")
#: Con la continuidad encendida: no se retoma y no se dice por que.
NOT_FOUND = CopyKey("chat.resume.not_found")
#: Con la continuidad apagada (AC1.19.5): se explica que un caso se retoma por el canal donde
#: empezo, sin prometer que el chat pueda.
ORIGINAL_CHANNEL = CopyKey("chat.resume.original_channel")
#: Solo para el dueno: su caso ya no esta en captura y tampoco esta decidido.
WITH_ADJUSTER = CopyKey("chat.resume.with_adjuster")
#: Lo mismo, con el caso todavia en revision (US1.17): puede cerrarse solo o quedar con un
#: ajustador, y todavia no se sabe cual, asi que no se dice que ya lo tiene uno.
IN_REVIEW = CopyKey("chat.resume.in_review")

#: Los estados en los que el chat puede seguir tomando datos. El resto lo tiene un ajustador o
#: ya esta decidido, y no hay captura que continuar.
CONTINUABLE = frozenset({CaseState.OPEN, CaseState.CAPTURING})


@lru_cache(maxsize=8)
def _patron(prefijos: tuple[str, ...]) -> re.Pattern[str]:
    alternativas = "|".join(re.escape(prefijo) for prefijo in prefijos)
    return re.compile(
        rf"(?<![A-Za-z0-9-])({alternativas})[\s-]?([1-9]\d{{0,5}})(?![A-Za-z0-9])",
        re.IGNORECASE,
    )


def find(text: str) -> str | None:
    """El numero de caso que trae el mensaje, con la forma `AP-29`, o nada.

    Acepta que lo escriban con guion, con espacio o pegado, y en minusculas. Devuelve el primero
    que encuentre: un mensaje con dos numeros es un mensaje raro, y atender el primero es lo
    predecible.

    **Con dos letras de prefijo el cuidado es mayor**: no puede ir precedido de una letra, un
    digito ni un guion (`ZNX-9706` no contiene `NX-9706`, ni `SA-PAP-2026` a `AP-2026`), y el
    contador no lleva ceros a la izquierda ni mas de seis cifras.
    """
    prefijos = tuple(
        sorted({tenant.case_number_prefix for tenant in tenancy_config.loaded().available})
    )
    if not prefijos:
        return None
    encontrado = _patron(prefijos).search(text)
    if encontrado is None:
        return None
    prefijo, contador = encontrado.groups()
    return f"{prefijo.upper()}-{contador}"


def pending_question(vista: casos.CaseView, *, language: Locale) -> str | None:
    """La pregunta que la captura haria ahora con este caso, o nada.

    Es la deduccion que ya hace la voz para retomar una llamada (`blocks.next_block` sobre la
    completitud guardada): no hay nada que persistir, con el mismo caso sale la misma pregunta.
    Se pide como si el caso estuviera capturando: uno abierto que aun no recibio su primer
    turno tambien tiene su primera pregunta.
    """
    bloque = blocks.next_block(vista.record_type, vista.completeness, CaseState.CAPTURING)
    if bloque not in blocks.order_for(vista.record_type):
        return None
    faltan = blocks.missing_fields_in_block(vista.record_type, bloque, vista.completeness)
    if not faltan:
        return None
    return composition.compose_question(bloque, faltan, language=language)


def continued(vista: casos.CaseView, *, language: Locale) -> str:
    """Lo que se dice al retomar el caso: que se retomo y solo lo que falta (AC1.20.1)."""
    pregunta = pending_question(vista, language=language)
    numero = str(vista.case_number)
    if pregunta is None:
        return copy_api.t(CONTINUED_OPEN, locale=language, case_number=numero)
    return copy_api.t(CONTINUED, locale=language, case_number=numero, question=pregunta)


def not_resumed(*, continuity_enabled: bool, language: Locale) -> str:
    """La unica respuesta hacia fuera cuando el numero no se retoma.

    Depende de la configuracion de la aseguradora y de nada mas: ni de si el numero existe, ni de
    quien lo abrio, ni de por que canal.
    """
    if continuity_enabled:
        return copy_api.t(NOT_FOUND, locale=language)
    return copy_api.t(ORIGINAL_CHANNEL, locale=language)


def not_in_capture(vista: casos.CaseView, *, language: Locale) -> str:
    """Para quien si es dueno de un caso que ya no esta en captura y no esta decidido."""
    numero = str(vista.case_number)
    if vista.state in closing_plan.REVIEW_STATES:
        return copy_api.t(IN_REVIEW, locale=language, case_number=numero)
    return copy_api.t(WITH_ADJUSTER, locale=language, case_number=numero)


__all__ = [
    "CONTINUABLE",
    "CONTINUED",
    "CONTINUED_OPEN",
    "IN_REVIEW",
    "NOT_FOUND",
    "ORIGINAL_CHANNEL",
    "WITH_ADJUSTER",
    "continued",
    "find",
    "not_in_capture",
    "not_resumed",
    "pending_question",
]
