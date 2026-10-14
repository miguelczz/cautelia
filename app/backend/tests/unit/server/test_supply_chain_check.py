"""El chequeo de cadena de suministro (SEC-U1.4).

Nace de un fallo real: los dos ajustes de pnpm estaban en `.npmrc`, pnpm 12 no
los leia y no avisaba. Por eso estas pruebas comprueban que el chequeo **falla**
cuando el control no esta vivo, que es lo unico que lo hace util.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from untangle.workspace import supply_chain_check


def _manifiesto(directorio: Path, valor: str | None) -> None:
    backend = directorio / "app" / "backend"
    backend.mkdir(parents=True, exist_ok=True)
    linea = f'exclude-newer = "{valor}"\n' if valor is not None else ""
    (backend / "pyproject.toml").write_text(f"[tool.uv]\n{linea}", encoding="utf-8")


@pytest.fixture(autouse=True)
def interfaz_registrada(tmp_path: Path) -> None:
    """Una interfaz sin dependencias y con su registro, que por eso esta al dia.

    Desde U6 el chequeo tambien compara `app/frontend/DEPENDENCIES.md` con
    `package.json` (TECH-U6.1); esa mitad tiene sus pruebas en
    `tests/unit/web/test_dependencies_ledger.py`. Aqui se deja en verde para que
    cada prueba mire solo la espera de los gestores.
    """
    frontend = tmp_path / "app" / "frontend"
    frontend.mkdir(parents=True)
    (frontend / "package.json").write_text("{}", encoding="utf-8")
    (frontend / "DEPENDENCIES.md").write_text("# Dependencias\n", encoding="utf-8")


def test_pasa_cuando_los_dos_gestores_tienen_su_espera(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _manifiesto(tmp_path, supply_chain_check.ESPERA_MINIMA_UV)
    monkeypatch.setattr(
        supply_chain_check,
        "_pnpm_config",
        lambda clave, _dir: {
            "minimumReleaseAge": str(supply_chain_check.ESPERA_MINIMA_MINUTOS),
            "ignoreScripts": "true",
        }[clave],
    )
    assert supply_chain_check.run_all(tmp_path) == []


def test_falla_cuando_pnpm_ignora_el_ajuste(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El fallo del 2026-09-20: el valor esta escrito y pnpm responde vacio."""
    _manifiesto(tmp_path, supply_chain_check.ESPERA_MINIMA_UV)
    monkeypatch.setattr(supply_chain_check, "_pnpm_config", lambda _c, _d: "")

    problemas = supply_chain_check.run_all(tmp_path)

    assert len(problemas) == 2
    assert any("minimumReleaseAge" in p for p in problemas)
    assert any("ignoreScripts" in p for p in problemas)
    # El mensaje tiene que decir donde va el ajuste, o no sirve de nada.
    assert all("pnpm-workspace.yaml" in p for p in problemas)


def test_falla_cuando_uv_no_tiene_su_espera(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _manifiesto(tmp_path, None)
    monkeypatch.setattr(
        supply_chain_check,
        "_pnpm_config",
        lambda clave, _dir: {
            "minimumReleaseAge": str(supply_chain_check.ESPERA_MINIMA_MINUTOS),
            "ignoreScripts": "true",
        }[clave],
    )

    problemas = supply_chain_check.run_all(tmp_path)

    assert len(problemas) == 1
    assert "exclude-newer" in problemas[0]


def test_falla_cuando_falta_el_manifiesto_de_python(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        supply_chain_check,
        "_pnpm_config",
        lambda clave, _dir: {
            "minimumReleaseAge": str(supply_chain_check.ESPERA_MINIMA_MINUTOS),
            "ignoreScripts": "true",
        }[clave],
    )

    problemas = supply_chain_check.run_all(tmp_path)

    assert len(problemas) == 1
    assert "manifiesto de Python" in problemas[0]
