"""Lo que las pruebas del ajustador de IA necesitan en la base efimera.

**No se construye un segundo juego de fixtures.** Los casos, el cifrador y el par de
aseguradoras que colisionan son los de la bandeja (U14), y el dinero vacio es el de U5: un doble
propio aqui seria uno escrito con lo que hacia falta para que esta pieza se viera, que es como se
aprueban pruebas que no prueban. Esta carpeta solo anade lo que pytest no hereda entre carpetas
hermanas.
"""

from __future__ import annotations

from ..u5.conftest import dinero
from ..u14.conftest import AHORA, app, base_de_u14, cifrador, dos_aseguradoras, nuevo_caso

__all__ = ["AHORA", "app", "base_de_u14", "cifrador", "dinero", "dos_aseguradoras", "nuevo_caso"]
