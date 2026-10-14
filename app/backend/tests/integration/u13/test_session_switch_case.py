"""Pasar la conversacion de un caso a otro porque la persona cambio de tema (2026-10-12).

`attach_case` ata una sola vez, a proposito: una segunda escritura significaria que se abrio un
caso por sorpresa, y eso hay que verlo. `switch_case` es el camino con nombre para el cambio de
tema, y solo parte del caso en que la conversacion de verdad esta. Con base de datos: lo que se
comprueba es la sentencia, no una copia en memoria.
"""

from __future__ import annotations

import pytest

from untangle.chat import session as chat_session

from .conftest import nuevo_caso
from .test_delivery import _conversacion_nueva

pytestmark = pytest.mark.usefixtures("base_de_u13")


async def _viva_en(tenant_id: str, clave: str) -> str | None:
    viva = await chat_session.find_live(tenant_id=tenant_id, visitor_key_digest=clave)
    assert viva is not None
    return viva.case_id


async def test_la_conversacion_pasa_del_caso_en_que_esta_al_nuevo(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    conversacion, clave = await _conversacion_nueva(propia)
    primero = await nuevo_caso(propia)
    segundo = await nuevo_caso(propia)
    conversacion = await chat_session.attach_case(conversacion, case_id=primero.case_id)

    movida = await chat_session.switch_case(
        conversacion, case_id=segundo.case_id, from_case_id=primero.case_id
    )

    assert movida.case_id == segundo.case_id
    assert await _viva_en(propia, clave) == segundo.case_id
    # Lo demas de la conversacion no se toca.
    assert movida.chat_session_id == conversacion.chat_session_id
    assert movida.message_count == conversacion.message_count
    assert movida.disclosed_at == conversacion.disclosed_at


async def test_si_la_conversacion_ya_no_esta_en_ese_caso_no_se_pisa(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Dos mensajes en vuelo: el segundo parte de un caso en el que la conversacion ya no esta."""
    _, propia = dos_aseguradoras
    conversacion, clave = await _conversacion_nueva(propia)
    primero = await nuevo_caso(propia)
    segundo = await nuevo_caso(propia)
    tercero = await nuevo_caso(propia)
    conversacion = await chat_session.attach_case(conversacion, case_id=primero.case_id)
    await chat_session.switch_case(
        conversacion, case_id=segundo.case_id, from_case_id=primero.case_id
    )

    with pytest.raises(chat_session.ConversationMovedError):
        await chat_session.switch_case(
            conversacion, case_id=tercero.case_id, from_case_id=primero.case_id
        )

    assert await _viva_en(propia, clave) == segundo.case_id


async def test_una_conversacion_sin_caso_no_se_cambia_de_caso(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Atar el primer caso es de `attach_case`; `switch_case` solo reemplaza uno ya atado."""
    _, propia = dos_aseguradoras
    conversacion, clave = await _conversacion_nueva(propia)
    caso = await nuevo_caso(propia)

    with pytest.raises(chat_session.ConversationMovedError):
        await chat_session.switch_case(conversacion, case_id=caso.case_id, from_case_id="otro")

    assert await _viva_en(propia, clave) is None


async def test_pasar_al_caso_en_que_ya_esta_no_cambia_nada(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    conversacion, clave = await _conversacion_nueva(propia)
    caso = await nuevo_caso(propia)
    conversacion = await chat_session.attach_case(conversacion, case_id=caso.case_id)

    igual = await chat_session.switch_case(
        conversacion, case_id=caso.case_id, from_case_id=caso.case_id
    )

    assert igual == conversacion
    assert await _viva_en(propia, clave) == caso.case_id


async def test_atar_sigue_sin_poder_reemplazar_un_caso_ya_atado(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """La guarda de `attach_case` no se afloja: el cambio de tema tiene su propio camino."""
    _, propia = dos_aseguradoras
    conversacion, clave = await _conversacion_nueva(propia)
    primero = await nuevo_caso(propia)
    segundo = await nuevo_caso(propia)
    await chat_session.attach_case(conversacion, case_id=primero.case_id)

    # Con la copia que todavia no sabe que ya tiene caso, la sentencia es la que se niega.
    await chat_session.attach_case(conversacion, case_id=segundo.case_id)

    assert await _viva_en(propia, clave) == primero.case_id
