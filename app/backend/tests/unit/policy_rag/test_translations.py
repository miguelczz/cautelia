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
    assert translations.part_text("Parte D", "en", root=tmp_path) is None
