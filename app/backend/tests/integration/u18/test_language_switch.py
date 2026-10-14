"""Cambiar de idioma a mitad de la llamada (US1.31, US1.32).

**Esta suite fijo, del 2026-10-11 al 2026-10-13, que la llamada NO cambiaba de idioma**:
la transcripcion era de un solo idioma por llamada --se elige antes de llamar, `mode:
monolingual`--, asi que cambiar la voz sin cambiar el oido dejaba a la persona hablando
con quien no la entendia (V18 de la auditoria). Desde el 2026-10-13 vuelve a cambiar, esta
vez completo: el motor cambia el idioma, escribe la fila, dice el acuse **ya en el idioma
nuevo** con la pregunta que seguia, y el ciclo reabre el reconocedor en ese idioma (eso lo
prueba `test_call_loop.py`, que es quien tiene el ciclo).

Las dos reglas `[bloquea]` siguen comprobandose **en la base**: cambiar de idioma no pierde
ningun bloque confirmado, y el idioma del caso no lo mueve un turno. Con el idioma solo en
memoria las dos pasarian sin tocar nada de lo que de verdad protegen.

Los dobles del reconocedor y de la sintesis son **los de U16, importados**, no
unos nuevos: ver la razon en `conftest.py`.
"""

from __future__ import annotations

import io
import json
import time
from collections.abc import AsyncIterator
from datetime import timedelta

import pytest

from untangle import observability
from untangle.base import Locale
from untangle.case_record import api as casos
from untangle.case_record import crypto, rules
from untangle.case_record.models import (
    Actor,
    ActorType,
    CaseField,
    CaseState,
    Channel,
    FieldStatus,
)
from untangle.copy_catalog import api as copy_api
from untangle.orchestration import contracts as c14
from untangle.providers.ports import ExternalText, Transcript, WordHypothesis
from untangle.telemetry.spend.models import VoiceMode
from untangle.tenancy import api as tenancy
from untangle.tenancy import session as db
from untangle.tenancy.models import TenantConfig
from untangle.voice import api as voz
from untangle.voice import latency, opening, resume
from untangle.voice.call import LANGUAGE_SWITCHED, SwitchReason

from ...unit.voice.dobles import con_rastro
from ..u16.conftest import AHORA, nuevo_caso
from ..u16.test_call_engine import _drenar_el_fondo

pytestmark = pytest.mark.usefixtures("base_de_u16")

#: PERF-U18.1: lo que reconocer el idioma anade al camino del turno.
PRESUPUESTO_DEL_IDIOMA_MS = 15

#: Una frase larga en ingles, para pasar el piso de palabras (BR3.3) con el detector de texto.
EN_INGLES = "I was driving north on the highway when the other car hit me"
#: Y su equivalente en espanol, para la llamada que empieza en ingles.
EN_ESPANOL = "Venia manejando hacia el norte por la autopista cuando el otro carro me choco"


def _final(
    texto: str, *, idioma: Locale | None = None, confianza: float | None = 0.95
) -> Transcript:
    """Un transcrito final, opcionalmente con el idioma que el reconocedor dijo.

    `idioma=None` es el caso real que mas se olvida: el proveedor no siempre lo
    manda, y entonces la unica fuente es el detector del proyecto.
    """
    palabras = tuple(
        WordHypothesis(
            text=ExternalText(p), start_s=i * 0.3, end_s=i * 0.3 + 0.2, confidence=confianza
        )
        for i, p in enumerate(texto.split())
    )
    return Transcript(text=ExternalText(texto), is_final=True, words=palabras, language=idioma)


def _habla(texto: str, *, idioma: Locale | None = None) -> voz.SpeechEnd:
    """Un turno de la persona, ya cerrado."""
    return voz.SpeechEnd(
        text=texto, at=AHORA, last_audible_word_at=None, last=_final(texto, idioma=idioma)
    )


def _con_deteccion(config: TenantConfig, *, activa: bool) -> TenantConfig:
    """La misma aseguradora con la deteccion automatica encendida o apagada.

    Se cambia **el dato**, que es donde vive la diferencia (BR3.1): un `if` por
    aseguradora dentro del codigo seria justo lo que `project.md` prohibe.
    """
    return config.model_copy(
        update={"voice": config.voice.model_copy(update={"auto_language_detection": activa})}
    )


async def _idioma_escrito(motor: voz.CallEngine) -> str:
    """El idioma que quedo en la fila de la llamada.

    Se consulta la tabla porque lo que esta prueba protege es **lo escrito**: una
    llamada que se corta y se retoma lee de ahi, no del objeto en memoria.
    """
    async with db.session_for(motor.call.tenant_id) as sesion:
        fila = await db.fetch_one(
            sesion,
            "SELECT language FROM call_session WHERE call_id = :call_id",
            call_id=motor.call.call_id,
        )
    assert fila is not None
    return str(fila["language"])


class _GrafoQueAnota:
    """El grafo, doblado, que guarda el turno que le entregaron.

    **No es mas permisivo que la pieza real**: `handle_turn` levanta si el turno
    llega sin caso, y este hace lo mismo.
    """

    def __init__(self) -> None:
        self.recibidos: list[c14.InboundTurn] = []

    async def _emitir(self, turn: c14.InboundTurn) -> AsyncIterator[c14.TurnEvent]:
        if turn.case_id is None:
            msg = "handle_turn necesita case_id"
            raise ValueError(msg)
        self.recibidos.append(turn)
        yield c14.FinalText(message_id="m1", text="Listo.", language=turn.language)

    def __call__(self, turn: c14.InboundTurn) -> AsyncIterator[c14.TurnEvent]:
        return self._emitir(turn)


async def _motor(
    *, language: Locale = "es", deteccion: bool = False, grafo: _GrafoQueAnota | None = None
) -> voz.CallEngine:
    """Una llamada de verdad, con su caso, en el idioma que pida la prueba."""
    aseguradora = tenancy.available_ids()[0]
    caso = await nuevo_caso(aseguradora)
    llamada = await voz.open_call(
        tenant_id=aseguradora,
        visitor_key_digest="digest-de-u18",
        language=language,
        voice_mode=VoiceMode.PRIMARY,
        now=AHORA,
    )
    llamada = await voz.attach_case(llamada, case_id=caso.case_id)
    return voz.CallEngine(
        call=llamada,
        config=_con_deteccion(tenancy.require(aseguradora), activa=deteccion),
        handle_turn=con_rastro(grafo or _GrafoQueAnota()),
        # Cero, igual que en las pruebas del ciclo de U16, porque **el reloj de la
        # prueba no avanza**: el turno se cierra cuando vence el fin del habla, y
        # con el reloj fijo y un plazo mayor que cero no vence nunca. Sin esto el
        # ciclo se queda escuchando para siempre y la prueba vence por tiempo, que
        # es lo que parece un fallo del cambio de idioma y no lo es.
        end_of_speech=timedelta(0),
        unpunctuated_end_of_speech=timedelta(0),
        incomplete_end_of_speech=timedelta(0),
    )


async def _turnos(
    motor: voz.CallEngine, dichos: list[str], *, idioma: Locale | None = None
) -> None:
    """Los turnos de la persona, uno tras otro, hasta que la agente termina de contestar."""
    for n, dicho in enumerate(dichos):
        _ = [u async for u in motor.speak_turn(_habla(dicho, idioma=idioma), turn_id=f"t{n}")]


# --- Pedir el otro idioma: la llamada cambia (AC1.31.1, AC1.31.2) -------------


@pytest.mark.parametrize(
    ("desde", "dicho", "hacia"),
    [
        ("es", "In English, please.", "en"),
        ("es", "¿Me lo puede decir in English?", "en"),
        ("en", "En español, por favor.", "es"),
        ("en", "Can you speak Spanish?", "es"),
    ],
)
async def test_pedir_el_otro_idioma_cambia_la_llamada_en_los_dos_sentidos(
    catalogo: None, desde: Locale, dicho: str, hacia: Locale
) -> None:
    """Y en los dos sentidos **dicho en cualquiera de los dos idiomas** (BR2.2): las
    filas segunda y cuarta son las que el detector solo no podria, porque estan dichas
    en el idioma de partida."""
    motor = await _motor(language=desde)
    await motor.opening_finished(at=AHORA)

    assert motor.is_side_request(_habla(dicho))
    dichas = [u async for u in motor.speak_turn(_habla(dicho), turn_id="t1")]

    assert [u.copy_key for u in dichas] == [LANGUAGE_SWITCHED]
    assert motor.language == hacia


@pytest.mark.parametrize(
    ("desde", "dicho", "hacia", "acuse"),
    [
        ("es", "In English, please.", "en", "Sure, we'll continue in English."),
        ("en", "En español, por favor.", "es", "Claro, seguimos en español."),
    ],
)
async def test_el_acuse_sale_en_el_idioma_nuevo_con_la_pregunta_que_seguia(
    catalogo: None, desde: Locale, dicho: str, hacia: Locale, acuse: str
) -> None:
    """El acuse lo dice la agente **ya en el idioma al que se pasa**, y a continuacion la
    pregunta que habia quedado en el aire, tambien en ese idioma: sin ella la persona se
    queda sin saber que sigue. Nada de colgar ni de elegirlo antes de llamar."""
    motor = await _motor(language=desde)
    await motor.opening_finished(at=AHORA)

    [frase] = [u async for u in motor.speak_turn(_habla(dicho), turn_id="t1")]

    assert str(frase.text) == f"{acuse} {opening.first_question(language=hacia)}"
    bajo = str(frase.text).lower()
    assert "cuelga" not in bajo and "hang up" not in bajo


@pytest.mark.parametrize("deteccion", [False, True])
async def test_el_pedido_cambia_la_llamada_con_la_deteccion_encendida_o_apagada(
    catalogo: None, deteccion: bool
) -> None:
    """Pedirlo y que lo noten solos son dos cosas: la bandera es de la segunda."""
    motor = await _motor(language="es", deteccion=deteccion)
    await motor.opening_finished(at=AHORA)

    await _turnos(motor, ["¿Me lo puede decir in English?"], idioma="es")

    assert motor.language == "en"


async def test_pedir_el_idioma_en_que_ya_se_esta_es_un_turno_como_cualquier_otro(
    catalogo: None,
) -> None:
    """Una peticion satisfecha de antemano no se contesta aparte: sigue al grafo."""
    grafo = _GrafoQueAnota()
    motor = await _motor(language="en", grafo=grafo)
    await motor.opening_finished(at=AHORA)

    assert not motor.is_side_request(_habla("In English, please."))
    await _turnos(motor, ["In English, please."])

    assert len(grafo.recibidos) == 1
    assert motor.language == "en"


async def test_el_pedido_no_llega_al_grafo_y_el_turno_siguiente_si_en_el_idioma_nuevo(
    catalogo: None,
) -> None:
    """AC1.31.1: "el turno siguiente es en ingles". El pedido se contesta aparte; lo que la
    persona diga despues llega al grafo, y llega ya en el idioma nuevo."""
    grafo = _GrafoQueAnota()
    motor = await _motor(language="es", grafo=grafo)
    await motor.opening_finished(at=AHORA)

    await _turnos(motor, ["In English, please"])
    assert grafo.recibidos == [], "el pedido llego al grafo"
    await _turnos(motor, ["I was hit from behind"])

    assert [(t.text, t.language) for t in grafo.recibidos] == [("I was hit from behind", "en")]


async def test_ida_y_vuelta_deja_la_llamada_en_el_idioma_en_que_empezo(catalogo: None) -> None:
    """AC1.31.2: "en español" despues de haber pasado al ingles."""
    motor = await _motor(language="es")
    await motor.opening_finished(at=AHORA)

    await _turnos(motor, ["In English, please", "En español, por favor"])

    assert motor.language == "es"
    assert await _idioma_escrito(motor) == "es"


async def test_la_pregunta_pendiente_se_retoma_en_el_idioma_nuevo_deducida_del_caso(
    catalogo: None, cifrador: crypto.Cipher
) -> None:
    """Lo que la agente pregunto estaba escrito en el otro idioma: se deduce otra vez del
    caso --lo ya confirmado no se vuelve a preguntar-- en vez de traducirse."""
    motor = await _motor(language="es")
    caso = motor.call.case_id
    assert caso is not None
    # El caso esta capturando: es de donde la captura deduce lo que falta preguntar.
    await casos.apply_transition(
        motor.call.tenant_id,
        caso,
        CaseState.CAPTURING,
        context=rules.TransitionContext(
            now=AHORA, actor=Actor(actor_type=ActorType.INSURED), channel=Channel.VOICE
        ),
    )
    await _confirmar_dos_campos(motor.call.tenant_id, caso, cifrador)
    await motor.opening_finished(at=AHORA)
    # Ya dijo a que llama: la pregunta que sigue es la del caso y no la de la apertura.
    assert motor.first_turn_purpose(_habla("tuve un choque en la calle diez")) is not None
    vista = await casos.get_case(motor.call.tenant_id, caso)
    assert vista is not None
    en_ingles = resume.next_question(vista, language="en")
    en_espanol = resume.next_question(vista, language="es")
    assert en_ingles is not None and en_espanol is not None, "el caso no tiene nada pendiente"

    [frase] = [u async for u in motor.speak_turn(_habla("In English, please"), turn_id="t1")]

    assert str(frase.text) == f"Sure, we'll continue in English. {en_ingles}"
    assert en_espanol not in str(frase.text)


async def test_una_oferta_abierta_se_repite_en_el_idioma_nuevo(catalogo: None) -> None:
    """ "¿Lo dejamos guardado o se lo paso a un ajustador?" sigue esperando su respuesta:
    el acuse la vuelve a decir, ya en el idioma nuevo."""
    motor = await _motor(language="es")
    await motor.opening_finished(at=AHORA)
    # La deja abierta el segundo silencio o la tercera vez que no se entiende.
    motor._abrir_la_oferta()

    [frase] = [u async for u in motor.speak_turn(_habla("In English, please"), turn_id="t1")]

    oferta = copy_api.t(copy_api.CopyKey("voice.offer.save_or_adjuster"), locale="en")
    assert str(frase.text).endswith(oferta)


async def test_lo_que_se_guarda_de_la_llamada_sale_en_el_idioma_en_que_se_dijo(
    catalogo: None,
) -> None:
    """El turno que pide el cambio y el acuse quedan en la transcripcion con el idioma
    nuevo, no con el de partida (BR2.3)."""
    motor = await _motor(language="es")
    await motor.opening_finished(at=AHORA)
    assert motor.call.case_id is not None

    await _turnos(motor, ["In English, please"])
    await _drenar_el_fondo()

    turnos = await casos.transcript_of(motor.call.tenant_id, motor.call.case_id)
    assert [t.language for t in turnos] == ["en", "en"]


async def test_el_caso_nuevo_de_la_misma_llamada_registra_la_divulgacion_que_se_dijo(
    catalogo: None,
) -> None:
    """La divulgacion sono en español; si la llamada pasa al ingles y se abre otro caso, el
    registro del caso nuevo sigue diciendo el idioma en que se dijo y no el actual."""
    motor = await _motor(language="es")
    await motor.opening_finished(at=AHORA)
    await _turnos(motor, ["In English, please"])

    await motor.opening_finished(at=AHORA)

    assert motor.language == "en"
    assert motor.opening_language == "es"


async def test_el_idioma_de_la_llamada_queda_escrito_en_la_fila(catalogo: None) -> None:
    """Y no solo en memoria: una llamada que se corta y se retoma tiene que volver en el
    idioma en que se estaba hablando (BR2.3)."""
    motor = await _motor(language="es")
    await motor.opening_finished(at=AHORA)

    await _turnos(motor, ["In English, please"])

    assert await _idioma_escrito(motor) == "en"


# --- Lo que el cambio no puede tocar (BR5.1, `[bloquea]`) ---------------------


async def test_cambiar_de_idioma_no_pierde_ningun_bloque_confirmado(
    catalogo: None, cifrador: crypto.Cipher
) -> None:
    """La primera regla `[bloquea]` de la unidad.

    Si pedir el idioma reiniciara el caso, quien lo pide a mitad de la conversacion
    pagaria por pedirlo volviendo a contar todo. Se comprueba **en la base** y no sobre
    el objeto en memoria: lo que se protege es lo escrito.
    """
    motor = await _motor(language="es")
    caso = motor.call.case_id
    assert caso is not None
    confirmados = await _confirmar_dos_campos(motor.call.tenant_id, caso, cifrador)
    await motor.opening_finished(at=AHORA)

    await _turnos(motor, ["In English, please"])

    assert motor.language == "en"
    vista = await casos.get_case(motor.call.tenant_id, caso)
    assert vista is not None
    for clave in confirmados:
        assert vista.completeness.per_field[clave] is True, f"«{clave}» dejo de estar confirmado"


async def test_el_idioma_del_caso_no_lo_mueve_un_turno(catalogo: None) -> None:
    """La segunda regla `[bloquea]`, y es RT-10 con otra ropa.

    El idioma del caso es el que tenia al abrirse, porque es el que decide en que
    cola lo ve la aseguradora. Si siguiera al ultimo turno, mover un caso de cola
    costaria decir dos palabras en el otro idioma: no haria falta ninguna
    credencial.
    """
    motor = await _motor(language="es")
    caso = motor.call.case_id
    assert caso is not None
    antes = await casos.get_case(motor.call.tenant_id, caso)
    assert antes is not None
    await motor.opening_finished(at=AHORA)

    await _turnos(motor, ["In English, please", EN_INGLES])

    despues = await casos.get_case(motor.call.tenant_id, caso)
    assert despues is not None
    assert motor.language == "en"
    assert despues.language == antes.language


async def test_la_identidad_de_voz_no_cambia_con_el_idioma(catalogo: None) -> None:
    """AC1.31.3: la misma agente en los dos idiomas, en todas las aseguradoras.

    No es conducta de codigo: es una propiedad de la carpeta versionada, y por eso se
    comprueba sobre ella y no sobre una llamada. La voz por idioma vive en el bloque
    `primary`, y que sus dos entradas coincidan es lo que hace que el idioma de la
    llamada no suene a otra persona.
    """
    revisadas = 0
    for tenant_id in tenancy.available_ids():
        primary = tenancy.require(tenant_id).voice.primary
        if primary is None or primary.es is None or primary.en is None:
            continue
        revisadas += 1
        assert primary.es == primary.en, (
            f"«{tenant_id}» usa una voz principal distinta por idioma: "
            f"{primary.es.voice_id} y {primary.en.voice_id}"
        )
    assert revisadas, "ninguna aseguradora tiene voz principal en los dos idiomas"


async def _confirmar_dos_campos(tenant_id: str, case_id: str, cifrador: crypto.Cipher) -> list[str]:
    """Deja dos campos del caso confirmados, por la API de U4.

    Se toman los que la propia completitud declara pendientes en vez de escribir
    la lista: si el esquema gana un campo, esto sigue midiendo lo mismo.
    """
    vista = await casos.get_case(tenant_id, case_id)
    assert vista is not None
    pendientes = [c for c, listo in vista.completeness.per_field.items() if not listo][:2]
    assert len(pendientes) == 2, "el caso no tiene dos campos que confirmar"
    for clave in pendientes:
        await casos.set_field(
            tenant_id,
            CaseField(
                case_id=case_id,
                field_key=clave,
                value=cifrador.seal("lo que dijo"),
                status=FieldStatus.CONFIRMED,
                evidence_turn_id=f"turno-{clave}",
                confirmed_aloud_at=AHORA,
                updated_at=AHORA,
            ),
            cipher=cifrador,
            actor=Actor(actor_type=ActorType.INSURED),
        )
    return pendientes


# --- Hablar en el otro idioma sin pedirlo (US1.32) ---------------------------


async def test_dos_turnos_seguidos_en_el_otro_idioma_cambian_la_llamada(catalogo: None) -> None:
    """AC1.32.1: "la respuesta al turno t+1 ya es en el otro idioma". El primero se atiende
    en el idioma de la llamada, el segundo ya llega al grafo en el nuevo."""
    grafo = _GrafoQueAnota()
    motor = await _motor(language="es", deteccion=True, grafo=grafo)
    await motor.opening_finished(at=AHORA)

    await _turnos(motor, [EN_INGLES, EN_INGLES])

    assert [t.language for t in grafo.recibidos] == ["es", "en"]
    assert motor.language == "en"
    assert await _idioma_escrito(motor) == "en"


async def test_la_vuelta_tambien_se_nota_sola(catalogo: None) -> None:
    grafo = _GrafoQueAnota()
    motor = await _motor(language="en", deteccion=True, grafo=grafo)
    await motor.opening_finished(at=AHORA)

    await _turnos(motor, [EN_ESPANOL, EN_ESPANOL])

    assert [t.language for t in grafo.recibidos] == ["en", "es"]
    assert motor.language == "es"


async def test_un_solo_turno_en_el_otro_idioma_no_cambia_nada(catalogo: None) -> None:
    """Una cita o un modismo no mueven la conversacion entera."""
    motor = await _motor(language="es", deteccion=True)
    await motor.opening_finished(at=AHORA)

    await _turnos(motor, [EN_INGLES])

    assert motor.language == "es"


async def test_un_turno_en_el_idioma_de_la_llamada_entre_los_dos_reinicia_la_cuenta(
    catalogo: None,
) -> None:
    """Dos turnos en el otro idioma tienen que ser **seguidos**."""
    motor = await _motor(language="es", deteccion=True)
    await motor.opening_finished(at=AHORA)

    await _turnos(motor, [EN_INGLES, EN_ESPANOL, EN_INGLES])

    assert motor.language == "es"


@pytest.mark.parametrize(
    "dicho",
    ["okay", "el Toyota Highlander", "Marcela Rios", "ok thanks", "mi Ford Focus"],
)
async def test_una_palabra_suelta_una_marca_o_un_nombre_no_cambian_el_idioma(
    catalogo: None, dicho: str
) -> None:
    """AC1.32.2. El piso de palabras manda **sobre las dos fuentes**: ni el idioma que
    diga el reconocedor ni el del detector de texto cambian nada con tan pocas palabras."""
    motor = await _motor(language="es", deteccion=True)
    await motor.opening_finished(at=AHORA)

    await _turnos(motor, [dicho] * 4, idioma="en")

    assert motor.language == "es"


async def test_con_la_deteccion_apagada_hablar_el_otro_idioma_no_cambia_nada(
    catalogo: None,
) -> None:
    """AC1.31.5: la agente sigue en el idioma actual, aunque la persona hable cuatro turnos
    seguidos en el otro. Pedirlo, en cambio, si cambia (arriba)."""
    grafo = _GrafoQueAnota()
    motor = await _motor(language="es", deteccion=False, grafo=grafo)
    await motor.opening_finished(at=AHORA)

    await _turnos(motor, [EN_INGLES] * 4, idioma="en")

    assert [t.language for t in grafo.recibidos] == ["es"] * 4
    assert motor.language == "es"


async def test_el_idioma_que_dice_el_reconocedor_manda_sobre_el_del_texto(
    catalogo: None,
) -> None:
    """Con el reconocedor en modo multiidioma cada transcrito trae su idioma, y es la
    primera fuente: un texto que el detector leeria como español cuenta como ingles si el
    reconocedor lo oyo asi."""
    motor = await _motor(language="es", deteccion=True)
    await motor.opening_finished(at=AHORA)

    await _turnos(motor, [EN_ESPANOL] * 2, idioma="en")

    assert motor.language == "en"


async def test_un_turno_que_no_se_entendio_no_cuenta_para_cambiar_de_idioma(
    catalogo: None,
) -> None:
    """Un ruido con poca confianza no es evidencia de que la persona cambio de idioma."""
    motor = await _motor(language="es", deteccion=True)
    await motor.opening_finished(at=AHORA)
    sin_confianza = voz.SpeechEnd(
        text=EN_INGLES,
        at=AHORA,
        last_audible_word_at=None,
        last=_final(EN_INGLES, idioma="en", confianza=0.1),
    )

    for n in range(3):
        _ = [u async for u in motor.speak_turn(sin_confianza, turn_id=f"t{n}")]

    assert motor.language == "es"


async def test_un_detector_roto_no_tumba_la_llamada_y_deja_su_rastro(
    catalogo: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El detector es una extension de un tercero: si levanta, la llamada sigue en su
    idioma y el fallo deja un evento que dice el tipo y nunca el mensaje (RT-14)."""

    def roto(_: str) -> Locale | None:
        msg = "texto de la persona que no debe salir"
        raise RuntimeError(msg)

    monkeypatch.setattr("untangle.voice.call.deteccion.measured", roto)
    motor = await _motor(language="es", deteccion=True)
    await motor.opening_finished(at=AHORA)
    rastro = io.StringIO()
    observability.set_stream(rastro)

    await _turnos(motor, [EN_INGLES, EN_INGLES])

    assert motor.language == "es"
    eventos = _eventos(rastro, latency.LANGUAGE_DETECTION_FAILED)
    assert eventos, "el fallo del detector no dejo rastro"
    assert eventos[0]["error_type"] == "RuntimeError"
    assert "no debe salir" not in rastro.getvalue()


async def test_la_deteccion_llega_encendida_en_todas_las_aseguradoras(catalogo: None) -> None:
    """El valor vive en la carpeta versionada, no en un `if` (BR3.1)."""
    aseguradoras = tenancy.available_ids()
    # Sin esta linea el recorrido pasaria en vacio: una carpeta que no cargara
    # ninguna aseguradora daria esta prueba en verde sin haber mirado nada.
    assert aseguradoras, "la carpeta de aseguradoras no cargo ninguna"
    for tenant_id in aseguradoras:
        assert tenancy.require(tenant_id).voice.auto_language_detection is True


# --- La traza (ADR-013, RT-14) -----------------------------------------------


@pytest.mark.parametrize(
    ("dichos", "motivo"),
    [
        (["In English, please"], SwitchReason.REQUESTED),
        ([EN_INGLES, EN_INGLES], SwitchReason.DETECTED),
    ],
)
async def test_el_cambio_deja_su_evento_con_los_dos_idiomas_y_el_motivo(
    catalogo: None, dichos: list[str], motivo: SwitchReason
) -> None:
    """Los que la persona pidio deben ser el 100 %; los que decidio la deteccion son una
    tasa de acierto. El motivo los separa."""
    motor = await _motor(language="es", deteccion=True)
    await motor.opening_finished(at=AHORA)
    rastro = io.StringIO()
    observability.set_stream(rastro)

    await _turnos(motor, dichos)

    (evento,) = _eventos(rastro, latency.LANGUAGE_SWITCHED)
    assert evento["from"] == "es"
    assert evento["to"] == "en"
    assert evento["reason"] == motivo.value


async def test_el_evento_del_cambio_no_lleva_lo_que_se_dijo(catalogo: None) -> None:
    """ADR-013, y es lo que cierra RT-14: el turno que pide el idioma es texto de una
    persona, y en la traza no entra."""
    motor = await _motor(language="es")
    await motor.opening_finished(at=AHORA)
    rastro = io.StringIO()
    observability.set_stream(rastro)

    await _turnos(motor, ["In English please my plate is ABC123"])

    (evento,) = _eventos(rastro, latency.LANGUAGE_SWITCHED)
    assert "ABC123" not in json.dumps(evento)
    assert "ABC123" not in rastro.getvalue()


def _eventos(rastro: io.StringIO, nombre: str) -> list[dict[str, object]]:
    lineas = [json.loads(linea) for linea in rastro.getvalue().splitlines() if linea.strip()]
    return [e for e in lineas if e["event"] == nombre]


# --- El presupuesto propio (PERF-U18.1) --------------------------------------


async def test_reconocer_el_pedido_cabe_en_su_presupuesto(catalogo: None) -> None:
    """PERF-U18.1: p95 ≤ 15 ms de lo que esta unidad anade al camino del turno.

    Lo que corre en cada turno es el reconocedor de pedidos de idioma y de espera: dos
    listas versionadas. La deteccion de texto solo corre con la deteccion encendida y despues
    del piso de palabras. Si se pasa, alguien metio algo caro en un sitio donde se llama en
    cada turno, y eso es lo que el numero esta ahi para atrapar.
    """
    motor = await _motor(language="es", deteccion=True)
    turno = _habla("me chocaron por detras en la carrera septima")
    motor.is_side_request(turno)

    muestras: list[float] = []
    for _ in range(20):
        inicio = time.perf_counter()
        motor.is_side_request(turno)
        muestras.append((time.perf_counter() - inicio) * 1000)

    muestras.sort()
    p95 = muestras[int(len(muestras) * 0.95) - 1]
    # Tres decimales y no uno: el valor vive dos ordenes de magnitud por debajo del
    # presupuesto, y con un decimal la cifra publicada seria "0,0 ms".
    print(f"PERF-U18.1: p95 {p95:.3f} ms sobre {len(muestras)} turnos (max {muestras[-1]:.3f})")
    assert p95 <= PRESUPUESTO_DEL_IDIOMA_MS, f"p95 de {p95:.1f} ms, muestras {muestras}"
