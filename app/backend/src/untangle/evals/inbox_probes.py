"""Las sondas de DS-2 que miden la bandeja (U14, tanda 4).

Tres comprobaciones, y las tres se resuelven **sin base de datos y sin modelo**:
funciones puras sobre escenarios estructurados, la configuracion versionada de cada
aseguradora y el catalogo de textos. Por eso sus casos entran al subconjunto de
arranque, mientras que lo que esta unidad prueba con base --el aislamiento, la
decision y el enlace-- vive en sus pruebas de integracion.

**Por que la explicacion se mide aqui y no solo en la pantalla.** Que la
explicacion responda sus cinco preguntas es una regla de negocio (BR2.4), no una
decision de maquetacion: la pantalla puede cambiar de forma diez veces y la regla
sigue siendo la misma. Medirla solo en la pantalla la ataria a una implementacion
que va a cambiar.

**Por que las acciones tambien.** BR4.5 dice que la diferencia entre una agencia y
una emisora sale de la configuracion y no del codigo, y eso se comprueba de dos
maneras que no se sustituyen: esta sonda corre la funcion real contra las tres
aseguradoras cargadas, y el ultimo chequeo lee el texto del modulo que decide para
ver que no nombra a ninguna.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from untangle.base import Locale
from untangle.copy_catalog import api as catalogo
from untangle.copy_catalog.api import CopyKey
from untangle.evals import inbox_fixtures as fx
from untangle.evals.models import Dataset
from untangle.evals.runner.api import CheckOutcome, EvalTarget, register_check, register_targets
from untangle.inbox import actions, explanation

# La configuracion de las aseguradoras por su cargador y **no** por
# `tenancy.api`: esa via llega al punto unico de sesion, y el contrato
# `evals-sin-base-de-datos` lo prohibe tambien por cadena. Es lo mismo que ya hace
# la sonda contra el despliegue vivo, y lo que mantiene el camino del clon al
# reporte sin base de datos.
from untangle.tenancy import config as tenant_config

#: La unidad a la que se le miden estas comprobaciones (C-22).
UNIT = "u14-inbox"


def _decisor(fila: fx.InboxFixtureRow) -> explanation.Decider | None:
    """El decisor de una fila, o nada. La hora no importa: importa que la haya."""
    if fila.decided_by_kind is None:
        return None
    return explanation.Decider(
        actor_kind=fila.decided_by_kind,
        actor_id=None if fila.decided_by_kind == "insured" else "quien-decidio",
        at=datetime(2026, 9, 28, 12, 0, tzinfo=UTC),
    )


def _problemas_de_explicacion(fixtures: fx.InboxFixtures) -> list[str]:
    """Cada fila del escenario `explanation`, contra la pieza real (BR2.4, BR5.5)."""
    filas = fixtures.rows_for("explanation")
    if not filas:
        return ["el escenario 'explanation' no tiene filas: no se midio nada"]

    problemas: list[str] = []
    for fila in filas:
        esperado = fila.expected or {}
        try:
            resumen = explanation.summarize(
                explanation.Evidence(
                    questions=fila.questions or 0,
                    cited_clauses=fila.cited_clauses or 0,
                    fired_rules=fila.fired_rules or 0,
                    rule_category=fila.rule_category,
                    decider=_decisor(fila),
                ),
                closed=fila.state is fila.state.CLOSED,
            )
        except Exception as error:  # noqa: BLE001 -- una compuerta que no corrio nunca es verde
            problemas.append(f"{fila.id}: la explicacion no se pudo construir ({error})")
            continue

        for pregunta in explanation.Question:
            quiere = esperado.get(pregunta.value)
            if quiere is None:
                problemas.append(f"{fila.id}: la fila no declara que espera de '{pregunta.value}'")
                continue
            dio = resumen.answers[pregunta].value
            if dio != quiere:
                problemas.append(
                    f"{fila.id}: '{pregunta.value}' se esperaba '{quiere}' y dio '{dio}'"
                )

        # BR5.5: la decision tomada con el enlace se atribuye al visitante y nunca
        # a una persona de la aseguradora. Se comprueba sobre lo que la explicacion
        # entrega, que es lo que la pantalla y el historial leen.
        if fila.decided_by_kind is not None:
            quien = resumen.decider
            if quien is None or quien.actor_kind != fila.decided_by_kind:
                problemas.append(
                    f"{fila.id}: se decidio como '{fila.decided_by_kind}' y la "
                    f"explicacion dice '{quien.actor_kind if quien else 'nadie'}'"
                )
    return problemas


def _explicacion(*, language: Locale, root: Path) -> CheckOutcome:
    try:
        fixtures = fx.load_inbox_fixtures(language, root)
    except fx.InboxFixtureError as error:
        return CheckOutcome(passed=False, detail=str(error))
    problemas = _problemas_de_explicacion(fixtures)
    return CheckOutcome(passed=not problemas, detail="; ".join(problemas))


def _etiquetas_de_cobertura(*, language: Locale, root: Path) -> CheckOutcome:
    """BR2.5: las cuatro salidas de cobertura tienen frase, y las cuatro difieren.

    Lo que la regla prohibe es colapsar "sin clausula" con "no pude verificar", y dos
    claves distintas con el **mismo texto** las colapsan igual que una sola clave: el
    chequeo compara las frases, no las claves.

    **Las cuatro claves van escritas literales en la llamada**, no recorriendo una
    tabla. La primera version las recorria y el chequeo del propio catalogo (BR3.4) la
    rechazo, con razon: una clave que llega como dato no se encuentra con un grep, y
    entonces el chequeo de claves sin consumidor se queda ciego. Cuatro lineas repetidas
    a cambio de que ese chequeo siga sirviendo.
    """
    del root  # El catalogo se carga por su propia ruta, igual que en el proceso.
    catalog = catalogo.get_catalog()
    frases = {
        "verified": catalog.t(CopyKey("inbox.coverage.verified"), locale=language),
        "rejected": catalog.t(CopyKey("inbox.coverage.rejected"), locale=language),
        "no_clause_found": catalog.t(CopyKey("inbox.coverage.no_clause_found"), locale=language),
        "unverifiable": catalog.t(CopyKey("inbox.coverage.unverifiable"), locale=language),
    }

    problemas: list[str] = []
    dichas: dict[str, str] = {}
    for salida, texto in sorted(frases.items()):
        # El catalogo devuelve la clave cuando la entrada falta --nunca lanza y nunca
        # devuelve vacio--, asi que la frase se compara **contra su clave**: es lo que
        # veria una persona, y aqui es un fallo con nombre.
        if texto == f"inbox.coverage.{salida}":
            problemas.append(f"la salida '{salida}' no tiene frase en '{language}'")
            continue
        dichas[salida] = texto

    for salida, texto in sorted(dichas.items()):
        gemelas = sorted(otra for otra, suyo in dichas.items() if otra != salida and suyo == texto)
        if gemelas:
            problemas.append(
                f"la salida '{salida}' dice lo mismo que {gemelas} en '{language}': "
                "dos resultados distintos con la misma etiqueta se leen como uno"
            )
    return CheckOutcome(passed=not problemas, detail="; ".join(problemas))


def _acciones(*, language: Locale, root: Path) -> CheckOutcome:
    """BR4.5 y BR4.3: las acciones salen de la configuracion y del estado."""
    try:
        fixtures = fx.load_inbox_fixtures(language, root)
    except fx.InboxFixtureError as error:
        return CheckOutcome(passed=False, detail=str(error))

    filas = fixtures.rows_for("agency-actions")
    if not filas:
        return CheckOutcome(passed=False, detail="el escenario 'agency-actions' no tiene filas")

    problemas: list[str] = []
    for fila in filas:
        try:
            config = tenant_config.require(fila.tenant_id)
        except Exception as error:  # noqa: BLE001 -- una aseguradora que no carga no es verde
            problemas.append(f"{fila.id}: no se pudo cargar '{fila.tenant_id}' ({error})")
            continue
        ofrecidas = actions.offered_for(config, state=fila.state)
        dio = tuple(sorted(a.value for a in ofrecidas))
        quiere = tuple(sorted(fila.expected_actions or ()))
        if dio != quiere:
            problemas.append(f"{fila.id}: se esperaban {list(quiere)} y ofrecio {list(dio)}")

    # La segunda mitad de BR4.5, sobre el texto del modulo: la diferencia entre
    # una agencia y una emisora sale de un archivo, y ninguna condicion escrita
    # nombra una aseguradora. Es el mismo chequeo que hace la prueba de
    # integracion; aqui corre tambien en la compuerta de evaluaciones, que es
    # donde el criterio de aceptacion lo pide.
    fuente = Path(actions.__file__).read_text(encoding="utf-8")
    problemas.extend(
        f"'{tenant_id}' escrito en el codigo que decide las acciones"
        for tenant_id in tenant_config.available_ids()
        if tenant_id in fuente
    )
    return CheckOutcome(passed=not problemas, detail="; ".join(problemas))


SONDAS: dict[str, Callable[..., CheckOutcome]] = {
    "inbox_explanation_answers_five": _explicacion,
    "inbox_coverage_outcomes_labelled": _etiquetas_de_cobertura,
    "inbox_actions_from_tenant_config": _acciones,
}

TARGETS: tuple[EvalTarget, ...] = (
    EvalTarget(
        "inbox_explanation_answers_five",
        Dataset.DS_2,
        "La explicacion responde sus cinco preguntas, con 'pendiente de decision' donde "
        "todavia no hay decision, y atribuye la del enlace al visitante (AC3.2.3, BR2.4, BR5.5)",
    ),
    EvalTarget(
        "inbox_coverage_outcomes_labelled",
        Dataset.DS_2,
        "'Sin clausula' y 'no pude verificar' llevan etiquetas distintas, y las cuatro "
        "salidas de cobertura difieren entre si (AC3.2.4, BR2.5)",
    ),
    EvalTarget(
        "inbox_actions_from_tenant_config",
        Dataset.DS_2,
        "Las acciones que ofrece un caso salen de la configuracion de su aseguradora y de "
        "su estado, y ningun identificador de aseguradora vive en ese codigo (AC3.6.2, "
        "AC3.6.3, BR4.5, BR4.3)",
    ),
)


def register_inbox_probes() -> None:
    """Registra las tres sondas y los objetivos de U14 en el corredor."""
    for criterio, sonda in SONDAS.items():
        register_check(criterio, sonda)
    register_targets(UNIT, TARGETS)
