"""El vocabulario con el que una unidad monta una superficie (U6, F8, BR5.2).

Una **superficie** es una parte del aplicativo que un visitante o una persona de
la bandeja puede abrir: el chat, la consola de voz, la comparacion, la bandeja,
la vista por enlace y los dos paneles. Lo que no esta montado no existe para la
interfaz ni para el chequeo periodico (FD-U6-1): el inicio no muestra su boton y
la salud no inventa su estado.

**Por que vive aqui, en la raiz del paquete, y no en `server/`.** Quien monta una
superficie es la unidad que la construye --el chat, la bandeja, la voz--, y esas
unidades estan **debajo** de `untangle.server` en el contrato de capas: no
pueden importarlo. Este modulo es una hoja sin dependencias del aplicativo, como
`base.py`, para que cualquiera pueda declarar su superficie sin arrastrar la
parte servida. El registro que las junta, las valida y corre sus sondas si es de
la parte servida, y vive en `untangle.server.surfaces`.

**La lista es cerrada**: siete superficies. La cotizacion no es una: vive dentro
del chat y de la bandeja (M12). Una superficie nueva es una entrada nueva aqui,
en el mismo cambio que la unidad que la monta.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum


class SurfaceId(StrEnum):
    """Las siete superficies del aplicativo. Lista cerrada (FD-U6-1)."""

    CHAT = "chat"
    VOICE_CONSOLE = "voice_console"
    COMPARISON = "comparison"
    INBOX = "inbox"
    CASE_LINK = "case_link"
    METRICS_PANEL = "metrics_panel"
    SPEND_PANEL = "spend_panel"


#: Las superficies que son **canales**: por donde un visitante reporta. Sin
#: ninguna montada, el inicio dice en una linea que la demostracion todavia no
#: tiene canales abiertos (BR4.3).
CHANNELS: frozenset[SurfaceId] = frozenset({SurfaceId.CHAT, SurfaceId.VOICE_CONSOLE})

#: El tiempo maximo que puede declarar una sonda, en milisegundos. Las sondas
#: corren en paralelo y la salud de listo tiene un segundo en total (C-02): con
#: medio segundo por sonda, la mas lenta todavia deja margen a la base.
MAX_PROBE_TIMEOUT_MS = 500

#: La comprobacion que corre una sonda. Levanta si la superficie no responde;
#: devolver es "responde". **No llama al modelo, a la voz ni a ningun
#: proveedor, no gasta y no consume limites de visitantes** (BR5.2, AC5.16.1).
type ProbeCheck = Callable[[], Awaitable[None]]


@dataclass(frozen=True)
class SurfaceProbe:
    """La comprobacion barata de que una superficie responde (BR5.2)."""

    check: ProbeCheck
    timeout_ms: int

    def __post_init__(self) -> None:
        if not 1 <= self.timeout_ms <= MAX_PROBE_TIMEOUT_MS:
            msg = (
                f"una sonda declara entre 1 y {MAX_PROBE_TIMEOUT_MS} ms de tiempo "
                f"maximo; declaro {self.timeout_ms}"
            )
            raise ValueError(msg)


@dataclass(frozen=True)
class SurfaceSpec:
    """Una superficie que una unidad monta en la raiz de composicion (C-24, F8).

    La unidad la devuelve desde `surfaces()` en el modulo que declara la
    capacidad `surfaces`. **La sonda es obligatoria**: la raiz se niega a
    arrancar, nombrando el modulo, si una superficie llega sin ella (BR5.2).
    """

    surface_id: SurfaceId
    #: La unidad que la monta, para leer el reporte de salud sin adivinar.
    owning_unit: str
    #: Si la ve un visitante sin credencial. La bandeja con credencial no.
    public: bool
    #: Si hay una por aseguradora (el chat) o una sola (los paneles).
    per_tenant: bool
    probe: SurfaceProbe
