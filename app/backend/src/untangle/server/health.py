"""La salud del proceso: vivo y listo (C-02, F7, BR5.1 a BR5.3, FD-U6-6).

Dos preguntas distintas con dos rutas distintas:

- **Vivo** (`/api/health/live`) responde 200 mientras el proceso corre. No toca
  la base ni los proveedores: es lo que dice "el proceso existe".
- **Listo** (`/api/health/ready`) dice si el proceso puede atender: la base
  responde, la configuracion de aseguradoras esta cargada y cada superficie
  montada responde a su sonda. Es lo que mira el chequeo periodico y lo que la
  interfaz consulta mientras espera a que la demo despierte.

**503 solo cuando no hay base o no hay configuracion** (NFR16.2). Una superficie
caida sale `down` con 200: el chequeo periodico tiene que poder distinguir "no
despierta" de "el chat esta caido", y el chat caido no apaga la bandeja.

**Nada aqui llama a un proveedor, gasta dinero, consume un limite de visitante
ni registra un hito de activacion** (BR5.1, BR5.2, BR8.4, SEC-U6.9). Los
indicadores de diagnostico que U1 y U5 publicaban en el `/health` retirado
--cuantos precios cargo la tabla y que usos tienen clave-- se calculan **una vez
al arrancar** y viajan como nombres de uso y un conteo, nunca como una clave ni
como una llamada de comprobacion (FD-U6-6, SEC-U6.3).

**Todo en un segundo** (C-02, NFR16.4). La base y las sondas corren a la vez;
la base tiene medio segundo y cada sonda el suyo, de medio segundo como mucho.

**El reinicio nocturno es un indicador y no una condicion** (2026-10-13). Pasadas
24 horas sin un reinicio exitoso la demo deja de aceptar casos nuevos (BR3.2 de
U20), y nadie se enteraba: el campo `checks.demo_reset` lo hace legible desde
fuera, para el chequeo diario de GitHub Actions. Como `providers`, **no vuelve no
apto al proceso**: el chat de los casos ya abiertos y la lectura siguen
funcionando con el reinicio vencido, y apagar la salud por eso los apagaria.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, Self

from fastapi import APIRouter
from pydantic import Field, model_validator

from untangle import observability
from untangle.base import Frozen
from untangle.demo_operations import api as demo
from untangle.demo_operations.api import ResetRun
from untangle.server.problems import ProblemCode, ProblemError, problem_responses
from untangle.server.surfaces import SurfaceRegistry
from untangle.surface_spec import SurfaceId
from untangle.tenancy import api as tenancy

#: Cuanto puede tardar la comprobacion de la base, en segundos. Medio segundo:
#: corre a la vez que las sondas, que tienen el mismo tope, y los dos juntos
#: caben en el segundo de C-02 con margen para responder.
DATABASE_TIMEOUT_S = 0.5

#: Cuanto puede tardar la lectura del ultimo reinicio exitoso, en segundos. Igual
#: que la base y por la misma razon: corre a la vez que ella y las sondas, y no
#: puede alargar la salud mas alla del segundo de C-02.
DEMO_RESET_TIMEOUT_S = 0.5

#: La consulta que comprueba la base. No lee ninguna tabla: lo que se pregunta
#: es si la base responde por el punto unico de sesion, no que hay dentro.
DATABASE_PROBE_SQL = "SELECT 1 AS ok"

#: Lo que dice la salud cuando el despliegue no declaro su commit. Es verdad;
#: inventar uno no lo seria.
VERSION_UNKNOWN = "unknown"

#: Cada cuanto conviene volver a preguntar a un proceso que no esta listo. Es el
#: mismo intervalo con el que la interfaz consulta mientras espera (BR5.4).
READY_RETRY_AFTER_S = 5

type DatabaseCheck = Callable[[], Awaitable[None]]
type DemoResetProbe = Callable[[], Awaitable[DemoResetCheck]]


class DatabaseStatus(StrEnum):
    """El estado de la base en el reporte (C-02).

    U6 produce `ok` y `down`. `degraded` es del contrato y queda reservado: nada
    en esta unidad sabe distinguir una base degradada de una que responde, y
    escribirlo sin saberlo seria inventar el estado.
    """

    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"


class LiveReport(Frozen):
    """La respuesta de vivo."""

    status: Literal["live"] = "live"


class SurfaceCheck(Frozen):
    """El resultado de la sonda de una superficie montada (OBS-U6.1)."""

    status: Literal["ok", "down"]
    duration_ms: int = Field(ge=0)


class ProviderIndicators(Frozen):
    """Los indicadores de diagnostico de U1 y U5 (FD-U6-6).

    Nombres de uso y un conteo, **nunca una clave**. No vuelven no apto al
    proceso: sin precio el costo se registra como no medido, y un uso sin clave
    falla al pedirlo nombrando la variable que falta.
    """

    priced_units: int = Field(ge=0)
    uses_with_key: tuple[str, ...]


class DemoResetStatus(StrEnum):
    """Si el reinicio nocturno de la demo esta al dia (BR3.2 de U20).

    Tres valores y no dos: "vencido" y "no pude leerlo" son cosas distintas, y
    colapsarlas haria pasar un fallo de lectura por un reinicio que no corrio, o
    al reves (convencion 8c del equipo).
    """

    #: El ultimo reinicio exitoso es de hace menos de 24 horas.
    CURRENT = "current"
    #: Pasaron 24 horas o mas, o no hay ningun reinicio exitoso conocido: la demo
    #: ya no acepta casos nuevos.
    OVERDUE = "overdue"
    #: No se pudo leer el registro de corridas, o se tardo mas de lo que la salud
    #: puede esperar.
    UNREADABLE = "unreadable"


class DemoResetCheck(Frozen):
    """El estado del reinicio nocturno, con la hora del ultimo exitoso si se conoce.

    Una hora no es dato personal, y aqui no viaja nada mas: ni el identificador de
    la corrida ni lo que borro cada purgador.
    """

    status: DemoResetStatus
    #: Cuando termino el ultimo reinicio exitoso. `None` si no hay ninguno
    #: conocido o si no se pudo leer.
    last_successful_at: datetime | None = None

    @model_validator(mode="after")
    def _la_hora_concuerda_con_el_estado(self) -> Self:
        if self.status is DemoResetStatus.CURRENT and self.last_successful_at is None:
            msg = "un reinicio al dia tiene que decir cuando fue el ultimo exitoso"
            raise ValueError(msg)
        if self.status is DemoResetStatus.UNREADABLE and self.last_successful_at is not None:
            msg = "un reinicio que no se pudo leer no puede traer la hora del ultimo exitoso"
            raise ValueError(msg)
        if self.last_successful_at is not None and self.last_successful_at.tzinfo is None:
            msg = "la hora del ultimo reinicio exitoso no trae zona horaria"
            raise ValueError(msg)
        return self


class HealthChecks(Frozen):
    """Lo que se comprobo. `surfaces`, `providers` y `demo_reset` son aditivos a C-02."""

    database: DatabaseStatus
    tenants: int = Field(ge=0)
    #: Solo las superficies montadas; vacio cuando no hay ninguna, nunca con
    #: valores inventados (BR5.3).
    surfaces: dict[SurfaceId, SurfaceCheck]
    providers: ProviderIndicators
    #: Indicador, no condicion: un reinicio vencido no vuelve no apto al proceso.
    demo_reset: DemoResetCheck


class HealthReport(Frozen):
    """La respuesta de listo (C-02). Solo existe con 200."""

    status: Literal["ready"] = "ready"
    #: El commit que corre.
    version: str
    checks: HealthChecks


@dataclass(frozen=True)
class Readiness:
    """El resultado de evaluar si el proceso puede atender."""

    ready: bool
    checks: HealthChecks


@dataclass(frozen=True)
class HealthDeps:
    """Lo que la salud necesita, entregado por la raiz de composicion."""

    version: str
    providers: ProviderIndicators
    registry: SurfaceRegistry
    #: La comprobacion de la base, o `None` si el proceso arranco sin base.
    database_check: DatabaseCheck | None
    #: Cuantas aseguradoras quedaron cargadas.
    tenant_count: Callable[[], int]
    #: La lectura del reinicio nocturno, o `None` si el proceso arranco sin base:
    #: sin registro de corridas no hay nada que leer y el estado sale
    #: `unreadable`.
    demo_reset_check: DemoResetProbe | None


async def database_check() -> None:
    """Comprueba la base **por el punto unico de sesion** (C-10).

    Se abre la sesion de la primera aseguradora cargada, que es el mismo camino
    por el que pasa cualquier consulta del aplicativo: una salud que llegara a la
    base por otra via diria que responde una puerta que nadie usa. Sin ninguna
    aseguradora cargada no hay sesion que abrir, y eso levanta: el proceso no
    puede llegar a la base, que es lo que la salud tiene que decir.
    """
    disponibles = tenancy.available_ids()
    if not disponibles:
        msg = "no tenant is loaded, so no session can reach the database"
        raise LookupError(msg)
    async with tenancy.session_for(disponibles[0]) as sesion:
        fila = await tenancy.fetch_one(sesion, DATABASE_PROBE_SQL)
    if fila is None:  # pragma: no cover -- SELECT 1 siempre devuelve su fila
        msg = "the database answered the probe with no row"
        raise RuntimeError(msg)


def judge_demo_reset(runs: Sequence[ResetRun], *, now: datetime) -> DemoResetCheck:
    """Si el reinicio esta al dia, **con la regla de U20 y no con una copia**.

    Quien decide si pasaron 24 horas es `accepts_new_cases`, la misma funcion que
    cierra el chat y la voz; aqui no se escribe la ventana por segunda vez, para
    que el aviso y el cierre no puedan discrepar. `runs` son las corridas
    exitosas: un intento fallido no llega hasta aqui.
    """
    ultima = demo.last_successful_reset(runs)
    al_dia = demo.accepts_new_cases(runs, now=now)
    return DemoResetCheck(
        status=DemoResetStatus.CURRENT if al_dia else DemoResetStatus.OVERDUE,
        last_successful_at=None if ultima is None else ultima.finished_at,
    )


async def demo_reset_check() -> DemoResetCheck:
    """Lee el ultimo reinicio exitoso del registro de corridas y lo juzga."""
    return judge_demo_reset(await demo.successful_runs(), now=datetime.now(UTC))


async def _estado_del_reinicio(check: DemoResetProbe | None) -> DemoResetCheck:
    if check is None:
        return DemoResetCheck(status=DemoResetStatus.UNREADABLE)
    try:
        async with asyncio.timeout(DEMO_RESET_TIMEOUT_S):
            return await check()
    except Exception as error:  # noqa: BLE001 -- un registro que no se lee es un estado, no una caida de la salud
        observability.emit(
            "server.demo_reset_unreadable",
            error_type=type(error).__name__,
            timed_out=isinstance(error, TimeoutError),
        )
        return DemoResetCheck(status=DemoResetStatus.UNREADABLE)


async def _estado_de_la_base(check: DatabaseCheck | None) -> DatabaseStatus:
    if check is None:
        return DatabaseStatus.DOWN
    try:
        async with asyncio.timeout(DATABASE_TIMEOUT_S):
            await check()
    except Exception as error:  # noqa: BLE001 -- una base que no responde es un estado, no una caida de la salud
        observability.emit(
            "server.database_check_failed",
            error_type=type(error).__name__,
            timed_out=isinstance(error, TimeoutError),
        )
        return DatabaseStatus.DOWN
    return DatabaseStatus.OK


async def evaluate(deps: HealthDeps) -> Readiness:
    """Si el proceso puede atender, con la base y las sondas **a la vez** (NFR16.4)."""
    base, sondas, reinicio = await asyncio.gather(
        _estado_de_la_base(deps.database_check),
        deps.registry.probe_all(),
        _estado_del_reinicio(deps.demo_reset_check),
    )
    aseguradoras = deps.tenant_count()
    checks = HealthChecks(
        database=base,
        tenants=aseguradoras,
        surfaces={
            superficie: SurfaceCheck(status=resultado.status, duration_ms=resultado.duration_ms)
            for superficie, resultado in sondas.items()
        },
        providers=deps.providers,
        demo_reset=reinicio,
    )
    return Readiness(ready=base is DatabaseStatus.OK and aseguradoras > 0, checks=checks)


def router(deps: HealthDeps) -> APIRouter:
    """Las dos rutas de la salud, sin credencial y sin aseguradora (C-02)."""
    enrutador = APIRouter(prefix="/api/health", tags=["health"])

    @enrutador.get(
        "/live",
        response_model=LiveReport,
        operation_id="getHealthLive",
        responses=problem_responses(),
    )
    async def live() -> LiveReport:
        return LiveReport()

    @enrutador.get(
        "/ready",
        response_model=HealthReport,
        operation_id="getHealthReady",
        responses=problem_responses(503),
    )
    async def ready() -> HealthReport:
        resultado = await evaluate(deps)
        if not resultado.ready:
            # No se registra cada salud exitosa --son miles al mes y no dicen
            # nada que el chequeo no guarde--; una que no esta lista, si.
            observability.emit(
                "server.not_ready",
                database=resultado.checks.database.value,
                tenants=resultado.checks.tenants,
            )
            raise ProblemError(
                status=503,
                # C-01 no tiene un codigo propio para "todavia no esta listo", y
                # no se inventa uno: es la dependencia la que no esta.
                code=ProblemCode.PROVIDER_UNAVAILABLE,
                title="Service not ready",
                detail="The database or the tenant configuration is not available yet.",
                retry_after_s=READY_RETRY_AFTER_S,
            )
        return HealthReport(version=deps.version, checks=resultado.checks)

    return enrutador
