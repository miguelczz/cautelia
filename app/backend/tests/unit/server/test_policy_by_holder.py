"""La busqueda de polizas por nombre del titular, en la raiz de composicion (2026-10-13).

Es el puerto con el que `intake` propone la poliza de quien dijo su nombre completo cuando el
numero se oyo mal. Sin base: la lectura del corpus se sustituye, y lo que se vigila es el
cableado --de que aseguradora se lee y que se devuelve--, no el aislamiento de la base, que
prueban las pruebas de integracion de `list_policies`.
"""

from __future__ import annotations

from datetime import date

import pytest

from untangle.orchestration.nodes.intake import policy
from untangle.policy_rag.corpus import api as corpus_api
from untangle.policy_rag.corpus.models import IssuedPolicy
from untangle.server import composition

ASEGURADORA = "sunmeadow"


def _poliza(numero: str, titular: str, *vehiculos: str) -> IssuedPolicy:
    return IssuedPolicy(
        tenant_id=ASEGURADORA,
        policy_number=numero,
        issuer_tenant=ASEGURADORA,
        form_id="SUN-PAP-2026",
        form_version="2026.1",
        named_insured={"full_name": titular},
        vehicles=tuple({"make_model_year": v} for v in vehiculos),
        period_start=date(2026, 1, 1),
        period_end=date(2027, 1, 1),
    )


CORPUS = (
    _poliza("POL-200117", "Marco Parker", "Ford Escape 2020"),
    _poliza("POL-422088", "Ana Torres", "Subaru Outback 2014", "Ford F-150 2018"),
    _poliza("POL-398476", "Olivia Russo"),
)


@pytest.fixture
def leidas(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Las aseguradoras cuyo corpus se leyo, en orden."""
    registro: list[str] = []

    async def listar(tenant_id: str) -> tuple[IssuedPolicy, ...]:
        registro.append(tenant_id)
        return CORPUS

    monkeypatch.setattr(corpus_api, "list_policies", listar)
    return registro


async def test_devuelve_la_poliza_del_titular_nombrado_con_lo_que_el_nodo_necesita(
    leidas: list[str],
) -> None:
    encontradas = await composition._polizas_del_titular(
        ASEGURADORA, "Claro, mi nombre completo es Marco Parker y mi póliza es Paul 201 17."
    )

    assert encontradas == (
        policy.PolicyMatch(
            policy_number="POL-200117", holder_name="Marco Parker", vehicle="Ford Escape 2020"
        ),
    )
    # Solo se leyo el corpus de la aseguradora de la llamada.
    assert leidas == [ASEGURADORA]


async def test_el_primer_vehiculo_es_el_que_sale_y_sin_vehiculo_sale_nulo(
    leidas: list[str],
) -> None:
    (ana,) = await composition._polizas_del_titular(ASEGURADORA, "Soy Ana Torres")
    (olivia,) = await composition._polizas_del_titular(ASEGURADORA, "Olivia Russo")

    assert ana.vehicle == "Subaru Outback 2014"
    assert olivia.vehicle is None


@pytest.mark.parametrize(
    "dicho",
    [
        "Soy Marco, mi póliza es Paul 201 17",  # un solo nombre no nombra a nadie
        "Soy Parker",
        "Mi póliza es Paul 201 17",
        "Camila Restrepo Vélez",
        "",
    ],
)
async def test_sin_el_nombre_entero_de_un_titular_no_sale_ninguna_poliza(
    leidas: list[str], dicho: str
) -> None:
    assert await composition._polizas_del_titular(ASEGURADORA, dicho) == ()


async def test_si_el_texto_nombra_a_dos_titulares_salen_las_dos(leidas: list[str]) -> None:
    """Cuantas hay lo decide el nodo: con mas de una, no adivina cual."""
    encontradas = await composition._polizas_del_titular(ASEGURADORA, "Marco Parker y Ana Torres")

    assert {p.policy_number for p in encontradas} == {"POL-200117", "POL-422088"}
