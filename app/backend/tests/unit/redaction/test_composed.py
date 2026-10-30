"""Lo que dice la agente, tapado para guardarse: `redact_composed` (2026-10-10).

Visto en el chat: la respuesta "Encontre la poliza POL-11 a nombre de Natalia
Henao Rendon" se guardaba en claro, porque salia de una frase del catalogo y esa
puerta no miraba lo que la frase llevaba dentro. La otra puerta, `redact`, guardaba
"[NOMBRE 1] la poliza": tapaba nuestra palabra. Esta tapa los datos y respeta las
palabras.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from untangle.compliance.redaction import api as redaccion
from untangle.compliance.redaction.recognizers.models import DetectedEntity, EntityType

#: Frases como las del catalogo, con sus huecos: de aqui sale el vocabulario propio.
FRASES = (
    "Encontré la póliza {policy} a nombre de {holder}, con un {vehicle}. ¿Eres tú?",
    "Perfecto, gracias. Confirmo: {identity}. ¿Es correcto?",
    "Confirmo la placa: {plate}. ¿Es correcto?",
)


@pytest.fixture(autouse=True)
def vocabulario() -> Iterator[None]:
    redaccion.allow_own_vocabulary(FRASES)
    redaccion.allow_public_terms(["Renault Logan"])
    yield
    redaccion.allow_own_vocabulary([])
    redaccion.allow_public_terms([])


def _guardado(texto: str) -> str:
    return str(redaccion.redact_composed(texto, language="es"))


def test_tapa_lo_que_la_frase_lleva_dentro_y_respeta_las_palabras_nuestras() -> None:
    guardado = _guardado(
        "Encontré la póliza POL-11 a nombre de Natalia Henao Rendón, "
        "con un Renault Logan 2024. ¿Eres tú?"
    )

    assert "POL-11" not in guardado
    assert "Natalia" not in guardado
    assert "Rendón" not in guardado
    # Nuestras palabras siguen ahi: el ajustador lee la frase que la persona leyo.
    assert guardado.startswith("Encontré la póliza [PÓLIZA 1] a nombre de [NOMBRE 1]")
    assert "Renault Logan 2024" in guardado


def test_con_un_acuse_delante_tampoco_confunde_el_verbo_con_un_nombre() -> None:
    """El caso de la llamada: con "Perfecto, gracias." delante, `redact` tapaba
    "Encontré" y "Confirmo"."""
    guardado = _guardado("Perfecto, gracias. Confirmo: Natalia Henao Rendón. ¿Es correcto?")

    assert guardado == "Perfecto, gracias. Confirmo: [NOMBRE 1]. ¿Es correcto?"


def test_lo_que_tiene_forma_de_dato_se_tapa_aunque_el_catalogo_lo_nombre() -> None:
    guardado = _guardado("Confirmo la placa: ABC123, y el teléfono 3104567890. ¿Es correcto?")

    assert "ABC123" not in guardado
    assert "3104567890" not in guardado


def test_un_nombre_que_no_es_palabra_nuestra_se_tapa_aunque_vaya_solo() -> None:
    assert "Marcela" not in _guardado("Gracias, Marcela Ríos. ¿Es correcto?")


def test_lo_que_dijo_la_persona_no_cambia_de_puerta() -> None:
    """El vocabulario propio solo cuenta para lo que compone la agente: `redact`
    sigue tapando el texto de la persona entero, como antes."""
    de_la_persona = str(redaccion.redact("Soy Natalia Henao Rendón", language="es"))

    assert "Natalia" not in de_la_persona


def test_sin_vocabulario_instalado_tapa_como_redact() -> None:
    """Falla hacia tapar: un despliegue que no instalo el vocabulario no guarda de mas."""
    redaccion.allow_own_vocabulary([])
    texto = "Confirmo: Natalia Henao Rendón, póliza POL-31."

    assert _guardado(texto) == str(redaccion.redact(texto, language="es"))


# --- El numero del caso no es una persona (2026-10-11) ------------------------------


def _de_persona(texto: str, trozo: str) -> DetectedEntity:
    inicio = texto.index(trozo)
    return DetectedEntity(
        entity_type=EntityType.PERSON,
        start=inicio,
        end=inicio + len(trozo),
        recognizer_id="spacy",
        confidence=0.85,
    )


@pytest.mark.parametrize("numero", ["SA-1", "AP-29", "AC-602938"])
def test_el_numero_del_caso_no_se_tapa_como_si_fuera_un_nombre(numero: str) -> None:
    """El reconocedor de nombres lo etiqueta como persona **segun que prefijo y que
    digitos traiga**: el aviso de la decision se guardaba "tu caso [NOMBRE 1]". Fallo en
    la revision de GitHub y no en cuatro corridas locales, porque el numero era al azar.
    Se prueba la regla y no el modelo, para que no dependa de la suerte. Los de dos
    letras y contador corto (`SA-1`, `AP-29`) incluidos."""
    from untangle.compliance.redaction import detector

    texto = f"Un ajustador revisó tu caso {numero} y lo aprobó."

    assert detector._es_solo_vocabulario_propio(texto, _de_persona(texto, numero))


def test_un_numero_de_poliza_no_se_perdona_por_parecerse() -> None:
    """Tiene la misma forma y si es un dato: lo tapa su propio reconocedor, y esta
    regla no lo excusa."""
    from untangle.compliance.redaction import detector

    texto = "Encontré la póliza POL-14 a tu nombre."

    assert not detector._es_solo_vocabulario_propio(texto, _de_persona(texto, "POL-14"))


def test_el_aviso_que_fallo_en_github_se_guarda_con_su_numero() -> None:
    """El texto exacto de esa corrida, con el numero que el modelo tomo por nombre."""
    aviso = "Un ajustador revisó tu caso SA-602938 y lo aprobó. Tu nota fue «Revisamos las fotos.»."

    assert "SA-602938" in str(redaccion.redact_composed(aviso, language="es"))
