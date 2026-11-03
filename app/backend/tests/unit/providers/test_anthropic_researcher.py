"""El investigador con busqueda web de Anthropic, sin red y sin clave: el cliente es un doble.

Lo que se prueba es lo que el adaptador promete al ajustador: la herramienta de busqueda bien
declarada y acotada, las paginas que respaldan el texto, el consumo --tokens **y busquedas**--
registrado siempre y valorado con la tabla de precios de verdad, los cuatro tipos de error, la
parada por saldo agotado y el techo consultado antes de llamar.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import anthropic
import pytest

from untangle import paths
from untangle.base import ProviderErrorKind, ProviderName, SpendSource, UnitKind, Use
from untangle.providers import config as provider_config
from untangle.providers.adapters.anthropic import AnthropicWebResearcher
from untangle.providers.ports import (
    BudgetExhausted,
    ExhaustedResource,
    ProviderError,
    ResearchResult,
    UsageReport,
    WebResearcher,
)
from untangle.telemetry.spend import pricing

from .test_anthropic import (
    _Cliente,
    _Contabilidad,
    _Mensajes,
    _prompt,
    _rechazo,
    _Techo,
)

DOMINIOS = ("fasecolda.com", "tucarro.com.co")


def _resultado(url: str, titulo: str, edad: str | None = None) -> Any:
    return SimpleNamespace(
        type="web_search_result",
        url=url,
        title=titulo,
        page_age=edad,
        encrypted_content="cifrado",
    )


def _cita(url: str, titulo: str) -> Any:
    return SimpleNamespace(
        type="web_search_result_location",
        url=url,
        title=titulo,
        cited_text="...",
        encrypted_index="x",
    )


def _respuesta_con_busqueda(*, parada: str = "end_turn", busquedas: int | None = 2) -> Any:
    """Lo que el servidor devuelve cuando el modelo busca dos veces y cita una pagina."""
    servidor = None if busquedas is None else SimpleNamespace(web_search_requests=busquedas)
    return SimpleNamespace(
        content=[
            SimpleNamespace(type="text", text="Voy a buscar el valor de referencia."),
            SimpleNamespace(
                type="server_tool_use", id="srv_1", name="web_search", input={"query": "mazda 3"}
            ),
            SimpleNamespace(
                type="web_search_tool_result",
                tool_use_id="srv_1",
                content=[
                    _resultado("https://fasecolda.com/guia", "Guia de valores", "hace 3 dias"),
                    _resultado("https://tucarro.com.co/aviso-1", "Mazda 3 2020"),
                ],
            ),
            SimpleNamespace(
                type="text",
                text=" El valor de referencia ronda los 62.000.000 COP.",
                citations=[_cita("https://fasecolda.com/guia", "Guia de valores")],
            ),
        ],
        stop_reason=parada,
        usage=SimpleNamespace(
            input_tokens=5200,
            output_tokens=310,
            server_tool_use=servidor,
        ),
    )


def _armar(
    mensajes: _Mensajes, *, techo: _Techo | None = None
) -> tuple[AnthropicWebResearcher, _Contabilidad]:
    contabilidad = _Contabilidad()
    investigador = AnthropicWebResearcher(
        _Cliente(mensajes),
        use=Use.ADJUSTER,
        model="claude-haiku-5-5",
        gate=techo or _Techo(),
        usage=contabilidad,
    )
    return investigador, contabilidad


async def _investigar(investigador: AnthropicWebResearcher, **cambios: Any) -> ResearchResult:
    argumentos: dict[str, Any] = {
        "use": Use.ADJUSTER,
        "max_searches": 3,
        "allowed_domains": DOMINIOS,
    }
    return await investigador.research(_prompt(), **(argumentos | cambios))


def _unidades(reporte: UsageReport) -> dict[UnitKind, int]:
    return {u.unit_kind: int(u.units) for u in reporte.units}


def test_cumple_el_puerto() -> None:
    investigador, _ = _armar(_Mensajes())
    assert isinstance(investigador, WebResearcher)


async def test_devuelve_el_texto_las_paginas_citadas_y_las_busquedas_que_hizo() -> None:
    investigador, _ = _armar(_Mensajes(resultado=_respuesta_con_busqueda()))

    resultado = await _investigar(investigador)

    assert "62.000.000 COP" in resultado.text
    assert resultado.searches_used == 2
    # Solo la pagina que el texto cita, con la antiguedad que trajo la busqueda.
    [fuente] = resultado.sources
    assert fuente.url == "https://fasecolda.com/guia"
    assert fuente.title == "Guia de valores"
    assert fuente.page_age == "hace 3 dias"


async def test_el_texto_es_lo_que_escribio_despues_de_su_ultima_busqueda() -> None:
    """La frase de antes de buscar ("voy a buscar...") no es parte del hallazgo."""
    investigador, _ = _armar(_Mensajes(resultado=_respuesta_con_busqueda()))

    resultado = await _investigar(investigador)

    assert "Voy a buscar" not in resultado.text
    assert resultado.text.startswith("El valor de referencia")


async def test_sin_citas_las_fuentes_son_todas_las_que_trajo_la_busqueda() -> None:
    respuesta = _respuesta_con_busqueda()
    respuesta.content[-1].citations = None
    investigador, _ = _armar(_Mensajes(resultado=respuesta))

    resultado = await _investigar(investigador)

    assert [f.url for f in resultado.sources] == [
        "https://fasecolda.com/guia",
        "https://tucarro.com.co/aviso-1",
    ]
    assert resultado.sources[1].page_age is None


async def test_una_pagina_repetida_o_citada_dos_veces_sale_una_vez() -> None:
    respuesta = _respuesta_con_busqueda()
    respuesta.content[-1].citations = [
        _cita("https://fasecolda.com/guia", "Guia"),
        _cita("https://fasecolda.com/guia", "Guia"),
    ]
    investigador, _ = _armar(_Mensajes(resultado=respuesta))

    resultado = await _investigar(investigador)

    assert len(resultado.sources) == 1


async def test_el_modelo_que_no_busca_devuelve_cero_busquedas_y_ninguna_fuente_sin_error() -> None:
    respuesta = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="No hace falta buscar.")],
        stop_reason="end_turn",
        usage=SimpleNamespace(input_tokens=900, output_tokens=20, server_tool_use=None),
    )
    investigador, contabilidad = _armar(_Mensajes(resultado=respuesta))

    resultado = await _investigar(investigador)

    assert resultado.searches_used == 0
    assert resultado.sources == ()
    assert resultado.text == "No hace falta buscar."
    # Cero busquedas no es consumo: no deja una fila de busquedas en el libro.
    assert UnitKind.WEB_SEARCHES not in _unidades(contabilidad.reportes[0])


async def test_agotar_las_busquedas_permitidas_no_es_un_error() -> None:
    """`max_uses_exceeded` llega como un objeto de error dentro del resultado, con 200."""
    respuesta = _respuesta_con_busqueda(busquedas=3)
    respuesta.content.insert(
        3,
        SimpleNamespace(
            type="web_search_tool_result",
            tool_use_id="srv_2",
            content=SimpleNamespace(
                type="web_search_tool_result_error", error_code="max_uses_exceeded"
            ),
        ),
    )
    investigador, _ = _armar(_Mensajes(resultado=respuesta))

    resultado = await _investigar(investigador)

    assert resultado.searches_used == 3
    assert [f.url for f in resultado.sources] == ["https://fasecolda.com/guia"]


async def test_declara_la_herramienta_acotada_y_no_pide_salida_estructurada() -> None:
    mensajes = _Mensajes(resultado=_respuesta_con_busqueda())
    investigador, _ = _armar(mensajes)

    await _investigar(investigador, max_searches=2)

    [llamada] = mensajes.llamadas
    [herramienta] = llamada["tools"]
    assert herramienta == {
        "type": "web_search_20260318",
        "name": "web_search",
        "max_uses": 2,
        "allowed_domains": ["fasecolda.com", "tucarro.com.co"],
        "allowed_callers": ["direct"],
    }
    # La busqueda y la salida estructurada van en llamadas separadas.
    assert "format" not in llamada["output_config"]
    assert llamada["model"] == "claude-haiku-5-5"
    assert llamada["thinking"] == {"type": "disabled"}


async def test_la_instruccion_va_aparte_del_contenido() -> None:
    mensajes = _Mensajes(resultado=_respuesta_con_busqueda())
    investigador, _ = _armar(mensajes)

    await _investigar(investigador)

    [llamada] = mensajes.llamadas
    [instruccion] = llamada["system"]
    assert "<mensaje_de_la_persona>Hola" not in instruccion["text"]
    assert llamada["messages"][0]["role"] == "user"
    assert "<mensaje_de_la_persona>Hola" in llamada["messages"][0]["content"]


async def test_registra_tokens_y_busquedas_y_se_valoran_con_la_tabla_de_precios_de_verdad() -> None:
    """El costo de la llamada es los tokens mas las busquedas, a precio de lista."""
    investigador, contabilidad = _armar(_Mensajes(resultado=_respuesta_con_busqueda(busquedas=3)))

    await _investigar(investigador)

    [reporte] = contabilidad.reportes
    assert reporte.provider is ProviderName.ANTHROPIC
    assert reporte.use is Use.ADJUSTER
    assert reporte.source is SpendSource.PROVIDER_REPORTED
    assert _unidades(reporte) == {
        UnitKind.INPUT_TOKENS: 5200,
        UnitKind.OUTPUT_TOKENS: 310,
        UnitKind.WEB_SEARCHES: 3,
    }

    tabla = pricing.PriceTable.from_entries(
        provider_config.load(paths.providers_dir()).prices.price_entries()
    )
    costos = [
        pricing.price_call(
            tabla,
            provider=reporte.provider,
            model=reporte.model,
            unit_kind=unidad.unit_kind,
            units=unidad.units,
        ).cost
        for unidad in reporte.units
    ]
    assert all(costo.is_measured for costo in costos), "todas las unidades tienen precio"
    total = sum((costo.amount_usd or Decimal(0) for costo in costos), Decimal(0))
    # 5200 de entrada a 0,10 USD/M, 310 de salida a 0,50 USD/M y 3 busquedas a 0,01 USD.
    assert total == Decimal("0.00052") + Decimal("0.000155") + Decimal("0.03")


@pytest.mark.parametrize(
    ("estado", "esperado"),
    [
        (429, ProviderErrorKind.RATE_LIMITED),
        (529, ProviderErrorKind.UNAVAILABLE),
        (500, ProviderErrorKind.UNAVAILABLE),
        (401, ProviderErrorKind.UNAVAILABLE),
        (504, ProviderErrorKind.TIMEOUT),
        (408, ProviderErrorKind.TIMEOUT),
        (400, ProviderErrorKind.INVALID_RESPONSE),
    ],
)
async def test_cada_rechazo_sale_como_uno_de_los_cuatro_tipos(
    estado: int, esperado: ProviderErrorKind
) -> None:
    investigador, contabilidad = _armar(_Mensajes(error=_rechazo(estado)))

    with pytest.raises(ProviderError) as fallo:
        await _investigar(investigador)

    assert fallo.value.kind is esperado
    assert fallo.value.use is Use.ADJUSTER
    assert len(contabilidad.reportes) == 1, "el gasto se registra tambien cuando falla"


async def test_el_saldo_agotado_es_la_parada_y_no_un_error_que_se_reintenta() -> None:
    investigador, _ = _armar(_Mensajes(error=_rechazo(402)))

    with pytest.raises(BudgetExhausted) as parada:
        await _investigar(investigador)

    assert parada.value.resource is ExhaustedResource.PROVIDER_QUOTA
    assert parada.value.use is Use.ADJUSTER


async def test_el_tiempo_vencido_y_la_red_caida_tienen_su_tipo() -> None:
    peticion = _rechazo(500).request
    investigador, _ = _armar(_Mensajes(error=anthropic.APITimeoutError(request=peticion)))
    with pytest.raises(ProviderError) as vencido:
        await _investigar(investigador)
    assert vencido.value.kind is ProviderErrorKind.TIMEOUT

    investigador, _ = _armar(
        _Mensajes(error=anthropic.APIConnectionError(message="sin red", request=peticion))
    )
    with pytest.raises(ProviderError) as caido:
        await _investigar(investigador)
    assert caido.value.kind is ProviderErrorKind.UNAVAILABLE


async def test_una_llamada_que_falla_sin_consumo_deja_un_tope_que_incluye_todas_las_busquedas() -> (
    None
):
    """Sin consumo informado la fila quedaria sin valorar, y una sola cierra todo lo que cuesta
    dinero. El tope cuenta de mas, nunca de menos: aqui, las 3 busquedas que la llamada admitia."""
    peticion = _rechazo(500).request
    investigador, contabilidad = _armar(
        _Mensajes(error=anthropic.APITimeoutError(request=peticion))
    )

    with pytest.raises(ProviderError):
        await _investigar(investigador, max_searches=3)

    [reporte] = contabilidad.reportes
    assert reporte.source is SpendSource.COUNTED_LOCALLY
    unidades = _unidades(reporte)
    assert unidades[UnitKind.WEB_SEARCHES] == 3
    assert unidades[UnitKind.OUTPUT_TOKENS] == 2048
    assert unidades[UnitKind.INPUT_TOKENS] > 0


async def test_con_el_techo_cerrado_no_llama() -> None:
    mensajes = _Mensajes(resultado=_respuesta_con_busqueda())
    investigador, contabilidad = _armar(mensajes, techo=_Techo(cerrado=True))

    with pytest.raises(BudgetExhausted):
        await _investigar(investigador)

    assert mensajes.llamadas == []
    assert contabilidad.reportes == []


@pytest.mark.parametrize("parada", ["pause_turn", "max_tokens", "refusal"])
async def test_una_respuesta_incompleta_o_negada_es_invalid_response_y_se_cobra(
    parada: str,
) -> None:
    investigador, contabilidad = _armar(_Mensajes(resultado=_respuesta_con_busqueda(parada=parada)))

    with pytest.raises(ProviderError) as fallo:
        await _investigar(investigador)

    assert fallo.value.kind is ProviderErrorKind.INVALID_RESPONSE
    assert _unidades(contabilidad.reportes[0])[UnitKind.WEB_SEARCHES] == 2


async def test_un_texto_vacio_es_invalid_response() -> None:
    respuesta = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="   ")],
        stop_reason="end_turn",
        usage=SimpleNamespace(input_tokens=10, output_tokens=1, server_tool_use=None),
    )
    investigador, _ = _armar(_Mensajes(resultado=respuesta))

    with pytest.raises(ProviderError) as fallo:
        await _investigar(investigador)

    assert fallo.value.kind is ProviderErrorKind.INVALID_RESPONSE


async def test_no_atiende_otro_uso() -> None:
    investigador, _ = _armar(_Mensajes(resultado=_respuesta_con_busqueda()))
    with pytest.raises(ValueError, match="adjuster"):
        await _investigar(investigador, use=Use.CHAT_REPLY)


async def test_una_busqueda_sin_dominios_o_sin_busquedas_no_llama() -> None:
    mensajes = _Mensajes(resultado=_respuesta_con_busqueda())
    investigador, contabilidad = _armar(mensajes)

    with pytest.raises(ValueError, match="dominios"):
        await _investigar(investigador, allowed_domains=())
    with pytest.raises(ValueError, match="al menos una"):
        await _investigar(investigador, max_searches=0)

    assert mensajes.llamadas == []
    assert contabilidad.reportes == []
