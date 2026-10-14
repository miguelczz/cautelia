"""Lo que la pantalla recupera al abrirse: la apertura y la conversacion guardada.

**Hasta el 2026-10-06 la conversacion vivia solo en la pestana.** El servidor la
tenia entera --la sesion por la galleta del navegador, el caso atado a la sesion y
cada turno en la transcripcion del caso-- y la pantalla no la pedia nunca: quien
salia a mirar el numero de su poliza volvia a una ventana vacia, y su primer
"hola" recibia la pregunta por la que iba la agente, sin apertura y sin nada
delante que la explicara. Lo vio Miguel, y es la captura que pidio arreglar.

**Lo que se devuelve es lo guardado, que esta redactado.** La transcripcion se
persiste tapada --`append_turn` exige el tipo redactado de U3, y no hay otra
puerta-- asi que lo que la persona vuelve a leer de si misma lleva etiquetas
donde escribio un nombre o un numero de poliza. No es un defecto que esconder:
es la regla de redactar antes de persistir, vista desde el lado del visitante, y
la pantalla lo dice en una linea en vez de dejar que la etiqueta parezca un
error de maquetacion.

**La apertura se compone de nuevo, no se lee.** No es un turno de la
transcripcion --sale antes de que exista caso-- y es determinista desde la
configuracion de la aseguradora y el idioma de la sesion, asi que recomponerla
da el mismo texto que la persona leyo. Lo que si queda guardado es que salio
(`disclosed_at`), y es lo unico que esta funcion necesita saber de ella.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from untangle.base import Frozen, Locale
from untangle.case_record import api as casos
from untangle.case_record.models import Speaker, TranscriptTurn
from untangle.chat import citation, opening
from untangle.chat import session as chat
from untangle.orchestration.nodes.intake import suggestions as sugerencias
from untangle.orchestration.transcript_writer import COVERAGE_TURN_PREFIX
from untangle.policy_rag.citations import api as citas
from untangle.policy_rag.citations.models import CoverageOutcome
from untangle.tenancy.models import TenantConfig

#: Quien habla, visto desde la pantalla del visitante: lo suyo y lo de la
#: aseguradora. Lo que escribe el personal de la bandeja lo lee la persona como
#: una voz mas de la aseguradora, no como una tercera columna.
HistorySpeaker = Literal["visitor", "agent"]


class HistoryTurn(Frozen):
    """Un turno guardado, tal como la pantalla lo vuelve a dibujar."""

    turn_id: str
    speaker: HistorySpeaker
    #: Ya redactado al guardarse (SEC-U4.6). Se llama `text` y no `text_redacted`
    #: porque para la pantalla es el texto del mensaje; que venga tapado lo dice la
    #: nota que acompana al historial, no el nombre del campo.
    text: str
    language: Locale
    channel: str
    at: str
    #: Las clausulas de una respuesta de cobertura, como llegaron en vivo: sin ellas, al
    #: volver al chat la respuesta quedaba sin sus tarjetas (2026-10-08).
    citations: tuple[citation.CitationDetail, ...] = ()


class OpeningView(Frozen):
    """El primer mensaje de la agente, con el mismo identificador que viaja por el flujo."""

    message_id: str
    text: str
    language: Locale
    #: Los botones de lo que la agente sabe hacer (fase 0, 2026-10-07).
    suggestions: tuple[str, ...] = ()


class ChatHistory(Frozen):
    """Lo que la pantalla necesita para dibujar la conversacion como estaba.

    `opening` es `None` solo cuando la conversacion todavia no la tiene entregada,
    que tras pasar por la ruta no ocurre: la ruta la entrega antes de componer
    esto. El tipo lo conserva porque la composicion es pura y no puede asumir lo
    que la ruta hizo.
    """

    opening: OpeningView | None
    turns: tuple[HistoryTurn, ...]
    #: El numero legible del caso, cuando la conversacion ya abrio uno. Es lo que la
    #: persona puede anotar para retomar desde otro navegador (BR6.1).
    case_number: str | None
    language: Locale


def speaker_of(speaker: Speaker) -> HistorySpeaker:
    """De quien es un turno, para la pantalla. Tabla cerrada: un cuarto hablante
    tiene que decidir aqui de que lado se dibuja, en vez de caer en uno por omision."""
    match speaker:
        case Speaker.INSURED:
            return "visitor"
        case Speaker.AGENT | Speaker.STAFF:
            return "agent"


def opening_message_id(session_: chat.ChatSession) -> str:
    """El identificador con el que la apertura viaja por el flujo.

    Es el mismo que publica la ruta del mensaje cuando la entrega por el flujo, y
    tiene que serlo: la pantalla quita los repetidos por identificador, asi que si
    la apertura llegara una vez por el historial y otra por el flujo con nombres
    distintos, se leeria dos veces.
    """
    return f"opening-{session_.chat_session_id}"


def turn_view(
    turno: TranscriptTurn, citations: tuple[citation.CitationDetail, ...] = ()
) -> HistoryTurn:
    """Un turno de la transcripcion en la forma de la pantalla."""
    return HistoryTurn(
        turn_id=turno.turn_id,
        speaker=speaker_of(turno.speaker),
        text=turno.text_redacted,
        language=turno.language,
        channel=turno.channel.value,
        at=turno.started_at.isoformat(),
        citations=citations,
    )


def compose(
    session_: chat.ChatSession,
    *,
    config: TenantConfig,
    turns: tuple[TranscriptTurn, ...],
    case_number: str | None,
    citations: Mapping[str, tuple[citation.CitationDetail, ...]] | None = None,
) -> ChatHistory:
    """El historial, a partir de lo que ya se leyo. Pura: no toca la base.

    La apertura solo se compone si la conversacion la tiene entregada. Componerla
    para una que no la tiene diria que la persona leyo algo que no leyo, que es
    exactamente lo que el registro de la divulgacion existe para impedir.
    """
    apertura = (
        OpeningView(
            message_id=opening_message_id(session_),
            text=opening.compose(config, language=session_.language).text,
            language=session_.language,
            suggestions=sugerencias.options(
                language=session_.language, quote_enabled=config.quote_enabled
            ),
        )
        if session_.opening_delivered
        else None
    )
    return ChatHistory(
        opening=apertura,
        turns=tuple(turn_view(turno, (citations or {}).get(turno.turn_id, ())) for turno in turns),
        case_number=case_number,
        language=session_.language,
    )


async def load(session_: chat.ChatSession, *, config: TenantConfig) -> ChatHistory:
    """El historial de una conversacion viva, leyendo su caso si lo tiene.

    Sin caso no hay transcripcion ni numero: la conversacion acaba de abrirse y lo
    unico que la pantalla dibuja es la apertura. Un caso que la politica de fila
    no deje ver --no deberia ocurrir, la sesion es de esta aseguradora-- se trata
    como ausente y no como error: la pantalla sigue dibujando la apertura.

    **Lo dicho en los casos por los que paso la conversacion tambien se dibuja** (2026-10-13):
    quien cambio de tema abrio un caso nuevo, y al recargar la pantalla perdia de vista lo que
    hablo antes. El numero es el del caso en que esta la conversacion; la transcripcion de cada
    caso sigue siendo suya en la bandeja y en "Ver mi caso".
    """
    if session_.case_id is None:
        return compose(session_, config=config, turns=(), case_number=None)
    vista = await casos.get_case(session_.tenant_id, session_.case_id)
    turnos = await casos.conversation_transcript(session_.tenant_id, session_.case_id)
    return compose(
        session_,
        config=config,
        turns=turnos,
        case_number=None if vista is None else str(vista.case_number),
        citations=await _citas_de_la_conversacion(session_.tenant_id, turnos),
    )


async def _citas_de_la_conversacion(
    tenant_id: str, turnos: tuple[TranscriptTurn, ...]
) -> dict[str, tuple[citation.CitationDetail, ...]]:
    """Las clausulas de las respuestas de cobertura de cada caso de la conversacion.

    La respuesta verificada se guarda por el caso que la dijo, asi que se busca caso por caso y
    los turnos se agrupan por el `case_id` que cada uno conserva. Con un solo caso es la misma
    consulta de siempre."""
    por_caso: dict[str, list[TranscriptTurn]] = {}
    for turno in turnos:
        por_caso.setdefault(turno.case_id, []).append(turno)
    salida: dict[str, tuple[citation.CitationDetail, ...]] = {}
    for case_id, suyos in por_caso.items():
        salida.update(await _citas_de_cobertura(tenant_id, case_id, tuple(suyos)))
    return salida


@dataclass(frozen=True)
class _Cita:
    clause_id: str
    amount_deferred: bool


async def _citas_de_cobertura(
    tenant_id: str,
    case_id: str,
    turnos: tuple[TranscriptTurn, ...],
) -> dict[str, tuple[citation.CitationDetail, ...]]:
    """Las clausulas de cada respuesta de cobertura verificada, por su turno.

    Las respuestas verificadas y los turnos que las dijeron van en el mismo orden: el
    fondo guarda la respuesta y despues la dice. Se emparejan en ese orden.

    **Cada tarjeta se rotula en el idioma en que se respondio** (2026-10-13), el que la
    respuesta dejo guardado, como cuando llego en vivo. Antes se usaba el idioma de la
    conversacion, que en una aseguradora que arranca en ingles no cambia aunque la persona
    escriba en espanol: la respuesta llegaba con «Parte D» y al recargar volvia con «Part D».
    """
    de_cobertura = [t.turn_id for t in turnos if t.turn_id.startswith(COVERAGE_TURN_PREFIX)]
    if not de_cobertura:
        return {}
    verificadas = [
        (respuesta.answer_language, comprobaciones)
        for respuesta, comprobaciones in sorted(
            await citas.answers_for(tenant_id, case_id), key=lambda par: par[0].created_at
        )
        if respuesta.outcome is CoverageOutcome.VERIFIED and comprobaciones
    ]
    salida: dict[str, tuple[citation.CitationDetail, ...]] = {}
    for turn_id, (idioma, comprobaciones) in zip(de_cobertura, verificadas, strict=False):
        salida[turn_id] = await citation.details_for(
            tenant_id,
            [
                _Cita(clause_id=c.clause_id, amount_deferred=bool(c.amended_by))
                for c in comprobaciones
                if c.outcome is CoverageOutcome.VERIFIED
            ],
            language=idioma,
        )
    return salida


__all__ = [
    "ChatHistory",
    "HistorySpeaker",
    "HistoryTurn",
    "OpeningView",
    "compose",
    "load",
    "opening_message_id",
    "speaker_of",
    "turn_view",
]
