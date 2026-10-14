"""El enlace a una traza en la interfaz del backend de trazas.

Quien abre su caso puede ver ahi como trabajo la agente, y la direccion de una traza
en Langfuse es `{host}/project/{projectId}/traces/{traceId}`. El `projectId` no se
conoce hasta preguntarle a Langfuse con la clave, asi que la raiz de composicion lo
pide **una vez** al arrancar y lo enchufa aqui; hasta entonces --o si Langfuse no
contesto, o no hay Langfuse-- no hay enlace y quien lo pide recibe `None`.

Esta pieza no habla con la red: guarda la direccion y arma la URL. Ni importa el
adaptador ni el cliente HTTP, que es lo que deja a las superficies que muestran el
enlace (la bandeja) importarla sin llegar a ningun proveedor.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

from untangle.telemetry.traces.models import TraceSummary, TraceSummaryStatus


@dataclass(frozen=True)
class TraceLinks:
    """Donde vive la interfaz de trazas y a que proyecto pertenece este entorno."""

    host: str
    project_id: str

    def url_for(self, trace_id: str) -> str:
        # `quote` sin caracteres seguros: un identificador con `/` o `?` no puede
        # cambiar la ruta ni anadir una consulta, venga de donde venga.
        proyecto = quote(self.project_id, safe="")
        traza = quote(trace_id, safe="")
        return f"{self.host.rstrip('/')}/project/{proyecto}/traces/{traza}"


_links: TraceLinks | None = None


def install(links: TraceLinks | None) -> None:
    """La raiz de composicion enchufa la direccion cuando la sabe. `None` la quita."""
    global _links
    _links = links


def trace_url(trace_id: str) -> str | None:
    """La direccion de esta traza en la interfaz, o `None` si no se sabe cual es."""
    if _links is None:
        return None
    return _links.url_for(trace_id)


def summary_url(resumen: TraceSummary | None) -> str | None:
    """La direccion de la traza de este resumen, o `None` si todavia no hay a donde llevar.

    **La regla de "hay enlace" es una sola y vive aqui**, para que la bandeja y el tablero de
    gasto no la escriban cada uno: solo cuando el resumen esta `ready`. Uno que se esta
    registrando todavia no salio y uno `lost` no llego, asi que su direccion llevaria a una
    pagina que no existe. Y `None` si el backend no esta configurado o no se supo el proyecto.
    """
    if resumen is None or resumen.status is not TraceSummaryStatus.READY:
        return None
    return trace_url(resumen.trace_id)


def available() -> bool:
    return _links is not None


__all__ = ["TraceLinks", "available", "install", "summary_url", "trace_url"]
