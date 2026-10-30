"""Las sondas de DS-6 que miden la redaccion: RT-14 y RT-15.

Son chequeos deterministas --se resuelven sin llamar a ningun modelo de
lenguaje-- pero **no sin los modelos de spaCy**: lo que miden es que detecta el
detector, y un doble no detecta nada. Por eso el subconjunto `rt14` necesita
`mise run models:install` y el subconjunto de arranque no.

Dos sondas y no una, porque miden dos cosas distintas:

- **RT-14** comprueba que ningun valor sembrado sale en claro, sobre los tipos
  por formato --los cuatro propios del dominio y el VIN-- en sus tres formas de
  escritura.
- **RT-15** comprueba que dictar el dato en el otro idioma no lo saca en claro,
  y ademas que el informe **atribuye el hallazgo al reconocedor que lo
  encontro** y no al idioma del turno (BR2.9). Sin esa segunda mitad, la
  medicion por idioma diria que un idioma funciona cuando quien atrapo el dato
  fue el otro juego.

**Ningun detalle de fallo imprime el valor sembrado.** El reporte de
evaluaciones es uno de los cinco puntos de salida (BR4.4, SEC-U3.14): describe la
diferencia --que semilla, que tipo, que idioma-- sin mostrar lo que se escapo.
Un mensaje de diagnostico que imprimiera el valor convertiria a la sonda en el
punto de fuga que existe para detectar.
"""

from __future__ import annotations

from pathlib import Path

from untangle.base import Locale
from untangle.compliance.redaction import api as redaction
from untangle.evals.models import Dataset
from untangle.evals.redaction_fixtures import Seed, expected_recognizer_id, load_fixtures
from untangle.evals.runner.api import CheckOutcome, EvalTarget, register_check, register_targets

#: La unidad a la que se le miden estas comprobaciones (C-22).
UNIT = "u3-pii-redaction"


def _sin_valor_sembrado(seed: Seed, redactado: str) -> str | None:
    """El problema si el valor sembrado sigue visible. Nunca imprime el valor."""
    if seed.value in redactado:
        return f"{seed.id} ({seed.entity_type.value}, forma {seed.form}): el valor sembrado sigue en el texto"
    return None


def _tipo_contado(seed: Seed, informe: redaction.RedactionReport) -> str | None:
    """El problema si el informe no cuenta ningun hallazgo del tipo sembrado."""
    if informe.counts_by_type.get(seed.entity_type, 0) < 1:
        return (
            f"{seed.id} ({seed.entity_type.value}, forma {seed.form}): el informe "
            f"cuenta {informe.counts_by_type.get(seed.entity_type, 0)} hallazgos de su tipo"
        )
    return None


def rt14_seeded_pii_redacted(*, language: Locale, root: Path) -> CheckOutcome:
    """RT-14: ningun valor sembrado sale en claro, en ninguna de sus tres formas.

    Compuerta dura de NFR11: un solo hallazgo detiene la entrega. No hay umbral
    que bajar ni promedio que lo diluya.
    """
    fixtures = load_fixtures(language, root)
    problemas: list[str] = []

    for seed in fixtures.seeds:
        redactado = redaction.redact(seed.text, language=language)
        informe = redaction.redaction_report(seed.text, language=language)
        problemas.extend(
            problema
            for problema in (_sin_valor_sembrado(seed, redactado), _tipo_contado(seed, informe))
            if problema is not None
        )

    if problemas:
        return CheckOutcome(passed=False, detail="; ".join(problemas))
    return CheckOutcome(passed=True)


def rt15_cross_language_redacted(*, language: Locale, root: Path) -> CheckOutcome:
    """RT-15: dictar el dato en el otro idioma no lo saca en claro.

    Dos mitades. La primera es la compuerta dura AC4.13.4: el dato se tapa igual.
    La segunda es BR2.9: el informe tiene que atribuir el hallazgo al reconocedor
    que lo encontro --el juego del otro idioma-- y no al idioma del turno. Sin
    ella, un reconocedor roto de un idioma quedaria escondido detras del otro.
    """
    fixtures = load_fixtures(language, root)
    problemas: list[str] = []

    for seed in fixtures.cross_language:
        redactado = redaction.redact(seed.text, language=language)
        informe = redaction.redaction_report(seed.text, language=language)

        problemas.extend(
            problema
            for problema in (_sin_valor_sembrado(seed, redactado), _tipo_contado(seed, informe))
            if problema is not None
        )

        esperado = expected_recognizer_id(seed)
        if informe.counts_by_recognizer.get(esperado, 0) < 1:
            problemas.append(
                f"{seed.id} ({seed.entity_type.value}): el informe no atribuye "
                f"ningun hallazgo a '{esperado}', que es el reconocedor del idioma "
                f"en que viene dictado; atribuirlo al idioma del turno esconderia "
                "un reconocedor roto detras del otro (BR2.9)"
            )

    if problemas:
        return CheckOutcome(passed=False, detail="; ".join(problemas))
    return CheckOutcome(passed=True)


#: Las sondas que U3 aporta al corredor, por el criterio que resuelven.
SONDAS = {
    "rt14_seeded_pii_redacted": rt14_seeded_pii_redacted,
    "rt15_cross_language_redacted": rt15_cross_language_redacted,
}

#: Las dos son compuertas duras (NFR11 [bloquea], AC4.13.4 [bloquea]): un solo
#: hallazgo detiene la entrega y ninguna explicacion de regresion lo levanta
#: (U21, correccion del 2026-09-25).
TARGETS: tuple[EvalTarget, ...] = (
    EvalTarget(
        "rt14_seeded_pii_redacted",
        Dataset.DS_6,
        "RT-14: ningun valor sembrado sale en claro, en ninguna de sus tres formas "
        "(NFR11 [bloquea])",
        blocking=True,
    ),
    EvalTarget(
        "rt15_cross_language_redacted",
        Dataset.DS_6,
        "RT-15: dictar el dato en el otro idioma no lo saca en claro (AC4.13.4 [bloquea])",
        blocking=True,
    ),
)


def register_redaction_probes() -> None:
    """Registra las sondas y los objetivos de redaccion en el corredor."""
    for criterio, sonda in SONDAS.items():
        register_check(criterio, sonda)
    register_targets(UNIT, TARGETS)
