"""Donde el caso se guarda y de donde se lee.

**Ninguna conexion propia.** Toda consulta pasa por el punto unico de sesion de
U2, que fija la aseguradora antes de devolver la sesion (SEC-U4.1). Este archivo
no sabe la direccion de la base, no construye un motor y no arma SQL por
concatenacion: los parametros se ligan. Un contrato de importacion falla ante
cualquier apertura de conexion plantada aqui.

**No conoce la clave ni el algoritmo.** Recibe valores ya sellados y los
escribe; al leer, declara que los bytes de la columna son un valor sellado y los
devuelve tal cual. Quien quiera el texto se lo pide al cifrador. Eso deja una
sola puerta hacia el almacen para el dato personal, que es lo que hace
comprobable "todo lo personal se cifra antes de persistir".

**Un caso de otra aseguradora y uno inexistente responden igual** (SEC-U4.3), y
no porque se compare y se disimule: la politica de fila filtra antes, asi que la
consulta devuelve cero filas en los dos casos y este codigo no tiene forma de
distinguirlos aunque quisiera. Un control que no se puede saltar ni queriendo es
mejor que uno que se cumple por cuidado.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from untangle.case_record.crypto import from_storage
from untangle.case_record.models import (
    Actor,
    ActorType,
    Case,
    CaseChange,
    CaseField,
    CaseId,
    CaseNumber,
    CaseParty,
    CaseState,
    ChangeKind,
    ClosingEvidence,
    KeyId,
    Sealed,
    TranscriptTurn,
)
from untangle.tenancy import session
from untangle.tenancy.models import TenantId

INSERTAR_CASO = """
    INSERT INTO case_record (case_id, tenant_id, case_number, record_type, state,
                             resolution, channel, origin, language, policy_ref,
                             derivation_reason, derived_turn_id, continues_case_id, priority,
                             closing_evidence, created_at, updated_at, closed_at)
    VALUES (:case_id, :tenant_id, :case_number, :record_type, :state,
            :resolution, :channel, :origin, :language, :policy_ref,
            :derivation_reason, :derived_turn_id, :continues_case_id, :priority,
            CAST(:closing_evidence AS jsonb), :created_at, :updated_at, :closed_at)
"""

#: La evidencia de cierre solo se escribe **una vez**: `COALESCE` conserva la
#: que ya estaba y la nueva solo entra si no habia ninguna (BR6.4). Hoy nadie
#: llega ahi porque `closed` es terminal en la tabla de transiciones, pero eso
#: es ausencia de camino y no rechazo, y el camino vive en otro archivo. Un caso
#: cerrado expone que se comprobo **al cerrarlo**, no lo ultimo que alguien
#: escribio encima.
ACTUALIZAR_CASO = """
    UPDATE case_record
       SET state = :state, resolution = :resolution,
           derivation_reason = :derivation_reason, derived_turn_id = :derived_turn_id,
           priority = :priority,
           policy_ref = :policy_ref,
           closing_evidence = COALESCE(closing_evidence, CAST(:closing_evidence AS jsonb)),
           updated_at = :updated_at, closed_at = :closed_at
     WHERE case_id = :case_id AND state = :expected_state
"""

#: Atar la poliza no mueve el caso, asi que no escribe su estado: una sentencia que
#: volviera a escribir la fila entera devolveria a su sitio un estado que otro acaba
#: de cambiar.
FIJAR_POLIZA = """
    UPDATE case_record SET policy_ref = :policy_ref WHERE case_id = :case_id
"""

LEER_CASO = "SELECT * FROM case_record WHERE case_id = :case_id"

#: Por el numero legible, que es lo que una persona anota y teclea. Responde
#: igual que el de arriba ante un caso ajeno: la politica de fila filtra antes.
LEER_POR_NUMERO = "SELECT * FROM case_record WHERE case_number = :case_number"

GUARDAR_CAMPO = """
    INSERT INTO case_field (case_id, tenant_id, field_key, value, sealed_key_id,
                            status, evidence_turn_id, evidence_change_id,
                            confirmed_aloud_at, updated_at)
    VALUES (:case_id, :tenant_id, :field_key, :value, :sealed_key_id,
            :status, :evidence_turn_id, :evidence_change_id,
            :confirmed_aloud_at, :updated_at)
    ON CONFLICT (case_id, field_key) DO UPDATE
       SET value = excluded.value, sealed_key_id = excluded.sealed_key_id,
           status = excluded.status,
           evidence_turn_id = excluded.evidence_turn_id,
           evidence_change_id = excluded.evidence_change_id,
           confirmed_aloud_at = excluded.confirmed_aloud_at,
           updated_at = excluded.updated_at
"""

LEER_CAMPOS = "SELECT * FROM case_field WHERE case_id = :case_id ORDER BY field_key"

#: La pagina de casos de una aseguradora, con sus filtros, su orden y su cursor
#: (C-12, enmienda del 2026-09-28 pedida por U14).
#:
#: **Los filtros son condiciones con parametro ligado y nunca SQL armado por
#: concatenacion**: cada uno se apaga solo cuando su parametro llega nulo. Armar
#: la clausula `WHERE` con las claves que trajo la peticion seria dejar que quien
#: llama escriba SQL, y la convencion 7 del equipo lo prohibe por esto mismo.
#:
#: **El orden es prioridad y luego espera**, que es BR1.1 de U14: dentro de cada
#: prioridad, primero lo que lleva mas tiempo sin moverse. El rango se calcula en
#: la consulta y no se guarda: derivarlo de la columna deja un solo sitio donde
#: existe la prioridad.
#:
#: **La espera se mide desde `updated_at`** y no desde `created_at`. Un caso que
#: se abrio hace tres dias pero se movio hace un minuto no lleva tres dias
#: esperando: lleva un minuto. Y un caso derivado no se toca mientras espera
#: decision, asi que su `updated_at` es exactamente el momento en que se derivo.
#:
#: **El cursor compara la terna entera** `(rango, espera, identificador)` con la
#: comparacion de filas del propio motor. Comparar solo la fecha se saltaria los
#: casos que comparten instante --que es lo normal cuando se siembran juntos-- y
#: el tercer termino es lo que hace la pagina reproducible.
LISTAR_CASOS = """
    SELECT * FROM (
        SELECT case_id, tenant_id, case_number, record_type, state, resolution,
               channel, origin, language, policy_ref, derivation_reason,
               derived_turn_id, continues_case_id, priority,
               closing_evidence, created_at, updated_at, closed_at,
               CASE priority WHEN 'high' THEN 0 ELSE 1 END AS priority_rank
        FROM case_record
        WHERE NOT (state = ANY(:excluded_states))
          AND (CAST(:record_type AS text) IS NULL OR record_type = :record_type)
          AND (CAST(:state AS text) IS NULL OR state = :state)
          AND (CAST(:channel AS text) IS NULL OR channel = :channel)
          AND (CAST(:language AS text) IS NULL OR language = :language)
          AND (CAST(:priority AS text) IS NULL OR priority = :priority)
          AND (CAST(:origin AS text) IS NULL OR origin = :origin)
    ) AS cola
    WHERE CAST(:cursor_case_id AS text) IS NULL
       OR (cola.priority_rank, cola.updated_at, cola.case_id)
          > (:cursor_rank, CAST(:cursor_updated_at AS timestamptz), :cursor_case_id)
    ORDER BY cola.priority_rank ASC, cola.updated_at ASC, cola.case_id ASC
    LIMIT :limit
"""

#: Los campos de varios casos en una sola consulta. Pedirlos caso por caso haria
#: que una pagina de veinte costara veintiuna consultas, que es el numero que la
#: vista de caso declara como objetivo medible.
LEER_CAMPOS_DE_VARIOS = (
    "SELECT * FROM case_field WHERE case_id = ANY(:case_ids) ORDER BY case_id, field_key"
)

#: Varios casos en una sola consulta: lo pide la telemetria para describir los
#: casos de su lista (2026-10-09).
LEER_VARIOS_CASOS = "SELECT * FROM case_record WHERE case_id = ANY(:case_ids)"

#: La conversacion de un caso: sus turnos y los de los casos de los que viene, del mas antiguo al
#: propio, y dentro de cada caso en el orden en que se dijeron (2026-10-13). El caso es "del que
#: viene" cuando la persona cambio de tema en el chat; ver `case_record.continues_case_id`.
#:
#: **Va por la politica de fila como toda consulta**, y la llave del enlace lleva la aseguradora:
#: la cadena no puede cruzar a otra ni aunque alguien escribiera el enlace a mano. El tope es
#: del recorrido y no de la base: un enlace solo se escribe al crear el caso y apunta a uno
#: anterior, asi que no hay ciclos, pero un recorrido sin limite es el tipo de consulta que un
#: dato raro convierte en una espera sin fin. Se ordena por la posicion en la cadena y despues
#: por la hora, no solo por la hora: cada caso se abre despues de los turnos del anterior, asi
#: que es el mismo orden, y con relojes iguales (las pruebas) deja de ser arbitrario.
LEER_TURNOS_DE_LA_CONVERSACION = """
    WITH RECURSIVE cadena AS (
        SELECT case_id, continues_case_id, 0 AS saltos
        FROM case_record WHERE case_id = :case_id
        UNION ALL
        SELECT previo.case_id, previo.continues_case_id, cadena.saltos + 1
        FROM case_record previo
        JOIN cadena ON previo.case_id = cadena.continues_case_id
        WHERE cadena.saltos < :max_hops
    )
    SELECT t.* FROM case_transcript_turn t
    JOIN cadena ON t.case_id = cadena.case_id
    ORDER BY cadena.saltos DESC, t.started_at, t.turn_id
"""

INSERTAR_PARTE = """
    INSERT INTO case_party (party_id, tenant_id, case_id, role, name, contact,
                            plate, sealed_key_id, injury_status,
                            vehicle_description, plate_status,
                            plate_evidence_turn_id, statement_version, relation)
    VALUES (:party_id, :tenant_id, :case_id, :role, :name, :contact,
            :plate, :sealed_key_id, :injury_status,
            :vehicle_description, :plate_status,
            :plate_evidence_turn_id, :statement_version, :relation)
"""

LEER_PARTES = "SELECT * FROM case_party WHERE case_id = :case_id ORDER BY party_id"

INSERTAR_TURNO = """
    INSERT INTO case_transcript_turn (turn_id, tenant_id, case_id, speaker, channel,
                                      language, text_redacted, started_at, ended_at,
                                      interrupted)
    VALUES (:turn_id, :tenant_id, :case_id, :speaker, :channel,
            :language, :text_redacted, :started_at, :ended_at, :interrupted)
"""

LEER_TURNOS = """
    SELECT * FROM case_transcript_turn WHERE case_id = :case_id
     ORDER BY started_at, turn_id
"""

INSERTAR_CAMBIO = """
    INSERT INTO case_change (change_id, tenant_id, case_id, change_kind, field_key,
                             previous_value, new_value, sealed_key_id, actor_type,
                             actor_id, channel, detail, changed_at)
    VALUES (:change_id, :tenant_id, :case_id, :change_kind, :field_key,
            :previous_value, :new_value, :sealed_key_id, :actor_type,
            :actor_id, :channel, :detail, :changed_at)
"""

#: Por orden de insercion y no por fecha: dos entradas del mismo instante --que
#: las hay, cuando fijar un campo deja su entrada en el mismo milisegundo--
#: quedarian en orden arbitrario ordenando por el reloj.
LEER_CAMBIOS = """
    SELECT * FROM case_change WHERE case_id = :case_id ORDER BY seq
"""

#: Cuantas entradas de una clase dejo un actor en un caso. Una cuenta, no las filas: quien
#: pregunta (el tope de anotaciones del visitante) no necesita leer el historial entero ni
#: abrir sus valores sellados.
CONTAR_CAMBIOS_DE = """
    SELECT count(*) AS total FROM case_change
     WHERE tenant_id = :tenant_id AND case_id = :case_id AND change_kind = :change_kind
       AND actor_type = :actor_type AND actor_id = :actor_id
"""

#: Los seriales ya emitidos por esa aseguradora, del libro que **sobrevive al
#: reinicio nocturno** (BR2.5 de U20). Se consulta el libro y no `case_record`:
#: los casos del visitante se borran cada noche y sus numeros volverian a quedar
#: libres, que es como un numero acaba nombrando dos casos distintos.
#:
#: Devuelve el **serial** y no la columna entera. Antes devolvia `case_number`
#: --`STO-123456`-- y el acunador comparaba el serial --`123456`--, asi que la
#: comprobacion de unicidad no podia coincidir nunca: dos formas del mismo dato,
#: una en cada lado de la frontera.
SERIALES_EMITIDOS = "SELECT serial FROM case_number_issued"

#: El serial queda anotado en la misma transaccion que el caso. `ON CONFLICT DO
#: NOTHING` por una sola razon: sembrar dos veces el mismo caso --la siembra es
#: idempotente-- no es un fallo.
ANOTAR_SERIAL = """
    INSERT INTO case_number_issued (tenant_id, serial, issued_at)
    VALUES (:tenant_id, :serial, :issued_at)
    ON CONFLICT DO NOTHING
"""


@asynccontextmanager
async def _en(
    tenant_id: TenantId, dada: session.TenantSession | None
) -> AsyncIterator[session.TenantSession]:
    """La sesion que me pasan, o una propia si no me pasan ninguna.

    Existe por una razon concreta: escribir un campo y anexar su entrada al
    historial son **una sola cosa**. Con una sesion por operacion, cada una
    confirma por separado y un fallo de la segunda deja un campo escrito sin
    rastro de quien lo cambio, que es literalmente lo que BR5.1 llama una
    perdida. Lo encontro la revision asesora de esta etapa.

    Pasar la sesion no abre una segunda via de acceso: sigue saliendo del punto
    unico de U2, que ya fijo la aseguradora antes de entregarla.
    """
    if dada is not None:
        yield dada
    else:
        async with session.session_for(tenant_id) as nueva:
            yield nueva


def _sellado(fila: Any, columna: str) -> Any:
    """Declara que los bytes de una columna son un valor sellado, o nada.

    Pasa por `from_storage` --y no por un `cast`-- porque es la unica forma que
    el analisis estatico admite de producir el tipo fuera del punto de cifrado.
    """
    crudo = fila[columna]
    return from_storage(bytes(crudo)) if crudo is not None else None


def _a_caso(fila: Any) -> Case:
    prefijo, serial = str(fila["case_number"]).split("-", 1)
    evidencia = fila["closing_evidence"]
    return Case(
        case_id=fila["case_id"],
        tenant_id=fila["tenant_id"],
        case_number=CaseNumber(prefix=prefijo, serial=serial),
        record_type=fila["record_type"],
        state=fila["state"],
        resolution=fila["resolution"],
        channel=fila["channel"],
        origin=fila["origin"],
        language=fila["language"],
        policy_ref=fila["policy_ref"],
        derivation_reason=fila["derivation_reason"],
        derived_turn_id=fila["derived_turn_id"],
        continues_case_id=fila["continues_case_id"],
        priority=fila["priority"],
        closing_evidence=ClosingEvidence.model_validate(evidencia) if evidencia else None,
        created_at=fila["created_at"],
        updated_at=fila["updated_at"],
        closed_at=fila["closed_at"],
    )


def _del_caso(case: Case) -> dict[str, Any]:
    return {
        "case_id": case.case_id,
        "tenant_id": case.tenant_id,
        "case_number": str(case.case_number),
        "record_type": case.record_type.value,
        "state": case.state.value,
        "resolution": case.resolution.value if case.resolution else None,
        "channel": case.channel.value,
        "origin": case.origin.value,
        "language": case.language,
        "policy_ref": case.policy_ref,
        "derivation_reason": (case.derivation_reason.value if case.derivation_reason else None),
        "derived_turn_id": case.derived_turn_id,
        "continues_case_id": case.continues_case_id,
        "priority": case.priority.value,
        # Texto JSON con conversion explicita en la sentencia, no un diccionario
        # de Python: el controlador no adapta uno a la columna por su cuenta, y
        # descubrirlo al cerrar el primer caso en produccion seria tarde.
        "closing_evidence": (
            case.closing_evidence.model_dump_json() if case.closing_evidence else None
        ),
        "created_at": case.created_at,
        "updated_at": case.updated_at,
        "closed_at": case.closed_at,
    }


async def insert_case(
    tenant_id: TenantId, case: Case, *, en: session.TenantSession | None = None
) -> None:
    """Escribe el caso **y anota su serial** en el libro, en la misma transaccion.

    Las dos cosas van juntas porque separarlas deja el estado que BR2.5 prohibe:
    un caso con un numero que el libro no conoce es un numero que manana se
    vuelve a dar.
    """
    async with _en(tenant_id, en) as sesion:
        await session.execute_sql(sesion, INSERTAR_CASO, **_del_caso(case))
        await session.execute_sql(
            sesion,
            ANOTAR_SERIAL,
            tenant_id=tenant_id,
            serial=case.case_number.serial,
            issued_at=case.created_at,
        )


async def update_case(
    tenant_id: TenantId,
    case: Case,
    *,
    expected_state: CaseState,
    en: session.TenantSession | None = None,
) -> bool:
    """Actualiza lo que cambia, **solo si el caso sigue donde se leyo**.

    El numero, el tipo y el origen no estan aqui. No es un olvido: un caso no cambia
    de numero ni de tipo, y dejar la columna fuera del `UPDATE` es mas barato y mas
    claro que una comprobacion que alguien puede quitar.

    `expected_state` es el estado que tenia el caso cuando quien llama lo leyo, y la
    sentencia no escribe si ya no es ese. Desde el 2026-10-13 dos actores mueven un
    mismo caso en los mismos segundos --el sistema que lo cierra por las reglas y el
    ajustador que lo toma, o la persona que pide hablar con alguien--, y sin esta
    condicion el segundo en escribir pisaba al primero: un caso `closed`, que es
    terminal, podia volver a `derived`. Devuelve si escribio; quien llama decide que
    rastro deja cuando no.
    """
    async with _en(tenant_id, en) as sesion:
        tocadas = await session.execute_sql(
            sesion, ACTUALIZAR_CASO, **_del_caso(case), expected_state=expected_state.value
        )
    return tocadas == 1


async def set_policy_ref(
    tenant_id: TenantId,
    case_id: CaseId,
    policy_ref: str,
    *,
    en: session.TenantSession | None = None,
) -> None:
    """Escribe la poliza del caso y nada mas (ver `FIJAR_POLIZA`)."""
    async with _en(tenant_id, en) as sesion:
        await session.execute_sql(sesion, FIJAR_POLIZA, case_id=case_id, policy_ref=policy_ref)


async def load_case(
    tenant_id: TenantId, case_id: CaseId, *, en: session.TenantSession | None = None
) -> Case | None:
    """El caso, o nada. Nada significa las dos cosas a la vez, y esta bien."""
    async with _en(tenant_id, en) as sesion:
        fila = await session.fetch_one(sesion, LEER_CASO, case_id=case_id)
    return _a_caso(fila) if fila is not None else None


async def load_cases(
    tenant_id: TenantId, case_ids: Sequence[CaseId], *, en: session.TenantSession | None = None
) -> tuple[Case, ...]:
    """Los casos que existan de esa lista. Los que no, simplemente no vuelven."""
    if not case_ids:
        return ()
    async with _en(tenant_id, en) as sesion:
        filas = await session.fetch_all(sesion, LEER_VARIOS_CASOS, case_ids=list(case_ids))
    return tuple(_a_caso(fila) for fila in filas)


async def load_case_by_number(
    tenant_id: TenantId, case_number: str, *, en: session.TenantSession | None = None
) -> Case | None:
    """El caso con ese numero legible, o nada.

    El numero **no es una credencial** (SEC-U4.14): adivinarlo no da acceso,
    porque el acceso lo decide el enlace firmado de U2. Esta consulta existe
    para quien ya entro y teclea el numero que anoto.
    """
    async with _en(tenant_id, en) as sesion:
        fila = await session.fetch_one(sesion, LEER_POR_NUMERO, case_number=case_number)
    return _a_caso(fila) if fila is not None else None


async def issued_serials(
    tenant_id: TenantId, *, en: session.TenantSession | None = None
) -> frozenset[str]:
    """Los **seriales** ya emitidos por esa aseguradora, para no repetir al acunar.

    Del libro que sobrevive al reinicio nocturno, no de los casos vivos: lo que
    BR2.5 prohibe es que un numero se repita **despues** del reinicio, y los casos
    de anoche ya no estan para compararse.

    El nombre dice "serial" a proposito. Mientras dijo "numeros" devolvia la
    columna entera y el acunador comparaba seriales, asi que la comprobacion no
    podia coincidir; un nombre que nombra la forma del dato es lo que no deja
    volver a ese estado sin verlo.
    """
    async with _en(tenant_id, en) as sesion:
        filas = await session.fetch_all(sesion, SERIALES_EMITIDOS)
    return frozenset(str(fila["serial"]) for fila in filas)


async def save_field(
    tenant_id: TenantId,
    campo: CaseField,
    *,
    key_id: KeyId | None,
    en: session.TenantSession | None = None,
) -> None:
    async with _en(tenant_id, en) as sesion:
        await session.execute_sql(
            sesion,
            GUARDAR_CAMPO,
            case_id=campo.case_id,
            tenant_id=tenant_id,
            field_key=campo.field_key,
            value=bytes(campo.value) if campo.value is not None else None,
            sealed_key_id=key_id if campo.value is not None else None,
            status=campo.status.value,
            evidence_turn_id=campo.evidence_turn_id,
            evidence_change_id=campo.evidence_change_id,
            confirmed_aloud_at=campo.confirmed_aloud_at,
            updated_at=campo.updated_at,
        )


#: El valor sellado de unos campos, con la clave que los cerro.
LEER_VALORES = """
    SELECT field_key, value, sealed_key_id FROM case_field
    WHERE case_id = :case_id AND value IS NOT NULL
"""


async def load_sealed_values(
    tenant_id: TenantId, case_id: CaseId, *, en: session.TenantSession | None = None
) -> dict[str, tuple[Sealed, str]]:
    """El valor sellado de cada campo del caso, con **la clave que lo cerro**.

    Existe aparte de `load_fields` porque `CaseField` no lleva el identificador de
    la clave --es detalle del almacen y el modelo no lo expone-- y sin el no se
    puede abrir nada: `Cipher.unseal` lo exige para no descifrar a ciegas una fila
    que cerro otra clave. Es lo unico que faltaba para que una lectura de
    confirmacion pueda nombrar lo que confirma (FD-U11-8).

    Devuelve solo los campos **con valor**: uno en `not_stated` no tiene nada que
    abrir.
    """
    async with _en(tenant_id, en) as sesion:
        filas = await session.fetch_all(sesion, LEER_VALORES, case_id=case_id)
    return {
        fila["field_key"]: (_sellado(fila, "value"), str(fila["sealed_key_id"])) for fila in filas
    }


async def load_fields(
    tenant_id: TenantId, case_id: CaseId, *, en: session.TenantSession | None = None
) -> tuple[CaseField, ...]:
    async with _en(tenant_id, en) as sesion:
        filas = await session.fetch_all(sesion, LEER_CAMPOS, case_id=case_id)
    return tuple(
        CaseField(
            case_id=fila["case_id"],
            field_key=fila["field_key"],
            value=_sellado(fila, "value"),
            status=fila["status"],
            evidence_turn_id=fila["evidence_turn_id"],
            evidence_change_id=fila["evidence_change_id"],
            confirmed_aloud_at=fila["confirmed_aloud_at"],
            updated_at=fila["updated_at"],
        )
        for fila in filas
    )


@dataclass(frozen=True)
class ListingFilters:
    """Los filtros de la cola. Todos opcionales y ninguno derivable de otro."""

    state: str | None = None
    channel: str | None = None
    language: str | None = None
    priority: str | None = None
    #: El tipo de registro. Lo anadio U19 porque la bandeja del suscriptor muestra
    #: **solo** solicitudes de cotizacion (BR4.2), y ese recorte tiene que pasar
    #: por la consulta: filtrado despues de traer la pagina, el limite y el cursor
    #: cuentan filas que la lista no muestra, y una peticion directa a la API ve
    #: lo que la pantalla esconde.
    record_type: str | None = None
    #: Los estados que esta lista no muestra **nunca**, ni con filtro. Quien llama
    #: decide cuales: esta capa no sabe que significa cada estado para una
    #: pantalla, y meterle esa decision seria poner la politica de la bandeja
    #: dentro de la tabla del caso.
    excluded_states: tuple[str, ...] = ()
    #: El origen del caso. Lo usa la lista publica de casos de ejemplo para traer
    #: **solo** los del generador: el recorte tiene que pasar por la consulta, porque
    #: filtrado despues de traer la pagina se contaria el limite con filas que la
    #: lista no muestra, y una fila de visitante habria salido ya de la base.
    origin: str | None = None


@dataclass(frozen=True)
class ListingCursor:
    """Donde se quedo la pagina anterior. La terna entera, no solo la fecha."""

    priority_rank: int
    updated_at: datetime
    case_id: CaseId


async def list_cases(
    tenant_id: TenantId,
    *,
    filters: ListingFilters,
    limit: int,
    cursor: ListingCursor | None = None,
    en: session.TenantSession | None = None,
) -> tuple[tuple[Case, ...], tuple[int, ...]]:
    """Una pagina de casos de esa aseguradora, en el orden de la cola.

    Devuelve los casos y, junto a ellos, el rango de prioridad que el motor
    calculo para cada uno: quien arma el cursor lo necesita y recalcularlo fuera
    seria tener la regla del orden escrita en dos sitios.

    Un caso de otra aseguradora no sale aqui, y no porque se compare: la politica
    de fila filtra antes de que esta consulta mire nada.
    """
    async with _en(tenant_id, en) as sesion:
        filas = await session.fetch_all(
            sesion,
            LISTAR_CASOS,
            excluded_states=list(filters.excluded_states),
            record_type=filters.record_type,
            state=filters.state,
            channel=filters.channel,
            language=filters.language,
            priority=filters.priority,
            origin=filters.origin,
            cursor_rank=cursor.priority_rank if cursor is not None else 0,
            cursor_updated_at=cursor.updated_at if cursor is not None else None,
            cursor_case_id=cursor.case_id if cursor is not None else None,
            limit=limit,
        )
    return (
        tuple(_a_caso(fila) for fila in filas),
        tuple(int(fila["priority_rank"]) for fila in filas),
    )


async def load_fields_of(
    tenant_id: TenantId,
    case_ids: Sequence[CaseId],
    *,
    en: session.TenantSession | None = None,
) -> dict[CaseId, tuple[CaseField, ...]]:
    """Los campos de varios casos, agrupados por caso, en una sola consulta."""
    if not case_ids:
        return {}
    async with _en(tenant_id, en) as sesion:
        filas = await session.fetch_all(sesion, LEER_CAMPOS_DE_VARIOS, case_ids=list(case_ids))

    por_caso: dict[CaseId, list[CaseField]] = {case_id: [] for case_id in case_ids}
    for fila in filas:
        por_caso.setdefault(fila["case_id"], []).append(
            CaseField(
                case_id=fila["case_id"],
                field_key=fila["field_key"],
                value=_sellado(fila, "value"),
                status=fila["status"],
                evidence_turn_id=fila["evidence_turn_id"],
                evidence_change_id=fila["evidence_change_id"],
                confirmed_aloud_at=fila["confirmed_aloud_at"],
                updated_at=fila["updated_at"],
            )
        )
    return {case_id: tuple(campos) for case_id, campos in por_caso.items()}


async def insert_party(
    tenant_id: TenantId,
    parte: CaseParty,
    *,
    key_id: KeyId | None,
    en: session.TenantSession | None = None,
) -> None:
    async with _en(tenant_id, en) as sesion:
        await session.execute_sql(
            sesion,
            INSERTAR_PARTE,
            party_id=parte.party_id,
            tenant_id=tenant_id,
            case_id=parte.case_id,
            role=parte.role.value,
            name=bytes(parte.name) if parte.name is not None else None,
            contact=bytes(parte.contact) if parte.contact is not None else None,
            plate=bytes(parte.plate) if parte.plate is not None else None,
            sealed_key_id=key_id,
            injury_status=parte.injury_status,
            vehicle_description=parte.vehicle_description,
            plate_status=parte.plate_status.value,
            plate_evidence_turn_id=parte.plate_evidence_turn_id,
            statement_version=parte.statement_version,
            relation=parte.relation,
        )


async def load_parties(
    tenant_id: TenantId, case_id: CaseId, *, en: session.TenantSession | None = None
) -> tuple[CaseParty, ...]:
    async with _en(tenant_id, en) as sesion:
        filas = await session.fetch_all(sesion, LEER_PARTES, case_id=case_id)
    return tuple(
        CaseParty(
            party_id=fila["party_id"],
            case_id=fila["case_id"],
            role=fila["role"],
            name=_sellado(fila, "name"),
            contact=_sellado(fila, "contact"),
            plate=_sellado(fila, "plate"),
            injury_status=fila["injury_status"],
            vehicle_description=fila["vehicle_description"],
            plate_status=fila["plate_status"],
            plate_evidence_turn_id=fila["plate_evidence_turn_id"],
            statement_version=fila["statement_version"],
            relation=fila["relation"],
        )
        for fila in filas
    )


async def insert_turn(
    tenant_id: TenantId, turno: TranscriptTurn, *, en: session.TenantSession | None = None
) -> None:
    async with _en(tenant_id, en) as sesion:
        await session.execute_sql(
            sesion,
            INSERTAR_TURNO,
            turn_id=turno.turn_id,
            tenant_id=tenant_id,
            case_id=turno.case_id,
            speaker=turno.speaker.value,
            channel=turno.channel.value,
            language=turno.language,
            text_redacted=turno.text_redacted,
            started_at=turno.started_at,
            ended_at=turno.ended_at,
            interrupted=turno.interrupted,
        )


def _a_turno(fila: Any) -> TranscriptTurn:
    return TranscriptTurn(
        turn_id=fila["turn_id"],
        case_id=fila["case_id"],
        speaker=fila["speaker"],
        channel=fila["channel"],
        language=fila["language"],
        text_redacted=fila["text_redacted"],
        started_at=fila["started_at"],
        ended_at=fila["ended_at"],
        interrupted=fila["interrupted"],
    )


async def load_turns(
    tenant_id: TenantId, case_id: CaseId, *, en: session.TenantSession | None = None
) -> tuple[TranscriptTurn, ...]:
    async with _en(tenant_id, en) as sesion:
        filas = await session.fetch_all(sesion, LEER_TURNOS, case_id=case_id)
    return tuple(_a_turno(fila) for fila in filas)


async def load_conversation_turns(
    tenant_id: TenantId,
    case_id: CaseId,
    *,
    max_hops: int,
    en: session.TenantSession | None = None,
) -> tuple[TranscriptTurn, ...]:
    """Los turnos de este caso y de los casos de los que viene, del mas antiguo al propio.

    Cada turno lleva su `case_id`: quien necesite agrupar por caso --las clausulas de una
    respuesta de cobertura se buscan por el caso que la dijo-- lo hace con el. Un caso que no
    existe en esta aseguradora devuelve la tupla vacia, igual que `load_turns`.
    """
    async with _en(tenant_id, en) as sesion:
        filas = await session.fetch_all(
            sesion, LEER_TURNOS_DE_LA_CONVERSACION, case_id=case_id, max_hops=max_hops
        )
    return tuple(_a_turno(fila) for fila in filas)


async def insert_change(
    tenant_id: TenantId,
    cambio: CaseChange,
    *,
    key_id: KeyId | None,
    en: session.TenantSession | None = None,
) -> None:
    async with _en(tenant_id, en) as sesion:
        await session.execute_sql(
            sesion,
            INSERTAR_CAMBIO,
            change_id=cambio.change_id,
            tenant_id=tenant_id,
            case_id=cambio.case_id,
            change_kind=cambio.change_kind.value,
            field_key=cambio.field_key,
            previous_value=(
                bytes(cambio.previous_value) if cambio.previous_value is not None else None
            ),
            new_value=bytes(cambio.new_value) if cambio.new_value is not None else None,
            sealed_key_id=key_id,
            actor_type=cambio.actor.actor_type.value,
            actor_id=cambio.actor.actor_id,
            channel=cambio.channel.value if cambio.channel else None,
            detail=cambio.detail,
            changed_at=cambio.changed_at,
        )


async def count_changes_by(  # noqa: PLR0913 -- el caso, la clase, el actor y la sesion
    tenant_id: TenantId,
    case_id: CaseId,
    *,
    change_kind: ChangeKind,
    actor_type: ActorType,
    actor_id: str,
    en: session.TenantSession | None = None,
) -> int:
    async with _en(tenant_id, en) as sesion:
        fila = await session.fetch_one(
            sesion,
            CONTAR_CAMBIOS_DE,
            tenant_id=tenant_id,
            case_id=case_id,
            change_kind=change_kind.value,
            actor_type=actor_type.value,
            actor_id=actor_id,
        )
    return int(fila["total"]) if fila is not None else 0


async def load_changes(
    tenant_id: TenantId, case_id: CaseId, *, en: session.TenantSession | None = None
) -> tuple[CaseChange, ...]:
    async with _en(tenant_id, en) as sesion:
        filas = await session.fetch_all(sesion, LEER_CAMBIOS, case_id=case_id)
    return tuple(
        CaseChange(
            change_id=fila["change_id"],
            case_id=fila["case_id"],
            change_kind=fila["change_kind"],
            field_key=fila["field_key"],
            previous_value=_sellado(fila, "previous_value"),
            new_value=_sellado(fila, "new_value"),
            actor=Actor(actor_type=fila["actor_type"], actor_id=fila["actor_id"]),
            channel=fila["channel"],
            detail=fila["detail"],
            changed_at=fila["changed_at"],
        )
        for fila in filas
    )
