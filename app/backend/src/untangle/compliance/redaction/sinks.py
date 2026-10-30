"""El registro de los cinco puntos de salida (BR1.3, AC4.12.2).

**Solo los declara. No escribe en ninguno y no llama a la redaccion.** Por eso
queda fuera de la escalera de capas del modulo, con su propio contrato: no
importa ninguna otra pieza de `compliance.redaction`. Colocarlo en una capa le
habria dado permiso para importar las de abajo, y un registro que llamara a la
redaccion seria un septimo punto de salida encubierto.

Cada unidad duena implementa el suyo **exigiendo `Redacted`**. Lo que vive aqui
es la lista, en un solo sitio, que es lo que hace comprobable el criterio: un
modulo que escriba hacia una de estas cinco superficies y no este en esta lista
hace fallar la regla de importacion nombrandolo.

La lista es de cinco y esta cerrada a proposito. Eran seis hasta el 2026-10-30: la
transcripcion del caso dejo de redactarse al guardarse por decision de Miguel y
salio de la lista. Anadir un punto de salida es
anadir una linea aqui, y esa linea es lo que se ve en una revision: sin ella, un
punto de salida nuevo sin redaccion seria detectable al revisarlo, que es
exactamente lo que la regla del proyecto no admite.
"""

from __future__ import annotations

from enum import StrEnum

from untangle.base import Frozen
from untangle.copy_catalog import api as copy_api

#: Lo que responde un punto de salida cuando la redaccion no se pudo ejecutar.
#: **No sale el texto sin tapar: sale esto** (BR1.7, SEC-U3.10). La clave es
#: literal para que el chequeo de claves sin consumidor la encuentre, y vive
#: aqui, junto al registro, porque es la respuesta que los cinco comparten.
DEGRADED_COPY_KEY = copy_api.CopyKey("redaction.degraded")


class Surface(StrEnum):
    """Las cinco superficies por las que sale texto del aplicativo.

    La superficie no cambia **que** se tapa; cambia que se mide y como se
    reporta un fallo.
    """

    #: El evento tecnico, a la salida estandar.
    LOG = "log"
    #: El tramo de traza del turno o del nodo.
    TRACE = "trace"
    #: La exportacion de trazas del proceso.
    EXPORT = "export"
    #: El reporte por caso de la corrida de evaluaciones.
    REPORT = "report"
    #: La transcripcion parcial que la consola muestra mientras alguien habla.
    LIVE_PARTIAL = "live_partial"


class OutputSink(Frozen):
    """Un punto de salida declarado, con su superficie y su unidad duena."""

    name: str
    surface: Surface
    #: Quien lo implementa. U3 declara la lista; cada unidad duena escribe el
    #: suyo exigiendo `Redacted`.
    owning_unit: str
    #: Que sale por el, en una linea. Un punto de salida sin descripcion no se
    #: puede revisar: quien llegue nuevo no sabe si el suyo ya esta o no.
    writes: str


#: Los cinco. Cada unidad duena sale de `unit-of-work.md`, no de una suposicion:
#: el punto unico de eventos tecnicos es de U1 y su
#: propio codigo dice que el sitio donde encaja la redaccion lo dejo hecho para
#: U3; U5 "corre ... la exportacion de trazas del proceso" y declara depender de
#: U3 por eso mismo; el reporte por caso con sus turnos y su diferencia es de
#: U21; y la consola de llamada es de U16.
SINKS: tuple[OutputSink, ...] = (
    OutputSink(
        name="technical_log",
        surface=Surface.LOG,
        owning_unit="U1 workspace",
        writes="El evento tecnico estructurado, una linea por evento",
    ),
    OutputSink(
        name="trace_span",
        surface=Surface.TRACE,
        owning_unit="U5 provider-platform",
        writes="El tramo de traza del turno, del nodo y de la llamada al proveedor",
    ),
    OutputSink(
        name="trace_export",
        surface=Surface.EXPORT,
        owning_unit="U5 provider-platform",
        writes="La exportacion de trazas del proceso",
    ),
    OutputSink(
        name="eval_case_report",
        surface=Surface.REPORT,
        owning_unit="U21 eval-gates",
        writes="El reporte por caso, con sus turnos y la diferencia contra lo esperado",
    ),
    OutputSink(
        name="live_console_transcript",
        surface=Surface.LIVE_PARTIAL,
        owning_unit="U16 voice-call",
        writes="La transcripcion parcial que la consola muestra mientras alguien habla",
    ),
)


def by_surface(surface: Surface) -> tuple[OutputSink, ...]:
    """Los puntos de salida declarados de una superficie."""
    return tuple(sink for sink in SINKS if sink.surface is surface)


def declared_names() -> frozenset[str]:
    """Los nombres declarados. Lo que no este aqui no es un punto de salida."""
    return frozenset(sink.name for sink in SINKS)
