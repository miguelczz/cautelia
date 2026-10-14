"""El transporte de verdad: el unico sitio del aplicativo que habla por la red.

Cierra lo que el bloque E dejo abierto. `providers/transport.py` declara la
forma de la frontera --una peticion con su ruta, su cuerpo y sus dos tiempos
maximos-- y este archivo la implementa contra la API REST de Gemini, dentro del
paquete del adaptador, que es el unico sitio donde se puede importar un cliente
del proveedor (BR1.2, convencion 5b del equipo).

## Por que un cliente HTTP y no el SDK del proveedor

`nfr-requirements/tech-stack-decisions.md` inscribio `google-genai` como
dependencia de runtime. **No se instala, y la razon es de forma, no de gusto.**

El bloque E construyo la frontera contra la API REST: `ProviderRequest` lleva
`models/<id>:generateContent` y un cuerpo con `systemInstruction` separado de
`contents`, y `request.py` lee `candidates` y `usageMetadata` de la respuesta.
El SDK no tiene esa forma --recibe modelo, contenidos y configuracion, y
devuelve sus propios objetos--, asi que usarlo obligaria a rehacer la peticion,
la lectura y la traduccion de errores que ya estan escritas y revisadas. Y
usarlo **sin** eso seria instalar una dependencia de runtime que nadie ejecuta,
que es justo lo que la regla del equipo no permite: una dependencia nueva se
justifica por lo que hace, y una que no se llama no hace nada.

Lo que entra en su lugar no es un paquete nuevo: `httpx2` ya estaba en el arbol
como dependencia de desarrollo --el cliente de prueba de FastAPI lo exige-- y
pasa al juego de runtime con su razon. Un cliente HTTP menos en el arbol es
tambien una superficie menos que auditar.

**Lo que esto cuesta, dicho.** Sin el SDK no hay reintentos ni paginacion suyos,
y el dia que la API cambie de forma hay que verlo y escribirlo aqui. Los
reintentos no se pierden: no son de este adaptador (BR2.4), son la politica de
fallo del nodo que aplica el ejecutor comun de U12.

## La clave entra y no sale

Entra en `create(api_key=..., use=...)` y se queda **dentro del cliente**, en su
cabecera. No se guarda en ningun atributo propio, ningun metodo la devuelve y
`__repr__` no la imprime: nombra el uso y nada mas. Es la capa 2 del diseno de
seguridad escrita como codigo y no como cuidado.

La credencial viaja en cabecera y **nunca en la URL**, porque una URL acaba en
un registro de acceso, en un mensaje de error y en una traza.

## Un cliente por uso, con su tiempo maximo por peticion

La fabrica de `providers/factory.py` llama a `create` una vez por uso, asi que
cada uso tiene su propia agrupacion de conexiones y su propia clave, en su
propio proyecto del proveedor (ADR-018). Los dos tiempos maximos no van en el
cliente sino en **cada peticion**, porque el mismo cliente sirve peticiones de
un solo uso pero la frontera los declara por peticion y es el adaptador quien
los resuelve desde la configuracion versionada.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx2

from untangle.base import Use
from untangle.providers.transport import (
    ProviderRequest,
    ProviderResponse,
    Transport,
    TransportError,
)

__all__ = ["GEMINI_BASE_URL", "GeminiTransportFactory"]

#: La raiz de la API REST de Gemini. Vive aqui, en el adaptador, y no en
#: configuracion versionada: no es un ajuste del proyecto sino la forma de la API
#: de este proveedor, y cambiarla es cambiar de adaptador.
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/"

#: La cabecera con la que Gemini recibe la credencial.
_CABECERA_DE_CLAVE = "x-goog-api-key"


class _HttpTransport:
    """Un cliente ya construido, con su credencial dentro y sin forma de sacarla."""

    def __init__(
        self,
        *,
        api_key: str,
        use: Use,
        base_url: str,
        network: httpx2.AsyncBaseTransport | None = None,
    ) -> None:
        self._use = use
        # La clave entra aqui y se queda en las cabeceras del cliente. **No se
        # guarda como atributo propio**: lo que no existe no se puede imprimir.
        self._cliente = httpx2.AsyncClient(
            base_url=base_url,
            headers={_CABECERA_DE_CLAVE: api_key},
            transport=network,
        )

    def __repr__(self) -> str:
        """Nombra el uso. Nunca la clave, ni el cliente que la lleva dentro."""
        return f"_HttpTransport(use={self._use.value})"

    async def send(self, request: ProviderRequest) -> ProviderResponse:
        """Manda la peticion y devuelve lo que contesto, ya decodificado.

        La **unica** excepcion que deja salir es `TransportError`, y solo cuando
        no hubo respuesta que leer. Una respuesta con codigo de error no es un
        fallo de transporte: la traduce `errors.raise_for_response`, que es el
        unico sitio que convierte un codigo en uno de los cuatro tipos.
        """
        tiempos = httpx2.Timeout(
            connect=request.connect_timeout_ms / 1000,
            read=request.read_timeout_ms / 1000,
            write=request.read_timeout_ms / 1000,
            pool=request.connect_timeout_ms / 1000,
        )
        try:
            respuesta = await self._cliente.post(
                request.path, json=dict(request.body), timeout=tiempos
            )
        except httpx2.TimeoutException as fallo:
            # Se agoto la espera. El tipo del fallo **no cruza**: lo que sale es
            # la marca, y el adaptador la traduce a `timeout` (BR2.2).
            raise TransportError(type(fallo).__name__, timed_out=True) from None
        except httpx2.HTTPError as fallo:
            # No hubo con quien hablar: DNS, conexion rechazada, TLS. Desde el
            # nodo es indistinguible de un proveedor caido.
            raise TransportError(type(fallo).__name__, timed_out=False) from None

        return ProviderResponse(status_code=respuesta.status_code, body=_cuerpo(respuesta))

    async def aclose(self) -> None:
        await self._cliente.aclose()


def _cuerpo(respuesta: httpx2.Response) -> Mapping[str, object]:
    """El cuerpo como mapa, o vacio si no lo es.

    Un cuerpo que no se puede decodificar **no es un fallo de transporte**: el
    proveedor contesto, solo que no lo que el contrato dice. Devolverlo vacio lo
    convierte en `invalid_response` en el unico sitio que traduce respuestas, en
    vez de abrir aqui un segundo camino de traduccion que un dia diria otra cosa.

    Y no se mira ni se registra que venia: el cuerpo lleva la respuesta del
    modelo, y la respuesta del modelo lleva lo que el asegurado escribio.
    """
    try:
        cargado: Any = respuesta.json()
    except ValueError:
        return {}
    if not isinstance(cargado, dict):
        return {}
    return cargado


class GeminiTransportFactory:
    """Construye un transporte por uso. **Solo `ProviderClients` la llama.**

    Implementa `transport.TransportFactory`. No se declara heredando del
    `Protocol` a proposito: la conformidad la comprueba el comprobador de tipos
    en el sitio donde se inyecta, que es donde importa.

    Guarda los transportes creados para poder cerrarlos al apagar el proceso. Es
    lo unico que guarda: no ve ninguna clave despues de pasarla.
    """

    def __init__(
        self,
        *,
        base_url: str = GEMINI_BASE_URL,
        network: httpx2.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url
        # Por donde salen las peticiones de verdad. `None` es la pila de red del
        # cliente; las pruebas inyectan aqui la del propio cliente HTTP, que
        # responde sin tocar la red y **sin clave**. Es una costura de prueba
        # declarada, no una via alternativa: lo que cambia es quien contesta, no
        # como se arma la peticion ni por donde viaja la credencial.
        self._network = network
        self._creados: list[_HttpTransport] = []

    def create(self, *, api_key: str, use: Use) -> Transport:
        transporte = _HttpTransport(
            api_key=api_key, use=use, base_url=self._base_url, network=self._network
        )
        self._creados.append(transporte)
        return transporte

    async def aclose(self) -> None:
        """Cierra los clientes al apagar. La raiz de composicion, en su cierre."""
        for transporte in self._creados:
            await transporte.aclose()
        self._creados.clear()
