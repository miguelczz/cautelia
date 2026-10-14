"""El historial del caso: de solo anexar, y por tres caminos a la vez.

**No existe ninguna ruta del codigo que edite o borre una entrada** (SEC-U4.11).
Se sostiene por tres sitios independientes, y esa redundancia es deliberada
porque cada uno tapa un agujero distinto:

| Donde | Que impide |
| --- | --- |
| Esta superficie | Que exista una funcion a la que llamar para editar |
| El disparador de la base | Que un `UPDATE` escrito a mano funcione |
| Los tipos congelados | Que una entrada ya construida se modifique en memoria |

Con uno solo bastaria para el descuido; hacen falta los tres para el atajo.

**El borrado si se permite**, y la asimetria es deliberada: el reinicio nocturno
tiene que poder borrar un caso de visitante entero. Lo que la regla prohibe es
que una entrada **cambie**, no que la retencion acotada se cumpla.

**Las cuatro clases de entrada** son un campo que se fijo, una transicion que se
aplico, una que se rechazo y un cierre que se rechazo. Las dos ultimas son la
razon de ser del historial: sin ellas, un intento rechazado y un intento que
nunca ocurrio serian indistinguibles el dia que alguien pregunta que paso.
"""

from __future__ import annotations

import secrets
from datetime import datetime

from untangle.case_record import repository
from untangle.case_record.crypto import Cipher
from untangle.case_record.models import (
    Actor,
    ActorType,
    CaseChange,
    CaseField,
    CaseId,
    CaseState,
    ChangeKind,
    Channel,
    Sealed,
)
from untangle.tenancy import session
from untangle.tenancy.models import TenantId


def new_change_id() -> str:
    """Un identificador nuevo. Al azar y no correlativo: uno correlativo deja
    ver cuantos cambios lleva el caso a quien solo vio uno."""
    return f"chg-{secrets.token_hex(12)}"


def field_set(
    campo: CaseField,
    *,
    previous: Sealed | None,
    actor: Actor,
    channel: Channel | None,
    change_id: str | None = None,
) -> CaseChange:
    """La entrada de un campo que se fijo o se corrigio.

    Se deriva **del campo que se acaba de escribir**, y no de una lista de
    argumentos paralela: asi la clave, el valor nuevo y la hora de la entrada no
    pueden decir una cosa distinta de la fila que describen.

    Los dos valores van **sellados**: son copias del campo, y dejarlos en claro
    desharia el cifrado para todo lo que alguna vez se corrigio, que es el dato
    que mas veces se toco.
    """
    return CaseChange(
        # Quien corrige desde la bandeja acuna el identificador **antes**, porque
        # el campo que escribe lleva esa entrada como su unica evidencia y el tipo
        # lo exige: un campo confirmado sin evidencia no valida. Sin este
        # parametro, la entrada nacia aqui dentro y el campo no tenia a que
        # apuntar --lo encontro U14 al escribir su primera correccion--.
        change_id=change_id if change_id is not None else new_change_id(),
        case_id=campo.case_id,
        change_kind=ChangeKind.FIELD_SET,
        field_key=campo.field_key,
        previous_value=previous,
        new_value=campo.value,
        actor=actor,
        channel=channel,
        changed_at=campo.updated_at,
    )


def field_version_alternate(
    campo: CaseField, *, actor: Actor, channel: Channel | None
) -> CaseChange:
    """U11, BR5.5, FD-U11-7: una segunda version, anotada sin reemplazar la primera.

    Se deriva igual que `field_set` del campo que la describe, con dos
    diferencias que son toda la razon de que exista: su clase dice que el valor
    **no** se acepto, y no lleva `previous_value` --no hubo un valor anterior
    que cambiara, porque el del caso sigue siendo el primero confirmado.

    El campo del que se deriva **no se guarda**: existe solo para sellar el
    valor y sellar la hora en el mismo sitio que cualquier otra entrada.
    """
    return CaseChange(
        change_id=new_change_id(),
        case_id=campo.case_id,
        change_kind=ChangeKind.FIELD_VERSION_ALTERNATE,
        field_key=campo.field_key,
        previous_value=None,
        new_value=campo.value,
        actor=actor,
        channel=channel,
        changed_at=campo.updated_at,
    )


async def append(
    tenant_id: TenantId,
    cambio: CaseChange,
    *,
    cipher: Cipher | None = None,
    en: session.TenantSession | None = None,
) -> None:
    """Anexa una entrada. Es lo unico que esta superficie sabe hacer.

    No hay `update` ni `delete` aqui, y no es que esten ocultos: no existen. Una
    funcion privada que editara seria una funcion que alguien puede exportar
    manana con una linea.
    """
    key_id = cipher.id if cipher is not None else None
    lleva_valor = cambio.previous_value is not None or cambio.new_value is not None
    await repository.insert_change(tenant_id, cambio, key_id=key_id if lleva_valor else None, en=en)


async def of_case(tenant_id: TenantId, case_id: CaseId) -> tuple[CaseChange, ...]:
    """El historial completo, del mas viejo al mas nuevo."""
    return await repository.load_changes(tenant_id, case_id)


async def count_by_actor(  # noqa: PLR0913 -- el caso, la clase, el actor y la sesion
    tenant_id: TenantId,
    case_id: CaseId,
    *,
    kind: ChangeKind,
    actor_type: ActorType,
    actor_id: str,
    en: session.TenantSession | None = None,
) -> int:
    """Cuantas entradas de esa clase dejo ese actor en el caso.

    Una cuenta en la base y no `of_case` contada en memoria: quien pregunta (el tope de lo que
    un visitante puede anotar) lo hace en cada guardado y en cada lectura del caso, y no tiene
    por que leer ni descifrar el historial entero para saber un numero. Con `en` cuenta dentro
    de la transaccion de quien va a escribir, que es la unica forma de que la cuenta y la
    escritura vean lo mismo.
    """
    return await repository.count_changes_by(
        tenant_id,
        case_id,
        change_kind=kind,
        actor_type=actor_type,
        actor_id=actor_id,
        en=en,
    )


async def derived_at(tenant_id: TenantId, case_id: CaseId) -> datetime | None:
    """Cuando el caso entro en derivado **por ultima vez**, o nada.

    Sale del propio historial y no de quien llama. Lo pedia la revision asesora
    de esta etapa, y tiene razon: la ventana para retomar una llamada cortada es
    una de las cuatro condiciones de la unica vuelta atras del modelo, y una
    condicion cuyo insumo aporta entero el consumidor no es una condicion. Un
    consumidor que pasara la hora actual la abriria siempre.

    "Por ultima vez" y no la primera: un caso puede ir y volver de derivado, y
    la ventana cuenta desde la ultima salida.
    """
    entradas = await of_case(tenant_id, case_id)
    marcas = [
        entrada.changed_at
        for entrada in entradas
        if entrada.change_kind is ChangeKind.TRANSITION_APPLIED
        and entrada.detail is not None
        and entrada.detail.endswith(f"-> {CaseState.DERIVED.value}")
    ]
    return marcas[-1] if marcas else None
