"""El paso `vehicle_value`: de la investigacion a un valor verificable o a «no pude verificar».

Una llamada a Claude con busqueda web --hasta `max_searches`, solo en los dominios de la
configuracion-- y despues **codigo**: la investigacion termina con dos lineas de formato fijo
(`VALUE_COP:` y `CONFIDENCE:`) y esas se leen con una lectura estricta, nunca con una tercera
llamada al modelo. Un valor sin fuente de un dominio permitido, o fuera del rango creible que
fija la configuracion, no existe: el paso dice que no pudo verificarlo y la decision se toma
igual, porque no depende de el.

**Un error del proveedor es «no pude verificar» y no una excepcion**: el valor es un dato de
apoyo. El saldo agotado si se deja pasar --para quien tiene que detenerse--.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from urllib.parse import urlparse

from untangle.adjuster import prompting
from untangle.adjuster.config import AdjusterConfig
from untangle.adjuster.ports import AdjusterPorts
from untangle.base import Locale, Use
from untangle.providers.ports import ProviderError, ResearchSource

_VALUE_LINE = re.compile(r"^[ \t]*VALUE_COP:[ \t]*(?P<value>[^\r\n]*?)[ \t\r]*$", re.MULTILINE)
_CONFIDENCE_LINE = re.compile(
    r"^[ \t]*CONFIDENCE:[ \t]*(?P<value>[^\r\n]*?)[ \t\r]*$", re.MULTILINE
)
_DIGITS = re.compile(r"^[0-9]+$")
_NOT_FOUND = "not_found"


class Firmness(StrEnum):
    """Que tan firme es la fuente, segun la propia investigacion."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ValueStatus(StrEnum):
    FOUND = "found"
    NOT_VERIFIED = "not_verified"
    #: La poliza no trae un vehiculo: no hay nada que buscar.
    NO_VEHICLE = "no_vehicle"


class NotVerifiedReason(StrEnum):
    """Por que un valor no se pudo verificar. Vocabulario cerrado, para la traza."""

    NO_VALUE = "no_value"
    IMPLAUSIBLE = "implausible"
    NO_SOURCE = "no_source"
    PROVIDER_ERROR = "provider_error"


@dataclass(frozen=True)
class ParsedResearch:
    value_cop: int | None
    firmness: Firmness


@dataclass(frozen=True)
class VehicleValue:
    status: ValueStatus
    vehicle: str | None = None
    value_cop: int | None = None
    firmness: Firmness | None = None
    source: ResearchSource | None = None
    searches_used: int = 0
    reason: NotVerifiedReason | None = None


def parse_research(text: str) -> ParsedResearch:
    """Lee las dos lineas de formato fijo. La ultima de cada una manda; nada se interpreta.

    Una cifra con separadores, con texto alrededor o dentro de otra frase no es una cifra, y una
    firmeza que no es una de las tres es la mas baja: nada se supone firme.
    """
    valores = _VALUE_LINE.findall(text)
    ultimo = valores[-1] if valores else None
    valor = int(ultimo) if ultimo is not None and _DIGITS.match(ultimo) else None
    firmezas = _CONFIDENCE_LINE.findall(text)
    try:
        firmeza = Firmness(firmezas[-1].strip().lower()) if firmezas else Firmness.LOW
    except ValueError:
        firmeza = Firmness.LOW
    return ParsedResearch(value_cop=valor, firmness=firmeza)


def _in_allowed_domain(url: str, domains: Sequence[str]) -> bool:
    try:
        direccion = urlparse(url)
    except ValueError:
        return False
    host = (direccion.hostname or "").lower()
    if direccion.scheme not in {"http", "https"} or not host:
        return False
    return any(host == dominio or host.endswith(f".{dominio}") for dominio in domains)


def _not_verified(reason: NotVerifiedReason, vehicle: str, searches: int) -> VehicleValue:
    return VehicleValue(
        status=ValueStatus.NOT_VERIFIED, vehicle=vehicle, searches_used=searches, reason=reason
    )


async def look_up(
    vehicle: str | None,
    *,
    ports: AdjusterPorts,
    config: AdjusterConfig,
    language: Locale,
    today: date,
) -> VehicleValue:
    """El valor de referencia del vehiculo, verificado, o la razon por la que no se pudo."""
    if vehicle is None:
        return VehicleValue(status=ValueStatus.NO_VEHICLE)
    prompt = prompting.build_research_prompt(language=language, vehicle=vehicle, today=today)
    try:
        resultado = await ports.research.research(
            prompt,
            use=Use.ADJUSTER,
            max_searches=config.max_searches,
            allowed_domains=config.allowed_domains,
        )
    except ProviderError:
        return _not_verified(NotVerifiedReason.PROVIDER_ERROR, vehicle, 0)

    leido = parse_research(resultado.text)
    busquedas = resultado.searches_used
    if leido.value_cop is None:
        return _not_verified(NotVerifiedReason.NO_VALUE, vehicle, busquedas)
    if not config.is_plausible_vehicle_value(leido.value_cop):
        return _not_verified(NotVerifiedReason.IMPLAUSIBLE, vehicle, busquedas)
    fuente = next(
        (s for s in resultado.sources if _in_allowed_domain(s.url, config.allowed_domains)), None
    )
    if fuente is None:
        return _not_verified(NotVerifiedReason.NO_SOURCE, vehicle, busquedas)
    return VehicleValue(
        status=ValueStatus.FOUND,
        vehicle=vehicle,
        value_cop=leido.value_cop,
        firmness=leido.firmness,
        source=fuente,
        searches_used=busquedas,
    )


def pick_vehicle(vehicles: Sequence[str], narrative: str) -> str | None:
    """De los vehiculos de la poliza, el que nombra el relato; el primero si ninguno.

    Cuenta las palabras de la descripcion que el relato dice, y empata hacia el primero.
    """
    if not vehicles:
        return None
    dichas = set(re.findall(r"\w{3,}", narrative.casefold()))

    def _coincidencias(descripcion: str) -> int:
        return sum(palabra in dichas for palabra in re.findall(r"\w{3,}", descripcion.casefold()))

    return max(vehicles, key=_coincidencias)
