"""Las huellas de los formularios de terceros: solo hashes (U7, F4, BR5.1, SEC-U7.2).

`mise run synthetic:fingerprints` lee los specimens publicos que Miguel deja en
`tmp/specimens/` --que git ignora--, los normaliza con la misma normalizacion que
la compuerta (`untangle.text_fingerprints`), corta secuencias de ocho palabras y
guarda **solo el SHA-256 de cada una** en `app/config/content/third-party-shingles.json`.

Tres cosas que este modulo no hace, y cada una es un control:

- **No guarda texto.** El archivo de huellas solo admite hashes de 64 digitos
  hexadecimales y los datos del specimen (formulario, edicion, publicador, fecha
  y hash del archivo), y el modelo no admite campos de mas.
- **No imprime texto.** Lo que sale por pantalla son recuentos: un specimen en un
  log es un specimen en el repositorio el dia que alguien pega ese log.
- **No lo usa la composicion.** El generador no lee `tmp/`, y la compuerta vive en
  `content:check`: estas huellas se comparan con el corpus ya escrito, nunca
  entran en el.

`pypdf` es dependencia **de desarrollo** (CG-U7-5): este comando corre a mano en
la maquina de quien opera y nunca en el despliegue. Se importa al leer un PDF, y
si falta, el mensaje dice como instalarla.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from untangle.synthetic_data import canonical
from untangle.synthetic_data.models import FingerprintSet, FingerprintSource
from untangle.text_fingerprints import FingerprintSettings

__all__ = [
    "FingerprintError",
    "SpecimenFile",
    "build_fingerprint_set",
    "load_fingerprint_set",
    "read_specimen",
    "write_fingerprint_set",
]

#: Lo que el comando sabe leer: el PDF que publica el regulador, o su texto plano
#: si la extraccion del PDF falla (CG-U7-5).
FORMATOS = (".pdf", ".txt")


class FingerprintError(RuntimeError):
    """No se pudieron sacar las huellas. El mensaje nombra el archivo, nunca su texto."""


@dataclass(frozen=True)
class SpecimenFile:
    """Un specimen en disco y lo que se sabe de el. El texto no viaja aqui."""

    path: Path
    form: str
    edition: str
    publisher: str
    retrieved_at: date


def read_specimen(path: Path) -> str:
    """El texto de un specimen, para normalizarlo en memoria y descartarlo."""
    if path.suffix.lower() not in FORMATOS:
        msg = f"'{path.name}' no es un PDF ni texto plano: el comando lee {', '.join(FORMATOS)}"
        raise FingerprintError(msg)
    if not path.is_file():
        msg = f"no esta el specimen '{path}'"
        raise FingerprintError(msg)
    if path.suffix.lower() == ".txt":
        return path.read_text(encoding="utf-8")
    return _texto_de_pdf(path)


def _texto_de_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
    except ImportError as error:  # pragma: no cover - depende del entorno instalado
        msg = (
            "falta pypdf, que es dependencia de desarrollo: instale con "
            "`uv sync --locked --project app/backend --all-groups`"
        )
        raise FingerprintError(msg) from error
    try:
        lector = PdfReader(path)
        return "\n".join((pagina.extract_text() or "") for pagina in lector.pages)
    except (PdfReadError, OSError, ValueError) as error:
        msg = (
            f"no se pudo extraer el texto de '{path.name}': {type(error).__name__}. "
            "Si el PDF no se deja leer, deje su texto plano como .txt junto a el"
        )
        raise FingerprintError(msg) from error


def build_fingerprint_set(
    specimens: Sequence[SpecimenFile], settings: FingerprintSettings
) -> tuple[FingerprintSet, dict[str, int]]:
    """Las huellas de todos los specimens, y cuantas aporta cada uno.

    Un specimen sin ninguna secuencia de ocho palabras falla: o no se extrajo su
    texto, o no es un formulario, y en los dos casos guardar cero huellas de el
    dejaria la compuerta pasando sin haber comparado nada.
    """
    if not specimens:
        msg = "no se paso ningun specimen: sin huellas, la compuerta queda no medida"
        raise FingerprintError(msg)

    huellas: set[str] = set()
    fuentes: list[FingerprintSource] = []
    por_specimen: dict[str, int] = {}
    for specimen in specimens:
        contenido = specimen.path.read_bytes() if specimen.path.is_file() else b""
        propias = settings.fingerprint(read_specimen(specimen.path))
        if not propias:
            msg = (
                f"'{specimen.path.name}' no dio ninguna secuencia de {settings.shingle_size} "
                "palabras: o no se extrajo su texto, o no es un formulario"
            )
            raise FingerprintError(msg)
        huellas.update(propias)
        por_specimen[specimen.path.name] = len(propias)
        fuentes.append(
            FingerprintSource(
                form=specimen.form,
                edition=specimen.edition,
                publisher=specimen.publisher,
                retrieved_at=specimen.retrieved_at,
                file_sha256=canonical.sha256_hex(contenido),
            )
        )

    conjunto = FingerprintSet(
        shingle_size=settings.shingle_size,
        normalization=settings.normalization,
        sources=tuple(sorted(fuentes, key=lambda f: (f.form, f.edition, f.file_sha256))),
        hashes=tuple(sorted(huellas)),
    )
    return conjunto, por_specimen


def write_fingerprint_set(fingerprints: FingerprintSet, destination: Path) -> None:
    """Escribe el archivo de huellas en forma canonica: mismos specimens, mismos bytes."""
    canonical.write_atomic(destination, canonical.canonical_bytes(fingerprints))


def load_fingerprint_set(path: Path) -> FingerprintSet:
    """El archivo de huellas, validado contra su modelo."""
    try:
        return FingerprintSet.model_validate_json(path.read_bytes())
    except OSError as error:
        msg = f"no se pudo leer '{path}': {error}"
        raise FingerprintError(msg) from error
    except ValueError as error:
        msg = f"'{path}' no valida el modelo de huellas: {error}"
        raise FingerprintError(msg) from error
