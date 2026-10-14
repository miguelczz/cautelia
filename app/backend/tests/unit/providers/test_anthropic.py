"""El adaptador de Anthropic, sin red y sin clave: el cliente del SDK es un doble.

Lo que se prueba es lo que el adaptador promete al resto del aplicativo: el
texto, el gasto registrado siempre, los cuatro tipos de error, la parada por
saldo agotado y el techo consultado antes de llamar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import pytest
from pydantic import BaseModel

from untangle.base import ProviderErrorKind, ProviderName, UnitKind, Use
from untangle.providers import prompts
from untangle.providers.adapters.anthropic import AnthropicTextGenerator
from untangle.providers.ports import (
    BudgetExhausted,
    ExhaustedResource,
    ExternalText,
    Prompt,
    PromptPart,
    ProviderError,
    UsageReport,
)

_PETICION = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def _respuesta(texto: str = "Qué susto. ¿Hubo alguien herido?", *, parada: str = "end_turn") -> Any:
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=texto)],
        stop_reason=parada,
        usage=SimpleNamespace(input_tokens=480, output_tokens=40),
    )


def _rechazo(estado: int, cuerpo: dict[str, Any] | None = None) -> anthropic.APIStatusError:
    respuesta = httpx2.Response(estado, request=_PETICION)
    return anthropic.APIStatusError("rechazo", response=respuesta, body=cuerpo or {})


@dataclass
class _Mensajes:
    resultado: Any = None
    error: Exception | None = None
    llamadas: list[dict[str, Any]] = field(default_factory=list)

    async def create(self, **kwargs: Any) -> Any:
        self.llamadas.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.resultado


@dataclass
class _Cliente:
    messages: _Mensajes


@dataclass
class _Contabilidad:
    reportes: list[UsageReport] = field(default_factory=list)

    async def report(self, usage: UsageReport) -> None:
        self.reportes.append(usage)


@dataclass
class _Techo:
    cerrado: bool = False

    async def ensure_open(self, *, provider: ProviderName, use: Use) -> None:
        if self.cerrado:
            raise BudgetExhausted(ExhaustedResource.PROJECT_CAP, provider=provider, use=use)


def _prompt() -> Prompt:
    return Prompt(
        instruction=prompts.load_system_instruction("conversation", "es"),
        parts=(
            PromptPart(
                role="user",
                text=ExternalText("<mensaje_de_la_persona>Hola</mensaje_de_la_persona>"),
            ),
        ),
    )


def _armar(
    mensajes: _Mensajes, *, techo: _Techo | None = None
) -> tuple[AnthropicTextGenerator, _Contabilidad]:
    contabilidad = _Contabilidad()
    generador = AnthropicTextGenerator(
        _Cliente(mensajes),
        use=Use.CHAT_REPLY,
        model="claude-haiku-5-5",
        gate=techo or _Techo(),
        usage=contabilidad,
    )
    return generador, contabilidad


async def test_devuelve_el_texto_y_registra_lo_que_gasto() -> None:
    mensajes = _Mensajes(resultado=_respuesta())
    generador, contabilidad = _armar(mensajes)

    resultado = await generador.generate(_prompt(), schema=None, use=Use.CHAT_REPLY)

    assert resultado.text == "Qué susto. ¿Hubo alguien herido?"
    assert resultado.prompt.prompt_id == "conversation"
    [reporte] = contabilidad.reportes
    assert reporte.provider is ProviderName.ANTHROPIC
    assert reporte.use is Use.CHAT_REPLY
    assert {(u.unit_kind, int(u.units)) for u in reporte.units} == {
        (UnitKind.INPUT_TOKENS, 480),
        (UnitKind.OUTPUT_TOKENS, 40),
    }


async def test_la_instruccion_va_aparte_del_contenido() -> None:
    """La instruccion versionada en `system`; lo de fuera, solo en `messages`."""
    mensajes = _Mensajes(resultado=_respuesta())
    generador, _ = _armar(mensajes)

    await generador.generate(_prompt(), schema=None, use=Use.CHAT_REPLY)

    [llamada] = mensajes.llamadas
    [instruccion] = llamada["system"]
    assert "asistente de inteligencia artificial" in instruccion["text"]
    assert "<mensaje_de_la_persona>Hola" not in instruccion["text"]
    # Fija por uso e idioma: va en cache (2026-10-09).
    assert instruccion["cache_control"] == {"type": "ephemeral"}
    assert llamada["messages"][0]["role"] == "user"
    assert llamada["model"] == "claude-haiku-5-5"


@pytest.mark.parametrize(
    ("estado", "esperado"),
    [
        (429, ProviderErrorKind.RATE_LIMITED),
        (529, ProviderErrorKind.UNAVAILABLE),
        (500, ProviderErrorKind.UNAVAILABLE),
        (401, ProviderErrorKind.UNAVAILABLE),
        (504, ProviderErrorKind.TIMEOUT),
        (400, ProviderErrorKind.INVALID_RESPONSE),
    ],
)
async def test_cada_rechazo_sale_como_uno_de_los_cuatro_tipos(
    estado: int, esperado: ProviderErrorKind
) -> None:
    generador, contabilidad = _armar(_Mensajes(error=_rechazo(estado)))

    with pytest.raises(ProviderError) as fallo:
        await generador.generate(_prompt(), schema=None, use=Use.CHAT_REPLY)

    assert fallo.value.kind is esperado
    assert len(contabilidad.reportes) == 1, "el gasto se registra tambien cuando falla"


@pytest.mark.parametrize(
    ("estado", "cuerpo"),
    [
        (402, {}),
        (400, {"type": "error", "error": {"type": "billing_error", "message": "x"}}),
        (
            400,
            {
                "type": "error",
                "error": {
                    "type": "invalid_request_error",
                    "message": "Your credit balance is too low to access the Anthropic API.",
                },
            },
        ),
    ],
)
async def test_el_saldo_agotado_es_la_parada_y_no_un_error_que_se_reintenta(
    estado: int, cuerpo: dict[str, Any]
) -> None:
    generador, _ = _armar(_Mensajes(error=_rechazo(estado, cuerpo)))

    with pytest.raises(BudgetExhausted) as parada:
        await generador.generate(_prompt(), schema=None, use=Use.CHAT_REPLY)

    assert parada.value.resource is ExhaustedResource.PROVIDER_QUOTA


async def test_el_tiempo_vencido_y_la_red_caida_tienen_su_tipo() -> None:
    generador, _ = _armar(_Mensajes(error=anthropic.APITimeoutError(request=_PETICION)))
    with pytest.raises(ProviderError) as vencido:
        await generador.generate(_prompt(), schema=None, use=Use.CHAT_REPLY)
    assert vencido.value.kind is ProviderErrorKind.TIMEOUT

    generador, _ = _armar(
        _Mensajes(error=anthropic.APIConnectionError(message="sin red", request=_PETICION))
    )
    with pytest.raises(ProviderError) as caido:
        await generador.generate(_prompt(), schema=None, use=Use.CHAT_REPLY)
    assert caido.value.kind is ProviderErrorKind.UNAVAILABLE


async def test_con_el_techo_cerrado_no_llama() -> None:
    mensajes = _Mensajes(resultado=_respuesta())
    generador, contabilidad = _armar(mensajes, techo=_Techo(cerrado=True))

    with pytest.raises(BudgetExhausted):
        await generador.generate(_prompt(), schema=None, use=Use.CHAT_REPLY)

    assert mensajes.llamadas == []
    assert contabilidad.reportes == []


@pytest.mark.parametrize("respuesta", [_respuesta(parada="refusal"), _respuesta(texto="   ")])
async def test_una_negativa_o_un_texto_vacio_es_invalid_response(respuesta: Any) -> None:
    generador, _ = _armar(_Mensajes(resultado=respuesta))

    with pytest.raises(ProviderError) as fallo:
        await generador.generate(_prompt(), schema=None, use=Use.CHAT_REPLY)

    assert fallo.value.kind is ProviderErrorKind.INVALID_RESPONSE


async def test_no_atiende_otro_uso() -> None:
    generador, _ = _armar(_Mensajes(resultado=_respuesta()))
    with pytest.raises(ValueError, match="chat_reply"):
        await generador.generate(_prompt(), schema=None, use=Use.CHAT)


class _Esquema(BaseModel):
    intencion: str
    anios: int


async def test_con_esquema_pide_ese_formato_y_devuelve_la_salida_validada() -> None:
    mensajes = _Mensajes(resultado=_respuesta('{"intencion": "cotizar", "anios": 4}'))
    generador, _ = _armar(mensajes)

    resultado = await generador.generate(_prompt(), schema=_Esquema, use=Use.CHAT_REPLY)

    assert resultado.parsed_as(_Esquema) == _Esquema(intencion="cotizar", anios=4)
    [llamada] = mensajes.llamadas
    formato = llamada["output_config"]["format"]
    assert formato["type"] == "json_schema"
    assert set(formato["schema"]["properties"]) == {"intencion", "anios"}
    assert llamada["output_config"]["effort"] == "low"


async def test_sin_esquema_no_pide_formato() -> None:
    mensajes = _Mensajes(resultado=_respuesta())
    generador, _ = _armar(mensajes)

    await generador.generate(_prompt(), schema=None, use=Use.CHAT_REPLY)

    assert "format" not in mensajes.llamadas[0]["output_config"]


async def test_una_salida_que_no_cumple_el_esquema_es_invalid_response() -> None:
    generador, contabilidad = _armar(_Mensajes(resultado=_respuesta('{"intencion": 3}')))

    with pytest.raises(ProviderError) as fallo:
        await generador.generate(_prompt(), schema=_Esquema, use=Use.CHAT_REPLY)

    assert fallo.value.kind is ProviderErrorKind.INVALID_RESPONSE
    assert len(contabilidad.reportes) == 1


async def test_una_llamada_que_falla_sin_informar_consumo_deja_un_tope_contado() -> None:
    """Sin consumo informado la fila quedaria sin valorar, y una sola cierra todo lo que
    cuesta dinero (2026-10-08). El tope cuenta de mas, nunca de menos."""
    from untangle.base import SpendSource

    generador, contabilidad = _armar(_Mensajes(error=anthropic.APITimeoutError(request=_PETICION)))

    with pytest.raises(ProviderError):
        await generador.generate(_prompt(), schema=None, use=Use.CHAT_REPLY)

    [reporte] = contabilidad.reportes
    assert reporte.source is SpendSource.COUNTED_LOCALLY
    unidades = {u.unit_kind: int(u.units) for u in reporte.units}
    enviados = len(str(_prompt().instruction.text)) + len(_prompt().parts[0].text)
    assert unidades[UnitKind.INPUT_TOKENS] > enviados // 4, "nunca por debajo de lo real"
    assert unidades[UnitKind.OUTPUT_TOKENS] == 1024


async def test_con_consumo_informado_se_registra_el_del_proveedor() -> None:
    from untangle.base import SpendSource

    generador, contabilidad = _armar(_Mensajes(resultado=_respuesta()))

    await generador.generate(_prompt(), schema=None, use=Use.CHAT_REPLY)

    assert contabilidad.reportes[0].source is SpendSource.PROVIDER_REPORTED


async def test_lo_escrito_y_leido_de_la_cache_se_registra_a_su_precio() -> None:
    """Con cache, `input_tokens` es solo lo que no estaba en ella: lo escrito vale 1,25
    de entrada y lo leido 0,1, y se registra como entrada equivalente."""
    respuesta = _respuesta()
    respuesta.usage = SimpleNamespace(
        input_tokens=100,
        output_tokens=40,
        cache_creation_input_tokens=1000,
        cache_read_input_tokens=2000,
    )
    generador, contabilidad = _armar(_Mensajes(resultado=respuesta))

    await generador.generate(_prompt(), schema=None, use=Use.CHAT_REPLY)

    [reporte] = contabilidad.reportes
    assert {(u.unit_kind, int(u.units)) for u in reporte.units} == {
        (UnitKind.INPUT_TOKENS, 100 + 1250 + 200),
        (UnitKind.OUTPUT_TOKENS, 40),
    }


async def test_el_modo_cuidadoso_razona_y_el_normal_no() -> None:
    """La propuesta de citas razona; lo que va en el turno no (2026-10-08)."""
    normal = _Mensajes(resultado=_respuesta())
    cuidadoso = _Mensajes(resultado=_respuesta())
    generador, _ = _armar(normal)
    generador_cuidadoso = AnthropicTextGenerator(
        _Cliente(cuidadoso),
        use=Use.CHAT_REPLY,
        model="claude-haiku-5-5",
        gate=_Techo(),
        usage=_Contabilidad(),
        careful=True,
    )

    await generador.generate(_prompt(), schema=None, use=Use.CHAT_REPLY)
    await generador_cuidadoso.generate(_prompt(), schema=None, use=Use.CHAT_REPLY)

    assert normal.llamadas[0]["thinking"] == {"type": "disabled"}
    assert normal.llamadas[0]["output_config"]["effort"] == "low"
    assert cuidadoso.llamadas[0]["thinking"] == {"type": "adaptive"}
    assert cuidadoso.llamadas[0]["output_config"]["effort"] == "high"
    assert cuidadoso.llamadas[0]["max_tokens"] > normal.llamadas[0]["max_tokens"]
