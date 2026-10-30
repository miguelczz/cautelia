"""La configuracion por aseguradora (C-25, BR4.1 a BR4.4, FR9.3, FR9.5, FR9.6).

Lo que estas pruebas defienden es una propiedad, no un detalle: **anadir una
cuarta aseguradora es anadir una carpeta**. Si hiciera falta tocar codigo,
"multi-tenant" seria un adjetivo y no una propiedad del sistema.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from untangle import paths
from untangle.tenancy import config
from untangle.tenancy.models import (
    IntakeConfig,
    TenantConfigError,
    TenantKind,
    UnknownTenantError,
)
from untangle.workspace import tenancy_literals

CARPETA_VALIDA = """
config_version: 1
tenant_id: {tenant_id}
display_name: {display_name}
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
staff:
  - principal_id: alguien
    role: adjuster
    display_name: Alguien
"""


def _escribir(raiz: Path, tenant_id: str, contenido: str | None = None) -> Path:
    carpeta = raiz / tenant_id
    carpeta.mkdir(parents=True)
    texto = (
        contenido
        if contenido is not None
        else CARPETA_VALIDA.format(
            tenant_id=tenant_id,
            display_name=tenant_id.title(),
            # Se deriva del identificador para que dos carpetas de una misma
            # prueba no compartan prefijo: compartirlo es lo que U4 prohibe al
            # arrancar (BR4.2), y una fixture no deberia modelar lo prohibido.
            prefix=tenant_id[:2].upper().ljust(2, "X"),
        )
    )
    (carpeta / "tenant.yaml").write_text(texto, encoding="utf-8")
    return carpeta


def test_las_tres_aseguradoras_reales_cargan_con_sus_nombres_y_sus_personas() -> None:
    """FR9.5 y FR9.6: los nombres y las personas salen de la configuracion."""
    cargadas = config.load()

    assert cargadas.unavailable == ()
    assert set(cargadas.ids) == {"stonecroft", "sunmeadow", "knotwell"}

    nombres = {t.tenant_id: t.display_name for t in cargadas.available}
    assert nombres == {
        "stonecroft": "Seguros Aburrá",
        "sunmeadow": "Autos Poblado",
        "knotwell": "Agencia Castilla",
    }

    personas = {
        t.tenant_id: [(p.principal_id, p.role.value, p.display_name) for p in t.staff]
        for t in cargadas.available
    }
    assert personas["stonecroft"] == [("diana", "adjuster", "Diana")]
    # Dos personas, y con roles distintos: la que cotiza es la unica aseguradora
    # que declara un suscriptor, porque es la unica con `quote_enabled: true`
    # (U19, BR4.1).
    assert personas["sunmeadow"] == [
        ("marcus-webb", "adjuster", "Marcus Webb"),
        ("nadia-ferris", "underwriter", "Nadia Ferris"),
    ]
    assert personas["knotwell"] == [("priya-raman", "account_agent", "Priya Raman")]

    # La agencia no es una aseguradora, y esa diferencia vive en su carpeta.
    kinds = {t.tenant_id: t.kind for t in cargadas.available}
    assert kinds["knotwell"] is TenantKind.AGENCY
    assert kinds["stonecroft"] is TenantKind.CARRIER

    # Las tres en la misma jurisdiccion ficticia (FR9.5).
    assert {t.jurisdiction for t in cargadas.available} == {"corvane"}


def test_las_tres_aseguradoras_declaran_su_configuracion_de_insultos() -> None:
    """BR5.4, TECH-U11.5: el numero lo fija la configuracion, no el codigo.

    Dos y tres son los de AC1.13.3: "dado que insulto a la agente dos veces
    seguidas ... y si vuelvo a insultar". La tanda 2 traia uno y dos, que
    adelanta los dos pasos un insulto y le termina la sesion a quien todavia
    tenia un turno.
    """
    cargadas = config.load()
    for tenant in cargadas.available:
        assert tenant.intake.calm_after_insults == 2
        assert tenant.intake.close_after_insults == 3


def test_el_cierre_por_abuso_no_puede_llegar_antes_que_la_calma() -> None:
    with pytest.raises(ValueError, match="close_after_insults"):
        IntakeConfig(calm_after_insults=2, close_after_insults=2)


def test_ninguna_carpeta_de_aseguradora_contiene_una_credencial() -> None:
    """D23, BR2.6: las credenciales se emiten con un comando, no se publican."""
    sospechosas = ("password", "secret", "token", "api_key", "credential")

    for archivo in sorted(paths.tenants_dir().rglob("*.yaml")):
        texto = archivo.read_text(encoding="utf-8").lower()
        for palabra in sospechosas:
            assert palabra not in texto, f"'{archivo}' menciona '{palabra}'"


def test_una_carpeta_rota_no_tumba_a_las_otras_dos(tmp_path: Path) -> None:
    """BR4.1: un descuido de configuracion no puede ser una caida total."""
    _escribir(tmp_path, "primera")
    _escribir(tmp_path, "segunda")
    _escribir(tmp_path, "rota", contenido="config_version: 1\ntenant_id: rota\n")

    cargadas = config.load(tmp_path)

    assert set(cargadas.ids) == {"primera", "segunda"}
    assert [c.tenant_id for c in cargadas.unavailable] == ["rota"]
    # El mensaje nombra el archivo y las claves que faltan: sin eso, a las seis
    # semanas cuesta una tarde saber cual era.
    detalle = cargadas.unavailable[0].detail
    assert "tenant.yaml" in detalle
    assert "display_name" in detalle


def test_anadir_una_cuarta_carpeta_la_deja_disponible_sin_tocar_codigo(tmp_path: Path) -> None:
    """FR9.3, BR4.3: la propiedad entera de esta unidad, en una prueba."""
    _escribir(tmp_path, "primera")
    antes = config.load(tmp_path)

    _escribir(tmp_path, "cuarta")
    despues = config.load(tmp_path)

    assert set(antes.ids) == {"primera"}
    assert set(despues.ids) == {"primera", "cuarta"}


def test_una_carpeta_cuyo_identificador_no_coincide_con_su_nombre_no_carga(
    tmp_path: Path,
) -> None:
    """El identificador nombra la carpeta: dos verdades distintas no caben."""
    _escribir(
        tmp_path,
        "una",
        contenido=CARPETA_VALIDA.format(tenant_id="otra", display_name="Otra", prefix="OT"),
    )

    cargadas = config.load(tmp_path)

    assert cargadas.ids == ()
    assert "identificador nombra la carpeta" in cargadas.unavailable[0].detail


def test_pedir_una_aseguradora_inexistente_falla_nombrandola(tmp_path: Path) -> None:
    """BR1.5: no se devuelve una configuracion vacia que parezca "sin datos"."""
    _escribir(tmp_path, "primera")
    config.install(config.load(tmp_path))
    try:
        with pytest.raises(UnknownTenantError) as fallo:
            config.require("ninguna")
    finally:
        config.reset()

    assert "ninguna" in str(fallo.value)
    assert "primera" in str(fallo.value)


def test_un_archivo_de_reglas_sin_su_caso_de_prueba_no_valida(tmp_path: Path) -> None:
    """M5: cada regla trae su caso. Una regla que nadie comprueba no entra."""
    carpeta = _escribir(tmp_path, "primera")
    reglas = carpeta / "rules"
    reglas.mkdir()
    (reglas / "triage.yaml").write_text(
        'ruleset_version: "2026-09-18"\n'
        "rules:\n"
        "  - id: XX-R-001\n"
        "    version: 1\n"
        "    when: {}\n"
        "    then: {}\n",
        encoding="utf-8",
    )

    with pytest.raises(TenantConfigError) as fallo:
        config.load_tenant(carpeta)

    assert "triage.yaml" in str(fallo.value)


def test_el_chequeo_de_literales_encuentra_uno_plantado(tmp_path: Path) -> None:
    """SEC-U2.14, BR4.2: el chequeo se prueba con una violacion de verdad.

    Un chequeo que nunca se ha visto fallar es un chequeo del que nadie sabe si
    funciona.
    """
    (tmp_path / "mise.toml").write_text("# raiz de prueba\n", encoding="utf-8")
    aseguradoras = tmp_path / "app" / "config" / "tenants"
    aseguradoras.mkdir(parents=True)
    _escribir(aseguradoras, "primera")

    modulo = tmp_path / "app" / "backend" / "src" / "untangle" / "rules" / "triage.py"
    modulo.parent.mkdir(parents=True)
    modulo.write_text(
        'def categoria(tenant: str) -> str:\n    if tenant == "primera":\n        return "x"\n',
        encoding="utf-8",
    )

    hallazgos = tenancy_literals.run_all(tmp_path)

    assert [h.tenant_id for h in hallazgos] == ["primera"]
    assert hallazgos[0].path.as_posix().endswith("rules/triage.py")
    assert hallazgos[0].line == 2


def test_el_chequeo_de_literales_no_marca_el_cargador_ni_las_fixtures(tmp_path: Path) -> None:
    """Los dos sitios donde un literal es correcto siguen siendolo."""
    (tmp_path / "mise.toml").write_text("# raiz de prueba\n", encoding="utf-8")
    aseguradoras = tmp_path / "app" / "config" / "tenants"
    aseguradoras.mkdir(parents=True)
    _escribir(aseguradoras, "primera")

    fixture = tmp_path / "app" / "data" / "fixtures" / "ds8_isolation.json"
    fixture.parent.mkdir(parents=True)
    fixture.write_text('{"tenant_id": "primera"}\n', encoding="utf-8")

    assert tenancy_literals.run_all(tmp_path) == []


# --- Q2 de U23: quien emitio la poliza de ejemplo -----------------------------

#: Una carpeta de agencia, que es la que tiene que declarar su emisor.
CARPETA_DE_AGENCIA = CARPETA_VALIDA.replace("kind: carrier", "kind: agency")


def test_una_agencia_sin_emisor_de_su_poliza_de_ejemplo_no_carga(tmp_path: Path) -> None:
    """Q2: obligatorio en una agencia, y la carpeta rota se apaga sola.

    Es mas fuerte que fallar cerrado en la pantalla: asi el dato no puede faltar en
    ejecucion. La vista sigue fallando cerrada igual, porque las dos defensas cubren
    cosas distintas.
    """
    raiz = tmp_path / "tenants"
    _escribir(
        raiz,
        "agencia",
        CARPETA_DE_AGENCIA.format(tenant_id="agencia", display_name="Agencia", prefix="AG"),
    )

    cargadas = config.load(raiz)

    assert cargadas.ids == ()
    [rota] = cargadas.unavailable
    assert "example_policy_issuer" in rota.detail


def test_una_emisora_no_declara_que_su_poliza_la_emitio_alguien_mas(tmp_path: Path) -> None:
    """La otra mitad: declararlo donde no toca tambien apaga la carpeta.

    Sin esta mitad, la regla seria "lo puede declarar cualquiera" y una emisora
    mostraria en la vista que su propia poliza de ejemplo la emitio otra.
    """
    raiz = tmp_path / "tenants"
    texto = CARPETA_VALIDA.format(tenant_id="emisora", display_name="Emisora", prefix="EM")
    _escribir(raiz, "emisora", texto + "example_policy_issuer: otra\n")

    cargadas = config.load(raiz)

    assert cargadas.ids == ()
    [rota] = cargadas.unavailable
    assert "example_policy_issuer" in rota.detail


def test_una_agencia_con_su_emisor_declarado_carga(tmp_path: Path) -> None:
    """El control positivo: sin el, las dos de arriba pasarian con un campo roto."""
    raiz = tmp_path / "tenants"
    texto = CARPETA_DE_AGENCIA.format(tenant_id="agencia", display_name="Agencia", prefix="AG")
    _escribir(raiz, "agencia", texto + "example_policy_issuer: emisora\n")

    cargadas = config.load(raiz)

    assert cargadas.ids == ("agencia",)
    assert cargadas.available[0].example_policy_issuer == "emisora"
