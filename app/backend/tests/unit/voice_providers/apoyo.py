"""Lo que comparten las pruebas de los adaptadores de voz.

- **Clientes de voz con el reproductor**, construidos por la fabrica de verdad
  (`SpeechClients`) con claves generadas en cada prueba: ninguna clave de estas
  pruebas es real ni fija, porque una clave fija en el codigo de prueba es una
  clave en el repositorio.
- **El techo forzado al borde** (regla de `project.md`): la foto del presupuesto
  se arma con el acumulado que pida la prueba, con la aritmetica real de U5, y
  nunca gastando.
- **Un registro de uso** que guarda lo que el adaptador reporto, y **la salida de
  eventos** capturada, para poder afirmar que no lleva audio ni texto.
"""

from __future__ import annotations

import io
import json
import secrets
import sys
from collections.abc import AsyncIterator, Iterator, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from functools import cache
from typing import TYPE_CHECKING, Any

from untangle import observability
from untangle.base import Locale, ProviderName
from untangle.compliance.redaction import api as redaccion
from untangle.providers.ceiling import CeilingGate
from untangle.providers.factory import SpeechClients
from untangle.providers.ports import UsageReport
from untangle.providers.transport import CallTimeouts
from untangle.settings import Settings
from untangle.telemetry.spend import budget
from untangle.telemetry.spend.models import WINDOW_DAYS, WINDOW_START, BudgetState, BudgetWindow

from .replay import ReplayFactory, ReplayTransport

if TYPE_CHECKING:
    from untangle.compliance.redaction.api import Redacted

#: Los tiempos del uso `voice` en `providers.yaml`: dos segundos de conexion y
#: dos de lectura.
TIEMPOS = CallTimeouts(connect_timeout_ms=2000, read_timeout_ms=2000)

#: Las claves de evento que un adaptador de voz puede escribir. Ninguna lleva
#: texto libre: si aparece otra, un evento empezo a cargar algo que no deberia.
CLAVES_DE_EVENTO = frozenset({"event", "provider", "use", "error_kind", "resource", "error"})


@cache
def redactado(texto: str, idioma: Locale) -> Redacted:
    """El texto por el punto unico de redaccion, que es la unica forma legitima de
    tener un `Redacted`. Se guarda en memoria porque cargar el detector cuesta."""
    return redaccion.redact(texto, language=idioma)


@dataclass
class Registro:
    """El registro de uso de prueba: lo que el adaptador reporto, en orden."""

    reports: list[UsageReport] = field(default_factory=list)

    async def report(self, usage: UsageReport) -> None:
        self.reports.append(usage)


class Abierto:
    """Un techo abierto, que cuenta cuantas veces se le pregunto."""

    def __init__(self) -> None:
        self.consultas = 0

    async def ensure_open(self, *, provider: ProviderName, use: object) -> None:
        self.consultas += 1


def foto(*, gastado: str = "0", sin_valorar: int = 0) -> BudgetState:
    """La foto del presupuesto con el acumulado **forzado**, con la aritmetica de U5."""
    ventana = BudgetWindow(
        window_start=WINDOW_START,
        window_end=WINDOW_START + timedelta(days=WINDOW_DAYS),
        billable_spent_usd=Decimal(gastado),
        unmeasured_billable_calls=sin_valorar,
        updated_at=datetime(2026, 9, 21, 12, 0, tzinfo=UTC),
    )
    return budget.state(ventana)


def techo(*, gastado: str = "0", sin_valorar: int = 0) -> CeilingGate:
    """El techo de verdad, leyendo una foto forzada en vez de la base."""
    estado = foto(gastado=gastado, sin_valorar=sin_valorar)

    async def leer() -> BudgetState:
        return estado

    return CeilingGate(leer)


def clientes(
    provider: ProviderName, fixture: Mapping[str, Any]
) -> tuple[SpeechClients, ReplayTransport, ReplayFactory]:
    """Los clientes de voz de verdad, con el reproductor como transporte."""
    transporte = ReplayTransport(fixture)
    fabrica = ReplayFactory(transporte)
    ajustes = Settings(
        voice_deepgram_api_key=secrets.token_urlsafe(24),
        voice_cartesia_api_key=secrets.token_urlsafe(24),
    )
    return SpeechClients(settings=ajustes, transports={provider: fabrica}), transporte, fabrica


@dataclass
class Eventos:
    """La salida de eventos de una prueba, ya separada en lineas JSON."""

    salida: io.StringIO

    @property
    def lineas(self) -> list[dict[str, Any]]:
        return [json.loads(linea) for linea in self.salida.getvalue().splitlines() if linea]

    @property
    def crudo(self) -> str:
        return self.salida.getvalue()


def capturar_eventos() -> Iterator[Eventos]:
    salida = io.StringIO()
    observability.set_stream(salida)
    try:
        yield Eventos(salida)
    finally:
        observability.set_stream(sys.stdout)


async def audio_de(bytes_totales: int, trozo: int = 960) -> AsyncIterator[bytes]:
    """Audio de entrada para la transcripcion: silencio, en trozos de 20 ms."""
    for inicio in range(0, bytes_totales, trozo):
        yield bytes(min(trozo, bytes_totales - inicio))
