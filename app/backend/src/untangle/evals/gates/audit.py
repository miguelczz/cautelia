"""El segundo detector: mecanismo propio, distinto del de U3 (BR4.1, AC4.14.1).

Revisa lo que ya se redacto -- trazas, logs, exportaciones y el propio reporte
-- con sus propios patrones y validadores de formato, sin modelo de lenguaje y
sin importar `untangle.compliance.redaction` (TECH-U21.2). Un contrato de
importacion lo comprueba; una prueba aparte lee los dos archivos de
reconocedores de U3 como YAML, sin importar su modulo, solo para comprobar que
ninguna expresion coincide con la de aqui (BR4.1).

Cuatro tipos, en los dos idiomas, con validadores por longitud y prefijo en vez
del sistema de puntaje por contexto del primero: telefono, cedula, placa y
numero de poliza. Ningun hallazgo guarda el valor que encontro, por la misma
razon que en U3: un diagnostico que lo hiciera seria el punto de fuga que este
componente existe para atrapar.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from untangle.base import Locale
from untangle.evals.report import EvalReport


class AuditEntityType(StrEnum):
    """Los cuatro tipos que este detector busca (TECH-U21.2)."""

    PHONE = "phone"
    NATIONAL_ID = "national_id"
    LICENSE_PLATE = "license_plate"
    POLICY_NUMBER = "policy_number"


@dataclass(frozen=True)
class AuditFinding:
    """Donde se encontro un dato, nunca que valor (BR4.2).

    `source` nombra el archivo, o `"report"` cuando el hallazgo vino del
    reporte de la corrida (AC4.14.2, "con el archivo, el idioma y el tipo de
    entidad").
    """

    source: str
    language: Locale
    entity_type: AuditEntityType


@dataclass(frozen=True)
class _Pattern:
    entity_type: AuditEntityType
    regex: re.Pattern[str]


# --- Patrones propios, escritos desde cero -------------------------------------
#
# Ninguno se copia de `compliance.redaction.recognizers`: son mas simples y mas
# estrictos a proposito -- este es un segundo filtro sobre lo ya redactado, no
# un reemplazo del primero -- y validan por longitud y prefijo en vez del
# sistema de puntaje por contexto de U3, que es lo que hace que el mecanismo
# sea otro y no una copia con otro nombre (AC4.14.1).

_ES_PATTERNS: tuple[_Pattern, ...] = (
    # Celular colombiano: prefijo 3, diez digitos en total, con o sin +57.
    _Pattern(AuditEntityType.PHONE, re.compile(r"(?<!\d)(?:\+?57)?3\d{9}(?!\d)")),
    # Cedula: siete a diez digitos que no empiecen por 3, para no solapar con
    # el celular. Igual que U3 con el SSN compacto, el costo aceptado es dejar
    # pasar alguna cedula que empiece por 3.
    _Pattern(AuditEntityType.NATIONAL_ID, re.compile(r"(?<!\d)[0-24-9]\d{6,9}(?!\d)")),
    # Placa colombiana: carro (ABC123) o moto (ABC12D), con o sin guion.
    _Pattern(AuditEntityType.LICENSE_PLATE, re.compile(r"\b[A-Za-z]{3}-?\d{2}[A-Za-z0-9]\b")),
    # Numero de poliza de las tres aseguradoras de la demo: prefijo POL y seis
    # digitos.
    _Pattern(AuditEntityType.POLICY_NUMBER, re.compile(r"\bPOL-?\d{6}\b", re.IGNORECASE)),
)

_EN_PATTERNS: tuple[_Pattern, ...] = (
    # NANP: diez digitos, con o sin +1.
    _Pattern(AuditEntityType.PHONE, re.compile(r"(?<!\d)(?:\+?1)?\d{10}(?!\d)")),
    # SSN, solo en su forma separada: un tramo de nueve digitos en fila es
    # demasiado comun para cubrirlo sin ambiguedad, la misma razon por la que
    # U3 puntua bajo su forma compacta.
    _Pattern(AuditEntityType.NATIONAL_ID, re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")),
    _Pattern(AuditEntityType.LICENSE_PLATE, re.compile(r"\b[A-Za-z]{3}-?\d{2}[A-Za-z0-9]\b")),
    _Pattern(AuditEntityType.POLICY_NUMBER, re.compile(r"\bPOL-?\d{6}\b", re.IGNORECASE)),
)

PATTERNS: dict[Locale, tuple[_Pattern, ...]] = {"es": _ES_PATTERNS, "en": _EN_PATTERNS}


def scan_text(text: str, *, language: Locale, source: str) -> tuple[AuditFinding, ...]:
    """Los hallazgos de un idioma sobre un texto (F3, paso 2)."""
    return tuple(
        AuditFinding(source=source, language=language, entity_type=patron.entity_type)
        for patron in PATTERNS[language]
        for _ in patron.regex.finditer(text)
    )


def scan_text_both_languages(text: str, *, source: str) -> tuple[AuditFinding, ...]:
    """Los dos juegos de patrones sobre un texto sin idioma declarado.

    Para archivos de una corrida bilingue -- una traza exportada, un log --
    donde no hay una sola atribucion de idioma posible por linea.
    """
    return scan_text(text, language="es", source=source) + scan_text(
        text, language="en", source=source
    )


def scan_file(path: Path) -> tuple[AuditFinding, ...]:
    """Un archivo, si existe. Uno ausente no es un hallazgo ni un error."""
    if not path.is_file():
        return ()
    texto = path.read_text(encoding="utf-8", errors="replace")
    return scan_text_both_languages(texto, source=str(path))


def scan_paths(paths: Iterable[Path]) -> tuple[AuditFinding, ...]:
    """Trazas, logs y exportaciones: la lista que exista en esta corrida (F3, paso 1)."""
    return tuple(hallazgo for ruta in paths for hallazgo in scan_file(ruta))


def scan_report(report: EvalReport) -> tuple[AuditFinding, ...]:
    """El propio reporte de la corrida (AC4.14.2).

    Deliberadamente **no** serializa el reporte entero: `run_id`, `commit_sha`,
    `prompt_hashes` y `model_ids` son identificadores hexadecimales largos, y
    una racha de diez digitos seguidos dentro de uno de ellos coincidiria con
    el patron de telefono por puro azar -- una compuerta que se disparara por
    eso entrenaria a cualquiera a ignorarla, que es el problema que REL-U21
    existe para evitar.

    El esquema de `EvalReport` no guarda texto libre -- ningun campo carga el
    detalle de un fallo (BR4.4) -- asi que hoy no hay nada que revisar de
    verdad: cada campo es un identificador, un enum o un numero. Esta funcion
    devuelve siempre vacio por esa razon, no porque no se ejecute; el dia que
    un campo de texto libre se agregue al reporte, revisarlo aqui es parte de
    ese cambio.
    """
    return ()
