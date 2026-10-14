"""El adaptador de Gemini: **el unico sitio donde se importa su SDK** (BR1.2).

Un contrato `forbidden` de importacion lo comprueba en cada corrida del guion de
verificacion, y el contrato `protected` deja que solo la raiz de composicion
importe este paquete. Las dos reglas juntas son lo que hace cierto que ningun
nodo puede llamar al proveedor saltandose el puerto, la contabilidad y la traza.

Cinco piezas:

- `api.py` --los dos puertos que esta unidad implementa: generar y embeddings.
- `request.py` --como se arma la peticion, con la instruccion de sistema separada
  del contenido externo. Es el control `SEC-U5.16`.
- `errors.py` --la traduccion a los cuatro tipos, y la senal de parada que no es
  ninguno de ellos.
- `breaker.py` --el cortacircuitos, uno por pareja (proveedor, uso).
- `transport.py` --el cliente HTTP de verdad, el unico del aplicativo que habla
  por la red. Vive aqui dentro porque aqui es donde se puede importar un cliente
  de proveedor, y por eso el resto del aplicativo no tiene ninguno.
"""

from __future__ import annotations

from untangle.providers.adapters.gemini.api import (
    GeminiEmbedder,
    GeminiTextGenerator,
    ProviderMisconfiguredError,
)
from untangle.providers.adapters.gemini.breaker import (
    CircuitBreakerRegistry,
    CircuitState,
)

__all__ = [
    "CircuitBreakerRegistry",
    "CircuitState",
    "GeminiEmbedder",
    "GeminiTextGenerator",
    "ProviderMisconfiguredError",
]
