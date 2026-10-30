"""PERF-U11.1, ADR-006: el presupuesto de 3.900 tokens de entrada se cuenta."""

from __future__ import annotations

from untangle.orchestration.nodes.intake import budget, extraction
from untangle.providers import prompts


def test_contar_no_depende_de_llamar_al_proveedor() -> None:
    """Dos conteos del mismo texto dan el mismo numero, sin red ni proveedor."""
    texto = "Soy Laura Gomez, mi poliza es POL-50."
    assert budget.count_tokens(texto) == budget.count_tokens(texto)
    assert budget.count_tokens(texto) > 0


def test_el_prompt_real_de_extraccion_cabe_en_el_presupuesto_de_voz() -> None:
    instruccion = prompts.load_system_instruction("intake_extraction", "es")
    turno = "Soy Laura Gomez, mi poliza es POL-50." * 3
    prompt = extraction.build_extraction_prompt(instruccion, turno)
    assert budget.assert_within_voice_budget(prompt) == ()


def test_un_turno_que_desborda_el_presupuesto_se_detecta() -> None:
    instruccion = prompts.load_system_instruction("intake_extraction", "es")
    turno_enorme = "palabra " * 4_000
    prompt = extraction.build_extraction_prompt(instruccion, turno_enorme)
    problemas = budget.assert_within_voice_budget(prompt)
    assert len(problemas) == 1
    assert "3900" in problemas[0] or "3.900" in problemas[0] or "3_900" in problemas[0]
