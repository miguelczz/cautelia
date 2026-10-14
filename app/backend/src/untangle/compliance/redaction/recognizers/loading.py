"""Carga del juego de reconocedores de un idioma desde su archivo versionado.

Un archivo por idioma, en YAML porque lo escribe una persona (CD-4), y **dentro
del paquete** y no bajo `app/config/`: viaja con el despliegue, como los modelos,
porque un servicio que se duerme y despierta cada noche no puede depender de que
alguien haya copiado un archivo suelto para poder redactar.

La ruta es parte del contrato y no un detalle: U21 la lee **como archivo** para
comprobar que su segundo detector no comparte mecanismo con este, sin importar
ninguna pieza de este modulo (BR4.6, decision FD-U3-12).

Esta es la unica ruta del aplicativo que no se resuelve por `untangle.paths`, y
la razon es esa: `paths` resuelve archivos bajo `app/`, que existen en el
repositorio; estos viven dentro del paquete instalado y se resuelven desde el
propio modulo, que es lo unico que sigue siendo cierto dentro de una rueda.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, get_args

import yaml
from pydantic import ValidationError

from untangle.base import Locale
from untangle.compliance.redaction.recognizers.models import RecognizerSet

#: Los dos idiomas del producto, derivados del tipo para que anadir uno no exija
#: acordarse de tocar esta lista.
LOCALES: tuple[Locale, ...] = get_args(Locale)


class RecognizerLoadError(Exception):
    """El juego de reconocedores no se pudo cargar. El mensaje nombra el archivo.

    Es un fallo de arranque a proposito: si el detector no puede cargar sus
    reconocedores, el proceso no arranca (BR1.7, NFRD-U3-2). Un aplicativo vivo
    con la redaccion muerta parece que funciona, y ese es el peor estado posible
    para un control silencioso.
    """


def recognizers_dir() -> Path:
    """El directorio donde viven los archivos de reconocedores."""
    return Path(__file__).resolve().parent


def load_recognizer_set(language: Locale, root: Path | None = None) -> RecognizerSet:
    """El juego de un idioma, validado y nombrando el archivo en cada fallo."""
    directorio = root if root is not None else recognizers_dir()
    archivo = directorio / f"{language}.yaml"

    if not archivo.is_file():
        msg = (
            f"falta el juego de reconocedores del idioma '{language}': se esperaba "
            f"'{archivo}'. Sin el, ese idioma no se redacta y el fallo no avisa: "
            "el texto sale igual, solo que con el dato dentro."
        )
        raise RecognizerLoadError(msg)

    try:
        cargado: Any = yaml.safe_load(archivo.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        msg = f"no se pudo leer '{archivo}': {error}"
        raise RecognizerLoadError(msg) from error

    try:
        juego = RecognizerSet.model_validate(cargado)
    except ValidationError as error:
        # Se incluye el **mensaje** de cada problema y no solo la ruta del campo:
        # los validadores de los modelos nombran el reconocedor culpable, y
        # "recognizers.3" obliga a contar entradas a mano para saber cual es.
        problemas = "; ".join(
            f"{'.'.join(str(parte) for parte in problema['loc']) or '(raiz)'}: {problema['msg']}"
            for problema in error.errors()
        )
        msg = (
            f"el juego de reconocedores '{archivo}' no valida su esquema. "
            f"{problemas}. Los cinco campos obligatorios --identificador, tipo, "
            "idioma, mecanismo y procedencia-- no son ceremonia: un reconocedor a "
            "medias es un agujero que no avisa (BR2.6)"
        )
        raise RecognizerLoadError(msg) from error

    if juego.language != language:
        msg = f"'{archivo}' declara el idioma '{juego.language}' y se cargo como '{language}'"
        raise RecognizerLoadError(msg)

    return juego


def load_all(root: Path | None = None) -> dict[Locale, RecognizerSet]:
    """Los juegos de **los dos** idiomas.

    Los dos, siempre, sea cual sea el idioma del turno. Cargar solo el del turno
    es la forma natural de escribirlo y es exactamente el agujero de RT-15: una
    cedula dictada en espanol dentro de un turno en ingles saldria en claro, y
    BR2.3 --que es compuerta dura y existe precisamente para eso-- fallaria por
    construccion y no por un error de configuracion (BR2.9).
    """
    return {idioma: load_recognizer_set(idioma, root) for idioma in LOCALES}
