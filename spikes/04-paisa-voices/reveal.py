#!/usr/bin/env python3
"""Experimento 4, paso 3: junta las planillas de audición y revela qué voz es cada código.

Cada persona que escucha copia score-sheet-template.csv a scores/<iniciales>.csv
y lo llena. La regla de la guía de voz: se adopta la primera voz que promedie 4 o
más en "suena de Medellín" y en "suena real".

Uso:
  python3 spikes/04-paisa-voices/reveal.py
"""

from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import common  # noqa: E402

BLIND_KEY = HERE / "blind-key.csv"
SCORES = HERE / "scores"
PASS_MARK = 4.0


def mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def read_score(value: str) -> float | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        number = float(value.replace(",", "."))
    except ValueError:
        return None
    return number if 1 <= number <= 5 else None


def main() -> None:
    if not BLIND_KEY.exists():
        sys.exit("Falta blind-key.csv. Corre primero synthesize.py.")
    sheets = sorted(SCORES.glob("*.csv")) if SCORES.exists() else []
    if not sheets:
        sys.exit("No hay planillas en scores/. Copia score-sheet-template.csv allí, una por persona.")

    with BLIND_KEY.open(encoding="utf-8") as handle:
        key = {row["code"]: row for row in csv.DictReader(handle)}

    scores: dict[str, dict[str, list[float]]] = {code: {"medellin": [], "real": [], "same": []} for code in key}
    listeners: dict[str, set[str]] = {code: set() for code in key}
    for sheet in sheets:
        with sheet.open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                code = row.get("code", "").strip()
                if code not in scores:
                    continue
                listeners[code].add(sheet.stem)
                lang = row.get("text_id", "").split("-", 1)[0]
                medellin = read_score(row.get("sounds_medellin_1_to_5", ""))
                real = read_score(row.get("sounds_real_1_to_5", ""))
                same = read_score(row.get("same_person_in_english_1_to_5", ""))
                if lang == "es" and medellin is not None:
                    scores[code]["medellin"].append(medellin)
                if real is not None:
                    scores[code]["real"].append(real)
                if lang == "en" and same is not None:
                    scores[code]["same"].append(same)

    latency: dict[str, list[float]] = {code: [] for code in key}
    runs = sorted((HERE / "results").glob("synthesis-*.json")) if (HERE / "results").exists() else []
    if runs:
        for row in json.loads(runs[-1].read_text(encoding="utf-8"))["measurements"]:
            if row.get("first_byte_ms") is not None and row["code"] in latency:
                latency[row["code"]].append(row["first_byte_ms"])

    results: list[dict[str, Any]] = []
    for code, voice in key.items():
        medellin = mean(scores[code]["medellin"])
        real = mean(scores[code]["real"])
        results.append(
            {
                "code": code,
                "provider": voice["provider"],
                "voice_id": voice["voice_id"],
                "name": voice["name"],
                "model": voice["model"],
                "listeners": len(listeners[code]),
                "sounds_medellin": medellin,
                "sounds_real": real,
                "same_person_in_english": mean(scores[code]["same"]),
                "first_byte_ms_p50": common.percentile(latency[code], 50),
                "passes": medellin is not None and real is not None and medellin >= PASS_MARK and real >= PASS_MARK,
            }
        )
    results.sort(key=lambda r: (not r["passes"], -((r["sounds_medellin"] or 0) + (r["sounds_real"] or 0))))

    path = common.write_results(
        HERE,
        "reveal",
        {
            "experiment": "04-paisa-voices",
            "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "pass_mark": PASS_MARK,
            "sheets": len(sheets),
            "voices": results,
        },
    )
    print(
        common.markdown_table(
            ["Código", "Proveedor", "Voz", "Personas", "Suena de Medellín", "Suena real", "Misma persona en inglés", "Primer byte p50 (ms)", "Pasa"],
            [
                [r["code"], r["provider"], r["name"], r["listeners"], r["sounds_medellin"], r["sounds_real"], r["same_person_in_english"], r["first_byte_ms_p50"], r["passes"]]
                for r in results
            ],
        )
    )
    print(f"\nResultado: {path.relative_to(HERE.parent.parent)}")


if __name__ == "__main__":
    main()
