"""El nodo `policy_verification`: recupera, verifica y registra una respuesta de cobertura (paso 8, tanda 3).

Corre en el ritmo de fondo, igual que `decision` y `compliance` (D22, BR3.7):
dentro del turno solo corren los tres controles baratos de cumplimiento, y la
verificación de póliza no es uno de ellos.

**Puro y cerrado** (BR5.1, C-15): recibe campos del estado tipado, devuelve solo
su conjunto de escritura, no abre transacciones y no importa ningún SDK de
proveedor ni ningún canal -- solo el puerto `Embedder` de `providers/ports.py`,
recibido por closure igual que `ClockPort` en `decision` y `ReviewPort` en
`compliance`. El contrato de importación `nodos-independientes` de
`.importlinter` comprueba que este paquete no importa los otros tres nodos.

## El recorrido

1. **Recuperación con reintento** (BR5.2): embeber la pregunta con `Embedder`
   y recuperar con `PolicyCorpus.retrieve` es lo único que puede fallar por el
   proveedor. Un reintento (`spec.attempts`), y si el segundo también falla el
   resultado es `unverifiable`: no una excepción que alguien más traduzca, sino
   el valor que este paso decide aquí mismo, porque es la única pieza que sabe
   que "no pude buscar" y "busqué y no hay nada" (BR3.4) son cosas distintas.
   Cada intento fallido deja su rastro: un evento con el nodo, el tipo de error
   y el número de intento (BR5.3, OBS-U8.2); la política declarada en
   `POLICY_VERIFICATION_SPEC` es la misma que aplicaría un ejecutor común de
   U12 si existiera, pero como todavía no existe (`nfr-requirements/
   performance-requirements.md`), este paso la aplica él mismo -- es
   exactamente lo que el comentario de `citations/verifier.py` ("es el fallo
   del nodo tras su reintento") dejó anunciado para esta tanda.
2. **Verificación** (BR3.1 a BR3.8): solo si hubo recuperación. Sin cláusulas
   recuperadas y sin nada que citar, `no_clause_found`; sin cláusulas
   recuperadas pero con una cita propuesta, esa cita se rechaza sin necesidad
   de conocer la póliza (BR3.1 ya la rechaza por no estar en lo recuperado).
   Con cláusulas, `CitationVerifier.verify` decide.
3. **Registro** (BR4.1): `CitationVerifier.record_answer` escribe, nunca este
   nodo.
4. **La forma de la cita, por canal** (BR5.4 a BR5.8): el contenido verificado
   es el mismo en los dos canales; lo que cambia es la forma. Este nodo entrega
   los dos: `citations` trae el identificador y la parte que el canal de texto
   necesita (BR5.4), y ya trae compuesto el resumen de una frase que el canal
   de voz puede decir tal cual, sin tocar nunca el texto de la cláusula
   (BR5.4) ni su monto (BR5.5, AC2.7.2): cuando la cita trae un endoso vigente
   que la modifica (`amended_by`), el resumen es la frase de "un ajustador lo
   confirma", no la que nombra la parte.

## Lo que no hace

La forma del texto que llega a una persona en el turno en vivo -- decidir si se
lee en voz o se muestra en pantalla, y pasarlo por la guardia de salida de U10
antes de sintetizar o de responder -- es del canal (U13, U16), no de este nodo:
`guard_output` es uno de los tres controles baratos que corren **dentro** del
turno (D22), y este nodo corre en el ritmo de fondo. Lo que este nodo entrega
ya es seguro por construcción y no por revisión: nunca repite el texto de una
cláusula ni el de la afirmación del modelo, así que no hay monto que pueda
colarse en lo que compone.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime

from pydantic import Field

from untangle import observability
from untangle.base import Frozen, Locale
from untangle.compliance.controls import phrases as compliance_phrases
from untangle.orchestration.nodes.policy_verification import phrases
from untangle.orchestration.nodes.policy_verification.proposal import (
    ClauseForProposal,
    ProposalRequest,
    ProposerPort,
)
from untangle.orchestration.state import NodeSpec
from untangle.policy_rag.citations import api as citations
from untangle.policy_rag.citations.models import CitationReason, CoverageOutcome
from untangle.policy_rag.citations.verifier import CitationVerdict, VerificationResult
from untangle.policy_rag.corpus import api as corpus
from untangle.policy_rag.corpus.models import Clause, IssuedPolicy, RelationKind
from untangle.policy_rag.corpus.retrieval import RetrievalResult
from untangle.providers.ports import BudgetExhausted, ProviderError, Vector
from untangle.telemetry.traces.models import NodeName
from untangle.tenancy.models import TENANT_ID_PATTERN, TenantId


class DraftCitation(Frozen):
    """Una cita que el modelo propuso, antes de que este nodo la verifique.

    Llega en la entrada, o la propone el modelo por el puerto `propose` sobre las
    clausulas que este nodo acaba de recuperar (fase 1, 2026-10-08). En los dos
    casos se comprueba contra lo que **él mismo** recupera (BR3.1) -- una cita que
    nadie recuperó se rechaza aunque el modelo la haya dicho con total seguridad.
    """

    clause_id: str = Field(min_length=1)
    claim: str = Field(min_length=1)


class PolicyVerificationNodeInput(Frozen):
    """Los campos del estado que el nodo lee (`NodeSpec.reads`)."""

    tenant_id: TenantId = Field(pattern=TENANT_ID_PATTERN)
    case_id: str = Field(min_length=1)
    turn_id: str = Field(min_length=1)
    policy_number: str = Field(min_length=1)
    question: str = Field(min_length=1)
    #: Lo que el modelo propuso citar. Vacío es una respuesta legítima: es la
    #: que da cuando decide que la póliza no dice nada (BR5.6).
    draft_citations: tuple[DraftCitation, ...] = ()
    answer_language: Locale


class CoverageCitationView(Frozen):
    """Una cita `verified`, lista para que cualquier canal la muestre (BR5.4).

    `clause_id` y `part` son lo que el canal de texto necesita (BR5.4): el
    identificador y la parte, nunca el texto de la cláusula, que U13 despliega
    por su cuenta. `voice_summary` es la frase de una sola oración que el canal
    de voz puede decir tal cual (AC2.7.1), y ya decide sola si el monto se
    difiere (AC2.7.2): nunca lee el texto de la cláusula ni cifra alguna.
    """

    clause_id: str
    part: str
    clause_language: Locale
    #: Cierto cuando un endoso vigente modifica esta cláusula (BR3.5): la
    #: respuesta nunca dice el monto que trae, en ningún canal (BR5.5).
    amount_deferred: bool
    voice_summary: str
    #: Lo que la IA dice que trata la clausula, en una oracion y en el idioma de la
    #: conversacion, ya verificado contra la clausula (2026-10-08). El chat lo usa para
    #: explicar la cita; si la guardia lo rechaza, la respuesta sale sin el.
    claim: str = ""


class PolicyVerificationNodeOutput(Frozen):
    """El conjunto de escritura del nodo (`NodeSpec.writes`), y nada más."""

    outcome: CoverageOutcome
    answer_id: str
    citation_check_ids: tuple[str, ...]
    clause_language: Locale | None
    #: Solo cuando `outcome` es `verified`; vacío en cualquier otro caso.
    citations: tuple[CoverageCitationView, ...] = ()
    #: La clave del catálogo de la frase fija, cuando la hay (BR5.6, BR5.7):
    #: `no_clause_found`, `unverifiable` o la derivación genérica de
    #: `rejected`. `None` cuando `outcome` es `verified`, porque ahí el
    #: contenido sale de `citations` y no de una frase única.
    response_key: str | None = None
    response_text: str | None = None
    #: BR5.8: la frase que avisa de la diferencia de idioma, ya resuelta.
    #: `None` cuando no hubo cita o cuando los dos idiomas coinciden.
    cross_language_notice: str | None = None


#: **60 000 ms y dos intentos.** El uso `corpus` (PASO 0) tolera la misma cola
#: del plan gratuito que `operations`, porque el ritmo es de fondo y nadie
#: espera al teléfono (D22): el presupuesto real de este nodo antes de
#: degradar es de U12 `graph-runtime`, que todavía no existe
#: (`nfr-requirements/performance-requirements.md`, PERF-U8.3); este número
#: es el que deja el dato declarado mientras esa unidad no fija el suyo desde
#: la medición real. Un reintento y no más, como la convención 8b del equipo.
#:
#: **Su degradación es `unverifiable`.** A diferencia de `decision` y
#: `compliance`, no es una frase genérica de derivación: es un resultado propio
#: de `CoverageOutcome` (BR3.3, BR3.4), porque colapsarlo con la derivación
#: genérica escondería un fallo de infraestructura detrás de una conducta de
#: la agente (BR3.4).
#:
#: **Aviso para U12 `graph-runtime`: este nodo ya consume sus `attempts`.** Es
#: el único de los cuatro que lo hace. `decision` y `compliance` dejan subir el
#: fallo para que el ejecutor común aplique la política (convención 8b); este
#: no puede, porque tras agotar los intentos todavía tiene trabajo: escribir el
#: `CoverageAnswer` con `unverifiable`, que es el valor distinguible que BR3.4
#: exige en el caso y que nadie más sabe escribir. La consecuencia es que un
#: ejecutor que vuelva a aplicar `attempts` sobre este nodo haría **cuatro**
#: llamadas al proveedor en vez de dos.
#:
#: **Resuelto en el paso 4 de U12 (FD-U12-2, 2026-09-27):** `retries_owned_by`
#: declara aqui `"node"` -- la unica excepcion entre los cuatro -- y
#: `orchestration/executor.py` lo lee para llamar a este nodo una sola vez, sin
#: aplicarle encima su propio bucle de reintento.
POLICY_VERIFICATION_SPEC = NodeSpec(
    name=NodeName.POLICY_VERIFICATION,
    reads=frozenset(PolicyVerificationNodeInput.model_fields),
    writes=frozenset(PolicyVerificationNodeOutput.model_fields),
    rhythm="background",
    timeout_ms=60_000,
    attempts=2,
    degraded_copy_key=phrases.UNVERIFIABLE,
    retries_owned_by="node",
)

#: El reloj, tal como lo recibe el nodo por closure (igual que en `decision`).
ClockPort = Callable[[], datetime]

#: Embeber la pregunta, ya cableado con el uso `corpus` y su clave por la raíz
#: de composición (PASO 0): el nodo nunca ve la clave ni el `Use`.
EmbedPort = Callable[[Sequence[str]], Awaitable[list[Vector]]]


def next_node(_output: PolicyVerificationNodeOutput) -> NodeName:
    """Siempre `decision`: la secuencia del grafo es fija (convención 3 del equipo)."""
    return NodeName.DECISION


class PolicyVerificationNode:
    """El nodo `policy_verification` (C-15). Se construye con sus puertos por closure."""

    spec: NodeSpec = POLICY_VERIFICATION_SPEC

    def __init__(
        self,
        *,
        embed: EmbedPort,
        embedding_model: str,
        clock: ClockPort,
        propose: ProposerPort | None = None,
    ) -> None:
        self._embed = embed
        self._embedding_model = embedding_model
        self._clock = clock
        # Quien propone las citas (fase 1, 2026-10-08). Sin el, el nodo solo
        # verifica las que le llegan en la entrada, como antes.
        self._propose = propose

    async def run(self, state: PolicyVerificationNodeInput) -> PolicyVerificationNodeOutput:
        """Recupera, verifica y registra. Mismo estado, misma respuesta: también al reanudar."""
        ahora = self._clock()
        retrieval, verification = await self.answer(state, now=ahora)
        answer = await citations.record_answer(
            state.tenant_id,
            case_id=state.case_id,
            turn_id=state.turn_id,
            question=state.question,
            verification=verification,
            answer_language=state.answer_language,
            now=ahora,
        )
        return self._compose_output(
            state, answer=answer, retrieval=retrieval, verification=verification
        )

    async def answer(
        self, state: PolicyVerificationNodeInput, *, now: datetime
    ) -> tuple[RetrievalResult | None, VerificationResult]:
        """Recupera, propone y verifica, sin registrar nada. Lo usa `run` y lo usa la
        evaluacion de las citas, para medir exactamente lo mismo que responde."""
        retrieval = await self._retrieve_with_retry(
            tenant_id=state.tenant_id,
            policy_number=state.policy_number,
            question=state.question,
            now=now,
        )
        propuesta = await self._proponer(state, retrieval)
        if propuesta is None:
            # El modelo que propone fallo: no se sabe si hay clausula, que es
            # "no pude verificar" y nunca "no hay clausula" (BR3.4).
            return retrieval, VerificationResult(
                outcome=CoverageOutcome.UNVERIFIABLE, citations=(), clause_language=None
            )
        return retrieval, await self._verify(propuesta, retrieval=retrieval, now=now)

    async def _proponer(
        self, state: PolicyVerificationNodeInput, retrieval: RetrievalResult | None
    ) -> PolicyVerificationNodeInput | None:
        """La entrada con las citas que propone el modelo, o `None` si fallo.

        Solo cuando hay clausulas recuperadas, ninguna cita propuesta en la entrada y
        un puerto enchufado; en cualquier otro caso la entrada sigue tal cual.
        """
        if (
            self._propose is None
            or retrieval is None
            or not retrieval.clauses
            or state.draft_citations
        ):
            return state
        fuentes = retrieval.probe.sources
        peticion = ProposalRequest(
            tenant_id=state.tenant_id,
            language=state.answer_language,
            question=state.question,
            clauses=tuple(
                ClauseForProposal(
                    clause_id=clausula.clause_id,
                    part=clausula.part,
                    text=clausula.text,
                    related_to=(
                        fuentes[clausula.clause_id].closure_of
                        if clausula.clause_id in fuentes
                        else None
                    ),
                )
                for clausula in retrieval.clauses
            ),
        )
        try:
            propuesta = await self._propose(peticion)
        except (ProviderError, BudgetExhausted) as error:
            observability.emit(
                "policy_rag.proposal_failed",
                node=NodeName.POLICY_VERIFICATION.value,
                error=type(error).__name__,
            )
            return None
        observability.emit(
            "policy_rag.citations_proposed",
            node=NodeName.POLICY_VERIFICATION.value,
            proposed=len(propuesta.citations),
            retrieved=len(retrieval.clauses),
        )
        return state.model_copy(
            update={
                "draft_citations": tuple(
                    DraftCitation(clause_id=c.clause_id.strip(), claim=c.claim.strip())
                    for c in propuesta.citations
                    # Una cita sin clausula o sin razon no es una cita: no se verifica.
                    if c.clause_id.strip() and c.claim.strip()
                )
            }
        )

    async def _retrieve_with_retry(
        self, *, tenant_id: TenantId, policy_number: str, question: str, now: datetime
    ) -> RetrievalResult | None:
        """BR5.2: un reintento; `None` cuando los dos intentos fallan por el proveedor."""
        for intento in range(1, self.spec.attempts + 1):
            try:
                vectores = await self._embed((question,))
            except ProviderError as error:
                self._dejar_rastro(error, attempt=intento)
                continue
            return await corpus.retrieve(
                tenant_id,
                policy_number=policy_number,
                query_text=question,
                query_vector=vectores[0],
                embedding_model=self._embedding_model,
                now=now,
            )
        return None

    def _dejar_rastro(self, error: ProviderError, *, attempt: int) -> None:
        """BR5.3, OBS-U8.2: el nodo, el tipo de error y el número de intento."""
        observability.emit(
            "policy_rag.node_failure",
            node=NodeName.POLICY_VERIFICATION.value,
            error_kind=error.kind.value,
            attempt=attempt,
        )

    async def _verify(
        self,
        state: PolicyVerificationNodeInput,
        *,
        retrieval: RetrievalResult | None,
        now: datetime,
    ) -> VerificationResult:
        if retrieval is None:
            # BR5.2: la recuperación falló tras su reintento. Es un fallo, no
            # un resultado buscado: nunca se colapsa con `no_clause_found`
            # (BR3.4).
            return VerificationResult(
                outcome=CoverageOutcome.UNVERIFIABLE, citations=(), clause_language=None
            )

        if not retrieval.clauses:
            if not state.draft_citations:
                # BR5.6: no había nada que citar, y de verdad no hay nada: es
                # un resultado buscado.
                return VerificationResult(
                    outcome=CoverageOutcome.NO_CLAUSE_FOUND, citations=(), clause_language=None
                )
            # BR3.1: nada se recuperó, así que cualquier cita propuesta se
            # rechaza sin necesidad de conocer la póliza -- la comprobación no
            # depende de ella, solo de lo que este nodo recuperó.
            rechazadas = tuple(
                CitationVerdict(
                    clause_id=propuesta.clause_id,
                    claim=propuesta.claim,
                    outcome=CoverageOutcome.REJECTED,
                    reasons=(CitationReason.NOT_IN_RETRIEVED_SET,),
                    amended_by=(),
                    clause_version=None,
                )
                for propuesta in state.draft_citations
            )
            return VerificationResult(
                outcome=CoverageOutcome.REJECTED, citations=rechazadas, clause_language=None
            )

        poliza = await corpus.find_policy(state.tenant_id, policy_number=state.policy_number)
        if poliza is None:  # pragma: no cover -- retrieve() ya la encontró; defensivo
            return VerificationResult(
                outcome=CoverageOutcome.UNVERIFIABLE, citations=(), clause_language=None
            )

        propuestas = await self._con_sus_endosos(
            state.tenant_id,
            tuple(
                citations.Citation(clause_id=draft.clause_id, claim=draft.claim)
                for draft in state.draft_citations
            ),
            policy=poliza,
            retrieved=retrieval.clauses,
        )
        return await citations.verify(
            state.tenant_id,
            policy=poliza,
            retrieved_clauses=retrieval.clauses,
            citations=propuestas,
            now=now,
        )

    async def _con_sus_endosos(
        self,
        tenant_id: str,
        propuestas: tuple[citations.Citation, ...],
        *,
        policy: IssuedPolicy,
        retrieved: Sequence[Clause],
    ) -> tuple[citations.Citation, ...]:
        """Las citas, mas el endoso vigente que modifica a alguna y no vino citado.

        El prompt se lo pide al modelo y a veces lo olvida: la respuesta entera se
        rechazaba (BR3.5) y la persona leia "no pude verificar" con la clausula y su
        endoso ya recuperados (`DS-3/en/endorsement-electronics-exclusion`,
        2026-10-11). Que endoso modifica que clausula es un dato del corpus, no una
        opinion, asi que lo completa el codigo. La regla del verificador no cambia:
        sigue rechazando una respuesta que cite la clausula sin su endoso.

        Va sin `claim`: de ese endoso nadie escribio una explicacion, y la respuesta
        lo dice entonces con la frase del catalogo y no con una oracion del modelo.
        """
        recuperadas = {clausula.clause_id: clausula for clausula in retrieved}
        citadas = {propuesta.clause_id for propuesta in propuestas}
        en_juego = tuple(sorted(citadas & recuperadas.keys()))
        if not en_juego:
            return propuestas
        relaciones = await corpus.relations_into(tenant_id, clause_ids=en_juego)
        faltan = sorted(
            {
                relacion.from_clause
                for relacion in relaciones
                if relacion.relation is RelationKind.ENDORSEMENT_MODIFIES
                and relacion.to_clause in citadas
                and relacion.from_clause not in citadas
                and (endoso := recuperadas.get(relacion.from_clause)) is not None
                and endoso.form_id in policy.endorsement_ids
            }
        )
        if not faltan:
            return propuestas
        observability.emit(
            "policy_rag.endorsement_added",
            node=NodeName.POLICY_VERIFICATION.value,
            added=len(faltan),
        )
        return (*propuestas, *(citations.Citation(clause_id=c, claim="") for c in faltan))

    def _compose_output(
        self,
        state: PolicyVerificationNodeInput,
        *,
        answer: citations.CoverageAnswer,
        retrieval: RetrievalResult | None,
        verification: VerificationResult,
    ) -> PolicyVerificationNodeOutput:
        if answer.outcome is CoverageOutcome.VERIFIED:
            por_id = {
                clausula.clause_id: clausula
                for clausula in (retrieval.clauses if retrieval else ())
            }
            vistas = tuple(
                self._citation_view(
                    veredicto, clause=por_id[veredicto.clause_id], locale=state.answer_language
                )
                for veredicto in verification.citations
            )
            response_key, response_text = None, None
        else:
            vistas = ()
            response_key, response_text = self._degraded_response(
                answer.outcome, locale=state.answer_language
            )

        aviso_cruzado = None
        if answer.clause_language is not None and answer.clause_language != state.answer_language:
            aviso_cruzado = phrases.cross_language_notice_text(
                locale=state.answer_language, clause_language=answer.clause_language
            )

        return PolicyVerificationNodeOutput(
            outcome=answer.outcome,
            answer_id=answer.answer_id,
            citation_check_ids=answer.citation_check_ids,
            clause_language=answer.clause_language,
            citations=vistas,
            response_key=response_key,
            response_text=response_text,
            cross_language_notice=aviso_cruzado,
        )

    def _citation_view(
        self, verdict: CitationVerdict, *, clause: Clause, locale: Locale
    ) -> CoverageCitationView:
        diferido = bool(verdict.amended_by)
        resumen = (
            phrases.amount_deferred_text(locale=locale)
            if diferido
            else phrases.voice_summary_text(locale=locale, part=clause.part)
        )
        return CoverageCitationView(
            clause_id=clause.clause_id,
            part=clause.part,
            clause_language=clause.language,
            amount_deferred=diferido,
            voice_summary=resumen,
            claim=verdict.claim,
        )

    def _degraded_response(self, outcome: CoverageOutcome, *, locale: Locale) -> tuple[str, str]:
        if outcome is CoverageOutcome.NO_CLAUSE_FOUND:
            return phrases.NO_CLAUSE_FOUND, phrases.no_clause_found_text(locale=locale)
        if outcome is CoverageOutcome.UNVERIFIABLE:
            return phrases.UNVERIFIABLE, phrases.unverifiable_text(locale=locale)
        # BR3.8: `rejected` -- una cita no pasó -- se deriva con la misma frase
        # genérica que `decision` y `compliance` ya usan (AC1.9.1): no hay una
        # segunda forma de decir "esto lo revisa un ajustador".
        return compliance_phrases.HANDOFF, compliance_phrases.handoff_text(locale=locale)


__all__ = [
    "POLICY_VERIFICATION_SPEC",
    "ClockPort",
    "CoverageCitationView",
    "DraftCitation",
    "EmbedPort",
    "PolicyVerificationNode",
    "PolicyVerificationNodeInput",
    "PolicyVerificationNodeOutput",
    "next_node",
]
