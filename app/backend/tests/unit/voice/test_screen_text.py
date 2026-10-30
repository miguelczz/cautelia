"""Lo que la consola de la llamada pinta de lo que dice la agente (2026-10-13).

Regla de Miguel, pedida cuatro veces: en su propia pantalla la persona lo ve todo sin
etiquetas. La base sigue guardando tapado, y el sintetizador sigue recibiendo `Redacted`;
lo que cambia es que la consola recibe el texto sin tapar y que **nada de lo que suena**
puede decir una etiqueta en voz alta.

Sin base de datos: el motor se arma sobre una sesion de mentira, y lo que se prueba es lo
que `CallEngine` decide mostrar y decir de cada frase.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest

from untangle.base import Locale
from untangle.compliance.redaction import api as redaccion
from untangle.orchestration.contracts import FinalText, InboundTurn, PartialText, TurnEvent
from untangle.tenancy.models import TenantConfig
from untangle.voice.call import CallEngine, Utterance
from untangle.voice.models import CallSession, CallState, VoiceMode

pytestmark = pytest.mark.usefixtures("catalogo_cargado")

#: Cualquier etiqueta de la redaccion, en cualquiera de los dos idiomas: `[NOMBRE 1]`,
#: `[PLATE 2]`.
ETIQUETA = re.compile(r"\[[^\[\]]+? \d+\]")

PLACA = "ABC123"


def _sin_grafo(turn: InboundTurn) -> AsyncIterator[TurnEvent]:
    """Aqui no se entrega ningun turno: se prueba lo que el motor hace con cada frase."""
    msg = f"no se esperaba ningun turno: {turn.session_ref}"
    raise AssertionError(msg)


def _motor(aseguradora: TenantConfig, idioma: Locale) -> CallEngine:
    llamada = CallSession(
        call_id="llamada-de-prueba",
        tenant_id=aseguradora.tenant_id,
        visitor_key_digest="digest-de-prueba",
        language=idioma,
        voice_mode=VoiceMode.PRIMARY,
        state=CallState.LIVE,
        started_at=datetime(2026, 10, 13, 12, 0, tzinfo=UTC),
        case_id="caso-de-prueba",
    )
    return CallEngine(call=llamada, config=aseguradora, handle_turn=_sin_grafo)


def _hablar(motor: CallEngine, evento: TurnEvent) -> Utterance:
    """La forma hablada de un evento: es privada, y se prueba por si sola."""
    return motor._hablar(evento)


# --- Lo que escribio el modelo --------------------------------------------------


@pytest.mark.parametrize(
    ("idioma", "escrito"),
    [
        ("en", f"I have your plate as {PLACA}."),
        ("es", f"Tengo tu placa como {PLACA}."),
    ],
)
def test_lo_que_escribio_el_modelo_se_lee_sin_tapar_y_se_sintetiza_sin_etiquetas(
    aseguradoras: tuple[TenantConfig, ...], idioma: Locale, escrito: str
) -> None:
    motor = _motor(aseguradoras[0], idioma)

    dicha = _hablar(motor, FinalText(message_id="m-1", text=escrito, language=idioma))

    # Lo que se lee: tal cual, con la placa a la vista y sin una sola etiqueta.
    assert motor.on_screen(dicha) == (escrito,)
    # Lo que va al puerto de sintesis: tapado, como siempre.
    assert PLACA not in str(dicha.text)
    assert ETIQUETA.search(str(dicha.text))
    # Y lo que suena: ni la placa ni la etiqueta, una palabra neutra.
    suena = str(motor.spoken(dicha))
    assert PLACA not in suena
    assert ETIQUETA.search(suena) is None
    assert "[" not in suena


def test_un_parcial_del_modelo_tambien_se_lee_sin_tapar(
    aseguradoras: tuple[TenantConfig, ...],
) -> None:
    motor = _motor(aseguradoras[0], "en")

    dicha = _hablar(motor, PartialText(message_id="m-1", seq=1, text=f"Plate {PLACA}"))

    assert motor.on_screen(dicha) == (f"Plate {PLACA}",)
    assert PLACA not in str(dicha.text)


def test_una_frase_del_catalogo_se_lee_igual_que_suena(
    aseguradoras: tuple[TenantConfig, ...],
) -> None:
    """Sin `shown`, la consola pinta lo que hay: una frase del catalogo no lleva datos."""
    motor = _motor(aseguradoras[0], "en")

    apertura = motor.opening()

    assert apertura.shown is None
    assert motor.on_screen(apertura) == (str(apertura.text),)


# --- La respuesta de cobertura que llega del fondo -------------------------------


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_la_respuesta_del_fondo_se_lee_sin_tapar_en_dos_lineas(
    aseguradoras: tuple[TenantConfig, ...], idioma: Locale
) -> None:
    """La respuesta, y despues "volviendo al reporte" con su pregunta.

    Dos lineas porque la base guarda la respuesta sola, y la pantalla del caso solo
    destapa un turno si la copia que recuerda el navegador encaja con el entero.
    """
    motor = _motor(aseguradoras[0], idioma)
    pregunta = "¿Cuál es tu placa?" if idioma == "es" else "What is your license plate?"
    # Lo que deja el turno anterior: la pregunta que la persona todavia debe.
    motor._pregunta_pendiente = pregunta
    respuesta = (
        f"Tu póliza cubre la grua para {PLACA}."
        if idioma == "es"
        else f"Your policy covers towing for {PLACA}."
    )

    dicha = motor.background_answer(respuesta)

    lineas = motor.on_screen(dicha)
    assert len(lineas) == 2
    assert lineas[0] == respuesta
    assert lineas[1].endswith(pregunta)
    assert not any(ETIQUETA.search(linea) for linea in lineas)
    # Al sintetizador va tapado (el dato no sale del proceso) y de ahi, sin etiqueta.
    assert PLACA not in str(dicha.text)
    suena = str(motor.spoken(dicha))
    assert PLACA not in suena
    assert ETIQUETA.search(suena) is None
    assert pregunta in suena, "la pregunta pendiente tiene que seguir sonando"


def test_la_respuesta_del_fondo_sin_pregunta_pendiente_es_una_sola_linea(
    aseguradoras: tuple[TenantConfig, ...],
) -> None:
    motor = _motor(aseguradoras[0], "en")

    dicha = motor.background_answer("Your policy covers towing.")

    assert motor.on_screen(dicha) == ("Your policy covers towing.",)


# --- Lo que llega de la base ya tapado -------------------------------------------


@pytest.mark.parametrize(
    ("idioma", "guardado", "esperado"),
    [
        ("en", "Call [NAME 1] back about [PLATE 2].", "Call that name back about that plate."),
        ("es", "Llama a [NOMBRE 1] por [PLACA 2].", "Llama a ese nombre por esa placa."),
        # La llamada cambio de idioma despues de guardarse el comentario.
        ("en", "Call [NOMBRE 1] back.", "Call that name back."),
    ],
)
def test_lo_que_la_base_guardo_tapado_no_se_pinta_ni_suena_con_etiqueta(
    aseguradoras: tuple[TenantConfig, ...], idioma: Locale, guardado: str, esperado: str
) -> None:
    """El comentario de un ajustador se guarda tapado y no hay con que destaparlo: ni la
    consola ni el altavoz dicen la etiqueta."""
    motor = _motor(aseguradoras[0], idioma)
    dicha = Utterance(text=redaccion.from_catalog(guardado, language=idioma))

    assert motor.on_screen(dicha) == (esperado,)
    assert str(motor.spoken(dicha)) == esperado


def test_lo_que_suena_conserva_los_codigos_dichos_como_se_dictan(
    aseguradoras: tuple[TenantConfig, ...],
) -> None:
    """Quitar las etiquetas no deshace lo de `speakable`: los dos pasan por `spoken`."""
    motor = _motor(aseguradoras[0], "en")
    dicha = Utterance(
        text=redaccion.from_catalog("Your policy POL-31 and [NAME 1].", language="en")
    )

    suena = str(motor.spoken(dicha))

    assert "three one" in suena
    assert "that name" in suena
    assert "[" not in suena
