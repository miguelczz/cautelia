"""La conversacion de un navegador, y quien decide si un mensaje se atiende.

Aqui se ata la compuerta dura de la tanda: **ningun texto del visitante se procesa
antes de que la apertura haya salido y quedado registrada** (BR1.1, BR1.2). No es una
promesa del que escribe el manejador del turno: `admit` no devuelve un mensaje
admitido si la conversacion no tiene su apertura hecha, y no hay otra forma de llegar
al proveedor.

**La conversacion se resuelve por el resumen de la clave del navegador**, nunca por la
clave: un volcado de la base no sirve para hacerse pasar por nadie (SEC-U13.4). La
misma forma que U2 ya usa para sus enlaces firmados.

**Toda consulta sale del punto unico de sesion** con la aseguradora fijada, como todo
lo demas del aplicativo.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from untangle.base import Locale
from untangle.chat.limits import Counters, LimitDecision, LimitKind, decide
from untangle.tenancy import session as db
from untangle.tenancy.models import ChatConfig, TenantId

_CREAR = """
    INSERT INTO chat_session
        (chat_session_id, tenant_id, visitor_key_digest, language, origin_digest,
         message_count, created_at)
    VALUES
        (:chat_session_id, :tenant_id, :visitor_key_digest, :language, :origin_digest,
         0, :created_at)
"""

_BUSCAR_VIVA = """
    SELECT chat_session_id, case_id, language, origin_digest, message_count,
           last_message_at, disclosed_at
    FROM chat_session
    WHERE tenant_id = :tenant_id AND visitor_key_digest = :visitor_key_digest
      AND closed_at IS NULL
"""

#: Los casos de las conversacions de ese navegador. Lo pide la telemetria para
#: marcar "tu caso" en la lista de casos (2026-10-09): sin el resumen de la galleta
#: no hay a quien marcar, y con el solo salen los suyos.
_CASOS_DEL_NAVEGADOR = """
    SELECT DISTINCT case_id
    FROM chat_session
    WHERE tenant_id = :tenant_id AND visitor_key_digest = :visitor_key_digest
      AND case_id IS NOT NULL
"""

#: Cuales de esos casos nacieron de la vista de comparacion, y de que navegador son
#: (2026-10-11). Lo pide el tablero de gasto para mostrar como **una sola cosa** las
#: consultas que salen de un clic en "Comparar": la vista habla tres veces, una por
#: aseguradora, y no hay otro dato que las ate.
#:
#: "Nacio de la comparacion" no se adivina: es la divulgacion que quedo registrada al
#: abrir el caso (`disclosure_record.catalog_key`), que es la del bloque de la
#: comparacion solo cuando la mostro esa vista. Y el navegador es el de la
#: conversacion que lo abrio, viva o cerrada. La union cruza dos tablas con la misma
#: politica de fila, dentro de la sesion de una sola aseguradora.
_CASOS_DE_COMPARACION = """
    SELECT DISTINCT s.case_id, s.visitor_key_digest
    FROM chat_session s
    JOIN disclosure_record d
      ON d.tenant_id = s.tenant_id AND d.case_id = s.case_id AND d.channel = 'chat'
    WHERE s.tenant_id = :tenant_id
      AND s.case_id = ANY(:case_ids)
      AND d.catalog_key = :catalog_key
"""

#: Quien escucha por un caso (U19, tanda 2). Devuelve el resumen de la clave del
#: navegador, que es con lo que se busca su cola: la conversacion no sirve --se va
#: con el reinicio nocturno-- y la clave en claro no sale de U2.
#:
#: **Solo conversaciones vivas.** Una cerrada no tiene pestana escuchando, y
#: publicar en su cola seria escribir en una cola que nadie drena.
_BUSCAR_POR_CASO = """
    SELECT visitor_key_digest, language
    FROM chat_session
    WHERE tenant_id = :tenant_id AND case_id = :case_id
      AND closed_at IS NULL
"""

_MARCAR_DIVULGADA = """
    UPDATE chat_session SET disclosed_at = :ahora
    WHERE tenant_id = :tenant_id AND chat_session_id = :chat_session_id
      AND disclosed_at IS NULL
"""

#: El caso se ata **una sola vez**. `case_id IS NULL` no es una optimizacion: una
#: conversacion tiene un caso, y una segunda escritura significaria que el grafo
#: abrio otro -- que es un fallo que hay que ver, no uno que hay que absorber
#: pisando el primero.
_ATAR_CASO = """
    UPDATE chat_session SET case_id = :case_id
    WHERE tenant_id = :tenant_id AND chat_session_id = :chat_session_id
      AND case_id IS NULL
"""

#: Pasa la conversacion a otro caso porque la persona **cambio de tema** (2026-10-12): de
#: consultar su poliza a reportar un accidente. Es la unica escritura que reemplaza un caso ya
#: atado, y se lee como una comparacion y cambio: solo si la conversacion sigue en el caso del
#: que se parte, para que dos mensajes en vuelo no se pisen el uno al otro. El caso anterior
#: no se toca; solo deja de ser el de esta conversacion.
_CAMBIAR_CASO = """
    UPDATE chat_session SET case_id = :case_id
    WHERE tenant_id = :tenant_id AND chat_session_id = :chat_session_id
      AND case_id = :anterior
"""

#: Los contadores **de ese dia**, y de ningun otro. Hasta el 2026-10-12 la condicion era
#: solo `window_start >= :desde`: con el reloj de verdad es lo mismo, porque no hay filas
#: de manana, pero quien recibe `now` por argumento --el conductor de evaluaciones, que
#: conversa en un dia fijo del pasado-- sumaba ademas todo lo que se hubiera escrito
#: despues, y un dia agoto el cupo sin que nadie hubiera escrito ese dia.
_CONTAR_ORIGEN = """
    SELECT COALESCE(sum(count), 0) AS total FROM chat_rate_window
    WHERE tenant_id = :tenant_id AND scope = 'origin' AND scope_key = :scope_key
      AND window_start >= :desde AND window_start < :hasta
"""

_CONTAR_SITIO = """
    SELECT COALESCE(sum(count), 0) AS total FROM chat_rate_window
    WHERE tenant_id = :tenant_id AND scope = 'site_day'
      AND window_start >= :desde AND window_start < :hasta
"""

_OLVIDAR_DIA = """
    DELETE FROM chat_rate_window
    WHERE tenant_id = :tenant_id AND window_start >= :desde AND window_start < :hasta
"""

_SUMAR = """
    INSERT INTO chat_rate_window (tenant_id, scope, scope_key, window_start, count)
    VALUES (:tenant_id, :scope, :scope_key, :window_start, 1)
    ON CONFLICT (tenant_id, scope, scope_key, window_start)
    DO UPDATE SET count = chat_rate_window.count + 1
"""

#: Cierra la conversacion de un navegador porque **la persona pidio empezar de
#: cero** (decision de Miguel, 2026-10-06). Hasta entonces ningun camino del
#: aplicativo escribia `closed_at`: solo el reinicio nocturno borraba la fila. El
#: caso de la conversacion cerrada queda como esta, con su numero, y lo borra el
#: reinicio nocturno; la fila cerrada sigue atando el caso a este navegador para
#: retomarlo por su numero (BR6.2).
_CERRAR = """
    UPDATE chat_session SET closed_at = :ahora
    WHERE tenant_id = :tenant_id AND chat_session_id = :chat_session_id
      AND closed_at IS NULL
"""

#: El idioma de una conversacion **que todavia no ha dicho nada** se ajusta al de
#: la pantalla (decision de Miguel, 2026-10-06: la agente habla el idioma del
#: selector salvo senal clara en el mensaje). Solo con cero mensajes: una
#: conversacion en marcha cambia de idioma por lo que la persona escribe, no por
#: un selector que alguien toco sin querer.
_CAMBIAR_IDIOMA = """
    UPDATE chat_session SET language = :language
    WHERE tenant_id = :tenant_id AND chat_session_id = :chat_session_id
      AND message_count = 0
"""

_CONTAR_MENSAJE = """
    UPDATE chat_session
    SET message_count = message_count + 1, last_message_at = :ahora
    WHERE tenant_id = :tenant_id AND chat_session_id = :chat_session_id
"""


class OpeningNotDeliveredError(RuntimeError):
    """Se intento atender un mensaje antes de que saliera la apertura (BR1.1).

    Es un error del codigo que llama, no del visitante: la apertura sale al cargar
    la pagina, antes de que haya nada que escribir. Falla en el acto y nombra la
    conversacion, en vez de atender el mensaje y registrar la divulgacion despues,
    que seria decir que se dijo algo que no se dijo.
    """


@dataclass(frozen=True)
class ChatSession:
    """Una conversacion viva, tal como esta en la base."""

    chat_session_id: str
    tenant_id: TenantId
    language: Locale
    origin_digest: str
    message_count: int
    case_id: str | None = None
    last_message_at: datetime | None = None
    #: Cuando salio la apertura. `None` mientras no ha salido, y mientras sea
    #: `None` ningun mensaje se atiende.
    disclosed_at: datetime | None = None

    @property
    def opening_delivered(self) -> bool:
        return self.disclosed_at is not None


@dataclass(frozen=True)
class Listener:
    """Quien esta escuchando por un caso: su navegador y su idioma."""

    visitor_key_digest: str
    language: Locale


async def listener_of(tenant_id: TenantId, case_id: str) -> Listener | None:
    """Quien escucha por este caso, o `None` si no hay conversacion viva.

    `None` no es un fallo: es que la pestana se cerro, o que el caso llego por la
    voz y no por el chat. Quien llama lo trata como "no habia a quien avisar".
    """
    async with db.session_for(tenant_id) as sesion:
        fila = await db.fetch_one(sesion, _BUSCAR_POR_CASO, tenant_id=tenant_id, case_id=case_id)
    if fila is None:
        return None
    return Listener(visitor_key_digest=fila["visitor_key_digest"], language=fila["language"])


@dataclass(frozen=True)
class Admission:
    """Si el mensaje se atiende, y si no, cual limite lo paro."""

    session: ChatSession
    decision: LimitDecision

    @property
    def admitted(self) -> bool:
        return self.decision.allowed

    @property
    def limit(self) -> LimitKind | None:
        return self.decision.kind


def _inicio_del_dia(now: datetime) -> datetime:
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


async def open_session(
    *,
    tenant_id: TenantId,
    visitor_key_digest: str,
    origin_digest: str,
    language: Locale,
    now: datetime,
) -> ChatSession:
    """Abre la conversacion de un navegador. Todavia **sin** apertura entregada."""
    chat_session_id = f"chat-{uuid.uuid4().hex[:16]}"
    async with db.session_for(tenant_id) as sesion:
        await db.execute_sql(
            sesion,
            _CREAR,
            chat_session_id=chat_session_id,
            tenant_id=tenant_id,
            visitor_key_digest=visitor_key_digest,
            language=language,
            origin_digest=origin_digest,
            created_at=now,
        )
    return ChatSession(
        chat_session_id=chat_session_id,
        tenant_id=tenant_id,
        language=language,
        origin_digest=origin_digest,
        message_count=0,
    )


async def find_live(*, tenant_id: TenantId, visitor_key_digest: str) -> ChatSession | None:
    """La conversacion viva de ese navegador, si la tiene."""
    async with db.session_for(tenant_id) as sesion:
        fila = await db.fetch_one(
            sesion, _BUSCAR_VIVA, tenant_id=tenant_id, visitor_key_digest=visitor_key_digest
        )
    if fila is None:
        return None
    return ChatSession(
        chat_session_id=fila["chat_session_id"],
        tenant_id=tenant_id,
        language=fila["language"],
        origin_digest=fila["origin_digest"],
        message_count=fila["message_count"],
        case_id=fila["case_id"],
        last_message_at=fila["last_message_at"],
        disclosed_at=fila["disclosed_at"],
    )


async def mark_opening_delivered(session_: ChatSession, *, now: datetime) -> ChatSession:
    """Deja constancia de que la apertura salio en esta conversacion (BR1.1).

    Solo la primera vez: la condicion `disclosed_at IS NULL` de la sentencia hace
    que volver a cargar la pagina no mueva la hora de cuando de verdad se dijo.
    """
    async with db.session_for(session_.tenant_id) as sesion:
        await db.execute_sql(
            sesion,
            _MARCAR_DIVULGADA,
            tenant_id=session_.tenant_id,
            chat_session_id=session_.chat_session_id,
            ahora=now,
        )
    if session_.disclosed_at is not None:
        return session_
    return ChatSession(
        chat_session_id=session_.chat_session_id,
        tenant_id=session_.tenant_id,
        language=session_.language,
        origin_digest=session_.origin_digest,
        message_count=session_.message_count,
        case_id=session_.case_id,
        last_message_at=session_.last_message_at,
        disclosed_at=now,
    )


async def attach_case(session_: ChatSession, *, case_id: str) -> ChatSession:
    """Ata el caso que el grafo abrio a la conversacion que lo produjo (BR6.4).

    **Sin esto la conversacion no sabe cual es su caso**, y no es un detalle de
    comodidad: el turno siguiente vuelve al grafo con `case_id` en nulo --asi que
    cada mensaje parece una conversacion nueva--, la transcripcion no se escribe
    porque no hay caso donde escribirla, y el resumen de traza no se abre porque
    no hay caso al que atarlo. Faltaba, y lo encontro el conductor de evaluaciones
    la primera vez que corrio una conversacion entera por el canal: el asegurado
    simulado contesto veinte veces el mismo campo.

    Solo la primera vez, por la condicion de la sentencia.
    """
    if session_.case_id is not None:
        return session_
    async with db.session_for(session_.tenant_id) as sesion:
        await db.execute_sql(
            sesion,
            _ATAR_CASO,
            tenant_id=session_.tenant_id,
            chat_session_id=session_.chat_session_id,
            case_id=case_id,
        )
    return ChatSession(
        chat_session_id=session_.chat_session_id,
        tenant_id=session_.tenant_id,
        language=session_.language,
        origin_digest=session_.origin_digest,
        message_count=session_.message_count,
        case_id=case_id,
        last_message_at=session_.last_message_at,
        disclosed_at=session_.disclosed_at,
    )


class ConversationMovedError(RuntimeError):
    """La conversacion ya no esta en el caso del que se queria pasar a otro.

    Otro mensaje en vuelo la movio antes. No se absorbe pisando: se ve, y el turno falla
    diciendolo en vez de dejar dos casos que se creen el de la conversacion."""


async def switch_case(session_: ChatSession, *, case_id: str, from_case_id: str) -> ChatSession:
    """Pasa la conversacion de su caso actual a otro, cuando la persona cambia de tema.

    **El caso anterior queda intacto**: esto no lo borra ni lo cierra. Es el unico camino que
    reemplaza un caso ya atado, y por eso no reutiliza `attach_case`: aquella guarda existe
    para que un segundo caso abierto por sorpresa se vea, y aflojarla habria tapado justo lo
    que vigila. Este camino tiene nombre, su regla y `from_case_id` como condicion.
    """
    if session_.case_id == case_id:
        return session_
    async with db.session_for(session_.tenant_id) as sesion:
        filas = await db.execute_sql(
            sesion,
            _CAMBIAR_CASO,
            tenant_id=session_.tenant_id,
            chat_session_id=session_.chat_session_id,
            case_id=case_id,
            anterior=from_case_id,
        )
    if filas == 0:
        msg = f"la conversacion '{session_.chat_session_id}' ya no esta en el caso del que se parte"
        raise ConversationMovedError(msg)
    return ChatSession(
        chat_session_id=session_.chat_session_id,
        tenant_id=session_.tenant_id,
        language=session_.language,
        origin_digest=session_.origin_digest,
        message_count=session_.message_count,
        case_id=case_id,
        last_message_at=session_.last_message_at,
        disclosed_at=session_.disclosed_at,
    )


async def admit(
    session_: ChatSession,
    *,
    config: ChatConfig,
    message_characters: int,
    now: datetime,
) -> Admission:
    """Si este mensaje se atiende (BR1.1, BR3.1, BR3.2).

    **Primero la apertura.** Una conversacion sin apertura entregada no llega a
    mirar ningun limite: levanta, porque atender el mensaje y registrar la
    divulgacion despues seria decir que se dijo algo que no se dijo.

    Despues los cinco controles, con los contadores leidos de la base. Lo que
    decide sigue siendo la funcion pura de `limits`; esto solo le trae los datos.
    """
    if not session_.opening_delivered:
        msg = (
            f"la conversacion '{session_.chat_session_id}' no tiene la apertura "
            "entregada: ningun texto del visitante se procesa antes (BR1.1)"
        )
        raise OpeningNotDeliveredError(msg)

    desde = _inicio_del_dia(now)
    hasta = desde + timedelta(days=1)
    async with db.session_for(session_.tenant_id) as sesion:
        por_origen = await db.fetch_one(
            sesion,
            _CONTAR_ORIGEN,
            tenant_id=session_.tenant_id,
            scope_key=session_.origin_digest,
            desde=desde,
            hasta=hasta,
        )
        del_sitio = await db.fetch_one(
            sesion, _CONTAR_SITIO, tenant_id=session_.tenant_id, desde=desde, hasta=hasta
        )

    contadores = Counters(
        session_messages=session_.message_count,
        origin_messages_today=int(por_origen["total"]) if por_origen is not None else 0,
        site_messages_today=int(del_sitio["total"]) if del_sitio is not None else 0,
        last_message_at=session_.last_message_at,
    )
    decision = decide(
        config=config, counters=contadores, message_characters=message_characters, now=now
    )
    return Admission(session=session_, decision=decision)


async def set_language_if_fresh(session_: ChatSession, *, language: Locale) -> ChatSession:
    """El idioma de la pantalla, para una conversacion que todavia no ha dicho nada.

    Devuelve la conversacion con el idioma nuevo si se aplico; tal cual si ya
    tenia mensajes o ya estaba en ese idioma.
    """
    if session_.message_count > 0 or session_.language == language:
        return session_
    async with db.session_for(session_.tenant_id) as sesion:
        await db.execute_sql(
            sesion,
            _CAMBIAR_IDIOMA,
            tenant_id=session_.tenant_id,
            chat_session_id=session_.chat_session_id,
            language=language,
        )
    return ChatSession(
        chat_session_id=session_.chat_session_id,
        tenant_id=session_.tenant_id,
        language=language,
        origin_digest=session_.origin_digest,
        message_count=session_.message_count,
        case_id=session_.case_id,
        last_message_at=session_.last_message_at,
        disclosed_at=session_.disclosed_at,
    )


async def close_session(session_: ChatSession, *, now: datetime) -> None:
    """Cierra la conversacion porque la persona quiso empezar de cero.

    Solo la fila de la conversacion: el caso queda como esta, con su numero, y la
    persona puede retomarlo por ese numero. La conversacion siguiente de este
    navegador nace nueva, con su apertura.
    """
    async with db.session_for(session_.tenant_id) as sesion:
        await db.execute_sql(
            sesion,
            _CERRAR,
            tenant_id=session_.tenant_id,
            chat_session_id=session_.chat_session_id,
            ahora=now,
        )


async def count_message(session_: ChatSession, *, now: datetime) -> None:
    """Suma el mensaje a los tres contadores. Solo lo llama quien fue admitido.

    Sumar antes de saber si se atiende gastaria el presupuesto del visitante con
    los mensajes que se le rechazaron, que es justo lo contrario de lo que los
    limites existen para hacer.
    """
    ventana = _inicio_del_dia(now)
    async with db.session_for(session_.tenant_id) as sesion:
        await db.execute_sql(
            sesion,
            _CONTAR_MENSAJE,
            tenant_id=session_.tenant_id,
            chat_session_id=session_.chat_session_id,
            ahora=now,
        )
        for ambito, clave in (
            ("origin", session_.origin_digest),
            ("site_day", ventana.date().isoformat()),
        ):
            await db.execute_sql(
                sesion,
                _SUMAR,
                tenant_id=session_.tenant_id,
                scope=ambito,
                scope_key=clave,
                window_start=ventana,
            )


class DayStillCountsError(ValueError):
    """Se pidio olvidar los contadores de un dia que todavia limita a alguien."""


async def forget_past_day(tenant_id: TenantId, *, day: datetime, now: datetime) -> None:
    """Borra los contadores de un dia **ya pasado** de esa aseguradora.

    Los contadores de un dia que termino no limitan a nadie: `admit` solo mira los de
    hoy. Existe para el conductor de evaluaciones, que conversa siempre en el mismo dia
    fijo del pasado (dos corridas tienen que ver los mismos tiempos) y antes de cada
    conversacion deja ese dia en cero, como lo encontraria un visitante en un dia
    tranquilo. Sin esto, cada corrida sumaba sobre la anterior y a las pocas corridas
    el canal rechazaba todo por cupo diario.

    **Se niega con hoy o con un dia futuro** (`now` es el reloj de verdad): eso si seria
    levantarle el limite a alguien, y este modulo no ofrece esa puerta.
    """
    desde = _inicio_del_dia(day)
    if desde >= _inicio_del_dia(now):
        msg = (
            f"el dia {desde.date().isoformat()} no ha terminado: sus contadores todavia "
            "limitan los mensajes de hoy y no se olvidan"
        )
        raise DayStillCountsError(msg)
    async with db.session_for(tenant_id) as sesion:
        await db.execute_sql(
            sesion,
            _OLVIDAR_DIA,
            tenant_id=tenant_id,
            desde=desde,
            hasta=desde + timedelta(days=1),
        )


async def case_ids_of_visitor(*, tenant_id: TenantId, visitor_key_digest: str) -> frozenset[str]:
    """Los casos que este navegador abrio por conversacion en esa aseguradora."""
    async with db.session_for(tenant_id) as sesion:
        filas = await db.fetch_all(
            sesion,
            _CASOS_DEL_NAVEGADOR,
            tenant_id=tenant_id,
            visitor_key_digest=visitor_key_digest,
        )
    return frozenset(str(fila["case_id"]) for fila in filas)


async def comparison_browsers(
    *, tenant_id: TenantId, case_ids: Sequence[str], catalog_key: str
) -> dict[str, str]:
    """Del caso al resumen del navegador, solo para los que abrio la comparacion.

    `catalog_key` es la clave de divulgacion de esa vista (la decide quien llama, que
    es quien conoce las superficies). El resumen no sale del aplicativo: sirve para
    agrupar, y lo que se publica es la posicion del grupo.
    """
    if not case_ids:
        return {}
    async with db.session_for(tenant_id) as sesion:
        filas = await db.fetch_all(
            sesion,
            _CASOS_DE_COMPARACION,
            tenant_id=tenant_id,
            case_ids=list(case_ids),
            catalog_key=catalog_key,
        )
    return {str(fila["case_id"]): str(fila["visitor_key_digest"]) for fila in filas}


__all__ = [
    "Admission",
    "ChatSession",
    "ConversationMovedError",
    "DayStillCountsError",
    "OpeningNotDeliveredError",
    "admit",
    "attach_case",
    "case_ids_of_visitor",
    "close_session",
    "comparison_browsers",
    "count_message",
    "find_live",
    "forget_past_day",
    "mark_opening_delivered",
    "open_session",
    "set_language_if_fresh",
    "switch_case",
]
