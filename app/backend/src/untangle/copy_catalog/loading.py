"""Carga del catalogo de textos desde sus archivos por idioma.

El catalogo se lee una sola vez al arrancar el proceso y queda en memoria como
estructura inmutable (diseno de rendimiento): no se relee por llamada y no tiene
invalidacion, porque no cambia en caliente -- un cambio de texto es un cambio de
archivo versionado y llega con un despliegue.

Si un archivo no esta, falla al arrancar nombrandolo, no en la primera frase que
alguien pida.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any, get_args

import yaml
from pydantic import ValidationError

from untangle import paths
from untangle.base import Locale
from untangle.copy_catalog.models import CopyEntry

# Los dos idiomas, derivados del tipo para que anadir uno no exija acordarse de
# tocar esta lista.
LOCALES: tuple[Locale, ...] = get_args(Locale)


class CatalogLoadError(Exception):
    """El catalogo no se pudo cargar. El mensaje nombra el archivo."""


def _flatten(node: Any, prefix: str = "") -> dict[str, Any]:
    """Aplana el arbol de un archivo de catalogo en claves con puntos.

    El archivo se escribe anidado porque asi lo lee una persona; la clave que
    consume el codigo es siempre literal y con puntos (BR3.4).
    """
    plano: dict[str, Any] = {}
    if not isinstance(node, dict):
        return {prefix: node} if prefix else {}

    for bruto, valor in node.items():
        clave = f"{prefix}.{bruto}" if prefix else str(bruto)
        if isinstance(valor, dict) and "text" not in valor:
            plano.update(_flatten(valor, clave))
        else:
            plano[clave] = valor
    return plano


def load_locale_file(path: Path, locale: Locale) -> tuple[CopyEntry, ...]:
    """Las entradas de un idioma, en orden estable por clave."""
    if not path.is_file():
        msg = f"falta el archivo de catalogo del idioma '{locale}': se esperaba '{path}'"
        raise CatalogLoadError(msg)

    try:
        crudo = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        msg = f"no se pudo leer el catalogo '{path}': {error}"
        raise CatalogLoadError(msg) from error

    if crudo is None:
        crudo = {}
    if not isinstance(crudo, dict):
        msg = f"el catalogo '{path}' no contiene un mapa en su raiz"
        raise CatalogLoadError(msg)

    entradas: list[CopyEntry] = []
    for clave, valor in sorted(_flatten(crudo).items()):
        if not isinstance(valor, dict):
            msg = f"la entrada '{clave}' de '{path}' no es un mapa con al menos 'text' y 'surface'"
            raise CatalogLoadError(msg)
        try:
            entradas.append(CopyEntry.model_validate({**valor, "key": clave, "locale": locale}))
        except ValidationError as error:
            msg = f"la entrada '{clave}' de '{path}' no valida su esquema: {error}"
            raise CatalogLoadError(msg) from error

    return tuple(entradas)


def load_raw_entries(root: Path | None = None) -> dict[tuple[str, str], dict[str, Any]]:
    """Las entradas de los dos idiomas **sin validar** contra el modelo.

    Existe para los chequeos: si validaran, una entrada rota reventaria la carga
    con una traza y el chequeo no llegaria a decir que clave es la culpable. El
    modelo sigue siendo la ultima linea de defensa en la carga del proceso.
    """
    directorio = root if root is not None else paths.copy_dir()
    crudas: dict[tuple[str, str], dict[str, Any]] = {}

    for locale in LOCALES:
        archivo = directorio / f"{locale}.yaml"
        if not archivo.is_file():
            msg = f"falta el archivo de catalogo del idioma '{locale}': se esperaba '{archivo}'"
            raise CatalogLoadError(msg)
        try:
            cargado = yaml.safe_load(archivo.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as error:
            msg = f"no se pudo leer el catalogo '{archivo}': {error}"
            raise CatalogLoadError(msg) from error
        if not isinstance(cargado, dict):
            msg = f"el catalogo '{archivo}' no contiene un mapa en su raiz"
            raise CatalogLoadError(msg)

        for clave, valor in sorted(_flatten(cargado).items()):
            crudas[(clave, locale)] = valor if isinstance(valor, dict) else {"text": valor}

    return crudas


def load_catalog(root: Path | None = None) -> Mapping[tuple[str, str], CopyEntry]:
    """El catalogo completo de los dos idiomas, como estructura inmutable.

    La inmutabilidad no es decoracion: el catalogo se comparte entre el proceso
    servido, el corredor y las pruebas, y un mapa mutable compartido es una
    diferencia entre dos corridas esperando a ocurrir.
    """
    directorio = root if root is not None else paths.copy_dir()
    entradas: dict[tuple[str, str], CopyEntry] = {}

    for locale in LOCALES:
        for entrada in load_locale_file(directorio / f"{locale}.yaml", locale):
            entradas[(entrada.key, entrada.locale)] = entrada

    return MappingProxyType(entradas)
