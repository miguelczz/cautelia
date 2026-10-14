"""El comando que anota un ajuste conciliado: lo que decide antes de tocar la base.

Sin base: el libro se sustituye por dobles. Lo que se comprueba aqui es lo que el comando
exige **antes de escribir** --un importe plausible, una nota, un uso del mismo proveedor, el
libro presente-- porque un ajuste no se deshace: el libro no admite importes negativos.

Que la fila y el acumulado entren juntos, que reintentar no duplique y que la base rechace un
ajuste mal formado se prueba contra la base de verdad, en `tests/integration/u5/test_adjustment.py`.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest

from untangle.providers import config as provider_config
from untangle.server import manual_ledger, spend_reconcile, spend_wiring
from untangle.settings import Settings
from untangle.telemetry.spend import api as spend

NOTA = "consola de Anthropic, 2026-10-13"
BASE = ["--provider", "anthropic", "--use", "evals_chat", "--amount", "0.24", "--note", NOTA]


@pytest.fixture(autouse=True)
def contabilidad() -> Iterator[None]:
    spend.reset()
    spend.install(spend_wiring.spend_runtime(provider_config.load()))
    yield
    spend.reset()


@pytest.fixture
def libro(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """El libro sustituido: dice que paso (abrir, escribir, cerrar) sin abrir ninguna base."""
    pasos: list[str] = []

    async def abrir(_config: Any, url: str) -> None:
        pasos.append(f"abrir {url}")

    async def cerrar() -> Decimal | None:
        pasos.append("cerrar")
        return Decimal("0.89")

    async def escribir(entrada: Any, **_: Any) -> spend.AdjustmentResult:
        pasos.append(f"escribir {entrada.cost_usd}")
        return spend.AdjustmentResult(entry=entrada, written=True, spent_usd=Decimal("0.89"))

    monkeypatch.setattr(manual_ledger, "open_ledger", abrir)
    monkeypatch.setattr(manual_ledger, "close_ledger", cerrar)
    monkeypatch.setattr(spend, "record_adjustment", escribir)
    monkeypatch.setenv("UNTANGLE_DATABASE_URL", "postgresql+psycopg://x:y@proyecto/untangle")
    return pasos


# --- El importe, la nota y la fecha -------------------------------------------


@pytest.mark.parametrize(
    ("texto", "dice"),
    [
        ("0", "mayor que cero"),
        ("-0.24", "mayor que cero"),
        ("abc", "no es un numero"),
        ("NaN", "mayor que cero"),
        ("Infinity", "mayor que cero"),
        ("0.1234567", "hasta 6 decimales"),
        ("1000.01", "no puede pasar de 1000 USD"),
    ],
)
def test_un_importe_implausible_se_rechaza_con_su_motivo(
    texto: str, dice: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        spend_reconcile.main([*BASE[:4], "--amount", texto, *BASE[6:]])
    assert dice in capsys.readouterr().err


def test_la_nota_y_la_fecha_se_validan(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        spend_reconcile.main([*BASE[:6], "--note", "   "])
    assert "no puede ir vacia" in capsys.readouterr().err

    with pytest.raises(SystemExit):
        spend_reconcile.main([*BASE[:6], "--note", "x" * 201])
    assert "admite hasta 200 caracteres" in capsys.readouterr().err

    with pytest.raises(SystemExit):
        spend_reconcile.main([*BASE, "--date", "13/10/2026"])
    assert "AAAA-MM-DD" in capsys.readouterr().err


def test_la_nota_se_limpia_de_saltos_de_linea_y_espacios_de_mas() -> None:
    argumentos = spend_reconcile._analizador().parse_args(
        [*BASE[:6], "--note", "  consola de\nAnthropic,   2026-10-13 "]
    )
    assert argumentos.note == "consola de Anthropic, 2026-10-13"


# --- El limite de lo grande ---------------------------------------------------


def test_un_importe_de_cinco_dolares_o_mas_pide_confirmacion_y_no_escribe(
    libro: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    """Casi siempre es el total de la consola puesto por error, y un ajuste no se borra."""
    codigo = spend_reconcile.main([*BASE[:4], "--amount", "5", *BASE[6:]])

    assert codigo == 2
    assert "--allow-large" in capsys.readouterr().err
    assert libro == []


def test_con_allow_large_el_importe_grande_pasa(libro: list[str]) -> None:
    codigo = spend_reconcile.main([*BASE[:4], "--amount", "5", *BASE[6:], "--allow-large"])

    assert codigo == 0
    assert libro == ["abrir postgresql+psycopg://x:y@proyecto/untangle", "escribir 5", "cerrar"]


# --- Sin libro no se escribe --------------------------------------------------


def test_sin_la_base_del_proyecto_no_escribe_y_dice_que_falta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(spend_reconcile, "Settings", lambda: Settings(database_url=None))

    with pytest.raises(SystemExit, match="UNTANGLE_DATABASE_URL"):
        spend_reconcile.main(BASE)


# --- El camino feliz y el dry-run ---------------------------------------------


def test_anota_abriendo_el_libro_antes_y_cerrandolo_despues(
    libro: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    codigo = spend_reconcile.main([*BASE, "--date", "2026-10-13"])

    salida = capsys.readouterr().out
    assert codigo == 0
    assert libro == ["abrir postgresql+psycopg://x:y@proyecto/untangle", "escribir 0.24", "cerrar"]
    assert "proveedor     anthropic" in salida
    assert "modelo        claude-haiku-5-5" in salida
    assert "evals_chat  (facturable)" in salida
    assert f"nota          {NOTA}" in salida
    assert "fecha         2026-10-13" in salida
    assert "Anotado. Cuenta contra el techo de la ventana." in salida
    assert "0.890000 USD" in salida


def test_dry_run_ensena_el_asiento_y_no_escribe(
    libro: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    codigo = spend_reconcile.main([*BASE, "--dry-run"])

    assert codigo == 0
    assert libro == ["abrir postgresql+psycopg://x:y@proyecto/untangle", "cerrar"]
    salida = capsys.readouterr().out
    assert "--dry-run: no se escribio nada" in salida
    assert "adj-" in salida


def test_el_modelo_se_puede_decir_y_si_no_es_el_del_uso(
    libro: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    spend_reconcile.main([*BASE, "--model", "claude-otro", "--dry-run"])
    assert "modelo        claude-otro" in capsys.readouterr().out


def test_un_uso_de_otro_proveedor_se_rechaza_antes_de_escribir(
    libro: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    codigo = spend_reconcile.main([*BASE[:2], "--use", "operations", *BASE[4:]])

    assert codigo == 2
    assert "es de gemini, no de anthropic" in capsys.readouterr().err
    assert "escribir 0.24" not in libro
    # El libro se cierra igual: abrirlo cambio el punto de sesion y hay que devolverlo.
    assert libro[-1] == "cerrar"


def test_el_reintento_se_dice_y_no_se_anuncia_como_nuevo(
    monkeypatch: pytest.MonkeyPatch, libro: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    async def ya_estaba(entrada: Any, **_: Any) -> spend.AdjustmentResult:
        return spend.AdjustmentResult(entry=entrada, written=False, spent_usd=None)

    monkeypatch.setattr(spend, "record_adjustment", ya_estaba)

    assert spend_reconcile.main(BASE) == 0

    salida = capsys.readouterr().out
    assert "ya estaba en el libro" in salida
    assert "Anotado." not in salida
