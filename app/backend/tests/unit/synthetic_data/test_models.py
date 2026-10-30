"""Los modelos de U7: cada forma de romper una regla falla nombrando el archivo y la clave.

Se prueban **a traves de quien los usa** --el cargador de fuentes y la
comprobacion de salidas--, no construyendo el modelo a mano: lo que la regla
exige es que quien abre el archivo sepa que arreglar, y eso solo se ve en el
mensaje que llega hasta el.

Reglas: BR2.2 (marca de revision), BR3.2 (identificador y version), BR3.4
(distractores ligados), BR3.6 (poliza emitida) y BR7.1 (datos ficticios).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from untangle.case_record.models import CaseState, Resolution, Speaker
from untangle.synthetic_data import manifest, models
from untangle.synthetic_data.sources import SourceLoadError, load_sources
from untangle.tenancy import config as tenancy_config

from .apoyo import VIN_FICTICIO, entrada, escribir_fuente, persona, poliza, repo, vehiculo

PARTE_A = "app/data/sources/stonecroft/es/part_a.yaml"


def _cargar(raiz: Path) -> Any:
    return load_sources(
        raiz / "app" / "data" / "sources",
        repo_root=raiz,
        tenants=tenancy_config.load(raiz / "app" / "config" / "tenants"),
    )


def _problemas(raiz: Path) -> str:
    with pytest.raises(SourceLoadError) as error:
        _cargar(raiz)
    return "\n".join(error.value.problems)


# --- Camino feliz -------------------------------------------------------------


def test_una_fuente_revisada_se_carga_con_la_aseguradora_y_el_idioma_de_su_archivo(
    tmp_path: Path,
) -> None:
    raiz = repo(tmp_path)
    escribir_fuente(
        raiz,
        [
            entrada(),
            entrada(
                source_id="SA-PAP-2025-A.INS",
                kind="distractor",
                version="2025.1",
                distractor_of="SA-PAP-2026-A.INS",
                distractor_reason="superseded_version",
            ),
        ],
    )

    paquete = _cargar(raiz)

    clausula, distractor = paquete.texts
    assert (clausula.tenant_id, clausula.language, clausula.form_id) == (
        "stonecroft",
        "es",
        "SA-PAP-2026",
    )
    assert distractor.form_id == "SA-PAP-2025"
    assert list(paquete.input_hashes()) == [PARTE_A]


# --- BR2.2: sin marca de revision no entra ------------------------------------


@pytest.mark.parametrize("marca", ["reviewed_at", "reviewed_by", "drafted_with"])
def test_un_texto_sin_marca_de_revision_se_rechaza_nombrando_archivo_y_clave(
    tmp_path: Path, marca: str
) -> None:
    raiz = repo(tmp_path)
    escribir_fuente(
        raiz,
        [
            entrada(),
            entrada(source_id="SA-PAP-2026-A.EXCL.3", clause_key="A.EXCL.3", **{marca: None}),
        ],
    )

    problemas = _problemas(raiz)

    assert f"'{PARTE_A}': texts[1].{marca} (SA-PAP-2026-A.EXCL.3): falta '{marca}'" in problemas
    assert "BR2.2" in problemas


def test_una_marca_de_revision_de_quien_no_revisa_se_rechaza(tmp_path: Path) -> None:
    raiz = repo(tmp_path)
    escribir_fuente(raiz, [entrada(reviewed_by="gemini")])

    assert f"'{PARTE_A}': texts[0].reviewed_by (SA-PAP-2026-A.INS)" in _problemas(raiz)


# --- BR3.2: identificador del formulario mas la numeracion, y version ----------


@pytest.mark.parametrize(
    ("cambios", "esperado"),
    [
        ({"source_id": "SA-PAP-2026-A.EXCL.3"}, "no termina en su numeracion 'A.INS'"),
        ({"source_id": "STO-2026-A.INS"}, "no tiene la forma de un formulario"),
        ({"version": "2026"}, "texts[0].version (SA-PAP-2026-A.INS)"),
        ({"version": "2025.1"}, "el formulario es de 2026 y la version '2025.1' de otro ano"),
        ({"source_id": "SA-PAP-2026-END-1-A.INS"}, "va en un formulario <prefijo>-PAP-<ano>"),
    ],
)
def test_un_identificador_o_una_version_mal_formados_se_rechazan(
    tmp_path: Path, cambios: dict[str, str], esperado: str
) -> None:
    raiz = repo(tmp_path)
    escribir_fuente(raiz, [entrada(**cambios)])

    problemas = _problemas(raiz)

    assert f"'{PARTE_A}'" in problemas
    assert esperado in problemas


def test_un_identificador_repetido_entre_dos_archivos_nombra_los_dos(tmp_path: Path) -> None:
    raiz = repo(tmp_path)
    escribir_fuente(raiz, [entrada()])
    escribir_fuente(raiz, [entrada(part="Parte B")], parte="part_b")

    problemas = _problemas(raiz)

    assert (
        f"'app/data/sources/stonecroft/es/part_b.yaml': 'SA-PAP-2026-A.INS' ya esta en '{PARTE_A}'"
    ) in problemas


def test_una_clausula_repetida_en_una_salida_se_nombra() -> None:
    clausula = {
        "clause_id": "SA-PAP-2026-A.INS",
        "form_id": "SA-PAP-2026",
        "form_version": "2026.1",
        "clause_key": "A.INS",
        "part": "Parte A",
        "language": "es",
        "text": "Relleno de prueba.",
        "issuer_label": "Seguros Aburrá",
    }
    archivo = json.dumps({"form_id": "SA-PAP-2026", "clauses": [clausula, clausula]})

    problemas = manifest.verify_output(
        "app/data/tenants/stonecroft/clauses/SA-PAP-2026.json", archivo.encode()
    )

    assert problemas == [
        "'app/data/tenants/stonecroft/clauses/SA-PAP-2026.json': (raiz): clause_id "
        "repetidos: SA-PAP-2026-A.INS"
    ]


# --- BR3.4: cada distractor dice con que se confunde ---------------------------


@pytest.mark.parametrize(
    ("cambios", "esperado"),
    [
        (
            {
                "kind": "distractor",
                "source_id": "SA-PAP-2026-A.INS.ALT",
                "clause_key": "A.INS.ALT",
            },
            "un distractor dice con que clausula se confunde (distractor_of) y por que",
        ),
        (
            {
                "kind": "distractor",
                "distractor_of": "SA-PAP-2026-A.INS",
                "distractor_reason": "near_duplicate",
            },
            "un distractor no se confunde consigo mismo",
        ),
        (
            {"distractor_reason": "near_duplicate"},
            "solo un distractor lleva distractor_of y distractor_reason",
        ),
        (
            {
                "kind": "distractor",
                "source_id": "SA-PAP-2026-A.INS.ALT",
                "clause_key": "A.INS.ALT",
                "distractor_of": "SA-PAP-2026-A.INS",
                "distractor_reason": "mas_o_menos_igual",
            },
            "texts[0].distractor_reason (SA-PAP-2026-A.INS.ALT)",
        ),
    ],
)
def test_un_distractor_sin_destino_o_sin_razon_se_rechaza(
    tmp_path: Path, cambios: dict[str, str], esperado: str
) -> None:
    raiz = repo(tmp_path)
    escribir_fuente(raiz, [entrada(**cambios)])

    problemas = _problemas(raiz)

    assert f"'{PARTE_A}'" in problemas
    assert esperado in problemas


# --- Contra la configuracion de aseguradoras ----------------------------------


def test_una_agencia_no_tiene_textos_propios(tmp_path: Path) -> None:
    raiz = repo(tmp_path)
    escribir_fuente(raiz, [entrada(source_id="AC-PAP-2026-A.INS")], tenant="knotwell", idioma="en")

    assert "'knotwell' es una agencia y no tiene textos propios" in _problemas(raiz)


def test_la_cabecera_y_la_ruta_tienen_que_decir_lo_mismo(tmp_path: Path) -> None:
    raiz = repo(tmp_path)
    # Un archivo escrito para ingles que acabo en la carpeta de espanol.
    ingles = escribir_fuente(raiz, [entrada()], idioma="en")
    destino = raiz / PARTE_A
    destino.parent.mkdir(parents=True)
    ingles.rename(destino)

    assert f"'{PARTE_A}': language: la cabecera dice 'en' y la ruta 'es'" in _problemas(raiz)


def test_un_identificador_con_el_prefijo_de_otra_aseguradora_se_rechaza(tmp_path: Path) -> None:
    raiz = repo(tmp_path)
    escribir_fuente(raiz, [entrada(source_id="AP-PAP-2026-A.INS")])

    assert "no empieza por el prefijo 'SA' de su aseguradora" in _problemas(raiz)


# --- BR3.6: la poliza emitida -------------------------------------------------

POLIZA = "app/data/tenants/stonecroft/issued_policies/POL-11.json"


def _problemas_de_poliza(**cambios: Any) -> list[str]:
    return manifest.verify_output(POLIZA, json.dumps(poliza(**cambios)).encode())


def test_una_poliza_valida_no_tiene_problemas() -> None:
    assert _problemas_de_poliza() == []


@pytest.mark.parametrize(
    ("cambios", "esperado"),
    [
        ({"form_version": None}, f"'{POLIZA}': form_version: falta 'form_version'"),
        ({"policy_number": "POL-12345"}, f"'{POLIZA}': policy_number:"),
        ({"policy_number": "SA-100042"}, f"'{POLIZA}': policy_number:"),
        (
            {"endorsement_ids": ["AP-PAP-2026-END-1"]},
            "endorsement_ids trae endosos que no son de 'SA-PAP-2026'",
        ),
        ({"period_end": "2025-12-31"}, "el periodo termina antes de empezar"),
        ({"form_version": "2025.4"}, "form_version '2025.4' no es de su formulario"),
    ],
)
def test_una_poliza_sin_version_con_otro_numero_o_endosos_ajenos_no_valida(
    cambios: dict[str, Any], esperado: str
) -> None:
    problemas = "\n".join(_problemas_de_poliza(**cambios))

    assert esperado in problemas


# --- BR7.1: datos personales ficticios y reconocibles como tales ---------------


@pytest.mark.parametrize(
    ("cambios", "clave", "esperado"),
    [
        ({"named_insured": persona(phone="310 555 0200")}, "named_insured.phone", "555-01XX"),
        ({"named_insured": persona(phone="310 777 0142")}, "named_insured.phone", "555-01XX"),
        ({"named_insured": persona(email="alguien@gmail.com")}, "named_insured.email", ""),
        (
            {"vehicles": [vehiculo(vin="1M8GDM9AXKP042788")]},
            "vehicles[0].vin",
            "pasa su digito de control",
        ),
    ],
)
def test_un_dato_personal_fuera_de_su_rango_ficticio_se_nombra(
    cambios: dict[str, Any], clave: str, esperado: str
) -> None:
    problemas = "\n".join(_problemas_de_poliza(**cambios))

    assert f"'{POLIZA}': {clave}:" in problemas
    assert esperado in problemas


def test_el_digito_de_control_del_vin_es_el_de_la_norma() -> None:
    # El ejemplo clasico de la norma: su digito de control es 'X'.
    assert models.vin_check_digit("1M8GDM9AXKP042788") == "X"
    assert models.vin_check_digit(VIN_FICTICIO) != VIN_FICTICIO[8]


def test_los_telefonos_ficticios_de_los_dos_idiomas_validan() -> None:
    for telefono in ("310 555 0142", "+57 310 555 0199", "212-555-0100", "(212) 555-0142"):
        assert models.PersonaRef.model_validate(persona(phone=telefono)).phone == telefono


# --- Muestra humana y formularios ---------------------------------------------


def test_un_veredicto_sin_fecha_ni_commit_no_valida() -> None:
    ids = [f"SA-PAP-2026-A.EXCL.{n}" for n in range(1, 11)]
    with pytest.raises(ValueError, match="un veredicto lleva la fecha"):
        models.ReviewSample.model_validate(
            {
                "tenant_id": "stonecroft",
                "sample_seed": 7,
                "clause_ids": ids,
                "verdict": "own_text_structure_ok",
            }
        )
    with pytest.raises(ValueError, match="clause_ids"):
        models.ReviewSample.model_validate(
            {"tenant_id": "stonecroft", "sample_seed": 7, "clause_ids": ids[:9]}
        )


def test_un_formulario_base_sin_jurisdiccion_no_valida() -> None:
    formulario = {
        "form_id": "SA-PAP-2026",
        "form_kind": "base",
        "form_version": "2026.1",
        "issuer_tenant": "stonecroft",
        "issuer_label": "Seguros Aburrá",
        "language": "es",
        "clause_ids": ["SA-PAP-2026-A.INS"],
    }

    problemas = manifest.verify_output(
        "app/data/tenants/stonecroft/forms/SA-PAP-2026.json", json.dumps(formulario).encode()
    )

    assert problemas == [
        "'app/data/tenants/stonecroft/forms/SA-PAP-2026.json': (raiz): 'SA-PAP-2026': un "
        "formulario base referencia su documento de jurisdiccion"
    ]


# --- La copia de los estados del caso no se queda sola -------------------------


def test_los_estados_resoluciones_y_hablantes_sembrados_son_los_del_registro_del_caso() -> None:
    assert [e.value for e in models.SeededState] == [e.value for e in CaseState]
    assert [e.value for e in models.SeededResolution] == [e.value for e in Resolution]
    assert [e.value for e in models.SeededSpeaker] == [e.value for e in Speaker]
