"""Las traducciones de referencia de las clausulas (decision de Miguel del 2026-10-08)."""

from __future__ import annotations

import json
from pathlib import Path

from untangle.policy_rag.corpus import translations


def test_lee_la_traduccion_de_una_clausula_y_de_su_parte(tmp_path: Path) -> None:
    (tmp_path / "es.json").write_text(
        json.dumps(
            {
                "language": "es",
                "parts": {"Endorsements": "Endosos"},
                "clauses": {"AP-PAP-2026-END-2-D.EXCL.5": "La exclusión de llantas no aplica."},
            }
        ),
        encoding="utf-8",
    )

    assert (
        translations.clause_text("AP-PAP-2026-END-2-D.EXCL.5", "es", root=tmp_path)
        == "La exclusión de llantas no aplica."
    )
    assert translations.part_text("Endorsements", "es", root=tmp_path) == "Endosos"


def test_sin_traduccion_no_se_inventa_ninguna(tmp_path: Path) -> None:
    assert translations.clause_text("X-1", "en", root=tmp_path) is None
    assert (
        translations.part_text("Pérdida del vehículo por daños y por hurto", "en", root=tmp_path)
        is None
    )


def _clausulas_de_las_emisoras() -> dict[str, tuple[str, str]]:
    """Cada clausula del corpus de las emisoras: su identificador, su idioma y su parte."""
    from untangle import paths

    encontradas: dict[str, tuple[str, str]] = {}
    for tenant in ("stonecroft", "sunmeadow"):
        for archivo in sorted((paths.corpus_tenants_dir() / tenant / "clauses").glob("*.json")):
            for clausula in json.loads(archivo.read_text(encoding="utf-8"))["clauses"]:
                encontradas[clausula["clause_id"]] = (clausula["language"], clausula["part"])
    return encontradas


def test_cada_clausula_de_una_emisora_tiene_su_traduccion_y_ninguna_sobra() -> None:
    """Ni una clave huerfana ni una faltante: las traducciones salen del texto vigente.

    `en.json` traduce las clausulas escritas en espanol y `es.json` las escritas en ingles; una
    clausula reescrita sin tocar su traduccion deja de mostrarse en el idioma de quien lee.
    """
    from untangle import paths

    corpus = _clausulas_de_las_emisoras()
    for destino, origen in (("en", "es"), ("es", "en")):
        archivo = paths.config_dir() / "corpus_translations" / f"{destino}.json"
        datos = json.loads(archivo.read_text(encoding="utf-8"))
        esperadas = {cid for cid, (idioma, _) in corpus.items() if idioma == origen}
        assert set(datos["clauses"]) == esperadas, destino
        partes = {parte for idioma, parte in corpus.values() if idioma == origen}
        assert set(datos["parts"]) == partes, destino
