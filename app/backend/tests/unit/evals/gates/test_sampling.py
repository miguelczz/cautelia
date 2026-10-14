"""Pruebas de la muestra para revision humana (BR3.4): reproducible, sin `random`."""

from __future__ import annotations

from untangle.evals.gates.sampling import review_sample


def test_la_misma_semilla_elige_siempre_lo_mismo() -> None:
    casos = tuple(f"DS-2/es/{i:03d}" for i in range(20))
    a = review_sample(casos, seed="hito-1")
    b = review_sample(casos, seed="hito-1")
    assert a == b


def test_el_veinte_por_ciento_se_respeta() -> None:
    casos = tuple(f"DS-2/es/{i:03d}" for i in range(20))
    assert len(review_sample(casos, seed="hito-1")) == 4


def test_todos_los_fallos_del_juez_entran_aunque_no_esten_en_el_veinte_por_ciento() -> None:
    casos = tuple(f"DS-2/es/{i:03d}" for i in range(20))
    fallo = "DS-2/es/999"
    muestra = review_sample(casos, seed="hito-1", judge_failures=frozenset({fallo}))
    assert fallo in muestra


def test_una_semilla_distinta_puede_elegir_otro_subconjunto() -> None:
    casos = tuple(f"DS-2/es/{i:03d}" for i in range(20))
    a = review_sample(casos, seed="hito-1")
    b = review_sample(casos, seed="hito-2")
    assert a != b
