#!/usr/bin/env python3
"""Experimento 4, paso 3: página para escuchar a ciegas y calificar sin editar un CSV.

Crea samples/escuchar.html con un reproductor por frase, en el orden al azar de
score-sheet-template.csv, y un botón que descarga los puntajes de quien escucha
como puntajes-<iniciales>.csv. Después, --collect mueve esas descargas a scores/
para que reveal.py las lea.

Uso:
  python3 spikes/04-paisa-voices/listen.py
  python3 spikes/04-paisa-voices/listen.py --collect
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SAMPLES = HERE / "samples"
SCORES = HERE / "scores"
TEMPLATE = HERE / "score-sheet-template.csv"
PAGE = SAMPLES / "escuchar.html"
DOWNLOADS = Path.home() / "Downloads"

STYLE = """
body{margin:0;padding:24px 16px 64px;background:#F5F6F8;color:#15161D;font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:760px;margin:0 auto;display:grid;gap:16px}
h1{font-size:1.5rem;margin:0}
.row{background:#fff;border:1px solid #E1E4E9;border-radius:12px;padding:14px 16px;display:grid;gap:8px}
.row audio{width:100%}
.phrase{color:#525866;font-size:.9rem}
fieldset{border:0;padding:0;margin:0;display:flex;flex-wrap:wrap;gap:6px 12px;align-items:center}
legend{font-weight:600;font-size:.9rem;margin-bottom:4px;width:100%}
label{display:inline-flex;align-items:center;gap:4px;min-height:36px}
input[type=text]{font:inherit;padding:8px 10px;border:1px solid #7A808D;border-radius:8px;width:100%;box-sizing:border-box}
button{font:inherit;font-weight:600;padding:12px 20px;border-radius:999px;border:0;background:#9A4F12;color:#fff;cursor:pointer}
.note{color:#525866;font-size:.9rem}
"""

SCRIPT = """
function download(){
  const who=document.getElementById('who').value.trim().replace(/[^A-Za-z0-9]/g,'').toLowerCase();
  if(!who){alert('Escribe tus iniciales antes de descargar.');document.getElementById('who').focus();return;}
  const lines=['code,text_id,sounds_medellin_1_to_5,sounds_real_1_to_5,same_person_in_english_1_to_5,comment'];
  document.querySelectorAll('.row').forEach(row=>{
    const pick=name=>{const c=row.querySelector('input[name="'+name+'"]:checked');return c?c.value:'';};
    const id=row.dataset.id;
    const comment=(row.querySelector('input[type=text]').value||'').replace(/"/g,"'");
    lines.push([row.dataset.code,row.dataset.text,pick(id+'-medellin'),pick(id+'-real'),pick(id+'-same'),'"'+comment+'"'].join(','));
  });
  const blob=new Blob([lines.join('\\n')+'\\n'],{type:'text/csv'});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='puntajes-'+who+'.csv';a.click();
}
"""


def scale(name: str, legend: str) -> str:
    options = "".join(f'<label><input type="radio" name="{name}" value="{n}"> {n}</label>' for n in range(1, 6))
    return f"<fieldset><legend>{html.escape(legend)}</legend>{options}</fieldset>"


def build_page() -> None:
    if not TEMPLATE.exists():
        sys.exit("Falta score-sheet-template.csv. Corre primero synthesize.py.")
    texts = {t["id"]: t for t in json.loads((HERE / "texts.json").read_text(encoding="utf-8"))["texts"]}
    with TEMPLATE.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    blocks = []
    for index, row in enumerate(rows, 1):
        text = texts.get(row["text_id"], {})
        lang = text.get("lang", "es")
        audio = f"{row['code']}-{row['text_id']}.wav"
        if not (SAMPLES / audio).exists():
            continue
        rid = f"r{index}"
        scales = scale(f"{rid}-real", "¿Suena real? 1 = robot, 5 = persona")
        if lang == "es":
            scales = scale(f"{rid}-medellin", "¿Suena de Medellín? 1 = nada, 5 = totalmente") + scales
        else:
            scales += scale(f"{rid}-same", "¿Parece la misma persona hablando inglés? 1 = otra, 5 = la misma")
        blocks.append(
            f'<section class="row" data-id="{rid}" data-code="{html.escape(row["code"])}" data-text="{html.escape(row["text_id"])}">'
            f'<strong>Audio {index} de {len(rows)}</strong>'
            f'<audio controls preload="none" src="{html.escape(audio)}"></audio>'
            f'<span class="phrase" lang="{lang}">{html.escape(text.get("text", ""))}</span>'
            f"{scales}"
            f'<input type="text" aria-label="Comentario del audio {index}" placeholder="Comentario opcional">'
            "</section>"
        )
    page = (
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1"><title>Escuchar voces</title>'
        f"<style>{STYLE}</style></head><body><main>"
        "<h1>Escucha y califica cada voz</h1>"
        '<p class="note">No sabes qué voz es cuál, y así debe ser. Escucha cada audio completo, marca los puntajes y, '
        "al final, descarga tus respuestas. No hay respuestas correctas.</p>"
        '<label for="who"><strong>Tus iniciales</strong></label><input type="text" id="who" autocomplete="off">'
        + "".join(blocks)
        + '<button type="button" onclick="download()">Descargar mis puntajes</button>'
        '<p class="note">El archivo se guarda en Descargas como puntajes-tus-iniciales.csv. Envíaselo a Miguel.</p>'
        f"</main><script>{SCRIPT}</script></body></html>\n"
    )
    PAGE.write_text(page, encoding="utf-8")
    print(f"Página creada: {PAGE.relative_to(HERE.parent.parent)} ({len(blocks)} audios).")
    print("Ábrela con: open spikes/04-paisa-voices/samples/escuchar.html")


def collect() -> None:
    SCORES.mkdir(exist_ok=True)
    found = sorted(DOWNLOADS.glob("puntajes-*.csv"))
    if not found:
        sys.exit(f"No encontré archivos puntajes-*.csv en {DOWNLOADS}.")
    for path in found:
        target = SCORES / path.name.replace("puntajes-", "")
        shutil.move(str(path), target)
        print(f"Movido a {target.relative_to(HERE.parent.parent)}")
    print("Cuando estén todas las planillas, corre: python3 spikes/04-paisa-voices/reveal.py")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--collect", action="store_true", help="mueve las descargas puntajes-*.csv a scores/")
    args = parser.parse_args()
    collect() if args.collect else build_page()


if __name__ == "__main__":
    main()
