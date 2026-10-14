"""El proceso servido: la interfaz y la API desde el mismo origen (BR6.1 a BR6.4).

Tres ramas, decididas por la ruta y en este orden (BR6.1):

1. **`/api/...`** la atiende la API. Una ruta que no existe responde `404` con
   `code: not_found` y la forma de C-01, **nunca la aplicacion**: un cliente que
   pide JSON y recibe HTML se rompe de la peor manera, en silencio.
2. **Un archivo compilado** se sirve tal cual desde `app/frontend/dist/`
   (CG-U6-5). Los que llevan huella de contenido en el nombre se marcan
   inmutables por un ano; los demas se revalidan en cada carga (BR6.3).
3. **Cualquier otra ruta** devuelve la pagina de entrada, **sin cache**, para que
   el enrutador de la interfaz dibuje la pantalla o "no encontrada", y para que
   un despliegue nuevo se vea en la siguiente carga (BR6.3).

Sin la interfaz compilada, las rutas de la interfaz responden el error de
servicio no disponible de la API (CG-U6-5): el camino de los quince minutos
(NFR21) no compila la interfaz y no tiene por que.

## Comprimido si el navegador lo acepta

La compilacion deja junto a cada archivo de texto su version brotli (`.br`) y
gzip (`.gz`); el proceso sirve la que el navegador acepta, con el tipo del
original y `Vary: Accept-Encoding`. Es lo que hace que la pagina de espera pese
lo que mide PERF-U6.1 --el peso **comprimido** de lo que se descarga antes de
pintarla-- y no el triple. Se comprime al compilar y no en cada peticion, y solo
estaticos: una respuesta de la API no se comprime, porque mezclar un secreto y
un texto del visitante en un cuerpo comprimido es la puerta de un ataque de
compresion, y la API no gana nada que lo justifique.

## Lo que lleva toda respuesta

El intermediario de este modulo envuelve la aplicacion entera y pone en **toda**
respuesta --las tres ramas, los errores y el error no previsto-- el conjunto
unico de cabeceras de seguridad (BR6.2) y el identificador de traza (BR6.4,
OBS-U6.2). Por eso el error no previsto lo atrapa aqui y no un manejador del
marco: el marco responde ese error **fuera** de todo intermediario, y la
respuesta saldria sin cabeceras justo cuando algo fallo.
"""

from __future__ import annotations

import mimetypes
import re
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from starlette.datastructures import MutableHeaders
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from untangle import observability
from untangle.server.problems import (
    TRACE_HEADER,
    ProblemCode,
    bind_trace_id,
    internal_error_response,
    new_trace_id,
    problem_response,
    release_trace_id,
    unknown_route_error,
)
from untangle.server.security_headers import headers_for

#: La pagina de entrada que compila Vite.
ENTRY_FILE = "index.html"

#: Un archivo con huella de contenido: Vite los deja en `assets/` con un resumen
#: en el nombre (`index-DPw5nODq.js`). Si el contenido cambia, cambia el nombre,
#: y por eso pueden guardarse un ano sin riesgo de servir uno viejo.
HASHED_ASSET = re.compile(r"^assets/[^/]+-[A-Za-z0-9_-]{8,}\.[A-Za-z0-9]+$")

CACHE_IMMUTABLE = "public, max-age=31536000, immutable"
#: La pagina de entrada no se guarda nunca: es la que nombra los archivos con
#: huella del despliegue en curso.
CACHE_NEVER = "no-store"
#: Lo que no lleva huella --el paso de modo, un icono-- se guarda pero se
#: revalida en cada carga.
CACHE_REVALIDATE = "no-cache"

#: Los metodos del catch-all de la API. Todos: cualquier combinacion de metodo y
#: ruta que la API no atiende es `not_found`, y nunca cae en la aplicacion.
_METODOS = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]


class ServedProcessMiddleware:
    """Traza y cabeceras de seguridad en **toda** respuesta; el no previsto, en C-01."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        traza = new_trace_id()
        marca = bind_trace_id(traza)
        cabeceras = (*headers_for(https=scope.get("scheme") == "https"), (TRACE_HEADER, traza))
        empezada = False

        async def enviar(message: Message) -> None:
            nonlocal empezada
            if message["type"] == "http.response.start":
                empezada = True
                propias = MutableHeaders(scope=message)
                for nombre, valor in cabeceras:
                    propias[nombre] = valor
            await send(message)

        try:
            await self.app(scope, receive, enviar)
        except Exception as error:
            # Lo que paso de verdad va al evento, con la traza que lleva la
            # respuesta; al cliente, `internal` sin detalle (BR6.4, SEC-U6.4).
            # La ruta va como plantilla y no tal cual: una ruta real puede
            # nombrar un caso o llevar un token.
            ruta = getattr(scope.get("route"), "path", None)
            observability.emit(
                "server.unhandled_error",
                error_type=type(error).__name__,
                route=ruta,
                trace_id=traza,
            )
            if empezada:
                # La respuesta ya salio a medias: no se puede mandar otra. Se
                # deja al servidor cortar la conexion, que es lo honesto.
                raise
            await internal_error_response()(scope, receive, enviar)
        finally:
            release_trace_id(marca)


def cache_control_for(relative: str) -> str:
    """Cuanto se puede guardar un archivo compilado, por su nombre (BR6.3)."""
    if relative == ENTRY_FILE:
        return CACHE_NEVER
    if HASHED_ASSET.match(relative):
        return CACHE_IMMUTABLE
    return CACHE_REVALIDATE


def _no_compilada() -> Response:
    """La interfaz no esta compilada: servicio no disponible, con la forma de C-01."""
    return problem_response(
        status=503,
        code=ProblemCode.PROVIDER_UNAVAILABLE,
        title="Interface not built",
        detail="Run `mise run web:build` to serve the interface.",
    )


#: Las codificaciones precomprimidas, en orden de preferencia, con su extension.
ENCODINGS: tuple[tuple[str, str], ...] = (("br", ".br"), ("gzip", ".gz"))


def _acepta(accept_encoding: str, codificacion: str) -> bool:
    """Si la cabecera `Accept-Encoding` admite una codificacion (sin `q=0`)."""
    for parte in accept_encoding.lower().split(","):
        nombre, _, parametros = parte.strip().partition(";")
        if nombre.strip() == codificacion:
            return parametros.replace(" ", "") not in {"q=0", "q=0.0"}
    return False


def _archivo(original: Path, cache: str, accept_encoding: str) -> Response:
    """El archivo, o su version comprimida si existe y el navegador la acepta."""
    tipo = mimetypes.guess_type(original.name)[0] or "application/octet-stream"
    cabeceras = {"Cache-Control": cache, "Vary": "Accept-Encoding"}
    for codificacion, extension in ENCODINGS:
        comprimido = original.with_name(original.name + extension)
        if _acepta(accept_encoding, codificacion) and comprimido.is_file():
            return FileResponse(
                comprimido,
                media_type=tipo,
                headers={**cabeceras, "Content-Encoding": codificacion},
            )
    return FileResponse(original, media_type=tipo, headers=cabeceras)


def serve_interface(dist_dir: Path, requested: str, accept_encoding: str = "") -> Response:
    """Un archivo compilado si existe dentro de `dist`; si no, la pagina de entrada.

    La ruta pedida se resuelve y se exige que quede **dentro** de `dist`: una
    ruta con `..` o un enlace simbolico que apunte fuera no sirve nada de fuera,
    cae en la pagina de entrada como cualquier ruta que no es un archivo.
    """
    raiz = dist_dir.resolve()
    entrada = raiz / ENTRY_FILE
    if not entrada.is_file():
        return _no_compilada()

    if requested:
        candidato = (raiz / requested).resolve()
        if candidato.is_relative_to(raiz) and candidato.is_file():
            relativo = candidato.relative_to(raiz).as_posix()
            return _archivo(candidato, cache_control_for(relativo), accept_encoding)

    return _archivo(entrada, CACHE_NEVER, accept_encoding)


def install(app: FastAPI, *, dist_dir: Path) -> None:
    """Las dos ultimas ramas del proceso servido y el intermediario de toda respuesta.

    Se instala **despues** de todas las rutas de la API: el enrutador prueba las
    rutas en orden, y estas dos atrapan todo lo que quede.
    """

    @app.api_route("/api/{rest:path}", methods=_METODOS, include_in_schema=False)
    async def api_desconocida(rest: str) -> Response:
        del rest
        raise unknown_route_error()

    @app.api_route("/{requested:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def interfaz(requested: str, request: Request) -> Response:
        return serve_interface(dist_dir, requested, request.headers.get("accept-encoding", ""))

    app.add_middleware(ServedProcessMiddleware)
