"""Pruebas del nodo `policy_verification`, sin base de datos (CG-U8-4, paso 8).

Cada regla de precedencia o de apagado que le toca a esta tanda lleva su propia
prueba, aislada: BR5.2 (un reintento y luego `unverifiable`, con su rastro
doble), BR3.1 aplicado por el nodo (nada recuperado rechaza cualquier cita
propuesta, sin necesidad de conocer la póliza), BR3.4/BR5.6 (`no_clause_found`
frente a `unverifiable`, nunca colapsados), BR5.5/AC2.7.2 (el monto se difiere
cuando hay un endoso vigente) y BR5.8 (el aviso de idioma cruzado).

`corpus.retrieve`, `corpus.find_policy`, `citations.verify` y
`citations.record_answer` se sustituyen por dobles deterministas: lo que estas
pruebas comprueban es la composición del nodo, no lo que tanda 1 y tanda 2 ya
probaron con PostgreSQL de verdad.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest

from untangle.base import ProviderErrorKind, ProviderName, Use
from untangle.compliance.controls import phrases as compliance_phrases
from untangle.orchestration.nodes.policy_verification import node, phrases
from untangle.policy_rag.citations import api as citations
from untangle.policy_rag.citations.models import CitationReason, CoverageAnswer, CoverageOutcome
from untangle.policy_rag.citations.verifier import CitationVerdict, VerificationResult
from untangle.policy_rag.corpus import api as corpus
from untangle.policy_rag.corpus.models import Clause, IssuedPolicy
from untangle.policy_rag.corpus.retrieval import RetrievalProbe, RetrievalResult
from untangle.providers.ports import ProviderError
from untangle.telemetry.traces.models import NodeName

TENANT_ID = "stonecroft"
EMBEDDING_MODEL = "gemini-embedding-001"
AHORA = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)


def _correr(coro: Any) -> Any:
    return asyncio.run(coro)


def _reloj() -> datetime:
    return AHORA


class _EmbedderFalso:
    """Falla `fails` veces y despues responde. Nunca llama al proveedor de verdad."""

    def __init__(self, *, fails: int = 0, vector: tuple[float, ...] = (0.1, 0.2)) -> None:
        self.fails = fails
        self.vector = vector
        self.llamadas = 0

    async def __call__(self, texts: Any) -> list[tuple[float, ...]]:
        self.llamadas += 1
        if self.llamadas <= self.fails:
            raise ProviderError(
                ProviderErrorKind.TIMEOUT, provider=ProviderName.GEMINI, use=Use.CORPUS, attempt=1
            )
        return [self.vector for _ in texts]


def _clausula(clause_id: str, *, part: str = "Parte A", language: str = "es") -> Clause:
    return Clause(
        tenant_id=TENANT_ID,
        clause_id=clause_id,
        clause_key=clause_id,
        form_id="STO-PAP-2026",
        form_version="2026.1",
        part=part,
        language=language,  # type: ignore[arg-type]
        text=f"Texto de {clause_id}.",
        is_distractor=False,
        issuer_label="Seguros Aburrá",
    )


def _poliza(**cambios: Any) -> IssuedPolicy:
    base: dict[str, Any] = {
        "tenant_id": TENANT_ID,
        "policy_number": "POL-001",
        "issuer_tenant": TENANT_ID,
        "form_id": "STO-PAP-2026",
        "form_version": "2026.1",
        "endorsement_ids": (),
        "named_insured": {},
        "vehicles": (),
        "limits_and_deductibles": {},
        "period_start": "2026-01-01",
        "period_end": "2027-01-01",
    }
    return IssuedPolicy.model_validate(base | cambios)


def _retrieval(clauses: tuple[Clause, ...]) -> RetrievalResult:
    return RetrievalResult(
        clauses=clauses,
        probe=RetrievalProbe(
            clause_ids=tuple(c.clause_id for c in clauses), sources={}, filtered_by={}
        ),
    )


class _RecordAnswerEco:
    """Sustituye a `citations.record_answer`: devuelve la respuesta que se le pide, sin base de datos.

    Lo que tanda 2 ya probó (redacción antes de persistir, idempotencia por
    clave) no se repite aquí: estas pruebas comprueban qué construye el nodo
    con lo que `record_answer` devuelve, no `record_answer` en sí.
    """

    def __init__(self) -> None:
        self.llamadas: list[VerificationResult] = []

    async def __call__(  # noqa: PLR0913 -- la misma firma que `citations.record_answer`
        self,
        tenant_id: str,
        *,
        case_id: str,
        turn_id: str,
        question: str,
        verification: VerificationResult,
        answer_language: str,
        now: datetime,
    ) -> CoverageAnswer:
        self.llamadas.append(verification)
        verificados = tuple(
            v for v in verification.citations if v.outcome is CoverageOutcome.VERIFIED
        )
        return CoverageAnswer(
            answer_id="ans-test",
            tenant_id=tenant_id,
            case_id=case_id,
            turn_id=turn_id,
            idempotency_key="coverage-test",
            question_redacted=question,
            outcome=verification.outcome,
            citation_check_ids=tuple(f"citck-{v.clause_id}" for v in verificados),
            answer_language=answer_language,  # type: ignore[arg-type]
            clause_language=verification.clause_language,
            created_at=now,
        )


def _nodo(  # noqa: PLR0913 -- cada costura del corpus que la prueba puede sustituir, por nombre
    monkeypatch: pytest.MonkeyPatch,
    *,
    embed: _EmbedderFalso | None = None,
    retrieve: Any = None,
    find_policy: Any = None,
    verify: Any = None,
    relations_into: Any = None,
) -> tuple[node.PolicyVerificationNode, list[dict[str, Any]]]:
    embebedor = embed if embed is not None else _EmbedderFalso()

    async def _sin_relaciones(*_a: Any, **_k: Any) -> tuple[Any, ...]:
        return ()

    monkeypatch.setattr(
        corpus, "relations_into", relations_into if relations_into is not None else _sin_relaciones
    )
    if retrieve is not None:
        monkeypatch.setattr(corpus, "retrieve", retrieve)
    if find_policy is not None:
        monkeypatch.setattr(corpus, "find_policy", find_policy)
    if verify is not None:
        monkeypatch.setattr(citations, "verify", verify)
    monkeypatch.setattr(citations, "record_answer", _RecordAnswerEco())

    eventos: list[dict[str, Any]] = []
    monkeypatch.setattr(
        node,
        "observability",
        type(
            "_Obs",
            (),
            {
                "emit": staticmethod(
                    lambda evento, **campos: eventos.append({"event": evento, **campos})
                )
            },
        )(),
    )

    return (
        node.PolicyVerificationNode(embed=embebedor, embedding_model=EMBEDDING_MODEL, clock=_reloj),
        eventos,
    )


def _estado(**cambios: Any) -> node.PolicyVerificationNodeInput:
    base: dict[str, Any] = {
        "tenant_id": TENANT_ID,
        "case_id": "caso-1",
        "turn_id": "turno-1",
        "policy_number": "POL-001",
        "question": "¿Qué cubre la parte A?",
        "draft_citations": (),
        "answer_language": "es",
    }
    return node.PolicyVerificationNodeInput.model_validate(base | cambios)


# --- La especificación ---------------------------------------------------------


def test_la_especificacion_declara_ritmo_de_fondo_un_reintento_y_su_degradacion() -> None:
    spec = node.POLICY_VERIFICATION_SPEC
    assert spec.rhythm == "background"
    assert spec.attempts == 2
    assert spec.degraded_copy_key == phrases.UNVERIFIABLE
    assert set(node.PolicyVerificationNodeInput.model_fields) == spec.reads
    assert set(node.PolicyVerificationNodeOutput.model_fields) == spec.writes
    assert node.PolicyVerificationNode.spec is spec


def test_next_node_siempre_decision() -> None:
    salida = node.PolicyVerificationNodeOutput(
        outcome=CoverageOutcome.NO_CLAUSE_FOUND,
        answer_id="a",
        citation_check_ids=(),
        clause_language=None,
    )
    assert node.next_node(salida) is NodeName.DECISION


# --- BR5.2, BR5.3, OBS-U8.2: un reintento, y su rastro doble --------------------


def test_la_recuperacion_que_falla_dos_veces_se_declara_unverifiable_con_su_rastro(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2.6.1, AC2.6.2: el resultado es `unverifiable`, distinto de `no_clause_found`,
    y quedan dos eventos de traza, uno por intento."""
    embebedor = _EmbedderFalso(fails=2)
    nodo, eventos = _nodo(monkeypatch, embed=embebedor)

    salida = _correr(nodo.run(_estado()))

    assert salida.outcome is CoverageOutcome.UNVERIFIABLE
    assert salida.response_key == phrases.UNVERIFIABLE
    assert salida.response_text == phrases.unverifiable_text(locale="es")
    assert salida.citations == ()

    fallos = [e for e in eventos if e["event"] == "policy_rag.node_failure"]
    assert [f["attempt"] for f in fallos] == [1, 2]
    assert all(f["node"] == "policy_verification" for f in fallos)
    assert all(f["error_kind"] == "timeout" for f in fallos)


def test_la_recuperacion_que_falla_una_vez_y_pasa_al_reintentar_no_se_degrada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un solo fallo no basta para degradar (BR5.2: "se reintenta una sola vez")."""
    embebedor = _EmbedderFalso(fails=1)
    poliza = _poliza()
    clausula = _clausula("STO-PAP-2026-A.1")

    async def _retrieve(*args: Any, **kwargs: Any) -> RetrievalResult:
        return _retrieval((clausula,))

    async def _find_policy(*args: Any, **kwargs: Any) -> IssuedPolicy:
        return poliza

    async def _verify(*args: Any, **kwargs: Any) -> VerificationResult:
        return VerificationResult(
            outcome=CoverageOutcome.NO_CLAUSE_FOUND, citations=(), clause_language=None
        )

    nodo, eventos = _nodo(
        monkeypatch, embed=embebedor, retrieve=_retrieve, find_policy=_find_policy, verify=_verify
    )

    salida = _correr(nodo.run(_estado()))

    assert salida.outcome is CoverageOutcome.NO_CLAUSE_FOUND
    fallos = [e for e in eventos if e["event"] == "policy_rag.node_failure"]
    assert len(fallos) == 1
    assert fallos[0]["attempt"] == 1


# --- BR3.1 aplicado por el nodo: nada recuperado rechaza cualquier cita --------


async def _retrieve_vacio(*args: Any, **kwargs: Any) -> RetrievalResult:
    return _retrieval(())


def test_sin_clausulas_recuperadas_y_sin_citas_propuestas_es_no_clause_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2.5.1, BR5.6: no había nada que citar, y de verdad no hay nada."""

    def _find_policy_no_debe_llamarse(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("no hace falta la poliza cuando no se recupero nada")

    nodo, _ = _nodo(
        monkeypatch, retrieve=_retrieve_vacio, find_policy=_find_policy_no_debe_llamarse
    )

    salida = _correr(nodo.run(_estado(draft_citations=())))

    assert salida.outcome is CoverageOutcome.NO_CLAUSE_FOUND
    assert salida.response_key == phrases.NO_CLAUSE_FOUND
    assert salida.response_text == phrases.no_clause_found_text(locale="es")


def test_sin_clausulas_recuperadas_una_cita_propuesta_se_rechaza_sin_conocer_la_poliza(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BR3.1: una cita que nadie recuperó se rechaza aunque el modelo la proponga."""

    def _find_policy_no_debe_llamarse(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("BR3.1 rechaza sin necesidad de mirar la poliza")

    nodo, _ = _nodo(
        monkeypatch, retrieve=_retrieve_vacio, find_policy=_find_policy_no_debe_llamarse
    )

    salida = _correr(
        nodo.run(
            _estado(
                draft_citations=(
                    node.DraftCitation(clause_id="STO-PAP-2026-A.1", claim="Cubre todo."),
                )
            )
        )
    )

    assert salida.outcome is CoverageOutcome.REJECTED
    assert salida.response_key == compliance_phrases.HANDOFF
    assert salida.response_text == compliance_phrases.handoff_text(locale="es")


# --- BR5.4, BR5.5/AC2.7.2: la forma de la cita, y el monto que se difiere ------


def test_una_cita_verificada_trae_identificador_parte_e_idioma(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2.7.1, BR5.4: el canal de texto recibe identificador y parte."""
    clausula = _clausula("STO-PAP-2026-A.1", part="Parte A — Responsabilidad Civil")
    poliza = _poliza()

    async def _retrieve(*args: Any, **kwargs: Any) -> RetrievalResult:
        return _retrieval((clausula,))

    async def _find_policy(*args: Any, **kwargs: Any) -> IssuedPolicy:
        return poliza

    async def _verify(*args: Any, **kwargs: Any) -> VerificationResult:
        return VerificationResult(
            outcome=CoverageOutcome.VERIFIED,
            citations=(
                CitationVerdict(
                    clause_id=clausula.clause_id,
                    claim="Cubre el siniestro.",
                    outcome=CoverageOutcome.VERIFIED,
                    reasons=(),
                    amended_by=(),
                    clause_version="2026.1",
                ),
            ),
            clause_language="es",
        )

    nodo, _ = _nodo(monkeypatch, retrieve=_retrieve, find_policy=_find_policy, verify=_verify)

    salida = _correr(nodo.run(_estado()))

    assert salida.outcome is CoverageOutcome.VERIFIED
    assert salida.response_key is None
    assert len(salida.citations) == 1
    vista = salida.citations[0]
    assert vista.clause_id == clausula.clause_id
    assert vista.part == "Parte A — Responsabilidad Civil"
    assert vista.clause_language == "es"
    assert vista.amount_deferred is False
    assert vista.voice_summary == phrases.voice_summary_text(locale="es", part=vista.part)


def test_un_endoso_vigente_que_modifica_la_clausula_difiere_el_monto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2.7.2: nunca dice el monto; la frase de "un ajustador lo confirma" sustituye
    al resumen normal, en los dos canales."""
    clausula = _clausula("STO-PAP-2026-A.LIMIT")
    poliza = _poliza(endorsement_ids=("STO-PAP-2026-END-1",))

    async def _retrieve(*args: Any, **kwargs: Any) -> RetrievalResult:
        return _retrieval((clausula,))

    async def _find_policy(*args: Any, **kwargs: Any) -> IssuedPolicy:
        return poliza

    async def _verify(*args: Any, **kwargs: Any) -> VerificationResult:
        return VerificationResult(
            outcome=CoverageOutcome.VERIFIED,
            citations=(
                CitationVerdict(
                    clause_id=clausula.clause_id,
                    claim="El limite es el que muestra la caratula.",
                    outcome=CoverageOutcome.VERIFIED,
                    reasons=(),
                    amended_by=("STO-PAP-2026-END-1-A.LIMIT",),
                    clause_version="2026.1",
                ),
            ),
            clause_language="es",
        )

    nodo, _ = _nodo(monkeypatch, retrieve=_retrieve, find_policy=_find_policy, verify=_verify)

    salida = _correr(nodo.run(_estado()))

    vista = salida.citations[0]
    assert vista.amount_deferred is True
    assert vista.voice_summary == phrases.amount_deferred_text(locale="es")
    assert "límite" not in vista.voice_summary.lower() or "confirma" in vista.voice_summary.lower()


# --- BR5.8: el aviso de idioma cruzado, sin traducir la cláusula ----------------


def test_idioma_cruzado_avisa_de_la_diferencia_sin_traducir_la_clausula(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FD-U8-1, BR5.8: pregunta en español contra una cláusula redactada en inglés."""
    clausula = _clausula("SUN-PAP-2026-A.1", language="en")
    poliza = _poliza(tenant_id="sunmeadow", issuer_tenant="sunmeadow", form_id="SUN-PAP-2026")

    async def _retrieve(*args: Any, **kwargs: Any) -> RetrievalResult:
        return _retrieval((clausula,))

    async def _find_policy(*args: Any, **kwargs: Any) -> IssuedPolicy:
        return poliza

    async def _verify(*args: Any, **kwargs: Any) -> VerificationResult:
        return VerificationResult(
            outcome=CoverageOutcome.VERIFIED,
            citations=(
                CitationVerdict(
                    clause_id=clausula.clause_id,
                    claim="Covers the loss.",
                    outcome=CoverageOutcome.VERIFIED,
                    reasons=(),
                    amended_by=(),
                    clause_version="2026.1",
                ),
            ),
            clause_language="en",
        )

    nodo, _ = _nodo(monkeypatch, retrieve=_retrieve, find_policy=_find_policy, verify=_verify)

    salida = _correr(
        nodo.run(_estado(tenant_id="sunmeadow", policy_number="POL-002", answer_language="es"))
    )

    assert salida.clause_language == "en"
    assert salida.cross_language_notice == phrases.cross_language_notice_text(
        locale="es", clause_language="en"
    )
    # La cláusula se muestra en su propio idioma: la vista nunca la traduce.
    assert salida.citations[0].clause_language == "en"


def test_sin_diferencia_de_idioma_no_hay_aviso(monkeypatch: pytest.MonkeyPatch) -> None:
    clausula = _clausula("STO-PAP-2026-A.1", language="es")
    poliza = _poliza()

    async def _retrieve(*args: Any, **kwargs: Any) -> RetrievalResult:
        return _retrieval((clausula,))

    async def _find_policy(*args: Any, **kwargs: Any) -> IssuedPolicy:
        return poliza

    async def _verify(*args: Any, **kwargs: Any) -> VerificationResult:
        return VerificationResult(
            outcome=CoverageOutcome.VERIFIED,
            citations=(
                CitationVerdict(
                    clause_id=clausula.clause_id,
                    claim="Cubre el siniestro.",
                    outcome=CoverageOutcome.VERIFIED,
                    reasons=(),
                    amended_by=(),
                    clause_version="2026.1",
                ),
            ),
            clause_language="es",
        )

    nodo, _ = _nodo(monkeypatch, retrieve=_retrieve, find_policy=_find_policy, verify=_verify)

    salida = _correr(nodo.run(_estado()))

    assert salida.cross_language_notice is None


# --- BR3.8: una cita rechazada por el verificador se deriva --------------------


def test_rejected_por_el_verificador_se_deriva_con_la_frase_generica(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clausula = _clausula("STO-PAP-2026-A.1")
    poliza = _poliza()

    async def _retrieve(*args: Any, **kwargs: Any) -> RetrievalResult:
        return _retrieval((clausula,))

    async def _find_policy(*args: Any, **kwargs: Any) -> IssuedPolicy:
        return poliza

    async def _verify(*args: Any, **kwargs: Any) -> VerificationResult:
        return VerificationResult(
            outcome=CoverageOutcome.REJECTED,
            citations=(
                CitationVerdict(
                    clause_id=clausula.clause_id,
                    claim="Cubre todo.",
                    outcome=CoverageOutcome.REJECTED,
                    reasons=(CitationReason.POLICY_NOT_IN_FORCE,),
                    amended_by=(),
                    clause_version="2026.1",
                ),
            ),
            clause_language="es",
        )

    nodo, _ = _nodo(monkeypatch, retrieve=_retrieve, find_policy=_find_policy, verify=_verify)

    salida = _correr(nodo.run(_estado()))

    assert salida.outcome is CoverageOutcome.REJECTED
    assert salida.citations == ()
    assert salida.response_key == compliance_phrases.HANDOFF
