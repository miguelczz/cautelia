"""`mise run synthetic:seed`: carga los casos sembrados por la API de U4 (U7, F6, BR6.3).

Lee los casos que la generacion dejo en `app/data/tenants/*/cases/` y crea cada
uno **por la superficie publica de U4** --`create_case`, `append_turn`,
`set_field`, `apply_transition` y `close_case`-- con origen `generator`, que es el
que el borrado de datos de visitantes no toca (BR4.6 de U4). Nunca con SQL
directo: la siembra pasa por las mismas reglas que cualquier otro consumidor, y
un caso sembrado que no se pudiera crear asi seria un caso que el aplicativo no
podria tener.

**Por que vive aqui y no en `untangle.synthetic_data`** (FD-U7-9): el contrato de
capas deja el generador **debajo** del registro del caso, para que U8 lea los
modelos del corpus sin ciclos. La raiz de composicion es la capa que puede usar
la API de U4 y la que construye el cifrador.

Cuatro cosas que hace por cada caso, y las tres primeras son reglas de U4:

1. **Redacta cada turno antes de anexarlo** (C-13, SEC-U4.6): `append_turn` solo
   acepta texto redactado, y los datos personales sembrados son ficticios pero
   tienen la forma real, que es justo lo que la redaccion tapa.
2. **Declara el motivo al derivar** (BR3.7): los derivados, los que esperan al
   asegurado y los cerrados por decision de una persona pasan por `derived` con
   su motivo, y quien pidio una persona queda con prioridad alta (BR3.8).
3. **Cierra con la evidencia de cierre de U4** (BR6.3, NFR-U4-9): la
   transcripcion esta presente --su referencia es la clave del caso sembrado, que
   es donde se recupera--. Las reglas de un caso que paso por la decision van
   presentes (ver el punto 4); los otros tres adjuntos van **vacios**: el
   generador no cito clausulas, no dejo traza ni resultados de controles, y lo
   declara porque sabe que no existen, no porque nadie los mirara.
4. **Evalua las reglas reales de su aseguradora cuando el caso ya paso por la
   decision** (`evaluates_rules`): con los insumos que el aplicativo vivo deriva
   del caso (`composition.insumos_del_caso`, la misma funcion, no una copia) y por
   el mismo nodo `decision` que guarda la evaluacion, de modo que la vista del caso
   de ejemplo explica como termino. **No se fuerza ningun resultado**: la categoria
   es la que dan las reglas con los datos del caso, aunque no cuadre con como esta
   sembrado; esa incoherencia es del dato de ejemplo y se corrige ahi, nunca en la
   regla ni aqui. El caso que sigue en captura, en verificacion, en decision o que
   un ajustador recibio a peticion de la persona no tiene evaluacion, igual que en
   vivo.

**Quien cierra, igual que en vivo** (2026-10-13). Un caso cerrado por las reglas (`registered`,
T6) lo cierra el sistema; uno cuya resolucion solo puede poner el personal de la aseguradora
(aprobado, rechazado, enviado a la aseguradora; T9, desde `derived`) lo cierra **una persona de su
configuracion** (`tenancy` -> `staff`) con el rol que la tabla de permisos exige para esa decision,
como `inbox.decision.decide`. Asi el historial del ejemplo dice lo que en vivo solo puede decir, y
la vista "quien decidio y cuando" lo cuenta sin inferirlo de la resolucion. Ningun identificador de
persona vive en este codigo: sale de la configuracion de la aseguradora.

Es idempotente: un caso que ya existe en el estado que dice su archivo se deja
como esta. Uno que existe en **otro** estado detiene la siembra nombrandolo: es un
caso sembrado a medias, o uno que alguien movio, y los dos hay que verlos. La unica
cosa que hace sobre uno que esta bien es **completarle la evaluacion de reglas si no
tiene ninguna** (un caso sembrado antes de que la siembra evaluara): no toca nada
mas y no borra nada, y sembrar otra vez no agrega una segunda.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from untangle import paths
from untangle.case_record import api
from untangle.case_record.crypto import Cipher, EncryptionKeyMissingError
from untangle.case_record.models import (
    Actor,
    ActorType,
    AttachmentKind,
    AttachmentState,
    CaseField,
    CaseState,
    Channel,
    ClosingEvidence,
    DerivationReason,
    FieldStatus,
    Origin,
    RecordType,
    Resolution,
    Speaker,
)
from untangle.case_record.rules import TransitionContext
from untangle.case_record.transcript import TurnDraft
from untangle.compliance.redaction.api import redact
from untangle.inbox import actions as inbox_actions
from untangle.inbox import api as inbox_api
from untangle.orchestration.nodes.decision import node as decision_node
from untangle.rules import api as rules_api
from untangle.rules.models import RuleNotConfiguredError
from untangle.server import composition
from untangle.settings import Settings
from untangle.synthetic_data.cases import SeededCaseLoadError, load_seeded_cases
from untangle.synthetic_data.models import SeededCaseRecord, SeededSpeaker
from untangle.tenancy import api as tenancy
from untangle.tenancy import session

__all__ = [
    "SEED_ACTOR",
    "SeedError",
    "SeedOutcome",
    "closing_actor_for",
    "closing_evidence_for",
    "evaluates_rules",
    "main",
    "path_to",
    "seed_all",
    "seed_case",
    "seeded_case_id",
]

#: Quien hace cada cambio de la siembra: el sistema, no una persona ni la agente. La unica
#: excepcion es el cierre que en vivo pone el personal de la aseguradora (`closing_actor_for`).
SEED_ACTOR = Actor(actor_type=ActorType.SYSTEM)

#: La accion de la bandeja que produce cada resolucion: la inversa de `inbox.actions.RESOLUTION_OF`,
#: derivada de ella para que no haya dos tablas que puedan discrepar. `registered` no esta: no la
#: produce ninguna accion de la bandeja, la ponen las reglas.
_ACCION_DE: dict[Resolution, inbox_actions.InboxAction] = {
    resolucion: accion for accion, resolucion in inbox_actions.RESOLUTION_OF.items()
}

_VACIO = AttachmentState(kind=AttachmentKind.EMPTY)


class SeedError(RuntimeError):
    """Un caso no se pudo sembrar como dice su archivo. El mensaje nombra la clave."""


@dataclass(frozen=True)
class SeedOutcome:
    """Lo que paso con un caso sembrado."""

    case_key: str
    case_id: str
    state: CaseState
    created: bool
    #: La categoria de la evaluacion de reglas que tiene el caso, o `None` si no paso por la
    #: decision (`evaluates_rules`). Es la que dieron las reglas, no la que se esperaba.
    rule_category: str | None = None
    #: Cierto cuando **esta** llamada guardo la evaluacion: al crear el caso, o al
    #: completarle la que le faltaba a uno sembrado antes.
    evaluated_now: bool = False


def seeded_case_id(case_key: str) -> str:
    """El identificador del caso en la base: estable, y el mismo en cada siembra (BR6.2).

    Sale de la clave del caso y no de un contador ni del azar, para que dos
    siembras del mismo commit den el mismo caso y una prueba pueda nombrarlo. No
    se deriva del numero legible, que acuna U4 (BR7.3 de U4).
    """
    return f"seed-{hashlib.sha256(case_key.encode('utf-8')).hexdigest()[:24]}"


def closing_evidence_for(case_key: str, *, with_rules: bool = False) -> ClosingEvidence:
    """La evidencia de cierre de un caso sembrado (ver el punto 3 del modulo).

    Con `with_rules` las reglas van presentes, con la clave del caso por referencia, igual que
    en vivo: es el caso que paso por la decision y tiene su evaluacion guardada. Sin ella van
    vacias, que es lo que dice un caso que no paso por las reglas.
    """
    return ClosingEvidence(
        transcript=AttachmentState(kind=AttachmentKind.PRESENT, reference=case_key),
        cited_clauses=_VACIO,
        fired_rules=(
            AttachmentState(kind=AttachmentKind.PRESENT, reference=case_key)
            if with_rules
            else _VACIO
        ),
        trace_id=_VACIO,
        control_results=_VACIO,
    )


def path_to(record: SeededCaseRecord) -> tuple[CaseState, ...]:
    """Los estados por los que pasa el caso hasta el suyo, por la tabla de U4.

    Un caso que se deriva por una regla llega desde `deciding` (T7); por la
    peticion de una persona o por el limite de la demostracion, desde la captura
    (T3). Un cerrado `registered` lo cierran las reglas desde `deciding` (T6); los
    demas, una persona desde `derived` (T9).
    """
    captura = (CaseState.CAPTURING,)
    hasta_decidir = (CaseState.CAPTURING, CaseState.VERIFYING, CaseState.DECIDING)
    motivo = record.derivation_reason
    derivar = (
        (*hasta_decidir, CaseState.DERIVED)
        if motivo is not None and DerivationReason(motivo.value) is DerivationReason.RULE
        else (*captura, CaseState.DERIVED)
    )
    estado = CaseState(record.state.value)
    caminos: dict[CaseState, tuple[CaseState, ...]] = {
        CaseState.OPEN: (),
        CaseState.CAPTURING: captura,
        CaseState.VERIFYING: hasta_decidir[:2],
        CaseState.DECIDING: hasta_decidir,
        CaseState.DERIVED: derivar,
        CaseState.AWAITING_INSURED: (*derivar, CaseState.AWAITING_INSURED),
        CaseState.CLOSED: derivar if motivo is not None else hasta_decidir,
    }
    return caminos[estado]


def evaluates_rules(record: SeededCaseRecord) -> bool:
    """Si el caso ya paso por la decision y salio de ella: entonces tiene evaluacion de reglas.

    En vivo, el nodo `decision` evalua y guarda **mientras el caso esta en `deciding`**, y el
    caso solo sale de ahi --cerrado por T6, derivado por T7-- con la evaluacion ya guardada. Lo
    mismo vale aqui y sale del camino del caso, no de una lista: pasa por `deciding` y su estado
    no es `deciding`. Por eso quedan sin evaluacion el que sigue en captura, en verificacion o
    en `deciding` (la agente aun lo evalua) y el que una persona pidio derivar sin que las
    reglas lo miraran: decir que paso por las reglas seria mostrar una categoria que en vivo
    nadie le dio.
    """
    return (
        CaseState.DECIDING in path_to(record)
        and CaseState(record.state.value) is not CaseState.DECIDING
    )


def closing_actor_for(record: SeededCaseRecord) -> Actor:
    """Quien aplica el cierre del caso: una persona de su aseguradora, o el sistema (`SEED_ACTOR`).

    El cierre directo (`registered`, T6) es de las reglas y nadie lo decide, y un caso que no se
    cierra no tiene cierre: los dos quedan con el sistema. El que pone una persona desde la bandeja
    (T9) sigue el camino de la decision en vivo (`inbox.decision.decide`): la resolucion fija la
    accion de la bandeja, el tipo de registro fija el permiso que esa accion pide
    (`inbox.api.permiso_de_decision`), y el autor es **la primera persona de la configuracion de la
    aseguradora cuyo rol tiene ese permiso en la tabla versionada**. No se elige por nombre ni por
    un rol escrito aqui: una agencia marca como enviado con su agente de cuenta y un siniestro lo
    decide el ajustador.

    No se fuerza nada: si la aseguradora no ofrece esa accion (una agencia con un `approved` en su
    archivo) o nadie de su configuracion tiene el permiso, el caso no se puede sembrar y la siembra
    lo dice nombrandolo, en vez de cerrarlo con un autor que en vivo no existiria.
    """
    if record.resolution is None:
        return SEED_ACTOR
    resolucion = Resolution(record.resolution.value)
    accion = _ACCION_DE.get(resolucion)
    if accion is None:
        return SEED_ACTOR
    aseguradora = tenancy.require(record.tenant_id)
    if accion not in inbox_actions.allowed_for(aseguradora):
        msg = (
            f"'{record.case_key}' esta cerrado como '{resolucion.value}' y su aseguradora "
            f"(tipo '{aseguradora.kind.value}') no ofrece la accion '{accion.value}': "
            "en vivo ese cierre no existiria"
        )
        raise SeedError(msg)
    permiso = inbox_api.permiso_de_decision(
        record_type=RecordType(record.record_type.value), action=accion
    )
    for persona in aseguradora.staff:
        if tenancy.is_permitted(persona.role, permiso):
            return Actor(actor_type=ActorType.STAFF, actor_id=persona.principal_id)
    msg = (
        f"'{record.case_key}' esta cerrado como '{resolucion.value}', que en vivo cierra "
        f"quien tiene el permiso '{permiso.value}', y ninguna persona de la configuracion de "
        f"'{record.tenant_id}' lo tiene"
    )
    raise SeedError(msg)


def _partir_en_la_decision(
    camino: tuple[CaseState, ...],
) -> tuple[tuple[CaseState, ...], tuple[CaseState, ...]]:
    """Las transiciones hasta `deciding` (incluida) y las que vienen despues.

    El camino empieza en la captura, que se aplica antes de los turnos; aqui se parte lo que
    queda. La evaluacion de reglas va entre las dos mitades, que es donde esta en vivo.
    """
    resto = camino[1:]
    if CaseState.DECIDING not in resto:
        return resto, ()
    corte = resto.index(CaseState.DECIDING) + 1
    return resto[:corte], resto[corte:]


class _Reloj:
    """Un segundo por paso, para que el historial y la transcripcion queden en orden."""

    def __init__(self, inicio: datetime) -> None:
        self._actual = inicio

    def tic(self) -> datetime:
        self._actual += timedelta(seconds=1)
        return self._actual


async def _anexar_turnos(record: SeededCaseRecord, case_id: str, reloj: _Reloj) -> str | None:
    """Anexa cada turno ya redactado. Devuelve el ultimo turno del asegurado."""
    ultimo_del_asegurado: str | None = None
    for indice, turno in enumerate(record.transcript, start=1):
        turn_id = f"{case_id}-t{indice:02d}"
        borrador = TurnDraft(
            turn_id=turn_id,
            case_id=case_id,
            speaker=Speaker(turno.speaker.value),
            channel=Channel(record.channel.value),
            language=record.language,
            started_at=reloj.tic(),
        )
        # Antes de anexar, siempre: `append_turn` no acepta otra cosa (C-13).
        await api.append_turn(
            record.tenant_id, borrador, redact(turno.text, language=record.language)
        )
        if turno.speaker is SeededSpeaker.INSURED:
            ultimo_del_asegurado = turn_id
    return ultimo_del_asegurado


async def _fijar_campos(
    record: SeededCaseRecord, case_id: str, evidencia: str | None, cipher: Cipher, reloj: _Reloj
) -> None:
    """Cada campo, sellado y con su evidencia.

    El archivo no dice en que turno se dijo cada campo, y la evidencia es
    obligatoria (BR2.4 de U4): se usa **el ultimo turno del asegurado**, que es el
    primer momento en que es seguro que ya lo habia dicho. Un campo confirmado
    lleva la marca de la lectura de confirmacion en ese mismo momento (BR2.2).
    """
    if record.fields and evidencia is None:
        msg = f"'{record.case_key}' fija campos y no tiene ningun turno del asegurado que los respalde"
        raise SeedError(msg)
    for clave, campo in sorted(record.fields.items()):
        momento = reloj.tic()
        estado = FieldStatus(campo.status.value)
        await api.set_field(
            record.tenant_id,
            CaseField(
                case_id=case_id,
                field_key=clave,
                value=cipher.seal(campo.value),
                status=estado,
                evidence_turn_id=evidencia,
                confirmed_aloud_at=momento if estado is FieldStatus.CONFIRMED else None,
                updated_at=momento,
            ),
            cipher=cipher,
            actor=SEED_ACTOR,
            channel=Channel(record.channel.value),
        )


def _contexto(
    record: SeededCaseRecord,
    momento: datetime,
    hacia: CaseState,
    *,
    actor: Actor = SEED_ACTOR,
) -> TransitionContext:
    motivo = (
        DerivationReason(record.derivation_reason.value)
        if hacia is CaseState.DERIVED and record.derivation_reason is not None
        else None
    )
    return TransitionContext(
        now=momento,
        actor=actor,
        channel=Channel(record.channel.value),
        derivation_reason=motivo,
    )


async def _evaluar_reglas(
    record: SeededCaseRecord, case_id: str, *, cipher: Cipher, reloj: _Reloj
) -> decision_node.DecisionNodeOutput:
    """Evalua las reglas de su aseguradora con los insumos del caso y guarda la evaluacion.

    **El mismo camino que el aplicativo vivo**: los insumos salen de
    `composition.insumos_del_caso` (los campos del caso, sus partes y lo que anoto un
    ajustador) y la evaluacion la hace y la guarda el nodo `decision`, que forma su identificador
    con el caso, la version del conjunto y los insumos: evaluar otra vez el mismo caso no deja
    una segunda fila. Nada se fuerza ni se retoca: sale lo que dan las reglas.
    """
    try:
        insumos = await composition.insumos_del_caso(record.tenant_id, case_id, cipher=cipher)
        nodo = decision_node.DecisionNode(clock=reloj.tic, save=rules_api.save_evaluation)
        return await nodo.run(
            decision_node.DecisionNodeInput(
                tenant_id=record.tenant_id, case_id=case_id, inputs=insumos
            )
        )
    except RuleNotConfiguredError as error:
        msg = (
            f"'{record.case_key}' pasa por la decision y su aseguradora no tiene un conjunto de "
            f"reglas cargado y valido: {error}"
        )
        raise SeedError(msg) from error


async def _completar_evaluacion(
    record: SeededCaseRecord, case_id: str, *, cipher: Cipher, now: datetime
) -> tuple[str | None, bool]:
    """Para un caso que ya existe: su categoria, y si hubo que evaluarlo ahora.

    Un caso sembrado antes de que la siembra evaluara las reglas no tiene ninguna; este es el
    unico cambio que se le hace. Si ya tiene alguna --la de la siembra, o la que dejo un
    ajustador al anotar-- no se le agrega otra: la mas reciente es la vigente.
    """
    if not evaluates_rules(record):
        return None, False
    guardadas = await rules_api.evaluations_for(record.tenant_id, case_id)
    if guardadas:
        return str(guardadas[-1].category), False
    salida = await _evaluar_reglas(record, case_id, cipher=cipher, reloj=_Reloj(now))
    return str(salida.category), True


async def _existente(
    record: SeededCaseRecord, case_id: str, *, cipher: Cipher, now: datetime
) -> SeedOutcome | None:
    vista = await api.get_case(record.tenant_id, case_id)
    if vista is None:
        return None
    esperado = CaseState(record.state.value)
    if vista.state is not esperado:
        msg = (
            f"'{record.case_key}' ya existe en '{vista.state.value}' y su archivo dice "
            f"'{esperado.value}': es una siembra a medias o un caso que alguien movio"
        )
        raise SeedError(msg)
    categoria, evaluado = await _completar_evaluacion(record, case_id, cipher=cipher, now=now)
    return SeedOutcome(
        record.case_key,
        case_id,
        vista.state,
        created=False,
        rule_category=categoria,
        evaluated_now=evaluado,
    )


async def seed_case(record: SeededCaseRecord, *, cipher: Cipher, now: datetime) -> SeedOutcome:
    """Crea un caso sembrado por la API de U4, hasta su estado, con origen `generator`."""
    case_id = seeded_case_id(record.case_key)
    existente = await _existente(record, case_id, cipher=cipher, now=now)
    if existente is not None:
        return existente

    # Antes de escribir nada: si el cierre no tiene autor posible, no queda un caso a medias.
    quien_cierra = closing_actor_for(record)
    reloj = _Reloj(now)
    await api.create_case(
        record.tenant_id,
        api.NewCase(
            case_id=case_id,
            record_type=RecordType(record.record_type.value),
            channel=Channel(record.channel.value),
            origin=Origin.GENERATOR,
            language=record.language,
            policy_ref=record.policy_number,
        ),
        now=reloj.tic(),
    )
    camino = path_to(record)
    # T1: la captura empieza con el primer turno de la persona.
    if camino:
        await api.apply_transition(
            record.tenant_id, case_id, camino[0], context=_contexto(record, reloj.tic(), camino[0])
        )
    evidencia = await _anexar_turnos(record, case_id, reloj)
    await _fijar_campos(record, case_id, evidencia, cipher, reloj)
    hasta_decidir, despues = _partir_en_la_decision(camino)
    for hacia in hasta_decidir:
        await api.apply_transition(
            record.tenant_id, case_id, hacia, context=_contexto(record, reloj.tic(), hacia)
        )
    # Entre llegar a `deciding` y salir de ahi, que es donde el nodo `decision` evalua en vivo.
    evalua = evaluates_rules(record)
    categoria: str | None = None
    if evalua:
        categoria = str(
            (await _evaluar_reglas(record, case_id, cipher=cipher, reloj=reloj)).category
        )
    for hacia in despues:
        await api.apply_transition(
            record.tenant_id, case_id, hacia, context=_contexto(record, reloj.tic(), hacia)
        )

    vista: api.CaseView | None
    if record.resolution is not None:
        vista = await api.close_case(
            record.tenant_id,
            case_id,
            resolution=Resolution(record.resolution.value),
            closing_evidence=closing_evidence_for(record.case_key, with_rules=evalua),
            context=_contexto(record, reloj.tic(), CaseState.CLOSED, actor=quien_cierra),
        )
    else:
        vista = await api.get_case(record.tenant_id, case_id)
    if vista is None or vista.state is not CaseState(record.state.value):
        msg = f"'{record.case_key}' no quedo en '{record.state.value}' tras sembrarlo"
        raise SeedError(msg)
    return SeedOutcome(
        record.case_key,
        case_id,
        vista.state,
        created=True,
        rule_category=categoria,
        evaluated_now=evalua,
    )


async def seed_all(
    records: Sequence[SeededCaseRecord], *, cipher: Cipher, now: datetime
) -> tuple[SeedOutcome, ...]:
    """Siembra todos, en el orden de su clave. El primero que falla detiene el resto."""
    return tuple([await seed_case(record, cipher=cipher, now=now) for record in records])


def _imprimir(resultados: Sequence[SeedOutcome]) -> None:
    for resultado in resultados:
        como = "sembrado" if resultado.created else "ya estaba"
        reglas = resultado.rule_category or "no pasa por las reglas"
        print(
            f"synthetic:seed: {resultado.case_key} -> {resultado.state.value} ({como}); "
            f"reglas: {reglas}"
        )
    nuevos = sum(1 for r in resultados if r.created)
    evaluados = sum(1 for r in resultados if r.evaluated_now)
    print(
        f"synthetic:seed: {len(resultados)} caso(s), {nuevos} sembrado(s) ahora y "
        f"{len(resultados) - nuevos} que ya estaban, todos con origen generator; "
        f"{evaluados} evaluacion(es) de reglas guardada(s) ahora"
    )


async def _correr(data_dir: Path, cipher: Cipher, now: datetime) -> tuple[SeedOutcome, ...]:
    try:
        return await seed_all(load_seeded_cases(data_dir), cipher=cipher, now=now)
    finally:
        await session.dispose()


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0]).parse_args(argv)
    opciones = Settings()
    if not opciones.database_url:
        print(
            "synthetic:seed: falta UNTANGLE_DATABASE_URL: sin base no hay donde sembrar. "
            "Levante la local con `mise run services:up`",
            file=sys.stderr,
        )
        return 1
    try:
        cipher = Cipher.from_settings(opciones)
    except EncryptionKeyMissingError as error:
        print(f"synthetic:seed: {error}", file=sys.stderr)
        return 1

    session.configure(opciones.database_url)
    try:
        resultados = asyncio.run(_correr(paths.data_dir(), cipher, datetime.now(UTC)))
    except (SeedError, SeededCaseLoadError) as error:
        print(f"synthetic:seed: {error}", file=sys.stderr)
        return 1
    _imprimir(resultados)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
