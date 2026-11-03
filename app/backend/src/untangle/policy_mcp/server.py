"""Las herramientas MCP de los datos rigidos de una poliza, con SDK oficial de Python (`mcp`).

**Que expone.** Siete herramientas de solo lectura, cada una una funcion de
`untangle.policy_rag.facts.api` con entradas y salidas tipadas: el esquema JSON que ve el cliente
sale de esos modelos. Todas piden `tenant_id` y `policy_number`; la de vigencia acepta ademas la
fecha contra la que se calcula (`on`, por omision hoy) y las que traen montos o rotulos aceptan
`language`.

**Que no expone, y por que.** Ningun dato de un caso ni de un visitante: este paquete no importa
`case_record` (un contrato de importacion lo comprueba) y un numero de caso no es una credencial.
Tampoco el texto de la conversacion, la bandeja ni los proveedores. Es la poliza emitida --dato
sintetico sembrado-- y nada mas.

**Una poliza que no existe y la de otra aseguradora devuelven lo mismo** (BR2.6): la politica de fila
ya filtro la segunda antes de que el codigo la viera, asi que el error es uno y no distingue.

**Los textos de estas herramientas** (descripciones, errores) son el registro tecnico: los lee un
cliente MCP o quien lo programa, no una persona usando el producto, y por eso van en ingles. Lo que
si es lenguaje de la poliza --rotulos de limites, lo que cambia un endoso-- sale del catalogo en el
idioma que el cliente pida.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, date, datetime
from typing import Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations

from untangle.base import Locale
from untangle.policy_rag.facts import api as facts
from untangle.policy_rag.facts.models import (
    ClauseFact,
    DeductibleFact,
    DriverFact,
    EndorsementFact,
    LimitFact,
    PolicySummary,
    VehicleFact,
)
from untangle.tenancy import api as tenancy

#: El nombre con que el servidor se presenta al cliente.
SERVER_NAME = "cautelia-policy-facts"

INSTRUCTIONS = (
    "Read-only facts about the synthetic sample auto policies of Cautelia, a demo of an AI agent "
    "for car-accident reports. Every tool takes a tenant_id (the insurer or agency) and a "
    "policy_number (e.g. POL-21). Amounts are Colombian pesos: `units` are thousands of pesos as "
    "stored in the record, `pesos` the full amount and `formatted` the text for the language. "
    "These tools return what the issued policy declares; they never say whether something is "
    "covered, which needs reading the policy clauses."
)

#: Lo que declara toda herramienta: lee, no cambia nada, repetirla da lo mismo y no sale a la red.
_SOLO_LECTURA = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)

#: La fecha de hoy, inyectable para que la vigencia se pruebe con fechas fijas.
type Today = Callable[[], date]


def _hoy_utc() -> date:
    return datetime.now(UTC).date()


def _aseguradora(tenant_id: str) -> str:
    """El `tenant_id` si es una aseguradora cargada; si no, un error que lista las que hay."""
    if tenant_id not in tenancy.available_ids():
        disponibles = ", ".join(sorted(tenancy.available_ids()))
        msg = f"unknown tenant_id '{tenant_id}'; available: {disponibles}"
        raise ToolError(msg)
    return tenant_id


def _sin_poliza(tenant_id: str, policy_number: str) -> ToolError:
    # Una sola frase para inexistente y de otra aseguradora (BR2.6).
    return ToolError(f"no policy '{policy_number}' was found for tenant '{tenant_id}'")


async def get_limits(
    tenant_id: str, policy_number: str, language: Literal["es", "en"] = "es"
) -> list[LimitFact]:
    limites = await facts.limits(_aseguradora(tenant_id), policy_number, language=_idioma(language))
    if limites is None:
        raise _sin_poliza(tenant_id, policy_number)
    return list(limites)


async def get_deductibles(
    tenant_id: str, policy_number: str, language: Literal["es", "en"] = "es"
) -> list[DeductibleFact]:
    deducibles = await facts.deductibles(
        _aseguradora(tenant_id), policy_number, language=_idioma(language)
    )
    if deducibles is None:
        raise _sin_poliza(tenant_id, policy_number)
    return list(deducibles)


async def get_insured_vehicles(tenant_id: str, policy_number: str) -> list[VehicleFact]:
    vehiculos = await facts.vehicles(_aseguradora(tenant_id), policy_number)
    if vehiculos is None:
        raise _sin_poliza(tenant_id, policy_number)
    return list(vehiculos)


async def get_listed_drivers(tenant_id: str, policy_number: str) -> list[DriverFact]:
    conductores = await facts.drivers(_aseguradora(tenant_id), policy_number)
    if conductores is None:
        raise _sin_poliza(tenant_id, policy_number)
    return list(conductores)


async def get_endorsements(
    tenant_id: str, policy_number: str, language: Literal["es", "en"] = "es"
) -> list[EndorsementFact]:
    endosos = await facts.endorsements(
        _aseguradora(tenant_id), policy_number, language=_idioma(language)
    )
    if endosos is None:
        raise _sin_poliza(tenant_id, policy_number)
    return list(endosos)


async def get_clause(tenant_id: str, policy_number: str, clause_id: str) -> ClauseFact:
    clausula = await facts.clause(_aseguradora(tenant_id), policy_number, clause_id)
    if clausula is None:
        # Inexistente, de otro formulario, senuelo o de otra poliza: lo mismo.
        msg = (
            f"no clause '{clause_id}' was found on policy '{policy_number}' of tenant '{tenant_id}'"
        )
        raise ToolError(msg)
    return clausula


def _resumen(today: Today) -> Callable[..., Awaitable[PolicySummary]]:
    """La herramienta del resumen, con la fecha de hoy inyectada para probar la vigencia."""

    async def get_policy_summary(
        tenant_id: str, policy_number: str, on: date | None = None
    ) -> PolicySummary:
        resumen = await facts.policy_summary(
            _aseguradora(tenant_id), policy_number, on=on or today()
        )
        if resumen is None:
            raise _sin_poliza(tenant_id, policy_number)
        return resumen

    return get_policy_summary


def build_server(
    *,
    today: Today = _hoy_utc,
    lifespan: Callable[[MCPServer], AbstractAsyncContextManager[None]] | None = None,
) -> MCPServer:
    """El servidor con sus siete herramientas. No abre la base: lo hace la primera llamada.

    `lifespan` lo pasa el proceso (`__main__`) para cerrar el grupo de conexiones al terminar.
    """
    servidor: MCPServer = MCPServer(SERVER_NAME, instructions=INSTRUCTIONS, lifespan=lifespan)
    herramientas: tuple[tuple[Callable[..., Awaitable[object]], str, str], ...] = (
        (
            _resumen(today),
            "Policy summary",
            "Holder, issuer, form, policy period and whether the policy is in force on a date "
            "(`on`, ISO date, default today; both period ends count as in force), plus how many "
            "vehicles, listed drivers and endorsements it carries.",
        ),
        (
            get_limits,
            "Policy limits",
            "The liability, occupant medical-expense and driver personal-accident limits the policy declares. "
            "Deductibles are a separate tool.",
        ),
        (
            get_deductibles,
            "Policy deductibles",
            "The vehicle deductibles the policy declares (partial loss by damage and partial loss by theft).",
        ),
        (
            get_insured_vehicles,
            "Insured vehicles",
            "The vehicles on the policy, by make, model and year. No plate and no VIN.",
        ),
        (
            get_listed_drivers,
            "Listed drivers",
            "The drivers the policy declares, holder first. An empty list means the policy "
            "declares no drivers, not that nobody else may drive.",
        ),
        (
            get_endorsements,
            "Policy endorsements",
            "The endorsements (special conditions) on the policy and which clauses each one "
            "changes.",
        ),
        (
            get_clause,
            "Policy clause",
            "One clause of the policy by its clause_id, only if it belongs to this policy's base "
            "form or one of its endorsements. Returns the clause text as written; it does not "
            "interpret it or say whether anything is covered.",
        ),
    )
    for funcion, titulo, descripcion in herramientas:
        servidor.add_tool(funcion, title=titulo, description=descripcion, annotations=_SOLO_LECTURA)
    return servidor


def _idioma(language: str) -> Locale:
    return "en" if language == "en" else "es"


__all__ = ["INSTRUCTIONS", "SERVER_NAME", "build_server"]
