"""El transporte de trazas hacia Langfuse Cloud: entregar, pedir el proyecto y borrar.

Langfuse entra al proyecto como **un transporte mas** de `telemetry/traces/export.py`,
no como un camino nuevo: recibe un lote que ya paso por el punto unico de redaccion
(`send` exige `Redacted`, el mismo tipo que exige el de archivo) y lo manda por HTTP.
Lo unico que el lote tiene de propio es su forma, que este transporte pide con
`wire_format`.

## Las tres cosas que hace, y por que las tres viven aqui

1. **Entregar** un lote: `POST /api/public/otel/v1/traces`, OTLP por HTTP/JSON, con
   autenticacion basica (`public:secret` en base64) y la cabecera de ingestion v4, que
   es la que le dice a Langfuse que lo muestre al momento y no diez minutos despues.
2. **Pedir el identificador del proyecto** (`GET /api/public/projects`), que el
   enlace a una traza necesita (`{host}/project/{projectId}/traces/{traceId}`) y que
   solo se sabe preguntandole a Langfuse con la clave.
3. **Borrar** lo anterior a un corte (`purge_before`), para el reinicio nocturno:
   `GET /api/public/traces?toTimestamp=...` lista y `DELETE /api/public/traces` con
   `{"traceIds": [...]}` borra de a mil como maximo. El borrado de Langfuse es
   asincrono: la peticion se acepta y la traza desaparece despues, asi que "borrada"
   aqui quiere decir "aceptada para borrar".

Las tres comparten el cliente HTTP porque comparten la clave, y la clave **entra en el
constructor y se queda dentro del cliente**, en su cabecera. No es un atributo propio,
ningun metodo la devuelve, ningun error la nombra y `__repr__` no la imprime (capa 2
del diseno de seguridad, igual que en el adaptador de Gemini).

## Sin reintentos, con plazo corto

Cinco segundos y un solo intento. El fallo no se esconde aqui: `export_batch` lo
registra y marca perdidos los resumenes, que es lo que BR6.7 pide del backend caido.
Reintentar en este adaptador retrasaria el siguiente ciclo y no cambiaria el resultado.

## Sin el SDK de Langfuse ni el de OpenTelemetry

El exportador del SDK entrega por su cuenta y esquivaria la redaccion (ver el
encabezado de `telemetry/traces/api.py`). `httpx2` ya es dependencia de ejecucion.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx2

from untangle import observability
from untangle.compliance.redaction.api import Redacted
from untangle.settings import Settings
from untangle.telemetry.traces.export import RemotePurge, WireFormat

__all__ = ["LangfuseError", "LangfuseTransport", "build_transport"]

#: La ruta de ingestion OTLP de Langfuse. Acepta HTTP/JSON y protobuf, no gRPC.
INGEST_PATH = "/api/public/otel/v1/traces"
PROJECTS_PATH = "/api/public/projects"
TRACES_PATH = "/api/public/traces"
#: Por donde se listan las trazas para borrarlas. La lista de trazas de antes
#: (`GET /api/public/traces`) responde `410` en los proyectos nuevos de Langfuse v4,
#: comprobado el 2026-10-14 contra el proyecto local; la de observaciones v2 es la
#: que la reemplaza, y cada observacion trae el `traceId` de su traza.
OBSERVATIONS_PATH = "/api/public/v2/observations"

#: Plazo de cada peticion. Corto a proposito: la entrega corre en un hilo del ciclo
#: de exportacion y un destino que no contesta no puede retenerlo.
TIMEOUT_SECONDS = 5.0

#: Cuantas observaciones pide por pagina el borrado: el maximo que admite la lista v2.
_PAGE_SIZE = 1000

#: Cuantas paginas lee como maximo una corrida de borrado (cien mil observaciones, unas
#: diez mil trazas). Una demo no llega a eso en una noche; si llegara, la corrida queda
#: incompleta y la siguiente sigue.
_MAX_PAGES = 100

#: Desde cuando se lista hacia atras. La lista v2 pide los dos extremos; el plan gratuito
#: deja ver treinta dias, y noventa cubre de sobra lo que una corrida anterior no alcanzo.
_LIST_WINDOW = timedelta(days=90)

#: Cuantas trazas manda cada peticion de borrado. Langfuse admite mil.
_DELETE_CHUNK = 500


class LangfuseError(RuntimeError):
    """Langfuse no contesto, o contesto con algo que no es un exito.

    El mensaje es un codigo corto --`timeout`, `http_401`, `ConnectError`-- y **nunca**
    lleva la direccion con la clave, una cabecera ni el cuerpo de la respuesta: este
    error acaba en un registro.
    """


class LangfuseTransport:
    """Un cliente de Langfuse con su clave dentro. Cumple `SpanTransport`.

    `network` solo existe para las pruebas: un transporte de `httpx2` falso, para no
    salir a la red.
    """

    #: La forma del lote que Langfuse lee. `export_batch` la consulta antes de serializar.
    wire_format = WireFormat.LANGFUSE

    def __init__(
        self,
        *,
        public_key: str,
        secret_key: str,
        host: str,
        timeout_seconds: float = TIMEOUT_SECONDS,
        network: httpx2.BaseTransport | None = None,
    ) -> None:
        self._host = host
        # La clave se codifica aqui y se queda en las cabeceras del cliente. **No se
        # guarda como atributo propio**: lo que no existe no se puede imprimir.
        autenticacion = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode("ascii")
        self._cliente = httpx2.Client(
            base_url=host,
            headers={
                "Authorization": f"Basic {autenticacion}",
                # Sin esto, lo que se manda directo a Langfuse puede tardar hasta diez
                # minutos en verse; con esto, se ve al momento.
                "x-langfuse-ingestion-version": "4",
            },
            timeout=httpx2.Timeout(timeout_seconds),
            transport=network,
        )

    def __repr__(self) -> str:
        """Nombra el destino. Nunca la clave, ni el cliente que la lleva dentro."""
        return f"LangfuseTransport(host={self._host})"

    def close(self) -> None:
        self._cliente.close()

    # --- Lo que pide una peticion -------------------------------------------

    def _pedir(self, metodo: str, ruta: str, **argumentos: Any) -> httpx2.Response:
        """Una peticion; todo lo que no sea un exito sale como `LangfuseError` sin detalle.

        El error se levanta **fuera** del `except`, a proposito: levantado dentro, el
        error de red quedaria colgado como contexto del nuestro, y un mensaje de red
        puede traer la direccion o una cabecera. Asi el contexto es vacio y no hay nada
        que un registro pueda imprimir por descuido.
        """
        codigo: str | None = None
        respuesta: httpx2.Response | None = None
        try:
            respuesta = self._cliente.request(metodo, ruta, **argumentos)
        except httpx2.TimeoutException:
            codigo = "timeout"
        except (httpx2.HTTPError, httpx2.InvalidURL) as fallo:
            codigo = type(fallo).__name__
        if respuesta is None:
            raise LangfuseError(codigo or "unknown")
        if not 200 <= respuesta.status_code < 300:
            raise LangfuseError(f"http_{respuesta.status_code}")
        return respuesta

    # --- Entregar ------------------------------------------------------------

    def send(self, payload: Redacted) -> None:
        """Manda un lote ya redactado. Cualquier respuesta que no sea 2xx es un fallo."""
        self._pedir(
            "POST",
            INGEST_PATH,
            content=str(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

    # --- El identificador del proyecto ----------------------------------------

    def project_id(self) -> str:
        """El identificador del proyecto al que pertenece la clave."""
        respuesta = self._pedir("GET", PROJECTS_PATH)
        try:
            identificador = respuesta.json()["data"][0]["id"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise LangfuseError("projects_shape") from None
        if not isinstance(identificador, str) or not identificador:
            raise LangfuseError("projects_shape")
        return identificador

    # --- Borrar lo anterior a un corte -----------------------------------------

    def purge_before(self, cutoff: datetime, *, dry_run: bool = False) -> RemotePurge:
        """Borra las trazas anteriores al corte, de a lotes. **No levanta**: devuelve que paso.

        Primero se lista **todo** lo anterior al corte y despues se borra: borrar mientras
        se lista corre la lista (y Langfuse borra de forma asincrona, asi que una traza ya
        pedida puede seguir apareciendo). Si algo falla a mitad, lo ya aceptado para borrar
        se cuenta y el resto se dice en `failure`: la corrida siguiente retoma, porque el
        corte es el mismo criterio.
        """
        identificadores, fallo = self._listar(cutoff)

        if dry_run:
            return RemotePurge(deleted=len(identificadores), failure=fallo)

        borradas = 0
        for inicio in range(0, len(identificadores), _DELETE_CHUNK):
            lote = identificadores[inicio : inicio + _DELETE_CHUNK]
            try:
                self._pedir("DELETE", TRACES_PATH, json={"traceIds": lote})
            except LangfuseError as error:
                return RemotePurge(deleted=borradas, failure=fallo or f"delete_{error}")
            borradas += len(lote)
        return RemotePurge(deleted=borradas, failure=fallo)

    def _listar(self, corte: datetime) -> tuple[list[str], str | None]:
        """Los identificadores de las trazas anteriores al corte, y por que no son todos.

        Se recorren las observaciones v2 con su cursor y se juntan sus `traceId` sin repetir:
        una traza de un turno trae varias observaciones (el turno, cada nodo, cada llamada).
        """
        vistos: dict[str, None] = {}
        consulta: dict[str, str | int] = {
            "fromStartTime": _instante(corte - _LIST_WINDOW),
            "toStartTime": _instante(corte),
            "limit": _PAGE_SIZE,
            # Solo lo esencial de cada observacion: aqui no se lee nada mas que su traza.
            "fields": "core",
        }
        for pagina in range(1, _MAX_PAGES + 1):
            try:
                cuerpo = self._pedir("GET", OBSERVATIONS_PATH, params=consulta).json()
                datos = cuerpo["data"]
                siguiente = cuerpo.get("meta", {}).get("cursor")
            except LangfuseError as error:
                return list(vistos), f"list_{error}"
            except (ValueError, KeyError, TypeError, AttributeError):
                return list(vistos), "list_shape"
            if not isinstance(datos, list):
                return list(vistos), "list_shape"
            for observacion in datos:
                if isinstance(observacion, dict) and isinstance(observacion.get("traceId"), str):
                    vistos[observacion["traceId"]] = None
            if not datos or not siguiente:
                return list(vistos), None
            if pagina == _MAX_PAGES:
                break
            consulta = {**consulta, "cursor": str(siguiente)}
        observability.emit("traces.langfuse_purge_page_cap", pages=_MAX_PAGES)
        return list(vistos), "list_page_cap"


def _instante(momento: datetime) -> str:
    """Un instante como lo lee la lista v2 de Langfuse: UTC, al segundo, con `Z`."""
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_transport(settings: Settings) -> LangfuseTransport | None:
    """El transporte de Langfuse si las tres variables estan puestas, y `None` si no.

    **El unico sitio que construye el cliente de Langfuse**, igual que la fabrica de
    proveedores lo es de los de modelo. Sin las tres variables no hay transporte y
    nada de lo que depende de el corre.
    """
    publica = settings.langfuse_public_key
    secreta = settings.langfuse_secret_key
    direccion = settings.langfuse_host
    if not (publica and secreta and direccion):
        return None
    return LangfuseTransport(public_key=publica, secret_key=secreta, host=direccion)
