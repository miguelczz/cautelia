"""Que bloque toca preguntar, deducido del caso y no de un contador (BR3.2, BR3.3, FD-U11-1).

**El estado de la conversacion no existe como tal** (`functional-spec.md`,
parrafo del paso 4). El bloque que toca se lee de `Completeness.per_field` --
que campos del caso ya cuentan como completos, segun el esquema de U4 -- y de
nada mas: sin un contador propio que U11 tuviera que llevar y reconciliar al
reanudar tras `interrupt()` (ADR-003).

**Un bloque agrupa uno o mas `source_block` del esquema** (`fields.yaml`):
`when` y `where` son dos campos distintos del siniestro (`incident_datetime`,
`location`) pero una sola pregunta de conversacion, "cuando y donde" -- el
mapa de abajo es la unica traduccion entre las dos granularidades, y vive aqui
para que nadie mas tenga que repetirla.

**Una solicitud de cotizacion tiene su propio orden** (U19, `QUOTE_BLOCK_ORDER`): conductor,
vehiculo, uso e historial, cuatro bloques con confirmacion cada uno. Es un dato por tipo de
registro --`order_for`-- y no una rama en el nodo: el mismo `next_block` recorre el orden que
le toca al tipo del caso, y el grafo no gana nodos (BR1.1 de U19).

**`coverage_question` no participa de este orden.** Es el unico
`source_block` de `coverage_inquiry` que no es `identity`, y U11 no lo
gestiona: la respuesta de cobertura es de U8 (`functional-spec.md`, "Lo que
U11 no hace"). Una consulta de cobertura pasa por `IDENTITY_AND_POLICY` y de
ahi a `FINAL_CONFIRMATION` sin que este modulo le pida nada mas.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from untangle.case_record import fields
from untangle.case_record.models import CaseState, Completeness, RecordType


class Block(StrEnum):
    """Los valores de `IntakeTurnResult.next_block`: los ocho de `entities.md` y los cuatro de U19."""

    SAFETY = "safety"
    IDENTITY_AND_POLICY = "identity_and_policy"
    WHAT_HAPPENED = "what_happened"
    WHEN_AND_WHERE = "when_and_where"
    VEHICLE_AND_DRIVER = "vehicle_and_driver"
    OTHER_PARTIES = "other_parties"
    #: Los cuatro bloques de una solicitud de cotizacion (U19, BR1.2).
    QUOTE_DRIVER = "quote_driver"
    QUOTE_VEHICLE = "quote_vehicle"
    QUOTE_USAGE = "quote_usage"
    QUOTE_HISTORY = "quote_history"
    FINAL_CONFIRMATION = "final_confirmation"
    DONE = "done"


#: El orden fijo de BR3.2: seguridad, identidad y poliza, que paso, cuando y
#: donde, vehiculo y conductor, otras partes. `FINAL_CONFIRMATION` y `DONE` no
#: son bloques de campos -- son lo que viene despues de que los de campos se
#: agoten -- y por eso no estan en esta tupla.
BLOCK_ORDER: tuple[Block, ...] = (
    Block.SAFETY,
    Block.IDENTITY_AND_POLICY,
    Block.WHAT_HAPPENED,
    Block.WHEN_AND_WHERE,
    Block.VEHICLE_AND_DRIVER,
    Block.OTHER_PARTIES,
)

#: El orden de una solicitud de cotizacion (U19, BR1.2): conductor, vehiculo, uso e
#: historial. Cada uno se pregunta campo a campo y se confirma antes de pasar al siguiente.
QUOTE_BLOCK_ORDER: tuple[Block, ...] = (
    Block.QUOTE_DRIVER,
    Block.QUOTE_VEHICLE,
    Block.QUOTE_USAGE,
    Block.QUOTE_HISTORY,
)


def order_for(record_type: RecordType) -> tuple[Block, ...]:
    """El orden fijo de bloques que le toca a este tipo de registro."""
    if record_type is RecordType.QUOTE_REQUEST:
        return QUOTE_BLOCK_ORDER
    return BLOCK_ORDER


#: `source_block` del esquema -> bloque de la conversacion (BR3.2). Un
#: `source_block` que no aparece aqui (hoy solo `coverage_question`) no
#: participa de este orden.
_SOURCE_BLOCK_OF: dict[str, Block] = {
    "safety": Block.SAFETY,
    "identity": Block.IDENTITY_AND_POLICY,
    "what_happened": Block.WHAT_HAPPENED,
    "when": Block.WHEN_AND_WHERE,
    "where": Block.WHEN_AND_WHERE,
    "vehicle": Block.VEHICLE_AND_DRIVER,
    "other_parties": Block.OTHER_PARTIES,
    "quote_driver": Block.QUOTE_DRIVER,
    "quote_vehicle": Block.QUOTE_VEHICLE,
    "quote_usage": Block.QUOTE_USAGE,
    "quote_history": Block.QUOTE_HISTORY,
}


def block_of(source_block: str) -> Block | None:
    """El bloque de la conversacion al que pertenece un `source_block` del esquema.

    Se expone porque quien compone la lectura necesita saber que campos agrupa un
    bloque, y la alternativa era copiar esta correspondencia en otro archivo: dos
    copias de un mapa se separan el dia que el esquema gana un campo.
    """
    return _SOURCE_BLOCK_OF.get(source_block)


def _missing_by_block(
    record_type: RecordType, completeness: Completeness, *, include_optional: bool = False
) -> dict[Block, bool]:
    """Que bloques de campos del tipo de caso tienen algo sin completar.

    Los campos opcionales no deciden el bloque que toca (P4): se ofrecen al
    final, y solo cuentan aqui cuando quien pregunta quiere saber que queda por
    ofrecer (`include_optional`).
    """
    faltan: dict[Block, bool] = {}
    for definicion in fields.definitions_for(record_type):
        bloque = _SOURCE_BLOCK_OF.get(definicion.source_block)
        if bloque is None:
            continue
        if definicion.optional and not include_optional:
            continue
        if not completeness.per_field.get(definicion.key, False):
            faltan[bloque] = True
    return faltan


def optional_blocks_missing(
    record_type: RecordType, completeness: Completeness
) -> tuple[Block, ...]:
    """Los bloques opcionales que la persona todavia no dijo, en orden (P4).

    Son los que la agente ofrece al cerrar --"¿quiere agregar el vehiculo y las
    otras personas, o lo dejamos para el ajustador?"-- y los que pregunta, uno
    por turno, si la persona quiere agregarlos.
    """
    opcionales = {
        _SOURCE_BLOCK_OF.get(d.source_block)
        for d in fields.definitions_for(record_type)
        if d.optional and not completeness.per_field.get(d.key, False)
    }
    return tuple(bloque for bloque in order_for(record_type) if bloque in opcionales)


def readback_due(record_type: RecordType, block: Block, completeness: Completeness) -> bool:
    """Si a este bloque ya no le falta nada por decir y espera su lectura.

    Es la pregunta que separa preguntar de leer de vuelta, y no se podia hacer
    hasta que la completitud distinguio "nadie lo dijo" de "lo dijo y falta
    confirmarlo": con un solo booleano, un campo dicho y sin confirmar se veia
    igual que uno que nadie menciono, y la agente volvia a preguntarlo.
    """
    if block not in order_for(record_type):
        return False
    pendientes = missing_fields_in_block(record_type, block, completeness)
    return not pendientes and bool(readback_fields_in_block(record_type, block, completeness))


def readback_fields_in_block(
    record_type: RecordType, block: Block, completeness: Completeness
) -> tuple[str, ...]:
    """Los campos de ese bloque que estan dichos y esperan su lectura."""
    return tuple(
        definicion.key
        for definicion in fields.definitions_for(record_type)
        if _SOURCE_BLOCK_OF.get(definicion.source_block) is block
        and definicion.key in completeness.awaiting_readback
    )


def next_block(record_type: RecordType, completeness: Completeness, state: CaseState) -> Block:
    """BR3.2, FD-U11-1: el bloque que toca, leido del caso.

    Con el mismo `record_type`, la misma `completeness` y el mismo `state`,
    esta funcion devuelve siempre el mismo bloque -- no hay ningun contador
    interno que pudiera desincronizarse al reanudar tras `interrupt()`.

    `state` manda primero: un caso que ya salio de `CAPTURING` (a `VERIFYING`
    o mas alla) no tiene mas bloque que preguntar, aunque su completitud fuera
    parcial -- por ejemplo, un caso derivado a mitad de captura.
    """
    if state is not CaseState.CAPTURING:
        return Block.DONE
    if completeness.total == 0:
        # Un tipo sin campos declarados: no hay ningun bloque que le corresponda.
        return Block.DONE
    faltan = _missing_by_block(record_type, completeness)
    for bloque in order_for(record_type):
        if faltan.get(bloque):
            return bloque
    return Block.FINAL_CONFIRMATION


def missing_blocks(record_type: RecordType, completeness: Completeness) -> tuple[Block, ...]:
    """Los bloques de campos a los que todavia les falta algo, en el orden que toca.

    Es lo que la agente nombra cuando la persona pregunta cuanto falta
    (`social.SocialIntent.PROGRESS`): se lee del caso, con el mismo criterio que
    `next_block`, y no de ningun contador. Un bloque dicho y sin confirmar sigue
    faltando, porque hasta el si no cuenta (BR3.1).
    """
    faltan = _missing_by_block(record_type, completeness)
    return tuple(bloque for bloque in order_for(record_type) if faltan.get(bloque))


def missing_fields_in_block(
    record_type: RecordType, block: Block, completeness: Completeness
) -> tuple[str, ...]:
    """BR3.3: lo que falta del bloque que toca, y nada de lo ya dicho.

    Un campo del bloque que ya cuenta como completo -- porque llego adelantado
    en un turno anterior -- no aparece aqui, y por eso quien compone la
    pregunta no lo vuelve a pedir.

    **"Ya dicho" incluye lo que espera su lectura de confirmacion**, y eso es una
    correccion del 2026-09-29. Esta frase del docstring decia la verdad desde el
    principio; lo que no podia decirla era el dato: `per_field` es un booleano de
    "cuenta como completo", y un campo dicho pendiente de leer no cuenta. Salia
    por aqui como si nadie lo hubiera mencionado, la agente lo volvia a preguntar
    y el bloque no terminaba nunca. Con `awaiting_readback` en la completitud, la
    funcion hace por fin lo que promete.
    """
    return tuple(
        definicion.key
        for definicion in fields.definitions_for(record_type)
        if _SOURCE_BLOCK_OF.get(definicion.source_block) is block
        and not completeness.per_field.get(definicion.key, False)
        and definicion.key not in completeness.awaiting_readback
    )


class AskKind(StrEnum):
    """Que le toca a la persona en el siguiente turno, visto desde fuera del nodo."""

    #: Un dato que falta: la agente lo pregunta (a veces junto con otros) y la persona
    #: contesta ese campo.
    FIELD = "field"
    #: Nada falta pero hay datos dichos esperando su lectura: la agente lee y la persona
    #: confirma.
    CONFIRMATION = "confirmation"
    #: Nada que contestar: el caso ya no captura, o todo esta dicho y confirmado.
    DONE = "done"


@dataclass(frozen=True)
class NextAsk:
    """Lo que el nodo va a preguntar, deducido del caso y sin ejecutar el nodo."""

    kind: AskKind
    #: `FIELD`: la clave del campo. `CONFIRMATION`: el bloque con el que el nodo deja la
    #: lectura en espera (`intake_awaiting_confirmation`), que es la clave con la que un
    #: guion contesta la confirmacion. `DONE`: vacia.
    key: str
    #: El bloque que el nodo reporta en `intake_next_block` en ese turno.
    block: Block


def next_ask(record_type: RecordType, completeness: Completeness, state: CaseState) -> NextAsk:
    """Lo que el nodo `intake` va a preguntar con este caso, para quien tiene que contestarle.

    Es un **espejo de lectura**: dice lo mismo que el nodo decide, sin que el nodo la use,
    para que quien simula a la persona --el conductor de las evaluaciones-- conteste lo que
    la agente de verdad pregunta. Una prueba (`tests/unit/intake/test_next_ask.py`) corre el
    nodo con varios estados de completitud y exige que coincidan; si el nodo cambia la
    forma de preguntar, esa prueba cae y este espejo se corrige a la vista.

    **La solicitud de cotizacion no es como los demas tipos** (2026-10-08). No lee de vuelta
    cada bloque: pregunta por el primer bloque que tenga datos sin decir --aunque uno
    anterior espere su lectura--, y cuando a ninguno le falta nada lee la solicitud entera
    una sola vez y la deja en espera del **ultimo** bloque. Por eso los campos de la
    cotizacion, que exigen lectura, no cuentan hasta ese ultimo si, y preguntar "como
    siempre" (el bloque que `next_block` devuelve) contestaba una confirmacion que el nodo
    ya no pide. Los demas tipos siguen el bloque de `next_block`: el primer dato que falta
    en el, o la lectura de ese bloque cuando solo le queda confirmar.
    """
    if state is not CaseState.CAPTURING or completeness.total == 0:
        return NextAsk(AskKind.DONE, "", next_block(record_type, completeness, state))

    if record_type is RecordType.QUOTE_REQUEST:
        return _next_ask_of_quote(record_type, completeness, state)

    bloque = next_block(record_type, completeness, state)
    if bloque in (Block.FINAL_CONFIRMATION, Block.DONE):
        return NextAsk(AskKind.DONE, "", bloque)
    faltan = missing_fields_in_block(record_type, bloque, completeness)
    if faltan:
        return NextAsk(AskKind.FIELD, faltan[0], bloque)
    return NextAsk(AskKind.CONFIRMATION, bloque.value, bloque)


def _next_ask_of_quote(
    record_type: RecordType, completeness: Completeness, state: CaseState
) -> NextAsk:
    """La solicitud: el primer bloque con datos sin decir, o la lectura de toda ella."""
    orden = order_for(record_type)
    for bloque in orden:
        faltan = missing_fields_in_block(record_type, bloque, completeness)
        if faltan:
            return NextAsk(AskKind.FIELD, faltan[0], bloque)
    if any(readback_fields_in_block(record_type, bloque, completeness) for bloque in orden):
        ultimo = orden[-1]
        return NextAsk(AskKind.CONFIRMATION, ultimo.value, ultimo)
    return NextAsk(AskKind.DONE, "", next_block(record_type, completeness, state))


__all__ = [
    "BLOCK_ORDER",
    "QUOTE_BLOCK_ORDER",
    "AskKind",
    "Block",
    "NextAsk",
    "block_of",
    "missing_blocks",
    "missing_fields_in_block",
    "next_ask",
    "next_block",
    "optional_blocks_missing",
    "order_for",
    "readback_due",
    "readback_fields_in_block",
]
