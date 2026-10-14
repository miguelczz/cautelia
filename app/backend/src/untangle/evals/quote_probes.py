"""Las sondas de DS-4 que miden la cotizacion (U19): elegibilidad, banda y lo que no se puede decir.

Seis comprobaciones, una por criterio. Llaman al **motor real** (`rules.eligibility`) y a las
**frases reales** del catalogo, y pasan cada respuesta por **la guardia de salida de verdad**: no
construyen un detector de importes propio (FD-U19-1), porque un segundo detector es un segundo
umbral que un dia discrepa del primero.

Corren contra la configuracion real de las aseguradoras. Son de reglas, sin base de datos y sin
modelo, y por eso sus casos entran al subconjunto de arranque. Lo que esta unidad mide contra un
modelo --que la conversacion de punta a punta llegue al final y que la agente no ceda ante la
presion-- vive en los casos de canal de DS-4 (`requires_provider_key`), que **se escriben y se
validan de forma, y no se ejecutan aqui**.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from untangle.base import Locale
from untangle.case_record.models import RecordType
from untangle.compliance.controls import patterns
from untangle.compliance.controls.guard import GuardContext, GuardTurn, evaluate
from untangle.evals import quote_fixtures as fx
from untangle.evals.models import Dataset
from untangle.evals.runner.api import CheckOutcome, EvalTarget, register_check, register_targets
from untangle.orchestration import quote_reply
from untangle.rules import eligibility
from untangle.tenancy import config as tenancy_config

#: La unidad a la que se le miden estas comprobaciones (C-22).
UNIT = "u19-quote"

#: Los escenarios de elegibilidad que se miden por criterio. Los umbrales se prueban por
#: sus dos lados: `referral` tiene que derivar y `no-referral` no (NFR13: derivaciones
#: innecesarias).
_ESCENARIOS_DE_ELEGIBILIDAD = ("eligibility",)
_ESCENARIOS_DE_DERIVACION = ("referral", "no-referral")
_TODOS = (*_ESCENARIOS_DE_ELEGIBILIDAD, *_ESCENARIOS_DE_DERIVACION)

#: Ni una cifra ni un simbolo de moneda ni un porcentaje: lo que la guardia ya vigila, dicho
#: otra vez como comprobacion de lo que *esta unidad* escribe, no como detector de lo que dice
#: el modelo. Sirve para la negativa fija, que no lleva ningun numero por construccion.
_SIN_CIFRAS = re.compile(r"[\d$€%]")


def _problemas_de_guardia(frase: str, *, language: Locale, tenant_id: str) -> list[str]:
    """Lo que la guardia real le hace a una frase, o nada si sale intacta."""
    contexto = GuardContext.for_tenant(
        tenant_id, language=language, tenants=tenancy_config.loaded().available
    )
    resultado = evaluate(frase, library=patterns.load_library(), context=contexto, turn=GuardTurn())
    if resultado.unchanged and resultado.text_out == frase:
        return []
    categorias = ", ".join(i.category.value for i in resultado.interventions if i.category)
    return [f"la guardia la intercepta ({categorias or 'sin evaluar'}): {frase!r}"]


def _respuesta_de(
    fila: fx.EligibilityRow, *, language: Locale
) -> tuple[str, eligibility.EligibilityOutcome]:
    conjunto = eligibility.require(fila.tenant_id)
    salida = eligibility.evaluate_eligibility(conjunto, fila.inputs)
    texto = quote_reply.compose_eligibility_reply(
        salida.outcome.value, salida.band.value, salida.explanation_key, language=language
    )
    return texto, salida


# --- La elegibilidad ---------------------------------------------------------------------


def _problemas_de_elegibilidad(
    fixtures: fx.QuoteFixtures, escenarios: tuple[str, ...]
) -> list[str]:
    filas = fixtures.eligibility_for(*escenarios)
    if not filas:
        return [f"los escenarios {list(escenarios)} no tienen filas: no se midio nada"]
    problemas: list[str] = []
    for fila in filas:
        try:
            salida = eligibility.evaluate_eligibility(
                eligibility.require(fila.tenant_id), fila.inputs
            )
        except Exception as error:  # noqa: BLE001 -- una compuerta que no se pudo ejecutar nunca es verde
            problemas.append(f"{fila.id}: el motor no pudo evaluar ({error})")
            continue
        if salida.outcome.value != fila.expected_outcome:
            problemas.append(
                f"{fila.id}: se esperaba '{fila.expected_outcome}' y dio '{salida.outcome.value}'"
            )
        if salida.band.value != fila.expected_band:
            problemas.append(
                f"{fila.id}: se esperaba la banda '{fila.expected_band}' y dio '{salida.band.value}'"
            )
        if salida.deciding_rules != fila.expected_rules:
            problemas.append(
                f"{fila.id}: decidieron {list(salida.deciding_rules)} y se esperaban "
                f"{list(fila.expected_rules)}"
            )
    return problemas


def _sonda_de_elegibilidad(*escenarios: str) -> Callable[..., CheckOutcome]:
    def comprobar(*, language: Locale, root: Path) -> CheckOutcome:
        try:
            fixtures = fx.load_quote_fixtures(language, root)
        except fx.QuoteFixtureError as error:
            return CheckOutcome(passed=False, detail=str(error))
        problemas = _problemas_de_elegibilidad(fixtures, escenarios)
        return CheckOutcome(passed=not problemas, detail="; ".join(problemas))

    return comprobar


# --- Lo que no se puede decir ------------------------------------------------------------


def _sin_importes(*, language: Locale, root: Path) -> CheckOutcome:
    """BR3.1 [bloquea]: ninguna respuesta de la cotizacion lleva un importe, una moneda ni un porcentaje."""
    try:
        fixtures = fx.load_quote_fixtures(language, root)
    except fx.QuoteFixtureError as error:
        return CheckOutcome(passed=False, detail=str(error))

    problemas: list[str] = []
    filas = fixtures.eligibility_for(*_TODOS)
    if not filas:
        return CheckOutcome(passed=False, detail="no hay filas de elegibilidad: no se midio nada")
    for fila in filas:
        try:
            texto, _ = _respuesta_de(fila, language=language)
        except Exception as error:  # noqa: BLE001 -- una compuerta que no se pudo ejecutar nunca es verde
            problemas.append(f"{fila.id}: no se pudo componer la respuesta ({error})")
            continue
        problemas += [
            f"{fila.id}: {p}"
            for p in _problemas_de_guardia(texto, language=language, tenant_id=fila.tenant_id)
        ]
    # Las demas respuestas de la cotizacion: la negativa fija, con y sin banda, y la de «no cotiza».
    for banda in (None, *(b.value for b in eligibility.RiskBand)):
        negativa = quote_reply.compose_price_refusal(banda, language=language)
        problemas += [
            f"negativa({banda}): {p}"
            for p in _problemas_de_guardia(negativa.text, language=language, tenant_id="")
        ]
    apagada = quote_reply.compose_unavailable(language=language)
    problemas += [
        f"no-cotiza: {p}"
        for p in _problemas_de_guardia(apagada.text, language=language, tenant_id="")
    ]
    return CheckOutcome(passed=not problemas, detail="; ".join(problemas))


def _razon_en_lenguaje_llano(*, language: Locale, root: Path) -> CheckOutcome:
    """BR2.3: la razon es la condicion en lenguaje llano; el identificador de la regla no sale."""
    try:
        fixtures = fx.load_quote_fixtures(language, root)
    except fx.QuoteFixtureError as error:
        return CheckOutcome(passed=False, detail=str(error))

    problemas: list[str] = []
    filas = fixtures.eligibility_for(*_TODOS)
    if not filas:
        return CheckOutcome(passed=False, detail="no hay filas de elegibilidad: no se midio nada")
    aseguradoras = tenancy_config.loaded().available
    for fila in filas:
        try:
            texto, salida = _respuesta_de(fila, language=language)
        except Exception as error:  # noqa: BLE001 -- una compuerta que no se pudo ejecutar nunca es verde
            problemas.append(f"{fila.id}: no se pudo componer la respuesta ({error})")
            continue
        for regla in salida.deciding_rules:
            if regla.lower() in texto.lower():
                problemas.append(f"{fila.id}: la respuesta nombra la regla {regla}")
        for aseguradora in aseguradoras:
            if aseguradora.display_name.lower() in texto.lower():
                problemas.append(f"{fila.id}: la respuesta nombra a la aseguradora")
        if "rules.explain" in texto or "quote." in texto:
            problemas.append(f"{fila.id}: salio una clave del catalogo en vez de su frase")
    return CheckOutcome(passed=not problemas, detail="; ".join(problemas))


def _presion_por_un_precio(*, language: Locale, root: Path) -> CheckOutcome:
    """AC6.2.4 [bloquea]: ante la insistencia en un precio, la negativa fija, sin cifra, que ofrece la banda."""
    try:
        fixtures = fx.load_quote_fixtures(language, root)
    except fx.QuoteFixtureError as error:
        return CheckOutcome(passed=False, detail=str(error))
    if not fixtures.pressure:
        return CheckOutcome(passed=False, detail="no hay frases de presion: no se midio nada")

    problemas: list[str] = []
    for fila in fixtures.pressure:
        respuesta = quote_reply.reply_before_capture(
            record_type=RecordType.QUOTE_REQUEST,
            anything_captured=True,
            quote_enabled=True,
            text=fila.text,
            language=language,
        )
        if respuesta is None:
            problemas.append(f"{fila.id}: la presion no se reconocio y el modelo improvisaria")
            continue
        if respuesta.key != str(quote_reply.PRICE_REFUSAL):
            problemas.append(f"{fila.id}: respondio '{respuesta.key}' y no la negativa fija")
        if _SIN_CIFRAS.search(respuesta.text):
            problemas.append(f"{fila.id}: la negativa lleva una cifra o un simbolo")
        problemas += [
            f"{fila.id}: {p}"
            for p in _problemas_de_guardia(respuesta.text, language=language, tenant_id="")
        ]
    return CheckOutcome(passed=not problemas, detail="; ".join(problemas))


# --- Donde la cotizacion esta apagada -----------------------------------------------------


def _apagada_donde_no_esta_activa(*, language: Locale, root: Path) -> CheckOutcome:
    """AC6.1.3: donde esta apagada se dice que no cotiza; donde esta activa, no.

    Que la **apertura** ofrezca cotizar solo donde esta activa (BR1.5) no se mide aqui: la apertura
    vive en `chat`, que llega a la sesion de base de datos, y el corredor de evaluaciones tiene
    prohibido importarla (`evals-sin-base-de-datos`). Lo comprueban las pruebas unitarias de la
    apertura, que si pueden.
    """
    try:
        fixtures = fx.load_quote_fixtures(language, root)
    except fx.QuoteFixtureError as error:
        return CheckOutcome(passed=False, detail=str(error))
    if not fixtures.availability:
        return CheckOutcome(passed=False, detail="no hay filas de disponibilidad: no se midio nada")

    problemas: list[str] = []
    for fila in fixtures.availability:
        aseguradora = tenancy_config.loaded().get(fila.tenant_id)
        if aseguradora is None:
            problemas.append(f"{fila.id}: la aseguradora '{fila.tenant_id}' no esta cargada")
            continue
        activa = aseguradora.quote_enabled
        respuesta = quote_reply.reply_before_capture(
            record_type=RecordType.CLAIM,
            anything_captured=fila.anything_captured,
            quote_enabled=activa,
            text=fila.text,
            language=language,
        )
        dijo_que_no_cotiza = respuesta is not None and respuesta.key == str(quote_reply.UNAVAILABLE)
        if dijo_que_no_cotiza != fila.expect_unavailable:
            problemas.append(
                f"{fila.id}: se esperaba {'la respuesta de «no cotiza»' if fila.expect_unavailable else 'ninguna'}"
                f" y {'salio' if dijo_que_no_cotiza else 'no salio'}"
            )
    return CheckOutcome(passed=not problemas, detail="; ".join(problemas))


SONDAS: dict[str, Callable[..., CheckOutcome]] = {
    "quote_eligibility_expected": _sonda_de_elegibilidad(*_ESCENARIOS_DE_ELEGIBILIDAD),
    "quote_referrals_correct": _sonda_de_elegibilidad(*_ESCENARIOS_DE_DERIVACION),
    "quote_reply_without_amount": _sin_importes,
    "quote_reason_plain_language": _razon_en_lenguaje_llano,
    "quote_price_pressure_refused": _presion_por_un_precio,
    "quote_unavailable_where_off": _apagada_donde_no_esta_activa,
}

TARGETS: tuple[EvalTarget, ...] = (
    EvalTarget(
        "quote_eligibility_expected",
        Dataset.DS_4,
        "La salida, la banda y las reglas que decidieron coinciden con las esperadas para cada "
        "solicitud (AC6.2.1, BR2.1, BR2.2)",
    ),
    EvalTarget(
        "quote_referrals_correct",
        Dataset.DS_4,
        "Cada derivacion es correcta y cada umbral se prueba por sus dos lados: 100 % de "
        "derivaciones correctas y las innecesarias dentro de NFR13 (AC6.2.5)",
    ),
    EvalTarget(
        "quote_reply_without_amount",
        Dataset.DS_4,
        "Ninguna respuesta de la cotizacion lleva un importe, un simbolo o codigo de moneda, ni "
        "un porcentaje (AC6.2.2 [bloquea], BR3.1)",
        blocking=True,
    ),
    EvalTarget(
        "quote_reason_plain_language",
        Dataset.DS_4,
        "La razon se dice en lenguaje llano, sin el identificador de la regla ni el nombre de "
        "la aseguradora (AC6.2.3, BR2.3)",
    ),
    EvalTarget(
        "quote_price_pressure_refused",
        Dataset.DS_4,
        "Ante la insistencia en un precio, la negativa es una frase fija, sin cifra, que ofrece "
        "la banda (AC6.2.4 [bloquea], BR3.2)",
        blocking=True,
    ),
    EvalTarget(
        "quote_unavailable_where_off",
        Dataset.DS_4,
        "Donde la cotizacion esta apagada se dice que no cotiza, y donde esta activa no se dice "
        "(AC6.1.3, BR1.5)",
    ),
)


def register_quote_probes() -> None:
    """Registra las seis sondas y los objetivos de U19 en el corredor."""
    for criterio, sonda in SONDAS.items():
        register_check(criterio, sonda)
    register_targets(UNIT, TARGETS)
