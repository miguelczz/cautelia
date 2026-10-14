"""Anotar para las reglas: guardar, dejar rastro y volver a evaluar el caso.

Un ajustador anota el monto estimado, la cobertura disputada o la sospecha de fraude
(`triage_notes`). Esta pieza hace lo que ocurre alrededor: comprueba que el caso admite la
anotacion, la guarda con su entrada de historial, **vuelve a evaluar el conjunto de reglas
de esa aseguradora con todos los insumos del caso** y deja la evaluacion nueva como la
vigente.

**No cambia el estado del caso ni le dice nada al asegurado.** La anotacion es para las
reglas y para la vista de quien decide. Cuando la agente retome la conversacion, la cadena
de fondo vera lo anotado como cualquier otro insumo (`_insumos_de_triage`), pero este
camino no escribe en el chat ni en la llamada, y **lo que anota el personal** nunca llega a
la pantalla del visitante: nada que mencione montos llega al asegurado sin la firma de un
ajustador.

**El visitante que hace de ajustador tambien puede anotar, sobre su propio caso**
(2026-10-13), con tres diferencias que son toda la razon de ser de las otras piezas de este
modulo. (1) Queda como `insured` con el identificador de visitante de la decision, nunca
como una persona de la aseguradora. (2) **No toca lo que anoto el personal**: si la nota la
escribio un ajustador con credencial, el visitante ni la lee ni la pisa (`StaffNoteLockedError`);
la promesa de la pantalla del personal es que no la ve quien reporto el caso. Lo que el
visitante anota, en cambio, lo ve el y lo ve el personal. (3) **Es una escritura publica y
tiene techo**: guardar lo mismo no escribe nada, y pasadas `VISITOR_ANNOTATION_LIMIT` entradas
de historial el siguiente cambio se rechaza (`AnnotationLimitReachedError`). Para el personal,
nada de eso aplica.

**Los insumos completos entran por un puerto** (`install_rule_inputs`). Los dos que salen de
la conversacion --heridos y terceros con datos pendientes-- se derivan abriendo campos
sellados con el cifrador, y esa derivacion vive en la raiz de composicion, que es la que
sabe del cifrador. La bandeja no puede importarla (esta por debajo en el contrato de
capas) ni conviene duplicarla: dos derivaciones del mismo insumo son dos verdades. Asi que
la raiz enchufa **la misma funcion que usa la cadena de fondo**, y esta pieza la llama; el
puerto devuelve conversacion mas anotaciones, ya mezcladas en un solo sitio.

**Cada guardado es una evaluacion nueva, con identificador propio.** El de la cadena de
fondo se deriva de los insumos, y eso aqui seria un error: anotar, quitar y volver a anotar
devuelve a insumos que ya tuvieron una evaluacion, y el `ON CONFLICT` de `save_evaluation`
conservaria la vieja --con su hora vieja-- bajo la nueva, de modo que la vista, que muestra
la mas reciente, seguiria mostrando el estado anterior. El identificador lleva la clave de
idempotencia: un reintento de la misma peticion no duplica, y otra peticion no choca.

**El orden importa**, igual que al corregir un campo: primero se mira el recibo --una
repeticion no vuelve a escribir--, despues se escribe la anotacion con su rastro, despues
se evalua, y solo al final se anota el recibo. Al reves, una caida entre los dos dejaria una
clave marcada como usada sin que la evaluacion existiera, y el reintento legitimo
respondería que ya estaba hecho.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from untangle.case_record import api as casos
from untangle.case_record import history as historial
from untangle.case_record.models import (
    Actor,
    CaseChange,
    CaseState,
    ChangeKind,
    RecordType,
)
from untangle.inbox import decision, events, receipts, triage_notes
from untangle.inbox.triage_notes import TriageNote, TriageValues
from untangle.rules import api as reglas
from untangle.rules.fields import RuleValue
from untangle.rules.models import RuleEvaluation
from untangle.tenancy import api as tenancy
from untangle.tenancy.models import TenantId

#: Los estados en los que un caso admite anotaciones: con un ajustador (`derived`) o
#: esperando al asegurado. Fuera quedan el que aun se esta contando (`open`, `capturing`),
#: el que la agente todavia evalua (`verifying`, `deciding`) --sus reglas siguen corriendo
#: y una anotacion a mitad de la evaluacion competiria con ella-- y el cerrado, que
#: expone lo que se comprobo al cerrarlo (BR6.4 de U4).
ANNOTATABLE_STATES: frozenset[CaseState] = frozenset(
    {CaseState.DERIVED, CaseState.AWAITING_INSURED}
)

#: Cuantos caracteres de la huella entran en el identificador de la evaluacion; con el
#: prefijo sobra margen bajo el tope de 64 de `rule_evaluation.evaluation_id`.
_LARGO_DE_HUELLA = 32

#: El resumen del aviso a las demas pestanas. Lo escribe el codigo, no una persona.
_RESUMEN_DEL_AVISO = "anotaciones del ajustador"

#: Cuantas entradas de historial de anotacion puede dejar el visitante en su caso. Un guardado
#: deja a lo sumo tres (una por dato), asi que 30 son diez guardados completos: de sobra para
#: probar combinaciones y ver como cambian las reglas, y poca cosa para quien quiera llenar el
#: historial de un caso con una escritura publica y sin credencial. Se cuenta en entradas y no
#: en guardados porque es lo que el historial guarda; un ultimo guardado de tres datos puede
#: pasarse del numero en dos, y no se parte para que quepa.
VISITOR_ANNOTATION_LIMIT: Final = 30


class NotAnnotatableError(RuntimeError):
    """El caso no admite anotaciones ahora: otro estado, o un tipo de registro sin triage."""


class StaffNoteLockedError(RuntimeError):
    """La nota del caso la escribio el personal y quien entra con enlace no la pisa."""


class AnnotationLimitReachedError(RuntimeError):
    """El visitante ya dejo `VISITOR_ANNOTATION_LIMIT` entradas en el historial de su caso."""


class RuleInputsNotInstalledError(RuntimeError):
    """Nadie enchufo los insumos de las reglas.

    Falla en el acto en vez de evaluar solo con lo anotado: una evaluacion que ignora lo
    que la persona conto se ve igual que una buena, y mandaria al ajustador a decidir con
    un resultado de reglas que no es el del caso.
    """


#: Los insumos que lee el motor para un caso: lo derivado de la conversacion mas lo que
#: anoto un ajustador. La raiz de composicion enchufa la funcion que ya usa la cadena de
#: fondo, para que las dos evaluaciones lean lo mismo.
RuleInputsPort = Callable[[TenantId, str], Awaitable[Mapping[str, RuleValue]]]

_INSUMOS: RuleInputsPort | None = None


def install_rule_inputs(port: RuleInputsPort) -> None:
    """La raiz de composicion enchufa los insumos completos de las reglas."""
    global _INSUMOS
    _INSUMOS = port


def current_rule_inputs() -> RuleInputsPort:
    if _INSUMOS is None:
        msg = (
            "no hay insumos de reglas enchufados: la raiz de composicion llama a "
            "`install_rule_inputs` al montar la bandeja"
        )
        raise RuleInputsNotInstalledError(msg)
    return _INSUMOS


def reset_rule_inputs() -> None:
    """Desenchufa. Lo usan las pruebas para no filtrar un doble entre casos."""
    global _INSUMOS
    _INSUMOS = None


def can_annotate(*, state: CaseState, record_type: RecordType) -> bool:
    """Si un caso en ese estado y de ese tipo admite anotaciones.

    Una sola pregunta para la ruta y para la vista: la pantalla que decidiera por su cuenta
    cuando ofrecer el bloque escribiria la regla por segunda vez, y el dia que una cambie
    la otra seguiria diciendo lo de antes. Solo los siniestros: las reglas de triage miran
    heridos, terceros, monto y fraude, y una solicitud de cotizacion se decide por otro
    conjunto de reglas (U19).
    """
    return state in ANNOTATABLE_STATES and record_type is RecordType.CLAIM


def note_is_visitors(note: TriageNote | None) -> bool:
    """Si el visitante puede leer y cambiar esa nota: no hay ninguna, o la escribio el.

    La unica definicion de "la escribio el personal": la lectura del caso y el guardado
    preguntan lo mismo, y dos copias de la pregunta son dos sitios donde la nota del
    ajustador podria quedar a la vista.
    """
    return note is None or note.noted_by == decision.VISITOR_ACTOR_ID


async def visitor_has_budget(tenant_id: TenantId, case_id: str) -> bool:
    """Si al visitante le quedan anotaciones por hacer en este caso."""
    hechas = await _entradas_del_visitante(tenant_id, case_id)
    return hechas < VISITOR_ANNOTATION_LIMIT


async def _entradas_del_visitante(
    tenant_id: TenantId, case_id: str, *, en: tenancy.TenantSession | None = None
) -> int:
    actor = decision.actor_of(principal_id=None)
    assert actor.actor_id is not None  # noqa: S101 -- el visitante siempre lleva su identificador
    return await historial.count_by_actor(
        tenant_id,
        case_id,
        kind=ChangeKind.TRIAGE_NOTED,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        en=en,
    )


@dataclass(frozen=True)
class AnnotationApplied:
    """Lo que devuelve una anotacion aplicada, o la que ya estaba."""

    #: `None` solo cuando el visitante guardo lo mismo que ya estaba: no se escribio nada y por
    #: eso no hay recibo que dar.
    receipt_id: str | None
    #: La evaluacion que dejo esta peticion. `None` solo si ya no esta en la base --el
    #: caso se borro entre la peticion y su repeticion--.
    evaluation: RuleEvaluation | None
    #: Cierto cuando esta peticion no escribio nada porque la misma clave ya habia escrito.
    replayed: bool


def _evaluation_id(
    *,
    tenant_id: TenantId,
    case_id: str,
    ruleset_version: str,
    inputs: Mapping[str, RuleValue],
    idempotency_key: str,
) -> str:
    """Determinista por peticion: la misma clave da el mismo id, otra clave da otro.

    Deliberadamente **distinto** del de la cadena de fondo, que no lleva la clave: ver el
    docstring del modulo.
    """
    huella = json.dumps(
        {
            "tenant_id": tenant_id,
            "case_id": case_id,
            "ruleset_version": ruleset_version,
            "inputs": dict(inputs),
            "idempotency_key": idempotency_key,
        },
        sort_keys=True,
    )
    return f"reval-{hashlib.sha256(huella.encode('utf-8')).hexdigest()[:_LARGO_DE_HUELLA]}"


def _entrada_del_historial(
    cambio: triage_notes.TriageChange, *, case_id: str, actor: Actor, now: datetime
) -> CaseChange:
    """La entrada de un dato anotado: quien, cuando, cual y de que a que.

    Los valores van en `detail`, en el registro tecnico (`unset`, `true`, `false`, el
    entero), y no sellados: ninguno es dato personal --son un entero estimado por el
    ajustador y dos si/no--, y asi el historial se lee sin el cifrador.
    """
    return CaseChange(
        change_id=historial.new_change_id(),
        case_id=case_id,
        change_kind=ChangeKind.TRIAGE_NOTED,
        field_key=cambio.field_key,
        actor=actor,
        detail=f"{cambio.before} -> {cambio.after}",
        changed_at=now,
    )


async def _evaluacion_guardada(
    tenant_id: TenantId, case_id: str, evaluation_id: str
) -> RuleEvaluation | None:
    guardadas = await reglas.evaluations_for(tenant_id, case_id)
    return next((e for e in guardadas if e.evaluation_id == evaluation_id), None)


async def _evaluacion_vigente(tenant_id: TenantId, case_id: str) -> RuleEvaluation | None:
    """La mas reciente del caso, que es la que la vista muestra."""
    guardadas = await reglas.evaluations_for(tenant_id, case_id)
    return guardadas[-1] if guardadas else None


async def apply(  # noqa: PLR0913 -- el caso, lo anotado, la clave, quien y el reloj
    tenant_id: TenantId,
    *,
    case_id: str,
    values: TriageValues,
    idempotency_key: str,
    principal_id: str | None,
    now: datetime,
) -> AnnotationApplied:
    """Anota, deja su rastro, reevalua las reglas y guarda la evaluacion nueva.

    `principal_id` es la persona de la aseguradora que anota, o `None` cuando quien anota
    entro con el enlace de su propio caso: el rastro lo atribuye entonces a un visitante, igual
    que la decision.

    Levanta `CaseNotFoundError` si el caso no existe para esa aseguradora (la politica de
    fila hace que "de otra aseguradora" y "no existe" sean lo mismo), `NotAnnotatableError`
    si el estado o el tipo no lo admiten, `RecycledKeyError` si la clave se uso para otra
    peticion y `RuleNotConfiguredError` si la aseguradora no tiene reglas cargadas. Solo para
    el visitante: `StaffNoteLockedError` si la nota la escribio el personal y
    `AnnotationLimitReachedError` si ya llego al tope de entradas. Un visitante que guarda lo
    que ya estaba no escribe nada --ni anotacion, ni evaluacion, ni recibo, ni aviso-- y recibe
    la evaluacion vigente del caso.
    """
    por_visitante = principal_id is None
    actor = decision.actor_of(principal_id=principal_id)
    anotada_por = decision.VISITOR_ACTOR_ID if principal_id is None else principal_id
    huella = receipts.digest_of(
        case_id, *(triage_notes.describe(valor) for valor in values.as_mapping().values())
    )
    anterior = await receipts.reuse_or_none(
        tenant_id,
        operation=receipts.Operation.TRIAGE_NOTE,
        idempotency_key=idempotency_key,
        request_digest=huella,
    )
    if anterior is not None:
        return AnnotationApplied(
            receipt_id=anterior.receipt_id,
            evaluation=await _evaluacion_guardada(tenant_id, case_id, anterior.result_ref),
            replayed=True,
        )

    caso = await casos.get_case(tenant_id, case_id)
    if caso is None:
        msg = f"no hay caso '{case_id}' en esta aseguradora"
        raise casos.CaseNotFoundError(msg)
    if not can_annotate(state=caso.state, record_type=caso.record_type):
        msg = (
            f"un caso '{caso.record_type.value}' en '{caso.state.value}' no admite anotaciones "
            "para las reglas: solo uno derivado o que espera al asegurado"
        )
        raise NotAnnotatableError(msg)
    # Antes de escribir nada: una aseguradora sin reglas no puede reevaluar, y una
    # anotacion guardada sin su evaluacion deja la vista diciendo lo de antes.
    reglas.required_inputs(tenant_id=tenant_id)

    # 1. La anotacion y su rastro, en **una sola transaccion**: una anotacion sin la
    #    entrada que dice quien la hizo es una perdida de auditoria.
    async with tenancy.session_for(tenant_id) as sesion:
        previa = await triage_notes.read_for_update(sesion, tenant_id, case_id)
        if por_visitante and not note_is_visitors(previa):
            msg = f"la nota del caso '{case_id}' la escribio el personal: el visitante no la cambia"
            raise StaffNoteLockedError(msg)
        cambios = triage_notes.changes_between(
            previa.values if previa is not None else TriageValues(), values
        )
        sin_cambios = por_visitante and not cambios
        if cambios:
            # La cuenta va con la sesion que ya tiene la fila bloqueada: dos guardados del
            # visitante a la vez no leen el mismo "me quedan".
            if por_visitante and (
                await _entradas_del_visitante(tenant_id, case_id, en=sesion)
                >= VISITOR_ANNOTATION_LIMIT
            ):
                msg = (
                    f"el visitante ya dejo {VISITOR_ANNOTATION_LIMIT} entradas de "
                    f"anotacion en el caso '{case_id}'"
                )
                raise AnnotationLimitReachedError(msg)
            await triage_notes.write(
                sesion,
                tenant_id,
                case_id,
                values,
                noted_by=anotada_por,
                now=now,
            )
            for cambio in cambios:
                await historial.append(
                    tenant_id,
                    _entrada_del_historial(cambio, case_id=case_id, actor=actor, now=now),
                    en=sesion,
                )
    if sin_cambios:
        return AnnotationApplied(
            receipt_id=None,
            evaluation=await _evaluacion_vigente(tenant_id, case_id),
            replayed=False,
        )

    # 2. La evaluacion con todos los insumos del caso, ya con lo recien anotado.
    insumos = await current_rule_inputs()(tenant_id, case_id)
    vista = await reglas.evaluate(tenant_id, insumos)
    evaluacion = await reglas.save_evaluation(
        RuleEvaluation(
            evaluation_id=_evaluation_id(
                tenant_id=tenant_id,
                case_id=case_id,
                ruleset_version=vista.ruleset_version,
                inputs=insumos,
                idempotency_key=idempotency_key,
            ),
            tenant_id=tenant_id,
            case_id=case_id,
            ruleset_version=vista.ruleset_version,
            category=vista.category,
            fired_rules=vista.fired_rules,
            inputs_snapshot=vista.inputs_snapshot,
            explanation_key=vista.explanation_key,
            evaluated_at=now,
        )
    )

    # 3. El recibo, al final.
    recibo = await receipts.record(
        tenant_id,
        operation=receipts.Operation.TRIAGE_NOTE,
        idempotency_key=idempotency_key,
        case_id=case_id,
        request_digest=huella,
        result_ref=evaluacion.evaluation_id,
        now=now,
    )

    # 4. El aviso a las demas pestanas abiertas, despues de que todo este escrito.
    await events.append(
        tenant_id,
        case_id=case_id,
        kind=events.EventKind.CASE_UPDATED,
        summary=_RESUMEN_DEL_AVISO,
        language=caso.language,
        now=now,
    )
    return AnnotationApplied(receipt_id=recibo.receipt_id, evaluation=evaluacion, replayed=False)
