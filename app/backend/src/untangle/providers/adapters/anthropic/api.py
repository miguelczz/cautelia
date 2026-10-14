"""El adaptador de Anthropic: Claude Haiku 5.5 para entender y para decir en el chat.

Implementa el mismo puerto que Gemini, `TextGenerator`, y hace lo mismo que el:
pide con la instruccion **separada** del contenido, traduce el error a uno de los
cuatro tipos, reporta lo que consumio a la contabilidad y consulta el techo antes
de llamar. Lo que no hace, tampoco lo hace Gemini: no reintenta --quien llama
decide; aqui, mandar la frase del catalogo-- y no degrada a otro proveedor.

**Es el unico archivo del aplicativo que importa el SDK de Anthropic** (contrato
`sdk-solo-en-su-adaptador`). El cliente lo recibe construido desde la raiz de
composicion, con la clave del uso `chat_reply` dentro, y este archivo no la ve.

Decision de Miguel del 2026-10-07: el chat sonaba a contestadora. Medido ese dia
con este modelo y estos parametros: mediana 1,1 s y peor caso 1,5 s por
respuesta, 0,0001 USD por respuesta. El mismo dia, segunda decision: la agente
entiende la conversacion con este modelo, y para eso el adaptador admite un
esquema y devuelve la salida ya validada contra el (salida estructurada del
proveedor, `output_config.format`).
"""

from __future__ import annotations

from decimal import ROUND_CEILING, Decimal
from typing import Any, Protocol

import anthropic
from pydantic import BaseModel, ValidationError

from untangle.base import ProviderErrorKind, ProviderName, SpendSource, UnitKind, Use
from untangle.providers.ports import (
    BudgetExhausted,
    ExhaustedResource,
    GenerationResult,
    Prompt,
    ProviderError,
    SpendGate,
    TextGenerator,
    UsageReport,
    UsageSink,
    UsageUnits,
)

PROVIDER = ProviderName.ANTHROPIC

#: Sin razonamiento y con esfuerzo bajo: la tarea es decir con otras palabras una
#: frase que el codigo ya eligio, y el razonamiento solo agregaria espera. Claude
#: Haiku 5.5 acepta `disabled` con esfuerzo `low`.
_THINKING: dict[str, Any] = {"type": "disabled"}
#: El modo cuidadoso: razonamiento adaptativo y espacio para el.
_THINKING_CUIDADOSO: dict[str, Any] = {"type": "adaptive"}
_MAX_TOKENS_CUIDADOSO = 8192
#: Holgado a proposito: una respuesta cortada a medias es peor que una larga, y el
#: formulario lleva la respuesta ademas de los datos. `model_reply.usable_reply` ya descarta
#: las respuestas que se alargan de mas.
_MAX_TOKENS = 1024

#: Los estados HTTP que no son del contenido sino de la salud del proveedor.
_NO_DISPONIBLE = frozenset({401, 403, 500, 502, 503, 529})


class MessagesClient(Protocol):
    """Lo que el adaptador usa del cliente del SDK: `messages.create`. Las pruebas
    lo sustituyen por un doble con la misma forma."""

    @property
    def messages(self) -> Any: ...


class AnthropicTextGenerator(TextGenerator):
    """Genera con Claude para **un** uso, el que se le entrega: texto libre, o una
    salida que cumple un esquema cuando quien llama lo pasa."""

    def __init__(  # noqa: PLR0913 -- el cliente, su uso, su modelo, su techo, su contabilidad y su modo
        self,
        client: MessagesClient,
        *,
        use: Use,
        model: str,
        gate: SpendGate,
        usage: UsageSink,
        careful: bool = False,
    ) -> None:
        self._cliente = client
        # Sin razonamiento y con esfuerzo bajo para lo que va en el turno; con
        # razonamiento para lo que corre en el fondo y tiene que decidir con cuidado,
        # como la propuesta de citas (2026-10-08).
        self._cuidadoso = careful
        self._max_tokens = _MAX_TOKENS_CUIDADOSO if careful else _MAX_TOKENS
        self._uso = use
        self._modelo = model
        self._techo = gate
        self._contabilidad = usage

    async def generate(
        self, prompt: Prompt, *, schema: type[BaseModel] | None, use: Use
    ) -> GenerationResult:
        if use is not self._uso:
            msg = f"este adaptador atiende el uso '{self._uso.value}'; se le pidio '{use.value}'"
            raise ValueError(msg)
        await self._techo.ensure_open(provider=PROVIDER, use=use)

        unidades: tuple[UsageUnits, ...] = ()
        fuente = SpendSource.PROVIDER_REPORTED
        try:
            respuesta = await self._cliente.messages.create(
                model=self._modelo,
                max_tokens=self._max_tokens,
                thinking=_THINKING_CUIDADOSO if self._cuidadoso else _THINKING,
                output_config=_configuracion_de_salida(
                    schema, "high" if self._cuidadoso else "low"
                ),
                # Las instrucciones son fijas por uso e idioma: van en cache (2026-10-09).
                # En Haiku 5.5 se guarda desde 512 tokens y leerla cuesta la decima
                # parte; las de comprension rondan los 1 600 y se mandaban enteras en
                # cada mensaje.
                system=[
                    {
                        "type": "text",
                        "text": str(prompt.instruction.text),
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[
                    {
                        "role": "assistant" if parte.role == "model" else "user",
                        "content": parte.text,
                    }
                    for parte in prompt.parts
                ],
            )
            unidades = _unidades(respuesta)
        except anthropic.APIStatusError as error:
            raise self._traducir(error) from None
        except anthropic.APITimeoutError:
            raise self._error(ProviderErrorKind.TIMEOUT) from None
        except anthropic.APIConnectionError:
            raise self._error(ProviderErrorKind.UNAVAILABLE) from None
        finally:
            # Siempre, tambien si fallo: lo que el proveedor cobro se registra. Si
            # fallo sin decir cuanto consumio, se registra un tope contado aqui
            # (2026-10-08): una llamada sin valorar cierra todo lo que cuesta dinero
            # hasta que alguien la valore a mano, y un plazo vencido de centavos
            # no puede apagar la voz y el chat. El tope nunca cuenta de menos.
            if not unidades:
                unidades = _tope_contado(prompt, max_tokens=self._max_tokens)
                fuente = SpendSource.COUNTED_LOCALLY
            reporte = UsageReport(
                provider=PROVIDER,
                model=self._modelo,
                use=use,
                units=unidades,
                source=fuente,
            )
            await self._contabilidad.report(reporte)

        texto = "".join(
            bloque.text for bloque in respuesta.content if getattr(bloque, "type", "") == "text"
        ).strip()
        if respuesta.stop_reason != "end_turn" or not texto:
            raise self._error(ProviderErrorKind.INVALID_RESPONSE)
        interpretado: BaseModel | None = None
        if schema is not None:
            try:
                interpretado = schema.model_validate_json(texto)
            except ValidationError:
                raise self._error(ProviderErrorKind.INVALID_RESPONSE) from None
        return GenerationResult(
            text=texto, parsed=interpretado, usage=reporte, prompt=prompt.instruction.ref
        )

    def _error(self, kind: ProviderErrorKind) -> ProviderError:
        return ProviderError(kind, provider=PROVIDER, use=self._uso)

    def _traducir(self, error: anthropic.APIStatusError) -> Exception:
        """Un estado HTTP del proveedor, a uno de los cuatro tipos o a la parada."""
        if _es_saldo_agotado(error):
            return BudgetExhausted(
                ExhaustedResource.PROVIDER_QUOTA, provider=PROVIDER, use=self._uso
            )
        if error.status_code == 429:
            return self._error(ProviderErrorKind.RATE_LIMITED)
        if error.status_code in {408, 504}:
            return self._error(ProviderErrorKind.TIMEOUT)
        if error.status_code in _NO_DISPONIBLE:
            return self._error(ProviderErrorKind.UNAVAILABLE)
        return self._error(ProviderErrorKind.INVALID_RESPONSE)


def build_client(api_key: str, *, connect_timeout_ms: int, read_timeout_ms: int) -> MessagesClient:
    """El cliente del SDK con la clave de un uso. Solo lo llama la raiz de composicion.

    Sin reintentos: quien llama ya tiene su respaldo --la frase del catalogo-- y
    un reintento solo alargaria la espera de la persona.
    """
    tiempos = anthropic.Timeout(read_timeout_ms / 1000, connect=connect_timeout_ms / 1000)
    return anthropic.AsyncAnthropic(api_key=api_key, max_retries=0, timeout=tiempos)


def _configuracion_de_salida(schema: type[BaseModel] | None, effort: str) -> dict[str, Any]:
    """El esfuerzo bajo siempre; con esquema, ademas, el formato que el proveedor
    hace cumplir. `transform_schema` del SDK adapta el esquema de Pydantic a lo que
    la API acepta (objetos cerrados, sin las restricciones que no admite)."""
    if schema is None:
        return {"effort": effort}
    return {
        "effort": effort,
        "format": {"type": "json_schema", "schema": anthropic.transform_schema(schema)},
    }


def _tope_contado(prompt: Prompt, *, max_tokens: int) -> tuple[UsageUnits, ...]:
    """El maximo que pudo cobrar una llamada que no informo su consumo.

    Entrada: un token por cada dos caracteres enviados, que en espanol y en ingles
    es mas del doble de lo real. Salida: el maximo que la llamada permitia. Contar
    de mas es el lado seguro del techo; contar de menos, el que existe para impedir.
    """
    enviados = len(str(prompt.instruction.text)) + sum(len(parte.text) for parte in prompt.parts)
    return (
        UsageUnits(unit_kind=UnitKind.INPUT_TOKENS, units=Decimal(enviados // 2 + 1)),
        UsageUnits(unit_kind=UnitKind.OUTPUT_TOKENS, units=Decimal(max_tokens)),
    )


#: Lo que cuesta un token de cache frente a uno de entrada (precio de lista de
#: Anthropic, visto el 2026-10-09): escribirla con vida de 5 minutos, 1,25; leerla, 0,1.
_ESCRITURA_DE_CACHE = Decimal("1.25")
_LECTURA_DE_CACHE = Decimal("0.1")


def _unidades(respuesta: Any) -> tuple[UsageUnits, ...]:
    """Lo que la llamada consumio, en las unidades de la tabla de precios.

    Con cache, `input_tokens` es solo lo que no estaba en cache; lo escrito y lo
    leido llegan aparte. Se suman como entrada **equivalente** --cada uno por su
    factor de precio--, para que el libro mayor valore lo que cobra el proveedor sin
    dos clases de unidad nuevas. Redondeado hacia arriba: contar de mas es el lado
    seguro del techo.
    """
    uso = getattr(respuesta, "usage", None)
    if uso is None:
        return ()
    escritos = int(getattr(uso, "cache_creation_input_tokens", 0) or 0)
    leidos = int(getattr(uso, "cache_read_input_tokens", 0) or 0)
    entrada = (
        Decimal(int(uso.input_tokens))
        + Decimal(escritos) * _ESCRITURA_DE_CACHE
        + Decimal(leidos) * _LECTURA_DE_CACHE
    ).to_integral_value(rounding=ROUND_CEILING)
    return (
        UsageUnits(unit_kind=UnitKind.INPUT_TOKENS, units=entrada),
        UsageUnits(unit_kind=UnitKind.OUTPUT_TOKENS, units=Decimal(int(uso.output_tokens))),
    )


def _es_saldo_agotado(error: anthropic.APIStatusError) -> bool:
    """Si el rechazo dice que se acabo el saldo. Solo se lee el tipo del error.

    El saldo prepagado agotado es la parada que la regla del proyecto quiere: se
    detiene, se dice que se acabo y Miguel decide si recarga.
    """
    if error.status_code == 402:
        return True
    cuerpo: dict[str, Any] = error.body if isinstance(error.body, dict) else {}
    anidado = cuerpo.get("error")
    detalle: dict[str, Any] = anidado if isinstance(anidado, dict) else cuerpo
    tipo = str(detalle.get("type", ""))
    mensaje = str(detalle.get("message", "")).casefold()
    return tipo == "billing_error" or "credit balance" in mensaje


__all__ = ["PROVIDER", "AnthropicTextGenerator", "MessagesClient", "build_client"]
