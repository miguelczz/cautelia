"""BR5.2 a BR5.4: emocion, insultos y registro prohibido."""

from __future__ import annotations

from untangle.orchestration.nodes.intake import tone

# --- BR5.2: reconocimiento -----------------------------------------------


def test_llanto_se_reconoce_antes_que_enojo() -> None:
    texto = "(llorando) Estoy muy asustada, el carro venia muy rapido."
    assert tone.detect_emotion(texto, language="es") is tone.Emotion.FEAR_OR_CRYING


def test_insulto_se_lee_como_enojo() -> None:
    texto = "Ustedes son unos inutiles, esto es un robo."
    assert tone.detect_emotion(texto, language="es") is tone.Emotion.ANGER


def test_texto_neutro_no_dispara_ninguna_senal() -> None:
    texto = "Mi carro es un Mazda 3 gris, placa ABC123."
    assert tone.detect_emotion(texto, language="es") is None


def test_reconoce_en_ingles() -> None:
    texto = "(crying) I'm really scared, the car was going so fast."
    assert tone.detect_emotion(texto, language="en") is tone.Emotion.FEAR_OR_CRYING


# --- BR5.4: el contador de insultos, recalculado y no llevado -------------


def test_contar_insultos_no_depende_de_un_contador_propio() -> None:
    """La prueba que aisla BR5.4: mismo historial, dos llamadas, el mismo numero."""
    historial = (
        "Esto es una porqueria, ustedes son unos inutiles.",
        "Ya les dije que son unos incompetentes.",
        "Mi carro es un Mazda 3 gris.",
    )
    primera = tone.count_insults(historial, language="es")
    segunda = tone.count_insults(historial, language="es")
    assert primera == segunda == 2


def test_un_turno_sin_insulto_no_cuenta() -> None:
    assert tone.count_insults(("Mi carro es un Mazda 3 gris.",), language="es") == 0


# --- BR5.3: registro prohibido de la agente -------------------------------


def test_frase_que_culpa_es_registro_prohibido() -> None:
    assert (
        tone.forbidden_register_violation("Usted no debio estacionar ahi.", language="es") == "IR-1"
    )


def test_trato_informal_es_registro_prohibido() -> None:
    assert (
        tone.forbidden_register_violation("Listo mija, ya quedo anotado.", language="es") == "IR-3"
    )


def test_dos_diminutivos_son_registro_prohibido() -> None:
    resultado = tone.forbidden_register_violation(
        "Un momentico, le hago una preguntica.", language="es"
    )
    assert resultado == "IR-DIMINUTIVES"


def test_un_solo_diminutivo_no_es_registro_prohibido() -> None:
    assert (
        tone.forbidden_register_violation("Espere un momentico, por favor.", language="es") is None
    )


def test_turno_limpio_no_tiene_violacion() -> None:
    assert (
        tone.forbidden_register_violation(
            "Entiendo. ¿En que fecha ocurrio el accidente?", language="es"
        )
        is None
    )


def test_el_registro_prohibido_se_mide_sobre_el_texto_plegado() -> None:
    """BR5.3, AC1.13.4: "¿qué más?" es la forma que el criterio nombra.

    La tanda 2 comparaba los patrones contra el texto crudo mientras el archivo
    declaraba en su encabezado que se comparan plegados: "¿que mas?" coincidia y
    "¿qué más?" --con tildes, que es como se escribe-- no.
    """
    assert tone.forbidden_register_violation("Hola, ¿qué más?", language="es") == "IR-3"
    assert tone.forbidden_register_violation("Hola, ¿que mas?", language="es") == "IR-3"
