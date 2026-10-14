#!/usr/bin/env python3
"""Experimento 4, paso 2: sintetiza las frases de audición con cada voz marcada y mide la latencia.

Cada voz recibe un código al azar (V1, V2...). Los audios se guardan con ese
código para que la audición sea a ciegas; la correspondencia entre código y voz
queda en blind-key.csv, que git ignora. No abras ese archivo ni los resultados
antes de escuchar.

Uso:
  python3 spikes/04-paisa-voices/synthesize.py
  python3 spikes/04-paisa-voices/synthesize.py --cartesia-model sonic-3.6 --elevenlabs-model eleven_flash_v2_5
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import common  # noqa: E402

CANDIDATES = HERE / "candidates.json"
SAMPLES = HERE / "samples"
BLIND_KEY = HERE / "blind-key.csv"
SCORE_TEMPLATE = HERE / "score-sheet-template.csv"
CARTESIA_URL = "https://api.cartesia.ai/tts/bytes"
CARTESIA_VERSION = "2026-08-14"
ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream?output_format=mp3_44100_128"


def synthesize(voice: dict[str, Any], text: str, lang: str, keys: dict[str, str], models: dict[str, str]) -> tuple[bytes, str, float, float]:
    """Devuelve (audio, extensión, segundos al primer byte, segundos totales)."""
    if voice["provider"] == "cartesia":
        headers = {"Authorization": f"Bearer {keys['cartesia']}", "Cartesia-Version": CARTESIA_VERSION}
        payload = {
            "model_id": models["cartesia"],
            "transcript": text,
            "voice": {"id": voice["voice_id"]},
            "language": lang,
            "output_format": {"container": "wav", "encoding": "pcm_s16le", "sample_rate": 24000},
        }
        audio, first, total = common.with_retries(lambda: common.stream_bytes(CARTESIA_URL, headers, payload))
        return audio, "wav", first, total

    url = ELEVENLABS_URL.format(voice_id=voice["voice_id"])
    headers = {"xi-api-key": keys["elevenlabs"]}
    payload: dict[str, Any] = {"text": text, "model_id": models["elevenlabs"], "language_code": lang}
    try:
        audio, first, total = common.with_retries(lambda: common.stream_bytes(url, headers, payload))
    except common.HttpError as exc:
        # Algunos modelos no aceptan language_code: se reintenta sin él.
        if exc.status != 400 or "language" not in exc.body.lower():
            raise
        payload.pop("language_code")
        audio, first, total = common.with_retries(lambda: common.stream_bytes(url, headers, payload))
    return audio, "mp3", first, total


def save_as_wav(audio: bytes, extension: str, target: Path) -> Path:
    """Guarda todo como WAV para que el formato no delate al proveedor."""
    if extension == "wav":
        target.write_bytes(audio)
        return target
    if shutil.which("ffmpeg") is None:
        fallback = target.with_suffix(f".{extension}")
        fallback.write_bytes(audio)
        print("  aviso: sin ffmpeg el formato del archivo delata al proveedor", file=sys.stderr)
        return fallback
    with tempfile.NamedTemporaryFile(suffix=f".{extension}", delete=False) as handle:
        handle.write(audio)
        temporary = Path(handle.name)
    try:
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(temporary), "-ac", "1", "-ar", "24000", str(target)],
            check=True,
        )
    finally:
        temporary.unlink(missing_ok=True)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cartesia-model", default="sonic-3.6")
    parser.add_argument("--elevenlabs-model", default="eleven_flash_v2_5")
    parser.add_argument("--texts", help="identificadores de frase separados por comas")
    parser.add_argument("--yes", action="store_true", help="no pedir confirmación antes de gastar créditos")
    parser.add_argument("--no-warmup", action="store_true", help="no descartar la primera llamada por proveedor")
    args = parser.parse_args()
    common.load_env()

    if not CANDIDATES.exists():
        sys.exit("Falta candidates.json. Corre primero find_voices.py.")
    voices = [v for v in json.loads(CANDIDATES.read_text(encoding="utf-8"))["voices"] if v.get("use")]
    if not voices:
        sys.exit('Ninguna voz tiene "use": true en candidates.json.')
    if len(voices) > 5:
        print(f"aviso: marcaste {len(voices)} voces; cada una gasta créditos gratuitos.", file=sys.stderr)

    texts = json.loads((HERE / "texts.json").read_text(encoding="utf-8"))["texts"]
    if args.texts:
        wanted = {item.strip() for item in args.texts.split(",")}
        texts = [t for t in texts if t["id"] in wanted]

    providers = {v["provider"] for v in voices}
    keys: dict[str, str] = {}
    if "cartesia" in providers:
        keys["cartesia"] = common.require_env("CARTESIA_API_KEY", "la consola de Cartesia (play.cartesia.ai)")
    if "elevenlabs" in providers:
        keys["elevenlabs"] = common.require_env("ELEVENLABS_API_KEY", "la cuenta de ElevenLabs (elevenlabs.io)")
    models = {"cartesia": args.cartesia_model, "elevenlabs": args.elevenlabs_model}

    characters = sum(len(t["text"]) for t in texts) * len(voices)
    print(f"{len(voices)} voces × {len(texts)} frases = {characters} caracteres de los créditos gratuitos.")
    if not args.yes and input("¿Continuar? [s/N] ").strip().lower() not in {"s", "si", "sí", "y", "yes"}:
        return

    rng = random.SystemRandom()
    rng.shuffle(voices)
    codes = {f"V{index}": voice for index, voice in enumerate(voices, 1)}
    SAMPLES.mkdir(exist_ok=True)

    if not args.no_warmup:
        for provider in sorted(providers):
            sample = next(v for v in voices if v["provider"] == provider)
            try:
                synthesize(sample, "Hola.", "es", keys, models)
            except Exception as exc:  # noqa: BLE001 - el calentamiento no es una medición
                print(f"  aviso: calentamiento de {provider} falló ({common.classify_error(exc)})", file=sys.stderr)

    measurements: list[dict[str, Any]] = []
    for code, voice in codes.items():
        for text in texts:
            row: dict[str, Any] = {"code": code, "text_id": text["id"], "lang": text["lang"], "characters": len(text["text"])}
            try:
                audio, extension, first, total = synthesize(voice, text["text"], text["lang"], keys, models)
                saved = save_as_wav(audio, extension, SAMPLES / f"{code}-{text['id']}.wav")
                row.update(first_byte_ms=common.ms(first), total_ms=common.ms(total), file=saved.name)
                print(f"  {code} {text['id']}: primer byte {row['first_byte_ms']} ms")
            except Exception as exc:  # noqa: BLE001 - se registra y se sigue
                row.update(error=common.classify_error(exc), detail=str(exc)[:300])
                print(f"  {code} {text['id']}: {row['error']}", file=sys.stderr)
                reason = common.spend_stop_reason(exc)
                if reason:
                    # Sin saldo o sin permiso de plan, las demás frases de esta voz fallarían igual.
                    row["stopped"] = reason
                    measurements.append(row)
                    break
            measurements.append(row)
            time.sleep(0.5)

    with BLIND_KEY.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["code", "provider", "voice_id", "name", "model"])
        for code, voice in codes.items():
            writer.writerow([code, voice["provider"], voice["voice_id"], voice["name"], models[voice["provider"]]])

    rows = [(code, text["id"]) for code in codes for text in texts]
    rng.shuffle(rows)
    with SCORE_TEMPLATE.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["code", "text_id", "sounds_medellin_1_to_5", "sounds_real_1_to_5", "same_person_in_english_1_to_5", "comment"])
        for code, text_id in rows:
            writer.writerow([code, text_id, "", "", "", ""])

    path = common.write_results(
        HERE,
        "synthesis",
        {
            "experiment": "04-paisa-voices",
            "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "models": models,
            "voices": len(codes),
            "measurements": measurements,
        },
    )
    print(f"\nMuestras en {SAMPLES.relative_to(HERE.parent.parent)}/ y planilla en {SCORE_TEMPLATE.name}.")
    print(f"Latencias por código en {path.relative_to(HERE.parent.parent)} (no lo abras antes de escuchar).")


if __name__ == "__main__":
    main()
