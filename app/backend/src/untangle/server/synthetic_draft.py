"""El comando a mano que redacta borradores de texto fuente con el modelo (U7, F1).

    mise run synthetic:draft -- --tenant <id> --part <parte> [--part ...]
                                [--language es|en] [--variant <v>]

**Nunca corre en GitHub Actions** (BR2.1): llama a Gemini con la clave del uso
`operations`, en plan gratuito, y depende de la red. Vive aqui y no en
`untangle.synthetic_data` porque necesita el adaptador del proveedor, y solo la
raiz de composicion puede construirlo (contrato `raiz-de-composicion`).

## El camino de cada llamada

El mismo que una llamada del proceso servido: la fabrica de U5 construye el
cliente del uso `operations` con **su** clave, el techo del proyecto se consulta
antes de llamar, y el adaptador reporta lo que consumio al registro de gasto
(BR2.1, CG-U7-3). El adaptador solo conoce los tiempos del uso `operations`: si
alguien le pidiera otro uso, fallaria en vez de llamar con la clave equivocada.

## Que escribe y que no

Un borrador por parte en `tmp/synthetic-drafts/<aseguradora>/<idioma>/<parte>.yaml`
(ver `synthetic_data/drafting.py`). Nada en `app/data/`: pasar un borrador a texto
fuente es una revision, no un comando.

## Cuando se acaba la cuota

Si el proveedor contesta que se acabo la cuota del plan gratuito, o el techo del
proyecto esta cerrado, el comando **se detiene** y dice que se acabo: no se
reintenta, no se cambia de plan ni de clave, y se retoma otro dia (CG-U7-7, regla
de `project.md`). Imprime siempre lo que gasto la corrida.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from untangle import paths
from untangle.base import Use
from untangle.providers import config as provider_config
from untangle.providers import factory
from untangle.providers.adapters.gemini import api as gemini
from untangle.providers.adapters.gemini import breaker as circuitos
from untangle.providers.adapters.gemini import transport as gemini_transport
from untangle.providers.ceiling import CeilingGate
from untangle.providers.ports import (
    BudgetExhausted,
    ProviderError,
    ProviderErrorKind,
    SpendGate,
    UsageSink,
)
from untangle.providers.transport import CallTimeouts, TransportFactory
from untangle.server import manual_ledger, spend_wiring
from untangle.settings import Settings
from untangle.synthetic_data import drafting
from untangle.synthetic_data.models import PolicyPart
from untangle.telemetry.spend import api as spend
from untangle.tenancy import config as tenancy_config

__all__ = [
    "DraftPlatform",
    "build_draft_platform",
    "draft_transports",
    "main",
]


@dataclass(frozen=True)
class DraftPlatform:
    """Lo que la redaccion necesita, construido por el camino del aplicativo."""

    clients: factory.ProviderClients
    model: drafting.DraftModel
    #: Cierra los clientes de red al terminar, si los hay.
    close: Callable[[], Awaitable[None]] | None


def draft_transports() -> TransportFactory:
    """El transporte de verdad hacia Gemini. Las pruebas lo sustituyen por su doble."""
    return gemini_transport.GeminiTransportFactory()


def build_draft_platform(
    settings: Settings,
    config: provider_config.ProviderPlatformConfig,
    *,
    transports: TransportFactory | None = None,
    gate: SpendGate | None = None,
    usage: UsageSink | None = None,
) -> DraftPlatform:
    """La fabrica, el adaptador del uso `operations`, el techo y el registro de gasto.

    Las tres costuras con nombre existen para las pruebas --transporte doble, techo
    forzado, registro que anota-- y para que el comando envuelva el registro y
    pueda imprimir lo gastado. Por omision, todo es lo de verdad.
    """
    transportes = transports if transports is not None else draft_transports()
    clientes = factory.ProviderClients(
        settings=settings, config=config.providers, transports=transportes
    )
    uso = config.providers.for_use(Use.OPERATIONS)
    generador = gemini.GeminiTextGenerator(
        clientes,
        config=config.providers,
        breakers=circuitos.CircuitBreakerRegistry(config.providers.circuit_breaker),
        usage=usage if usage is not None else spend_wiring.LedgerUsageSink(),
        # Solo el uso `operations`: el adaptador falla ante cualquier otro.
        timeouts={
            Use.OPERATIONS: CallTimeouts(
                connect_timeout_ms=uso.connect_timeout_ms, read_timeout_ms=uso.read_timeout_ms
            )
        },
    )
    cierre = (
        transportes.aclose
        if isinstance(transportes, gemini_transport.GeminiTransportFactory)
        else None
    )
    return DraftPlatform(
        clients=clientes,
        model=drafting.DraftModel(
            generator=generador,
            gate=gate if gate is not None else CeilingGate(spend.budget_state),
            provider=uso.provider,
        ),
        close=cierre,
    )


async def run_drafts(
    platform: DraftPlatform,
    requests: Sequence[drafting.DraftRequest],
    *,
    reference: str,
    template: drafting.DraftTemplate,
    drafts_dir: Path,
) -> int:
    """Redacta las partes pedidas, una tras otra, y se detiene en el primer fallo."""
    for pedido in requests:
        try:
            resultado = await drafting.draft_part(
                pedido,
                model=platform.model,
                reference=reference,
                template=template,
                drafts_dir=drafts_dir,
            )
        except BudgetExhausted as parada:
            print(
                f"SE DETUVO: {parada}. No se reintenta ni se recarga; si es la cuota del plan "
                "gratuito, se retoma otro dia (CG-U7-7). Decide Miguel.",
                file=sys.stderr,
            )
            return 2
        except ProviderError as error:
            print(
                f"La redaccion de '{pedido.part.value}' fallo: {error}. No se reintenta.",
                file=sys.stderr,
            )
            if error.kind is ProviderErrorKind.RATE_LIMITED:
                # La cuota diaria del plan gratuito llega asi, no como saldo agotado:
                # el proveedor la cuenta como limite de ritmo.
                print(
                    "Si es la cuota diaria del plan gratuito, se retoma otro dia, sin cambiar "
                    "de plan ni de clave (CG-U7-7).",
                    file=sys.stderr,
                )
            return 1
        print(f"borrador: {resultado.path} ({len(resultado.draft.clauses)} clausulas)")
        for nota in resultado.notes:
            print(f"  revise: {nota}")
    return 0


def _analizador() -> argparse.ArgumentParser:
    analizador = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    analizador.add_argument("--tenant", required=True, help="la emisora cuyo texto se redacta")
    analizador.add_argument(
        "--part",
        required=True,
        action="append",
        choices=[p.value for p in PolicyPart],
        help="la parte que se redacta; se repite para pedir varias",
    )
    analizador.add_argument(
        "--language", choices=("es", "en"), default=None, help="por omision, el de la emisora"
    )
    analizador.add_argument("--variant", default=None, help="la variante de la parte, si la tiene")
    analizador.add_argument(
        "--out-dir", type=Path, default=None, help="por omision, tmp/synthetic-drafts/"
    )
    return analizador


def _pedidos(argumentos: argparse.Namespace) -> list[drafting.DraftRequest]:
    aseguradoras = tenancy_config.load()
    aseguradora = aseguradoras.get(argumentos.tenant)
    if aseguradora is None:
        disponibles = ", ".join(aseguradoras.ids) or "(ninguna)"
        msg = f"la aseguradora '{argumentos.tenant}' no esta cargada; disponibles: {disponibles}"
        raise drafting.DraftError(msg)
    if argumentos.variant is not None and PolicyPart.ENDORSEMENTS.value not in argumentos.part:
        msg = "--variant solo aplica a la parte endorsements, y no se pidio"
        raise drafting.DraftError(msg)
    return [
        drafting.request_for(
            aseguradora,
            part=PolicyPart(parte),
            language=argumentos.language,
            variant=argumentos.variant if parte == PolicyPart.ENDORSEMENTS.value else None,
        )
        for parte in argumentos.part
    ]


async def _con_registro(
    platform: DraftPlatform,
    annotator: manual_ledger.AnnotatingUsageSink,
    config: provider_config.ProviderPlatformConfig,
    url: str,
    *,
    run: Callable[[], Awaitable[int]],
) -> int:
    await manual_ledger.open_ledger(config, url)
    gastado: Decimal | None = None
    try:
        codigo = await run()
    finally:
        gastado = await manual_ledger.close_ledger()
        if platform.close is not None:
            await platform.close()
    manual_ledger.print_spend(annotator.reports, config, gastado)
    return codigo


def main(argv: list[str] | None = None) -> int:
    argumentos = _analizador().parse_args(argv)
    ajustes = Settings()
    config = provider_config.load()
    try:
        pedidos = _pedidos(argumentos)
        plantilla = drafting.load_template()
        referencia = drafting.read_structure_reference(
            paths.policy_structure_reference_path(), repo_root=paths.repo_root()
        )
        # Todos los prompts se arman antes de gastar nada: un pedido mal hecho
        # --una variante que falta-- se dice aqui, sin haber llamado a nadie.
        for pedido in pedidos:
            drafting.build_prompt(pedido, reference=referencia, template=plantilla)
    except drafting.DraftError as error:
        print(str(error), file=sys.stderr)
        return 1

    anotador = manual_ledger.AnnotatingUsageSink(spend_wiring.LedgerUsageSink())
    plataforma = build_draft_platform(ajustes, config, usage=anotador)
    try:
        # La clave se exige **antes** de levantar ninguna base.
        plataforma.clients.require(Use.OPERATIONS)
    except factory.MissingProviderKeyError as error:
        print(str(error), file=sys.stderr)
        return 2

    destino = argumentos.out_dir if argumentos.out_dir is not None else paths.synthetic_drafts_dir()
    url = manual_ledger.project_ledger_url(ajustes, purpose="llamada de redaccion (BR2.1)")
    return asyncio.run(
        _con_registro(
            plataforma,
            anotador,
            config,
            url,
            run=lambda: run_drafts(
                plataforma,
                pedidos,
                reference=referencia,
                template=plantilla,
                drafts_dir=destino,
            ),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
