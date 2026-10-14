"""La despedida de un reporte completo dice como quedo el caso (US1.17, 2026-10-13).

Al terminar la captura el caso pasa a revision y las reglas deciden **en el fondo**; la
despedida de la llamada espera ese resultado un instante y dice lo que hay. Aqui el estado del
caso lo pone la prueba, que es lo unico que la despedida mira: las reglas y la revision de
cumplimiento no se ejecutan dentro de la llamada, y esta prueba comprueba justo eso.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from types import SimpleNamespace

import pytest

from untangle.case_record import api as casos
from untangle.case_record import crypto
from untangle.case_record.models import (
    Actor,
    ActorType,
    AttachmentKind,
    AttachmentState,
    ClosingEvidence,
    Resolution,
)
from untangle.case_record.rules import TransitionContext
from untangle.compliance.controls.api import HandoffReason
from untangle.copy_catalog import api as copy_api
from untangle.orchestration import case_context
from untangle.server import voice_routes
from untangle.voice import case_number, closing
from untangle.voice.call import CallEngine
from untangle.voice.models import EndReason

from .conftest import AHORA
from .test_call_engine import _completar_caso, _final_simple, _habla, _motor

pytestmark = pytest.mark.usefixtures("base_de_u16")

#: La espera de la despedida, acortada para la prueba: el valor de verdad es de `closing`.
ESPERA = timedelta(milliseconds=200)


def _presente(referencia: str) -> AttachmentState:
    return AttachmentState(kind=AttachmentKind.PRESENT, reference=referencia)


async def _cerrar_como_registrado(tenant_id: str, case_id: str) -> None:
    """Lo que hace el desenlace de las reglas, por la API de U4."""
    await casos.close_case(
        tenant_id,
        case_id,
        resolution=Resolution.REGISTERED,
        closing_evidence=ClosingEvidence(
            transcript=_presente(case_id),
            cited_clauses=AttachmentState(kind=AttachmentKind.EMPTY),
            fired_rules=_presente(case_id),
            trace_id=_presente("traza"),
            control_results=_presente("revision"),
        ),
        context=TransitionContext(now=AHORA, actor=Actor(actor_type=ActorType.SYSTEM)),
    )


async def _despedida(motor: CallEngine) -> str:
    dichas = [u async for u in motor.speak_turn(_habla(motor, "highway"), turn_id="t-1")]
    assert dichas[-1].end_reason is EndReason.COMPLETED
    return str(dichas[-1].text)


async def _motor_en_revision(tenant_id: str, cifrador: crypto.Cipher) -> tuple[CallEngine, str]:
    motor, _ = await _motor(tenant_id, guion=(_final_simple("Got it."),))
    await motor.opening_finished(at=AHORA)
    motor.result_wait = ESPERA
    motor.result_poll_seconds = 0.01
    case_id = motor.call.case_id
    assert case_id is not None
    await _completar_caso(tenant_id, case_id, cifrador)
    assert await case_context.begin_review(tenant_id=tenant_id, case_id=case_id, now=AHORA)
    return motor, case_id


async def test_un_caso_que_las_reglas_ya_cerraron_se_despide_registrado(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    a, _ = dos_aseguradoras
    motor, case_id = await _motor_en_revision(a, cifrador)
    await _cerrar_como_registrado(a, case_id)

    texto = await _despedida(motor)

    assert copy_api.t(closing.REGISTERED, locale="en") in texto
    vista = await casos.get_case(a, case_id)
    assert vista is not None
    assert case_number.spell(str(vista.case_number), language="en") in texto


async def test_un_caso_con_un_ajustador_se_despide_como_siempre(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    a, _ = dos_aseguradoras
    motor, case_id = await _motor_en_revision(a, cifrador)
    assert await case_context.derive_case(
        tenant_id=a,
        case_id=case_id,
        reason=HandoffReason.RULE,
        turn_id=None,
        now=AHORA,
    )

    texto = await _despedida(motor)

    assert "An adjuster reviews your case" in texto


async def test_si_las_reglas_no_terminaron_la_despedida_no_promete_nada(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    a, _ = dos_aseguradoras
    motor, _ = await _motor_en_revision(a, cifrador)

    texto = await _despedida(motor)

    assert "Your report is saved" in texto
    assert "adjuster" not in texto.lower()
    assert "registered" not in texto.lower()


async def test_la_despedida_espera_el_resultado_y_lo_dice_si_llega_a_tiempo(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """El fondo termina mientras la despedida espera: dice el resultado, no el neutral."""
    a, _ = dos_aseguradoras
    motor, case_id = await _motor_en_revision(a, cifrador)

    async def _el_fondo_termina() -> None:
        await asyncio.sleep(0.05)
        await _cerrar_como_registrado(a, case_id)

    fondo = asyncio.create_task(_el_fondo_termina())
    texto = await _despedida(motor)
    await fondo

    assert "doesn't need an adjuster's review" in texto
    assert "Your report is saved" not in texto


async def test_un_caso_que_nunca_paso_por_revision_se_despide_como_siempre(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """Sin cierre de captura de por medio (otra ruta, un doble) no hay nada que esperar."""
    a, _ = dos_aseguradoras
    motor, _ = await _motor(a, guion=(_final_simple("Got it."),))
    await motor.opening_finished(at=AHORA)
    assert motor.call.case_id is not None
    await _completar_caso(a, motor.call.case_id, cifrador)

    texto = await _despedida(motor)

    assert "An adjuster reviews your case" in texto


# La red de seguridad del fin de la llamada ----------------------------------------------


async def test_el_fin_de_la_llamada_resuelve_la_revision_y_un_fallo_no_la_rompe() -> None:
    llamadas: list[tuple[str, str]] = []

    async def _resuelve(case_id: str, /, *, tenant_id: str) -> None:
        llamadas.append((tenant_id, case_id))

    async def _revienta(case_id: str, /, *, tenant_id: str) -> None:
        del case_id, tenant_id
        msg = "la base no responde"
        raise RuntimeError(msg)

    llamada = SimpleNamespace(case_id="caso-1", call_id="llamada-1")

    await voice_routes._resolver_la_revision(
        SimpleNamespace(settle_review=_resuelve),  # type: ignore[arg-type]
        llamada,  # type: ignore[arg-type]
        "stonecroft",
    )
    await voice_routes._resolver_la_revision(
        SimpleNamespace(settle_review=_revienta),  # type: ignore[arg-type]
        llamada,  # type: ignore[arg-type]
        "stonecroft",
    )
    await voice_routes._resolver_la_revision(
        SimpleNamespace(settle_review=None),  # type: ignore[arg-type]
        llamada,  # type: ignore[arg-type]
        "stonecroft",
    )
    await voice_routes._resolver_la_revision(
        SimpleNamespace(settle_review=_resuelve),  # type: ignore[arg-type]
        SimpleNamespace(case_id=None, call_id="llamada-2"),  # type: ignore[arg-type]
        "stonecroft",
    )

    assert llamadas == [("stonecroft", "caso-1")], "la que no tiene caso no pide nada"
