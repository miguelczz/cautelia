"""El aviso de que un caso cambio, y como se reanuda sin perder nada (BR6.1 a BR6.3).

**El identificador crece por aseguradora**, no globalmente. Es el `id:` del cable y
la posicion desde la que un navegador reanuda: con un contador global, la secuencia
que ve un inquilino tendria huecos --los numeros que se llevaron los eventos de
otras-- y quien pidiera desde el ultimo hueco recibiria eventos ajenos o ninguno.

**Se guarda y no solo se emite.** El navegador que se reconecta manda
`Last-Event-ID` y el servidor reproduce lo posterior (ADR-021); eso exige que los
eventos existan **despues** de haberse entregado. Sin esto, una reconexion deja la
cola mostrando un estado viejo sin que nadie lo note, que es peor que no
actualizarse.

**El resumen va redactado al escribirse, no al leerse** (BR6.3). Un evento guardado
con texto sin redactar es un punto de salida sin redaccion aunque nadie lo lea
todavia, y el reporte de redaccion lo encontraria en la tabla.

**Que el numero sea por aseguradora lo impone la politica de fila, no el `WHERE`.**
Se comprobo rompiendo: quitar `WHERE tenant_id = :tenant_id` del `MAX` no tumba
ninguna prueba, porque la politica ya filtra la tabla antes de que la consulta mire
--el `MAX` global es inalcanzable desde el punto unico de sesion--. El filtro se
escribe igual, como segunda copia y porque hace la consulta legible, pero no hay que
confundirlo con el cerrojo. Es la misma leccion que la tanda 1 dejo escrita sobre la
credencial y la cola, y la segunda vez que aparece en esta unidad.

**El numero se reserva dentro de la misma transaccion que inserta.** Se calcula con
`MAX(event_id) + 1` de esa aseguradora y la llave primaria compuesta es lo que
decide si hubo carrera: dos escrituras a la vez chocan y una reintenta. Calcularlo
fuera de la transaccion y confiar en que no colisione seria confiar en que dos
pestanas no cierran un caso a la vez, que es justo lo que pasa.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from untangle import observability
from untangle.base import Locale
from untangle.compliance.redaction.api import redact
from untangle.tenancy import api as tenancy
from untangle.tenancy.models import TenantId

#: Cuantas veces se reintenta cuando dos escrituras se pelean el mismo numero. Dos
#: pestanas a la vez es el caso normal; tres colisiones seguidas sobre la misma
#: aseguradora ya no son una carrera, son un fallo que hay que ver.
REINTENTOS = 3


class EventKind(StrEnum):
    """Los tres tipos de C-06. Conjunto cerrado: un cuarto es un cambio de contrato."""

    CASE_CREATED = "case_created"
    CASE_UPDATED = "case_updated"
    CASE_DECIDED = "case_decided"


@dataclass(frozen=True)
class InboxEvent:
    """Un aviso tal como esta en la base y tal como sale por el cable."""

    event_id: int
    case_id: str
    kind: EventKind
    summary_redacted: str
    created_at: datetime


_INSERTAR = """
    INSERT INTO inbox_event (tenant_id, event_id, case_id, kind, summary_redacted, created_at)
    SELECT :tenant_id,
           COALESCE((SELECT MAX(event_id) FROM inbox_event WHERE tenant_id = :tenant_id), 0) + 1,
           :case_id, :kind, :summary_redacted, :created_at
    ON CONFLICT (tenant_id, event_id) DO NOTHING
    RETURNING event_id
"""

_DESDE = """
    SELECT event_id, case_id, kind, summary_redacted, created_at
    FROM inbox_event
    WHERE tenant_id = :tenant_id AND event_id > :desde
    ORDER BY event_id
    LIMIT :limite
"""

_ULTIMO = """
    SELECT COALESCE(MAX(event_id), 0) AS ultimo FROM inbox_event WHERE tenant_id = :tenant_id
"""

#: Cuantos eventos se reproducen de una reconexion. No es un umbral de calidad: es
#: lo que impide que una pestana abierta toda la noche pida diez mil eventos de
#: golpe. Quien se pasa de aqui recibe los mas recientes y **lo sabe**, porque el
#: flujo le dice que refresque; perder eventos en silencio es lo que BR6.2 prohibe.
MAXIMO_REPRODUCIDO = 500


async def append(  # noqa: PLR0913 -- los cinco datos de un aviso mas el reloj
    tenant_id: TenantId,
    *,
    case_id: str,
    kind: EventKind,
    summary: str,
    language: Locale,
    now: datetime,
) -> InboxEvent:
    """Escribe un aviso con el siguiente numero de esa aseguradora.

    El resumen se redacta **aqui**, antes de escribirlo: quien llama no tiene que
    acordarse, y por eso no puede olvidarse.
    """
    redactado = str(redact(summary, language=language))
    for intento in range(REINTENTOS):
        async with tenancy.session_for(tenant_id) as sesion:
            fila = await tenancy.fetch_one(
                sesion,
                _INSERTAR,
                tenant_id=tenant_id,
                case_id=case_id,
                kind=kind.value,
                summary_redacted=redactado,
                created_at=now,
            )
        if fila is None:
            # Otra escritura tomo el numero entre el `MAX` y el `INSERT`. El
            # `ON CONFLICT` la detecta sin levantar --el contrato de importaciones
            # no deja que una unidad conozca las excepciones del motor-- y se
            # reintenta. Sin la llave primaria compuesta, la segunda habria pisado
            # a la primera en vez de chocar.
            observability.emit("inbox.event_id_collision", tenant_id=tenant_id, attempt=intento + 1)
            continue
        return InboxEvent(
            event_id=int(fila["event_id"]),
            case_id=case_id,
            kind=kind,
            summary_redacted=redactado,
            created_at=now,
        )

    msg = (
        f"no se pudo numerar un aviso de '{tenant_id}' en {REINTENTOS} intentos; "
        "tres carreras seguidas sobre la misma aseguradora no son concurrencia normal"
    )
    raise RuntimeError(msg)


async def since(tenant_id: TenantId, last_event_id: int) -> tuple[InboxEvent, ...]:
    """Los avisos posteriores a ese identificador, en orden.

    Es la mitad que hace util guardar los eventos: una reconexion pide desde donde
    se quedo y recibe lo que se perdio, en vez de seguir mostrando un estado viejo.
    """
    async with tenancy.session_for(tenant_id) as sesion:
        filas = await tenancy.fetch_all(
            sesion, _DESDE, tenant_id=tenant_id, desde=last_event_id, limite=MAXIMO_REPRODUCIDO
        )
    return tuple(
        InboxEvent(
            event_id=int(fila["event_id"]),
            case_id=str(fila["case_id"]),
            kind=EventKind(fila["kind"]),
            summary_redacted=str(fila["summary_redacted"]),
            created_at=fila["created_at"],
        )
        for fila in filas
    )


async def last_event_id(tenant_id: TenantId) -> int:
    """El ultimo numero entregado a esa aseguradora, o cero si no hay ninguno.

    Lo pide quien abre el flujo **sin** `Last-Event-ID`: se coloca al final y recibe
    lo que venga, en vez de que le reproduzcan el historial entero de la demostracion.
    """
    async with tenancy.session_for(tenant_id) as sesion:
        fila = await tenancy.fetch_one(sesion, _ULTIMO, tenant_id=tenant_id)
    return int(fila["ultimo"]) if fila is not None else 0


def parse_last_event_id(cabecera: str | None) -> int | None:
    """Lee la cabecera `Last-Event-ID`, o nada si no vale.

    Una cabecera ilegible **no** se trata como "desde el principio": reproducir todo
    a quien mando basura le daria eventos que ya vio. Se trata como si no la hubiera
    mandado, que es colocarse al final.
    """
    if cabecera is None:
        return None
    try:
        numero = int(cabecera)
    except ValueError:
        return None
    return numero if numero >= 0 else None
