"""El azar del generador: SHA-256 sobre semilla, salida y contador (CG-U7-1, BR1.2).

## Por que no el modulo `random`

La documentacion de Python solo garantiza entre versiones la secuencia de
`random()`; los demas metodos --`choice`, `sample`, `randrange`-- pueden cambiar
de algoritmo, y con eso cambiarian los bytes del corpus al subir de version de
Python sin que nadie tocara una fuente. Un SHA-256 no cambia. El modulo `random`
esta prohibido en todo el aplicativo por el linter (TID251), y una prueba lo
comprueba ademas sobre este paquete.

## Por que un flujo por salida

Cada salida pide su propio elegidor, sembrado con su ruta: las elecciones de un
archivo dependen solo de la semilla, de su ruta y de cuantas veces se eligio
dentro de el. Anadir un archivo nuevo **no cambia** los demas, porque no consume
nada del flujo de ellos (BR1.2). La fabrica se niega a dar dos veces el mismo
flujo en una generacion: dos piezas que lo compartieran harian elecciones
identicas sin que nadie lo notara.

## Como sale un numero sin sesgo

Cada extraccion toma los primeros 8 bytes del SHA-256 de
`[semilla, flujo, contador]` en JSON compacto --sin ambiguedad posible entre los
tres-- y los lee como entero. Para un numero menor que `n` se rechazan los
enteros de la franja final que no reparte parejo: un modulo directo daria mas
probabilidad a los numeros bajos.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Final

__all__ = ["ChooserFactory", "SeededChooser"]

#: Cuantos enteros distintos da una extraccion: 8 bytes.
_ESPACIO: Final = 1 << 64


class SeededChooser:
    """Las elecciones de una sola salida, en un orden que solo depende de ella."""

    def __init__(self, seed: int, stream: str) -> None:
        self._seed = seed
        self._stream = stream
        self._contador = 0

    @property
    def stream(self) -> str:
        return self._stream

    def _extraer(self) -> int:
        mensaje = json.dumps(
            [self._seed, self._stream, self._contador], separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        self._contador += 1
        return int.from_bytes(hashlib.sha256(mensaje).digest()[:8], "big")

    def below(self, n: int) -> int:
        """Un entero en `[0, n)`, sin sesgo."""
        if n <= 0:
            msg = f"no hay ningun entero en [0, {n})"
            raise ValueError(msg)
        limite = _ESPACIO - (_ESPACIO % n)
        while True:
            valor = self._extraer()
            if valor < limite:
                return valor % n

    def between(self, low: int, high: int) -> int:
        """Un entero en `[low, high]`, los dos incluidos."""
        if high < low:
            msg = f"el intervalo [{low}, {high}] esta vacio"
            raise ValueError(msg)
        return low + self.below(high - low + 1)

    def choice[T](self, options: Sequence[T]) -> T:
        """Uno de los elementos."""
        if not options:
            msg = f"no hay nada que elegir en el flujo '{self._stream}'"
            raise ValueError(msg)
        return options[self.below(len(options))]

    def sample[T](self, options: Sequence[T], k: int) -> tuple[T, ...]:
        """`k` elementos distintos, en el orden en que se eligieron (Fisher-Yates parcial)."""
        if not 0 <= k <= len(options):
            msg = f"no se pueden elegir {k} de {len(options)} en el flujo '{self._stream}'"
            raise ValueError(msg)
        restantes = list(options)
        for i in range(k):
            j = i + self.below(len(restantes) - i)
            restantes[i], restantes[j] = restantes[j], restantes[i]
        return tuple(restantes[:k])

    def shuffled[T](self, options: Sequence[T]) -> tuple[T, ...]:
        """Todos los elementos, en un orden elegido."""
        return self.sample(options, len(options))

    def digits(self, count: int) -> str:
        """`count` digitos decimales."""
        return "".join(str(self.below(10)) for _ in range(count))


class ChooserFactory:
    """Da un elegidor por salida, y nunca dos veces el mismo en una generacion."""

    def __init__(self, seed: int) -> None:
        self._seed = seed
        self._entregados: set[str] = set()

    @property
    def seed(self) -> int:
        return self._seed

    def for_output(self, output: str, *, purpose: str = "") -> SeededChooser:
        """El elegidor de una salida, por su ruta dentro de `app/data/`.

        `purpose` separa dos flujos dentro del mismo archivo cuando hacen falta:
        `for_output(ruta, purpose="vehiculos")` no comparte extracciones con el
        flujo principal de esa ruta.
        """
        flujo = f"{output}#{purpose}" if purpose else output
        if flujo in self._entregados:
            msg = (
                f"el flujo '{flujo}' ya se entrego en esta generacion: dos piezas que lo "
                "compartieran harian las mismas elecciones (BR1.2)"
            )
            raise ValueError(msg)
        self._entregados.add(flujo)
        return SeededChooser(self._seed, flujo)
