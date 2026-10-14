"""Pruebas de `policy_rag.corpus.retrieval`, sin base de datos (CG-U8-4).

Dos capas, cada una probada donde corresponde:

- `reciprocal_rank_fusion` y `_close_over_relations` son funciones puras sobre
  listas de identificadores y relaciones ya leidas: se prueban aqui, solas.
- `retrieve` es orquestacion sobre `repository`; se prueba aqui tambien,
  sustituyendo cada funcion de `repository` por un doble que no toca ninguna
  base (`monkeypatch`). Las pruebas de la SQL real -- que el filtro aisle de
  verdad entre aseguradoras, que la busqueda lexica y la vectorial devuelvan lo
  que la base de verdad devuelve -- son de integracion y viven en
  `tests/integration/u8/test_retrieval.py`, con PostgreSQL.

Cada regla de precedencia lleva su propia prueba, aislada (unit-test-instructions.md):
BR2.1 (filtrar antes de puntuar), BR2.2 (fuera de vigencia), BR2.4 (el cierre no
cuenta para la metrica de recuperacion), BR2.6 (poliza ajena = inexistente).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from typing import Any

import pytest

from untangle.base import Locale
from untangle.policy_rag.corpus import repository, retrieval
from untangle.policy_rag.corpus.models import Clause, ClauseRelation, IssuedPolicy, RelationKind

TENANT_ID = "testco"
AHORA = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)


def _poliza(**cambios: Any) -> IssuedPolicy:
    base: dict[str, Any] = {
        "tenant_id": TENANT_ID,
        "policy_number": "POL-TEST-001",
        "issuer_tenant": TENANT_ID,
        "form_id": "TCO-PAP-2026",
        "form_version": "2026.1",
        "endorsement_ids": ("TCO-PAP-2026-END-1",),
        "named_insured": {},
        "vehicles": (),
        "limits_and_deductibles": {},
        "period_start": date(2026, 1, 1),
        "period_end": date(2027, 1, 1),
    }
    return IssuedPolicy.model_validate(base | cambios)


def _clausula(clause_id: str, *, language: Locale = "es", form_id: str = "TCO-PAP-2026") -> Clause:
    return Clause(
        tenant_id=TENANT_ID,
        clause_id=clause_id,
        clause_key=clause_id,
        form_id=form_id,
        form_version="2026.1",
        part="Parte A",
        language=language,
        text=f"Texto de {clause_id}.",
        is_distractor=False,
        issuer_label="Testco Mutual",
    )


def _relacion(from_clause: str, relation: RelationKind, to_clause: str) -> ClauseRelation:
    return ClauseRelation(
        tenant_id=TENANT_ID, from_clause=from_clause, relation=relation, to_clause=to_clause
    )


# --- reciprocal_rank_fusion: pura, sin base (BR2.3, TECH-U8.3) -----------------


def test_fusion_suma_el_rango_reciproco_de_las_dos_listas() -> None:
    fusionadas = retrieval.reciprocal_rank_fusion(
        lexical=("A", "B", "C"), vector=("B", "A", "D"), k=60
    )
    # B aparece primero en vectorial (rango 2) y segundo en lexico (rango 2):
    # 1/62 + 1/62 = mas que A, que tambien aparece en las dos pero mas lejos en
    # vectorial. Se afirma el orden completo, no solo el primero.
    assert fusionadas == ("A", "B", "C", "D")


def test_fusion_nunca_suma_puntajes_de_escalas_distintas() -> None:
    # Si sumara puntajes crudos en vez de rango reciproco, una lista con
    # valores en otra escala mandaria. Aqui solo importa la posicion.
    fusionadas = retrieval.reciprocal_rank_fusion(lexical=("X",), vector=("Y", "Z"))
    assert fusionadas == ("X", "Y", "Z")


def test_fusion_es_deterministica_a_igualdad_de_puntaje() -> None:
    # Dos identificadores que solo aparecen, cada uno, en una sola lista y en
    # el mismo rango relativo empatan en puntaje; el desempate es el orden de
    # aparicion (lexico antes que vectorial), no el alfabetico.
    fusionadas_1 = retrieval.reciprocal_rank_fusion(lexical=("Z",), vector=("A",))
    fusionadas_2 = retrieval.reciprocal_rank_fusion(lexical=("Z",), vector=("A",))
    assert fusionadas_1 == fusionadas_2 == ("Z", "A")


def test_fusion_de_dos_listas_vacias_es_vacia() -> None:
    assert retrieval.reciprocal_rank_fusion(lexical=(), vector=()) == ()


# --- _close_over_relations: pura, sin base (BR2.4) -----------------------------


def test_cierre_anade_el_endoso_vigente_que_modifica_una_clausula_recuperada() -> None:
    relaciones = (_relacion("END-1-A", RelationKind.ENDORSEMENT_MODIFIES, "A"),)
    cierre = retrieval._close_over_relations(
        ("A",), relations=relaciones, candidate_clause_ids=frozenset({"A", "END-1-A"})
    )
    assert cierre == {"END-1-A": "A"}


def test_cierre_anade_la_definicion_que_usa_una_clausula_recuperada() -> None:
    relaciones = (_relacion("DEF.X", RelationKind.DEFINES, "A"),)
    cierre = retrieval._close_over_relations(
        ("A",), relations=relaciones, candidate_clause_ids=frozenset({"A", "DEF.X"})
    )
    assert cierre == {"DEF.X": "A"}


def test_cierre_ignora_refers_to() -> None:
    # refers_to apunta al documento de jurisdiccion: no compite ni cierra (BR2.4).
    relaciones = (_relacion("A", RelationKind.REFERS_TO, "JUR-1"),)
    cierre = retrieval._close_over_relations(
        ("A",), relations=relaciones, candidate_clause_ids=frozenset({"A", "JUR-1"})
    )
    assert cierre == {}


def test_cierre_no_arrastra_un_endoso_que_no_es_vigente_para_esta_poliza() -> None:
    # La relacion existe en el corpus, pero el endoso no esta en el universo
    # candidato de esta poliza (no es uno de sus endosos vigentes): no entra
    # por la puerta de atras del cierre.
    relaciones = (_relacion("END-9-A", RelationKind.ENDORSEMENT_MODIFIES, "A"),)
    cierre = retrieval._close_over_relations(
        ("A",), relations=relaciones, candidate_clause_ids=frozenset({"A"})
    )
    assert cierre == {}


def test_cierre_no_duplica_una_clausula_que_ya_esta_en_la_fusion() -> None:
    relaciones = (_relacion("B", RelationKind.ENDORSEMENT_MODIFIES, "A"),)
    cierre = retrieval._close_over_relations(
        ("A", "B"), relations=relaciones, candidate_clause_ids=frozenset({"A", "B"})
    )
    assert cierre == {}


# --- retrieve(): orquestacion sobre `repository`, con dobles (BR2.1 a BR2.6) ---


def test_poliza_inexistente_y_de_otra_aseguradora_devuelven_lo_mismo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BR2.6: la funcion no tiene ninguna rama que las distinga.

    `find_policy` ya devuelve `None` para las dos -- la politica de fila filtra
    la segunda antes de que este codigo la vea -- asi que ejercitar "inexistente"
    es ejercitar tambien "de otra aseguradora": es literalmente el mismo camino.
    """

    async def _sin_poliza(tenant_id: str, *, policy_number: str) -> None:
        return None

    monkeypatch.setattr(repository, "find_policy", _sin_poliza)

    resultado = _correr(
        retrieval.retrieve(
            TENANT_ID,
            policy_number="POL-INEXISTENTE",
            query_text="cualquier pregunta",
            query_vector=(0.1, 0.2),
            embedding_model="test-embedder-v1",
            now=AHORA,
        )
    )

    assert resultado.clauses == ()
    assert resultado.probe.clause_ids == ()
    assert resultado.probe.filtered_by == {"tenant_id": TENANT_ID}


def test_poliza_fuera_de_vigencia_da_conjunto_vacio(monkeypatch: pytest.MonkeyPatch) -> None:
    """BR2.2: ni de la version anterior ni aproximada -- vacio, sin mas."""
    poliza = _poliza(period_start=date(2020, 1, 1), period_end=date(2021, 1, 1))

    async def _con_poliza(tenant_id: str, *, policy_number: str) -> IssuedPolicy:
        return poliza

    llamadas: list[str] = []

    async def _candidatas_que_no_deberian_llamarse(*args: Any, **kwargs: Any) -> tuple[Clause, ...]:
        llamadas.append("candidate_clauses")
        return ()

    monkeypatch.setattr(repository, "find_policy", _con_poliza)
    monkeypatch.setattr(repository, "candidate_clauses", _candidatas_que_no_deberian_llamarse)

    resultado = _correr(
        retrieval.retrieve(
            TENANT_ID,
            policy_number=poliza.policy_number,
            query_text="pregunta",
            query_vector=(0.1,),
            embedding_model="test-embedder-v1",
            now=AHORA,
        )
    )

    assert resultado.clauses == ()
    assert resultado.probe.clause_ids == ()
    # Y ni siquiera se busco un candidato: una poliza vencida no recupera nada,
    # no se aproxima a la version anterior (BR2.2).
    assert llamadas == []


def test_filtra_antes_de_puntuar_el_candidato_no_incluye_otra_aseguradora(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BR2.1: el universo que se busca es exactamente el que la poliza referencia.

    El doble de `candidate_clauses` afirma con que filtros lo llamaron --
    formulario, version y endosos de la poliza-- antes de que la fusion vea
    nada: si la busqueda pidiera un candidato mas amplio y filtrara despues,
    esta aserción lo detectaria.
    """
    poliza = _poliza()
    clausula = _clausula("TCO-PAP-2026-A.LIMIT")
    filtros_usados: dict[str, Any] = {}

    async def _con_poliza(tenant_id: str, *, policy_number: str) -> IssuedPolicy:
        return poliza

    async def _candidatas(
        tenant_id: str, *, form_id: str, form_version: str, endorsement_ids: Any
    ) -> tuple[Clause, ...]:
        filtros_usados.update(
            form_id=form_id, form_version=form_version, endorsement_ids=tuple(endorsement_ids)
        )
        return (clausula,)

    async def _lexico(*args: Any, **kwargs: Any) -> tuple[str, ...]:
        return (clausula.clause_id,)

    async def _vectorial(*args: Any, **kwargs: Any) -> tuple[str, ...]:
        return ()

    async def _relaciones(*args: Any, **kwargs: Any) -> tuple[ClauseRelation, ...]:
        return ()

    async def _por_id(tenant_id: str, *, clause_ids: Any) -> tuple[Clause, ...]:
        return tuple(c for c in (clausula,) if c.clause_id in clause_ids)

    monkeypatch.setattr(repository, "find_policy", _con_poliza)
    monkeypatch.setattr(repository, "candidate_clauses", _candidatas)
    monkeypatch.setattr(repository, "lexical_rank", _lexico)
    monkeypatch.setattr(repository, "vector_rank", _vectorial)
    monkeypatch.setattr(repository, "relations_into", _relaciones)
    monkeypatch.setattr(repository, "clauses_by_ids", _por_id)

    resultado = _correr(
        retrieval.retrieve(
            TENANT_ID,
            policy_number=poliza.policy_number,
            query_text="cual es mi limite",
            query_vector=(0.1,),
            embedding_model="test-embedder-v1",
            now=AHORA,
        )
    )

    assert filtros_usados == {
        "form_id": poliza.form_id,
        "form_version": poliza.form_version,
        "endorsement_ids": poliza.endorsement_ids,
    }
    assert resultado.clauses == (clausula,)


def test_una_clausula_de_cierre_no_lleva_rango_lexico_ni_vectorial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BR2.4: el cierre no cuenta para la metrica de recuperacion.

    La cláusula que entró por el cierre tiene que quedar marcada como tal en la
    sonda -- `closure_of` distinto de `None`, sin rango en ninguna de las dos
    búsquedas -- para que quien mida REL-U8.1 no la confunda con algo que la
    búsqueda encontró de verdad.
    """
    poliza = _poliza()
    base = _clausula("A")
    endoso = _clausula("END-1-A", form_id="TCO-PAP-2026-END-1")

    async def _con_poliza(tenant_id: str, *, policy_number: str) -> IssuedPolicy:
        return poliza

    async def _candidatas(*args: Any, **kwargs: Any) -> tuple[Clause, ...]:
        return (base, endoso)

    async def _lexico(*args: Any, **kwargs: Any) -> tuple[str, ...]:
        return ("A",)

    async def _vectorial(*args: Any, **kwargs: Any) -> tuple[str, ...]:
        return ()

    async def _relaciones(tenant_id: str, *, clause_ids: Any) -> tuple[ClauseRelation, ...]:
        return (_relacion("END-1-A", RelationKind.ENDORSEMENT_MODIFIES, "A"),)

    async def _por_id(tenant_id: str, *, clause_ids: Any) -> tuple[Clause, ...]:
        universo = {"A": base, "END-1-A": endoso}
        return tuple(universo[cid] for cid in clause_ids if cid in universo)

    monkeypatch.setattr(repository, "find_policy", _con_poliza)
    monkeypatch.setattr(repository, "candidate_clauses", _candidatas)
    monkeypatch.setattr(repository, "lexical_rank", _lexico)
    monkeypatch.setattr(repository, "vector_rank", _vectorial)
    monkeypatch.setattr(repository, "relations_into", _relaciones)
    monkeypatch.setattr(repository, "clauses_by_ids", _por_id)

    resultado = _correr(
        retrieval.retrieve(
            TENANT_ID,
            policy_number=poliza.policy_number,
            query_text="cual es mi limite",
            query_vector=(0.1,),
            embedding_model="test-embedder-v1",
            now=AHORA,
        )
    )

    assert resultado.clauses == (base, endoso)
    fuente_base = resultado.probe.sources["A"]
    fuente_endoso = resultado.probe.sources["END-1-A"]
    assert fuente_base.lexical_rank == 1
    assert fuente_endoso.closure_of == "A"
    assert fuente_endoso.lexical_rank is None
    assert fuente_endoso.vector_rank is None


def _correr(coro: Any) -> Any:
    return asyncio.run(coro)
