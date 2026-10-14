"""La completitud y la evidencia de los campos.

La cifra de completitud es la que ve la persona y la que aparece en la bandeja,
asi que lo que se prueba aqui no es que sume: es **sobre que suma**. Un
denominador fijo daria una cifra que no significa lo mismo en un siniestro que
en una consulta de cobertura, y nadie lo notaria mirando el numero.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from untangle.case_record import fields, schema_loading
from untangle.case_record.crypto import from_storage
from untangle.case_record.models import (
    CaseField,
    CaseSchemaError,
    FieldStatus,
    RecordType,
    Sealed,
)

AHORA = datetime(2026, 9, 20, 15, 0, tzinfo=UTC)
VALOR: Sealed = from_storage(b"sellado-de-prueba")


def campo(clave: str, estado: FieldStatus, **cambios: object) -> CaseField:
    base = {
        "case_id": "CASO-1",
        "field_key": clave,
        "status": estado,
        "updated_at": AHORA,
    }
    if estado is not FieldStatus.NOT_STATED:
        base["value"] = VALOR
        base["evidence_turn_id"] = "turno-1"
    return CaseField(**{**base, **cambios})  # type: ignore[arg-type]


# --- El denominador sale del tipo del caso (BR2.7) ----------------------------


def test_el_siniestro_cuenta_sobre_sus_cinco_campos_obligatorios() -> None:
    """Siete campos en el mapa, cinco en la cuenta: el vehiculo y las otras partes
    son opcionales desde el 2026-10-06 (P4, decision de Miguel) y se ofrecen al
    final sin contar para la completitud."""
    resultado = fields.completeness_of(RecordType.CLAIM, ())

    assert len(resultado.per_field) == 7
    assert resultado.optional == {"vehicle_and_driver", "other_parties"}
    assert resultado.total == 5
    assert resultado.complete == 0


def test_la_consulta_de_cobertura_cuenta_sobre_sus_dos() -> None:
    """La misma cifra sobre otro denominador. Uno fijo mentiria en uno de los dos."""
    resultado = fields.completeness_of(RecordType.COVERAGE_INQUIRY, ())

    assert resultado.total == 2


def test_un_tipo_sin_campos_no_deja_crear_un_caso(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un tipo que no declara ningun campo no deja crear un caso suyo (BR1.6).

    Hasta U19 lo ejercia `quote_request`, que estaba vacio a proposito. Ahora declara sus
    diecisiete campos, asi que la guarda se prueba con un esquema al que se le vacia ese
    tipo: lo que se protege es que un caso con completitud 0/0 no se pueda cerrar sin haber
    capturado nada, no que `quote_request` en particular este vacio.
    """
    vaciado = {**schema_loading.fields_by_record_type(), RecordType.QUOTE_REQUEST: ()}
    monkeypatch.setattr(schema_loading, "fields_by_record_type", lambda: vaciado)

    with pytest.raises(CaseSchemaError) as error:
        fields.completeness_of(RecordType.QUOTE_REQUEST, ())

    assert "quote_request" in str(error.value)


def test_la_solicitud_cuenta_sobre_sus_diecisiete_campos() -> None:
    """El denominador sale del tipo (BR2.7): diecisiete, no los siete de un siniestro."""
    resultado = fields.completeness_of(RecordType.QUOTE_REQUEST, ())

    assert resultado.total == 17
    assert resultado.complete == 0


# --- El umbral lo pone el campo (BR2.2, BR2.6, FD-U4-2) -----------------------


def test_un_campo_que_no_pide_lectura_cuenta_estando_dicho() -> None:
    resultado = fields.completeness_of(
        RecordType.CLAIM, (campo("description", FieldStatus.STATED),)
    )

    assert resultado.per_field["description"] is True
    assert resultado.complete == 1


def test_un_campo_que_pide_lectura_no_cuenta_solo_dicho() -> None:
    """Los bloques de la solicitud de cotizacion se confirman en voz alta: dicho no
    cuenta, confirmado si. En el siniestro ya no queda ninguno asi (P4)."""
    resultado = fields.completeness_of(
        RecordType.QUOTE_REQUEST, (campo("driver_name", FieldStatus.STATED),)
    )

    assert resultado.per_field["driver_name"] is False
    assert resultado.complete == 0


def test_un_campo_que_pide_lectura_cuenta_confirmado() -> None:
    resultado = fields.completeness_of(
        RecordType.QUOTE_REQUEST, (campo("driver_name", FieldStatus.CONFIRMED),)
    )

    assert resultado.per_field["driver_name"] is True


@pytest.mark.parametrize(
    "clave",
    [
        "identity_and_policy",
        "incident_datetime",
        "location",
        "description",
        "vehicle_and_driver",
        "other_parties",
        "injuries",
    ],
)
def test_ningun_campo_del_siniestro_exige_lectura(clave: str) -> None:
    """Decision de Miguel del 2026-10-06 (P4): lo que la persona dice se guarda sin
    "¿es correcto?", y si lo corrige, se corrige. Escrito aqui para que un campo
    con lectura no vuelva al siniestro sin que alguien lo decida."""
    definicion = fields.definition_of(RecordType.CLAIM, clave)

    assert definicion.requires_readback is False


def test_un_campo_dicho_del_siniestro_cuenta_en_el_acto() -> None:
    resultado = fields.completeness_of(RecordType.CLAIM, (campo("injuries", FieldStatus.STATED),))

    assert resultado.per_field["injuries"] is True
    assert resultado.complete == 1
    assert resultado.awaiting_readback == frozenset()


def test_el_campo_no_dicho_no_cuenta() -> None:
    resultado = fields.completeness_of(
        RecordType.CLAIM, (campo("description", FieldStatus.NOT_STATED),)
    )

    assert resultado.complete == 0


def test_un_campo_que_el_esquema_no_declara_no_suma() -> None:
    """Si sumara, guardar basura bajo una clave inventada subiria la cifra."""
    resultado = fields.completeness_of(
        RecordType.CLAIM,
        (campo("description", FieldStatus.STATED), campo("inventado", FieldStatus.STATED)),
    )

    assert resultado.complete == 1
    assert "inventado" not in resultado.per_field


def test_el_siniestro_con_sus_obligatorios_dichos_da_cinco_de_cinco() -> None:
    """Y con los dos opcionales dichos tambien, sigue dando cinco de cinco: lo
    opcional esta en el mapa y no en la cuenta (P4)."""
    obligatorios = tuple(
        campo(d.key, FieldStatus.STATED)
        for d in fields.definitions_for(RecordType.CLAIM)
        if not d.optional
    )
    todos = tuple(
        campo(d.key, FieldStatus.STATED) for d in fields.definitions_for(RecordType.CLAIM)
    )

    assert (
        fields.completeness_of(RecordType.CLAIM, obligatorios).complete,
        fields.completeness_of(RecordType.CLAIM, obligatorios).total,
    ) == (5, 5)
    completo = fields.completeness_of(RecordType.CLAIM, todos)
    assert (completo.complete, completo.total) == (5, 5)
    assert completo.per_field["vehicle_and_driver"] is True


# --- La evidencia (BR2.3, BR2.4, BR2.5) ---------------------------------------


def test_un_campo_dicho_lleva_exactamente_una_evidencia() -> None:
    con_las_dos = {
        "case_id": "CASO-1",
        "field_key": "description",
        "status": FieldStatus.STATED,
        "value": VALOR,
        "evidence_turn_id": "turno-1",
        "evidence_change_id": "chg-1",
        "updated_at": AHORA,
    }

    with pytest.raises(ValueError, match="exactamente una evidencia"):
        CaseField(**con_las_dos)  # type: ignore[arg-type]


def test_un_campo_no_dicho_no_lleva_evidencia_ni_valor() -> None:
    """Es la distincion que separa "la persona dijo que no hubo lesionados" de
    "nadie pregunto", y es el error que el experimento 2 encontro."""
    with pytest.raises(ValueError, match="no dicho no lleva evidencia"):
        CaseField(
            case_id="CASO-1",
            field_key="injuries",
            status=FieldStatus.NOT_STATED,
            evidence_turn_id="turno-1",
            updated_at=AHORA,
        )


def test_un_campo_corregido_desde_la_bandeja_no_lleva_marca_de_lectura() -> None:
    """No hubo conversacion: nadie se lo leyo en voz alta a nadie (BR2.5)."""
    with pytest.raises(ValueError, match="no lleva marca de lectura"):
        CaseField(
            case_id="CASO-1",
            field_key="description",
            status=FieldStatus.CONFIRMED,
            value=VALOR,
            evidence_change_id="chg-1",
            confirmed_aloud_at=AHORA,
            updated_at=AHORA,
        )


def test_un_campo_que_el_esquema_no_declara_no_se_valida() -> None:
    """Falla en el acto y nombra el campo y el tipo, en vez de escribir algo que
    la completitud despues no sabria contar."""
    with pytest.raises(CaseSchemaError) as error:
        fields.validate_field(RecordType.COVERAGE_INQUIRY, campo("injuries", FieldStatus.STATED))

    assert "injuries" in str(error.value)
    assert "coverage_inquiry" in str(error.value)


def test_un_campo_declarado_pasa_la_validacion() -> None:
    declarado = campo("identity_and_policy", FieldStatus.STATED)

    assert fields.validate_field(RecordType.COVERAGE_INQUIRY, declarado) is declarado


# --- BR2.2: lo que exige lectura no llega a confirmado sin ella ---------------


def test_un_campo_de_lectura_no_llega_a_confirmado_sin_la_lectura() -> None:
    """Sin esto, la cifra de completitud subia sin que nadie hubiera leido nada.

    Es el hueco que encontro la revision: `fields.py` imponia el umbral de la
    completitud (BR2.6) y nadie imponia como se alcanza el estado (BR2.2).
    """
    with pytest.raises(CaseSchemaError, match="lectura de confirmacion"):
        fields.validate_field(
            RecordType.QUOTE_REQUEST,
            campo("driver_name", FieldStatus.CONFIRMED),
        )


def test_el_mismo_campo_con_su_marca_de_lectura_si_pasa() -> None:
    confirmado = campo("driver_name", FieldStatus.CONFIRMED, confirmed_aloud_at=AHORA)

    assert fields.validate_field(RecordType.QUOTE_REQUEST, confirmado) is confirmado


def test_un_campo_corregido_desde_la_bandeja_llega_a_confirmado_sin_lectura() -> None:
    """BR2.5: una persona lo escribio, no hubo conversacion que leer en voz alta."""
    corregido = CaseField(
        case_id="CASO-1",
        field_key="injuries",
        status=FieldStatus.CONFIRMED,
        value=VALOR,
        evidence_change_id="chg-1",
        updated_at=AHORA,
    )

    assert fields.validate_field(RecordType.CLAIM, corregido) is corregido


def test_un_campo_que_no_exige_lectura_llega_a_confirmado_sin_ella() -> None:
    """La regla es de tres campos, no de todos."""
    confirmado = campo("description", FieldStatus.CONFIRMED)

    assert fields.validate_field(RecordType.CLAIM, confirmado) is confirmado
