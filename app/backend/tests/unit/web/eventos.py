"""Captura de los eventos del punto unico de salida, para afirmar sobre ellos.

Se sustituye el destino de `observability` por un buffer y se devuelve una
funcion que lee lo escrito como una lista de eventos ya parseados. Al salir, el
destino vuelve a la salida estandar: es estado compartido entre pruebas, y una
prueba que lo dejara cambiado romperia la siguiente sin avisar.
"""

from __future__ import annotations

import io
import json
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from untangle import observability

type Eventos = Callable[[], list[dict[str, Any]]]


@contextmanager
def capturar() -> Iterator[Eventos]:
    destino = io.StringIO()
    observability.set_stream(destino)
    try:
        yield lambda: [json.loads(linea) for linea in destino.getvalue().splitlines() if linea]
    finally:
        observability.set_stream(sys.stdout)
