"""El unico sitio que construye un cliente de proveedor (BR1.3, capa 2 de seguridad).

Un cliente por uso --voz, chat, evaluaciones y operacion--, cada uno con **su
clave** y en **su proyecto** del proveedor. No es ceremonia: Gemini limita por
proyecto y no por clave (ADR-018, enmienda del 2026-09-17), asi que una cuota
agotada en el chat no debe poder apagar la voz.

## El cliente no sale de aqui

`_Client` es privado y ningun metodo lo devuelve. Lo que esta fabrica ofrece al
adaptador es `send(request, use=...)`: "manda esto por el cliente de este uso".
Asi no hay ningun sitio, dentro ni fuera de este archivo, donde alguien pueda
tener el objeto del cliente y por tanto no hay donde imprimirlo. La clave entra
en `TransportFactory.create` y se queda dentro del transporte; esta clase no la
guarda ni la vuelve a leer.

## Por que la fabrica no construye el adaptador

Porque el contrato `raiz-de-composicion` dice que solo `untangle.server` importa
`untangle.providers.adapters`. La raiz junta las dos piezas: pide el transporte
concreto al paquete del adaptador --que es el unico que puede importar el SDK--,
se lo pasa a esta fabrica, y le pasa esta fabrica al adaptador.

## Que pasa cuando falta una clave

No se inventa ninguna y no se cae a la de otro uso, que seria exactamente lo que
las claves separadas existen para impedir. El uso queda sin cliente y pedirlo
falla nombrando **la variable de entorno** que hay que definir.

Falla al pedirlo y no al arrancar porque hay un camino que llega hasta el
reporte sin ninguna clave --`mise run bootstrap`, la cifra de NFR21--, y hacerlo
fallar al construir la fabrica cerraria ese camino. Lo que si falla al arrancar
es `require(...)`: la raiz de composicion nombra los usos que **ese** proceso
necesita y los exige antes de construir nada mas, con la cuota intacta y sin la
mitad de los casos ya ejecutados.
"""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass

from untangle.base import ProviderName, Use
from untangle.providers.config import ProvidersConfig
from untangle.providers.speech_wire import (
    ByteStream,
    DuplexChannel,
    SpeechRequest,
    SpeechTransport,
    SpeechTransportFactory,
)
from untangle.providers.transport import (
    ProviderRequest,
    ProviderResponse,
    Transport,
    TransportFactory,
)
from untangle.settings import (
    VOICE_CARTESIA_API_KEY_VAR,
    VOICE_DEEPGRAM_API_KEY_VAR,
    Settings,
)

__all__ = [
    "MissingProviderKeyError",
    "ProviderClients",
    "SpeechClients",
    "env_var_for",
    "speech_env_var_for",
]

#: El nombre de la variable de entorno de cada uso. Una por uso, y el mapa esta
#: aqui entero para que se lea de un vistazo cual alimenta a cual: repartido por
#: el codigo, la respuesta a "de donde sale la clave del chat" seria un grep.
_VARIABLE_POR_USO: dict[Use, str] = {
    Use.VOICE: "UNTANGLE_VOICE_MODEL_API_KEY",
    Use.CHAT: "UNTANGLE_CHAT_MODEL_API_KEY",
    Use.EVALS: "UNTANGLE_EVALS_MODEL_API_KEY",
    Use.OPERATIONS: "UNTANGLE_OPERATIONS_MODEL_API_KEY",
    Use.CORPUS: "UNTANGLE_CORPUS_MODEL_API_KEY",
    Use.CHAT_REPLY: "UNTANGLE_ANTHROPIC_API_KEY_CHAT",
    Use.EVALS_CHAT: "UNTANGLE_ANTHROPIC_API_KEY_EVALS",
}


def env_var_for(use: Use) -> str:
    """La variable de entorno que lleva la clave de ese uso."""
    return _VARIABLE_POR_USO[use]


class MissingProviderKeyError(RuntimeError):
    """Ese uso no tiene clave declarada.

    Es un fallo de configuracion y no del proveedor, por eso **no** es uno de los
    cuatro tipos de error ni la senal de parada: no hay nada que reintentar ni
    ningun saldo que se haya acabado. Su mensaje nombra la variable que falta,
    que es lo unico que se puede decir sin decir nada de la clave.
    """


@dataclass(frozen=True)
class _Client:
    """Un cliente por uso. **Privado: ningun metodo de este modulo lo devuelve.**

    No guarda la clave: la entrego a `TransportFactory.create` al construirse y
    vive dentro del transporte. Lo que queda aqui es a que proveedor y con que
    modelo habla ese uso.
    """

    use: Use
    provider: ProviderName
    model: str
    transport: Transport

    def __repr__(self) -> str:
        """Nombra el uso, el proveedor y el modelo. Nunca nada mas."""
        return f"_Client(use={self.use.value}, provider={self.provider.value}, model={self.model})"


class ProviderClients:
    """La fabrica, y el `ProviderCaller` que reciben los adaptadores.

    Se construye una vez, en la raiz de composicion, con la configuracion ya
    validada y las claves ya leidas por el punto unico. **No acepta una clave por
    argumento**: si la aceptara, cualquiera podria construir un cliente con la
    que tuviera a mano y la separacion por uso seria una costumbre en vez de una
    propiedad.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        config: ProvidersConfig,
        transports: TransportFactory,
    ) -> None:
        self._clientes: dict[Use, _Client] = {}
        self._sin_clave: dict[Use, str] = {}

        for uso in config.uses:
            # Este registro arma transportes de Gemini. Un uso de otro proveedor
            # --`chat_reply`, de Anthropic-- tiene su cliente en su propio
            # adaptador y no pasa por aqui.
            if uso.provider is not ProviderName.GEMINI:
                continue
            clave = self._clave_de(settings, uso.use)
            if clave is None:
                self._sin_clave[uso.use] = env_var_for(uso.use)
                continue
            self._clientes[uso.use] = _Client(
                use=uso.use,
                provider=uso.provider,
                model=uso.model,
                transport=transports.create(api_key=clave, use=uso.use),
            )

    @staticmethod
    def _clave_de(settings: Settings, use: Use) -> str | None:
        """La clave de ese uso, leida del punto unico y de ningun otro sitio.

        Se lee por atributo y no por nombre de variable porque `settings` ya
        valido el entorno al construirse: volver a mirar el entorno aqui seria un
        segundo punto de lectura, que es justo lo que SEC-U1.2 prohibe.
        """
        claves: dict[Use, str | None] = {
            Use.VOICE: settings.voice_model_api_key,
            Use.CHAT: settings.chat_model_api_key,
            Use.EVALS: settings.evals_model_api_key,
            Use.OPERATIONS: settings.operations_model_api_key,
            Use.CORPUS: settings.corpus_model_api_key,
            Use.CHAT_REPLY: settings.anthropic_api_key_chat,
            Use.EVALS_CHAT: settings.anthropic_api_key_evals,
        }
        return claves[use]

    def require(self, *uses: Use) -> None:
        """Exige que esos usos tengan cliente. La raiz lo llama al arrancar.

        Falla **antes** de construir nada mas y antes de la primera llamada, que
        es lo que deja la cuota intacta: descubrir a mitad de una corrida que
        faltaba una clave cuesta lo que ya se gasto.
        """
        faltan = sorted(env_var_for(uso) for uso in uses if uso in self._sin_clave)
        if faltan:
            msg = (
                f"faltan estas variables de entorno: {', '.join(faltan)}. Cada uso lleva "
                "su propia clave, en su propio proyecto del proveedor, para que una cuota "
                "agotada en uno no apague los otros (BR1.3)"
            )
            raise MissingProviderKeyError(msg)

    def available(self) -> tuple[Use, ...]:
        """Los usos que tienen cliente. Para la senal de salud, no para decidir."""
        return tuple(sorted(self._clientes, key=lambda uso: uso.value))

    def model_for(self, use: Use) -> str:
        """El identificador exacto del modelo de ese uso (BR1.4).

        Lo necesita el adaptador para armar la ruta y para estampar
        `gen_ai.request.model` en el tramo. Es el identificador, no la clave.
        """
        return self._exigir(use).model

    def provider_for(self, use: Use) -> ProviderName:
        """A que proveedor habla ese uso."""
        return self._exigir(use).provider

    async def send(self, request: ProviderRequest, *, use: Use) -> ProviderResponse:
        """Manda la peticion por el cliente de ese uso, y por ningun otro."""
        return await self._exigir(use).transport.send(request)

    def _exigir(self, use: Use) -> _Client:
        cliente = self._clientes.get(use)
        if cliente is not None:
            return cliente
        variable = self._sin_clave.get(use)
        if variable is None:
            msg = (
                f"el uso '{use.value}' no esta declarado en la configuracion de "
                "proveedores: todo uso declara su plan y su modelo (BR1.3)"
            )
            raise MissingProviderKeyError(msg)
        msg = (
            f"el uso '{use.value}' no tiene clave: defina '{variable}'. No se usa la de "
            "otro uso, que es exactamente lo que las claves separadas impiden (BR1.3)"
        )
        raise MissingProviderKeyError(msg)


# --- La voz: un transporte por proveedor, con la clave del uso `voice` --------

#: La variable de cada proveedor de voz. **Solo del uso `voice`**: no hay clave de
#: Deepgram ni de Cartesia para ningun otro uso, y por eso esta tabla no tiene
#: columna de uso (BR1.3, SEC-U15.2).
_VARIABLE_DE_VOZ: dict[ProviderName, str] = {
    ProviderName.DEEPGRAM: VOICE_DEEPGRAM_API_KEY_VAR,
    ProviderName.CARTESIA: VOICE_CARTESIA_API_KEY_VAR,
}


def speech_env_var_for(provider: ProviderName) -> str:
    """La variable de entorno con la clave de voz de ese proveedor."""
    variable = _VARIABLE_DE_VOZ.get(provider)
    if variable is None:
        msg = f"'{provider.value}' no es un proveedor de voz: no tiene clave del uso voice"
        raise MissingProviderKeyError(msg)
    return variable


class SpeechClients:
    """Los clientes de voz, uno por proveedor, y el `SpeechCaller` que reciben sus adaptadores.

    Hermana de `ProviderClients` y con sus mismas reglas: **no acepta una clave
    por argumento**, la lee del punto unico por atributo, y el transporte que
    construye no sale de aqui. Lo que cambia es la forma de la llamada --la voz
    transmite en streaming-- y que **solo existe el uso `voice`**: un adaptador de
    voz que pidiera su cliente con otro uso falla en vez de recibir el de la voz,
    porque eso es exactamente lo que las claves separadas existen para impedir.

    Un proveedor sin clave no tiene cliente y **no se inventa ninguno**: pedirlo
    falla nombrando la variable que falta. Nada se exige al arrancar, por la
    misma razon que en Gemini: el camino del clon al reporte no habla con la voz.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        transports: Mapping[ProviderName, SpeechTransportFactory],
    ) -> None:
        self._transportes: dict[ProviderName, SpeechTransport] = {}
        self._sin_clave: dict[ProviderName, str] = {}
        for proveedor, fabrica in transports.items():
            clave = self._clave_de(settings, proveedor)
            if clave is None:
                self._sin_clave[proveedor] = speech_env_var_for(proveedor)
                continue
            self._transportes[proveedor] = fabrica.create(api_key=clave, use=Use.VOICE)

    @staticmethod
    def _clave_de(settings: Settings, provider: ProviderName) -> str | None:
        """La clave de voz de ese proveedor, leida del punto unico y de ningun otro sitio."""
        claves: dict[ProviderName, str | None] = {
            ProviderName.DEEPGRAM: settings.voice_deepgram_api_key,
            ProviderName.CARTESIA: settings.voice_cartesia_api_key,
        }
        if provider not in claves:
            speech_env_var_for(provider)  # falla nombrando por que no hay clave
        return claves[provider]

    def require(self, *providers: ProviderName) -> None:
        """Exige que esos proveedores tengan cliente, antes de gastar nada."""
        faltan = sorted(self._sin_clave[p] for p in providers if p in self._sin_clave)
        if faltan:
            msg = (
                f"faltan estas variables de entorno: {', '.join(faltan)}. La voz lleva "
                "sus propias claves, del uso voice, y no usa las de ningun otro (BR1.3)"
            )
            raise MissingProviderKeyError(msg)

    def available(self) -> tuple[ProviderName, ...]:
        """Los proveedores de voz que tienen cliente."""
        return tuple(sorted(self._transportes, key=lambda p: p.value))

    def open_duplex(
        self, request: SpeechRequest, *, provider: ProviderName, use: Use
    ) -> AbstractAsyncContextManager[DuplexChannel]:
        return self._exigir(provider, use).open_duplex(request)

    def stream_post(
        self, request: SpeechRequest, *, provider: ProviderName, use: Use
    ) -> AbstractAsyncContextManager[ByteStream]:
        return self._exigir(provider, use).stream_post(request)

    async def get_json(
        self, request: SpeechRequest, *, provider: ProviderName, use: Use
    ) -> tuple[int, Mapping[str, object]]:
        return await self._exigir(provider, use).get_json(request)

    def _exigir(self, provider: ProviderName, use: Use) -> SpeechTransport:
        if use is not Use.VOICE:
            msg = (
                f"se pidio el cliente de '{provider.value}' para el uso '{use.value}': los "
                "proveedores de voz solo tienen clave del uso voice (BR1.3)"
            )
            raise MissingProviderKeyError(msg)
        transporte = self._transportes.get(provider)
        if transporte is not None:
            return transporte
        variable = self._sin_clave.get(provider) or speech_env_var_for(provider)
        msg = (
            f"'{provider.value}' no tiene clave de voz: defina '{variable}'. No se usa la "
            "de otro uso, que es exactamente lo que las claves separadas impiden (BR1.3)"
        )
        raise MissingProviderKeyError(msg)
