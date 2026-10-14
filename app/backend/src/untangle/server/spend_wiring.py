"""El puente entre lo que reporta un adaptador y el libro de gasto (C-16 -> C-17).

Dos piezas que ninguno de los dos modulos puede tener: `providers` esta encima de
`telemetry` en el contrato de capas, asi que la contabilidad no puede leer un
`UsageReport` ni `providers.yaml`, y el adaptador no puede llamar a la
contabilidad sin romper su propio aislamiento. Viven en `untangle.server`
porque es el unico paquete que ve los dos lados.

Estuvieron dentro de `composition.py` como piezas privadas mientras solo las
usaba la raiz del proceso servido. Con U15 las usan tambien los comandos a mano
de la voz (`voice:contract-live` y `voice:say`), que recorren el mismo camino de
gasto que una llamada de verdad; alcanzar una pieza privada de otro modulo seria
esconder esa dependencia donde nadie la ve, asi que pasaron aqui con nombre
publico.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from untangle.base import ProviderName, UnitKind, Use
from untangle.providers import config as provider_config
from untangle.providers import ports
from untangle.telemetry.spend import api as spend
from untangle.telemetry.spend import attribution, pricing
from untangle.telemetry.spend.models import CallUsage, PricedUnits
from untangle.telemetry.traces import api as trazas

__all__ = ["LedgerUsageSink", "spend_runtime"]

#: Los usos cuyo gasto nunca se atribuye a un caso: el de las pruebas de calidad.
_SIN_CASO = frozenset({Use.EVALS, Use.EVALS_CHAT})


@dataclass(frozen=True)
class LedgerUsageSink(ports.UsageSink):
    """Lo que el adaptador reporto, convertido en filas de gasto (C-16 -> C-17).

    El adaptador recibe un `UsageSink` inyectado y no sabe que existe una
    contabilidad; esta es la implementacion de verdad, la que escribe en el libro
    mayor.

    **Una llamada de generacion deja dos filas, no una.** El proveedor cobra los
    tokens de entrada y los de salida a precios distintos, y la fila de gasto
    solo admite una clase de unidad. Las dos filas nombran el mismo caso y el
    mismo momento.

    **Una llamada que no reporto nada deja una fila no medida.** No cero: cero
    seria afirmar que no consumio, y una llamada que salio y no volvio pudo
    haber consumido. Sin esa fila, el costo por caso quedaria por debajo del
    real y nadie lo notaria (BR3.1, BR3.3).
    """

    async def report(self, usage: ports.UsageReport) -> None:
        contexto = trazas.current_context()
        # La aseguradora es **atribucion, no aislamiento** (BR7.1): sale del
        # contexto del turno por la misma razon que el caso, y por la misma via
        # --una variable de contexto, no una llamada al backend de trazas--, asi
        # que un panel de trazas caido no deja un gasto sin atribuir (BR4.8).
        tenant = contexto.tenant_id if contexto is not None else None
        # Lo que corre fuera del turno --la transcripcion y la voz de una llamada--
        # lo atribuye quien abrio la llamada (2026-10-09). Sin esto el tablero no
        # podia decir cuanto costo un caso ni una llamada.
        #
        # **Las pruebas de calidad no se atribuyen**: sus turnos llevan casos de la
        # corrida que no existen en la base, y la columna del caso es una llave
        # foranea. Su gasto se cuenta igual, sin caso.
        externa = attribution.current()
        caso = usage.case_ref
        llamada = None
        if usage.use not in _SIN_CASO:
            if caso is None and contexto is not None:
                caso = contexto.case_id
            if externa is not None:
                tenant = tenant or externa.tenant_id
                caso = caso or externa.case_id
                llamada = externa.call_id

        if not usage.units:
            await spend.record_spend(
                provider=usage.provider,
                model=usage.model,
                use=usage.use,
                units=None,
                unit_kind=UnitKind.INPUT_TOKENS,
                case_id=caso,
                call_ref=llamada,
                tenant_ref=tenant,
                source=usage.source,
            )
            return

        for unidad in usage.units:
            await spend.record_spend(
                provider=usage.provider,
                model=usage.model,
                use=usage.use,
                units=unidad.units,
                unit_kind=unidad.unit_kind,
                case_id=caso,
                call_ref=llamada,
                tenant_ref=tenant,
                source=usage.source,
            )


def spend_runtime(config: provider_config.ProviderPlatformConfig) -> spend.SpendRuntime:
    """Lo que la contabilidad necesita de la configuracion versionada.

    Se **copia**, no se importa: `telemetry` esta debajo de `providers` en el
    contrato de capas, asi que la contabilidad no puede leer `providers.yaml`.
    Lo que cruza es el dato, y este es el unico sitio que lo traduce.
    """
    proveedores = config.providers
    return spend.SpendRuntime(
        prices=pricing.PriceTable.from_entries(config.prices.price_entries()),
        plans={
            uso.use: spend.UsePlan(provider=uso.provider, model=uso.model, billable=uso.billable)
            for uso in proveedores.uses
        },
        zone=proveedores.zone,
        chat_messages_per_session=proveedores.chat_limits.messages_per_session,
        chat_messages_per_day=proveedores.chat_limits.messages_per_day,
        voice_calls_per_visitor_per_day=proveedores.voice_limits.calls_per_visitor_per_day,
        site_daily_cap=proveedores.voice_limits.site_daily_cap,
        max_call_seconds=proveedores.voice_limits.max_call_seconds,
        call_usage=_consumo_de_una_llamada(proveedores),
        recording_minutes=proveedores.recording_reserve.minutes,
    )


def _consumo_de_una_llamada(proveedores: provider_config.ProvidersConfig) -> CallUsage:
    """Lo que `providers.yaml` declara que consume una llamada, en unidades.

    La traduccion vive aqui por la misma razon que las demas: `telemetry` esta
    debajo de `providers` en el contrato de capas, asi que la contabilidad no puede
    leer el archivo. Lo que cruza es el dato.

    **Los segundos de audio salen del limite de duracion**, no de este bloque: la
    transcripcion corre toda la llamada, y declarar la duracion dos veces es como
    se acaba teniendo dos duraciones.
    """
    consumo = proveedores.call_reserve
    segundos = Decimal(proveedores.voice_limits.max_call_seconds)
    caracteres = Decimal(consumo.synthesis.characters)
    return CallUsage(
        transcription=PricedUnits(
            provider=ProviderName(consumo.transcription.provider),
            model=consumo.transcription.model,
            unit_kind=UnitKind.AUDIO_SECONDS,
            units=segundos,
        ),
        synthesis_primary=PricedUnits(
            provider=ProviderName(consumo.synthesis.primary.provider),
            model=consumo.synthesis.primary.model,
            unit_kind=UnitKind.CHARACTERS,
            units=caracteres,
        ),
        synthesis_fallback=PricedUnits(
            provider=ProviderName(consumo.synthesis.fallback.provider),
            model=consumo.synthesis.fallback.model,
            unit_kind=UnitKind.CHARACTERS,
            units=caracteres,
        ),
        model_input=PricedUnits(
            provider=ProviderName(consumo.model.provider),
            model=consumo.model.model,
            unit_kind=UnitKind.INPUT_TOKENS,
            units=Decimal(consumo.model.input_tokens),
        ),
        model_output=PricedUnits(
            provider=ProviderName(consumo.model.provider),
            model=consumo.model.model,
            unit_kind=UnitKind.OUTPUT_TOKENS,
            units=Decimal(consumo.model.output_tokens),
        ),
    )
