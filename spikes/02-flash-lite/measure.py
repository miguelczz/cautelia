#!/usr/bin/env python3
"""Experimento 2: extracción y latencia de los modelos Flash-Lite de Gemini.

Responde dos preguntas para la decisión de modelo (riesgo R3, supuesto A2):

1. ¿Extrae bien los datos de un turno del asegurado, en español y en inglés,
   sin inventar lo que no se dijo?
2. ¿Cuánto tarda en empezar a responder un turno corto de la agente?

Uso:
  python3 spikes/02-flash-lite/measure.py --dry-run
  python3 spikes/02-flash-lite/measure.py
  python3 spikes/02-flash-lite/measure.py --models gemini-3.5-flash-lite --sleep 6
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import common  # noqa: E402

API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"
# gemini-2.5-flash-lite quedó fuera: el 2026-09-16 la API respondió 404, "no
# longer available to new users".
DEFAULT_MODELS = ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]

# Precios de lista en USD por millón de tokens de texto, tomados de
# https://ai.google.dev/gemini-api/docs/pricing el 2026-09-16. Sirven solo para
# estimar: el tier gratuito no cobra y los precios cambian.
PRICES = {
    "gemini-3.1-flash-lite": {"input": 0.25, "output": 1.50},
    "gemini-3.5-flash-lite": {"input": 0.30, "output": 2.50},
}

# Turnos de la agente en una llamada de tres minutos (estimación del PRD).
TURNS_PER_CALL = 15

FIELDS = [
    "when_date",
    "when_time",
    "place",
    "description",
    "vehicle",
    "plate",
    "other_vehicle_plate",
    "other_parties",
    "injuries",
    "driver_is_policyholder",
    "policy_number",
    "national_id",
    "phone",
]
TEXT_FIELDS = {"place", "description", "vehicle"}
# description solo se evalúa cuando el caso la nombra: cualquier turno puede
# describir algo y castigarlo añadiría ruido, no señal.
SCORED_ONLY_WHEN_NAMED = {"description"}

EXTRACTION_INSTRUCTION = """You extract claim facts from ONE utterance of a person reporting a car accident to an insurer.
Today is Tuesday 2026-09-15, 16:00 local time.
Rules:
- Return only facts stated in this utterance. Use null for anything not stated. Never guess.
- when_date: YYYY-MM-DD resolved against today, also for relative days such as "yesterday" or "last night".
- when_time: HH:MM in 24 hours only if a concrete clock time was stated; a vague time such as "last night" gives a date but a null time.
- injuries and other_parties: null unless the caller talked about them; silence is not "none" or 0.
- plate, other_vehicle_plate and policy_number: uppercase letters and digits only, without spaces or dashes; spelled-out digits become digits.
- national_id and phone: digits only.
- other_parties: number of other vehicles or people outside the caller's car that were involved.
- injuries: "none" if the caller says nobody was hurt, "minor" for small injuries without hospital, "serious" for hospital, paramedics or severe injuries.
- driver_is_policyholder: false if someone else was driving, true if the caller was driving.
- If the caller corrects an earlier detail, return only the corrected value.
- place, description and vehicle: short phrases in the caller's language."""

AGENT_INSTRUCTION = """You are Valentina, the AI assistant of a car insurer, taking a first notice of loss by phone.
Reply in the caller's language with one short acknowledgment if needed and exactly one question, 25 words or fewer.
Never promise coverage, amounts or fault. Do not ask again for details the caller already gave."""


def _nullable(kind: str, description: str, **extra: Any) -> dict[str, Any]:
    return {"type": kind, "nullable": True, "description": description, **extra}


EXTRACTION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "when_date": _nullable("STRING", "Accident date as YYYY-MM-DD."),
        "when_time": _nullable("STRING", "Accident time as HH:MM, only if a concrete time was stated."),
        "place": _nullable("STRING", "Where the accident happened."),
        "description": _nullable("STRING", "What happened, in a few words."),
        "vehicle": _nullable("STRING", "Make and model of the caller's own vehicle."),
        "plate": _nullable("STRING", "License plate of the caller's own vehicle."),
        "other_vehicle_plate": _nullable("STRING", "License plate of the other vehicle."),
        "other_parties": _nullable("INTEGER", "Number of other vehicles or people outside the caller's car."),
        "injuries": _nullable("STRING", "none, minor or serious.", enum=["none", "minor", "serious"], format="enum"),
        "driver_is_policyholder": _nullable("BOOLEAN", "Whether the caller was driving."),
        "policy_number": _nullable("STRING", "Policy number."),
        "national_id": _nullable("STRING", "National ID or driver's license number, digits only."),
        "phone": _nullable("STRING", "Phone number, digits only."),
    },
    "required": FIELDS,
    "propertyOrdering": FIELDS,
}


def thinking_config(model: str, level: str) -> dict[str, Any]:
    """Pide el mínimo razonamiento posible: lo que se mide es la latencia del turno."""
    if model.startswith("gemini-2."):
        return {"thinkingBudget": 0}
    return {"thinkingLevel": level}


def extraction_payload(case: dict[str, Any], model: str, level: str) -> dict[str, Any]:
    prompt = f"Agent asked: {case['question']}\nCaller said: {case['utterance']}"
    return {
        "systemInstruction": {"parts": [{"text": EXTRACTION_INSTRUCTION}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "seed": 7,
            "responseMimeType": "application/json",
            "responseSchema": EXTRACTION_SCHEMA,
            "thinkingConfig": thinking_config(model, level),
        },
    }


def turn_payload(case: dict[str, Any], model: str, level: str) -> dict[str, Any]:
    return {
        "systemInstruction": {"parts": [{"text": AGENT_INSTRUCTION}]},
        "contents": [
            {"role": "user", "parts": [{"text": "(call connected)"}]},
            {"role": "model", "parts": [{"text": case["question"]}]},
            {"role": "user", "parts": [{"text": case["utterance"]}]},
        ],
        "generationConfig": {
            "temperature": 0,
            "seed": 7,
            "maxOutputTokens": 200,
            "thinkingConfig": thinking_config(model, level),
        },
    }


class ModelSession:
    """Llamadas a un modelo, con retroceso a razonamiento "low" si "minimal" no existe."""

    def __init__(self, model: str, key: str) -> None:
        self.model = model
        self.headers = {"x-goog-api-key": key}
        self.level = "minimal"

    def call(self, build: Callable[[str, str], dict[str, Any]], stream: bool = False) -> Any:
        while True:
            payload = build(self.model, self.level)
            try:
                if stream:
                    url = f"{API_ROOT}/{self.model}:streamGenerateContent?alt=sse"
                    return common.with_retries(lambda: common.stream_sse(url, self.headers, payload))
                url = f"{API_ROOT}/{self.model}:generateContent"
                return common.with_retries(lambda: common.request_json(url, self.headers, payload))
            except common.HttpError as exc:
                can_fallback = (
                    exc.status == 400
                    and "thinking" in exc.body.lower()
                    and self.level == "minimal"
                    and not self.model.startswith("gemini-2.")
                )
                if not can_fallback:
                    raise
                self.level = "low"


def response_text(response: dict[str, Any]) -> str:
    candidates = response.get("candidates") or []
    if not candidates:
        return ""
    parts = candidates[0].get("content", {}).get("parts", [])
    return "".join(part.get("text", "") for part in parts if not part.get("thought"))


def normalize_exact(field: str, value: Any) -> Any:
    if value is None:
        return None
    if field in {"plate", "other_vehicle_plate", "policy_number"}:
        return re.sub(r"[^A-Z0-9]", "", str(value).upper()) or None
    if field in {"national_id", "phone"}:
        return re.sub(r"\D", "", str(value)) or None
    if field == "when_time":
        # Se acepta "5:30 PM": lo que se mide es si entendió la hora, no el formato.
        match = re.match(r"^\s*(\d{1,2}):(\d{2})\s*([ap])?\.?\s*m?\.?", str(value), re.IGNORECASE)
        if not match:
            return str(value).strip()
        hour = int(match.group(1))
        suffix = (match.group(3) or "").lower()
        if suffix == "p" and hour < 12:
            hour += 12
        if suffix == "a" and hour == 12:
            hour = 0
        return f"{hour:02d}:{match.group(2)}"
    if field == "other_parties":
        try:
            return int(value)
        except (TypeError, ValueError):
            return str(value)
    if field == "injuries":
        return str(value).strip().lower()
    if isinstance(value, str):
        return value.strip()
    return value


def score_case(case: dict[str, Any], extracted: Any) -> dict[str, dict[str, Any]]:
    expected = case["expected"]
    got_all = extracted if isinstance(extracted, dict) else {}
    scores: dict[str, dict[str, Any]] = {}
    for field in FIELDS:
        if field in SCORED_ONLY_WHEN_NAMED and field not in expected:
            continue
        spec = expected.get(field)
        if isinstance(spec, dict) and spec.get("any"):
            continue
        got = got_all.get(field)
        if field in TEXT_FIELDS:
            if spec is None:
                ok = got in (None, "")
                kind = "must_be_null"
            else:
                text = common.fold(str(got or ""))
                has_all = all(common.fold(word) in text for word in spec.get("keywords", []))
                has_forbidden = any(common.fold(word) in text for word in spec.get("forbidden", []))
                ok = bool(got) and has_all and not has_forbidden
                kind = "keywords"
        else:
            ok = normalize_exact(field, spec) == normalize_exact(field, got)
            kind = "must_be_null" if spec is None else "exact"
        scores[field] = {"ok": ok, "kind": kind, "expected": spec, "got": got}
    return scores


def turn_cost(model: str, usage: dict[str, Any]) -> float | None:
    price = PRICES.get(model)
    if not price or not usage:
        return None
    prompt = usage.get("promptTokenCount", 0)
    output = usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0)
    return (prompt * price["input"] + output * price["output"]) / 1_000_000


def summarize(model: str, result: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for lang in ("es", "en"):
        extractions = [item for item in result["extraction"] if item["lang"] == lang]
        scored = [score for item in extractions for score in item["scores"].values()]
        per_field: dict[str, list[int]] = {}
        for item in extractions:
            for field, score in item["scores"].items():
                slot = per_field.setdefault(field, [0, 0])
                slot[0] += int(score["ok"])
                slot[1] += 1
        turns = [turn for turn in result["turns"] if turn["lang"] == lang]
        costs = [cost for cost in (turn_cost(model, turn["usage"]) for turn in turns) if cost is not None]
        per_turn = sum(costs) / len(costs) if costs else None
        summary[lang] = {
            "cases": len(extractions),
            "fields_scored": len(scored),
            "field_accuracy": round(sum(s["ok"] for s in scored) / len(scored), 3) if scored else None,
            "invented_values": sum(1 for s in scored if s["kind"] == "must_be_null" and not s["ok"]),
            "cases_with_every_field_right": sum(all(s["ok"] for s in item["scores"].values()) for item in extractions),
            "per_field": {field: f"{ok}/{total}" for field, (ok, total) in sorted(per_field.items())},
            "turns": len(turns),
            "ttft_ms_p50": common.percentile([t["ttft_ms"] for t in turns], 50),
            "ttft_ms_p95": common.percentile([t["ttft_ms"] for t in turns], 95),
            "total_ms_p50": common.percentile([t["total_ms"] for t in turns], 50),
            "total_ms_p95": common.percentile([t["total_ms"] for t in turns], 95),
            "longest_reply_words": max((len(t["reply"].split()) for t in turns), default=None),
            "usd_per_turn_estimate": None if per_turn is None else round(per_turn, 7),
            "usd_per_3min_call_estimate": None if per_turn is None else round(per_turn * TURNS_PER_CALL, 5),
        }
    summary["errors"] = len(result["errors"])
    return summary


def load_cases(lang: str | None, limit: int | None) -> list[dict[str, Any]]:
    data = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    cases = data["cases"]
    ids = [case["id"] for case in cases]
    if len(ids) != len(set(ids)):
        sys.exit("cases.json tiene identificadores repetidos.")
    for case in cases:
        if case["lang"] not in {"es", "en"}:
            sys.exit(f"{case['id']}: idioma desconocido {case['lang']!r}.")
        unknown = set(case["expected"]) - set(FIELDS)
        if unknown:
            sys.exit(f"{case['id']}: campos desconocidos {sorted(unknown)}.")
        for field, spec in case["expected"].items():
            if field in TEXT_FIELDS and spec is not None and not isinstance(spec, dict):
                sys.exit(f"{case['id']}: {field} necesita keywords o any.")
    if lang:
        cases = [case for case in cases if case["lang"] == lang]
    if limit:
        kept: list[dict[str, Any]] = []
        for code in ("es", "en"):
            kept.extend([case for case in cases if case["lang"] == code][:limit])
        cases = kept
    return cases


def record_error(result: dict[str, Any], case_id: str, task: str, exc: BaseException) -> str | None:
    """Registra el fallo y devuelve qué se acabó cuando el fallo obliga a detener el modelo."""
    kind = common.classify_error(exc)
    result["errors"].append({"id": case_id, "task": task, "kind": kind, "detail": str(exc)[:300]})
    print(f"  {case_id} {task}: {kind}", file=sys.stderr)
    reason = common.spend_stop_reason(exc)
    if reason:
        result["stopped"] = reason
    return reason


def run(args: argparse.Namespace) -> None:
    common.load_env()
    cases = load_cases(args.lang, args.limit)
    models = [model.strip() for model in args.models.split(",") if model.strip()]
    calls = len(models) * (len(cases) * (1 + args.repeat) + (0 if args.no_warmup else 1))
    minutes = calls * (args.sleep + 3) / 60
    print(f"Modelos: {', '.join(models)}")
    print(f"Casos: {len(cases)} ({sum(c['lang'] == 'es' for c in cases)} es, {sum(c['lang'] == 'en' for c in cases)} en)")
    print(f"Llamadas previstas: {calls}, unos {minutes:.0f} minutos con {args.sleep:.0f} s de pausa entre llamadas")
    if args.dry_run:
        sample = extraction_payload(cases[0], models[0], "minimal")
        print("\nEjemplo de petición de extracción (sin clave):")
        print(json.dumps(sample, ensure_ascii=False, indent=2)[:1500])
        return

    key = common.require_env("GEMINI_API_KEY", "Google AI Studio (aistudio.google.com)")
    results: dict[str, Any] = {
        "experiment": "02-flash-lite",
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "prices_usd_per_million_tokens": PRICES,
        "prices_source": "https://ai.google.dev/gemini-api/docs/pricing (consultado 2026-09-16)",
        "turns_per_3min_call": TURNS_PER_CALL,
        "sleep_seconds": args.sleep,
        "models": {},
    }

    for model in models:
        print(f"\n== {model}")
        session = ModelSession(model, key)
        result: dict[str, Any] = {"extraction": [], "turns": [], "errors": []}
        if not args.no_warmup:
            try:
                session.call(lambda m, level: turn_payload(cases[0], m, level), stream=True)
            except common.HttpError as exc:
                if exc.status == 404:
                    print(f"  {model} no está disponible: {common.provider_message(exc.body)} Se omite.")
                    results["models"][model] = {"unavailable": str(exc)[:300]}
                    continue
                record_error(result, "warmup", "turn", exc)
            except Exception as exc:  # noqa: BLE001 - se registra y se sigue
                record_error(result, "warmup", "turn", exc)
            time.sleep(args.sleep)

        for case in cases:
            if result.get("stopped"):
                break
            try:
                response, seconds = session.call(lambda m, level: extraction_payload(case, m, level))
                text = response_text(response)
                extracted = json.loads(text) if text else {}
                result["extraction"].append(
                    {
                        "id": case["id"],
                        "lang": case["lang"],
                        "seconds": round(seconds, 3),
                        "extracted": extracted,
                        "scores": score_case(case, extracted),
                    }
                )
            except Exception as exc:  # noqa: BLE001 - se registra y se sigue
                if record_error(result, case["id"], "extraction", exc):
                    break
            time.sleep(args.sleep)

            for _ in range(args.repeat):
                try:
                    events, first, total = session.call(
                        lambda m, level: turn_payload(case, m, level), stream=True
                    )
                    reply = "".join(response_text(event) for event in events)
                    usage = next((e["usageMetadata"] for e in reversed(events) if e.get("usageMetadata")), {})
                    result["turns"].append(
                        {
                            "id": case["id"],
                            "lang": case["lang"],
                            "ttft_ms": common.ms(first),
                            "total_ms": common.ms(total),
                            "reply": reply.strip(),
                            "usage": usage,
                        }
                    )
                except Exception as exc:  # noqa: BLE001 - se registra y se sigue
                    if record_error(result, case["id"], "turn", exc):
                        break
                time.sleep(args.sleep)

        if not model.startswith("gemini-2."):
            result["thinking_level"] = session.level
        result["summary"] = summarize(model, result)
        results["models"][model] = result

    path = common.write_results(HERE, "flash-lite", results)
    rows = []
    for model, result in results["models"].items():
        if "summary" not in result:
            rows.append([model, "—", "no disponible", None, None, None, None])
            continue
        for lang in ("es", "en"):
            s = result["summary"][lang]
            rows.append(
                [
                    model,
                    lang,
                    None if s["field_accuracy"] is None else f"{s['field_accuracy'] * 100:.1f} %".replace(".", ","),
                    s["invented_values"],
                    s["ttft_ms_p50"],
                    s["ttft_ms_p95"],
                    s["usd_per_3min_call_estimate"],
                ]
            )
    print("\n" + common.markdown_table(
        ["Modelo", "Idioma", "Campos bien", "Valores inventados", "Primer token p50 (ms)", "Primer token p95 (ms)", "USD por llamada de 3 min"],
        rows,
    ))
    for model, result in results["models"].items():
        if result.get("stopped"):
            print(f"\nSe detuvo {model}: {result['stopped']}. Sus cifras quedan incompletas; revisa la cuenta antes de repetir.")
    print(f"\nResultado completo: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--models", default=",".join(DEFAULT_MODELS), help="modelos separados por comas")
    parser.add_argument("--lang", choices=["es", "en"], help="solo un idioma")
    parser.add_argument("--limit", type=int, help="casos por idioma")
    parser.add_argument("--repeat", type=int, default=1, help="mediciones de turno por caso")
    parser.add_argument("--sleep", type=float, default=4.0, help="segundos entre llamadas (tier gratuito)")
    parser.add_argument("--no-warmup", action="store_true", help="no descartar la primera llamada por modelo")
    parser.add_argument("--dry-run", action="store_true", help="valida los casos y muestra el plan sin llamar a nadie")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
