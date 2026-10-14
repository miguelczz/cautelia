"""El resumen de traza que ve el visitante, sin credencial (BR4.3, BR4.4).

**Una sola via de rechazo, otra vez.** Un identificador inexistente, uno de otra
conversacion y uno de otra aseguradora se responden **igual**: no hay resumen. La
comparacion de dueno la hace U5 en tiempo constante contra el resumen de la clave; esta
unidad no la repite ni la afina, porque dos comparaciones de dueno son dos que un dia
difieren. Lo unico que aporta aqui es que ninguna de las tres causas salga por una
puerta distinta: un "prohibido" confirmaria que ese caso existe, que es la mitad de lo
que el visitante de al lado querria saber.

**"Se esta registrando" no es "no encontrado"** (BR4.4). Son dos respuestas distintas
porque son dos hechos distintos, y confundirlos rompe justo la regla de arriba: si una
traza en curso se dijera "no encontrada", el visitante legitimo veria lo mismo que el
intruso y no sabria que esperar.

**Aqui no se redacta y es a proposito.** El resumen no tiene donde alojar texto libre:
son nodos de un conjunto cerrado, dos recuentos, milisegundos y un costo con su estado.
Esa es la garantia de U5 --ningun atributo admite texto libre, comprobado por el
comprobador de tipos y por la prueba de canarios-- y anadir una redaccion aqui simularia
proteger algo que no puede entrar.
"""

from __future__ import annotations

from dataclasses import dataclass

from untangle.telemetry.traces import api as traces
from untangle.telemetry.traces.models import TraceSummary, TraceSummaryStatus
from untangle.tenancy.models import TenantId


@dataclass(frozen=True)
class NodeView:
    """Un nodo del recorrido, como la pagina lo muestra."""

    node: str
    duration_ms: int
    cost_usd: str | None
    cost_status: str


@dataclass(frozen=True)
class TraceView:
    """El resumen de una respuesta. `status` decide que dibuja la pagina."""

    status: str
    nodes: tuple[NodeView, ...]
    clauses_retrieved: int
    clauses_verified: int
    latency_ms: int | None
    cost_usd: str | None
    cost_status: str

    @property
    def recording(self) -> bool:
        """Todavia se esta escribiendo: la pagina se actualiza sola (BR4.4)."""
        return self.status == TraceSummaryStatus.RECORDING.value


def _nodo(timing: object) -> NodeView:
    costo = getattr(timing, "cost", None)
    cantidad = getattr(costo, "amount_usd", None)
    return NodeView(
        node=str(getattr(timing, "node", "")),
        duration_ms=int(getattr(timing, "duration_ms", 0)),
        cost_usd=None if cantidad is None else str(cantidad),
        cost_status=str(getattr(costo, "status", "")),
    )


def view_of(summary: TraceSummary) -> TraceView:
    """La forma que sale por el cable, sin nada que la pagina no muestre."""
    return TraceView(
        status=summary.status.value,
        nodes=tuple(_nodo(nodo) for nodo in summary.nodes),
        clauses_retrieved=summary.clauses_retrieved,
        clauses_verified=summary.clauses_verified,
        latency_ms=summary.latency_ms,
        cost_usd=None if summary.cost.amount_usd is None else str(summary.cost.amount_usd),
        cost_status=summary.cost.status.value,
    )


async def by_trace(
    trace_id: str, *, tenant_id: TenantId, visitor_key_hash: str | None
) -> TraceView | None:
    """El resumen de esta traza, solo para el navegador que la produjo.

    `None` es la unica forma de decir que no hay nada que mostrar, y cubre las tres
    causas a la vez: no existe, es de otra conversacion, es de otra aseguradora.
    """
    resumen = await traces.summary_by_trace(
        trace_id, tenant_id=tenant_id, visitor_key_hash=visitor_key_hash
    )
    return None if resumen is None else view_of(resumen)


__all__ = ["NodeView", "TraceView", "by_trace", "view_of"]
