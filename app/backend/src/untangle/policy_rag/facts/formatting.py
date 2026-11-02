"""Montos y fechas escritos para un idioma, igual que la pestana de polizas (plan 09, punto 6).

No es un formato nuevo: reproduce el de `app/frontend/src/pages/policies/policies-page.tsx`
(`formatPesos` y `formatDate`, con `Intl` en `es-CO` y `en-US`), para que la agente, el servidor MCP y
la pantalla de polizas digan lo mismo de la misma poliza. Una prueba compara los textos contra los
que produce `Intl` en esa pantalla. Se escribe a mano porque la biblioteca estandar no trae
formato por idioma y una dependencia de internacionalizacion para dos formatos no se justifica.

**La unidad.** El corpus guarda miles de pesos colombianos (decision de Miguel del 2026-10-07): un
`1500` del corpus son `$ 1.500.000`.
"""

from __future__ import annotations

from datetime import date

from untangle.base import Locale

#: Los montos del corpus son miles de pesos. El mismo valor que `PESOS_POR_UNIDAD` de la pantalla.
PESOS_PER_UNIT = 1000

#: Espacio de no separacion: lo que pone `Intl` entre el simbolo de la moneda y la cifra.
_NBSP = "\xa0"

_MESES: dict[Locale, tuple[str, ...]] = {
    "es": (
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    ),
    "en": (
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ),
}


def to_pesos(units: int) -> int:
    """Los pesos colombianos de un monto del corpus."""
    return units * PESOS_PER_UNIT


def format_pesos(units: int, language: Locale, *, spoken: bool = False) -> str:
    """Un monto del corpus en pesos, para ese idioma.

    Escrito: `$ 1.500.000` en espanol y `COP 1,500,000` en ingles, como la pestana de polizas.
    Hablado --una llamada--: la cifra con la palabra, sin simbolo ni codigo de moneda
    (`1.500.000 pesos`, `1,500,000 Colombian pesos`), que es lo que un sintetizador de voz lee bien.
    """
    pesos = to_pesos(units)
    if language == "es":
        cifra = f"{pesos:,}".replace(",", ".")
        return f"{cifra} pesos" if spoken else f"${_NBSP}{cifra}"
    cifra = f"{pesos:,}"
    return f"{cifra} Colombian pesos" if spoken else f"COP{_NBSP}{cifra}"


def format_date(day: date, language: Locale) -> str:
    """Una fecha larga: `14 de junio de 2026` o `June 14, 2026`."""
    mes = _MESES[language][day.month - 1]
    if language == "es":
        return f"{day.day} de {mes} de {day.year}"
    return f"{mes} {day.day}, {day.year}"


__all__ = ["PESOS_PER_UNIT", "format_date", "format_pesos", "to_pesos"]
