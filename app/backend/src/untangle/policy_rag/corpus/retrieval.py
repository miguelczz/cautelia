"""Recuperación filtrada por póliza: filtrar, buscar, fusionar y cerrar (paso 4, tanda 2).

El recorrido, en el orden de `functional-spec.md`:

1. **Resolver la póliza de quien pregunta** (`repository.find_policy`). Fuera de
   vigencia (BR2.2) o de otro inquilino (BR2.6, indistinguible de inexistente
   porque la política de fila ya la escondió) → conjunto vacío.
2. **El conjunto candidato** (`repository.candidate_clauses`, BR2.1): el
   formulario base de la versión que la póliza referencia, más sus endosos
   vigentes. Se calcula **antes** de puntuar, no después: filtrar después de
   ordenar es como se cuela una cláusula ajena en el primer lugar.
3. **Búsqueda léxica y vectorial**, las dos restringidas al candidato.
4. **Fusión por rango recíproco** (`reciprocal_rank_fusion`, BR2.3, TECH-U8.3):
   escrita a mano, nunca por suma de puntajes.
5. **Cierre por relaciones** (`_close_over_relations`, BR2.4): los endosos
   vigentes que modifican alguna cláusula recuperada y las definiciones que usan,
   añadidos **después** de fusionar y sin competir por el orden.

Lo que hace posible probar la fusión y el cierre sin base de datos: las dos son
funciones puras sobre listas de identificadores y relaciones ya leídas. Solo lo
que de verdad toca la base -- `find_policy`, `candidate_clauses`,
`lexical_rank`, `vector_rank`, `relations_into`, `clauses_by_ids` -- vive en
`repository.py` y se prueba de integración, con PostgreSQL de verdad.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from untangle import observability
from untangle.policy_rag.corpus import repository
from untangle.policy_rag.corpus.models import Clause, ClauseRelation, IssuedPolicy, RelationKind
from untangle.providers.ports import Vector
from untangle.tenancy.models import TenantId

#: La constante de la fusión por rango recíproco (TECH-U8.3, ADR-010). 60 es el
#: valor que usa la literatura de RRF (Cormack et al.): bastante grande para que
#: la diferencia entre el primer y el segundo lugar de una lista no aplaste al
#: resto, y una sola constante versionada aquí en vez de un número repetido.
RRF_K = 60

#: Cuántas cláusulas trae cada búsqueda antes de fusionar, y cuántas quedan tras
#: la fusión (antes del cierre). Ningún documento aprobado fija un número: con
#: 104 cláusulas por corpus, ocho es generoso para las preguntas de DS-3 sin
#: dejar de ser barato (PERF-U8.3 lo mide y lo publica).
DEFAULT_LIMIT = 8

#: Las dos relaciones que participan en el cierre (BR2.4). `refers_to` no: esa
#: es la que apunta al documento de jurisdicción y no compite ni cierra.
_RELACIONES_DE_CIERRE = frozenset({RelationKind.ENDORSEMENT_MODIFIES, RelationKind.DEFINES})


def reciprocal_rank_fusion(
    *, lexical: Sequence[str], vector: Sequence[str], k: int = RRF_K
) -> tuple[str, ...]:
    """Fusiona dos listas ordenadas por su posición, nunca por su puntaje (BR2.3).

    Los puntajes de `ts_rank_cd` y de la distancia de coseno no viven en la
    misma escala; sumarlos dejaría que la escala mandara sobre la relevancia.
    El rango recíproco solo usa la posición: `1 / (k + rango)`, sumado sobre
    las listas en las que aparece cada identificador.

    El desempate es determinista y no es el orden alfabético: a igualdad de
    puntaje, gana quien apareció primero en la lista léxica y, si tampoco
    apareció ahí, quien apareció primero en la vectorial. Dos corridas del
    mismo commit tienen que fusionar igual (`team.md`, REL-U1.1).
    """
    puntajes: dict[str, float] = {}
    for lista in (lexical, vector):
        for posicion, clause_id in enumerate(lista, start=1):
            puntajes[clause_id] = puntajes.get(clause_id, 0.0) + 1.0 / (k + posicion)

    orden_de_aparicion: dict[str, int] = {}
    for indice, clause_id in enumerate((*lexical, *vector)):
        orden_de_aparicion.setdefault(clause_id, indice)
    return tuple(
        sorted(
            puntajes, key=lambda clause_id: (-puntajes[clause_id], orden_de_aparicion[clause_id])
        )
    )


def _close_over_relations(
    fused: Sequence[str],
    *,
    relations: Sequence[ClauseRelation],
    candidate_clause_ids: frozenset[str],
) -> dict[str, str]:
    """Los identificadores que el cierre añade, y de cuál cláusula recuperada salió cada uno.

    Solo `endorsement_modifies` y `defines` cierran (BR2.4); `refers_to` no
    participa. Una relación que apunte fuera del universo que esta póliza
    puede citar (`candidate_clause_ids`) no cierra tampoco: un endoso que no es
    vigente para esta póliza no entra por la puerta de atrás.
    """
    fused_set = set(fused)
    cierre: dict[str, str] = {}
    for relacion in sorted(relations, key=lambda r: (r.to_clause, r.from_clause)):
        if relacion.relation not in _RELACIONES_DE_CIERRE:
            continue
        if relacion.to_clause not in fused_set:
            continue
        if relacion.from_clause not in candidate_clause_ids:
            continue
        if relacion.from_clause in fused_set or relacion.from_clause in cierre:
            continue
        cierre[relacion.from_clause] = relacion.to_clause
    return cierre


@dataclass(frozen=True)
class ClauseSource:
    """De dónde vino una cláusula recuperada (OBS-U8.1, `entities.md`).

    `lexical_rank`/`vector_rank` son la posición (1 es la mejor) en la lista de
    esa búsqueda, o `None` si no apareció ahí. `closure_of` es el identificador
    de la cláusula recuperada que arrastró a esta por relación, o `None` cuando
    la cláusula entró por la fusión y no por el cierre -- que es justo lo que
    BR2.4 exige poder distinguir: el cierre no cuenta para la métrica de
    recuperación.
    """

    lexical_rank: int | None
    vector_rank: int | None
    closure_of: str | None


@dataclass(frozen=True)
class RetrievalProbe:
    """La forma del resultado de una recuperación (`entities.md`). No se persiste.

    `filtered_by` lleva solo lo que se sabía al filtrar: para una póliza que no
    se encontró (inexistente o de otra aseguradora, BR2.6) queda con el
    inquilino y nada más, porque el código nunca llega a saber más que eso.
    """

    clause_ids: tuple[str, ...]
    sources: Mapping[str, ClauseSource]
    filtered_by: Mapping[str, object]


@dataclass(frozen=True)
class RetrievalResult:
    """Lo que `retrieve` devuelve: las cláusulas, en el orden de la sonda, y la sonda misma."""

    clauses: tuple[Clause, ...]
    probe: RetrievalProbe


def _emit_probe(probe: RetrievalProbe) -> None:
    """El evento de recuperación (tabla de `observability-requirements.md`).

    Nunca lleva la pregunta ni el texto de una cláusula: solo identificadores,
    filtros y de dónde vino cada uno -- datos del proyecto, no de una persona
    (`observability.py`, "Aqui no entra texto de una persona").
    """
    observability.emit(
        "policy_rag.retrieval_probe",
        clause_ids=list(probe.clause_ids),
        sources={
            clause_id: {
                "lexical_rank": fuente.lexical_rank,
                "vector_rank": fuente.vector_rank,
                "closure_of": fuente.closure_of,
            }
            for clause_id, fuente in probe.sources.items()
        },
        filtered_by=dict(probe.filtered_by),
    )


def _empty_probe(tenant_id: TenantId) -> RetrievalProbe:
    return RetrievalProbe(clause_ids=(), sources={}, filtered_by={"tenant_id": tenant_id})


def _vigente(poliza: IssuedPolicy, *, now: datetime) -> bool:
    return poliza.period_start <= now.date() <= poliza.period_end


async def retrieve(  # noqa: PLR0913 -- siete datos de una recuperacion, ninguno derivable de otro
    tenant_id: TenantId,
    *,
    policy_number: str,
    query_text: str,
    query_vector: Vector,
    embedding_model: str,
    now: datetime,
    limit: int = DEFAULT_LIMIT,
) -> RetrievalResult:
    """Filtra, busca, fusiona y cierra: el conjunto que puede citar una respuesta (BR2.1 a BR2.6).

    `now` entra por argumento y no se lee del reloj del sistema, por la misma
    razón que el resto del proyecto: la vigencia de una póliza se prueba con
    fechas fijas, no con la hora en que corrió la prueba.
    """
    poliza = await repository.find_policy(tenant_id, policy_number=policy_number)
    if poliza is None:
        # BR2.6: inexistente y de otra aseguradora llegan aqui identicos,
        # porque la politica de fila ya escondio la segunda antes de esta
        # linea. No hay una segunda rama que las distinga.
        probe = _empty_probe(tenant_id)
        _emit_probe(probe)
        return RetrievalResult(clauses=(), probe=probe)

    if not _vigente(poliza, now=now):
        # BR2.2: fuera de vigencia, conjunto vacio. Aqui si sabemos de que
        # poliza se trata -- es la propia, no una ajena -- asi que el filtro
        # completo viaja en la sonda.
        probe = RetrievalProbe(clause_ids=(), sources={}, filtered_by=_filtros(tenant_id, poliza))
        _emit_probe(probe)
        return RetrievalResult(clauses=(), probe=probe)

    candidatas = await repository.candidate_clauses(
        tenant_id,
        form_id=poliza.form_id,
        form_version=poliza.form_version,
        endorsement_ids=poliza.endorsement_ids,
    )
    candidate_ids = frozenset(clausula.clause_id for clausula in candidatas)
    if not candidatas:
        probe = RetrievalProbe(clause_ids=(), sources={}, filtered_by=_filtros(tenant_id, poliza))
        _emit_probe(probe)
        return RetrievalResult(clauses=(), probe=probe)

    # TECH-U8.4: la configuracion del analizador es la del idioma del corpus
    # candidato, no la de la conversacion. Una poliza referencia un solo
    # formulario y todas sus clausulas -- base y endosos -- comparten idioma.
    idioma_del_corpus = candidatas[0].language

    lexicos = await repository.lexical_rank(
        tenant_id,
        embedding_model=embedding_model,
        candidate_ids=tuple(candidate_ids),
        query_text=query_text,
        query_language=idioma_del_corpus,
        limit=limit,
    )
    vectoriales = await repository.vector_rank(
        tenant_id,
        embedding_model=embedding_model,
        candidate_ids=tuple(candidate_ids),
        query_vector=query_vector,
        limit=limit,
    )
    fusionadas = reciprocal_rank_fusion(lexical=lexicos, vector=vectoriales)[:limit]

    relaciones = await repository.relations_into(tenant_id, clause_ids=fusionadas)
    cierre = _close_over_relations(
        fusionadas, relations=relaciones, candidate_clause_ids=candidate_ids
    )

    todos_los_ids = (*fusionadas, *cierre)
    encontradas = await repository.clauses_by_ids(tenant_id, clause_ids=todos_los_ids)
    por_id = {clausula.clause_id: clausula for clausula in encontradas}
    clausulas_en_orden = tuple(por_id[cid] for cid in todos_los_ids if cid in por_id)

    rango_lexico = {clause_id: i + 1 for i, clause_id in enumerate(lexicos)}
    rango_vectorial = {clause_id: i + 1 for i, clause_id in enumerate(vectoriales)}
    sources: dict[str, ClauseSource] = {
        clause_id: ClauseSource(
            lexical_rank=rango_lexico.get(clause_id),
            vector_rank=rango_vectorial.get(clause_id),
            closure_of=None,
        )
        for clause_id in fusionadas
    }
    for clause_id, de_donde in cierre.items():
        sources[clause_id] = ClauseSource(lexical_rank=None, vector_rank=None, closure_of=de_donde)

    probe = RetrievalProbe(
        clause_ids=todos_los_ids, sources=sources, filtered_by=_filtros(tenant_id, poliza)
    )
    _emit_probe(probe)
    return RetrievalResult(clauses=clausulas_en_orden, probe=probe)


def _filtros(tenant_id: TenantId, poliza: IssuedPolicy) -> dict[str, object]:
    return {
        "tenant_id": tenant_id,
        "issuer_tenant": poliza.issuer_tenant,
        "form_id": poliza.form_id,
        "form_version": poliza.form_version,
        "endorsement_ids": list(poliza.endorsement_ids),
    }


__all__ = [
    "DEFAULT_LIMIT",
    "RRF_K",
    "ClauseSource",
    "RetrievalProbe",
    "RetrievalResult",
    "reciprocal_rank_fusion",
    "retrieve",
]
