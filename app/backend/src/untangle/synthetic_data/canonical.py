"""La forma canonica de lo que se escribe, y su hash (BR1.1).

Dos corridas con la misma semilla y las mismas fuentes escriben **los mismos
bytes** en cualquier maquina. Para eso cada archivo JSON se escribe siempre asi:

- claves ordenadas, en todos los niveles;
- UTF-8 sin escapar (`ensure_ascii=False`): "Pólizas" se lee como tal en un diff;
- sangria de 2 espacios y un salto de linea LF al final;
- sin `NaN` ni infinitos, que no son JSON y cada lector interpreta a su manera.

Nada de esto depende del reloj, del sistema de archivos ni del orden en que se
recorrio un conjunto: lo que podria depender de un orden se ordena antes de
llegar aqui.

La escritura en disco es atomica por archivo: se escribe a un temporal en el
mismo directorio y se renombra encima. Un proceso cortado a mitad deja el archivo
viejo o el nuevo, nunca uno a medias.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel

__all__ = ["canonical_bytes", "sha256_hex", "write_atomic"]


def canonical_bytes(value: BaseModel | Any) -> bytes:
    """Los bytes canonicos de un modelo o de un valor JSON.

    Un modelo se vuelca en modo JSON antes: las fechas salen como `AAAA-MM-DD`,
    las tuplas como listas y los enums como su valor.
    """
    datos = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    texto = json.dumps(datos, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False)
    return (texto + "\n").encode("utf-8")


def sha256_hex(data: bytes) -> str:
    """El SHA-256 en hexadecimal: la forma en que el manifiesto nombra un contenido."""
    return hashlib.sha256(data).hexdigest()


def write_atomic(path: Path, data: bytes) -> None:
    """Escribe los bytes tal cual, sin traducir saltos de linea, y de una sola vez."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporal = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "wb") as archivo:
            archivo.write(data)
        Path(temporal).replace(path)
    except BaseException:
        Path(temporal).unlink(missing_ok=True)
        raise
