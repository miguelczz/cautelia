"""Que transiciones permite el modelo, y que deja escrito cada intento.

Dos cosas se prueban aqui y la segunda es la que se olvida: que las transiciones
legales pasen, y que **las ilegales dejen rastro**. Un rechazo silencioso y un
rechazo con entrada se ven igual desde fuera --el caso no cambio-- y solo uno de
los dos permite saber despues que alguien lo intento (BR5.4, SEC-U4.12).

Los dos bordes de la ventana de T12 se prueban con el reloj inyectado en 14:59 y
15:01, no "por dentro": un borde que solo se prueba por dentro no prueba el
borde.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from untangle.case_record import rules, schema_loading
from untangle.case_record.models import (
    Actor,
    ActorType,
    AttachmentKind,
    AttachmentState,
    Case,
    CaseNumber,
    CaseState,
    ChangeKind,
    Channel,
    ClosingEvidence,
    DerivationReason,
    Origin,
    Priority,
    RecordType,
    Resolution,
)

AHORA = datetime(2026, 9, 20, 15, 0, tzinfo=UTC)
AGENTE = Actor(actor_type=ActorType.AGENT)
CLAVE = "clave-del-navegador-de-la-persona"

PRESENTE = AttachmentState(kind=AttachmentKind.PRESENT, reference="ref-1")
VACIO = AttachmentState(kind=AttachmentKind.EMPTY)
SIN_EVALUAR = AttachmentState(kind=AttachmentKind.NOT_EVALUATED)

COMPLETA = ClosingEvidence(
    transcript=PRESENTE,
    cited_clauses=VACIO,
    fired_rules=PRESENTE,
    trace_id=PRESENTE,
    control_results=PRESENTE,
)
INCOMPLETA = COMPLETA.model_copy(update={"trace_id": SIN_EVALUAR})


def caso(**cambios: object) -> Case:
    base = Case(
        case_id="CASO-1",
        tenant_id="stonecroft",
        case_number=CaseNumber(prefix="SA", serial="1"),
        record_type=RecordType.CLAIM,
        channel=Channel.CHAT,
        origin=Origin.PUBLIC_CHAT,
        language="es",
        created_at=AHORA,
        updated_at=AHORA,
    )
    # `evolve` y no `model_copy`: el segundo no vuelve a validar, asi que una
    # prueba que espera un rechazo del tipo no lo veria nunca.
    return base.evolve(**cambios)


def contexto(
    *,
    now: datetime = AHORA,
    derived_at: datetime | None = None,
    browser_key: str | None = None,
    case_browser_key: str | None = None,
    decision_started: bool = False,
) -> rules.TransitionContext:
    return rules.TransitionContext(
        now=now,
        actor=AGENTE,
        channel=Channel.CHAT,
        derived_at=derived_at,
        browser_key=browser_key,
        case_browser_key=case_browser_key,
        decision_started=decision_started,
    )


# --- La tabla manda -----------------------------------------------------------


def test_una_transicion_de_la_tabla_se_aplica() -> None:
    resultado = rules.attempt_transition(caso(), to=CaseState.CAPTURING, context=contexto())

    assert resultado.accepted
    assert resultado.case is not None
    assert resultado.case.state is CaseState.CAPTURING
    assert resultado.change.change_kind is ChangeKind.TRANSITION_APPLIED


def test_una_pareja_que_no_esta_en_la_tabla_se_rechaza_dejando_entrada() -> None:
    """El caso no cambia **y** queda escrito que alguien lo intento.

    Es la mitad que se olvida: sin la entrada, un rechazo y un intento que nunca
    ocurrio son indistinguibles el dia que alguien pregunta.
    """
    resultado = rules.attempt_transition(caso(), to=CaseState.CLOSED, context=contexto())

    assert not resultado.accepted
    assert resultado.case is None
    assert resultado.change.change_kind is ChangeKind.TRANSITION_REJECTED
    assert "open" in (resultado.change.detail or "")
    assert "closed" in (resultado.change.detail or "")


def test_derivar_sin_motivo_se_rechaza() -> None:
    """Derivar sin decir por que dejaria un caso en la bandeja sin explicacion."""
    resultado = rules.attempt_transition(
        caso(state=CaseState.CAPTURING), to=CaseState.DERIVED, context=contexto()
    )

    assert not resultado.accepted
    assert "derivation_reason_declared" in (resultado.change.detail or "")


def test_derivar_con_motivo_se_aplica() -> None:
    resultado = rules.attempt_transition(
        caso(state=CaseState.CAPTURING, derivation_reason=DerivationReason.RULE),
        to=CaseState.DERIVED,
        context=contexto(),
    )

    assert resultado.accepted


def test_derivar_con_el_turno_del_contexto_lo_escribe_en_el_caso() -> None:
    """El turno de la derivacion es un dato de la derivacion, y se escribe con ella.

    Es lo que deja a la revision de cumplimiento acotarse hasta ahi (BR5.1 de U10)
    en vez de adivinar: con el ultimo turno absolveria una derivacion que llego
    tarde, y sin nada acusaria de no haber derivado a quien si derivo.
    """
    resultado = rules.attempt_transition(
        caso(state=CaseState.CAPTURING),
        to=CaseState.DERIVED,
        context=replace(
            contexto(),
            derivation_reason=DerivationReason.RULE,
            derivation_turn_id="turn-de-la-frase",
        ),
    )

    assert resultado.accepted
    assert resultado.case is not None
    assert resultado.case.derived_turn_id == "turn-de-la-frase"


def test_el_turno_de_la_derivacion_se_ignora_si_la_transicion_no_deriva() -> None:
    """La misma condicion que el motivo: solo cuenta al derivar.

    Un turno de derivacion escrito en una transicion que no deriva seria un dato
    que contradice el estado, y la revision lo creeria.
    """
    resultado = rules.attempt_transition(
        caso(state=CaseState.CAPTURING),
        to=CaseState.VERIFYING,
        context=replace(contexto(), derivation_turn_id="turn-de-la-frase"),
    )

    assert resultado.accepted
    assert resultado.case is not None
    assert resultado.case.derived_turn_id is None


def test_un_caso_sin_derivar_no_puede_llevar_turno_de_derivacion() -> None:
    """La invariante en el tipo, probada rompiendola.

    No es simetrica con el motivo --que es obligatorio al derivar-- porque hay
    derivaciones que no ocurren en un turno; lo que no existe es un turno de
    derivacion sin derivacion.
    """
    with pytest.raises(ValidationError, match="turno de derivacion"):
        caso(state=CaseState.CAPTURING, derived_turn_id="turn-de-la-frase")


def test_cerrar_un_caso_derivado_en_una_conversacion_conserva_su_turno() -> None:
    """Visto el 2026-10-11: decidir cualquier caso derivado desde el chat fallaba con
    un error interno. El tipo rechazaba el caso ya cerrado porque seguia llevando el
    turno en que se derivo, que es su historia y no una contradiccion."""
    derivado = caso(
        state=CaseState.DERIVED,
        derivation_reason=DerivationReason.RULE,
        derived_turn_id="turn-de-la-frase",
    )

    resultado = rules.attempt_close(
        derivado,
        resolution=Resolution.APPROVED,
        closing_evidence=COMPLETA,
        context=contexto(),
    )

    assert resultado.accepted, resultado.reason
    assert resultado.case is not None
    assert resultado.case.state is CaseState.CLOSED
    assert resultado.case.derived_turn_id == "turn-de-la-frase"


@pytest.mark.parametrize(
    ("motivo", "prioridad"),
    [
        (DerivationReason.RULE, Priority.NORMAL),
        (DerivationReason.DEMO_LIMIT, Priority.NORMAL),
        (DerivationReason.PERSON_REQUESTED, Priority.HIGH),
    ],
)
def test_derivar_con_el_motivo_del_contexto_lo_escribe_en_el_caso(
    motivo: DerivationReason, prioridad: Priority
) -> None:
    """Quien deriva declara el motivo en el intento; el caso lo lleva desde ahi.

    Sin esto, T3, T5 y T7 solo se cumplian con un motivo que nadie podia escribir
    por la superficie publica. Pedir una persona sube la prioridad (BR3.8).
    """
    resultado = rules.attempt_transition(
        caso(state=CaseState.CAPTURING),
        to=CaseState.DERIVED,
        context=replace(contexto(), derivation_reason=motivo),
    )

    assert resultado.accepted
    assert resultado.case is not None
    assert resultado.case.derivation_reason is motivo
    assert resultado.case.priority is prioridad


def test_el_motivo_del_contexto_no_se_escribe_si_la_transicion_no_deriva() -> None:
    """Un motivo en el contexto de una transicion que no deriva no deja rastro:
    un caso capturando con motivo de derivacion diria algo que no paso."""
    resultado = rules.attempt_transition(
        caso(),
        to=CaseState.CAPTURING,
        context=replace(contexto(), derivation_reason=DerivationReason.PERSON_REQUESTED),
    )

    assert resultado.case is not None
    assert resultado.case.derivation_reason is None
    assert resultado.case.priority is Priority.NORMAL


def test_de_cerrado_no_sale_nada() -> None:
    """`closed` es terminal: ninguna fila de la tabla sale de el."""
    cerrado = caso(
        state=CaseState.CLOSED,
        resolution=Resolution.REGISTERED,
        closing_evidence=COMPLETA,
        closed_at=AHORA,
    )

    for destino in CaseState:
        resultado = rules.attempt_transition(cerrado, to=destino, context=contexto())
        assert not resultado.accepted, destino


# --- Los dos bordes de T12 (BR3.3, ADR-005) -----------------------------------


def _contexto_para_retomar(
    *,
    now: datetime = AHORA,
    derived_at: datetime | None = AHORA,
    browser_key: str | None = CLAVE,
    case_browser_key: str | None = CLAVE,
    decision_started: bool = False,
) -> rules.TransitionContext:
    """Las cuatro condiciones de T12 cumplidas, para que cada prueba rompa una.

    Los valores por defecto son el caso que pasa. Cada prueba cambia **uno** y
    exige el rechazo: asi el rechazo se atribuye a lo que se rompio y no a algo
    que quedo mal armado de paso.
    """
    return contexto(
        now=now,
        derived_at=derived_at,
        browser_key=browser_key,
        case_browser_key=case_browser_key,
        decision_started=decision_started,
    )


def _derivado_por_el_limite() -> Case:
    return caso(state=CaseState.DERIVED, derivation_reason=DerivationReason.DEMO_LIMIT)


def test_a_los_catorce_minutos_cincuenta_y_nueve_se_retoma() -> None:
    """Dentro de la ventana. El borde se prueba en el borde, no por dentro."""
    resultado = rules.attempt_transition(
        _derivado_por_el_limite(),
        to=CaseState.CAPTURING,
        context=_contexto_para_retomar(now=AHORA + timedelta(minutes=14, seconds=59)),
    )

    assert resultado.accepted


def test_retomar_un_caso_derivado_en_un_turno_suelta_ese_turno() -> None:
    """La persona retoma la conversacion: aquel turno ya no describe su estado, y
    conservarlo dejaria un caso en captura que el tipo rechaza. Pasa con una llamada
    que se quedo sin tiempo y se retoma (2026-10-11)."""
    derivado = caso(
        state=CaseState.DERIVED,
        derivation_reason=DerivationReason.DEMO_LIMIT,
        derived_turn_id="turn-de-la-despedida",
    )

    resultado = rules.attempt_transition(
        derivado, to=CaseState.CAPTURING, context=_contexto_para_retomar()
    )

    assert resultado.accepted, resultado.reason
    assert resultado.case is not None
    assert resultado.case.state is CaseState.CAPTURING
    assert resultado.case.derived_turn_id is None


def test_a_los_quince_minutos_exactos_todavia_se_retoma() -> None:
    """La regla dice "no han pasado quince minutos": el propio minuto quince
    cuenta como dentro, y excluirlo rechazaria a quien vuelve justo a tiempo."""
    resultado = rules.attempt_transition(
        _derivado_por_el_limite(),
        to=CaseState.CAPTURING,
        context=_contexto_para_retomar(now=AHORA + rules.VENTANA_PARA_RETOMAR),
    )

    assert resultado.accepted


def test_a_los_quince_minutos_y_un_segundo_ya_no_se_retoma() -> None:
    """Fuera de la ventana. El otro borde."""
    resultado = rules.attempt_transition(
        _derivado_por_el_limite(),
        to=CaseState.CAPTURING,
        context=_contexto_para_retomar(now=AHORA + timedelta(minutes=15, seconds=1)),
    )

    assert not resultado.accepted
    assert "within_resume_window" in (resultado.change.detail or "")


def test_no_se_retoma_lo_que_derivo_una_regla() -> None:
    """Solo se retoma lo que corto la demostracion."""
    resultado = rules.attempt_transition(
        caso(state=CaseState.DERIVED, derivation_reason=DerivationReason.RULE),
        to=CaseState.CAPTURING,
        context=_contexto_para_retomar(),
    )

    assert not resultado.accepted
    assert "derivation_reason_is_demo_limit" in (resultado.change.detail or "")


def test_otro_navegador_no_retoma_el_caso() -> None:
    resultado = rules.attempt_transition(
        _derivado_por_el_limite(),
        to=CaseState.CAPTURING,
        context=_contexto_para_retomar(browser_key="la-clave-de-otra-persona"),
    )

    assert not resultado.accepted
    assert "same_browser_key" in (resultado.change.detail or "")


def test_sin_clave_de_navegador_no_se_retoma() -> None:
    """Dos claves ausentes **no** son la misma.

    Tratarlo como coincidencia dejaria a cualquiera sin cookie retomar el caso
    de otro, que es la forma mas barata de que el aislamiento se rompa.
    """
    resultado = rules.attempt_transition(
        _derivado_por_el_limite(),
        to=CaseState.CAPTURING,
        context=_contexto_para_retomar(browser_key=None, case_browser_key=None),
    )

    assert not resultado.accepted


def test_un_caso_ya_decidido_no_vuelve_a_captura() -> None:
    """La agente cuenta la decision en vez de volver a capturar."""
    resultado = rules.attempt_transition(
        _derivado_por_el_limite(),
        to=CaseState.CAPTURING,
        context=_contexto_para_retomar(decision_started=True),
    )

    assert not resultado.accepted
    assert "no_decision_started" in (resultado.change.detail or "")


def test_sin_marca_de_cuando_derivo_no_se_retoma() -> None:
    """No hay ventana que medir, y dar por buena una condicion que no se pudo
    comprobar es como una condicion deja de ser una condicion."""
    resultado = rules.attempt_transition(
        _derivado_por_el_limite(),
        to=CaseState.CAPTURING,
        context=_contexto_para_retomar(derived_at=None),
    )

    assert not resultado.accepted


# --- El cierre ----------------------------------------------------------------


def test_cerrar_con_los_cinco_adjuntos_se_aplica() -> None:
    resultado = rules.attempt_close(
        caso(state=CaseState.DECIDING),
        resolution=Resolution.APPROVED,
        closing_evidence=COMPLETA,
        context=contexto(),
    )

    assert resultado.accepted
    assert resultado.case is not None
    assert resultado.case.state is CaseState.CLOSED
    assert resultado.case.closed_at == AHORA
    assert resultado.case.closing_evidence == COMPLETA


def test_un_conjunto_vacio_cuenta_como_presente() -> None:
    """Vacio dice que se miro y no habia. Es distinto de no evaluado, y esa
    distincion es lo que impide cerrar casos que nadie reviso (BR6.3)."""
    todo_vacio = ClosingEvidence(
        transcript=VACIO,
        cited_clauses=VACIO,
        fired_rules=VACIO,
        trace_id=VACIO,
        control_results=VACIO,
    )

    resultado = rules.attempt_close(
        caso(state=CaseState.DECIDING),
        resolution=Resolution.REGISTERED,
        closing_evidence=todo_vacio,
        context=contexto(),
    )

    assert resultado.accepted


def test_un_adjunto_sin_evaluar_rechaza_el_cierre_y_lo_nombra() -> None:
    """El ajustador necesita saber **cual** falto, no que falto alguno."""
    resultado = rules.attempt_close(
        caso(state=CaseState.DECIDING),
        resolution=Resolution.APPROVED,
        closing_evidence=INCOMPLETA,
        context=contexto(),
    )

    assert not resultado.accepted
    assert resultado.change.change_kind is ChangeKind.CLOSE_REJECTED
    assert "trace_id" in (resultado.change.detail or "")


def test_cerrar_desde_un_estado_que_no_cierra_deja_entrada_de_cierre() -> None:
    """Se reetiqueta como rechazo de cierre porque eso es lo que se intento."""
    resultado = rules.attempt_close(
        caso(state=CaseState.CAPTURING),
        resolution=Resolution.APPROVED,
        closing_evidence=COMPLETA,
        context=contexto(),
    )

    assert not resultado.accepted
    assert resultado.change.change_kind is ChangeKind.CLOSE_REJECTED


# --- Las condiciones son datos con implementacion obligatoria -----------------


def test_toda_condicion_de_la_tabla_tiene_implementacion() -> None:
    """Sin esto, una condicion mal escrita en el archivo no se evaluaria nunca y
    la transicion pasaria siempre: el fallo que se parece a que todo funciona."""
    rules.assert_conditions_are_implemented()


def test_una_condicion_sin_implementacion_hace_fallar_el_arranque() -> None:
    """La comprobacion se prueba con una violacion de verdad."""
    inventada = schema_loading.transitions()[0].model_copy(
        update={"conditions": ("condicion_que_nadie_escribio",)}
    )

    with pytest.raises(rules.ConditionNotImplementedError) as error:
        rules.assert_conditions_are_implemented((inventada,))

    assert "condicion_que_nadie_escribio" in str(error.value)


def test_una_implementacion_que_nadie_nombra_tambien_falla() -> None:
    """Casi siempre es un nombre escrito distinto en los dos sitios."""
    sin_condiciones = tuple(
        fila.model_copy(update={"conditions": ()}) for fila in schema_loading.transitions()
    )

    with pytest.raises(rules.ConditionNotImplementedError) as error:
        rules.assert_conditions_are_implemented(sin_condiciones)

    assert "ninguna transicion las nombra" in str(error.value)


# --- Ninguna secuencia llega a un estado ilegal -------------------------------


def test_ninguna_secuencia_de_transiciones_sale_de_los_siete_estados() -> None:
    """Se recorre el grafo entero, no una muestra al azar.

    Siete estados y doce transiciones caben enteros en un recorrido exhaustivo,
    y un recorrido exhaustivo dice mas que cualquier numero de secuencias
    aleatorias: aqui no queda ninguna sin visitar.
    """
    legales = {(fila.from_state, fila.to_state) for fila in schema_loading.transitions()}
    pendientes = [CaseState.OPEN]
    vistos: set[CaseState] = set()

    while pendientes:
        actual = pendientes.pop()
        if actual in vistos:
            continue
        vistos.add(actual)
        for destino in CaseState:
            if (actual, destino) in legales:
                pendientes.append(destino)

    assert vistos <= set(CaseState)
    # Y lo que importa: el recorrido llega a los siete, asi que ninguno esta
    # declarado y sin camino que lleve a el.
    assert vistos == set(CaseState)


def test_cerrado_no_tiene_ninguna_salida_en_la_tabla() -> None:
    """La otra mitad del recorrido: que sea terminal de verdad."""
    salidas = [f.id for f in schema_loading.transitions() if f.from_state is CaseState.CLOSED]

    assert salidas == []


# --- Las dos reglas que ata el propio tipo ------------------------------------


def test_quien_pidio_hablar_con_una_persona_va_con_prioridad_alta() -> None:
    """BR3.8. Alguien que pide hablar con una persona ya pidio ayuda una vez, y
    que su caso quede detras de otros en la bandeja es el fallo que se siente
    como que no lo escucharon."""
    with pytest.raises(ValueError, match="prioridad alta"):
        caso(
            state=CaseState.DERIVED,
            derivation_reason=DerivationReason.PERSON_REQUESTED,
        )


def test_el_mismo_caso_con_prioridad_alta_si_se_construye() -> None:
    derivado = caso(
        state=CaseState.DERIVED,
        derivation_reason=DerivationReason.PERSON_REQUESTED,
        priority=Priority.HIGH,
    )

    assert derivado.priority is Priority.HIGH


def test_un_caso_sin_cerrar_no_lleva_resolucion() -> None:
    """BR3.5. Una fila con resolucion y sin cerrar se leeria como decidida en
    cualquier consulta que mire la columna y no el estado."""
    with pytest.raises(ValueError, match="no esta cerrado"):
        caso(state=CaseState.DECIDING, resolution=Resolution.APPROVED)
