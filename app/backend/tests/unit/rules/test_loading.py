"""La carga del significado de un conjunto de reglas (BR1.1 a BR1.4).

`tenancy.config` ya prueba la forma del archivo; aqui se prueba lo que U9 le
anade, con conjuntos pequenos escritos para cada caso (nunca `rules/triage.yaml`
de verdad: ese llega en el paso 6 de esta unidad).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from untangle.rules import loading
from untangle.rules.conditions import ConditionError
from untangle.rules.models import RuleValidationError
from untangle.tenancy import config as tenancy_config
from untangle.tenancy.models import RuleDefinition, RuleSet

_THEN_POR_DEFECTO: dict[str, object] = {
    "category": "standard_review",
    "touches_money": False,
    "explanation_key": "rules.explain.generic",
}


def _regla(
    rule_id: str,
    *,
    when: dict[str, object],
    then: dict[str, object] | None = None,
    tests: tuple[dict[str, object], ...] = ({"given": {}, "expect": False},),
) -> RuleDefinition:
    return RuleDefinition(
        id=rule_id,
        version=1,
        when=when,
        then=_THEN_POR_DEFECTO | (then or {}),
        tests=tests,
    )


#: Una regla que nunca dispara sobre un mapa vacio: sirve para completar el
#: conteo de BR1.1 sin interferir con las condiciones que cada prueba mira.
def _relleno(n: int) -> tuple[RuleDefinition, ...]:
    return tuple(
        _regla(
            f"FILLER-{indice:02d}",
            when={"operator": "absent", "field": "claim_amount"},
            tests=({"given": {}, "expect": True},),
        )
        for indice in range(n)
    )


#: La regla por defecto, valida (BR1.3): dispara siempre con revision estandar.
DEFECTO = _regla(
    "R-DEFAULT",
    when={"always": True},
    then={"explanation_key": "rules.explain.default"},
    tests=({"given": {}, "expect": True},),
)


def test_un_conjunto_con_diez_reglas_y_una_por_defecto_valida(tmp_path: Path) -> None:
    """El piso de BR1.1, exacto."""
    crudo = RuleSet(ruleset_version="v1", rules=(DEFECTO, *_relleno(9)))

    validado = loading.validate_ruleset(crudo, tenant_id="stonecroft")

    assert len(validado.rules) == 10
    assert validado.default_rule.id == "R-DEFAULT"


def test_un_conjunto_con_veinte_reglas_valida() -> None:
    """El techo de BR1.1, exacto."""
    crudo = RuleSet(ruleset_version="v1", rules=(DEFECTO, *_relleno(19)))

    validado = loading.validate_ruleset(crudo, tenant_id="stonecroft")

    assert len(validado.rules) == 20


@pytest.mark.parametrize("relleno", [8, 20])
def test_fuera_del_rango_de_diez_a_veinte_reglas_falla_con_br1_1(relleno: int) -> None:
    crudo = RuleSet(ruleset_version="v1", rules=(DEFECTO, *_relleno(relleno)))

    with pytest.raises(RuleValidationError, match=r"BR1\.1"):
        loading.validate_ruleset(crudo, tenant_id="stonecroft")


def test_sin_ninguna_regla_por_defecto_falla_con_br1_3() -> None:
    crudo = RuleSet(ruleset_version="v1", rules=_relleno(10))

    with pytest.raises(RuleValidationError, match=r"BR1\.3"):
        loading.validate_ruleset(crudo, tenant_id="sunmeadow")


def test_con_dos_reglas_por_defecto_falla_con_br1_3() -> None:
    segunda_por_defecto = _regla(
        "R-DEFAULT-2", when={"always": True}, tests=({"given": {}, "expect": True},)
    )
    crudo = RuleSet(ruleset_version="v1", rules=(DEFECTO, segunda_por_defecto, *_relleno(8)))

    with pytest.raises(RuleValidationError, match=r"BR1\.3"):
        loading.validate_ruleset(crudo, tenant_id="sunmeadow")


def test_una_regla_que_siempre_deriva_no_sustituye_a_la_por_defecto() -> None:
    """La de la agencia (BR2.6) puede usar `always`, pero no cuenta como por defecto."""
    defecto_referral = _regla(
        "R-DEFAULT",
        when={"always": True},
        then={"category": "referral"},
        tests=({"given": {}, "expect": True},),
    )
    crudo = RuleSet(ruleset_version="v1", rules=(defecto_referral, *_relleno(9)))

    with pytest.raises(RuleValidationError, match=r"BR1\.3"):
        loading.validate_ruleset(crudo, tenant_id="knotwell")


def test_la_agencia_deriva_siempre_junto_a_la_por_defecto() -> None:
    agencia = _regla(
        "R-AGENCY",
        when={"always": True},
        then={"category": "referral", "explanation_key": "rules.explain.agency"},
        tests=({"given": {}, "expect": True},),
    )
    crudo = RuleSet(ruleset_version="v1", rules=(agencia, DEFECTO, *_relleno(8)))

    validado = loading.validate_ruleset(crudo, tenant_id="knotwell")

    assert validado.default_rule.id == "R-DEFAULT"


def test_una_regla_que_siempre_cierra_directo_falla_con_br1_3() -> None:
    siempre_cierra = _regla(
        "R-ALWAYS-CLOSE",
        when={"always": True},
        then={"category": "direct_close"},
        tests=({"given": {}, "expect": True},),
    )
    crudo = RuleSet(ruleset_version="v1", rules=(siempre_cierra, DEFECTO, *_relleno(8)))

    with pytest.raises(RuleValidationError, match="R-ALWAYS-CLOSE"):
        loading.validate_ruleset(crudo, tenant_id="sunmeadow")


def test_una_condicion_con_operador_fuera_del_cerrado_falla_nombrando_la_regla() -> None:
    rota = _regla("R-ROTA", when={"operator": "matches", "field": "claim_amount", "value": "x"})
    crudo = RuleSet(ruleset_version="v1", rules=(DEFECTO, rota, *_relleno(8)))

    with pytest.raises(ConditionError, match="R-ROTA"):
        loading.validate_ruleset(crudo, tenant_id="stonecroft")


def test_una_regla_que_no_pasa_su_propio_caso_falla_con_br1_4() -> None:
    """M5: la prueba de una regla se corre contra su propia condicion al cargar."""
    miente = _regla(
        "R-MIENTE",
        when={"operator": "equals", "field": "injuries_present", "value": True},
        tests=({"given": {"injuries_present": False}, "expect": True},),
    )
    crudo = RuleSet(ruleset_version="v1", rules=(DEFECTO, miente, *_relleno(8)))

    with pytest.raises(RuleValidationError, match="R-MIENTE"):
        loading.validate_ruleset(crudo, tenant_id="stonecroft")


def test_load_rulesets_carga_las_tres_aseguradoras_reales() -> None:
    """`rules/triage.yaml` de las tres aseguradoras, real y validado (paso 6 de esta unidad)."""
    # Se resetean los dos para no heredar la configuracion que otra prueba haya
    # instalado: cada prueba corre sola y en cualquier orden.
    tenancy_config.reset()
    loading.reset()
    try:
        resultado = loading.load_rulesets()

        assert resultado.unavailable == ()
        assert set(resultado.available) == set(tenancy_config.loaded().ids)
        for ruleset in resultado.available.values():
            assert 10 <= len(ruleset.rules) <= 20
            assert ruleset.default_rule.then.category == "standard_review"
    finally:
        tenancy_config.reset()
        loading.reset()


CARPETA_TENANT = """
config_version: 1
tenant_id: {tenant_id}
display_name: {tenant_id}
kind: carrier
default_language: es
jurisdiction: corvane
quote_enabled: false
example_policy: XX-000001
case_number_prefix: {prefix}
copy_overrides: []
voice:
  primary_voice: catalina
  language_default: es
staff: []
"""

RELLENO_YAML = """  - id: FILLER-{indice:02d}
    version: 1
    when: {{operator: absent, field: claim_amount}}
    then: {{category: standard_review, explanation_key: rules.explain.generic}}
    tests:
      - given: {{}}
        expect: true
"""

DEFECTO_YAML = """  - id: R-DEFAULT
    version: 1
    when: {always: true}
    then: {category: standard_review, explanation_key: rules.explain.default}
    tests:
      - given: {}
        expect: true
"""


def _ruleset_yaml(*, filler_count: int) -> str:
    """Un archivo de reglas valido: la regla por defecto mas `filler_count` de relleno."""
    filas = "".join(RELLENO_YAML.format(indice=indice) for indice in range(filler_count))
    return f"ruleset_version: v1\nrules:\n{DEFECTO_YAML}{filas}"


def test_load_rulesets_apaga_solo_la_aseguradora_con_el_archivo_roto(tmp_path: Path) -> None:
    """BR1.1: una carpeta rota (aqui, menos de diez reglas) no tumba a las demas."""
    raiz = tmp_path / "tenants"
    contenidos = {
        "buena": _ruleset_yaml(filler_count=9),  # 10 reglas: dentro del piso de BR1.1
        "rota": _ruleset_yaml(filler_count=0),  # 1 regla: fuera del piso de BR1.1
    }
    for tenant_id, ruleset_yaml in contenidos.items():
        carpeta = raiz / tenant_id
        (carpeta / "rules").mkdir(parents=True)
        (carpeta / "tenant.yaml").write_text(
            CARPETA_TENANT.format(tenant_id=tenant_id, prefix=tenant_id[:2].upper()),
            encoding="utf-8",
        )
        (carpeta / "rules" / "triage.yaml").write_text(ruleset_yaml, encoding="utf-8")

    tenancy_config.reset()
    loading.reset()
    try:
        tenancy_config.install(tenancy_config.load(raiz))
        resultado = loading.load_rulesets(raiz)
    finally:
        tenancy_config.reset()
        loading.reset()

    assert set(resultado.available) == {"buena"}
    assert resultado.available["buena"].default_rule.id == "R-DEFAULT"
    caidos = {caida.tenant_id: caida.detail for caida in resultado.unavailable}
    assert set(caidos) == {"rota"}
    assert "BR1.1" in caidos["rota"]
