"""El fin del habla (BR3.1, PA-6). Ninguna prueba duerme: el reloj entra."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from untangle.voice.turn_detection import (
    DEFAULT_END_OF_SPEECH,
    INCOMPLETE_END_OF_SPEECH,
    MAX_WORD_TO_FINAL,
    SIGNAL_GRACE,
    SIGNAL_ONLY_EXTENSION,
    UNPUNCTUATED_END_OF_SPEECH,
    Ending,
    TurnDetector,
    ending_of,
)

from .dobles import VACIO, final, parcial

INICIO = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)


def _detector() -> TurnDetector:
    return TurnDetector(started_at=INICIO)


def test_sin_nada_no_hay_turno_abierto() -> None:
    d = _detector()
    assert not d.speaking
    assert d.deadline is None
    assert not d.expired(INICIO + timedelta(seconds=10))


def test_un_parcial_no_abre_el_turno() -> None:
    """Un parcial dice que alguien habla, no que termino. Quien lo usa para
    pintar es la consola."""
    d = _detector()
    d.observe(parcial("highway exit"), at=INICIO + timedelta(seconds=1))
    assert not d.speaking
    assert d.deadline is None


def test_un_final_abre_el_plazo_desde_su_llegada() -> None:
    d = _detector()
    llegada = INICIO + timedelta(seconds=1)
    d.observe(final("highway exit twelve"), at=llegada)
    assert d.speaking
    assert d.deadline == llegada + DEFAULT_END_OF_SPEECH


def test_el_plazo_no_vence_antes_de_tiempo() -> None:
    d = _detector()
    llegada = INICIO + timedelta(seconds=1)
    d.observe(final("highway"), at=llegada)
    assert not d.expired(llegada + DEFAULT_END_OF_SPEECH - timedelta(milliseconds=1))
    assert d.expired(llegada + DEFAULT_END_OF_SPEECH)


def test_un_final_nuevo_corre_el_plazo() -> None:
    """Quien sigue hablando no ve su turno cerrado a mitad de frase."""
    d = _detector()
    primero = INICIO + timedelta(seconds=1)
    segundo = INICIO + timedelta(seconds=2)
    d.observe(final("highway"), at=primero)
    d.observe(final("exit twelve"), at=segundo)
    assert d.deadline == segundo + DEFAULT_END_OF_SPEECH


def test_un_parcial_si_cuenta_como_oido_aunque_no_corra_el_plazo() -> None:
    """La escalera de silencios mira `last_heard_at`: quien esta a mitad de frase
    no esta callado, aunque el turno siga abierto hasta su final."""
    d = TurnDetector(started_at=INICIO)
    assert d.last_heard_at is None
    d.observe(parcial("en la"), at=INICIO + timedelta(seconds=4))
    assert d.last_heard_at == INICIO + timedelta(seconds=4)
    assert d.deadline is None
    d.observe(final("en la autopista"), at=INICIO + timedelta(seconds=6))
    assert d.last_heard_at == INICIO + timedelta(seconds=6)
    d.close()
    assert d.last_heard_at is None


def test_un_parcial_tras_un_final_dice_que_la_persona_siguio_hablando() -> None:
    """Visto en una llamada el 2026-10-11: una pausa a media frase y la agente
    respondia encima. Antes un parcial no movia el plazo, y "quiero hablarte...
    referente a mi poliza" se atendia como dos turnos; el primero se entendio como
    pedir una persona y la llamada se cerro."""
    d = _detector()
    llegada = INICIO + timedelta(seconds=1)
    d.observe(final("No."), at=llegada)
    siguio = llegada + timedelta(milliseconds=500)
    d.observe(parcial("la verdad quiero"), at=siguio)

    assert not d.expired(llegada + DEFAULT_END_OF_SPEECH)
    assert d.deadline == siguio + INCOMPLETE_END_OF_SPEECH


def test_al_llegar_el_final_de_lo_que_siguio_el_turno_vuelve_a_su_plazo() -> None:
    d = _detector()
    d.observe(final("No."), at=INICIO)
    d.observe(parcial("la verdad quiero"), at=INICIO + timedelta(milliseconds=400))
    termino = INICIO + timedelta(seconds=2)
    d.observe(final("La verdad quiero preguntar por mi póliza."), at=termino)

    assert d.deadline == termino + DEFAULT_END_OF_SPEECH
    assert d.close().text == "No. La verdad quiero preguntar por mi póliza."


def test_un_parcial_vacio_tras_un_final_no_alarga_el_turno() -> None:
    """El reconocedor manda parciales sin palabras mientras hay silencio: no son
    alguien hablando."""
    d = _detector()
    d.observe(final("No."), at=INICIO)
    d.observe(parcial(""), at=INICIO + timedelta(milliseconds=400))

    assert d.deadline == INICIO + DEFAULT_END_OF_SPEECH


def test_el_ultimo_transcrito_del_turno_es_su_ultimo_final() -> None:
    """La confianza del turno se mira sobre lo que el reconocedor afirmo, no sobre
    un parcial que llego despues."""
    d = _detector()
    afirmado = final("No.")
    d.observe(afirmado, at=INICIO)
    d.observe(parcial("la verdad"), at=INICIO + timedelta(milliseconds=400))

    assert d.close().last is afirmado


def test_la_marca_es_la_del_ultimo_final_y_no_la_del_vencimiento() -> None:
    """BR3.1: el tiempo de esperar el silencio es del detector, no de la
    respuesta. Cargarselo a NFR1 mediria otra cosa."""
    d = _detector()
    llegada = INICIO + timedelta(seconds=1)
    d.observe(final("highway exit twelve"), at=llegada)
    cerrado = d.close()
    assert cerrado.at == llegada
    assert cerrado.at != d.deadline


def test_subir_la_tolerancia_no_empeora_la_marca() -> None:
    """Si la marca fuera la del vencimiento, tocar la tolerancia moveria una meta
    que no se movio. Esta prueba es la que lo impide."""
    llegada = INICIO + timedelta(seconds=1)
    marcas = []
    for tolerancia in (timedelta(milliseconds=300), timedelta(seconds=3)):
        d = TurnDetector(started_at=INICIO, end_of_speech=tolerancia)
        d.observe(final("highway exit twelve"), at=llegada)
        marcas.append(d.close().at)
    assert marcas[0] == marcas[1] == llegada


def test_el_texto_acumula_los_finales_en_orden() -> None:
    d = _detector()
    d.observe(final("highway"), at=INICIO + timedelta(seconds=1))
    d.observe(final("exit twelve"), at=INICIO + timedelta(seconds=2))
    assert d.close().text == "highway exit twelve"


def test_un_final_vacio_no_aporta_texto_pero_si_cierra_el_turno() -> None:
    """Es el caso de BR3.4: llego algo y no se entendio. Distinto de un silencio,
    donde no llego nada."""
    d = _detector()
    llegada = INICIO + timedelta(seconds=1)
    d.observe(VACIO, at=llegada)
    assert d.speaking
    cerrado = d.close()
    assert cerrado.text == ""
    assert cerrado.last is VACIO


def test_publica_la_variante_de_la_ultima_palabra_audible() -> None:
    """AC1.23.5 pide las dos y no la mas favorable."""
    d = TurnDetector(started_at=INICIO, stream_started_at=INICIO)
    llegada = INICIO + timedelta(seconds=5)
    d.observe(final("highway exit twelve", desde=1.0), at=llegada)
    cerrado = d.close()
    assert cerrado.last_audible_word_at is not None
    assert cerrado.last_audible_word_at != cerrado.at
    # La ultima palabra del guion termina en el segundo 2,0 del flujo.
    transcurrido = (cerrado.last_audible_word_at - INICIO).total_seconds()
    assert transcurrido == pytest.approx(2.0)


def test_un_turno_un_minuto_despues_de_abrir_la_llamada_no_cae_en_el_futuro() -> None:
    """Los tiempos de palabra cuentan desde que empezo el flujo de audio de la llamada y
    no desde que empezo el turno: con un solo `listen` por llamada, el reconocedor sigue
    numerando desde el primer trozo. Anclados al turno, cualquier turno que no fuera el
    primero daba una ultima palabra posterior al final que la trajo (2026-10-12)."""
    abre_la_llamada = INICIO
    empieza_el_turno = INICIO + timedelta(seconds=60)
    d = TurnDetector(started_at=empieza_el_turno, stream_started_at=abre_la_llamada)
    # Dice algo que termina en el segundo 62,0 de la llamada; el final llega en el 62,8.
    llegada = INICIO + timedelta(seconds=62.8)
    d.observe(final("highway exit twelve", desde=61.0), at=llegada)

    cerrado = d.close()

    assert cerrado.last_audible_word_at is not None
    assert cerrado.last_audible_word_at < cerrado.at
    assert cerrado.at - cerrado.last_audible_word_at < MAX_WORD_TO_FINAL
    assert (cerrado.last_audible_word_at - abre_la_llamada).total_seconds() == pytest.approx(62.0)


def test_una_palabra_posterior_al_final_que_la_trae_se_descarta() -> None:
    """Imposible: no se publica un numero imposible."""
    d = TurnDetector(started_at=INICIO, stream_started_at=INICIO)
    d.observe(final("highway exit twelve", desde=9.0), at=INICIO + timedelta(seconds=5))
    assert d.close().last_audible_word_at is None


def test_una_palabra_demasiado_anterior_al_final_se_descarta() -> None:
    """Si el flujo no iba en tiempo de pared --una pausa en el envio, una cola
    atrasada--, la cuenta saldria segundos antes de lo que paso."""
    d = TurnDetector(started_at=INICIO, stream_started_at=INICIO)
    llegada = INICIO + timedelta(seconds=30)
    d.observe(final("highway exit twelve", desde=1.0), at=llegada)
    assert llegada - (INICIO + timedelta(seconds=2.0)) > MAX_WORD_TO_FINAL
    assert d.close().last_audible_word_at is None


def test_al_borde_del_margen_todavia_se_publica() -> None:
    d = TurnDetector(started_at=INICIO, stream_started_at=INICIO)
    d.observe(
        final("highway exit twelve", desde=1.0),
        at=INICIO + timedelta(seconds=2) + MAX_WORD_TO_FINAL,
    )
    assert d.close().last_audible_word_at == INICIO + timedelta(seconds=2.0)


def test_sin_el_inicio_del_flujo_la_ultima_palabra_no_se_inventa() -> None:
    d = TurnDetector(started_at=INICIO)
    d.observe(final("highway exit twelve", desde=1.0), at=INICIO + timedelta(seconds=5))
    assert d.close().last_audible_word_at is None


def test_sin_tiempos_de_palabra_la_segunda_variante_es_nula() -> None:
    """Nula y no inventada: el proveedor no siempre los manda."""
    d = _detector()
    d.observe(VACIO, at=INICIO + timedelta(seconds=1))
    assert d.close().last_audible_word_at is None


def test_cerrar_sin_turno_abierto_falla() -> None:
    """Un turno vacio con la hora de ahora es un dato inventado."""
    with pytest.raises(ValueError, match="turno abierto"):
        _detector().close()


def test_cerrar_deja_el_detector_listo_para_el_siguiente() -> None:
    d = _detector()
    d.observe(final("highway"), at=INICIO + timedelta(seconds=1))
    d.close()
    assert not d.speaking
    assert d.deadline is None
    d.observe(final("exit twelve"), at=INICIO + timedelta(seconds=5))
    assert d.close().text == "exit twelve"


def test_una_frase_a_medias_espera_mas_antes_de_cerrar_el_turno() -> None:
    """2026-10-09: «mi poliza es» y una pausa para pensar el numero cortaba el turno
    ahi, y el numero llegaba solo como otro turno."""
    from untangle.voice.turn_detection import INCOMPLETE_END_OF_SPEECH

    d = _detector()
    d.observe(final("mi póliza es"), at=INICIO)

    assert not d.expired(INICIO + DEFAULT_END_OF_SPEECH + timedelta(milliseconds=50))
    assert d.expired(INICIO + INCOMPLETE_END_OF_SPEECH)


def test_una_frase_acabada_cierra_con_la_tolerancia_de_siempre() -> None:
    d = _detector()
    d.observe(final("nadie se lastimó"), at=INICIO)

    assert d.expired(INICIO + DEFAULT_END_OF_SPEECH)


# --- La puntuacion del reconocedor dice si la frase termino (2026-10-11) ------------


@pytest.mark.parametrize(
    "sin_cierre",
    [
        "El vehículo que yo iba conduciendo",
        "Hola, Catalina. No, la verdad quiero hablarte",
        "I was driving on the highway when a truck",
        "Iba por la autopista sur cuando una moto,",
    ],
)
def test_una_frase_larga_sin_su_punto_espera_la_intermedia(sin_cierre: str) -> None:
    """Las dos primeras son de una llamada real: la agente contesto encima.

    Cambia a proposito la prueba de 2026-10-11, que esperaba el mismo plazo largo que una
    frase a medias: ahora son dos esperas distintas, y esta es la intermedia (2026-10-12).
    """
    d = _detector()
    d.observe(final(sin_cierre), at=INICIO)

    assert not d.expired(INICIO + UNPUNCTUATED_END_OF_SPEECH - timedelta(milliseconds=1))
    assert d.expired(INICIO + UNPUNCTUATED_END_OF_SPEECH)


@pytest.mark.parametrize(
    "terminada",
    [
        "Hace poco, alrededor de las 11 am.",
        "¿Mi póliza cubre esto?",
        "Nobody was hurt, thankfully.",
        # Una respuesta corta no espera de mas aunque llegue sin punto.
        "no",
        "sí claro",
        "ayer en la tarde",
    ],
)
def test_una_frase_terminada_o_una_respuesta_corta_no_espera_de_mas(terminada: str) -> None:
    d = _detector()
    d.observe(final(terminada), at=INICIO)

    assert d.expired(INICIO + DEFAULT_END_OF_SPEECH)


# --- Tres esperas, segun como termino la frase (2026-10-12) -------------------------


def test_las_tres_esperas_son_distintas_y_van_de_la_corta_a_la_larga() -> None:
    assert DEFAULT_END_OF_SPEECH < UNPUNCTUATED_END_OF_SPEECH < INCOMPLETE_END_OF_SPEECH


@pytest.mark.parametrize(
    "texto",
    [
        # El caso real: cuatro palabras, termina en preposicion, y el turno se cerro a los
        # 0,7 s en plena pausa de 1,3 s.
        "Hola, quería consultar sobre",
        # Menos de cinco palabras y sin punto, pero a medias: nunca es una respuesta corta.
        "sobre",
        "con una",
        "mi póliza es",
        "quería consultar sobre",
        "fue por",
        "y",
        "no sé si",
        "pero",
        "porque",
        "cuando",
        # Con puntuacion pegada a la palabra, o con coma.
        "Iba por la autopista y,",
        "Quiero hablar de...",
        "¿Mi póliza cubre un choque con?",
        # Y con mas de cuatro palabras.
        "Hola, buenas tardes, quería consultar sobre",
        # Ingles.
        "I wanted to ask about",
        "my policy is",
        "it was a",
        "I was hit by",
        "that\u2019s",
        "I'm",
        "because of",
        "Hi, I wanted to talk about",
        "and",
    ],
)
def test_una_frase_que_termina_en_una_palabra_de_continuacion_espera_la_larga(
    texto: str,
) -> None:
    assert ending_of(texto) is Ending.INCOMPLETE

    d = _detector()
    d.observe(final(texto), at=INICIO)
    assert not d.expired(INICIO + INCOMPLETE_END_OF_SPEECH - timedelta(milliseconds=1))
    assert d.expired(INICIO + INCOMPLETE_END_OF_SPEECH)


@pytest.mark.parametrize(
    "texto",
    [
        "El vehículo que yo iba conduciendo",
        "I was driving on the highway when a truck",
        "Hace poco alrededor de las once",
        "Iba por la autopista sur cuando una moto,",
    ],
)
def test_una_frase_larga_que_el_reconocedor_no_cerro_espera_la_intermedia(texto: str) -> None:
    assert ending_of(texto) is Ending.UNPUNCTUATED


@pytest.mark.parametrize(
    "texto",
    [
        # Las respuestas cortas legitimas siguen rapidas, lleguen con punto o sin el.
        "no",
        "No.",
        "sí",
        "Sí.",
        "sí claro",
        "ayer en la tarde",
        "yes",
        "no, nobody was hurt",
        # "si" a secas es una respuesta: el reconocedor no siempre pone la tilde.
        "si",
        "Si.",
        # Cerradas por el reconocedor.
        "Hace poco, alrededor de las 11 am.",
        "¿Mi póliza cubre esto?",
        "Nobody was hurt, thankfully.",
        "Iba por la autopista sur cuando una moto me chocó.",
        "¡Me chocaron!",
        # Sin nada que esperar.
        "",
        "   ",
    ],
)
def test_una_respuesta_corta_o_una_frase_cerrada_espera_la_corta(texto: str) -> None:
    assert ending_of(texto) is Ending.CLOSED

    d = _detector()
    d.observe(final(texto), at=INICIO)
    if texto.strip():
        assert d.deadline == INICIO + DEFAULT_END_OF_SPEECH


def test_el_si_con_tilde_y_el_no_no_piden_continuacion_pero_el_si_condicional_si() -> None:
    """«sí» y «no» solos son respuestas completas; «si» condicional deja la frase abierta."""
    assert ending_of("creo que sí") is Ending.CLOSED
    assert ending_of("claro que no") is Ending.CLOSED
    assert ending_of("no sé si") is Ending.INCOMPLETE
    assert ending_of("avíseme si") is Ending.INCOMPLETE


def test_solo_cuenta_el_ultimo_final_para_decidir_cuanto_esperar() -> None:
    d = _detector()
    d.observe(final("Hola, quería consultar sobre"), at=INICIO)
    d.observe(final("si mi póliza cubre un choque."), at=INICIO + timedelta(seconds=3))

    assert d.deadline == INICIO + timedelta(seconds=3) + DEFAULT_END_OF_SPEECH


def test_la_pausa_a_mitad_de_frase_del_caso_real_no_cierra_el_turno() -> None:
    """2026-10-12, llamada simulada: «Hola, quería consultar sobre», una pausa de 1,3 s y
    «si mi póliza me cubre un choque con una moto». El turno se cerraba a los 0,7 s y la
    agente contestaba a la mitad (una pregunta de heridos que nadie habia pedido)."""
    d = _detector()
    llego = INICIO + timedelta(seconds=12.98)
    d.observe(final("Hola, quería consultar sobre"), at=llego)

    # La persona retoma 1,3 s despues de callar, y su parcial llega unas decimas despues.
    pausa = llego + timedelta(seconds=1.65)
    assert not d.expired(pausa), "el turno se cerro en plena pausa"
    d.observe(parcial("si mi póliza me cubre"), at=pausa)
    assert not d.expired(pausa + timedelta(seconds=1))
    termino = pausa + timedelta(seconds=2.5)
    d.observe(final("si mi póliza me cubre un choque con una moto."), at=termino)

    assert d.deadline == termino + DEFAULT_END_OF_SPEECH
    assert d.close().text == (
        "Hola, quería consultar sobre si mi póliza me cubre un choque con una moto."
    )


def test_las_tres_esperas_son_datos_que_entran_por_argumento() -> None:
    """Quien prueba el ritmo sin reloj las pone en cero, y quien configura una aseguradora
    las cambia sin tocar el detector."""
    cero = timedelta(0)
    d = TurnDetector(
        started_at=INICIO,
        end_of_speech=cero,
        unpunctuated_end_of_speech=cero,
        incomplete_end_of_speech=cero,
    )
    for texto in ("no", "El vehículo que yo iba conduciendo", "mi póliza es"):
        d.observe(final(texto), at=INICIO)
        assert d.expired(INICIO)
        d.close()

    largas = TurnDetector(
        started_at=INICIO,
        end_of_speech=timedelta(seconds=1),
        unpunctuated_end_of_speech=timedelta(seconds=2),
        incomplete_end_of_speech=timedelta(seconds=3),
    )
    esperas = []
    for texto in ("no", "El vehículo que yo iba conduciendo", "mi póliza es"):
        largas.observe(final(texto), at=INICIO)
        esperas.append((largas.deadline - INICIO).total_seconds() if largas.deadline else None)
        largas.close()
    assert esperas == [1, 2, 3]


# --- La senal de voz del reconocedor (2026-10-12) -----------------------------------
#
# Los parciales del proveedor llegan una vez por segundo de audio; la senal de que alguien
# empezo a hablar llega en decimas. Sin ella, el plazo de un final vencia antes de que se
# supiera que la persona seguia.


def _s(segundos: float) -> timedelta:
    return timedelta(seconds=segundos)


def test_el_caso_real_la_senal_aplaza_el_cierre_aunque_el_parcial_llegue_tarde() -> None:
    """«Hola, quería consultar sobre» (final a los 13,15 s), una pausa de 1,7 s, y la
    persona retoma: la senal llega 0,3 s despues, y los parciales, uno por segundo de audio
    con su latencia. Sin senal el primer parcial llega a los 2,9 s, cuando el turno ya se
    cerro a los 2,5 s con la persona hablando."""
    llego = INICIO + _s(13.15)
    retoma = llego + _s(1.7)

    sin_senal = _detector()
    sin_senal.observe(final("Hola, quería consultar sobre"), at=llego)
    assert sin_senal.expired(llego + INCOMPLETE_END_OF_SPEECH), "el caso ya no es el real"

    d = _detector()
    d.observe(final("Hola, quería consultar sobre"), at=llego)
    d.speech_started(retoma + _s(0.3))
    assert not d.expired(llego + INCOMPLETE_END_OF_SPEECH)
    assert not d.expired(llego + INCOMPLETE_END_OF_SPEECH + _s(0.4))

    parcial_1 = retoma + _s(1.2)
    d.observe(parcial("si mi póliza me cubre"), at=parcial_1)
    assert d.deadline == parcial_1 + INCOMPLETE_END_OF_SPEECH
    d.observe(parcial("si mi póliza me cubre un choque con"), at=parcial_1 + _s(1.0))
    d.observe(parcial("si mi póliza me cubre un choque con una moto"), at=parcial_1 + _s(2.0))
    assert not d.expired(parcial_1 + _s(2.0) + _s(2.4))

    termino = parcial_1 + _s(2.3)
    d.observe(final("si mi póliza me cubre un choque con una moto."), at=termino)
    assert d.deadline == termino + DEFAULT_END_OF_SPEECH
    assert d.close().text == (
        "Hola, quería consultar sobre si mi póliza me cubre un choque con una moto."
    )


def test_la_senal_sola_mantiene_abierto_el_turno_solo_la_espera_corta() -> None:
    """Un «No.» cierra a los 0,7 s; si el reconocedor avisa de voz a los 0,4, el turno espera
    `SIGNAL_GRACE` desde la senal a que llegue un parcial con palabras, y no la espera mas
    larga de antes (2026-10-13: una tos costaba 2,5 s)."""
    d = _detector()
    d.observe(final("No."), at=INICIO)
    assert d.deadline == INICIO + DEFAULT_END_OF_SPEECH

    d.speech_started(INICIO + _s(0.4))

    assert d.deadline == INICIO + _s(0.4) + SIGNAL_GRACE
    assert d.deadline < INICIO + _s(0.4) + INCOMPLETE_END_OF_SPEECH


def test_la_senal_no_acorta_el_plazo_cuando_el_normal_ya_es_mas_largo() -> None:
    """Una frase a medias espera 2,5 s: una senal a los 0,4 s no puede adelantar ese cierre."""
    d = _detector()
    d.observe(final("mi póliza es"), at=INICIO)

    d.speech_started(INICIO + _s(0.4))

    assert d.deadline == INICIO + INCOMPLETE_END_OF_SPEECH


def test_un_ruido_tras_la_senal_no_deja_el_turno_colgado() -> None:
    """Si despues de la senal no llega ni una palabra, nada renueva el plazo: vence solo, a
    `SIGNAL_GRACE` de la senal, y el turno se cierra con lo que habia."""
    d = _detector()
    d.observe(final("No."), at=INICIO)
    d.speech_started(INICIO + _s(0.4))
    d.observe(parcial(""), at=INICIO + _s(1.4))  # un parcial sin palabras no es hablar

    vence = INICIO + _s(0.4) + SIGNAL_GRACE
    assert not d.expired(vence - timedelta(milliseconds=1))
    assert d.expired(vence)
    assert d.close().text == "No."


def test_una_senal_mas_reciente_corre_el_plazo_de_la_espera_corta() -> None:
    d = _detector()
    d.observe(final("No."), at=INICIO)
    d.speech_started(INICIO + _s(0.4))
    d.speech_started(INICIO + _s(1.0))

    assert d.deadline == INICIO + _s(1.0) + SIGNAL_GRACE


def test_el_parcial_con_palabras_tras_la_senal_manda_con_la_espera_larga_de_siempre() -> None:
    """La senal solo era una pista: con palabras, la persona retomo de verdad y el plazo es el
    de un parcial con palabras, sin el tope de las senales."""
    d = _detector()
    d.observe(final("No."), at=INICIO)
    d.speech_started(INICIO + _s(0.4))
    parcial_a = INICIO + _s(1.3)
    d.observe(parcial("la verdad quiero"), at=parcial_a)

    assert d.deadline == parcial_a + INCOMPLETE_END_OF_SPEECH
    assert d.deadline > INICIO + DEFAULT_END_OF_SPEECH + SIGNAL_ONLY_EXTENSION


def test_la_senal_sin_turno_abierto_no_abre_ninguno_ni_cuenta_como_oido() -> None:
    """Solo un final abre un turno. Una senal suelta puede ser el eco de la propia agente
    o un ruido: no es alguien que no este callado para la escalera de silencios."""
    d = _detector()
    d.speech_started(INICIO + _s(1))

    assert not d.speaking
    assert d.deadline is None
    assert d.last_heard_at is None
    d.observe(final("No."), at=INICIO + _s(2))
    assert d.deadline == INICIO + _s(2) + DEFAULT_END_OF_SPEECH


def test_un_final_tras_la_senal_devuelve_el_turno_a_su_plazo() -> None:
    d = _detector()
    d.observe(final("No."), at=INICIO)
    d.speech_started(INICIO + _s(1))
    termino = INICIO + _s(3)
    d.observe(final("La verdad quiero preguntar por mi póliza."), at=termino)

    assert d.deadline == termino + DEFAULT_END_OF_SPEECH
    assert d.close().text == "No. La verdad quiero preguntar por mi póliza."


def test_la_senal_sola_no_cuenta_como_oido_ni_con_el_turno_abierto() -> None:
    """2026-10-13: `last_heard_at` dice que alguien esta hablando --la escalera de silencios lo
    lee para no preguntar «¿sigue ahi?» a quien habla--, y una senal sin palabras no lo dice:
    puede ser una tos, la musica o el teclado. Hasta hoy contaba aqui; no cambia nada que se
    vea (con el turno abierto la escalera no se consulta), pero deja de mentir."""
    d = _detector()
    d.observe(final("No."), at=INICIO)
    d.speech_started(INICIO + _s(0.4))

    assert d.last_heard_at == INICIO

    d.observe(parcial("la verdad"), at=INICIO + _s(0.9))
    assert d.last_heard_at == INICIO + _s(0.9)


# --- Una senal sin palabras no pesa como la persona retomando la frase (2026-10-13) --------
#
# Visto en dos llamadas reales desde un portatil sin audifonos: el turno se cerraba 3,4 y 5,3 s
# despues del ultimo final, y en la de ingles nunca se cerro. La senal es deteccion de voz por
# energia y la disparan tambien una tos, el teclado, la musica o el eco de la sala.


def _cierre_con_ruido(d: TurnDetector, cada: float, desde: float, paso: float = 0.05) -> float:
    """Simula la llamada: el reloj avanza de `paso` en `paso` y una senal sin palabras llega
    cada `cada` segundos; devuelve el segundo, desde el inicio, en que el turno vence."""
    t = 0.0
    proxima = desde
    while not d.expired(INICIO + _s(t)):
        if t >= proxima:
            d.speech_started(INICIO + _s(t))
            proxima = t + cada
        t += paso
        assert t < 60, "el turno no vencio nunca: el ruido lo deja abierto sin limite"
    return t


@pytest.mark.parametrize(
    ("frase", "normal"),
    [
        ("No.", DEFAULT_END_OF_SPEECH),
        ("El vehículo que yo iba conduciendo", UNPUNCTUATED_END_OF_SPEECH),
        ("mi póliza es", INCOMPLETE_END_OF_SPEECH),
    ],
)
def test_ruido_repetido_no_mantiene_el_turno_abierto_mas_alla_del_tope(
    frase: str, normal: timedelta
) -> None:
    """Una senal cada segundo y medio dejaba el turno abierto sin limite. Ahora vence, como
    mucho, `SIGNAL_ONLY_EXTENSION` despues de su plazo normal."""
    d = _detector()
    d.observe(final(frase), at=INICIO)

    cierra_a = _cierre_con_ruido(d, cada=1.0, desde=0.2)

    tope = (normal + SIGNAL_ONLY_EXTENSION).total_seconds()
    assert cierra_a == pytest.approx(tope, abs=0.06)
    cerrado = d.close()
    assert cerrado.unconfirmed_signals >= 1
    assert cerrado.held_by_signals <= SIGNAL_ONLY_EXTENSION


def test_un_ruido_suelto_cuesta_la_espera_corta_y_no_la_larga() -> None:
    """El caso comun: tras un «No.» entra un ruido a los 0,3 s. Antes el turno se cerraba a los
    2,8 s (la senal mas 2,5 s); ahora a los 1,8 s (la senal mas 1,5 s)."""
    d = _detector()
    d.observe(final("No."), at=INICIO)

    cierra_a = _cierre_con_ruido(d, cada=60, desde=0.3)

    assert cierra_a == pytest.approx(0.3 + SIGNAL_GRACE.total_seconds(), abs=0.06)
    assert cierra_a < 0.3 + INCOMPLETE_END_OF_SPEECH.total_seconds() - 0.9


def test_el_parcial_que_tarda_casi_un_segundo_tras_la_senal_todavia_llega_a_tiempo() -> None:
    """La razon de `SIGNAL_GRACE`: el parcial del reconocedor sale hasta un segundo de audio
    despues de la senal (0,9 s medido el 2026-10-12). Con la senal en el ultimo instante del
    plazo normal, el turno sigue abierto cuando llega, y desde ahi vale la espera larga."""
    d = _detector()
    d.observe(final("Hola, quería consultar sobre"), at=INICIO)
    senal_a = INICIO + INCOMPLETE_END_OF_SPEECH - _s(0.1)
    d.speech_started(senal_a)

    llega = senal_a + _s(1.0)
    assert not d.expired(llega), "el turno se cerro antes de que llegara el parcial"
    d.observe(parcial("si mi póliza me cubre"), at=llega)

    assert d.deadline == llega + INCOMPLETE_END_OF_SPEECH
    assert SIGNAL_GRACE > _s(1.0), "por debajo de un segundo se contestaria encima de quien retoma"


def test_la_pausa_dentro_de_la_frase_retomada_tambien_espera_su_parcial() -> None:
    """Ya habia palabras tras el final (plazo largo desde el parcial) y la persona hace otra
    pausa: la senal que anuncia que retoma parte de ese plazo y no del primer final, o el tope
    la dejaria sin espera."""
    d = _detector()
    d.observe(final("Hola, quería consultar sobre"), at=INICIO)
    primero = INICIO + _s(3.0)
    d.observe(parcial("si mi póliza"), at=primero)
    base = primero + INCOMPLETE_END_OF_SPEECH

    senal_a = base - _s(0.3)
    d.speech_started(senal_a)

    assert d.deadline == senal_a + SIGNAL_GRACE
    assert d.deadline > base


def test_las_senales_sin_palabras_se_cuentan_al_cerrar_el_turno() -> None:
    d = _detector()
    d.observe(final("No."), at=INICIO)
    d.speech_started(INICIO + _s(0.2))
    d.speech_started(INICIO + _s(0.9))

    cerrado = d.close()

    assert cerrado.unconfirmed_signals == 2
    assert cerrado.held_by_signals == (_s(0.9) + SIGNAL_GRACE) - DEFAULT_END_OF_SPEECH
    # El detector queda limpio para el siguiente turno.
    d.observe(final("Sí."), at=INICIO + _s(5))
    siguiente = d.close()
    assert siguiente.unconfirmed_signals == 0
    assert siguiente.held_by_signals == timedelta(0)


def test_una_senal_que_la_siguen_palabras_no_es_ruido() -> None:
    """Un parcial con palabras o un final despues de la senal la confirman: era la persona."""
    con_parcial = _detector()
    con_parcial.observe(final("No."), at=INICIO)
    con_parcial.speech_started(INICIO + _s(0.3))
    con_parcial.observe(parcial("la verdad"), at=INICIO + _s(1.0))
    assert con_parcial.close().unconfirmed_signals == 0

    con_final = _detector()
    con_final.observe(final("No."), at=INICIO)
    con_final.speech_started(INICIO + _s(0.3))
    con_final.observe(final("Pero sí hubo un herido."), at=INICIO + _s(1.2))
    cerrado = con_final.close()
    assert cerrado.unconfirmed_signals == 0
    assert cerrado.held_by_signals == timedelta(0)


def test_un_final_vacio_tras_la_senal_la_deja_como_ruido_y_acaba_su_espera() -> None:
    """El reconocedor oyo algo y no saco palabras: es exactamente lo que es un ruido. El
    plazo vuelve al normal, contado desde ese final."""
    d = _detector()
    d.observe(final("No."), at=INICIO)
    d.speech_started(INICIO + _s(0.3))
    vacio_a = INICIO + _s(0.9)
    d.observe(VACIO, at=vacio_a)

    assert d.deadline == vacio_a + DEFAULT_END_OF_SPEECH
    assert d.close().unconfirmed_signals == 1


def test_la_senal_sola_no_cuenta_como_retomar() -> None:
    """Quien mira `resumed` para soltar una lectura que cuesta dinero espera palabras."""
    d = _detector()
    d.observe(final("Tuve un choque."), at=INICIO)
    d.speech_started(INICIO + _s(0.3))

    assert not _retomo(d)
    d.observe(parcial("y"), at=INICIO + _s(1.0))
    assert _retomo(d)


def test_las_esperas_de_la_senal_son_datos_que_entran_por_argumento() -> None:
    d = TurnDetector(
        started_at=INICIO, signal_grace=timedelta(seconds=10), signal_only_extension=timedelta(0)
    )
    d.observe(final("No."), at=INICIO)
    d.speech_started(INICIO + _s(0.3))

    # Sin extension permitida, la senal no mueve nada.
    assert d.deadline == INICIO + DEFAULT_END_OF_SPEECH


# --- Lo que la llamada mira para adelantar la lectura del modelo (2026-10-13) -----------
#
# `pending_end` entrega el turno tal como `close` lo entregaria, sin cerrarlo; `ending` y
# `resumed` dicen si vale la pena leerlo ya y si la persona retomo la palabra.


def test_sin_turno_abierto_no_hay_turno_pendiente() -> None:
    d = _detector()
    assert d.pending_end() is None
    d.observe(parcial("highway exit"), at=INICIO)
    assert d.pending_end() is None


def test_el_turno_pendiente_es_el_que_close_entregaria_y_no_cierra_nada() -> None:
    d = _detector()
    llegada = INICIO + _s(1)
    d.observe(final("Hola, quería reportar un choque."), at=llegada)

    pendiente = d.pending_end()

    assert pendiente is not None
    assert pendiente.text == "Hola, quería reportar un choque."
    assert pendiente.at == llegada
    assert d.speaking, "mirar el turno no lo cierra"
    assert d.close() == pendiente


def test_el_turno_pendiente_junta_los_finales_y_toma_la_hora_del_ultimo() -> None:
    d = _detector()
    d.observe(final("Mi placa es ABC123."), at=INICIO)
    d.observe(parcial("y"), at=INICIO + _s(0.3))
    ultimo = INICIO + _s(1)
    d.observe(final("Y fue ayer."), at=ultimo)

    pendiente = d.pending_end()

    assert pendiente is not None
    assert pendiente.text == "Mi placa es ABC123. Y fue ayer."
    assert pendiente.at == ultimo


def test_ending_dice_como_termino_lo_ultimo_dicho() -> None:
    cerrada = _detector()
    cerrada.observe(final("Tuve un choque ayer."), at=INICIO)
    assert cerrada.ending is Ending.CLOSED

    a_medias = _detector()
    a_medias.observe(final("Tuve un choque ayer."), at=INICIO)
    a_medias.observe(final("mi poliza es"), at=INICIO + _s(1))
    assert a_medias.ending is Ending.INCOMPLETE


def _retomo(d: TurnDetector) -> bool:
    """`resumed` por una funcion: el comprobador de tipos no estrecha un valor tras otro assert."""
    return d.resumed


def test_retomar_la_palabra_se_ve_con_un_parcial_con_palabras_y_se_apaga_con_el_final() -> None:
    d = _detector()
    assert not _retomo(d)
    d.observe(final("Tuve un choque."), at=INICIO)
    assert not _retomo(d)

    d.observe(parcial("y"), at=INICIO + _s(0.3))
    assert _retomo(d)

    d.observe(final("Y fue ayer."), at=INICIO + _s(1.4))
    assert not _retomo(d)


def test_la_senal_de_voz_no_cuenta_como_retomar_ni_con_turno_ni_sin_el() -> None:
    """Cambia a proposito la prueba de 2026-10-12, que esperaba retomar con la senal y el turno
    abierto: una senal sin palabras puede ser un ruido (2026-10-13)."""
    d = _detector()
    d.speech_started(INICIO)
    assert not _retomo(d)

    d.observe(final("Tuve un choque."), at=INICIO + _s(1))
    d.speech_started(INICIO + _s(1.3))
    assert not _retomo(d)


def test_un_parcial_sin_palabras_no_cuenta_como_retomar() -> None:
    d = _detector()
    d.observe(final("Tuve un choque."), at=INICIO)
    d.observe(parcial(""), at=INICIO + _s(0.3))
    assert not _retomo(d)
