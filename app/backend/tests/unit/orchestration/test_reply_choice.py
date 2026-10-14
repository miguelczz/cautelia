"""Que texto sale de un turno: lo que escribio el modelo, o la frase del catalogo (2026-10-12).

`turn._texto_del_turno` es una tabla de ramas, en orden, y la primera que aplica manda:
hito, sin modelo, primer mensaje, dato rechazado, respuesta que no vale, y en la voz lo que el
redactor cambiaria. Pura: sin base, sin modelo y sin red; la voz usa el redactor real. De punta a
punta por el turno esta en `tests/integration/u12/test_turn.py`.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest

from untangle.base import Locale
from untangle.chat import delivery
from untangle.compliance.controls.signals import TurnSignals
from untangle.compliance.redaction import api as redaccion
from untangle.orchestration import contracts, outcome_claim, turn
from untangle.orchestration.model_reply import FallbackReason, agent_name_of
from untangle.orchestration.nodes.intake import composition, understanding
from untangle.orchestration.nodes.intake.blocks import Block
from untangle.orchestration.nodes.intake.extraction import ExtractedField
from untangle.orchestration.nodes.intake.node import IntakeNodeOutput
from untangle.tenancy import api as tenancy

_SIN_SENALES = TurnSignals(human_request=False, identity_question=False, emergency=False)
_BASE = "¿Cuándo ocurrió el accidente?"
_REPLY = "Qué alivio que estén bien. ¿Me cuentas cuándo fue?"


@pytest.fixture(autouse=True)
def aseguradoras() -> None:
    tenancy.install(tenancy.load())


def _mensaje(*, channel: str = "chat", **mas: Any) -> contracts.InboundTurn:
    return contracts.InboundTurn(
        tenant_id="sunmeadow",
        session_ref="s",
        case_id="c",
        text="no, todos bien",
        language="es",
        channel=channel,  # type: ignore[arg-type]
        received_at=datetime(2026, 10, 12, 12, 0, tzinfo=UTC),
        **mas,
    )


def _campo(clave: str) -> ExtractedField:
    return ExtractedField(
        field_key=clave,
        value="no",
        normalized=None,
        evidence_turn_id="t",
        evidence_verbatim_redacted="no",
    )


def _salida(
    *extraidos: str,
    clave: str = "intake.question.when_and_where",
    bloque: Block = Block.WHEN_AND_WHERE,
) -> IntakeNodeOutput:
    return IntakeNodeOutput(
        intake_next_block=bloque,
        intake_extracted=tuple(_campo(k) for k in extraidos),
        intake_awaiting_confirmation=None,
        intake_readback_resolved=None,
        intake_response_key=clave,
        intake_response_text=_BASE,
        intake_session_ended=None,
    )


def _entendido(reply: str | None = _REPLY, *items: str) -> understanding.UnderstandingResponse:
    return understanding.UnderstandingResponse(
        wants=understanding.Want.CONTINUE,
        items=tuple(understanding.UnderstoodItem(field_key=k, value="no") for k in items),  # type: ignore[arg-type]
        reply=reply,
    )


def _elegir(
    *,
    entendido: understanding.UnderstandingResponse | None,
    salida: IntakeNodeOutput | None = None,
    mensaje: contracts.InboundTurn | None = None,
    senales: TurnSignals = _SIN_SENALES,
    revision_lanzada: bool = False,
) -> tuple[str | None, FallbackReason | None]:
    return turn._texto_del_turno(
        mensaje or _mensaje(),
        senales,
        entendido,
        salida or _salida(),
        revision_lanzada=revision_lanzada,
    )


def test_cuando_todo_cuadra_sale_lo_que_escribio_el_modelo_y_sin_motivo() -> None:
    assert _elegir(entendido=_entendido()) == (_REPLY, None)


def test_la_respuesta_sale_sin_los_espacios_de_los_bordes() -> None:
    texto, _ = _elegir(entendido=_entendido("  Qué susto.  "))

    assert texto == "Qué susto."


def test_un_hito_manda_sobre_todo_lo_demas() -> None:
    cerrado = _salida(clave="intake.closing.fast_claim_done")

    assert _elegir(entendido=_entendido(), salida=cerrado) == (None, FallbackReason.MILESTONE)
    assert _elegir(entendido=None, salida=cerrado) == (None, FallbackReason.MILESTONE)
    assert _elegir(entendido=_entendido(), revision_lanzada=True) == (
        None,
        FallbackReason.MILESTONE,
    )
    emergencia = TurnSignals(human_request=False, identity_question=False, emergency=True)
    assert _elegir(entendido=_entendido(), senales=emergencia) == (None, FallbackReason.MILESTONE)


def test_sin_modelo_sale_la_frase_del_catalogo() -> None:
    assert _elegir(entendido=None) == (None, FallbackReason.NO_MODEL)


def test_el_primer_mensaje_que_abrio_el_caso_sale_por_la_frase_del_catalogo() -> None:
    mensaje = _mensaje(understood_without_case=True)

    assert _elegir(entendido=_entendido(), mensaje=mensaje) == (
        None,
        FallbackReason.OPENING_TURN,
    )


def test_un_dato_que_el_codigo_rechazo_deja_la_frase_del_catalogo() -> None:
    # El modelo anoto dos datos y el codigo se quedo con uno.
    assert _elegir(
        entendido=_entendido(_REPLY, "injuries", "location"), salida=_salida("injuries")
    ) == (None, FallbackReason.ITEMS_REJECTED)


def test_si_el_codigo_acepto_todo_lo_que_anoto_el_modelo_sale_su_respuesta() -> None:
    # Y puede haber de mas: lo derivado, o lo que el codigo agrego por su cuenta.
    assert _elegir(
        entendido=_entendido(_REPLY, "injuries"), salida=_salida("injuries", "location")
    ) == (_REPLY, None)


@pytest.mark.parametrize(
    "reply",
    [None, "", "  ", "a" * 601, "Mira https://x.example", "Escribe a a@b.co"],
)
def test_una_respuesta_que_no_vale_deja_la_frase_del_catalogo(reply: str | None) -> None:
    assert _elegir(entendido=_entendido(reply)) == (None, FallbackReason.INVALID_REPLY)


def test_el_nombre_de_la_agente_sin_que_la_frase_base_lo_traiga_deja_la_frase_del_catalogo() -> (
    None
):
    nombre = agent_name_of("sunmeadow", "es")

    assert _elegir(entendido=_entendido(f"Soy {nombre}. {_REPLY}")) == (
        None,
        FallbackReason.INVALID_REPLY,
    )


def test_el_orden_es_hito_modelo_primer_mensaje_dato_respuesta() -> None:
    """Un dato rechazado con una respuesta vacia dice «dato rechazado»: la primera que aplica."""
    assert _elegir(entendido=_entendido(None, "injuries")) == (
        None,
        FallbackReason.ITEMS_REJECTED,
    )
    mensaje = _mensaje(understood_without_case=True)
    assert _elegir(entendido=_entendido(None, "injuries"), mensaje=mensaje) == (
        None,
        FallbackReason.OPENING_TURN,
    )


# --- El idioma de la respuesta es el de la conversacion ---------------------------------


@pytest.mark.parametrize("canal", ["chat", "voice"])
def test_una_respuesta_en_el_otro_idioma_deja_la_frase_del_catalogo(canal: str) -> None:
    """La llamada iba en espanol, la persona dijo «En English, please» y el modelo contesto
    en ingles: sonaba bien y dejaba el reconocedor y las frases fijas en espanol."""
    en_ingles = "Of course. Were there any injuries in the accident?"

    assert _elegir(entendido=_entendido(en_ingles), mensaje=_mensaje(channel=canal)) == (
        None,
        FallbackReason.WRONG_LANGUAGE,
    )


def test_una_respuesta_corta_o_con_una_palabra_del_otro_idioma_no_se_descarta() -> None:
    # Sin senal suficiente no se adivina: «Okay.» no es ingles, y una marca tampoco.
    assert _elegir(entendido=_entendido("Okay, gracias.")) == ("Okay, gracias.", None)
    con_marca = "Anotado el Ford Mustang. ¿Hubo alguien más involucrado en el choque?"
    assert _elegir(entendido=_entendido(con_marca)) == (con_marca, None)


def test_en_una_conversacion_en_ingles_la_respuesta_en_ingles_sale() -> None:
    en_ingles = "Thanks, I noted that. Was anyone hurt in the accident?"

    en_conversacion_en_ingles = replace(_mensaje(), language="en")
    assert _elegir(entendido=_entendido(en_ingles), mensaje=en_conversacion_en_ingles) == (
        en_ingles,
        None,
    )


# --- La llamada: la agente nunca dice una etiqueta en voz alta ---------------------------


def test_en_la_voz_sale_la_respuesta_si_el_redactor_no_la_cambia() -> None:
    assert str(redaccion.redact(_REPLY, language="es")) == _REPLY

    assert _elegir(entendido=_entendido(), mensaje=_mensaje(channel="voice")) == (_REPLY, None)


@pytest.mark.parametrize(
    "reply",
    ["Gracias, Marcela Ríos. ¿Cuándo fue?", "Tengo la póliza POL-000001. ¿Cuándo fue?"],
    ids=["un-nombre", "una-poliza"],
)
def test_en_la_voz_si_el_redactor_cambia_algo_sale_la_frase_del_catalogo(reply: str) -> None:
    assert str(redaccion.redact(reply, language="es")) != reply

    assert _elegir(entendido=_entendido(reply), mensaje=_mensaje(channel="voice")) == (
        None,
        FallbackReason.REDACTED_VOICE,
    )


def test_en_el_chat_el_mismo_texto_no_pasa_por_el_redactor_de_la_voz() -> None:
    reply = "Tengo la póliza POL-000001. ¿Cuándo fue?"

    assert _elegir(entendido=_entendido(reply)) == (reply, None)


def test_si_el_redactor_no_se_puede_ejecutar_en_la_voz_no_se_dice_nada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Falla cerrado, como todo punto de salida: sin redactor no hay texto que decir."""

    def _roto(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("el detector no cargo")

    monkeypatch.setattr(redaccion, "redact", _roto)

    assert turn._la_voz_taparia_algo(_REPLY, "es") is True
    assert _elegir(entendido=_entendido(), mensaje=_mensaje(channel="voice")) == (
        None,
        FallbackReason.REDACTED_VOICE,
    )


# --- La respuesta no da el reporte por hecho mientras la captura sigue abierta (2026-10-13) ---

#: Lo que contesto el modelo en la llamada simulada con el lugar todavia sin decir.
_LA_PROMESA = "De nada. Ya quedó anotado tu reporte; un ajustador lo revisará con tu póliza."
_LA_PROMESA_EN = "You're welcome. Your report is saved and an adjuster will review it."


@pytest.mark.parametrize("canal", ["chat", "voice"])
@pytest.mark.parametrize(
    ("idioma", "reply"), [("es", _LA_PROMESA), ("en", _LA_PROMESA_EN)], ids=["es", "en"]
)
def test_una_respuesta_que_da_el_reporte_por_hecho_con_la_captura_abierta_deja_la_frase_del_codigo(
    canal: str, idioma: Locale, reply: str
) -> None:
    """Visto en una llamada simulada: el lugar sin decir, la persona dice «eso es todo» y el
    modelo contesta que ya quedo anotado y que lo revisa un ajustador. Falso: el caso sigue
    tomando datos. Va en los dos canales y en los dos idiomas."""
    mensaje = replace(_mensaje(channel=canal), language=idioma)

    assert _elegir(entendido=_entendido(reply), mensaje=mensaje) == (
        None,
        FallbackReason.REPORT_NOT_DONE,
    )


@pytest.mark.parametrize(
    "bloque",
    [Block.SAFETY, Block.IDENTITY_AND_POLICY, Block.WHAT_HAPPENED, Block.WHEN_AND_WHERE],
)
def test_vale_para_cualquier_bloque_de_campos_que_siga_pendiente(bloque: Block) -> None:
    assert _elegir(entendido=_entendido(_LA_PROMESA), salida=_salida(bloque=bloque)) == (
        None,
        FallbackReason.REPORT_NOT_DONE,
    )


@pytest.mark.parametrize("bloque", [Block.DONE, Block.FINAL_CONFIRMATION])
def test_con_la_captura_cerrada_la_respuesta_puede_hablar_del_desenlace(bloque: Block) -> None:
    """Un caso ya en revision, con un ajustador o cerrado no tiene bloque que preguntar: el
    modelo puede decir que lo tiene el ajustador, que es lo que su instruccion le pide."""
    respuesta = "Ya lo tiene un ajustador. ¿Necesitas algo más?"
    assert outcome_claim.claims_outcome(respuesta)

    assert _elegir(entendido=_entendido(respuesta), salida=_salida(bloque=bloque)) == (
        respuesta,
        None,
    )


@pytest.mark.parametrize(
    "reply",
    [
        "Anoté el lugar. ¿Qué carro era?",
        "Si prefieres, paso tu caso a un ajustador. ¿Seguimos con tu reporte?",
        "Tu reporte todavía no está completo: me falta el lugar. ¿Me lo dices?",
        "Entiendo. Cuando me cuentes dónde fue, un ajustador podrá revisarlo.",
    ],
)
def test_ofrecer_anotar_o_decir_que_falta_algo_sale_tal_cual(reply: str) -> None:
    assert _elegir(entendido=_entendido(reply)) == (reply, None)


def test_el_orden_milestone_rechazo_invalida_idioma_y_despues_la_promesa() -> None:
    """La promesa es la penultima que se mira: lo que la precede manda, y la voz va despues."""
    hito = _salida(clave="intake.closing.fast_claim_done")
    assert _elegir(entendido=_entendido(_LA_PROMESA), salida=hito) == (
        None,
        FallbackReason.MILESTONE,
    )
    assert _elegir(entendido=_entendido(_LA_PROMESA, "injuries"), salida=_salida()) == (
        None,
        FallbackReason.ITEMS_REJECTED,
    )
    assert _elegir(entendido=_entendido(_LA_PROMESA + " https://x.example")) == (
        None,
        FallbackReason.INVALID_REPLY,
    )
    # Escrita en el otro idioma: se descarta por el idioma, no por la promesa.
    assert _elegir(entendido=_entendido(_LA_PROMESA_EN)) == (None, FallbackReason.WRONG_LANGUAGE)


# --- La frase que sale en su lugar dice la verdad ---------------------------------------------


@pytest.mark.parametrize(
    ("idioma", "bloque", "etiqueta"),
    [
        ("es", Block.WHEN_AND_WHERE, "cuándo y dónde"),
        ("es", Block.IDENTITY_AND_POLICY, "tu nombre y tu póliza"),
        ("en", Block.WHEN_AND_WHERE, "when and where"),
        ("en", Block.SAFETY, "whether anyone was hurt"),
    ],
)
def test_la_frase_de_respaldo_dice_que_falta_que_queda_guardado_y_pregunta_una_vez(
    idioma: Locale, bloque: Block, etiqueta: str
) -> None:
    salida = _salida(bloque=bloque)

    texto = turn._frase_base(salida, FallbackReason.REPORT_NOT_DONE, language=idioma)

    assert etiqueta in texto, "nombra el bloque que toca, no uno fijo"
    assert texto != salida.intake_response_text
    assert texto.count("?") == 1 and texto.endswith("?"), "una sola pregunta, la ultima"
    assert not any(c.isdigit() for c in texto), (
        "sin el numero del caso: tambien se dice en voz alta"
    )
    assert ("guardado" if idioma == "es" else "saved") in texto
    # Y no afirma lo que la respuesta descartada afirmaba.
    assert not outcome_claim.claims_outcome(texto)


@pytest.mark.parametrize(
    "motivo",
    [None, FallbackReason.NO_MODEL, FallbackReason.INVALID_REPLY, FallbackReason.WRONG_LANGUAGE],
)
def test_con_cualquier_otro_motivo_sale_la_frase_que_compuso_el_nodo(
    motivo: FallbackReason | None,
) -> None:
    assert turn._frase_base(_salida(), motivo, language="es") == _BASE


def test_la_frase_de_respaldo_sale_de_la_composicion_del_catalogo() -> None:
    """`_frase_base` no escribe texto: lo pide a la composicion, que lo saca del catalogo."""
    esperado = composition.compose_unfinished(Block.WHAT_HAPPENED, language="es")[1]

    assert (
        turn._frase_base(
            _salida(bloque=Block.WHAT_HAPPENED), FallbackReason.REPORT_NOT_DONE, language="es"
        )
        == esperado
    )


@pytest.mark.parametrize("bloque", [Block.DONE, Block.FINAL_CONFIRMATION])
def test_los_bloques_de_cierre_no_se_nombran_como_pendientes(bloque: Block) -> None:
    with pytest.raises(ValueError, match="no se nombra"):
        composition.compose_unfinished(bloque, language="es")


# --- El mismo rechazo en el mensaje que todavia no abre caso ----------------------------------


def test_sin_caso_una_respuesta_que_da_un_reporte_por_hecho_deja_la_frase_del_catalogo() -> None:
    """No hay reporte: «ya quedo anotado tu reporte» es falso de raiz."""
    mensaje = replace(_mensaje(), case_id=None)

    assert delivery._lo_que_dice_el_modelo_sin_caso(
        mensaje, _entendido("Hola, ya quedó anotado tu reporte."), _BASE
    ) == (None, FallbackReason.REPORT_NOT_DONE)
    assert delivery._lo_que_dice_el_modelo_sin_caso(
        mensaje, _entendido("Hola, ¿en qué te ayudo?"), _BASE
    ) == ("Hola, ¿en qué te ayudo?", None)
