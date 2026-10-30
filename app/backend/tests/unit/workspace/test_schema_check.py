"""El chequeo de esquemas sobre el significado de `rules/triage.yaml` (U9, BR1.1 a BR1.4).

`tenant_config.load_tenant` ya prueba la **forma** del archivo en otras
suites; esta prueba es la que este paso anade: que `schema:check` tambien
corra la validacion de **significado** de U9 (conteo, regla por defecto,
pruebas de cada regla) y que el fallo nombre la aseguradora -- por la
carpeta y por el prefijo de la regla, igual que en la configuracion real --
y la regla exacta que lo rompe.
"""

from __future__ import annotations

from pathlib import Path

from untangle import paths
from untangle.workspace import schema_check

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

RELLENO_YAML = """  - id: {tenant_prefix}-R-{indice:02d}
    version: 1
    when: {{operator: absent, field: claim_amount}}
    then: {{category: standard_review, explanation_key: rules.explain.default}}
    tests:
      - given: {{}}
        expect: true
"""

DEFECTO_YAML = """  - id: {tenant_prefix}-R-DEFAULT
    version: 1
    when: {{always: true}}
    then: {{category: standard_review, explanation_key: rules.explain.default}}
    tests:
      - given: {{}}
        expect: true
"""

#: Una regla rota a proposito: dice que dispara con `injuries_present` en
#: falso y su propia prueba pide lo contrario (BR1.4).
REGLA_QUE_MIENTE_YAML = """  - id: {tenant_prefix}-R-MIENTE
    version: 1
    when: {{operator: equals, field: injuries_present, value: false}}
    then: {{category: standard_review, explanation_key: rules.explain.default}}
    tests:
      - given: {{injuries_present: true}}
        expect: true
"""


def _escribir_aseguradora(raiz: Path, tenant_id: str, *, rota: bool) -> None:
    carpeta = raiz / tenant_id
    (carpeta / "rules").mkdir(parents=True)
    (carpeta / "tenant.yaml").write_text(
        CARPETA_TENANT.format(tenant_id=tenant_id, prefix=tenant_id[:2].upper()),
        encoding="utf-8",
    )
    prefijo = tenant_id[:3].upper()
    filas = "".join(
        RELLENO_YAML.format(tenant_prefix=prefijo, indice=indice) for indice in range(9)
    )
    regla_extra = REGLA_QUE_MIENTE_YAML.format(tenant_prefix=prefijo) if rota else ""
    ruleset = (
        f"ruleset_version: v1\nrules:\n"
        f"{DEFECTO_YAML.format(tenant_prefix=prefijo)}{filas}{regla_extra}"
    )
    (carpeta / "rules" / "triage.yaml").write_text(ruleset, encoding="utf-8")


def test_una_regla_que_no_pasa_su_prueba_falla_el_chequeo_de_esquemas_nombrando_todo(
    tmp_path: Path,
) -> None:
    raiz = tmp_path / "app" / "config" / "tenants"
    _escribir_aseguradora(raiz, "rota", rota=True)
    _escribir_aseguradora(raiz, "buena", rota=False)

    # `_revisar_significado_de_reglas` es la pieza exacta que este paso anade:
    # cada carpeta se revisa por separado, igual que hace su llamador con la
    # forma (BR1.1).
    de_rota = schema_check._revisar_significado_de_reglas(raiz / "rota")
    de_buena = schema_check._revisar_significado_de_reglas(raiz / "buena")

    assert de_buena == []
    assert any("ROT-R-MIENTE" in p and "BR1.4" in p for p in de_rota), de_rota


def test_una_aseguradora_sana_no_reporta_ningun_problema(tmp_path: Path) -> None:
    raiz = tmp_path / "app" / "config" / "tenants"
    _escribir_aseguradora(raiz, "buena", rota=False)

    assert schema_check._revisar_significado_de_reglas(raiz / "buena") == []


def test_el_arbol_real_de_aseguradoras_pasa_el_chequeo_de_significado() -> None:
    """Linea base: las tres aseguradoras reales, con sus 30 reglas, validan (paso 6)."""
    assert schema_check._revisar_configuracion_por_aseguradora(paths.repo_root()) == []


# --- U23, Q2: lo declarado contra el dato versionado --------------------------

#: Una agencia, con su emisor declarado. Es la unica que puede declararlo.
AGENCIA_TENANT = (
    CARPETA_TENANT.replace("kind: carrier", "kind: agency") + "example_policy_issuer: {emisor}\n"
)


def _escribir_poliza(raiz: Path, tenant_id: str, numero: str, emisor: str) -> None:
    """La poliza emitida, tal como el generador la deja en `app/data/`."""
    carpeta = raiz / "app" / "data" / "tenants" / tenant_id / "issued_policies"
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / f"{numero}.json").write_text(
        f'{{"policy_number": "{numero}", "tenant_id": "{tenant_id}", "issuer_tenant": "{emisor}"}}',
        encoding="utf-8",
    )


def _agencia(raiz: Path, tenant_id: str, *, declara: str) -> Path:
    carpeta = raiz / "app" / "config" / "tenants" / tenant_id
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "tenant.yaml").write_text(
        AGENCIA_TENANT.format(tenant_id=tenant_id, prefix=tenant_id[:2].upper(), emisor=declara),
        encoding="utf-8",
    )
    return carpeta


def test_un_emisor_declarado_que_la_poliza_desmiente_falla_el_chequeo(tmp_path: Path) -> None:
    """La mitad que hacia dudar de poner el emisor en la configuracion (Q2).

    Dos fuentes que pueden discrepar; con el chequeo, discrepar **falla**, que es la
    diferencia entre declarar y adivinar.
    """
    _agencia(tmp_path, "agencia", declara="quien-no-fue")
    _escribir_poliza(tmp_path, "agencia", "XX-000001", emisor="quien-si-fue")
    from untangle.tenancy import config as tenant_config

    aseguradora = tenant_config.load_tenant(tmp_path / "app" / "config" / "tenants" / "agencia")

    problemas = schema_check._revisar_emisor_de_la_poliza_de_ejemplo(tmp_path, aseguradora)

    assert len(problemas) == 1
    assert "quien-no-fue" in problemas[0]
    assert "quien-si-fue" in problemas[0]


def test_un_emisor_declarado_que_la_poliza_confirma_no_reporta_nada(tmp_path: Path) -> None:
    """El control positivo: sin el, un chequeo que siempre fallara pasaria igual."""
    _agencia(tmp_path, "agencia", declara="quien-si-fue")
    _escribir_poliza(tmp_path, "agencia", "XX-000001", emisor="quien-si-fue")
    from untangle.tenancy import config as tenant_config

    aseguradora = tenant_config.load_tenant(tmp_path / "app" / "config" / "tenants" / "agencia")

    assert schema_check._revisar_emisor_de_la_poliza_de_ejemplo(tmp_path, aseguradora) == []
