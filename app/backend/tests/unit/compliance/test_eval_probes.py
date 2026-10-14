"""Las catorce sondas de DS-2 y DS-6 de U10 (NFR9.1, NFR12.2, NFR20.2).

Dos promesas, y la segunda es la que se olvida: las sondas **pasan** con la
guardia y las senales de verdad, y **no pasan con independencia de ellas**. Para
lo segundo se copia al directorio temporal lo que leen --las frases, los
patrones y las aseguradoras-- y se rompe una cosa cada vez.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml

from untangle import paths
from untangle.evals import compliance_fixtures, compliance_probes, loading
from untangle.evals.runner import api as runner_api


@pytest.fixture(autouse=True)
def _registro_limpio() -> Iterator[None]:
    runner_api.reset()
    yield
    runner_api.reset()


@pytest.fixture
def raiz_copiada(tmp_path: Path) -> Path:
    """Lo que las sondas leen, copiado para poder romperlo sin tocar el repositorio."""
    origen = paths.repo_root()
    for relativa in (
        "app/evals/fixtures/compliance",
        "app/config/compliance",
        "app/config/tenants",
    ):
        shutil.copytree(origen / relativa, tmp_path / relativa)
    return tmp_path


def _casos_de_u10() -> list[tuple[str, str, str]]:
    """Cada caso de U10 con su criterio, leidos de los archivos versionados."""
    casos: list[tuple[str, str, str]] = []
    for archivo in sorted(paths.cases_dir().rglob("*.yaml")):
        caso = loading.load_case(archivo)
        for criterio in caso.expected_verdicts:
            if criterio in compliance_probes.SONDAS:
                casos.append((caso.case_key, caso.language, criterio))
    return casos


def test_cada_caso_de_u10_nombra_una_sonda_registrada_y_hay_uno_por_idioma() -> None:
    casos = _casos_de_u10()

    assert {criterio for _, _, criterio in casos} == set(compliance_probes.SONDAS)
    for criterio in compliance_probes.SONDAS:
        idiomas = sorted(idioma for _, idioma, c in casos if c == criterio)
        assert idiomas == ["en", "es"], f"{criterio} no tiene un caso por idioma"


@pytest.mark.parametrize("idioma", ["es", "en"])
@pytest.mark.parametrize("criterio", sorted(compliance_probes.SONDAS))
def test_cada_sonda_pasa_con_la_guardia_y_las_senales_de_verdad(criterio: str, idioma: str) -> None:
    resultado = compliance_probes.SONDAS[criterio](
        language="es" if idioma == "es" else "en", root=paths.repo_root()
    )

    assert resultado.passed, resultado.detail


def test_una_frase_que_tenia_que_salir_y_la_guardia_detiene_pone_la_sonda_en_rojo(
    raiz_copiada: Path,
) -> None:
    """Si alguien cambiara una fila limpia para que pidiera un bloqueo, la sonda lo ve."""
    archivo = raiz_copiada / "app/evals/fixtures/compliance/es.yaml"
    datos = yaml.safe_load(archivo.read_text(encoding="utf-8"))
    fila = next(f for f in datos["guard"] if f["id"] == "rt-1-direct-injection/01")
    fila["expected_category"] = None
    archivo.write_text(yaml.safe_dump(datos, allow_unicode=True), encoding="utf-8")

    resultado = compliance_probes.SONDAS["rt1_injected_coverage_claim_blocked"](
        language="es", root=raiz_copiada
    )

    assert not resultado.passed
    assert "rt-1-direct-injection/01" in resultado.detail
    # El detalle nombra la fila y nunca el texto (el reporte es un punto de salida).
    assert fila["text"] not in resultado.detail


def test_una_emergencia_que_los_patrones_no_ven_pone_la_sonda_en_rojo(raiz_copiada: Path) -> None:
    """Sin los patrones de emergencia del ingles, los casos de heridos graves caen."""
    archivo = raiz_copiada / "app/config/compliance/en/emergency.yaml"
    datos = yaml.safe_load(archivo.read_text(encoding="utf-8"))
    datos["patterns"] = [{"id": "emergency.en.signal.001", "regex": "\\bnunca-coincide\\b"}]
    archivo.write_text(yaml.safe_dump(datos), encoding="utf-8")

    resultado = compliance_probes.SONDAS["serious_injury_emergency_first"](
        language="en", root=raiz_copiada
    )

    assert not resultado.passed
    assert "serious-injury/01" in resultado.detail


def test_un_escenario_sin_filas_no_se_da_por_medido(raiz_copiada: Path) -> None:
    archivo = raiz_copiada / "app/evals/fixtures/compliance/en.yaml"
    datos = yaml.safe_load(archivo.read_text(encoding="utf-8"))
    datos["turns"] = [f for f in datos["turns"] if f["scenario"] != "emergency-negatives"]
    archivo.write_text(yaml.safe_dump(datos, allow_unicode=True), encoding="utf-8")

    resultado = compliance_probes.SONDAS["emergency_negatives_no_alarm"](
        language="en", root=raiz_copiada
    )

    assert not resultado.passed
    assert "no se midio nada" in resultado.detail


def test_un_archivo_de_patrones_roto_pone_la_sonda_en_rojo_nombrandolo(raiz_copiada: Path) -> None:
    (raiz_copiada / "app/config/compliance/es/guard.yaml").unlink()

    resultado = compliance_probes.SONDAS["rt6_fault_and_legal_advice_blocked"](
        language="es", root=raiz_copiada
    )

    assert not resultado.passed
    assert "guard" in resultado.detail


def test_las_filas_son_las_mismas_en_los_dos_idiomas() -> None:
    """P12, NFR20.2: la paridad es fila por fila, no solo caso por caso."""
    raiz = paths.repo_root()
    es = compliance_fixtures.load_fixtures("es", raiz)
    en = compliance_fixtures.load_fixtures("en", raiz)

    for seccion in ("guard", "turns", "untrusted"):
        assert [f.id for f in getattr(es, seccion)] == [f.id for f in getattr(en, seccion)]


def test_registrar_las_sondas_deja_los_catorce_criterios_y_sus_objetivos() -> None:
    compliance_probes.register_compliance_probes()

    assert set(compliance_probes.SONDAS) <= set(runner_api.registered_checks())
    objetivos = runner_api.registered_targets()[compliance_probes.UNIT]
    assert {o.criterion for o in objetivos} == set(compliance_probes.SONDAS)
