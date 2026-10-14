#!/usr/bin/env python3
"""Experimento 3: transcribe las grabaciones con Deepgram y mide dos cosas.

1. Error por palabra (WER) en las frases conversacionales, con acento paisa.
2. Si los datos dictados (placa, póliza, cédula, teléfono, número de caso)
   llegan exactos a la transcripción.

Responde el riesgo R4 del PRD: si el WER en español supera el 15 %, el riesgo
se dispara.

Uso:
  python3 spikes/03-spanish-stt/transcribe.py --dry-run
  python3 spikes/03-spanish-stt/transcribe.py
  python3 spikes/03-spanish-stt/transcribe.py --speaker miguel --variants-es nova-3:es,nova-3:multi
  python3 spikes/03-spanish-stt/transcribe.py --rescore spikes/03-spanish-stt/results/spanish-stt-<fecha>.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import common  # noqa: E402

RECORDINGS = HERE / "recordings"
LISTEN_URL = "https://api.deepgram.com/v1/listen"
CONTENT_TYPES = {".wav": "audio/wav", ".m4a": "audio/mp4", ".mp3": "audio/mpeg", ".webm": "audio/webm"}
R4_THRESHOLD = 0.15

NUMBER_WORDS = {
    "es": [
        "cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez",
        "once", "doce", "trece", "catorce", "quince", "dieciseis", "diecisiete", "dieciocho",
        "diecinueve", "veinte", "veintiuno", "veintidos", "veintitres", "veinticuatro",
        "veinticinco", "veintiseis", "veintisiete", "veintiocho", "veintinueve", "treinta",
    ],
    "en": [
        "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
        "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
        "nineteen", "twenty", "twenty one", "twenty two", "twenty three", "twenty four",
        "twenty five", "twenty six", "twenty seven", "twenty eight", "twenty nine", "thirty",
    ],
}
DIGIT_WORDS = {
    word: str(index)
    for lang in ("es", "en")
    for index, word in enumerate(NUMBER_WORDS[lang][:10])
}
# Palabras que el hablante dice entre partes de un código y que no forman parte del dato.
FILLERS = {"guion", "dash", "hyphen"}


def wer_tokens(text: str, lang: str) -> list[str]:
    """Normaliza para el WER: sin tildes, sin puntuación y con los números en palabras."""
    tokens: list[str] = []
    for token in re.sub(r"[^a-z0-9 ]+", " ", common.fold(text)).split():
        if token.isdigit() and int(token) < len(NUMBER_WORDS[lang]):
            tokens.extend(NUMBER_WORDS[lang][int(token)].split())
        else:
            tokens.append(token)
    return tokens


def edit_distance(reference: list[str], hypothesis: list[str]) -> int:
    previous = list(range(len(hypothesis) + 1))
    for i, ref_token in enumerate(reference, 1):
        current = [i] + [0] * len(hypothesis)
        for j, hyp_token in enumerate(hypothesis, 1):
            current[j] = min(
                previous[j] + 1,
                current[j - 1] + 1,
                previous[j - 1] + (ref_token != hyp_token),
            )
        previous = current
    return previous[-1]


def entity_stream(text: str) -> str:
    """Letras y dígitos seguidos, con los dígitos dichos en palabras ya convertidos."""
    # El formato inteligente a veces pega al código el separador dicho ("SUNDash610447").
    folded = re.sub(r"(?<=[a-z0-9])(" + "|".join(sorted(FILLERS)) + r")(?=[a-z0-9])", " ", common.fold(text))
    tokens = [t for t in re.split(r"[^0-9a-z]+", folded) if t and t not in FILLERS]
    return "".join(DIGIT_WORDS.get(token, token) for token in tokens).upper()


def discover(speaker: str | None, take: str | None) -> list[dict[str, Any]]:
    phrases = {p["id"]: p for p in json.loads((HERE / "script.json").read_text(encoding="utf-8"))["phrases"]}
    found: list[dict[str, Any]] = []
    if not RECORDINGS.exists():
        return found
    for path in sorted(RECORDINGS.glob("*/*/*")):
        if path.suffix.lower() not in CONTENT_TYPES:
            continue
        person, condition = path.parent.parent.name, path.parent.name
        if (speaker and person != speaker) or (take and condition != take):
            continue
        phrase = phrases.get(path.stem)
        if phrase is None:
            print(f"aviso: {path.relative_to(HERE)} no corresponde a ninguna frase del guion", file=sys.stderr)
            continue
        found.append({"path": path, "speaker": person, "take": condition, "phrase": phrase})
    return found


def transcribe(path: Path, model: str, language: str, smart: bool, key: str) -> tuple[str, Any, float]:
    params = {
        "model": model,
        "language": language,
        "smart_format": "true" if smart else "false",
        "punctuate": "true",
    }
    url = f"{LISTEN_URL}?{urllib.parse.urlencode(params)}"
    headers = {"Authorization": f"Token {key}", "Content-Type": CONTENT_TYPES[path.suffix.lower()]}
    body = path.read_bytes()
    response, seconds = common.with_retries(lambda: common.post_binary(url, headers, body))
    alternative = response["results"]["channels"][0]["alternatives"][0]
    return alternative.get("transcript", ""), alternative.get("confidence"), seconds


def score_row(row: dict[str, Any], phrase: dict[str, Any]) -> None:
    """Añade al resultado de una llamada sus errores por palabra o sus datos exactos."""
    if phrase["kind"] == "conversation":
        reference = wer_tokens(phrase["text"], phrase["lang"])
        row["reference_words"] = len(reference)
        row["edits"] = edit_distance(reference, wer_tokens(row["transcript"], phrase["lang"]))
    else:
        stream = entity_stream(row["transcript"])
        row["entities"] = [{**entity, "found": entity["value"].upper() in stream} for entity in phrase["entities"]]


def print_summary(summary: list[dict[str, Any]]) -> None:
    print(
        "\n"
        + common.markdown_table(
            ["Variante", "Idioma", "Grabaciones", "WER conversación", "Dispara R4", "Datos exactos", "Confianza media"],
            [
                [s["variant"], s["lang"], s["recordings"], s["conversation_wer"], s["r4_triggered"], s["entities_exact"], s["mean_confidence"]]
                for s in summary
            ],
        )
    )


def rescore(source: Path) -> None:
    """Recalcula un resultado guardado con la normalización vigente, sin volver a llamar a Deepgram."""
    data = json.loads(source.read_text(encoding="utf-8"))
    phrases = {p["id"]: p for p in json.loads((HERE / "script.json").read_text(encoding="utf-8"))["phrases"]}
    rows = data["rows"]
    for row in rows:
        if "transcript" in row:
            score_row(row, phrases[row["id"]])
    summary = summarize(rows)
    path = common.write_results(
        HERE,
        "spanish-stt",
        {
            **data,
            "rescored_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "rescored_from": source.name,
            "summary": summary,
            "rows": rows,
        },
    )
    print_summary(summary)
    print(f"\nResultado recalculado: {path}")


def parse_variants(text: str) -> list[tuple[str, str]]:
    variants = []
    for item in text.split(","):
        model, _, language = item.strip().partition(":")
        if not model or not language:
            sys.exit(f"Variante inválida {item!r}: usa modelo:idioma, por ejemplo nova-3:es")
        variants.append((model, language))
    return variants


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault((row["variant"], row["lang"]), []).append(row)
    summary = []
    for (variant, lang), items in sorted(groups.items()):
        conversation = [r for r in items if r["kind"] == "conversation" and "edits" in r]
        entities = [e for r in items if r["kind"] == "entity" for e in r.get("entities", [])]
        by_type: dict[str, list[int]] = {}
        for entity in entities:
            slot = by_type.setdefault(entity["type"], [0, 0])
            slot[0] += int(entity["found"])
            slot[1] += 1
        ref_words = sum(r["reference_words"] for r in conversation)
        confidences = [r["confidence"] for r in items if isinstance(r.get("confidence"), (int, float))]
        wer = round(sum(r["edits"] for r in conversation) / ref_words, 3) if ref_words else None
        summary.append(
            {
                "variant": variant,
                "lang": lang,
                "recordings": len(items),
                "conversation_wer": wer,
                "r4_triggered": None if wer is None or lang != "es" else wer > R4_THRESHOLD,
                "entities_exact": f"{sum(e['found'] for e in entities)}/{len(entities)}" if entities else None,
                "entities_by_type": {k: f"{ok}/{total}" for k, (ok, total) in sorted(by_type.items())},
                "mean_confidence": round(sum(confidences) / len(confidences), 3) if confidences else None,
                "errors": sum(1 for r in items if r.get("error")),
            }
        )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--speaker", help="solo las grabaciones de esta persona")
    parser.add_argument("--take", help="solo esta toma (quiet, noise...)")
    parser.add_argument("--variants-es", default="nova-3:es,nova-3:es-419,nova-3:multi")
    parser.add_argument("--variants-en", default="nova-3:en,nova-3:multi")
    parser.add_argument("--sleep", type=float, default=0.5, help="segundos entre llamadas")
    parser.add_argument("--dry-run", action="store_true", help="lista lo que se enviaría, sin llamar a Deepgram")
    parser.add_argument("--rescore", type=Path, help="recalcula un resultado guardado, sin llamar a Deepgram")
    args = parser.parse_args()
    if args.rescore:
        rescore(args.rescore)
        return

    common.load_env()
    recordings = discover(args.speaker, args.take)
    variants = {"es": parse_variants(args.variants_es), "en": parse_variants(args.variants_en)}
    calls = sum(len(variants[r["phrase"]["lang"]]) for r in recordings)
    print(f"Grabaciones encontradas: {len(recordings)}; llamadas previstas: {calls}")
    if not recordings:
        sys.exit("No hay grabaciones. Graba primero con record.py (ver README.md).")
    if args.dry_run:
        for item in recordings:
            names = ", ".join(f"{m}:{l}" for m, l in variants[item["phrase"]["lang"]])
            print(f"  {item['speaker']}/{item['take']}/{item['path'].name}  →  {names}")
        return

    key = common.require_env("DEEPGRAM_API_KEY", "la consola de Deepgram (console.deepgram.com)")
    rows: list[dict[str, Any]] = []
    stopped: str | None = None
    for item in recordings:
        if stopped:
            break
        phrase = item["phrase"]
        # Las frases conversacionales van sin formato inteligente para medir palabras;
        # las de datos van con formato inteligente, que es como las usaría el sistema.
        smart = phrase["kind"] == "entity"
        for model, language in variants[phrase["lang"]]:
            row: dict[str, Any] = {
                "file": str(item["path"].relative_to(HERE)),
                "speaker": item["speaker"],
                "take": item["take"],
                "id": phrase["id"],
                "lang": phrase["lang"],
                "kind": phrase["kind"],
                "variant": f"{model}:{language}",
                "smart_format": smart,
            }
            try:
                transcript, confidence, seconds = transcribe(item["path"], model, language, smart, key)
                row.update(transcript=transcript, confidence=confidence, seconds=round(seconds, 3))
                score_row(row, phrase)
            except Exception as exc:  # noqa: BLE001 - se registra y se sigue
                row["error"] = common.classify_error(exc)
                row["detail"] = str(exc)[:300]
                print(f"  {row['file']} {row['variant']}: {row['error']}", file=sys.stderr)
                stopped = common.spend_stop_reason(exc)
                if stopped:
                    # Sin crédito o sin cuota, las llamadas que siguen fallarían igual.
                    row["stopped"] = stopped
                    rows.append(row)
                    break
            rows.append(row)
            time.sleep(args.sleep)

    summary = summarize(rows)
    path = common.write_results(
        HERE,
        "spanish-stt",
        {
            "experiment": "03-spanish-stt",
            "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "r4_threshold_wer": R4_THRESHOLD,
            "summary": summary,
            "rows": rows,
        },
    )
    print_summary(summary)
    if stopped:
        print(f"\nSe detuvo: {stopped}. Las cifras quedan incompletas; revisa la cuenta antes de repetir.")
    print(f"\nResultado completo: {path}")


if __name__ == "__main__":
    main()
