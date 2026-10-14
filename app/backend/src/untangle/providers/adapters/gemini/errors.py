"""De lo que contesta Gemini a los cuatro tipos, o a la senal de parada.

Es la frontera entera en un archivo: **ningun tipo del proveedor la cruza**
(BR2.2), y de este lado solo salen `ProviderError` con uno de cuatro valores o
`BudgetExhausted`, que no es ninguno de ellos (BR2.1, BR2.3).

## Lo que estas funciones nunca hacen

**No meten el cuerpo de la respuesta en el mensaje del error.** Ni entero ni
recortado. El cuerpo lleva la respuesta del modelo, y la respuesta del modelo
lleva lo que el asegurado escribio. Un mensaje de error que lo arrastrara
convertiria el camino de fallo en el punto de fuga que esta unidad evita, y los
mensajes de error acaban en logs, en trazas y en pantallas.

Por la misma razon el error de validacion se levanta **`from None`**: encadenarlo
dejaria el `ValidationError` original colgando del nuevo, y ese trae dentro el
valor que no valido. Cualquiera que registre la traza completa --que es lo
normal-- imprimiria la respuesta del modelo entera sin haberlo decidido.

## El 429 ambiguo, dicho antes de que muerda

Gemini contesta **429 tanto por limite de ritmo como por cuota agotada**, y de la
diferencia depende algo grande: `rate_limited` deja que el nodo reintente, y
`BudgetExhausted` detiene el trabajo hasta que una persona decida. Lo que
distingue a los dos esta en el cuerpo: `error.status` y los `reason` de
`error.details`.

La lista de razones de abajo esta **versionada aqui** y el valor por omision de
un 429 es `rate_limited`, que es el lado seguro de equivocarse: tratar un limite
de ritmo pasajero como "se acabo el dinero" detendria una demostracion viva por
nada, mientras que lo contrario solo produce reintentos que no cuestan --no hay
cuota que gastar-- y cinco seguidos abren el circuito de todas formas.

**Esto es una suposicion hasta que haya una respuesta real grabada.** La prueba
de contrato contra el proveedor de verdad, que corre por hito (BR1.6), es la que
la confirma o la corrige.
"""

from __future__ import annotations

from collections.abc import Mapping

from untangle.base import ProviderName, Use
from untangle.providers.ports import (
    BudgetExhausted,
    ExhaustedResource,
    ProviderError,
    ProviderErrorKind,
)
from untangle.providers.transport import ProviderResponse, TransportError

__all__ = ["PROVIDER", "kind_for_status", "raise_for_response", "translate_transport_failure"]

#: El proveedor de este adaptador. Un solo sitio lo nombra.
PROVIDER = ProviderName.GEMINI

#: Que codigo de estado es que tipo. Lo que **no** esta aqui cae en
#: `invalid_response`: un codigo que no reconocemos no es una razon para declarar
#: caido a un proveedor que acaba de contestar.
_POR_CODIGO: dict[int, ProviderErrorKind] = {
    # El proveedor tardo mas de lo que el intermediario aguanta. Es el mismo
    # hecho que un tiempo agotado de nuestro lado, visto desde el otro.
    408: ProviderErrorKind.TIMEOUT,
    504: ProviderErrorKind.TIMEOUT,
    # No nos sirve. Desde el nodo es indistinguible de caido, y la lista cerrada
    # de cuatro no tiene un valor para "mal configurado": ampliarla seria
    # cambiar un conjunto cerrado que comparte con el atributo de la traza.
    401: ProviderErrorKind.UNAVAILABLE,
    403: ProviderErrorKind.UNAVAILABLE,
    500: ProviderErrorKind.UNAVAILABLE,
    502: ProviderErrorKind.UNAVAILABLE,
    503: ProviderErrorKind.UNAVAILABLE,
    429: ProviderErrorKind.RATE_LIMITED,
}

#: Las razones que significan "se acabo", versionadas aqui. Se comparan sin
#: distinguir mayusculas contra `error.status` y contra cada `reason` de
#: `error.details`.
_RAZONES_DE_AGOTAMIENTO: frozenset[str] = frozenset(
    {
        "billing_disabled",
        "account_state_invalid",
        "quota_exceeded",
        "insufficient_quota",
        "credit_exhausted",
        "out_of_credits",
    }
)

#: Un 402 es "paga": no hace falta mirar el cuerpo.
_CODIGO_DE_PAGO = 402


def kind_for_status(status_code: int) -> ProviderErrorKind:
    """El tipo de un codigo de estado, sin mirar el cuerpo."""
    return _POR_CODIGO.get(status_code, ProviderErrorKind.INVALID_RESPONSE)


def translate_transport_failure(
    failure: TransportError, *, use: Use, attempt: int
) -> ProviderError:
    """Un fallo de conexion, traducido. No hubo respuesta que leer."""
    kind = ProviderErrorKind.TIMEOUT if failure.timed_out else ProviderErrorKind.UNAVAILABLE
    return ProviderError(kind, provider=PROVIDER, use=use, attempt=attempt)


def raise_for_response(response: ProviderResponse, *, use: Use, attempt: int) -> None:
    """Levanta lo que corresponda si la respuesta no es un exito.

    Sale por aqui o no sale: es el unico sitio del adaptador que convierte un
    codigo de estado en un error.
    """
    if 200 <= response.status_code < 300:
        return

    if _dice_que_se_acabo(response):
        raise BudgetExhausted(ExhaustedResource.PROVIDER_QUOTA, provider=PROVIDER, use=use)

    raise ProviderError(
        kind_for_status(response.status_code),
        provider=PROVIDER,
        use=use,
        attempt=attempt,
    )


def _dice_que_se_acabo(response: ProviderResponse) -> bool:
    """Si el cuerpo nombra una razon de agotamiento, o el codigo es 402."""
    if response.status_code == _CODIGO_DE_PAGO:
        return True

    error = response.body.get("error")
    if not isinstance(error, Mapping):
        return False

    for razon in _razones(error):
        if razon.strip().lower() in _RAZONES_DE_AGOTAMIENTO:
            return True
    return False


def _razones(error: Mapping[str, object]) -> list[str]:
    """`error.status` y cada `error.details[].reason`, como texto.

    Solo se leen esas dos claves. El `message` **no** se mira: lo escribe el
    proveedor en prosa, puede cambiar sin aviso y es el sitio donde una
    coincidencia casual con una de las razones decidiria detener el trabajo.
    """
    encontradas: list[str] = []
    estado = error.get("status")
    if isinstance(estado, str):
        encontradas.append(estado)

    detalles = error.get("details")
    if isinstance(detalles, list):
        for detalle in detalles:
            if isinstance(detalle, Mapping):
                razon = detalle.get("reason")
                if isinstance(razon, str):
                    encontradas.append(razon)
    return encontradas
