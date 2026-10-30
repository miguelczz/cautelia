"""Escribir en el chat el numero de un caso empezado por llamada (US1.20, AC1.19.5).

Dos de los criterios **bloquean la entrega** y son de seguridad: un numero de caso creado desde otro
navegador (AC1.20.2) y uno de otra aseguradora (AC1.20.3) tienen que recibir exactamente lo mismo
que un numero que no existe. Se comprueban **comparando** lo que sale por el cable, lo que queda en
la base y lo que se le entrega al grafo, y con el control positivo delante: sin el, las
comparaciones pasarian igual con un chat que nunca retomara nada.

Todo por el canal real (`delivery.deliver`), con un entendedor y un grafo de mentira que cuentan
cuantas veces los llaman: el numero se reconoce antes de entregarle el mensaje a nadie.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import timedelta
from typing import Any

import pytest

from untangle.base import Locale
from untangle.case_record import api as casos
from untangle.case_record import rules as case_rules
from untangle.case_record.models import (
    Actor,
    ActorType,
    CaseState,
    Channel,
    DerivationReason,
    Origin,
    RecordType,
)
from untangle.chat import case_number, delivery
from untangle.chat import resume as chat_resume
from untangle.chat import session as chat_session
from untangle.chat.wire import EventQueue
from untangle.orchestration import contracts as u12
from untangle.orchestration import transcript_writer
from untangle.orchestration.nodes.intake import understanding
from untangle.tenancy import config as tenancy_config
from untangle.tenancy import session
from untangle.tenancy.models import TenantConfig
from untangle.voice import session as voice_session
from untangle.voice.models import VoiceMode

from ..u12.test_turn import _Entendedor, _sembrar_dichos
from .conftest import AHORA, nuevo_caso
from .test_delivery import _conversacion_nueva

pytestmark = pytest.mark.usefixtures("base_de_u13", "cifrador")


@pytest.fixture(autouse=True)
def _con_la_voz_enchufada() -> Iterator[None]:
    """El puerto que la raiz de composicion enchufa; ninguna prueba lo deja puesto."""
    chat_resume.install_call_cases(voice_session.case_ids_of_visitor)
    yield
    chat_resume.install_call_cases(None)
    delivery.install_understanding(None, None)


@pytest.fixture
def continuidad_apagada() -> Iterator[None]:
    """La configuracion de las aseguradoras con la continuidad voz a chat apagada."""
    original = tenancy_config.loaded()
    apagadas = tuple(
        t.model_copy(update={"voice_to_chat_continuity": False}) for t in original.available
    )
    tenancy_config.install(
        tenancy_config.LoadedTenants(available=apagadas, unavailable=original.unavailable)
    )
    yield
    tenancy_config.install(original)


class _Grafo:
    """Un grafo de mentira: guarda los turnos que le entregan y contesta algo corto."""

    def __init__(self) -> None:
        self.turnos: list[u12.InboundTurn] = []

    async def __call__(self, turn: u12.InboundTurn) -> AsyncIterator[u12.TurnEvent]:
        self.turnos.append(turn)
        yield u12.FinalText(message_id="m", text="ok", language="es")


async def _caso_de_llamada(
    tenant_id: str,
    navegador: str,
    *,
    estado: CaseState = CaseState.CAPTURING,
    con_datos: bool = True,
    cipher: Any = None,
) -> tuple[str, str]:
    """Un caso que este navegador empezo por llamada. Devuelve (id, numero).

    Con cuatro datos dichos y dos turnos de voz, como lo deja una llamada que se corto."""
    case_id = f"u13-voz-{uuid.uuid4().hex[:10]}"
    comienzo = AHORA - timedelta(hours=1)
    vista = await casos.create_case(
        tenant_id,
        casos.NewCase(
            case_id=case_id,
            record_type=RecordType.CLAIM,
            channel=Channel.VOICE,
            origin=Origin.PUBLIC_VOICE_CONSOLE,
            language="es",
        ),
        now=comienzo,
    )
    llamada = await voice_session.open_call(
        tenant_id=tenant_id,
        visitor_key_digest=navegador,
        language="es",
        voice_mode=VoiceMode.PRIMARY,
        now=comienzo,
    )
    await voice_session.attach_case(llamada, case_id=case_id)
    ambito = transcript_writer.TranscriptScope(
        tenant_id=tenant_id, case_id=case_id, channel=Channel.VOICE, language="es"
    )
    await transcript_writer.record_agent_turn(
        ambito, text="Cuéntame qué pasó.", now=comienzo + timedelta(minutes=1), from_catalog=True
    )
    await transcript_writer.record_person_turn(
        ambito, text="Me chocaron ayer", now=comienzo + timedelta(minutes=2)
    )
    for paso in {
        CaseState.CAPTURING: [CaseState.CAPTURING],
        CaseState.DERIVED: [CaseState.CAPTURING, CaseState.DERIVED],
    }[estado]:
        await casos.apply_transition(
            tenant_id,
            case_id,
            paso,
            context=case_rules.TransitionContext(
                now=comienzo + timedelta(minutes=3),
                actor=Actor(actor_type=ActorType.SYSTEM),
                channel=Channel.VOICE,
                derivation_reason=(DerivationReason.RULE if paso is CaseState.DERIVED else None),
            ),
        )
    if con_datos:
        await _sembrar_dichos(
            tenant_id,
            case_id,
            cipher=cipher,
            identity_and_policy="Marcela Rios, POL-01",
            incident_datetime="ayer a las 8 de la noche",
            location="la calle 10 con la carrera 43",
            injuries="nadie se lastimó",
        )
    return case_id, str(vista.case_number)


async def _escribir(  # noqa: PLR0913 -- el escenario de la prueba, por nombre
    tenant_id: str,
    conversacion: Any,
    clave: str,
    texto: str,
    *,
    grafo: _Grafo | None = None,
    entendedor: _Entendedor | None = None,
    language: Locale = "es",
) -> tuple[delivery.Delivered, EventQueue, _Grafo, _Entendedor]:
    """Un mensaje por el canal real. Devuelve lo entregado, la cola y los dos dobles."""
    grafo = grafo or _Grafo()
    entendedor = entendedor or _Entendedor(
        understanding.UnderstandingResponse(wants=understanding.Want.CONTINUE)
    )
    delivery.install_understanding(entendedor, None)
    cola = EventQueue(stream_ref=conversacion.chat_session_id)
    entregado = await delivery.deliver(
        cola,
        u12.InboundTurn(
            tenant_id=tenant_id,
            session_ref=conversacion.chat_session_id,
            case_id=conversacion.case_id,
            text=texto,
            language=language,
            channel="chat",
            received_at=AHORA,
        ),
        handle_turn=grafo,
        visitor_key_hash=clave,
        origin=Origin.PUBLIC_CHAT,
    )
    return entregado, cola, grafo, entendedor


async def _lo_que_salio(cola: EventQueue) -> dict[str, Any]:
    """El evento publicado, sin su identificador: es lo unico que cambia entre corridas."""
    cable = await cola.next_event(heartbeat_after=1)
    assert cable is not None
    return {clave: valor for clave, valor in cable.items() if clave != "message_id"}


async def _foto_de_la_base(tenant_id: str) -> tuple[int, int]:
    """Cuantos casos y cuantos turnos hay: lo que un numero que no se retoma no puede mover."""
    async with session.session_for(tenant_id) as sesion:
        casos_ = await session.fetch_one(sesion, "SELECT count(*) AS n FROM case_record")
        turnos = await session.fetch_one(sesion, "SELECT count(*) AS n FROM case_transcript_turn")
    assert casos_ is not None and turnos is not None
    return int(casos_["n"]), int(turnos["n"])


# --- El control positivo, primero ---------------------------------------------------------


async def test_el_dueno_retoma_por_chat_el_caso_que_empezo_por_voz(
    dos_aseguradoras: tuple[str, str], cifrador: Any
) -> None:
    """AC1.20.1 y AC1.20.4. Va primero a proposito: sin el, las compuertas de abajo pasarian
    igual con un chat que no retomara nunca nada."""
    _, propia = dos_aseguradoras
    conversacion, clave = await _conversacion_nueva(propia)
    caso, numero = await _caso_de_llamada(propia, clave, cipher=cifrador)
    antes = await _foto_de_la_base(propia)

    entregado, cola, grafo, entendedor = await _escribir(
        propia, conversacion, clave, f"quiero seguir con el caso {numero}"
    )

    # Un solo caso, y la conversacion queda atada a el.
    viva = await chat_session.find_live(tenant_id=propia, visitor_key_digest=clave)
    assert viva is not None and viva.case_id == caso
    assert entregado.case_id == caso
    assert (await _foto_de_la_base(propia))[0] == antes[0], "no se abrio ningun caso"
    # Lo decide el codigo: ni el modelo que entiende ni el grafo recibieron el mensaje.
    assert entendedor.peticiones == [] and grafo.turnos == []
    # La agente pide solo lo que falta: los cuatro datos de la llamada no se vuelven a pedir.
    salio = await _lo_que_salio(cola)
    assert salio["kind"] == "turn.final" and salio["case_id"] == caso
    assert numero in salio["text"]
    vista = await casos.get_case(propia, caso)
    assert vista is not None
    pregunta = case_number.pending_question(vista, language="es")
    assert pregunta is not None and pregunta in salio["text"]
    assert "póliza" not in pregunta.lower() and "herid" not in pregunta.lower()
    # La transcripcion de los dos canales, en orden, con el canal de cada turno.
    turnos = await casos.transcript_of(propia, caso)
    assert [(t.channel, t.speaker.value) for t in turnos] == [
        (Channel.VOICE, "agent"),
        (Channel.VOICE, "insured"),
        (Channel.CHAT, "insured"),
        (Channel.CHAT, "agent"),
    ]
    assert numero in turnos[2].text_redacted or "[" in turnos[2].text_redacted
    # La divulgacion del chat se registra aparte de la de la voz: una por canal.
    async with session.session_for(propia) as sesion:
        registros = await session.fetch_all(
            sesion, "SELECT channel FROM disclosure_record WHERE case_id = :id", id=caso
        )
    assert [r["channel"] for r in registros] == ["chat"]


async def test_en_ingles_se_retoma_y_se_contesta_en_ingles(
    dos_aseguradoras: tuple[str, str], cifrador: Any
) -> None:
    _, propia = dos_aseguradoras
    conversacion, clave = await _conversacion_nueva(propia, language="en")
    caso, numero = await _caso_de_llamada(propia, clave, cipher=cifrador)

    entregado, cola, *_ = await _escribir(
        propia, conversacion, clave, f"I want to continue case {numero}", language="en"
    )

    salio = await _lo_que_salio(cola)
    assert entregado.case_id == caso and salio["language"] == "en"
    assert "picked your case" in salio["text"] and numero in salio["text"]


async def test_el_numero_escrito_de_otra_forma_tambien_se_retoma(
    dos_aseguradoras: tuple[str, str], cifrador: Any
) -> None:
    _, propia = dos_aseguradoras
    conversacion, clave = await _conversacion_nueva(propia)
    caso, numero = await _caso_de_llamada(propia, clave, cipher=cifrador)
    dictado = f"{numero[:3].lower()} {numero[4:7]} {numero[7:]}"

    entregado, *_ = await _escribir(propia, conversacion, clave, f"es el {dictado}")

    assert entregado.case_id == caso


async def test_con_la_conversacion_ya_en_otro_caso_la_pasa_al_retomado(
    dos_aseguradoras: tuple[str, str], cifrador: Any
) -> None:
    """«Vale tanto si la conversacion no tiene caso como si ya tiene uno»."""
    _, propia = dos_aseguradoras
    conversacion, clave = await _conversacion_nueva(propia)
    propio = await nuevo_caso(propia, record_type=RecordType.COVERAGE_INQUIRY)
    conversacion = await chat_session.attach_case(conversacion, case_id=propio.case_id)
    caso, numero = await _caso_de_llamada(propia, clave, cipher=cifrador)

    entregado, _, grafo, _ = await _escribir(propia, conversacion, clave, numero)

    viva = await chat_session.find_live(tenant_id=propia, visitor_key_digest=clave)
    assert viva is not None and viva.case_id == caso
    assert entregado.case_id == caso and grafo.turnos == []
    # El caso en que estaba queda como estaba.
    anterior = await casos.get_case(propia, propio.case_id)
    assert anterior is not None and anterior.record_type is RecordType.COVERAGE_INQUIRY


async def test_el_mensaje_siguiente_sigue_en_el_caso_retomado(
    dos_aseguradoras: tuple[str, str], cifrador: Any
) -> None:
    _, propia = dos_aseguradoras
    conversacion, clave = await _conversacion_nueva(propia)
    caso, numero = await _caso_de_llamada(propia, clave, cipher=cifrador)
    await _escribir(propia, conversacion, clave, numero)
    viva = await chat_session.find_live(tenant_id=propia, visitor_key_digest=clave)

    _, _, grafo, _ = await _escribir(propia, viva, clave, "me chocó una moto")

    [turno] = grafo.turnos
    assert turno.case_id == caso, "el grafo sigue en el caso que la llamada empezo"


async def test_un_numero_de_poliza_no_se_toma_por_un_numero_de_caso(
    dos_aseguradoras: tuple[str, str], cifrador: Any
) -> None:
    """Tiene la misma forma --tres letras, guion, seis digitos--, y la persona lo escribe
    mientras se identifica."""
    _, propia = dos_aseguradoras
    conversacion, clave = await _conversacion_nueva(propia)
    caso = await nuevo_caso(propia)
    conversacion = await chat_session.attach_case(conversacion, case_id=caso.case_id)

    _, _, grafo, _ = await _escribir(propia, conversacion, clave, "mi póliza es POL-11")

    assert len(grafo.turnos) == 1, "es un mensaje de la captura, no un intento de retomar"


# --- BR6.2 / AC1.20.2: un numero de otro navegador, compuerta dura -------------------------


async def test_un_numero_de_otro_navegador_responde_igual_que_uno_que_no_existe(
    dos_aseguradoras: tuple[str, str], cifrador: Any
) -> None:
    """Compuerta dura. **Identico**, no «sin el dato del otro»: por el cable, en la base y en lo
    que se le entrega al grafo, aunque quien lo escribe se identifique con la misma poliza."""
    _, propia = dos_aseguradoras
    _, dueno = await _conversacion_nueva(propia)
    caso_ajeno, numero_ajeno = await _caso_de_llamada(propia, dueno, cipher=cifrador)
    turnos_del_ajeno = await casos.transcript_of(propia, caso_ajeno)
    inventado = "SA-999999" if numero_ajeno.startswith("SA") else "AC-999999"

    resultados = []
    for numero in (numero_ajeno, inventado):
        conversacion, clave = await _conversacion_nueva(propia)
        antes = await _foto_de_la_base(propia)
        entregado, cola, grafo, entendedor = await _escribir(
            propia, conversacion, clave, f"mi póliza es POL-01 y mi caso es {numero}"
        )
        viva = await chat_session.find_live(tenant_id=propia, visitor_key_digest=clave)
        assert viva is not None
        resultados.append(
            (
                entregado,
                await _lo_que_salio(cola),
                viva.case_id,
                await _foto_de_la_base(propia) == antes,
                len(grafo.turnos),
                len(entendedor.peticiones),
            )
        )

    desde_otro, de_un_inventado = resultados
    assert desde_otro == de_un_inventado
    entregado, salio, caso_de_la_conversacion, base_igual, al_grafo, al_modelo = desde_otro
    assert entregado.case_id is None and caso_de_la_conversacion is None
    assert salio["kind"] == "turn.final" and salio["case_id"] is None
    assert base_igual, "no se abrio ni se escribio nada"
    assert (al_grafo, al_modelo) == (0, 0)
    assert "SA-" not in salio["text"] and "AC-" not in salio["text"], "no repite el numero"
    # Y el caso ajeno no se movio: ni un turno de mas.
    assert await casos.transcript_of(propia, caso_ajeno) == turnos_del_ajeno


# --- BR6.3 / AC1.20.3: un numero de otra aseguradora, compuerta dura -----------------------


async def test_un_numero_de_otra_aseguradora_responde_igual_que_uno_que_no_existe(
    dos_aseguradoras: tuple[str, str], cifrador: Any
) -> None:
    """Compuerta dura. Con el **mismo navegador** en las dos: lo que lo para es la aseguradora, y
    no se compara en este codigo --la politica de fila filtra antes de que el caso se vea--."""
    ajena, propia = dos_aseguradoras
    conversacion, clave = await _conversacion_nueva(propia)
    _, numero_de_la_otra = await _caso_de_llamada(ajena, clave, cipher=cifrador)
    inventado = "AP-999999" if not numero_de_la_otra.startswith("AP") else "SA-999999"

    resultados = []
    for numero in (numero_de_la_otra, inventado):
        conversacion, clave = await _conversacion_nueva(propia)
        await _caso_de_llamada(ajena, clave, cipher=cifrador)  # el mismo navegador, en la otra
        antes = (await _foto_de_la_base(propia), await _foto_de_la_base(ajena))
        entregado, cola, grafo, entendedor = await _escribir(propia, conversacion, clave, numero)
        despues = (await _foto_de_la_base(propia), await _foto_de_la_base(ajena))
        viva = await chat_session.find_live(tenant_id=propia, visitor_key_digest=clave)
        assert viva is not None
        resultados.append(
            (
                entregado,
                await _lo_que_salio(cola),
                viva.case_id,
                despues == antes,
                len(grafo.turnos),
                len(entendedor.peticiones),
            )
        )

    assert resultados[0] == resultados[1]
    entregado, salio, caso_de_la_conversacion, base_igual, al_grafo, al_modelo = resultados[0]
    assert caso_de_la_conversacion is None and base_igual
    # Lo reconocio como numero de caso --de cualquier aseguradora-- y no se lo dio a nadie: ni al
    # modelo ni al grafo. Sin esto, un numero que el chat no reconociera pasaria por un mensaje
    # corriente, y «igual que uno inventado» se cumpliria por no haber mirado.
    assert (al_grafo, al_modelo) == (0, 0)
    assert salio["text"] == case_number.not_resumed(continuity_enabled=True, language="es")


# --- AC1.19.5: sin continuidad entre canales -------------------------------------------------


@pytest.mark.usefixtures("continuidad_apagada")
async def test_sin_continuidad_el_chat_explica_el_canal_y_no_promete_retomarlo(
    dos_aseguradoras: tuple[str, str], cifrador: Any
) -> None:
    _, propia = dos_aseguradoras
    conversacion, clave = await _conversacion_nueva(propia)
    _, numero = await _caso_de_llamada(propia, clave, cipher=cifrador)

    entregado, cola, grafo, entendedor = await _escribir(propia, conversacion, clave, numero)
    salio = await _lo_que_salio(cola)

    viva = await chat_session.find_live(tenant_id=propia, visitor_key_digest=clave)
    assert viva is not None and viva.case_id is None, "no se ato a ningun caso"
    assert entregado.case_id is None
    assert salio["text"] == case_number.not_resumed(continuity_enabled=False, language="es")
    assert "mismo canal" in salio["text"] and "llam" in salio["text"].lower()
    assert numero not in salio["text"]
    assert grafo.turnos == [] and entendedor.peticiones == []


@pytest.mark.usefixtures("continuidad_apagada")
async def test_sin_continuidad_el_numero_ajeno_recibe_la_misma_explicacion(
    dos_aseguradoras: tuple[str, str], cifrador: Any
) -> None:
    """Sin continuidad la explicacion no depende de que el caso exista: si dijera el canal del
    caso, un desconocido sabria que existe y por donde empezo."""
    _, propia = dos_aseguradoras
    _, dueno = await _conversacion_nueva(propia)
    _, numero_ajeno = await _caso_de_llamada(propia, dueno, cipher=cifrador)
    salidas = []
    for numero in (numero_ajeno, "SA-999999"):
        conversacion, clave = await _conversacion_nueva(propia)
        _, cola, _, _ = await _escribir(propia, conversacion, clave, numero)
        salidas.append(await _lo_que_salio(cola))

    assert salidas[0] == salidas[1]


@pytest.mark.usefixtures("continuidad_apagada")
async def test_sin_continuidad_un_caso_de_chat_del_mismo_navegador_si_se_retoma(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """La continuidad apagada solo quita la voz: el caso que el chat abrio sigue retomandose
    por su numero (BR6.1), tambien despues de empezar de cero."""
    _, propia = dos_aseguradoras
    conversacion, clave = await _conversacion_nueva(propia)
    propio = await nuevo_caso(propia)
    conversacion = await chat_session.attach_case(conversacion, case_id=propio.case_id)
    vista = await casos.get_case(propia, propio.case_id)
    assert vista is not None
    await chat_session.close_session(conversacion, now=AHORA)
    nueva = await chat_session.open_session(
        tenant_id=propia, visitor_key_digest=clave, origin_digest="org", language="es", now=AHORA
    )

    entregado, *_ = await _escribir(propia, nueva, clave, str(vista.case_number))

    assert entregado.case_id == propio.case_id


# --- Lo que el dueno encuentra cuando el caso ya no esta en captura -----------------------------


async def test_un_caso_decidido_se_dice_decidido_y_no_se_ata(
    dos_aseguradoras: tuple[str, str], cifrador: Any
) -> None:
    from ..u14.conftest import nuevo_caso as caso_derivado
    from ..u14.test_correction import _cerrar

    _, propia = dos_aseguradoras
    conversacion, clave = await _conversacion_nueva(propia)
    propio = await nuevo_caso(propia)
    conversacion = await chat_session.attach_case(conversacion, case_id=propio.case_id)
    decidido = await caso_derivado(propia)
    await _cerrar(propia, decidido)
    llamada = await voice_session.open_call(
        tenant_id=propia,
        visitor_key_digest=clave,
        language="es",
        voice_mode=VoiceMode.PRIMARY,
        now=AHORA,
    )
    await voice_session.attach_case(llamada, case_id=decidido)
    vista = await casos.get_case(propia, decidido)
    assert vista is not None

    entregado, cola, grafo, _ = await _escribir(propia, conversacion, clave, str(vista.case_number))

    salio = await _lo_que_salio(cola)
    assert str(vista.case_number) in salio["text"] and "decisión" in salio["text"]
    viva = await chat_session.find_live(tenant_id=propia, visitor_key_digest=clave)
    assert viva is not None and viva.case_id == propio.case_id, "sigue en el caso que tenia"
    assert grafo.turnos == []
    assert entregado.case_id == decidido


async def test_un_caso_en_manos_de_un_ajustador_no_se_ata(
    dos_aseguradoras: tuple[str, str], cifrador: Any
) -> None:
    _, propia = dos_aseguradoras
    conversacion, clave = await _conversacion_nueva(propia)
    caso, numero = await _caso_de_llamada(
        propia, clave, estado=CaseState.DERIVED, con_datos=False, cipher=cifrador
    )

    _, cola, grafo, _ = await _escribir(propia, conversacion, clave, numero)

    salio = await _lo_que_salio(cola)
    assert numero in salio["text"] and "ajustador" in salio["text"]
    viva = await chat_session.find_live(tenant_id=propia, visitor_key_digest=clave)
    assert viva is not None and viva.case_id is None
    assert grafo.turnos == []
    assert caso


# --- La carpeta de cada aseguradora lo enciende ------------------------------------------------


def test_las_tres_aseguradoras_traen_la_continuidad_encendida() -> None:
    cargadas: tuple[TenantConfig, ...] = tenancy_config.loaded().available

    assert len(cargadas) == 3
    assert all(t.voice_to_chat_continuity for t in cargadas)
