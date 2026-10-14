"""La sonda que corre la prueba de integracion de U12 lee bien su resultado (2026-10-09).

Se sustituye el proceso de pytest por uno que escribe el reporte que se quiere: lo
que se prueba es la lectura, no la prueba de integracion, que tiene la suya.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from untangle.evals import integration_probes as ip
from untangle.evals.runner.failures import TargetUnavailableError


def _con_reporte(monkeypatch: pytest.MonkeyPatch, cuerpo: str | None) -> None:
    ip._correr.cache_clear()

    def falso(argumentos: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        if cuerpo is not None:
            destino = next(a for a in argumentos if a.startswith("--junitxml="))
            Path(destino.split("=", 1)[1]).write_text(
                f'<testsuites><testsuite><testcase name="t">{cuerpo}</testcase>'
                "</testsuite></testsuites>",
                encoding="utf-8",
            )
        return subprocess.CompletedProcess(argumentos, 0, "", "")

    monkeypatch.setattr(subprocess, "run", falso)


def _chequeo() -> Any:
    return ip._sonda("test_ds2_dropped_call_resumed")


def test_la_prueba_que_pasa_es_un_caso_en_verde(monkeypatch: pytest.MonkeyPatch) -> None:
    _con_reporte(monkeypatch, "")
    assert _chequeo()(language="es", root=Path()).passed is True


def test_la_prueba_que_falla_es_un_caso_en_rojo(monkeypatch: pytest.MonkeyPatch) -> None:
    _con_reporte(monkeypatch, '<failure message="x"/>')
    assert _chequeo()(language="en", root=Path()).passed is False


@pytest.mark.parametrize("cuerpo", ['<error message="sin base"/>', "<skipped/>", None])
def test_sin_poder_prepararla_el_caso_queda_no_medido(
    monkeypatch: pytest.MonkeyPatch, cuerpo: str | None
) -> None:
    _con_reporte(monkeypatch, cuerpo)
    with pytest.raises(TargetUnavailableError):
        _chequeo()(language="es", root=Path())


def test_los_tres_criterios_quedan_registrados() -> None:
    from untangle.evals.runner import api

    api.reset()
    ip.register_integration_probes()
    for criterio in ip.CRITERIOS:
        assert api.check_for(criterio) is not None
    api.reset()
