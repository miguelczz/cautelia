"""La transcripción del caso tiene los dos lados, y la derivación tiene su turno.

**Faltaba la mitad, y faltaba entera.** El chat persistía el turno de la persona y
no el de la agente: ninguna línea del aplicativo escribía un turno con `speaker =
agent`, y los únicos casos con los dos lados eran los sembrados por el generador,
que es la razón por la que la bandeja parecía funcionar.

Lo que eso rompía no era estético:

- la revisión de cumplimiento comprueba que toda petición de persona se derive **en
  el turno siguiente de la agente** (BR5.1 de U10), y sin turnos de la agente ese
  control no podía pasar nunca;
- la evidencia de cierre promete la transcripción del caso (BR6.3 de U4) y prometía
  la mitad;
- lo que la agente afirmó --que es lo que hay que poder auditar-- no estaba en el
  caso.

Y la otra mitad de la costura: una petición de persona abría la pausa y **el caso
se quedaba en captura**. La cola del ajustador excluye ese estado a propósito, así
que quien pedía hablar con alguien no llegaba a la bandeja de nadie.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest

from untangle.case_record import api as casos
from untangle.case_record.models import CaseState, Origin, Speaker
from untangle.chat import delivery
from untangle.chat import session as chat_session
from untangle.chat.wire import EventQueue
from untangle.compliance.controls.api import HandoffReason
from untangle.compliance.redaction import api as redaccion
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey
from untangle.orchestration import contracts as u12
from untangle.tenancy import api as tenancy

from .conftest import AHORA, nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u13", "cifrador")

CLAVE_DEL_NAVEGADOR = "b" * 64

_FINAL = u12.FinalText(message_id="m1", text="Anotado. Cuenteme que paso.", language="es")
_DERIVA = u12.Handoff(
    reason_code=HandoffReason.HUMAN_REQUEST,
    copy_key=CopyKey("compliance.handoff.adjuster_review"),
    text="Un ajustador revisa su caso y le escribe.",
)


def _grafo_que_devuelve(*eventos: u12.TurnEvent) -> Any:
    async def falso(entrante: u12.InboundTurn) -> AsyncIterator[u12.TurnEvent]:
        del entrante
        for evento in eventos:
            yield evento

    return falso


def _turno(tenant_id: str, conversacion: Any, case_id: str, texto: str) -> u12.InboundTurn:
    return u12.InboundTurn(
        tenant_id=tenant_id,
        session_ref=conversacion.chat_session_id,
        case_id=case_id,
        text=texto,
        language="es",
        channel="chat",
        received_at=AHORA,
    )


async def _conversacion(tenant_id: str) -> Any:
    visitante = await tenancy.resolve_visitor_key(
        tenant_id=tenant_id, visitor_key=tenancy.new_visitor_key(), origin="prueba"
    )
    return await chat_session.open_session(
        tenant_id=tenant_id,
        visitor_key_digest=visitante.visitor_key_hash,
        origin_digest=visitante.origin,
        language="es",
        now=AHORA,
    )


async def test_la_transcripcion_guarda_los_dos_lados_del_turno(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Un turno deja dos líneas: lo que dijo la persona y lo que contestó la agente.

    Y se comprueba **quién habla en cada una**, no cuántas hay: dos líneas con el
    mismo hablante pasarían un conteo.
    """
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    conversacion = await _conversacion(propia)

    await delivery.deliver(
        EventQueue(stream_ref="chat-1"),
        _turno(propia, conversacion, caso.case_id, "Me chocaron el carro"),
        handle_turn=_grafo_que_devuelve(_FINAL),
        visitor_key_hash=CLAVE_DEL_NAVEGADOR,
        origin=Origin.PUBLIC_CHAT,
    )

    turnos = await casos.transcript_of(propia, caso.case_id)
    assert [t.speaker for t in turnos] == [Speaker.INSURED, Speaker.AGENT]
    assert "Anotado" in turnos[1].text_redacted


async def test_la_frase_de_espera_no_deja_turno(dos_aseguradoras: tuple[str, str]) -> None:
    """El control que impide guardar la conversación dos veces.

    La frase de espera no cierra el turno --la persona sigue esperando-- y los
    fragmentos son la misma frase a trozos. Si cualquier evento dejara su línea, la
    transcripción tendría tres entradas de la agente por turno y la revisión
    acotaría hasta una frase que no es la última.
    """
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    conversacion = await _conversacion(propia)
    espera = u12.Waiting(copy_key=CopyKey("chat.turn.waiting"), text="Un momento.")
    parcial = u12.PartialText(message_id="m1", seq=1, text="Ano")

    await delivery.deliver(
        EventQueue(stream_ref="chat-1"),
        _turno(propia, conversacion, caso.case_id, "Me chocaron el carro"),
        handle_turn=_grafo_que_devuelve(espera, parcial, _FINAL),
        visitor_key_hash=CLAVE_DEL_NAVEGADOR,
        origin=Origin.PUBLIC_CHAT,
    )

    turnos = await casos.transcript_of(propia, caso.case_id)
    de_la_agente = [t for t in turnos if t.speaker is Speaker.AGENT]
    assert len(de_la_agente) == 1
    assert "Anotado" in de_la_agente[0].text_redacted


async def test_una_derivacion_deriva_el_caso_con_su_turno(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """La costura que faltaba: el caso llega a la bandeja, y con su turno anotado.

    Las tres mitades juntas, porque separadas pasarían con media costura: el caso
    queda **derivado** --antes se quedaba en captura, y la cola del ajustador excluye
    ese estado--, con **prioridad alta** porque la persona lo pidió (BR3.8), y con el
    **turno de la frase de derivación**, que es lo que deja a la revisión de
    cumplimiento acotarse hasta ahí.
    """
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    conversacion = await _conversacion(propia)

    await delivery.deliver(
        EventQueue(stream_ref="chat-1"),
        _turno(propia, conversacion, caso.case_id, "Quiero hablar con una persona"),
        handle_turn=_grafo_que_devuelve(_DERIVA),
        visitor_key_hash=CLAVE_DEL_NAVEGADOR,
        origin=Origin.PUBLIC_CHAT,
    )

    vista = await casos.get_case(propia, caso.case_id)
    assert vista is not None
    assert vista.state is CaseState.DERIVED
    assert vista.derivation_reason == "person_requested"
    # Y el turno que nombra **está en la transcripción**: la revisión falla si le
    # piden acotarse a un turno que no existe, así que un identificador inventado
    # dejaría el caso sin revisión posible.
    turnos = {t.turn_id for t in await casos.transcript_of(propia, caso.case_id)}
    assert vista.derived_turn_id in turnos


async def test_un_turno_normal_no_deriva_nada(dos_aseguradoras: tuple[str, str]) -> None:
    """El control contrario: solo la derivación deriva.

    Sin esta prueba, una versión que derivara en cada turno pasaría la de arriba, y
    toda conversación acabaría en la bandeja desde su primera frase.
    """
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    conversacion = await _conversacion(propia)

    await delivery.deliver(
        EventQueue(stream_ref="chat-1"),
        _turno(propia, conversacion, caso.case_id, "Me chocaron el carro"),
        handle_turn=_grafo_que_devuelve(_FINAL),
        visitor_key_hash=CLAVE_DEL_NAVEGADOR,
        origin=Origin.PUBLIC_CHAT,
    )

    vista = await casos.get_case(propia, caso.case_id)
    assert vista is not None
    assert vista.state is not CaseState.DERIVED
    assert vista.derived_turn_id is None


# --- Por qué puerta se tapa lo que se guarda (U18, corregido el 2026-10-03) ----


@pytest.fixture
def como_arranca_el_servidor() -> Iterator[None]:
    """Los nombres públicos y las palabras del catálogo, como los instala la raíz.

    Desde el 2026-10-10 lo que dice la agente pasa siempre por la redacción, que
    respeta esos nombres y esas palabras. Sin instalarlos, esta prueba mediría un
    despliegue que no existe.
    """
    redaccion.allow_public_terms(
        [*(t.display_name for t in tenancy.loaded().available), "Catalina"]
    )
    redaccion.allow_own_vocabulary([e.text for e in copy_api.load().entries.values()])
    yield
    redaccion.allow_public_terms([])
    redaccion.allow_own_vocabulary([])


@pytest.mark.usefixtures("como_arranca_el_servidor")
async def test_lo_que_sale_del_catalogo_conserva_los_nombres_propios(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Una frase del catálogo se guarda con los nombres de la agente y la aseguradora.

    **El defecto que esto cierra lo introduje con la transcripción misma.** Escribía
    todo con `redact`, también lo que la agente dice desde el catálogo. En español
    el detector etiqueta como persona el nombre de la agente y el de la
    aseguradora, así que la transcripción guardaba «[NOMBRE 1]» donde la persona
    había oído «Catalina». Tapar lo que ya era seguro no protege a nadie y rompe
    justo lo que un ajustador tiene que poder leer.

    La señal ya existía en el evento; lo que faltaba era mirarla.
    """
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    conversacion = await _conversacion(propia)
    del_catalogo = u12.FinalText(
        message_id="m1",
        text="Le habla Catalina, la asistente de Seguros Aburrá.",
        language="es",
        from_catalog=True,
    )

    await delivery.deliver(
        EventQueue(stream_ref="chat-1"),
        _turno(propia, conversacion, caso.case_id, "Hola"),
        handle_turn=_grafo_que_devuelve(del_catalogo),
        visitor_key_hash=CLAVE_DEL_NAVEGADOR,
        origin=Origin.PUBLIC_CHAT,
    )

    turnos = await casos.transcript_of(propia, caso.case_id)
    guardado = next(t for t in turnos if t.speaker is Speaker.AGENT).text_redacted
    assert "Catalina" in guardado, guardado
    assert "Catalina" in guardado, guardado
    assert "[" not in guardado, guardado


async def test_lo_que_compone_el_modelo_se_guarda_como_lo_dijo(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Desde el 2026-10-30 la conversacion no se redacta al guardarse (decision de
    Miguel): el nombre que repitio el modelo queda como la persona lo leyo."""
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    conversacion = await _conversacion(propia)
    del_modelo = u12.FinalText(
        message_id="m1",
        text="Entendido, Derek Warren. Anoto lo que me cuenta.",
        language="es",
        from_catalog=False,
    )

    await delivery.deliver(
        EventQueue(stream_ref="chat-1"),
        _turno(propia, conversacion, caso.case_id, "Hola"),
        handle_turn=_grafo_que_devuelve(del_modelo),
        visitor_key_hash=CLAVE_DEL_NAVEGADOR,
        origin=Origin.PUBLIC_CHAT,
    )

    turnos = await casos.transcript_of(propia, caso.case_id)
    guardado = next(t for t in turnos if t.speaker is Speaker.AGENT).text_redacted
    assert guardado == "Entendido, Derek Warren. Anoto lo que me cuenta.", guardado


@pytest.mark.usefixtures("como_arranca_el_servidor")
async def test_la_frase_de_derivacion_tambien_es_del_catalogo(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Una derivación y un error llevan su `copy_key`: salen del catálogo siempre.

    No lo declaran con un campo, y por eso la regla tiene que decirlo. Sin esta
    prueba, tratarlos como texto del modelo pasaría inadvertido --la frase de
    derivación del catálogo no tiene nombres propios-- hasta el día en que una los
    lleve, y entonces el ajustador leería «[NOMBRE 1] revisa su caso».
    """
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    conversacion = await _conversacion(propia)
    deriva = u12.Handoff(
        reason_code=HandoffReason.HUMAN_REQUEST,
        copy_key=CopyKey("compliance.handoff.adjuster_review"),
        # **Catalina y no el nombre de la aseguradora**: "Seguros Aburrá" sobrevive
        # a las dos puertas, así que una aserción sobre él no distinguiría cuál se
        # usó. El detector español sí tapa "Catalina", y eso es lo que separa.
        text="Catalina pasa su caso a un ajustador, que le escribe.",
    )

    await delivery.deliver(
        EventQueue(stream_ref="chat-1"),
        _turno(propia, conversacion, caso.case_id, "Quiero hablar con una persona"),
        handle_turn=_grafo_que_devuelve(deriva),
        visitor_key_hash=CLAVE_DEL_NAVEGADOR,
        origin=Origin.PUBLIC_CHAT,
    )

    turnos = await casos.transcript_of(propia, caso.case_id)
    guardado = next(t for t in turnos if t.speaker is Speaker.AGENT).text_redacted
    assert "Catalina" in guardado, guardado
