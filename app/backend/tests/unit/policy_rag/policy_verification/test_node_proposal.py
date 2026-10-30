"""El nodo de cobertura con quien propone las citas (fase 1, 2026-10-08).

Lo que se prueba es lo que cambia con el puerto: que el modelo ve solo lo recuperado,
que lo que propone llega al verificador exacto y que su fallo es "no pude verificar",
nunca "no hay clausula".
"""

from __future__ import annotations

from typing import Any

import pytest

from untangle.base import ProviderErrorKind, ProviderName, Use
from untangle.orchestration.nodes.policy_verification import node
from untangle.orchestration.nodes.policy_verification.proposal import (
    CitationProposal,
    ProposalRequest,
    ProposedCitation,
)
from untangle.policy_rag.citations.models import CoverageOutcome
from untangle.policy_rag.citations.verifier import Citation, VerificationResult
from untangle.policy_rag.corpus.models import ClauseRelation, IssuedPolicy, RelationKind
from untangle.policy_rag.corpus.retrieval import ClauseSource, RetrievalProbe, RetrievalResult
from untangle.providers.ports import BudgetExhausted, ExhaustedResource, ProviderError

from .test_node import (
    EMBEDDING_MODEL,
    TENANT_ID,
    _clausula,
    _correr,
    _EmbedderFalso,
    _estado,
    _nodo,
    _poliza,
    _reloj,
)

ENDOSO = _clausula("SA-PAP-2026-END-3-D.EXCL.3", part="Endoso 3")
BASE = _clausula("SA-PAP-2026-D.EXCL.3", part="Parte D")


def _recuperadas() -> RetrievalResult:
    return RetrievalResult(
        clauses=(BASE, ENDOSO),
        probe=RetrievalProbe(
            clause_ids=(BASE.clause_id, ENDOSO.clause_id),
            sources={
                BASE.clause_id: ClauseSource(lexical_rank=1, vector_rank=1, closure_of=None),
                ENDOSO.clause_id: ClauseSource(
                    lexical_rank=None, vector_rank=None, closure_of=BASE.clause_id
                ),
            },
            filtered_by={},
        ),
    )


def _con_proponedor(
    monkeypatch: pytest.MonkeyPatch, proponer: Any
) -> tuple[node.PolicyVerificationNode, list[tuple[Citation, ...]]]:
    verificadas: list[tuple[Citation, ...]] = []

    async def _retrieve(*_a: Any, **_k: Any) -> RetrievalResult:
        return _recuperadas()

    async def _find_policy(*_a: Any, **_k: Any) -> IssuedPolicy:
        return _poliza()

    async def _verify(*_a: Any, citations: Any, **_k: Any) -> VerificationResult:
        verificadas.append(tuple(citations))
        return VerificationResult(
            outcome=CoverageOutcome.NO_CLAUSE_FOUND if not citations else CoverageOutcome.REJECTED,
            citations=(),
            clause_language=None,
        )

    _nodo(monkeypatch, retrieve=_retrieve, find_policy=_find_policy, verify=_verify)
    nodo = node.PolicyVerificationNode(
        embed=_EmbedderFalso(), embedding_model=EMBEDDING_MODEL, clock=_reloj, propose=proponer
    )
    return nodo, verificadas


def test_el_modelo_ve_solo_lo_recuperado_y_lo_que_propone_va_al_verificador(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vistas: list[ProposalRequest] = []

    async def proponer(peticion: ProposalRequest) -> CitationProposal:
        vistas.append(peticion)
        return CitationProposal(
            citations=(
                ProposedCitation(clause_id=BASE.clause_id, claim="Excluye el equipo de sonido."),
                ProposedCitation(clause_id=ENDOSO.clause_id, claim="El endoso la modifica."),
            )
        )

    nodo, verificadas = _con_proponedor(monkeypatch, proponer)

    _correr(nodo.run(_estado(question="¿Cubren el equipo de sonido?")))

    [peticion] = vistas
    assert [c.clause_id for c in peticion.clauses] == [BASE.clause_id, ENDOSO.clause_id]
    assert peticion.clauses[1].related_to == BASE.clause_id, "el endoso dice a quien modifica"
    assert peticion.question == "¿Cubren el equipo de sonido?"
    [citas] = verificadas
    assert {c.clause_id for c in citas} == {BASE.clause_id, ENDOSO.clause_id}


def test_una_propuesta_sin_razon_o_sin_clausula_no_llega_al_verificador(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def proponer(_p: ProposalRequest) -> CitationProposal:
        return CitationProposal(
            citations=(
                ProposedCitation(clause_id=BASE.clause_id, claim="  "),
                ProposedCitation(clause_id="", claim="algo"),
            )
        )

    nodo, verificadas = _con_proponedor(monkeypatch, proponer)

    salida = _correr(nodo.run(_estado()))

    assert verificadas == [()]
    assert salida.outcome is CoverageOutcome.NO_CLAUSE_FOUND


@pytest.mark.parametrize(
    "error",
    [
        ProviderError(
            ProviderErrorKind.TIMEOUT, provider=ProviderName.ANTHROPIC, use=Use.CHAT_REPLY
        ),
        BudgetExhausted(
            ExhaustedResource.PROVIDER_QUOTA, provider=ProviderName.ANTHROPIC, use=Use.CHAT_REPLY
        ),
    ],
)
def test_si_el_modelo_falla_es_no_pude_verificar_y_nunca_no_hay_clausula(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    """BR3.4: el fallo de quien propone no se colapsa con un resultado buscado."""

    async def proponer(_p: ProposalRequest) -> CitationProposal:
        raise error

    nodo, verificadas = _con_proponedor(monkeypatch, proponer)

    salida = _correr(nodo.run(_estado()))

    assert salida.outcome is CoverageOutcome.UNVERIFIABLE
    assert verificadas == [], "sin propuesta no se verifica nada"


def test_con_citas_en_la_entrada_no_se_le_pregunta_al_modelo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llamadas: list[ProposalRequest] = []

    async def proponer(peticion: ProposalRequest) -> CitationProposal:
        llamadas.append(peticion)
        return CitationProposal()

    nodo, verificadas = _con_proponedor(monkeypatch, proponer)

    _correr(
        nodo.run(
            _estado(draft_citations=(node.DraftCitation(clause_id=BASE.clause_id, claim="x"),))
        )
    )

    assert llamadas == []
    assert [c.clause_id for c in verificadas[0]] == [BASE.clause_id]


# --- El endoso que el modelo olvido (2026-10-11) -------------------------------

FORMULARIO_DEL_ENDOSO = "SA-PAP-2026-END-3"
ENDOSO_VIGENTE = ENDOSO.model_copy(update={"form_id": FORMULARIO_DEL_ENDOSO})


def _solo_la_base(
    monkeypatch: pytest.MonkeyPatch, *, relacion: RelationKind, endosos: tuple[str, ...]
) -> tuple[Citation, ...]:
    """El modelo cita la clausula y olvida su endoso, que si se recupero."""
    verificadas: list[tuple[Citation, ...]] = []

    async def _retrieve(*_a: Any, **_k: Any) -> RetrievalResult:
        return RetrievalResult(
            clauses=(BASE, ENDOSO_VIGENTE),
            probe=RetrievalProbe(
                clause_ids=(BASE.clause_id, ENDOSO_VIGENTE.clause_id), sources={}, filtered_by={}
            ),
        )

    async def _find_policy(*_a: Any, **_k: Any) -> IssuedPolicy:
        return _poliza(endorsement_ids=endosos)

    async def _verify(*_a: Any, citations: Any, **_k: Any) -> VerificationResult:
        verificadas.append(tuple(citations))
        return VerificationResult(
            outcome=CoverageOutcome.REJECTED, citations=(), clause_language=None
        )

    async def _relations_into(*_a: Any, **_k: Any) -> tuple[ClauseRelation, ...]:
        return (
            ClauseRelation(
                tenant_id=TENANT_ID,
                from_clause=ENDOSO_VIGENTE.clause_id,
                to_clause=BASE.clause_id,
                relation=relacion,
            ),
        )

    async def proponer(_peticion: ProposalRequest) -> CitationProposal:
        return CitationProposal(
            citations=(ProposedCitation(clause_id=BASE.clause_id, claim="Excluye el equipo."),)
        )

    _nodo(
        monkeypatch,
        retrieve=_retrieve,
        find_policy=_find_policy,
        verify=_verify,
        relations_into=_relations_into,
    )
    nodo = node.PolicyVerificationNode(
        embed=_EmbedderFalso(), embedding_model=EMBEDDING_MODEL, clock=_reloj, propose=proponer
    )
    _correr(nodo.run(_estado(question="¿Cubren el equipo de sonido?")))
    [citas] = verificadas
    return citas


def test_si_el_modelo_olvida_el_endoso_vigente_lo_agrega_el_codigo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sin esto la respuesta entera se rechazaba con la clausula y su endoso a la vista."""
    citas = _solo_la_base(
        monkeypatch,
        relacion=RelationKind.ENDORSEMENT_MODIFIES,
        endosos=(FORMULARIO_DEL_ENDOSO,),
    )

    assert [c.clause_id for c in citas] == [BASE.clause_id, ENDOSO_VIGENTE.clause_id]
    # Nadie explico ese endoso: va sin oracion del modelo, y la respuesta usa la del catalogo.
    assert citas[1].claim == ""


@pytest.mark.parametrize(
    ("relacion", "endosos"),
    [
        # Un endoso que esta poliza no tiene no la modifica.
        (RelationKind.ENDORSEMENT_MODIFIES, ()),
        # Otra relacion --una definicion-- no obliga a citar nada.
        (
            next(k for k in RelationKind if k is not RelationKind.ENDORSEMENT_MODIFIES),
            (FORMULARIO_DEL_ENDOSO,),
        ),
    ],
)
def test_solo_se_agrega_el_endoso_que_de_verdad_modifica_esa_poliza(
    monkeypatch: pytest.MonkeyPatch, relacion: RelationKind, endosos: tuple[str, ...]
) -> None:
    citas = _solo_la_base(monkeypatch, relacion=relacion, endosos=endosos)

    assert [c.clause_id for c in citas] == [BASE.clause_id]
