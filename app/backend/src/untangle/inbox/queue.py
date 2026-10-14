"""La cola de casos de una aseguradora: sus filtros, su orden y su cursor.

**El orden lo decide el servidor y no la pantalla** (BR1.1): prioridad primero y,
dentro de cada prioridad, la espera mas larga delante. Dos personas mirando la
misma cola tienen que ver lo mismo, y eso no se consigue ordenando en cada
navegador.

**Una solicitud de persona cuenta como prioridad alta** (AC3.1.2), y eso es dato
de la configuracion de la aseguradora: el caso llega con su prioridad ya puesta y
aqui no hay ninguna rama por aseguradora ni por motivo de derivacion.

**La cola no guarda nada.** Cada fila es una proyeccion de lo que U4 ya tiene,
filtrada y ordenada al consultar. Una copia seria una segunda verdad que hay que
mantener al dia, y el dia que discrepara no habria forma de saber cual manda.

**El cursor es opaco a proposito.** Lleva la terna con que se ordena --rango de
prioridad, instante de espera e identificador-- porque la paginacion por
desplazamiento se salta filas cuando la cola cambia entre dos paginas, que en una
bandeja viva es siempre. Que sea opaco impide que el navegador lo fabrique: un
cursor escrito a mano es una consulta escrita a mano.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from untangle.base import Locale
from untangle.case_record import api as casos
from untangle.case_record import repository as case_repo
from untangle.case_record.models import CaseState, Channel, Priority, RecordType
from untangle.tenancy.models import Role, TenantId

#: Cuantas filas trae una pagina cuando nadie lo dice (C-01).
DEFAULT_LIMIT = 25

#: El techo de una pagina (C-01). No es un umbral de calidad: es lo que impide que
#: una peticion pida la tabla entera y convierta una consulta barata en un
#: recorrido completo.
MAX_LIMIT = 100

#: Los estados que **no** aparecen en la cola, ni siquiera pidiendolos por su
#: nombre: el caso sigue en conversacion con el asegurado y no espera nada de
#: nadie en la bandeja. Sale de la tabla del diseno funcional, que dice estado
#: por estado que ofrece la bandeja.
#:
#: `closed` **si** aparece: un caso resuelto es lo que alguien busca cuando quiere
#: ver como quedo, y esconderlo obligaria a una segunda pantalla para leerlo.
FUERA_DE_LA_COLA: tuple[CaseState, ...] = (CaseState.OPEN, CaseState.CAPTURING)

#: El separador del cursor. Ninguno de los tres campos puede contenerlo: el rango
#: es un entero, el instante es ISO-8601 y el identificador de caso es opaco pero
#: acunado por U4 sin este caracter.
_SEPARADOR = "|"


class InvalidCursorError(ValueError):
    """El cursor no se puede leer.

    Se falla en vez de empezar la cola desde el principio en silencio: una pagina
    que vuelve al principio sin decirlo hace que quien recorre la cola vea las
    mismas filas para siempre sin enterarse.
    """


class InvalidFilterError(ValueError):
    """Un filtro nombra un valor que no esta en su conjunto cerrado.

    Se rechaza en vez de ignorarlo. Un filtro ignorado devuelve **mas** casos de
    los que se pidieron, y quien lo lea creera que esos son todos los que hay.
    """


class UndeclaredRoleScopeError(RuntimeError):
    """Un rol sin alcance declarado en la tabla de abajo.

    Falla en vez de atender la peticion con la cola entera: un rol nuevo cuyo
    alcance nadie escribio veria todos los casos de su aseguradora, y eso se
    descubriria en la pantalla de quien no debia verlos.
    """


@dataclass(frozen=True)
class RoleScope:
    """A que casos se limita **siempre** la bandeja de un rol.

    No es un filtro que pida la pantalla: es el recorte que el servidor aplica
    pase lo que pase en la peticion (BR4.2). Un campo en `None` es "este rol no
    se limita por ahi", no "lo decide quien llama".
    """

    record_type: RecordType | None = None
    state: CaseState | None = None


#: El alcance de cada rol de la bandeja. **Tabla cerrada y escrita**, con fila
#: para todos los roles, incluidos los dos que no se limitan a nada: un rol
#: ausente seria un rol sin recorte, y el valor por defecto de un recorte de
#: seguridad no puede ser "ninguno". Una prueba comprueba que no falte ninguno.
ALCANCE_DE_ROL: dict[Role, RoleScope] = {
    Role.ADJUSTER: RoleScope(),
    Role.ACCOUNT_AGENT: RoleScope(),
    # El suscriptor ve solo solicitudes de cotizacion **derivadas** (BR4.2): ni
    # siniestros, ni las que las reglas ya resolvieron por si solas. Una decidida
    # queda cerrada y por eso sale de su lista, que es lo que AC6.3.1 describe.
    Role.UNDERWRITER: RoleScope(record_type=RecordType.QUOTE_REQUEST, state=CaseState.DERIVED),
}


def scope_of(role: Role) -> RoleScope:
    """El alcance declarado de ese rol."""
    alcance = ALCANCE_DE_ROL.get(role)
    if alcance is None:
        msg = f"el rol '{role.value}' no declara su alcance de bandeja en `ALCANCE_DE_ROL`"
        raise UndeclaredRoleScopeError(msg)
    return alcance


@dataclass(frozen=True)
class QueueFilters:
    """Los cuatro filtros de C-05, ya comprobados contra sus conjuntos cerrados.

    El tipo de registro no esta entre ellos a proposito: no lo pide quien llama,
    lo impone el alcance del rol.
    """

    state: CaseState | None = None
    channel: Channel | None = None
    language: Locale | None = None
    priority: Priority | None = None
    #: Lo pone `narrow`, nunca la peticion.
    record_type: RecordType | None = None

    def as_repository(self) -> case_repo.ListingFilters:
        return case_repo.ListingFilters(
            state=self.state.value if self.state else None,
            channel=self.channel.value if self.channel else None,
            language=self.language,
            priority=self.priority.value if self.priority else None,
            record_type=self.record_type.value if self.record_type else None,
            excluded_states=tuple(estado.value for estado in FUERA_DE_LA_COLA),
        )


def narrow(filters: QueueFilters, *, role: Role) -> QueueFilters | None:
    """Los filtros pedidos, acotados al alcance del rol.

    Devuelve `None` cuando lo pedido y el alcance **no se cruzan** --un suscriptor
    pidiendo los cerrados, por ejemplo--: entonces la pagina sale vacia sin
    consultar nada. Es distinto de ignorar el filtro y devolver lo derivado, que
    responderia filas que nadie pidio.
    """
    alcance = scope_of(role)
    if alcance.state is not None and filters.state not in (None, alcance.state):
        return None
    return QueueFilters(
        state=alcance.state if alcance.state is not None else filters.state,
        channel=filters.channel,
        language=filters.language,
        priority=filters.priority,
        record_type=alcance.record_type,
    )


def parse_filters(
    *,
    state: str | None,
    channel: str | None,
    language: str | None,
    priority: str | None,
) -> QueueFilters:
    """Convierte los cuatro parametros de la direccion en filtros comprobados."""

    def _uno[T](crudo: str | None, enum: type[T], nombre: str) -> T | None:
        if crudo is None or crudo == "":
            return None
        try:
            return enum(crudo)  # type: ignore[call-arg]
        except ValueError as error:
            msg = f"el filtro '{nombre}' no admite ese valor"
            raise InvalidFilterError(msg) from error

    idioma: Locale | None = None
    if language:
        if language not in ("es", "en"):
            msg = "el filtro 'language' no admite ese valor"
            raise InvalidFilterError(msg)
        idioma = cast("Locale", language)

    return QueueFilters(
        state=_uno(state, CaseState, "state"),
        channel=_uno(channel, Channel, "channel"),
        language=idioma,
        priority=_uno(priority, Priority, "priority"),
    )


def encode_cursor(cursor: case_repo.ListingCursor) -> str:
    """La terna del orden, empaquetada en una cadena opaca."""
    crudo = _SEPARADOR.join(
        (str(cursor.priority_rank), cursor.updated_at.isoformat(), cursor.case_id)
    )
    return base64.urlsafe_b64encode(crudo.encode("utf-8")).decode("ascii").rstrip("=")


def decode_cursor(crudo: str | None) -> case_repo.ListingCursor | None:
    """Lee un cursor, o falla nombrando que no se pudo leer."""
    if not crudo:
        return None
    relleno = "=" * (-len(crudo) % 4)
    try:
        texto = base64.urlsafe_b64decode(crudo + relleno).decode("utf-8")
        rango, instante, case_id = texto.split(_SEPARADOR)
        return case_repo.ListingCursor(
            priority_rank=int(rango),
            updated_at=datetime.fromisoformat(instante),
            case_id=case_id,
        )
    except (binascii.Error, UnicodeDecodeError, ValueError) as error:
        msg = "el cursor no se puede leer"
        raise InvalidCursorError(msg) from error


@dataclass(frozen=True)
class QueuedCase:
    """Una fila de la cola: los seis datos con los que se decide cual abrir (BR1.2).

    Ninguno es texto libre del asegurado, asi que la fila no necesita redaccion:
    lo que lleva son enums, numeros y horas.
    """

    case_id: str
    case_number: str
    record_type: RecordType
    state: CaseState
    channel: Channel
    language: Locale
    priority: Priority
    completeness_complete: int
    completeness_total: int
    derivation_reason: str | None
    #: Desde cuando no se mueve, que **es** el tiempo de espera de BR1.2: un caso
    #: derivado no se toca mientras espera decision. La pantalla lo convierte en
    #: "hace 3 h" en su idioma; el servidor manda el instante, que es el dato, y
    #: no la frase. Se llama como lo llama C-05 y no "waiting_since", para que el
    #: contrato y el codigo digan la misma palabra.
    updated_at: datetime


@dataclass(frozen=True)
class QueuePage:
    """Una pagina de la cola y, si hay mas, por donde sigue."""

    items: tuple[QueuedCase, ...]
    next_cursor: str | None


def clamp_limit(limit: int | None) -> int:
    """El tamano de pagina pedido, dentro de lo que el contrato admite."""
    if limit is None:
        return DEFAULT_LIMIT
    return max(1, min(limit, MAX_LIMIT))


async def page(
    tenant_id: TenantId,
    *,
    filters: QueueFilters,
    role: Role,
    limit: int | None = None,
    cursor: str | None = None,
) -> QueuePage:
    """Una pagina de la cola de esa aseguradora, acotada al alcance del rol.

    La aseguradora llega ya resuelta desde la credencial: esta funcion no la
    saca de ningun sitio y no tiene forma de mirar otra, porque la politica de
    fila se aplica sobre la sesion que abre U4.

    **El rol entra aqui y no en la ruta**, por la misma razon por la que las
    acciones que ofrece un caso no las decide la pantalla: una ruta que acotara
    por su cuenta seria una segunda definicion de BR4.2, y el dia que una cambie
    la otra seguiria diciendo lo de antes.
    """
    acotados = narrow(filters, role=role)
    if acotados is None:
        return QueuePage(items=(), next_cursor=None)

    pagina = await casos.list_cases(
        tenant_id,
        filters=acotados.as_repository(),
        limit=clamp_limit(limit),
        cursor=decode_cursor(cursor),
    )
    return QueuePage(
        items=tuple(
            QueuedCase(
                case_id=fila.case_id,
                case_number=fila.case_number,
                record_type=fila.record_type,
                state=fila.state,
                channel=fila.channel,
                language=fila.language,
                priority=fila.priority,
                completeness_complete=fila.completeness.complete,
                completeness_total=fila.completeness.total,
                derivation_reason=fila.derivation_reason,
                updated_at=fila.updated_at,
            )
            for fila in pagina.items
        ),
        next_cursor=(encode_cursor(pagina.next_cursor) if pagina.next_cursor is not None else None),
    )
