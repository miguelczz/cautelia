"""El cortacircuitos, uno por pareja (proveedor, uso).

Vive en el adaptador porque **la salud de una dependencia externa es suya**, no
del nodo: si el proveedor esta caido lo esta para los cuatro nodos, y un
mecanismo por nodo obligaria a que cada uno lo descubriera por su cuenta --cuatro
esperas por turno en vez de una--.

Por **uso** y no solo por proveedor porque las claves y los proyectos estan
separados justamente para que una cuota agotada en el chat no apague la voz. Un
circuito compartido lo apagaria igualmente, y con el la separacion dejaria de
comprar nada.

## Los tres numeros, y de donde salen

Los tres estan en `app/config/providers/providers.yaml`, no aqui: cambiarlos no
deberia exigir un despliegue de logica. Lo que **si** es una decision de diseno y
por eso no es configurable: **que tipos de error cuentan**.

- Cuentan `timeout`, `unavailable` y `rate_limited`: los tres dicen algo sobre el
  proveedor.
- **`invalid_response` no cuenta, y tampoco rompe la racha.** Es un problema del
  contenido --un esquema que no valida, un prompt mal hecho-- y contarlo abriria
  el circuito por un error nuestro. Ignorarlo del todo, en vez de tratarlo como
  exito, evita ademas lo contrario: que una respuesta invalida entre cinco
  timeouts mantuviera el circuito cerrado para siempre.
- `BudgetExhausted` tampoco lo toca: el proveedor esta sano; lo que se acabo es
  el dinero.

## El reloj se inyecta

Los treinta segundos se prueban sin dormir. Un `sleep` en una prueba la hace
lenta y la ata al reloj de la maquina, que es una forma de depender del ambiente.
Se usa reloj **monotono** y no el de pared porque lo que se mide es un intervalo:
con el de pared, un ajuste de hora cerraria o alargaria un circuito sin que nadie
lo hubiera decidido.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from enum import StrEnum

from untangle import observability
from untangle.base import ProviderErrorKind, ProviderName, Use
from untangle.providers.config import CircuitBreakerConfig

__all__ = ["CircuitBreaker", "CircuitBreakerRegistry", "CircuitState", "cuenta_para_el_circuito"]

#: Los tres tipos que hablan de la salud del proveedor. `invalid_response` no
#: esta, y esa ausencia es la decision entera de este modulo.
_TIPOS_DE_SALUD: frozenset[ProviderErrorKind] = frozenset(
    {
        ProviderErrorKind.TIMEOUT,
        ProviderErrorKind.UNAVAILABLE,
        ProviderErrorKind.RATE_LIMITED,
    }
)


def cuenta_para_el_circuito(kind: ProviderErrorKind) -> bool:
    """Si ese tipo de error dice algo sobre la salud del proveedor."""
    return kind in _TIPOS_DE_SALUD


class CircuitState(StrEnum):
    """Los tres estados. `HALF_OPEN` es el que deja pasar la llamada de prueba."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """El circuito de una pareja (proveedor, uso).

    Sus transiciones no tienen ningun `await` dentro, asi que dos llamadas
    concurrentes del mismo bucle no se pueden intercalar a mitad de un cambio de
    estado. No hace falta un candado y tenerlo seria peor: un candado en el
    camino del turno es una espera mas.
    """

    def __init__(
        self,
        *,
        provider: ProviderName,
        use: Use,
        config: CircuitBreakerConfig,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._provider = provider
        self._use = use
        self._config = config
        self._monotonic = monotonic
        self._state = CircuitState.CLOSED
        self._fallos = 0
        self._abierto_en: float | None = None
        self._sondas = 0

    @property
    def state(self) -> CircuitState:
        """El estado, **ya vencido el plazo si toca**.

        Se consulta el reloj al leer y no con un temporizador: un temporizador
        exigiria una tarea viva por circuito, y lo que decide si la llamada pasa
        es justo este momento.
        """
        if self._state is CircuitState.OPEN and self._plazo_cumplido():
            self._cambiar(CircuitState.HALF_OPEN)
            self._sondas = 0
        return self._state

    def allows_call(self) -> bool:
        """Si esta llamada puede salir.

        Con el circuito abierto devuelve `False` **en el acto**: el adaptador
        levanta `unavailable` sin tocar la red y el nodo aplica su politica sobre
        esa respuesta, igual que sobre cualquier otra.
        """
        estado = self.state
        if estado is CircuitState.CLOSED:
            return True
        if estado is CircuitState.OPEN:
            return False
        if self._sondas >= self._config.half_open_probes:
            return False
        self._sondas += 1
        return True

    def record_success(self) -> None:
        """La llamada paso: la racha vuelve a cero y el circuito cierra."""
        self._fallos = 0
        self._sondas = 0
        if self._state is not CircuitState.CLOSED:
            self._cambiar(CircuitState.CLOSED)

    def record_failure(self, kind: ProviderErrorKind) -> None:
        """Un fallo. Solo abre el circuito si dice algo de la salud del proveedor."""
        if not cuenta_para_el_circuito(kind):
            return

        if self._state is CircuitState.HALF_OPEN:
            # La llamada de prueba fallo: vuelve a abrir y el plazo empieza de
            # nuevo. No se acumulan sondas fallidas hasta un segundo umbral: con
            # el circuito ya abierto una vez, la pregunta es "sigue caido?", y
            # una sola respuesta la contesta.
            self._abrir()
            return

        self._fallos += 1
        if self._fallos >= self._config.failure_threshold:
            self._abrir()

    def _abrir(self) -> None:
        self._abierto_en = self._monotonic()
        self._sondas = 0
        self._fallos = 0
        self._cambiar(CircuitState.OPEN)

    def _plazo_cumplido(self) -> bool:
        if self._abierto_en is None:  # pragma: no cover - no se abre sin marcar la hora
            return True
        return self._monotonic() - self._abierto_en >= self._config.open_seconds

    def _cambiar(self, nuevo: CircuitState) -> None:
        """Cambia de estado **y lo dice**.

        Un cortacircuitos que se abre en silencio es indistinguible de un
        proveedor lento, y la diferencia es lo unico que permite saber si hay que
        mirar al proveedor o al codigo.
        """
        if self._state is nuevo:
            return
        self._state = nuevo
        observability.emit(
            "providers.circuit_state_changed",
            provider=self._provider.value,
            use=self._use.value,
            state=nuevo.value,
        )


class CircuitBreakerRegistry:
    """Un circuito por pareja (proveedor, uso), compartido por los adaptadores.

    Compartido a proposito: el generador de texto y el de embeddings del mismo
    proveedor y el mismo uso hablan con **la misma** dependencia externa. Con un
    circuito por adaptador, el primero podria estar abierto y el segundo seguir
    llamando a un proveedor que ya se sabe caido, y "uno por pareja (proveedor,
    uso)" seria falso.
    """

    def __init__(
        self,
        config: CircuitBreakerConfig,
        *,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._config = config
        self._monotonic = monotonic
        self._circuitos: dict[tuple[ProviderName, Use], CircuitBreaker] = {}

    def for_pair(self, provider: ProviderName, use: Use) -> CircuitBreaker:
        clave = (provider, use)
        circuito = self._circuitos.get(clave)
        if circuito is None:
            circuito = CircuitBreaker(
                provider=provider,
                use=use,
                config=self._config,
                monotonic=self._monotonic,
            )
            self._circuitos[clave] = circuito
        return circuito
