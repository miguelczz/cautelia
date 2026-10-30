"""El insumo `unlisted_driver` en la raiz de composicion: de donde saca la poliza y que dice la traza.

La derivacion en si es pura y la prueban `tests/unit/orchestration/test_unlisted_driver.py`.
Lo que esta prueba vigila es el cableado, sin base: que la poliza se lea por el numero que el caso
tiene atado, que un caso sin poliza o con una poliza que no declara conductores quede ausente, y
que la traza diga **por que** sin llevar el valor, que es dato personal.
"""

from __future__ import annotations

import io
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime

import pytest

from untangle import observability
from untangle.case_record import api as casos_api
from untangle.case_record.models import (
    Case,
    CaseNumber,
    Channel,
    FieldStatus,
    Origin,
    RecordType,
)
from untangle.policy_rag.corpus import api as corpus_api
from untangle.policy_rag.corpus.models import DeclaredDriver, IssuedPolicy
from untangle.server import composition

ASEGURADORA = "stonecroft"
CASO = "case-del-conductor"
DICHO = "Renault Logan 2024. Lo manejaba mi hijo Carlos Ruiz Mora."


@dataclass
class _Lecturas:
    """Lo que el cableado le pidio a la base, para comprobar que no la toca de mas."""

    casos: int = 0
    polizas: list[str] | None = None


def _caso(policy_ref: str | None) -> Case:
    ahora = datetime(2026, 10, 13, 9, 0, tzinfo=UTC)
    return Case(
        case_id=CASO,
        tenant_id=ASEGURADORA,
        case_number=CaseNumber(prefix="SA", serial="1"),
        record_type=RecordType.CLAIM,
        channel=Channel.CHAT,
        origin=Origin.PUBLIC_CHAT,
        language="es",
        policy_ref=policy_ref,
        created_at=ahora,
        updated_at=ahora,
    )


def _poliza(*conductores: str) -> IssuedPolicy:
    return IssuedPolicy(
        tenant_id=ASEGURADORA,
        policy_number="POL-11",
        issuer_tenant=ASEGURADORA,
        form_id="SA-PAP-2026",
        form_version="2026.1",
        named_insured={"full_name": "Natalia Henao Rendón"},
        drivers=tuple(DeclaredDriver(full_name=n) for n in conductores),
        period_start=date(2026, 1, 1),
        period_end=date(2027, 1, 1),
    )


@pytest.fixture
def lecturas(monkeypatch: pytest.MonkeyPatch) -> _Lecturas:
    registro = _Lecturas(polizas=[])

    async def casos(tenant_id: str, case_ids: list[str]) -> tuple[Case, ...]:
        registro.casos += 1
        return (_caso("POL-11"),)

    async def poliza(tenant_id: str, *, policy_number: str) -> IssuedPolicy | None:
        assert registro.polizas is not None
        registro.polizas.append(policy_number)
        return _poliza("Natalia Henao Rendón", "Mateo Henao Gómez")

    monkeypatch.setattr(casos_api, "cases_by_id", casos)
    monkeypatch.setattr(corpus_api, "find_policy", poliza)
    return registro


@contextmanager
def _eventos() -> Iterator[io.StringIO]:
    recogidos = io.StringIO()
    observability.set_stream(recogidos)
    try:
        yield recogidos
    finally:
        observability.set_stream(sys.stdout)


async def test_un_conductor_ajeno_a_la_poliza_del_caso_no_figura(lecturas: _Lecturas) -> None:
    resultado = await composition._conductor_que_no_figura(
        ASEGURADORA, CASO, value=DICHO, status=FieldStatus.STATED
    )

    assert resultado is True
    assert lecturas.polizas == ["POL-11"]


async def test_el_titular_con_su_nombre_figura(lecturas: _Lecturas) -> None:
    resultado = await composition._conductor_que_no_figura(
        ASEGURADORA, CASO, value="Lo conducía Natalia Henao Rendón", status=FieldStatus.CONFIRMED
    )

    assert resultado is False
    assert lecturas.polizas == ["POL-11"]


async def test_sin_decir_nada_del_conductor_no_se_lee_ni_el_caso_ni_la_poliza(
    lecturas: _Lecturas,
) -> None:
    """Una derivacion que no tiene nada que leer no cuesta dos lecturas por decision."""
    resultado = await composition._conductor_que_no_figura(
        ASEGURADORA, CASO, value=None, status=FieldStatus.NOT_STATED
    )

    assert resultado is None
    assert (lecturas.casos, lecturas.polizas) == (0, [])


async def test_un_caso_sin_poliza_identificada_deja_el_insumo_ausente(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def casos(tenant_id: str, case_ids: list[str]) -> tuple[Case, ...]:
        return (_caso(None),)

    async def poliza(tenant_id: str, *, policy_number: str) -> IssuedPolicy | None:
        pytest.fail("no hay numero de poliza que buscar")

    monkeypatch.setattr(casos_api, "cases_by_id", casos)
    monkeypatch.setattr(corpus_api, "find_policy", poliza)

    with _eventos() as recogidos:
        resultado = await composition._conductor_que_no_figura(
            ASEGURADORA, CASO, value=DICHO, status=FieldStatus.STATED
        )

    assert resultado is None
    assert '"policy_identified": false' in recogidos.getvalue()


@pytest.mark.parametrize("conductores", [(), ("Natalia Henao Rendón",)], ids=["ninguno", "titular"])
async def test_una_poliza_sin_conductores_adicionales_declarados_solo_conoce_al_titular(
    monkeypatch: pytest.MonkeyPatch, conductores: tuple[str, ...]
) -> None:
    """Sin lista (`()`), nada que comparar: ausente. Con solo el titular, un ajeno no figura."""

    async def casos(tenant_id: str, case_ids: list[str]) -> tuple[Case, ...]:
        return (_caso("POL-11"),)

    async def poliza(tenant_id: str, *, policy_number: str) -> IssuedPolicy | None:
        return _poliza(*conductores)

    monkeypatch.setattr(casos_api, "cases_by_id", casos)
    monkeypatch.setattr(corpus_api, "find_policy", poliza)

    resultado = await composition._conductor_que_no_figura(
        ASEGURADORA, CASO, value=DICHO, status=FieldStatus.STATED
    )

    assert resultado is (True if conductores else None)


async def test_la_traza_dice_por_que_queda_ausente_y_no_lleva_lo_que_dijo_la_persona(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def casos(tenant_id: str, case_ids: list[str]) -> tuple[Case, ...]:
        return (_caso("POL-11"),)

    async def poliza(tenant_id: str, *, policy_number: str) -> IssuedPolicy | None:
        return _poliza()

    monkeypatch.setattr(casos_api, "cases_by_id", casos)
    monkeypatch.setattr(corpus_api, "find_policy", poliza)

    with _eventos() as recogidos:
        resultado = await composition._conductor_que_no_figura(
            ASEGURADORA, CASO, value=DICHO, status=FieldStatus.STATED
        )

    traza = recogidos.getvalue()
    assert resultado is None
    assert "orchestration.driver_not_derivable" in traza
    assert '"policy_declares_drivers": false' in traza
    assert "Carlos" not in traza
    assert "Ruiz" not in traza
