"""Los tokens de lo que no tiene precio publicado (2026-10-11).

"Sin precio" no es "sin dato": el proveedor reporta cuantos tokens conto aunque la
tabla de precios no tenga la linea de ese modelo, y el tablero los muestra en vez
de callar. Lo que estas pruebas defienden es que **solo se diga "plan gratuito"
cuando el dato lo respalda** y que las tres consultas que calculan los tokens no
discrepen entre si ni con la que decide la actividad.
"""

from __future__ import annotations

import re

from untangle.base import UnitKind
from untangle.telemetry.spend import repository
from untangle.telemetry.spend.models import TOKEN_UNIT_KINDS, UnpricedUsage


def test_sumar_dos_parciales_gratuitos_sigue_siendo_gratuito() -> None:
    suma = UnpricedUsage(tokens=10, free_plan=True) + UnpricedUsage(tokens=5, free_plan=True)

    assert suma == UnpricedUsage(tokens=15, uncounted=0, free_plan=True)


def test_una_sola_parte_de_pago_quita_el_plan_gratuito_a_la_suma() -> None:
    suma = UnpricedUsage(tokens=10, free_plan=True) + UnpricedUsage(tokens=5, free_plan=False)

    assert suma.tokens == 15
    assert suma.free_plan is False


def test_una_parte_sin_recuento_tambien_dice_de_que_plan_es() -> None:
    # El servicio de vectores de Google no reporta tokens: de esas llamadas se sabe
    # cuantas fueron y que no cuestan, y eso tambien respalda decir "plan gratuito".
    gratis_sin_recuento = UnpricedUsage(uncounted=2, free_plan=True)
    de_pago_sin_recuento = UnpricedUsage(uncounted=2, free_plan=False)

    assert (UnpricedUsage(tokens=7, free_plan=True) + gratis_sin_recuento).free_plan is True
    assert (UnpricedUsage(tokens=7, free_plan=True) + de_pago_sin_recuento).free_plan is False
    assert (gratis_sin_recuento + gratis_sin_recuento) == UnpricedUsage(uncounted=4, free_plan=True)


def test_una_parte_vacia_no_decide_nada() -> None:
    assert (UnpricedUsage() + UnpricedUsage(tokens=7, free_plan=True)).free_plan is True
    assert (UnpricedUsage() + UnpricedUsage()).free_plan is False


def test_los_llamados_sin_recuento_se_suman_aparte_y_no_inventan_tokens() -> None:
    suma = UnpricedUsage(tokens=3, uncounted=1, free_plan=True) + UnpricedUsage(uncounted=4)

    assert suma.tokens == 3
    assert suma.uncounted == 5


def test_las_clases_de_token_son_las_de_tokens_y_nada_mas() -> None:
    assert (
        frozenset({UnitKind.INPUT_TOKENS, UnitKind.OUTPUT_TOKENS, UnitKind.EMBEDDING_TOKENS})
        == TOKEN_UNIT_KINDS
    )
    assert UnitKind.AUDIO_SECONDS not in TOKEN_UNIT_KINDS
    assert UnitKind.CHARACTERS not in TOKEN_UNIT_KINDS


def _columnas_sin_precio(consulta: str) -> str:
    """Las tres columnas de tokens, sin el alias de tabla, para compararlas."""
    texto = re.sub(r"\s+", " ", re.sub(r"\be\.", "", consulta))
    encontrado = re.search(r"COALESCE\(SUM\(units\).*?AS unpriced_free_plan", texto)
    assert encontrado is not None
    return encontrado.group(0)


def test_las_tres_consultas_de_tokens_cuentan_lo_mismo() -> None:
    por_caso = _columnas_sin_precio(repository.CASOS_RECIENTES)
    por_proveedor = _columnas_sin_precio(repository.SIN_PRECIO_POR_PROVEEDOR)
    por_actividad = _columnas_sin_precio(repository.SIN_PRECIO_POR_ACTIVIDAD)

    assert por_caso == por_proveedor == por_actividad


def test_la_actividad_de_los_tokens_se_decide_con_la_misma_regla_que_la_del_dinero() -> None:
    def regla(consulta: str) -> str:
        texto = re.sub(r"\s+", " ", consulta)
        return texto[texto.index("CASE ") : texto.index(" END") + 4]

    assert regla(repository.SIN_PRECIO_POR_ACTIVIDAD) == regla(repository.GASTO_POR_DIA_Y_ACTIVIDAD)
