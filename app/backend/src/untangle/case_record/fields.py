"""Los campos del caso: que los respalda, y cuantos estan.

Dos calculos, y los dos salen del esquema versionado en vez de una lista escrita
aqui. Anadir un campo es anadir una entrada al archivo (BR1.3).

**Un campo lleva su evidencia, y son de dos clases** (BR2.4): el turno en que la
persona lo dijo, o la entrada del historial si lo escribio un ajustador desde la
bandeja. Exactamente una, y ninguna si el campo no se ha dicho. Sin esto, "la
persona dijo que no hubo lesionados" y "nadie pregunto" serian el mismo dato.

**La completitud se cuenta sobre los campos del tipo del caso**, nunca sobre una
lista fija (BR2.7): un siniestro con cinco de sus siete da 5/7, y una consulta
de cobertura cuenta sobre sus dos. Un denominador fijo publicaria una cifra que
no significa lo mismo en los dos casos.

**Y un campo cuenta como completo al alcanzar el estado que su propio campo
exige** (BR2.2, BR2.6, decision FD-U4-2 de Miguel). Tres campos del siniestro
--lugar, vehiculo y conductor, y lesiones-- solo cuentan **confirmados**, porque
equivocarse en ellos cuesta caro y la lectura en voz alta es lo que los
confirma. Los demas cuentan dichos. Cual es cual lo dice el archivo, no este
modulo.
"""

from __future__ import annotations

from untangle.case_record import schema_loading
from untangle.case_record.models import (
    CaseField,
    CaseSchemaError,
    Completeness,
    FieldDefinition,
    FieldStatus,
    RecordType,
)


def definitions_for(record_type: RecordType) -> tuple[FieldDefinition, ...]:
    """Los campos que declara ese tipo de registro.

    Falla si el tipo no declara ninguno. Un caso con completitud 0/0 se podria
    cerrar sin haber capturado nada (BR1.6).

    **Hoy ningun tipo esta vacio**: `quote_request` lo estuvo a proposito hasta que
    U19 aporto sus diecisiete campos. La guarda se queda igual --protege la regla y
    no a un tipo concreto-- y sus dos pruebas vacian el tipo en el esquema para
    ejercerla, en vez de apoyarse en que alguno siga vacio.
    """
    declarados = schema_loading.fields_by_record_type().get(record_type, ())
    if not declarados:
        msg = (
            f"el tipo de registro '{record_type}' no declara ningun campo, asi "
            f"que no se puede crear un caso suyo: su completitud seria 0/0 y "
            f"cerraria sin haber capturado nada (BR1.6)"
        )
        raise CaseSchemaError(msg)
    return declarados


def definition_of(record_type: RecordType, field_key: str) -> FieldDefinition:
    """La definicion de un campo, o el fallo que nombra cual y de que tipo."""
    for definicion in definitions_for(record_type):
        if definicion.key == field_key:
            return definicion
    declarados = [d.key for d in definitions_for(record_type)]
    msg = (
        f"el esquema no declara el campo '{field_key}' para un caso de tipo "
        f"'{record_type}'; declara {declarados} (BR1.3)"
    )
    raise CaseSchemaError(msg)


def counts_as_complete(definicion: FieldDefinition, status: FieldStatus) -> bool:
    """Si ese campo, en ese estado, cuenta para la completitud.

    El umbral lo pone el campo: `requires_readback` decide si basta con que se
    haya dicho o hace falta que se confirme en voz alta.
    """
    if definicion.requires_readback:
        return status is FieldStatus.CONFIRMED
    return status in (FieldStatus.STATED, FieldStatus.CONFIRMED)


def completeness_of(record_type: RecordType, campos: tuple[CaseField, ...]) -> Completeness:
    """Cuantos campos del tipo estan, y cual de ellos.

    El denominador sale del tipo del caso. Un campo que el esquema no declara
    **no cuenta**, ni siquiera para el numerador: si contara, guardar basura
    bajo una clave inventada subiria la cifra.
    """
    declarados = definitions_for(record_type)
    por_clave = {campo.field_key: campo for campo in campos}

    por_campo: dict[str, bool] = {}
    esperando: set[str] = set()
    for definicion in declarados:
        campo = por_clave.get(definicion.key)
        por_campo[definicion.key] = campo is not None and counts_as_complete(
            definicion, campo.status
        )
        # Dicho y sin confirmar: no cuenta, pero **tampoco hay que volver a
        # preguntarlo**. Lo que toca con el es leerlo de vuelta.
        if (
            campo is not None
            and definicion.requires_readback
            and campo.status is FieldStatus.STATED
        ):
            esperando.add(definicion.key)

    return Completeness.derive(
        por_campo,
        awaiting_readback=frozenset(esperando),
        optional=frozenset(d.key for d in declarados if d.optional),
    )


def validate_field(record_type: RecordType, campo: CaseField) -> CaseField:
    """Comprueba que el esquema declara ese campo para ese tipo de caso.

    Lo demas --una sola evidencia, ninguna si no se ha dicho, la marca de
    lectura solo con turno-- lo impone el propio tipo al construirse, asi que no
    se repite aqui, y esta funcion no vuelve a enumerar sus nueve campos. Lo
    unico que no se puede saber sin el esquema delante es si el campo **existe**
    para ese tipo de caso, y eso es lo que comprueba.

    Devuelve el mismo campo para poder encadenarla donde se construye: una
    comprobacion cuyo resultado se puede ignorar acaba ignorandose.
    """
    definicion = definition_of(record_type, campo.field_key)

    # BR2.2. Tres campos del siniestro --lugar, vehiculo y conductor, y
    # lesiones-- solo llegan a confirmado despues de la lectura en voz alta, o
    # porque una persona los corrigio desde la bandeja, que tambien los deja
    # confirmados (BR2.5). Sin esta comprobacion, un campo que exige lectura
    # llegaba a confirmado sin ella y la completitud lo contaba: la cifra subia
    # sin que nadie hubiera leido nada.
    #
    # Va aqui y no en el tipo porque es la unica regla del campo que necesita el
    # esquema delante: `requires_readback` vive en `fields.yaml`, y `CaseField`
    # es una hoja que no lo lee.
    if (
        definicion.requires_readback
        and campo.status is FieldStatus.CONFIRMED
        and campo.confirmed_aloud_at is None
        and campo.evidence_change_id is None
    ):
        msg = (
            f"el campo '{campo.field_key}' solo llega a confirmado despues de la "
            f"lectura de confirmacion, o corregido por una persona desde la "
            f"bandeja; este no trae ninguna de las dos (BR2.2, BR2.5)"
        )
        raise CaseSchemaError(msg)

    return campo
