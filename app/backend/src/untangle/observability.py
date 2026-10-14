"""El punto unico por el que sale un evento tecnico del aplicativo.

Una linea por evento, en formato estructurado, a la salida estandar. Existe como
punto unico y no como llamadas sueltas a `print` por una razon que se paga
despues: la regla del proyecto dice que un punto de salida nuevo sin redaccion
debe ser **imposible por construccion**, no detectable por disciplina.

U1 no redacta: el punto unico de redaccion es de U3. Lo que U1 deja hecho es el
sitio donde ese punto encaja -- un solo lugar que envolver -- en lugar de
docenas de llamadas repartidas que habria que encontrar una por una.

Aqui no entra texto de una persona. Los eventos de esta unidad llevan claves,
identificadores de caso y nombres de archivo, que son datos del proyecto y no de
nadie.
"""

from __future__ import annotations

import json
import sys
from typing import IO, Any

# La salida se puede sustituir en una prueba sin tocar `sys.stdout` global, que
# es estado compartido entre pruebas.
_destino: IO[str] = sys.stdout


def set_stream(stream: IO[str]) -> None:
    """Cambia la salida de los eventos. Solo lo usan las pruebas."""
    global _destino
    _destino = stream


def failure_location(error: BaseException) -> str:
    """El archivo y la linea del aplicativo donde nacio el error, sin su mensaje.

    El mensaje de un error puede llevar lo que escribio o dijo una persona; el archivo y
    la linea, no. Es el marco mas interno que cae dentro de `untangle/`, que es donde hay
    algo que arreglar: el de una biblioteca no dice por donde buscar. Vive aqui, que es lo
    unico que importan a la vez el chat y la llamada, para que los dos digan el sitio de
    la misma manera.

    Una biblioteca instalada dentro del repositorio (`.venv/.../site-packages`) tambien
    tiene `/untangle/` en su ruta cuando el repositorio se llama asi, y no cuenta.
    """
    propio = "desconocido"
    rastro = error.__traceback__
    while rastro is not None:
        archivo = rastro.tb_frame.f_code.co_filename
        if "/untangle/" in archivo and "/site-packages/" not in archivo:
            propio = f"{archivo.rsplit('/untangle/', 1)[1]}:{rastro.tb_lineno}"
        rastro = rastro.tb_next
    return propio


def emit(event: str, **fields: Any) -> None:
    """Escribe un evento estructurado, una linea.

    `event` es un nombre tecnico en ingles y de un conjunto conocido; los campos
    son datos del proyecto.
    """
    registro: dict[str, Any] = {"event": event, **fields}
    _destino.write(json.dumps(registro, ensure_ascii=False, sort_keys=True, default=str) + "\n")
    _destino.flush()
