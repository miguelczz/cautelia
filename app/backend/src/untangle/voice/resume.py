"""Retomar una llamada que se corto (BR6.1 a BR6.5).

**Un corte no es un final: es una pausa.** El socket que se cierra sin cuadro de
colgar deja el caso esperando al asegurado con lo confirmado y con su ventana de
retoma, y asi aparece en la bandeja. Lo que impide que una ajustadora lo lea como
abandonado es precisamente ese estado.

**La busqueda es solo por el navegador, y su firma lo impone** (BR6.3, criterio
`[bloquea]` AC1.27.3). La poliza de ejemplo es publica y la comparten todos los
visitantes de una aseguradora: buscar por ella significaria que decir un numero
publico en voz alta abre el caso de otra persona --su nombre, su direccion, lo que
conto del accidente--. `session.find_resumable` no admite un parametro de poliza,
y hay una prueba sobre su firma.

**La apertura va primero siempre** (BR6.2). Saltarsela porque "ya la oyo la vez
pasada" es exactamente el atajo que la compuerta de divulgacion existe para
impedir.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from untangle.base import Locale
from untangle.case_record import api as casos
from untangle.case_record import history as historial
from untangle.case_record.models import ChangeKind
from untangle.compliance.controls.normalization import fold
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey
from untangle.orchestration.nodes.intake import blocks, composition, confirmation
from untangle.tenancy.models import TenantId
from untangle.voice import hold_request, notice
from untangle.voice.models import CallSession

OFFER = CopyKey("voice.resume.offer")
#: Lo que se dice al seguir con el caso, antes de su pregunta pendiente.
ACCEPTED = CopyKey("voice.resume.accepted")
#: Cuando el caso no tiene pregunta pendiente que retomar (ya decidido, o a la espera de
#: su lectura final): se le pregunta a la persona que quiere agregar.
CONTINUE_OPEN = CopyKey("voice.resume.continue_open")
#: Lo que se dice al abrir un caso nuevo, antes de preguntar en que se la ayuda.
NEW_CASE = CopyKey("voice.resume.new_case")


@dataclass(frozen=True)
class Resumable:
    """Un caso que este navegador puede retomar, y como se le habla de el."""

    case_id: str
    case_number: str
    #: Nulo mientras nadie lo haya decidido.
    spoken_decision: notice.Spoken | None
    #: La llamada que se corto, para enlazar la marca de recuperacion (BR8.3).
    dropped_call_id: str
    #: Como termino esa llamada: un corte, un fallo o un "guardalo" dicho a proposito.
    #: Viaja en la marca para que NFR3 --retomar tras un corte-- no cuente como corte
    #: una llamada que la persona dejo guardada.
    ended_by: str | None = None
    #: La pregunta con que el caso habia quedado, la que la captura haria ahora: se
    #: deduce de lo que ya tiene (`blocks.next_block`), sin guardar nada ni llamar al
    #: grafo. Nula cuando ya no hay bloque que preguntar.
    pending_question: str | None = None


def offer(*, language: Locale) -> str:
    """ "Veo que tiene un caso abierto." Va **despues** de la apertura completa."""
    return copy_api.t(OFFER, locale=language)


def acknowledge_continue(*, language: Locale) -> str:
    """Lo que se dice al seguir con el caso, antes de su pregunta pendiente."""
    return copy_api.t(ACCEPTED, locale=language)


def ask_what_else(*, language: Locale) -> str:
    """La pregunta cuando el caso no tiene ninguna pendiente que retomar."""
    return copy_api.t(CONTINUE_OPEN, locale=language)


def acknowledge_new_case(*, language: Locale) -> str:
    """Lo que se dice al abrir un caso nuevo, antes de preguntar en que se la ayuda."""
    return copy_api.t(NEW_CASE, locale=language)


class Reply(StrEnum):
    """Lo que la persona contesto a "¿seguimos con ese?" (BR6.4)."""

    #: Un si a secas: se sigue con el caso y la agente retoma su pregunta pendiente.
    CONTINUE = "continue"
    #: Un no, o pedir uno nuevo: se abre un caso nuevo y el anterior queda intacto.
    NEW_CASE = "new_case"
    #: Cuenta algo --"fue ayer en la calle diez"--: se sigue con el caso y eso es ya su
    #: turno, que se atiende como cualquier otro.
    WITH_CONTENT = "with_content"


#: Las formas de pedir uno nuevo que no abren con un "no", plegadas. Cerrada y de frases
#: enteras: "otra cosa" a secas aparece en "tengo otra cosa que agregar", y eso es seguir
#: con el caso.
_UNO_NUEVO: tuple[str, ...] = (
    "empezar de nuevo",
    "empezar otro",
    "empezar uno nuevo",
    "desde cero",
    "uno nuevo",
    "caso nuevo",
    "reporte nuevo",
    "nuevo caso",
    "nuevo reporte",
    "otro caso",
    "otro reporte",
    "otro accidente",
    "otro siniestro",
    "es otra cosa",
    "start over",
    "start again",
    "start a new",
    "start fresh",
    "from scratch",
    "a new one",
    "new case",
    "new report",
    "another case",
    "another report",
    "another accident",
    "different accident",
    "different one",
)
_PATRON_UNO_NUEVO = re.compile(r"\b(?:" + "|".join(_UNO_NUEVO) + r")\b")
_PALABRAS = re.compile(r"[^\W_]+")

#: Lo que acompana a un si sin ser contenido: las cortesias de `hold_request` y los
#: verbos y articulos con que se dice "sigamos con ese". Cerrada a proposito: una sola
#: palabra de mas y el turno cuenta algo, que es el lado seguro (se atiende como turno).
_SIN_CONTENIDO: frozenset[str] = hold_request.RELLENOS | frozenset(
    {
        "correcto", "exacto", "asi", "es", "ese", "esa", "eso", "mismo", "misma", "el", "la",
        "caso", "reporte", "seguimos", "sigamos", "sigue", "seguir", "continuemos", "continuar",
        "con", "dale", "listo", "vale", "perfecto", "yep", "right", "exactly", "correct", "that",
        "one", "same", "the", "it", "is", "lets", "let", "s", "continue", "keep", "going", "go",
        "ahead", "us",
    }
)  # fmt: skip


def _trae_contenido(answer: str) -> bool:
    return any(palabra not in _SIN_CONTENIDO for palabra in _PALABRAS.findall(fold(answer)))


def reply_to(answer: str, *, language: Locale) -> Reply:
    """Que contesto la persona a la oferta de retomar.

    Reusa el reconocedor de U11 para el si y el no (`confirmation`), el mismo que
    confirma un codigo leido. Tres desenlaces y no dos: antes todo lo que no era un si
    era un no, y quien contestaba contando el accidente abria un caso nuevo sin querer.
    Callar no acepta, pero eso lo decide el reloj de silencio y no esta funcion.
    """
    plegado = fold(answer)
    if _PATRON_UNO_NUEVO.search(plegado) is not None or confirmation.is_negative(
        answer, language=language
    ):
        return Reply.NEW_CASE
    if _trae_contenido(answer):
        return Reply.WITH_CONTENT
    return Reply.CONTINUE


async def _comentario_del_cierre(tenant_id: TenantId, case_id: str) -> str:
    """El comentario de quien decidio, leido del historial.

    No vive en el caso sino en la entrada que lo cerro: el comentario y el cierre
    son el mismo acto y se guardan juntos (BR4.1 de U14). Se lee por el mismo
    camino que la vista de la bandeja, no por uno propio.
    """
    entradas = await historial.of_case(tenant_id, case_id)
    cierres = [e for e in entradas if e.change_kind is ChangeKind.TRANSITION_APPLIED and e.detail]
    return cierres[-1].detail or "" if cierres else ""


def _pending_question(vista: casos.CaseView, *, language: Locale) -> str | None:
    """La pregunta que la captura haria ahora con este caso, o nada.

    Es la misma deduccion que hace el grafo para saber que pregunto en el turno
    anterior (`blocks.next_block` sobre la completitud guardada), asi que no hay nada
    que persistir: con el mismo caso sale la misma pregunta. Un caso que ya no esta
    capturando, o que ya lo tiene todo, no tiene ninguna.
    """
    bloque = blocks.next_block(vista.record_type, vista.completeness, vista.state)
    if bloque not in blocks.order_for(vista.record_type):
        return None
    faltan = blocks.missing_fields_in_block(vista.record_type, bloque, vista.completeness)
    if not faltan:
        return None
    return composition.compose_question(bloque, faltan, language=language)


def next_question(vista: casos.CaseView, *, language: Locale) -> str | None:
    """La pregunta que la captura haria ahora con este caso, en ese idioma, o nada.

    Es `_pending_question` hecha publica (2026-10-13): al cambiar de idioma a mitad de una
    llamada, la pregunta que la agente dejo en el aire hay que volver a decirla en el
    idioma nuevo, y la unica forma de tenerla es deducirla otra vez del caso.
    """
    return _pending_question(vista, language=language)


async def find(
    call: CallSession, *, tenant_id: TenantId, now: datetime, language: Locale
) -> Resumable | None:
    """El caso retomable de este navegador, ya con lo que se le va a decir.

    Devuelve `None` cuando no hay ninguno, cuando el caso se borro, o cuando la
    llamada cortada no llego a tener caso: nada de eso es un error, es que no hay
    nada que retomar.
    """
    if call.case_id is None:
        return None
    vista = await casos.get_case(tenant_id, call.case_id)
    if vista is None:
        return None
    dicho = None
    if vista.resolution is not None:
        # Un caso que todavia se esta capturando no tiene nada que resumir: lo
        # que toca ahi es la oferta de continuar, no un parte de algo que no paso.
        dicho = notice.resolved(
            vista.resolution,
            case_number=str(vista.case_number),
            comment=await _comentario_del_cierre(tenant_id, vista.case_id),
            language=vista.language,
        )
    return Resumable(
        case_id=vista.case_id,
        case_number=str(vista.case_number),
        spoken_decision=dicho,
        dropped_call_id=call.call_id,
        ended_by=None if call.end_reason is None else call.end_reason.value,
        pending_question=_pending_question(vista, language=language),
    )


__all__ = [
    "ACCEPTED",
    "CONTINUE_OPEN",
    "NEW_CASE",
    "OFFER",
    "Reply",
    "Resumable",
    "acknowledge_continue",
    "acknowledge_new_case",
    "ask_what_else",
    "find",
    "next_question",
    "offer",
    "reply_to",
]
