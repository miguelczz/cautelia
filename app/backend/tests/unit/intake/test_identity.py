"""BR1.1 a BR1.6: identidad y poliza, sin tocar la base (lo que no la necesita)."""

from __future__ import annotations

from datetime import date

import pytest

from untangle.orchestration.nodes.intake import identity
from untangle.policy_rag.corpus.models import IssuedPolicy

_POLIZA = IssuedPolicy(
    tenant_id="stonecroft",
    policy_number="POL-480915",
    issuer_tenant="stonecroft",
    form_id="form-1",
    form_version="2026.1",
    named_insured={"full_name": "Persona de Prueba", "national_id": "43218907"},
    period_start=date(2026, 1, 1),
    period_end=date(2027, 1, 1),
)


class _EspiaDeBusqueda:
    """Un doble de `PolicyLookupPort` que cuenta llamadas y nunca toca la base."""

    def __init__(self, respuesta: IssuedPolicy | None) -> None:
        self.respuesta = respuesta
        self.calls: list[tuple[str, str]] = []

    async def __call__(self, tenant_id: str, identificador: str) -> IssuedPolicy | None:
        self.calls.append((tenant_id, identificador))
        return self.respuesta


# --- BR1.6: numero incompleto, nunca se busca --------------------------------


@pytest.mark.parametrize("numero", ["POL-4809", "48-0915", "POL480915", "", "POL-48091X"])
async def test_numero_con_forma_invalida_nunca_llega_a_buscar(numero: str) -> None:
    espia = _EspiaDeBusqueda(respuesta=_POLIZA)
    resultado = await identity.identify_by_policy_number("stonecroft", numero, lookup=espia)
    assert resultado.outcome is identity.IdentificationOutcome.MALFORMED
    assert espia.calls == []  # nunca se adivino ni se busco el mas parecido


async def test_numero_bien_formado_si_busca() -> None:
    espia = _EspiaDeBusqueda(respuesta=_POLIZA)
    resultado = await identity.identify_by_policy_number("stonecroft", "POL-480915", lookup=espia)
    assert resultado.outcome is identity.IdentificationOutcome.IDENTIFIED
    assert resultado.policy is _POLIZA
    assert espia.calls == [("stonecroft", "POL-480915")]


# --- BR1.2: la compuerta dura. Ajena e inexistente, exactamente igual. ------


async def test_poliza_ajena_y_poliza_inexistente_dan_el_mismo_desenlace() -> None:
    """`lookup` (`corpus.find_policy`) ya devuelve `None` para las dos; esta
    funcion no vuelve a mirar de cual se trataba -- por eso las dos pruebas de
    abajo llaman a la MISMA rama de codigo con el MISMO doble.
    """
    espia_ajena = _EspiaDeBusqueda(respuesta=None)  # simula la poliza de otra aseguradora
    espia_inexistente = _EspiaDeBusqueda(respuesta=None)  # simula un numero que no existe

    ajena = await identity.identify_by_policy_number("stonecroft", "POL-173620", lookup=espia_ajena)
    inexistente = await identity.identify_by_policy_number(
        "stonecroft", "POL-999999", lookup=espia_inexistente
    )

    assert ajena.outcome is identity.IdentificationOutcome.NOT_FOUND
    assert inexistente.outcome is identity.IdentificationOutcome.NOT_FOUND
    assert ajena == identity.IdentificationResult(outcome=identity.IdentificationOutcome.NOT_FOUND)
    assert ajena == inexistente


async def test_identificar_por_cedula_no_encontrada_es_not_found() -> None:
    espia = _EspiaDeBusqueda(respuesta=None)
    resultado = await identity.identify_by_national_id("stonecroft", "99999999", lookup=espia)
    assert resultado.outcome is identity.IdentificationOutcome.NOT_FOUND


async def test_identificar_por_cedula_encontrada() -> None:
    espia = _EspiaDeBusqueda(respuesta=_POLIZA)
    resultado = await identity.identify_by_national_id("stonecroft", "43218907", lookup=espia)
    assert resultado.outcome is identity.IdentificationOutcome.IDENTIFIED
    assert resultado.policy is _POLIZA


# --- BR1.5: solo lo que el tercero aporto de si mismo ------------------------


def test_disclosed_fields_solo_lo_que_el_tercero_aporto() -> None:
    tercero = identity.ThirdPartyReporter(relation="vecino")
    assert identity.disclosed_fields(tercero) == frozenset({"relation"})


def test_disclosed_fields_no_inventa_nada_que_no_se_dio() -> None:
    tercero = identity.ThirdPartyReporter(name="Ana", relation="hija del asegurado")
    revelado = identity.disclosed_fields(tercero)
    assert revelado == frozenset({"name", "relation"})
    assert "contact" not in revelado
