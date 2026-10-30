"""El resumen de traza contra la base: que sobreviva, que aisle y que se borre.

Cuatro conductas que el almacen del proceso **no puede** demostrar, y por eso
estas pruebas levantan una base de verdad en vez de un doble:

- Que el resumen sobreviva al proceso. Un diccionario en memoria pasa cualquier
  prueba de ida y vuelta dentro de la misma corrida y pierde todo al reiniciar.
- Que la politica de fila filtre antes que el codigo. Es conducta del motor, y un
  doble no la tiene.
- Que la cascada del caso se lleve el resumen. Tambien es del motor: lo que
  `case_record/purge.py` borra es el caso, y el resumen se va con el (BR7.4).
- Que `lost` se guarde como **valor** y no como ausencia. Una fila que
  desapareciera pasaria igual una lectura que devuelve `None`, y la cifra de
  resumenes perdidos --la que dice si el backend de trazas esta sano-- se cuenta
  sobre estas filas.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from untangle.case_record import purge as purga_del_caso
from untangle.telemetry.spend.models import CostStatus, Money
from untangle.telemetry.traces import api, repository
from untangle.telemetry.traces.models import (
    NodeName,
    NodeTiming,
    TraceOutcome,
    TraceSummaryStatus,
)
from untangle.tenancy import ephemeral, session

AHORA = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)

#: Las dos aseguradoras que estas pruebas usan. Salen de la configuracion
#: versionada, igual que en las demas pruebas de la suite.
PROPIA = "stonecroft"
AJENA = "sunmeadow"

CREAR_CASO = """
    INSERT INTO case_record (case_id, tenant_id, case_number, record_type,
                             state, channel, origin, language, created_at, updated_at)
    VALUES (:case_id, :tenant_id, :numero, 'claim', 'capturing', 'chat',
            'public_chat', 'es', :creado, :creado)
"""

CONTAR_RESUMENES = "SELECT count(*) AS total FROM trace_summary WHERE case_id = :case_id"


class RelojFijo:
    """El reloj del modulo de trazas, movido a mano. El plazo se prueba, no se espera."""

    def __init__(self, momento: datetime = AHORA) -> None:
        self.momento = momento

    def now(self) -> datetime:
        return self.momento

    def avanzar(self, segundos: float) -> None:
        self.momento += timedelta(seconds=segundos)


@pytest.fixture
async def trazas(sesiones: ephemeral.EphemeralDatabase) -> AsyncIterator[RelojFijo]:
    """Instala el almacen de base y el reloj fijo, y los suelta al terminar.

    Los dos son estado del proceso: sin soltarlos, la siguiente prueba --de este
    archivo o de cualquier otro-- heredaria una base y un reloj que no pidio.
    Tambien limpia **antes** de ceder el control, que es la mitad de la promesa
    de "corre sola y en cualquier orden" que mas se olvida.
    """
    await _borrar_casos()
    reloj = RelojFijo()
    api.install_clock(reloj)
    api.install_summary_store(repository.DatabaseSummaryStore())
    yield reloj
    api.install_clock(None)
    api.reset_summaries()
    await _borrar_casos()


async def _borrar_casos() -> None:
    """Borra los casos de las dos aseguradoras. Los resumenes se van por la cascada."""
    for tenant_id in (PROPIA, AJENA):
        async with session.session_for(tenant_id) as sesion:
            await session.execute_sql(sesion, "DELETE FROM case_record")


async def _sembrar_caso(
    case_id: str, *, tenant_id: str = PROPIA, numero: str, creado: datetime = AHORA
) -> None:
    async with session.session_for(tenant_id) as sesion:
        await session.execute_sql(
            sesion, CREAR_CASO, case_id=case_id, tenant_id=tenant_id, numero=numero, creado=creado
        )


def _lo_que_trajo_el_rastro() -> TraceOutcome:
    return TraceOutcome(
        nodes=(
            NodeTiming(
                node=NodeName.INTAKE,
                started_at=AHORA,
                duration_ms=320,
                cost=Money.measured(Decimal("0.000200")),
            ),
            NodeTiming(
                node=NodeName.POLICY_VERIFICATION,
                started_at=AHORA,
                duration_ms=640,
                cost=Money.not_measured(),
            ),
        ),
        latency_ms=1450,
        cost=Money.measured(Decimal("0.000231")),
        clauses_retrieved=3,
        clauses_verified=2,
    )


# --- Que sobreviva al proceso -------------------------------------------------


async def test_el_resumen_sobrevive_al_reinicio_del_proceso(trazas: RelojFijo) -> None:
    """Se escribe con un almacen y se lee con **otro**, recien construido.

    Es lo que un almacen en memoria no puede demostrar: ahi la ida y la vuelta
    pasan por el mismo diccionario, y un reinicio se lo lleva entero sin que
    ninguna prueba lo note.
    """
    await _sembrar_caso("CASO-VIVE", numero="SA-910")
    await api.open_summary(
        trace_id="TRAZA-VIVE",
        tenant_id=PROPIA,
        case_id="CASO-VIVE",
        visitor_key_hash="el-del-dueno",
        turn_ref="TURN-1",
    )
    await api.record_trace("TRAZA-VIVE", _lo_que_trajo_el_rastro(), tenant_id=PROPIA)

    # Un almacen nuevo, como el que construiria el proceso al arrancar de cero.
    api.install_summary_store(repository.DatabaseSummaryStore())
    vuelto = await api.trace_summary_for(
        "CASO-VIVE", tenant_id=PROPIA, visitor_key_hash="el-del-dueno"
    )

    assert vuelto is not None
    assert vuelto.trace_id == "TRAZA-VIVE"
    assert vuelto.status is TraceSummaryStatus.READY
    assert vuelto.turn_ref == "TURN-1"
    assert vuelto.latency_ms == 1450
    assert vuelto.clauses_retrieved == 3
    assert vuelto.clauses_verified == 2
    # El costo vuelve con su estado, y el decimal vuelve exacto: guardarlo en
    # coma flotante lo devolveria parecido, que en dinero no es lo mismo.
    assert vuelto.cost == Money.measured(Decimal("0.000231"))
    # Y los nodos vuelven enteros, con el que no se pudo valorar todavia sin
    # valorar: colapsarlo a cero seria inventar una cifra (BR3.3).
    assert [nodo.node for nodo in vuelto.nodes] == [
        NodeName.INTAKE,
        NodeName.POLICY_VERIFICATION,
    ]
    assert vuelto.nodes[1].cost.status is CostStatus.NOT_MEASURED


# --- Que solo lo vea quien lo produjo -----------------------------------------


async def test_otra_clave_de_navegador_recibe_lo_mismo_que_un_caso_que_no_existe(
    trazas: RelojFijo,
) -> None:
    """`None` a los dos, contra la base (BR6.6).

    Contra la base y no solo en memoria porque aqui la fila **existe de verdad**:
    lo que se comprueba es que estando ahi no se devuelva, y que la respuesta sea
    indistinguible de la de un caso que nunca existio. Un "prohibido" confirmaria
    que existe, que es la mitad de lo que el visitante de al lado querria saber.
    """
    await _sembrar_caso("CASO-DUENO", numero="SA-911")
    await api.open_summary(
        trace_id="TRAZA-DUENO",
        tenant_id=PROPIA,
        case_id="CASO-DUENO",
        visitor_key_hash="el-del-dueno",
    )

    del_dueno = await api.trace_summary_for(
        "CASO-DUENO", tenant_id=PROPIA, visitor_key_hash="el-del-dueno"
    )
    de_otro = await api.trace_summary_for(
        "CASO-DUENO", tenant_id=PROPIA, visitor_key_hash="el-de-otro"
    )
    inexistente = await api.trace_summary_for(
        "CASO-QUE-NO-EXISTE", tenant_id=PROPIA, visitor_key_hash="el-de-otro"
    )

    assert del_dueno is not None
    assert de_otro is None
    assert inexistente is None
    # Y la fila sigue ahi: no se devolvio, no se borro.
    async with session.session_for(PROPIA) as sesion:
        fila = await session.fetch_one(sesion, CONTAR_RESUMENES, case_id="CASO-DUENO")
    assert fila is not None
    assert int(fila["total"]) == 1


async def test_desde_otra_aseguradora_el_resumen_no_se_alcanza_ni_con_su_identificador(
    trazas: RelojFijo,
) -> None:
    """La politica de fila filtra antes de que el codigo tenga nada que comparar.

    Ni siquiera la clave correcta del navegador lo alcanza desde otra
    aseguradora: la consulta devuelve cero filas, y este codigo no tendria forma
    de distinguirlo de un resumen que no existe aunque quisiera (BR7.4).
    """
    await _sembrar_caso("CASO-AISLADO", numero="SA-912")
    await api.open_summary(
        trace_id="TRAZA-AISLADA",
        tenant_id=PROPIA,
        case_id="CASO-AISLADO",
        visitor_key_hash="el-del-dueno",
    )

    propia = await api.summary_by_trace(
        "TRAZA-AISLADA", tenant_id=PROPIA, visitor_key_hash="el-del-dueno"
    )
    ajena = await api.summary_by_trace(
        "TRAZA-AISLADA", tenant_id=AJENA, visitor_key_hash="el-del-dueno"
    )

    assert propia is not None
    assert ajena is None


# --- Que `lost` sea un valor guardado -----------------------------------------


async def test_el_estado_lost_se_guarda_como_valor_y_no_como_ausencia(
    trazas: RelojFijo,
) -> None:
    """A los diez segundos la fila sigue ahi, con `lost` escrito (BR6.7).

    Si el vencimiento borrara la fila, esta prueba pasaria igual leyendo `None`, y
    la cifra de resumenes perdidos --la que sirve para ver si el backend de
    trazas esta sano-- no se podria contar. Por eso se mira la tabla ademas de la
    superficie.
    """
    reloj = trazas
    await _sembrar_caso("CASO-PERDIDO", numero="SA-913")
    await api.open_summary(
        trace_id="TRAZA-PERDIDA",
        tenant_id=PROPIA,
        case_id="CASO-PERDIDO",
        visitor_key_hash="el-del-dueno",
    )

    reloj.avanzar(9)
    aun = await api.summary_by_trace(
        "TRAZA-PERDIDA", tenant_id=PROPIA, visitor_key_hash="el-del-dueno"
    )
    assert aun is not None
    assert aun.status is TraceSummaryStatus.RECORDING

    reloj.avanzar(1)
    perdido = await api.summary_by_trace(
        "TRAZA-PERDIDA", tenant_id=PROPIA, visitor_key_hash="el-del-dueno"
    )
    assert perdido is not None
    assert perdido.status is TraceSummaryStatus.LOST

    # El vencimiento se **escribio**: un almacen nuevo lo encuentra igual.
    api.install_summary_store(repository.DatabaseSummaryStore())
    async with session.session_for(PROPIA) as sesion:
        fila = await session.fetch_one(
            sesion,
            "SELECT status FROM trace_summary WHERE trace_id = :id",
            id="TRAZA-PERDIDA",
        )
    assert fila is not None, "la fila desaparecio: `lost` es un valor, no una ausencia"
    assert fila["status"] == "lost"

    # Y el rastro que llega despues no lo revive: `lost` es terminal.
    tardio = await api.record_trace("TRAZA-PERDIDA", _lo_que_trajo_el_rastro(), tenant_id=PROPIA)
    assert tardio is not None
    assert tardio.status is TraceSummaryStatus.LOST


# --- Que el reinicio nocturno se lo lleve -------------------------------------


async def test_el_purgador_nocturno_se_lleva_el_resumen_con_su_caso(trazas: RelojFijo) -> None:
    """BR7.4 y C-11. Lo borra la cascada del caso, no un purgador propio.

    Darle un purgador propio seria declarar un segundo dueno de un borrado que ya
    ocurre, y el dia que los dos discreparan no habria forma de saber cual manda.
    """
    viejo = AHORA - timedelta(days=2)
    await _sembrar_caso("CASO-DE-ANOCHE", numero="SA-914", creado=viejo)
    await api.open_summary(
        trace_id="TRAZA-DE-ANOCHE",
        tenant_id=PROPIA,
        case_id="CASO-DE-ANOCHE",
        visitor_key_hash="el-del-dueno",
    )
    async with session.session_for(PROPIA) as sesion:
        antes = await session.fetch_one(sesion, CONTAR_RESUMENES, case_id="CASO-DE-ANOCHE")
    assert antes is not None
    assert int(antes["total"]) == 1

    resultado = await purga_del_caso.CASE_RECORD_PURGER.purge(older_than=AHORA)

    assert resultado.deleted >= 1
    assert "trace_summary" in purga_del_caso.CASE_RECORD_PURGER.tables
    async with session.session_for(PROPIA) as sesion:
        despues = await session.fetch_one(sesion, CONTAR_RESUMENES, case_id="CASO-DE-ANOCHE")
    assert despues is not None
    assert int(despues["total"]) == 0

    # Y la superficie responde igual que si nunca hubiera existido.
    assert (
        await api.trace_summary_for(
            "CASO-DE-ANOCHE", tenant_id=PROPIA, visitor_key_hash="el-del-dueno"
        )
        is None
    )
