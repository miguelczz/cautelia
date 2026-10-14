"""Lo que la raiz de composicion junta, y que ninguna de las dos piezas ve sola.

Son de integracion porque lo que se comprueba es el **cableado**: que lo que el
adaptador reporta acabe en filas de gasto, y que los resumenes de traza acaben en
la tabla en vez de en la memoria del proceso. Cada mitad funciona por su cuenta
--y sus propias pruebas lo dicen--; lo que ninguna de las dos puede comprobar es
que esten conectadas, porque ninguna importa a la otra.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal

import pytest

from untangle.base import ProviderName, SpendSource, UnitKind, Use
from untangle.copy_catalog import api as copy_api
from untangle.providers import config as providers_config
from untangle.providers import factory, ports
from untangle.server import composition, spend_wiring
from untangle.settings import Settings
from untangle.telemetry.spend import api as spend
from untangle.telemetry.traces import api as trazas
from untangle.telemetry.traces import repository as trazas_repo
from untangle.tenancy import ephemeral, session

from .conftest import sembrar_ventana
from .test_api import MODELO, _runtime


@pytest.fixture(autouse=True)
def montaje(dinero: None) -> Iterator[None]:
    """Deja el proceso como estaba: catalogo, contabilidad, trazas y sesion.

    Esta suite construye la aplicacion entera, que instala cosas en variables de
    modulo. Sin devolverlas a su sitio, la siguiente prueba heredaria el almacen
    de resumenes de esta y la suite dejaria de poder correr en cualquier orden.
    """
    spend.reset()
    spend.install(_runtime())
    yield
    spend.reset()
    trazas.reset_summaries()
    copy_api.reset()


def _reporte(*unidades: tuple[UnitKind, int]) -> ports.UsageReport:
    return ports.UsageReport(
        provider=ProviderName.GEMINI,
        model=MODELO,
        use=Use.CHAT,
        units=tuple(
            ports.UsageUnits(unit_kind=clase, units=Decimal(cuantas)) for clase, cuantas in unidades
        ),
        source=SpendSource.PROVIDER_REPORTED,
        case_ref=None,
    )


async def _filas() -> list[tuple[str, Decimal, str]]:
    """Las filas de gasto en la forma que estas pruebas miran, ya tipadas."""
    async with session.unscoped_session() as sesion:
        filas = await session.fetch_all(
            sesion, "SELECT unit_kind, units, cost_status FROM spend_entry ORDER BY unit_kind"
        )
    return [
        (str(fila["unit_kind"]), Decimal(fila["units"]), str(fila["cost_status"])) for fila in filas
    ]


async def test_una_llamada_de_generacion_deja_una_fila_por_clase_de_unidad(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """El proveedor cobra entrada y salida a precios distintos, y la fila de
    gasto solo admite una clase de unidad: son **dos filas**, no una.

    BR3.1 dice "una fila por llamada" y la entidad no lo permite. Convertirlas a
    una unidad comun perderia el precio de lista con el que se calculo cada una,
    que es justo lo que AC4.8.4 exige guardar.
    """
    await sembrar_ventana()
    sink = spend_wiring.LedgerUsageSink()

    await sink.report(_reporte((UnitKind.INPUT_TOKENS, 1200), (UnitKind.OUTPUT_TOKENS, 300)))
    await spend.flush_deferred()

    filas = await _filas()
    assert [clase for clase, _, _ in filas] == ["input_tokens", "output_tokens"]
    assert [cuantas for _, cuantas, _ in filas] == [Decimal(1200), Decimal(300)]


async def test_una_llamada_sin_recuento_deja_una_fila_no_medida_y_no_cero(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """Una llamada que salio y no volvio **pudo haber consumido** (BR3.1, BR3.3).

    Cero se sumaria como cierto y dejaria el costo por caso por debajo del real;
    no escribir la fila lo dejaria mas bajo todavia. Lo unico honesto es una fila
    que dice "ocurrio y no se pudo valorar".
    """
    await sembrar_ventana()
    sink = spend_wiring.LedgerUsageSink()

    await sink.report(_reporte())
    await spend.flush_deferred()

    filas = await _filas()
    assert len(filas) == 1
    assert filas[0][2] == "not_measured"


def test_la_raiz_instala_el_almacen_de_base_solo_cuando_hay_base(
    base_efimera: ephemeral.EphemeralDatabase,
) -> None:
    """C-23 y BR7.4: sin esta linea los resumenes viven solo en el proceso.

    Y el valor por omision **se queda como esta**, a proposito: hay un camino
    --el del corredor de evaluaciones, la cifra publicada de NFR21-- que llega
    hasta el reporte sin base de datos, y ahi el almacen del proceso es lo
    correcto. Las dos mitades en la misma prueba porque son una sola decision.
    """
    trazas.reset_summaries()
    composition.build_app(Settings(env="local"))
    assert isinstance(trazas.current_summary_store(), trazas.InProcessSummaryStore)

    composition.build_app(Settings(env="local", database_url=base_efimera.app_url))
    assert isinstance(trazas.current_summary_store(), trazas_repo.DatabaseSummaryStore)


def test_la_raiz_construye_un_cliente_por_uso_y_ninguno_sin_su_clave() -> None:
    """Cuatro usos, cuatro clientes, cada uno con **su** clave (BR1.3, ADR-018).

    Sin clave no hay cliente y **no se inventa ninguna**: pedirlo falla nombrando
    la variable de entorno que falta. Cae al pedirlo y no al arrancar porque hay
    un camino que llega hasta el reporte sin cuenta en ningun proveedor; lo que
    si falla al arrancar es `require(...)`, que la raiz llama por los usos que
    ese proceso necesita.
    """
    plataforma = composition.build_app(
        Settings(env="local", chat_model_api_key="prueba-de-cableado")
    ).state.providers

    assert plataforma.clients.available() == (Use.CHAT,)
    # Contra lo que declara `providers.yaml` y no contra un literal: el modelo del
    # chat es configuracion versionada y cambiarlo es un cambio de codigo (se
    # cambio el 2026-10-06 y esta prueba, que lo tenia escrito, puso `main` en rojo
    # durante dos commits). Lo que se prueba es que la raiz cablea **el declarado**.
    declarado = next(
        uso.model for uso in providers_config.load().providers.uses if uso.use is Use.CHAT
    )
    assert plataforma.clients.model_for(Use.CHAT) == declarado

    with pytest.raises(factory.MissingProviderKeyError) as error:
        plataforma.clients.require(Use.VOICE)

    assert "UNTANGLE_VOICE_MODEL_API_KEY" in str(error.value)


def test_el_purgador_de_u5_esta_en_el_registro_escrito_a_mano() -> None:
    """C-11: el registro es explicito y nunca descubrimiento automatico.

    Se nombra por su nombre, no por cuantos hay: el dia que alguien lo borre sin
    querer, esta prueba lo dice.
    """
    assert "spend_quota_counters" in [p.name for p in composition.PURGADORES]
