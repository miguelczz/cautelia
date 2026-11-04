"""El ajustador de IA enchufado: sus puertos con el adaptador de Anthropic y su disparo (plan 09, fase 5).

Es la unica pieza que importa `untangle.adjuster` en el proceso servido (contrato
`ajustador-solo-desde-la-raiz`) y la que construye el cliente del uso `adjuster`, con su clave
propia y su propio tope en el proveedor: el mismo cliente atiende la decision (salida
estructurada) y la investigacion (busqueda web), que son dos llamadas separadas del mismo uso.

**Sin lo que necesita, no se enchufa nada y el producto se comporta como antes.** Sin la clave
del uso, sin cifrador o sin base, el caso derivado espera a una persona con credencial; se dice al
arrancar con un evento, no con un fallo.

La decision se registra por la misma ruta que una persona (`inbox.decision.decide`), con el actor
`adjuster_ai` y una llave de idempotencia estable por caso (la que el proceso entrega).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime

from untangle import observability
from untangle.adjuster import config as adjuster_config
from untangle.adjuster.ports import AdjusterPorts, DecisionToRecord
from untangle.adjuster.service import AdjusterService
from untangle.base import Use
from untangle.case_record.crypto import Cipher
from untangle.inbox import adjuster_view
from untangle.inbox import decision as inbox_decision
from untangle.orchestration import derivation_trigger
from untangle.providers import config as provider_config
from untangle.providers import factory
from untangle.providers.adapters import anthropic as anthropic_adapter
from untangle.providers.ceiling import CeilingGate
from untangle.providers.ports import Vector
from untangle.server import corpus_ingest, spend_wiring
from untangle.settings import Settings
from untangle.telemetry.spend import api as spend
from untangle.tenancy import api as tenancy

USE = Use.ADJUSTER


async def _registrar(decision: DecisionToRecord) -> None:
    """Registra el cierre del caso como lo haria una persona, firmado por el ajustador de IA."""
    await inbox_decision.decide(
        tenancy.require(decision.tenant_id),
        case_id=decision.case_id,
        action=decision.action,
        comment=decision.comment,
        idempotency_key=decision.idempotency_key,
        principal_id=None,
        adjuster_ai=True,
        now=datetime.now(UTC),
    )


def build_ports(
    settings: Settings,
    config: provider_config.ProviderPlatformConfig,
    *,
    cipher: Cipher,
    embed: Callable[[Sequence[str]], Awaitable[list[Vector]]],
) -> AdjusterPorts | None:
    """Los puertos del ajustador, o nada si el uso no tiene clave."""
    clave = settings.anthropic_api_key_adjuster
    if not clave:
        observability.emit("server.adjuster_not_installed", missing=factory.env_var_for(USE))
        return None
    declarado = config.providers.for_use(USE)
    cliente = anthropic_adapter.build_client(
        clave,
        connect_timeout_ms=declarado.connect_timeout_ms,
        read_timeout_ms=declarado.read_timeout_ms,
    )
    techo = CeilingGate(spend.budget_state)
    contabilidad = spend_wiring.LedgerUsageSink()
    return AdjusterPorts(
        generate=anthropic_adapter.AnthropicTextGenerator(
            cliente,
            use=USE,
            model=declarado.model,
            gate=techo,
            usage=contabilidad,
            careful=False,
        ),
        research=anthropic_adapter.AnthropicWebResearcher(
            cliente, use=USE, model=declarado.model, gate=techo, usage=contabilidad
        ),
        embed=embed,
        embedding_model=corpus_ingest.embedding_model_for(config.providers).model_id,
        model=declarado.model,
        cipher=cipher,
        now=lambda: datetime.now(UTC),
        record_decision=_registrar,
    )


def install(
    settings: Settings,
    config: provider_config.ProviderPlatformConfig,
    *,
    cipher: Cipher | None,
    embed: Callable[[Sequence[str]], Awaitable[list[Vector]]],
) -> AdjusterService | None:
    """Enchufa el ajustador: oyente de la derivacion y vigia del caso. `None` si no se puede.

    Antes de nada desenchufa lo que dejara otra aplicacion del mismo proceso: los dos puertos
    son de modulo, y un servicio de una aplicacion anterior seguiria disparando.
    """
    uninstall()
    if not settings.database_url:
        return None
    if cipher is None:
        observability.emit("server.adjuster_not_installed", missing="case_cipher")
        return None
    puertos = build_ports(settings, config, cipher=cipher, embed=embed)
    if puertos is None:
        return None
    servicio = AdjusterService(ports=puertos, config=adjuster_config.load())
    derivation_trigger.install_derived_listener(servicio.on_derived)
    adjuster_view.install(servicio)
    return servicio


def uninstall() -> None:
    """Desenchufa los dos puertos. Para el cierre ordenado y las pruebas."""
    derivation_trigger.install_derived_listener(None)
    adjuster_view.install(None)
