"""Que la agente entienda la conversacion, y no la lea por palabras clave (2026-10-07).

Decision de Miguel sobre `docs/propuesta-2026-10/03-propuesta-y-diseno.md`, fase 0:
el tipo de conversacion salia de palabras clave, los datos los copiaba un modelo
gratuito sin razonar y nadie contestaba lo que la persona preguntaba. Asi quedaron
18 anios de licencia donde eran 4, y «¿cuantos anios es eso?» sin respuesta.

**Que hace el modelo y que hace el codigo.** El modelo lee el mensaje con el
contexto del caso y devuelve una salida **cerrada**: que quiere la persona, de un
conjunto fijo; los datos que dio, ya interpretados («desde 2022» son 4 anios); si
contesto si o no a lo que se le pregunto; y la pregunta que hizo, si hizo una. El
codigo valida esa salida con los mismos normalizadores de siempre y sigue
decidiendo que falta, cuando se cierra y cuando se deriva. Ninguna transicion del
grafo sale de texto libre del modelo.

**Desde el 2026-10-12 el mismo formulario trae la respuesta** (`reply`): el modelo ve la
conversacion y el estado del caso, y contesta el mismo en esta llamada, en vez de que el
codigo elija una frase y un segundo modelo la reescriba sin ver nada
(`docs/propuesta-2026-10/07-el-modelo-lleva-la-conversacion.md`). Que texto sale de verdad,
y cuando sale la frase del catalogo en su lugar, lo decide `turn.py`; este modulo solo
define la forma de lo que se pide y de lo que vuelve.

**Si el modelo falla o tarda, el turno sigue como antes**: reglas y extraccion. Por
eso `understand` nunca levanta; devuelve `None` y deja su evento.

Este modulo no llama a ningun proveedor: define el puerto, la forma de la salida y
como se pide. El puerto lo construye la raiz de composicion.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

from untangle import observability
from untangle.base import Locale
from untangle.case_record.models import RecordType
from untangle.orchestration.nodes.intake.extraction import ExtractedItem, ExtractionResponse
from untangle.providers.ports import BudgetExhausted, ProviderError
from untangle.tenancy.models import TenantId


class Want(StrEnum):
    """Que quiere la persona con este mensaje. Conjunto cerrado."""

    REPORT_ACCIDENT = "report_accident"
    POLICY_QUESTION = "policy_question"
    QUOTE = "quote"
    GENERAL_QUESTION = "general_question"
    GREETING = "greeting"
    TALK_TO_PERSON = "talk_to_person"
    #: Sigue con lo que se le estaba pidiendo: contesta, corrige o cuenta mas.
    CONTINUE = "continue"
    OTHER = "other"


class Answer(StrEnum):
    """Que contesto a una pregunta de si o no pendiente. `none` si no habia o no contesto."""

    YES = "yes"
    NO = "no"
    NONE = "none"


#: Los campos que el modelo puede nombrar: los de los tres tipos de caso de
#: `case_record/schema/fields.yaml`, menos los que solo escribe el codigo. Lista
#: cerrada en el esquema, para que el proveedor la haga cumplir: con texto libre el
#: modelo devolvia `claim.incident_datetime` y el primer mensaje perdia sus datos
#: (visto en la evaluacion del 2026-10-08). Una prueba la compara con `fields.yaml`.
FieldKey = Literal[
    "injuries",
    "identity_and_policy",
    "description",
    "incident_datetime",
    "location",
    "vehicle_and_driver",
    "other_parties",
    "question_asked",
    "driver_name",
    "driver_birth_date",
    "license_years",
    "license_jurisdiction",
    "vehicle_year",
    "vehicle_make",
    "vehicle_model",
    "vin",
    "salvage_title",
    "use_type",
    "annual_mileage_band",
    "garaging_jurisdiction",
    "at_fault_losses_3y",
    "claims_3y",
    "prior_coverage_active",
    "lapse_months",
]


class UnderstoodItem(BaseModel):
    """Un dato que dio la persona, con su campo de la lista cerrada."""

    model_config = ConfigDict(frozen=True)

    field_key: FieldKey
    value: str


class UnderstandingResponse(BaseModel):
    """La salida que se le pide al modelo, validada contra este esquema."""

    model_config = ConfigDict(frozen=True)

    wants: Want
    items: tuple[UnderstoodItem, ...] = ()
    answer: Answer = Answer.NONE
    #: La pregunta que hizo la persona, con sus palabras, o `None`.
    person_question: str | None = None
    #: Si pregunta si algo esta cubierto por su poliza.
    asks_about_coverage: bool = False
    #: Ya no lo usa nadie: la instruccion `conversation` lo deja siempre en `null`. Se
    #: conserva en el esquema para que el formulario sea el mismo que ya valida el
    #: proveedor (2026-10-12: el acuse de la llamada pasó a ser parte de `reply`).
    acknowledgement: str | None = None
    #: Lo que la agente le dice a la persona en este turno. **Va al final del formulario
    #: a proposito**: el modelo la escribe despues de haber decidido los datos que anota,
    #: y asi la respuesta cuenta con ellos. El texto es del modelo: lo que de verdad sale
    #: lo decide el turno (`turn._texto_del_turno`), que la comprueba y la pasa por la
    #: guardia de salida.
    reply: str | None = None

    def as_extraction(self) -> ExtractionResponse:
        """Los datos, en la forma que ya valida y normaliza la captura."""
        return ExtractionResponse(
            items=tuple(ExtractedItem(field_key=i.field_key, value=i.value) for i in self.items)
        )


class CaseStatus(StrEnum):
    """En que va el caso, dicho como lo necesita quien conversa (2026-10-12)."""

    NONE = "none"
    RECEIVING = "receiving"
    #: El reporte esta completo y las reglas lo revisan (US1.17): puede cerrarse solo o quedar
    #: con un ajustador, y todavia no se sabe cual.
    IN_REVIEW = "in_review"
    WITH_ADJUSTER = "with_adjuster"
    CLOSED = "closed"


@dataclass(frozen=True)
class NotedDetail:
    """Un dato ya anotado, tal como se le cuenta al modelo."""

    field_key: str
    #: El valor guardado, o `None` cuando no se manda: lo de identidad (nombre y poliza)
    #: va como «ya lo dio», sin el valor, porque la respuesta no puede repetirlo.
    value: str | None = None


@dataclass(frozen=True)
class HistoryLine:
    """Una intervencion de la conversacion, tal como esta guardada (ya tapada)."""

    speaker: Literal["person", "agent"]
    text: str


#: Cuantas intervenciones anteriores ve el modelo.
HISTORY_LINES = 12


@dataclass(frozen=True)
class UnderstandingRequest:
    """Lo que necesita quien entiende y contesta. Todo es dato; nada es instruccion."""

    tenant_id: TenantId
    language: Locale
    today: date
    #: El tipo del caso, o `None` en el primer mensaje, cuando todavia no hay caso.
    record_type: RecordType | None
    quote_enabled: bool
    #: Los datos ya anotados, con su valor, y las claves de los que faltan, en el orden
    #: en que se piden.
    noted: tuple[NotedDetail, ...]
    missing: tuple[str, ...]
    person_text: str
    #: Por donde habla la persona: la llamada pide una sola frase corta y sin simbolos.
    channel: Literal["chat", "voice"] = "chat"
    #: Como se llama la agente de esta aseguradora. `None` y la raiz de composicion
    #: resuelve el de la aseguradora.
    agent_name: str | None = None
    case_status: CaseStatus = CaseStatus.NONE
    #: Si la poliza de la persona ya esta identificada en el caso.
    policy_identified: bool = False
    #: Si hay una revision de poliza en curso: la respuesta esta por llegar.
    answer_pending: bool = False
    #: Las ultimas `HISTORY_LINES` intervenciones del caso, de la mas vieja a la mas
    #: nueva y sin el mensaje actual, que va aparte y sin tapar.
    history: tuple[HistoryLine, ...] = ()


#: El puerto: lo construye la raiz de composicion con el cliente de Claude. Puede
#: levantar; `understand` lo trata como "no se entendio" y el turno sigue por reglas.
Understander = Callable[[UnderstandingRequest], Awaitable[UnderstandingResponse]]

#: Cuanto se espera al modelo antes de seguir por reglas, **por canal**. Desde el 2026-10-12
#: la llamada tambien redacta la respuesta, asi que en el chat se espera mas: medido el
#: 2026-10-07 con Claude Haiku 5.5 y salida estructurada, entender tardaba de 1,3 a 1,7 s
#: en caliente y 2,5 s en frio, y la respuesta le suma salida. La voz se queda en lo que
#: tenia: quien llama espera al telefono y dos segundos de silencio ya se notan.
UNDERSTANDING_TIMEOUT_CHAT_S = 6.5
UNDERSTANDING_TIMEOUT_VOICE_S = 3.5


def understanding_timeout_s(channel: Literal["chat", "voice"]) -> float:
    """El plazo del modelo en ese canal."""
    return UNDERSTANDING_TIMEOUT_CHAT_S if channel == "chat" else UNDERSTANDING_TIMEOUT_VOICE_S


async def understand(
    understander: Understander | None, request: UnderstandingRequest
) -> UnderstandingResponse | None:
    """Lo que el modelo entendio, o `None` si no hay modelo, falla o tarda."""
    if understander is None:
        return None
    empezo = time.monotonic()
    try:
        respuesta = await asyncio.wait_for(
            understander(request), understanding_timeout_s(request.channel)
        )
    except TimeoutError:
        _sin_entender(request, "timeout", empezo)
        return None
    except (ProviderError, BudgetExhausted) as error:
        _sin_entender(request, type(error).__name__, empezo)
        return None
    respuesta = canonical_reading(respuesta, request.record_type)
    observability.emit(
        "chat.understood",
        tenant_id=request.tenant_id,
        wants=respuesta.wants.value,
        items=len(respuesta.items),
        answer=respuesta.answer.value,
        asked=respuesta.person_question is not None,
        coverage=respuesta.asks_about_coverage,
        ms=int((time.monotonic() - empezo) * 1000),
    )
    return respuesta


#: La intencion que corresponde a cada tipo de conversacion abierta.
_TEMA_DEL_TIPO: dict[RecordType, Want] = {
    RecordType.CLAIM: Want.REPORT_ACCIDENT,
    RecordType.COVERAGE_INQUIRY: Want.POLICY_QUESTION,
    RecordType.QUOTE_REQUEST: Want.QUOTE,
}


def canonical_reading(
    respuesta: UnderstandingResponse, record_type: RecordType | None
) -> UnderstandingResponse:
    """Una sola lectura para dos formas de decir lo mismo (medido el 2026-10-08).

    - Una duda que pregunta si algo esta cubierto es una pregunta por la poliza,
      aunque el modelo la llame duda general: «si se me rompe el vidrio, ¿me
      responden?» alterna entre las dos.
    - Dentro de una conversacion abierta, pedir lo mismo es seguir con ella: dar un
      dato en un reporte y decir que se quiere reportar son la misma lectura.
    """
    if respuesta.wants is Want.GENERAL_QUESTION and respuesta.asks_about_coverage:
        respuesta = respuesta.model_copy(update={"wants": Want.POLICY_QUESTION})
    if record_type is not None and respuesta.wants is _TEMA_DEL_TIPO[record_type]:
        respuesta = respuesta.model_copy(update={"wants": Want.CONTINUE})
    return respuesta


def _sin_entender(request: UnderstandingRequest, cause: str, started: float) -> None:
    observability.emit(
        "chat.understanding_fallback",
        tenant_id=request.tenant_id,
        cause=cause,
        ms=int((time.monotonic() - started) * 1000),
    )


def opening_record_type(
    understood: UnderstandingResponse, *, quote_enabled: bool
) -> RecordType | None:
    """Que caso abre el primer mensaje, o `None` si todavia no hay caso que abrir.

    Sin caso: un saludo, una duda general, algo que no es ninguna de las tres
    cosas, o pedir cotizar donde la aseguradora no cotiza. A esos se les contesta y
    se les dice que se puede hacer, sin abrir nada. Quien pide hablar con alguien
    abre un reporte, porque es lo que el ajustador recibe.
    """
    if understood.wants is Want.QUOTE:
        return RecordType.QUOTE_REQUEST if quote_enabled else None
    if understood.wants is Want.POLICY_QUESTION:
        return RecordType.COVERAGE_INQUIRY
    if understood.wants in (Want.REPORT_ACCIDENT, Want.TALK_TO_PERSON):
        return RecordType.CLAIM
    return None


#: Lo inverso: el tipo de caso que abre cada una de las tres intenciones que abren caso.
_TIPO_DEL_TEMA: dict[Want, RecordType] = {tema: tipo for tipo, tema in _TEMA_DEL_TIPO.items()}


def switch_record_type(
    understood: UnderstandingResponse, *, current: RecordType, quote_enabled: bool
) -> RecordType | None:
    """El tipo del caso nuevo si la persona cambio de tema en el chat, o `None` (2026-10-12).

    Cambiar de tema es pedir, con un caso abierto, otra de las tres cosas que abren caso
    (`report_accident`, `policy_question`, `quote`) cuyo tipo no es el del caso. La
    decision la toma el codigo sobre un valor cerrado: el modelo solo propone la intencion.

    Lo que **no** es cambiar de tema:

    - preguntar por cobertura dentro de un reporte en curso: sigue siendo el reporte, y la
      pregunta se revisa en el fondo como siempre;
    - preguntar, dentro de una consulta, si la poliza cubre algo que paso: quien cuenta un
      choque para saber si esta cubierto sigue consultando, y pasarlo solo a un reporte que
      no pidio fue lo que se vio el 2026-10-13. El reporte se abre cuando lo pide;
    - cotizar donde la aseguradora no cotiza (se contesta con la frase fija);
    - un mensaje que contesta una pregunta de si o no pendiente (`answer` distinto de
      `none`): es la respuesta a lo que se acaba de preguntar, no una peticion nueva.
    """
    if understood.answer is not Answer.NONE:
        return None
    pedido = _TIPO_DEL_TEMA.get(understood.wants)
    if pedido is None or pedido is current:
        return None
    if current is RecordType.CLAIM and pedido is RecordType.COVERAGE_INQUIRY:
        return None
    if (
        current is RecordType.COVERAGE_INQUIRY
        and pedido is RecordType.CLAIM
        and understood.asks_about_coverage
    ):
        return None
    if pedido is RecordType.QUOTE_REQUEST and not quote_enabled:
        return None
    return pedido


__all__ = [
    "HISTORY_LINES",
    "UNDERSTANDING_TIMEOUT_CHAT_S",
    "UNDERSTANDING_TIMEOUT_VOICE_S",
    "Answer",
    "CaseStatus",
    "FieldKey",
    "HistoryLine",
    "NotedDetail",
    "Understander",
    "UnderstandingRequest",
    "UnderstandingResponse",
    "UnderstoodItem",
    "Want",
    "canonical_reading",
    "opening_record_type",
    "switch_record_type",
    "understand",
    "understanding_timeout_s",
]
