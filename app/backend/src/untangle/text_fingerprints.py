"""Las huellas de texto: una sola normalizacion para sacarlas y para compararlas (U7).

Dos piezas usan esto, y tienen que normalizar **exactamente igual**:

- `mise run synthetic:fingerprints` (`untangle.synthetic_data.fingerprints`), que
  saca las huellas de los formularios de terceros y guarda solo sus SHA-256
  (BR5.1);
- `mise run content:check` (`untangle.evals.content_checks`), que normaliza cada
  clausula del corpus igual y busca esos hashes con umbral cero (BR5.2).

**Por que vive aqui, en la raiz del paquete, y no en ninguno de los dos.** El
corredor de evaluaciones no puede importar el generador (BR8.1, contrato de
importacion), y el generador no puede importar el corredor (el codigo de
produccion no importa `untangle.evals`). Dos normalizaciones escritas por
separado acabarian divergiendo, y una compuerta que normaliza distinto de lo que
se guardo mide otra cosa sin avisar: pasaria en verde con el texto copiado. Por
eso hay una sola, en un modulo que los dos pueden importar, como `paths` o
`base`. No importa nada del aplicativo salvo `paths`.

**La normalizacion, en el orden en que se aplica** (su version entra en el
archivo de huellas, y la compuerta se niega a comparar contra otra):

1. NFKD sin tildes y en minusculas: "Poliza" y "poliza" son la misma palabra.
2. Palabras de letras y digitos; todo lo demas separa. Un guion al final de linea
   seguido de minuscula une la palabra partida, que es como la parte el PDF.
3. Sin los **encabezados de la referencia** de estructura, como secuencias de
   palabras y no como lineas: el PDF de la edicion de 2018 parte "Part D --
   Coverage for Damage to Your Auto" en dos lineas. La estructura esta permitida
   y documentada (`docs/reference/estructura-poliza-iso-pap.md`); lo prohibido es
   el texto de clausula (P8).
4. Sin la **numeracion**: digitos, letras sueltas y numerales romanos. "A.",
   "(1)" y "iv)" son estructura.
5. Ventanas de ocho palabras seguidas, y el SHA-256 de cada una unida por un
   espacio.

Todo se aplica **a los dos lados**, asi que una copia exacta sigue siendo una
copia exacta despues de normalizar: quitar un encabezado o una letra suelta
nunca esconde un calco. Lo que no detecta es una traduccion, y ese riesgo lo
cubre la muestra humana (BR5.4).
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import yaml

from untangle import paths

__all__ = [
    "NORMALIZATION_VERSION",
    "SHINGLE_SIZE",
    "FingerprintSettings",
    "SettingsError",
    "load_settings",
    "normalized_words",
    "shingle_hashes",
]

#: Cuantas palabras seguidas forman una huella (BR5.1, Q3).
SHINGLE_SIZE: Final = 8

#: La version de la normalizacion. Cambiarla deja las huellas guardadas sin
#: comparar hasta que se vuelvan a sacar, y la compuerta lo dice como "no medido".
NORMALIZATION_VERSION: Final = "v1"

#: La seccion de `app/config/content-checks.yaml` que gobierna las huellas.
SECCION: Final = "third_party_text"

#: Numerales romanos de mas de una letra. Los de una sola letra ya caen como
#: letras sueltas.
_ROMANOS: Final = frozenset({"ii", "iii", "iv", "vi", "vii", "viii", "ix", "xi", "xii"})

_PALABRA = re.compile(r"[a-z0-9]+")
_PALABRA_PARTIDA = re.compile(r"(?<=[A-Za-z])-\n(?=[a-z])")
_DIGITOS = re.compile(r"\d+")


class SettingsError(ValueError):
    """La seccion de huellas falta o no se puede leer. El mensaje nombra el archivo."""


def _sin_tildes_en_minusculas(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFKD", texto.casefold())
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def _palabras(texto: str) -> list[str]:
    unido = _PALABRA_PARTIDA.sub("", texto)
    return _PALABRA.findall(_sin_tildes_en_minusculas(unido))


def _es_numeracion(palabra: str) -> bool:
    return len(palabra) == 1 or palabra in _ROMANOS or _DIGITOS.fullmatch(palabra) is not None


def _sin_encabezados(palabras: Sequence[str], encabezados: Sequence[tuple[str, ...]]) -> list[str]:
    """Quita cada encabezado donde aparezca, del mas largo al mas corto.

    Del mas largo primero para que "Part A -- Liability Coverage" se quite entero
    antes de que "Agreement" o una palabra suelta se lleve solo un trozo.
    """
    ordenados = sorted(encabezados, key=len, reverse=True)
    restantes: list[str] = []
    indice = 0
    while indice < len(palabras):
        for encabezado in ordenados:
            largo = len(encabezado)
            if tuple(palabras[indice : indice + largo]) == encabezado:
                indice += largo
                break
        else:
            restantes.append(palabras[indice])
            indice += 1
    return restantes


def normalized_words(text: str, headings: Sequence[tuple[str, ...]]) -> tuple[str, ...]:
    """Las palabras de un texto despues de normalizarlo (pasos 1 a 4 del modulo)."""
    sin_encabezados = _sin_encabezados(_palabras(text), headings)
    return tuple(palabra for palabra in sin_encabezados if not _es_numeracion(palabra))


def shingle_hashes(words: Sequence[str], size: int = SHINGLE_SIZE) -> frozenset[str]:
    """El SHA-256 de cada ventana de `size` palabras seguidas (paso 5).

    Un texto con menos palabras que la ventana no tiene huellas: no puede
    compartir una secuencia de ocho palabras con nada.
    """
    if size < 1:
        msg = f"una ventana de {size} palabras no es una ventana"
        raise ValueError(msg)
    return frozenset(
        hashlib.sha256(" ".join(words[inicio : inicio + size]).encode("utf-8")).hexdigest()
        for inicio in range(len(words) - size + 1)
    )


@dataclass(frozen=True)
class FingerprintSettings:
    """Lo que declara la seccion `third_party_text` de los chequeos de contenido."""

    #: El archivo de huellas, relativo a la raiz del repositorio.
    shingles_file: str
    #: Donde vive el corpus que se compara, relativo a la raiz.
    corpus: str
    #: Los encabezados de la referencia, ya normalizados como secuencias.
    structure_headings: tuple[tuple[str, ...], ...]
    shingle_size: int = SHINGLE_SIZE

    @property
    def normalization(self) -> str:
        """La normalizacion con su version y la huella de la lista de encabezados.

        Es lo que se escribe en el archivo de huellas y lo que la compuerta exige
        encontrar: si cambia la lista de encabezados sin volver a sacar las
        huellas, las dos normalizaciones ya no son la misma y comparar no mide
        nada.
        """
        lista = "\n".join(" ".join(encabezado) for encabezado in self.structure_headings)
        huella = hashlib.sha256(lista.encode("utf-8")).hexdigest()[:12]
        return (
            f"{NORMALIZATION_VERSION}: nfkd sin tildes y en minusculas; palabras de letras "
            "y digitos; sin los encabezados de la referencia "
            f"(sha256:{huella}); sin numeracion (digitos, letras sueltas y romanos); "
            f"ventanas de {self.shingle_size} palabras unidas por un espacio; sha256"
        )

    def fingerprint(self, text: str) -> frozenset[str]:
        """Las huellas de un texto con esta normalizacion."""
        return shingle_hashes(
            normalized_words(text, self.structure_headings), size=self.shingle_size
        )


def _encabezados(crudos: Iterable[Any]) -> tuple[tuple[str, ...], ...]:
    vistos: dict[tuple[str, ...], None] = {}
    for crudo in crudos:
        palabras = tuple(_palabras(str(crudo)))
        if palabras:
            vistos.setdefault(palabras, None)
    return tuple(vistos)


def settings_path(root: Path) -> Path:
    """Donde se declaran: la lista versionada de los chequeos de contenido."""
    return root / "app" / "config" / "content-checks.yaml"


def load_settings(root: Path | None = None) -> FingerprintSettings:
    """Lee la seccion de huellas. Falla nombrando el archivo si falta algo."""
    base = root if root is not None else paths.repo_root()
    archivo = settings_path(base)
    try:
        cargado: Any = yaml.safe_load(archivo.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as error:
        msg = f"no se pudo leer '{archivo}': {error}"
        raise SettingsError(msg) from error

    seccion = cargado.get(SECCION) if isinstance(cargado, dict) else None
    if not isinstance(seccion, dict):
        msg = f"'{archivo}' no declara la seccion '{SECCION}' de las huellas de terceros"
        raise SettingsError(msg)

    faltan = [
        clave
        for clave in ("shingles_file", "corpus", "structure_headings")
        if not seccion.get(clave)
    ]
    if faltan:
        msg = f"la seccion '{SECCION}' de '{archivo}' no declara {faltan}"
        raise SettingsError(msg)

    encabezados = _encabezados(seccion["structure_headings"])
    if not encabezados:
        msg = f"la seccion '{SECCION}' de '{archivo}' no trae ningun encabezado"
        raise SettingsError(msg)

    return FingerprintSettings(
        shingles_file=str(seccion["shingles_file"]),
        corpus=str(seccion["corpus"]),
        structure_headings=encabezados,
    )
