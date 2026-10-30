"""Reconocer el numero de un caso escrito en el chat (US1.19, US1.20).

Lo importante es lo que **no** se reconoce: un numero de poliza tiene una forma parecida, y la persona
lo escribe mientras se identifica; y con solo dos letras de prefijo, una placa o un modelo de carro
tambien se le parecen. Y lo que si: el de cualquier aseguradora, para que uno ajeno reciba la
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
        ("SA-1", "SA-1"),
        ("AP-29", "AP-29"),
        ("mi caso es ap-29", "AP-29"),
        ("es el AP 29", "AP-29"),
        ("AP29", "AP-29"),
        ("seguimos con el caso AP-29, por favor", "AP-29"),
        ("(AP-29)", "AP-29"),
        ("AP-482913", "AP-482913"),
        # El de cualquier aseguradora cargada: la respuesta a uno ajeno es la de uno inventado.
        ("AC-7", "AC-7"),
        ("SA-333", "SA-333"),
    ],
)
def test_reconoce_el_numero_de_caso_escrito_de_varias_formas(texto: str, esperado: str) -> None:
    assert case_number.find(texto) == esperado


@pytest.mark.parametrize(
    "texto",
    [
        "hola",
        # Lo que tiene casi la forma de un numero de caso y es otra cosa: una poliza, una
        # placa, un modelo de carro, el identificador de un formulario o de una clausula.
        "mi póliza es POL-11",
        "POL-23",
        "mi placa es ZNX-9706",
        "SA-PAP-2026",
        "AP-PAP-2026-END-3",
        "la clausula SA-PAP-2026-D.LIMIT",
        "ZAP-29",
        "un Mazda CX-5",
        # Un prefijo que ninguna aseguradora cargada usa.
        "XY-29",
        # Un contador que no lo es: con cero a la izquierda, de mas de seis cifras o pegado
        # a una letra.
        "AP-029",
        "AP-0",
        "AP-1234567",
        "AP-29A",
        "mi teléfono es 300 123 4567",
    ],
)
def test_no_toma_por_numero_de_caso_lo_que_no_lo_es(texto: str) -> None:
    assert case_number.find(texto) is None


def test_un_mensaje_con_dos_numeros_atiende_el_primero() -> None:
    assert case_number.find("SA-1 o SA-2") == "SA-1"


def test_sin_aseguradoras_cargadas_no_reconoce_nada(monkeypatch: pytest.MonkeyPatch) -> None:
    sin_nada = tenancy_config.LoadedTenants(available=(), unavailable=())
    monkeypatch.setattr(tenancy_config, "loaded", lambda: sin_nada)

    assert case_number.find("SA-1") is None


def test_las_dos_respuestas_a_un_numero_que_no_se_retoma_no_dicen_el_motivo() -> None:
    encendida = case_number.not_resumed(continuity_enabled=True, language="es")
    apagada = case_number.not_resumed(continuity_enabled=False, language="es")

    assert encendida != apagada
    for frase in (encendida, apagada):
        assert "SA" not in frase.split() and "existe" not in frase.lower()
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
        case_number="SA-1",
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

    assert "SA-1" in frase
    assert "ajustador" not in frase.lower()
    assert "adjuster" not in frase.lower()


@pytest.mark.parametrize("estado", [CaseState.DERIVED, CaseState.AWAITING_INSURED])
def test_un_caso_con_un_ajustador_sigue_diciendolo(estado: CaseState) -> None:
    frase = case_number.not_in_capture(_vista(estado), language="es")

    assert "ajustador" in frase.lower()


def test_un_caso_en_revision_no_se_retoma_porque_el_chat_ya_no_toma_datos() -> None:
    assert CaseState.VERIFYING not in case_number.CONTINUABLE
    assert CaseState.DECIDING not in case_number.CONTINUABLE
