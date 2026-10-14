#!/usr/bin/env python3
"""Experimento 4, paso 1: busca voces femeninas colombianas o paisas en Cartesia y ElevenLabs.

Escribe candidates.json con cada voz encontrada y su enlace de muestra. Escucha
las muestras y marca "use": true en las que quieras audicionar (cinco como
máximo, para no gastar los créditos gratuitos). Volver a correrlo conserva las
marcas que ya pusiste.

Uso:
  python3 spikes/04-paisa-voices/find_voices.py
  python3 spikes/04-paisa-voices/find_voices.py --provider cartesia
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import common  # noqa: E402

CANDIDATES = HERE / "candidates.json"
CARTESIA_VERSION = "2026-08-14"
CARTESIA_QUERIES = [None, "colombia", "colombian", "medellin", "paisa", "latin"]
ELEVENLABS_QUERIES = ["medellin", "paisa", "colombian", "colombia"]


def relevance(*texts: Any) -> int:
    folded = common.fold(" ".join(str(t) for t in texts if t))
    if "medell" in folded or "paisa" in folded or "antioqu" in folded:
        return 2
    if "colomb" in folded:
        return 1
    return 0


def cartesia_voices(key: str) -> list[dict[str, Any]]:
    headers = {"Authorization": f"Bearer {key}", "Cartesia-Version": CARTESIA_VERSION}
    found: dict[str, dict[str, Any]] = {}
    for query in CARTESIA_QUERIES:
        params = {"language": "es", "gender": "feminine", "limit": "100", "expand[]": "preview_file_url"}
        if query:
            params["q"] = query
        url = f"https://api.cartesia.ai/voices?{urllib.parse.urlencode(params)}"
        response, _ = common.with_retries(lambda: common.request_json(url, headers, method="GET"))
        items = response.get("data", []) if isinstance(response, dict) else (response or [])
        for voice in items:
            found[voice["id"]] = {
                "provider": "cartesia",
                "voice_id": voice["id"],
                "name": voice.get("name"),
                "description": voice.get("description"),
                "accent": voice.get("accents") or voice.get("accent"),
                "language": voice.get("language"),
                "preview_url": voice.get("preview_file_url"),
                "free_users_allowed": True,
                "relevance": relevance(voice.get("name"), voice.get("description"), voice.get("accents")),
            }
    return list(found.values())


def elevenlabs_voices(key: str | None) -> list[dict[str, Any]]:
    headers = {"xi-api-key": key} if key else {}
    found: dict[str, dict[str, Any]] = {}
    for query in ELEVENLABS_QUERIES:
        params = {"search": query, "gender": "female", "page_size": "100"}
        url = f"https://api.elevenlabs.io/v1/shared-voices?{urllib.parse.urlencode(params)}"
        response, _ = common.with_retries(lambda: common.request_json(url, headers, method="GET"))
        for voice in (response or {}).get("voices", []):
            found[voice["voice_id"]] = {
                "provider": "elevenlabs",
                "voice_id": voice["voice_id"],
                "public_owner_id": voice.get("public_owner_id"),
                "name": voice.get("name"),
                "description": voice.get("description"),
                "accent": voice.get("accent"),
                "language": voice.get("language"),
                "preview_url": voice.get("preview_url"),
                "free_users_allowed": voice.get("free_users_allowed"),
                "relevance": relevance(voice.get("name"), voice.get("description"), voice.get("accent")),
            }
    return list(found.values())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--provider", choices=["cartesia", "elevenlabs"], help="solo un proveedor")
    args = parser.parse_args()
    common.load_env()

    voices: list[dict[str, Any]] = []
    if args.provider in (None, "cartesia"):
        key = common.require_env("CARTESIA_API_KEY", "la consola de Cartesia (play.cartesia.ai)")
        voices.extend(cartesia_voices(key))
    if args.provider in (None, "elevenlabs"):
        voices.extend(elevenlabs_voices(os.environ.get("ELEVENLABS_API_KEY") or None))

    previous: dict[tuple[str, str], bool] = {}
    if CANDIDATES.exists():
        for item in json.loads(CANDIDATES.read_text(encoding="utf-8")).get("voices", []):
            previous[(item["provider"], item["voice_id"])] = bool(item.get("use"))
    for voice in voices:
        voice["use"] = previous.get((voice["provider"], voice["voice_id"]), False)
    voices.sort(key=lambda v: (-v["relevance"], v["provider"], str(v["name"])))

    CANDIDATES.write_text(
        json.dumps({"voices": voices}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        common.markdown_table(
            ["Proveedor", "Nombre", "Acento", "Relevancia", "Usable gratis por API", "Muestra"],
            [
                [v["provider"], v["name"], v["accent"], v["relevance"], v["free_users_allowed"], v["preview_url"]]
                for v in voices
            ],
        )
    )
    print(f"\n{len(voices)} voces en {CANDIDATES.relative_to(HERE.parent.parent)}.")
    print('Escucha las muestras y marca "use": true en hasta cinco; después corre synthesize.py.')


if __name__ == "__main__":
    main()
