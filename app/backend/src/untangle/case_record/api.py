"""La superficie de U4: las once operaciones del modulo.

Seis las declara el contrato C-12 --abrir, leer, transicionar, fijar un campo,
anexar un turno y anexar al historial--. Las otras cinco se anadieron aqui con su
razon escrita: **cerrar**, que es la transicion con nombre propio porque su
rechazo nombra el adjunto que falto; **leer por numero**, que es la otra mitad
de BR7.3 y lo que una persona teclea de verdad; **leer la transcripcion**, que
anadio U10 porque la revision completa de cumplimiento la lee (BR5.1); y
**registrar una parte** junto con **leerlas**, que anadio U11 porque es quien
primero necesita anotar al tercero que reporta y a las demas partes del
accidente (BR1.5).

Ocho unidades consumen este modulo --U8, U9, U10, U11, U12, U14, U19 y U20-- y
ninguna toca el repositorio, el historial ni el cifrador por su cuenta. Lo que
esta aqui es el acuerdo; lo que no esta, no se puede hacer.

**Lo que esta superficie deliberadamente NO ofrece**, y cada ausencia es una
garantia que se puede comprobar leyendo esta lista:

| No existe | Por que |
| --- | --- |
| Editar o borrar una entrada del historial | Es de solo anexar (SEC-U4.11) |
| Guardar un turno sin redactar | El tipo del texto es el redactado de U3 (SEC-U4.6) |
| Fijar un campo sin su evidencia | Un campo dicho lleva exactamente una (BR2.4) |
| Cambiar el numero, el tipo o el origen de un caso | No cambian |
| Cerrar sin resolucion o sin los cinco adjuntos | BR3.4 y BR6.3 |

**La vista no lleva ningun dato personal**, y eso no es una omision: lleva el
estado, la completitud y las etiquetas, que es lo que las ocho unidades
necesitan. El nombre del testigo y el valor de un campo viven cifrados y se
piden aparte, con el cifrador delante, por quien de verdad los necesita.

**Una transicion rechazada levanta**, y el llamador no la captura para seguir
adelante (convencion 8b del equipo). Antes de levantar deja su entrada en el
historial: la excepcion sale **despues** de que el rastro este guardado, no en
vez de el.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime

from untangle.base import Locale
from untangle.case_record import fields, history, numbering, repository, rules, transcript
from untangle.case_record.crypto import Cipher
from untangle.case_record.models import (
    Actor,
    Case,
    CaseChange,
    CaseField,
    CaseId,
    CaseParty,
    CaseState,
    Channel,
    ClosingEvidence,
    Completeness,
    Origin,
    Priority,
    RecordType,
    Resolution,
    TranscriptTurn,
    TurnId,
)
from untangle.case_record.models import (
    ClosingRejectedError as ClosingRejectedError,
)
from untangle.case_record.models import (
    FieldStatus as FieldStatus,
)
from untangle.case_record.models import (
    InvalidTransitionError as InvalidTransitionError,
)
from untangle.compliance.redaction.api import Redacted
from untangle.tenancy import session
from untangle.tenancy.models import TenantId


class CaseClosedError(RuntimeError):
    """El caso esta cerrado y lo que se pidio lo cambiaria.

    Un caso cerrado expone que se comprobo al cerrarlo. Dejar que sus campos
    cambien despues convertiria esa evidencia en un adorno: seguiria ahi,
    atestiguando algo que ya no es.
    """


class CaseNotFoundError(LookupError):
    """No hay caso con ese identificador **en esta aseguradora**.

    Los dos sentidos caben aqui a proposito --no existe, o no es suyo-- porque
    la politica de fila no deja distinguirlos y el mensaje tampoco lo intenta:
    quien prueba numeros de caso no puede confirmar que uno ajeno existe
    (SEC-U4.3, SEC-U4.14).
    """


@dataclass(frozen=True)
class CaseView:
    """Lo que ve quien consume U4. Sin un solo dato personal dentro.

    Los valores internos de los enums **no se imprimen nunca** hacia una
    persona: la etiqueta sale del catalogo de textos en su idioma (SEC-U4.15).
    Viajan aqui porque quien consume es codigo, no una pantalla.
    """

    case_id: CaseId
    case_number: str
    record_type: RecordType
    state: CaseState
    resolution: Resolution | None
    channel: Channel
    origin: Origin
    language: Locale
    policy_ref: str | None
    derivation_reason: str | None
    #: El turno en que salio la frase de derivacion, cuando la hubo en un turno.
    derived_turn_id: str | None
    completeness: Completeness


def _vista(case: Case, completitud: Completeness) -> CaseView:
    return CaseView(
        case_id=case.case_id,
        case_number=str(case.case_number),
        record_type=case.record_type,
        state=case.state,
        resolution=case.resolution,
        channel=case.channel,
        origin=case.origin,
        language=case.language,
        policy_ref=case.policy_ref,
        derivation_reason=(case.derivation_reason.value if case.derivation_reason else None),
        derived_turn_id=case.derived_turn_id,
        completeness=completitud,
    )


async def _con_completitud(tenant_id: TenantId, case: Case) -> CaseView:
    campos = await repository.load_fields(tenant_id, case.case_id)
    return _vista(case, fields.completeness_of(case.record_type, campos))


@dataclass(frozen=True)
class CaseSummary:
    """Una fila de una lista de casos: lo que se decide **sin** abrir el caso.

    Es `CaseView` mas lo que solo importa cuando hay muchos delante --prioridad y
    los dos instantes--, y menos nada. Sigue sin llevar un solo dato personal: lo
    que hay aqui son enums, numeros y horas (BR1.2 de U14).
    """

    case_id: CaseId
    case_number: str
    record_type: RecordType
    state: CaseState
    resolution: Resolution | None
    channel: Channel
    language: Locale
    priority: Priority
    derivation_reason: str | None
    completeness: Completeness
    created_at: datetime
    #: Desde cuando no se mueve. Es la espera de la cola: un caso derivado no se
    #: toca mientras espera decision, asi que esto es cuando se derivo.
    updated_at: datetime
    #: El rango con que lo ordeno el motor. Viaja para que quien arme el cursor
    #: no tenga que recalcular la regla del orden en un segundo sitio.
    priority_rank: int


@dataclass(frozen=True)
class CasePage:
    """Una pagina de casos y, si hay mas, por donde sigue."""

    items: tuple[CaseSummary, ...]
    next_cursor: repository.ListingCursor | None


async def list_cases(
    tenant_id: TenantId,
    *,
    filters: repository.ListingFilters,
    limit: int,
    cursor: repository.ListingCursor | None = None,
) -> CasePage:
    """Una pagina de casos de esa aseguradora, con su completitud ya calculada.

    Los campos de la pagina entera se leen en **una** consulta: pedirlos caso por
    caso haria que una pagina de veinte costara veintiuna, y la vista de caso
    declara el conteo de consultas como objetivo medible.

    Se pide una fila de mas que el limite para saber si hay pagina siguiente sin
    contar el total: contar obligaria a recorrer la tabla entera para responder
    una pregunta de si o no.
    """
    casos, rangos = await repository.list_cases(
        tenant_id, filters=filters, limit=limit + 1, cursor=cursor
    )
    hay_mas = len(casos) > limit
    casos, rangos = casos[:limit], rangos[:limit]

    campos = await repository.load_fields_of(tenant_id, [caso.case_id for caso in casos])
    filas = tuple(
        CaseSummary(
            case_id=caso.case_id,
            case_number=str(caso.case_number),
            record_type=caso.record_type,
            state=caso.state,
            resolution=caso.resolution,
            channel=caso.channel,
            language=caso.language,
            priority=caso.priority,
            derivation_reason=(caso.derivation_reason.value if caso.derivation_reason else None),
            completeness=fields.completeness_of(caso.record_type, campos.get(caso.case_id, ())),
            created_at=caso.created_at,
            updated_at=caso.updated_at,
            priority_rank=rango,
        )
        for caso, rango in zip(casos, rangos, strict=True)
    )
    siguiente = (
        repository.ListingCursor(
            priority_rank=filas[-1].priority_rank,
            updated_at=filas[-1].updated_at,
            case_id=filas[-1].case_id,
        )
        if hay_mas and filas
        else None
    )
    return CasePage(items=filas, next_cursor=siguiente)


@dataclass(frozen=True)
class NewCase:
    """Lo que hace falta para abrir un caso. Nada opcional se inventa."""

    case_id: CaseId
    record_type: RecordType
    channel: Channel
    origin: Origin
    language: Locale
    policy_ref: str | None = None
    #: El caso del que viene este, cuando la persona cambio de tema en el chat. Solo se
    #: escribe al crear (2026-10-13): ver `conversation_transcript`.
    continues_case_id: CaseId | None = None


async def create_case(tenant_id: TenantId, nuevo: NewCase, *, now: datetime) -> CaseView:
    """Abre un caso con su numero acunado y su completitud en cero.

    El numero se acuna contra los ya **emitidos** por esa aseguradora --los del
    libro que sobrevive al reinicio nocturno-- y no contra un contador: un numero
    correlativo deja ver cuantos casos lleva la demostracion a cualquiera que
    reciba uno.

    Falla si el tipo de registro no declara campos: un caso con completitud 0/0
    se podria cerrar sin haber capturado nada (BR1.6).
    """
    fields.definitions_for(nuevo.record_type)
    # Los seriales del **libro de emitidos**, que sobrevive al reinicio nocturno
    # (BR2.5 de U20): los casos de anoche ya no estan, y sin el libro sus numeros
    # volverian a quedar libres.
    tomados = await repository.issued_serials(tenant_id)
    case = Case(
        case_id=nuevo.case_id,
        tenant_id=tenant_id,
        case_number=numbering.mint(tenant_id, taken=tomados),
        record_type=nuevo.record_type,
        channel=nuevo.channel,
        origin=nuevo.origin,
        language=nuevo.language,
        policy_ref=nuevo.policy_ref,
        continues_case_id=nuevo.continues_case_id,
        created_at=now,
        updated_at=now,
    )
    await repository.insert_case(tenant_id, case)
    return _vista(case, fields.completeness_of(case.record_type, ()))


async def summary_with_fields(
    tenant_id: TenantId, case_id: CaseId
) -> tuple[CaseSummary, tuple[CaseField, ...]] | None:
    """El caso como fila --con prioridad y espera-- y sus campos, en dos consultas.

    Anadida por U14 el 2026-09-28, enmienda aditiva a C-12. `get_case` devuelve
    `CaseView`, que no lleva prioridad ni el instante desde el que espera, y la
    bandeja los necesita en el encabezado del caso; ademas los devuelve **junto**
    con los campos porque quien abre un caso los quiere los dos y pedirlos por
    separado leeria la tabla de campos dos veces --una dentro del calculo de
    completitud y otra fuera--.

    Que la fila de la cola y el encabezado del caso salgan del mismo tipo no es
    comodidad: es lo que impide que digan cosas distintas del mismo caso.
    """
    case = await repository.load_case(tenant_id, case_id)
    if case is None:
        return None
    campos = await repository.load_fields(tenant_id, case_id)
    completitud = fields.completeness_of(case.record_type, campos)
    return (
        CaseSummary(
            case_id=case.case_id,
            case_number=str(case.case_number),
            record_type=case.record_type,
            state=case.state,
            resolution=case.resolution,
            channel=case.channel,
            language=case.language,
            priority=case.priority,
            derivation_reason=(case.derivation_reason.value if case.derivation_reason else None),
            completeness=completitud,
            created_at=case.created_at,
            updated_at=case.updated_at,
            priority_rank=0 if case.priority is Priority.HIGH else 1,
        ),
        campos,
    )


async def get_case(tenant_id: TenantId, case_id: CaseId) -> CaseView | None:
    """El caso, o nada.

    Un caso de otra aseguradora y uno inexistente devuelven lo mismo, y no
    porque se compare y se disimule: la politica de fila filtra antes, asi que
    aqui no hay forma de distinguirlos aunque se quisiera (SEC-U4.3, SEC-U4.14).
    """
    case = await repository.load_case(tenant_id, case_id)
    return await _con_completitud(tenant_id, case) if case is not None else None


async def cases_by_id(tenant_id: TenantId, case_ids: Sequence[CaseId]) -> tuple[Case, ...]:
    """Varios casos de esa aseguradora, sin completitud: solo lo que son.

    Lo usa la telemetria para nombrar cada caso de su lista por lo que fue --tipo,
    canal y hora-- sin mostrar su numero (2026-10-09).
    """
    return await repository.load_cases(tenant_id, case_ids)


async def get_case_by_number(tenant_id: TenantId, case_number: str) -> CaseView | None:
    """El caso por su numero legible, o nada.

    Es la otra mitad de BR7.3: la regla se dispara al consultar "por su
    identificador **o por su numero**", y hasta la revision asesora de esta
    etapa solo existia la primera. Un numero de otra aseguradora responde igual
    que uno que no existe, por la misma razon y sin ninguna comparacion: la
    politica de fila filtra antes de que este codigo mire.
    """
    case = await repository.load_case_by_number(tenant_id, case_number)
    return await _con_completitud(tenant_id, case) if case is not None else None


async def apply_transition(
    tenant_id: TenantId, case_id: CaseId, to: CaseState, *, context: rules.TransitionContext
) -> CaseView:
    """Lleva el caso al estado pedido, o levanta dejando el intento escrito.

    La entrada del historial se anexa **antes** de levantar, en los dos caminos.
    Es la diferencia entre un rechazo que se puede auditar y uno que solo existio
    en la memoria del proceso (BR5.4, SEC-U4.12).
    """
    case = await _caso_o_error(tenant_id, case_id)

    # La marca de cuando el caso entro en derivado la pone **U4**, que es quien
    # tiene el historial, y no quien llama. Es lo que convierte la ventana para
    # retomar en una condicion de verdad: un consumidor que pasara la hora
    # actual la abriria siempre. Lo que sigue a cargo del consumidor --la clave
    # del navegador y si una decision empezo-- esta escrito en el contrato.
    if context.derived_at is None:
        context = replace(context, derived_at=await history.derived_at(tenant_id, case_id))

    resultado = rules.attempt_transition(case, to=to, context=context)

    # El caso movido y su entrada se escriben en **una sola transaccion**. Con
    # una por operacion, un fallo del `UPDATE` dejaria en el historial una
    # transicion que no ocurrio, y un fallo del anexado dejaria un caso movido
    # sin rastro de quien lo movio (BR5.1, SEC-U4.12).
    #
    # El caso se escribe primero y **solo si sigue en el estado que se leyo**: si otro
    # lo movio entretanto, lo que se anexa es el rechazo y no una transicion que no
    # ocurrio (ver `repository.update_case`).
    cambio = resultado.change
    async with session.session_for(tenant_id) as sesion:
        if resultado.accepted and resultado.case is not None:
            escrito = await repository.update_case(
                tenant_id, resultado.case, expected_state=case.state, en=sesion
            )
            if not escrito:
                cambio = rules.moved_meanwhile(case, to=to, context=context)
        await history.append(tenant_id, cambio, en=sesion)

    if cambio is not resultado.change:
        raise InvalidTransitionError(cambio.detail or "transicion rechazada")
    if not resultado.accepted or resultado.case is None:
        raise InvalidTransitionError(resultado.reason or "transicion rechazada")

    return await _con_completitud(tenant_id, resultado.case)


async def set_policy_ref(tenant_id: TenantId, case_id: CaseId, policy_number: str) -> CaseView:
    """Ata el caso a la poliza que la persona confirmo (P3, decision de Miguel, 2026-10-06).

    Hasta entonces `policy_ref` solo lo escribian el alta del caso y el sembrado:
    una poliza dada por la conversacion nunca llegaba a la columna, y la pregunta
    de cobertura degradaba por "sin poliza identificada" aunque la persona la
    hubiera dicho. Solo se escribe una poliza que el corpus devolvio y la persona
    confirmo; el numero, el tipo y el origen del caso no se tocan.
    """
    case = await _caso_o_error(tenant_id, case_id)
    # `evolve` valida el caso con la poliza nueva; lo que se escribe es solo la poliza,
    # para no devolver a su sitio un estado que otro acaba de mover.
    case.evolve(policy_ref=policy_number)
    await repository.set_policy_ref(tenant_id, case_id, policy_number)
    return await _con_completitud(tenant_id, await _caso_o_error(tenant_id, case_id))


async def close_case(  # noqa: PLR0913 -- la resolucion, la evidencia, el contexto y el comentario
    tenant_id: TenantId,
    case_id: CaseId,
    *,
    resolution: Resolution,
    closing_evidence: ClosingEvidence,
    context: rules.TransitionContext,
    comment: str | None = None,
) -> CaseView:
    """Cierra el caso con su resolucion y sus cinco adjuntos.

    Es una transicion como las demas y va por el mismo camino; existe aparte
    porque su rechazo **nombra el adjunto que falto**, que es lo unico que el
    ajustador necesita para resolverlo.
    """
    case = await _caso_o_error(tenant_id, case_id)
    resultado = rules.attempt_close(
        case,
        resolution=resolution,
        closing_evidence=closing_evidence,
        context=context,
        # El comentario de quien decidio, ya redactado por quien llama: esta
        # superficie no redacta, igual que no cifra. Lo que si hace es dejarlo en
        # la misma entrada que el cierre, porque es el mismo acto (BR4.1 de U14).
        comment=comment,
    )

    cambio = resultado.change
    async with session.session_for(tenant_id) as sesion:
        if resultado.accepted and resultado.case is not None:
            escrito = await repository.update_case(
                tenant_id, resultado.case, expected_state=case.state, en=sesion
            )
            if not escrito:
                cambio = rules.moved_meanwhile(
                    case, to=CaseState.CLOSED, context=context, closing=True
                )
        await history.append(tenant_id, cambio, en=sesion)

    if cambio is not resultado.change:
        raise ClosingRejectedError(cambio.detail or "cierre rechazado")
    if not resultado.accepted or resultado.case is None:
        raise ClosingRejectedError(resultado.reason or "cierre rechazado")

    return await _con_completitud(tenant_id, resultado.case)


async def open_field_values(
    tenant_id: TenantId,
    case_id: CaseId,
    keys: Iterable[str],
    *,
    cipher: Cipher,
) -> dict[str, str]:
    """Abre el valor de unos campos del caso, en claro (C-12, FD-U11-8).

    **Es la puerta simetrica de `set_field`**: esta unidad sella al escribir y
    esta unidad abre al leer, y por eso el cifrador entra por argumento en las
    dos. Antes del 2026-09-29 no existia: los valores se escribian y nadie los
    volvia a leer en claro, asi que una lectura de confirmacion no podia nombrar
    lo que confirmaba --y sin nombrarlo, FD-U11-8 no se cumple--.

    **Se pide lo que se necesita, no el caso entero.** Quien llama nombra las
    claves; abrir todo "por comodidad" convertiria cada turno en una operacion
    sobre todos los datos personales del caso.

    **Un campo que no se puede abrir no sale.** Pasa cuando la fila la cerro otra
    clave --una rotacion a mitad de caso-- o el dato esta corrupto. No se levanta
    ni se devuelve un marcador: se omite, y su ausencia deja al consumidor
    tratandolo como lo que es, un dato que hoy no se tiene. `unseal` ya dejo su
    evento de rastro con la clave y la causa, **nunca con el valor**.
    """
    pedidas = set(keys)
    if not pedidas:
        return {}
    sellados = await repository.load_sealed_values(tenant_id, case_id)
    abiertos: dict[str, str] = {}
    for clave in pedidas:
        guardado = sellados.get(clave)
        if guardado is None:
            continue
        valor, key_id = guardado
        abierto = cipher.unseal(valor, stored_key_id=key_id)
        if isinstance(abierto, str):
            abiertos[clave] = abierto
    return abiertos


async def set_field(  # noqa: PLR0913 -- el campo, el cifrador, el actor, el canal y la entrada
    tenant_id: TenantId,
    campo: CaseField,
    *,
    cipher: Cipher,
    actor: Actor,
    channel: Channel | None = None,
    change_id: str | None = None,
) -> None:
    """Fija o corrige un campo, y deja su entrada con el valor anterior.

    El valor llega ya sellado dentro del campo: esta superficie no cifra, y el
    cifrador entra solo para escribir el identificador de la clave con la fila y
    para sellar la copia que va al historial.
    """
    case = await _caso_o_error(tenant_id, campo.case_id)
    if case.state is CaseState.CLOSED:
        # Un caso cerrado expone que se comprobo **al cerrarlo** (BR6.4,
        # NFR-U4-9). Si sus campos pudieran cambiar despues, la evidencia
        # congelada seguiria ahi atestiguando algo que ya no es. Lo encontro la
        # revision asesora de esta etapa: nadie lo impedia.
        msg = (
            f"el caso '{campo.case_id}' esta cerrado y sus campos ya no cambian: "
            f"su evidencia de cierre atestigua lo que habia al cerrarlo (BR6.4)"
        )
        raise CaseClosedError(msg)
    fields.validate_field(case.record_type, campo)
    anteriores = await repository.load_fields(tenant_id, campo.case_id)
    previo = next((c.value for c in anteriores if c.field_key == campo.field_key), None)

    # El campo y su entrada, en **una sola transaccion**: si la segunda fallara
    # por separado quedaria un campo escrito sin rastro de quien lo cambio, que
    # es literalmente lo que BR5.1 llama una perdida.
    async with session.session_for(tenant_id) as sesion:
        await repository.save_field(tenant_id, campo, key_id=cipher.id, en=sesion)
        await history.append(
            tenant_id,
            history.field_set(
                campo,
                previous=previo,
                actor=actor,
                channel=channel,
                # Cuando quien llama ya acuno el identificador --porque el campo
                # lo lleva como su evidencia-- se usa el suyo. Acunar otro aqui
                # dejaria al campo apuntando a una entrada que no existe.
                change_id=change_id,
            ),
            cipher=cipher,
            en=sesion,
        )


async def register_party(tenant_id: TenantId, parte: CaseParty, *, cipher: Cipher) -> None:
    """Registra una parte del caso -- testigo, otro conductor, otro vehiculo o lesionado.

    **Novena^2 operacion**, anadida por U11 (enmienda de C-12 del 2026-09-27,
    mismo patron que la novena de U10): `parties.register_party` ya sellaba la
    fila con su cipher y `repository.insert_party` ya la guardaba, pero ninguna
    unidad anterior necesitaba escribirla, asi que esta superficie no la
    ofrecia (BR1.5).

    **Sin entrada de historial.** `ChangeKind` no declara un valor para esta
    escritura, y anadir uno alteraria la restriccion `CHECK` de `case_change`
    -- exactamente la migracion que a esta unidad le esta prohibido crear
    (FD-U11-5, `entities.md`: "U11 no crea ninguna entidad ni migracion"). Las
    partes del caso quedan, por ahora, sin la misma pista de auditoria que un
    campo o una transicion; es una limitacion heredada de U4 que esta unidad
    no resuelve, no una que introduzca.
    """
    case = await _caso_o_error(tenant_id, parte.case_id)
    if case.state is CaseState.CLOSED:
        msg = (
            f"el caso '{parte.case_id}' esta cerrado y sus partes ya no cambian "
            "(BR6.4, la misma regla que protege sus campos)"
        )
        raise CaseClosedError(msg)
    await repository.insert_party(tenant_id, parte, key_id=cipher.id)


async def parties_of(tenant_id: TenantId, case_id: CaseId) -> tuple[CaseParty, ...]:
    """Las partes ya registradas del caso, en el orden en que se anexaron.

    Solo lectura, como `transcript_of`: no abre ninguna puerta que
    `register_party` no abriera ya.
    """
    return await repository.load_parties(tenant_id, case_id)


#: Cuantos casos atras se sigue una conversacion que cambio de tema. Es un tope del recorrido,
#: no una regla de negocio: nadie cambia de tema diez veces en una demostracion, y una cadena
#: mas larga leeria mas de lo que cabe en el contexto del modelo.
CHAIN_MAX_HOPS = 10


async def conversation_transcript(
    tenant_id: TenantId, case_id: CaseId, *, max_hops: int = CHAIN_MAX_HOPS
) -> tuple[TranscriptTurn, ...]:
    """Lo dicho en este caso y en los casos por los que paso la conversacion hasta llegar a el.

    Anadida el 2026-10-13 (enmienda aditiva a C-12): quien cambia de tema en el chat abre un caso
    nuevo, y lo que la agente recuerda y lo que la pantalla recupera al recargar tienen que
    salir de los dos. Se lee **a traves de la cadena y no copiando turnos**: copiarlos duplicaria
    las respuestas y dejaria sin sus clausulas las de cobertura. Del caso mas antiguo al propio;
    cada turno conserva su `case_id`.

    Solo recorre hacia atras, por los enlaces que el propio canal escribio al abrir cada caso, y
    la llave lleva la aseguradora: no cruza a otra. Quien llama parte del caso de **su**
    conversacion, nunca de uno que le dieron de fuera. Para la transcripcion de un solo caso
    --la bandeja, "Ver mi caso", la revision de cumplimiento-- sigue `transcript_of`.
    """
    return await repository.load_conversation_turns(tenant_id, case_id, max_hops=max_hops)


async def append_turn(tenant_id: TenantId, draft: transcript.TurnDraft, text: Redacted) -> TurnId:
    """Guarda un turno **ya redactado**. No acepta texto sin redactar.

    El tipo lo impide antes de ejecutar: `Redacted` solo lo fabrica el modulo de
    redaccion de U3, y `mise run redaction:constructor` falla ante cualquier
    otro sitio que lo intente (C-13, SEC-U4.6).
    """
    turno = transcript.append(draft, text)
    await repository.insert_turn(tenant_id, turno)
    return turno.turn_id


async def transcript_of(tenant_id: TenantId, case_id: CaseId) -> tuple[TranscriptTurn, ...]:
    """La transcripcion del caso, en el orden en que se dijo, ya redactada.

    La **novena** operacion, anadida por U10 (enmienda de C-12 del 2026-09-21):
    la revision completa de cumplimiento lee la conversacion para comprobar la
    ruta a persona y los datos personales (BR5.1), y hasta hoy ningun consumidor
    la leia, asi que la superficie no la ofrecia. Es solo lectura y no abre
    ninguna puerta nueva: el texto ya esta redactado al guardarse (SEC-U4.6), y
    un caso de otra aseguradora devuelve vacio porque la politica de fila filtra
    antes de que este codigo lo vea.
    """
    return await repository.load_turns(tenant_id, case_id)


async def record_change(
    tenant_id: TenantId, cambio: CaseChange, *, cipher: Cipher | None = None
) -> None:
    """Anexa una entrada al historial. No hay forma de editar ni de borrar."""
    await history.append(tenant_id, cambio, cipher=cipher)


async def _caso_o_error(tenant_id: TenantId, case_id: CaseId) -> Case:
    case = await repository.load_case(tenant_id, case_id)
    if case is None:
        msg = f"no hay caso '{case_id}' en esta aseguradora"
        raise CaseNotFoundError(msg)
    return case


__all__ = [
    "CHAIN_MAX_HOPS",
    "CaseClosedError",
    "CaseNotFoundError",
    "CaseView",
    "ClosingRejectedError",
    "FieldStatus",
    "InvalidTransitionError",
    "NewCase",
    "append_turn",
    "apply_transition",
    "cases_by_id",
    "close_case",
    "conversation_transcript",
    "create_case",
    "get_case",
    "get_case_by_number",
    "open_field_values",
    "parties_of",
    "record_change",
    "register_party",
    "set_field",
    "set_policy_ref",
    "transcript_of",
]
