"""Los atributos que Langfuse lee, derivados de lo que un tramo ya lleva.

Langfuse recibe OTLP y entiende, ademas de los nombres de OpenTelemetry, unos
propios (`langfuse.session.id`, `langfuse.observation.type`, el costo...). Esos
nombres no estan en la lista cerrada de `api.SpanAttributes` y **no se anaden a
ella**: la lista es el diseno de lo que un tramo puede decir, y esto es solo como
Langfuse lo lee. Aqui se **derivan**, al serializar para Langfuse, de lo que el
tramo ya trae; ningun valor nace aqui.

## La regla que esto cumple

Todo valor de abajo sale de un campo del tramo --un atributo de la lista cerrada,
su nombre, su nivel, su aseguradora o su identificador--, que son enums, numeros
e identificadores. No hay texto libre en ninguna entrada, asi que lo que la
derivacion produce tampoco lo tiene. Y como esto ocurre **antes** de redactar, lo
derivado pasa por el mismo punto unico de salida que el resto del lote.

## Por que los identificadores de tramo se acortan

El tramo del proyecto se identifica con 32 cifras (`api._identificador_nuevo`), la
longitud del identificador de una traza. OTLP manda ocho bytes para el
identificador de un tramo, es decir 16 cifras, y Langfuse los lee como tales. El
corte es determinista y se aplica igual al tramo y al `parentSpanId` de sus hijos,
asi que el arbol sigue siendo el mismo. Se hace solo en la forma de Langfuse: el
archivo de la corrida conserva las 32.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation

from untangle.telemetry.spend.models import CostStatus
from untangle.telemetry.traces.api import FinishedSpan
from untangle.telemetry.traces.models import SpanLevel

#: Lo que un atributo puede valer en el cable de Langfuse: texto, entero, booleano o
#: una lista de textos (las etiquetas de la traza).
type AttributeValue = str | int | bool | tuple[str, ...]

#: Las claves que `derive` puede escribir, y ninguna otra. Existe porque la redaccion
#: lee el lote como texto: la raiz de composicion las pasa a la lista de nombres
#: publicos para que no se confundan con nombres de personas, y una prueba comprueba
#: que `derive` no escribe ninguna que no este aqui.
DERIVED_KEYS: frozenset[str] = frozenset(
    {
        "langfuse.session.id",
        "langfuse.trace.name",
        "langfuse.trace.public",
        "langfuse.trace.tags",
        "langfuse.trace.metadata.tenant_id",
        "langfuse.observation.type",
        "langfuse.observation.usage_details",
        "langfuse.observation.cost_details",
        "langfuse.observation.metadata.tenant_id",
        "langfuse.observation.metadata.node",
        "langfuse.observation.metadata.attempt",
    }
)

#: Cuantos digitos hexadecimales tiene el identificador de un tramo en OTLP.
_SPAN_ID_HEX_DIGITS = 16


def wire_span_id(span_id: str, attempt: int = 0) -> str:
    """El identificador de tramo en la longitud que OTLP manda (ocho bytes).

    En el primer intento es el principio del identificador del tramo. Si la redaccion
    estropeo alguno --el modelo de nombres toma por persona alguna cadena de cifras, y
    lo hace por cadena concreta--, el exportador vuelve a armar el lote con `attempt` mayor y
    cada tramo recibe otro identificador de 16 cifras, derivado del suyo. Un tramo no
    significa nada fuera del lote: lo unico que importa es que el padre y los hijos usen
    el mismo en el mismo intento, y lo hacen porque la derivacion es una funcion.
    """
    if attempt == 0:
        return span_id[:_SPAN_ID_HEX_DIGITS]
    resumen = hashlib.sha256(f"{attempt}:{span_id}".encode()).digest()
    return f"{int.from_bytes(resumen[:8], 'big') % 10**_SPAN_ID_HEX_DIGITS:0{_SPAN_ID_HEX_DIGITS}d}"


def _texto(span: FinishedSpan, clave: str) -> str | None:
    valor = span.attributes.get(clave)
    return valor if isinstance(valor, str) else None


def _entero(span: FinishedSpan, clave: str) -> int | None:
    valor = span.attributes.get(clave)
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None


def _costo_en_texto(span: FinishedSpan) -> str | None:
    """El costo como JSON de Langfuse, **solo si se midio**.

    Un costo no medido no se escribe como cero: seria una cifra falsa que despues
    alguien suma, que es lo que `Money` prohibe en todo el aplicativo. El numero se
    escribe desde el decimal en texto y no desde un flotante, para que lo que
    Langfuse muestra sea exactamente lo que el libro de gasto dice.
    """
    if _texto(span, "untangle.cost_status") != CostStatus.MEASURED.value:
        return None
    crudo = _texto(span, "untangle.cost_usd")
    if crudo is None:
        return None
    try:
        monto = Decimal(crudo)
    except InvalidOperation:
        return None
    if not monto.is_finite():
        return None
    return '{"total": ' + format(monto, "f") + "}"


def _de_la_traza(span: FinishedSpan) -> dict[str, AttributeValue]:
    """Lo que solo dice un tramo raiz: visibilidad, aseguradora y, si es el turno, nombre y etiqueta."""
    atributos: dict[str, AttributeValue] = {
        "langfuse.trace.metadata.tenant_id": span.tenant_id,
        # Visible sin cuenta por su direccion: es lo que deja a quien abre su caso
        # ver como trabajo la agente sin tener que entrar a Langfuse. La direccion
        # lleva el identificador de la traza, que son 32 cifras al azar y no se adivina.
        "langfuse.trace.public": True,
    }
    # El nombre y las etiquetas los pone el tramo del turno. Los dos momentos del
    # caso tambien son raices, pero comparten la traza del turno y no la renombran.
    if span.level is SpanLevel.TURN:
        atributos["langfuse.trace.name"] = span.name
        uso = _texto(span, "untangle.use")
        if uso is not None:
            atributos["langfuse.trace.tags"] = (uso,)
    return atributos


def _de_la_generacion(span: FinishedSpan) -> dict[str, AttributeValue]:
    """Lo que hace de una llamada con modelo una generacion de Langfuse: tipo, tokens y costo."""
    atributos: dict[str, AttributeValue] = {"langfuse.observation.type": "generation"}

    uso_de_tokens: dict[str, int] = {}
    entrada = _entero(span, "gen_ai.usage.input_tokens")
    salida = _entero(span, "gen_ai.usage.output_tokens")
    if entrada is not None:
        uso_de_tokens["input"] = entrada
    if salida is not None:
        uso_de_tokens["output"] = salida
    if uso_de_tokens:
        atributos["langfuse.observation.usage_details"] = json.dumps(uso_de_tokens, sort_keys=True)

    costo = _costo_en_texto(span)
    if costo is not None:
        atributos["langfuse.observation.cost_details"] = costo
    return atributos


def derive(span: FinishedSpan) -> dict[str, AttributeValue]:
    """Los atributos de Langfuse que se pueden decir de este tramo, y solo esos."""
    atributos: dict[str, AttributeValue] = {}

    caso = _texto(span, "untangle.case_id")
    if caso is not None:
        atributos["langfuse.session.id"] = caso

    # La aseguradora es dato de direccion del tramo, no un atributo. Va como
    # metadato de cada observacion --para poder filtrar por ella--.
    atributos["langfuse.observation.metadata.tenant_id"] = span.tenant_id

    if span.parent_span_id is None:
        atributos.update(_de_la_traza(span))

    nodo = _texto(span, "untangle.node")
    if nodo is not None:
        atributos["langfuse.observation.metadata.node"] = nodo

    intento = _entero(span, "untangle.attempt")
    if intento is not None:
        atributos["langfuse.observation.metadata.attempt"] = str(intento)

    # Una llamada con modelo es una generacion de Langfuse: es lo que le hace
    # mostrar el modelo, los tokens y el costo en su columna propia.
    if span.level is SpanLevel.CALL and _texto(span, "gen_ai.request.model") is not None:
        atributos.update(_de_la_generacion(span))

    return atributos


__all__ = ["DERIVED_KEYS", "AttributeValue", "derive", "wire_span_id"]
