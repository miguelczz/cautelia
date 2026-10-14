"""Los errores de la API con la forma de C-01, y la correlacion de cada peticion.

Todo error de la API sale como `application/problem+json` (RFC 9457) con dos
campos que la interfaz si usa --`code`, de una lista cerrada, y `trace_id`-- y
dos que **nunca muestra**: `title` y `detail` son texto tecnico en ingles para
quien depura (C-01, BR3.2). La frase que lee una persona la resuelve la interfaz
por el catalogo de textos con la clave de `code`.

**Un error no previsto sale con `code: internal` y sin detalle** (BR6.4,
SEC-U6.4): ni el tipo de la excepcion, ni su mensaje, ni una traza de pila. Lo
que paso de verdad va al evento del servidor, con el mismo `trace_id`, y ahi es
donde se busca.

## La correlacion

Cada peticion recibe un identificador de traza al entrar, con el mismo formato
que usa la telemetria para sus tramos. Viaja en la cabecera `X-Trace-Id` de toda
respuesta y en el `trace_id` de todo error (OBS-U6.2). Un canal que abra un turno
lo hereda con `current_request_trace_id()`, para que la respuesta, el error y la
traza del caso lleven el mismo valor (C-01, Correlacion).
"""

from __future__ import annotations

from collections.abc import Mapping
from contextvars import ContextVar, Token
from enum import StrEnum
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from untangle import observability
from untangle.base import Frozen

#: El tipo de contenido de un error (RFC 9457).
PROBLEM_MEDIA_TYPE = "application/problem+json"

#: La cabecera de correlacion de C-01.
TRACE_HEADER = "X-Trace-Id"


class ProblemCode(StrEnum):
    """Los codigos de error de C-01. **Lista cerrada**.

    Un codigo nuevo es un cambio aditivo solo porque la interfaz tiene una rama
    por defecto para los que no conoce (BR3.3); aun asi, se anade aqui y en el
    contrato en el mismo cambio, nunca se inventa en una ruta.
    """

    VALIDATION_FAILED = "validation_failed"
    NOT_FOUND = "not_found"
    FORBIDDEN_ORIGIN = "forbidden_origin"
    LINK_INVALID = "link_invalid"
    CONFLICT_IDEMPOTENCY = "conflict_idempotency"
    #: El estado de lo que se pidio no admite la accion: un caso ya decidido, uno
    #: cerrado que no acepta correcciones, una accion que esa aseguradora no
    #: ofrece. Distinto de `conflict_idempotency`, que es una clave reusada.
    #: Anadido el 2026-09-28 con U14, que fue la primera unidad en devolver `409`
    #: por una razon que no era la clave.
    CONFLICT_STATE = "conflict_state"
    RATE_LIMITED_SESSION = "rate_limited_session"
    RATE_LIMITED_DAILY = "rate_limited_daily"
    RATE_LIMITED_SITE = "rate_limited_site"
    BUDGET_EXHAUSTED = "budget_exhausted"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    UNVERIFIABLE = "unverifiable"
    #: Pasaron 24 horas sin un reinicio nocturno exitoso, asi que las superficies
    #: publicas no aceptan **casos nuevos** (BR3.2 de U20). Distinto de
    #: `budget_exhausted`, que es dinero, y de los tres de cuota: aqui lo que
    #: falta es la garantia de que lo que entra se borra esa noche. Lo que ya
    #: estaba abierto sigue, asi que una llamada que retoma su caso no recibe
    #: este codigo (BR3.3). Anadido el 2026-10-02 con U20.
    DEMO_CLOSED = "demo_closed"
    INTERNAL = "internal"


class Problem(Frozen):
    """El cuerpo de un error de la API (C-01, RFC 9457)."""

    type: str = "about:blank"
    #: Texto tecnico en ingles. **La interfaz no lo muestra.**
    title: str
    status: int
    #: Texto tecnico en ingles, sin datos de nadie. **La interfaz no lo muestra.**
    detail: str | None = None
    instance: str | None = None
    trace_id: str
    #: Cuando conviene volver a intentar, si aplica.
    retry_after_s: int | None = None
    code: ProblemCode


class ProblemError(Exception):
    """Lo que una ruta levanta para responder un error de C-01.

    Lleva el codigo cerrado y el estado; el cuerpo lo arma el manejador, con el
    `trace_id` de la peticion.
    """

    def __init__(
        self,
        *,
        status: int,
        code: ProblemCode,
        title: str,
        detail: str | None = None,
        retry_after_s: int | None = None,
    ) -> None:
        super().__init__(title)
        self.status = status
        self.code = code
        self.title = title
        self.detail = detail
        self.retry_after_s = retry_after_s


def unknown_route_error() -> ProblemError:
    """El error de una ruta de la API que no existe: `404 not_found`, titulo `Not found`.

    **Una sola construccion, dos usuarios.** La rama que atrapa toda ruta `/api/...`
    desconocida la levanta, y el panel de gasto la levanta ante una clave que no
    vale: "responde igual que una ruta inexistente" (SEC-U22.2) deja de ser un
    acuerdo entre dos literales y pasa a ser la misma linea. La prueba compara
    contra la ruta inexistente de verdad, asi que si alguien cambia una de las dos
    copias sin la otra --o vuelve a escribir el literal-- se cae.
    """
    return ProblemError(status=404, code=ProblemCode.NOT_FOUND, title="Not found")


# --- La correlacion de la peticion --------------------------------------------

_trace_id: ContextVar[str | None] = ContextVar("untangle_request_trace_id", default=None)


def new_trace_id() -> str:
    """Un identificador nuevo, con el formato de los tramos de la telemetria."""
    return uuid4().hex


def bind_trace_id(trace_id: str) -> Token[str | None]:
    """Fija el identificador de la peticion en curso. Devuelve la marca para soltarlo."""
    return _trace_id.set(trace_id)


def release_trace_id(token: Token[str | None]) -> None:
    """Suelta el identificador de la peticion al terminar."""
    _trace_id.reset(token)


def current_request_trace_id() -> str:
    """El identificador de la peticion en curso (C-01, Correlacion).

    Fuera de una peticion --un comando, una prueba de una funcion suelta-- se
    crea uno: un error sin `trace_id` no se podria cruzar con nada.
    """
    actual = _trace_id.get()
    return actual if actual is not None else new_trace_id()


# --- El cuerpo y los manejadores ----------------------------------------------


def problem_response(  # noqa: PLR0913 -- son los campos del error, ninguno derivable de otro
    *,
    status: int,
    code: ProblemCode,
    title: str,
    detail: str | None = None,
    retry_after_s: int | None = None,
    instance: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """La respuesta de un error, con la forma de C-01 y el `trace_id` de la peticion."""
    cuerpo = Problem(
        title=title,
        status=status,
        detail=detail,
        instance=instance,
        trace_id=current_request_trace_id(),
        retry_after_s=retry_after_s,
        code=code,
    )
    cabeceras = dict(headers) if headers is not None else {}
    if retry_after_s is not None:
        cabeceras["Retry-After"] = str(retry_after_s)
    return JSONResponse(
        cuerpo.model_dump(mode="json", exclude_none=True),
        status_code=status,
        media_type=PROBLEM_MEDIA_TYPE,
        headers=cabeceras or None,
    )


def internal_error_response() -> JSONResponse:
    """El error no previsto: `internal`, **sin detalle** (BR6.4, SEC-U6.4)."""
    return problem_response(status=500, code=ProblemCode.INTERNAL, title="Internal error")


async def _de_la_ruta(_: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, ProblemError):  # pragma: no cover -- el registro lo garantiza
        return internal_error_response()
    return problem_response(
        status=error.status,
        code=error.code,
        title=error.title,
        detail=error.detail,
        retry_after_s=error.retry_after_s,
    )


#: Que codigo lleva cada estado HTTP que levanta el propio marco. Una ruta
#: desconocida es `not_found`; un metodo que la ruta no acepta tambien lo es,
#: con su estado 405: C-01 no tiene un codigo propio para eso y no se inventa.
#: Que codigo de C-01 corresponde a cada estado que el marco levanta.
#:
#: Hasta el 2026-09-28 solo tenia `404` y `405`, asi que un `400`, un `409` o un
#: `422` levantado por una ruta respondia con codigo `internal` --"algo se rompio
#: en el servidor"-- cuando lo que habia pasado era que la peticion no valia o
#: chocaba. Lo destapo U14, que es la primera unidad que devuelve los tres. El
#: contrato C-05 ya declaraba `400` y `409`, asi que el esquema decia una cosa y
#: el servidor respondia otra.
#:
#: **Un `409` no distingue aqui entre clave reusada y estado que no admite la
#: accion**, porque una ruta no puede elegir su codigo: el vocabulario vive en
#: este modulo y las unidades estan por debajo en el contrato de capas, asi que no
#: pueden importarlo. Se escoge `conflict_state`, que es el caso general. Mover el
#: vocabulario a la raiz del paquete es de U6, su dueña, y esta anotado.
_CODIGO_POR_ESTADO: dict[int, ProblemCode] = {
    400: ProblemCode.VALIDATION_FAILED,
    404: ProblemCode.NOT_FOUND,
    405: ProblemCode.NOT_FOUND,
    409: ProblemCode.CONFLICT_STATE,
    422: ProblemCode.VALIDATION_FAILED,
}


async def _del_marco(_: Request, error: Exception) -> JSONResponse:
    if not isinstance(
        error, StarletteHTTPException
    ):  # pragma: no cover -- el registro lo garantiza
        return internal_error_response()
    codigo = _CODIGO_POR_ESTADO.get(error.status_code)
    if codigo is None:
        # Un estado que el marco levanta y que C-01 no nombra: se responde con
        # su estado y `internal`, y queda el evento para saber cual fue.
        observability.emit(
            "server.unmapped_http_status",
            status=error.status_code,
            trace_id=current_request_trace_id(),
        )
        codigo = ProblemCode.INTERNAL
    # Las cabeceras del marco se conservan: un 405 lleva `Allow`, que dice que si
    # se acepta en esa ruta.
    return problem_response(
        status=error.status_code,
        code=codigo,
        title="Request not handled",
        headers=error.headers,
    )


async def _de_validacion(_: Request, error: Exception) -> JSONResponse:
    # El detalle de validacion no se devuelve ni se registra entero: podria
    # repetir lo que envio el visitante. Al cliente le basta el codigo; al evento
    # van solo **donde** fallo --los nombres de los campos, que son del
    # esquema--, nunca con que valor.
    campos = (
        [".".join(str(parte) for parte in problema["loc"]) for problema in error.errors()]
        if isinstance(error, RequestValidationError)
        else []
    )
    observability.emit("server.request_invalid", fields=campos, trace_id=current_request_trace_id())
    return problem_response(
        status=422, code=ProblemCode.VALIDATION_FAILED, title="Request validation failed"
    )


def install_handlers(app: FastAPI) -> None:
    """Registra los tres manejadores. El no previsto lo atrapa el proceso servido."""
    app.add_exception_handler(ProblemError, _de_la_ruta)
    app.add_exception_handler(StarletteHTTPException, _del_marco)
    app.add_exception_handler(RequestValidationError, _de_validacion)


# --- El error en el esquema OpenAPI --------------------------------------------

#: Como se nombra el error en el esquema. Se declara por referencia y no con el
#: `model` de FastAPI: con `model`, el marco anade el error tambien como
#: `application/json`, y el esquema diria que un error puede llegar con dos tipos
#: de contenido cuando llega con uno solo (RFC 9457).
PROBLEM_SCHEMA_REF: dict[str, str] = {"$ref": "#/components/schemas/Problem"}


def problem_responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    """Las respuestas de error de una ruta, con la forma de C-01.

    Siempre incluye `default`: **cualquier** error de la API tiene esta forma, y
    asi el cliente generado lo tipa en todas las rutas, no solo en las que
    declaran un estado concreto.
    """
    contenido = {PROBLEM_MEDIA_TYPE: {"schema": PROBLEM_SCHEMA_REF}}
    respuestas: dict[int | str, dict[str, Any]] = {
        status: {"description": "Error with the C-01 shape", "content": contenido}
        for status in statuses
    }
    respuestas["default"] = {"description": "Error with the C-01 shape", "content": contenido}
    return respuestas


def install_openapi(app: FastAPI) -> None:
    """Genera el esquema con el error de C-01 registrado entre sus componentes.

    Es la extension que documenta FastAPI para retocar el esquema: se reemplaza
    `app.openapi` por una funcion que genera el esquema una vez y lo guarda. Lo
    unico que se anade es el componente `Problem` --y el de su codigo cerrado--,
    que las rutas nombran por referencia.
    """

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is not None:
            return app.openapi_schema
        esquema = get_openapi(
            title=app.title,
            version=app.version,
            openapi_version=app.openapi_version,
            routes=app.routes,
        )
        problema = Problem.model_json_schema(
            mode="serialization", ref_template="#/components/schemas/{model}"
        )
        anidados = problema.pop("$defs", {})
        componentes = esquema.setdefault("components", {}).setdefault("schemas", {})
        componentes.update(anidados)
        componentes["Problem"] = problema
        esquema["components"]["schemas"] = dict(sorted(componentes.items()))
        app.openapi_schema = esquema
        return esquema

    # La extension documentada del esquema de FastAPI es reemplazar el metodo;
    # el comprobador de tipos no admite asignar a un metodo sin decirlo.
    app.openapi = openapi  # type: ignore[method-assign]
