"""Las traducciones de referencia de las clausulas (decision de Miguel del 2026-10-08).

Hasta esta fecha la regla era no traducir nunca una clausula (BR4.2 de U13): se mostraba
en su idioma con un aviso. Miguel decidio que se lean en el idioma de la conversacion,
con el original a un clic, porque una persona que pregunta en espanol no podia
comprobar que la cita respondia lo que pregunto.

**El texto que rige sigue siendo el original.** La agente cita y el verificador
comprueba contra el original; la traduccion es solo para leer, se genero una vez, se
reviso y vive versionada en `app/config/corpus_translations/<idioma>.json`. Una
clausula sin traduccion se muestra en su idioma, como antes.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

from untangle import paths
from untangle.base import Locale


def _archivo(language: Locale, root: Path | None) -> Path:
    base = root if root is not None else paths.config_dir() / "corpus_translations"
    return base / f"{language}.json"


@cache
def _cargar(language: Locale, root: Path | None = None) -> tuple[dict[str, str], dict[str, str]]:
    ruta = _archivo(language, root)
    if not ruta.is_file():
        return {}, {}
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return dict(datos.get("clauses", {})), dict(datos.get("parts", {}))


def clause_text(clause_id: str, language: Locale, *, root: Path | None = None) -> str | None:
    """La traduccion de una clausula a `language`, o `None` si no hay."""
    return _cargar(language, root)[0].get(clause_id)


def part_text(part: str, language: Locale, *, root: Path | None = None) -> str | None:
    """El nombre de la parte en `language`, o `None` si no hay."""
    return _cargar(language, root)[1].get(part)


__all__ = ["clause_text", "part_text"]
