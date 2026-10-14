"""Un caso de golden set no puede nombrar un campo que no existe (U13).

Los guiones se indexan por campo, y el asegurado simulado contesta la frase de
desconocimiento cuando le piden uno que no esta -- lo cual es correcto para un
campo que el guion no cubre, y **silencioso** para uno que no existe en ninguna
parte. Los cuatro casos nuevos de esta unidad nacieron con tres campos inventados
(`incident_location`, `driver`, `third_parties`) y ninguna compuerta lo dijo: el
caso cargaba, el conductor preguntaba, y el recorrido moria sin explicacion.

Se comprueba contra el **esquema de U4**, no contra una lista escrita aqui: una
lista propia deja de coincidir el dia que el esquema cambie, y esta prueba seguiria
en verde midiendo campos que ya no existen.
"""

from __future__ import annotations

from untangle.case_record import fields
from untangle.case_record.models import CaseSchemaError, RecordType
from untangle.evals import loading


def test_ningun_guion_nombra_un_campo_que_el_esquema_no_declara() -> None:
    reales: set[str] = set()
    for tipo in RecordType:
        try:
            reales.update(definicion.key for definicion in fields.definitions_for(tipo))
        except CaseSchemaError:
            # Un tipo de registro que no declare campos no aporta claves y no
            # invalida las de los demas. Hoy los tres tipos los declaran --
            # `quote_request` desde U19--, asi que esto es la red del dia que un
            # tipo nuevo nazca vacio (BR1.6 de U4).
            continue

    # Los bloques tambien valen como clave: una sonda puede contestar el bloque
    # entero en un turno, que es como U11 escribio sus casos.
    from untangle.orchestration.nodes.intake.blocks import Block

    validas = reales | {bloque.value for bloque in Block}

    inventados = {
        caso.case_key: sorted({a.field_key for a in caso.script} - validas)
        for caso in loading.load_cases()
        if {a.field_key for a in caso.script} - validas
    }

    assert inventados == {}, f"casos con campos que no existen: {inventados}"


def test_la_lista_de_campos_no_esta_vacia() -> None:
    """Sin esto, lo de arriba pasaria con un esquema sin campos."""
    assert len(fields.definitions_for(RecordType.CLAIM)) > 0
