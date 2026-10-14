"""El cierre por voz y el numero de caso (BR3.7, AC1.23.4)."""

from __future__ import annotations

import pytest

from untangle.base import Locale
from untangle.copy_catalog import api as copy_api
from untangle.voice import case_number, closing

pytestmark = pytest.mark.usefixtures("catalogo_cargado")

IDIOMAS: tuple[Locale, ...] = ("en", "es")

# --- El numero de caso --------------------------------------------------------


@pytest.mark.parametrize("language", IDIOMAS)
def test_los_digitos_van_uno_a_uno_en_dos_grupos_de_tres(language: Locale) -> None:
    """D2: digitos uno a uno. Desde el 2026-10-09, una sola pausa en medio: con una
    coma entre cada digito la voz se detenia seis veces y el numero sonaba lento."""
    dicho = case_number.spell("SUN482913", language=language)
    esperado = (
        "four eight two, nine one three" if language == "en" else "cuatro ocho dos, nueve uno tres"
    )
    assert dicho == esperado


@pytest.mark.parametrize("language", IDIOMAS)
def test_el_cero_se_dice_por_su_nombre_y_nunca_oh(language: Locale) -> None:
    """Decision D2. El nombre sale de la tabla de U11, donde el cero solo tiene
    un nombre: un modulo que tradujera digitos por su cuenta seria la segunda
    tabla que un dia dice 'oh'."""
    dicho = case_number.spell("SUN000000", language=language)
    esperado = "zero" if language == "en" else "cero"
    assert dicho.replace(",", "").split() == [esperado] * 6


@pytest.mark.parametrize("language", IDIOMAS)
def test_la_frase_nombra_la_aseguradora_y_no_deletrea_el_prefijo(language: Locale) -> None:
    frase = case_number.say("SUN482913", insurer="Autos Poblado", language=language)
    assert "Autos Poblado" in frase
    assert "SUN" not in frase
    assert case_number.spell("SUN482913", language=language) in frase


# --- La cola del cierre -------------------------------------------------------


def _cierre(language: Locale) -> str:
    return closing.build(number="SUN482913", insurer="Autos Poblado", language=language)


@pytest.mark.parametrize("language", IDIOMAS)
def test_el_cierre_dice_que_sigue_el_numero_y_se_despide(language: Locale) -> None:
    texto = _cierre(language)
    assert "Autos Poblado" in texto
    esperado = "four" if language == "en" else "cuatro"
    assert esperado in texto


@pytest.mark.parametrize("language", IDIOMAS)
def test_el_cierre_no_arma_el_resumen(language: Locale) -> None:
    """El resumen de tres frases lo trae el grafo, con los valores en claro.
    Armarlo aqui obligaria al canal de voz a descifrar campos del caso, y un
    segundo sitio que descifra es un segundo sitio que puede dejar de redactar."""
    texto = _cierre(language)
    for campo in ("description", "incident_datetime", "location", "injuries"):
        assert campo not in texto


@pytest.mark.parametrize("language", IDIOMAS)
def test_el_cierre_no_termina_preguntando(language: Locale) -> None:
    """El resumen de U11 cierra el bloque pidiendo confirmacion; este cierra la
    llamada. Una llamada que termina preguntando no termina."""
    assert not _cierre(language).rstrip().endswith("?")


@pytest.mark.parametrize("language", IDIOMAS)
def test_la_despedida_no_invita_a_volver_a_llamar(language: Locale) -> None:
    """El enlace publico admite una llamada al dia, asi que ofrecer otra seria
    prometer lo que no se puede cumplir (AC1.23.4)."""
    texto = _cierre(language).lower()
    for prohibida in ("call me anytime", "cualquier cosa me llama", "vuelva a llamar"):
        assert prohibida not in texto


@pytest.mark.parametrize("language", IDIOMAS)
def test_el_cierre_dice_que_sigue_sin_plazo_ni_llamada(language: Locale) -> None:
    """Decision D9: sin plazo y sin llamada saliente. La demo no garantiza el
    primero y no hace la segunda."""
    texto = _cierre(language).lower()
    esperado = "show up on this screen" if language == "en" else "aparece en esta pantalla"
    assert esperado in texto
    for prohibida in ("today", "hoy", "will call you", "le llamamos"):
        assert prohibida not in texto


# --- Dejarlo guardado (2026-10-11) ----------------------------------------------


@pytest.mark.parametrize("language", IDIOMAS)
def test_dejarlo_guardado_dice_hasta_cuando_con_la_ventana_de_la_aseguradora(
    language: Locale,
) -> None:
    from datetime import timedelta

    dicho = closing.build_saved(window=timedelta(seconds=900), language=language)

    assert "15" in dicho
    assert dicho.endswith(copy_api.t(closing.FAREWELL, locale=language))


@pytest.mark.parametrize(("segundos", "esperado"), [(60, "un minuto"), (119, "un minuto")])
def test_un_minuto_se_dice_en_singular_y_nunca_se_redondea_hacia_arriba(
    segundos: int, esperado: str
) -> None:
    from datetime import timedelta

    dicho = closing.build_saved(window=timedelta(seconds=segundos), language="es")

    assert esperado in dicho
    assert "minutos" not in dicho


# --- Como quedo el reporte, dicho al despedirse (US1.17, 2026-10-13) -------------------------


@pytest.mark.parametrize("language", IDIOMAS)
def test_la_despedida_de_un_reporte_registrado_no_necesita_ajustador_y_dice_el_numero(
    language: Locale,
) -> None:
    texto = closing.build_registered(number="SUN482913", insurer="Autos Poblado", language=language)

    assert copy_api.t(closing.REGISTERED, locale=language) in texto
    assert case_number.say("SUN482913", insurer="Autos Poblado", language=language) in texto
    assert texto.endswith(copy_api.t(closing.FAREWELL, locale=language))
    assert "adjuster" in texto.lower() or "ajustador" in texto.lower()  # dice que no lo necesita
    # El enlace no se pronuncia: aparece en la pantalla.
    assert "http" not in texto


@pytest.mark.parametrize("language", IDIOMAS)
def test_la_despedida_pendiente_no_promete_ni_un_cierre_ni_un_ajustador(language: Locale) -> None:
    texto = closing.build_pending(number="SUN482913", insurer="Autos Poblado", language=language)

    assert copy_api.t(closing.PENDING, locale=language) in texto
    assert case_number.say("SUN482913", insurer="Autos Poblado", language=language) in texto
    assert "ajustador" not in texto.lower()
    assert "adjuster" not in texto.lower()
    assert "regist" not in texto.lower()


def test_la_espera_del_resultado_es_corta_porque_es_la_despedida_y_no_el_turno() -> None:
    """Mas de un segundo y medio es silencio al telefono."""
    assert closing.RESULT_WAIT.total_seconds() <= 1.5
    assert 0 < closing.RESULT_POLL_SECONDS < closing.RESULT_WAIT.total_seconds()
