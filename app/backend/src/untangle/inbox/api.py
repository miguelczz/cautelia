"""La bandeja del ajustador: sus rutas y su superficie (C-05, C-24).

**La aseguradora sale de la credencial y nunca de la direccion** (BR1.4
`[bloquea]`). El identificador que viene en la ruta no elige nada: solo se
comprueba que coincida con el de la credencial, y cuando no coincide la respuesta
es la misma que ante una credencial ilegible.

**Donde esta de verdad esa compuerta**, porque no es donde parece: la impone la
comparacion de `verify_credential`, no el `credencial.tenant_id` que se le pasa a
la consulta. Se comprobo rompiendo: cambiar ese argumento por el de la ruta no
tumba ninguna prueba --llegados ahi los dos valen lo mismo, porque la comparacion
ya paso-- mientras que desactivar la comparacion tumba tres. El argumento se
escribe igual, como segunda copia, pero no hay que confundirlo con el cerrojo.

El aislamiento tiene dos capas mas por debajo: la politica de fila, que filtra en
la base aunque este codigo se equivocara, y la llave compuesta hacia el caso.

**Todas las causas de rechazo responden igual.** Credencial ausente, ilegible,
caducada, de otra aseguradora, de una aseguradora que no existe y rol sin permiso
salen por la misma puerta con `404 not_found`. No es cortesia: una respuesta
distinta por causa le dice a quien prueba credenciales cual de sus intentos
acerto, y convierte el rechazo en un oraculo. La causa real viaja al rastro, que
es donde sirve. La forma la decidio U2 y aqui solo se respeta.

**Las respuestas de error no se documentan con el vocabulario de C-01**, por la
misma razon que dejo escrita U13: ese vocabulario vive en `untangle.server`, que
esta por encima de las unidades en el contrato de capas. El manejador de la raiz
convierte el `HTTPException` de aqui en la forma de C-01, asi que el cliente ve
el contrato aunque esta unidad no pueda nombrarlo. Queda anotado para U6, su
dueña, igual que lo dejo U13.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Mapping
from datetime import UTC, datetime
from typing import Annotated, Any

import orjson
from fastapi import APIRouter, Cookie, Header, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import Field, StrictBool, StrictInt

from untangle import observability
from untangle.base import Frozen, Locale
from untangle.case_record import api as casos
from untangle.case_record import crypto
from untangle.case_record import labels as etiquetas
from untangle.case_record.api import CaseClosedError, CaseNotFoundError
from untangle.case_record.models import (
    CaseState,
    ChangeKind,
    Channel,
    Priority,
    RecordType,
)
from untangle.inbox import (
    actions,
    annotation,
    case_view,
    correction,
    decision,
    events,
    examples,
    explanation,
    queue,
    receipts,
    triage_notes,
)
from untangle.inbox import visitor as enlace
from untangle.inbox.correction import InvalidFieldError
from untangle.rules import api as reglas
from untangle.rules.models import RuleEvaluation, RuleNotConfiguredError
from untangle.surface_spec import SurfaceId, SurfaceProbe, SurfaceSpec
from untangle.telemetry.traces import links as trace_links
from untangle.tenancy import api as tenancy
from untangle.tenancy import session as db
from untangle.tenancy import staff_identity
from untangle.tenancy.models import (
    Action,
    CredentialRejectedError,
    CredentialRejection,
    StaffCredential,
    TenantConfig,
    UnknownTenantError,
)

#: La cookie con la credencial de la bandeja. `HttpOnly` y `SameSite=Lax` cuando
#: se emite: nada del lado del navegador necesita leerla, y lo que no se puede
#: leer no se puede robar con un script inyectado en la pagina. **Nunca viaja en
#: la direccion**: una credencial en la ruta queda en cada registro que la vea
#: pasar.
COOKIE = "untangle_staff"

#: Lo que la sonda de la superficie tiene de plazo. Es una consulta que no toca
#: ninguna fila.
PROBE_TIMEOUT_MS = 200

#: Cada cuanto late el flujo cuando no hay nada que decir. Sin latido, un
#: intermediario corta una conexion ociosa y la pantalla se queda mirando algo que
#: ya no se va a actualizar, sin que nadie lo note. Es el mismo valor que U13.
HEARTBEAT_SECONDS = 15.0

#: Cada cuanto se pregunta a la base si hay avisos nuevos. El flujo de la bandeja no
#: cuelga de una cola en memoria como el del chat: sus avisos los escriben otras
#: peticiones --y en otro proceso, el dia que haya dos-- asi que la unica fuente que
#: los ve todos es la tabla. Un segundo es imperceptible para quien mira y son 60
#: consultas por hora y pestana, que es lo que una demostracion aguanta.
POLL_SECONDS = 1.0

#: La clave con que se verifica la credencial, puesta por la raiz de composicion.
#:
#: **No se lee del entorno dentro de la peticion.** Construir `Settings()` en la
#: ruta hace que la ruta se comporte segun lo que haya en el entorno en ese
#: instante y no segun lo que resolvio la raiz al montar la aplicacion: los dos
#: pueden diferir, y cuando difieren la ruta rechaza credenciales que la
#: aplicacion emitio. Lo encontro la prueba de la compuerta de esta misma tanda.
#:
#: Sigue el patron que ya usan `copy_api.install`, `tenancy.install` y
#: `chat_api.install_turn_handler`: la raiz enchufa, el modulo consume.
#:
#: **Las dos claves se enchufan juntas**, en un solo punto. Con un enchufe por
#: clave, la siguiente se anade y alguien escribe `Settings()` dentro de su ruta
#: "por ahora": paso con la del enlace firmado en esta misma unidad, dos tandas
#: despues de haberlo arreglado para la de la credencial.
_CLAVE_DE_CREDENCIAL: str | None = None
_CLAVE_DE_ENLACE: str | None = None


def install_keys(*, staff_credential: str | None, case_link: str | None) -> None:
    """La raiz de composicion enchufa las dos claves que la bandeja verifica.

    Las dos admiten `None`, y eso **no es un error**: es un despliegue sin bandeja y
    sin enlaces de caso. Las rutas lo tratan como cualquier otra causa de rechazo, con
    la misma respuesta; levantar ahi seria decirle a quien prueba que existe una
    bandeja mal configurada.
    """
    global _CLAVE_DE_CREDENCIAL, _CLAVE_DE_ENLACE
    _CLAVE_DE_CREDENCIAL = staff_credential
    _CLAVE_DE_ENLACE = case_link


def reset_keys() -> None:
    """Desenchufa las dos. Las usan las pruebas para no filtrarlas entre casos."""
    install_keys(staff_credential=None, case_link=None)


def _clave_de_enlace() -> str:
    """La clave con la que se verifica un enlace, o el mismo rechazo de siempre.

    Sin clave no hay enlace que pueda valer, asi que responde como un enlace que no
    vale. Es la misma decision que con la credencial y por la misma razon: un `500`
    aqui distingue "no configurado" de "no valido", y las cuatro causas de rechazo de
    esta unidad comparten respuesta a proposito.
    """
    if _CLAVE_DE_ENLACE is None:
        observability.emit("inbox.case_link_key_missing")
        raise _rechazo()
    return _CLAVE_DE_ENLACE


class QueueItem(Frozen):
    """Una fila de la cola, con la forma que C-05 declara."""

    case_id: str
    case_number: str
    state: CaseState
    record_type: RecordType
    channel: Channel
    language: Locale
    priority: Priority
    #: Cuantos campos de cuantos. Van los dos numeros y no el porcentaje: "3 de 7"
    #: dice cuanto falta y "43 %" no.
    completeness: float
    completeness_complete: int
    completeness_total: int
    derivation_reason: str | None = None
    updated_at: str


class QueuePage(Frozen):
    """La pagina de C-01: sus filas y por donde sigue."""

    items: tuple[QueueItem, ...]
    next_cursor: str | None = None


class CaseFieldView(Frozen):
    """Un campo del caso: su clave, su estado, si esta completo y, a su dueno, su valor.

    **El valor solo viaja a quien entro con el enlace de su propio caso** (decision
    de Miguel del 2026-10-11): la pantalla decia "Completo" y quien decidia el caso
    como ajustador en la demo no veia que se habia anotado. Son sus propias
    palabras, en su pantalla. A una credencial de la bandeja sigue sin viajar: lo
    que lee es la transcripcion, ya redactada.
    """

    field_key: str
    status: str
    complete: bool
    #: El dato no cuenta para la completitud: se ofrece al final y se anota si la
    #: persona quiere.
    optional: bool = False
    #: Lo anotado, en claro. `None` si nadie lo dijo, si no se pudo abrir o si
    #: quien pregunta no es el dueno del caso.
    value: str | None = None
    #: La clave del catalogo con la que se nombra el campo. Viaja desde aqui y no
    #: se arma en la pantalla: el juego de campos lo declara el esquema de U4, y su
    #: correspondencia con el catalogo vive junto a las de los enums, con su prueba
    #: en los dos sentidos. Una pantalla que mostrara `vehicle_and_driver`
    #: imprimiria el valor interno de un campo, que es lo que SEC-U4.15 prohibe.
    label_key: str


class TranscriptTurnView(Frozen):
    """Un turno, **ya redactado por U3**. La bandeja no lo destapa (BR2.3)."""

    turn_id: str
    speaker: str
    text_redacted: str
    started_at: str


class CitationView(Frozen):
    """Una clausula citada, con lo que la persona va a comparar contra su poliza."""

    clause_id: str
    clause_version: str
    part: str
    text: str
    clause_language: Locale
    amount_deferred: bool
    #: Quien emitio la clausula (BR2.6). En una agencia no es quien atiende el
    #: caso, y sin este dato las clausulas citadas parecen de la agencia.
    issuer_label: str
    #: De que condicion especial es la clausula, si es de una: con el numero la tarjeta
    #: se rotula igual que en el chat (2026-10-11). Aditivo.
    special_condition_number: int | None = None
    #: El nombre de la parte en el idioma en que la clausula no esta escrita (2026-10-13).
    #: Esta pantalla no conversa, asi que no hay "idioma pedido": la pantalla rotula la
    #: tarjeta con este nombre cuando su idioma es el otro, en vez de dejar «Part C —
    #: Uninsured Motorists Coverage» en una pantalla en espanol. El texto de la clausula
    #: sigue en su idioma. Aditivo.
    part_in_other_language: str | None = None


class CoverageAnswerOut(Frozen):
    """Una respuesta de cobertura.

    `outcome` viaja con su valor propio: "sin clausula" y "no pude verificar" son
    dos cosas distintas y la pantalla les pone etiquetas distintas (BR2.5).
    """

    answer_id: str
    outcome: str
    question_redacted: str
    citations: tuple[CitationView, ...]


class ExplanationOut(Frozen):
    """Las cinco preguntas de BR2.4 con su respuesta, y quien decidio si ya lo hizo.

    Las cinco viajan **siempre**: un hueco en la explicacion se lee como un dato que
    se perdio, y quien firma una decision sobre cobertura necesita distinguir "no
    habia" de "todavia no ha pasado". El valor `pending` existe solo para las dos de
    la decision, y es la diferencia entre "nadie decidio" y "aun no se ha decidido".

    `decided_by` y `decided_at` traen **el mismo estado**, porque salen del mismo
    hecho. Van las dos porque la pantalla dibuja las cinco filas de la regla, y
    derivar una de la otra en el navegador seria escribir alli una regla que ya
    esta decidida aqui.
    """

    asked: explanation.Answer
    cited: explanation.Answer
    rule: explanation.Answer
    decided_by: explanation.Answer
    decided_at: explanation.Answer
    #: El tipo de actor de U4: `staff` para quien entro con credencial, `insured`
    #: para quien entro con el enlace de demostracion (BR5.5) y `system` para el cierre
    #: directo, que aplican las reglas sin que nadie decida (US1.17). La etiqueta que lee
    #: una persona sale del catalogo; aqui viaja el valor cerrado.
    decided_by_kind: str | None
    #: Quien decidio, **solo cuando es una persona de la aseguradora y quien lo pide puede
    #: verla**: es su identificador de la tabla versionada, no el nombre de nadie real. Con el
    #: enlace de demostracion no hay identificador que mandar y la pantalla dice la frase del
    #: visitante (BR5.5), asi que aqui viaja vacio. En un caso de ejemplo, que se lee sin
    #: credencial, tambien viaja vacio aunque lo decidiera una persona: el tipo (`staff`) alcanza
    #: para decir que lo decidio un ajustador, y el identificador se parece demasiado a una
    #: credencial para ponerlo en una pagina publica.
    decided_by_id: str | None
    decided_at_iso: str | None


class TriageNoteView(Frozen):
    """Lo que un ajustador anoto para las reglas, tal como esta guardado.

    **Cada dato puede venir `null`, y `null` es "sin anotar"**, que no es lo mismo que
    `false`: una regla que lee un dato ausente no dispara, y una que lee `false` afirma que
    alguien lo comprobo. La pantalla los distingue y no los mezcla.

    `claim_amount` es la cifra interna del motor (la que comparan las reglas); el proyecto
    la muestra en pesos multiplicandola por mil.
    """

    claim_amount: int | None
    coverage_disputed: bool | None
    fraud_suspected: bool | None


class CaseDetailOut(Frozen):
    """El caso con sus seis bloques (C-05)."""

    case_id: str
    case_number: str
    state: CaseState
    record_type: RecordType
    channel: Channel
    language: Locale
    priority: Priority
    derivation_reason: str | None
    completeness_complete: int
    completeness_total: int
    fields: tuple[CaseFieldView, ...]
    transcript: tuple[TranscriptTurnView, ...]
    coverage_answers: tuple[CoverageAnswerOut, ...]
    rule_category: str | None
    fired_rules: tuple[str, ...]
    #: Los cuatro controles. `None` cuando la revision completa no ha corrido:
    #: decirlo es distinto de decir que los cuatro pasaron.
    controls_ok: bool | None
    control_findings: tuple[str, ...]
    #: El estado del resumen de traza, nunca un hueco: `recording`, `ready` o
    #: `lost`, y `None` si no hay resumen todavia.
    trace_status: str | None
    #: El costo **solo si se midio**. Un costo no medido no se escribe como cero:
    #: seria una cifra falsa que despues alguien suma. Por eso viaja su estado al
    #: lado, y la pantalla dice "no medido" en vez de dejar un hueco.
    trace_cost_usd: str | None
    trace_cost_status: str | None
    trace_latency_ms: int | None
    updated_at: str
    #: La resolucion, cuando el caso ya esta cerrado. Es lo que el encabezado
    #: muestra en lugar de las acciones, y lo que responde "que se decidio".
    resolution: str | None
    #: Las acciones que la bandeja **ofrece ahora** (BR4.5, BR4.3, BR4.4). Las
    #: decide la configuracion de la aseguradora y el estado del caso, y viajan
    #: resueltas: una pantalla que las dedujera del tipo de aseguradora escribiria
    #: la misma regla por segunda vez, en otro lenguaje, y el dia que una cambie la
    #: otra seguiria diciendo lo de antes. **Ofrecer no es permitir**: lo que impide
    #: la accion es la ruta, y esto es la cortesia de no dibujar un boton que va a
    #: ser rechazado.
    available_actions: tuple[actions.InboxAction, ...]
    #: Si se ofrece corregir un campo. `False` en un caso cerrado (BR3.4), por la
    #: misma razon y con el mismo reparto: la peticion directa la rechaza U4.
    can_correct_fields: bool
    explanation: ExplanationOut
    #: Lo que se anoto para las reglas (monto estimado, cobertura disputada, sospecha de
    #: fraude). Lo recibe el personal, **siempre**, y el visitante con enlace **solo si la nota
    #: la escribio el mismo** haciendo de ajustador (2026-10-13): lo que anota una persona de la
    #: aseguradora no llega a su pantalla, y nada que mencione montos le llega sin la firma de un
    #: ajustador. El caso de ejemplo lo recibe siempre en `null`. `null` tambien cuando nadie ha
    #: anotado nada. Aditivo.
    triage_note: TriageNoteView | None = None
    #: Si se ofrece anotar para las reglas. Al personal: el rol lo permite, el caso esta con un
    #: ajustador o espera al asegurado, y no es de solo lectura. Al visitante con enlace: lo
    #: mismo, mas que la nota no la haya escrito el personal y que no haya llegado al tope de
    #: entradas. Viaja resuelto, igual que `can_correct_fields`: la peticion directa se rechaza
    #: igual, y esto es la cortesia de no dibujar un formulario que va a ser rechazado. Aditivo.
    can_annotate_triage: bool = False
    #: Los montos desde los que las reglas de esta aseguradora cambian lo que hacen, de menor a
    #: mayor, en la cifra interna del motor (miles de pesos). Sale del archivo de reglas y viaja
    #: **solo cuando `can_annotate_triage` es cierto**: es la ayuda de quien anota, y la
    #: pantalla no escribe ninguna cifra por su cuenta. Vacio si ninguna regla lee el monto.
    #: Aditivo.
    triage_amount_steps: tuple[int, ...] = ()
    #: La direccion de la traza mas reciente del caso en la interfaz del backend de trazas
    #: (Langfuse), para que quien abre el caso vea ahi como trabajo la agente. **Solo** la reciben
    #: las dos puertas con dueno --el personal con su credencial y el visitante con el enlace de
    #: su caso--; el caso de ejemplo la recibe siempre en `null`, porque su pagina es publica y no
    #: hay traza de nadie que ensenar. `null` tambien cuando la traza todavia se registra o se
    #: perdio, cuando el backend no esta configurado y cuando no se pudo averiguar el proyecto.
    #: Aditivo.
    trace_url: str | None = None


class ExampleCaseItem(Frozen):
    """Una fila de la lista publica de casos de ejemplo.

    Menos que `QueueItem` a proposito: sin prioridad ni espera, que son de quien
    decide, y sin motivo de derivacion, que se lee al abrir el caso. Lo que hay son
    enums, numeros y el identificador con el que se pide el detalle.
    """

    case_id: str
    case_number: str
    record_type: RecordType
    state: CaseState
    channel: Channel
    language: Locale
    #: Cuantos campos de cuantos, como en la cola: "3 de 7" dice cuanto falta.
    completeness_complete: int
    completeness_total: int


class ExampleCaseList(Frozen):
    """Los casos de ejemplo de una aseguradora, ya en el orden en que se muestran."""

    items: tuple[ExampleCaseItem, ...]


class DecisionIn(Frozen):
    """Lo que se manda para decidir. `request_more` **no existe** aqui (BR4.7)."""

    decision: actions.InboxAction
    comment: str = Field(min_length=1, max_length=2000)


class DecisionOut(Frozen):
    """La decision registrada. El grafo se reanuda de fondo y no se espera."""

    decision_id: str
    case_state: CaseState
    resolution: str


class RedeemIn(Frozen):
    """El token del enlace. Llega en el cuerpo y **nunca** en la direccion."""

    token: str = Field(min_length=1)


class RedeemOut(Frozen):
    """Lo que la pantalla del visitante necesita saber de su sesion (C-07)."""

    case_id: str
    tenant: str
    access: str
    expires_at: str


class CorrectionIn(Frozen):
    """Lo que se manda para corregir un campo."""

    value: str


class CorrectionOut(Frozen):
    """El recibo de la correccion. Repetir la misma clave devuelve este mismo."""

    receipt_id: str
    field_key: str


class TriageNoteIn(Frozen):
    """Lo que se manda para anotar: **los tres datos, siempre**, cada uno con su valor o `null`.

    Es el estado completo y no un cambio parcial (PUT): `null` es "sin anotar", y es lo que
    permite quitar algo ya anotado y volver a dejarlo sin anotar. Con un cuerpo parcial, un
    dato ausente seria ambiguo entre "no lo toques" y "quitalo", y la pantalla no podria
    deshacer una anotacion. Los tipos son estrictos: un `true` no es un monto de 1, ni un
    `1` un si.
    """

    claim_amount: Annotated[StrictInt, Field(ge=0, le=triage_notes.MAX_CLAIM_AMOUNT)] | None
    coverage_disputed: StrictBool | None
    fraud_suspected: StrictBool | None


class TriageNoteOut(Frozen):
    """La anotacion registrada y lo que las reglas dijeron con ella.

    Repetir la misma clave devuelve esta misma respuesta (C-05). `rule_category` y
    `fired_rules` son de la evaluacion que dejo esta peticion; la pantalla vuelve a leer el
    caso para mostrarla, y esto es lo que le dice que ya existe.

    `receipt_id` es `null` solo cuando quien guardo entro con el enlace de su caso y guardo lo
    que ya estaba: no se escribio nada, asi que no hay recibo. Entonces `rule_category` y
    `fired_rules` son los de la evaluacion vigente del caso (o `null` y vacio si no hay ninguna).
    """

    receipt_id: str | None
    rule_category: str | None
    fired_rules: tuple[str, ...]


def _campos(detalle: case_view.CaseDetail, anotado: Mapping[str, str]) -> tuple[CaseFieldView, ...]:
    return tuple(
        CaseFieldView(
            field_key=clave,
            status=next(
                (c.status.value for c in detalle.fields if c.field_key == clave),
                "not_stated",
            ),
            complete=completo,
            optional=clave in detalle.completeness_optional,
            value=anotado.get(clave),
            # Un campo sin etiqueta no se puede dibujar sin imprimir su clave
            # interna, asi que se manda la del marcador de campo no disponible, que
            # ya existe para este caso. Que no ocurra lo comprueba la prueba de U4
            # que compara el esquema contra la correspondencia, en los dos sentidos.
            label_key=etiquetas.FIELD_KEYS.get(clave, etiquetas.FIELD_UNAVAILABLE),
        )
        for clave, completo in sorted(detalle.completeness_per_field.items())
    )


def _quien_decidio(detalle: case_view.CaseDetail) -> explanation.Decider | None:
    """Quien firmo la decision y cuando, del historial del caso (BR2.4, BR5.5).

    Es la **ultima transicion aplicada** de un caso cerrado con resolucion, y eso
    la identifica sin ambiguedad: `closed` es terminal, asi que no hay ninguna
    transicion despues de la que cerro. La alternativa era que U4 anadiera el actor
    del cierre a la fila del caso, y seria un segundo sitio guardando lo que el
    historial ya guarda.

    No se inventa nada: el tipo de actor sale tal cual, asi que una decision tomada
    con el enlace de demostracion se atribuye a un visitante y jamas a una persona
    de la aseguradora.
    """
    if detalle.state is not CaseState.CLOSED or detalle.resolution is None:
        return None
    cierres = [
        cambio for cambio in detalle.history if cambio.change_kind is ChangeKind.TRANSITION_APPLIED
    ]
    if not cierres:
        return None
    ultimo = max(cierres, key=lambda cambio: cambio.changed_at)
    return explanation.Decider(
        actor_kind=ultimo.actor.actor_type.value,
        actor_id=ultimo.actor.actor_id,
        at=ultimo.changed_at,
    )


def _explicacion(detalle: case_view.CaseDetail, *, nombrar_personal: bool = True) -> ExplanationOut:
    """La explicacion del caso, por la misma pieza que mide su caso de golden set.

    Con `nombrar_personal` apagado el identificador de quien decidio no viaja, y el tipo de actor
    si: es la forma de los casos de ejemplo, que se leen sin credencial.
    """
    quien = _quien_decidio(detalle)
    resumen = explanation.summarize(
        explanation.Evidence(
            questions=len(detalle.coverage_answers),
            cited_clauses=sum(len(r.citations) for r in detalle.coverage_answers),
            fired_rules=(
                len(detalle.rule_evaluation.fired_rules)
                if detalle.rule_evaluation is not None
                else 0
            ),
            rule_category=(
                str(detalle.rule_evaluation.category)
                if detalle.rule_evaluation is not None
                else None
            ),
            decider=quien,
        ),
        closed=detalle.state is CaseState.CLOSED,
    )
    return ExplanationOut(
        asked=resumen.answers[explanation.Question.ASKED],
        cited=resumen.answers[explanation.Question.CITED],
        rule=resumen.answers[explanation.Question.RULE],
        decided_by=resumen.answers[explanation.Question.DECIDED_BY],
        decided_at=resumen.answers[explanation.Question.DECIDED_AT],
        decided_by_kind=quien.actor_kind if quien is not None else None,
        decided_by_id=(
            quien.actor_id
            if nombrar_personal and quien is not None and quien.actor_kind == "staff"
            else None
        ),
        decided_at_iso=quien.at.isoformat() if quien is not None else None,
    )


def _reglas_a_la_vista(
    regla: RuleEvaluation | None, tenant: TenantConfig, *, ver_las_de_lo_anotado: bool
) -> tuple[str, ...]:
    """Los identificadores de las reglas disparadas que esta persona puede ver.

    Quien entro con credencial las ve todas, y tambien el visitante cuando **lo anotado lo
    escribio el mismo** (2026-10-13): son las reglas que dispararon sus propios datos, y verlas
    es el sentido de hacer de ajustador. Al visitante cuya nota escribio el personal, o que no
    tiene ninguna, y al caso de ejemplo **no se les muestran las que dispararon los datos que
    anota un ajustador** (monto, cobertura, fraude): el identificador de una regla de fraude
    escrito en su pantalla cuenta lo que la anotacion no debe contar. Las que dispararon con lo
    que la propia persona conto se siguen viendo, igual que antes.
    """
    if regla is None:
        return ()
    ocultas: frozenset[str] = frozenset()
    if not ver_las_de_lo_anotado:
        try:
            ocultas = reglas.rule_ids_reading(
                tenant_id=tenant.tenant_id, fields=frozenset(triage_notes.NOTED_FIELDS)
            )
        except RuleNotConfiguredError:
            ocultas = frozenset()
    return tuple(r.id for r in regla.fired_rules if r.id not in ocultas)


def _pasos_del_monto(tenant: TenantConfig) -> tuple[int, ...]:
    """Los montos desde los que cambian las reglas; vacio si la aseguradora no tiene reglas."""
    try:
        return reglas.amount_steps(tenant_id=tenant.tenant_id)
    except RuleNotConfiguredError:
        return ()


def _enlace_a_la_traza(detalle: case_view.CaseDetail) -> str | None:
    """La direccion de la traza mas reciente del caso en el backend de trazas, o `None`.

    La regla (solo con el resumen `ready`, y `None` si el backend no esta configurado) es
    `telemetry.traces.links.summary_url`: el tablero de gasto usa la misma.
    """
    return trace_links.summary_url(detalle.trace)


def _al_cable(  # noqa: PLR0913 -- el caso, la aseguradora y lo que cambia segun quien lo pide
    detalle: case_view.CaseDetail,
    tenant: TenantConfig,
    *,
    anotado: Mapping[str, str],
    solo_lectura: bool = False,
    por_personal: bool = False,
    nombrar_personal: bool = True,
    nota_de_triage: triage_notes.TriageNote | None = None,
    puede_anotar: bool = False,
    ver_las_reglas_de_lo_anotado: bool = False,
    con_enlace_a_la_traza: bool = False,
) -> CaseDetailOut:
    """El caso con la forma del contrato.

    Con `solo_lectura` el caso sale **sin ninguna accion**: ni decidir ni corregir un
    campo. Es el de los casos de ejemplo, que se leen y nada mas.

    `por_personal` dice que quien lo pide entro con credencial: solo a esa persona se le
    ofrece tomar un caso que la agente aun evalua.

    Lo anotado para las reglas lo decide la ruta, que sabe quien pide y de quien es la nota:
    `nota_de_triage` es **lo que esta persona puede ver** (el personal, todo; el visitante, solo
    lo que escribio el), `puede_anotar` es si su puerta se lo permite (el rol, o el visitante
    sin nota del personal y sin haber llegado al tope) y `ver_las_reglas_de_lo_anotado` si le
    llegan los identificadores de las reglas que dispararon esos datos. Aqui solo se suma lo
    que depende del caso: el estado, el tipo y la lectura de solo lectura.

    `nombrar_personal` apagado omite el identificador de la persona de la aseguradora que decidio
    (`explanation.decided_by_id`); lo apaga la ruta de los casos de ejemplo.

    `con_enlace_a_la_traza` lo **enciende** la ruta que tiene dueno --personal o visitante con el
    enlace de su caso--; apagado por omision, de modo que el caso de ejemplo, que es publico, no
    pueda recibirlo ni por descuido.
    """
    regla = detalle.rule_evaluation
    revision = detalle.compliance
    traza = detalle.trace
    se_ofrece_anotar = (
        not solo_lectura
        and puede_anotar
        and annotation.can_annotate(state=detalle.state, record_type=detalle.record_type)
    )
    return CaseDetailOut(
        case_id=detalle.case_id,
        case_number=detalle.case_number,
        state=detalle.state,
        record_type=detalle.record_type,
        channel=detalle.channel,
        language=detalle.language,
        priority=detalle.priority,
        derivation_reason=detalle.derivation_reason,
        completeness_complete=detalle.completeness_complete,
        completeness_total=detalle.completeness_total,
        fields=_campos(detalle, anotado),
        transcript=tuple(
            TranscriptTurnView(
                turn_id=turno.turn_id,
                speaker=turno.speaker.value,
                text_redacted=turno.text_redacted,
                started_at=turno.started_at.isoformat(),
            )
            for turno in detalle.transcript
        ),
        coverage_answers=tuple(
            CoverageAnswerOut(
                answer_id=respuesta.answer_id,
                outcome=respuesta.outcome,
                question_redacted=respuesta.question_redacted,
                citations=tuple(
                    CitationView(
                        clause_id=cita.clause_id,
                        clause_version=cita.clause_version,
                        part=cita.part,
                        text=cita.text,
                        clause_language=cita.clause_language,
                        amount_deferred=cita.amount_deferred,
                        issuer_label=cita.issuer_label,
                        special_condition_number=cita.special_condition_number,
                        part_in_other_language=cita.part_in_other_language,
                    )
                    for cita in respuesta.citations
                ),
            )
            for respuesta in detalle.coverage_answers
        ),
        rule_category=str(regla.category) if regla is not None else None,
        fired_rules=_reglas_a_la_vista(
            regla, tenant, ver_las_de_lo_anotado=ver_las_reglas_de_lo_anotado
        ),
        controls_ok=(
            None
            if revision is None
            else (revision.disclosure_ok and revision.human_route_ok and revision.explainability_ok)
        ),
        control_findings=(() if revision is None else tuple(f.value for f in revision.findings)),
        trace_status=traza.status.value if traza is not None else None,
        trace_cost_usd=(
            str(traza.cost.amount_usd)
            if traza is not None and traza.cost.amount_usd is not None
            else None
        ),
        trace_cost_status=traza.cost.status.value if traza is not None else None,
        trace_latency_ms=traza.latency_ms if traza is not None else None,
        updated_at=detalle.updated_at.isoformat(),
        resolution=detalle.resolution.value if detalle.resolution is not None else None,
        available_actions=(
            ()
            if solo_lectura
            else tuple(
                sorted(
                    actions.offered_for(tenant, state=detalle.state, by_staff=por_personal),
                    key=lambda a: a.value,
                )
            )
        ),
        can_correct_fields=not solo_lectura and detalle.state is not CaseState.CLOSED,
        explanation=_explicacion(detalle, nombrar_personal=nombrar_personal),
        triage_note=(
            TriageNoteView(
                claim_amount=nota_de_triage.values.claim_amount,
                coverage_disputed=nota_de_triage.values.coverage_disputed,
                fraud_suspected=nota_de_triage.values.fraud_suspected,
            )
            if nota_de_triage is not None and not nota_de_triage.values.is_empty()
            else None
        ),
        can_annotate_triage=se_ofrece_anotar,
        triage_amount_steps=_pasos_del_monto(tenant) if se_ofrece_anotar else (),
        trace_url=_enlace_a_la_traza(detalle) if con_enlace_a_la_traza else None,
    )


def _sse(evento: events.InboxEvent) -> bytes:
    """Un aviso en el formato del cable, con su `id:` --el de su aseguradora--."""
    cuerpo = {
        "kind": evento.kind.value,
        "case_id": evento.case_id,
        "summary": evento.summary_redacted,
        "at": evento.created_at.isoformat(),
    }
    return b"id: %d\ndata: %s\n\n" % (evento.event_id, orjson.dumps(cuerpo))


async def inbox_stream(tenant_id: str, *, desde: int) -> AsyncGenerator[bytes]:
    """Los avisos de una aseguradora desde un identificador, con su latido.

    Publica a proposito, igual que la de U13: es la forma exacta del cable y es
    donde vive la conducta que hay que comprobar, y un flujo abierto no se puede
    consumir entero desde una prueba porque no termina hasta que la pestana cierra.
    """
    # Lo primero, en cuanto la conexion se abre: el intervalo de reconexion y una
    # senal de vida. Sin esto, durante quince segundos una conexion viva y una
    # colgada se ven exactamente igual.
    yield b"retry: 3000\n: open\n\n"

    posicion = desde
    while True:
        nuevos = await events.since(tenant_id, posicion)
        if not nuevos:
            await asyncio.sleep(POLL_SECONDS)
            yield b": heartbeat\n\n"
            continue
        for evento in nuevos:
            yield _sse(evento)
            posicion = evento.event_id


async def _quien_entra(
    tenant_id: str,
    case_id: str,
    *,
    action: Action,
    credencial: str | None,
    cookie_de_caso: str | None,
) -> str | None:
    """Quien esta decidiendo: una persona de la aseguradora, o un visitante.

    La accion entra por argumento porque no es la misma en cada ruta: ver un caso
    y decidirlo son dos permisos distintos, y una agencia que puede lo primero y
    no lo segundo es exactamente el caso que la tabla de permisos existe para
    distinguir.

    Devuelve el identificador de la persona, o `None` cuando entro con un enlace.
    Ese `None` es lo que hace que la decision se atribuya a un visitante de
    demostracion y nunca a alguien de la bandeja (BR5.5).

    **La credencial manda sobre la cookie.** Si llegan las dos, decide la persona:
    es la unica lectura en la que el registro no puede mentir, porque una cookie
    de caso que quedara por delante convertiria a cualquier ajustador con una
    pestana vieja abierta en "un visitante".
    """
    if credencial:
        try:
            cred = _credencial(tenant_id, credencial, action)
        except HTTPException:
            # Una credencial que no vale --vencida, de otra aseguradora-- no da
            # ningun permiso, y no puede quitar el del enlace: el visitante que
            # alguna vez probo la bandeja quedaba sin poder abrir su propio caso
            # (2026-10-09). Sin cookie de caso, el rechazo de siempre.
            if not cookie_de_caso:
                raise
        else:
            return cred.principal_id

    if not cookie_de_caso:
        raise _rechazo()

    ahora = _ahora()
    try:
        sesion = await enlace.session_from_cookie(
            cookie_de_caso, signing_key=_clave_de_enlace(), now=ahora
        )
        # De otro caso o de otra aseguradora: las dos responden como un caso que
        # no existe. El vencimiento lo comprueba U2 dentro de `session_from_cookie`,
        # en **cada** peticion y no solo al canjear, asi que aqui no se repite.
        enlace.authorize(sesion, case_id=case_id)
    except enlace.CaseSessionInvalidError as error:
        raise _rechazo() from error
    if sesion.tenant_id != tenant_id:
        raise _rechazo()
    return None


def _ahora() -> datetime:
    """El reloj del proceso, en un solo sitio.

    Aqui y no dentro de cada pieza: las de abajo lo reciben por argumento, que es
    lo que permite probar los bordes sin esperar.
    """
    return datetime.now(UTC)


def _rechazo() -> HTTPException:
    """La unica salida de rechazo de esta unidad. Una sola, a proposito."""
    return HTTPException(status_code=404)


class UndeclaredDecisionPermissionError(RuntimeError):
    """Un tipo de registro sin permiso de decision declarado en la tabla de abajo.

    Falla en vez de caer en uno por omision: el permiso por omision de una
    decision no puede elegirlo quien olvido escribir la fila.
    """


#: Que permiso de la tabla de U2 pide decidir cada tipo de registro. **Tabla
#: cerrada y escrita**, con fila para los tres tipos de U4.
#:
#: Aqui esta lo que separa BR4.1 de U19 de BR4.1 de U14: un siniestro y una
#: consulta de cobertura los decide quien decide cobertura, y una solicitud de
#: cotizacion la decide el suscriptor. Sin esta tabla, `decide_quote` seria un
#: nombre nuevo sin efecto: el ajustador seguiria decidiendo solicitudes por la
#: ruta que ya existia, porque es la misma ruta.
_PERMISO_DE_DECISION: dict[RecordType, Action] = {
    RecordType.CLAIM: Action.DECIDE_CASE,
    RecordType.COVERAGE_INQUIRY: Action.DECIDE_CASE,
    RecordType.QUOTE_REQUEST: Action.DECIDE_QUOTE,
}


def permiso_de_decision(*, record_type: RecordType, action: actions.InboxAction) -> Action:
    """El permiso que pide esta decision: depende de que se decide y sobre que.

    Marcar como enviado es de la agencia y no mira el tipo: lo que traspasa es el
    caso, cualquiera que sea.
    """
    if action is actions.InboxAction.MARK_SENT:
        return Action.MARK_SENT
    permiso = _PERMISO_DE_DECISION.get(record_type)
    if permiso is None:
        msg = (
            f"el tipo de registro '{record_type.value}' no declara su permiso de "
            "decision en `_PERMISO_DE_DECISION`"
        )
        raise UndeclaredDecisionPermissionError(msg)
    return permiso


def _credencial(tenant_id: str, cookie: str | None, action: Action) -> StaffCredential:
    """Los cinco pasos de U2 antes de tocar nada, y una sola forma de fallar.

    El orden importa: la credencial se comprueba **antes** de preguntar si la
    aseguradora existe. Al reves, una aseguradora inexistente respondería por un
    camino distinto que una existente y ajena, y comparar las dos respuestas
    diria cuales estan desplegadas.
    """
    if _CLAVE_DE_CREDENCIAL is None:
        # Un despliegue sin clave de personal es un despliegue **sin bandeja**: no
        # existe credencial que pueda valer, asi que la respuesta es la misma que
        # ante una ilegible. Antes era un `500`, y eso le decia a quien prueba
        # credenciales que ahi hay una bandeja mal configurada. Lo encontro el arnes
        # de accesibilidad, que corre el proceso real sin claves.
        observability.emit("inbox.credential_key_missing", tenant_id=tenant_id)
        raise _rechazo()

    try:
        credencial = staff_identity.verify_credential(
            cookie,
            expected_tenant=tenant_id,
            signing_key=_CLAVE_DE_CREDENCIAL,
        )
        staff_identity.authorize(credencial, action)
    except CredentialRejectedError as error:
        # La causa va al rastro y no al cliente (SEC-U2.6).
        observability.emit(
            "inbox.credential_rejected", tenant_id=tenant_id, cause=error.cause.value
        )
        raise _rechazo() from error

    try:
        tenancy.require(tenant_id)
    except UnknownTenantError as error:
        # Una credencial valida cuya aseguradora no esta cargada: es un despliegue
        # a medias, no un ataque, pero hacia fuera responde igual.
        observability.emit(
            "inbox.credential_rejected",
            tenant_id=tenant_id,
            cause=CredentialRejection.UNKNOWN_PRINCIPAL.value,
        )
        raise _rechazo() from error

    return credencial


def _permitido(tenant_id: str, cookie: str | None, action: Action) -> bool:
    """Si la credencial que ya se verifico permite esa accion, **sin dejar rastro de rechazo**.

    Es una pregunta de la vista --ofrecer o no un formulario--, no una peticion: un rol que
    abre cada caso sin poder anotar no tiene que llenar el rastro de rechazos que lee quien
    busca sondeos de credenciales. Quien la llama ya paso por `_quien_entra`, asi que una
    credencial que no vale responde que no, sin mas.
    """
    if _CLAVE_DE_CREDENCIAL is None or not cookie:
        return False
    try:
        credencial = staff_identity.verify_credential(
            cookie, expected_tenant=tenant_id, signing_key=_CLAVE_DE_CREDENCIAL
        )
    except CredentialRejectedError:
        return False
    return staff_identity.is_permitted(credencial.role, action)


def router() -> APIRouter:  # noqa: C901, PLR0915 -- seis rutas declaradas, ninguna con logica propia
    """Las rutas de la bandeja (C-05, C-06)."""
    enrutador = APIRouter(prefix="/api/inbox", tags=["inbox"])

    @enrutador.get("/{tenant_id}/cases", operation_id="listInboxCases")
    async def list_cases(  # noqa: PLR0913 -- son los filtros del contrato, ninguno derivable de otro
        tenant_id: str,
        *,
        state: Annotated[str | None, Query()] = None,
        channel: Annotated[str | None, Query()] = None,
        language: Annotated[str | None, Query()] = None,
        priority: Annotated[str | None, Query()] = None,
        cursor: Annotated[str | None, Query()] = None,
        limit: Annotated[int | None, Query(ge=1, le=queue.MAX_LIMIT)] = None,
        untangle_staff: Annotated[str | None, Cookie()] = None,
    ) -> QueuePage:
        credencial = _credencial(tenant_id, untangle_staff, Action.LIST_CASES)
        try:
            filtros = queue.parse_filters(
                state=state, channel=channel, language=language, priority=priority
            )
            pagina = await queue.page(
                credencial.tenant_id,
                filters=filtros,
                role=credencial.role,
                limit=limit,
                cursor=cursor,
            )
        except (queue.InvalidFilterError, queue.InvalidCursorError) as error:
            # 422, la misma forma que da el marco a un parametro mal tipado: es un
            # error de quien pide, no una cola vacia.
            raise HTTPException(status_code=422) from error

        return QueuePage(
            items=tuple(
                QueueItem(
                    case_id=fila.case_id,
                    case_number=fila.case_number,
                    state=fila.state,
                    record_type=fila.record_type,
                    channel=fila.channel,
                    language=fila.language,
                    priority=fila.priority,
                    completeness=(
                        fila.completeness_complete / fila.completeness_total
                        if fila.completeness_total
                        else 0.0
                    ),
                    completeness_complete=fila.completeness_complete,
                    completeness_total=fila.completeness_total,
                    derivation_reason=fila.derivation_reason,
                    updated_at=fila.updated_at.isoformat(),
                )
                for fila in pagina.items
            ),
            next_cursor=pagina.next_cursor,
        )

    @enrutador.get("/{tenant_id}/cases/{case_id}", operation_id="getInboxCase")
    async def get_case(
        tenant_id: str,
        case_id: str,
        response: Response,
        *,
        untangle_staff: Annotated[str | None, Cookie()] = None,
        ut_case: Annotated[str | None, Cookie()] = None,
    ) -> CaseDetailOut:
        """El caso con sus seis bloques, pedidos a quien los guarda (BR2.2).

        Dos puertas: la credencial de personal y la cookie de caso del visitante.
        La segunda abre **ese** caso y nada mas; la cola le responde como a quien
        no tiene nada (BR5.1), y eso lo decide la ruta de la cola, que no acepta
        la cookie de caso en absoluto.
        """
        quien = await _quien_entra(
            tenant_id,
            case_id,
            action=Action.VIEW_CASE,
            credencial=untangle_staff,
            cookie_de_caso=ut_case,
        )
        # Lo anotado para las reglas se pide **a la vez** que el caso, a las dos puertas: quien
        # entra con credencial lo ve entero, y el visitante lo ve solo si lo escribio el mismo
        # (2026-10-13). Fuera de `detail_for` a proposito, porque ese cuesta un numero de
        # consultas medido y esto es una consulta por caso, no por elemento.
        detalle, nota = await asyncio.gather(
            case_view.detail_for(tenant_id, case_id),
            triage_notes.read(tenant_id, case_id),
        )
        if detalle is None:
            # Un caso de otra aseguradora y uno que no existe responden igual, y
            # no porque se comparen: la politica de fila filtro antes.
            raise _rechazo()
        # Lo anotado en los campos del caso, solo a quien entro con el enlace de su propio caso.
        anotado = (
            await casos.open_field_values(
                tenant_id,
                case_id,
                detalle.completeness_per_field,
                cipher=crypto.active(),
            )
            if quien is None
            else {}
        )
        por_personal = quien is not None
        # Lo que escribio el personal no sale por la puerta del visitante: ni la nota, ni que
        # se pueda cambiar, ni las reglas que disparo (la pantalla del personal lo promete).
        de_quien_pide = por_personal or annotation.note_is_visitors(nota)
        response.headers["Cache-Control"] = "private, no-store"
        return _al_cable(
            detalle,
            tenancy.require(tenant_id),
            anotado=anotado,
            por_personal=por_personal,
            # A quien entra con el enlace de su caso se le dice que lo decidio un
            # ajustador, no cual: el identificador del personal es para el personal.
            nombrar_personal=por_personal,
            nota_de_triage=nota if de_quien_pide else None,
            puede_anotar=(
                _permitido(tenant_id, untangle_staff, Action.ANNOTATE_TRIAGE)
                if por_personal
                else (
                    de_quien_pide
                    # El tope se cuenta solo si el estado ya deja anotar: la cuenta es una
                    # consulta y no tiene sentido pagarla por un caso cerrado.
                    and annotation.can_annotate(
                        state=detalle.state, record_type=detalle.record_type
                    )
                    and await annotation.visitor_has_budget(tenant_id, case_id)
                )
            ),
            # Las reglas que dispararon lo anotado las ve quien lo escribio: el personal siempre,
            # y el visitante cuando la nota existe y es suya (sin nota no hay nada que mostrar).
            ver_las_reglas_de_lo_anotado=por_personal or (nota is not None and de_quien_pide),
            # Las dos puertas de `get_case` tienen dueno (la credencial o la cookie del caso).
            con_enlace_a_la_traza=True,
        )

    @enrutador.patch(
        "/{tenant_id}/cases/{case_id}/fields/{field_key}",
        operation_id="correctInboxCaseField",
    )
    async def correct_field(  # noqa: PLR0913 -- los tres de la ruta, el cuerpo y las dos cabeceras
        tenant_id: str,
        case_id: str,
        field_key: str,
        body: CorrectionIn,
        *,
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
        untangle_staff: Annotated[str | None, Cookie()] = None,
    ) -> CorrectionOut:
        """Corrige un campo dejando rastro (BR3.1 a BR3.4)."""
        credencial = _credencial(tenant_id, untangle_staff, Action.CORRECT_FIELD)
        # El caso, no su vista entera: corregir necesita saber que existe y en que
        # idioma esta, y pedir los seis bloques para eso serian nueve consultas
        # donde bastan dos.
        caso = await casos.get_case(credencial.tenant_id, case_id)
        if caso is None:
            raise _rechazo()
        if not idempotency_key:
            # La clave es obligatoria y no se inventa una: sin ella, un segundo
            # envio del formulario escribiria una segunda correccion, que es el
            # dano real que la idempotencia existe para evitar (C-01).
            raise HTTPException(status_code=422)
        try:
            aplicada = await correction.apply(
                credencial.tenant_id,
                case_id=case_id,
                field_key=field_key,
                value=body.value,
                idempotency_key=idempotency_key,
                principal_id=credencial.principal_id,
                cipher=crypto.active(),
                # El idioma del caso, no el de quien corrige: la redaccion del
                # resumen escribe sus etiquetas en el idioma del caso.
                language=caso.language,
                now=_ahora(),
            )
        except receipts.RecycledKeyError as error:
            # `409`: la clave dice una cosa y la peticion dice otra. Devolverle el
            # resultado guardado le diria que se aplico lo que pidio.
            raise HTTPException(status_code=409) from error
        except CaseNotFoundError as error:
            raise _rechazo() from error
        except CaseClosedError as error:
            # Un caso cerrado expone lo que se comprobo al cerrarlo (BR3.4). La
            # pantalla no ofrece la accion; esto es lo que de verdad lo impide.
            raise HTTPException(status_code=409) from error
        except InvalidFieldError as error:
            # El mensaje que lee una persona sale del catalogo por idioma; lo que
            # sale por aqui es el codigo, nunca el texto ni el valor rechazado.
            raise HTTPException(status_code=422) from error
        return CorrectionOut(receipt_id=aplicada.receipt_id, field_key=aplicada.field_key)

    @enrutador.put(
        "/{tenant_id}/cases/{case_id}/triage-note",
        operation_id="annotateInboxCaseTriage",
    )
    async def annotate_triage(  # noqa: PLR0913 -- los dos de la ruta, el cuerpo y las tres cabeceras
        tenant_id: str,
        case_id: str,
        body: TriageNoteIn,
        *,
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
        untangle_staff: Annotated[str | None, Cookie()] = None,
        ut_case: Annotated[str | None, Cookie()] = None,
    ) -> TriageNoteOut:
        """Anota el monto estimado, la cobertura disputada y la sospecha de fraude.

        Dos puertas, igual que decidir: la credencial de personal con el permiso del rol, y el
        enlace del caso del visitante (2026-10-13), que anota **solo su propio caso** y queda como
        visitante. Guarda lo anotado --`null` es "sin anotar"--, deja su entrada en el historial
        del caso y vuelve a evaluar las reglas de la aseguradora con todos los insumos del caso.
        No cambia el estado del caso ni escribe en el chat.

        Lo que cambia para el visitante: no lee ni pisa la nota que escribio el personal, guardar
        lo que ya estaba no escribe nada, y las entradas que puede dejar tienen tope. Los tres
        rechazos responden `409` y no escriben.
        """
        # Primero quien entra, con el permiso minimo de **ver**: no se anota lo que no se puede
        # abrir. Un enlace de otro caso, vencido o alterado responde como un caso que no existe.
        principal = await _quien_entra(
            tenant_id,
            case_id,
            action=Action.VIEW_CASE,
            credencial=untangle_staff,
            cookie_de_caso=ut_case,
        )
        if principal is not None:
            # Quien entro con credencial necesita ademas el permiso de anotar; quien entro por su
            # enlace no tiene rol, y lo que puede lo decide `annotation.apply`.
            _credencial(tenant_id, untangle_staff, Action.ANNOTATE_TRIAGE)
        if not idempotency_key:
            # Sin clave, un segundo envio del formulario escribiria una segunda evaluacion.
            raise HTTPException(status_code=422)
        try:
            aplicada = await annotation.apply(
                tenancy.require(tenant_id).tenant_id,
                case_id=case_id,
                values=triage_notes.TriageValues(
                    claim_amount=body.claim_amount,
                    coverage_disputed=body.coverage_disputed,
                    fraud_suspected=body.fraud_suspected,
                ),
                idempotency_key=idempotency_key,
                principal_id=principal,
                now=_ahora(),
            )
        except receipts.RecycledKeyError as error:
            raise HTTPException(status_code=409) from error
        except (
            annotation.NotAnnotatableError,
            annotation.StaffNoteLockedError,
            annotation.AnnotationLimitReachedError,
            RuleNotConfiguredError,
        ) as error:
            # `409`: no falta permiso, el caso no admite anotaciones ahora (otro estado, otro
            # tipo), la nota es del personal, el visitante llego al tope o la aseguradora no
            # tiene reglas que reevaluar. Y se rechaza sin escribir.
            raise HTTPException(status_code=409) from error
        except CaseNotFoundError as error:
            raise _rechazo() from error
        evaluacion = aplicada.evaluation
        return TriageNoteOut(
            receipt_id=aplicada.receipt_id,
            rule_category=str(evaluacion.category) if evaluacion is not None else None,
            fired_rules=(
                tuple(regla.id for regla in evaluacion.fired_rules)
                if evaluacion is not None
                else ()
            ),
        )

    @enrutador.get("/{tenant_id}/stream", operation_id="streamInbox")
    async def stream_inbox(
        tenant_id: str,
        *,
        last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
        untangle_staff: Annotated[str | None, Cookie()] = None,
    ) -> StreamingResponse:
        """El flujo de avisos de la aseguradora (C-06, BR6.1, BR6.2).

        Sin `Last-Event-ID` se **coloca al final**: quien abre la bandeja quiere lo
        que pase desde ahora, no que le reproduzcan la demostracion entera. Con el,
        recibe lo que se perdio mientras estuvo caido.
        """
        credencial = _credencial(tenant_id, untangle_staff, Action.LIST_CASES)
        pedido = events.parse_last_event_id(last_event_id)
        desde = pedido if pedido is not None else await events.last_event_id(credencial.tenant_id)
        return StreamingResponse(
            inbox_stream(credencial.tenant_id, desde=desde),
            media_type="text/event-stream",
            headers={"cache-control": "no-store", "x-accel-buffering": "no"},
        )

    @enrutador.post(
        "/{tenant_id}/cases/{case_id}/decision",
        status_code=202,
        operation_id="decideInboxCase",
    )
    async def decide_case(  # noqa: PLR0913 -- los dos de la ruta, el cuerpo y las tres cabeceras
        tenant_id: str,
        case_id: str,
        body: DecisionIn,
        *,
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
        untangle_staff: Annotated[str | None, Cookie()] = None,
        ut_case: Annotated[str | None, Cookie()] = None,
    ) -> DecisionOut:
        """Aprobar, rechazar o marcar como enviado (BR4.1 a BR4.6, BR5.5).

        Dos puertas para la misma accion: la credencial de personal y la cookie de
        caso del visitante. Lo que cambia entre las dos es **quien queda como
        autor**, y nada mas: las reglas de que se puede decidir y con que
        comentario son las mismas.
        """
        # Primero quien entra, con el permiso minimo de **ver**: no se decide lo
        # que no se puede abrir, y hasta leer el caso no se sabe que permiso pide
        # su decision.
        principal = await _quien_entra(
            tenant_id,
            case_id,
            action=Action.VIEW_CASE,
            credencial=untangle_staff,
            cookie_de_caso=ut_case,
        )
        caso = await casos.get_case(tenancy.require(tenant_id).tenant_id, case_id)
        if caso is None:
            raise _rechazo()

        # Y ahora el permiso de la decision, que depende de **que** se decide y
        # **sobre que**: una agencia marca como enviado y no aprueba, y una
        # solicitud de cotizacion la decide el suscriptor y no el ajustador. Son
        # filas distintas de la tabla versionada, y resolverlas con una sola
        # accion obligaria a darle las tres a quien solo necesita una.
        #
        # **Se mira quien entro, no que cookie llego** (2026-10-12). `_quien_entra` ya
        # tolera una credencial vieja --vencida, de otra aseguradora-- cuando hay una
        # cookie de caso valida; comprobarla otra vez aqui por el solo hecho de que
        # llego rechazaba al visitante que habia entrado por su enlace, y la pantalla lo
        # contaba como "el enlace vencio" aunque faltara casi una hora.
        if principal is not None:
            _credencial(
                tenant_id,
                untangle_staff,
                permiso_de_decision(record_type=caso.record_type, action=body.decision),
            )
        elif caso.record_type is RecordType.QUOTE_REQUEST:
            # Un enlace de demostracion deja ver el caso propio y, en un siniestro,
            # decidirlo como visitante (BR5.5 de U14). Una solicitud de cotizacion
            # no: quien la pidio aprobandola a si misma no es una decision, y el
            # rol que la decide es el del suscriptor (BR4.1 de U19).
            raise _rechazo()

        if not idempotency_key:
            raise HTTPException(status_code=422)
        try:
            registrada = await decision.decide(
                tenancy.require(tenant_id),
                case_id=case_id,
                action=body.decision,
                comment=body.comment,
                idempotency_key=idempotency_key,
                principal_id=principal,
                now=_ahora(),
            )
        except decision.CommentRequiredError as error:
            raise HTTPException(status_code=400) from error
        except receipts.RecycledKeyError as error:
            raise HTTPException(status_code=409) from error
        except actions.ActionNotAllowedError as error:
            # `409` y no `403`: no es que falte permiso, es que el caso o la
            # aseguradora no admiten esa accion ahora. Aqui llega tambien "otra
            # persona decidio antes" (BR4.4), porque un caso cerrado no esta entre
            # los estados decidibles: es la misma regla y tiene una sola guardia.
            # Y se rechaza **sin cambiar el caso**, que es lo que la regla pide.
            raise HTTPException(status_code=409) from error
        except casos.ClosingRejectedError as error:
            # El caso no se pudo cerrar --le falta un adjunto por evaluar--: es un
            # estado del caso, no un defecto, y se responde como tal en vez de con
            # un error interno. El intento ya quedo en su historial.
            raise HTTPException(status_code=409) from error
        except LookupError as error:
            raise _rechazo() from error
        return DecisionOut(
            decision_id=registrada.receipt_id,
            case_state=registrada.case_state,
            resolution=registrada.resolution.value,
        )

    return enrutador


def visitor_router() -> APIRouter:
    """El canje del enlace (C-07). Sin credencial y fuera del prefijo de la bandeja.

    Fuera de `/api/inbox` a proposito: es la ruta de un visitante que no tiene
    aseguradora ni credencial, y colgarla del prefijo de la bandeja diria que
    pertenece a una.
    """
    enrutador = APIRouter(prefix="/api", tags=["inbox"])

    @enrutador.post(enlace.REDEEM_PATH, operation_id="redeemCaseLink")
    async def redeem_case_link(body: RedeemIn, response: Response) -> RedeemOut:
        """Cambia el token por una cookie limitada a **ese** caso (BR5.2, BR5.6).

        Las cuatro causas de rechazo responden lo mismo: un mensaje distinto por
        causa le dice a quien prueba enlaces cual de sus intentos acerto.
        """
        ahora = _ahora()
        try:
            sesion = await enlace.redeem(body.token, signing_key=_clave_de_enlace(), now=ahora)
        except enlace.CaseSessionInvalidError as error:
            raise _rechazo() from error

        response.set_cookie(
            enlace.CASE_COOKIE,
            body.token,
            max_age=enlace.cookie_max_age(sesion, now=ahora),
            httponly=True,
            secure=True,
            samesite="lax",
            # Solo bajo `/api`: la pagina no la necesita y lo que no se manda no
            # se filtra.
            path="/api",
        )
        return RedeemOut(
            case_id=sesion.case_id,
            tenant=sesion.tenant_id,
            access=sesion.access,
            expires_at=sesion.expires_at.isoformat(),
        )

    return enrutador


def examples_router() -> APIRouter:
    """Los casos de ejemplo (C-05, ampliacion aditiva del 2026-10-11).

    Dos lecturas publicas, sin credencial, fuera del prefijo de la bandeja: quien
    las usa no es personal de ninguna aseguradora. **Solo entregan casos del
    generador** (`examples`): un caso de visitante, uno de otra aseguradora y uno
    que no existe responden lo mismo, y no se emite ningun enlace ni cookie.
    """
    enrutador = APIRouter(prefix="/api/examples", tags=["examples"])

    def _aseguradora(tenant_id: str) -> TenantConfig:
        try:
            return tenancy.require(tenant_id)
        except UnknownTenantError as error:
            raise _rechazo() from error

    @enrutador.get("/{tenant_id}/cases", operation_id="listExampleCases")
    async def list_example_cases(tenant_id: str) -> ExampleCaseList:
        """Los casos de ejemplo de la aseguradora, por estado y luego por numero."""
        aseguradora = _aseguradora(tenant_id)
        filas = await examples.listar(aseguradora.tenant_id)
        return ExampleCaseList(
            items=tuple(
                ExampleCaseItem(
                    case_id=fila.case_id,
                    case_number=fila.case_number,
                    record_type=fila.record_type,
                    state=fila.state,
                    channel=fila.channel,
                    language=fila.language,
                    completeness_complete=fila.completeness.complete,
                    completeness_total=fila.completeness.total,
                )
                for fila in filas
            )
        )

    @enrutador.get("/{tenant_id}/cases/{case_id}", operation_id="getExampleCase")
    async def get_example_case(tenant_id: str, case_id: str) -> CaseDetailOut:
        """Un caso de ejemplo con sus seis bloques, sin ninguna accion posible."""
        aseguradora = _aseguradora(tenant_id)
        detalle = await examples.detalle(aseguradora.tenant_id, case_id)
        if detalle is None:
            raise _rechazo()
        # Lo anotado va en claro, como en el caso del visitante: son datos sinteticos
        # que escribio el generador, y sin ellos la pantalla diria "Completo" sin
        # mostrar que se anoto.
        anotado = await casos.open_field_values(
            aseguradora.tenant_id,
            case_id,
            detalle.completeness_per_field,
            cipher=crypto.active(),
        )
        # Sin credencial, y la pagina es publica: el tipo de quien decidio viaja y su
        # identificador no (la pantalla dice "un ajustador de la aseguradora").
        return _al_cable(
            detalle, aseguradora, anotado=anotado, solo_lectura=True, nombrar_personal=False
        )

    return enrutador


async def _sonda() -> None:
    """Que la bandeja responde: una consulta que no toca ninguna fila."""
    tenant_id = tenancy.available_ids()[0]
    async with db.session_for(tenant_id) as sesion:
        await db.fetch_one(sesion, "SELECT 1 AS ok FROM inbox_event LIMIT 1")


def surfaces() -> tuple[SurfaceSpec, ...]:
    """La superficie de la bandeja, una por aseguradora (C-24, F8).

    **No es publica**: se entra con credencial, y las credenciales no se publican
    (D23). Lo que decide `public` es si aparece en el inicio del sitio, y una
    bandeja anunciada en el inicio invitaria a probar credenciales.
    """
    return (
        SurfaceSpec(
            surface_id=SurfaceId.INBOX,
            owning_unit="u14-inbox",
            public=False,
            per_tenant=True,
            probe=SurfaceProbe(check=_sonda, timeout_ms=PROBE_TIMEOUT_MS),
        ),
        # El enlace firmado al caso del visitante (BR5.5): el chat lo entrega desde que
        # el caso nace, y sin declararlo la guia escondia sus dos pasos (D4, fase 3,
        # 2026-10-08). Publico porque lo abre quien reporto, sin credencial de personal.
        SurfaceSpec(
            surface_id=SurfaceId.CASE_LINK,
            owning_unit="u14-inbox",
            public=True,
            per_tenant=True,
            probe=SurfaceProbe(check=_sonda, timeout_ms=PROBE_TIMEOUT_MS),
        ),
    )


def purgers() -> tuple[Any, ...]:
    """El purgador de la bandeja (C-11). Lo consume la raiz de composicion."""
    from untangle.inbox.purge import INBOX_PURGER

    return (INBOX_PURGER,)


__all__ = [
    "COOKIE",
    "QueueItem",
    "QueuePage",
    "install_keys",
    "purgers",
    "reset_keys",
    "router",
    "surfaces",
]
