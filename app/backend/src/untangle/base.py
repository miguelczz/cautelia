"""El vocabulario que cruza todo el aplicativo, y de nadie en particular.

Vive en la raiz del paquete y no dentro de un modulo porque **no es de ninguno**:
si `copy_catalog` fuera el dueno del idioma, `evals` tendria que importarlo para
hablar de un caso en espanol, y esa dependencia no describe ninguna relacion
real. Un modulo hoja sin dependencias es lo que evita esas aristas inventadas.

Lo que hay aqui son tres cosas y solo tres:

1. **`Locale` y `Frozen`**, desde el primer commit.
2. **Los cuatro enums cerrados que hablan los dos lados de una llamada a un
   proveedor** --`Use`, `ProviderName`, `UnitKind`, `SpendSource`-- y la
   taxonomia cerrada de errores de la frontera, `ProviderErrorKind`. Los
   escriben el adaptador que reporta, la contabilidad que valora y la traza que
   registra: tres modulos que no se importan entre si y que tienen que usar
   **la misma grafia**. Dos listas que coinciden hoy es exactamente como se
   pierde una.
3. **La regla de la coma flotante** y el recuento de unidades cobrables,
   `UnitCount`, que es el otro factor de la multiplicacion que produce el costo.
   El dinero en si --`UsdAmount`, `Money`, `SpendTotal`-- se queda en
   `telemetry/spend/models.py`, que es su dueno; lo que sube aqui es la regla
   que los dos comparten.

**Por que subieron en el bloque F.** Estaban en `telemetry/spend/models.py` y en
`telemetry/traces/models.py`, y `providers/ports.py` --lo que ven seis unidades--
los importaba de alli. Eso obligaba a escribir el contrato de importacion del
paso 21 como "`ports.py` no importa ningun SDK ni `telemetry.*.api` ni
`telemetry.*.repository`", y quien lo leyera en seis semanas se preguntaria por
que si puede importar `telemetry.*.models`. Con la mudanza el contrato dice la
cosa simple y verdadera: **`ports.py` no importa nada de `telemetry/`**.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

#: Los dos idiomas del producto. La paridad entre ellos no es una preferencia de
#: formato: un promedio esconde que una capacidad funciona en uno y no en el otro
#: (P12).
Locale = Literal["es", "en"]


class Frozen(BaseModel):
    """Base comun: modelos congelados y sin campos de mas."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    def evolve(self, **cambios: Any) -> Self:
        """Una copia con esos campos cambiados, **validada de nuevo**.

        Existe porque `model_copy(update=...)` **no vuelve a validar**: entrega
        un objeto del tipo correcto que puede violar todas las reglas que su
        tipo impone. En un modelo cuyo valor entero esta en sus invariantes
        --un caso cerrado lleva su resolucion, un campo dicho lleva su
        evidencia-- esa es la forma mas silenciosa de perderlas: el codigo se
        lee igual, los tipos pasan, y la regla deja de aplicarse.

        Cuesta reconstruir el objeto. Es el precio de que "el tipo lo impide"
        siga siendo cierto despues del primer cambio.
        """
        return type(self).model_validate({**self.model_dump(), **cambios})


# --- El vocabulario de una llamada a un proveedor -----------------------------
# Ninguno de estos valores se imprime hacia una persona: la etiqueta sale del
# catalogo de textos en su idioma (convencion 4 del equipo). Estan aqui porque el
# conjunto es cerrado y un valor fuera de el tiene que ser imposible de escribir,
# no solo improbable.


class Use(StrEnum):
    """Para que se llama al proveedor (BR1.3).

    No es una etiqueta: decide el proyecto del proveedor, la clave, el plan y si
    la llamada se factura. Las claves estan separadas por uso justamente para que
    una cuota agotada en el chat no apague la voz.
    """

    VOICE = "voice"
    CHAT = "chat"
    EVALS = "evals"
    OPERATIONS = "operations"
    #: Embeddings del corpus de pólizas: la ingesta de U7/U8 y la consulta en
    #: tiempo de recuperación (U8, PASO 0 de `u8-tanda-3`). Va aparte de
    #: `OPERATIONS` porque un `UseConfig` es un modelo por uso, y los cuatro
    #: usos anteriores ya apuntaban al modelo de generación: mezclar el de
    #: embeddings ahí habría roto esa otra llamada.
    CORPUS = "corpus"
    #: La redaccion natural de la respuesta del chat (decision de Miguel del
    #: 2026-10-07): el codigo elige que decir y este uso lo dice con naturalidad.
    #: Va aparte de `CHAT` porque es otro proveedor, otro plan --pago, con saldo
    #: prepagado-- y otra clave, y una cuota agotada aqui no puede apagar la
    #: extraccion de datos del chat.
    CHAT_REPLY = "chat_reply"
    #: Las evaluaciones de la comprension del chat con Claude (2026-10-08,
    #: `mise run evals:entender`). Va aparte de `EVALS` --Gemini gratuito-- porque
    #: es otro proveedor y otro plan, y de `CHAT_REPLY` porque es otra clave: una
    #: corrida no gasta el saldo que atiende a los visitantes. Sin uso propio su
    #: gasto quedaba marcado como no facturable y no contaba contra el techo.
    EVALS_CHAT = "evals_chat"


class ProviderName(StrEnum):
    """Los proveedores del proyecto (BR3.1).

    Uno nuevo es una entrada nueva en esta lista, no una cadena libre, y llega con
    su revision de migracion: la restriccion `spend_entry_proveedor_valido` del
    libro mayor enumera los mismos valores, y una prueba de integracion falla si
    la base y esta lista dicen cosas distintas.

    Los dos ultimos son la voz, construida por U15 `speech-providers`: Deepgram
    transcribe y da la voz de respaldo (Aura-2), y Cartesia da la principal
    (Catalina). Hubo un cuarto, `fallback_tts`, que U5 reservo para una voz de
    respaldo sin proveedor decidido; la enmienda del 2026-09-21 de ADR-008 la dio
    a Deepgram, el nombre dejo de describir nada construido y se retiro con la
    revision `u15_speech_0001_provider_check`.
    """

    GEMINI = "gemini"
    DEEPGRAM = "deepgram"
    CARTESIA = "cartesia"
    #: Claude Haiku 5.5, para la redaccion natural del chat (uso `chat_reply`,
    #: 2026-10-07). Llega con la revision `u23_reply_0001_anthropic`.
    ANTHROPIC = "anthropic"


class UnitKind(StrEnum):
    """Que cobra el proveedor.

    No se convierte a una unidad comun: hacerlo perderia el precio de lista con
    el que se calculo, que es lo que AC4.8.4 exige guardar.
    """

    INPUT_TOKENS = "input_tokens"
    OUTPUT_TOKENS = "output_tokens"
    EMBEDDING_TOKENS = "embedding_tokens"
    AUDIO_SECONDS = "audio_seconds"
    CHARACTERS = "characters"


class SpendSource(StrEnum):
    """De donde salio el recuento de unidades.

    Un conteo propio y uno del proveedor no valen lo mismo, y no se mezclan sin
    decirlo: cuando los dos discrepan, esta columna es lo unico que permite saber
    cual de los dos se estaba sumando.

    `RECONCILED_ADJUSTMENT` no es un recuento: es el asiento que Miguel anota a
    mano cuando el libro quedo por debajo de lo que cobro el proveedor (2026-10-13,
    `mise run spend:reconcile`). Lo escribe una persona, nunca un adaptador, y por
    eso no lleva unidades ni precio de lista: lleva el importe y la nota de donde
    salio la cifra.
    """

    PROVIDER_REPORTED = "provider_reported"
    COUNTED_LOCALLY = "counted_locally"
    RECONCILED_ADJUSTMENT = "reconciled_adjustment"


class ProviderErrorKind(StrEnum):
    """Los cuatro tipos de error de la frontera del proveedor (convencion 8a).

    Los escriben tres modulos que no se importan entre si --el adaptador que
    traduce, el tramo que registra `untangle.error_kind` y el reporte de
    evaluaciones que los cuenta-- y el atributo del tramo no admite texto libre,
    asi que el tipo tiene que ser uno solo y no tres listas que coinciden hoy.

    `BudgetExhausted` **no esta aqui** y es deliberado (entidades, "Lo que no se
    guarda"): los cuatro de abajo admiten politica de reintento y ese no, porque
    significa "para". Meterlo en la misma lista invitaria a reintentarlo.
    """

    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    UNAVAILABLE = "unavailable"
    INVALID_RESPONSE = "invalid_response"


# --- La regla de la coma flotante ---------------------------------------------


class FloatMoneyError(ValueError):
    """Se intento construir un importe o un recuento con coma flotante.

    Hereda de `ValueError` y no de `TypeError` --que describiria mejor lo que
    pasa-- por una razon practica: Pydantic solo convierte en error de validacion
    lo que sea `ValueError`, y solo asi el cargador de configuracion puede
    envolverlo nombrando **el archivo y la clave** donde iba el numero. Un
    `TypeError` se escaparia crudo y diria que algo es un `float` sin decir de
    donde salio, que es la mitad inutil del mensaje.
    """


def reject_float(valor: object) -> object:
    """Rechaza `float` antes de que Pydantic lo convierta a `Decimal`.

    Sin esto, `Decimal(0.1)` entraria como 0.1000000000000000055511151231257827,
    el tipo seguiria diciendo `Decimal` y la perdida de exactitud viajaria hasta
    el total publicado sin que nada la delatara. Se rechaza en la frontera
    porque es el unico sitio donde todavia se puede nombrar el origen.
    """
    if isinstance(valor, float):
        msg = (
            "el dinero y las unidades se escriben en decimal exacto, nunca en coma "
            f"flotante; llego {valor!r}. Use Decimal('...') en el codigo, y en YAML "
            "escriba el numero entre comillas para que no se lea como coma flotante"
        )
        raise FloatMoneyError(msg)
    return valor


#: Un recuento de unidades cobrables --tokens, segundos de audio, caracteres--.
#: Mismo tipo exacto que el dinero y por la misma razon: es uno de los dos
#: factores de la multiplicacion que produce el costo, y basta con que uno sea
#: inexacto para que el producto lo sea.
UnitCount = Annotated[Decimal, BeforeValidator(reject_float), Field(ge=0)]
