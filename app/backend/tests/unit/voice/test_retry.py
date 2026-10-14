"""Cuando no se entendio lo que se dijo (BR3.4, AC1.23.3)."""

from __future__ import annotations

import pytest

from untangle.base import Locale
from untangle.providers.ports import Transcript
from untangle.voice import retry

from .dobles import VACIO, final

IDIOMAS: tuple[Locale, ...] = ("en", "es")


def test_nada_no_se_entiende() -> None:
    assert not retry.understood(None)


def test_una_transcripcion_vacia_no_se_entiende() -> None:
    assert not retry.understood(VACIO)


def test_una_transcripcion_de_solo_espacios_no_se_entiende() -> None:
    assert not retry.understood(final("   "))


def test_una_transcripcion_clara_se_entiende() -> None:
    assert retry.understood(final("highway exit twelve", confianza=0.95))


def _mezcla(
    claras: str, confianza_clara: float, dudosas: str, confianza_dudosa: float
) -> Transcript:
    claro = final(claras, confianza=confianza_clara)
    dudoso = final(dudosas, confianza=confianza_dudosa)
    return type(claro)(text=claro.text, is_final=True, words=(*claro.words, *dudoso.words))


def test_una_palabra_dudosa_no_tumba_una_frase_clara() -> None:
    """Llamada real del 2026-10-07: siete palabras seguras y una en 0,58 se
    descartaban enteras con la regla de la peor palabra, y la agente decia «no le
    escuche bien» a una frase que habia oido perfectamente."""
    frase = _mezcla("tuve un choque en la calle", 0.95, "diez", 0.58)
    assert retry.understood(frase, confidence_floor=0.6)


def test_una_frase_mayormente_dudosa_no_se_entiende() -> None:
    """El ruido de fondo transcrito como palabras sueltas sigue sin entenderse."""
    frase = _mezcla("eh", 0.9, "mm ta la", 0.2)
    assert not retry.understood(frase, confidence_floor=0.6)


def test_sin_confianza_no_cuenta_en_contra() -> None:
    """BR3.1 de U15: nula significa 'el proveedor no lo dijo', nunca 'salio mal'.
    Tratarla como la peor palabra posible pediria repetir todo el tiempo."""
    assert retry.understood(final("highway exit twelve", confianza=None))


def test_la_escalera_tiene_tres_peldanos_y_cada_uno_dice_otra_cosa() -> None:
    """**El segundo cambió con U18** (BR4.4): decía otra vez "no le escuché bien"
    y ahora dice qué idiomas se atienden y que se puede pedir el cambio.

    Dos criterios aprobados describían este mismo momento --el reconocedor
    devolviendo baja confianza dos turnos seguidos-- con respuestas distintas.
    Gana AC1.31.4 por lo que le sirve a quien está al teléfono: repetirle la misma
    frase dos veces no le ayuda, y es lo que hace colgar a la gente.
    """
    assert retry.next_step(0) is retry.RetryStep.NONE
    assert retry.next_step(1) is retry.RetryStep.ASK_AGAIN
    assert retry.next_step(2) is retry.RetryStep.LANGUAGES
    assert retry.next_step(3) is retry.RetryStep.OFFER


@pytest.mark.parametrize("language", IDIOMAS)
def test_los_tres_peldanos_dicen_tres_cosas_distintas(language: Locale) -> None:
    """Ninguno repite al anterior.

    Es lo que la escalera existe para hacer: si dos peldaños dijeran lo mismo, el
    segundo no sería un peldaño, sería la misma frase otra vez.
    """
    dichas = [retry.prompt_for(n, language=language) for n in (1, 2, 3)]

    assert all(frase is not None for frase in dichas)
    claves = [frase.copy_key for frase in dichas if frase is not None]
    assert claves == [retry.NOT_UNDERSTOOD, retry.ONLY_TWO_LANGUAGES, retry.OFFER]
    textos = [frase.text for frase in dichas if frase is not None]
    assert len(set(textos)) == len(textos)


@pytest.mark.parametrize("language", IDIOMAS)
def test_el_segundo_peldano_nombra_los_dos_idiomas(language: Locale) -> None:
    """AC1.31.4: se dice en español y en inglés a la vez. Quien no entiende uno de los
    dos tiene que poder entender el otro."""
    frase = retry.prompt_for(2, language=language)

    assert frase is not None
    bajo = frase.text.lower()
    assert "español" in bajo and "spanish" in bajo
    assert "inglés" in bajo and "english" in bajo


@pytest.mark.parametrize("language", IDIOMAS)
def test_el_segundo_peldano_ensena_a_pedir_el_otro_idioma(language: Locale) -> None:
    """AC1.31.4 y AC1.31.5, otra vez verdad desde el 2026-10-13: la llamada si cambia de
    idioma a pedido (se quito el 2026-10-11, cuando el reconocedor era de un solo idioma).
    La frase recuerda que se puede decir "in English" o "en español" y nombra al ajustador
    como alternativa, en los dos idiomas."""
    frase = retry.prompt_for(2, language=language)

    assert frase is not None
    texto = frase.text
    # Las dos frases entre comillas son el pedido que la agente promete reconocer.
    assert "in English" in texto and "en español" in texto
    bajo = texto.lower()
    assert "ajustador" in bajo and "adjuster" in bajo
    # Y ya no manda a colgar ni a elegirlo antes de llamar: ahora se puede pedir en la llamada.
    assert "cuelga" not in bajo and "hang up" not in bajo
    assert "antes de llamar" not in bajo and "before you call" not in bajo


def test_cada_pedido_que_el_segundo_peldano_ensena_lo_reconoce_el_ciclo() -> None:
    """La frase promete algo: lo que ensena a decir lo reconoce `language_request`, en el
    sentido en que se dice. Una frase que prometiera un pedido que nadie reconoce seria
    exactamente la promesa que la regla del proyecto prohibe."""
    from untangle.voice import language_request

    assert language_request.requested("in English") == "en"
    assert language_request.requested("en español") == "es"


@pytest.mark.parametrize("language", IDIOMAS)
def test_a_la_tercera_ofrece_otra_cosa_y_nunca_devolver_la_llamada(
    language: Locale,
) -> None:
    frase = retry.prompt_for(3, language=language)
    assert frase is not None
    assert frase.copy_key == retry.OFFER
    bajo = frase.text.lower()
    assert "call you back" not in bajo
    assert "devolver" not in bajo
