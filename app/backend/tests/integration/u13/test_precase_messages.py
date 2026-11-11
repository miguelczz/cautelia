"""Lo hablado antes de abrir caso, contra PostgreSQL (2026-11-11).

Lo que se comprueba lo hace el motor y no el codigo: la politica de fila, la cascada al borrar
la conversacion (que es como el reinicio nocturno la limpia), la llave compuesta con la
aseguradora, el tope de cuarenta y el orden. Y de punta a punta, que `history.load` lo devuelve
antes de los turnos del caso, sin duplicarlos.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from untangle.chat import history, precase
from untangle.chat import session as chat
from untangle.chat.purge import CHAT_PURGER
from untangle.tenancy import config as tenancy_config
from untangle.tenancy import purge as tenancy_purge
from untangle.tenancy import session

from .conftest import AHORA, nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u13")

INSERTAR = (
    "INSERT INTO chat_session_message "
    "(message_id, tenant_id, chat_session_id, seq, speaker, text, language, created_at) "
    "VALUES (:message_id, :tenant_id, :chat_session_id, :seq, :speaker, :text, 'es', :ahora)"
)


async def _conversacion(tenant_id: str) -> chat.ChatSession:
    abierta = await chat.open_session(
        tenant_id=tenant_id,
        visitor_key_digest=f"nav-{uuid.uuid4().hex[:12]}",
        origin_digest=f"org-{uuid.uuid4().hex[:8]}",
        language="es",
        now=AHORA,
    )
    return await chat.mark_opening_delivered(abierta, now=AHORA)


async def _decir(tenant_id: str, chat_session_id: str, persona: str, agente: str) -> None:
    await precase.append_precase_exchange(
        tenant_id=tenant_id,
        chat_session_id=chat_session_id,
        exchange=precase.Exchange(person_text=persona, agent_text=agente, language="es"),
        now=AHORA,
    )


async def _filas(tenant_id: str) -> int:
    async with session.session_for(tenant_id) as sesion:
        return len(await session.fetch_all(sesion, "SELECT 1 FROM chat_session_message"))


async def test_guarda_y_lee_en_orden_y_tal_como_se_escribio(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    conversacion = await _conversacion(propia)
    texto = "Mi póliza es POL-21 y soy Marcela Ríos"

    await _decir(propia, conversacion.chat_session_id, "Hola", "¿En qué le ayudo?")
    await _decir(propia, conversacion.chat_session_id, texto, "Anotado.")

    leidos = await precase.load_precase_messages(
        tenant_id=propia, chat_session_id=conversacion.chat_session_id
    )

    assert [(m.speaker, m.text) for m in leidos] == [
        ("person", "Hola"),
        ("agent", "¿En qué le ayudo?"),
        ("person", texto),
        ("agent", "Anotado."),
    ], "en orden de llegada y sin redactar"
    ultimos = await precase.load_precase_messages(
        tenant_id=propia, chat_session_id=conversacion.chat_session_id, last=2
    )
    assert [m.message_id for m in ultimos] == [m.message_id for m in leidos[-2:]]


async def test_otra_aseguradora_no_ve_las_filas(dos_aseguradoras: tuple[str, str]) -> None:
    ajena, propia = dos_aseguradoras
    conversacion = await _conversacion(ajena)
    await _decir(ajena, conversacion.chat_session_id, "Hola", "Buenas")

    # La misma conversacion, vista con la sesion de otra aseguradora: no existe.
    vistas = await precase.load_precase_messages(
        tenant_id=propia, chat_session_id=conversacion.chat_session_id
    )

    assert vistas == ()
    assert await _filas(propia) == 0
    assert await _filas(ajena) == 2


async def test_una_aseguradora_no_puede_escribir_en_la_conversacion_de_otra(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """La llave lleva la aseguradora: el motor rechaza el cruce aunque la politica de fila
    deje escribir la fila propia."""
    ajena, propia = dos_aseguradoras
    conversacion = await _conversacion(ajena)

    with pytest.raises(IntegrityError) as error:
        async with session.session_for(propia) as sesion:
            await session.execute_sql(
                sesion,
                INSERTAR,
                message_id="m-cruzado",
                tenant_id=propia,
                chat_session_id=conversacion.chat_session_id,
                seq=1,
                speaker="person",
                text="x",
                ahora=AHORA,
            )

    assert "chat_session_message_de_la_conversacion" in str(error.value)


async def test_el_orden_es_unico_por_conversacion(dos_aseguradoras: tuple[str, str]) -> None:
    _, propia = dos_aseguradoras
    conversacion = await _conversacion(propia)
    fila = {
        "tenant_id": propia,
        "chat_session_id": conversacion.chat_session_id,
        "seq": 1,
        "speaker": "person",
        "text": "x",
        "ahora": AHORA,
    }
    async with session.session_for(propia) as sesion:
        await session.execute_sql(sesion, INSERTAR, message_id="m-1", **fila)

    with pytest.raises(IntegrityError) as error:
        async with session.session_for(propia) as sesion:
            await session.execute_sql(sesion, INSERTAR, message_id="m-2", **fila)

    assert "chat_session_message_orden_unico" in str(error.value)


async def test_pasado_el_tope_los_siguientes_no_se_guardan_y_no_hay_error(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    conversacion = await _conversacion(propia)

    for n in range(precase.MAX_MESSAGES // 2 + 3):
        await _decir(propia, conversacion.chat_session_id, f"p{n}", f"a{n}")

    leidos = await precase.load_precase_messages(
        tenant_id=propia, chat_session_id=conversacion.chat_session_id
    )
    assert len(leidos) == precase.MAX_MESSAGES
    assert leidos[0].text == "p0", "se conservan los primeros, no los ultimos"
    assert leidos[-1].text == f"a{precase.MAX_MESSAGES // 2 - 1}"


async def test_borrar_la_conversacion_se_lleva_sus_mensajes(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Es como el reinicio nocturno la limpia: sin sentencia propia, por la cascada."""
    _, propia = dos_aseguradoras
    conversacion = await _conversacion(propia)
    await _decir(propia, conversacion.chat_session_id, "Hola", "Buenas")
    assert await _filas(propia) == 2

    despues = AHORA + timedelta(days=365)
    await CHAT_PURGER.purge(older_than=despues)

    assert await _filas(propia) == 0


async def test_la_tabla_esta_marcada_y_la_cubre_un_purgador() -> None:
    marcadas = await tenancy_purge.visitor_data_tables()
    assert "chat_session_message" in marcadas
    assert "chat_session_message" in CHAT_PURGER.tables


async def test_el_historial_trae_lo_previo_antes_de_los_turnos_del_caso(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """De punta a punta por `history.load`: sin caso, lo previo; con caso, lo previo primero y
    despues la transcripcion del caso, sin que ningun mensaje salga dos veces."""
    _, propia = dos_aseguradoras
    config = tenancy_config.require(propia)
    conversacion = await _conversacion(propia)
    await _decir(propia, conversacion.chat_session_id, "Hola", "¿En qué le ayudo?")

    sin_caso = await history.load(conversacion, config=config)

    assert [t.text for t in sin_caso.turns] == ["Hola", "¿En qué le ayudo?"]
    assert [t.speaker for t in sin_caso.turns] == ["visitor", "agent"]
    assert all(t.turn_id.startswith("pre-") for t in sin_caso.turns)
    assert sin_caso.case_number is None

    caso = await nuevo_caso(propia)
    con_caso = await chat.attach_case(conversacion, case_id=caso.case_id)
    recargado = await history.load(con_caso, config=config)

    ids = [t.turn_id for t in recargado.turns]
    assert ids[:2] == [t.turn_id for t in sin_caso.turns]
    assert len(ids) == len(set(ids))
    assert recargado.case_number is not None
