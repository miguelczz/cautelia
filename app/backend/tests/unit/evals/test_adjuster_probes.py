"""Las sondas del ajustador de IA (plan 09, fase 5, tanda 2c): que cada criterio vea su violacion,
que sin quien decida el caso quede no medido y que los casos concuerden con el corpus.

Sin modelo, sin base y sin red: quien decide es un doble que devuelve lo observado que se le diga.
Lo que mide el proceso de verdad lo mide `mise run evals:ajustador`, contra Claude."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import replace
from datetime import date
from typing import Any

import pytest

from untangle import paths
from untangle.base import Locale, ProviderErrorKind
from untangle.evals import adjuster_probes, loading
from untangle.evals.adjuster_probes import (
    CRITERIA,
    MAX_SEARCHES,
    AdjusterObservation,
    AdjusterProviderError,
    AdjusterRequest,
)
from untangle.evals.models import (
    AdjusterExpectation,
    CaseResult,
    CaseStatus,
    GoldenCase,
    NotMeasuredCause,
)
from untangle.evals.runner import api as runner_api
from untangle.evals.runner import failures, runner
from untangle.evals.runner.failures import BudgetExhaustedError, TargetUnavailableError
from untangle.settings import ADJUSTER_ANTHROPIC_API_KEY_VAR, Settings

NOMBRES = (
    "collision-approved",
    "platform-excluded",
    "policy-expired",
    "agency-mark-sent",
    "vehicle-value-not-found",
)
CHOQUE = "AP-PAP-2026-D.INS.COLLISION"


def _esperado(**cambios: object) -> AdjusterExpectation:
    base: dict[str, object] = {
        "policy_number": "POL-21",
        "narrative": "Choqué contra un poste.",
        "allowed_actions": ("approve", "reject"),
        "expected_action": "approve",
        "policy_in_force": True,
        "cites_any_of": ("D.INS.COLLISION",),
    }
    return AdjusterExpectation.model_validate(base | cambios)


def _observado(**cambios: Any) -> AdjusterObservation:
    """Una decision sana: aprueba, cita el choque, todo verificado, en espanol, sin sustituciones."""
    base = AdjusterObservation(
        status="decided",
        action="approve",
        headline="Tu reporte quedó aprobado.",
        explanation="Tu póliza estaba vigente y cubre los daños por el choque.",
        reasons_text="La póliza estaba vigente.\nLos daños por un choque están cubiertos.",
        cited_clause_ids=(CHOQUE,),
        retrieved_clause_ids=(CHOQUE, "AP-PAP-2026-D.EXCL.1"),
        verified_clause_ids=(CHOQUE,),
        searches_used=2,
        explanation_language="es",
        guard_clean=True,
        policy_in_force=True,
        vehicle_value_found=True,
        vehicle_step_text="El valor de referencia es $ 50.000.000.",
    )
    return replace(base, **cambios)


def _fallos(
    esperado: AdjusterExpectation | None = None,
    observado: AdjusterObservation | None = None,
    language: Locale = "es",
) -> dict[str, list[str]]:
    return adjuster_probes.evaluate(esperado or _esperado(), observado or _observado(), language)


# --- Cada criterio ve su violacion plantada --------------------------------------------------


def test_una_decision_sana_pasa_los_ocho_criterios() -> None:
    assert set(_fallos()) == set(CRITERIA)
    assert all(not fallos for fallos in _fallos().values())


@pytest.mark.parametrize(
    ("criterio", "observado", "esperado", "idioma", "fragmento"),
    [
        (
            "action_allowed",
            _observado(action="mark_sent"),
            _esperado(),
            "es",
            "no es de las que ofrece",
        ),
        (
            "citations_verified",
            _observado(cited_clause_ids=(CHOQUE, "AP-PAP-2026-D.EXCL.99")),
            _esperado(),
            "es",
            "no se recupero",
        ),
        (
            "citations_verified",
            _observado(verified_clause_ids=()),
            _esperado(),
            "es",
            "no da por buena",
        ),
        (
            "citations_verified",
            _observado(explanation="Aplica AP-PAP-2026-D.EXCL.1 a tu caso."),
            _esperado(),
            "es",
            "nombra 'AP-PAP-2026-D.EXCL.1'",
        ),
        ("language", _observado(explanation_language="en"), _esperado(), "es", "esta en 'en'"),
        (
            "searches_within_limit",
            _observado(searches_used=MAX_SEARCHES + 1),
            _esperado(),
            "es",
            "tope es 3",
        ),
        (
            "guard_unsubstituted",
            _observado(guard_clean=False),
            _esperado(),
            "es",
            "sustituiria",
        ),
        (
            "facts_agree",
            _observado(action="reject"),
            _esperado(),
            "es",
            "los hechos piden 'approve'",
        ),
        (
            "facts_agree",
            _observado(policy_in_force=False),
            _esperado(),
            "es",
            "no rige",
        ),
        (
            "facts_agree",
            _observado(policy_in_force=None),
            _esperado(),
            "es",
            "no se pudo leer la vigencia",
        ),
        (
            "facts_agree",
            _observado(action="approve", policy_in_force=False),
            _esperado(policy_in_force=False, expected_action="reject"),
            "es",
            "aprobo con la poliza fuera de vigencia",
        ),
        (
            "cites_expected_clause",
            _observado(
                cited_clause_ids=("AP-PAP-2026-D.EXCL.1",),
                verified_clause_ids=("AP-PAP-2026-D.EXCL.1",),
            ),
            _esperado(),
            "es",
            "no cito ninguna de",
        ),
        (
            "vehicle_value_reported",
            _observado(vehicle_value_found=True),
            _esperado(vehicle_value="not_found"),
            "es",
            "trajo un valor con fuente web",
        ),
        (
            "vehicle_value_reported",
            _observado(vehicle_value_found=False, vehicle_step_text=""),
            _esperado(vehicle_value="not_found"),
            "es",
            "no dice nada",
        ),
        (
            "vehicle_value_reported",
            _observado(vehicle_value_found=False, action="reject"),
            _esperado(vehicle_value="not_found"),
            "es",
            "sin el valor no decidio",
        ),
    ],
)
def test_cada_criterio_detecta_su_violacion(
    criterio: str,
    observado: AdjusterObservation,
    esperado: AdjusterExpectation,
    idioma: Locale,
    fragmento: str,
) -> None:
    fallos = _fallos(esperado, observado, idioma)

    assert any(fragmento in f for f in fallos[criterio]), fallos[criterio]
    # Y solo el suyo: un criterio en rojo por la violacion de otro no dice nada.
    if criterio != "facts_agree":
        assert fallos["action_allowed"] == [] or criterio == "action_allowed"


def test_el_idioma_que_no_se_puede_medir_no_cuenta_como_fallo() -> None:
    assert _fallos(observado=_observado(explanation_language=None))["language"] == []


def test_el_valor_que_no_se_encuentra_se_dice_y_se_decide_igual() -> None:
    esperado = _esperado(vehicle_value="not_found")
    observado = _observado(vehicle_value_found=False)

    assert _fallos(esperado, observado)["vehicle_value_reported"] == []


def test_la_cita_se_reconoce_por_sufijo_y_no_por_coincidencia_parcial() -> None:
    assert _fallos(observado=_observado(cited_clause_ids=("X-D.INS.COLLISION.ALT",)))[
        "cites_expected_clause"
    ]
    assert _fallos()["cites_expected_clause"] == []


@pytest.mark.parametrize("estado", ["failed", "capped"])
def test_si_no_llego_a_decidir_todos_los_criterios_lo_dicen(estado: str) -> None:
    observado = AdjusterObservation(status=estado, error_kind="guard_blocked")

    fallos = _fallos(observado=observado)

    assert set(fallos) == set(CRITERIA)
    assert all("no llego a decidir" in f[0] and "guard_blocked" in f[0] for f in fallos.values())


def test_la_expectativa_no_acepta_una_accion_que_el_caso_no_permite() -> None:
    with pytest.raises(ValueError, match="no esta entre las permitidas"):
        _esperado(allowed_actions=("mark_sent",), expected_action="approve")


# --- Las sondas registradas ------------------------------------------------------------------


@pytest.fixture
def registro() -> Iterator[None]:
    runner_api.reset()
    adjuster_probes.register_adjuster_probes(paths.repo_root())
    yield None
    adjuster_probes.install(None)
    runner_api.reset()


class _Decisor:
    def __init__(self, observado: AdjusterObservation) -> None:
        self.observado = observado
        self.pedidos: list[AdjusterRequest] = []

    async def __call__(self, request: AdjusterRequest) -> AdjusterObservation:
        self.pedidos.append(request)
        return self.observado


@pytest.mark.usefixtures("registro")
async def test_sin_quien_decida_el_caso_queda_no_medido() -> None:
    adjuster_probes.install(None)
    nombre = "collision-approved"
    chequeo = runner_api.async_check_for(adjuster_probes.criterion_of("action_allowed", nombre))
    assert chequeo is not None

    with pytest.raises(TargetUnavailableError, match="evals:ajustador"):
        await chequeo(language="es", root=paths.repo_root())


@pytest.mark.usefixtures("registro")
async def test_los_ocho_criterios_de_un_caso_miran_la_misma_decision() -> None:
    decisor = _Decisor(_observado(action="reject", policy_in_force=True))
    adjuster_probes.install(decisor)
    nombre = "adjuster-collision-approved"

    resultados = {}
    for criterio in CRITERIA:
        chequeo = runner_api.async_check_for(adjuster_probes.criterion_of(criterio, nombre))
        assert chequeo is not None
        resultados[criterio] = await chequeo(language="es", root=paths.repo_root())

    assert len(decisor.pedidos) == 1
    pedido = decisor.pedidos[0]
    assert (pedido.tenant_id, pedido.policy_number, pedido.language) == (
        "sunmeadow",
        "POL-21",
        "es",
    )
    assert pedido.evaluated_on == date(2026, 11, 15)
    assert not resultados["facts_agree"].passed
    assert resultados["searches_within_limit"].passed


@pytest.mark.usefixtures("registro")
async def test_un_proveedor_que_no_dejo_decidir_no_es_un_rojo() -> None:
    adjuster_probes.install(
        _Decisor(AdjusterObservation(status="failed", error_kind="provider_timeout"))
    )
    chequeo = runner_api.async_check_for(
        adjuster_probes.criterion_of("action_allowed", "adjuster-agency-mark-sent")
    )
    assert chequeo is not None

    with pytest.raises(AdjusterProviderError) as error:
        await chequeo(language="en", root=paths.repo_root())

    assert error.value.kind is ProviderErrorKind.TIMEOUT
    # El corredor lo clasifica como lo que es: un caso no medido.
    veredicto = failures.classify(error.value)
    assert veredicto is not None
    assert veredicto.cause is not None


@pytest.mark.usefixtures("registro")
async def test_un_saldo_agotado_tampoco_es_un_rojo() -> None:
    adjuster_probes.install(_Decisor(AdjusterObservation(status="capped")))
    chequeo = runner_api.async_check_for(
        adjuster_probes.criterion_of("action_allowed", "adjuster-agency-mark-sent")
    )
    assert chequeo is not None

    with pytest.raises(BudgetExhaustedError):
        await chequeo(language="es", root=paths.repo_root())


@pytest.mark.usefixtures("registro")
def test_cada_criterio_de_cada_caso_tiene_su_objetivo_en_el_dataset_2() -> None:
    objetivos = runner_api.registered_targets()[adjuster_probes.UNIT]

    assert len(objetivos) == len(NOMBRES) * len(CRITERIA)
    assert all(o.dataset.value == "DS-2" and not o.blocking for o in objetivos)


# --- Los casos ----------------------------------------------------------------------------


def _casos() -> dict[str, GoldenCase]:
    return {c.case_key: c for c in loading.load_cases() if "/adjuster-" in c.case_key}


def test_hay_cinco_casos_en_los_dos_idiomas_y_ninguno_corre_en_cada_entrega() -> None:
    casos = _casos()

    assert sorted(casos) == sorted(f"DS-2/{i}/adjuster-{n}" for n in NOMBRES for i in ("es", "en"))
    for caso in casos.values():
        assert caso.adjuster is not None
        assert caso.requires_provider_key is True
        assert caso.subset_only is True
        assert caso.channel is None


def test_cada_caso_pide_los_ocho_criterios_y_la_pareja_pide_lo_mismo() -> None:
    casos = _casos()
    for nombre in NOMBRES:
        pedidos = {
            idioma: set(casos[f"DS-2/{idioma}/adjuster-{nombre}"].expected_verdicts)
            for idioma in ("es", "en")
        }
        esperados = {adjuster_probes.criterion_of(c, f"adjuster-{nombre}") for c in CRITERIA}
        assert pedidos["es"] == pedidos["en"] == esperados
        es = casos[f"DS-2/es/adjuster-{nombre}"].adjuster
        en = casos[f"DS-2/en/adjuster-{nombre}"].adjuster
        assert es is not None
        assert en is not None
        assert es.model_copy(update={"narrative": ""}) == en.model_copy(update={"narrative": ""})
        assert es.narrative != en.narrative


def test_el_subconjunto_lista_exactamente_los_casos_del_ajustador() -> None:
    subconjunto = loading.load_subset("ajustador", paths.subsets_dir())

    assert subconjunto.requires_provider_key is True
    assert sorted(subconjunto.case_keys) == sorted(_casos())
    assert len(loading.resolve_subset_cases(subconjunto, loading.load_cases())) == 10


def test_la_corrida_sin_subconjunto_no_toma_los_casos_del_ajustador() -> None:
    manifiesto = loading.load_manifest()
    corren = {d.dataset for d in manifiesto.datasets if d.built and d.runs_per_delivery}
    seleccion = [c for c in loading.load_cases() if c.dataset in corren and not c.subset_only]

    assert not [c for c in seleccion if c.adjuster is not None]
    assert loading.check_manifest_counts(manifiesto, loading.load_cases()) == ()
    assert loading.check_language_parity(loading.load_cases()) == ()


def test_el_corredor_pide_la_clave_del_ajustador_y_se_detiene_sin_ella() -> None:
    subconjunto = loading.load_subset("ajustador", paths.subsets_dir())
    casos = loading.resolve_subset_cases(subconjunto, loading.load_cases())
    sin_clave = Settings(anthropic_api_key_adjuster=None)

    with pytest.raises(runner.EnvironmentNotReadyError, match=ADJUSTER_ANTHROPIC_API_KEY_VAR):
        runner.validate_environment(casos, sin_clave)

    con_clave = Settings(anthropic_api_key_adjuster="clave-de-prueba")
    assert runner.validate_environment(casos, con_clave) == frozenset()


# --- Los casos contra el corpus versionado ------------------------------------------------


def _poliza(tenant: str, numero: str) -> dict[str, object]:
    archivo = paths.app_dir() / "data" / "tenants" / tenant / "issued_policies" / f"{numero}.json"
    datos: dict[str, object] = json.loads(archivo.read_text(encoding="utf-8"))
    return datos


def _clausulas(tenant: str) -> set[str]:
    carpeta = paths.app_dir() / "data" / "tenants" / tenant / "clauses"
    ids: set[str] = set()
    for archivo in carpeta.glob("*.json"):
        datos = json.loads(archivo.read_text(encoding="utf-8"))
        items = datos if isinstance(datos, list) else datos.get("clauses", [])
        ids.update(c["clause_id"] for c in items)
    return ids


@pytest.mark.parametrize("caso", [c for _, c in sorted(_casos().items())])
def test_los_hechos_del_caso_son_los_de_la_poliza_del_corpus(caso: GoldenCase) -> None:
    esperado = caso.adjuster
    assert esperado is not None
    assert caso.tenant is not None
    poliza = _poliza(caso.tenant, esperado.policy_number)

    inicio = date.fromisoformat(str(poliza["period_start"]))
    fin = date.fromisoformat(str(poliza["period_end"]))
    assert (inicio <= esperado.evaluated_on <= fin) is esperado.policy_in_force
    sufijos = esperado.cites_any_of
    if sufijos:
        propias = _clausulas(caso.tenant)
        assert any(c.endswith(f"-{s}") for c in propias for s in sufijos)


def test_el_caso_de_la_agencia_solo_permite_enviar_y_los_demas_aprobar_o_rechazar() -> None:
    for caso in _casos().values():
        esperado = caso.adjuster
        assert esperado is not None
        if caso.tenant == "knotwell":
            assert esperado.allowed_actions == ("mark_sent",)
        else:
            assert esperado.allowed_actions == ("approve", "reject")


# --- El resumen por criterio y por idioma ------------------------------------------------


def _resultado(clave: str, estado: CaseStatus, **veredictos: str) -> CaseResult:
    causa = NotMeasuredCause.PROVIDER_KEY_MISSING if estado is CaseStatus.NOT_MEASURED else None
    return CaseResult(
        result_id=f"r:{clave}",
        run_id="r",
        case_key=clave,
        status=estado,
        not_measured_cause=causa,
        criteria_results=veredictos,
    )


def test_el_resumen_separa_los_idiomas_y_cuenta_aparte_lo_no_medido() -> None:
    resumen = adjuster_probes.summarize_by_criterion(
        [
            _resultado(
                "DS-2/es/adjuster-collision-approved",
                CaseStatus.FAILED,
                adjuster_action_allowed_collision_approved="pass",
                adjuster_language_collision_approved="fail",
            ),
            _resultado(
                "DS-2/en/adjuster-collision-approved",
                CaseStatus.PASSED,
                adjuster_action_allowed_collision_approved="pass",
                adjuster_language_collision_approved="pass",
            ),
            _resultado("DS-2/en/adjuster-policy-expired", CaseStatus.NOT_MEASURED),
            _resultado("DS-2/es/rigid-deductible-from-record", CaseStatus.PASSED, otro="pass"),
        ]
    )

    filas = {linea.split()[0]: linea.split()[1:] for linea in resumen.splitlines()[1:]}
    assert filas["action_allowed"] == ["1/0/0", "1/0/1"]
    assert filas["language"] == ["0/1/0", "1/0/1"]
    assert "rigid" not in resumen
