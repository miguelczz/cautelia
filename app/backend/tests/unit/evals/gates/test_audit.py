"""Pruebas del segundo detector (BR4.1, BR4.2, AC4.14.1, AC4.14.4).

Sin modelo: nada aqui llama a spaCy ni a ningun proveedor. Todo escribe en
directorio temporal, nunca en `app/evals/`.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from untangle import paths
from untangle.evals.gates import audit
from untangle.evals.gates.audit import AuditEntityType, scan_file, scan_report, scan_text
from untangle.evals.models import CaseStatus

from .builders import fila, reporte

# --- AC4.14.4: el detector detecta ---------------------------------------------


def test_un_telefono_sin_redactar_en_un_archivo_de_trazas_se_detecta(tmp_path: Path) -> None:
    archivo = tmp_path / "trace.jsonl"
    archivo.write_text('{"turn": "mi telefono es 3001234567"}\n', encoding="utf-8")

    hallazgos = scan_file(archivo)

    assert any(h.entity_type is AuditEntityType.PHONE for h in hallazgos)
    assert all(h.source == str(archivo) for h in hallazgos)


def test_un_archivo_sin_datos_personales_no_produce_hallazgos(tmp_path: Path) -> None:
    archivo = tmp_path / "trace.jsonl"
    archivo.write_text('{"turn": "hola, tengo una pregunta sobre mi poliza"}\n', encoding="utf-8")

    assert scan_file(archivo) == ()


def test_un_archivo_ausente_no_es_un_hallazgo_ni_un_error(tmp_path: Path) -> None:
    assert scan_file(tmp_path / "no-existe.jsonl") == ()


def test_scan_paths_junta_los_hallazgos_de_varios_archivos(tmp_path: Path) -> None:
    limpio = tmp_path / "limpio.log"
    limpio.write_text("todo bien por aqui", encoding="utf-8")
    sucio = tmp_path / "sucio.log"
    sucio.write_text("placa ABC123 vista en el lote", encoding="utf-8")

    hallazgos = audit.scan_paths((limpio, sucio))

    assert hallazgos
    assert all(h.source == str(sucio) for h in hallazgos)
    assert all(h.entity_type is AuditEntityType.LICENSE_PLATE for h in hallazgos)


def test_numero_de_poliza_se_detecta_en_los_dos_idiomas() -> None:
    texto = "la poliza POL-11 esta activa"
    assert any(
        h.entity_type is AuditEntityType.POLICY_NUMBER
        for h in scan_text(texto, language="es", source="x")
    )
    assert any(
        h.entity_type is AuditEntityType.POLICY_NUMBER
        for h in scan_text(texto, language="en", source="x")
    )


def test_cedula_colombiana_se_detecta_sin_confundirse_con_un_celular() -> None:
    hallazgos_cedula = scan_text("mi cedula es 79123456", language="es", source="x")
    hallazgos_celular = scan_text("mi celular es 3001234567", language="es", source="x")

    assert any(h.entity_type is AuditEntityType.NATIONAL_ID for h in hallazgos_cedula)
    assert not any(h.entity_type is AuditEntityType.NATIONAL_ID for h in hallazgos_celular)
    assert any(h.entity_type is AuditEntityType.PHONE for h in hallazgos_celular)


# --- El reporte nunca dispara falsos positivos por sus identificadores --------


def test_scan_report_no_encuentra_nada_hoy_porque_el_reporte_no_guarda_texto_libre() -> None:
    """El reporte no tiene ningun campo de texto libre (BR4.4): esta funcion no
    serializa la cabecera para evitar que un hash hexadecimal largo -- commit_sha,
    run_id -- coincida por azar con un patron de telefono."""
    rep = reporte(
        (fila("DS-2/es/017", status=CaseStatus.FAILED),),
        commit_sha="1234567890abcdef1234567890abcdef12345678",
        run_id="run-1234567890ab",
    )
    assert scan_report(rep) == ()


# --- BR4.1: mecanismo distinto, sin reconocedores compartidos -----------------


def test_no_comparte_ninguna_expresion_regular_con_los_reconocedores_de_u3() -> None:
    """Lee los dos archivos de U3 como YAML, sin importar su modulo (BR4.1,
    BR4.6): solo para comprobar que ninguna expresion coincide con la de aqui."""
    propias = {patron.regex.pattern for patrones in audit.PATTERNS.values() for patron in patrones}

    recognizers_dir = (
        paths.backend_dir() / "src" / "untangle" / "compliance" / "redaction" / "recognizers"
    )
    ajenas: set[str] = set()
    for archivo in (recognizers_dir / "es.yaml", recognizers_dir / "en.yaml"):
        datos = yaml.safe_load(archivo.read_text(encoding="utf-8"))
        for reconocedor in datos.get("recognizers", []):
            for patron in reconocedor.get("patterns", ()):
                ajenas.add(patron["regex"])

    assert propias.isdisjoint(ajenas)
