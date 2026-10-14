"""La validacion de la carpeta de una aseguradora (US5.1, BR1.1).

Lo que se defiende: **todas** las faltas en una corrida, cada una con su archivo y
su campo. Cada prueba parte de una copia de una carpeta real y completa, y le
quita exactamente lo que quiere comprobar.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from untangle import paths
from untangle.demo_operations.api import TenantFolderReport, validate_tenant_folder

_REALES = sorted(p.name for p in (paths.config_dir() / "tenants").iterdir() if p.is_dir())


class _Arbol:
    """Una copia de una carpeta real y de su corpus, en un directorio temporal."""

    def __init__(self, raiz: Path, tenant_id: str) -> None:
        self.tenant_id = tenant_id
        self.carpeta = raiz / "tenants" / tenant_id
        self.corpus_root = raiz / "data"
        shutil.copytree(paths.config_dir() / "tenants" / tenant_id, self.carpeta)
        shutil.copytree(
            paths.app_dir() / "data" / "tenants" / tenant_id, self.corpus_root / tenant_id
        )

    @property
    def tenant_yaml(self) -> Path:
        return self.carpeta / "tenant.yaml"

    def validar(self) -> TenantFolderReport:
        return validate_tenant_folder(self.carpeta, corpus_root=self.corpus_root)

    def editar_yaml(self, viejo: str, nuevo: str = "") -> None:
        texto = self.tenant_yaml.read_text(encoding="utf-8")
        assert viejo in texto, f"la prueba espera encontrar {viejo!r} en tenant.yaml"
        self.tenant_yaml.write_text(texto.replace(viejo, nuevo, 1), encoding="utf-8")


@pytest.fixture
def arbol(tmp_path: Path) -> _Arbol:
    return _Arbol(tmp_path, _REALES[0])


def _faltas(reporte: TenantFolderReport) -> set[tuple[str, str]]:
    return {(Path(f.file).name, f.field) for f in reporte.missing}


@pytest.mark.parametrize("tenant_id", _REALES)
def test_las_carpetas_reales_estan_completas(tmp_path: Path, tenant_id: str) -> None:
    reporte = _Arbol(tmp_path, tenant_id).validar()

    assert reporte.missing == ()
    assert reporte.complete
    assert reporte.tenant_id == tenant_id


def test_una_carpeta_sin_dos_cosas_reporta_las_dos_con_archivo_y_campo(arbol: _Arbol) -> None:
    arbol.editar_yaml("display_name:", "nombre_de_mas:")
    (arbol.carpeta / "rules" / "triage.yaml").unlink()

    reporte = arbol.validar()

    assert not reporte.complete
    faltas = _faltas(reporte)
    assert ("tenant.yaml", "display_name") in faltas
    assert ("triage.yaml", "(archivo)") in faltas
    # Y cada falta nombra el archivo completo, no solo el campo.
    assert all(f.file and f.field and f.detail for f in reporte.missing)


def test_reporta_todas_las_faltas_y_no_la_primera(arbol: _Arbol) -> None:
    """BR1.1: cinco faltas distintas, cinco filas en una sola corrida."""
    arbol.editar_yaml("display_name:", "nombre_de_mas:")
    arbol.editar_yaml("staff:", "personal:")
    arbol.editar_yaml("  stt:", "  stt_de_mas:")
    (arbol.carpeta / "rules" / "triage.yaml").unlink()
    shutil.rmtree(arbol.corpus_root / arbol.tenant_id / "clauses")

    faltas = _faltas(arbol.validar())

    assert {
        ("tenant.yaml", "display_name"),
        ("tenant.yaml", "staff"),
        ("tenant.yaml", "voice.stt"),
        ("triage.yaml", "(archivo)"),
        ("clauses", "(carpeta)"),
    } <= faltas


def test_una_carpeta_vacia_no_revienta_y_nombra_lo_que_falta(tmp_path: Path) -> None:
    carpeta = tmp_path / "tenants" / "nueva"
    carpeta.mkdir(parents=True)

    reporte = validate_tenant_folder(carpeta, corpus_root=tmp_path / "data")

    faltas = _faltas(reporte)
    assert ("tenant.yaml", "(archivo)") in faltas
    assert ("triage.yaml", "(archivo)") in faltas
    assert {
        ("forms", "(carpeta)"),
        ("clauses", "(carpeta)"),
        ("issued_policies", "(carpeta)"),
    } <= faltas
    assert reporte.tenant_id == "nueva"


@pytest.mark.parametrize(
    ("bloque", "campo"),
    [("stt", "voice.stt"), ("primary", "voice.primary"), ("fallback", "voice.fallback")],
)
def test_una_voz_sin_un_bloque_no_esta_completa(arbol: _Arbol, bloque: str, campo: str) -> None:
    texto = arbol.tenant_yaml.read_text(encoding="utf-8")
    arbol.tenant_yaml.write_text(
        texto.replace(f"\n  {bloque}:", f"\n  {bloque}_de_mas:", 1), encoding="utf-8"
    )

    assert ("tenant.yaml", campo) in _faltas(arbol.validar())


def test_una_voz_sin_uno_de_los_dos_idiomas_nombra_cual(arbol: _Arbol) -> None:
    texto = arbol.tenant_yaml.read_text(encoding="utf-8")
    # Solo en el bloque de respaldo: dejar la voz principal intacta aisla la falta.
    cabeza, _, cola = texto.partition("  fallback:\n")
    arbol.tenant_yaml.write_text(
        cabeza + "  fallback:\n" + cola.replace("    en:", "    xx:", 1), encoding="utf-8"
    )

    faltas = _faltas(arbol.validar())

    assert ("tenant.yaml", "voice.fallback.en") in faltas
    assert ("tenant.yaml", "voice.primary.en") not in faltas


def test_sin_personas_de_bandeja_falta_staff(arbol: _Arbol) -> None:
    texto = arbol.tenant_yaml.read_text(encoding="utf-8")
    inicio = texto.index("staff:")
    fin = texto.index("\n\n", inicio)
    arbol.tenant_yaml.write_text(texto[:inicio] + "staff: []" + texto[fin:], encoding="utf-8")

    assert ("tenant.yaml", "staff") in _faltas(arbol.validar())


def test_una_poliza_de_ejemplo_que_no_esta_en_el_corpus_se_nombra(arbol: _Arbol) -> None:
    texto = arbol.tenant_yaml.read_text(encoding="utf-8")
    actual = next(linea for linea in texto.splitlines() if linea.startswith("example_policy:"))
    arbol.tenant_yaml.write_text(
        texto.replace(actual, "example_policy: POL-000000"), encoding="utf-8"
    )

    reporte = arbol.validar()

    falta = next(f for f in reporte.missing if f.field == "example_policy")
    assert "POL-000000" in falta.detail


def test_una_poliza_de_ejemplo_que_no_es_la_que_dice_ser_se_nombra(arbol: _Arbol) -> None:
    carpeta = arbol.corpus_root / arbol.tenant_id / "issued_policies"
    ejemplo = (
        next(
            linea
            for linea in arbol.tenant_yaml.read_text(encoding="utf-8").splitlines()
            if linea.startswith("example_policy:")
        )
        .split(":")[1]
        .strip()
    )
    destino = carpeta / f"{ejemplo}.json"
    assert destino.is_file()
    destino.write_text(
        destino.read_text(encoding="utf-8").replace(f'"{ejemplo}"', '"POL-999999"'),
        encoding="utf-8",
    )

    assert (f"{ejemplo}.json", "policy_number") in _faltas(arbol.validar())


def test_una_poliza_de_ejemplo_no_puede_salirse_de_su_carpeta(arbol: _Arbol) -> None:
    """Un archivo **existente** fuera de `issued_policies` no se lee como poliza.

    Sin el archivo plantado, la ausencia ya produciria una falta en el mismo
    campo y la prueba pasaria aunque nadie vigilara el nombre.
    """
    (arbol.corpus_root / arbol.tenant_id / "fuera.json").write_text(
        '{"policy_number": "../fuera"}', encoding="utf-8"
    )
    texto = arbol.tenant_yaml.read_text(encoding="utf-8")
    actual = next(linea for linea in texto.splitlines() if linea.startswith("example_policy:"))
    arbol.tenant_yaml.write_text(
        texto.replace(actual, "example_policy: ../fuera"), encoding="utf-8"
    )

    reporte = arbol.validar()

    falta = next(f for f in reporte.missing if f.field == "example_policy")
    assert "nombre de poliza valido" in falta.detail


def test_el_identificador_tiene_que_nombrar_la_carpeta(arbol: _Arbol) -> None:
    arbol.editar_yaml(f"tenant_id: {arbol.tenant_id}", "tenant_id: otra")

    assert ("tenant.yaml", "tenant_id") in _faltas(arbol.validar())


def test_una_clave_desconocida_se_nombra(arbol: _Arbol) -> None:
    arbol.tenant_yaml.write_text(
        arbol.tenant_yaml.read_text(encoding="utf-8") + "\nclave_inventada: 1\n", encoding="utf-8"
    )

    assert ("tenant.yaml", "clave_inventada") in _faltas(arbol.validar())


def test_un_conjunto_de_reglas_roto_se_nombra_por_archivo(arbol: _Arbol) -> None:
    (arbol.carpeta / "rules" / "triage.yaml").write_text(
        "ruleset_version: v1\nrules: []\n", encoding="utf-8"
    )

    faltas = _faltas(arbol.validar())

    assert ("triage.yaml", "rules") in faltas


def test_validar_no_escribe_nada(arbol: _Arbol) -> None:
    def foto() -> dict[str, bytes]:
        return {
            str(p): p.read_bytes()
            for raiz in (arbol.carpeta, arbol.corpus_root)
            for p in sorted(raiz.rglob("*"))
            if p.is_file()
        }

    # Una carpeta con una falta: el camino que mas tentaria a "arreglar" algo.
    (arbol.carpeta / "rules" / "triage.yaml").unlink()
    antes = foto()

    arbol.validar()

    assert foto() == antes


def test_un_yaml_ilegible_se_nombra_sin_reventar(arbol: _Arbol) -> None:
    arbol.tenant_yaml.write_text("a: [sin cerrar", encoding="utf-8")

    assert ("tenant.yaml", "(archivo)") in _faltas(arbol.validar())


def test_un_yaml_cuya_raiz_no_es_un_mapa_se_nombra(arbol: _Arbol) -> None:
    arbol.tenant_yaml.write_text("- uno\n- dos\n", encoding="utf-8")

    assert ("tenant.yaml", "(raiz)") in _faltas(arbol.validar())


def test_un_archivo_de_reglas_con_forma_invalida_nombra_su_campo(arbol: _Arbol) -> None:
    (arbol.carpeta / "rules" / "triage.yaml").write_text("rules: 3\n", encoding="utf-8")

    faltas = _faltas(arbol.validar())

    assert ("triage.yaml", "ruleset_version") in faltas
    assert ("triage.yaml", "rules") in faltas


def test_una_poliza_de_ejemplo_que_no_es_json_se_nombra(arbol: _Arbol) -> None:
    ejemplo = (
        next(
            linea
            for linea in arbol.tenant_yaml.read_text(encoding="utf-8").splitlines()
            if linea.startswith("example_policy:")
        )
        .split(":")[1]
        .strip()
    )
    destino = arbol.corpus_root / arbol.tenant_id / "issued_policies" / f"{ejemplo}.json"
    destino.write_text("{no es json", encoding="utf-8")

    assert (f"{ejemplo}.json", "(archivo)") in _faltas(arbol.validar())
