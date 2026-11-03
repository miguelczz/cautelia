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

from collections.abc import Sequence
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
    ResearchResult,
    ResearchSource,
    SpendGate,
    TextGenerator,
    UsageReport,
    UsageSink,
    UsageUnits,
    WebResearcher,
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
        return _traducir_rechazo(error, self._uso)


def _traducir_rechazo(error: anthropic.APIStatusError, use: Use) -> Exception:
    """Un estado HTTP del proveedor, a uno de los cuatro tipos o a la parada.

    Una sola tabla para los dos puertos del adaptador --generar y investigar--: dos copias
    acabarian diciendo cosas distintas del mismo 429.
    """
    if _es_saldo_agotado(error):
        return BudgetExhausted(ExhaustedResource.PROVIDER_QUOTA, provider=PROVIDER, use=use)
    if error.status_code == 429:
        tipo = ProviderErrorKind.RATE_LIMITED
    elif error.status_code in {408, 504}:
        tipo = ProviderErrorKind.TIMEOUT
    elif error.status_code in _NO_DISPONIBLE:
        tipo = ProviderErrorKind.UNAVAILABLE
    else:
        tipo = ProviderErrorKind.INVALID_RESPONSE
    return ProviderError(tipo, provider=PROVIDER, use=use)


#: La herramienta de busqueda web del servidor, en su version mas reciente. Se llama de forma
#: **directa** (`allowed_callers`): la version con filtrado dinamico corre la busqueda desde
#: dentro de la ejecucion de codigo, que aqui no se usa ni se paga, y haria que las busquedas
#: salieran anidadas en la respuesta. Leido el 2026-11-03 en la documentacion de la herramienta.
_HERRAMIENTA_DE_BUSQUEDA = "web_search_20260318"
#: Holgado: la respuesta es un parrafo con su valor y sus fuentes, pero los resultados de la
#: busqueda entran como entrada y no cuentan aqui.
_MAX_TOKENS_INVESTIGACION = 2048
#: Las paradas de la investigacion que son una respuesta completa. `pause_turn` --el
#: servidor corto un turno largo-- no lo es: el texto que trae es el preambulo.
_PARADAS_COMPLETAS = frozenset({"end_turn", "stop_sequence"})


class AnthropicWebResearcher(WebResearcher):
    """Investiga con la herramienta de busqueda web del servidor de Anthropic.

    Hermana de `AnthropicTextGenerator` y con sus mismas reglas: instruccion separada del
    contenido, techo consultado antes de llamar, consumo registrado siempre --tokens **y
    busquedas**, que se cobran aparte--, errores traducidos a los cuatro tipos y ningun
    reintento. Lo que cambia es que la llamada es de texto con una herramienta del servidor y
    que lee de la respuesta las paginas en que se apoya.
    """

    def __init__(
        self,
        client: MessagesClient,
        *,
        use: Use,
        model: str,
        gate: SpendGate,
        usage: UsageSink,
    ) -> None:
        self._cliente = client
        self._uso = use
        self._modelo = model
        self._techo = gate
        self._contabilidad = usage

    async def research(
        self,
        prompt: Prompt,
        *,
        use: Use,
        max_searches: int,
        allowed_domains: Sequence[str],
    ) -> ResearchResult:
        if use is not self._uso:
            msg = f"este adaptador atiende el uso '{self._uso.value}'; se le pidio '{use.value}'"
            raise ValueError(msg)
        if max_searches < 1:
            msg = "una investigacion con busqueda web admite al menos una busqueda"
            raise ValueError(msg)
        if not allowed_domains:
            msg = (
                "la busqueda web necesita sus dominios permitidos: sin ellos es abierta, y abrirla "
                "se decide en la configuracion"
            )
            raise ValueError(msg)
        await self._techo.ensure_open(provider=PROVIDER, use=use)

        unidades: tuple[UsageUnits, ...] = ()
        fuente = SpendSource.PROVIDER_REPORTED
        try:
            respuesta = await self._cliente.messages.create(
                model=self._modelo,
                max_tokens=_MAX_TOKENS_INVESTIGACION,
                thinking=_THINKING,
                output_config={"effort": "low"},
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
                tools=[
                    {
                        "type": _HERRAMIENTA_DE_BUSQUEDA,
                        "name": "web_search",
                        "max_uses": max_searches,
                        "allowed_domains": list(allowed_domains),
                        "allowed_callers": ["direct"],
                    }
                ],
            )
            unidades = (*_unidades(respuesta), *_unidades_de_busqueda(respuesta))
        except anthropic.APIStatusError as error:
            raise _traducir_rechazo(error, self._uso) from None
        except anthropic.APITimeoutError:
            raise self._error(ProviderErrorKind.TIMEOUT) from None
        except anthropic.APIConnectionError:
            raise self._error(ProviderErrorKind.UNAVAILABLE) from None
        finally:
            # Como en la generacion: siempre, y sin consumo informado se registra el tope
            # contado, que aqui incluye **todas las busquedas que la llamada admitia**.
            if not unidades:
                unidades = (
                    *_tope_contado(prompt, max_tokens=_MAX_TOKENS_INVESTIGACION),
                    UsageUnits(unit_kind=UnitKind.WEB_SEARCHES, units=Decimal(max_searches)),
                )
                fuente = SpendSource.COUNTED_LOCALLY
            await self._contabilidad.report(
                UsageReport(
                    provider=PROVIDER,
                    model=self._modelo,
                    use=use,
                    units=unidades,
                    source=fuente,
                )
            )

        texto = _texto_de(respuesta)
        if respuesta.stop_reason not in _PARADAS_COMPLETAS or not texto:
            raise self._error(ProviderErrorKind.INVALID_RESPONSE)
        return ResearchResult(
            text=texto,
            sources=_fuentes_de(respuesta),
            searches_used=_busquedas_de(respuesta),
        )

    def _error(self, kind: ProviderErrorKind) -> ProviderError:
        return ProviderError(kind, provider=PROVIDER, use=self._uso)


def _texto_de(respuesta: Any) -> str:
    """El texto de la respuesta: lo que el modelo escribio **despues** de su ultima busqueda.

    Antes de buscar el modelo narra lo que va a hacer ("voy a buscar...") y esa frase no es parte
    del hallazgo; en una respuesta sin busquedas el texto es todo. Los bloques de texto de una
    respuesta con citas son trozos de una misma frase, asi que se unen sin separador.
    """
    bloques = list(respuesta.content)
    ultima = max(
        (i for i, b in enumerate(bloques) if getattr(b, "type", "") == "web_search_tool_result"),
        default=-1,
    )
    return "".join(
        b.text for b in bloques[ultima + 1 :] if getattr(b, "type", "") == "text"
    ).strip()


def _busquedas_de(respuesta: Any) -> int:
    """Cuantas busquedas hizo el servidor, segun su propio recuento de uso."""
    uso = getattr(respuesta, "usage", None)
    del_servidor = getattr(uso, "server_tool_use", None)
    return int(getattr(del_servidor, "web_search_requests", 0) or 0)


def _unidades_de_busqueda(respuesta: Any) -> tuple[UsageUnits, ...]:
    """Las busquedas como unidad cobrable. Ninguna busqueda no deja fila: cero no es consumo."""
    hechas = _busquedas_de(respuesta)
    if hechas == 0:
        return ()
    return (UsageUnits(unit_kind=UnitKind.WEB_SEARCHES, units=Decimal(hechas)),)


def _fuentes_de(respuesta: Any) -> tuple[ResearchSource, ...]:
    """Las paginas que respaldan el texto: las que cita, o todas las que trajo la busqueda.

    Una busqueda que fallo trae un objeto de error en vez de una lista (`max_uses_exceeded`,
    `unavailable`...): no aporta paginas y no es un error de la llamada.
    """
    traidas: dict[str, ResearchSource] = {}
    citadas: list[str] = []
    for bloque in respuesta.content:
        tipo = getattr(bloque, "type", "")
        if tipo == "web_search_tool_result" and isinstance(bloque.content, list):
            for resultado in bloque.content:
                url = str(getattr(resultado, "url", "") or "")
                if url and url not in traidas:
                    traidas[url] = ResearchSource(
                        url=url,
                        title=str(getattr(resultado, "title", "") or ""),
                        page_age=getattr(resultado, "page_age", None),
                    )
        elif tipo == "text":
            for cita in getattr(bloque, "citations", None) or ():
                url = str(getattr(cita, "url", "") or "")
                if not url:
                    continue
                if url not in traidas:
                    traidas[url] = ResearchSource(
                        url=url, title=str(getattr(cita, "title", "") or "")
                    )
                if url not in citadas:
                    citadas.append(url)
    elegidas = citadas or list(traidas)
    return tuple(traidas[url] for url in elegidas)


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


__all__ = [
    "PROVIDER",
    "AnthropicTextGenerator",
    "AnthropicWebResearcher",
    "MessagesClient",
    "build_client",
]
