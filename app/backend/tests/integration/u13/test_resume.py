"""Las dos compuertas duras de U13: retomar un caso que no es tuyo (BR6.2, BR6.3).

Compuertas duras: pasa o falla por caso, un solo fallo detiene la entrega y ninguna
explicacion la levanta.

**Como se comprueban.** No mirando que el dato ajeno no aparezca, sino **comparando**
la respuesta contra la de un numero que no existe. La razon la dejo escrita U12 y esta
unidad la hereda: la filtracion no es el dato, es la distincion. Recibir algo distinto
de lo que recibe un desconocido ya dice que ese caso existe.

Y el **control positivo va delante** en las dos: sin el, las dos aserciones pasarian
igual con una implementacion que no devolviera nunca nada.
"""

from __future__ import annotations

import uuid

import pytest

from untangle.case_record import api as casos
from untangle.chat import resume
from untangle.chat import session as chat

from .conftest import AHORA, nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u13")


def _nav() -> str:
    return f"nav-{uuid.uuid4().hex[:12]}"


async def _caso_de(tenant_id: str, navegador: str) -> tuple[str, str]:
    """Un caso abierto desde una conversacion de ese navegador. Devuelve (id, numero)."""
    caso = await nuevo_caso(tenant_id)
    sesion = await chat.open_session(
        tenant_id=tenant_id,
        visitor_key_digest=navegador,
        origin_digest=f"org-{uuid.uuid4().hex[:8]}",
        language="es",
        now=AHORA,
    )
    from untangle.tenancy import session as db

    async with db.session_for(tenant_id) as s:
        await db.execute_sql(
            s,
            "UPDATE chat_session SET case_id = :case_id WHERE chat_session_id = :id",
            case_id=caso.case_id,
            id=sesion.chat_session_id,
        )
    vista = await casos.get_case(tenant_id, caso.case_id)
    assert vista is not None
    return caso.case_id, str(vista.case_number)


# --- El control positivo, primero ---------------------------------------------


async def test_el_propio_navegador_si_retoma_su_caso(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Va primero a proposito: sin el, las dos compuertas de abajo pasarian igual
    con una implementacion que no devolviera nunca nada."""
    _, propia = dos_aseguradoras
    navegador = _nav()
    case_id, numero = await _caso_de(propia, navegador)

    retomado = await resume.by_case_number(
        tenant_id=propia, case_number=numero, visitor_key_digest=navegador
    )

    assert retomado is not None
    assert retomado.case_id == case_id


# --- BR6.2: otro navegador, compuerta dura ------------------------------------


async def test_un_caso_de_otro_navegador_responde_igual_que_uno_inexistente(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Compuerta dura. **Identico**, no "sin el dato del otro".

    Las tres polizas de ejemplo son publicas a proposito, asi que identificarse con
    una no prueba nada: lo que ata un caso a una persona es la clave de su
    navegador. Un visitante que teclea el numero de otro tiene que recibir
    exactamente lo mismo que si lo hubiera inventado.
    """
    _, propia = dos_aseguradoras
    _, numero_ajeno = await _caso_de(propia, _nav())

    desde_otro = await resume.by_case_number(
        tenant_id=propia, case_number=numero_ajeno, visitor_key_digest=_nav()
    )
    inventado = await resume.by_case_number(
        tenant_id=propia, case_number="XXX-000-000", visitor_key_digest=_nav()
    )

    assert desde_otro == inventado
    assert desde_otro is None


# --- BR6.3: otra aseguradora, compuerta dura ----------------------------------


async def test_un_caso_de_otra_aseguradora_responde_igual_que_uno_inexistente(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Compuerta dura. Y no lo sostiene ninguna comprobacion de esta unidad: la
    politica de fila lo filtro antes de que la consulta lo viera, asi que el codigo
    del chat nunca llega a saber cual de los dos casos era.
    """
    ajena, propia = dos_aseguradoras
    navegador = _nav()
    _, numero_de_la_otra = await _caso_de(ajena, navegador)

    desde_la_propia = await resume.by_case_number(
        tenant_id=propia, case_number=numero_de_la_otra, visitor_key_digest=navegador
    )
    inventado = await resume.by_case_number(
        tenant_id=propia, case_number="XXX-000-000", visitor_key_digest=navegador
    )

    assert desde_la_propia == inventado
    assert desde_la_propia is None


async def test_el_mismo_navegador_con_la_misma_poliza_no_basta(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """El caso que la compuerta persigue de verdad, dicho entero: **el mismo
    navegador**, en **la misma aseguradora**, con la **misma poliza de ejemplo**, y
    aun asi no ve el caso que no abrio. Lo que ata el caso no es la poliza.
    """
    _, propia = dos_aseguradoras
    poliza = "POL-01"
    ajeno = await nuevo_caso(propia, policy_ref=poliza)
    vista_ajena = await casos.get_case(propia, ajeno.case_id)
    assert vista_ajena is not None

    curioso = _nav()
    await _caso_de(propia, curioso)  # tiene su propio caso con la misma poliza

    intento = await resume.by_case_number(
        tenant_id=propia, case_number=str(vista_ajena.case_number), visitor_key_digest=curioso
    )

    assert intento is None
