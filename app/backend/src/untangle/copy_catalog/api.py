"""Catalogo de textos: la unica fuente de texto visible del sistema (C-21).

Ninguna cadena visible para una persona se escribe en linea en un nodo, un
adaptador o una pantalla. Una frase escrita en linea se salta la paridad por
idioma y la revision de formas prohibidas, que son dos compuertas del proyecto.

El catalogo se carga una sola vez al arrancar el proceso y queda inmutable. No se
relee por llamada y no tiene invalidacion: un cambio de texto es un cambio de
archivo versionado y llega con un despliegue.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import NewType

from untangle import observability
from untangle.base import Locale
from untangle.copy_catalog.loading import LOCALES, load_catalog
from untangle.copy_catalog.models import CopyEntry, Surface

# Las claves son literales y jerarquicas con puntos (BR3.4). El tipo propio
# existe para que una cadena cualquiera no pase por clave sin que se note.
CopyKey = NewType("CopyKey", str)


class MissingVariableError(KeyError):
    """Una frase pide una variable que quien la resuelve no paso.

    Falla ruidosamente a proposito: una frase a medio sustituir que llega a una
    persona es peor que un fallo, porque nadie la ve hasta que ya salio.
    """


class Catalog:
    """El catalogo cargado. Inmutable desde que se construye."""

    def __init__(self, entries: Mapping[tuple[str, str], CopyEntry]) -> None:
        self._entries: dict[tuple[str, str], CopyEntry] = dict(entries)
        por_superficie: dict[Surface, set[CopyKey]] = {s: set() for s in Surface}
        for (clave, _), entrada in self._entries.items():
            por_superficie[entrada.surface].add(CopyKey(clave))
        self._by_surface: dict[Surface, frozenset[CopyKey]] = {
            superficie: frozenset(claves) for superficie, claves in por_superficie.items()
        }

    @property
    def entries(self) -> Mapping[tuple[str, str], CopyEntry]:
        return dict(self._entries)

    def keys(self) -> frozenset[CopyKey]:
        """Todas las claves del catalogo, sin repetir por idioma."""
        return frozenset(CopyKey(clave) for clave, _ in self._entries)

    def keys_for(self, surface: str) -> frozenset[CopyKey]:
        """Las claves de una superficie. Una superficie desconocida no lanza."""
        try:
            objetivo = Surface(surface)
        except ValueError:
            observability.emit("copy.unknown_surface", surface=surface)
            return frozenset()
        return self._by_surface.get(objetivo, frozenset())

    def t(self, key: CopyKey, *, locale: Locale, **vars: str) -> str:
        """La frase de una clave en un idioma, con sus variables sustituidas.

        Cuando la entrada falta se devuelve **la clave misma** y se registra el
        evento; nunca una cadena vacia. Una cadena vacia en pantalla parece un
        problema de maquetacion y se busca donde no es; la clave dice
        exactamente que falta.
        """
        entrada = self._entries.get((key, locale))
        if entrada is None:
            observability.emit("copy.missing_entry", key=key, locale=locale)
            return key

        if not vars:
            return entrada.text
        try:
            return entrada.text.format(**vars)
        except (KeyError, IndexError) as error:
            msg = f"la frase '{key}' ({locale}) pide una variable que no se paso: {error}"
            raise MissingVariableError(msg) from error


_catalog: Catalog | None = None


def install(catalog: Catalog) -> None:
    """Fija el catalogo del proceso. Lo llama la raiz de composicion (C-24)."""
    global _catalog
    _catalog = catalog


def load(root: Path | None = None) -> Catalog:
    """Carga el catalogo desde sus archivos. Falla nombrando el archivo."""
    return Catalog(load_catalog(root))


def get_catalog() -> Catalog:
    """El catalogo del proceso, cargandolo la primera vez si hace falta.

    El proceso servido lo instala en la raiz de composicion; el corredor y las
    pruebas usan esta misma carga, sin ruta especial.
    """
    global _catalog
    if _catalog is None:
        _catalog = load()
    return _catalog


def reset() -> None:
    """Olvida el catalogo cargado. Lo usan las pruebas para no compartir estado."""
    global _catalog
    _catalog = None


def t(key: CopyKey, *, locale: Locale, **vars: str) -> str:
    """La frase de una clave en un idioma (C-21)."""
    return get_catalog().t(key, locale=locale, **vars)


def keys_for(surface: str) -> frozenset[CopyKey]:
    """Las claves de una superficie (C-21)."""
    return get_catalog().keys_for(surface)


__all__ = [
    "LOCALES",
    "Catalog",
    "CopyKey",
    "MissingVariableError",
    "get_catalog",
    "install",
    "keys_for",
    "load",
    "reset",
    "t",
]
