"""Entregar un turno al grafo y poner de vuelta lo que salga (BR2.5, BR6.4, REL-U13.1).

Con base de datos porque la mitad de lo que hay que comprobar es que el turno queda
escrito en la transcripcion **con su canal**, y eso no se ve sin la tabla.

El grafo entra **por su puerto**, no parcheando un modulo: `deliver` lo recibe por
argumento porque el contrato de importacion del proyecto no deja que un canal llegue
al runtime ni por transitividad. La prueba se aprovecha de lo mismo que la
arquitectura gano: inyectar un doble es pasar un argumento.

Lo que aqui se prueba es la entrega --que todo evento llega al cable, que el error
tambien, y que la pestana que se va no tumba el turno--, no lo que el grafo decide,
que tiene sus propias pruebas en U12.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

from untangle.base import Locale, Use
from untangle.case_record import api as casos
from untangle.case_record import crypto
from untangle.case_record.models import Origin, RecordType
from untangle.chat import delivery, opening, stream
from untangle.chat import session as chat_session
from untangle.chat.wire import MAX_PENDING, EventQueue
from untangle.compliance.controls.api import HandoffReason
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey
from untangle.orchestration import contracts as u12
from untangle.orchestration import turn as orquestacion
from untangle.orchestration.nodes.intake import understanding
from untangle.orchestration.nodes.intake.node import IntakeNode
from untangle.orchestration.nodes.policy_verification.node import PolicyVerificationNode
from untangle.server import composition
from untangle.settings import Settings
from untangle.telemetry.traces import api as trazas
from untangle.tenancy import api as tenancy
from untangle.tenancy import ephemeral, session

from .conftest import AHORA, CasoSembrado, nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u13")


def _turno(tenant_id: str, case_id: str | None, texto: str = "Me chocaron") -> u12.InboundTurn:
    return u12.InboundTurn(
        tenant_id=tenant_id,
        session_ref="chat-1",
        case_id=case_id,
        text=texto,
        language="es",
        channel="chat",
        received_at=AHORA,
    )


def _turno_de(
    conversacion: Any, case_id: str | None, texto: str, *, language: Locale = "es"
) -> u12.InboundTurn:
    """Un turno de una conversacion de verdad, con su referencia de sesion."""
    return u12.InboundTurn(
        tenant_id=conversacion.tenant_id,
        session_ref=conversacion.chat_session_id,
        case_id=case_id,
        text=texto,
        language=language,
        channel="chat",
        received_at=AHORA,
    )


def _grafo_que_devuelve(*eventos: u12.TurnEvent) -> Any:
    """Un doble de `handle_turn` que emite lo que se le diga y nada mas."""

    async def falso(entrante: u12.InboundTurn) -> AsyncIterator[u12.TurnEvent]:
        del entrante
        for evento in eventos:
            yield evento

    return falso


_FINAL = u12.FinalText(message_id="m1", text="Anotado.", language="es")
_PARCIAL = u12.PartialText(message_id="m1", seq=1, text="Ano")
_ERROR = u12.TurnError(
    code="internal_error", copy_key=CopyKey("chat.turn.error"), text="Tuve un problema."
)
_DERIVA = u12.Handoff(
    reason_code=HandoffReason.HUMAN_REQUEST,
    copy_key=CopyKey("compliance.handoff.adjuster_review"),
    text="Un ajustador revisa su caso.",
)


#: El resumen de la clave del navegador, que es lo que ata el resumen de traza a
#: quien lo produjo. Un valor cualquiera con la forma de un resumen: lo que aqui se
#: comprueba es que viaje, no como se calcula --eso es de U2 y tiene sus pruebas--.
CLAVE_DEL_NAVEGADOR = "a" * 64

# --- Todo evento llega al cable -----------------------------------------------


async def test_los_eventos_del_grafo_llegan_al_cable_en_orden(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    cola = EventQueue(stream_ref="chat-1")

    entregado = await delivery.deliver(
        cola,
        _turno(propia, caso.case_id),
        handle_turn=_grafo_que_devuelve(_PARCIAL, _FINAL),
        visitor_key_hash=CLAVE_DEL_NAVEGADOR,
        origin=Origin.PUBLIC_CHAT,
    )

    assert entregado.events == 2
    assert entregado.closed, "el final cierra el turno"
    assert [(await cola.next_event(heartbeat_after=1))["kind"] for _ in range(2)] == [  # type: ignore[index]
        "turn.partial",
        "turn.final",
    ]


@pytest.mark.parametrize(
    ("nombre", "evento"), [("error", _ERROR), ("derivacion", _DERIVA), ("final", _FINAL)]
)
async def test_cada_uno_de_los_tres_finales_cierra_el_turno(
    dos_aseguradoras: tuple[str, str],
    nombre: str,
    evento: u12.TurnEvent,
) -> None:
    """REL-U13.1. El del error importa mas que los otros dos: un camino que se lo
    tragara dejaria la conversacion colgada sin decir nada."""
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    cola = EventQueue(stream_ref="chat-1")

    entregado = await delivery.deliver(
        cola,
        _turno(propia, caso.case_id),
        handle_turn=_grafo_que_devuelve(evento),
        visitor_key_hash=CLAVE_DEL_NAVEGADOR,
        origin=Origin.PUBLIC_CHAT,
    )

    assert entregado.closed, nombre
    assert entregado.events == 1


async def test_un_turno_sin_ningun_evento_no_se_declara_cerrado(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """El control negativo: si `closed` fuera siempre `True`, las pruebas de
    arriba pasarian con una entrega que no entrega nada."""
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    cola = EventQueue(stream_ref="chat-1")

    entregado = await delivery.deliver(
        cola,
        _turno(propia, caso.case_id),
        handle_turn=_grafo_que_devuelve(),
        visitor_key_hash=CLAVE_DEL_NAVEGADOR,
        origin=Origin.PUBLIC_CHAT,
    )

    assert not entregado.closed
    assert entregado.events == 0


# --- BR6.4: el turno queda escrito, con su canal ------------------------------


async def test_el_turno_de_la_persona_queda_en_la_transcripcion_con_su_canal(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Un caso empezado por voz y seguido por chat es un solo caso, y lo que
    distingue sus turnos es este campo."""
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    entregado = await delivery.deliver(
        EventQueue(stream_ref="chat-1"),
        _turno(propia, caso.case_id),
        handle_turn=_grafo_que_devuelve(_FINAL),
        visitor_key_hash=CLAVE_DEL_NAVEGADOR,
        origin=Origin.PUBLIC_CHAT,
    )

    assert entregado.turn_id is not None
    async with session.session_for(propia) as sesion:
        fila = await session.fetch_one(
            sesion,
            "SELECT channel, speaker FROM case_transcript_turn WHERE turn_id = :id",
            id=entregado.turn_id,
        )
    assert fila is not None
    assert fila["channel"] == "chat"
    assert fila["speaker"] == "insured"


async def test_un_turno_sin_conversacion_viva_no_abre_ningun_caso(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Se comprueba **antes** de abrir: un caso que ninguna conversacion reclama es
    un caso que el turno siguiente duplica.

    El resumen de clave de esta prueba no corresponde a ninguna conversacion, que es
    exactamente lo que no deberia poder pasar: quien entrega acaba de resolver la
    conversacion de ese navegador. Falla nombrando la sesion, y el control esta en
    que **no queda ningun caso** en la aseguradora.
    """
    _, propia = dos_aseguradoras
    with pytest.raises(delivery.ConversationNotFoundError):
        await delivery.deliver(
            EventQueue(stream_ref="chat-1"),
            _turno(propia, None),
            handle_turn=_grafo_que_devuelve(_FINAL),
            visitor_key_hash=CLAVE_DEL_NAVEGADOR,
            origin=Origin.PUBLIC_CHAT,
        )

    async with session.session_for(propia) as sesion:
        fila = await session.fetch_one(sesion, "SELECT count(*) AS n FROM case_record")
    assert fila is not None
    assert fila["n"] == 0, "se abrio un caso que ninguna conversacion puede reclamar"


async def test_lo_que_se_persiste_va_redactado(dos_aseguradoras: tuple[str, str]) -> None:
    """El tipo lo impone --`append_turn` exige `Redacted`-- y esta prueba lo mira
    en la fila. La columna se llama `text_redacted`, que es U4 diciendo la misma
    invariante por tercera vez: en el tipo, en el nombre y aqui."""
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    entregado = await delivery.deliver(
        EventQueue(stream_ref="chat-1"),
        _turno(propia, caso.case_id, "Mi placa es ABC123 y mi telefono el 3001234567"),
        handle_turn=_grafo_que_devuelve(_FINAL),
        visitor_key_hash=CLAVE_DEL_NAVEGADOR,
        origin=Origin.PUBLIC_CHAT,
    )

    async with session.session_for(propia) as sesion:
        fila = await session.fetch_one(
            sesion,
            "SELECT text_redacted FROM case_transcript_turn WHERE turn_id = :id",
            id=entregado.turn_id,
        )
    assert fila is not None
    assert "ABC123" not in fila["text_redacted"]
    assert "3001234567" not in fila["text_redacted"]


# --- La pestana que se fue a mitad del turno ----------------------------------


async def test_si_la_pestana_se_fue_el_turno_no_revienta(dos_aseguradoras: tuple[str, str]) -> None:
    """El trabajo de fondo sigue su curso y el caso queda igual; lo que se acabo
    es a quien entregarselo. Levantar aqui convertiria una pestana cerrada en un
    turno fallido."""
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    muchos = [u12.PartialText(message_id="m", seq=n, text="x") for n in range(MAX_PENDING + 5)]
    cola = EventQueue(stream_ref="chat-1")

    entregado = await delivery.deliver(
        cola,
        _turno(propia, caso.case_id),
        handle_turn=_grafo_que_devuelve(*muchos),
        visitor_key_hash=CLAVE_DEL_NAVEGADOR,
        origin=Origin.PUBLIC_CHAT,
    )

    assert entregado.events == MAX_PENDING, "se entrego lo que cabia y se paro ahi"
    assert not entregado.closed
    assert cola.closed


# --- El resumen de traza queda abierto (BR4.3) --------------------------------


def _grafo_dentro_de_su_tramo(
    tenant_id: str, case_id: str, *eventos: u12.TurnEvent
) -> delivery.TurnHandler:
    """Un grafo que entrega **desde dentro de su tramo de turno**, como el de verdad.

    Importa que sea asi y no un doble plano: el identificador de traza vive en el
    contexto del tramo, y lo que esta prueba comprueba es justamente que la entrega
    lo alcanza mientras el generador sigue suspendido ahi dentro.
    """

    async def _handle(turn: u12.InboundTurn) -> AsyncIterator[u12.TurnEvent]:
        with trazas.turn_span(tenant_id=tenant_id, case_id=case_id, use=Use.CHAT):
            for evento in eventos:
                yield evento

    return _handle


async def test_el_turno_deja_abierto_el_resumen_de_traza_de_este_navegador(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """U5 construyo toda la maquinaria del resumen y **nadie la estrenaba**: no habia
    un solo `open_summary` en produccion, asi que la tabla estaba vacia y la pagina
    del resumen habria dicho "no encontrado" siempre. Lo abre el canal porque el
    resumen se ata a la clave del navegador, que no conoce nadie mas."""
    trazas.reset_summaries()
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    cola = EventQueue(stream_ref="chat-1")

    await delivery.deliver(
        cola,
        _turno(propia, caso.case_id),
        handle_turn=_grafo_dentro_de_su_tramo(propia, caso.case_id, _FINAL),
        visitor_key_hash=CLAVE_DEL_NAVEGADOR,
        origin=Origin.PUBLIC_CHAT,
    )

    resumen = await trazas.trace_summary_for(
        caso.case_id, tenant_id=propia, visitor_key_hash=CLAVE_DEL_NAVEGADOR
    )
    assert resumen is not None, "sin esto la pagina del resumen no tendria nada que leer"
    assert resumen.case_id == caso.case_id


async def test_el_resumen_abierto_no_lo_ve_otro_navegador(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """La clave con la que se abre es la que decide quien lo ve: abrirlo con una
    cualquiera dejaria el resumen de una conversacion a la vista de la de al lado."""
    trazas.reset_summaries()
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)

    await delivery.deliver(
        EventQueue(stream_ref="chat-1"),
        _turno(propia, caso.case_id),
        handle_turn=_grafo_dentro_de_su_tramo(propia, caso.case_id, _FINAL),
        visitor_key_hash=CLAVE_DEL_NAVEGADOR,
        origin=Origin.PUBLIC_CHAT,
    )

    # El control positivo primero: sin el, esta prueba pasa igual con una entrega
    # que no abra ningun resumen, que es exactamente lo que estaba pasando antes.
    del_dueno = await trazas.trace_summary_for(
        caso.case_id, tenant_id=propia, visitor_key_hash=CLAVE_DEL_NAVEGADOR
    )
    del_otro = await trazas.trace_summary_for(
        caso.case_id, tenant_id=propia, visitor_key_hash="z" * 64
    )

    assert del_dueno is not None
    assert del_otro is None


# --- El caso nace en el primer turno (BR1.1) ----------------------------------


async def _conversacion_nueva(tenant_id: str, *, language: Locale = "es") -> tuple[Any, str]:
    """Una conversacion viva de un navegador, sin caso todavia."""
    visitante = await tenancy.resolve_visitor_key(
        tenant_id=tenant_id, visitor_key=tenancy.new_visitor_key(), origin="prueba"
    )
    conversacion = await chat_session.open_session(
        tenant_id=tenant_id,
        visitor_key_digest=visitante.visitor_key_hash,
        origin_digest=visitante.origin,
        language=language,
        now=AHORA,
    )
    assert conversacion.case_id is None, "el control: nace sin caso"
    return conversacion, visitante.visitor_key_hash


async def test_el_primer_turno_abre_el_caso_y_el_grafo_lo_recibe(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """El defecto que dejo el chat sin poder atender a nadie, con su prueba.

    Tres unidades correctas por dentro y la costura entre ellas sin dueno: U11
    construyo `open_case` y nadie la llamaba, U12 exige `case_id` y levanta si
    falta, U13 entregaba el turno con nulo confiando en que "el grafo lo dira por su
    cuenta si lo necesitaba". El primer mensaje de cualquier visitante moria en una
    tarea que nadie esperaba y la pantalla se quedaba muda.

    Se comprueba lo que de verdad importaba y ninguna prueba miraba: **que el grafo
    recibe un turno con caso**. Sin esa asercion, un `deliver` que abriera el caso y
    siguiera entregando el turno sin el pasaria igual.
    """
    trazas.reset_summaries()
    _, propia = dos_aseguradoras
    conversacion, clave = await _conversacion_nueva(propia)

    recibidos: list[str | None] = []

    async def _grafo_que_anota(turn: u12.InboundTurn) -> AsyncIterator[u12.TurnEvent]:
        recibidos.append(turn.case_id)
        yield _FINAL

    entregado = await delivery.deliver(
        EventQueue(stream_ref=conversacion.chat_session_id),
        _turno_de(conversacion, None, "Me chocaron"),
        handle_turn=_grafo_que_anota,
        visitor_key_hash=clave,
        origin=Origin.PUBLIC_CHAT,
    )

    assert entregado.case_id is not None
    assert recibidos == [entregado.case_id], "el grafo recibio el turno sin caso"

    # Y la conversacion lo aprendio: sin esto el turno siguiente vuelve sin caso y
    # cada mensaje parece una conversacion nueva.
    viva = await chat_session.find_live(tenant_id=propia, visitor_key_digest=clave)
    assert viva is not None
    assert viva.case_id == entregado.case_id

    # La transcripcion se escribe desde el primer turno, que es lo que DS-7 necesita.
    assert entregado.turn_id is not None


async def test_el_tipo_del_caso_lo_decide_el_primer_mensaje(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """BR1.1: preguntar por cobertura abre una consulta; contar un choque, un siniestro.

    Los dos lados, porque con uno solo la prueba pasa igual contra un codigo que
    abra siempre el mismo tipo. La diferencia no es cosmetica: un siniestro trae
    siete campos con la pregunta de seguridad (AC1.5.1) y una consulta dos sin ella
    (AC1.3.6), y la completitud de la bandeja sale de ahi.
    """
    _, propia = dos_aseguradoras

    async def _abrir(texto: str, *, language: Locale) -> str:
        conversacion, clave = await _conversacion_nueva(propia, language=language)
        entregado = await delivery.deliver(
            EventQueue(stream_ref=conversacion.chat_session_id),
            _turno_de(conversacion, None, texto, language=language),
            handle_turn=_grafo_que_devuelve(_FINAL),
            visitor_key_hash=clave,
            origin=Origin.PUBLIC_CHAT,
        )
        assert entregado.case_id is not None
        return entregado.case_id

    # Los dos idiomas, porque el reconocedor es bilingue y la paridad es regla del
    # proyecto: una prueba en un solo idioma pasa igual con el patron del otro roto.
    casos_abiertos = {
        ("es", "claim"): await _abrir("Me chocaron ayer", language="es"),
        ("es", "inquiry"): await _abrir("¿Mi póliza cubre el granizo?", language="es"),
        ("en", "claim"): await _abrir("Someone rear-ended me yesterday", language="en"),
        ("en", "inquiry"): await _abrir("Does my policy cover hail?", language="en"),
    }
    vistas = {
        clave: await casos.get_case(propia, case_id) for clave, case_id in casos_abiertos.items()
    }

    for (idioma, clase), vista in vistas.items():
        assert vista is not None
        esperado = RecordType.CLAIM if clase == "claim" else RecordType.COVERAGE_INQUIRY
        assert vista.record_type is esperado, f"{idioma}/{clase} abrio el tipo equivocado"

    # Y la diferencia no es cosmetica: la consulta tiene menos campos que llenar.
    siniestro, consulta = vistas[("es", "claim")], vistas[("es", "inquiry")]
    assert siniestro is not None
    assert consulta is not None
    assert consulta.completeness.total < siniestro.completeness.total


async def test_el_segundo_turno_no_abre_un_segundo_caso(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Una conversacion tiene un caso. El segundo turno llega con el suyo y no abre otro."""
    _, propia = dos_aseguradoras
    conversacion, clave = await _conversacion_nueva(propia)

    primero = await delivery.deliver(
        EventQueue(stream_ref=conversacion.chat_session_id),
        _turno_de(conversacion, None, "Me chocaron"),
        handle_turn=_grafo_que_devuelve(_FINAL),
        visitor_key_hash=clave,
        origin=Origin.PUBLIC_CHAT,
    )
    segundo = await delivery.deliver(
        EventQueue(stream_ref=conversacion.chat_session_id),
        _turno_de(conversacion, primero.case_id, "Fue en la autopista"),
        handle_turn=_grafo_que_devuelve(_FINAL),
        visitor_key_hash=clave,
        origin=Origin.PUBLIC_CHAT,
    )

    assert segundo.case_id == primero.case_id
    async with session.session_for(propia) as sesion:
        fila = await session.fetch_one(sesion, "SELECT count(*) AS n FROM case_record")
    assert fila is not None
    assert fila["n"] == 1, "la conversacion acabo con mas de un caso"


async def test_el_origen_del_caso_es_el_que_pide_quien_entrega(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """El origen decide que borra el reinicio nocturno (BR4.6 de U4).

    El chat publico abre `public_chat` y una corrida de evaluaciones
    `local_deployment`. Se comprueba el segundo, que es el que un valor por omision
    se habria comido: un caso de una corrida marcado como dato de visitante
    desaparece en el reinicio, y uno de una persona marcado como local se queda para
    siempre.
    """
    _, propia = dos_aseguradoras
    conversacion, clave = await _conversacion_nueva(propia)

    entregado = await delivery.deliver(
        EventQueue(stream_ref=conversacion.chat_session_id),
        _turno_de(conversacion, None, "Me chocaron"),
        handle_turn=_grafo_que_devuelve(_FINAL),
        visitor_key_hash=clave,
        origin=Origin.LOCAL_DEPLOYMENT,
    )

    async with session.session_for(propia) as sesion:
        fila = await session.fetch_one(
            sesion,
            "SELECT origin FROM case_record WHERE case_id = :id",
            id=entregado.case_id,
        )
    assert fila is not None
    assert fila["origin"] == Origin.LOCAL_DEPLOYMENT.value


# --- Ningun fallo de la entrega muere en silencio (REL-U13.1) ------------------


async def test_un_fallo_de_la_entrega_llega_a_la_pantalla_y_se_relanza(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """El segundo defecto, y el peor: el fallo era **invisible**.

    El `POST` respondia 202, la excepcion moria en una tarea que nadie esperaba y la
    pantalla se quedaba muda -- ni la frase de degradacion del catalogo, ni un error.
    Ahora el navegador recibe un evento que **cierra el turno** con la clave del
    catalogo (REL-U13.1) y la excepcion se relanza, para que quien entrega no
    confunda un turno roto con uno atendido.

    Se comprueba la clave y no el texto: el cable manda la clave y la resuelve el
    navegador, y afirmar el texto aqui seria escribirlo por segunda vez.
    """
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    cola = EventQueue(stream_ref="chat-1")

    async def _grafo_que_revienta(turn: u12.InboundTurn) -> AsyncIterator[u12.TurnEvent]:
        # Revienta **a mitad**, despues de haber entregado un fragmento: es la forma
        # peor y la que de verdad pasaba, porque deja la pantalla con media respuesta
        # y sin nada que cierre el turno.
        assert turn.case_id is not None
        yield _PARCIAL
        msg = "el grafo reventó (inyectado por la prueba)"
        raise RuntimeError(msg)

    with pytest.raises(RuntimeError):
        await delivery.deliver(
            cola,
            _turno(propia, caso.case_id),
            handle_turn=_grafo_que_revienta,
            visitor_key_hash=CLAVE_DEL_NAVEGADOR,
            origin=Origin.PUBLIC_CHAT,
        )

    # Se vacia la cola: el fragmento ya iba dentro, y lo que importa es **con que
    # termina**. Un turno que deja media respuesta y nada que lo cierre es el defecto.
    entregados: list[dict[str, object]] = []
    while len(entregados) < 5:
        evento = await cola.next_event(heartbeat_after=0.05)
        if evento is None:
            break
        entregados.append(evento)

    assert entregados, "la pantalla se quedo sin recibir nada"
    ultimo = entregados[-1]
    assert ultimo["kind"] == stream.ERROR
    assert ultimo["copy_key"] == str(delivery.DELIVERY_ERROR)
    assert stream.closes_turn(ultimo), "el navegador seguiria esperando"


# --- El recorrido con el grafo de verdad, y la raiz que lo enchufa -------------
#
# **Esto es lo que faltaba, y por eso el chat nunca atendio a nadie.** Las 2.363
# pruebas del proyecto que tocan el canal enchufan un doble de `handle_turn`, y el
# doble aceptaba un turno sin caso. El de verdad lo exige y levanta. Encima, nadie
# llamaba a `install_runtime`: el segundo muro, escondido detras del primero.
#
# Las dos pruebas de abajo cierran los dos, y **corren en cada entrega**: ninguna
# llama a ningun proveedor. El caso de golden set de punta a punta
# (`DS-2/es/chat-claim-end-to-end`) si lo necesita, y por eso queda fuera del
# subconjunto de arranque; esta mitad no.


@pytest.fixture
async def raiz_con_grafo_real(
    sesiones: ephemeral.EphemeralDatabase, tmp_path: Path
) -> AsyncIterator[None]:
    """La raiz de composicion de verdad, con todo lo que enchufa.

    No se sustituye nada: es el mismo `build_app` que corre `mise run dev`. Lleva la
    clave de cifrado porque los puntos de control del grafo van cifrados, y una de
    marca porque aqui no se llama a ningun proveedor.
    """
    ajustes = Settings(
        env="local",
        database_url=sesiones.app_url,
        commit_sha="abc1234",
        chat_model_api_key="marca-de-clave-de-chat-que-no-se-usa-0001",
        case_field_encryption_key=crypto.generate_key(),
    )
    composition.build_app(ajustes, dist_dir=tmp_path)
    try:
        yield
    finally:
        orquestacion.reset_runtime()
        crypto.reset()
        await session.dispose()
        session.configure(sesiones.app_url)
        copy_api.reset()


async def test_la_raiz_de_composicion_deja_el_grafo_y_el_cifrador_enchufados(
    raiz_con_grafo_real: None,
) -> None:
    """El defecto que estaba **detras** del primero: nadie enchufaba nada.

    `install_runtime` y `crypto.install` no tenian un solo llamador en produccion.
    El primero dejaba el chat sin poder atender ni un turno con caso; el segundo
    dejaba la correccion de un campo en la bandeja fallando con "no hay cifrador
    instalado". Los dos existian, documentados, esperando a esta raiz.
    """
    del raiz_con_grafo_real
    runtime = orquestacion.get_runtime()

    # El ritmo del turno, real: el nodo de U11, no un doble.
    assert isinstance(runtime.intake, IntakeNode)
    # Y el cifrador del proceso, que es lo que el punto de control necesita.
    assert crypto.active().id == runtime.cipher.id
    # El grafo de fondo compilado **no** esta: sus tres enlaces necesitan entradas que
    # `GraphState` no lleva. Lo que si esta es el nodo de cobertura, que corre por el
    # ejecutor directo porque su entrada depende del caso -- la misma razon escrita
    # para `intake`--, y es lo que hace que preguntar por cobertura tenga respuesta.
    assert runtime.background_graph is None
    assert isinstance(runtime.coverage, PolicyVerificationNode)
    assert runtime.build_coverage_input is not None, (
        "un nodo sin quien le arme la entrada no se puede ejecutar"
    )


async def test_el_grafo_de_verdad_atiende_el_primer_turno_sin_llamar_a_ningun_proveedor(
    raiz_con_grafo_real: None,
    dos_aseguradoras: tuple[str, str],
) -> None:
    """**La compuerta que habria cazado el defecto el primer dia.**

    Nada sustituido entre el canal y el grafo: `deliver` abre el caso, se lo entrega
    a `handle_turn` de U12 --el de verdad, con el runtime que enchufo la raiz-- y lo
    que vuelve pasa por el punto unico de salida y llega al cable.

    **No gasta un centimo.** El texto pide hablar con una persona: es una senal que
    U10 reconoce con sus patrones versionados, y el turno deriva sin llegar al nodo
    de captura, que es el unico sitio del ritmo del turno que llama al modelo. La
    clave de proveedor de este fixture es una marca; si algo la usara, la llamada
    fallaria y esta prueba lo diria.
    """
    del raiz_con_grafo_real
    _, propia = dos_aseguradoras
    conversacion, clave = await _conversacion_nueva(propia)
    cola = EventQueue(stream_ref=conversacion.chat_session_id)

    entregado = await delivery.deliver(
        cola,
        _turno_de(conversacion, None, "Quiero hablar con una persona"),
        handle_turn=orquestacion.handle_turn,
        visitor_key_hash=clave,
        origin=Origin.PUBLIC_CHAT,
    )

    assert entregado.case_id is not None, "el canal no abrio el caso"
    assert entregado.closed, "el turno quedo abierto: la pantalla seguiria esperando"

    evento = await cola.next_event(heartbeat_after=0.05)
    assert evento is not None, "la pantalla no recibio nada, que es el defecto"
    # Una derivacion, no un error: el turno se **atendio**. Con el defecto presente
    # esta linea leia un `turn.error` --o nada en absoluto--.
    assert evento["kind"] == stream.HANDOFF, f"el turno no se atendio: {evento}"
    assert evento["case_id"] == entregado.case_id
    assert evento["copy_key"], "la frase sale del catalogo, no del codigo"


async def test_un_saludo_suelto_pregunta_en_que_ayudar_y_no_abre_caso(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Decision de Miguel del 2026-10-07: un "hola" ya no es un accidente.

    Antes el saludo abria un siniestro y la agente preguntaba si habia heridos.
    Ahora se contesta en que se puede ayudar, sin caso y sin pasar por el grafo,
    y el caso nace con el mensaje siguiente, con el tipo que ese mensaje diga.
    """
    _, propia = dos_aseguradoras
    conversacion, clave = await _conversacion_nueva(propia)
    cola = EventQueue(stream_ref=conversacion.chat_session_id)
    recibidos: list[str | None] = []

    async def _grafo_que_anota(turn: u12.InboundTurn) -> AsyncIterator[u12.TurnEvent]:
        recibidos.append(turn.case_id)
        yield _FINAL

    saludo = await delivery.deliver(
        cola,
        _turno_de(conversacion, None, "Hola, buenas tardes"),
        handle_turn=_grafo_que_anota,
        visitor_key_hash=clave,
        origin=Origin.PUBLIC_CHAT,
    )

    assert saludo.case_id is None
    assert recibidos == [], "el saludo no pasa por el grafo"
    cable = await cola.next_event(heartbeat_after=1)
    assert cable is not None
    assert str(cable["text"]).startswith("¡Hola! ¿Quieres reportar un accidente")
    viva = await chat_session.find_live(tenant_id=propia, visitor_key_digest=clave)
    assert viva is not None
    assert viva.case_id is None

    pedido = await delivery.deliver(
        cola,
        _turno_de(conversacion, None, "¿Mi póliza cubre el granizo?"),
        handle_turn=_grafo_que_anota,
        visitor_key_hash=clave,
        origin=Origin.PUBLIC_CHAT,
    )

    assert pedido.case_id is not None
    assert recibidos == [pedido.case_id]
    vista = await casos.get_case(propia, pedido.case_id)
    assert vista is not None
    assert vista.record_type.value == "coverage_inquiry"


# --- Fase 0 (2026-10-07): el primer mensaje se entiende por su sentido ----------


def _entendedor_que_dice(respuesta: understanding.UnderstandingResponse) -> Any:
    vistas: list[understanding.UnderstandingRequest] = []

    async def entender(
        peticion: understanding.UnderstandingRequest,
    ) -> understanding.UnderstandingResponse:
        vistas.append(peticion)
        return respuesta

    entender.vistas = vistas  # type: ignore[attr-defined]
    return entender


@pytest.fixture
def sin_comprension() -> Any:
    yield
    delivery.install_understanding(None, None)


@pytest.mark.usefixtures("sin_comprension")
async def test_una_duda_general_se_contesta_sin_abrir_un_accidente(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """C1: «¿Que es un deducible?» abria un siniestro y preguntaba si hubo heridos."""
    _, propia = dos_aseguradoras
    conversacion, clave = await _conversacion_nueva(propia)
    cola = EventQueue(stream_ref=conversacion.chat_session_id)
    recibidos: list[str | None] = []

    async def _grafo_que_anota(turn: u12.InboundTurn) -> AsyncIterator[u12.TurnEvent]:
        recibidos.append(turn.case_id)
        yield _FINAL

    delivery.install_understanding(
        _entendedor_que_dice(
            understanding.UnderstandingResponse(
                wants=understanding.Want.GENERAL_QUESTION, person_question="¿Qué es un deducible?"
            )
        ),
        None,
    )
    entregado = await delivery.deliver(
        cola,
        _turno_de(conversacion, None, "¿Qué es un deducible?"),
        handle_turn=_grafo_que_anota,
        visitor_key_hash=clave,
        origin=Origin.PUBLIC_CHAT,
    )

    assert entregado.case_id is None
    assert recibidos == []
    cable = await cola.next_event(heartbeat_after=1)
    assert cable is not None
    assert "¿Quieres reportar un accidente" in str(cable["text"])
    assert "herido" not in str(cable["text"])


@pytest.mark.usefixtures("sin_comprension")
async def test_lo_entendido_decide_el_caso_y_viaja_con_el_turno(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Un accidente contado sin la palabra choque abre un siniestro, y el turno recibe
    lo entendido para no volver a entenderlo."""
    _, propia = dos_aseguradoras
    conversacion, clave = await _conversacion_nueva(propia)
    cola = EventQueue(stream_ref=conversacion.chat_session_id)
    recibidos: list[u12.InboundTurn] = []
    entendido = understanding.UnderstandingResponse(wants=understanding.Want.REPORT_ACCIDENT)

    async def _grafo_que_anota(turn: u12.InboundTurn) -> AsyncIterator[u12.TurnEvent]:
        recibidos.append(turn)
        yield _FINAL

    entendedor = _entendedor_que_dice(entendido)
    delivery.install_understanding(entendedor, None)
    entregado = await delivery.deliver(
        cola,
        _turno_de(conversacion, None, "Me rayaron el carro en el parqueadero"),
        handle_turn=_grafo_que_anota,
        visitor_key_hash=clave,
        origin=Origin.PUBLIC_CHAT,
    )

    assert entregado.case_id is not None
    vista = await casos.get_case(propia, entregado.case_id)
    assert vista is not None
    assert vista.record_type is RecordType.CLAIM
    [turno] = recibidos
    assert turno.understood == entendido
    [peticion] = entendedor.vistas
    assert peticion.record_type is None
    assert [linea.speaker for linea in peticion.history] == ["agent"], (
        "la apertura es lo unico que dijo la agente"
    )
    assert turno.understood_by_channel and turno.understood_without_case


def _entendedor_en_orden(*respuestas: understanding.UnderstandingResponse) -> Any:
    pendientes = list(respuestas)

    async def entender(
        peticion: understanding.UnderstandingRequest,
    ) -> understanding.UnderstandingResponse:
        del peticion
        return pendientes.pop(0)

    return entender


_IDENTIDAD = understanding.UnderstandingResponse(
    wants=understanding.Want.GREETING,
    items=(
        understanding.UnderstoodItem(field_key="identity_and_policy", value="Marcela Rios, POL-01"),
    ),
)


async def _dos_mensajes(
    propia: str, segundo: understanding.UnderstandingResponse, texto: str
) -> tuple[Any, list[u12.InboundTurn]]:
    conversacion, clave = await _conversacion_nueva(propia)
    cola = EventQueue(stream_ref=conversacion.chat_session_id)
    recibidos: list[u12.InboundTurn] = []

    async def _grafo_que_anota(turn: u12.InboundTurn) -> AsyncIterator[u12.TurnEvent]:
        recibidos.append(turn)
        yield _FINAL

    delivery.install_understanding(_entendedor_en_orden(_IDENTIDAD, segundo), None)
    primero = await delivery.deliver(
        cola,
        _turno_de(conversacion, None, "Soy Marcela Ríos, mi póliza es POL-01."),
        handle_turn=_grafo_que_anota,
        visitor_key_hash=clave,
        origin=Origin.PUBLIC_CHAT,
    )
    assert primero.case_id is None, "el control: dar datos sin elegir no abre caso"
    segundo_entregado = await delivery.deliver(
        cola,
        _turno_de(conversacion, None, texto),
        handle_turn=_grafo_que_anota,
        visitor_key_hash=clave,
        origin=Origin.PUBLIC_CHAT,
    )
    return segundo_entregado, recibidos


@pytest.mark.usefixtures("sin_comprension")
async def test_lo_que_dijo_antes_de_elegir_viaja_con_el_caso_que_abre(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """2026-10-09: nombre y poliza primero, «reportar» despues; la agente no los vuelve
    a pedir (la corrida de evaluaciones lo vio dar quince vueltas)."""
    _, propia = dos_aseguradoras
    entregado, recibidos = await _dos_mensajes(
        propia,
        understanding.UnderstandingResponse(wants=understanding.Want.REPORT_ACCIDENT),
        "Reportar un accidente",
    )

    assert entregado.case_id is not None
    [turno] = recibidos
    assert turno.understood is not None
    assert [i.field_key for i in turno.understood.items] == ["identity_and_policy"]


@pytest.mark.usefixtures("sin_comprension")
async def test_quien_sigue_dando_datos_sin_elegir_abre_un_reporte(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    entregado, recibidos = await _dos_mensajes(
        propia, _IDENTIDAD, "Soy Marcela Ríos, mi póliza es POL-01."
    )

    assert entregado.case_id is not None
    vista = await casos.get_case(propia, entregado.case_id)
    assert vista is not None
    assert vista.record_type is RecordType.CLAIM
    assert len(recibidos) == 1


@pytest.mark.usefixtures("sin_comprension")
async def test_pedir_cotizar_donde_no_se_cotiza_no_abre_caso(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    if tenancy.require(propia).quote_enabled:
        pytest.skip("esta prueba necesita una aseguradora que no cotiza")
    conversacion, clave = await _conversacion_nueva(propia)
    cola = EventQueue(stream_ref=conversacion.chat_session_id)

    delivery.install_understanding(
        _entendedor_que_dice(understanding.UnderstandingResponse(wants=understanding.Want.QUOTE)),
        None,
    )
    entregado = await delivery.deliver(
        cola,
        _turno_de(conversacion, None, "¿Cuánto me saldría asegurar el carro?"),
        handle_turn=_grafo_que_devuelve(_FINAL),
        visitor_key_hash=clave,
        origin=Origin.PUBLIC_CHAT,
    )

    assert entregado.case_id is None
    cable = await cola.next_event(heartbeat_after=1)
    assert cable is not None
    assert cable["text"] == copy_api.t(CopyKey("quote.reply.unavailable"), locale="es")


async def test_la_comparacion_pregunta_con_la_poliza_de_ejemplo_sin_pedirla(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """A8 (fase 1, 2026-10-08): cada columna compara la poliza de ejemplo de su
    aseguradora; antes la agente le pedia la poliza y la columna leia eso como "no hay
    clausula"."""
    _, propia = dos_aseguradoras
    conversacion, clave = await _conversacion_nueva(propia)
    cola = EventQueue(stream_ref=conversacion.chat_session_id)
    recibidos: list[u12.InboundTurn] = []

    async def _grafo_que_anota(turn: u12.InboundTurn) -> AsyncIterator[u12.TurnEvent]:
        recibidos.append(turn)
        yield _FINAL

    entregado = await delivery.deliver(
        cola,
        _turno_de(conversacion, None, "¿Me cubre el granizo?"),
        handle_turn=_grafo_que_anota,
        visitor_key_hash=clave,
        origin=Origin.PUBLIC_CHAT,
        surface=opening.Surface.COMPARISON,
    )

    assert entregado.case_id is not None
    vista = await casos.get_case(propia, entregado.case_id)
    assert vista is not None
    assert vista.record_type is RecordType.COVERAGE_INQUIRY
    assert vista.policy_ref == tenancy.require(propia).example_policy
    [turno] = recibidos
    assert turno.understood is not None
    assert turno.understood.asks_about_coverage
    assert turno.understood.person_question == "¿Me cubre el granizo?"


async def test_un_caso_decidido_dice_donde_ver_la_decision_y_no_sigue_capturando(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """B3 (fase 1, 2026-10-08): antes un reporte decia que seguia con el ajustador y una
    consulta o una cotizacion daban error."""
    from ..u14.conftest import nuevo_caso as caso_derivado
    from ..u14.test_correction import _cerrar

    _, propia = dos_aseguradoras
    conversacion, clave = await _conversacion_nueva(propia)
    caso = CasoSembrado(tenant_id=propia, case_id=await caso_derivado(propia))
    await _cerrar(propia, caso.case_id)
    cola = EventQueue(stream_ref=conversacion.chat_session_id)
    recibidos: list[u12.InboundTurn] = []

    async def _grafo_que_anota(turn: u12.InboundTurn) -> AsyncIterator[u12.TurnEvent]:
        recibidos.append(turn)
        yield _FINAL

    entregado = await delivery.deliver(
        cola,
        _turno_de(conversacion, caso.case_id, "¿Y qué pasó con mi caso?"),
        handle_turn=_grafo_que_anota,
        visitor_key_hash=clave,
        origin=Origin.PUBLIC_CHAT,
    )

    assert recibidos == [], "un caso decidido no vuelve a la captura"
    assert entregado.closed
    cable = await cola.next_event(heartbeat_after=1)
    assert cable is not None
    vista = await casos.get_case(propia, caso.case_id)
    assert vista is not None
    assert str(vista.case_number) in str(cable["text"])
    assert "Ver mi caso" in str(cable["text"])


async def test_un_caso_que_las_reglas_cerraron_se_dice_registrado_y_no_decidido(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """US1.17: un cierre directo no tiene una decision de nadie. A quien sigue escribiendo se le
    dice que quedo registrado, con el enlace de arriba, y el turno no vuelve a la captura."""
    from untangle.case_record.models import (
        Actor,
        ActorType,
        AttachmentKind,
        AttachmentState,
        Channel,
        ClosingEvidence,
        Resolution,
    )
    from untangle.case_record.rules import TransitionContext

    from ..u14.conftest import nuevo_caso as caso_derivado

    _, propia = dos_aseguradoras
    conversacion, clave = await _conversacion_nueva(propia)
    case_id = await caso_derivado(propia)
    await casos.close_case(
        propia,
        case_id,
        resolution=Resolution.REGISTERED,
        closing_evidence=ClosingEvidence(
            transcript=AttachmentState(kind=AttachmentKind.PRESENT, reference=case_id),
            cited_clauses=AttachmentState(kind=AttachmentKind.EMPTY),
            fired_rules=AttachmentState(kind=AttachmentKind.EMPTY),
            trace_id=AttachmentState(kind=AttachmentKind.EMPTY),
            control_results=AttachmentState(kind=AttachmentKind.EMPTY),
        ),
        context=TransitionContext(
            now=AHORA, actor=Actor(actor_type=ActorType.SYSTEM), channel=Channel.CHAT
        ),
    )
    cola = EventQueue(stream_ref=conversacion.chat_session_id)
    recibidos: list[u12.InboundTurn] = []

    async def _grafo_que_anota(turn: u12.InboundTurn) -> AsyncIterator[u12.TurnEvent]:
        recibidos.append(turn)
        yield _FINAL

    entregado = await delivery.deliver(
        cola,
        _turno_de(conversacion, case_id, "¿Y qué pasó con mi caso?"),
        handle_turn=_grafo_que_anota,
        visitor_key_hash=clave,
        origin=Origin.PUBLIC_CHAT,
    )

    assert recibidos == [], "un caso cerrado no vuelve a la captura"
    assert entregado.closed
    cable = await cola.next_event(heartbeat_after=1)
    assert cable is not None
    vista = await casos.get_case(propia, case_id)
    assert vista is not None
    texto = str(cable["text"])
    assert str(vista.case_number) in texto
    assert "registrado" in texto
    assert "decisión" not in texto
