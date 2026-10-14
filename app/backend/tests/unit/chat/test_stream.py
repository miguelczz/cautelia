"""Los eventos de U12 en el cable del chat (C-04, REL-U13.1).

Lo que se comprueba no es que la traduccion "funcione": es que el cable dice
exactamente lo que el contrato con el navegador fija, y **que no dice de mas**.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from untangle.chat import stream
from untangle.chat.citation import CitationDetail
from untangle.compliance.controls.api import HandoffReason
from untangle.copy_catalog.api import CopyKey
from untangle.orchestration.turn import (
    FinalText,
    Handoff,
    PartialText,
    TurnError,
    Waiting,
)


def _detalle() -> CitationDetail:
    """Una cita **ya completada desde el corpus**, que es como llega al cable.

    Lo que el grafo deja en el evento es otra cosa --ver la prueba de abajo--, y
    escribir aqui un doble con los cinco campos de C-04 puestos fue exactamente lo
    que oculto que tres de ellos salian vacios en cada respuesta real.
    """
    return CitationDetail(
        clause_id="RC-04",
        clause_version="2",
        part="Responsabilidad civil",
        text="La compania responde por los danos a terceros.",
        clause_language="es",
        amount_deferred=False,
        issuer_label="Seguros Aburrá",
    )


@dataclass(frozen=True)
class _VistaDelGrafo:
    """La forma **real** que el grafo pone en `FinalText.citations`.

    Son los campos de `CoverageCitationView` de U12, copiados a proposito: sin
    version, sin texto y sin referencia de traza, porque ese tipo dice en su
    docstring que el texto lo despliega U13 por su cuenta.
    """

    clause_id: str = "RC-04"
    part: str = "Responsabilidad civil"
    clause_language: str = "es"
    amount_deferred: bool = False
    voice_summary: str = "Su poliza tiene una clausula sobre eso."


# --- Cada evento en su forma del contrato -------------------------------------


def test_el_fragmento_lleva_su_orden() -> None:
    """`seq` es lo que deja al navegador recomponer una respuesta larga."""
    cable = stream.to_wire(PartialText(message_id="m1", seq=3, text="La cláusula"))

    assert cable == {"kind": "turn.partial", "message_id": "m1", "seq": 3, "text": "La cláusula"}


def test_la_respuesta_final_lleva_su_idioma_y_sus_citas() -> None:
    cable = stream.to_wire(
        FinalText(
            message_id="m2",
            text="Su póliza lo cubre.",
            language="es",
            case_id="caso-1",
            citations=(_VistaDelGrafo(),),
        ),
        citations=(_detalle(),),
        trace_ref="trace-abc123",
    )

    assert cable["kind"] == "turn.final"
    assert cable["language"] == "es"
    assert cable["citations"] == [
        {
            "clause_id": "RC-04",
            "clause_version": "2",
            "part": "Responsabilidad civil",
            "text": "La compania responde por los danos a terceros.",
            "clause_language": "es",
            "amount_deferred": False,
            "trace_ref": "trace-abc123",
            # Sin traduccion: la clausula esta en el idioma de la conversacion.
            "translated_text": None,
            "translated_part": None,
            # De la poliza base: no es una condicion especial.
            "special_condition_number": None,
        }
    ]


def test_la_condicion_especial_de_la_clausula_viaja_en_el_cable() -> None:
    """Aditivo (2026-10-11): la tarjeta rotula "Condicion especial 5" y no "Endosos"."""
    cable = stream.to_wire(
        FinalText(message_id="m2", text="Sí.", language="es"),
        citations=(replace(_detalle(), special_condition_number=5),),
    )

    assert cable["citations"][0]["special_condition_number"] == 5


def test_las_citas_no_salen_del_evento_sino_de_lo_que_se_le_pasa() -> None:
    """El defecto que esta tanda encontro, con su prueba.

    El cable leia los cinco campos de C-04 del propio evento con `getattr`, y el
    objeto que el grafo pone ahi solo tiene dos de ellos: version, texto y
    referencia de traza salian como cadena vacia en **cada respuesta real**. Ninguna
    compuerta lo vio porque la prueba usaba un doble con los cinco campos puestos.

    Ahora el evento por si solo no produce ninguna cita: las trae `details_for`
    desde el corpus. Un cable vacio aqui es la senal de que no hay ningun camino por
    el que una cita se serialice a medias.
    """
    cable = stream.to_wire(
        FinalText(
            message_id="m2",
            text="Su póliza lo cubre.",
            language="es",
            citations=(_VistaDelGrafo(),),
        )
    )

    assert cable["citations"] == []


def test_la_referencia_de_traza_es_la_del_turno_y_se_copia_a_cada_cita() -> None:
    """C-04 la pide dentro de cada cita, pero la traza es del turno: se copia."""
    cable = stream.to_wire(
        FinalText(message_id="m2", text="Sí.", language="es"),
        citations=(_detalle(), _detalle()),
        trace_ref="trace-unica",
    )

    assert [cita["trace_ref"] for cita in cable["citations"]] == ["trace-unica", "trace-unica"]


def test_la_derivacion_lleva_su_motivo_del_conjunto_cerrado() -> None:
    cable = stream.to_wire(
        Handoff(
            reason_code=HandoffReason.HUMAN_REQUEST,
            copy_key=CopyKey("compliance.handoff.adjuster_review"),
            text="Un ajustador revisa su caso.",
            case_id="caso-1",
        )
    )

    assert cable["kind"] == "turn.handoff"
    assert cable["reason_code"] == "human_request"
    assert cable["copy_key"] == "compliance.handoff.adjuster_review"


# --- Lo que viaja ademas de la clave: el texto del turno ----------------------
#
# Hasta el 2026-10-12 la espera, la derivacion y el error viajaban solo con su clave
# y el navegador las resolvia de su tabla. El servidor estreno una clave que la tabla
# no tenia (`compliance.handoff.adjuster_review_inquiry`) y quien pidio un ajustador
# leyo "tuve un problema para responder eso" con el caso ya derivado. Ahora el texto
# ya resuelto, en el idioma del turno, viaja con la clave: la pantalla usa su tabla
# cuando la conoce y este texto cuando no.


def test_la_frase_de_espera_viaja_con_su_clave_y_su_texto() -> None:
    cable = stream.to_wire(
        Waiting(copy_key=CopyKey("chat.turn.waiting"), text="Déjeme revisar su póliza.")
    )

    assert cable == {
        "kind": "turn.waiting",
        "copy_key": "chat.turn.waiting",
        "text": "Déjeme revisar su póliza.",
    }


def test_el_error_viaja_con_su_codigo_su_clave_y_su_texto() -> None:
    """El codigo sigue siendo lo unico tecnico que sale: ningun detalle interno."""
    cable = stream.to_wire(
        TurnError(
            code="internal_error",
            copy_key=CopyKey("chat.turn.error"),
            text="Tuve un problema para responder eso.",
        )
    )

    assert cable == {
        "kind": "turn.error",
        "code": "internal_error",
        "copy_key": "chat.turn.error",
        "text": "Tuve un problema para responder eso.",
    }


def test_la_derivacion_viaja_con_el_texto_de_su_clave() -> None:
    cable = stream.to_wire(
        Handoff(
            reason_code=HandoffReason.HUMAN_REQUEST,
            copy_key=CopyKey("compliance.handoff.adjuster_review_inquiry"),
            text="Listo: un ajustador revisa tu consulta.",
            case_id="caso-1",
        )
    )

    assert cable["copy_key"] == "compliance.handoff.adjuster_review_inquiry"
    assert cable["text"] == "Listo: un ajustador revisa tu consulta."


def test_el_fallo_de_la_entrega_viaja_con_el_texto_del_catalogo() -> None:
    cable = stream.delivery_error(copy_key="chat.turn.error", text="Tuve un problema.")

    assert cable == {
        "kind": "turn.error",
        "code": stream.DELIVERY_FAILED,
        "copy_key": "chat.turn.error",
        "text": "Tuve un problema.",
    }


def test_la_respuesta_que_promete_otra_viaja_marcada_como_pendiente() -> None:
    """2026-10-12: la pantalla muestra que se esta revisando mientras el fondo trae la
    respuesta. Sin la marca la conversacion se queda quieta 12 segundos."""
    pendiente = stream.to_wire(
        FinalText(message_id="m5", text="Déjame revisar.", language="es", answer_pending=True)
    )
    normal = stream.to_wire(FinalText(message_id="m6", text="Listo.", language="es"))

    assert pendiente["answer_pending"] is True
    assert normal["answer_pending"] is False


# --- REL-U13.1: ninguna ruta termina sin cerrar el turno ----------------------


@pytest.mark.parametrize(
    ("nombre", "evento"),
    [
        ("final", FinalText(message_id="m", text="listo", language="es")),
        (
            "derivacion",
            Handoff(
                reason_code=HandoffReason.HUMAN_REQUEST,
                copy_key=CopyKey("compliance.handoff.adjuster_review"),
                text="x",
            ),
        ),
        ("error", TurnError(code="c", copy_key=CopyKey("chat.turn.error"), text="x")),
    ],
)
def test_los_tres_eventos_finales_cierran_el_turno(nombre: str, evento: object) -> None:
    assert stream.closes_turn(stream.to_wire(evento)), nombre  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("nombre", "evento"),
    [
        ("fragmento", PartialText(message_id="m", seq=1, text="x")),
        ("espera", Waiting(copy_key=CopyKey("chat.turn.waiting"), text="x")),
    ],
)
def test_los_eventos_intermedios_no_cierran_el_turno(nombre: str, evento: object) -> None:
    """El control positivo del anterior: si `closes_turn` devolviera siempre
    `True`, el navegador dejaria de esperar al primer fragmento y la respuesta
    larga se veria cortada."""
    assert not stream.closes_turn(stream.to_wire(evento)), nombre  # type: ignore[arg-type]


def test_un_evento_que_el_contrato_no_conoce_falla_en_el_acto() -> None:
    """Saltarselo dejaria el turno abierto en el navegador sin ningun mensaje,
    que es justo el modo de fallo que REL-U13.1 existe para impedir."""
    with pytest.raises(stream.UnknownEventError):
        stream.to_wire(object())  # type: ignore[arg-type]


def test_la_respuesta_final_lleva_sus_botones_y_sin_ellos_una_lista_vacia() -> None:
    """Fase 0 (2026-10-07): los botones viajan resueltos; el navegador solo los dibuja."""
    con = stream.to_wire(
        FinalText(message_id="m3", text="¿Es correcto?", language="es", suggestions=("Sí", "No"))
    )
    sin = stream.to_wire(FinalText(message_id="m4", text="Gracias.", language="es"))

    assert con["suggestions"] == ["Sí", "No"]
    assert sin["suggestions"] == []
