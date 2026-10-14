"""Los tres estados del resumen de traza, cada uno con su clave del catalogo.

Los tres y no solo uno. El plan nombra "registrandose", que es el que se ve
mientras el rastro no ha llegado, pero los otros dos se ven igual de a menudo:
declarar uno solo dejaria a los otros dos saliendo como valor de enum en
pantalla, que es exactamente lo que la convencion 4 del equipo prohibe.

`lost` es un **valor, no un fallo** (BR6.7), y su frase tiene que decir eso: que
el rastro no llego, no que algo se rompio. Un caso que se cayera porque el panel
de trazas esta caido convertiria una herramienta de diagnostico en un punto de
fallo, y el texto que lo describe no puede sugerir lo contrario.

La correspondencia se escribe entera y no se compone, por la misma razon que en
el resto del proyecto: una clave armada en ejecucion deja de tener consumidor
literal, y el chequeo del catalogo la da por muerta.
"""

from __future__ import annotations

from untangle.copy_catalog.api import CopyKey
from untangle.telemetry.traces.models import TraceSummaryStatus

SUMMARY_STATUS_KEYS: dict[TraceSummaryStatus, CopyKey] = {
    TraceSummaryStatus.RECORDING: CopyKey("trace.summary.recording"),
    TraceSummaryStatus.READY: CopyKey("trace.summary.ready"),
    TraceSummaryStatus.LOST: CopyKey("trace.summary.lost"),
}


def all_keys() -> frozenset[CopyKey]:
    """Todas las claves que este modulo promete que el catalogo trae."""
    return frozenset(SUMMARY_STATUS_KEYS.values())
