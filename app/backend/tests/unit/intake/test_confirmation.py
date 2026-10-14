"""BR3.1, FD-U11-8: la lectura de confirmacion y su si/no."""

from __future__ import annotations

import pytest

from untangle.base import Locale
from untangle.case_record.models import RecordType
from untangle.orchestration.nodes.intake import confirmation
from untangle.orchestration.nodes.intake.blocks import Block

# --- FD-U11-8: lesiones, conductor y lugar se nombran, nunca se resumen -----


def test_la_lectura_de_seguridad_nombra_lo_dicho() -> None:
    lectura = confirmation.build_readback(Block.SAFETY, {"injuries": "sin heridos"}, language="es")
    assert "sin heridos" in lectura


def test_la_lectura_de_vehiculo_nombra_lo_dicho() -> None:
    lectura = confirmation.build_readback(
        Block.VEHICLE_AND_DRIVER,
        {"vehicle_and_driver": "un Mazda 3 gris, placa ABC123"},
        language="es",
    )
    assert "Mazda 3 gris" in lectura


def test_la_lectura_de_cuando_y_donde_nombra_los_dos_campos() -> None:
    lectura = confirmation.build_readback(
        Block.WHEN_AND_WHERE,
        {"incident_datetime": "ayer a las cinco", "location": "avenida Boyacá"},
        language="es",
    )
    assert "ayer a las cinco" in lectura
    assert "avenida Boyacá" in lectura


# --- BR3.1: sin un si explicito, no cuenta -----------------------------------


def test_si_confirma() -> None:
    assert confirmation.is_affirmative("Sí, así es.", language="es")
    assert not confirmation.is_negative("Sí, así es.", language="es")


def test_no_abre_la_correccion() -> None:
    assert confirmation.is_negative("No, eso no es correcto.", language="es")
    assert not confirmation.is_affirmative("No, eso no es correcto.", language="es")


def test_una_respuesta_ambigua_no_cuenta_como_si() -> None:
    """La prueba que aisla BR3.1: sin una forma de la lista de si, no hay confirmacion."""
    assert not confirmation.is_affirmative("Mmm, no sé, tal vez.", language="es")


def test_confirmacion_en_ingles() -> None:
    assert confirmation.is_affirmative("Yes, that's right.", language="en")
    assert confirmation.is_negative("No, that's wrong.", language="en")


# --- Lo que la revision de la tanda 2 corrigio --------------------------------


def test_un_si_seguido_de_un_no_descriptivo_confirma() -> None:
    """BR3.1: "Si, no hubo heridos" es la forma normal de confirmar el bloque de
    seguridad, cuya lectura pregunta justo por las lesiones.

    La tanda 2 buscaba "no" en cualquier posicion, asi que esa respuesta abria la
    correccion, se volvia a leer el bloque, y la persona no tenia forma de salir
    del bucle.
    """
    assert confirmation.is_affirmative("Sí, no hubo heridos.", language="es")
    assert not confirmation.is_negative("Sí, no hubo heridos.", language="es")
    assert confirmation.is_affirmative("Yes, no injuries.", language="en")


def test_un_no_que_abre_la_respuesta_sigue_negando() -> None:
    assert confirmation.is_negative("No, yo conducía.", language="es")
    assert not confirmation.is_affirmative("No, yo conducía.", language="es")
    assert confirmation.is_negative("No, that's wrong.", language="en")


def test_una_correccion_nombrada_niega_en_cualquier_posicion() -> None:
    assert confirmation.is_negative("Eso no es correcto, fue el jueves.", language="es")
    assert not confirmation.is_affirmative("Eso no es correcto, fue el jueves.", language="es")


def test_un_no_seguido_de_asi_esta_bien_confirma() -> None:
    """Lo vio Miguel el 2026-10-06: a "No, asi esta bien" la agente le borraba el
    bloque y lo volvia a preguntar. El "no" contesta a la duda, no al dato."""
    assert confirmation.is_affirmative("No, así está bien.", language="es")
    assert not confirmation.is_negative("No, así está bien.", language="es")
    assert confirmation.is_affirmative("No, that's fine.", language="en")
    assert confirmation.is_affirmative("No no, all good.", language="en")


def test_no_esta_bien_sigue_corrigiendo() -> None:
    """La frase entera es lo que confirma: "no esta bien" niega, como siempre."""
    assert confirmation.is_negative("No está bien, fue el jueves.", language="es")
    assert not confirmation.is_affirmative("No está bien, fue el jueves.", language="es")
    assert confirmation.is_negative("No, that's not right.", language="en")


def test_el_si_y_el_no_se_reconocen_aunque_vengan_en_el_otro_idioma() -> None:
    """BR2.2: un turno corto no cambia el idioma de la conversacion, asi que "No,
    asi esta bien" llega con `language="en"` en una aseguradora que habla ingles
    por omision. Se leia como un no y la lectura se repetia (Sunmeadow,
    2026-10-06). El idioma de la respuesta no cambia; lo que cambia es que se
    entiende lo dicho."""
    assert confirmation.is_affirmative("No, así está bien.", language="en")
    assert confirmation.is_affirmative("Sí, correcto.", language="en")
    assert confirmation.is_affirmative("Yes, that's right.", language="es")
    assert confirmation.is_negative("Eso no es correcto.", language="en")
    assert confirmation.is_negative("No, that's wrong.", language="es")


# --- AC1.5.2: el ultimo bloque del orden fijo --------------------------------

VALORES = {
    "description": "otro carro me chocó por detrás",
    "incident_datetime": "12 de marzo de 2026",
    "location": "la autopista salida 12",
    "vehicle_and_driver": "yo conducía mi Mazda",
    "injuries": "nadie resultó herido",
    "identity_and_policy": "la póliza POL-123456",
    "question_asked": "si el vidrio está cubierto",
}


def test_el_siniestro_ya_no_tiene_resumen_de_cierre() -> None:
    """P4 (decision de Miguel, 2026-10-06): el siniestro cierra con la frase del
    recorrido rapido, que compone el nodo, y no con un resumen que pregunta "¿esta
    todo correcto?". Pedir el resumen de un siniestro es un error de quien llama."""
    with pytest.raises(ValueError, match="recorrido rapido"):
        confirmation.build_closing_summary(RecordType.CLAIM, VALORES, language="es")
    with pytest.raises(ValueError, match="recorrido rapido"):
        confirmation.closing_summary_key(RecordType.CLAIM)


def test_el_cierre_de_una_consulta_de_cobertura_tiene_su_propia_forma() -> None:
    """Dos campos, no siete: su cierre confirma la poliza y la pregunta."""
    resumen = confirmation.build_closing_summary(
        RecordType.COVERAGE_INQUIRY, VALORES, language="en"
    )

    assert "POL-123456" in resumen
    assert "nadie resultó herido" not in resumen


@pytest.mark.parametrize(("idioma", "esperado"), [("es", "15/03/2004"), ("en", "03/15/2004")])
def test_la_fecha_de_nacimiento_se_lee_como_la_escribe_una_persona(
    idioma: Locale, esperado: str
) -> None:
    """La comprension la deja en AAAA-MM-DD; leerla asi sonaba a sistema (2026-10-08)."""
    lectura = confirmation.build_readback(
        Block.QUOTE_DRIVER,
        {
            "driver_name": "Miguel Cruz",
            "driver_birth_date": "2004-03-15",
            "license_years": "4",
            "license_jurisdiction": "Itagüí",
        },
        language=idioma,
    )

    assert esperado in lectura
    assert "2004-03-15" not in lectura
