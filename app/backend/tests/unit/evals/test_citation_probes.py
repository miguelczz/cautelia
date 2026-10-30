"""La sonda de citacion de DS-3: que cada forma de fallar se vea, y que sin quien
responda el caso quede no medido y nunca en verde (fase 1, 2026-10-08)."""

from __future__ import annotations

import pytest

from untangle import paths
from untangle.evals import citation_probes
from untangle.evals.models import CitationExpectation
from untangle.evals.runner import api as runner_api
from untangle.evals.runner.failures import TargetUnavailableError
from untangle.policy_rag.citations.models import CoverageOutcome
from untangle.policy_rag.citations.verifier import CitationVerdict, VerificationResult
from untangle.policy_rag.corpus.models import Clause
from untangle.policy_rag.corpus.retrieval import RetrievalProbe, RetrievalResult


def _clausula(clause_id: str, form_id: str = "SA-PAP-2026") -> Clause:
    return Clause(
        tenant_id="stonecroft",
        clause_id=clause_id,
        clause_key=clause_id,
        form_id=form_id,
        form_version="2026.1",
        part="Parte D",
        language="es",
        text="x",
        is_distractor=False,
        issuer_label="Seguros Aburrá",
    )


def _respuesta(
    *citadas: str, outcome: CoverageOutcome = CoverageOutcome.VERIFIED
) -> VerificationResult:
    return VerificationResult(
        outcome=outcome,
        citations=tuple(
            CitationVerdict(
                clause_id=c,
                claim="x",
                outcome=outcome,
                reasons=(),
                amended_by=(),
                clause_version="2026.1",
            )
            for c in citadas
        ),
        clause_language="es" if citadas else None,
    )


RECUPERADAS = RetrievalResult(
    clauses=(
        _clausula("SA-PAP-2026-D.EXCL.3"),
        _clausula("SA-PAP-2026-END-3-D.EXCL.3", form_id="SA-PAP-2026-END-3"),
    ),
    probe=RetrievalProbe(clause_ids=(), sources={}, filtered_by={}),
)

ENDOSO = CitationExpectation(
    policy_number="POL-12",
    question="¿Cubren el equipo de sonido?",
    expected_outcome="verified",
    clause_id="SA-PAP-2026-D.EXCL.3",
    amended_by="SA-PAP-2026-END-3",
)


def test_citar_la_clausula_y_su_endoso_pasa() -> None:
    respuesta = _respuesta("SA-PAP-2026-D.EXCL.3", "SA-PAP-2026-END-3-D.EXCL.3")

    assert citation_probes.evaluate(ENDOSO, RECUPERADAS, respuesta) == []


def test_sin_el_endoso_falla_aunque_cite_la_clausula() -> None:
    fallos = citation_probes.evaluate(ENDOSO, RECUPERADAS, _respuesta("SA-PAP-2026-D.EXCL.3"))

    assert fallos == ["no cito ninguna clausula del endoso 'SA-PAP-2026-END-3'"]


def test_citar_algo_cuando_no_hay_clausula_falla_y_lo_nombra() -> None:
    esperado = CitationExpectation(
        policy_number="POL-1", question="¿Y el terremoto?", expected_outcome="no_clause_found"
    )

    fallos = citation_probes.evaluate(esperado, RECUPERADAS, _respuesta("SA-PAP-2026-D.EXCL.3"))

    assert len(fallos) == 1
    assert "SA-PAP-2026-D.EXCL.3" in fallos[0]


def test_la_clausula_prohibida_falla_aunque_solo_se_recupere() -> None:
    esperado = ENDOSO.model_copy(update={"forbidden_clause_ids": ("SA-PAP-2026-END-3-D.EXCL.3",)})

    fallos = citation_probes.evaluate(esperado, RECUPERADAS, _respuesta("SA-PAP-2026-D.EXCL.3"))

    assert any("prohibida" in f for f in fallos)


def test_no_pude_verificar_nunca_pasa_por_no_hay_clausula() -> None:
    esperado = CitationExpectation(
        policy_number="POL-1", question="¿Y el terremoto?", expected_outcome="no_clause_found"
    )

    fallos = citation_probes.evaluate(
        esperado, None, _respuesta(outcome=CoverageOutcome.UNVERIFIABLE)
    )

    assert fallos and "unverifiable" in fallos[0]


async def test_sin_quien_responda_el_caso_queda_no_medido() -> None:
    runner_api.reset()
    citation_probes.install(None)
    citation_probes.register_citation_probes(paths.repo_root())
    sonda = runner_api.async_check_for("citation_endorsement_electronics_exclusion")
    assert sonda is not None

    with pytest.raises(TargetUnavailableError):
        await sonda(language="es", root=paths.repo_root())
    runner_api.reset()


# --- La compuerta dura: cero citas inexistentes (PRD 11.2 [bloquea], 2026-10-11) ----


def test_una_respuesta_verificada_que_cita_lo_recuperado_no_inventa_nada() -> None:
    respuesta = _respuesta("SA-PAP-2026-D.EXCL.3")

    assert citation_probes.invented(RECUPERADAS, respuesta) == []


def test_citar_una_clausula_que_no_se_recupero_de_esa_poliza_es_inventarla() -> None:
    respuesta = _respuesta("SA-PAP-2026-D.EXCL.3", "SA-PAP-2026-Z.NO.EXISTE")

    fallos = citation_probes.invented(RECUPERADAS, respuesta)

    assert fallos == ["cito 'SA-PAP-2026-Z.NO.EXISTE', que no se recupero de esa poliza"]


def test_una_cita_sin_verificar_dentro_de_una_respuesta_verificada_tambien_cuenta() -> None:
    respuesta = VerificationResult(
        outcome=CoverageOutcome.VERIFIED,
        citations=(
            CitationVerdict(
                clause_id="SA-PAP-2026-D.EXCL.3",
                claim="x",
                outcome=CoverageOutcome.REJECTED,
                reasons=(),
                amended_by=(),
                clause_version="2026.1",
            ),
        ),
        clause_language="es",
    )

    assert citation_probes.invented(RECUPERADAS, respuesta) == [
        "cito 'SA-PAP-2026-D.EXCL.3' sin verificarla (rejected)"
    ]


@pytest.mark.parametrize(
    "outcome",
    [CoverageOutcome.NO_CLAUSE_FOUND, CoverageOutcome.UNVERIFIABLE, CoverageOutcome.REJECTED],
)
def test_una_respuesta_que_no_se_entrega_como_verificada_no_inventa(
    outcome: CoverageOutcome,
) -> None:
    """La compuerta mira lo que **sale**: no encontrar la clausula esperada es del
    otro criterio del caso, y no detiene la entrega por si solo."""
    assert citation_probes.invented(None, _respuesta(outcome=outcome)) == []


async def test_los_dos_criterios_de_un_caso_miran_la_misma_respuesta() -> None:
    """Responder dos veces gastaria el doble y mediria dos respuestas distintas."""
    runner_api.reset()
    pedidas: list[str] = []

    async def responder(pregunta: citation_probes.CitationQuestion) -> tuple[object, object]:
        pedidas.append(pregunta.case_ref)
        return RECUPERADAS, _respuesta("SA-PAP-2026-Z.NO.EXISTE")

    citation_probes.install(responder)  # type: ignore[arg-type]
    citation_probes.register_citation_probes(paths.repo_root())
    try:
        nombre = "endorsement-electronics-exclusion"
        del_caso = runner_api.async_check_for(citation_probes.criterion_of(nombre))
        de_la_compuerta = runner_api.async_check_for(citation_probes.gate_criterion_of(nombre))
        assert del_caso is not None
        assert de_la_compuerta is not None

        await del_caso(language="es", root=paths.repo_root())
        resultado = await de_la_compuerta(language="es", root=paths.repo_root())

        assert len(pedidas) == 1
        assert resultado.passed is False
        assert "no se recupero" in resultado.detail
    finally:
        citation_probes.install(None)
        runner_api.reset()


def test_cada_caso_de_ds3_declara_su_compuerta_y_es_bloqueante() -> None:
    """Sin el criterio en el caso, la compuerta estaria registrada y nadie la
    correria: los casos piden por nombre lo que se les mide."""
    from untangle.evals import loading
    from untangle.evals.gates.gate import blocking_criteria_from_registry

    runner_api.reset()
    citation_probes.register_citation_probes(paths.repo_root())
    try:
        bloqueantes = blocking_criteria_from_registry()
        carpeta = paths.repo_root() / "app" / "evals" / "cases" / "ds3"
        casos = sorted(carpeta.glob("*/*.yaml"))
        assert len(casos) == 46
        for archivo in casos:
            caso = loading.load_case(archivo)
            compuerta = citation_probes.gate_criterion_of(archivo.parent.name)
            assert caso.expected_verdicts.get(compuerta) == "pass", archivo
            assert compuerta in bloqueantes
            assert citation_probes.criterion_of(archivo.parent.name) not in bloqueantes
    finally:
        runner_api.reset()
