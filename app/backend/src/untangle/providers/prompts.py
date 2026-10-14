"""El **unico** sitio que produce una instruccion de sistema (BR1.7, SEC-U5.16).

Un archivo por nodo y por idioma, versionado, con su identificador y su hash. El
hash viaja en la traza y en el registro de la corrida de evaluaciones, y
cambiarlo dispara la compuerta de evaluaciones como cualquier otro cambio de
codigo.

**Lo que hace este modulo imposible.** La firma de `load_system_instruction` no
acepta texto: recibe un identificador y un idioma, y el contenido sale del
archivo. No hay ningun argumento donde intercalar una instruccion escrita en
tiempo de ejecucion, asi que la posicion de instruccion del prompt no se puede
componer con nada que venga de fuera. Es una garantia mas fuerte que la del tipo
--que se borra en ejecucion, igual que `Redacted` en U3-- porque no depende de
que nadie recuerde usarlo.

**Lo que no hace.** No interpola variables. Un prompt con huecos que se rellenan
en tiempo de ejecucion es exactamente el punto donde se cuela una instruccion
ajena, y lo que el modelo necesita saber del caso entra como **contenido**, que
es la otra posicion. Si algun nodo necesitara una variante, es otro archivo con
su propio identificador y su propio hash, visible en un diff.

Los archivos los escriben las unidades que tienen nodos --U11 y U12-- en
`app/config/prompts/`. Esta unidad fija el formato, la ruta y el calculo del
hash; no inventa el contenido de un prompt que todavia no tiene dueno.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from untangle import paths
from untangle.base import Locale
from untangle.providers.ports import InstructionText, PromptRef, SystemInstruction

#: La extension de los archivos de prompt. Markdown porque son texto que una
#: persona lee y revisa en un diff.
PROMPT_SUFFIX = ".md"


class PromptNotFoundError(FileNotFoundError):
    """No existe el archivo de ese prompt en ese idioma.

    Falla en vez de caer a otro idioma. Una instruccion en el idioma equivocado
    produce una respuesta en el idioma equivocado, que es una regresion que el
    golden set ve caso por caso; un respaldo silencioso la esconderia detras de
    una respuesta que parece correcta.
    """


def prompt_path(prompt_id: str, locale: Locale, *, folder: Path | None = None) -> Path:
    """Donde vive el archivo de ese prompt y ese idioma.

    Un solo sitio calcula el nombre: si cada nodo lo compusiera, dos de ellos
    acabarian buscando en rutas distintas y el hash publicado dejaria de
    corresponder al archivo que se leyo.
    """
    base = folder if folder is not None else paths.prompts_dir()
    return base / f"{prompt_id}.{locale}{PROMPT_SUFFIX}"


def load_system_instruction(
    prompt_id: str, locale: Locale, *, folder: Path | None = None
) -> SystemInstruction:
    """La instruccion de sistema de ese nodo y ese idioma, con su hash.

    **No recibe texto y nunca lo va a recibir**: es lo que impide que la posicion
    de instruccion del prompt se componga con algo de origen externo.
    """
    ruta = prompt_path(prompt_id, locale, folder=folder)
    try:
        crudo = ruta.read_bytes()
    except OSError as error:
        msg = (
            f"no existe el prompt '{prompt_id}' en '{locale}': se busco en '{ruta}'. "
            "Cada nodo y cada idioma tienen su archivo versionado (BR1.7)"
        )
        raise PromptNotFoundError(msg) from error

    texto = crudo.decode("utf-8").strip()
    if not texto:
        msg = f"el prompt '{prompt_id}' en '{locale}' esta vacio: '{ruta}'"
        raise PromptNotFoundError(msg)

    return SystemInstruction(
        ref=PromptRef(
            prompt_id=prompt_id,
            locale=locale,
            # Sobre los **bytes** del archivo y no sobre el texto recortado: el
            # hash tiene que identificar lo que esta en el repositorio, para que
            # el diff y la compuerta hablen del mismo objeto.
            sha256=hashlib.sha256(crudo).hexdigest(),
        ),
        text=InstructionText(texto),
    )
