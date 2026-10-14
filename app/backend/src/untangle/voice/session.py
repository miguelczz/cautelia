"""La fila de una llamada: abrirla, encontrarla, atarle un caso y terminarla.

Mismo patron que `chat/session.py`, y por la misma razon: toda consulta pasa por
el punto unico que fija la aseguradora de la sesion antes de devolverla.

**`find_resumable` busca solo por el navegador** (BR6.3, criterio `[bloquea]`
AC1.27.3). La poliza de ejemplo es publica y la comparten todos los visitantes de
una aseguradora: si la busqueda la mirara, cualquiera que dijera ese numero en
voz alta abriria el caso de otra persona --su nombre, su direccion, lo que conto
del accidente--. La firma de esta funcion no admite una poliza, que es la forma
mas barata de que nadie la pase por descuido.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from untangle.base import Locale
from untangle.tenancy import session as db
from untangle.tenancy.models import TenantId
from untangle.voice.models import CallSession, CallState, EndReason, VoiceMode

_CREAR = """
    INSERT INTO call_session
        (call_id, tenant_id, visitor_key_digest, language, voice_mode, state, started_at)
    VALUES
        (:call_id, :tenant_id, :visitor_key_digest, :language, :voice_mode,
         :state, :started_at)
"""

#: La llamada viva de ese navegador. Sin `visitor_key_digest` esta consulta
#: devolveria la llamada de cualquiera, asi que el filtro no es una optimizacion.
_BUSCAR_VIVA = """
    SELECT call_id, case_id, visitor_key_digest, language, voice_mode, state,
           started_at, ended_at, end_reason, resume_until
    FROM call_session
    WHERE tenant_id = :tenant_id AND visitor_key_digest = :visitor_key_digest
      AND state <> 'ended'
    ORDER BY started_at DESC
    LIMIT 1
"""

#: Los casos de las llamadas de ese navegador. Lo pide la telemetria para
#: marcar "tu caso" en la lista de casos (2026-10-09): sin el resumen de la galleta
#: no hay a quien marcar, y con el solo salen los suyos.
_CASOS_DEL_NAVEGADOR = """
    SELECT DISTINCT case_id
    FROM call_session
    WHERE tenant_id = :tenant_id AND visitor_key_digest = :visitor_key_digest
      AND case_id IS NOT NULL
"""

#: Una llamada por su identificador, **solo si es de ese navegador**. Lo que la
#: consola necesita al terminar: la llamada ya no esta viva, asi que la busqueda
#: de arriba no la encuentra, y pedirla sin el resumen de la galleta dejaria que
#: cualquiera preguntara por el caso de cualquier llamada.
_BUSCAR_DEL_NAVEGADOR = """
    SELECT call_id, case_id, visitor_key_digest, language, voice_mode, state,
           started_at, ended_at, end_reason, resume_until
    FROM call_session
    WHERE tenant_id = :tenant_id AND call_id = :call_id
      AND visitor_key_digest = :visitor_key_digest
"""

#: La ultima llamada cortada de ese navegador, dentro de su ventana de retoma.
_BUSCAR_RETOMABLE = """
    SELECT call_id, case_id, visitor_key_digest, language, voice_mode, state,
           started_at, ended_at, end_reason, resume_until
    FROM call_session
    WHERE tenant_id = :tenant_id AND visitor_key_digest = :visitor_key_digest
      AND case_id IS NOT NULL
      AND resume_until IS NOT NULL AND resume_until > :ahora
    ORDER BY ended_at DESC
    LIMIT 1
"""

#: El caso se ata **una sola vez**, igual que en el chat: una segunda escritura
#: significaria que el grafo abrio otro caso, y eso es un fallo que hay que ver,
#: no uno que absorber pisando el primero.
_ATAR_CASO = """
    UPDATE call_session SET case_id = :case_id
    WHERE tenant_id = :tenant_id AND call_id = :call_id AND case_id IS NULL
"""

#: El unico caso en que un caso atado se reemplaza: la persona oyo la oferta de
#: retomar y dijo que llama por otro accidente (BR6.4). La guarda de arriba
#: --escribir solo sobre `NULL`-- existe contra que el grafo abra un segundo caso
#: sin que nadie lo pida, y eso sigue prohibido; esto es un camino nombrado, con
#: su regla, y solo mientras la llamada vive.
_CAMBIAR_CASO = """
    UPDATE call_session SET case_id = :case_id
    WHERE tenant_id = :tenant_id AND call_id = :call_id AND state <> 'ended'
"""

#: El idioma en que se esta hablando. Cambia cuando la persona lo pide o cuando la
#: deteccion lo decide (U18). **Solo mientras la llamada vive**: cambiar el idioma
#: de una llamada terminada seria reescribir lo que paso.
_CAMBIAR_IDIOMA = """
    UPDATE call_session SET language = :language
    WHERE tenant_id = :tenant_id AND call_id = :call_id AND state <> 'ended'
"""

_MARCAR_VIVA = """
    UPDATE call_session SET state = 'live'
    WHERE tenant_id = :tenant_id AND call_id = :call_id AND state = 'connecting'
"""

#: `state <> 'ended'` no es una guarda de mas: sin ella, dos caminos que terminan
#: la misma llamada --colgar y que se corte-- se pisarian el motivo, y el que
#: quedara escrito seria el ultimo en llegar y no el que de verdad la termino.
_TERMINAR = """
    UPDATE call_session
    SET state = 'ended', end_reason = :end_reason, ended_at = :ahora,
        resume_until = :resume_until
    WHERE tenant_id = :tenant_id AND call_id = :call_id AND state <> 'ended'
"""


class CallNotFoundError(LookupError):
    """La llamada no existe en esta aseguradora, o ya termino."""


def new_call_id() -> str:
    return f"call-{uuid.uuid4().hex[:16]}"


def _fila_a_llamada(fila: object, *, tenant_id: TenantId) -> CallSession:
    f = dict(fila)  # type: ignore[call-overload]
    return CallSession(
        call_id=f["call_id"],
        tenant_id=tenant_id,
        visitor_key_digest=f["visitor_key_digest"],
        language=f["language"],
        voice_mode=VoiceMode(f["voice_mode"]),
        state=CallState(f["state"]),
        started_at=f["started_at"],
        case_id=f["case_id"],
        ended_at=f["ended_at"],
        end_reason=EndReason(f["end_reason"]) if f["end_reason"] else None,
        resume_until=f["resume_until"],
    )


async def open_call(  # noqa: PLR0913 -- los cinco datos de la fila mas el identificador
    *,
    tenant_id: TenantId,
    visitor_key_digest: str,
    language: Locale,
    voice_mode: VoiceMode,
    now: datetime,
    call_id: str | None = None,
) -> CallSession:
    """Abre la llamada de un navegador. Todavia **sin** socket autenticado.

    `call_id` entra por argumento cuando quien abre ya lo necesito antes: el modo
    de voz se decide **con el identificador a la vista**, porque su decision queda
    en el rastro a nombre de esa llamada. Sin esto habria que elegir entre decidir
    el modo sin rastro o rastrearlo contra un identificador inventado.
    """
    call_id = call_id if call_id is not None else new_call_id()
    async with db.session_for(tenant_id) as sesion:
        await db.execute_sql(
            sesion,
            _CREAR,
            call_id=call_id,
            tenant_id=tenant_id,
            visitor_key_digest=visitor_key_digest,
            language=language,
            voice_mode=voice_mode.value,
            state=CallState.CONNECTING.value,
            started_at=now,
        )
    return CallSession(
        call_id=call_id,
        tenant_id=tenant_id,
        visitor_key_digest=visitor_key_digest,
        language=language,
        voice_mode=voice_mode,
        state=CallState.CONNECTING,
        started_at=now,
    )


async def find_live(*, tenant_id: TenantId, visitor_key_digest: str) -> CallSession | None:
    """La llamada sin terminar de ese navegador, si la tiene."""
    async with db.session_for(tenant_id) as sesion:
        fila = await db.fetch_one(
            sesion, _BUSCAR_VIVA, tenant_id=tenant_id, visitor_key_digest=visitor_key_digest
        )
    if fila is None:
        return None
    return _fila_a_llamada(fila, tenant_id=tenant_id)


async def find_of_visitor(
    *, tenant_id: TenantId, call_id: str, visitor_key_digest: str
) -> CallSession | None:
    """La llamada de ese navegador, viva o terminada (BR3.4).

    **Con el resumen de la galleta en la consulta y no despues**: comparar fuera
    dejaria la fila leida antes de saber si era suya, y una llamada ajena tiene que
    responder lo mismo que una que no existe.
    """
    async with db.session_for(tenant_id) as sesion:
        fila = await db.fetch_one(
            sesion,
            _BUSCAR_DEL_NAVEGADOR,
            tenant_id=tenant_id,
            call_id=call_id,
            visitor_key_digest=visitor_key_digest,
        )
    return None if fila is None else _fila_a_llamada(fila, tenant_id=tenant_id)


async def find_resumable(
    *, tenant_id: TenantId, visitor_key_digest: str, now: datetime
) -> CallSession | None:
    """La llamada cortada que este navegador puede retomar (BR6.3).

    **Solo por el navegador.** No hay parametro de poliza y no puede haberlo: la
    de ejemplo es publica, y buscarla ofreceria el caso de otro visitante.
    """
    async with db.session_for(tenant_id) as sesion:
        fila = await db.fetch_one(
            sesion,
            _BUSCAR_RETOMABLE,
            tenant_id=tenant_id,
            visitor_key_digest=visitor_key_digest,
            ahora=now,
        )
    if fila is None:
        return None
    return _fila_a_llamada(fila, tenant_id=tenant_id)


async def switch_case(call: CallSession, *, case_id: str) -> CallSession:
    """Mueve la llamada al caso nuevo cuando se llama por otro accidente (BR6.4).

    **El caso anterior queda intacto**: esto no lo borra ni lo cierra, solo deja
    de ser el caso de esta llamada. Es la unica escritura del proyecto que
    reemplaza un caso ya atado, y por eso no reutiliza `attach_case`: aquella
    guarda existe para que un segundo caso abierto por sorpresa se vea, y
    aflojarla habria tapado justo lo que vigila.
    """
    if call.case_id == case_id:
        return call
    async with db.session_for(call.tenant_id) as sesion:
        filas = await db.execute_sql(
            sesion, _CAMBIAR_CASO, tenant_id=call.tenant_id, call_id=call.call_id, case_id=case_id
        )
    if filas == 0:
        raise CallNotFoundError(call.call_id)
    return _con(call, case_id=case_id)


async def set_language(call: CallSession, *, language: Locale) -> CallSession:
    """Deja escrito el idioma en que se esta hablando (U18, BR2.3, BR5.1).

    **Escribe la llamada y no el caso.** El del caso es el que tenia al abrirse:
    si siguiera al ultimo turno, mover un caso de cola costaria decir dos palabras
    en el otro idioma, que es RT-10 con otra ropa.

    Se escribe y no se lleva en memoria porque una llamada que se corta y se
    retoma tiene que volver en el idioma en que se estaba hablando; con el idioma
    solo en memoria, retomar seria un cambio que nadie pidio.
    """
    if call.language == language:
        return call
    async with db.session_for(call.tenant_id) as sesion:
        filas = await db.execute_sql(
            sesion,
            _CAMBIAR_IDIOMA,
            tenant_id=call.tenant_id,
            call_id=call.call_id,
            language=language,
        )
    if filas == 0:
        raise CallNotFoundError(call.call_id)
    return _con(call, language=language)


async def mark_live(call: CallSession) -> CallSession:
    """El socket se autentico. Solo la primera vez."""
    async with db.session_for(call.tenant_id) as sesion:
        filas = await db.execute_sql(
            sesion, _MARCAR_VIVA, tenant_id=call.tenant_id, call_id=call.call_id
        )
    if filas == 0 and call.state is CallState.CONNECTING:
        raise CallNotFoundError(call.call_id)
    return call if call.state is not CallState.CONNECTING else _con(call, state=CallState.LIVE)


async def attach_case(call: CallSession, *, case_id: str) -> CallSession:
    """Ata el caso a la llamada. Una sola vez."""
    async with db.session_for(call.tenant_id) as sesion:
        await db.execute_sql(
            sesion,
            _ATAR_CASO,
            tenant_id=call.tenant_id,
            call_id=call.call_id,
            case_id=case_id,
        )
    return call if call.case_id is not None else _con(call, case_id=case_id)


async def end_call(
    call: CallSession,
    *,
    reason: EndReason,
    now: datetime,
    resume_window: timedelta | None = None,
) -> CallSession:
    """Termina la llamada con su motivo (BR1.6).

    `resume_window` solo tiene sentido en un corte: es lo que deja el caso
    retomable (BR6.1). Quien decide cuanto dura es U17; aqui entra por argumento.
    """
    hasta = now + resume_window if resume_window is not None else None
    async with db.session_for(call.tenant_id) as sesion:
        filas = await db.execute_sql(
            sesion,
            _TERMINAR,
            tenant_id=call.tenant_id,
            call_id=call.call_id,
            end_reason=reason.value,
            ahora=now,
            resume_until=hasta,
        )
    if filas == 0:
        raise CallNotFoundError(call.call_id)
    return _con(call, state=CallState.ENDED, ended_at=now, end_reason=reason, resume_until=hasta)


def _con(call: CallSession, **cambios: object) -> CallSession:
    from dataclasses import replace

    return replace(call, **cambios)  # type: ignore[arg-type]


async def case_ids_of_visitor(*, tenant_id: TenantId, visitor_key_digest: str) -> frozenset[str]:
    """Los casos que este navegador abrio por llamada en esa aseguradora."""
    async with db.session_for(tenant_id) as sesion:
        filas = await db.fetch_all(
            sesion,
            _CASOS_DEL_NAVEGADOR,
            tenant_id=tenant_id,
            visitor_key_digest=visitor_key_digest,
        )
    return frozenset(str(fila["case_id"]) for fila in filas)


__all__ = [
    "CallNotFoundError",
    "attach_case",
    "case_ids_of_visitor",
    "end_call",
    "find_live",
    "find_of_visitor",
    "find_resumable",
    "mark_live",
    "new_call_id",
    "open_call",
    "set_language",
    "switch_case",
]
