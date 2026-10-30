"""Las otras partes y la transcripcion.

Lo que se prueba de las partes no es que se guarden: es que **lo que no se sabe
quede vacio**. Un nombre inventado para que la ficha se vea completa es peor que
un hueco, porque el hueco se ve y se pregunta, y el invento se cita.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from untangle.case_record import crypto, parties, transcript
from untangle.case_record.models import (
    CaseParty,
    Channel,
    FieldStatus,
    PartyRole,
    Speaker,
)

AHORA = datetime(2026, 9, 20, 15, 0, tzinfo=UTC)


@pytest.fixture
def cifrador(monkeypatch: pytest.MonkeyPatch) -> crypto.Cipher:
    monkeypatch.setenv(crypto.KEY_ENV_VAR, crypto.generate_key())
    return crypto.Cipher.from_settings()


def _registrar(cifrador: crypto.Cipher, details: parties.PartyDetails) -> CaseParty:
    return parties.register_party(
        case_id="CASO-1",
        party_id="parte-1",
        role=PartyRole.WITNESS,
        details=details,
        cipher=cifrador,
    )


# --- Lo que no se sabe queda vacio (BR1.8, AC1.8.2) ---------------------------


def test_una_parte_de_la_que_solo_se_sabe_el_rol_queda_con_todo_vacio(
    cifrador: crypto.Cipher,
) -> None:
    """Y eso es un dato, no un hueco que rellenar."""
    parte = _registrar(cifrador, parties.PartyDetails())

    assert parte.role is PartyRole.WITNESS
    assert parte.name is None
    assert parte.contact is None
    assert parte.plate is None
    assert parte.injury_status is None


def test_los_atributos_personales_se_guardan_sellados(cifrador: crypto.Cipher) -> None:
    """Ni el nombre ni el contacto aparecen legibles en lo que se persiste."""
    parte = _registrar(
        cifrador,
        parties.PartyDetails(name="Nayibe Quintero Ospina", contact="+57 300 111 2233"),
    )

    assert parte.name is not None
    assert b"Nayibe" not in bytes(parte.name)
    assert b"Quintero" not in bytes(parte.name)
    assert parte.contact is not None
    assert b"300" not in bytes(parte.contact)


def test_lo_sellado_se_vuelve_a_abrir_con_la_misma_clave(cifrador: crypto.Cipher) -> None:
    """El ajustador tiene que poder leerlo: cifrar sin poder abrir es perder."""
    parte = _registrar(cifrador, parties.PartyDetails(name="Nayibe Quintero Ospina"))

    assert parte.name is not None
    assert cifrador.unseal(parte.name, stored_key_id=cifrador.id) == "Nayibe Quintero Ospina"


def test_los_atributos_no_personales_no_se_sellan(cifrador: crypto.Cipher) -> None:
    """ "Sedan gris" no identifica a nadie, y cifrarlo haria imposible agrupar
    casos por vehiculo sin abrir cada fila."""
    parte = _registrar(
        cifrador,
        parties.PartyDetails(vehicle_description="Sedan gris", injury_status="sin lesiones"),
    )

    assert parte.vehicle_description == "Sedan gris"
    assert parte.injury_status == "sin lesiones"


# --- La placa lleva su estado y su evidencia ----------------------------------


def test_una_placa_dicha_pero_no_confirmada_no_cuenta_como_completa(
    cifrador: crypto.Cipher,
) -> None:
    """Una placa equivocada manda a la aseguradora a perseguir a otra persona."""
    parte = _registrar(
        cifrador,
        parties.PartyDetails(
            plate=parties.PlateReading(
                value="ABC123", status=FieldStatus.STATED, evidence_turn_id="turno-4"
            )
        ),
    )

    assert parte.plate_status is FieldStatus.STATED
    assert parte.plate_evidence_turn_id == "turno-4"
    assert parte.plate is not None
    assert b"ABC123" not in bytes(parte.plate)


def test_una_placa_confirmada_lo_dice(cifrador: crypto.Cipher) -> None:
    parte = _registrar(
        cifrador,
        parties.PartyDetails(
            plate=parties.PlateReading(
                value="ABC123", status=FieldStatus.CONFIRMED, evidence_turn_id="turno-4"
            )
        ),
    )

    assert parte.plate_status is FieldStatus.CONFIRMED


def test_una_placa_dicha_sin_evidencia_no_se_puede_construir() -> None:
    """La evidencia es la mitad del punto: sin ella no se sabe de donde salio."""
    with pytest.raises(ValueError, match="el turno que la respalda"):
        CaseParty(
            party_id="parte-1",
            case_id="CASO-1",
            role=PartyRole.OTHER_DRIVER,
            plate_status=FieldStatus.STATED,
        )


def test_una_placa_no_dicha_no_lleva_valor(cifrador: crypto.Cipher) -> None:
    parte = _registrar(cifrador, parties.PartyDetails())

    assert parte.plate_status is FieldStatus.NOT_STATED
    assert parte.plate is None
    assert parte.plate_evidence_turn_id is None


# --- La transcripcion ---------------------------------------------------------


def _borrador(**cambios: object) -> transcript.TurnDraft:
    base = transcript.TurnDraft(
        turn_id="turno-1",
        case_id="CASO-1",
        speaker=Speaker.INSURED,
        channel=Channel.CHAT,
        language="es",
        started_at=AHORA,
    )
    return transcript.TurnDraft(**{**base.__dict__, **cambios})


def test_el_turno_se_guarda_tal_como_se_dijo() -> None:
    """Desde el 2026-10-30 la conversacion no se redacta al guardarse (decision de
    Miguel): ninguna pantalla vuelve a mostrar «[NOMBRE 1]»."""
    turno = transcript.append(_borrador(), "Me llamo Nayibe Quintero y mi telefono es 3001112233")

    assert turno.text_redacted == "Me llamo Nayibe Quintero y mi telefono es 3001112233"


def test_el_idioma_sale_del_borrador() -> None:
    turno = transcript.append(_borrador(language="en"), "My name is Nayibe Quintero")

    assert turno.language == "en"


def test_el_turno_conserva_lo_que_no_es_texto() -> None:
    turno = transcript.append(_borrador(interrupted=True, ended_at=AHORA), "Se me cruzo un carro")

    assert turno.interrupted is True
    assert turno.ended_at == AHORA
    assert turno.speaker is Speaker.INSURED
