"""Las dos tablas del chat: su aislamiento, sus llaves y su purgador (BR3.1, NFR19).

Estas pruebas no se pueden escribir sin base de datos, y por eso viven aqui: lo que
comprueban es lo que **PostgreSQL** hace, no lo que el codigo cree que hace.

Cuatro cosas, y cada una cierra un fallo distinto:

1. **La politica de fila.** La conversacion de una aseguradora no existe para otra.
2. **La llave compuesta.** Las comprobaciones de llave foranea las hace el motor por
   encima de las politicas, asi que una llave de una sola columna dejaria a una
   aseguradora escribir una conversacion suya que nombrara el caso de otra.
3. **Una sola conversacion viva por navegador**, impuesta por el indice y no por una
   comprobacion previa en Python.
4. **El purgador**, que es lo que la marca de dato de visitante obliga a tener.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError

from untangle.chat.purge import CHAT_PURGER
from untangle.server import composition
from untangle.tenancy import purge as tenancy_purge
from untangle.tenancy import session

from .conftest import AHORA, nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u13")

INSERTAR_SESION = (
    "INSERT INTO chat_session "
    "(chat_session_id, tenant_id, visitor_key_digest, case_id, language, "
    " origin_digest, message_count, created_at) "
    "VALUES (:chat_session_id, :tenant_id, :visitor_key_digest, :case_id, :language, "
    " :origin_digest, :message_count, :created_at)"
)


def _id(prefijo: str) -> str:
    return f"{prefijo}-{uuid.uuid4().hex[:12]}"


def _sesion(
    tenant_id: str, *, case_id: str | None = None, navegador: str | None = None
) -> dict[str, Any]:
    return {
        "chat_session_id": _id("chat"),
        "tenant_id": tenant_id,
        "visitor_key_digest": navegador or _id("nav"),
        "case_id": case_id,
        "language": "es",
        "origin_digest": _id("org"),
        "message_count": 0,
        "created_at": AHORA,
    }


async def _escribir(tenant_id: str, fila: dict[str, Any]) -> None:
    async with session.session_for(tenant_id) as sesion:
        await session.execute_sql(sesion, INSERTAR_SESION, **fila)


async def _rechazo(tenant_id: str, fila: dict[str, Any]) -> str:
    with pytest.raises(IntegrityError) as error:
        await _escribir(tenant_id, fila)
    return str(error.value)


# --- 1. La politica de fila ---------------------------------------------------


async def test_la_conversacion_de_una_aseguradora_no_existe_para_otra(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Ni su contenido, ni el hecho de que este ahi."""
    ajena, propia = dos_aseguradoras
    await _escribir(ajena, _sesion(ajena))

    async with session.session_for(propia) as sesion:
        filas = await session.fetch_all(sesion, "SELECT chat_session_id FROM chat_session")

    assert not filas


# --- 2. La llave compuesta ----------------------------------------------------


async def test_una_conversacion_no_puede_apuntar_al_caso_de_otra_aseguradora(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """La llave lleva la aseguradora, y por eso el motor rechaza el cruce.

    Dos inserciones con la misma forma, cambiando una sola cosa: la primera apunta
    a lo propio y entra --asi el rechazo de la segunda no se puede deber a otra
    restriccion--; la segunda apunta al caso de la otra aseguradora y choca.
    """
    ajena, propia = dos_aseguradoras
    caso_ajeno = await nuevo_caso(ajena)
    caso_propio = await nuevo_caso(propia)

    await _escribir(propia, _sesion(propia, case_id=caso_propio.case_id))

    cruzada = _sesion(propia, case_id=caso_ajeno.case_id)
    mensaje = await _rechazo(propia, cruzada)

    assert "chat_session_del_caso" in mensaje


async def test_borrar_el_caso_se_lleva_su_conversacion(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """La cascada: un caso de visitante borrado no deja su conversacion detras."""
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    await _escribir(propia, _sesion(propia, case_id=caso.case_id))

    async with session.session_for(propia) as sesion:
        await session.execute_sql(
            sesion, "DELETE FROM case_record WHERE case_id = :case_id", case_id=caso.case_id
        )
        quedan = await session.fetch_all(sesion, "SELECT 1 FROM chat_session")

    assert not quedan


# --- 3. Una sola conversacion viva por navegador ------------------------------


async def test_dos_conversaciones_vivas_del_mismo_navegador_no_caben(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Dos abiertas dejarian la retoma sin saber cual retomar."""
    _, propia = dos_aseguradoras
    navegador = _id("nav")
    await _escribir(propia, _sesion(propia, navegador=navegador))

    mensaje = await _rechazo(propia, _sesion(propia, navegador=navegador))

    assert "chat_session_una_viva" in mensaje


async def test_cerrada_la_primera_el_mismo_navegador_puede_abrir_otra(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """El control positivo del anterior: el indice es parcial, no absoluto.

    Sin esta prueba, un indice unico **sin** su condicion pasaria la de arriba
    igual y dejaria a un visitante con una sola conversacion para siempre.
    """
    _, propia = dos_aseguradoras
    navegador = _id("nav")
    primera = _sesion(propia, navegador=navegador)
    await _escribir(propia, primera)

    async with session.session_for(propia) as sesion:
        await session.execute_sql(
            sesion,
            "UPDATE chat_session SET closed_at = :ahora WHERE chat_session_id = :id",
            ahora=AHORA,
            id=primera["chat_session_id"],
        )

    await _escribir(propia, _sesion(propia, navegador=navegador))

    async with session.session_for(propia) as sesion:
        filas = await session.fetch_all(sesion, "SELECT 1 FROM chat_session")
    assert len(filas) == 2


# --- 4. El purgador que la marca obliga a tener -------------------------------


async def test_la_conversacion_esta_marcada_y_tiene_su_purgador() -> None:
    marcadas = await tenancy_purge.visitor_data_tables()
    assert "chat_session" in marcadas
    assert await tenancy_purge.tables_without_purger(composition.PURGADORES) == frozenset()


async def test_el_reinicio_nocturno_se_lleva_la_conversacion_y_conserva_el_conteo_del_dia(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Lo que apunta a alguien se va; la cifra del sitio se queda (NFR19).

    El conteo por dia es el que el panel publico necesita vivo, y por eso vuelve
    como `kept` y no como `deleted`: quien lea el resultado tiene que ver que se
    conservo a proposito y no que se olvido.
    """
    _, propia = dos_aseguradoras
    await _escribir(propia, _sesion(propia))
    async with session.session_for(propia) as sesion:
        await session.execute_sql(
            sesion,
            "INSERT INTO chat_rate_window (tenant_id, scope, scope_key, window_start, count) "
            "VALUES (:t, 'origin', :k, :w, 3), (:t, 'site_day', '2026-09-28', :w, 40)",
            t=propia,
            k=_id("org"),
            w=AHORA,
        )

    despues = AHORA.replace(year=AHORA.year + 1)
    resultado = await CHAT_PURGER.purge(older_than=despues)

    assert resultado.deleted == 2, "la conversacion y el contador por origen"
    assert resultado.kept == 1, "el conteo del dia del sitio"

    async with session.session_for(propia) as sesion:
        quedan = await session.fetch_all(
            sesion, "SELECT scope FROM chat_rate_window ORDER BY scope"
        )
        sesiones = await session.fetch_all(sesion, "SELECT 1 FROM chat_session")
    assert [f["scope"] for f in quedan] == ["site_day"]
    assert not sesiones
