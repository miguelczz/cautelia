"""La reanudacion (paso 6 de U12): BR3.1, BR3.2, BR3.3 y la compuerta dura BR3.4.

Cuatro bloques, en el orden en que el paso los declara:

1. **Reanudar es leer el ultimo punto de control** (BR3.1, BR3.2), a traves de
   `resume_state`, con un `TenantCheckpointSaver` **nuevo** en cada lectura --
   simula el reinicio del proceso sin necesitar reiniciar nada de verdad,
   porque la pieza no guarda estado propio entre llamadas (su docstring lo dice:
   "una sola instancia sirve a toda aseguradora").
2. **La sesion abandonada no decide nada** (BR3.3): se comprueba contra
   `case_record.api.get_case`, no contra una suposicion -- el caso tiene que
   seguir exactamente como estaba.
3. **La compuerta dura, BR3.4**: dos casos de la misma aseguradora comparten
   poliza; el que no tiene historia propia no ve la del otro, y se compara
   contra un tercer caso sin ninguna relacion para probar que "nada que
   ofrecer" es literalmente el mismo valor en los dos casos.
4. **`interrupt()` de verdad** (BR4.1, BR4.4): un grafo minimo, compilado con
   nuestro checkpointer, para probar que `raise_interrupt` suspende de verdad y
   que `Command(resume=...)` continua con la decision.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TypedDict

import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from untangle.case_record import api as casos
from untangle.case_record import crypto
from untangle.orchestration.abandonment import mark_abandoned
from untangle.orchestration.checkpoint import TenantCheckpointSaver
from untangle.orchestration.pause import PauseReason, raise_interrupt
from untangle.orchestration.pause_repository import DatabaseHumanReviewRequestStore
from untangle.orchestration.resume import ResumeState, resume_state

from .conftest import nuevo_caso
from .test_checkpointer import _checkpoint, _config, _metadata

pytestmark = pytest.mark.usefixtures("base_de_u12")

_AHORA = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)

_SIN_NADA_QUE_OFRECER = ResumeState(has_checkpoint=False, open_pause_reason=None)


# --- 1. Reanudar es leer el ultimo punto de control (BR3.1, BR3.2) ------------


async def test_reanudar_tras_un_reinicio_simulado_lee_lo_confirmado(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """Un `TenantCheckpointSaver` nuevo -- el reinicio -- lee lo que el anterior escribio."""
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    pausas = DatabaseHumanReviewRequestStore()

    antes_del_reinicio = TenantCheckpointSaver(cipher=cifrador)
    guardado = await antes_del_reinicio.aput(
        _config(propia, caso.case_id),
        _checkpoint("confirmo la placa ABC123"),
        _metadata(0),
        {},
    )

    # "El proceso se reinicia": una instancia nueva, sin nada compartido con la
    # anterior salvo la base.
    despues_del_reinicio = TenantCheckpointSaver(cipher=cifrador)
    estado = await resume_state(
        despues_del_reinicio, pausas, tenant_id=propia, case_id=caso.case_id
    )

    assert estado.has_checkpoint is True
    assert estado.open_pause_reason is None

    # Y el punto de control es de verdad el que se escribio: no solo "hay uno".
    tupla = await despues_del_reinicio.aget_tuple(_config(propia, caso.case_id))
    assert tupla is not None
    assert tupla.checkpoint["channel_values"]["texto"] == "confirmo la placa ABC123"
    assert (
        tupla.config["configurable"]["checkpoint_id"] == guardado["configurable"]["checkpoint_id"]
    )


# --- 2. La sesion abandonada no decide nada (BR3.3) ----------------------------


async def test_marcar_abandonado_abre_la_pausa_sin_tocar_el_caso(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    antes = await casos.get_case(propia, caso.case_id)
    assert antes is not None
    pausas = DatabaseHumanReviewRequestStore()

    pausa = await mark_abandoned(pausas, tenant_id=propia, case_id=caso.case_id, now=_AHORA)

    assert pausa.reason is PauseReason.INCOMPLETE_CAPTURE

    despues = await casos.get_case(propia, caso.case_id)
    assert despues is not None
    # Nada del caso cambio: ni su estado, ni su resolucion, ni su completitud.
    # "Sin decidir nada" es literal -- si esta prueba fallara aqui, seria
    # porque `mark_abandoned` empezo a tocar el caso, que es exactamente lo que
    # BR3.3 prohibe.
    assert despues.state == antes.state
    assert despues.resolution == antes.resolution
    assert despues.completeness == antes.completeness


async def test_marcar_abandonado_dos_veces_deja_una_sola_pausa_viva(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Dos avisos de abandono (dos ritmos de fondo que corren, por ejemplo) no duplican la pausa."""
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    pausas = DatabaseHumanReviewRequestStore()

    primera = await mark_abandoned(pausas, tenant_id=propia, case_id=caso.case_id, now=_AHORA)
    segunda = await mark_abandoned(pausas, tenant_id=propia, case_id=caso.case_id, now=_AHORA)

    assert segunda.request_id == primera.request_id


# --- 3. La compuerta dura: BR3.4 -----------------------------------------------


async def test_br3_4_la_poliza_compartida_no_ofrece_el_caso_ajeno(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """Compuerta dura. Un solo fallo aqui detiene la entrega (BR3.4, AC1.19.3).

    Tres casos de la misma aseguradora:

    - `con_historia`: la poliza de ejemplo, con un punto de control y una pausa
      abierta -- "el primer navegador dejo un caso a medias" (AC1.19.3).
    - `misma_poliza_sin_historia`: **la misma poliza**, un `case_id` que ese
      primer navegador nunca conocio -- "el segundo navegador se identifica con
      la misma poliza de ejemplo".
    - `sin_relacion`: otra poliza, sin ningun punto de control ni pausa --
      "una sesion sin casos abiertos".

    La aserccion que importa es la de igualdad exacta entre las dos ultimas:
    si `resume_state` alguna vez empezara a mirar la poliza en vez del
    `case_id`, esta prueba es la que lo veria, porque las dos comparten poliza
    y solo una de ellas tiene algo que ofrecer.

    **Esta prueba cierra la mitad de la compuerta, no la compuerta entera.**
    BR3.4 pide que la respuesta del segundo navegador sea identica "en texto y
    en estado". Aqui se comprueba **el estado**: `ResumeState` campo por campo,
    que es todo lo que existe en este paso. El **texto** -- la respuesta que el
    segundo navegador de verdad recibe -- sale de `handle_turn`, que es del paso
    7, y su mitad de esta compuerta se verifica ahi. Decirlo asi no es una
    salvedad: una compuerta dura que parezca cerrada estando a medias es peor
    que una que se declare a medias.
    """
    _, propia = dos_aseguradoras
    poliza_publica = "POL-000001"

    con_historia = await nuevo_caso(propia, policy_ref=poliza_publica)
    misma_poliza_sin_historia = await nuevo_caso(propia, policy_ref=poliza_publica)
    sin_relacion = await nuevo_caso(propia, policy_ref="POL-000002")

    checkpointer = TenantCheckpointSaver(cipher=cifrador)
    pausas = DatabaseHumanReviewRequestStore()
    await checkpointer.aput(
        _config(propia, con_historia.case_id),
        _checkpoint("a mitad del bloque de vehiculo"),
        _metadata(0),
        {},
    )
    await mark_abandoned(pausas, tenant_id=propia, case_id=con_historia.case_id, now=_AHORA)

    # Control positivo: el propio caso, por su propio `case_id`, si tiene algo
    # que ofrecer. Sin esto, un `resume_state` que siempre devolviera "nada"
    # pasaria igual las dos aserciones de abajo.
    estado_propio = await resume_state(
        checkpointer, pausas, tenant_id=propia, case_id=con_historia.case_id
    )
    assert estado_propio.has_checkpoint is True
    assert estado_propio.open_pause_reason is PauseReason.INCOMPLETE_CAPTURE

    # El segundo navegador, con la misma poliza pero su propio `case_id` nuevo:
    # nada que ofrecer.
    estado_poliza_compartida = await resume_state(
        checkpointer, pausas, tenant_id=propia, case_id=misma_poliza_sin_historia.case_id
    )
    assert estado_poliza_compartida == _SIN_NADA_QUE_OFRECER

    # Identico, campo por campo, a una sesion sin ninguna relacion con el
    # primer caso: la mitad "en estado" de BR3.4. La mitad "en texto" la cierra
    # el paso 7 sobre `handle_turn` (ver el docstring).
    estado_sin_relacion = await resume_state(
        checkpointer, pausas, tenant_id=propia, case_id=sin_relacion.case_id
    )
    assert estado_poliza_compartida == estado_sin_relacion


# --- 4. `interrupt()` de verdad: suspende y `Command(resume=...)` continua ----


class _EstadoDeJuguete(TypedDict):
    """El estado minimo de un grafo de una sola pieza, solo para esta prueba.

    No es `GraphState` (paso 3): este grafo no representa ningun nodo real de
    la unidad, existe solo para compilar algo de verdad sobre nuestro
    checkpointer y comprobar la semantica de `interrupt()`/`Command(resume=...)`
    sin esperar al grafo de produccion, que es del paso 7.
    """

    motivo_de_la_pausa: str | None
    decision: str | None


def _nodo_que_deriva(estado: _EstadoDeJuguete) -> _EstadoDeJuguete:
    decidido = raise_interrupt(PauseReason.COMPLIANCE_REFERRAL)
    return {"motivo_de_la_pausa": None, "decision": decidido}


async def test_interrupt_real_suspende_el_grafo_y_command_resume_continua(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    checkpointer = TenantCheckpointSaver(cipher=cifrador)

    grafo = StateGraph(_EstadoDeJuguete)
    # `mypy` no resuelve el sobrecargado de `add_node` contra un `TypedDict` de
    # prueba definido fuera de la biblioteca (friccion conocida de los stubs de
    # LangGraph, no de este codigo): el grafo de produccion es del paso 7 y
    # usara `GraphState`, no este tipo de usar y tirar.
    grafo.add_node("deriva", _nodo_que_deriva)  # type: ignore[call-overload]
    grafo.add_edge(START, "deriva")
    grafo.add_edge("deriva", END)
    compilado = grafo.compile(checkpointer=checkpointer)

    config: RunnableConfig = {"configurable": {"tenant_id": propia, "thread_id": caso.case_id}}

    suspendido = await compilado.ainvoke({"motivo_de_la_pausa": None, "decision": None}, config)

    # El grafo no llego a `END`: `decision` nunca se escribio, y el resultado
    # trae la interrupcion con nuestro motivo, no un texto libre del modelo.
    assert suspendido.get("decision") is None
    interrupciones = suspendido.get("__interrupt__")
    assert interrupciones
    assert interrupciones[0].value == {"reason": PauseReason.COMPLIANCE_REFERRAL.value}

    retomado = await compilado.ainvoke(Command(resume="revisado_por_ajustador"), config)

    assert retomado["decision"] == "revisado_por_ajustador"
    assert "__interrupt__" not in retomado or not retomado["__interrupt__"]
