#!/usr/bin/env python3
"""Reparte los archivos de prueba del servidor en N tandas deterministas.

Imprime, uno por linea, los archivos de la tanda K (1..N). Es un reparto
codicioso por peso (el archivo mas pesado a la tanda mas liviana), con desempate
por ruta, asi que el mismo arbol da siempre el mismo reparto y la union de las N
tandas es exactamente el conjunto de archivos `test_*.py`: ninguno se pierde ni
se repite.

El peso es el tiempo estimado del archivo, en segundos, de `scripts/shard-pesos.json`
(calibrado el 2026-11-11 con los tiempos reales de la corrida de GitHub: el tamano del
archivo, que era el peso antes, dejaba una tanda en 13,7 min y otra en 4,4). Un archivo
nuevo que todavia no esta en ese archivo pesa su tamano por el promedio medido de los demas,
asi que nunca queda fuera del reparto; para recalibrar se reparte de nuevo con los tiempos
de la ultima corrida.

Uso: python3 scripts/shard-pruebas.py K N
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PRUEBAS = RAIZ / "app" / "backend" / "tests"
PESOS = Path(__file__).resolve().parent / "shard-pesos.json"


def archivos() -> list[tuple[float, str]]:
    """Cada archivo de prueba con su peso: segundos estimados, o su tamano escalado si es nuevo."""
    conocidos: dict[str, float] = (
        json.loads(PESOS.read_text(encoding="utf-8")) if PESOS.exists() else {}
    )
    rutas = {
        ruta.relative_to(RAIZ).as_posix(): ruta.stat().st_size
        for ruta in PRUEBAS.rglob("test_*.py")
    }
    bytes_conocidos = sum(tam for rel, tam in rutas.items() if rel in conocidos)
    segundos_por_byte = (
        sum(conocidos[rel] for rel in rutas if rel in conocidos) / bytes_conocidos
        if bytes_conocidos
        else 1.0
    )
    return [
        (conocidos.get(rel, tam * segundos_por_byte), rel) for rel, tam in rutas.items()
    ]


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
