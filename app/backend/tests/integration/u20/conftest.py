"""Lo que las pruebas de integracion de U20 necesitan: datos de visitante de verdad.

La tanda 1 probo la orquestacion con purgadores dobles, que es donde se prueba el
camino del fallo. Lo que aqui se comprueba es lo otro: que **los nueve purgadores
de verdad** dejan la base sin un dato de visitante, que el registro de gasto
sobrevive, y que la corrida queda escrita donde el contador de 24 horas la busca.

**Se siembra por la superficie de cada dueno** --el caso por la API de U4, la
conversacion por la de U13, el enlace por la de U2-- y no con `INSERT` a mano
donde hay API. Una siembra escrita a mano puede dejar una fila que el aplicativo
no sabe crear, y entonces lo que se borra no es lo que un visitante deja. Donde
no hay API --la ventana del presupuesto y el contador del sitio-- se escribe
directo y se dice por que: llegar a ellos de verdad cuesta dinero.

**El corte de todas estas pruebas es `HOY`** y lo sembrado es de `AYER`: es la
forma de la corrida nocturna, que barre lo anterior a su propio instante.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx2
import pytest
from fastapi import FastAPI

from untangle.case_record import api as casos
from untangle.case_record.models import Channel, Origin, RecordType
from untangle.chat import api as chat_api
from untangle.chat import session as chat
from untangle.copy_catalog import api as copy_api
from untangle.inbox import events as avisos
from untangle.providers import config as provider_config
from untangle.server import composition, spend_wiring, voice_routes
from untangle.settings import Settings
from untangle.telemetry.activation import api as activacion
from untangle.telemetry.activation.models import ActivationMilestone, ActivationSource
from untangle.telemetry.spend import api as spend
from untangle.telemetry.spend import budget
from untangle.telemetry.spend.models import WINDOW_DAYS, WINDOW_START, BudgetWindow, QuotaScope
from untangle.telemetry.traces import api as trazas
from untangle.telemetry.traces import repository as trazas_repo
from untangle.tenancy import ephemeral, session, visitor_access
from untangle.voice import session as llamadas
from untangle.voice.models import VoiceMode

CLAVE_DE_ENLACES = "marca-de-clave-de-enlaces-que-no-debe-salir-000020"
#: La del token de socket, otra a proposito (PENDIENTES 1.16).
CLAVE_DEL_SOCKET = "marca-de-clave-del-token-de-voz-que-no-sale-000020"

#: El dia de estas pruebas. El reinicio corta en su propio instante, asi que lo
#: sembrado es de la noche anterior y el corte es el mediodia de hoy.
AYER = datetime(2026, 10, 1, 22, 0, tzinfo=UTC)
HOY = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)

VENTANA_FIN = WINDOW_START + timedelta(days=WINDOW_DAYS)

ORIGEN = "https://demo.untangle.local"

SEMBRAR_VENTANA = """
    INSERT INTO budget_window (
        window_start, window_end, billable_spent_usd, cap_usd, alert_usd,
        alert_sent_at, recording_reserve_usd, recording_reserve_status,
        recording_spent_usd, unmeasured_billable_calls, unmeasured_recording_calls,
        updated_at
    ) VALUES (
        :inicio, :fin, :gastado, '5.00', '3.00',
        NULL, '0.225', 'measured', '0', 0, 0, :ahora
    )
"""

SEMBRAR_GASTO = """
    INSERT INTO spend_entry (
        entry_id, provider, model, use, tenant_ref, case_ref, units, unit_kind,
        unit_price_usd, price_list_version, price_list_effective_date, cost_usd,
        cost_status, billable, lane, source, occurred_at
    ) VALUES (
        :entry_id, 'gemini', 'gemini-3.1-flash-lite', 'chat', :tenant_ref, :case_ref,
        '1000', 'input_tokens', '0.0000001', 'v1', '2026-09-16', '0.0001',
        'measured', true, 'public', 'counted_locally', :ocurrio
    )
"""

#: El contador del sitio: su sujeto es el literal `site` y no nombra a nadie, asi
#: que el purgador de U5 lo **conserva**. Se siembra directo porque consumirlo de
#: verdad pasa por el presupuesto, y eso es gasto.
SEMBRAR_CONTADOR_DEL_SITIO = """
    INSERT INTO quota_counter (
        counter_key, scope, subject_key, period_start, count, limit_at_period_start, updated_at
    )
    VALUES (:clave, 'voice_calls_site_day', 'site', :periodo, 1, 1, :ahora)
"""

CONTAR = "SELECT count(*) AS total FROM {tabla}"


@dataclass(frozen=True)
class Sembrado:
    """Lo que quedo sembrado, para que una prueba pueda nombrarlo despues."""

    tenant_id: str
    case_id: str
    case_number: str
    visitor_key: str
    visitor_key_digest: str
    link_token: str
    chat_session_id: str
    call_id: str
    tablas: tuple[str, ...]


async def sembrar_datos_de_visitante(tenant_id: str) -> Sembrado:
    """Todo lo que un visitante deja en una noche, por la superficie de cada dueno."""
    clave = visitor_access.new_visitor_key()
    registro = await visitor_access.resolve_visitor_key(
        tenant_id=tenant_id, visitor_key=clave, origin=ORIGEN, now=AYER
    )

    caso = await casos.create_case(
        tenant_id,
        casos.NewCase(
            case_id="case-de-visitante-de-ayer",
            record_type=RecordType.CLAIM,
            channel=Channel.CHAT,
            origin=Origin.PUBLIC_CHAT,
            language="es",
        ),
        now=AYER,
    )

    enlace = await visitor_access.issue_case_link(
        tenant_id=tenant_id,
        case_id=caso.case_id,
        signing_key=CLAVE_DE_ENLACES,
        now=AYER,
    )

    conversacion = await chat.open_session(
        tenant_id=tenant_id,
        visitor_key_digest=registro.visitor_key_hash,
        origin_digest=registro.origin,
        language="es",
        now=AYER,
    )

    llamada = await llamadas.open_call(
        tenant_id=tenant_id,
        visitor_key_digest=registro.visitor_key_hash,
        language="es",
        voice_mode=VoiceMode.PRIMARY,
        now=AYER,
    )

    await avisos.append(
        tenant_id,
        case_id=caso.case_id,
        kind=avisos.EventKind.CASE_CREATED,
        summary="llamo diciendo que su auto quedo con la puerta hundida",
        language="es",
        now=AYER,
    )

    await activacion.record_milestone(
        tenant_id=tenant_id,
        visitor_key_hash=registro.visitor_key_hash,
        milestone=ActivationMilestone.FIRST_MESSAGE,
        source=ActivationSource.VISITOR,
        now=AYER,
    )

    await trazas.open_summary(
        trace_id="traza-de-visitante-de-ayer",
        tenant_id=tenant_id,
        case_id=caso.case_id,
        visitor_key_hash=registro.visitor_key_hash,
    )

    # Los dos contadores del chat: su sujeto es el resumen de la clave del
    # navegador, asi que son dato de visitante aunque su tabla sea del proyecto.
    # El del chat no pasa por el presupuesto, asi que consumirlo no gasta nada.
    await spend.check_quota(QuotaScope.CHAT_MESSAGES_DAY, registro.visitor_key_hash, now=AYER)
    await spend.check_quota(
        QuotaScope.CHAT_MESSAGES_SESSION,
        conversacion.chat_session_id,
        now=AYER,
        period_start=AYER,
    )

    return Sembrado(
        tenant_id=tenant_id,
        case_id=caso.case_id,
        case_number=str(caso.case_number),
        visitor_key=clave,
        visitor_key_digest=registro.visitor_key_hash,
        link_token=enlace.token,
        chat_session_id=conversacion.chat_session_id,
        call_id=llamada.call_id,
        tablas=(
            "visitor_key",
            "case_access_link",
            "case_record",
            "chat_session",
            "call_session",
            "inbox_event",
            "activation_progress",
            "trace_summary",
        ),
    )


async def sembrar_caso_del_generador(tenant_id: str, *, case_id: str = "seed-del-generador") -> str:
    """Un caso con origen `generator`: el que el reinicio **conserva**."""
    caso = await casos.create_case(
        tenant_id,
        casos.NewCase(
            case_id=case_id,
            record_type=RecordType.CLAIM,
            channel=Channel.CHAT,
            origin=Origin.GENERATOR,
            language="es",
        ),
        now=AYER,
    )
    return caso.case_id


async def sembrar_dinero(tenant_id: str, *, case_id: str | None) -> None:
    """La ventana, una fila del libro mayor y el contador del sitio.

    Las tres se escriben directo: llegar a ellas de verdad cuesta dinero, y una
    suite que consumiera el presupuesto dejaria al proyecto sin voz para
    demostrarlo, que es lo que el techo existe para evitar.
    """
    async with session.unscoped_session() as sesion:
        await session.execute_sql(
            sesion,
            SEMBRAR_VENTANA,
            inicio=WINDOW_START,
            fin=VENTANA_FIN,
            gastado=Decimal("1.50"),
            ahora=AYER,
        )
        await session.execute_sql(
            sesion,
            SEMBRAR_GASTO,
            entry_id="entrada-de-ayer",
            tenant_ref=tenant_id,
            case_ref=case_id,
            ocurrio=AYER,
        )
        await session.execute_sql(
            sesion,
            SEMBRAR_CONTADOR_DEL_SITIO,
            clave="contador-del-sitio-de-ayer",
            periodo=AYER,
            ahora=AYER,
        )


async def contar_en(tenant_id: str, tabla: str) -> int:
    """Las filas de una tabla con aseguradora fijada. El nombre no se compone: se elige."""
    async with session.session_for(tenant_id) as sesion:
        fila = await session.fetch_one(sesion, CONTAR.format(tabla=tabla))
    return int(fila["total"]) if fila is not None else 0


async def contar_sin_aseguradora(tabla: str) -> int:
    async with session.unscoped_session() as sesion:
        fila = await session.fetch_one(sesion, CONTAR.format(tabla=tabla))
    return int(fila["total"]) if fila is not None else 0


async def _vaciar() -> None:
    """Deja la base como estaba: las tablas de visitante, el dinero y el registro.

    Antes y despues de cada prueba, no solo despues: una prueba tiene que poder
    correr sola y en cualquier orden, y entrar limpia es la mitad de esa promesa.
    """
    for tenant_id in _aseguradoras():
        async with session.session_for(tenant_id) as sesion:
            for tabla in ("case_record", "chat_session", "call_session", "inbox_event"):
                await session.execute_sql(sesion, f"DELETE FROM {tabla}")  # noqa: S608 -- lista cerrada escrita aqui
            await session.execute_sql(sesion, "DELETE FROM activation_progress")
            await session.execute_sql(sesion, "DELETE FROM case_access_link")
            await session.execute_sql(sesion, "DELETE FROM visitor_key")
            # El libro de seriales emitidos **sobrevive al reinicio**, que es
            # para lo que existe; entre pruebas se vacia igual, porque una
            # prueba que hereda los numeros de la anterior cuenta de mas.
            await session.execute_sql(sesion, "DELETE FROM case_number_issued")
    async with session.unscoped_session() as sesion:
        for tabla in (
            "reset_run_purger",
            "reset_run",
            "spend_entry",
            "quota_counter",
            "budget_window",
            "voice_call_release",
        ):
            await session.execute_sql(sesion, f"DELETE FROM {tabla}")  # noqa: S608 -- lista cerrada escrita aqui


def _aseguradoras() -> tuple[str, ...]:
    from untangle.tenancy import api as tenancy

    return tuple(tenancy.available_ids())


@pytest.fixture
def sin_transporte(tmp_path: Path) -> Iterator[None]:
    """El noveno purgador, apuntando a un archivo de la prueba y no al del repositorio.

    Sin esto, el purgador del backend de trazas barreria el archivo OTLP de la
    corrida real: una prueba que borra un artefacto de quien la corre.
    """
    from untangle.telemetry.traces import export

    export.install_transport(export.FileTransport(tmp_path / "traces.otlp.jsonl"))
    yield None
    export.install_transport(None)


@pytest.fixture
async def base_de_u20(sesiones: ephemeral.EphemeralDatabase) -> AsyncIterator[None]:
    """La base efimera con el almacen de resumenes de traza puesto en la base.

    Sin instalarlo, `open_summary` escribiria en el almacen del proceso y la
    prueba del borrado pasaria sin que `trace_summary` existiera: seria la
    prueba que no puede distinguir.
    """
    del sesiones
    # La contabilidad con **la tabla de precios y los planes de verdad**, los que
    # la raiz de composicion instala: los contadores de cuota del chat son parte
    # de lo que el reinicio se lleva, y con una tabla inventada esta suite estaria
    # borrando contadores que el aplicativo no crea asi.
    spend.install(spend_wiring.spend_runtime(provider_config.load()))
    trazas.install_summary_store(trazas_repo.DatabaseSummaryStore())
    await _vaciar()
    yield
    await _vaciar()
    trazas.reset_summaries()
    spend.reset()


def aseguradora() -> str:
    return _aseguradoras()[0]


def foto(*, techo: str = "20.00") -> object:
    """Una foto del presupuesto con sitio para dos llamadas.

    Con el techo de verdad (5 USD) el cupo del sitio es **una** llamada al dia, y
    las pruebas de esta carpeta necesitan abrir una y retomarla: con una sola, la
    retoma chocaria contra el carril del sitio y la prueba diria que la ventana de
    la demostracion la paro, que es lo contrario de lo que comprueba.

    La reserva de grabacion se convierte con **la misma aritmetica que la
    aplicacion**: sin reserva el restante publico sale sin medir, y un restante sin
    medir cierra el carril del sitio.
    """
    reserva = spend.recording_reserve_usd()
    return budget.state(
        BudgetWindow(
            window_start=WINDOW_START,
            window_end=VENTANA_FIN,
            billable_spent_usd=Decimal(0),
            cap_usd=Decimal(techo),
            alert_usd=Decimal(techo) * Decimal("0.6"),
            unmeasured_billable_calls=0,
            recording_reserve_usd=reserva.amount_usd,
            recording_reserve_status=reserva.status,
            updated_at=HOY,
        )
    )


@pytest.fixture
async def app(
    sesiones: ephemeral.EphemeralDatabase,
    base_de_u20: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[FastAPI]:
    """La aplicacion de verdad, **sin sembrar ningun reinicio**.

    Es la diferencia con las demas carpetas: aqui la ventana de la demostracion es
    lo que se prueba, asi que cada prueba siembra la corrida que necesita --o
    ninguna-- y el estado de partida es el de una base recien creada.
    """
    del base_de_u20
    ajustes = Settings(
        env="local",
        database_url=sesiones.app_url,
        commit_sha="abc1234",
        case_link_signing_key=CLAVE_DE_ENLACES,
        voice_token_signing_key=CLAVE_DEL_SOCKET,
    )
    construida = composition.build_app(ajustes, dist_dir=tmp_path)

    async def presupuesto(*, now: datetime | None = None) -> object:
        del now
        return foto()

    monkeypatch.setattr(spend, "budget_state", presupuesto)
    try:
        yield construida
    finally:
        # Un mensaje aceptado se atiende aunque su flujo no este abierto (2026-10-13), asi
        # que la entrega puede seguir corriendo cuando la prueba acaba: se espera antes de
        # desmontar la base, o su ultima escritura cae sobre un caso que ya no existe.
        await asyncio.gather(*list(chat_api._ENTREGAS), return_exceptions=True)
        await session.dispose()
        session.configure(sesiones.app_url)
        spend.reset()
        trazas.reset_summaries()
        copy_api.reset()
        voice_routes.reset()


def cliente(app: FastAPI) -> httpx2.AsyncClient:
    """Un navegador. **Sobre `https`**: la galleta del visitante se pone `Secure`,
    y un cliente en texto plano la descartaria en silencio."""
    transporte = httpx2.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx2.AsyncClient(transport=transporte, base_url="https://testserver")


__all__ = [
    "AYER",
    "CLAVE_DEL_SOCKET",
    "CLAVE_DE_ENLACES",
    "HOY",
    "Sembrado",
    "aseguradora",
    "base_de_u20",
    "contar_en",
    "contar_sin_aseguradora",
    "sembrar_caso_del_generador",
    "sembrar_datos_de_visitante",
    "sembrar_dinero",
    "sin_transporte",
]
