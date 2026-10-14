"""La vista de un caso: los seis bloques, pedidos a quien los guarda (BR2.1 a BR2.6).

**La bandeja no guarda copia de ninguno.** El caso, sus campos, su transcripcion y
su historial son de U4; las citas de U8; la regla disparada de U9; el resultado de
los cuatro controles de U10; el resumen de traza de U5. Esta pieza los pide y los
junta. El dia que guardara su propia copia de cualquiera habria dos versiones de la
verdad y una forma de que discrepen, y la pantalla podria mostrar algo distinto de
lo que el sistema decidio --que es exactamente lo que esta vista existe para
impedir--.

**Por eso se mide el conteo de consultas.** Reunir seis bloques es la forma mas
facil de convertir una pantalla en veinte idas a la base sin que nadie lo note. Las
lecturas se piden **a la vez**, no una detras de otra: no dependen entre si, y
encadenarlas sumaria sus latencias por nada.

**"Sin clausula" y "no pude verificar" viajan distintos** (BR2.5). Son dos valores
distintos en el estado, en la traza y en el reporte de evaluaciones, y aqui
tambien: colapsarlos contaminaria con fallos de infraestructura una respuesta que
si se verifico.

**La transcripcion llega ya redactada de U3 y esta unidad no la destapa** (BR2.3).
Lo que sale son las etiquetas que U3 escribio en su momento; el valor completo vive
en el campo del caso, que viaja al lado, y relacionarlos es trabajo de la pantalla.
Ninguna funcion de aqui tiene forma de pedir el texto sin redactar.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from untangle.base import Locale
from untangle.case_record import api as casos
from untangle.case_record import history as historial
from untangle.case_record.models import (
    CaseChange,
    CaseField,
    CaseState,
    Channel,
    Priority,
    RecordType,
    Resolution,
    TranscriptTurn,
)
from untangle.chat import citation as citas
from untangle.compliance.controls import api as cumplimiento
from untangle.compliance.controls.models import ComplianceReview
from untangle.policy_rag.citations import api as u8
from untangle.rules import repository as reglas
from untangle.rules.models import RuleEvaluation
from untangle.telemetry.traces import api as trazas
from untangle.telemetry.traces.models import TraceSummary
from untangle.tenancy.models import TenantId

#: Cuantas consultas cuesta abrir un caso, contadas de verdad por su prueba. Es el
#: objetivo medible de esta vista y no un numero decorativo: reunir seis bloques es
#: la forma mas facil de convertir una pantalla en veinte idas a la base sin que
#: nadie lo note, y si alguien anade un bloque pidiendolo dentro de un bucle, la
#: prueba que las cuenta se cae y obliga a verlo.
#:
#: Las nueve: el caso y sus campos (dos, y **una sola vez** --por eso U4 las
#: devuelve juntas--), las partes, la transcripcion, el historial, las respuestas de
#: cobertura con sus comprobaciones (dos), la evaluacion de reglas, la revision de
#: cumplimiento y el resumen de traza. La decima es la expansion de las citas
#: contra el corpus, **una sola** para el caso entero: la primera version la hacia
#: dentro del bucle de respuestas y esta misma prueba la encontro.
CONSULTAS_POR_CASO = 10


@dataclass(frozen=True)
class CoverageAnswerView:
    """Una respuesta de cobertura con sus citas expandidas.

    `outcome` es el valor de U8 tal cual --`verified`, `rejected`,
    `no_clause_found`, `unverifiable`--. La pantalla le pone etiqueta distinta a
    cada uno; aqui no se agrupan.
    """

    answer_id: str
    outcome: str
    question_redacted: str
    answer_language: Locale
    clause_language: Locale | None
    citations: tuple[citas.CitationDetail, ...]
    created_at: datetime


@dataclass(frozen=True)
class CaseDetail:
    """Todo lo que la vista de un caso muestra, sin un solo dato personal en claro.

    Los valores de los campos **no viajan aqui**: lo que viaja es su clave, su
    estado y si esta completo. El valor sellado es de U4 y se descifra en el unico
    sitio que sabe hacerlo; una vista que lo trajera seria un punto de salida mas.
    """

    case_id: str
    case_number: str
    record_type: RecordType
    state: CaseState
    resolution: Resolution | None
    channel: Channel
    language: Locale
    priority: Priority
    derivation_reason: str | None
    completeness_complete: int
    completeness_total: int
    completeness_per_field: dict[str, bool]
    completeness_optional: frozenset[str]
    fields: tuple[CaseField, ...]
    transcript: tuple[TranscriptTurn, ...]
    history: tuple[CaseChange, ...]
    coverage_answers: tuple[CoverageAnswerView, ...]
    rule_evaluation: RuleEvaluation | None
    compliance: ComplianceReview | None
    trace: TraceSummary | None
    updated_at: datetime


async def _expandir(tenant_id: TenantId, respuestas: Any) -> tuple[CoverageAnswerView, ...]:
    """Convierte las respuestas de U8 en lo que la pantalla muestra.

    Las citas se expanden con la misma pieza que usa el chat (U13): la version y el
    texto salen del corpus y no del estado, porque es lo que la persona va a
    comparar contra su poliza. Una cita cuya clausula ya no esta en el corpus se
    cae con su evento, igual que alli.

    **Una sola consulta al corpus para el caso entero**, no una por respuesta. La
    primera version las expandia dentro del bucle y costaba una ida a la base por
    respuesta de cobertura; lo encontro la prueba que cuenta consultas, que es
    exactamente para lo que existe.
    """
    todas = [comprobacion for _, comprobaciones in respuestas for comprobacion in comprobaciones]
    detalles = await citas.details_for(tenant_id, todas)
    por_clausula = {detalle.clause_id: detalle for detalle in detalles}

    salida: list[CoverageAnswerView] = []
    for respuesta, comprobaciones in respuestas:
        detalle = tuple(
            por_clausula[comprobacion.clause_id]
            for comprobacion in comprobaciones
            if comprobacion.clause_id in por_clausula
        )
        salida.append(
            CoverageAnswerView(
                answer_id=respuesta.answer_id,
                outcome=respuesta.outcome.value,
                question_redacted=respuesta.question_redacted,
                answer_language=respuesta.answer_language,
                clause_language=respuesta.clause_language,
                citations=detalle,
                created_at=respuesta.created_at,
            )
        )
    return tuple(salida)


async def detail_for(tenant_id: TenantId, case_id: str) -> CaseDetail | None:
    """El caso con toda su evidencia, o nada.

    "Nada" significa las dos cosas a la vez --no existe, o es de otra
    aseguradora-- y esta bien: la politica de fila filtra antes, asi que este
    codigo no tiene forma de distinguirlas aunque quisiera.
    """
    cabecera = await casos.summary_with_fields(tenant_id, case_id)
    if cabecera is None:
        return None
    caso, campos = cabecera

    # Los bloques restantes no dependen entre si: se piden a la vez. Encadenarlos
    # sumaria seis latencias para producir exactamente el mismo resultado.
    transcripcion, cambios, respuestas, evaluaciones, revision, traza = await asyncio.gather(
        casos.transcript_of(tenant_id, case_id),
        historial.of_case(tenant_id, case_id),
        u8.answers_for(tenant_id, case_id),
        reglas.evaluations_for(tenant_id, case_id),
        cumplimiento.latest_review(tenant_id, case_id),
        trazas.trace_summary_for_staff(case_id, tenant_id=tenant_id),
    )

    return CaseDetail(
        case_id=caso.case_id,
        case_number=caso.case_number,
        record_type=caso.record_type,
        state=caso.state,
        resolution=caso.resolution,
        channel=caso.channel,
        language=caso.language,
        priority=caso.priority,
        derivation_reason=caso.derivation_reason,
        completeness_complete=caso.completeness.complete,
        completeness_total=caso.completeness.total,
        completeness_per_field=dict(caso.completeness.per_field),
        completeness_optional=caso.completeness.optional,
        fields=campos,
        transcript=transcripcion,
        history=cambios,
        coverage_answers=await _expandir(tenant_id, respuestas),
        # La ultima evaluacion es la vigente: las anteriores son de turnos previos,
        # y mostrarlas juntas diria que se dispararon varias reglas a la vez.
        rule_evaluation=evaluaciones[-1] if evaluaciones else None,
        compliance=revision,
        trace=traza,
        updated_at=caso.updated_at,
    )
