"""Las fuentes nuevas de la enmienda FD-U7-7: turnos de casos, repertorios y archivos de raiz.

Cada forma de romperlas falla nombrando el archivo y la clave, antes de componer
nada (BR2.2, BR6.2, BR7.1). Las fuentes son minimas y de relleno, escritas para
cada prueba; nunca se rompe una fuente real.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

from untangle.synthetic_data import generator
from untangle.synthetic_data.cli import CORPUS_COMPOSERS
from untangle.synthetic_data.sources import SourceLoadError, load_sources
from untangle.tenancy import config as tenancy_config

from .apoyo import RAIZ_REAL, REVISADO, entrada, escribir_fuente, repo


def _turnos(**cambios: Any) -> dict[str, Any]:
    """Una fuente de turnos valida de un caso abierto; `cambios` la rompe."""
    base: dict[str, Any] = {
        "source_id": "SA-CASE-ES-OPEN",
        "kind": "case_turns",
        "version": "2026.1",
        "text": "agent: Relleno de una pregunta de prueba.",
        "case": {"name": "open", "state": "open"},
        "reviewed_at": REVISADO,
        "reviewed_by": "conductor",
        "drafted_with": "hand",
    }
    base.update(cambios)
    return {k: v for k, v in base.items() if v is not None}


def _problemas(raiz: Path) -> str:
    with pytest.raises(SourceLoadError) as error:
        load_sources(
            raiz / "app" / "data" / "sources",
            repo_root=raiz,
            tenants=tenancy_config.load(raiz / "app" / "config" / "tenants"),
        )
    return "\n".join(error.value.problems)


def test_una_agencia_si_tiene_los_turnos_de_sus_casos(tmp_path: Path) -> None:
    raiz = repo(tmp_path)
    escribir_fuente(
        raiz,
        [_turnos(source_id="AC-CASE-EN-OPEN")],
        tenant="knotwell",
        idioma="en",
        parte="case_turns",
    )

    paquete = load_sources(
        raiz / "app" / "data" / "sources",
        repo_root=raiz,
        tenants=tenancy_config.load(raiz / "app" / "config" / "tenants"),
    )

    (turnos,) = paquete.texts
    assert (turnos.tenant_id, turnos.case is not None) == ("knotwell", True)


@pytest.mark.parametrize(
    ("cambio", "mensaje"),
    [
        ({"case": None}, "los turnos de un caso llevan su caso (case)"),
        ({"source_id": "SA-TURNOS-OPEN"}, "se llaman <prefijo>-CASE-<nombre>"),
        ({"text": "cliente: hola"}, "la linea 1 no es '<hablante>: <texto>'"),
        (
            {"case": {"name": "derivado", "state": "derived"}},
            "lleva la razon de su derivacion si y solo si paso por una",
        ),
        (
            {"case": {"name": "cerrado", "state": "closed"}},
            "un caso cerrado lleva resolucion, y solo uno cerrado la lleva",
        ),
        (
            {"case": {"name": "open", "state": "open", "used_by": ["US1.2"]}},
            "used_by",
        ),
    ],
    ids=[
        "sin-caso",
        "identificador",
        "hablante",
        "derivado-sin-razon",
        "cerrado-sin-resolucion",
        "criterio-mal-escrito",
    ],
)
def test_una_fuente_de_turnos_rota_se_nombra(
    tmp_path: Path, cambio: dict[str, Any], mensaje: str
) -> None:
    raiz = repo(tmp_path)
    escribir_fuente(raiz, [_turnos(**cambio)], parte="case_turns")

    problemas = _problemas(raiz)

    assert "stonecroft/es/case_turns.yaml" in problemas
    assert mensaje in problemas


@pytest.mark.parametrize(
    ("texto", "mensaje"),
    [
        ("Mariana\n\nCamilo", "sin lineas vacias"),
        ("Mariana\nMariana", "elementos repetidos: Mariana"),
    ],
    ids=["linea-vacia", "repetido"],
)
def test_un_repertorio_con_huecos_o_repetidos_se_nombra(
    tmp_path: Path, texto: str, mensaje: str
) -> None:
    raiz = repo(tmp_path)
    repertorio = entrada(
        source_id="SA-POOL-GIVEN-NAMES",
        kind="persona_pool",
        clause_key=None,
        part=None,
        text=texto,
        drafted_with="hand",
    )
    escribir_fuente(raiz, [repertorio], parte="pools")

    assert mensaje in _problemas(raiz)


def test_solo_una_definicion_declara_terminos_y_solo_una_clausula_remite(tmp_path: Path) -> None:
    raiz = repo(tmp_path)
    escribir_fuente(
        raiz,
        [
            entrada(defines_terms=["termino"]),
            entrada(
                source_id="SA-PAP-2025-A.INS",
                kind="distractor",
                version="2025.1",
                distractor_of="SA-PAP-2026-A.INS",
                distractor_reason="superseded_version",
                refers_to=["SA-JUR-2026-J.1"],
            ),
        ],
    )

    problemas = _problemas(raiz)

    assert "solo una definicion (DEF.*) lleva defines_terms" in problemas
    assert "solo una clausula o un endoso remiten a otra (refers_to)" in problemas


def test_un_archivo_de_raiz_sin_marca_de_revision_no_entra(tmp_path: Path) -> None:
    raiz = repo(tmp_path)
    escribir_fuente(raiz, [entrada()])
    criterios = raiz / "app" / "data" / "sources" / "seeded_criteria.yaml"
    criterios.write_text(
        yaml.safe_dump({"format_version": 1, "criteria": [{"ac_id": "AC1.1.1", "unit": "U1"}]}),
        encoding="utf-8",
    )

    problemas = _problemas(raiz)

    assert "'app/data/sources/seeded_criteria.yaml': reviewed_at: falta 'reviewed_at'" in problemas


def test_un_marcador_desconocido_detiene_la_generacion_nombrando_el_caso(
    tmp_path: Path,
) -> None:
    """Un dato personal escrito a mano en vez de marcador no llegaria a la lista (BR7.2)."""
    raiz = repo(tmp_path)
    shutil.copytree(RAIZ_REAL / "app" / "data" / "sources", raiz / "app" / "data" / "sources")
    turnos = raiz / "app" / "data" / "sources" / "stonecroft" / "es" / "case_turns.yaml"
    datos = yaml.safe_load(turnos.read_text(encoding="utf-8"))
    datos["texts"][0]["text"] = "insured: Mi telefono es {telefono_real}."
    turnos.write_text(yaml.safe_dump(datos, allow_unicode=True, sort_keys=False), encoding="utf-8")

    with pytest.raises(generator.GenerationError) as error:
        generator.render(
            generator.GenerationRequest(
                repo_root=raiz, data_dir=raiz / "app" / "data", composers=CORPUS_COMPOSERS
            )
        )

    assert any(
        "'SA-CASE-ES-OPEN': marcadores desconocidos telefono_real" in p
        for p in error.value.problems
    )
