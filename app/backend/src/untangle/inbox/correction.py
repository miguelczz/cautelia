"""Corregir un campo mal capturado, con rastro y sin tocar la conversacion.

**La bandeja no escribe una segunda validacion.** El formato de cada campo lo
declara U4 y lo comprueba U4; lo que esta pieza aporta es **quien** corrige y **por
donde** --una persona de la aseguradora, por la bandeja-- mas el recibo que impide
aplicarla dos veces. Escribir aqui una segunda validacion crearia dos reglas para el
mismo campo, y el dia que se separaran, la que gana seria la que corre antes.

**Un caso cerrado no admite correcciones** (BR3.4). Tampoco lo comprueba esta pieza:
lo rechaza U4, que es quien congela el caso al cerrarlo. La pantalla no ofrecera la
accion, pero lo que de verdad lo impide es que la peticion directa se rechace.

**La transcripcion no cambia** (BR3.2). Corregir arregla un error de captura; no
reescribe lo que dijo una persona. Aqui no hay ninguna llamada que la toque, y eso
es lo que lo garantiza.

**El valor no entra en el recibo.** Lo que se guarda es su huella, porque lo unico
que hace falta es poder decir si dos peticiones son la misma. Guardarlo abriria un
punto de salida mas para un dato personal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from untangle.base import Locale
from untangle.case_record import api as casos
from untangle.case_record import history as historial
from untangle.case_record.crypto import Cipher
from untangle.case_record.models import (
    Actor,
    ActorType,
    CaseField,
    CaseSchemaError,
    Channel,
    FieldStatus,
)
from untangle.inbox import events, receipts
from untangle.tenancy.models import TenantId


@dataclass(frozen=True)
class CorrectionApplied:
    """Lo que devuelve una correccion aplicada, o la que ya estaba."""

    receipt_id: str
    field_key: str
    #: Cierto cuando esta peticion no escribio nada porque la misma clave ya
    #: habia escrito antes. La ruta responde igual en los dos casos --C-05 promete
    #: que repetir devuelve la primera-- y este campo existe para el rastro.
    replayed: bool


async def apply(  # noqa: PLR0913 -- el caso, el campo, el valor y las cuatro cosas del rastro
    tenant_id: TenantId,
    *,
    case_id: str,
    field_key: str,
    value: str,
    idempotency_key: str,
    principal_id: str,
    cipher: Cipher,
    language: Locale,
    now: datetime,
) -> CorrectionApplied:
    """Corrige un campo y deja su entrada de historial, una sola vez.

    El orden importa y no es arbitrario: **primero se mira el recibo**, porque una
    repeticion no puede volver a escribir; despues se escribe el campo; y solo
    cuando el campo esta escrito se anota el recibo. Al reves --recibo primero,
    campo despues-- una caida entre los dos dejaria una clave marcada como usada
    sin que nada se hubiera corregido, y el reintento legitimo respondería que ya
    estaba hecho.
    """
    huella = receipts.digest_of(case_id, field_key, value)
    anterior = await receipts.reuse_or_none(
        tenant_id,
        operation=receipts.Operation.FIELD_CORRECTION,
        idempotency_key=idempotency_key,
        request_digest=huella,
    )
    if anterior is not None:
        return CorrectionApplied(receipt_id=anterior.receipt_id, field_key=field_key, replayed=True)

    # El identificador de la entrada se acuna **antes** del campo, porque el campo
    # la lleva como su unica evidencia y el tipo de U4 exige exactamente una. Sin
    # esto, un campo corregido desde la bandeja no valida: su evidencia no es un
    # turno --aqui no hay conversacion-- sino la entrada que lo registra.
    entrada = historial.new_change_id()
    campo = CaseField(
        case_id=case_id,
        field_key=field_key,
        value=cipher.seal(value),
        # Corregido por una persona que lo leyo: queda confirmado, no solo dicho.
        status=FieldStatus.CONFIRMED,
        evidence_change_id=entrada,
        updated_at=now,
    )
    # U4 valida el formato, rechaza el caso cerrado y escribe campo e historial en
    # una sola transaccion. Lo que sube de aqui es el actor y el canal.
    await casos.set_field(
        tenant_id,
        campo,
        cipher=cipher,
        actor=Actor(actor_type=ActorType.STAFF, actor_id=principal_id),
        channel=Channel.CHAT,
        change_id=entrada,
    )

    recibo = await receipts.record(
        tenant_id,
        operation=receipts.Operation.FIELD_CORRECTION,
        idempotency_key=idempotency_key,
        case_id=case_id,
        request_digest=huella,
        result_ref=field_key,
        now=now,
    )

    # El aviso sale despues de que el cambio este escrito: avisar antes contaria
    # un cambio que todavia puede no ocurrir.
    await events.append(
        tenant_id,
        case_id=case_id,
        kind=events.EventKind.CASE_UPDATED,
        summary=f"campo corregido: {field_key}",
        # El resumen que se guarda lo escribe esta unidad y no una persona: la
        # clave del campo es un token del esquema, no texto de nadie. Se redacta
        # igual, porque un punto de salida que decide por su cuenta cuando saltarse
        # la redaccion es uno que un dia se la salta con texto que si lo era.
        language=language,
        now=now,
    )
    return CorrectionApplied(receipt_id=recibo.receipt_id, field_key=field_key, replayed=False)


#: Lo que U4 levanta cuando el valor no cumple el formato del campo. Se reexporta
#: para que la ruta lo atrape sin importar el modulo de U4: el mensaje que ve una
#: persona sale del catalogo por idioma, no de esta excepcion.
InvalidFieldError = CaseSchemaError
