"""La contabilidad del gasto devuelve el punto de sesion como lo encontro.

**El defecto que estas pruebas fijan.** `open_ledger` apunta el punto unico de
sesion al registro del gasto y `close_ledger` lo soltaba **siempre**. Mientras la
contabilidad solo la usaban tareas que corrian solas no habia nadie a quien
perjudicar. Desde que el alta de una aseguradora invoca la ingesta dentro de su
propio bucle, soltarlo cierra el motor que el alta sigue usando: la ingesta
terminaba bien y el alta moria al sembrar, diciendo que no sabia a que base
conectarse.

Ninguna prueba lo vio porque las que existen sustituyen `open_ledger` y
`close_ledger` por dobles y nunca recorren el par de verdad.

Aqui no hay base: `configure` solo apunta --el motor se crea al primer uso-- asi
que se puede comprobar la contabilidad de la direccion sin levantar nada.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from untangle.server import manual_ledger, spend_wiring
from untangle.settings import Settings
from untangle.telemetry.spend import api as spend
from untangle.tenancy import session

pytestmark = pytest.mark.anyio

#: La comprobacion de verdad, tomada antes de que la fixture la silencie: las pruebas del final
#: ejercitan lo que dice cuando falla.
_COMPROBAR_DE_VERDAD = manual_ledger._comprobar_el_libro

OTRA = "postgresql+psycopg://x:y@otra/registro"
LA_DE_ANTES = "postgresql+psycopg://x:y@antes/aplicativo"


@pytest.fixture(autouse=True)
async def _sin_rastro() -> AsyncIterator[None]:
    """Deja el punto de sesion como estaba, pase lo que pase en la prueba."""
    previo = session.configured_url()
    yield
    if previo is None:
        await session.dispose()
    else:
        session.configure(previo)


@pytest.fixture(autouse=True)
def _contabilidad_muda(monkeypatch: pytest.MonkeyPatch) -> None:
    """Lo que se comprueba es la direccion, no el gasto."""
    monkeypatch.setattr(spend_wiring, "spend_runtime", lambda _config: None)
    monkeypatch.setattr(spend, "install", lambda _runtime: None)
    monkeypatch.setattr(manual_ledger, "_acumulado", _nada)
    monkeypatch.setattr(manual_ledger, "_comprobar_el_libro", _nada)


async def _nada() -> None:
    return None


async def _abrir(url: str) -> None:
    # `config` solo viaja hasta `spend.install`, que esta mudo en estas pruebas.
    await manual_ledger.open_ledger(None, url)  # type: ignore[arg-type]


async def test_no_suelta_la_base_que_ya_estaba_cuando_es_la_misma() -> None:
    """El caso que rompia el alta de una aseguradora.

    La contabilidad del proyecto apunta a la **misma** base que el aplicativo, asi
    que soltarla al cerrar deja sin motor a quien la configuro.
    """
    session.configure(LA_DE_ANTES)

    await _abrir(LA_DE_ANTES)
    await manual_ledger.close_ledger()

    assert session.configured_url() == LA_DE_ANTES


async def test_devuelve_la_de_antes_cuando_la_contabilidad_uso_otra() -> None:
    """Un libro en otra base no puede dejar al proceso apuntando a ella."""
    session.configure(LA_DE_ANTES)

    await _abrir(OTRA)
    assert session.configured_url() == OTRA
    await manual_ledger.close_ledger()

    assert session.configured_url() == LA_DE_ANTES


async def test_suelta_lo_que_puso_cuando_no_habia_nada() -> None:
    """La otra mitad, y la que no hay que romper al arreglar la primera.

    Una tarea que corre sola no tenia base antes; si la contabilidad se la
    quedara puesta, la siguiente creeria estar configurada sin estarlo.
    """
    await session.dispose()

    await _abrir(OTRA)
    await manual_ledger.close_ledger()

    assert session.configured_url() is None


# --- El libro tiene que poder leerse antes de gastar (2026-10-13) ---------------------


async def test_un_libro_ilegible_detiene_el_comando_y_deja_el_punto_de_sesion_como_estaba(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Si el libro no se puede leer, no se llama a nadie y nada queda apuntando a el."""

    async def ilegible() -> None:
        msg = "no se pudo leer el libro"
        raise SystemExit(msg)

    monkeypatch.setattr(manual_ledger, "_comprobar_el_libro", ilegible)
    session.configure(LA_DE_ANTES)

    with pytest.raises(SystemExit, match="no se pudo leer el libro"):
        await _abrir(OTRA)

    assert session.configured_url() == LA_DE_ANTES


async def test_la_base_apagada_se_dice_como_base_apagada_y_no_como_techo_cerrado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un libro ilegible se confundia con "el techo esta cerrado": son dos faltas distintas."""

    async def apagada(**_: object) -> None:
        msg = "no se pudo leer"
        raise spend.SpendUnavailableError(msg) from ConnectionError("rechazada")

    monkeypatch.setattr(manual_ledger, "_comprobar_el_libro", _COMPROBAR_DE_VERDAD)
    monkeypatch.setattr(spend, "budget_state", apagada)

    with pytest.raises(SystemExit) as parada:
        await manual_ledger._comprobar_el_libro()

    texto = str(parada.value)
    assert "mise run services:up" in texto
    assert "UNTANGLE_DATABASE_URL" in texto
    assert "No se llamo a ningun proveedor" in texto
    assert "ventana de presupuesto" not in texto


async def test_una_base_sin_ventana_se_dice_como_ventana_que_falta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sin acumulado no hay techo que comprobar: la falta es la ventana, no la conexion."""

    async def sin_ventana(**_: object) -> None:
        msg = "no hay ninguna ventana"
        raise spend.SpendUnavailableError(msg)

    monkeypatch.setattr(manual_ledger, "_comprobar_el_libro", _COMPROBAR_DE_VERDAD)
    monkeypatch.setattr(spend, "budget_state", sin_ventana)

    with pytest.raises(SystemExit) as parada:
        await manual_ledger._comprobar_el_libro()

    texto = str(parada.value)
    assert "no tiene la ventana de presupuesto" in texto
    assert "No se llamo a ningun proveedor" in texto
    assert "services:up" not in texto


def test_sin_la_variable_de_la_base_el_comando_no_gasta_y_dice_que_falta() -> None:
    """Nunca gastar sin poder anotarlo: sin la base del proyecto el comando se detiene."""
    with pytest.raises(SystemExit) as parada:
        manual_ledger.project_ledger_url(Settings(database_url=None), purpose="la prueba")

    texto = str(parada.value)
    assert "UNTANGLE_DATABASE_URL" in texto
    assert "la prueba" in texto
    assert "services:up" in texto
    assert "No se llamo a ningun proveedor" in texto


def test_con_la_variable_la_base_del_libro_es_la_del_proyecto() -> None:
    assert manual_ledger.project_ledger_url(Settings(database_url=OTRA), purpose="x") == OTRA


async def test_las_filas_que_no_se_pudieron_escribir_se_dicen_al_cerrar(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Un uso gratuito no rompe el turno si falla su escritura, pero un comando a mano no calla."""
    monkeypatch.setattr(spend, "deferred_failures", lambda: 2)
    await _abrir(OTRA)

    await manual_ledger.close_ledger()

    error = capsys.readouterr().err
    assert "2 fila(s) de gasto no se pudieron escribir" in error
    assert "spend:reconcile" in error


async def test_sin_filas_perdidas_el_cierre_no_dice_nada(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(spend, "deferred_failures", lambda: 0)
    await _abrir(OTRA)

    await manual_ledger.close_ledger()

    assert capsys.readouterr().err == ""
