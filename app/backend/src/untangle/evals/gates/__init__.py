"""La memoria entre corridas: linea base, inestables, explicaciones y compuerta.

Convierte el reporte de una corrida (`untangle.evals.report`) en una decision
de si la entrega pasa. Vive fuera de `untangle.evals.runner` a proposito: el
corredor ejecuta casos y no conoce el pasado, y la compuerta necesita el
pasado para decidir (TECH-U21.4).
"""

from __future__ import annotations
