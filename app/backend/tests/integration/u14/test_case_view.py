"""La vista de un caso: sus seis bloques, lo que distingue y lo que no destapa.

BR2.1 a BR2.6, por HTTP y no por la funcion: lo que esta unidad ofrece es una ruta.

Lo que aqui se vigila con mas cuidado es **el modulo que miente sobre si mismo**.
La vista dice reunir seis bloques de cinco unidades; comprobar que la funcion
existe no dice nada. Lo que se comprueba es que los seis **llegan**, con datos
sembrados distintos en cada uno, de modo que un bloque que se quedara vacio o que
copiara al de al lado se vea.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI

from untangle.case_record import api as casos
from untangle.case_record import crypto
from untangle.case_record import history as historial
from untangle.case_record.models import Actor, ActorType, Channel, Speaker
from untangle.case_record.transcript import TurnDraft
from untangle.compliance.controls.models import ComplianceReview, FindingCode
from untangle.compliance.controls.repository import save_review
from untangle.compliance.redaction.api import redact
from untangle.policy_rag.citations.models import CitationCheck, CoverageAnswer, CoverageOutcome
from untangle.policy_rag.citations.repository import save_answer_with_checks
from untangle.rules.models import FiredRule, RuleEvaluation
from untangle.rules.repository import save_evaluation

from .conftest import AHORA, cliente, credencial_de, nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u14")


@pytest.fixture
def aseguradora() -> str:
    from untangle.tenancy import api as tenancy

    return tenancy.available_ids()[0]


async def _ver(app: FastAPI, tenant_id: str, case_id: str) -> dict[str, Any]:
    async with cliente(app, credencial=credencial_de(tenant_id)) as http:
        respuesta = await http.get(f"/api/inbox/{tenant_id}/cases/{case_id}")
    assert respuesta.status_code == 200, respuesta.text
    cuerpo: dict[str, Any] = respuesta.json()
    return cuerpo


async def _sembrar_turno(tenant_id: str, case_id: str, texto: str) -> str:
    """Un turno del asegurado, redactado por U3 antes de guardarse."""
    return await casos.append_turn(
        tenant_id,
        TurnDraft(
            turn_id=f"turn-{uuid.uuid4().hex[:12]}",
            case_id=case_id,
            speaker=Speaker.INSURED,
            channel=Channel.CHAT,
            language="es",
            started_at=AHORA,
        ),
        redact(texto, language="es"),
    )


async def _sembrar_respuesta(
    tenant_id: str, case_id: str, turn_id: str, *, outcome: CoverageOutcome, sufijo: str
) -> None:
    comprobacion = CitationCheck(
        check_id=f"chk-{sufijo}",
        tenant_id=tenant_id,
        case_id=case_id,
        clause_id=f"CL-{sufijo}",
        clause_version="v1",
        claim_redacted="lo que se afirmo",
        outcome=CoverageOutcome.VERIFIED,
        reasons=(),
        checked_at=AHORA,
    )
    await save_answer_with_checks(
        CoverageAnswer(
            answer_id=f"ans-{sufijo}",
            tenant_id=tenant_id,
            case_id=case_id,
            turn_id=turn_id,
            idempotency_key=f"idem-{sufijo}",
            question_redacted=f"pregunta {sufijo}",
            outcome=outcome,
            citation_check_ids=(comprobacion.check_id,),
            answer_language="es",
            clause_language="es",
            created_at=AHORA,
        ),
        checks=(comprobacion,),
    )


async def _sembrar_regla(tenant_id: str, case_id: str) -> None:
    await save_evaluation(
        RuleEvaluation(
            evaluation_id=f"ev-{case_id}",
            tenant_id=tenant_id,
            case_id=case_id,
            ruleset_version="v1",
            category="referral",
            fired_rules=(FiredRule(id="R-DINERO", version=1, touches_money=True),),
            inputs_snapshot={"amount_mentioned": "true"},
            explanation_key="rules.explanation.referral",
            evaluated_at=AHORA,
        )
    )


async def _sembrar_cumplimiento(tenant_id: str, case_id: str, turn_id: str) -> None:
    await save_review(
        ComplianceReview(
            review_id=f"rev-{case_id}",
            tenant_id=tenant_id,
            case_id=case_id,
            disclosure_ok=True,
            human_route_ok=True,
            pii_ok=False,
            explainability_ok=True,
            findings=(FindingCode.PII_FOUND,),
            reviewed_through_turn=turn_id,
            reviewed_at=AHORA,
        )
    )


# --- BR2.2: los seis bloques llegan ------------------------------------------


async def test_la_vista_reune_los_bloques_de_las_cinco_unidades(
    app: FastAPI, aseguradora: str
) -> None:
    """Cada bloque con dato sembrado propio: uno vacio o copiado se ve.

    Es la comprobacion contra "el modulo que miente sobre si mismo": la vista
    **dice** reunir seis bloques, y lo que se afirma aqui es que los seis traen lo
    que su dueña guardo, no que la funcion exista.
    """
    caso = await nuevo_caso(aseguradora)
    turno = await _sembrar_turno(aseguradora, caso, "Me choco un carro en la calle 10.")
    await _sembrar_respuesta(
        aseguradora, caso, turno, outcome=CoverageOutcome.VERIFIED, sufijo="uno"
    )
    await _sembrar_regla(aseguradora, caso)
    await _sembrar_cumplimiento(aseguradora, caso, turno)

    cuerpo = await _ver(app, aseguradora, caso)

    assert cuerpo["completeness_total"] > 0, "el bloque de completitud llego vacio"
    assert cuerpo["fields"], "el bloque de campos llego vacio"
    assert len(cuerpo["transcript"]) == 1, "el bloque de transcripcion llego vacio"
    assert len(cuerpo["coverage_answers"]) == 1, "el bloque de cobertura llego vacio"
    assert cuerpo["rule_category"] == "referral", "el bloque de reglas llego vacio"
    assert cuerpo["fired_rules"] == ["R-DINERO"]
    assert cuerpo["controls_ok"] is False, "el bloque de controles llego vacio"
    assert cuerpo["control_findings"] == ["pii_found"]


async def test_sin_revision_de_cumplimiento_no_se_inventan_cuatro_verdes(
    app: FastAPI, aseguradora: str
) -> None:
    """`None` y no `true`: "todavia no se reviso" no es "los cuatro pasaron".

    Sin esta prueba, un bloque que escribiera `True` por omision diria que un caso
    sin revisar cumple, que es la peor forma de fallar de un control.
    """
    caso = await nuevo_caso(aseguradora)

    cuerpo = await _ver(app, aseguradora, caso)

    assert cuerpo["controls_ok"] is None
    assert cuerpo["control_findings"] == []


# --- BR2.5: dos resultados distintos, dos etiquetas distintas -----------------


async def test_sin_clausula_y_no_pude_verificar_no_se_colapsan(
    app: FastAPI, aseguradora: str
) -> None:
    """Los dos valores llegan distintos al cable.

    Colapsarlos contaminaria con fallos de infraestructura una respuesta que si se
    verifico, que es lo que la convencion del equipo prohibe en el estado, en la
    traza y en el reporte. Aqui tambien.
    """
    caso = await nuevo_caso(aseguradora)
    turno = await _sembrar_turno(aseguradora, caso, "Que cubre mi poliza?")
    await _sembrar_respuesta(
        aseguradora, caso, turno, outcome=CoverageOutcome.NO_CLAUSE_FOUND, sufijo="sin"
    )
    await _sembrar_respuesta(
        aseguradora, caso, turno, outcome=CoverageOutcome.UNVERIFIABLE, sufijo="nopude"
    )

    cuerpo = await _ver(app, aseguradora, caso)

    resultados = {r["outcome"] for r in cuerpo["coverage_answers"]}
    assert resultados == {"no_clause_found", "unverifiable"}


# --- BR2.3: la transcripcion llega redactada y no se destapa ------------------


async def test_la_transcripcion_llega_con_etiquetas_y_no_con_el_dato(
    app: FastAPI, aseguradora: str
) -> None:
    """El telefono que dijo la persona no aparece en ninguna parte de la respuesta.

    Se comprueba sobre la **respuesta entera** y no solo sobre el bloque de la
    transcripcion: un dato personal que se colara por el historial o por la
    pregunta de cobertura seria la misma fuga por otra puerta.
    """
    caso = await nuevo_caso(aseguradora)
    await _sembrar_turno(aseguradora, caso, "Mi telefono es 300 123 4567, llameme.")

    async with cliente(app, credencial=credencial_de(aseguradora)) as http:
        respuesta = await http.get(f"/api/inbox/{aseguradora}/cases/{caso}")

    assert "3001234567" not in respuesta.text
    assert "300 123 4567" not in respuesta.text
    assert respuesta.json()["transcript"][0]["text_redacted"] != ""


async def test_el_valor_de_un_campo_no_viaja_en_la_vista(app: FastAPI, aseguradora: str) -> None:
    """Los campos llegan con su clave y su estado, nunca con su valor.

    El valor sellado lo descifra el unico sitio que sabe hacerlo; una vista que lo
    trajera seria un punto de salida mas, y los puntos de salida se declaran.
    """
    caso = await nuevo_caso(aseguradora)
    entrada = historial.new_change_id()
    await casos.set_field(
        aseguradora,
        _campo(caso, "location", "Carrera 43 con calle 10", entrada=entrada),
        cipher=crypto.active(),
        actor=Actor(actor_type=ActorType.SYSTEM),
        channel=Channel.CHAT,
        change_id=entrada,
    )

    async with cliente(app, credencial=credencial_de(aseguradora)) as http:
        respuesta = await http.get(f"/api/inbox/{aseguradora}/cases/{caso}")

    assert "Carrera 43" not in respuesta.text
    campos = {c["field_key"] for c in respuesta.json()["fields"]}
    assert "location" in campos


def _campo(case_id: str, clave: str, valor: str, *, entrada: str) -> Any:
    from untangle.case_record.models import CaseField, FieldStatus

    return CaseField(
        case_id=case_id,
        field_key=clave,
        value=crypto.active().seal(valor),
        status=FieldStatus.CONFIRMED,
        evidence_change_id=entrada,
        updated_at=datetime(2026, 9, 28, 12, 0, tzinfo=UTC),
    )


# --- El aislamiento, tambien en la vista --------------------------------------


async def test_el_caso_de_otra_aseguradora_responde_como_uno_que_no_existe(
    app: FastAPI, dos_aseguradoras: tuple[str, str]
) -> None:
    """Con el control positivo delante: la propia entrega su caso."""
    ajena, propia = dos_aseguradoras
    caso_ajeno = await nuevo_caso(ajena)
    caso_propio = await nuevo_caso(propia)

    async with cliente(app, credencial=credencial_de(propia)) as http:
        mio = await http.get(f"/api/inbox/{propia}/cases/{caso_propio}")
        suyo = await http.get(f"/api/inbox/{propia}/cases/{caso_ajeno}")
        inventado = await http.get(f"/api/inbox/{propia}/cases/no-existe")

    assert mio.status_code == 200
    assert suyo.status_code == 404
    assert inventado.status_code == 404
    assert _sin_rastro(suyo) == _sin_rastro(inventado)


def _sin_rastro(respuesta: Any) -> dict[str, object]:
    cuerpo = dict(respuesta.json())
    assert cuerpo.pop("trace_id", None), "la respuesta de error no trae rastro (C-01)"
    return cuerpo


# --- El conteo de consultas ---------------------------------------------------


async def test_abrir_un_caso_no_multiplica_las_consultas(
    app: FastAPI, aseguradora: str, contador_de_consultas: Any
) -> None:
    """El objetivo medible de la vista, contado de verdad.

    Reunir seis bloques es la forma mas facil de convertir una pantalla en veinte
    idas a la base sin que nadie lo note: si alguien anade un bloque pidiendolo
    dentro de un bucle, esta prueba se cae.

    Se siembran **dos** respuestas de cobertura y **dos** turnos a proposito: con
    uno de cada, una implementacion que pidiera por elemento daria el mismo numero
    que una que pide por lote.
    """
    caso = await nuevo_caso(aseguradora)
    turno = await _sembrar_turno(aseguradora, caso, "Primero.")
    await _sembrar_turno(aseguradora, caso, "Segundo.")
    await _sembrar_respuesta(aseguradora, caso, turno, outcome=CoverageOutcome.VERIFIED, sufijo="a")
    await _sembrar_respuesta(aseguradora, caso, turno, outcome=CoverageOutcome.VERIFIED, sufijo="b")
    await _sembrar_regla(aseguradora, caso)
    await _sembrar_cumplimiento(aseguradora, caso, turno)

    with contador_de_consultas() as contadas:
        await _ver(app, aseguradora, caso)

    from untangle.inbox.case_view import CONSULTAS_POR_CASO

    # Una mas que la vista: lo anotado para las reglas (monto, cobertura, fraude). Se pide a la
    # vez que los seis bloques y es una consulta por caso, no por elemento. Esta prueba entra
    # con credencial; el visitante con enlace paga ademas la cuenta de sus anotaciones, que es
    # otra consulta, solo cuando el estado del caso deja anotar.
    esperadas = CONSULTAS_POR_CASO + 1
    assert len(contadas) == esperadas, (
        f"abrir un caso costo {len(contadas)} consultas y el objetivo son {esperadas}: {contadas}"
    )
