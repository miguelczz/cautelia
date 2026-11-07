#!/usr/bin/env python3
"""Reparte los archivos de prueba del servidor en N tandas deterministas.

Imprime, uno por linea, los archivos de la tanda K (1..N). Es un reparto
codicioso por peso (el archivo mas pesado a la tanda mas liviana), con desempate
por ruta, asi que el mismo arbol da siempre el mismo reparto y la union de las N
tandas es exactamente el conjunto de archivos `test_*.py`: ninguno se pierde ni
se repite. El peso es el tamano del archivo, mayor en integracion porque cada
prueba levanta la base (medido: ~1,0 ms/byte contra ~0,64 en unitarias).

Uso: python3 scripts/shard-pruebas.py K N
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PRUEBAS = RAIZ / "app" / "backend" / "tests"
FACTOR_INTEGRACION = 1.6


def archivos() -> list[tuple[float, str]]:
    salida = []
    for ruta in PRUEBAS.rglob("test_*.py"):
        rel = ruta.relative_to(RAIZ).as_posix()
        peso = ruta.stat().st_size * (FACTOR_INTEGRACION if "/integration/" in rel else 1.0)
        salida.append((peso, rel))
    return salida


def tanda(k: int, n: int) -> list[str]:
    cargas = [0.0] * n
    reparto: list[list[str]] = [[] for _ in range(n)]
    for peso, rel in sorted(archivos(), key=lambda x: (-x[0], x[1])):
        destino = min(range(n), key=lambda i: (cargas[i], i))
        cargas[destino] += peso
        reparto[destino].append(rel)
    return sorted(reparto[k - 1])


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 64
    k, n = int(sys.argv[1]), int(sys.argv[2])
    if not 1 <= k <= n:
        print(f"tanda fuera de rango: {k}/{n}", file=sys.stderr)
        return 64
    lista = tanda(k, n)
    if not lista:
        print(f"la tanda {k}/{n} quedo vacia", file=sys.stderr)
        return 1
    print("\n".join(lista))
    return 0


if __name__ == "__main__":
    sys.exit(main())
