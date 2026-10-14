"""La propia voz de la agente no cuenta como la de la persona (2026-10-13).

Pedido de Miguel: que la agente no se escuche a si misma «de ninguna manera», con o sin
audifonos. Lo que se prueba aqui es la pieza que lo decide; que el ciclo de la llamada la
use esta en `tests/integration/u16/test_call_loop.py`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from untangle.providers.ports import ExternalText, Transcript, WordHypothesis
from untangle.voice import own_voice
from untangle.voice.own_voice import OwnVoice

#: Cuando llego el primer trozo de audio de la llamada: el segundo cero del reconocedor.
INICIO = datetime(2026, 10, 13, 9, 0, tzinfo=UTC)
PREGUNTA = "Gracias por contarme. ¿Hubo alguien herido en el accidente?"


def _a(segundos: float) -> datetime:
    return INICIO + timedelta(seconds=segundos)


def _oido(texto: str, *, desde: float, final: bool = True, paso: float = 0.35) -> Transcript:
    """Un transcrito cuyas palabras empiezan en `desde` segundos de audio."""
    palabras = tuple(
        WordHypothesis(
            text=ExternalText(palabra),
            start_s=desde + i * paso,
            end_s=desde + i * paso + 0.3,
            confidence=0.9,
        )
        for i, palabra in enumerate(texto.split())
    )
    return Transcript(text=ExternalText(texto), is_final=final, words=palabras)


def _sonando(texto: str = PREGUNTA, *, de: float = 10.0, a: float | None = 14.0) -> OwnVoice:
    voz = OwnVoice()
    dicho = voz.begin(texto, starts_at=_a(de))
    dicho.ends_at = None if a is None else _a(a)
    return voz


def _quitar(voz: OwnVoice, oido: Transcript, *, llego: float) -> Transcript | None:
    return voz.strip(oido, heard_at=_a(llego), stream_started_at=INICIO)


# --- El eco se quita ------------------------------------------------------------------


def test_lo_que_la_agente_dice_y_vuelve_por_el_microfono_no_es_de_la_persona() -> None:
    voz = _sonando()

    assert (
        _quitar(voz, _oido("hubo alguien herido en el accidente", desde=11.5), llego=13.8) is None
    )


def test_un_parcial_del_eco_tampoco_pasa_aunque_la_frase_se_siga_enviando() -> None:
    # Mientras se envia no se sabe cuando termina de sonar: la frase sigue abierta.
    voz = _sonando(a=None)

    assert _quitar(voz, _oido("gracias por", desde=10.2, final=False), llego=10.9) is None
    assert _quitar(voz, _oido("gracias", desde=10.2, final=False), llego=10.6) is None


def test_el_eco_mal_oido_sigue_siendo_eco() -> None:
    voz = _sonando()

    # «erido» por «herido», «acidente» por «accidente»: lo que entrega un altavoz de portatil.
    assert _quitar(voz, _oido("hubo alguien erido en el acidente", desde=11.5), llego=13.9) is None


def test_la_cola_del_eco_cae_un_poco_despues_del_final_estimado() -> None:
    # El final es una estimacion por bytes enviados: el navegador suena algo despues.
    voz = _sonando()

    assert _quitar(voz, _oido("el accidente", desde=14.0 + 0.5), llego=15.2) is None


def test_un_eco_que_cruza_dos_frases_seguidas_se_reconoce() -> None:
    voz = OwnVoice()
    voz.begin("Listo, ya lo anoté.", starts_at=_a(10.0)).ends_at = _a(11.5)
    voz.begin("¿Dónde ocurrió?", starts_at=_a(11.5)).ends_at = _a(12.8)

    assert _quitar(voz, _oido("ya lo anoté dónde ocurrió", desde=10.6), llego=13.0) is None


def test_sin_tiempos_por_palabra_decide_la_hora_a_la_que_llego() -> None:
    voz = _sonando()
    sin_tiempos = Transcript(text=ExternalText("hubo alguien herido"), is_final=True, words=())

    assert voz.strip(sin_tiempos, heard_at=_a(15.0), stream_started_at=INICIO) is None
    # Y sin el segundo cero del flujo, igual: los tiempos no se pueden situar.
    con_palabras = _oido("hubo alguien herido", desde=11.5)
    assert voz.strip(con_palabras, heard_at=_a(15.0), stream_started_at=None) is None


# --- Lo de la persona se queda --------------------------------------------------------


def test_lo_que_la_persona_contesta_despues_se_queda_aunque_venga_pegado_al_eco() -> None:
    # Un solo transcrito del reconocedor: el eco de la pregunta y, enseguida, la respuesta.
    voz = _sonando()
    mezclado = _oido("hubo alguien herido en el accidente no, nadie salió herido", desde=12.2)

    limpio = _quitar(voz, mezclado, llego=16.5)

    assert limpio is not None
    assert str(limpio.text) == "no, nadie salió herido"
    assert [str(p.text) for p in limpio.words] == ["no,", "nadie", "salió", "herido"]
    assert limpio.is_final


def test_quien_interrumpe_con_otras_palabras_sigue_interrumpiendo() -> None:
    voz = _sonando()
    interrupcion = _oido("espera, eso no fue así", desde=11.0)

    assert _quitar(voz, interrupcion, llego=12.6) is interrupcion


def test_palabras_sueltas_que_coinciden_no_hacen_un_eco() -> None:
    # «no», «en» y «el» estan en la frase de la agente, pero no como un tramo seguido.
    voz = _sonando("No encontré la póliza en el sistema con el número que me diste.")
    persona = _oido("no en el carro no", desde=11.0)

    assert _quitar(voz, persona, llego=12.8) is persona


def test_lo_dicho_cuando_la_agente_ya_callo_no_se_toca() -> None:
    voz = _sonando()
    respuesta = _oido("hubo alguien herido", desde=14.0 + 1.5)

    # Las mismas palabras de la agente, pero dichas despues: es la persona repitiendolas.
    assert _quitar(voz, respuesta, llego=17.0) is respuesta


def test_lo_dicho_antes_de_que_la_agente_empezara_no_se_toca() -> None:
    voz = _sonando()
    antes = _oido("gracias por contarme", desde=8.0)

    assert _quitar(voz, antes, llego=10.5) is antes


def test_sin_nada_dicho_no_hay_nada_que_quitar() -> None:
    oido = _oido("tuve un choque", desde=1.0)

    assert OwnVoice().strip(oido, heard_at=_a(2.0), stream_started_at=INICIO) is oido


# --- Cuando suena ---------------------------------------------------------------------


def test_cortar_el_audio_cierra_la_ventana_del_eco() -> None:
    voz = _sonando(a=None)
    voz.cut(_a(11.0))

    assert voz.sounding(_a(11.0 + 0.5))
    assert not voz.sounding(_a(11.0 + own_voice.TAIL.total_seconds() + 0.1))
    # Lo que se diga despues del corte ya es de la persona, aunque repita la frase.
    despues = _oido("hubo alguien herido", desde=13.0)
    assert _quitar(voz, despues, llego=14.5) is despues


def test_suena_desde_un_poco_antes_del_inicio_y_hasta_un_poco_despues_del_final() -> None:
    voz = _sonando()

    assert not voz.sounding(_a(9.0))
    assert voz.sounding(_a(10.0 - 0.2))
    assert voz.sounding(_a(12.0))
    assert voz.sounding(_a(14.0 + 0.7))
    assert not voz.sounding(_a(14.0 + 1.0))


def test_solo_recuerda_las_ultimas_frases() -> None:
    voz = OwnVoice()
    for i in range(own_voice.KEPT + 3):
        voz.begin(f"frase número {i}", starts_at=_a(float(i))).ends_at = _a(i + 0.9)

    vieja = _oido("frase número 0", desde=0.1)
    assert _quitar(voz, vieja, llego=1.0) is vieja


# --- El margen del final y los trozos cortos -------------------------------------------


def test_la_ultima_palabra_de_la_frase_sola_en_el_margen_es_eco() -> None:
    voz = _sonando()

    assert _quitar(voz, _oido("accidente", desde=14.0 + 0.4), llego=15.0) is None


def test_una_respuesta_corta_en_el_margen_no_se_pierde() -> None:
    # La persona contesta en cuanto la agente termina. «no» no es el final de la frase de
    # la agente, y «gracias» esta en ella pero al principio: ninguna es su eco.
    voz = _sonando()

    rapida = _oido("no", desde=14.0 + 0.4)
    assert _quitar(voz, rapida, llego=15.0) is rapida
    cortes = _oido("gracias", desde=14.0 + 0.4)
    assert _quitar(voz, cortes, llego=15.0) is cortes


def test_un_parcial_corto_con_una_palabra_mal_oida_sigue_siendo_eco() -> None:
    # «hubo algo» por «hubo alguien»: sin esto el parcial pasaba con dos palabras, que es
    # justo lo que hace falta para callar a la agente.
    voz = _sonando()

    assert _quitar(voz, _oido("hubo algo", desde=11.5, final=False), llego=12.4) is None


def test_una_sola_palabra_que_no_esta_en_la_frase_es_de_la_persona() -> None:
    voz = _sonando()
    persona = _oido("espera", desde=11.5, final=False)

    assert _quitar(voz, persona, llego=12.0) is persona


def test_lo_que_queda_conserva_la_confianza_de_sus_palabras() -> None:
    # La interrupcion de una sola palabra se decide por su confianza: no se puede perder.
    voz = _sonando()
    mezclado = _oido("en el accidente no", desde=13.2)

    limpio = _quitar(voz, mezclado, llego=15.5)

    assert limpio is not None and str(limpio.text) == "no"
    assert [palabra.confidence for palabra in limpio.words] == [0.9]
