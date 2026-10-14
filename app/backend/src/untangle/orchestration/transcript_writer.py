"""Quien escribe la transcripcion de un caso, para **cualquier** canal.

**Por que existe en vez de una copia por canal.** El chat escribia sus dos turnos
en `chat/delivery.py` y la voz no escribia ninguno: una llamada dejaba su caso sin
una sola palabra, y con eso la revision de cumplimiento no se podia acotar --no hay
turno hasta donde llegar-- ni la bandeja dejaba cerrar el caso. La tentacion era
copiar las dos funciones al ciclo de la voz, y es justo lo que el catalogo de
revision de este proyecto llama dos guardias para la misma regla: el dia que una
cambie, la otra seguira diciendo lo de antes.

Asi que la regla vive aqui una sola vez y los dos canales la llaman. Lo que **no**
se movio es cuando se llama: el chat lo hace al cerrar su flujo de eventos y la voz
al cerrar su turno hablado, que son momentos distintos de dos ciclos distintos.

**El texto se persiste redactado y el tipo lo impone**: `append_turn` exige
`Redacted`, y ese tipo solo lo produce el punto unico de redaccion. No hay forma de
escribir aqui un `str` cualquiera.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from untangle.base import Locale
from untangle.case_record import api as casos
from untangle.case_record.models import Channel, Speaker
from untangle.case_record.transcript import TurnDraft
from untangle.compliance.redaction import api as redaccion
from untangle.orchestration.contracts import (
    CaseNotifier,
    FinalText,
    Handoff,
    TurnError,
    TurnEvent,
)
from untangle.tenancy.models import TenantId

#: El prefijo del turno de una respuesta de cobertura verificada: el historial le vuelve
#: a poner sus clausulas al reconocerlo (2026-10-08).
COVERAGE_TURN_PREFIX = "coverage-"

__all__ = [
    "COVERAGE_TURN_PREFIX",
    "Closing",
    "TranscriptScope",
    "closing_text",
    "record_agent_turn",
    "record_person_turn",
    "say_without_turn",
]


@dataclass(frozen=True)
class Closing:
    """Lo que cierra un turno: su texto y **de donde salio**.

    Las dos juntas porque la segunda decide por que puerta se tapa la primera, y
    separarlas deja a quien escribe adivinandolo.
    """

    text: str
    #: Cierto cuando lo compuso el catalogo de textos. Una frase del catalogo no
    #: lleva datos personales por construccion --la escribimos nosotros y vive en un
    #: archivo versionado-- y pasarle el detector de nombres solo puede danarla: en
    #: espanol etiqueta como persona el verbo con que arranca una frase, el nombre
    #: de la agente y el de la aseguradora.
    from_catalog: bool


def closing_text(evento: TurnEvent) -> Closing | None:
    """Lo que la agente dijo al **cerrar** el turno, o `None` si ese evento no cierra.

    Las tres ramas se nombran y no se adivina con `getattr`: los eventos del turno
    son un conjunto cerrado (C-14), y un cuarto evento con texto tiene que entrar
    aqui a proposito en vez de colarse --o quedarse fuera-- sin que nadie lo vea.

    Vive junto a quien escribe la transcripcion y no en un canal, porque es la misma
    regla para los dos: lo que se guarda es lo que la persona acabo oyendo o
    leyendo, no la frase de espera ni los fragmentos de una frase que llega a
    trozos.
    """
    if isinstance(evento, FinalText):
        return Closing(text=evento.text, from_catalog=evento.from_catalog)
    if isinstance(evento, Handoff | TurnError):
        # Los dos salen **siempre** del catalogo y no hace falta que lo declaren:
        # llevan su `copy_key`, que es de donde salio su texto. Solo `FinalText`
        # puede traer texto del modelo, y por eso es el unico con el campo.
        return Closing(text=evento.text, from_catalog=True)
    return None


@dataclass(frozen=True)
class TranscriptScope:
    """De que caso, por que canal y en que idioma se habla.

    Las cuatro viajan juntas porque describen **la misma conversacion**. Sueltas,
    la firma pide seis argumentos y dos de ellos son cadenas que se pueden cruzar
    --el caso en el sitio de la aseguradora-- sin que nada se queje hasta que una
    fila aparece donde no debia.
    """

    tenant_id: TenantId
    case_id: str
    channel: Channel
    language: Locale


async def _escribir(
    ambito: TranscriptScope,
    *,
    speaker: Speaker,
    text: str,
    now: datetime,
    turn_id: str | None = None,
) -> str:
    turn_id = turn_id or f"turn-{uuid.uuid4().hex[:16]}"
    borrador = TurnDraft(
        turn_id=turn_id,
        case_id=ambito.case_id,
        speaker=speaker,
        channel=ambito.channel,
        language=ambito.language,
        started_at=now,
        ended_at=now,
    )
    # **Lo que dijo la agente se guarda por una sola puerta, venga de donde venga**
    # (2026-10-10). Antes habia dos: la frase del catalogo pasaba sin mirarse y la
    # del modelo se tapaba entera. La primera dejaba en claro el numero de poliza y
    # el nombre que la frase llevaba dentro; la segunda guardaba "[NOMBRE 1]" donde
    # la persona habia leido "Encontre". `redact_composed` tapa los datos y respeta
    # nuestras palabras. Lo que dijo la persona sigue por `redact`, entero.
    tapado = (
        redaccion.redact(text, language=ambito.language)
        if speaker is Speaker.INSURED
        else redaccion.redact_composed(text, language=ambito.language)
    )
    await casos.append_turn(ambito.tenant_id, borrador, tapado)
    return turn_id


async def record_person_turn(ambito: TranscriptScope, *, text: str, now: datetime) -> str:
    """Lo que la persona dijo, con el canal por el que lo dijo (BR6.4)."""
    return await _escribir(ambito, speaker=Speaker.INSURED, text=text, now=now)


async def record_agent_turn(
    ambito: TranscriptScope,
    *,
    text: str,
    now: datetime,
    from_catalog: bool,
    turn_id: str | None = None,
) -> str:
    """Lo que la agente dijo al cerrar el turno.

    **Una sola vez por turno, y solo lo que cierra el turno.** La frase de espera no
    cierra --la persona sigue esperando la respuesta-- y los fragmentos son la misma
    frase que llega a trozos. Lo que se guarda es lo que la persona acabo oyendo o
    leyendo.

    **Su instante es el de ahora y no el de la llegada del mensaje.** La
    transcripcion se lee por `started_at`, y dos turnos con el mismo instante quedan
    en orden arbitrario; la revision de cumplimiento busca "el turno de la agente
    **siguiente** a la peticion de persona", asi que el orden es la regla que se
    comprueba.
    """
    # `from_catalog` ya no decide como se guarda: todo lo que dice la agente pasa por
    # la misma redaccion (ver `_escribir`). Se conserva en la firma porque quien
    # llama lo tiene a mano y es lo que la voz usa para decidir como lo **dice**.
    del from_catalog
    return await _escribir(ambito, speaker=Speaker.AGENT, text=text, now=now, turn_id=turn_id)


async def say_without_turn(  # noqa: PLR0913 -- el aviso y lo que acompana al texto, por nombre
    notifier: CaseNotifier,
    ambito: TranscriptScope,
    *,
    text: str,
    now: datetime,
    turn_id: str | None = None,
    from_catalog: bool = True,
    citations: tuple[object, ...] = (),
    suggestions: tuple[str, ...] = (),
    coverage_outcome: str | None = None,
) -> bool:
    """Lo que la agente dice **sin que haya un turno abierto**: se guarda y se publica.

    Es el unico camino por el que el fondo le habla a una pantalla, y existe por una
    regla: **todo texto de la agente que se publica queda en la transcripcion del
    caso**. El texto se guarda primero y se publica despues, asi quien nunca lo
    escucho --la pestana cerrada, la llamada ya colgada-- lo encuentra al volver. Antes
    cada llamador guardaba por su cuenta o no guardaba, y una frase publicada sin
    guardar (la de "que quieres saber", 2026-10-12) salia en pantalla y desaparecia al
    recargar. Un chequeo de la suite busca cualquier otra llamada a `notify`.

    Devuelve lo que devuelve el puerto: si habia alguien escuchando.
    """
    await record_agent_turn(ambito, text=text, now=now, from_catalog=from_catalog, turn_id=turn_id)
    return await notifier.notify(
        ambito.tenant_id,
        ambito.case_id,
        text=text,
        citations=citations,
        suggestions=suggestions,
        coverage_outcome=coverage_outcome,
        language=ambito.language,
    )
