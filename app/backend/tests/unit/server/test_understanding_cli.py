"""Con que modelos se declara una corrida de evaluacion (2026-10-11)."""

from __future__ import annotations

import argparse
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from untangle.case_record import crypto
from untangle.evals import adjuster_probes
from untangle.evals import cli as evals_cli
from untangle.evals.runner import runner
from untangle.providers import config as provider_config
from untangle.server import adjuster_eval, composition, manual_ledger, understanding_cli
from untangle.settings import ADJUSTER_ANTHROPIC_API_KEY_VAR, Settings


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


# --- evals:ajustador (2026-11-04) -------------------------------------------------------------


def _argumentos(destino: Path) -> argparse.Namespace:
    return understanding_cli._analizador().parse_args(
        ["--subset", "ajustador", "--out", str(destino)]
    )


@pytest.fixture
def ajustador(monkeypatch: pytest.MonkeyPatch) -> Iterator[SimpleNamespace]:
    """Lo que toca el exterior en la corrida del ajustador, doblado y anotado."""
    visto = SimpleNamespace(construyo=0, subconjunto=None, escribio=None)

    async def nada(*args: object) -> None:
        del args

    async def cerrar() -> str:
        return "0.01"

    async def correr(**kwargs: Any) -> Any:
        visto.subconjunto = kwargs["subset"]
        return SimpleNamespace(
            run=SimpleNamespace(run_id="run-1", results=()),
            report=object(),
            exit_code=0,
        )

    def construir(*args: object, **kwargs: object) -> Any:
        visto.construyo += 1
        return None

    monkeypatch.setattr(manual_ledger, "project_ledger_url", lambda *a, **k: "u")
    monkeypatch.setattr(manual_ledger, "open_ledger", nada)
    monkeypatch.setattr(manual_ledger, "close_ledger", cerrar)
    monkeypatch.setattr(evals_cli, "register_all_probes", lambda: None)
    monkeypatch.setattr(evals_cli, "summarize", lambda r: "resumen")
    monkeypatch.setattr(evals_cli, "write_report", lambda r, d: d)
    monkeypatch.setattr(runner, "run_evaluation", correr)
    monkeypatch.setattr(
        composition,
        "build_provider_platform",
        lambda *a, **k: SimpleNamespace(embedder=SimpleNamespace(embed=nada)),
    )
    monkeypatch.setattr(adjuster_eval, "build_decider", construir)
    monkeypatch.setattr(crypto, "install", lambda c: None)
    monkeypatch.setattr(crypto.Cipher, "from_settings", lambda *a, **k: object())
    yield visto
    adjuster_probes.install(None)


def test_el_ajustador_corre_su_subconjunto_con_la_clave_del_uso(
    ajustador: SimpleNamespace, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ajustes = Settings(anthropic_api_key_adjuster="clave", case_field_encryption_key="k")

    salida = understanding_cli._correr_ajustador(
        _argumentos(tmp_path / "r.json"), ajustes, provider_config.load()
    )

    assert salida == 0
    assert ajustador.construyo == 1
    assert ajustador.subconjunto == "ajustador"
    texto = capsys.readouterr().out
    assert "action_allowed" in texto
    assert "gasto acumulado" in texto


def test_sin_la_clave_del_uso_no_se_arma_nada_y_el_corredor_dice_cual_falta(
    ajustador: SimpleNamespace,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def sin_clave(**kwargs: Any) -> Any:
        msg = f"falta la variable de entorno {ADJUSTER_ANTHROPIC_API_KEY_VAR}"
        raise runner.EnvironmentNotReadyError(msg)

    monkeypatch.setattr(runner, "run_evaluation", sin_clave)

    salida = understanding_cli._correr_ajustador(
        _argumentos(tmp_path / "r.json"),
        Settings(anthropic_api_key_adjuster=None),
        provider_config.load(),
    )

    assert salida == 2
    assert ajustador.construyo == 0
    assert ADJUSTER_ANTHROPIC_API_KEY_VAR in capsys.readouterr().err


def test_sin_la_clave_de_cifrado_no_se_llama_a_nadie(
    ajustador: SimpleNamespace, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ajustes = Settings(anthropic_api_key_adjuster="clave", case_field_encryption_key=None)

    salida = understanding_cli._correr_ajustador(
        _argumentos(tmp_path / "r.json"), ajustes, provider_config.load()
    )

    assert salida == 2
    assert ajustador.subconjunto is None
    assert "No se llamo a nadie" in capsys.readouterr().err
