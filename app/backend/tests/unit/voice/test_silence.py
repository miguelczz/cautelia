"""La escalera de silencios (BR5.1, BR5.2, BR5.3)."""

from __future__ import annotations

import pytest

from untangle.base import Locale
from untangle.voice import silence

IDIOMAS: tuple[Locale, ...] = ("en", "es")


def test_sin_silencio_no_hay_peldano() -> None:
    assert silence.next_step(0) is silence.SilenceStep.NONE
    assert silence.prompt_for(0, language="en") is None


@pytest.mark.parametrize(
    ("consecutivos", "paso"),
    [
        (1, silence.SilenceStep.ASK),
        (2, silence.SilenceStep.OFFER),
        (3, silence.SilenceStep.FAREWELL),
    ],
)
def test_los_tres_peldanos_van_en_orden(consecutivos: int, paso: silence.SilenceStep) -> None:
    """El orden es parte del criterio y de la medicion del hito: el 100 % de los
    casos de silencio de DS-5 tiene que recibir las tres en secuencia."""
    assert silence.next_step(consecutivos) is paso


def test_pasado_el_tercero_no_hay_cuarto() -> None:
    """La llamada ya termino en el tercero; un cuarto seria hablarle a nadie."""
    assert silence.next_step(9) is silence.SilenceStep.FAREWELL


def test_solo_el_tercero_termina_la_llamada() -> None:
    finales = [
        silence.prompt_for(n, language="en").ends_call  # type: ignore[union-attr]
        for n in (1, 2, 3)
    ]
    assert finales == [False, False, True]


@pytest.mark.parametrize("language", IDIOMAS)
def test_cada_peldano_trae_su_clave_y_su_texto(language: Locale) -> None:
    for n, clave in (
        (1, silence.STILL_THERE),
        (2, silence.OFFER),
        (3, silence.FAREWELL),
    ):
        frase = silence.prompt_for(n, language=language)
        assert frase is not None
        assert frase.copy_key == clave
        assert frase.text.strip()


@pytest.mark.parametrize("language", IDIOMAS)
def test_ninguna_frase_ofrece_devolver_la_llamada(language: Locale) -> None:
    """BR5.3: la devolucion es C3, no existe, y P7 prohibe ofrecer lo que no
    esta construido. Se comprueba sobre el texto que de verdad sale."""
    prohibidas = ("call you back", "llamamos", "le devolvemos", "devolver la llamada")
    for n in (1, 2, 3):
        frase = silence.prompt_for(n, language=language)
        assert frase is not None
        bajo = frase.text.lower()
        assert not [p for p in prohibidas if p in bajo], frase.text


@pytest.mark.parametrize("language", IDIOMAS)
def test_la_oferta_es_la_misma_frase_aprobada_que_usa_el_otro_camino(
    language: Locale,
) -> None:
    """La decision D8 tiene **una** frase, y el segundo silencio y la tercera vez
    que no se entiende dicen la misma. Dos claves con el mismo texto es como una
    de las dos se queda vieja."""
    from untangle.voice import retry

    del_silencio = silence.prompt_for(2, language=language)
    del_reintento = retry.prompt_for(retry.PELDANOS, language=language)
    assert del_silencio is not None
    assert del_reintento is not None
    assert del_silencio.copy_key == del_reintento.copy_key
    assert del_silencio.text == del_reintento.text


def test_la_tolerancia_de_partida_es_la_de_la_guia_de_voz() -> None:
    assert silence.DEFAULT_TOLERANCE.total_seconds() == 5
