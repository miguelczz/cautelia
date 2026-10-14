#!/usr/bin/env python3
"""Pone en tu `.env` las claves de la voz, sin imprimirlas, o renombra las viejas.

Dos modos.

**Pedir claves** (`mise run claves:voz`). Las pide una por una **sin que se
impriman en pantalla** y las escribe en `.env`. Nadie mas las ve: ni quedan en
el historial de la terminal, ni salen en la salida del guion, ni viajan a ningun
sitio.

**Renombrar** (`mise run claves:voz -- --renombrar`). Desde U15, las claves de
Deepgram y de Cartesia son del **uso `voice`** del aplicativo y se leen por el
punto unico de `settings.py`, con el prefijo del aplicativo:
`UNTANGLE_VOICE_DEEPGRAM_API_KEY` y `UNTANGLE_VOICE_CARTESIA_API_KEY`. El
experimento 1 las dejo con sus nombres de entonces, `DEEPGRAM_API_KEY` y
`CARTESIA_API_KEY`. Este modo cambia **solo el nombre antes del `=`** de esas dos
lineas, en su sitio: no lee el valor hacia ninguna salida, no lo copia a otra
linea y no toca ninguna otra. Si el nombre nuevo ya existe, no toca esa pareja y
lo dice: dos lineas para la misma clave dejan el valor que gane al azar.

Tres cosas que hace antes de escribir, en los dos modos, y por las que existe
este guion en vez de un `echo >>` o un `sed`:

1. **Comprueba que `.env` esta ignorado por git.** Si no lo estuviera, se detiene
   sin escribir nada: una clave que llega a un commit se considera comprometida y
   hay que rotarla en el proveedor, y eso es peor que no tener el archivo.
2. **Actualiza en vez de duplicar.** Si la variable ya estaba, reemplaza su linea
   en su sitio. Dos lineas con la misma variable dejan el valor que gane al azar
   segun quien lea el archivo.
3. **Respeta lo que ya escribiste.** Si le das enter sin escribir nada a una
   variable que ya tiene valor, la deja como estaba.

**La linea `CARTESIA_VOICE_ID` ya no la lee nadie.** El identificador de la voz
de Catalina no es un secreto y paso a la configuracion versionada de cada
aseguradora (`voice.primary` en su `tenant.yaml`, CG-U15-5), que es donde el
proyecto declara proveedor, modelo y voz. Este guion ya no la pide y no la
borra: borrarla es decision tuya, y dejarla no hace dano.

Uso:

    mise run claves:voz
    mise run claves:voz -- --renombrar

Despues:

    mise run voice:contract-live
"""

from __future__ import annotations

import getpass
import subprocess
import sys
import webbrowser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ENV = RAIZ / ".env"

#: Que se pide, de donde sale, y la pagina que se abre para que no haya que
#: buscarla. El texto y la direccion son lo unico que se imprime: el valor nunca.
#:
#: Las claves no se pueden sacar solas y esa es la razon, no una limitacion del
#: guion: crearlas exige entrar a tus cuentas, y una clave que pasa por las manos
#: de otro deja de ser tuya. Lo que si se puede quitar es todo lo demas --buscar
#: la pantalla, abrir el archivo, no duplicar la linea--, que es lo que hace esto.
VARIABLES = (
    (
        "UNTANGLE_VOICE_DEEPGRAM_API_KEY",
        "https://console.deepgram.com/",
        'Entra, y en el menu de la izquierda: "API Keys" → "Create a New API Key".\n'
        "      Dale permiso de miembro y copiala: **solo se muestra una vez**. Es la\n"
        "      de la transcripcion y de la voz de respaldo (Aura-2).",
    ),
    (
        "UNTANGLE_VOICE_CARTESIA_API_KEY",
        "https://play.cartesia.ai/keys",
        "Esa pagina ya es la de claves. Boton de crear, y copiala. Es la de\n"
        "      Catalina, la voz principal.",
    ),
    (
        # Se incluye aqui para que **rotarla** sea este mismo comando. El
        # 2026-09-21 se imprimio en una traza del experimento 1 --la primera
        # version mandaba la clave en la URL y un error la saco entera--, y por
        # la regla del proyecto una clave que se imprime se rota en el proveedor.
        "UNTANGLE_VOICE_MODEL_API_KEY",
        "https://aistudio.google.com/apikey",
        "Es la clave del proyecto de voz de Gemini. Para rotarla: borra la\n"
        "      vieja en esa pagina, crea una nueva en el MISMO proyecto de voz, y\n"
        "      pegala aqui. Crearla en otro proyecto juntaria las cuotas.",
    ),
)

#: Los nombres del experimento 1 y los del aplicativo. El modo `--renombrar`
#: cambia el primero por el segundo **solo en el nombre**.
RENOMBRES = (
    ("DEEPGRAM_API_KEY", "UNTANGLE_VOICE_DEEPGRAM_API_KEY"),
    ("CARTESIA_API_KEY", "UNTANGLE_VOICE_CARTESIA_API_KEY"),
)


def _esta_ignorado() -> bool:
    """Si git ignora `.env`. Sin esto no se escribe nada."""
    resultado = subprocess.run(
        ["git", "check-ignore", "-q", ".env"],
        cwd=RAIZ,
        capture_output=True,
        check=False,
    )
    return resultado.returncode == 0


def _leer() -> list[str]:
    if not ENV.exists():
        return []
    return ENV.read_text(encoding="utf-8").splitlines()


def _valor_actual(lineas: list[str], nombre: str) -> str | None:
    for linea in lineas:
        if linea.startswith(f"{nombre}="):
            valor = linea.split("=", 1)[1].strip()
            return valor or None
    return None


def _poner(lineas: list[str], nombre: str, valor: str) -> list[str]:
    """Reemplaza la linea de esa variable, o la anade al final."""
    nueva = f"{nombre}={valor}"
    for indice, linea in enumerate(lineas):
        if linea.startswith(f"{nombre}="):
            lineas[indice] = nueva
            return lineas
    if lineas and lineas[-1].strip():
        lineas.append("")
    lineas.append(nueva)
    return lineas


def _indices(lineas: list[str], nombre: str) -> list[int]:
    return [i for i, linea in enumerate(lineas) if linea.startswith(f"{nombre}=")]


def renombrar() -> int:
    """Cambia los dos nombres viejos por los del aplicativo, sin tocar valores.

    Trabaja sobre el texto de cada linea y solo reescribe lo que va **antes del
    primer `=`**. El resto de la linea se copia tal cual, sin pasar por ninguna
    variable que se imprima. Devuelve cuantas lineas renombro.
    """
    lineas = _leer()
    if not lineas:
        print("No hay `.env` que renombrar.")
        return 0

    cambios = 0
    for viejo, nuevo in RENOMBRES:
        viejas = _indices(lineas, viejo)
        nuevas = _indices(lineas, nuevo)
        if not viejas:
            estado = "ya estaba" if nuevas else "no esta en el archivo"
            print(f"  {viejo}: sin cambios ({nuevo} {estado}).")
            continue
        if nuevas:
            print(
                f"  {viejo}: sin cambios. {nuevo} ya existe, y dos lineas para la "
                "misma clave dejan el valor que gane al azar. Borra una de las dos a mano."
            )
            continue
        if len(viejas) > 1:
            print(f"  {viejo}: sin cambios. Aparece {len(viejas)} veces; deja una sola a mano.")
            continue
        indice = viejas[0]
        lineas[indice] = nuevo + lineas[indice][len(viejo) :]
        cambios += 1
        print(f"  {viejo} -> {nuevo}")

    if cambios:
        ENV.write_text("\n".join(lineas) + "\n", encoding="utf-8")
        ENV.chmod(0o600)
        print(f"Renombradas {cambios} en {ENV.name}, con permisos solo para ti.")
    else:
        print("No cambio nada.")
    return cambios


def pedir() -> None:
    lineas = _leer()
    print("Las claves de la voz. No se imprime lo que escribas.")
    print("Enter sin escribir nada deja la que ya tengas.\n")

    cambios = 0
    for nombre, direccion, de_donde in VARIABLES:
        tenia = _valor_actual(lineas, nombre) is not None
        estado = "ya la tienes" if tenia else "falta"
        print(f"  {nombre}  ({estado})")
        print(f"      {direccion}")
        print(f"      {de_donde}")
        if not tenia:
            # Se abre la pagina exacta para no tener que buscarla. Si no hay
            # navegador disponible no pasa nada: la direccion ya esta impresa.
            webbrowser.open(direccion)
        try:
            valor = getpass.getpass("      valor: ").strip()
        except (EOFError, KeyboardInterrupt):
            # Sin terminal interactiva no hay forma de pedir un secreto sin que
            # quede escrito en algun sitio, asi que no se pide: se para.
            print(
                "\n\nEsto necesita una terminal donde puedas escribir. "
                "Correlo tu mismo con:\n    mise run claves:voz",
                file=sys.stderr,
            )
            raise SystemExit(130) from None
        print()
        if not valor:
            if not tenia:
                print(f"      {nombre} sigue sin valor; la voz fallara nombrandola.\n")
            continue
        lineas = _poner(lineas, nombre, valor)
        cambios += 1

    if cambios:
        ENV.write_text("\n".join(lineas) + "\n", encoding="utf-8")
        ENV.chmod(0o600)
        print(f"Escritas {cambios} en {ENV.name}, con permisos solo para ti.")
    else:
        print("No cambio nada.")

    faltan = [n for n, _, _ in VARIABLES if _valor_actual(_leer(), n) is None]
    if faltan:
        print("\nTodavia falta: " + ", ".join(faltan))
    else:
        print("\nListo. Ahora: mise run voice:contract-live")


def main() -> None:
    if not _esta_ignorado():
        print(
            "`.env` no esta ignorado por git y no voy a escribir claves ahi.\n"
            "Anade `.env` al `.gitignore` primero. Una clave que llega a un "
            "commit se considera comprometida y hay que rotarla en el proveedor.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    if "--renombrar" in sys.argv[1:]:
        renombrar()
        return
    pedir()


if __name__ == "__main__":
    main()
