"""Como sale una peticion hacia un proveedor, sin decir con que biblioteca.

Tres protocolos y dos valores. Existen para que la fabrica pueda construir **un
cliente por uso con su clave** sin importar el adaptador, y para que el adaptador
pueda hablar con el proveedor sin tener la clave nunca en la mano.

## Por que hay una pieza en medio y no una llamada directa

El contrato de importacion `raiz-de-composicion` dice que **solo
`untangle.server` importa `untangle.providers.adapters`**. Asi que la fabrica no
puede construir el adaptador, y el adaptador no puede construir su cliente: los
junta la raiz de composicion. Lo que los dos comparten es esto, que no es ni una
cosa ni la otra.

## Lo que esto compra en seguridad

La clave entra en `TransportFactory.create` y **no sale**: el `Transport` que
devuelve la lleva dentro, no la expone, y su representacion no la imprime. El
adaptador recibe un `ProviderCaller` --"dame el cliente de este uso y manda
esto"-- y por tanto no tiene ni argumento ni atributo donde una clave pueda
estar. Es la capa 2 del diseno de seguridad escrita como tipos.

## Ninguna biblioteca de red aqui dentro

La implementacion concreta --la que habla HTTP de verdad-- vive **dentro del
adaptador**, en `adapters/gemini/transport.py`, que es el unico sitio donde se
puede importar un cliente de proveedor (BR1.2). Este archivo declara la forma de
la frontera y no la cruza: un contrato de importacion comprueba que no llegue
aqui ningun cliente de red, porque un `httpx` en este archivo seria la misma
fuga con otro nombre y un nodo dejaria de poder probarse con un doble.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from pydantic import Field

from untangle.base import Frozen, Use

__all__ = [
    "CallTimeouts",
    "ProviderCaller",
    "ProviderRequest",
    "ProviderResponse",
    "Transport",
    "TransportError",
    "TransportFactory",
]


class CallTimeouts(Frozen):
    """Los dos tiempos maximos hacia el proveedor, **por uso**.

    Por uso y no globales porque los usos tienen paciencias distintas: el turno
    de voz no puede esperar lo que una corrida de evaluaciones si
    (`nfr-design/performance-design.md`).

    **De donde salen los numeros, y por que hoy no salen de ahi.** Ese mismo
    documento dice que se declaran en configuracion versionada, y
    `app/config/providers/providers.yaml` **no tiene todavia esos dos campos**:
    ningun documento aprobado fija sus valores. Asi que el adaptador los recibe
    construido, la raiz de composicion tendra que decidirlos a la vista, y aqui
    no queda ningun numero inventado escondido en un valor por defecto.
    """

    connect_timeout_ms: int = Field(ge=1)
    read_timeout_ms: int = Field(ge=1)


class ProviderRequest(Frozen):
    """Una peticion al proveedor, ya armada por su adaptador.

    El cuerpo llega armado desde el adaptador y este modulo no lo mira: es lo que
    permite que la frontera no sepa nada de la forma de ningun proveedor.
    """

    #: La ruta relativa al servidor del proveedor. Sin clave y sin parametros de
    #: consulta: la credencial viaja en cabecera, nunca en la URL, porque una URL
    #: acaba en un registro de acceso, en un mensaje de error y en una traza.
    path: str
    body: Mapping[str, object]
    #: Los dos tiempos maximos, declarados **por uso** (performance-design). El
    #: adaptador los recibe; este modulo solo los transporta.
    connect_timeout_ms: int
    read_timeout_ms: int


class ProviderResponse(Frozen):
    """Lo que el proveedor contesto, ya decodificado como mapa.

    No lleva las cabeceras de la peticion, y eso es deliberado: la cabecera de
    autorizacion es lo unico que no puede aparecer en ningun sitio, y la forma de
    garantizarlo es que el tipo del retorno no tenga donde ponerla.
    """

    status_code: int
    body: Mapping[str, object]


class TransportError(Exception):
    """La peticion no llego a tener respuesta: se agoto el tiempo o no hubo con quien.

    Es la **unica** excepcion que el transporte deja salir, y la traduce su
    adaptador a uno de los cuatro tipos. Se distingue de una respuesta con codigo
    de error porque no hay cuerpo que leer: lo que fallo es la conexion, no lo que
    el proveedor contesto.
    """

    def __init__(self, reason: str, *, timed_out: bool) -> None:
        self.reason = reason
        self.timed_out = timed_out
        super().__init__(reason)


class Transport(Protocol):
    """Un cliente ya construido, con su credencial dentro y sin forma de sacarla."""

    async def send(self, request: ProviderRequest) -> ProviderResponse: ...


class TransportFactory(Protocol):
    """Construye un transporte con una clave. **Solo la fabrica lo llama.**

    Recibe el uso ademas de la clave porque el proveedor limita por proyecto y
    quien mira una traza de red tiene que poder saber de que uso salio la
    llamada sin abrir el codigo.
    """

    def create(self, *, api_key: str, use: Use) -> Transport: ...


class ProviderCaller(Protocol):
    """ "Manda esto por el cliente de este uso". Lo implementa la fabrica.

    Es lo que recibe el adaptador. No tiene metodo para obtener el cliente ni la
    clave: el objeto del cliente no sale de la fabrica, asi que no hay donde
    imprimirlo.
    """

    async def send(self, request: ProviderRequest, *, use: Use) -> ProviderResponse: ...
