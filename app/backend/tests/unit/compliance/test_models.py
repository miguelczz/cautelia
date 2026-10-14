"""Los tipos de lo que U10 guarda: sus invariantes, antes de llegar a la base.

Sin base, sin red y sin modelos: lo que se prueba es que un valor que la tabla
rechazaria ya no se puede construir en el codigo, y que el mensaje dice cual
invariante se rompio. La base es la red de abajo, y la prueban las de
integracion del paso 6.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from untangle.compliance.controls.models import (
    ComplianceReview,
    DisclosureChannel,
    DisclosureRecord,
    FindingCode,
    GuardCategory,
    GuardIntervention,
    InterventionAction,
)

AHORA = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)

#: Una aseguradora con la forma de las de la configuracion. Es una fixture de
#: la prueba, no un identificador real: la forma es lo unico que se valida aqui.
ASEGURADORA = "aseguradora-de-prueba"


def _intervencion(**cambios: Any) -> GuardIntervention:
    campos: dict[str, Any] = {
        "intervention_id": "intervencion-1",
        "tenant_id": ASEGURADORA,
        "case_id": "caso-1",
        "turn_id": "caso-1-turno-2",
        "category": GuardCategory.COVERAGE_PROMISE,
        "pattern_id": "guard.es.coverage_promise.001",
        "action": InterventionAction.SUBSTITUTED,
        "catalog_key": "compliance.guard.coverage_promise",
        "occurred_at": AHORA,
    }
    return GuardIntervention(**(campos | cambios))


def _revision(**cambios: Any) -> ComplianceReview:
    campos: dict[str, Any] = {
        "review_id": "revision-1",
        "tenant_id": ASEGURADORA,
        "case_id": "caso-1",
        "disclosure_ok": True,
        "human_route_ok": True,
        "pii_ok": True,
        "explainability_ok": True,
        "findings": (),
        "reviewed_through_turn": "caso-1-turno-2",
        "reviewed_at": AHORA,
    }
    return ComplianceReview(**(campos | cambios))


# --- Intervenciones (BR1.4 a BR1.6) -------------------------------------------


def test_las_tres_acciones_validas_se_construyen() -> None:
    sustituida = _intervencion()
    descartada = _intervencion(action=InterventionAction.DROPPED, catalog_key=None)
    no_evaluable = _intervencion(
        action=InterventionAction.NOT_EVALUABLE,
        category=None,
        pattern_id=None,
        catalog_key="compliance.guard.degraded",
    )

    assert sustituida.catalog_key == "compliance.guard.coverage_promise"
    assert descartada.catalog_key is None
    assert no_evaluable.category is None


@pytest.mark.parametrize(
    ("cambios", "fragmento"),
    [
        ({"action": InterventionAction.DROPPED}, "solo la descartada"),
        ({"catalog_key": None}, "solo la descartada"),
        ({"action": InterventionAction.NOT_EVALUABLE}, "si y solo si la guardia pudo evaluar"),
        ({"category": None, "pattern_id": None}, "si y solo si la guardia pudo evaluar"),
        ({"pattern_id": None}, "van juntos"),
    ],
)
def test_una_intervencion_que_rompe_una_invariante_no_se_construye(
    cambios: dict[str, Any], fragmento: str
) -> None:
    with pytest.raises(ValidationError) as error:
        _intervencion(**cambios)

    assert fragmento in str(error.value)


@pytest.mark.parametrize(
    "cambios",
    [
        # BR8.2: la frase original no cabe donde va una clave del catalogo.
        {"catalog_key": "Si, esta cubierto por completo."},
        {"pattern_id": "coverage promise"},
        # Una hora sin zona: el dia del registro seria ambiguo.
        {"occurred_at": datetime(2026, 9, 21, 12, 0)},
        {"tenant_id": "Aseguradora Con Espacios"},
    ],
)
def test_texto_libre_o_una_hora_sin_zona_no_entran(cambios: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        _intervencion(**cambios)


# --- Revision (BR5.1) ---------------------------------------------------------


def test_una_revision_con_todo_en_verde_pasa_y_una_con_hallazgos_no() -> None:
    limpia = _revision()
    con_falta = _revision(disclosure_ok=False, findings=(FindingCode.DISCLOSURE_MISSING,))

    assert limpia.passed
    assert not con_falta.passed


def test_los_hallazgos_se_guardan_en_orden_canonico() -> None:
    """Dos revisiones iguales se escriben iguales, las diga quien las diga."""
    revision = _revision(
        pii_ok=False,
        disclosure_ok=False,
        findings=(FindingCode.PII_FOUND, FindingCode.DISCLOSURE_MISSING),
    )

    assert revision.findings == (FindingCode.DISCLOSURE_MISSING, FindingCode.PII_FOUND)


@pytest.mark.parametrize(
    "cambios",
    [
        # Un control en falso sin su codigo.
        {"human_route_ok": False},
        # Un codigo con su control en verdadero.
        {"findings": (FindingCode.ATTACHMENT_MISSING,)},
        # El mismo hallazgo dos veces.
        {
            "pii_ok": False,
            "findings": (FindingCode.PII_FOUND, FindingCode.PII_FOUND),
        },
    ],
)
def test_una_revision_cuyos_controles_no_concuerdan_no_se_construye(
    cambios: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        _revision(**cambios)


# --- Divulgacion (BR4.1) ------------------------------------------------------


def test_la_divulgacion_guarda_la_clave_y_no_el_texto() -> None:
    registro = DisclosureRecord(
        disclosure_id="divulgacion-1",
        tenant_id=ASEGURADORA,
        case_id="caso-1",
        channel=DisclosureChannel.CHAT,
        language="es",
        catalog_key="compliance.disclosure.opening",
        disclosed_at=AHORA,
    )

    assert registro.catalog_key == "compliance.disclosure.opening"
    with pytest.raises(ValidationError):
        registro.evolve(catalog_key="Hola, soy una asistente de inteligencia artificial.")
