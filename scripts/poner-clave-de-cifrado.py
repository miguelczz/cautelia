#!/usr/bin/env python3
"""Genera la clave de cifrado de los campos del caso y la pone en `.env`, sin imprimirla.

`UNTANGLE_CASE_FIELD_ENCRYPTION_KEY` es la que cifra en reposo los datos personales del
caso (NFRD-U4-4). A diferencia de las claves de proveedor, esta **se genera aqui**: no
hay ninguna cuenta de donde sacarla.

**Por que existe en vez de la linea de una sola vez.** `.env.example` documentaba esto:

    python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'

y esa linea tiene dos problemas, los dos vistos el 2026-09-29. Falla con
`ModuleNotFoundError` porque `cryptography` es dependencia del backend y no del Python
del sistema. Y, sobre todo, **imprime la clave**: queda en la pantalla, en el historial
de la terminal y en el registro de cualquier sesion que la vea pasar. Una clave impresa
se considera comprometida, y aqui no hay proveedor donde rotarla: rotarla es generar
otra, que es exactamente lo que hace este comando.

Hace las mismas tres cosas que el guion de las claves de voz, por las mismas razones:

1. **Comprueba que `.env` esta ignorado por git** antes de escribir nada.
2. **Actualiza la linea en su sitio** en vez de duplicarla: dos lineas con la misma
   variable dejan el valor que gane al azar.
3. **No imprime el valor.** Ni completo, ni un trozo, ni su longitud.

Rotar **no** vuelve ilegible lo guardado: cada fila lleva el identificador de la clave
que la cifro, asi que las viejas se siguen leyendo con la vieja mientras el proceso la
tenga (decision de Miguel, NFRD-U4-1). Lo que pasa al rotar sin conservar la vieja es
que esas filas devuelven "no disponible" y el caso se abre igual con el campo marcado.
Por eso este comando **no borra** la clave anterior de tu `.env` si le pides conservarla.

Uso:

    mise run claves:cifrado              genera una y la pone (pide confirmacion si ya hay)
    mise run claves:cifrado -- --forzar  la reemplaza sin preguntar
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from cryptography.fernet import Fernet

RAIZ = Path(__file__).resolve().parent.parent
ENV = RAIZ / ".env"
VARIABLE = "UNTANGLE_CASE_FIELD_ENCRYPTION_KEY"


def _esta_ignorado() -> bool:
    """Si git ignora `.env`. Sin esto no se escribe nada."""
    resultado = subprocess.run(
        ["git", "check-ignore", "-q", ".env"],
        cwd=RAIZ,
        capture_output=True,
        check=False,
    )
    return resultado.returncode == 0


def _poner(lineas: list[str], valor: str) -> list[str]:
    """Reemplaza la linea de la variable, o la anade al final."""
    nueva = f"{VARIABLE}={valor}"
    for indice, linea in enumerate(lineas):
        if linea.startswith(f"{VARIABLE}="):
            lineas[indice] = nueva
            return lineas
    if lineas and lineas[-1].strip():
        lineas.append("")
    lineas.append(nueva)
    return lineas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--forzar",
        action="store_true",
        help="Reemplaza la clave que ya haya, sin preguntar.",
    )
    argumentos = parser.parse_args()

    if not _esta_ignorado():
        print(
            "`.env` no esta ignorado por git y no se escribe nada: una clave que llega\n"
            "a un commit se considera comprometida. Revisa el `.gitignore` primero.",
            file=sys.stderr,
        )
        return 1

    lineas = ENV.read_text(encoding="utf-8").splitlines() if ENV.exists() else []
    ya_tiene = any(
        linea.startswith(f"{VARIABLE}=") and linea.split("=", 1)[1].strip()
        for linea in lineas
    )
    if ya_tiene and not argumentos.forzar:
        print(
            f"{VARIABLE} ya tiene valor. Reemplazarlo deja los campos cifrados con la\n"
            "clave anterior como «no disponible» mientras el proceso no la tenga (el\n"
            "caso se abre igual, con el campo marcado). Para hacerlo:\n\n"
            "    mise run claves:cifrado -- --forzar",
            file=sys.stderr,
        )
        return 1

    ENV.write_text(
        "\n".join(_poner(lineas, Fernet.generate_key().decode())) + "\n", "utf-8"
    )
    print(f"{VARIABLE} escrita en .env. No se imprimio y no salio de este archivo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
