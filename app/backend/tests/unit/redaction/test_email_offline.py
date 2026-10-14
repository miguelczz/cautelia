"""Validar un correo no sale a internet (C-13, enmienda del 2026-09-21).

El reconocedor de correos del motor valida el dominio con la lista publica de
sufijos. Con la configuracion por defecto de `tldextract`, la primera validacion
en una maquina sin cache intentaba descargar esa lista de publicsuffix.org. En
la maquina de Miguel la cache ya existia y nadie lo vio; en GitHub Actions no
existia, y la guardia de red de U7 lo detuvo. La redaccion corre en cada punto de
salida: no puede depender de la red ni avisar a un tercero de que esta
procesando un correo.

La prueba reproduce las condiciones de GitHub Actions en un proceso aparte --una
cache vacia y la red bloqueada-- porque la cache y el extractor son estado del
proceso: dentro de la misma corrida de pruebas, otra prueba ya los habria llenado.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_PROGRAMA = """
import socket

intentos = []

def sin_red(host, *args, **kwargs):
    intentos.append(host)
    raise OSError("sin red en la prueba")

socket.getaddrinfo = sin_red

from untangle.compliance.redaction.detector import OfflineEmailRecognizer

reconocedor = OfflineEmailRecognizer()
assert reconocedor.validate_result("ana.rios@example.com") is True
assert reconocedor.validate_result("ana.rios@example.invalidsuffixzz") is False
assert intentos == [], intentos
print("sin red")
"""


def _correr_sin_cache(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    entorno = dict(os.environ)
    entorno["TLDEXTRACT_CACHE"] = str(tmp_path / "cache-vacia")
    return subprocess.run(  # noqa: S603 - el ejecutable es el mismo interprete de la prueba
        [sys.executable, "-c", _PROGRAMA],
        capture_output=True,
        text=True,
        env=entorno,
        check=False,
        timeout=60,
    )


def test_validar_un_correo_con_la_cache_vacia_no_intenta_salir_a_internet(tmp_path: Path) -> None:
    resultado = _correr_sin_cache(tmp_path)

    assert resultado.returncode == 0, resultado.stderr
    assert resultado.stdout.strip() == "sin red"


def test_el_detector_registra_la_version_sin_red_bajo_el_nombre_declarado() -> None:
    """Los archivos de reconocedores siguen diciendo `EmailRecognizer`."""
    from untangle.compliance.redaction.detector import (
        RECONOCEDORES_DEL_MOTOR,
        OfflineEmailRecognizer,
    )

    assert RECONOCEDORES_DEL_MOTOR["EmailRecognizer"] is OfflineEmailRecognizer
