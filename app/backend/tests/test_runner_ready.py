"""Caso trivial que comprueba que el runner de Python esta instalado y corre.

Existe por el paso 5 del plan: el contrato de pruebas exige que el runner quede
ejecutable ANTES de la primera prueba real, porque la linea base es cero y no hay
ningun runner que verificar. No prueba conducta del aplicativo; prueba que la
herramienta arranca.
"""

from __future__ import annotations

import sys


def test_el_runner_corre_sobre_el_interprete_anclado() -> None:
    assert sys.version_info[:2] == (3, 13)
