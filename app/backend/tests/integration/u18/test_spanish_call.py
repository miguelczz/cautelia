"""La llamada entera en español (US1.29, US1.30).

**Esta es la mitad de la unidad que no escribe código**, y es la que demuestra lo
que U18 existe para demostrar: que el español no es un servicio de segunda.

Las piezas sueltas ya se prueban en los dos idiomas --las siete de
`tests/unit/voice/` están parametrizadas sobre `("en", "es")` desde U16--. Lo que
aquí se añade es el recorrido **armado**: el motor y el ciclo con la llamada en
español, que hasta ahora solo corrían en inglés.

Si alguna de estas pruebas obligara a ramificar por idioma dentro de U18, la
corrección va a U16 (BR5.2). Hay una prueba al final que lo vigila.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path

import pytest

from untangle.case_record import api as casos
from untangle.case_record import crypto
from untangle.copy_catalog import api as copy_api
from untangle.orchestration.contracts import FinalText, TurnEvent, Waiting
from untangle.orchestration.turn import WAITING_VOICE
from untangle.telemetry.spend.models import VoiceMode
from untangle.tenancy import api as tenancy
from untangle.voice import api as voz
from untangle.voice import case_number, readback, retry, silence
from untangle.voice.models import EndReason

from ...unit.voice.dobles import con_rastro
from ..u16.conftest import AHORA, nuevo_caso
from ..u16.test_call_engine import _completar_caso, _TurnoRegistrado
from ..u16.test_call_loop import CanalFalso, VozDoble, _correr
from .test_language_switch import _final, _habla

pytestmark = pytest.mark.usefixtures("base_de_u16")

#: Un turno cualquiera en español, con señal de sobra para cualquier detector.
UN_TURNO = "me chocaron por detras en la carrera septima"


async def _motor_es(
    *, guion: tuple[TurnEvent, ...] = ()
) -> tuple[voz.CallEngine, _TurnoRegistrado]:
    """El motor de U16 con la llamada **en español**, y nada más cambiado.

    Es la única diferencia con `_motor` de U16: un argumento. Que baste un
    argumento es parte de lo que esta unidad afirma.
    """
    aseguradora = tenancy.available_ids()[0]
    caso = await nuevo_caso(aseguradora)
    llamada = await voz.open_call(
        tenant_id=aseguradora,
        visitor_key_digest="digest-de-u18",
        language="es",
        voice_mode=VoiceMode.PRIMARY,
        now=AHORA,
    )
    llamada = await voz.attach_case(llamada, case_id=caso.case_id)
    manejador = _TurnoRegistrado(guion)
    motor = voz.CallEngine(
        call=llamada,
        config=tenancy.require(aseguradora),
        handle_turn=con_rastro(manejador),
        end_of_speech=timedelta(0),
        unpunctuated_end_of_speech=timedelta(0),
        incomplete_end_of_speech=timedelta(0),
    )
    return motor, manejador


def _en_espanol(texto: str) -> FinalText:
    return FinalText(message_id="m-1", text=texto, language="es")


# --- La apertura y el turno (AC1.29.1, AC1.28.1) ------------------------------


async def test_la_apertura_suena_en_espanol_y_con_su_divulgacion(catalogo: None) -> None:
    """AC1.28.1: la apertura declara que es una demostración y que se transcribe.

    Se mira **la palabra de la divulgación** y no la frase entera: la frase es del
    catálogo y comprobarla letra a letra convertiría cada ajuste de redacción en un
    fallo, sin que nadie hubiera roto nada.
    """
    motor, _ = await _motor_es()

    apertura = motor.opening()

    # "transcri" y no "transcrib": en espanol la palabra es "transcrita". Buscar el
    # tallo ingles daba un fallo que parecia una divulgacion ausente y era la
    # prueba mirando la palabra del otro idioma.
    assert "transcri" in str(apertura.text).lower(), str(apertura.text)
    assert motor.language == "es"


async def test_la_apertura_en_espanol_no_sale_mutilada_por_la_redaccion(
    catalogo: None,
) -> None:
    """El cableado, no las piezas: **por dónde sale** la apertura en la llamada real.

    La prueba hermana de `tests/unit/voice/test_opening.py` comprueba que el camino
    del catálogo no toca la frase. Esta comprueba que el motor usa **ese** camino y
    no el del detector, que es lo que estaba mal: en español la agente se presentaba
    diciendo "[NOMBRE 1] ayudarle a reportar un siniestro".
    """
    motor, _ = await _motor_es()

    apertura = str(motor.opening().text)

    assert "[NOMBRE" not in apertura, apertura
    assert "[LUGAR" not in apertura, apertura
    # Desde el 2026-10-07 la apertura no lista capacidades: lo que tiene que salir
    # entero es la divulgacion y la primera pregunta.
    assert "queda transcrita" in apertura, apertura
    assert apertura.rstrip().endswith("ayudar?"), apertura


async def test_lo_que_escribe_un_modelo_si_se_tapa(catalogo: None) -> None:
    """La otra mitad, y sin ella lo de arriba sería una puerta sin redacción.

    Un `FinalText` que **no** declara venir del catálogo se tapa entero, porque es
    lo que escribió un modelo. Se prueba con un teléfono, que es un dato personal
    que ningún catálogo escribiría.
    """
    # Sin `from_catalog`: es el valor por omision, y es lo que llega cuando el texto
    # no es nuestro.
    del_modelo = FinalText(
        message_id="m-1", text="Le devuelvo la llamada al 3005551234.", language="es"
    )
    motor, _ = await _motor_es(guion=(del_modelo,))
    await motor.opening_finished(at=AHORA)

    dichas = [u async for u in motor.speak_turn(_habla(UN_TURNO), turn_id="t-1")]

    dicho = str(dichas[-1].text)
    assert "3005551234" not in dicho, dicho


async def test_el_turno_llega_al_grafo_marcado_en_espanol(catalogo: None) -> None:
    """El idioma del turno es lo que decide en qué idioma responde el grafo.

    Sin esto, una llamada en español podría estar contestándose en inglés sin que
    ninguna prueba de la voz lo notara: la voz solo pasa el texto.
    """
    motor, manejador = await _motor_es(guion=(_en_espanol("Listo."),))
    await motor.opening_finished(at=AHORA)

    async for _ in motor.speak_turn(_habla(UN_TURNO), turn_id="t-1"):
        pass

    assert len(manejador.recibidos) == 1
    assert manejador.recibidos[0].language == "es"


async def test_la_frase_de_espera_sale_en_espanol(catalogo: None) -> None:
    """AC1.29.4: la pregunta de cobertura tarda, y el silencio se llena.

    La frase de espera es la única que la llamada dice **por su cuenta** mientras
    el grafo trabaja, y por eso es la que más fácilmente se queda en un idioma.
    """
    espera = Waiting(copy_key=WAITING_VOICE, text=copy_api.t(WAITING_VOICE, locale="es"))
    motor, _ = await _motor_es(guion=(espera, _en_espanol("Listo.")))
    await motor.opening_finished(at=AHORA)

    dichas = [
        u async for u in motor.speak_turn(_habla("¿mi poliza cubre el vidrio?"), turn_id="t-1")
    ]

    textos = [str(u.text) for u in dichas]
    assert any("momento" in t.lower() for t in textos), textos


# --- Los códigos dictados (AC1.29.2) -----------------------------------------


async def test_la_placa_se_lee_de_vuelta_en_espanol_antes_de_anotarla(catalogo: None) -> None:
    """AC1.29.2, y la mitad que importa: **no llega al grafo sin confirmar**.

    El deletreo usa la tabla de U11 en español, y esa tabla **no es el alfabeto de
    la OTAN traducido**: dice "a de ábaco", que es como se deletrea por teléfono en
    español. Lo que se comprueba es que salió esa y no la inglesa, y basta una
    letra para distinguirlas.
    """
    motor, manejador = await _motor_es(guion=(_en_espanol("Listo."),))
    await motor.opening_finished(at=AHORA)

    dichas = [u async for u in motor.speak_turn(_habla("ABC123"), turn_id="t-1")]

    assert manejador.recibidos == [], "la placa llego al grafo sin confirmarse"
    assert [u.copy_key for u in dichas] == [readback.CONFIRM]
    dicho = _sin_tildes(str(dichas[0].text).lower())
    assert "a de abaco" in dicho, dicho
    assert "alpha" not in dicho, "salio la tabla de deletreo inglesa en una llamada en espanol"


async def test_un_si_en_espanol_confirma_la_placa(catalogo: None) -> None:
    """El "sí" tiene que reconocerse **en español**, y no es una obviedad: quien
    confirma es el reconocedor de U11, que recibe el idioma de la llamada."""
    motor, manejador = await _motor_es(guion=(_en_espanol("Listo."),))
    await motor.opening_finished(at=AHORA)

    async for _ in motor.speak_turn(_habla("ABC123"), turn_id="t-1"):
        pass
    async for _ in motor.speak_turn(_habla("sí, correcto"), turn_id="t-2"):
        pass

    assert len(manejador.recibidos) == 1
    assert "ABC123" in manejador.recibidos[0].text


async def test_un_no_en_espanol_no_anota_nada_y_vuelve_a_pedirlo(catalogo: None) -> None:
    """Y lo pide con la frase española de "no le entendí", no con la inglesa."""
    motor, manejador = await _motor_es(guion=(_en_espanol("Listo."),))
    await motor.opening_finished(at=AHORA)

    async for _ in motor.speak_turn(_habla("ABC123"), turn_id="t-1"):
        pass
    dichas = [u async for u in motor.speak_turn(_habla("no, está mal"), turn_id="t-2")]

    assert manejador.recibidos == []
    assert [u.copy_key for u in dichas] == [retry.NOT_UNDERSTOOD]
    assert "no te escuche bien" in _sin_tildes(str(dichas[0].text).lower())


# --- La escalera de "no le entendí" (AC1.29.3) -------------------------------


async def test_los_tres_peldanos_suenan_en_espanol_y_dicen_tres_cosas(catalogo: None) -> None:
    """AC1.29.3 con el segundo peldaño ya cambiado por BR4.4.

    Se comprueba **el texto** y no solo la clave: una clave correcta con el texto
    resuelto en el otro idioma es exactamente el defecto que esta unidad busca, y
    la clave sola no lo vería.
    """
    motor, _ = await _motor_es()
    await motor.opening_finished(at=AHORA)

    claves = []
    textos = []
    for n in range(3):
        for dicha in [u async for u in motor.speak_turn(_habla(""), turn_id=f"t-{n}")]:
            claves.append(dicha.copy_key)
            textos.append(str(dicha.text))

    assert claves == [retry.NOT_UNDERSTOOD, retry.ONLY_TWO_LANGUAGES, retry.OFFER]
    assert len(set(textos)) == 3
    for texto in textos:
        assert _parece_espanol(texto), texto


# --- Los silencios y la retoma (AC1.30.2, AC1.30.3, AC1.30.4) ----------------


async def test_los_tres_silencios_suenan_en_espanol_y_solo_el_tercero_cuelga(
    catalogo: None,
) -> None:
    """AC1.30.2 y AC1.30.3. Colgar sin despedirse es la peor pantalla posible, y
    despedirse en el idioma que no es, la segunda peor."""
    motor, _ = await _motor_es()
    await motor.opening_finished(at=AHORA)

    dichas = [motor.on_silence() for _ in range(3)]

    assert [d.copy_key for d in dichas if d is not None] == [
        silence.STILL_THERE,
        silence.OFFER,
        silence.FAREWELL,
    ]
    assert [d.end_reason for d in dichas if d is not None] == [None, None, EndReason.SILENCE]
    for dicha in dichas:
        assert dicha is not None
        assert _parece_espanol(str(dicha.text)), str(dicha.text)


async def test_la_oferta_de_retomar_suena_en_espanol(catalogo: None) -> None:
    """AC1.30.4: la llamada que se cortó vuelve sobre su caso, y lo pregunta."""
    aseguradora = tenancy.available_ids()[0]
    anterior = await nuevo_caso(aseguradora)
    cortada = await voz.open_call(
        tenant_id=aseguradora,
        visitor_key_digest="digest-de-u18",
        language="es",
        voice_mode=VoiceMode.PRIMARY,
        now=AHORA,
    )
    cortada = await voz.attach_case(cortada, case_id=anterior.case_id)
    cortada = await voz.end_call(
        cortada, reason=EndReason.DROPPED, now=AHORA, resume_window=timedelta(minutes=15)
    )

    motor, _ = await _motor_es()
    # La apertura primero: la oferta de retomar va **despues** de la divulgacion
    # completa (BR6.2 de U16), y el motor lo hace cumplir levantando. Sin esta linea
    # lo que fallaba era la guarda, no el idioma.
    await motor.opening_finished(at=AHORA)
    await motor.look_for_resumable(cortada)
    oferta = motor.offer_resume()

    assert oferta is not None
    assert _parece_espanol(str(oferta.text)), str(oferta.text)


# --- El cierre (AC1.29.5) ----------------------------------------------------


async def test_el_cierre_dice_el_numero_digito_a_digito_en_espanol(
    catalogo: None, cifrador: crypto.Cipher
) -> None:
    """AC1.29.5. El número se dice uno a uno porque por teléfono es la única forma
    de que se pueda apuntar, y eso vale igual en los dos idiomas."""
    motor, _ = await _motor_es(guion=(_en_espanol("Listo."),))
    await motor.opening_finished(at=AHORA)
    assert motor.call.case_id is not None
    await _completar_caso(motor.call.tenant_id, motor.call.case_id, cifrador)

    dichas = [u async for u in motor.speak_turn(_habla(UN_TURNO), turn_id="t-1")]

    cierre = dichas[-1]
    assert cierre.end_reason is EndReason.COMPLETED
    vista = await casos.get_case(motor.call.tenant_id, motor.call.case_id)
    assert vista is not None
    dicho = case_number.spell(str(vista.case_number), language="es")
    assert dicho in str(cierre.text), "el numero no se dijo digito a digito en espanol"
    # Dos grupos de tres digitos (2026-10-09): una coma por digito lo hacia lento.
    assert [len(grupo.split()) for grupo in dicho.split(",")] == [3, 3]


# --- La interrupción, sobre el ciclo (AC1.30.1) ------------------------------


async def test_la_apertura_interrumpida_se_repite_entera_en_espanol(catalogo: None) -> None:
    """AC1.30.1, y media divulgación no es divulgación (BR4.5 de U16).

    Es la única de este archivo que pasa por el ciclo completo: la interrupción es
    del transporte y no del motor.
    """
    motor, _ = await _motor_es()
    doble = VozDoble(guion=[_final("espere, me equivoque en algo")], antes_del_audio=True)
    canal = CanalFalso(seguir=lambda: len(doble.dicho) < 2)

    await asyncio.wait_for(_correr(motor, canal, doble).run(), timeout=10)

    assert canal.de_tipo(voz.StopAudio), "no se mando la orden de vaciar la cola"
    assert len(doble.dicho) >= 2, "la apertura cortada no se repitio"
    assert motor.disclosed_at is not None, "la apertura nunca llego a registrarse"
    for dicho in doble.dicho[:2]:
        assert "transcri" in dicho.lower(), dicho


# --- Lo que esta unidad vigila de sí misma (BR5.2) ---------------------------


def test_ninguna_pieza_de_u18_se_ramifica_por_idioma() -> None:
    """BR5.2, comprobado sobre los archivos de la unidad.

    Una rama `if language == "es"` aquí sería la señal de que la pieza de U16
    estaba escrita para un solo idioma, y taparlo aquí dejaría el defecto donde
    nadie lo busca. Se recorre el código de producción de U18 --el detector, el
    reconocedor de peticiones y lo que U18 añadió a la llamada-- y no las pruebas,
    que sí eligen un idioma a propósito.

    Lo que se busca es la **comparación** con un idioma, no la palabra: pasar el
    idioma por argumento es justo lo que hace que no haya ramas.
    """
    raiz = Path(__file__).resolve().parents[3] / "src" / "untangle"
    propios = [raiz / "language.py", raiz / "voice" / "language_request.py"]
    sospechosos = [
        f"{archivo.name}:{numero}: {linea.strip()}"
        for archivo in propios
        for numero, linea in enumerate(archivo.read_text(encoding="utf-8").splitlines(), start=1)
        if ('== "es"' in linea or '== "en"' in linea or "== 'es'" in linea or "== 'en'" in linea)
        and not linea.strip().startswith("#")
    ]

    assert propios[0].is_file(), "no se encontro el detector: la prueba no miro nada"
    assert sospechosos == [], sospechosos


# --- Dos ayudas ---------------------------------------------------------------


def _sin_tildes(texto: str) -> str:
    import unicodedata

    plano = unicodedata.normalize("NFD", texto)
    return "".join(c for c in plano if unicodedata.category(c) != "Mn")


def _parece_espanol(texto: str) -> bool:
    """Si la frase está en español, mirada por el detector del proyecto.

    Se usa el detector y no una palabra buscada a mano por una razón: una lista de
    palabras encontraría "su" en una frase inglesa cualquiera, y lo que se quiere
    saber es si **la frase** está en el idioma de la llamada. Cuando la frase es
    tan corta que el detector no puede decirlo, se exige al menos que no sea
    reconocible como inglés.
    """
    from untangle import language as deteccion

    if deteccion.has_signal(texto):
        return deteccion.measured(texto) == "es"
    return deteccion.measured(texto) != "en"
