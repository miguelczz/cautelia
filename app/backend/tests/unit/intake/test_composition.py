"""BR3.4, BR3.6, BR4.1: la forma del turno y la emergencia que lo interrumpe."""

from __future__ import annotations

import pytest

from untangle.base import Locale
from untangle.case_record.models import RecordType
from untangle.compliance.controls import api as controls
from untangle.compliance.controls.phrases import EmergencyPhraseMode
from untangle.orchestration.nodes.intake import blocks, composition
from untangle.orchestration.nodes.intake.blocks import Block
from untangle.orchestration.nodes.intake.social import SocialIntent
from untangle.orchestration.nodes.intake.tone import Emotion

# --- BR3.4: una idea, veinticinco palabras ----------------------------------


def test_una_pregunta_corta_no_tiene_problemas() -> None:
    assert composition.assert_question_shape("¿Cuándo ocurrió el accidente?") == ()


def test_mas_de_veinticinco_palabras_es_un_problema() -> None:
    texto = " ".join(["palabra"] * 26)
    problemas = composition.assert_question_shape(texto)
    assert len(problemas) == 1
    assert "25" in problemas[0]


def test_dos_preguntas_en_el_mismo_turno_es_un_problema() -> None:
    texto = "¿Cuándo ocurrió? ¿Y dónde fue?"
    problemas = composition.assert_question_shape(texto)
    assert any("preguntas" in p for p in problemas)


def test_dos_preguntas_en_ingles_tambien_es_un_problema() -> None:
    """P12: la misma regla en los dos idiomas.

    La tanda 2 contaba `?` y `¿` juntos con umbral de dos signos, asi que estas
    dos preguntas pasaban en ingles mientras las mismas dos fallaban en espanol.
    """
    problemas = composition.assert_question_shape("Are you hurt? Where did it happen?")
    assert any("preguntas" in p for p in problemas)


def test_una_pregunta_en_ingles_no_tiene_problemas() -> None:
    assert composition.assert_question_shape("Where did it happen?") == ()


# --- BR3.6: el nombre de pila se pide antes de usarse, solo en ingles -------


def test_en_ingles_se_pide_permiso_para_el_nombre() -> None:
    assert composition.should_ask_name_permission(language="en", first_name="Laura", permitted=None)


def test_en_espanol_no_se_pide_permiso() -> None:
    assert not composition.should_ask_name_permission(
        language="es", first_name="Laura", permitted=None
    )


def test_no_se_vuelve_a_pedir_permiso_ya_concedido() -> None:
    assert not composition.should_ask_name_permission(
        language="en", first_name="Laura", permitted=True
    )


# --- BR4.1: la emergencia rompe el orden, en el mismo turno -----------------


#: La indicacion que produce el control barato de U10 (AC1.6.3). Entra como dato
#: en cada llamada: U11 no la busca ni la elige (FD-U11-3).
INDICACION = controls.emergency_instruction(EmergencyPhraseMode.PUBLIC, language="es")[1]


def test_la_emergencia_reemplaza_la_pregunta_del_bloque_en_curso() -> None:
    """La prueba que aisla BR4.1: con emergencia levantada, no se compone
    ninguna pregunta -- ni siquiera la del bloque que de verdad tocaba."""
    normal = composition.compose_turn(
        emergency_raised=False,
        block=Block.WHAT_HAPPENED,
        missing_field_keys=("description",),
        emotion=None,
        language="es",
    )
    con_emergencia = composition.compose_turn(
        emergency_raised=True,
        emergency_instruction=INDICACION,
        block=Block.WHAT_HAPPENED,
        missing_field_keys=("description",),
        emotion=None,
        language="es",
    )
    assert con_emergencia.text != normal.text
    assert "pasó" not in con_emergencia.text.lower()


def test_el_turno_de_emergencia_dice_que_llame_antes_de_ofrecer_seguir() -> None:
    """AC1.6.1, AC1.6.2 [bloquea]: las dos frases, y la indicacion primero.

    La tanda 2 devolvia solo el ofrecimiento de seguir despues, sin la
    indicacion: un turno que ante "alguien esta sangrando" respondia "podemos
    seguir con su reporte despues" y nada mas.
    """
    turno = composition.compose_turn(
        emergency_raised=True,
        emergency_instruction=INDICACION,
        block=Block.SAFETY,
        missing_field_keys=("injuries",),
        emotion=None,
        language="es",
    )
    continuacion = composition.compose_emergency_continuation(language="es")

    assert INDICACION in turno.text
    assert continuacion in turno.text
    assert turno.text.index(INDICACION) < turno.text.index(continuacion)
    assert turno.key == str(composition.EMERGENCY_CONTINUATION)


def test_sin_la_indicacion_de_u10_el_turno_de_emergencia_no_se_compone() -> None:
    """Fallar ruidosamente: medio turno de emergencia es peor que ninguno."""
    with pytest.raises(ValueError, match=r"AC1\.6\.1"):
        composition.compose_turn(
            emergency_raised=True,
            block=Block.SAFETY,
            missing_field_keys=("injuries",),
            emotion=None,
            language="es",
        )


@pytest.mark.parametrize("language", ["es", "en"])
def test_una_consulta_con_la_pregunta_hecha_promete_la_revision_y_sin_ella_la_pide(
    language: Locale,
) -> None:
    """2026-10-12: «te respondo en un momento» solo se dice si hay algo que revisar."""
    con = composition.compose_turn(
        emergency_raised=False,
        block=Block.FINAL_CONFIRMATION,
        missing_field_keys=(),
        emotion=None,
        language=language,
        record_type=RecordType.COVERAGE_INQUIRY,
        question_known=True,
    )
    sin = composition.compose_turn(
        emergency_raised=False,
        block=Block.FINAL_CONFIRMATION,
        missing_field_keys=(),
        emotion=None,
        language=language,
        record_type=RecordType.COVERAGE_INQUIRY,
        question_known=False,
    )

    assert con.key == str(composition.COVERAGE_CHECKING)
    assert sin.key == str(composition.COVERAGE_ASK_QUESTION)
    assert sin.text.count("?") + sin.text.count("¿") >= 1
    assert sin.text != con.text


def test_una_consulta_cerrada_sin_decir_si_la_pregunta_esta_no_se_compone() -> None:
    """Sin ese dato no se sabe que prometer, y adivinarlo es el defecto que esto arregla."""
    with pytest.raises(ValueError, match="pregunta"):
        composition.compose_turn(
            emergency_raised=False,
            block=Block.FINAL_CONFIRMATION,
            missing_field_keys=(),
            emotion=None,
            language="es",
            record_type=RecordType.COVERAGE_INQUIRY,
        )


def test_la_emergencia_manda_incluso_con_emocion_reconocida() -> None:
    con_emergencia = composition.compose_turn(
        emergency_raised=True,
        emergency_instruction=INDICACION,
        block=Block.SAFETY,
        missing_field_keys=("injuries",),
        emotion=Emotion.FEAR_OR_CRYING,
        language="es",
    )
    assert (
        composition.compose_acknowledgement(Emotion.FEAR_OR_CRYING, language="es")
        not in con_emergencia.text
    )
    assert INDICACION in con_emergencia.text


# --- Lo social y la transicion (decision de Miguel, 2026-10-06) ----------------


def test_cada_bloque_de_campos_tiene_nombre_en_los_dos_idiomas() -> None:

    for bloque in (*blocks.BLOCK_ORDER, *blocks.QUOTE_BLOCK_ORDER):
        for idioma in ("es", "en"):
            nombre = composition.block_label(bloque, language=idioma)
            assert nombre and "{" not in nombre, (bloque, idioma)


def test_el_avance_nombra_lo_que_falta_y_cabe_en_una_idea() -> None:
    avance = composition.Progress(
        done=3, total=7, missing=(Block.WHEN_AND_WHERE, Block.VEHICLE_AND_DRIVER)
    )
    clave, texto = composition.compose_social(SocialIntent.PROGRESS, language="es", progress=avance)
    assert clave == composition.SOCIAL_PROGRESS
    assert "3 de 7" in texto
    assert composition.block_label(Block.WHEN_AND_WHERE, language="es") in texto
    assert composition.count_words(texto) <= composition.MAX_WORDS


def test_el_avance_sin_caso_no_se_inventa() -> None:
    with pytest.raises(ValueError, match="avance"):
        composition.compose_social(SocialIntent.PROGRESS, language="es")


@pytest.mark.parametrize("language", ["es", "en"])
def test_lo_que_falta_para_terminar_nombra_el_bloque_que_toca_en_cada_bloque_de_campos(
    language: Locale,
) -> None:
    """La frase de `intake.unfinished` (2026-10-13): nombra el bloque que se le pasa y hace una
    sola pregunta, para cada bloque de campos de los dos tipos de caso."""
    for bloque in (*blocks.BLOCK_ORDER, *blocks.QUOTE_BLOCK_ORDER):
        clave, texto = composition.compose_unfinished(bloque, language=language)

        assert clave == composition.UNFINISHED
        assert composition.block_label(bloque, language=language) in texto
        assert "{" not in texto
        assert texto.count("?") == 1, (bloque, texto)
    # Distinto bloque, distinta frase: no es una frase fija.
    assert (
        composition.compose_unfinished(Block.SAFETY, language=language)[1]
        != composition.compose_unfinished(Block.WHAT_HAPPENED, language=language)[1]
    )


def test_la_frase_previa_va_delante_o_no_va() -> None:
    assert composition.with_lead_in("Gracias.", "¿Qué pasó?") == "Gracias. ¿Qué pasó?"
    assert composition.with_lead_in(None, "¿Qué pasó?") == "¿Qué pasó?"


@pytest.mark.parametrize("language", ["es", "en"])
@pytest.mark.parametrize("kind", list(composition.FastClosing))
def test_el_cierre_por_voz_no_habla_del_enlace_ni_repite_el_numero(
    kind: composition.FastClosing, language: Locale
) -> None:
    """2026-10-09: en la llamada se decia «puedes verlo con el enlace de arriba» y el
    numero de caso salia tres veces; la despedida de la llamada ya lo dice."""
    _, texto = composition.compose_fast_closing(
        kind,
        case_number="AP-103110",
        language=language,
        missing=(Block.VEHICLE_AND_DRIVER,),
        spoken=True,
    )
    assert "AP-103110" not in texto
    assert "enlace" not in texto
    assert "link" not in texto


#: Lo que dice cada forma de cierre en cada fase (US1.17): el cierre ya no promete un ajustador
#: hasta que las reglas lo deciden.
_SIN_PROMESA = [
    (composition.ClosingPhase.CAPTURING, composition.FastClosing.OFFER),
    (composition.ClosingPhase.CAPTURING, composition.FastClosing.DONE),
    (composition.ClosingPhase.REVIEWING, composition.FastClosing.AFTER_EXTRA),
    (composition.ClosingPhase.REVIEWING, composition.FastClosing.DECLINED),
    (composition.ClosingPhase.REVIEWING, composition.FastClosing.ALREADY),
]


@pytest.mark.parametrize("language", ["es", "en"])
@pytest.mark.parametrize(("phase", "kind"), _SIN_PROMESA)
def test_antes_de_que_las_reglas_decidan_ninguna_frase_promete_un_ajustador(
    phase: composition.ClosingPhase, kind: composition.FastClosing, language: Locale
) -> None:
    _, texto = composition.compose_fast_closing(
        kind,
        case_number="AP-103110",
        language=language,
        missing=(Block.VEHICLE_AND_DRIVER,),
        phase=phase,
    )

    assert "ajustador" not in texto.lower()
    assert "adjuster" not in texto.lower()


@pytest.mark.parametrize("language", ["es", "en"])
@pytest.mark.parametrize(
    "kind",
    # La oferta y el cierre sin oferta solo existen en el turno en que cierra la captura.
    [
        composition.FastClosing.AFTER_EXTRA,
        composition.FastClosing.DECLINED,
        composition.FastClosing.ALREADY,
    ],
)
def test_con_un_ajustador_las_frases_siguen_nombrandolo(
    kind: composition.FastClosing, language: Locale
) -> None:
    _, texto = composition.compose_fast_closing(
        kind,
        case_number="AP-103110",
        language=language,
        phase=composition.ClosingPhase.WITH_ADJUSTER,
    )

    assert "AP-103110" in texto
    assert "ajustador" in texto.lower() or "adjuster" in texto.lower()


@pytest.mark.parametrize("language", ["es", "en"])
@pytest.mark.parametrize("kind", list(composition.FastClosing))
def test_un_caso_cerrado_por_las_reglas_se_dice_registrado_en_cualquier_forma(
    kind: composition.FastClosing, language: Locale
) -> None:
    clave, texto = composition.compose_fast_closing(
        kind,
        case_number="AP-103110",
        language=language,
        phase=composition.ClosingPhase.REGISTERED,
    )

    assert clave == composition.CLOSING_FAST_REGISTERED
    assert "AP-103110" in texto
    assert "regist" in texto.lower()


@pytest.mark.parametrize("language", ["es", "en"])
@pytest.mark.parametrize("phase", list(composition.ClosingPhase))
@pytest.mark.parametrize("kind", list(composition.FastClosing))
def test_el_cierre_por_voz_no_habla_del_enlace_ni_repite_el_numero_en_ninguna_fase(
    kind: composition.FastClosing, phase: composition.ClosingPhase, language: Locale
) -> None:
    _, texto = composition.compose_fast_closing(
        kind,
        case_number="AP-103110",
        language=language,
        missing=(Block.VEHICLE_AND_DRIVER,),
        spoken=True,
        phase=phase,
    )

    assert "AP-103110" not in texto
    assert "enlace" not in texto
    assert "link" not in texto
    assert "ajustador" not in texto.lower()
    assert "adjuster" not in texto.lower()


def test_la_oferta_pregunta_una_sola_cosa_y_nombra_lo_que_falta() -> None:
    _, texto = composition.compose_fast_closing(
        composition.FastClosing.OFFER,
        case_number="AP-103110",
        language="es",
        missing=(Block.VEHICLE_AND_DRIVER, Block.OTHER_PARTIES),
        phase=composition.ClosingPhase.CAPTURING,
    )

    assert texto.count("?") == 1
    for bloque in (Block.VEHICLE_AND_DRIVER, Block.OTHER_PARTIES):
        assert composition.block_label(bloque, language="es") in texto
