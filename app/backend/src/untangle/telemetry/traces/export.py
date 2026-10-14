"""La exportacion de trazas: por lotes, fuera del camino de la respuesta.

Tres decisiones que este archivo hace cumplir, y una que hace **imposible**:

- **Por lotes y fuera del camino de la respuesta.** Cerrar un tramo no exporta
  nada: lo deja en el registrador. Exportar lo dispara quien tiene derecho a
  tardar --la raiz de composicion, la tuberia-- llamando a `export_pending`. Que
  no se pueda hacer de otra forma no es disciplina: `api.py` **no importa** este
  modulo, asi que desde el camino de la respuesta no hay a quien llamar.
- **Al backend cuando hay destino, al archivo cuando no.** El destino es
  `UNTANGLE_TRACES_ENDPOINT`, que ya existe en `settings.py` y es **opcional**.
  Sin destino se escribe el archivo OTLP de la corrida, que es lo que hace la
  tuberia, donde no cabe un backend de trazas.
- **Todo pasa por la redaccion de U3 antes de salir** (BR6.5). No porque quede
  texto --la lista cerrada de `api.py` ya lo impide-- sino porque la regla del
  proyecto dice que ninguna salida esquiva ese punto. Una excepcion "porque aqui
  no hace falta" es exactamente como se pierde esa propiedad.
- **Si el destino no responde, se registra la perdida y nada mas se detiene**
  (BR4.8, BR6.7). Ni el caso, ni el gasto, ni el corte. Por eso `export_pending`
  no levanta nunca: devuelve lo que paso.

## El punto unico de salida, no uno nuevo

U3 declara los seis puntos de salida del aplicativo en un registro cerrado, y
**dos son de esta unidad**: `trace_span` y `trace_export`. Este modulo implementa
el segundo y lo **busca por su nombre en ese registro** en vez de dar por hecho
que esta: si alguien lo quitara de la lista, esto falla al importarse con su
nombre, en vez de convertirse en un septimo punto de salida sin redaccion.

El tipo lo impone tambien: `SpanTransport.send` exige `Redacted`, y `Redacted`
solo lo produce `compliance/redaction/api.py` --lo comprueba el chequeo
`redaction:constructor`--. Un transporte que aceptara `str` seria la segunda via
que esta unidad no tiene.

## Sin el SDK de OpenTelemetry, y por que se queda asi

El bloque F **no instala** `opentelemetry-exporter-otlp`, y la razon es este
archivo: su exportador entrega tramos por su cuenta, y aqui el orden es
serializar, **redactar** y solo entonces entregar. Un exportador que saliera solo
seria un septimo punto de salida sin redaccion (BR6.5, regla de `project.md`).
La razon entera esta en el encabezado de `api.py`.

Lo que hay son dos transportes propios: el de archivo, que es real y completo y
es el que usa la tuberia, y el del backend, que **declara la perdida** mientras
no haya exportador instalado. El dia que se adopte el SDK, lo que se instala en
`install_transport` es un transporte que envuelva su exportador **despues** de
la redaccion; el tipo lo impone, porque `SpanTransport.send` exige `Redacted` y
ese tipo solo lo produce el punto unico de U3.

La forma del cable no depende de esa decision: `otlp_payload` escribe OTLP/JSON,
que es el **protocolo** y no la biblioteca.

## Langfuse es un transporte mas, no un camino nuevo

El backend de trazas del proyecto es Langfuse Cloud, y su transporte vive en su
adaptador (`providers/adapters/langfuse/`). Lo que le llega es **lo mismo**: un
lote ya serializado y ya redactado. Lo unico que cambia es la forma del lote, que
Langfuse lee con sus propios atributos (`langfuse.session.id`, el tipo de
observacion, el costo...) y con identificadores de tramo de 8 bytes, como manda
OTLP. Esa forma la pide el propio transporte con `wire_format`, y `otlp_payload`
la escribe: se **derivan** de lo que el tramo ya lleva (`langfuse_shape.py`), nunca
se anade texto, y se hace antes de redactar, asi que el orden serializar,
redactar y entregar no cambia.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from untangle import observability, paths
from untangle.base import Locale
from untangle.compliance.redaction import sinks
from untangle.compliance.redaction.api import Redacted, RedactionFailedError, redact
from untangle.settings import Settings
from untangle.telemetry.traces import api, langfuse_shape


#: El punto de salida de esta unidad, buscado en el registro cerrado de U3. Si
#: dejara de estar declarado, esto falla aqui --al importar-- y no callando.
def _punto_de_salida_declarado() -> sinks.OutputSink:
    declarado = next((s for s in sinks.SINKS if s.name == "trace_export"), None)
    if declarado is None:  # pragma: no cover - el registro es una tupla literal
        msg = (
            "'trace_export' no esta en el registro de puntos de salida de U3. Un "
            "punto de salida que no esta declarado es un punto de salida sin "
            "revision, y esta unidad no inventa uno propio"
        )
        raise RuntimeError(msg)
    return declarado


_SINK = _punto_de_salida_declarado()

#: El idioma con el que se redacta lo que sale hacia el backend de trazas.
#:
#: Ingles, y es una consecuencia de la convencion 4 del equipo: identificadores,
#: enums, claves y **logs tecnicos** van en ingles. Un rastro no es texto que lea
#: una persona no tecnica, asi que no sale del catalogo de copy. El idioma solo
#: decide en que idioma se escribiria la etiqueta de un hallazgo; los
#: reconocedores de los dos idiomas corren igual (BR2.9 de U3).
EXPORT_LOCALE: Locale = "en"


class WireFormat(StrEnum):
    """La forma del lote que un transporte sabe leer.

    `OTLP` es la del archivo de la corrida. `LANGFUSE` es la misma OTLP/JSON con
    los atributos y los identificadores que Langfuse espera. Un transporte que
    no dice nada recibe `OTLP`.
    """

    OTLP = "otlp"
    LANGFUSE = "langfuse"


class SpanTransport(Protocol):
    """Por donde sale un lote ya redactado.

    Exige `Redacted` a proposito: es lo que hace que no exista una via que
    esquive la redaccion, en vez de que no se use.

    Un transporte puede declarar ademas un atributo `wire_format` (`WireFormat`)
    si necesita otra forma del lote; no es obligatorio, y por eso no esta en el
    protocolo: los transportes que no lo declaran reciben OTLP.
    """

    def send(self, payload: Redacted) -> None: ...


@dataclass(frozen=True)
class RemotePurge:
    """Lo que un backend remoto hizo al barrer lo anterior al corte.

    `deleted` son las trazas que el backend **acepto borrar** (el borrado de
    Langfuse es asincrono: la peticion se acepta y la traza desaparece despues).
    `failure` dice por que no se termino, y vacio es que se termino.
    """

    deleted: int
    failure: str | None = None

    @property
    def complete(self) -> bool:
        return self.failure is None


@runtime_checkable
class PurgeableSpanTransport(SpanTransport, Protocol):
    """Un transporte que ademas sabe borrar lo que ya entrego (reinicio nocturno).

    El purgador de `purge.py` le pregunta por este metodo en vez de conocer a
    ningun backend: la direccion y la credencial son del transporte, y las capas
    de abajo no pueden importar al adaptador que las tiene.
    """

    def purge_before(self, cutoff: datetime, *, dry_run: bool = False) -> RemotePurge: ...


@dataclass(frozen=True)
class ExportResult:
    """Que paso con el lote. **No se levanta**: se devuelve.

    Levantar dejaria que la caida del backend de trazas se propagara hacia quien
    llamo, y quien llama es el ritmo de fondo del turno.
    """

    exported: int
    #: Por que no salio, cuando no salio. `None` es que si salio.
    failure: str | None = None

    @property
    def ok(self) -> bool:
        return self.failure is None


class FileTransport:
    """Escribe el archivo OTLP de la corrida, una linea por lote.

    Es lo que hace la tuberia, donde no cabe un backend de trazas, y lo que el
    reporte enlaza junto al identificador de traza.
    """

    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path

    def send(self, payload: Redacted) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as destino:
            destino.write(payload + "\n")


class UnavailableTransport:
    """Hay destino declarado y no hay exportador instalado todavia.

    **Este es el punto de extension del SDK de OpenTelemetry**: el dia que se
    adopte, un transporte que envuelva su exportador se instala con
    `install_transport` --despues de la redaccion, que el tipo impone-- y esta
    clase deja de construirse. Mientras tanto no finge: levanta, `export_pending`
    lo atrapa, registra la perdida y sigue, que es exactamente la conducta que
    BR6.7 pide del backend caido.
    """

    def __init__(self, endpoint: str) -> None:
        self._endpoint = endpoint

    def send(self, payload: Redacted) -> None:
        msg = (
            f"hay destino de trazas declarado ('{self._endpoint}') y no hay "
            "exportador OTLP instalado. "
            "Se registra la perdida y nada se detiene"
        )
        raise TransportUnavailableError(msg)


class TransportUnavailableError(RuntimeError):
    """El transporte no puede entregar el lote. Se registra, no se propaga."""


_transport: SpanTransport | None = None


def install_transport(transport: SpanTransport | None) -> None:
    """Fija el transporte del proceso. `None` vuelve a resolverlo por la configuracion."""
    global _transport
    _transport = transport


def default_run_file() -> Path:
    """El archivo OTLP de la corrida, cuando no hay destino declarado."""
    return paths.reports_dir() / "traces.otlp.jsonl"


def transport_for(settings: Settings) -> SpanTransport:
    """El transporte instalado, o el que la configuracion pide."""
    if _transport is not None:
        return _transport
    if settings.traces_endpoint:
        return UnavailableTransport(settings.traces_endpoint)
    return FileTransport(default_run_file())


def _instante(momento: datetime) -> int:
    """Nanosegundos desde la epoca, que es como OTLP cuenta el tiempo."""
    return int(momento.timestamp() * 1_000_000_000)


def _valor_otlp(valor: langfuse_shape.AttributeValue, *, wire: WireFormat) -> dict[str, Any]:
    """Un valor de atributo en la forma `AnyValue` de OTLP/JSON.

    Los enteros de 64 bits van como **texto** en la forma de Langfuse, que es como
    el protocolo los escribe en JSON; en la del archivo de la corrida siguen siendo
    numeros, que es como se escribieron siempre y lo que el purgador de archivo lee.
    """
    if isinstance(valor, bool):  # antes que `int`: en Python `True` es un entero
        return {"boolValue": valor}
    if isinstance(valor, int):
        return {"intValue": str(valor) if wire is WireFormat.LANGFUSE else valor}
    if isinstance(valor, tuple):
        return {"arrayValue": {"values": [{"stringValue": elemento} for elemento in valor]}}
    return {"stringValue": valor}


def _atributos(tramo: api.FinishedSpan, *, wire: WireFormat) -> list[dict[str, Any]]:
    atributos: dict[str, langfuse_shape.AttributeValue] = {**tramo.attributes}
    if wire is WireFormat.LANGFUSE:
        atributos.update(langfuse_shape.derive(tramo))
    return [
        {"key": clave, "value": _valor_otlp(valor, wire=wire)}
        for clave, valor in sorted(atributos.items())
    ]


def otlp_payload(
    spans: Sequence[api.FinishedSpan], *, wire: WireFormat = WireFormat.OTLP, attempt: int = 0
) -> dict[str, Any]:
    """El lote en la forma de OTLP/JSON, sin depender de su SDK.

    La forma se sostiene sola --es la del protocolo, no la de una biblioteca--,
    asi que el dia que el SDK entre, lo que cambia es quien la serializa y no
    que se serializa.

    Con `WireFormat.LANGFUSE` el lote lleva ademas los atributos que Langfuse lee,
    **derivados** de lo que cada tramo ya trae, y los identificadores de tramo de
    ocho bytes que OTLP manda; los tiempos y los enteros viajan como texto. Nada de
    eso cambia el orden de `export_batch`: sigue siendo serializar, redactar y
    entregar.

    `attempt` solo cambia los identificadores de tramo de la forma de Langfuse (ver
    `langfuse_shape.wire_span_id`); el primer intento es el que siempre se uso.
    """
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "untangle"}},
                    ]
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "untangle.telemetry.traces"},
                        "spans": [
                            _tramo_otlp(tramo, wire=wire, attempt=attempt) for tramo in spans
                        ],
                    }
                ],
            }
        ]
    }


def _tramo_otlp(tramo: api.FinishedSpan, *, wire: WireFormat, attempt: int) -> dict[str, Any]:
    """Un tramo en la forma de OTLP/JSON de cada transporte."""
    inicio = _instante(tramo.started_at)
    fin = _instante(tramo.ended_at)
    if wire is WireFormat.OTLP:
        return {
            "traceId": tramo.trace_id,
            "spanId": tramo.span_id,
            "parentSpanId": tramo.parent_span_id or "",
            "name": tramo.name,
            "startTimeUnixNano": inicio,
            "endTimeUnixNano": fin,
            "attributes": _atributos(tramo, wire=wire),
        }
    cable: dict[str, Any] = {
        "traceId": tramo.trace_id,
        "spanId": langfuse_shape.wire_span_id(tramo.span_id, attempt),
        "name": tramo.name,
        # Los enteros de 64 bits van como texto, que es como los escribe el protocolo.
        "startTimeUnixNano": str(inicio),
        "endTimeUnixNano": str(fin),
        "attributes": _atributos(tramo, wire=wire),
    }
    # Un tramo raiz **no lleva** `parentSpanId`: es como lo escribe todo exportador de
    # OTLP, y no depende de que quien lee tome una cadena vacia por "sin padre".
    if tramo.parent_span_id:
        cable["parentSpanId"] = langfuse_shape.wire_span_id(tramo.parent_span_id, attempt)
    return cable


def wire_vocabulary() -> tuple[str, ...]:
    """Los nombres de atributo que este exportador escribe, para la lista de nombres publicos.

    La redaccion lee el lote como texto y su modelo de nombres toma por una persona,
    segun el contexto, alguna clave --medido: `langfuse.observation.type` salia como
    `[NAME 1]` siempre--. La raiz de composicion pasa estos nombres a
    `allow_public_terms`, y un hallazgo hecho solo de ellos no se tapa. Son claves de
    nuestra lista cerrada, nunca texto de nadie.
    """
    return tuple(sorted({*api.ALLOWED_ATTRIBUTES, *langfuse_shape.DERIVED_KEYS, "service.name"}))


def _identidad(payload: Any) -> list[tuple[object, ...]] | None:
    """Lo que ata un tramo a su traza y a su padre, y cuando ocurrio, en orden."""
    try:
        tramos = payload["resourceSpans"][0]["scopeSpans"][0]["spans"]
        return [
            (
                t["traceId"],
                t["spanId"],
                t.get("parentSpanId"),
                t["startTimeUnixNano"],
                t["endTimeUnixNano"],
            )
            for t in tramos
        ]
    except (KeyError, IndexError, TypeError):
        return None


def _identidad_intacta(esperado: dict[str, Any], redactado: str) -> bool:
    """Si el lote redactado sigue siendo JSON y sus identificadores y tiempos no cambiaron."""
    try:
        recibido = json.loads(redactado)
    except ValueError:
        return False
    anterior = _identidad(esperado)
    return anterior is not None and anterior == _identidad(recibido)


#: Cuantas veces se arma el lote si la redaccion estropea un identificador. Cada intento
#: cambia los identificadores de tramo (los de traza no se pueden cambiar: el enlace del
#: visitante los lleva), asi que reintentar tiene sentido solo con tramos de por medio.
_INTENTOS_DE_ARMADO = 3


def _preparar(
    spans: Sequence[api.FinishedSpan], formato: WireFormat
) -> tuple[Redacted | None, str | None]:
    """Serializa, **redacta** y comprueba el lote: `(lote, None)` o `(None, motivo)`.

    El orden importa y es el unico posible: se serializa, se redacta, y solo entonces
    existe algo que un transporte pueda aceptar. Devuelve un par y no un `Redacted | str`
    porque `Redacted` **es** un `str` en ejecucion: un `isinstance` no los distinguiria.
    """
    for intento in range(_INTENTOS_DE_ARMADO):
        try:
            esperado = otlp_payload(spans, wire=formato, attempt=intento)
            crudo = json.dumps(esperado, ensure_ascii=False, sort_keys=True, default=str)
        except (TypeError, ValueError) as error:  # pragma: no cover - el lote ya esta validado
            observability.emit(
                "traces.export_failed", reason="serialize", error=type(error).__name__
            )
            return None, "serialize"

        try:
            redactado = redact(crudo, language=EXPORT_LOCALE)
        except RedactionFailedError as error:
            # Fallar cerrado: si la redaccion no se puede ejecutar, **no sale nada**.
            # El lote se pierde y se dice; lo que no pasa es que salga sin tapar.
            observability.emit(
                "traces.export_failed",
                reason="redaction",
                error=type(error).__name__,
                spans=len(spans),
            )
            return None, "redaction"

        # La redaccion lee texto, no estructura: puede tomar por un dato personal un
        # trozo de un identificador y dejarlo en `[NAME 1]`. Eso no filtra nada, pero
        # un identificador roto es un arbol huerfano y un enlace a una traza que no
        # existe, y a un backend que valida el formato le tira el lote entero. Se
        # comprueba, y si el lote cambio donde no debia **no se entrega**.
        if _identidad_intacta(esperado, redactado):
            return redactado, None
        observability.emit(
            "traces.export_ids_altered", attempt=intento, spans=len(spans), wire=formato.value
        )
        if formato is not WireFormat.LANGFUSE:
            break  # el intento solo cambia los identificadores de la forma de Langfuse

    # Ningun intento dejo los identificadores intactos: el estropeado es el de la traza, o la
    # redaccion se ensano con todos. Se pierde y se dice, como cualquier otro fallo.
    observability.emit("traces.export_failed", reason="redaction_altered_ids", spans=len(spans))
    return None, "redaction_altered_ids"


def _fallo_de_transporte(error: Exception, spans: Sequence[api.FinishedSpan]) -> ExportResult:
    # Se atrapa **cualquier** fallo del transporte, y es la unica forma correcta de
    # escribir esto: BR4.8 dice que si el backend de trazas cae, ni el caso, ni el
    # gasto, ni el corte se detienen. Una lista de tipos conocidos --backend caido,
    # disco lleno-- dejaria escapar el error del exportador OTLP el dia que el SDK se
    # adopte, que es precisamente cuando la regla tiene que seguir valiendo. El error
    # no se traga: se registra con su tipo y se devuelve en `ExportResult`.
    observability.emit(
        "traces.export_failed", reason="transport", error=type(error).__name__, spans=len(spans)
    )
    return ExportResult(exported=0, failure="transport")


def export_batch(spans: Sequence[api.FinishedSpan], *, settings: Settings) -> ExportResult:
    """Redacta el lote y lo entrega. **No levanta nunca.**

    El orden importa y es el unico posible: se serializa, **se redacta**, y solo
    entonces existe algo que un transporte pueda aceptar. No hay una rama en la
    que el transporte reciba texto sin pasar por ahi, porque no hay forma de
    fabricar el tipo que exige.
    """
    if not spans:
        return ExportResult(exported=0)

    # El transporte se resuelve **antes** de serializar porque es quien dice en
    # que forma quiere el lote. Elegirlo es lo unico que se hace antes: el orden
    # que importa --serializar, redactar, entregar-- no cambia.
    try:
        transporte = transport_for(settings)
    except Exception as error:  # noqa: BLE001 -- misma razon que en `_fallo_de_transporte`
        return _fallo_de_transporte(error, spans)

    preparado, motivo = _preparar(spans, getattr(transporte, "wire_format", WireFormat.OTLP))
    if preparado is None:
        return ExportResult(exported=0, failure=motivo)

    try:
        transporte.send(preparado)
    except Exception as error:  # noqa: BLE001 -- misma razon que en `_fallo_de_transporte`
        return _fallo_de_transporte(error, spans)

    observability.emit("traces.exported", spans=len(spans), sink=_SINK.name)
    return ExportResult(exported=len(spans))


async def export_pending(
    *, settings: Settings, recorder: api.BufferedRecorder | None = None
) -> ExportResult:
    """Se lleva lo acumulado y lo exporta. Lo llama quien tiene derecho a tardar.

    Cuando el lote no sale, los resumenes de esas trazas pasan a `lost`: el
    visitante ve "se perdio" en vez de "registrandose" para siempre, y la cifra
    de resumenes perdidos dice si el backend de trazas esta sano (BR6.7).
    """
    buffer = recorder if recorder is not None else api.current_recorder()
    if not isinstance(buffer, api.BufferedRecorder):
        msg = (
            "el registrador instalado no acumula lotes. Con el exportador del SDK "
            "instalado, la exportacion la dispara el SDK y no esta funcion"
        )
        raise TypeError(msg)

    lote = buffer.drain()
    if not lote:
        return ExportResult(exported=0)

    # **Una entrega por traza.** Los identificadores de una traza viajan en todos sus
    # tramos, y que uno solo se estropee (ver `_identidad_intacta`) no tiene por que
    # llevarse la de otro visitante: cada traza se redacta, se comprueba y se entrega
    # sola, y el fallo de una queda en esa y en su resumen.
    exportados = 0
    primer_fallo: str | None = None
    for posicion, grupo in enumerate(_por_traza(lote)):
        # En un hilo: la entrega a un backend remoto es de red y bloqueante, y esta
        # funcion la llama el ciclo del proceso que sirve. Sin esto, cada exportacion
        # dejaria el bucle de eventos parado hasta cinco segundos, que es justo lo que
        # "fuera del camino de la respuesta" prohibe. La redaccion ya se corre asi en
        # `compliance.redaction.streaming`.
        resultado = await asyncio.to_thread(export_batch, grupo, settings=settings)
        exportados += resultado.exported
        if resultado.ok:
            continue
        primer_fallo = primer_fallo or resultado.failure
        await _perder_resumenes(grupo, reason=f"export_{resultado.failure}")
        if resultado.failure == "transport":
            # El destino no responde: esperar su plazo por cada traza que queda
            # alargaria el ciclo sin entregar nada. Las demas se pierden y se dicen
            # igual, y la proxima vuelta ya trae lo nuevo.
            for resto in list(_por_traza(lote))[posicion + 1 :]:
                await _perder_resumenes(resto, reason="export_transport")
            break
    return ExportResult(exported=exportados, failure=primer_fallo)


def _por_traza(spans: Sequence[api.FinishedSpan]) -> list[tuple[api.FinishedSpan, ...]]:
    """Los tramos agrupados por aseguradora y traza, en el orden en que aparecen."""
    grupos: dict[tuple[str, str], list[api.FinishedSpan]] = {}
    for tramo in spans:
        grupos.setdefault((tramo.tenant_id, tramo.trace_id), []).append(tramo)
    return [tuple(grupo) for grupo in grupos.values()]


async def _perder_resumenes(spans: Iterable[api.FinishedSpan], *, reason: str) -> None:
    """Marca perdidos los resumenes del lote que no salio (BR6.7).

    La aseguradora sale del tramo, que la lleva como dato de direccion: la fila
    del resumen esta detras de la politica de aislamiento y no se alcanza sin
    ella.

    **Tampoco esto puede detener nada.** Si la base tambien esta caida, se
    registra y se sigue: el resumen se quedara en `recording` y el plazo de diez
    segundos lo pasara a `lost` la proxima vez que alguien lo lea. Levantar aqui
    convertiria dos herramientas de diagnostico caidas en un fallo del turno.
    """
    for tenant_id, trace_id in sorted({(t.tenant_id, t.trace_id) for t in spans}):
        try:
            await api.mark_lost(trace_id, tenant_id=tenant_id, reason=reason)
        except Exception as error:  # noqa: BLE001 -- misma razon que en `export_batch`
            observability.emit(
                "traces.summary_lost_failed",
                trace_id=trace_id,
                error=type(error).__name__,
            )


__all__ = [
    "EXPORT_LOCALE",
    "ExportResult",
    "FileTransport",
    "PurgeableSpanTransport",
    "RemotePurge",
    "SpanTransport",
    "TransportUnavailableError",
    "UnavailableTransport",
    "WireFormat",
    "default_run_file",
    "export_batch",
    "export_pending",
    "install_transport",
    "otlp_payload",
    "transport_for",
    "wire_vocabulary",
]
