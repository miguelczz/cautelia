"""El paso `vehicle_value`: de la investigacion a un valor verificable o a «no pude verificar».

La lectura del valor es de codigo --una linea de formato fijo, estricta-- y nunca de una tercera
llamada al modelo. Un valor sin fuente de los dominios permitidos o fuera del rango creible no
existe: el paso dice que no pudo verificarlo.
"""

from __future__ import annotations

from datetime import date

import pytest

from untangle.adjuster import vehicle_value
from untangle.adjuster.vehicle_value import (
    Firmness,
    NotVerifiedReason,
    ValueStatus,
)
from untangle.base import ProviderErrorKind, ProviderName, Use
from untangle.providers.ports import (
    BudgetExhausted,
    ExhaustedResource,
    ProviderError,
    ResearchResult,
    ResearchSource,
)

from .support import CONFIGURACION, Mundo, investigacion

HOY = date(2026, 11, 3)


@pytest.mark.parametrize(
    ("texto", "valor", "firmeza"),
    [
        ("Algo.\nVALUE_COP: 85000000\nCONFIDENCE: high", 85_000_000, Firmness.HIGH),
        ("VALUE_COP: 85000000\nCONFIDENCE: medium\n", 85_000_000, Firmness.MEDIUM),
        ("  VALUE_COP: 120000000  \n  CONFIDENCE: low  ", 120_000_000, Firmness.LOW),
        # La ultima linea manda: el modelo puede explicar sus intentos antes.
        ("VALUE_COP: 1\nVALUE_COP: 90000000\nCONFIDENCE: high", 90_000_000, Firmness.HIGH),
        # Sin firmeza dicha, la mas baja: nada se supone firme.
        ("VALUE_COP: 85000000", 85_000_000, Firmness.LOW),
        ("VALUE_COP: 85000000\nCONFIDENCE: altisima", 85_000_000, Firmness.LOW),
        ("VALUE_COP: not_found\nCONFIDENCE: low", None, Firmness.LOW),
        # Estricto: separadores, formato o texto alrededor no son una cifra.
        ("VALUE_COP: 85.000.000\nCONFIDENCE: high", None, Firmness.HIGH),
        ("VALUE_COP: 85,000,000", None, Firmness.LOW),
        ("**VALUE_COP:** 85000000", None, Firmness.LOW),
        ("El texto dice VALUE_COP: 85000000 pero no es una linea", None, Firmness.LOW),
        ("VALUE_COP: 85000000 pesos", None, Firmness.LOW),
        ("El valor es de 85 millones.", None, Firmness.LOW),
        ("", None, Firmness.LOW),
    ],
)
def test_se_lee_el_valor_solo_de_la_linea_de_formato_fijo(
    texto: str, valor: int | None, firmeza: Firmness
) -> None:
    leido = vehicle_value.parse_research(texto)

    assert leido.value_cop == valor
    assert leido.firmness is firmeza


def _con_texto(texto: str, *, url: str = "https://www.fasecolda.com/x") -> ResearchResult:
    return ResearchResult(
        text=texto, sources=(ResearchSource(url=url, title="Una pagina"),), searches_used=1
    )


async def test_un_valor_creible_con_fuente_de_un_dominio_permitido_es_encontrado(
    mundo: Mundo,
) -> None:
    mundo.investigador.respuesta = investigacion(firmeza="high")

    valor = await vehicle_value.look_up(
        "Mazda CX-5 2022", ports=mundo.puertos, config=CONFIGURACION, language="es", today=HOY
    )

    assert valor.status is ValueStatus.FOUND
    assert valor.value_cop == 85_000_000
    assert valor.firmness is Firmness.HIGH
    assert valor.source is not None
    assert valor.source.url.startswith("https://www.fasecolda.com/")
    assert valor.searches_used == 2
    assert valor.reason is None


@pytest.mark.parametrize(
    ("respuesta", "motivo"),
    [
        (_con_texto("VALUE_COP: 4999\nCONFIDENCE: high"), NotVerifiedReason.IMPLAUSIBLE),
        (_con_texto("VALUE_COP: 900000000\nCONFIDENCE: high"), NotVerifiedReason.IMPLAUSIBLE),
        (_con_texto("VALUE_COP: not_found"), NotVerifiedReason.NO_VALUE),
        (_con_texto("sin formato"), NotVerifiedReason.NO_VALUE),
        (
            _con_texto("VALUE_COP: 85000000", url="https://sitio-malo.example.com/x"),
            NotVerifiedReason.NO_SOURCE,
        ),
        (
            _con_texto("VALUE_COP: 85000000", url="https://fasecolda.com.evil.example.com/x"),
            NotVerifiedReason.NO_SOURCE,
        ),
        (
            ResearchResult(text="VALUE_COP: 85000000", sources=(), searches_used=0),
            NotVerifiedReason.NO_SOURCE,
        ),
    ],
)
async def test_lo_que_no_se_puede_verificar_nunca_es_un_valor(
    mundo: Mundo, respuesta: ResearchResult, motivo: NotVerifiedReason
) -> None:
    mundo.investigador.respuesta = respuesta

    valor = await vehicle_value.look_up(
        "Mazda CX-5 2022", ports=mundo.puertos, config=CONFIGURACION, language="es", today=HOY
    )

    assert valor.status is ValueStatus.NOT_VERIFIED
    assert valor.value_cop is None
    assert valor.source is None
    assert valor.reason is motivo


async def test_el_subdominio_de_un_dominio_permitido_cuenta(mundo: Mundo) -> None:
    mundo.investigador.respuesta = _con_texto(
        "VALUE_COP: 85000000\nCONFIDENCE: medium", url="https://guiadevalores.fasecolda.com/a"
    )

    valor = await vehicle_value.look_up(
        "Mazda CX-5 2022", ports=mundo.puertos, config=CONFIGURACION, language="es", today=HOY
    )

    assert valor.status is ValueStatus.FOUND


@pytest.mark.parametrize("tipo", list(ProviderErrorKind))
async def test_un_error_del_proveedor_es_no_pude_verificar_y_no_una_excepcion(
    mundo: Mundo, tipo: ProviderErrorKind
) -> None:
    mundo.investigador.respuesta = ProviderError(
        tipo, provider=ProviderName.ANTHROPIC, use=Use.ADJUSTER
    )

    valor = await vehicle_value.look_up(
        "Mazda CX-5 2022", ports=mundo.puertos, config=CONFIGURACION, language="es", today=HOY
    )

    assert valor.status is ValueStatus.NOT_VERIFIED
    assert valor.reason is NotVerifiedReason.PROVIDER_ERROR


async def test_el_saldo_agotado_no_se_traga(mundo: Mundo) -> None:
    mundo.investigador.respuesta = BudgetExhausted(
        ExhaustedResource.PROVIDER_QUOTA, provider=ProviderName.ANTHROPIC, use=Use.ADJUSTER
    )

    with pytest.raises(BudgetExhausted):
        await vehicle_value.look_up(
            "Mazda CX-5 2022", ports=mundo.puertos, config=CONFIGURACION, language="es", today=HOY
        )


async def test_sin_vehiculo_no_se_busca(mundo: Mundo) -> None:
    valor = await vehicle_value.look_up(
        None, ports=mundo.puertos, config=CONFIGURACION, language="es", today=HOY
    )

    assert valor.status is ValueStatus.NO_VEHICLE
    assert mundo.investigador.llamadas == []


def test_de_varios_vehiculos_se_elige_el_que_nombra_el_reporte() -> None:
    vehiculos = ("Chevrolet Spark 2019", "Mazda CX-5 2022")

    assert vehicle_value.pick_vehicle(vehiculos, "Es el Mazda, lo manejaba yo") == vehiculos[1]
    assert vehicle_value.pick_vehicle(vehiculos, "El carro rojo") == vehiculos[0]
    assert vehicle_value.pick_vehicle((), "Mazda") is None
