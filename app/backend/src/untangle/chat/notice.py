"""El aviso de lo que decidio el ajustador, en la conversacion donde se reporto.

**Es el unico camino por el que una salida de este sistema puede afirmar un
resultado** (BR5.2), y lo que lo autoriza es la firma de una persona. Lo sostienen
dos cosas, y ninguna es una exencion de la guardia.

- **Sin decision registrada no se compone nada.** El texto no llega a la guardia:
  no llega a existir. Comprobarlo despues dejaria el texto escrito en memoria a la
  espera de que alguien lo mirara.
- **El comentario del ajustador pasa por la guardia por su cuenta**, antes de
  entrar en la plantilla. Esto empezo siendo una exencion del catalogo --el
  mecanismo existe y estaba vacio esperando un consumidor-- y se midio antes de
  usarlo: la plantilla no dispara ningun patron por si sola, asi que la exencion
  no hacia falta; y eximir la clave eximia **el texto entero, comentario
  incluido**, de modo que un "su poliza cubre el choque" escrito por el ajustador
  pasaba sin intervencion. La firma autoriza su decision, no cualquier frase que
  escriba.

**El comentario del ajustador se redacta en la traza y en el log**, aunque llegue
entero a la conversacion. Va dirigido al asegurado y puede nombrar a terceros; quien
lee una traza no necesita eso.

**Un caso derivado sin decidir lo dice sin prometer una fecha** (BR5.3). Prometer un
plazo que nadie puede cumplir es la forma barata de que la demostracion parezca mejor
de lo que es.
"""

from __future__ import annotations

from dataclasses import dataclass

from untangle import observability
from untangle.base import Locale
from untangle.case_record.models import CaseState, Resolution
from untangle.compliance.controls import api as controls
from untangle.compliance.redaction import api as redaccion
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey
from untangle.tenancy.models import TenantId

#: Las claves de cada desenlace. Cada una se nombra literal en su rama, que es lo
#: que el chequeo de claves sin consumidor necesita (BR3.4 del catalogo).
APPROVED = CopyKey("chat.decision.approved")
REJECTED = CopyKey("chat.decision.rejected")
SENT_TO_INSURER = CopyKey("chat.decision.sent_to_insurer")
PENDING = CopyKey("chat.decision.pending")


class MissingDecisionError(RuntimeError):
    """Se pidio el aviso de una decision que no esta registrada (BR5.2).

    Es un error del codigo que llama, no del asegurado. Falla en el acto en vez de
    componer un texto que afirme un resultado sin nadie que lo firme.
    """


@dataclass(frozen=True)
class Notice:
    """El aviso ya compuesto y pasado por la guardia."""

    copy_key: CopyKey
    text: str
    #: El identificador de la decision humana que lo autoriza. Viaja al evento de
    #: la traza: es lo que deja auditar despues **por que** se dejo salir.
    decision_ref: str


def _frase_de(
    resolution: Resolution, *, language: Locale, case_number: str, comment: str
) -> tuple[CopyKey, str]:
    """La clave y el texto de cada desenlace, **cada rama con su literal dentro**.

    No se devuelve la clave para resolverla despues: el chequeo BR3.4 del catalogo
    exige que la clave sea un literal en su consumidor, porque de eso depende el
    chequeo de claves sin consumidor. Es la misma razon por la que `turn.py` de
    U12 repite las suyas rama por rama.
    """
    if resolution is Resolution.APPROVED:
        return APPROVED, copy_api.t(
            APPROVED, locale=language, case_number=case_number, comment=comment
        )
    if resolution is Resolution.REJECTED:
        return REJECTED, copy_api.t(
            REJECTED, locale=language, case_number=case_number, comment=comment
        )
    if resolution is Resolution.SENT_TO_INSURER:
        return SENT_TO_INSURER, copy_api.t(
            SENT_TO_INSURER, locale=language, case_number=case_number, comment=comment
        )
    msg = (
        f"la resolucion '{resolution.value}' no la firmo ninguna persona; "
        f"'{Resolution.REGISTERED.value}' es lo que el sistema pone al abrir "
        f"el caso, y avisar de ella seria avisar de nada (BR5.2)"
    )
    raise MissingDecisionError(msg)


@dataclass(frozen=True)
class Decision:
    """Lo que una persona decidio sobre un caso, tal como U4 lo guarda.

    Es lo que U14 entrega cuando el ajustador firma, y por eso viaja junto y no
    en cinco argumentos sueltos: quien lo compone ya lo tiene entero, y
    desarmarlo solo daria cinco sitios donde equivocarse al rearmarlo.

    `resolution` y `ref` llegan opcionales **a proposito**: un caso sin decidir
    existe, y el tipo lo dice en vez de esconderlo tras un valor de relleno.
    """

    case_id: str
    case_number: str
    resolution: Resolution | None
    comment: str
    #: La entrada del historial que la escribio. Es el identificador que autoriza
    #: al aviso a afirmar un resultado (BR5.2).
    ref: str | None


async def for_decision(decision: Decision, *, tenant_id: TenantId, language: Locale) -> Notice:
    """El aviso de una decision **registrada**, pasado por la guardia (BR5.1, BR5.2).

    Sin resolucion o sin su referencia no hay aviso, y no se compone un texto
    "por si acaso": levanta.
    """
    if decision.resolution is None or decision.ref is None:
        msg = (
            f"el caso '{decision.case_id}' no tiene decision registrada; el aviso "
            f"afirma un resultado, y lo que lo autoriza es la firma de una persona "
            f"(BR5.2)"
        )
        raise MissingDecisionError(msg)

    # El comentario primero y **solo**: es texto libre de una persona, y es la
    # unica parte del aviso que puede decir algo que la guardia tenga que parar.
    # Sin `source_key`: no se exime de nada.
    comentario = await controls.guard_output(
        decision.comment,
        tenant_id=tenant_id,
        language=language,
        case_id=decision.case_id,
        case_number=decision.case_number,
    )
    clave, texto = _frase_de(
        decision.resolution,
        language=language,
        case_number=decision.case_number,
        comment=comentario.text_out or "",
    )

    observability.emit(
        "chat.decision_notified",
        tenant_id=tenant_id,
        case_id=decision.case_id,
        resolution=decision.resolution.value,
        decision_ref=decision.ref,
        # Redactado: el comentario va dirigido al asegurado y puede nombrar a
        # terceros; quien lee una traza no necesita eso.
        comment=str(redaccion.redact(decision.comment, language=language)),
    )
    return Notice(copy_key=clave, text=texto, decision_ref=decision.ref)


def pending(*, state: CaseState, language: Locale) -> Notice | None:
    """Lo que se dice de un caso derivado y aun sin decidir (BR5.3).

    Dice que alguien lo esta revisando y **no promete cuando**. Devuelve `None`
    para cualquier otro estado: un caso que sigue en captura no tiene nada que
    avisar, y decir algo seria ruido.
    """
    if state is not CaseState.DERIVED:
        return None
    return Notice(
        copy_key=PENDING,
        text=copy_api.t(PENDING, locale=language),
        # No hay decision que referenciar, y ese es justo el caso: este aviso no
        # afirma ningun resultado, asi que no necesita autorizacion de nadie.
        decision_ref="",
    )


__all__ = [
    "APPROVED",
    "PENDING",
    "REJECTED",
    "SENT_TO_INSURER",
    "Decision",
    "MissingDecisionError",
    "Notice",
    "for_decision",
    "pending",
]
