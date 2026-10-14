"""Al terminar una conversacion de evaluacion, la oferta sin contestar se da por rechazada.

Desde el 2026-10-13 un reporte completo queda en revision con la oferta de datos opcionales
abierta, y el chat la da por rechazada a los dos minutos. El conductor hace lo mismo sin
esperarlos y lee el caso cuando el fondo lo saco de revision (2026-10-14: once casos en rojo
por leerlo antes). Sin base: el caso se lee por un doble.
"""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace

import pytest

from untangle.case_record import api as casos
from untangle.case_record.models import CaseState
from untangle.evals.drivers import chat as chat_driver


class Caso:
    """El caso tal como lo ve el conductor: pasa a `tras_resolver` cuando alguien lo resuelve."""

    def __init__(self, estado: CaseState, *, tras_resolver: CaseState | None = None) -> None:
        self.estado = estado
        self.tras_resolver = tras_resolver
        self.resoluciones: list[tuple[str, str]] = []

    async def leer(self, tenant_id: str, case_id: str) -> SimpleNamespace:
        return SimpleNamespace(state=self.estado)

    async def resolver(self, case_id: str, tenant_id: str) -> None:
        self.resoluciones.append((case_id, tenant_id))
        if self.tras_resolver is not None:
            self.estado = self.tras_resolver


@pytest.fixture(autouse=True)
def _sin_resolvedor() -> Iterator[None]:
    chat_driver.install_review_settler(None)
    yield
    chat_driver.install_review_settler(None)


def _con(caso: Caso, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(casos, "get_case", caso.leer)
    chat_driver.install_review_settler(caso.resolver)


async def test_un_reporte_en_revision_se_resuelve_y_se_espera_a_que_salga_de_ella(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    caso = Caso(CaseState.DECIDING, tras_resolver=CaseState.DERIVED)
    _con(caso, monkeypatch)

    await chat_driver._resolver_como_si_cerrara_la_pestana("tenant-x", "case-1")

    assert caso.resoluciones == [("case-1", "tenant-x")]
    assert caso.estado is CaseState.DERIVED


@pytest.mark.parametrize("estado", [CaseState.CAPTURING, CaseState.CLOSED, CaseState.DERIVED])
async def test_un_caso_fuera_de_revision_no_se_toca(
    estado: CaseState, monkeypatch: pytest.MonkeyPatch
) -> None:
    caso = Caso(estado)
    _con(caso, monkeypatch)

    await chat_driver._resolver_como_si_cerrara_la_pestana("tenant-x", "case-1")

    assert caso.resoluciones == []


async def test_sin_caso_o_sin_resolvedor_no_se_hace_nada(monkeypatch: pytest.MonkeyPatch) -> None:
    caso = Caso(CaseState.VERIFYING, tras_resolver=CaseState.DERIVED)
    monkeypatch.setattr(casos, "get_case", caso.leer)

    await chat_driver._resolver_como_si_cerrara_la_pestana("tenant-x", "case-1")
    chat_driver.install_review_settler(caso.resolver)
    await chat_driver._resolver_como_si_cerrara_la_pestana("tenant-x", None)

    assert caso.resoluciones == []
    assert caso.estado is CaseState.VERIFYING


async def test_si_el_fondo_no_lo_saca_de_revision_la_espera_tiene_tope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    caso = Caso(CaseState.DECIDING)  # nadie lo saca de revision
    _con(caso, monkeypatch)
    monkeypatch.setattr(chat_driver, "ESPERA_DEL_DESENLACE_S", 0.5)

    await chat_driver._resolver_como_si_cerrara_la_pestana("tenant-x", "case-1")

    assert caso.resoluciones == [("case-1", "tenant-x")]
    assert caso.estado is CaseState.DECIDING
