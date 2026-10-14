"""El corte y la retoma (BR6.1 a BR6.5, BR8.3).

El criterio que bloquea --AC1.27.3, que la poliza de ejemplo no abra casos
ajenos-- se prueba en `test_call_session_repository.py`, que es donde vive la
consulta. Aqui se prueba lo que la llamada **dice** al retomar.
"""

from __future__ import annotations

import io
import json
from datetime import timedelta

import pytest

from untangle import observability
from untangle.case_record import api as casos
from untangle.case_record import crypto, rules
from untangle.case_record.models import (
    Actor,
    ActorType,
    AttachmentKind,
    AttachmentState,
    CaseState,
    Channel,
    ClosingEvidence,
    DerivationReason,
    Resolution,
)
from untangle.copy_catalog import api as copy_api
from untangle.orchestration.nodes.intake import composition
from untangle.tenancy import config as tenancy_config
from untangle.voice import case_opening, latency, resume
from untangle.voice import session as llamadas
from untangle.voice.call import CallEngine
from untangle.voice.models import CallSession, EndReason, VoiceMode

from .conftest import AHORA, nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u16")

MI_NAVEGADOR = "7" * 64
OTRO_NAVEGADOR = "8" * 64
VENTANA = timedelta(minutes=15)
_ASEGURADO = Actor(actor_type=ActorType.INSURED)
_PRESENTE = AttachmentState(kind=AttachmentKind.PRESENT, reference="ref-1")
_VACIO = AttachmentState(kind=AttachmentKind.EMPTY)


async def _llamada_cortada(tenant_id: str, navegador: str) -> tuple[str, str]:
    """Una llamada de ese navegador que se corto con su caso. Devuelve caso y llamada."""
    case_id = await case_opening.open_for_call(tenant_id, language="en", now=AHORA)
    llamada = await llamadas.open_call(
        tenant_id=tenant_id,
        visitor_key_digest=navegador,
        language="en",
        voice_mode=VoiceMode.PRIMARY,
        now=AHORA,
    )
    llamada = await llamadas.attach_case(llamada, case_id=case_id)
    await llamadas.end_call(llamada, reason=EndReason.DROPPED, now=AHORA, resume_window=VENTANA)
    return case_id, llamada.call_id


async def _motor_nuevo(tenant_id: str) -> CallEngine:
    copy_api.install(copy_api.load())
    llamada = await llamadas.open_call(
        tenant_id=tenant_id,
        visitor_key_digest=MI_NAVEGADOR,
        language="en",
        voice_mode=VoiceMode.PRIMARY,
        now=AHORA + timedelta(minutes=1),
    )

    async def _sin_grafo(turn: object) -> object:  # pragma: no cover - no se usa
        raise AssertionError

    return CallEngine(
        call=llamada,
        config=tenancy_config.require(tenant_id),
        handle_turn=_sin_grafo,  # type: ignore[arg-type]
    )


async def test_un_corte_deja_el_caso_esperando_al_asegurado(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """BR6.1: un corte no es un final, es una pausa."""
    a, _ = dos_aseguradoras
    _, call_id = await _llamada_cortada(a, MI_NAVEGADOR)
    cortada = await llamadas.find_resumable(
        tenant_id=a, visitor_key_digest=MI_NAVEGADOR, now=AHORA + timedelta(minutes=1)
    )
    assert cortada is not None
    assert cortada.call_id == call_id
    assert cortada.end_reason is EndReason.DROPPED
    assert cortada.resume_until is not None


async def test_la_oferta_de_retomar_no_sale_antes_de_la_apertura(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """BR6.2. Saltarse la divulgacion porque 'ya la oyo la vez pasada' es
    exactamente el atajo que la compuerta existe para impedir."""
    a, _ = dos_aseguradoras
    await _llamada_cortada(a, MI_NAVEGADOR)
    motor = await _motor_nuevo(a)
    cortada = await llamadas.find_resumable(
        tenant_id=a, visitor_key_digest=MI_NAVEGADOR, now=AHORA + timedelta(minutes=1)
    )
    assert cortada is not None
    await motor.look_for_resumable(cortada)

    with pytest.raises(ValueError, match=r"BR6\.2"):
        motor.offer_resume()


async def test_despues_de_la_apertura_ofrece_seguir_con_el_caso(
    dos_aseguradoras: tuple[str, str],
) -> None:
    a, _ = dos_aseguradoras
    await _llamada_cortada(a, MI_NAVEGADOR)
    motor = await _motor_nuevo(a)
    caso_nuevo = await nuevo_caso(a)
    motor.call = await llamadas.attach_case(motor.call, case_id=caso_nuevo.case_id)
    await motor.opening_finished(at=AHORA + timedelta(minutes=1))
    cortada = await llamadas.find_resumable(
        tenant_id=a, visitor_key_digest=MI_NAVEGADOR, now=AHORA + timedelta(minutes=1)
    )
    assert cortada is not None
    await motor.look_for_resumable(cortada)

    dicha = motor.offer_resume()

    assert dicha is not None
    assert "open case" in str(dicha.text)


async def test_sin_caso_que_retomar_no_se_ofrece_nada(
    dos_aseguradoras: tuple[str, str],
) -> None:
    a, _ = dos_aseguradoras
    motor = await _motor_nuevo(a)
    assert motor.offer_resume() is None


async def test_aceptar_deja_la_marca_enlazada_al_caso_original(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """BR8.3: sin el enlace, la marca no distingue una retoma de una llamada
    nueva y NFR3 se contaria sobre el denominador equivocado."""
    a, _ = dos_aseguradoras
    case_id, call_id = await _llamada_cortada(a, MI_NAVEGADOR)
    motor = await _motor_nuevo(a)
    cortada = await llamadas.find_resumable(
        tenant_id=a, visitor_key_digest=MI_NAVEGADOR, now=AHORA + timedelta(minutes=1)
    )
    assert cortada is not None
    await motor.look_for_resumable(cortada)
    rastro = io.StringIO()
    observability.set_stream(rastro)

    assert motor.resume_accepted("yes", at=AHORA + timedelta(minutes=1))

    lineas = [json.loads(linea) for linea in rastro.getvalue().splitlines() if linea.strip()]
    marcas = [e for e in lineas if e["event"] == latency.RESUME_AFTER_DROP]
    assert len(marcas) == 1
    assert marcas[0]["case_id"] == case_id
    assert marcas[0]["dropped_call_id"] == call_id
    # Como termino la anterior: NFR3 cuenta cortes, y una llamada guardada no lo es.
    assert marcas[0]["previous_end_reason"] == "dropped"


async def test_llamar_por_otro_accidente_no_retoma_ni_deja_marca(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """BR6.4: una persona puede tener dos accidentes, y el caso anterior no se
    toca."""
    a, _ = dos_aseguradoras
    await _llamada_cortada(a, MI_NAVEGADOR)
    motor = await _motor_nuevo(a)
    cortada = await llamadas.find_resumable(
        tenant_id=a, visitor_key_digest=MI_NAVEGADOR, now=AHORA + timedelta(minutes=1)
    )
    assert cortada is not None
    await motor.look_for_resumable(cortada)
    rastro = io.StringIO()
    observability.set_stream(rastro)

    assert not motor.resume_accepted("no, another accident", at=AHORA)

    assert latency.RESUME_AFTER_DROP not in rastro.getvalue()


async def test_un_caso_ya_decidido_se_resume_antes_de_ofrecer(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """AC1.27.5: la persona llama para saber que paso; preguntarle en que se le
    ayuda antes de contarselo es la forma mas segura de que lo pregunte ella."""
    a, _ = dos_aseguradoras
    case_id, _ = await _llamada_cortada(a, MI_NAVEGADOR)
    await _decidir(a, case_id, comentario="Covered under the collision section.")

    motor = await _motor_nuevo(a)
    caso_nuevo = await nuevo_caso(a)
    motor.call = await llamadas.attach_case(motor.call, case_id=caso_nuevo.case_id)
    await motor.opening_finished(at=AHORA + timedelta(minutes=1))
    cortada = await llamadas.find_resumable(
        tenant_id=a, visitor_key_digest=MI_NAVEGADOR, now=AHORA + timedelta(minutes=1)
    )
    assert cortada is not None
    await motor.look_for_resumable(cortada)

    dicha = motor.offer_resume()

    assert dicha is not None
    texto = str(dicha.text)
    assert "approved" in texto
    assert "Covered under the collision section" in texto
    assert texto.index("approved") < texto.index("open case"), (
        "la oferta salio antes que el resultado"
    )


async def _decidir(tenant_id: str, case_id: str, *, comentario: str) -> None:
    """Cierra el caso como lo haria una ajustadora, por la API de U4."""
    for estado in (CaseState.CAPTURING, CaseState.VERIFYING, CaseState.DECIDING):
        await casos.apply_transition(
            tenant_id,
            case_id,
            estado,
            context=rules.TransitionContext(now=AHORA, actor=_ASEGURADO, channel=Channel.VOICE),
        )
    await casos.apply_transition(
        tenant_id,
        case_id,
        CaseState.DERIVED,
        context=rules.TransitionContext(
            now=AHORA,
            actor=_ASEGURADO,
            channel=Channel.VOICE,
            derivation_reason=DerivationReason.PERSON_REQUESTED,
        ),
    )
    await casos.close_case(
        tenant_id,
        case_id,
        resolution=Resolution.APPROVED,
        closing_evidence=ClosingEvidence(
            transcript=_PRESENTE,
            cited_clauses=_VACIO,
            fired_rules=_PRESENTE,
            trace_id=_PRESENTE,
            control_results=_PRESENTE,
        ),
        context=rules.TransitionContext(now=AHORA, actor=_ASEGURADO, channel=Channel.VOICE),
        comment=comentario,
    )


async def _retomable(tenant_id: str, navegador: str) -> CallSession:
    cortada = await llamadas.find_resumable(
        tenant_id=tenant_id, visitor_key_digest=navegador, now=AHORA + timedelta(minutes=1)
    )
    assert cortada is not None
    return cortada


async def test_lo_retomable_trae_la_pregunta_que_habia_quedado_pendiente(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Al decir que si, la agente retoma la pregunta con que el reporte se corto. Sale de
    lo que el caso ya tiene --la misma deduccion que hace la captura--, sin guardar nada."""
    copy_api.install(copy_api.load())
    a, _ = dos_aseguradoras
    case_id, _ = await _llamada_cortada(a, MI_NAVEGADOR)
    await casos.apply_transition(
        a,
        case_id,
        CaseState.CAPTURING,
        context=rules.TransitionContext(now=AHORA, actor=_ASEGURADO, channel=Channel.VOICE),
    )

    encontrado = await resume.find(
        await _retomable(a, MI_NAVEGADOR), tenant_id=a, now=AHORA, language="en"
    )

    assert encontrado is not None
    assert encontrado.pending_question == copy_api.t(composition.QUESTION_SAFETY, locale="en")


async def test_un_caso_ya_decidido_no_tiene_pregunta_que_retomar(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    copy_api.install(copy_api.load())
    a, _ = dos_aseguradoras
    case_id, _ = await _llamada_cortada(a, MI_NAVEGADOR)
    await _decidir(a, case_id, comentario="Covered.")

    encontrado = await resume.find(
        await _retomable(a, MI_NAVEGADOR), tenant_id=a, now=AHORA, language="en"
    )

    assert encontrado is not None
    assert encontrado.pending_question is None
