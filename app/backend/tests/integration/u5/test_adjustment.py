"""El asiento de ajuste conciliado, contra la base de verdad (2026-10-13).

Son de integracion porque lo que se comprueba son conductas **del motor**: que la fila y
el acumulado entren en una transaccion, que reintentar no sume dos veces, y que las
restricciones de la base --no el modelo de Python-- rechacen un ajuste mal formado.

**Ninguna prueba gasta un centavo**: un ajuste no llama a ningun proveedor, y el
acumulado se siembra directo en la fila de la ventana.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from untangle.base import ProviderName, Use
from untangle.providers import config as provider_config
from untangle.providers.ceiling import ceiling_closed
from untangle.server import spend_reconcile, spend_wiring
from untangle.telemetry.spend import api as spend
from untangle.telemetry.spend import repository
from untangle.telemetry.spend.models import WINDOW_START, SpendEntry
from untangle.tenancy import ephemeral, session

from .conftest import AHORA, VENTANA_FIN, sembrar_ventana

HOY = date(2026, 10, 13)
NOTA = "consola de Anthropic, 2026-10-13"

CONTAR = "SELECT count(*) AS total FROM spend_entry"
LEER_AJUSTES = (
    "SELECT entry_id, provider, model, use, units, unit_price_usd, price_list_version, "
    "price_list_effective_date, cost_usd, cost_status, billable, source, note, occurred_at "
    "FROM spend_entry WHERE source = 'reconciled_adjustment' ORDER BY entry_id"
)

_INSERTAR = """
    INSERT INTO spend_entry (
        entry_id, provider, model, use, units, unit_kind, unit_price_usd, price_list_version,
        price_list_effective_date, cost_usd, cost_status, billable, lane, source, occurred_at, note
    ) VALUES (
        :entrada, 'anthropic', 'claude-haiku-5-5', 'evals_chat', :unidades, 'input_tokens',
        :precio, :version, :fecha_de_lista, :costo, :estado, true, 'public', :origen, :ahora, :nota
    )
"""


@pytest.fixture(autouse=True)
def contabilidad(dinero: None) -> Iterator[None]:
    """La contabilidad con la configuracion de verdad, para que el plan de cada uso sea el real."""
    spend.reset()
    spend.install(spend_wiring.spend_runtime(provider_config.load()))
    yield
    spend.reset()


def _ajuste(*, importe: str = "0.24", nota: str = NOTA, uso: Use = Use.EVALS_CHAT) -> SpendEntry:
    proveedor = ProviderName.ANTHROPIC if uso is Use.EVALS_CHAT else ProviderName.GEMINI
    return spend.adjustment_entry(
        provider=proveedor, use=uso, amount_usd=Decimal(importe), note=nota, on=HOY
    )


async def _filas() -> int:
    async with session.unscoped_session() as sesion:
        fila = await session.fetch_one(sesion, CONTAR)
    return int(fila["total"]) if fila is not None else 0


async def _acumulado() -> Decimal:
    ventana = await repository.load_window(WINDOW_START)
    assert ventana is not None
    return ventana.billable_spent_usd


# --- Escribir un ajuste -------------------------------------------------------


async def test_un_ajuste_facturable_se_escribe_con_su_nota_y_suma_al_acumulado(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """La fila y el acumulado son una sola cosa: el techo ve lo que el ajuste suma."""
    await sembrar_ventana(gastado=Decimal("0.65"))

    resultado = await spend.record_adjustment(_ajuste(), now=AHORA)

    assert resultado.written
    assert resultado.spent_usd == Decimal("0.89")
    assert await _acumulado() == Decimal("0.89")
    async with session.unscoped_session() as sesion:
        (fila,) = await session.fetch_all(sesion, LEER_AJUSTES)
    assert fila["provider"] == "anthropic"
    # El modelo es el que `providers.yaml` declara para el uso, no uno inventado.
    assert fila["model"] == "claude-haiku-5-5"
    assert fila["use"] == "evals_chat"
    assert fila["cost_usd"] == Decimal("0.24")
    assert fila["cost_status"] == "measured"
    assert fila["billable"] is True
    assert fila["note"] == NOTA
    assert fila["units"] == 0
    # No lo valoro ninguna lista: ninguna de las tres columnas restantes de precio.
    assert fila["unit_price_usd"] is None
    assert fila["price_list_version"] is None
    assert fila["price_list_effective_date"] is None
    assert fila["occurred_at"] == datetime(2026, 10, 13, 12, tzinfo=UTC)


async def test_reintentar_el_mismo_ajuste_no_duplica_ni_suma_dos_veces(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """Sumar dos veces cerraria el techo antes de tiempo: el error contrario al que se corrige."""
    await sembrar_ventana(gastado=Decimal("0.65"))
    await spend.record_adjustment(_ajuste(), now=AHORA)

    de_nuevo = await spend.record_adjustment(_ajuste(), now=AHORA)

    assert not de_nuevo.written
    assert de_nuevo.spent_usd is None
    assert await _filas() == 1
    assert await _acumulado() == Decimal("0.89")


async def test_dos_ajustes_del_mismo_dia_se_distinguen_por_su_nota(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    await sembrar_ventana(gastado=Decimal(0))
    await spend.record_adjustment(_ajuste(nota="consola de Anthropic, 2026-10-13"), now=AHORA)
    await spend.record_adjustment(_ajuste(nota="factura de octubre de Anthropic"), now=AHORA)

    assert await _filas() == 2
    assert await _acumulado() == Decimal("0.48")


async def test_el_mismo_importe_escrito_de_dos_maneras_es_el_mismo_ajuste() -> None:
    assert _ajuste(importe="0.24").entry_id == _ajuste(importe="0.2400").entry_id
    assert _ajuste(importe="0.24").entry_id != _ajuste(importe="0.25").entry_id


async def test_un_ajuste_de_un_uso_gratuito_deja_la_fila_y_no_mueve_el_techo(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """Un uso en plan gratuito no suma contra el techo (BR4.2): se anota, no se cuenta."""
    await sembrar_ventana(gastado=Decimal("0.65"))

    resultado = await spend.record_adjustment(_ajuste(uso=Use.OPERATIONS), now=AHORA)

    assert resultado.written
    assert resultado.spent_usd is None
    assert await _filas() == 1
    assert await _acumulado() == Decimal("0.65")


async def test_sin_ventana_no_se_escribe_nada_ni_la_fila(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """La fila y el acumulado van juntos o no va ninguno: sin ventana, ninguno."""
    with pytest.raises(repository.WindowNotFoundError):
        await spend.record_adjustment(_ajuste(), now=AHORA)

    assert await _filas() == 0


async def test_el_techo_ve_el_ajuste_que_antes_no_veia(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """Para eso existe: con el libro corto, el techo decidia con un acumulado de menos."""
    await sembrar_ventana(gastado=Decimal("39.90"), techo=Decimal("40.00"), alerta=Decimal("24.00"))
    assert not ceiling_closed(await spend.budget_state())

    await spend.record_adjustment(_ajuste(importe="0.24"), now=AHORA)

    assert ceiling_closed(await spend.budget_state())


async def test_el_ajuste_cuenta_en_las_sumas_del_tablero(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """Entra por proveedor, por modelo, por actividad y en la suma de la ventana."""
    await sembrar_ventana()
    await spend.record_adjustment(_ajuste(), now=AHORA)

    por_proveedor = dict(await repository.spend_by_provider())
    assert por_proveedor[ProviderName.ANTHROPIC].measured_usd == Decimal("0.24")
    por_modelo = {(p, m): t.measured_usd for p, m, t in await repository.spend_by_model()}
    assert por_modelo[(ProviderName.ANTHROPIC, "claude-haiku-5-5")] == Decimal("0.24")
    del_dia = await repository.spend_by_day_and_activity(WINDOW_START)
    assert [(a.value, t.measured_usd) for _, a, t in del_dia] == [
        ("quality_tests", Decimal("0.24"))
    ]
    en_la_ventana = await repository.window_spend(WINDOW_START, VENTANA_FIN)
    assert en_la_ventana.measured_usd == Decimal("0.24")
    assert en_la_ventana.unmeasured_count == 0


# --- Lo que la base rechaza, aunque el modelo se saltara ----------------------


async def _insertar(**campos: object) -> None:
    base: dict[str, object] = {
        "entrada": "a-mano",
        "unidades": Decimal(0),
        "precio": None,
        "version": None,
        "fecha_de_lista": None,
        "costo": Decimal("0.24"),
        "estado": "measured",
        "origen": "reconciled_adjustment",
        "ahora": AHORA,
        "nota": NOTA,
    }
    async with session.unscoped_session() as sesion:
        await session.execute_sql(sesion, _INSERTAR, **(base | campos))


async def test_la_base_acepta_un_ajuste_bien_formado(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    await _insertar()
    assert await _filas() == 1


@pytest.mark.parametrize(
    ("campos", "restriccion"),
    [
        ({"nota": None}, "spend_entry_nota_solo_en_ajustes"),
        ({"origen": "provider_reported"}, "spend_entry_nota_solo_en_ajustes"),
        ({"unidades": Decimal(3)}, "spend_entry_ajuste_con_su_importe"),
        (
            {"costo": None, "estado": "not_measured"},
            "spend_entry_ajuste_con_su_importe",
        ),
        (
            {"precio": Decimal("0.1"), "version": "0", "fecha_de_lista": HOY},
            "spend_entry_precio_completo_o_ausente",
        ),
        ({"origen": "inventado", "nota": None}, "spend_entry_origen_valido"),
    ],
)
async def test_la_base_rechaza_un_ajuste_mal_formado_y_una_nota_donde_no_va(
    sesiones: ephemeral.EphemeralDatabase, campos: dict[str, object], restriccion: str
) -> None:
    with pytest.raises(IntegrityError, match=restriccion):
        await _insertar(**campos)
    assert await _filas() == 0


async def test_una_llamada_sigue_exigiendo_sus_cuatro_columnas_de_precio(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """Relajar la regla para el ajuste no la relaja para nadie mas (BR3.4)."""
    with pytest.raises(IntegrityError, match="spend_entry_precio_completo_o_ausente"):
        await _insertar(origen="provider_reported", nota=None, unidades=Decimal(10))


# --- El comando, de punta a punta sobre la base -------------------------------


def _argumentos(*extra: str) -> argparse.Namespace:
    return spend_reconcile._analizador().parse_args(
        ["--provider", "anthropic", "--use", "evals_chat", "--amount", "0.24", "--note", NOTA,
         "--date", "2026-10-13", *extra]
    )  # fmt: skip


async def test_el_comando_anota_el_ajuste_y_dice_el_acumulado_del_proyecto(
    sesiones: ephemeral.EphemeralDatabase, capsys: pytest.CaptureFixture[str]
) -> None:
    await sembrar_ventana(gastado=Decimal("0.65"))

    codigo = await spend_reconcile._anotar(provider_config.load(), sesiones.app_url, _argumentos())

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "Anotado. Cuenta contra el techo de la ventana." in salida
    assert "libro de la base del proyecto: 0.890000 USD" in salida
    assert NOTA in salida
    assert await _filas() == 1


async def test_el_comando_con_dry_run_ensena_el_asiento_y_no_escribe(
    sesiones: ephemeral.EphemeralDatabase, capsys: pytest.CaptureFixture[str]
) -> None:
    await sembrar_ventana(gastado=Decimal("0.65"))

    codigo = await spend_reconcile._anotar(
        provider_config.load(), sesiones.app_url, _argumentos("--dry-run")
    )

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "no se escribio nada" in salida
    assert "0.24 USD" in salida
    assert await _filas() == 0
    assert await _acumulado() == Decimal("0.65")


async def test_el_comando_repetido_dice_que_ya_estaba(
    sesiones: ephemeral.EphemeralDatabase, capsys: pytest.CaptureFixture[str]
) -> None:
    await sembrar_ventana(gastado=Decimal("0.65"))
    await spend_reconcile._anotar(provider_config.load(), sesiones.app_url, _argumentos())
    capsys.readouterr()

    codigo = await spend_reconcile._anotar(provider_config.load(), sesiones.app_url, _argumentos())

    assert codigo == 0
    assert "ya estaba en el libro" in capsys.readouterr().out
    assert await _filas() == 1
    assert await _acumulado() == Decimal("0.89")


async def test_el_comando_sin_ventana_se_detiene_sin_escribir(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    with pytest.raises(SystemExit, match="no tiene la ventana de presupuesto"):
        await spend_reconcile._anotar(provider_config.load(), sesiones.app_url, _argumentos())

    assert await _filas() == 0
    # Y el punto de sesion queda donde estaba: el comando no se lo lleva.
    assert session.configured_url() == sesiones.app_url


async def test_el_comando_con_un_uso_de_otro_proveedor_se_detiene_sin_escribir(
    sesiones: ephemeral.EphemeralDatabase, capsys: pytest.CaptureFixture[str]
) -> None:
    await sembrar_ventana()
    argumentos = spend_reconcile._analizador().parse_args(
        ["--provider", "anthropic", "--use", "operations", "--amount", "0.24", "--note", NOTA]
    )

    codigo = await spend_reconcile._anotar(provider_config.load(), sesiones.app_url, argumentos)

    assert codigo == 2
    assert "es de gemini, no de anthropic" in capsys.readouterr().err
    assert await _filas() == 0
