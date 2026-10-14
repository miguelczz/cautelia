"""Los eventos de U12 en el cable del chat (C-04).

Una sola funcion con una sola responsabilidad: traducir la union tipada que
devuelve `handle_turn` (C-14) a la union serializada que viaja por SSE (C-04).
Aqui no se decide nada de la conversacion; lo que se decide es **que se pone en
el cable y que no**.

**Una diferencia entre las dos uniones, y es deliberada.**

`Waiting`, `Handoff` y `TurnError` viajan con su clave **y con su texto ya resuelto
en el idioma del turno** (decision de Miguel del 2026-10-12). La clave sigue siendo
lo que el navegador resuelve de su propio catalogo cuando la conoce, para que una
frase no acabe diciendose de dos maneras; el texto es el respaldo para cuando no la
conoce. Antes viajaba solo la clave y, cuando el servidor estrenaba una que la tabla
de la pantalla no tenia, la persona leia "tuve un problema para responder eso" justo
despues de pedir un ajustador: el caso estaba derivado y la pantalla decia que habia
fallado.

Las **citas no se leen del evento**. C-14 las declara `tuple[object, ...]` y lo
que el grafo pone ahi no tiene ni la version ni el texto que C-04 exige; los trae
`citation.details_for` del corpus y este modulo los coloca. Leerlos del evento era
lo que se hacia, y mandaba tres campos vacios en cada respuesta real.

`PartialText` llega **ya pasado por la guardia de salida**. Este modulo no la
aplica ni la comprueba: la aplica el punto unico de U12 antes de emitir. Lo que
si hace es no inventar un camino por el que un texto llegue al cable sin haber
pasado por ahi -- por eso solo traduce lo que recibe y nunca compone texto propio.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from untangle.chat.citation import CitationDetail
from untangle.orchestration.contracts import (
    FinalText,
    Handoff,
    PartialText,
    TurnError,
    TurnEvent,
    Waiting,
)

#: El nombre de cada evento en el cable, tal como C-04 lo fija. Literales y no
#: derivados del nombre de la clase: el contrato es con el navegador, y renombrar
#: una clase en Python no puede cambiar lo que viaja por la red.
PARTIAL = "turn.partial"
FINAL = "turn.final"
WAITING = "turn.waiting"
HANDOFF = "turn.handoff"
ERROR = "turn.error"


class UnknownEventError(TypeError):
    """Llego un evento de C-14 que C-04 no sabe serializar.

    Falla en el acto y nombra el tipo. La alternativa --devolver `None` y saltarse
    el evento-- dejaria un turno sin cerrar en el navegador: la persona veria la
    conversacion detenida sin ningun mensaje, que es el modo de fallo que
    REL-U13.1 existe para impedir.
    """


def _citas(citations: Sequence[CitationDetail], *, trace_ref: str) -> list[dict[str, Any]]:
    """Las citas en la forma de C-04, ya completas.

    **No se leen del evento.** C-14 las declara `tuple[object, ...]` y lo que llega
    ahi es la vista del grafo, que no tiene ni la version ni el texto: los trae
    `citation.details_for`, que los lee del corpus. Serializarlos desde el evento
    --como se hacia-- daba cadenas vacias en los tres campos que el grafo no escribe,
    y ninguna compuerta lo veia porque la prueba usaba un doble con los cinco puestos.

    `trace_ref` es del turno y no de cada cita, pero C-04 lo pide dentro de cada una:
    se copia, no se inventa uno por cita.
    """
    return [
        {
            "clause_id": cita.clause_id,
            "clause_version": cita.clause_version,
            "part": cita.part,
            "text": cita.text,
            "clause_language": cita.clause_language,
            "amount_deferred": cita.amount_deferred,
            "trace_ref": trace_ref,
            # La traduccion de referencia, si la clausula esta en otro idioma (2026-10-08).
            "translated_text": cita.translated_text,
            "translated_part": cita.translated_part,
            # De que condicion especial es la clausula, si es de una (2026-10-11). Aditivo.
            "special_condition_number": cita.special_condition_number,
        }
        for cita in citations
    ]


def to_wire(
    event: TurnEvent,
    *,
    citations: Sequence[CitationDetail] = (),
    trace_ref: str = "",
) -> dict[str, Any]:
    """Un evento de C-14 en la forma que C-04 pone en el cable.

    Cada rama nombra su literal y sus campos: una tabla indexada por tipo leeria
    igual de bien y dejaria el contrato con el navegador sin un sitio donde
    buscarlo con un grep.
    """
    if isinstance(event, PartialText):
        return {
            "kind": PARTIAL,
            "message_id": event.message_id,
            "seq": event.seq,
            "text": event.text,
        }
    if isinstance(event, FinalText):
        return {
            "kind": FINAL,
            "message_id": event.message_id,
            "text": event.text,
            "language": event.language,
            "case_id": event.case_id,
            "citations": _citas(citations, trace_ref=trace_ref),
            "suggestions": list(event.suggestions),
            "coverage_outcome": event.coverage_outcome,
            # La traza del turno, tambien sin citas: la pantalla ofrece "como lo
            # penso" bajo cualquier respuesta (2026-10-09). Aditivo.
            "trace_ref": trace_ref or None,
            # El turno dijo "dejame revisar" y el fondo va a traer la respuesta: la
            # pantalla muestra que se esta revisando hasta que llegue (2026-10-12).
            # Aditivo.
            "answer_pending": event.answer_pending,
        }
    if isinstance(event, Waiting):
        return {"kind": WAITING, "copy_key": event.copy_key, "text": event.text}
    if isinstance(event, Handoff):
        return {
            "kind": HANDOFF,
            "reason_code": event.reason_code.value,
            "copy_key": event.copy_key,
            "text": event.text,
            "case_id": event.case_id,
            "case_link": event.case_link,
        }
    if isinstance(event, TurnError):
        return {"kind": ERROR, "code": event.code, "copy_key": event.copy_key, "text": event.text}

    # Inalcanzable **por tipos**: `TurnEvent` es una union cerrada y el
    # comprobador ya prueba que las cinco ramas de arriba la cubren entera --de
    # ahi el `unreachable`, que es una buena noticia y no un aviso--. La guardia
    # se queda porque protege la frontera donde los tipos no llegan: un llamador
    # sin comprobar, o un sexto evento anadido a C-14 sin pasar por aqui. Sin
    # ella ese caso devolveria un diccionario vacio y dejaria el turno abierto en
    # el navegador, que es justo lo que REL-U13.1 prohibe.
    msg = (  # type: ignore[unreachable]
        f"el evento '{type(event).__name__}' no tiene forma en C-04: un evento sin "
        "serializar dejaria el turno sin cerrar en el navegador (REL-U13.1)"
    )
    raise UnknownEventError(msg)


#: El codigo de un fallo **del canal**, no del grafo. `TurnError` de C-14 lleva
#: los del grafo (`internal_error`, y los tipos de error de un nodo degradado);
#: este nombra el otro caso: la entrega se rompio antes o alrededor del grafo --
#: al abrir el caso, al escribir la transcripcion-- y quien escribio nunca vio
#: pasar un evento del grafo.
DELIVERY_FAILED = "delivery_failed"


def delivery_error(*, copy_key: str, text: str) -> dict[str, Any]:
    """La forma de C-04 para un fallo de la entrega, con la frase del catalogo.

    Va aparte de `to_wire` porque no traduce ningun evento de C-14: **no hay
    ninguno**. Es justamente el caso en que el grafo no llego a emitir nada, y
    construir un `TurnError` de mentira para pasarlo por `to_wire` obligaria a
    inventarle un `code` de C-14 que nadie produjo. El texto lo resuelve quien llama,
    del catalogo y en el idioma del turno.

    Existe porque un turno que se rompe **tiene** que cerrarse en el navegador
    (REL-U13.1). Sin esto el `POST` respondia 202, la excepcion moria en una tarea
    que nadie esperaba y la pantalla se quedaba en silencio: el modo de fallo que
    esta regla existe para impedir, cumpliendose por dentro de la unidad que la
    escribio.
    """
    return {"kind": ERROR, "code": DELIVERY_FAILED, "copy_key": copy_key, "text": text}


#: Los eventos que cierran un turno. El navegador deja de esperar al recibir uno
#: de los tres, y ninguna ruta puede terminar sin haber mandado alguno
#: (REL-U13.1). Vive aqui, junto a la serializacion, porque es el cable quien lo
#: necesita: dentro del proceso el flujo simplemente se acaba.
CLOSING = frozenset({FINAL, HANDOFF, ERROR})


def closes_turn(wire: dict[str, Any]) -> bool:
    """Si este evento del cable cierra el turno (REL-U13.1)."""
    return wire.get("kind") in CLOSING


__all__ = [
    "CLOSING",
    "DELIVERY_FAILED",
    "ERROR",
    "FINAL",
    "HANDOFF",
    "PARTIAL",
    "WAITING",
    "UnknownEventError",
    "closes_turn",
    "delivery_error",
    "to_wire",
]
