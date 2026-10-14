"""Con que modelos se declara una corrida de evaluacion (2026-10-11)."""

from __future__ import annotations

from untangle.providers import config as provider_config
from untangle.server import understanding_cli


def test_los_modelos_de_la_corrida_salen_de_la_configuracion_versionada() -> None:
    """El identificador exacto con el que corrio, no uno escrito a mano en el reporte."""
    anclados = understanding_cli.pinned_models(provider_config.load())

    assert anclados["anthropic:generation"] == "claude-haiku-5-5"
    assert anclados["gemini:embedding"] == "gemini-embedding-001"
    # Dos modelos del mismo proveedor y uso: salen los dos, ninguno pisa al otro.
    de_gemini = {v for k, v in anclados.items() if k.startswith("gemini:generation")}
    assert len(de_gemini) == 2


def test_la_voz_no_se_declara_en_una_corrida_de_texto() -> None:
    anclados = understanding_cli.pinned_models(provider_config.load())

    assert not any("transcription" in clave or "synthesis" in clave for clave in anclados)
