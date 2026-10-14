"""El adaptador de Gemini: los dos puertos que esta unidad implementa.

Hace cinco cosas y ninguna mas: arma la peticion con la instruccion **separada**
del contenido, traduce el error a uno de cuatro tipos, valida la salida
estructurada, lleva el cortacircuitos de su proveedor, y reporta lo que consumio
a la contabilidad y lo que tardo a la traza.

## Lo que **no** hace, que es la parte que se olvida

- **No reintenta.** Ante `rate_limited` devuelve y decide la politica de fallo
  del nodo, que aplica el ejecutor comun de U12 (BR2.4). Una prueba comprueba que
  hizo exactamente una llamada.
- **No degrada a otro proveedor.** Ante saldo o cuota agotados sale
  `BudgetExhausted` y el trabajo se detiene: la regla del proyecto dice que
  entonces se identifica que se acabo y decide Miguel.
- **No escribe la fila de gasto ni calcula el costo.** Reporta unidades; la
  contabilidad las valora con la tabla de precios versionada. Asi el precio vive
  en un solo sitio.
- **No abre el circuito por una respuesta invalida.** Eso es contenido, no salud
  del proveedor.

## El tramo, y cuando no hay ninguno

El tramo de llamada cuelga del tramo de nodo, que cuelga del tramo del turno: un
costo que no se puede atribuir a su nodo es lo que AC4.8.1 existe para impedir, y
el ayudante del bloque D lo impone levantando ante un tramo huerfano.

Una llamada **fuera de turno** --el corredor de evaluaciones, una tarea de
operacion-- no tiene nodo del que colgar, asi que no emite tramo en vez de
emitir uno huerfano. Lo que no cambia es el gasto: la contabilidad no depende de
las trazas, y esa llamada deja su fila igual (BR4.8).

## El transporte, detras de su propia frontera

El que habla por la red vive en `transport.py`, dentro de este mismo paquete,
que es el unico sitio donde se puede importar un cliente de proveedor (BR1.2).
Este archivo esta escrito contra la superficie que ese transporte expone y no
contra el, asi que las pruebas inyectan respuestas y fallos **sin red y sin
clave**: lo que se doblan son las respuestas, no el adaptador.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager

from pydantic import BaseModel, ValidationError

from untangle import observability
from untangle.base import SpendSource, UnitKind, Use
from untangle.providers.adapters.gemini import request as armar
from untangle.providers.adapters.gemini.breaker import CircuitBreaker, CircuitBreakerRegistry
from untangle.providers.adapters.gemini.errors import (
    PROVIDER,
    raise_for_response,
    translate_transport_failure,
)
from untangle.providers.config import ModelKind, ProvidersConfig, UseConfig
from untangle.providers.ports import (
    BudgetExhausted,
    GenerationResult,
    Prompt,
    ProviderError,
    ProviderErrorKind,
    UsageReport,
    UsageSink,
    UsageUnits,
    Vector,
)
from untangle.providers.transport import (
    CallTimeouts,
    ProviderCaller,
    ProviderRequest,
    TransportError,
)
from untangle.telemetry.traces import api as trazas

__all__ = ["GeminiEmbedder", "GeminiTextGenerator", "ProviderMisconfiguredError"]

#: El adaptador hace **una** llamada por invocacion. No es un parametro: el
#: numero de intento real lo lleva el ejecutor de nodos de U12, que es quien
#: reintenta, y C-16 no le da al adaptador forma de conocerlo.
UN_SOLO_INTENTO = 1


class ProviderMisconfiguredError(RuntimeError):
    """Este adaptador recibio un uso que no habla con su proveedor.

    Es un fallo de cableado de la raiz de composicion, no del proveedor: por eso
    no es ninguno de los cuatro tipos ni la senal de parada. Falla en vez de
    llamar: una llamada al proveedor equivocado con la clave equivocada es
    exactamente lo que las claves separadas por uso existen para impedir.
    """


@contextmanager
def _tramo(*, model: str, use: Use) -> Iterator[trazas.Span | None]:
    """El tramo de la llamada, o ninguno si esta llamada no ocurre en un turno."""
    if trazas.current_context() is None:
        yield None
        return
    with trazas.call_span(
        provider=PROVIDER, model=model, use=use, attempt=UN_SOLO_INTENTO
    ) as tramo:
        yield tramo


def _caso_actual() -> str | None:
    """El caso al que atribuir el gasto, si lo hay.

    Sale del contexto de traza porque C-16 no lleva el caso en la firma de
    `generate`. Es una lectura de una variable de contexto, no una llamada al
    backend de trazas: que el panel de trazas este caido no deja un gasto sin
    atribuir. Lo que si lo deja es una llamada fuera de turno, y eso queda
    escrito.
    """
    contexto = trazas.current_context()
    return contexto.case_id if contexto is not None else None


class _GeminiAdapter:
    """Lo que comparten los dos puertos: la configuracion, el circuito y la llamada.

    Es una base y no una utilidad suelta porque los dos adaptadores tienen que
    compartir **el mismo registro de circuitos**: el generador y el calculador de
    embeddings del mismo uso hablan con la misma dependencia externa, y dos
    circuitos separados dejarian a uno llamando a un proveedor que el otro ya
    sabe caido.
    """

    def __init__(
        self,
        caller: ProviderCaller,
        *,
        config: ProvidersConfig,
        breakers: CircuitBreakerRegistry,
        usage: UsageSink,
        timeouts: Mapping[Use, CallTimeouts],
    ) -> None:
        self._caller = caller
        self._config = config
        self._breakers = breakers
        self._usage = usage
        self._timeouts = dict(timeouts)

    def _plan(self, use: Use) -> UseConfig:
        plan = self._config.for_use(use)
        if plan.provider is not PROVIDER:
            msg = (
                f"el uso '{use.value}' habla con '{plan.provider.value}' y este es el "
                f"adaptador de '{PROVIDER.value}': la raiz de composicion esta cableada "
                "al reves"
            )
            raise ProviderMisconfiguredError(msg)
        return plan

    def _tiempos(self, use: Use) -> CallTimeouts:
        tiempos = self._timeouts.get(use)
        if tiempos is None:
            msg = (
                f"el uso '{use.value}' no declara tiempo maximo de conexion ni de "
                "lectura. Son por uso porque el turno de voz no puede esperar lo que "
                "una corrida de evaluaciones si"
            )
            raise ProviderMisconfiguredError(msg)
        return tiempos

    async def _llamar(
        self,
        *,
        use: Use,
        path: str,
        body: Mapping[str, object],
        circuito: CircuitBreaker,
        tramo: trazas.Span | None,
    ) -> Mapping[str, object]:
        """Una llamada, con su circuito, su traduccion y su reporte de uso.

        El orden importa y es este: se mira el circuito **antes** de tocar la red;
        se reporta el uso de **toda** llamada que llego a tener respuesta o que
        salio y fallo, porque una fila de gasto que faltara dejaria el costo por
        caso por debajo del real sin que nadie lo notara; y solo despues se
        levanta el error.
        """
        if not circuito.allows_call():
            # Falla en el acto, sin tocar la red y **sin reportar uso**: no hubo
            # llamada que cobrar. El nodo aplica su politica sobre esta respuesta
            # igual que sobre cualquier otra.
            error = ProviderError(
                ProviderErrorKind.UNAVAILABLE,
                provider=PROVIDER,
                use=use,
                attempt=UN_SOLO_INTENTO,
            )
            self._marcar_fallo(tramo, error.kind)
            raise error

        peticion = ProviderRequest(
            path=path,
            body=body,
            connect_timeout_ms=self._tiempos(use).connect_timeout_ms,
            read_timeout_ms=self._tiempos(use).read_timeout_ms,
        )

        try:
            respuesta = await self._caller.send(peticion, use=use)
        except TransportError as fallo:
            error = translate_transport_failure(fallo, use=use, attempt=UN_SOLO_INTENTO)
            # Salio y no volvio: pudo haber consumido. No hay recuento que
            # reportar, pero la llamada existio y su fila tambien.
            await self._reportar(use, ())
            circuito.record_failure(error.kind)
            self._marcar_fallo(tramo, error.kind)
            raise error from None

        unidades = armar.read_usage(respuesta.body)
        await self._reportar(use, unidades)
        self._marcar_uso(tramo, unidades)

        try:
            raise_for_response(respuesta, use=use, attempt=UN_SOLO_INTENTO)
        except ProviderError as error:
            circuito.record_failure(error.kind)
            self._marcar_fallo(tramo, error.kind)
            raise
        except BudgetExhausted:
            # El circuito **no** se toca: el proveedor esta sano; lo que se acabo
            # es el dinero. Y la lista cerrada de atributos del tramo no tiene
            # valor para una parada --sus cuatro son los cuatro errores-- asi que
            # lo que queda de esto en el rastro es este evento.
            observability.emit(
                "providers.budget_exhausted",
                provider=PROVIDER.value,
                use=use.value,
            )
            raise

        circuito.record_success()
        return respuesta.body

    async def _reportar(self, use: Use, unidades: tuple[UsageUnits, ...]) -> None:
        """Lo que consumio esta llamada, hacia la contabilidad.

        El origen es siempre `PROVIDER_REPORTED`: lo que se reporta es lo que el
        proveedor conto, incluido no contar nada. Un recuento propio valdria otra
        cosa y por eso tiene su propio valor; mezclarlos sin decirlo dejaria sin
        forma de saber cual se estaba sumando cuando los dos discrepan.
        """
        await self._usage.report(self._reporte(use, unidades))

    def _reporte(self, use: Use, unidades: tuple[UsageUnits, ...]) -> UsageReport:
        """El reporte de uso, armado en un solo sitio.

        Lo construyen dos caminos --el que va a la contabilidad y el que viaja en
        el resultado-- y tienen que decir lo mismo: dos construcciones separadas
        es como un dia el modelo del reporte y el de la fila dejan de coincidir.
        """
        return UsageReport(
            provider=PROVIDER,
            model=self._config.for_use(use).model,
            use=use,
            units=unidades,
            source=SpendSource.PROVIDER_REPORTED,
            case_ref=_caso_actual(),
        )

    @staticmethod
    def _marcar_fallo(tramo: trazas.Span | None, kind: ProviderErrorKind) -> None:
        """Deja el tipo de error en el tramo (BR2.5).

        El numero de intento ya lo estampa el ayudante al abrirlo. Lo que **no**
        se escribe es nada del cuerpo: los atributos no admiten texto libre, y
        esa es justamente la lista que lo impide.
        """
        if tramo is not None:
            tramo.set({"untangle.error_kind": kind})

    @staticmethod
    def _marcar_uso(tramo: trazas.Span | None, unidades: tuple[UsageUnits, ...]) -> None:
        """Los dos recuentos de tokens en el tramo, si el proveedor los dio.

        Se escriben uno a uno y con su nombre literal porque la lista de
        atributos es cerrada y el comprobador de tipos la impone: una clave
        calculada en una variable no compilaria, que es exactamente lo que se
        quiere.
        """
        if tramo is None:
            return
        for unidad in unidades:
            if unidad.unit_kind is UnitKind.INPUT_TOKENS:
                tramo.set({"gen_ai.usage.input_tokens": int(unidad.units)})
            elif unidad.unit_kind is UnitKind.OUTPUT_TOKENS:
                tramo.set({"gen_ai.usage.output_tokens": int(unidad.units)})


class GeminiTextGenerator(_GeminiAdapter):
    """Generar texto con Gemini, con esquema o sin el (C-16, BR1.5).

    Hereda del `Protocol` sin declararlo: `TextGenerator` es estructural y el
    comprobador de tipos verifica la conformidad en el sitio donde se inyecta.
    """

    async def generate(
        self, prompt: Prompt, *, schema: type[BaseModel] | None, use: Use
    ) -> GenerationResult:
        plan = self._plan(use)
        circuito = self._breakers.for_pair(PROVIDER, use)

        with _tramo(model=plan.model, use=use) as tramo:
            if tramo is not None:
                tramo.set(
                    {
                        "untangle.prompt_id": prompt.instruction.ref.prompt_id,
                        "untangle.prompt_hash": prompt.instruction.ref.sha256,
                    }
                )
            cuerpo = await self._llamar(
                use=use,
                path=armar.generate_path(plan.model),
                body=armar.build_generate_body(prompt, schema=schema),
                circuito=circuito,
                tramo=tramo,
            )

            texto = armar.read_text(cuerpo, use=use, attempt=UN_SOLO_INTENTO)
            parsed = self._validar(texto, schema=schema, use=use, tramo=tramo, circuito=circuito)
            return GenerationResult(
                text=None if schema is not None else texto,
                parsed=parsed,
                usage=UsageReport(
                    provider=PROVIDER,
                    model=plan.model,
                    use=use,
                    units=armar.read_usage(cuerpo),
                    source=SpendSource.PROVIDER_REPORTED,
                    case_ref=_caso_actual(),
                ),
                prompt=prompt.instruction.ref,
            )

    def _validar(
        self,
        texto: str,
        *,
        schema: type[BaseModel] | None,
        use: Use,
        tramo: trazas.Span | None,
        circuito: CircuitBreaker,
    ) -> BaseModel | None:
        """La salida estructurada se valida **aqui dentro** (BR1.5).

        Un fallo de validacion es `invalid_response` y el objeto crudo no sale de
        este archivo. El error se levanta **`from None`** a proposito: encadenar
        el `ValidationError` dejaria colgando un objeto que lleva dentro el valor
        que no valido --es decir, la respuesta del modelo entera-- y cualquiera
        que registrara la traza completa la imprimiria sin haberlo decidido.
        """
        if schema is None:
            return None
        try:
            return schema.model_validate_json(texto)
        except ValidationError:
            error = ProviderError(
                ProviderErrorKind.INVALID_RESPONSE,
                provider=PROVIDER,
                use=use,
                attempt=UN_SOLO_INTENTO,
            )
            # No cuenta para el circuito --`record_failure` lo ignora-- y se llama
            # igual para que haya un solo camino por el que pasa todo fallo.
            circuito.record_failure(error.kind)
            self._marcar_fallo(tramo, error.kind)
            raise error from None


class GeminiEmbedder(_GeminiAdapter):
    """Calcular embeddings con Gemini (C-16).

    La dimension del vector sale de la configuracion versionada, no del codigo:
    cambiarla invalida el indice entero y eso tiene que verse en un diff
    (ADR-006).
    """

    async def embed(self, texts: Sequence[str], *, use: Use) -> list[Vector]:
        if not texts:
            return []

        plan = self._plan(use)
        circuito = self._breakers.for_pair(PROVIDER, use)
        dimensiones = self._dimensiones(plan)

        with _tramo(model=plan.model, use=use) as tramo:
            cuerpo = await self._llamar(
                use=use,
                path=armar.embed_path(plan.model),
                body=armar.build_embed_body(plan.model, texts, dimensions=dimensiones),
                circuito=circuito,
                tramo=tramo,
            )
            try:
                return armar.read_embeddings(
                    cuerpo, expected=len(texts), use=use, attempt=UN_SOLO_INTENTO
                )
            except ProviderError as error:
                self._marcar_fallo(tramo, error.kind)
                raise

    def _dimensiones(self, plan: UseConfig) -> int | None:
        for proveedor in self._config.providers:
            if proveedor.name is not PROVIDER:
                continue
            for modelo in proveedor.models:
                if modelo.id == plan.model and modelo.kind is ModelKind.EMBEDDING:
                    return modelo.dimensions
        msg = (
            f"el uso '{plan.use.value}' apunta al modelo '{plan.model}', que la "
            "configuracion no declara como modelo de embeddings"
        )
        raise ProviderMisconfiguredError(msg)
