"""Cada motivo de rechazo con su clave del catalogo, y ninguna frase aqui.

**Ninguna salida imprime el valor interno de un motivo.** `rate_limited_site` no
es texto para una persona: es un valor cerrado del modelo, y la frase que se lee
sale del catalogo en el idioma de la conversacion (convencion 4 del equipo).

La correspondencia se escribe entera, motivo por motivo, y **no se compone**.
Una clave armada con `f"spend.quota.{motivo.value}"` seria mas corta y romperia
dos cosas a la vez: el chequeo que exige un consumidor **literal** para cada
clave del catalogo dejaria de encontrarlas --y las daria por muertas-- y un
motivo nuevo sin su clave no fallaria en ningun sitio, solo saldria vacio en
pantalla.

## Por que el corte de la voz no tiene clave propia

AC5.14.3 fija la frase con la que la voz rechaza una llamada cuando el
presupuesto se agoto, y `budget_exhausted` es el motivo con el que la rechaza.
**Son la misma cosa dicha dos veces**, asi que llevan una sola clave: dos
entradas con el mismo texto es como un dia dejan de decir lo mismo, y entonces
la frase que el criterio fija y la que el visitante ve dejan de ser la misma.

## La discrepancia que esta frase arrastra, dicha

El motivo `budget_exhausted` sale tambien cuando el presupuesto **no se pudo
calcular** --la reserva de grabacion no esta medida-- porque el enum que consume
C-08 tiene cuatro valores cerrados y ampliarlo es tocar un contrato ya firmado.
Dentro no se colapsan: `BudgetStatus` distingue `exhausted` de `unmeasured` y el
panel de gasto muestra "no medida" en vez de "agotado". Hacia el visitante, en
cambio, las dos causas comparten esta frase. Queda escrito aqui en vez de
heredarse en silencio; el dia que C-08 se enmiende, entra su clave propia.
"""

from __future__ import annotations

from untangle.copy_catalog.api import CopyKey
from untangle.telemetry.spend.models import QuotaReason

QUOTA_REASON_KEYS: dict[QuotaReason, CopyKey] = {
    QuotaReason.RATE_LIMITED_SESSION: CopyKey("spend.quota.rate_limited_session"),
    QuotaReason.RATE_LIMITED_DAILY: CopyKey("spend.quota.rate_limited_daily"),
    QuotaReason.RATE_LIMITED_SITE: CopyKey("spend.quota.rate_limited_site"),
    #: La frase de AC5.14.3, literal. Es a la vez el motivo de cuota y el mensaje
    #: con el que la voz corta antes de pedir el microfono (BR4.4).
    QuotaReason.BUDGET_EXHAUSTED: CopyKey("spend.quota.budget_exhausted"),
}


def all_keys() -> frozenset[CopyKey]:
    """Todas las claves que este modulo promete que el catalogo trae."""
    return frozenset(QUOTA_REASON_KEYS.values())
