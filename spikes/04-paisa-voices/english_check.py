#!/usr/bin/env python3
"""Experimento 4, comprobación extra: ¿la voz elegida sigue siendo la misma persona en inglés?

En la primera escucha, Catalina sacó 5 en "misma persona" con la apertura en
inglés y 1 con la confirmación. Este script sintetiza más frases en inglés con
esa voz y arma una página que las mezcla, en orden al azar, con los dos audios en
inglés de la primera escucha y un audio de control de otra voz. Arriba va una
referencia de la voz en español. Las frases están en english-check.json.

Regla, fijada antes de escuchar: la voz conserva su identidad en inglés si las
frases nuevas promedian 4 o más en "misma persona" y en "suena real", y ninguna
baja de 3 en "misma persona". Los puntajes solo cuentan si el control, que es
otra voz, saca 2 o menos en "misma persona".

Uso:
  python3 spikes/04-paisa-voices/english_check.py
  python3 spikes/04-paisa-voices/english_check.py --collect
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import random
import shutil
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import common  # noqa: E402
from listen import STYLE, scale  # noqa: E402
from synthesize import synthesize  # noqa: E402

CONFIG = HERE / "english-check.json"
SAMPLES = HERE / "samples"
CHECK = SAMPLES / "ingles"
KEY = CHECK / "key.csv"
PAGE = CHECK / "escuchar-ingles.html"
BLIND_KEY = HERE / "blind-key.csv"
SCORES = HERE / "scores" / "ingles"
DOWNLOADS = Path.home() / "Downloads"
PASS_MARK = 4.0
FLOOR = 3.0
CONTROL_MAX = 2.0

SCRIPT = """
function download(){
  const who=document.getElementById('who').value.trim().replace(/[^A-Za-z0-9]/g,'').toLowerCase();
  if(!who){alert('Escribe tus iniciales antes de descargar.');document.getElementById('who').focus();return;}
  const lines=['clip,same_person_1_to_5,sounds_real_1_to_5,comment'];
  const missing=[];
  document.querySelectorAll('.row').forEach((row,index)=>{
    const pick=name=>{const c=row.querySelector('input[name="'+name+'"]:checked');return c?c.value:'';};
    const same=pick(row.dataset.id+'-same'), real=pick(row.dataset.id+'-real');
    if(!same||!real){missing.push(index+1);}
    const comment=(row.querySelector('input[type=text]').value||'').replace(/"/g,"'");
    lines.push([row.dataset.clip,same,real,'"'+comment+'"'].join(','));
  });
  if(missing.length&&!confirm('Faltan puntajes en el audio '+missing.join(', ')+'. ¿Descargar de todos modos?')){return;}
  const blob=new Blob([lines.join('\\n')+'\\n'],{type:'text/csv'});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='ingles-'+who+'.csv';a.click();
}
"""


def codes_by_voice() -> dict[str, str]:
    if not BLIND_KEY.exists():
        sys.exit("Falta blind-key.csv. Corre primero synthesize.py.")
    with BLIND_KEY.open(encoding="utf-8") as handle:
        return {row["name"]: row["code"] for row in csv.DictReader(handle)}


def earlier_sample(code: str, text_id: str) -> Path:
    path = SAMPLES / f"{code}-{text_id}.wav"
    if not path.exists():
        sys.exit(f"Falta {path.relative_to(HERE.parent.parent)}. Corre primero synthesize.py.")
    return path


def build(args: argparse.Namespace) -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    codes = codes_by_voice()
    voice_code, control_code = codes.get(config["voice"]), codes.get(config["control_voice"])
    if not voice_code or not control_code:
        sys.exit(f"blind-key.csv no tiene a {config['voice']} y a {config['control_voice']}.")
    voices = {v["name"]: v for v in json.loads((HERE / "candidates.json").read_text(encoding="utf-8"))["voices"]}
    voice = voices[config["voice"]]
    texts = config["texts"]

    characters = sum(len(t["text"]) for t in texts)
    print(f"{config['voice']} × {len(texts)} frases en inglés = {characters} caracteres de los créditos gratuitos.")
    common.load_env()
    keys = {"cartesia": common.require_env("CARTESIA_API_KEY", "la consola de Cartesia (play.cartesia.ai)")}
    if voice["provider"] != "cartesia":
        sys.exit("Este script solo sintetiza con Cartesia.")
    if not args.yes and input("¿Continuar? [s/N] ").strip().lower() not in {"s", "si", "sí", "y", "yes"}:
        return

    staging = CHECK / "nuevas"
    staging.mkdir(parents=True, exist_ok=True)
    models = {"cartesia": args.cartesia_model, "elevenlabs": ""}
    measurements: list[dict[str, Any]] = []
    clips: list[dict[str, Any]] = []
    for text in texts:
        row: dict[str, Any] = {"text_id": text["id"], "characters": len(text["text"])}
        try:
            audio, _, first, total = synthesize(voice, text["text"], text["lang"], keys, models)
            target = staging / f"{text['id']}.wav"
            target.write_bytes(audio)
            row.update(first_byte_ms=common.ms(first), total_ms=common.ms(total))
            clips.append({"group": "new", "voice": config["voice"], "text_id": text["id"], "source": target, "text": text["text"]})
            print(f"  {text['id']}: primer byte {row['first_byte_ms']} ms")
        except Exception as exc:  # noqa: BLE001 - se registra y se sigue
            row.update(error=common.classify_error(exc), detail=str(exc)[:300])
            print(f"  {text['id']}: {row['error']}", file=sys.stderr)
            reason = common.spend_stop_reason(exc)
            if reason:
                row["stopped"] = reason
                measurements.append(row)
                break
        measurements.append(row)
        time.sleep(0.5)

    if not clips:
        shutil.rmtree(staging)
        sys.exit("No se sintetizó ninguna frase nueva: revisa los avisos de arriba antes de repetir.")

    earlier = config["spoken_in_first_run"]
    for text_id in config["earlier_texts"]:
        clips.append({"group": "earlier", "voice": config["voice"], "text_id": text_id, "source": earlier_sample(voice_code, text_id), "text": earlier[text_id]})
    control_id = config["control_text"]
    clips.append({"group": "control", "voice": config["control_voice"], "text_id": control_id, "source": earlier_sample(control_code, control_id), "text": earlier[control_id]})

    random.SystemRandom().shuffle(clips)
    for old in CHECK.glob("clip-*.wav"):
        old.unlink()
    with KEY.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["clip", "group", "voice", "text_id"])
        for index, clip in enumerate(clips, 1):
            clip["clip"] = f"clip-{index:02d}"
            shutil.copyfile(clip["source"], CHECK / f"{clip['clip']}.wav")
            writer.writerow([clip["clip"], clip["group"], clip["voice"], clip["text_id"]])
    shutil.copyfile(earlier_sample(voice_code, config["reference_text"]), CHECK / "referencia.wav")
    shutil.rmtree(staging)

    blocks = []
    for index, clip in enumerate(clips, 1):
        rid = f"r{index}"
        blocks.append(
            f'<section class="row" data-id="{rid}" data-clip="{clip["clip"]}">'
            f"<strong>Audio {index} de {len(clips)}</strong>"
            f'<audio controls preload="none" src="{clip["clip"]}.wav"></audio>'
            f'<span class="phrase" lang="en">{html.escape(clip["text"])}</span>'
            + scale(f"{rid}-same", "¿Parece la misma persona de la referencia? 1 = otra persona, 5 = la misma")
            + scale(f"{rid}-real", "¿Suena real? 1 = robot, 5 = persona")
            + f'<input type="text" aria-label="Comentario del audio {index}" placeholder="Comentario opcional">'
            "</section>"
        )
    page = (
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1"><title>Voz en inglés</title>'
        f"<style>{STYLE}.reference{{background:#fff;border:2px solid #9A4F12;border-radius:12px;padding:14px 16px;display:grid;gap:8px}}</style>"
        "</head><body><main>"
        "<h1>¿Sigue siendo la misma persona en inglés?</h1>"
        '<p class="note">Primero escucha la referencia en español. Después escucha cada audio en inglés y marca si parece '
        "la misma persona de la referencia y si suena real. Algunos audios ya los oíste antes: califícalos igual, sin tratar "
        "de recordar qué les pusiste.</p>"
        '<section class="reference"><strong>Referencia: así suena la voz en español</strong>'
        '<audio controls preload="none" src="referencia.wav"></audio></section>'
        '<label for="who"><strong>Tus iniciales</strong></label><input type="text" id="who" autocomplete="off">'
        + "".join(blocks)
        + '<button type="button" onclick="download()">Descargar mis puntajes</button>'
        '<p class="note">El archivo se guarda en Descargas como ingles-tus-iniciales.csv.</p>'
        f"</main><script>{SCRIPT}</script></body></html>\n"
    )
    PAGE.write_text(page, encoding="utf-8")
    path = common.write_results(
        HERE,
        "english-check-synthesis",
        {
            "experiment": "04-paisa-voices",
            "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "voice": config["voice"],
            "model": args.cartesia_model,
            "clips": len(clips),
            "measurements": measurements,
        },
    )
    print(f"\nPágina creada con {len(clips)} audios: {PAGE.relative_to(HERE.parent.parent)}")
    print("Ábrela con: open spikes/04-paisa-voices/samples/ingles/escuchar-ingles.html")
    print(f"Latencias en {path.relative_to(HERE.parent.parent)}")


def mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def read_score(value: str) -> float | None:
    try:
        number = float((value or "").strip())
    except ValueError:
        return None
    return number if 1 <= number <= 5 else None


def collect() -> None:
    SCORES.mkdir(parents=True, exist_ok=True)
    for path in sorted(DOWNLOADS.glob("ingles-*.csv")):
        target = SCORES / path.name.replace("ingles-", "")
        shutil.move(str(path), target)
        print(f"Movido a {target.relative_to(HERE.parent.parent)}")
    sheets = sorted(SCORES.glob("*.csv"))
    if not sheets:
        sys.exit(f"No encontré planillas ingles-*.csv en {DOWNLOADS} ni en {SCORES.relative_to(HERE.parent.parent)}.")
    if not KEY.exists():
        sys.exit("Falta samples/ingles/key.csv. Corre primero english_check.py sin --collect.")

    with KEY.open(encoding="utf-8") as handle:
        clip_key = {row["clip"]: row for row in csv.DictReader(handle)}
    same: dict[str, list[float]] = {clip: [] for clip in clip_key}
    real: dict[str, list[float]] = {clip: [] for clip in clip_key}
    for sheet in sheets:
        with sheet.open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                clip = row.get("clip", "").strip()
                if clip not in clip_key:
                    continue
                if (value := read_score(row.get("same_person_1_to_5", ""))) is not None:
                    same[clip].append(value)
                if (value := read_score(row.get("sounds_real_1_to_5", ""))) is not None:
                    real[clip].append(value)

    clips = [
        {**clip_key[clip], "same_person": mean(same[clip]), "sounds_real": mean(real[clip])}
        for clip in sorted(clip_key, key=lambda c: (clip_key[c]["group"], clip_key[c]["text_id"]))
    ]
    new = [c for c in clips if c["group"] == "new" and c["same_person"] is not None]
    control = next((c for c in clips if c["group"] == "control"), None)
    new_same = mean([c["same_person"] for c in new])
    new_real = mean([c["sounds_real"] for c in new if c["sounds_real"] is not None])
    lowest = min(new, key=lambda c: c["same_person"]) if new else None
    control_ok = control is not None and control["same_person"] is not None and control["same_person"] <= CONTROL_MAX
    passes = (
        control_ok
        and new_same is not None
        and new_real is not None
        and new_same >= PASS_MARK
        and new_real >= PASS_MARK
        and lowest is not None
        and lowest["same_person"] >= FLOOR
    )

    print(
        "\n"
        + common.markdown_table(
            ["Audio", "Grupo", "Voz", "Frase", "Misma persona", "Suena real"],
            [[c["clip"], c["group"], c["voice"], c["text_id"], c["same_person"], c["sounds_real"]] for c in clips],
        )
    )
    print(f"\nFrases nuevas: misma persona {new_same}, suena real {new_real}, la más baja {lowest['text_id'] if lowest else '—'} ({lowest['same_person'] if lowest else '—'}).")
    if not control_ok:
        verdict = "no cuenta: el control, que es otra voz, no sacó 2 o menos en misma persona, así que los puntajes no distinguen voces"
    elif passes:
        verdict = "la voz conserva su identidad en inglés"
    else:
        verdict = "la voz no conserva su identidad en inglés según la regla"
    print(f"Resultado: {verdict}.")

    path = common.write_results(
        HERE,
        "english-check",
        {
            "experiment": "04-paisa-voices",
            "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "rule": {"pass_mark": PASS_MARK, "floor_same_person": FLOOR, "control_max_same_person": CONTROL_MAX},
            "sheets": len(sheets),
            "clips": clips,
            "new_same_person": new_same,
            "new_sounds_real": new_real,
            "control_ok": control_ok,
            "passes": passes,
            "verdict": verdict,
        },
    )
    print(f"Resultado completo: {path.relative_to(HERE.parent.parent)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--collect", action="store_true", help="junta las descargas ingles-*.csv y calcula el resultado")
    parser.add_argument("--cartesia-model", default="sonic-3.6")
    parser.add_argument("--yes", action="store_true", help="no pedir confirmación antes de gastar créditos")
    args = parser.parse_args()
    collect() if args.collect else build(args)


if __name__ == "__main__":
    main()
