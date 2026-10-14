"""El reporte de activacion (OBS-U6.3, BR8.5), sin base.

Una tabla por dia, una fila por aseguradora, una columna por hito, y **solo
conteos**: ningun identificador de sesion puede aparecer, porque el reporte no
recibe ninguno.
"""

from __future__ import annotations

from datetime import date

import pytest

from untangle.telemetry.activation.models import ActivationDailyCount, ActivationMilestone
from untangle.workspace import activation_report

ASEGURADORAS = ("knotwell", "stonecroft", "sunmeadow")


def _fila(tenant: str, dia: date, hito: ActivationMilestone, conteo: int) -> ActivationDailyCount:
    return ActivationDailyCount(tenant_id=tenant, day=dia, milestone=hito, count=conteo)


def test_sin_filas_dice_que_no_hay_sesiones_en_vez_de_ceros() -> None:
    lineas = activation_report.render_counts((), ASEGURADORAS)

    assert "(ninguna sesion registrada todavia)" in "\n".join(lineas)
    assert "stonecroft" not in "\n".join(lineas)


def test_una_tabla_por_dia_con_ceros_donde_nadie_llego() -> None:
    dia_uno = date(2026, 9, 20)
    dia_dos = date(2026, 9, 21)
    filas = (
        _fila("stonecroft", dia_uno, ActivationMilestone.FIRST_MESSAGE, 4),
        _fila("stonecroft", dia_uno, ActivationMilestone.THIRD_TURN, 2),
        _fila("sunmeadow", dia_dos, ActivationMilestone.LOOP_CLOSED, 1),
    )

    lineas = activation_report.render_counts(filas, ASEGURADORAS)
    texto = "\n".join(lineas)

    assert texto.index("2026-09-20") < texto.index("2026-09-21")
    [stonecroft_dia_uno] = [
        linea for linea in lineas[: lineas.index("2026-09-21")] if "stonecroft" in linea
    ]
    assert stonecroft_dia_uno.split()[1:] == ["4", "2", "0"]
    [knotwell_dia_dos] = [
        linea for linea in lineas[lineas.index("2026-09-21") :] if "knotwell" in linea
    ]
    assert knotwell_dia_dos.split()[1:] == ["0", "0", "0"]


def test_las_columnas_son_los_tres_hitos_en_el_orden_del_recorrido() -> None:
    lineas = activation_report.render_counts(
        (_fila("knotwell", date(2026, 9, 21), ActivationMilestone.FIRST_MESSAGE, 1),),
        ASEGURADORAS,
    )

    [cabecera] = [linea for linea in lineas if linea.strip().startswith("aseguradora")]
    assert cabecera.split()[1:] == ["first_message", "third_turn", "loop_closed"]


def test_sin_base_configurada_el_comando_falla_nombrando_la_variable(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Reportar ceros sin base se leeria como "nadie entro"."""
    monkeypatch.delenv("UNTANGLE_DATABASE_URL", raising=False)

    codigo = activation_report.main()

    assert codigo == 1
    assert "UNTANGLE_DATABASE_URL" in capsys.readouterr().err
