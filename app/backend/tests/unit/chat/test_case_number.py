"""Reconocer el numero de un caso escrito en el chat (US1.19, US1.20).

Lo importante es lo que **no** se reconoce: un numero de poliza tiene la misma forma, y la persona lo
escribe mientras se identifica. Y lo que si: el de cualquier aseguradora, para que uno ajeno reciba la
misma respuesta que uno inventado (AC1.20.3).
"""

from __future__ import annotations

import pytest

from untangle.case_record.api import CaseView
from untangle.case_record.models import CaseState, Channel, Completeness, Origin, RecordType
from untangle.chat import case_number
from untangle.tenancy import config as tenancy_config


@pytest.fixture(autouse=True)
def _estado_limpio() -> None:
    tenancy_config.reset()


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("STO-482913", "STO-482913"),
        ("mi caso es sto-482913", "STO-482913"),
        ("es el STO 482 913", "STO-482913"),
        ("STO482913", "STO-482913"),
        ("seguimos con el caso STO-482913, por favor", "STO-482913"),
        ("(STO-482913)", "STO-482913"),
        # El de cualquier aseguradora cargada: la respuesta a uno ajeno es la de uno inventado.
        ("KNO-111222", "KNO-111222"),
        ("SUN-333444", "SUN-333444"),
    ],
)
def test_reconoce_el_numero_de_caso_escrito_de_varias_formas(texto: str, esperado: str) -> None:
    assert case_number.find(texto) == esperado


@pytest.mark.parametrize(
    "texto",
    [
        "hola",
        "mi póliza es POL-100042",
        "POL-000001",
        "XYZ-482913",
        "STO-48291",
        "STO-4829130",
        "ASTO-482913",
        "STO-482913A",
        "mi teléfono es 300 123 4567",
    ],
)
def test_no_toma_por_numero_de_caso_lo_que_no_lo_es(texto: str) -> None:
    assert case_number.find(texto) is None


def test_un_mensaje_con_dos_numeros_atiende_el_primero() -> None:
    assert case_number.find("STO-111111 o STO-222222") == "STO-111111"


def test_sin_aseguradoras_cargadas_no_reconoce_nada(monkeypatch: pytest.MonkeyPatch) -> None:
    sin_nada = tenancy_config.LoadedTenants(available=(), unavailable=())
    monkeypatch.setattr(tenancy_config, "loaded", lambda: sin_nada)

    assert case_number.find("STO-482913") is None


def test_las_dos_respuestas_a_un_numero_que_no_se_retoma_no_dicen_el_motivo() -> None:
    encendida = case_number.not_resumed(continuity_enabled=True, language="es")
    apagada = case_number.not_resumed(continuity_enabled=False, language="es")

    assert encendida != apagada
    for frase in (encendida, apagada):
        assert "STO" not in frase and "existe" not in frase.lower()
    # AC1.19.5: apagada, no promete que el chat pueda retomarlo.
    assert "mismo canal" in apagada
    assert "seguir por chat" not in apagada.lower()


def test_cada_respuesta_sale_en_los_dos_idiomas() -> None:
    for continuidad in (True, False):
        es = case_number.not_resumed(continuity_enabled=continuidad, language="es")
        en = case_number.not_resumed(continuity_enabled=continuidad, language="en")
        assert es != en and not es.startswith("chat.") and not en.startswith("chat.")


def test_los_estados_en_que_el_chat_sigue_tomando_datos_son_los_de_captura() -> None:
    assert {estado.value for estado in case_number.CONTINUABLE} == {"open", "capturing"}


def _vista(estado: CaseState) -> CaseView:
    return CaseView(
        case_id="caso-1",
        case_number="STO-482913",
        record_type=RecordType.CLAIM,
        state=estado,
        resolution=None,
        channel=Channel.CHAT,
        origin=Origin.PUBLIC_CHAT,
        language="es",
        policy_ref=None,
        derivation_reason=None,
        derived_turn_id=None,
        completeness=Completeness(per_field={"injuries": True}, complete=1, total=1),
    )


@pytest.mark.parametrize("language", ["es", "en"])
@pytest.mark.parametrize("estado", [CaseState.VERIFYING, CaseState.DECIDING])
def test_un_caso_en_revision_no_dice_que_ya_lo_tiene_un_ajustador(
    estado: CaseState, language: str
) -> None:
    """US1.17: puede cerrarse solo, asi que todavia no se sabe que lo tendra uno."""
    frase = case_number.not_in_capture(_vista(estado), language=language)  # type: ignore[arg-type]

    assert "STO-482913" in frase
    assert "ajustador" not in frase.lower()
    assert "adjuster" not in frase.lower()


@pytest.mark.parametrize("estado", [CaseState.DERIVED, CaseState.AWAITING_INSURED])
def test_un_caso_con_un_ajustador_sigue_diciendolo(estado: CaseState) -> None:
    frase = case_number.not_in_capture(_vista(estado), language="es")

    assert "ajustador" in frase.lower()


def test_un_caso_en_revision_no_se_retoma_porque_el_chat_ya_no_toma_datos() -> None:
    assert CaseState.VERIFYING not in case_number.CONTINUABLE
    assert CaseState.DECIDING not in case_number.CONTINUABLE
