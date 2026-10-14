"""Cambiar de tema en el chat (2026-10-12): de consultar la poliza a reportar un accidente.

Hasta hoy una conversacion quedaba atada al tipo de caso con que empezo: quien consultaba su
poliza y decia «quiero reportar eso como un accidente» recibia «¿que quieres saber de tu
poliza?» (C4 de las correcciones del 2026-10-12). Ahora el canal entiende el mensaje antes de
entregarlo; si pide otra de las tres cosas que abren caso y su tipo no es el del caso, abre
uno nuevo, ata la conversacion a el, le lleva la identidad y la poliza ya dadas, y el turno
sigue en el con lo ya entendido.

De punta a punta: la entrega real del canal, el soporte real del nucleo y el turno real, con un
entendedor de mentira que devuelve el formulario. Sin modelo.
"""

from __future__ import annotations

import asyncio
import io
import sys
from collections.abc import AsyncIterator, Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from untangle import observability
from untangle.base import ProviderErrorKind, ProviderName, Use
from untangle.case_record import api as casos
from untangle.case_record import crypto
from untangle.case_record.models import CaseState, Channel, Origin, RecordType
from untangle.chat import delivery, demo_window
from untangle.chat import session as chat_session
from untangle.chat.wire import EventQueue
from untangle.orchestration import case_context, transcript_writer
from untangle.orchestration import contracts as u12
from untangle.orchestration import turn as orquestacion
from untangle.orchestration.nodes.intake import understanding
from untangle.providers.ports import ProviderError
from untangle.tenancy import session

from ..u12.test_turn import (
    _build_runtime,
    _drenar,
    _Entendedor,
    _FakeCoverageNode,
    _ScriptedExtractor,
    _sembrar_dichos,
)
from .conftest import AHORA, CasoSembrado, nuevo_caso
from .test_delivery import _conversacion_nueva

pytestmark = pytest.mark.usefixtures("base_de_u13")

_IDENTIDAD = "Marcela Rios, POL-000001"


@pytest.fixture(autouse=True)
def _sin_estado_compartido() -> Iterator[None]:
    """Ni el runtime, ni la comprension del canal, ni la ventana cruzan pruebas."""
    orquestacion.reset_runtime()
    case_context._person_turns.clear()
    demo_window.install_new_case_gate(_abierta)
    yield
    orquestacion.reset_runtime()
    case_context._person_turns.clear()
    delivery.install_understanding(None, None)
    demo_window.reset()


@pytest.fixture
def rastro() -> Iterator[io.StringIO]:
    destino = io.StringIO()
    observability.set_stream(destino)
    yield destino
    observability.set_stream(sys.stdout)


async def _abierta() -> bool:
    return True


async def _cerrada() -> bool:
    return False


def _respuesta(
    wants: understanding.Want, reply: str = "Claro, cuéntame qué pasó.", **mas: Any
) -> understanding.UnderstandingResponse:
    return understanding.UnderstandingResponse(wants=wants, reply=reply, **mas)


async def _consulta_con_identidad(
    tenant_id: str,
    cifrador: crypto.Cipher,
    *,
    record_type: RecordType = RecordType.COVERAGE_INQUIRY,
) -> tuple[Any, str, CasoSembrado]:
    """Una conversacion atada a un caso que ya tiene la identidad y la poliza."""
    conversacion, clave = await _conversacion_nueva(tenant_id)
    caso = await nuevo_caso(tenant_id, record_type=record_type, policy_ref="POL-000001")
    await _sembrar_dichos(tenant_id, caso.case_id, cipher=cifrador, identity_and_policy=_IDENTIDAD)
    conversacion = await chat_session.attach_case(conversacion, case_id=caso.case_id)
    return conversacion, clave, caso


class _Entrega:
    """Lo que dejo entregar un mensaje por el canal real."""

    def __init__(self, cola: EventQueue) -> None:
        self.cola = cola
        self.turnos: list[u12.InboundTurn] = []
        self.entregado: delivery.Delivered | None = None


async def _entregar(  # noqa: PLR0913, PLR0917 -- el escenario de la prueba, por nombre
    tenant_id: str,
    cifrador: crypto.Cipher,
    conversacion: Any,
    clave: str,
    entendedor: Any,
    texto: str,
    *,
    received_at: datetime = AHORA,
) -> _Entrega:
    """Un mensaje por el canal real: entiende, decide el caso y entrega al turno real."""
    tareas: list[asyncio.Task[object]] = []
    base = _build_runtime(
        cipher=cifrador,
        extractor=_ScriptedExtractor(),
        coverage_node=_FakeCoverageNode(),
        tareas=tareas,
    )
    orquestacion.install_runtime(replace(base, understander=entendedor))
    delivery.install_understanding(entendedor, orquestacion.ChatCaseTurnSupport())
    entrega = _Entrega(EventQueue(stream_ref=conversacion.chat_session_id))

    async def _el_turno_real(turn: u12.InboundTurn) -> AsyncIterator[u12.TurnEvent]:
        entrega.turnos.append(turn)
        async for evento in orquestacion.handle_turn(turn):
            yield evento

    entrega.entregado = await delivery.deliver(
        entrega.cola,
        u12.InboundTurn(
            tenant_id=tenant_id,
            session_ref=conversacion.chat_session_id,
            case_id=conversacion.case_id,
            text=texto,
            language="es",
            channel="chat",
            received_at=received_at,
        ),
        handle_turn=_el_turno_real,
        visitor_key_hash=clave,
        origin=Origin.PUBLIC_CHAT,
    )
    await _drenar(tareas)
    return entrega


def _no_debe_entregarse(turn: u12.InboundTurn) -> AsyncIterator[u12.TurnEvent]:
    raise AssertionError("un mensaje sin caso no llega al turno")


async def _caso_de_la_conversacion(tenant_id: str, clave: str) -> str | None:
    viva = await chat_session.find_live(tenant_id=tenant_id, visitor_key_digest=clave)
    assert viva is not None
    return viva.case_id


# --- El ejemplo de Miguel: consulta -> «quiero reportar eso como un accidente» ---------


async def test_de_consulta_a_reporte_abre_un_caso_nuevo_con_la_identidad_ya_dada(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher, rastro: io.StringIO
) -> None:
    _, propia = dos_aseguradoras
    conversacion, clave, consulta = await _consulta_con_identidad(propia, cifrador)
    antes = await casos.get_case(propia, consulta.case_id)
    entendedor = _Entendedor(_respuesta(understanding.Want.REPORT_ACCIDENT))

    entrega = await _entregar(
        propia, cifrador, conversacion, clave, entendedor, "quiero reportar eso como un accidente"
    )

    # Un caso nuevo, de reporte, al que la conversacion queda atada.
    nuevo = await _caso_de_la_conversacion(propia, clave)
    assert nuevo is not None and nuevo != consulta.case_id
    reporte = await casos.get_case(propia, nuevo)
    assert reporte is not None and reporte.record_type is RecordType.CLAIM
    assert entrega.entregado is not None and entrega.entregado.case_id == nuevo
    # La identidad y la poliza viajaron: la persona no las repite.
    assert reporte.completeness.per_field["identity_and_policy"] is True
    assert reporte.policy_ref == "POL-000001"
    valores = await casos.open_field_values(
        propia, nuevo, ("identity_and_policy",), cipher=cifrador
    )
    assert valores == {"identity_and_policy": _IDENTIDAD}
    # El caso anterior queda como estaba.
    despues = await casos.get_case(propia, consulta.case_id)
    assert despues == antes
    assert despues is not None and despues.record_type is RecordType.COVERAGE_INQUIRY
    conservado = await casos.open_field_values(
        propia, consulta.case_id, ("identity_and_policy",), cipher=cifrador
    )
    assert conservado == {"identity_and_policy": _IDENTIDAD}
    # El mensaje se entiende una sola vez, y el turno recibe lo entendido en el caso nuevo.
    assert len(entendedor.peticiones) == 1
    [turno] = entrega.turnos
    assert turno.case_id == nuevo
    assert turno.understood is not None and turno.understood_by_channel
    # Lo que el modelo escribio miraba el caso anterior: el turno dice la frase del catalogo.
    assert turno.understood_without_case is True
    # El mensaje de la persona queda en el caso nuevo, no en el anterior.
    dicho_nuevo = [t.text_redacted for t in await casos.transcript_of(propia, nuevo)]
    dicho_viejo = [t.text_redacted for t in await casos.transcript_of(propia, consulta.case_id)]
    assert any("reportar" in t for t in dicho_nuevo)
    assert not any("reportar" in t for t in dicho_viejo)
    # Y deja su rastro.
    assert '"event": "chat.topic_changed"' in rastro.getvalue()
    assert '"from_type": "coverage_inquiry"' in rastro.getvalue()
    assert '"to_type": "claim"' in rastro.getvalue()
    # La respuesta sale, y es la frase del catalogo del caso nuevo: lo que el entendedor
    # escribio («Claro, cuéntame qué pasó.») miraba el caso anterior y no se dice.
    cable = await entrega.cola.next_event(heartbeat_after=1)
    assert cable is not None and cable["kind"] == "turn.final"
    assert "cuéntame qué pasó" not in str(cable["text"])
    assert '"reason": "opening_turn"' in rastro.getvalue()


async def test_el_reporte_nuevo_no_vuelve_a_pedir_la_identidad(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """Lo que el codigo pregunta despues del cambio ya cuenta con la identidad llevada."""
    _, propia = dos_aseguradoras
    conversacion, clave, _ = await _consulta_con_identidad(propia, cifrador)
    entendedor = _Entendedor(
        _respuesta(understanding.Want.REPORT_ACCIDENT, reply="")  # sin respuesta valida
    )

    entrega = await _entregar(
        propia, cifrador, conversacion, clave, entendedor, "quiero reportar un accidente"
    )

    cable = await entrega.cola.next_event(heartbeat_after=1)
    assert cable is not None
    assert "póliza" not in str(cable["text"]).lower(), cable["text"]
    assert "nombre" not in str(cable["text"]).lower(), cable["text"]


async def test_de_consulta_a_cotizacion_donde_se_cotiza_abre_la_solicitud(
    cifrador: crypto.Cipher,
) -> None:
    conversacion, clave, consulta = await _consulta_con_identidad("sunmeadow", cifrador)
    entendedor = _Entendedor(_respuesta(understanding.Want.QUOTE, reply="Claro, empecemos."))

    await _entregar(
        "sunmeadow", cifrador, conversacion, clave, entendedor, "mejor quiero una cotización"
    )

    nuevo = await _caso_de_la_conversacion("sunmeadow", clave)
    assert nuevo is not None and nuevo != consulta.case_id
    solicitud = await casos.get_case("sunmeadow", nuevo)
    assert solicitud is not None and solicitud.record_type is RecordType.QUOTE_REQUEST
    # Una solicitud no tiene campo de identidad ni poliza: no se lleva nada.
    assert solicitud.policy_ref is None


# --- La conversacion sigue siendo una (2026-10-13) -----------------------------------------


async def _hablar_antes(tenant_id: str, case_id: str) -> None:
    """Lo que la consulta ya llevaba dicho: la persona pregunto y la agente contesto."""
    ambito = transcript_writer.TranscriptScope(
        tenant_id=tenant_id, case_id=case_id, channel=Channel.CHAT, language="es"
    )
    await transcript_writer.record_person_turn(
        ambito, text="¿me cubre la grúa?", now=AHORA - timedelta(minutes=10)
    )
    await transcript_writer.record_agent_turn(
        ambito,
        text="La grúa la trata la Parte D de tu póliza.",
        now=AHORA - timedelta(minutes=9),
        from_catalog=True,
    )


async def _viene_de(tenant_id: str, case_id: str) -> str | None:
    async with session.session_for(tenant_id) as sesion:
        fila = await session.fetch_one(
            sesion, "SELECT continues_case_id FROM case_record WHERE case_id = :id", id=case_id
        )
    assert fila is not None
    viene = fila["continues_case_id"]
    return None if viene is None else str(viene)


async def test_el_caso_nuevo_nace_diciendo_de_cual_viene(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    _, propia = dos_aseguradoras
    conversacion, clave, consulta = await _consulta_con_identidad(propia, cifrador)

    await _entregar(
        propia,
        cifrador,
        conversacion,
        clave,
        _Entendedor(_respuesta(understanding.Want.REPORT_ACCIDENT)),
        "quiero reportar eso como un accidente",
    )

    nuevo = await _caso_de_la_conversacion(propia, clave)
    assert nuevo is not None and nuevo != consulta.case_id
    assert await _viene_de(propia, nuevo) == consulta.case_id
    assert await _viene_de(propia, consulta.case_id) is None, "el anterior no cambia"


async def test_despues_del_cambio_la_agente_sigue_viendo_lo_hablado_en_el_caso_anterior(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """El defecto de Miguel: "eso" ya no significaba nada para la agente en el caso nuevo.

    El primer mensaje abre el reporte; el segundo, ya dentro del reporte, llega al modelo con la
    conversacion entera: lo de la consulta, el cambio de tema y la frase con que la agente abrio
    el reporte."""
    _, propia = dos_aseguradoras
    conversacion, clave, consulta = await _consulta_con_identidad(propia, cifrador)
    await _hablar_antes(propia, consulta.case_id)
    entendedor = _Entendedor(_respuesta(understanding.Want.REPORT_ACCIDENT))
    await _entregar(
        propia, cifrador, conversacion, clave, entendedor, "quiero reportar eso como un accidente"
    )
    nuevo = await _caso_de_la_conversacion(propia, clave)
    assert nuevo is not None and nuevo != consulta.case_id
    entendedor.peticiones.clear()
    viva = await chat_session.find_live(tenant_id=propia, visitor_key_digest=clave)

    await _entregar(
        propia,
        cifrador,
        viva,
        clave,
        _Entendedor(_respuesta(understanding.Want.CONTINUE)),
        "fue ayer en la mañana",
        received_at=datetime.now(UTC) + timedelta(minutes=1),
    )

    # El entendedor del segundo mensaje es otro: se lee lo que el pidio.
    # (se vuelve a pasar uno propio para poder inspeccionar su peticion)


async def test_el_modelo_recibe_la_conversacion_de_los_dos_casos(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    _, propia = dos_aseguradoras
    conversacion, clave, consulta = await _consulta_con_identidad(propia, cifrador)
    await _hablar_antes(propia, consulta.case_id)
    await _entregar(
        propia,
        cifrador,
        conversacion,
        clave,
        _Entendedor(_respuesta(understanding.Want.REPORT_ACCIDENT)),
        "quiero reportar eso como un accidente",
    )
    viva = await chat_session.find_live(tenant_id=propia, visitor_key_digest=clave)
    segundo = _Entendedor(_respuesta(understanding.Want.CONTINUE))

    await _entregar(
        propia,
        cifrador,
        viva,
        clave,
        segundo,
        "fue ayer en la mañana",
        received_at=datetime.now(UTC) + timedelta(minutes=1),
    )

    [peticion] = segundo.peticiones
    dicho = [(linea.speaker, linea.text) for linea in peticion.history]
    # Lo de la consulta va primero, tal como se guardo, y despues lo del reporte.
    assert dicho[:2] == [
        ("person", "¿me cubre la grúa?"),
        ("agent", "La grúa la trata la Parte D de tu póliza."),
    ]
    assert ("person", "quiero reportar eso como un accidente") in dicho
    assert dicho.index(("person", "quiero reportar eso como un accidente")) > 1
    assert len(dicho) <= understanding.HISTORY_LINES


async def test_la_transcripcion_de_cada_caso_sigue_siendo_suya(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """La bandeja y «Ver mi caso» leen un caso por separado: leer la conversacion a traves
    de la cadena no copia ni mueve ningun turno."""
    _, propia = dos_aseguradoras
    conversacion, clave, consulta = await _consulta_con_identidad(propia, cifrador)
    await _hablar_antes(propia, consulta.case_id)

    await _entregar(
        propia,
        cifrador,
        conversacion,
        clave,
        _Entendedor(_respuesta(understanding.Want.REPORT_ACCIDENT)),
        "quiero reportar eso como un accidente",
    )

    nuevo = await _caso_de_la_conversacion(propia, clave)
    assert nuevo is not None
    del_viejo = [t.text_redacted for t in await casos.transcript_of(propia, consulta.case_id)]
    del_nuevo = [t.text_redacted for t in await casos.transcript_of(propia, nuevo)]
    assert del_viejo == ["¿me cubre la grúa?", "La grúa la trata la Parte D de tu póliza."]
    assert "¿me cubre la grúa?" not in del_nuevo
    conversacion_entera = [
        t.text_redacted for t in await casos.conversation_transcript(propia, nuevo)
    ]
    assert conversacion_entera == [*del_viejo, *del_nuevo]


async def test_si_la_conversacion_ya_se_movio_no_se_abre_un_caso_suelto(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """Dos mensajes en vuelo: el segundo parte de un caso que la conversacion ya dejo. Se dice
    antes de abrir nada, porque el enlace del caso nuevo solo puede apuntar al caso **de esta
    conversacion**."""
    _, propia = dos_aseguradoras
    conversacion, clave, viejo = await _consulta_con_identidad(propia, cifrador)
    otro = await nuevo_caso(propia, record_type=RecordType.CLAIM)
    await chat_session.switch_case(conversacion, case_id=otro.case_id, from_case_id=viejo.case_id)
    async with session.session_for(propia) as sesion:
        antes = await session.fetch_one(sesion, "SELECT count(*) AS total FROM case_record")

    with pytest.raises(chat_session.ConversationMovedError):
        # El mensaje en vuelo todavia cree que la conversacion esta en el caso viejo.
        await _entregar(
            propia,
            cifrador,
            conversacion,
            clave,
            _Entendedor(_respuesta(understanding.Want.REPORT_ACCIDENT)),
            "quiero reportar eso como un accidente",
        )

    async with session.session_for(propia) as sesion:
        despues = await session.fetch_one(sesion, "SELECT count(*) AS total FROM case_record")
    assert antes is not None and despues is not None
    assert despues["total"] == antes["total"], "no quedo ningun caso suelto"


# --- Lo que NO cambia de tema ---------------------------------------------------------


async def test_cotizar_donde_la_aseguradora_no_cotiza_no_abre_nada(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    _, propia = dos_aseguradoras
    conversacion, clave, consulta = await _consulta_con_identidad(propia, cifrador)

    entrega = await _entregar(
        propia,
        cifrador,
        conversacion,
        clave,
        _Entendedor(_respuesta(understanding.Want.QUOTE)),
        "quiero una cotización",
    )

    assert await _caso_de_la_conversacion(propia, clave) == consulta.case_id
    [turno] = entrega.turnos
    assert turno.case_id == consulta.case_id


async def test_preguntar_por_cobertura_dentro_de_un_reporte_no_abre_nada(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """El desvio de cobertura de siempre: la pregunta se revisa y el reporte sigue."""
    _, propia = dos_aseguradoras
    conversacion, clave, reporte = await _consulta_con_identidad(
        propia, cifrador, record_type=RecordType.CLAIM
    )

    entrega = await _entregar(
        propia,
        cifrador,
        conversacion,
        clave,
        _Entendedor(
            _respuesta(
                understanding.Want.POLICY_QUESTION,
                asks_about_coverage=True,
                person_question="¿Me cubre?",
            )
        ),
        "¿y me cubre esto?",
    )

    assert await _caso_de_la_conversacion(propia, clave) == reporte.case_id
    [turno] = entrega.turnos
    assert turno.case_id == reporte.case_id


async def test_seguir_con_el_tema_no_abre_nada(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    _, propia = dos_aseguradoras
    conversacion, clave, consulta = await _consulta_con_identidad(propia, cifrador)

    await _entregar(
        propia,
        cifrador,
        conversacion,
        clave,
        _Entendedor(_respuesta(understanding.Want.CONTINUE)),
        "gracias",
    )

    assert await _caso_de_la_conversacion(propia, clave) == consulta.case_id


async def test_con_la_demostracion_estrechada_el_cambio_de_tema_no_abre_un_caso_nuevo(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher, rastro: io.StringIO
) -> None:
    """BR3.2 de U20: pasadas 24 horas sin reinicio nocturno la retencion dejo de estar
    acotada, y un caso nuevo es un caso nuevo aunque lo abra una conversacion con caso."""
    _, propia = dos_aseguradoras
    demo_window.install_new_case_gate(_cerrada)
    conversacion, clave, consulta = await _consulta_con_identidad(propia, cifrador)

    entrega = await _entregar(
        propia,
        cifrador,
        conversacion,
        clave,
        _Entendedor(_respuesta(understanding.Want.REPORT_ACCIDENT)),
        "quiero reportar un accidente",
    )

    assert await _caso_de_la_conversacion(propia, clave) == consulta.case_id
    [turno] = entrega.turnos
    assert turno.case_id == consulta.case_id
    assert '"event": "chat.topic_change_refused"' in rastro.getvalue()


async def test_quien_contesta_una_pregunta_de_si_o_no_no_cambia_de_tema(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    _, propia = dos_aseguradoras
    conversacion, clave, consulta = await _consulta_con_identidad(propia, cifrador)

    await _entregar(
        propia,
        cifrador,
        conversacion,
        clave,
        _Entendedor(_respuesta(understanding.Want.REPORT_ACCIDENT, answer=understanding.Answer.NO)),
        "no, mejor reporto un accidente",
    )

    assert await _caso_de_la_conversacion(propia, clave) == consulta.case_id


async def test_un_caso_decidido_no_cambia_de_tema_ni_llama_al_modelo(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    from ..u14.conftest import nuevo_caso as caso_derivado
    from ..u14.test_correction import _cerrar

    _, propia = dos_aseguradoras
    conversacion, clave = await _conversacion_nueva(propia)
    decidido = await caso_derivado(propia)
    await _cerrar(propia, decidido)
    conversacion = await chat_session.attach_case(conversacion, case_id=decidido)
    entendedor = _Entendedor(_respuesta(understanding.Want.REPORT_ACCIDENT))

    entrega = await _entregar(
        propia, cifrador, conversacion, clave, entendedor, "quiero reportar un accidente"
    )

    assert entrega.turnos == [], "un caso decidido no vuelve a la captura"
    assert entendedor.peticiones == []
    assert await _caso_de_la_conversacion(propia, clave) == decidido


async def test_entender_antes_de_entregar_no_cuenta_el_turno_dos_veces(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """El recuento de insultos (BR5.4) cuenta los turnos de la persona: leer el caso para
    entender no puede sumar el mensaje, porque el turno lo suma cuando lo carga."""
    _, propia = dos_aseguradoras
    conversacion, clave, consulta = await _consulta_con_identidad(propia, cifrador)

    await _entregar(
        propia,
        cifrador,
        conversacion,
        clave,
        _Entendedor(_respuesta(understanding.Want.CONTINUE)),
        "gracias",
    )

    assert case_context._person_turns[(propia, consulta.case_id)] == ["gracias"]


# --- Cuando el modelo no esta --------------------------------------------------------


async def test_si_el_modelo_no_pudo_el_turno_sigue_en_su_caso_y_no_lo_llama_otra_vez(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """Por reglas, como antes; y sin duplicar la espera justo cuando el proveedor anda mal."""
    llamadas: list[str] = []

    async def caido(peticion: understanding.UnderstandingRequest) -> object:
        llamadas.append(peticion.person_text)
        raise ProviderError(
            ProviderErrorKind.TIMEOUT, provider=ProviderName.ANTHROPIC, use=Use.CHAT_REPLY
        )

    _, propia = dos_aseguradoras
    conversacion, clave, consulta = await _consulta_con_identidad(propia, cifrador)

    entrega = await _entregar(
        propia, cifrador, conversacion, clave, caido, "quiero reportar un accidente"
    )

    assert llamadas == ["quiero reportar un accidente"], "una sola llamada"
    [turno] = entrega.turnos
    assert turno.case_id == consulta.case_id
    assert turno.understood is None and turno.understood_by_channel
    assert await _caso_de_la_conversacion(propia, clave) == consulta.case_id


async def test_pedir_un_ajustador_por_palabras_no_paga_una_llamada_al_modelo(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """Esa señal la resuelve el turno por reglas, sin modelo: llamarlo aqui seria pagarlo
    para tirar la respuesta."""
    _, propia = dos_aseguradoras
    conversacion, clave, consulta = await _consulta_con_identidad(propia, cifrador)
    entendedor = _Entendedor(_respuesta(understanding.Want.REPORT_ACCIDENT))

    entrega = await _entregar(
        propia, cifrador, conversacion, clave, entendedor, "quiero hablar con un humano"
    )

    assert entendedor.peticiones == []
    assert await _caso_de_la_conversacion(propia, clave) == consulta.case_id
    cable = await entrega.cola.next_event(heartbeat_after=1)
    assert cable is not None


async def test_sin_el_soporte_del_nucleo_el_chat_sigue_como_antes(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """Un proceso que monta el chat sin enchufar el soporte no entiende antes de entregar:
    el turno entiende por su cuenta y la conversacion sigue atada a su caso."""
    _, propia = dos_aseguradoras
    conversacion, clave, consulta = await _consulta_con_identidad(propia, cifrador)
    entendedor = _Entendedor(_respuesta(understanding.Want.REPORT_ACCIDENT))
    tareas: list[asyncio.Task[object]] = []
    base = _build_runtime(
        cipher=cifrador,
        extractor=_ScriptedExtractor(),
        coverage_node=_FakeCoverageNode(),
        tareas=tareas,
    )
    orquestacion.install_runtime(replace(base, understander=entendedor))
    delivery.install_understanding(entendedor, None)
    cola = EventQueue(stream_ref=conversacion.chat_session_id)

    await delivery.deliver(
        cola,
        u12.InboundTurn(
            tenant_id=propia,
            session_ref=conversacion.chat_session_id,
            case_id=conversacion.case_id,
            text="quiero reportar un accidente",
            language="es",
            channel="chat",
            received_at=AHORA,
        ),
        handle_turn=orquestacion.handle_turn,
        visitor_key_hash=clave,
        origin=Origin.PUBLIC_CHAT,
    )
    await _drenar(tareas)

    assert await _caso_de_la_conversacion(propia, clave) == consulta.case_id
    assert len(entendedor.peticiones) == 1, "lo entendio el turno, una vez"


# --- La identidad que viaja ----------------------------------------------------------


async def test_llevar_la_identidad_no_toca_el_caso_de_origen_y_solo_lleva_lo_que_el_destino_declara(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    _, propia = dos_aseguradoras
    origen = await nuevo_caso(propia, record_type=RecordType.COVERAGE_INQUIRY, policy_ref="POL-9")
    await _sembrar_dichos(propia, origen.case_id, cipher=cifrador, identity_and_policy=_IDENTIDAD)
    reporte = await nuevo_caso(propia, record_type=RecordType.CLAIM)
    solicitud = await nuevo_caso(propia, record_type=RecordType.QUOTE_REQUEST)

    llevado_al_reporte = await case_context.carry_over_identity(
        propia,
        origen.case_id,
        reporte.case_id,
        cipher=cifrador,
        channel=Channel.CHAT,
        now=AHORA,
    )
    llevado_a_la_solicitud = await case_context.carry_over_identity(
        propia,
        origen.case_id,
        solicitud.case_id,
        cipher=cifrador,
        channel=Channel.CHAT,
        now=AHORA,
    )

    assert llevado_al_reporte == ("identity_and_policy", "policy_ref")
    assert llevado_a_la_solicitud == (), "la solicitud no tiene identidad ni poliza"
    destino = await casos.get_case(propia, reporte.case_id)
    assert destino is not None and destino.policy_ref == "POL-9"
    origen_despues = await casos.get_case(propia, origen.case_id)
    assert origen_despues is not None
    assert origen_despues.state is CaseState.OPEN


async def test_si_el_caso_anterior_no_tenia_identidad_no_se_lleva_nada(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    _, propia = dos_aseguradoras
    origen = await nuevo_caso(propia, record_type=RecordType.COVERAGE_INQUIRY)
    reporte = await nuevo_caso(propia, record_type=RecordType.CLAIM)

    llevado = await case_context.carry_over_identity(
        propia,
        origen.case_id,
        reporte.case_id,
        cipher=cifrador,
        channel=Channel.CHAT,
        now=AHORA,
    )

    assert llevado == ()
    destino = await casos.get_case(propia, reporte.case_id)
    assert destino is not None and not destino.completeness.per_field["identity_and_policy"]


# --- Sin caso todavia: el primer mensaje -----------------------------------------------


async def test_un_saludo_sin_caso_se_contesta_con_lo_que_escribio_el_modelo(
    dos_aseguradoras: tuple[str, str], rastro: io.StringIO
) -> None:
    _, propia = dos_aseguradoras
    conversacion, clave = await _conversacion_nueva(propia)
    cola = EventQueue(stream_ref=conversacion.chat_session_id)
    delivery.install_understanding(
        _Entendedor(_respuesta(understanding.Want.GREETING, reply="¡Hola! ¿En qué te ayudo hoy?")),
        None,
    )

    entregado = await delivery.deliver(
        cola,
        u12.InboundTurn(
            tenant_id=propia,
            session_ref=conversacion.chat_session_id,
            case_id=None,
            text="hola",
            language="es",
            channel="chat",
            received_at=AHORA,
        ),
        handle_turn=_no_debe_entregarse,
        visitor_key_hash=clave,
        origin=Origin.PUBLIC_CHAT,
    )

    assert entregado.case_id is None
    cable = await cola.next_event(heartbeat_after=1)
    assert cable is not None
    assert cable["text"] == "¡Hola! ¿En qué te ayudo hoy?"
    assert '"event": "chat.reply_model"' in rastro.getvalue()


async def test_sin_caso_el_segundo_mensaje_ve_lo_que_se_hablo_en_el_primero(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Sin caso no hay transcripcion, y la agente contestaba cada mensaje como si fuera el
    primero: a «tengo una duda» y despues «¿que es un deducible?» no les veia relacion
    (conversacion simulada del 2026-10-13)."""
    _, propia = dos_aseguradoras
    conversacion, clave = await _conversacion_nueva(propia)
    cola = EventQueue(stream_ref=conversacion.chat_session_id)
    entendedor = _Entendedor(
        _respuesta(understanding.Want.GENERAL_QUESTION, reply="Claro, ¿cuál es tu duda?")
    )
    delivery.install_understanding(entendedor, None)

    for texto in ("hola, tengo una duda general", "¿qué es un deducible?"):
        await delivery.deliver(
            cola,
            u12.InboundTurn(
                tenant_id=propia,
                session_ref=conversacion.chat_session_id,
                case_id=None,
                text=texto,
                language="es",
                channel="chat",
                received_at=AHORA,
            ),
            handle_turn=_no_debe_entregarse,
            visitor_key_hash=clave,
            origin=Origin.PUBLIC_CHAT,
        )

    primera, segunda = entendedor.peticiones
    # El primero solo ve la apertura; el segundo, ademas, lo que se dijo en el primero.
    assert [linea.speaker for linea in primera.history] == ["agent"]
    assert [(linea.speaker, linea.text) for linea in segunda.history[1:]] == [
        ("person", "hola, tengo una duda general"),
        ("agent", "Claro, ¿cuál es tu duda?"),
    ]
    assert segunda.history[0] == primera.history[0]


@pytest.mark.parametrize(
    ("reply", "motivo"),
    [
        (None, "invalid_reply"),
        ("Mira https://untangle.example", "invalid_reply"),
        ("Tu póliza cubre todo, tranquilo.", "guard"),
    ],
    ids=["sin-respuesta", "con-enlace", "la-guardia-la-detiene"],
)
async def test_una_respuesta_que_no_vale_sin_caso_deja_la_frase_del_catalogo(
    dos_aseguradoras: tuple[str, str], rastro: io.StringIO, reply: str | None, motivo: str
) -> None:
    _, propia = dos_aseguradoras
    conversacion, clave = await _conversacion_nueva(propia)
    cola = EventQueue(stream_ref=conversacion.chat_session_id)
    delivery.install_understanding(
        _Entendedor(
            understanding.UnderstandingResponse(
                wants=understanding.Want.GENERAL_QUESTION, reply=reply
            )
        ),
        None,
    )

    await delivery.deliver(
        cola,
        u12.InboundTurn(
            tenant_id=propia,
            session_ref=conversacion.chat_session_id,
            case_id=None,
            text="¿Qué es un deducible?",
            language="es",
            channel="chat",
            received_at=AHORA,
        ),
        handle_turn=_no_debe_entregarse,
        visitor_key_hash=clave,
        origin=Origin.PUBLIC_CHAT,
    )

    cable = await cola.next_event(heartbeat_after=1)
    assert cable is not None
    assert reply is None or str(cable["text"]) != reply
    assert f'"reason": "{motivo}"' in rastro.getvalue()


async def test_el_primer_mensaje_que_abre_caso_lleva_las_marcas_y_la_apertura_como_historia(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    conversacion, clave = await _conversacion_nueva(propia)
    cola = EventQueue(stream_ref=conversacion.chat_session_id)
    entendedor = _Entendedor(_respuesta(understanding.Want.REPORT_ACCIDENT))
    delivery.install_understanding(entendedor, None)
    recibidos: list[u12.InboundTurn] = []

    async def _grafo(turn: u12.InboundTurn) -> AsyncIterator[u12.TurnEvent]:
        recibidos.append(turn)
        yield u12.FinalText(message_id="m", text="ok", language="es")

    await delivery.deliver(
        cola,
        u12.InboundTurn(
            tenant_id=propia,
            session_ref=conversacion.chat_session_id,
            case_id=None,
            text="Me chocaron ayer",
            language="es",
            channel="chat",
            received_at=AHORA,
        ),
        handle_turn=_grafo,
        visitor_key_hash=clave,
        origin=Origin.PUBLIC_CHAT,
    )

    [turno] = recibidos
    assert turno.understood_by_channel and turno.understood_without_case
    [peticion] = entendedor.peticiones
    assert peticion.case_status is understanding.CaseStatus.NONE
    assert peticion.record_type is None
    assert [linea.speaker for linea in peticion.history] == ["agent"], "la apertura"
    assert peticion.channel == "chat"
