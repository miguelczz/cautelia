#!/usr/bin/env python3
"""Graba las frases del guion, un archivo por frase, con ffmpeg y el micrófono del Mac.

Uso:
  python3 spikes/03-spanish-stt/record.py --list-devices
  python3 spikes/03-spanish-stt/record.py --speaker miguel --take quiet
  python3 spikes/03-spanish-stt/record.py --speaker miguel --take noise --lang es
  python3 spikes/03-spanish-stt/record.py --speaker miguel --take quiet --only es-c03 --redo

Si no indicas --device, usa el micrófono integrado del Mac y dice cuál eligió.
Después de cada frase revisa que la grabación tenga voz; si salió vacía o en
silencio, deja repetirla.

Las grabaciones quedan en spikes/03-spanish-stt/recordings/<persona>/<toma>/,
que git ignora: son voz de personas reales y no se versionan.
"""

from __future__ import annotations

import argparse
import array
import json
import re
import shutil
import signal
import subprocess
import sys
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
RECORDINGS = HERE / "recordings"
SLUG = re.compile(r"^[a-z0-9-]+$")
DEVICE_LINE = re.compile(r"\]\s\[(\d+)\]\s(.+)$")
# Dispositivos de audio virtuales: graban silencio o el sonido de otra aplicación.
VIRTUAL = re.compile(r"teams|zoom|blackhole|loopback|soundflower|virtual|aggregate|agregado", re.IGNORECASE)
MICROPHONE = re.compile(r"micr[oó]fono|microphone", re.IGNORECASE)
BUILT_IN = re.compile(r"macbook|imac|built-in|integrado", re.IGNORECASE)
MIN_SECONDS = 0.5
# Un pico por debajo del 2 % del máximo es casi silencio (unos -34 dBFS).
MIN_PEAK = 0.02
PERMISSION_HINT = "Ajustes del Sistema > Privacidad y seguridad > Micrófono"


def audio_devices() -> list[tuple[str, str]]:
    """Micrófonos que ve ffmpeg, como (índice, nombre)."""
    # ffmpeg imprime la lista y termina con error por no tener entrada: es lo esperado.
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
        capture_output=True,
        text=True,
        check=False,
    )
    devices: list[tuple[str, str]] = []
    in_audio = False
    for line in result.stderr.splitlines():
        if "audio devices" in line:
            in_audio = True
        elif "video devices" in line:
            in_audio = False
        elif in_audio and (match := DEVICE_LINE.search(line)):
            devices.append((match.group(1), match.group(2).strip()))
    return devices


def default_device(devices: list[tuple[str, str]]) -> tuple[str, str] | None:
    """El micrófono integrado del Mac; si no está, el primero que no sea virtual ni de un iPhone."""
    usable = [device for device in devices if not VIRTUAL.search(device[1])]
    for device in usable:
        if MICROPHONE.search(device[1]) and BUILT_IN.search(device[1]):
            return device
    for device in usable:
        if MICROPHONE.search(device[1]) and "iphone" not in device[1].lower():
            return device
    return usable[0] if usable else None


def resolve_device(requested: str | None, devices: list[tuple[str, str]]) -> tuple[str, str]:
    if requested is None:
        chosen = default_device(devices)
        if chosen is None:
            sys.exit("No encontré ningún micrófono. Revisa la lista con --list-devices.")
        return chosen
    for index, name in devices:
        if requested == index or requested.lower() in name.lower():
            return index, name
    if requested.isdigit() and not devices:
        return requested, f"dispositivo {requested}"
    sys.exit(f"No encontré el micrófono «{requested}». Revisa la lista con --list-devices.")


def list_devices() -> None:
    devices = audio_devices()
    if not devices:
        sys.exit("ffmpeg no mostró ningún micrófono.")
    chosen = default_device(devices)
    print("Micrófonos disponibles:")
    for index, name in devices:
        notes = []
        if chosen and index == chosen[0]:
            notes.append("se usa si no indicas --device")
        if VIRTUAL.search(name):
            notes.append("virtual: graba silencio")
        print(f"  [{index}] {name}" + (f"  ← {'; '.join(notes)}" if notes else ""))
    print("\nPara usar otro: --device <número>")


def duration_seconds(path: Path) -> float:
    try:
        with wave.open(str(path), "rb") as audio:
            return audio.getnframes() / audio.getframerate()
    except (wave.Error, EOFError):
        return 0.0


def recording_problem(path: Path) -> str | None:
    """Explica por qué una toma no sirve, o None si tiene voz."""
    if not path.exists():
        return f"No se creó el archivo. Revisa el permiso de micrófono en {PERMISSION_HINT}."
    try:
        with wave.open(str(path), "rb") as audio:
            seconds = audio.getnframes() / audio.getframerate()
            width = audio.getsampwidth()
            frames = audio.readframes(audio.getnframes())
    except (wave.Error, EOFError):
        return "La grabación salió dañada."
    if seconds < MIN_SECONDS:
        return "La grabación salió vacía o demasiado corta."
    if width == 2:
        samples = array.array("h")
        samples.frombytes(frames[: len(frames) // 2 * 2])
        if sys.byteorder == "big":
            samples.byteswap()
        peak = max((abs(sample) for sample in samples), default=0) / 32768
        if peak < MIN_PEAK:
            return (
                "La grabación salió casi en silencio. Revisa que el micrófono sea el del Mac y que la app desde donde "
                f"corres esto tenga permiso de micrófono en {PERMISSION_HINT}."
            )
    return None


def record_one(path: Path, device: str) -> None:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-f",
        "avfoundation",
        "-i",
        f":{device}",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-y",
        str(path),
    ]
    process = subprocess.Popen(command)
    try:
        input("  Grabando... pulsa Enter cuando termines de hablar. ")
    finally:
        # SIGINT hace que ffmpeg cierre el WAV con su cabecera correcta.
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


def record_until_usable(path: Path, device: str) -> bool:
    """Graba hasta que la toma tenga voz o se salte. Devuelve False si la persona quiere salir."""
    while True:
        try:
            record_one(path, device)
        except KeyboardInterrupt:
            # Una toma cortada a medias no se deja en disco: la próxima corrida la vuelve a pedir.
            path.unlink(missing_ok=True)
            raise
        problem = recording_problem(path)
        if problem is None:
            print(f"  Guardada ({duration_seconds(path):.1f} s).")
            return True
        print(f"  {problem}")
        answer = input("  Enter para repetir, s para saltar, q para salir: ").strip().lower()
        if answer in {"s", "q"}:
            # Una toma mala no se deja en disco: la próxima corrida la vuelve a pedir.
            path.unlink(missing_ok=True)
            return answer == "s"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list-devices", action="store_true", help="lista los micrófonos disponibles")
    parser.add_argument("--speaker", help="quién graba, en minúsculas y sin espacios (ej. miguel)")
    parser.add_argument("--take", default="quiet", help="condición de la toma: quiet, noise, car...")
    parser.add_argument("--device", help="número o nombre del micrófono según --list-devices; por defecto, el del Mac")
    parser.add_argument("--lang", choices=["es", "en"], help="solo las frases de un idioma")
    parser.add_argument("--only", help="identificadores separados por comas")
    parser.add_argument("--redo", action="store_true", help="vuelve a grabar aunque el archivo exista")
    args = parser.parse_args()

    if shutil.which("ffmpeg") is None:
        sys.exit("No encuentro ffmpeg. Instálalo con Homebrew: brew install ffmpeg")
    if args.list_devices:
        list_devices()
        return
    if not args.speaker or not SLUG.match(args.speaker) or not SLUG.match(args.take):
        sys.exit("Indica --speaker y --take en minúsculas, sin espacios (ej. --speaker miguel --take quiet).")

    device, device_name = resolve_device(args.device, audio_devices())
    phrases = json.loads((HERE / "script.json").read_text(encoding="utf-8"))["phrases"]
    if args.lang:
        phrases = [p for p in phrases if p["lang"] == args.lang]
    if args.only:
        wanted = {item.strip() for item in args.only.split(",")}
        phrases = [p for p in phrases if p["id"] in wanted]

    print(f"Micrófono: [{device}] {device_name}")
    if VIRTUAL.search(device_name):
        print("  aviso: ese dispositivo es virtual y suele grabar silencio.")
    print("Lee cada frase tal como está escrita, a tu ritmo normal de teléfono.")
    print("Si te equivocas, sáltala y vuelve a grabarla al final con --only <id> --redo.")
    print("La primera vez, macOS pide permiso de micrófono.\n")

    for index, phrase in enumerate(phrases, 1):
        out = RECORDINGS / args.speaker / args.take / f"{phrase['id']}.wav"
        if out.exists() and not args.redo:
            print(f"[{index}/{len(phrases)}] {phrase['id']}: ya grabada, se salta.")
            continue
        print(f"\n[{index}/{len(phrases)}] {phrase['id']}")
        print(f"  «{phrase['text']}»")
        if phrase.get("tip"):
            print(f"  Consejo: {phrase['tip']}")
        answer = input("  Enter para grabar, s para saltar, q para salir: ").strip().lower()
        if answer == "q":
            break
        if answer == "s":
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        if not record_until_usable(out, device):
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nGrabación detenida. Las frases guardadas se conservan: corre el mismo comando para seguir donde quedaste.")
        sys.exit(130)
