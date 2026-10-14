"""La elegibilidad de una cotizacion (U19): reglas versionadas, salida y banda.

Lo que estas pruebas protegen no es que el motor sume: es que **un conjunto mal escrito no
arranque** y que la salida y la banda sean un par que el tipo no deja desparejar. Los
conjuntos rotos se escriben aqui para cada caso; el de Sunmeadow es el real, porque lo que se
prueba de el es que dice lo que Miguel contesto en Q3 y Q1 (2026-09-30).
"""

from __future__ import annotations

import itertools
import statistics
import time
from collections.abc import Mapping

import pytest
from pydantic import ValidationError

from untangle.case_record import schema_loading
from untangle.case_record.models import RecordType
from untangle.rules import eligibility
from untangle.rules import loading as triage_loading
from untangle.rules.conditions import ConditionError
from untangle.rules.eligibility import (
    BANDS_OF,
    EligibilityOutcome,
    EligibilityOutcomeKind,
    EligibilityRuleSet,
    MissingEligibilityInputsError,
    RiskBand,
    evaluate_eligibility,
    validate_eligibility,
)
from untangle.rules.fields import ELIGIBILITY_FIELDS, KNOWN_FIELDS, TRIAGE_FIELDS, RuleValue
from untangle.rules.models import RuleNotConfiguredError, RuleValidationError
from untangle.tenancy import config as tenancy_config
from untangle.tenancy.models import RuleDefinition, RuleSet

SUNMEADOW = "sunmeadow"

#: Una solicitud sin nada que la saque de lo habitual: es elegible con riesgo habitual.
LIMPIA: dict[str, RuleValue] = {
    "use_type": "personal",
    "salvage_title": False,
    "at_fault_losses_3y": 0,
    "license_years": 10,
    "vehicle_age_years": 5,
}


def _conjunto() -> EligibilityRuleSet:
    return eligibility.require(SUNMEADOW)


def _evaluar(**cambios: RuleValue) -> EligibilityOutcome:
    return evaluate_eligibility(_conjunto(), {**LIMPIA, **cambios})


# --- Lo que Miguel contesto en Q3 y Q1 ------------------------------------------


@pytest.mark.parametrize(
    ("cambios", "salida", "banda", "regla"),
    [
        ({"use_type": "commercial"}, "not_eligible", "outside_appetite", "SUN-Q-01"),
        ({"salvage_title": True}, "not_eligible", "outside_appetite", "SUN-Q-02"),
        ({"at_fault_losses_3y": 2}, "referred", "pending_review", "SUN-Q-03"),
        ({"license_years": 0}, "referred", "pending_review", "SUN-Q-04"),
        ({"vehicle_age_years": 26}, "referred", "pending_review", "SUN-Q-05"),
        ({}, "eligible", "standard_risk", "SUN-Q-06"),
    ],
)
def test_las_cinco_condiciones_y_lo_demas_son_lo_que_contesto_miguel(
    cambios: dict[str, RuleValue], salida: str, banda: str, regla: str
) -> None:
    resultado = _evaluar(**cambios)

    assert resultado.outcome.value == salida
    assert resultado.band.value == banda
    assert resultado.deciding_rules == (regla,)


@pytest.mark.parametrize(
    ("cambios", "salida"),
    [
        # Cada umbral, en sus dos lados: "mas de 25" es 26, "menos de uno" es cero,
        # "dos o mas" es dos. Un umbral mal puesto por uno es el error que no rompe nada.
        ({"vehicle_age_years": 25}, "eligible"),
        ({"vehicle_age_years": 26}, "referred"),
        ({"license_years": 1}, "eligible"),
        ({"license_years": 0}, "referred"),
        ({"at_fault_losses_3y": 1}, "eligible"),
        ({"at_fault_losses_3y": 2}, "referred"),
        ({"use_type": "commuting"}, "eligible"),
        ({"use_type": "personal"}, "eligible"),
    ],
)
def test_cada_umbral_en_sus_dos_lados(cambios: dict[str, RuleValue], salida: str) -> None:
    assert _evaluar(**cambios).outcome.value == salida


@pytest.mark.parametrize(
    ("cambios", "banda"),
    [
        ({}, "standard_risk"),
        ({"license_years": 3}, "standard_risk"),
        ({"license_years": 2}, "elevated_risk"),
        ({"at_fault_losses_3y": 1}, "elevated_risk"),
        ({"at_fault_losses_3y": 1, "license_years": 2}, "elevated_risk"),
    ],
)
def test_la_banda_de_un_elegible_es_habitual_solo_sin_culpa_y_con_tres_anios(
    cambios: dict[str, RuleValue], banda: str
) -> None:
    """Q1: `standard_risk` exige las dos cosas; con alguna que falte es `elevated_risk`."""
    resultado = _evaluar(**cambios)

    assert resultado.outcome is EligibilityOutcomeKind.ELIGIBLE
    assert resultado.band.value == banda


def test_gana_la_salida_mas_prudente_y_nombra_todas_las_reglas_que_la_deciden() -> None:
    """No elegible le gana a derivar; y si dos reglas de la misma salida disparan, van las dos."""
    solo_uso = _evaluar(use_type="commercial", at_fault_losses_3y=3)
    assert solo_uso.outcome is EligibilityOutcomeKind.NOT_ELIGIBLE
    assert solo_uso.deciding_rules == ("SUN-Q-01",)

    las_dos = _evaluar(use_type="commercial", salvage_title=True)
    assert las_dos.deciding_rules == ("SUN-Q-01", "SUN-Q-02")
    # La razon que se le dice a quien pregunta es la de la primera, en el orden del archivo.
    assert las_dos.explanation_key == "rules.explain.quote_commercial_use"


def test_una_derivacion_con_dos_motivos_los_nombra_en_el_orden_del_archivo() -> None:
    resultado = _evaluar(license_years=0, vehicle_age_years=30)

    assert resultado.outcome is EligibilityOutcomeKind.REFERRED
    assert resultado.deciding_rules == ("SUN-Q-04", "SUN-Q-05")


def test_la_evaluacion_es_determinista() -> None:
    assert _evaluar(use_type="commercial") == _evaluar(use_type="commercial")


# --- El tipo impide una derivacion con banda afirmada (BR2.2) ---------------------


@pytest.mark.parametrize(
    ("salida", "banda"), list(itertools.product(EligibilityOutcomeKind, RiskBand))
)
def test_solo_cuatro_parejas_de_salida_y_banda_se_pueden_construir(
    salida: EligibilityOutcomeKind, banda: RiskBand
) -> None:
    """Las doce combinaciones: se construyen exactamente las que `BANDS_OF` declara."""
    datos = {
        "outcome": salida,
        "band": banda,
        "deciding_rules": ("R-1",),
        "explanation_key": "rules.explain.quote_standard_risk",
        "ruleset_version": "v1",
    }
    if banda in BANDS_OF[salida]:
        assert EligibilityOutcome.model_validate(datos).band is banda
    else:
        with pytest.raises(ValidationError, match=r"BR2\.2"):
            EligibilityOutcome.model_validate(datos)


def test_una_derivacion_con_banda_afirmada_no_se_construye() -> None:
    """El caso central de BR2.2: derivar y decir `elevated_risk` afirma lo que nadie decidio."""
    with pytest.raises(ValidationError, match="pending_review"):
        EligibilityOutcome(
            outcome=EligibilityOutcomeKind.REFERRED,
            band=RiskBand.ELEVATED_RISK,
            deciding_rules=("SUN-Q-03",),
            explanation_key="rules.explain.quote_at_fault_losses",
            ruleset_version="v1",
        )


def test_pending_review_es_la_unica_banda_de_una_derivacion() -> None:
    assert BANDS_OF[EligibilityOutcomeKind.REFERRED] == frozenset({RiskBand.PENDING_REVIEW})
    asignadas = [banda for bandas in BANDS_OF.values() for banda in bandas]
    assert sorted(asignadas) == sorted(RiskBand), "cada banda pertenece a una sola salida"


def test_una_salida_sin_regla_que_la_decida_no_se_construye() -> None:
    with pytest.raises(ValidationError):
        EligibilityOutcome(
            outcome=EligibilityOutcomeKind.ELIGIBLE,
            band=RiskBand.STANDARD_RISK,
            deciding_rules=(),
            explanation_key="rules.explain.quote_standard_risk",
            ruleset_version="v1",
        )


# --- Sin datos no se evalua (BR1.3) -----------------------------------------------


def test_sin_un_campo_que_el_conjunto_lee_no_se_evalua() -> None:
    """Un campo ausente no dispara nada, y sin esto la regla por defecto diria «elegible»."""
    sin_edad = {k: v for k, v in LIMPIA.items() if k != "vehicle_age_years"}

    with pytest.raises(MissingEligibilityInputsError, match="vehicle_age_years"):
        evaluate_eligibility(_conjunto(), sin_edad)


def test_un_campo_en_none_cuenta_como_ausente() -> None:
    con_none = {**LIMPIA, "license_years": None}

    with pytest.raises(MissingEligibilityInputsError, match="license_years"):
        evaluate_eligibility(_conjunto(), con_none)  # type: ignore[arg-type]


def test_un_conjunto_vacio_de_datos_nunca_es_elegible() -> None:
    with pytest.raises(MissingEligibilityInputsError):
        evaluate_eligibility(_conjunto(), {})


# --- De lo guardado a lo que la regla compara --------------------------------------


def test_los_valores_guardados_se_leen_como_lo_que_cada_campo_declara() -> None:
    leidos = eligibility.eligibility_inputs(
        {
            "use_type": "commuting",
            "salvage_title": "false",
            "at_fault_losses_3y": "1",
            "license_years": "12",
            "vehicle_age_years": "26",
            "driver_name": "no se lee",
        }
    )

    assert leidos == {
        "use_type": "commuting",
        "salvage_title": False,
        "at_fault_losses_3y": 1,
        "license_years": 12,
        "vehicle_age_years": 26,
    }


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("salvage_title", "quiza"),
        ("license_years", "muchos"),
        ("vehicle_age_years", ""),
        ("use_type", "a veces"),
    ],
)
def test_un_valor_guardado_ilegible_levanta_en_vez_de_omitirse(campo: str, valor: str) -> None:
    """Omitirlo lo volveria un campo ausente, y una solicitud mal capturada saldria «elegible»."""
    with pytest.raises(eligibility.EligibilityInputError, match=campo):
        eligibility.eligibility_inputs({campo: valor})


def test_cada_campo_de_elegibilidad_tiene_su_tipo() -> None:
    assert set(eligibility.FIELD_KINDS) == ELIGIBILITY_FIELDS


# --- El conjunto real de Sunmeadow --------------------------------------------------


def test_sunmeadow_carga_sus_siete_reglas_y_todas_traen_casos() -> None:
    conjunto = _conjunto()

    assert [regla.id for regla in conjunto.rules] == [f"SUN-Q-0{n}" for n in range(1, 8)]
    assert conjunto.default_rule.id == "SUN-Q-07"
    assert conjunto.ruleset_version == "v1"
    for regla in conjunto.rules:
        assert regla.definition.version >= 1
        assert len(regla.definition.tests) >= 2 or regla.condition.operator == "always"


def test_el_conjunto_lee_los_cinco_campos_y_ninguno_mas() -> None:
    """Cada campo del vocabulario lo lee alguna regla: ninguno esta declarado de adorno."""
    assert _conjunto().required_inputs == ELIGIBILITY_FIELDS


def test_las_dos_aseguradoras_sin_cotizacion_siguen_apagadas_y_sin_conjunto() -> None:
    cargadas = tenancy_config.loaded()
    activas = {t.tenant_id for t in cargadas.available if t.quote_enabled}

    assert activas == {SUNMEADOW}
    assert set(eligibility.loaded().available) == {SUNMEADOW}


def test_toda_aseguradora_con_la_cotizacion_activa_trae_un_conjunto_valido() -> None:
    """El hueco que esto cierra: `quote_enabled: true` sin reglas ofreceria algo que no existe."""
    cargado = eligibility.loaded()

    assert cargado.unavailable == ()
    for aseguradora in tenancy_config.loaded().available:
        if aseguradora.quote_enabled:
            assert cargado.get(aseguradora.tenant_id) is not None


def test_una_aseguradora_sin_cotizacion_no_tiene_conjunto_de_elegibilidad() -> None:
    with pytest.raises(RuleNotConfiguredError, match="stonecroft"):
        eligibility.require("stonecroft")


# --- Un conjunto mal escrito no arranca -----------------------------------------------

_THEN_DEFECTO: dict[str, object] = {
    "outcome": "eligible",
    "band": "elevated_risk",
    "explanation_key": "rules.explain.quote_elevated_risk",
}


def _regla(
    rule_id: str,
    when: dict[str, object],
    then: Mapping[str, object] | None = None,
    tests: tuple[dict[str, object], ...] = ({"given": {}, "expect": False},),
) -> RuleDefinition:
    return RuleDefinition(
        id=rule_id, version=1, when=when, then=dict(then or _THEN_DEFECTO), tests=tests
    )


DEFECTO = _regla("Q-DEFAULT", {"always": True}, tests=({"given": {}, "expect": True},))


def _validar(*reglas: RuleDefinition) -> EligibilityRuleSet:
    return validate_eligibility(RuleSet(ruleset_version="v1", rules=reglas), tenant_id="sunmeadow")


def test_un_conjunto_minimo_con_su_regla_por_defecto_valida() -> None:
    assert _validar(DEFECTO).default_rule.id == "Q-DEFAULT"


def test_una_regla_que_lee_un_campo_de_triage_no_carga() -> None:
    """Cada familia lee solo su vocabulario: elegibilidad no mira heridos ni montos."""
    leyendo_triage = _regla(
        "Q-01",
        {"operator": "gte", "field": "claim_amount", "value": 1},
        {"outcome": "referred", "band": "pending_review", "explanation_key": "rules.explain.x_y"},
    )

    with pytest.raises(RuleValidationError, match="claim_amount"):
        _validar(leyendo_triage, DEFECTO)


def test_una_regla_que_lee_el_anio_del_vehiculo_no_carga() -> None:
    """`vehicle_year` no es del vocabulario: lo que se compara es la antiguedad derivada (BR1.4)."""
    con_anio = _regla(
        "Q-01",
        {"operator": "lte", "field": "vehicle_year", "value": 2001},
        {"outcome": "referred", "band": "pending_review", "explanation_key": "rules.explain.x_y"},
    )

    with pytest.raises(RuleValidationError, match="vehicle_year"):
        _validar(con_anio, DEFECTO)


@pytest.mark.parametrize("anio", [1900, 2001, 2026])
def test_una_regla_que_compara_la_antiguedad_contra_un_anio_del_calendario_no_carga(
    anio: int,
) -> None:
    """BR1.4: `vehicle_age_years gte 2001` envejece sola y no falla nada; aqui falla al cargar."""
    contra_un_anio = _regla(
        "Q-01",
        {"operator": "gte", "field": "vehicle_age_years", "value": anio},
        {"outcome": "referred", "band": "pending_review", "explanation_key": "rules.explain.x_y"},
    )

    with pytest.raises(RuleValidationError, match=r"BR1\.4"):
        _validar(contra_un_anio, DEFECTO)


def test_la_comparacion_contra_un_anio_tambien_se_atrapa_dentro_de_un_combinador() -> None:
    anidada = _regla(
        "Q-01",
        {
            "operator": "all",
            "conditions": [
                {"operator": "equals", "field": "use_type", "value": "personal"},
                {"operator": "gte", "field": "vehicle_age_years", "value": 2001},
            ],
        },
        {"outcome": "referred", "band": "pending_review", "explanation_key": "rules.explain.x_y"},
    )

    with pytest.raises(RuleValidationError, match=r"BR1\.4"):
        _validar(anidada, DEFECTO)


def test_una_antiguedad_razonable_no_se_confunde_con_un_anio() -> None:
    razonable = _regla(
        "Q-01",
        {"operator": "gte", "field": "vehicle_age_years", "value": 40},
        {"outcome": "referred", "band": "pending_review", "explanation_key": "rules.explain.x_y"},
        tests=({"given": {"vehicle_age_years": 40}, "expect": True},),
    )

    assert _validar(razonable, DEFECTO).rules


@pytest.mark.parametrize(
    ("salida", "banda"),
    [
        ("referred", "elevated_risk"),
        ("referred", "standard_risk"),
        ("referred", "outside_appetite"),
        ("eligible", "pending_review"),
        ("not_eligible", "standard_risk"),
    ],
)
def test_una_regla_con_una_pareja_de_salida_y_banda_invalida_no_carga(
    salida: str, banda: str
) -> None:
    mala = _regla(
        "Q-01",
        {"operator": "equals", "field": "salvage_title", "value": True},
        {"outcome": salida, "band": banda, "explanation_key": "rules.explain.x_y"},
        tests=({"given": {"salvage_title": True}, "expect": True},),
    )

    with pytest.raises(RuleValidationError, match=r"BR2\.2"):
        _validar(mala, DEFECTO)


def test_una_salida_o_una_banda_fuera_del_conjunto_cerrado_no_carga() -> None:
    for then in (
        {"outcome": "approved", "band": "standard_risk", "explanation_key": "rules.explain.x_y"},
        {"outcome": "eligible", "band": "cheap", "explanation_key": "rules.explain.x_y"},
    ):
        mala = _regla("Q-01", {"operator": "present", "field": "use_type"}, then)
        with pytest.raises(RuleValidationError):
            _validar(mala, DEFECTO)


def test_una_regla_sin_clave_de_explicacion_valida_no_carga() -> None:
    sin_clave = _regla(
        "Q-01",
        {"operator": "present", "field": "use_type"},
        {"outcome": "referred", "band": "pending_review", "explanation_key": "Texto libre"},
    )

    with pytest.raises(RuleValidationError, match="explanation_key"):
        _validar(sin_clave, DEFECTO)


def test_un_conjunto_sin_regla_por_defecto_no_carga() -> None:
    solo_condicion = _regla(
        "Q-01",
        {"operator": "equals", "field": "salvage_title", "value": True},
        tests=({"given": {"salvage_title": True}, "expect": True},),
    )

    with pytest.raises(RuleValidationError, match="por defecto"):
        _validar(solo_condicion)


def test_un_conjunto_con_dos_reglas_por_defecto_no_carga() -> None:
    otra = _regla("Q-DEFAULT-2", {"always": True}, tests=({"given": {}, "expect": True},))

    with pytest.raises(RuleValidationError, match="por defecto"):
        _validar(DEFECTO, otra)


def test_una_regla_que_dispara_siempre_y_dice_no_elegible_no_carga() -> None:
    """Fuera de la por defecto, `always` solo puede derivar: cerrar la cotizacion es `quote_enabled`."""
    cierra_todo = _regla(
        "Q-ALL",
        {"always": True},
        {
            "outcome": "not_eligible",
            "band": "outside_appetite",
            "explanation_key": "rules.explain.x_y",
        },
        tests=({"given": {}, "expect": True},),
    )

    with pytest.raises(RuleValidationError, match="solo puede derivar"):
        _validar(cierra_todo, DEFECTO)


def test_una_regla_cuyo_propio_caso_de_prueba_falla_no_carga() -> None:
    """BR2.4: los `tests` del YAML se corren al cargar; una regla que no los pasa no arranca."""
    miente = _regla(
        "Q-01",
        {"operator": "equals", "field": "salvage_title", "value": True},
        tests=({"given": {"salvage_title": False}, "expect": True},),
    )

    with pytest.raises(RuleValidationError, match="Q-01"):
        _validar(miente, DEFECTO)


def test_un_caso_de_prueba_mal_formado_no_carga() -> None:
    mal = _regla(
        "Q-01",
        {"operator": "equals", "field": "salvage_title", "value": True},
        tests=({"given": {"salvage_title": True}, "expect": "si"},),
    )

    with pytest.raises(RuleValidationError, match="mal formado"):
        _validar(mal, DEFECTO)


def test_una_regla_sin_casos_de_prueba_ni_se_construye() -> None:
    """BR2.4, desde la forma del archivo: `RuleDefinition` rechaza una regla sin `tests` (M5)."""
    with pytest.raises(ValidationError, match="caso de prueba"):
        RuleDefinition(id="Q-01", version=1, when={"always": True}, then=dict(_THEN_DEFECTO))


def test_un_operador_fuera_del_conjunto_cerrado_no_carga() -> None:
    with pytest.raises((RuleValidationError, ConditionError)):
        _validar(_regla("Q-01", {"operator": "regex", "field": "use_type", "value": "x"}), DEFECTO)


# --- Las dos familias de campos no se mezclan -------------------------------------------


def test_el_vocabulario_son_dos_familias_disjuntas() -> None:
    assert TRIAGE_FIELDS.isdisjoint(ELIGIBILITY_FIELDS)
    assert KNOWN_FIELDS == TRIAGE_FIELDS | ELIGIBILITY_FIELDS


def test_el_triage_no_puede_leer_un_campo_de_elegibilidad() -> None:
    """El triage de siniestros no es de esta unidad: sus reglas no leen la solicitud.

    Por el cargador real del triage y no por la funcion suelta: lo que se protege es que
    `validate_ruleset` pase su propio vocabulario, no que el parametro exista.
    """
    then: dict[str, object] = {
        "category": "standard_review",
        "touches_money": False,
        "explanation_key": "rules.explain.default",
    }
    relleno = tuple(
        RuleDefinition(
            id=f"T-{n:02d}",
            version=1,
            when={"operator": "absent", "field": "claim_amount"},
            then=then,
            tests=({"given": {}, "expect": True},),
        )
        for n in range(8)
    )
    por_defecto = RuleDefinition(
        id="T-DEFAULT",
        version=1,
        when={"always": True},
        then=then,
        tests=({"given": {}, "expect": True},),
    )
    leyendo_la_solicitud = RuleDefinition(
        id="T-USO",
        version=1,
        when={"operator": "equals", "field": "use_type", "value": "commercial"},
        then={**then, "category": "referral"},
        tests=({"given": {"use_type": "commercial"}, "expect": True},),
    )
    conjunto = RuleSet(ruleset_version="v1", rules=(por_defecto, *relleno, leyendo_la_solicitud))

    with pytest.raises(ConditionError, match="use_type"):
        triage_loading.validate_ruleset(conjunto, tenant_id="stonecroft")


# --- BR1.3: ningun campo de elegibilidad existe sin el bloque que lo escribe -----------------


def test_cada_campo_de_elegibilidad_lo_escribe_un_bloque_de_captura() -> None:
    """FD-U19-3. El hueco que hoy tienen seis campos del triage: declarado, sin escritor, sin disparar.

    Si alguien anade un campo a `ELIGIBILITY_FIELDS` y no lo pone en el esquema de la
    solicitud, esta prueba falla nombrandolo, en vez de dejar una regla que nunca corre.
    """
    escritos = {d.key for d in schema_loading.fields_by_record_type()[RecordType.QUOTE_REQUEST]}

    sin_escritor = sorted(ELIGIBILITY_FIELDS - escritos)
    assert sin_escritor == [], f"campos de elegibilidad que ningun bloque escribe: {sin_escritor}"


def test_cada_campo_de_elegibilidad_pertenece_a_un_bloque_de_los_cuatro() -> None:
    por_clave = {
        d.key: d.source_block
        for d in schema_loading.fields_by_record_type()[RecordType.QUOTE_REQUEST]
    }

    bloques = {por_clave[campo] for campo in ELIGIBILITY_FIELDS}
    assert bloques <= set(schema_loading.QUOTE_FIELDS_BY_BLOCK)


# --- PERF-U19.1 ------------------------------------------------------------------------------


def test_perf_u19_1_la_evaluacion_de_una_solicitud_completa_es_p95_de_20_ms_o_menos() -> None:
    """PERF-U19.1: pura logica sobre datos ya cargados; sin base, sin proveedor.

    Lo que este numero atrapa es que alguien meta una consulta o una llamada dentro de la
    evaluacion. Se mide la mediana de muchos lotes y el p95 de las llamadas sueltas.
    """
    conjunto = _conjunto()
    muestras: list[float] = []
    for n in range(400):
        entrada = {**LIMPIA, "license_years": n % 12, "vehicle_age_years": n % 40}
        empezo = time.perf_counter()
        evaluate_eligibility(conjunto, entrada)
        muestras.append((time.perf_counter() - empezo) * 1000)

    muestras.sort()
    p95 = muestras[int(len(muestras) * 0.95) - 1]
    assert p95 <= 20.0, f"p95 = {p95:.3f} ms"
    assert statistics.median(muestras) <= 20.0
