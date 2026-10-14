"""Donde va el caso de la conversacion, para verlo mientras avanza (decision de Miguel, 2026-10-06).

**El inicio prometia «al terminar recibes un enlace a tu caso» y el chat nunca lo
daba.** La llamada lo emite al colgar (`voice_routes._desenlace`); el chat llevaba
el campo `case_link` de su evento de derivacion siempre vacio. Y quien recorre la
demostracion con prisa no quiere esperar al final: quiere ver que el caso existe,
cuanto lleva y abrirlo. Miguel lo pidio asi: «que la persona vea su flujo sin que
se haya terminado, sino a medida que va avanzando».

**Lo que se devuelve es poco y publico para quien lo pregunta:** el numero legible,
el estado, cuantos datos lleva de cuantos, y el enlace firmado al caso. Todo sale
del caso de la conversacion **de este navegador**, resuelta por la galleta: un
navegador sin conversacion viva o sin caso recibe `None`, igual que el resumen de
traza, y no hay forma de preguntar por otro caso.

**El enlace es el mismo que da la llamada** (`tenancy.issue_case_link`, una hora
de vida, el token en el fragmento de la direccion). Se emite uno por consulta: la
pantalla pregunta pocas veces --al abrir y cuando el caso cambia-- y las filas se
van con el reinicio nocturno.
"""

from __future__ import annotations

from datetime import datetime

from untangle.base import Frozen
from untangle.case_record import api as casos
from untangle.case_record import fields as campos
from untangle.case_record import labels as etiquetas
from untangle.case_record.api import CaseView
from untangle.chat import session as chat
from untangle.orchestration.nodes.intake import blocks
from untangle.tenancy import api as tenancy


class FieldProgress(Frozen):
    """Un dato del caso y si ya quedo anotado.

    `optional` dice que el dato no cuenta para "5 de 5": la lista traia siete filas
    bajo un contador de cinco y no se entendia por que (2026-10-10).

    `value` es lo anotado, en claro, y **solo lo llena el pensamiento de la agente**,
    que es del propio caso de este navegador (decision de Miguel del 2026-10-11):
    antes decia "Anotado" sin mostrar que. El estado del caso, que se pregunta a
    cada rato, no abre ningun valor.
    """

    field_key: str
    label_key: str
    done: bool
    optional: bool = False
    value: str | None = None


class ChatCaseStatus(Frozen):
    """Lo que la pantalla muestra bajo el titulo mientras el caso avanza."""

    case_number: str
    state: str
    complete: int
    total: int
    #: `/c#<token>`: el token va en el fragmento, que el navegador nunca manda al
    #: servidor (C-07). `None` cuando el despliegue no tiene clave de enlaces.
    case_link: str | None
    #: El bloque que la agente esta preguntando, leido del caso como lo lee ella
    #: (`blocks.next_block`). La pantalla lo usa para ofrecer la poliza de ejemplo
    #: justo cuando se pide (P3). `None` cuando ya no hay bloque que preguntar.
    pending_block: str | None = None
    #: La poliza que la persona confirmo como suya, si ya la confirmo (P3).
    policy_ref: str | None = None
    #: `claim`, `coverage_inquiry` o `quote_request`. La pantalla no muestra "2 de 2
    #: datos" en una consulta, donde nadie esta dando datos (2026-10-08).
    record_type: str | None = None
    #: Los datos del caso en el orden en que se piden, con si ya quedaron anotados.
    fields: tuple[FieldProgress, ...] = ()


def view_of(vista: CaseView, *, case_link: str | None) -> ChatCaseStatus:
    """La forma que sale por el cable, a partir del caso ya leido. Pura."""
    pendiente = blocks.next_block(vista.record_type, vista.completeness, vista.state)
    return ChatCaseStatus(
        case_number=str(vista.case_number),
        state=vista.state.value,
        record_type=vista.record_type.value,
        complete=vista.completeness.complete,
        total=vista.completeness.total,
        case_link=case_link,
        pending_block=None
        if pendiente in (blocks.Block.FINAL_CONFIRMATION, blocks.Block.DONE)
        else pendiente.value,
        policy_ref=vista.policy_ref,
        fields=tuple(
            FieldProgress(
                field_key=definicion.key,
                label_key=etiquetas.FIELD_KEYS.get(definicion.key, etiquetas.FIELD_UNAVAILABLE),
                done=vista.completeness.per_field.get(definicion.key, False),
                optional=definicion.key in vista.completeness.optional,
            )
            for definicion in campos.definitions_for(vista.record_type)
        ),
    )


async def for_session(
    session_: chat.ChatSession, *, signing_key: str | None, now: datetime
) -> ChatCaseStatus | None:
    """El estado del caso de esta conversacion, con su enlace, o `None` si no hay caso.

    Sin clave de firma no se emite enlace y el resto se devuelve igual: ver que el
    caso avanza no depende de poder abrirlo.
    """
    if session_.case_id is None:
        return None
    vista = await casos.get_case(session_.tenant_id, session_.case_id)
    if vista is None:
        return None
    enlace = None
    if signing_key is not None:
        emitido = await tenancy.issue_case_link(
            tenant_id=session_.tenant_id,
            case_id=session_.case_id,
            signing_key=signing_key,
            now=now,
        )
        enlace = f"/c#{emitido.token}"
    return view_of(vista, case_link=enlace)


__all__ = ["ChatCaseStatus", "for_session", "view_of"]
