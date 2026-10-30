"""Ningun numero de caso y ningun enlace firmado se repite tras el reinicio (BR2.5).

Un numero repetido haria que el papel que alguien anoto nombrara el caso de otra
persona, y un enlace repetido lo abriria. Es una fuga de datos con forma de
coincidencia, y las dos mitades se sostienen de maneras distintas:

- **El enlace** no se puede repetir porque su parte secreta son 32 bytes al azar
  y porque su fila desaparece con el reinicio: un enlace viejo no abre nada, ni
  el caso que nombraba --que ya no existe-- ni ninguno nuevo.
- **El numero si se podia repetir**, y de dos formas a la vez: no habia memoria
  --los numeros de anoche volvian a quedar libres-- y la comprobacion de unicidad
  comparaba la columna entera contra un serial, asi que no podia coincidir nunca.
  El libro de seriales emitidos es la memoria; que se consulte de verdad es lo
  que esta prueba comprueba.

**Como se comprueba.** Desde el 2026-10-30 el numero es un contador por aseguradora
(`SA-1`, `SA-2`...): el siguiente es el mayor del libro mas uno. Si despues del reinicio
el libro no se consultara, el primer caso del dia nuevo volveria a ser `SA-1`. La prueba
exige que sea el que sigue al de anoche, y el control contrario --el libro vaciado a
mano-- exige que entonces si vuelva a ser el primero.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI

from untangle.case_record import api as casos
from untangle.case_record import numbering
from untangle.case_record.models import Channel, Origin, RecordType
from untangle.server import composition, demo_reset
from untangle.tenancy import session, visitor_access
from untangle.tenancy.models import LinkRejectedError

from .conftest import CLAVE_DE_ENLACES, aseguradora, sembrar_datos_de_visitante

pytestmark = pytest.mark.usefixtures("base_de_u20", "sin_transporte")

AHORA = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)


async def _crear(tenant_id: str, case_id: str) -> casos.CaseView:
    return await casos.create_case(
        tenant_id,
        casos.NewCase(
            case_id=case_id,
            record_type=RecordType.CLAIM,
            channel=Channel.CHAT,
            origin=Origin.PUBLIC_CHAT,
            language="es",
        ),
        now=AHORA,
    )


async def test_un_serial_emitido_no_se_vuelve_a_dar_despues_del_reinicio(app: FastAPI) -> None:
    """La memoria sobrevive al borrado del caso que la ocasiono.

    Se crean dos casos, el reinicio se los lleva, y el caso nuevo sigue la cuenta: el
    libro tiene apuntados los dos seriales. Sin libro, o con un libro que el acunador no
    consultara, el caso nuevo naceria con el numero del primero de anoche.
    """
    del app
    tenant_id = aseguradora()
    primero = await _crear(tenant_id, "case-de-anoche")
    segundo = await _crear(tenant_id, "case-de-anoche-2")
    seriales = [int(numbering.parse(c.case_number).serial) for c in (primero, segundo)]
    assert seriales[1] == seriales[0] + 1

    corrida = await demo_reset.reset_now(composition.PURGADORES, now=datetime.now(UTC))
    assert corrida.outcome.value == "succeeded"
    assert await casos.get_case(tenant_id, "case-de-anoche") is None

    nuevo = await _crear(tenant_id, "case-de-hoy")

    assert int(numbering.parse(nuevo.case_number).serial) == seriales[1] + 1


async def test_el_libro_es_lo_que_lo_impide_y_no_otra_cosa(app: FastAPI) -> None:
    """El control contrario, que es el que da valor a la prueba de arriba.

    Con **el libro vaciado a mano**, el contador vuelve a empezar y el serial se repite.
    Es lo que demuestra que lo que para la repeticion es el libro y no el acunador, la
    base ni la casualidad.
    """
    del app
    tenant_id = aseguradora()
    primero = await _crear(tenant_id, "case-de-anoche")
    serial = numbering.parse(primero.case_number).serial
    await demo_reset.reset_now(composition.PURGADORES, now=datetime.now(UTC))

    async with session.session_for(tenant_id) as sesion:
        await session.execute_sql(sesion, "DELETE FROM case_number_issued")

    segundo = await _crear(tenant_id, "case-de-hoy")

    assert numbering.parse(segundo.case_number).serial == serial


async def test_el_libro_sobrevive_al_reinicio_y_el_caso_no(app: FastAPI) -> None:
    """La forma mas directa de decirlo: una fila se va y la otra se queda.

    Si el libro llevara la marca de dato de visitante, el registro de purgadores
    exigiria un dueno que lo borrara, y entonces BR2.5 volveria a ser imposible.
    """
    del app
    tenant_id = aseguradora()
    await _crear(tenant_id, "case-de-anoche")

    await demo_reset.reset_now(composition.PURGADORES, now=datetime.now(UTC))

    async with session.session_for(tenant_id) as sesion:
        casos_vivos = await session.fetch_one(
            sesion, "SELECT count(*) AS total FROM case_record WHERE case_id = 'case-de-anoche'"
        )
        seriales = await session.fetch_one(
            sesion, "SELECT count(*) AS total FROM case_number_issued"
        )
    assert casos_vivos is not None and int(casos_vivos["total"]) == 0
    assert seriales is not None and int(seriales["total"]) == 1


async def test_un_enlace_emitido_antes_no_abre_nada_despues(app: FastAPI) -> None:
    """El enlace de ayer no abre el caso de hoy, porque su fila ya no esta.

    Y el de hoy no coincide con el de ayer: su parte secreta es aleatoria, asi que
    la coincidencia no depende de que nadie la provoque.
    """
    del app
    tenant_id = aseguradora()
    sembrado = await sembrar_datos_de_visitante(tenant_id)
    de_ayer = sembrado.link_token

    await demo_reset.reset_now(composition.PURGADORES, now=datetime.now(UTC))

    # Y el rechazo es **el mismo** que recibe un token inventado: un enlace de
    # anoche no se distingue de uno que nunca existio, que es la unica forma de no
    # confirmar que ese caso existio (BR3.2 de U2).
    with pytest.raises(LinkRejectedError):
        await visitor_access.redeem_case_link(
            de_ayer, tenant_id=tenant_id, signing_key=CLAVE_DE_ENLACES, now=datetime.now(UTC)
        )

    nuevo_caso = await _crear(tenant_id, "case-de-hoy")
    de_hoy = await visitor_access.issue_case_link(
        tenant_id=tenant_id,
        case_id=nuevo_caso.case_id,
        signing_key=CLAVE_DE_ENLACES,
        now=datetime.now(UTC),
    )
    assert de_hoy.token != de_ayer
