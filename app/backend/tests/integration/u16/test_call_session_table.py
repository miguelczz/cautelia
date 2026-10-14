"""La tabla de la llamada: su aislamiento, sus conjuntos cerrados y su cascada."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from untangle.tenancy import session
from untangle.voice import session as llamadas
from untangle.voice.models import CallState, EndReason, VoiceMode

from .conftest import AHORA, nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u16")

CLAVE_A = "a" * 64
CLAVE_B = "b" * 64


async def test_la_llamada_de_una_aseguradora_no_se_ve_desde_la_otra(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """La colision sembrada: las dos filas viven en la misma tabla y comparten
    el resumen del navegador, asi que una consulta sin filtro por aseguradora
    devolveria las dos."""
    a, b = dos_aseguradoras
    await llamadas.open_call(
        tenant_id=a,
        visitor_key_digest=CLAVE_A,
        language="en",
        voice_mode=VoiceMode.PRIMARY,
        now=AHORA,
    )
    await llamadas.open_call(
        tenant_id=b,
        visitor_key_digest=CLAVE_A,
        language="en",
        voice_mode=VoiceMode.PRIMARY,
        now=AHORA,
    )

    desde_a = await llamadas.find_live(tenant_id=a, visitor_key_digest=CLAVE_A)
    desde_b = await llamadas.find_live(tenant_id=b, visitor_key_digest=CLAVE_A)

    assert desde_a is not None
    assert desde_b is not None
    assert desde_a.call_id != desde_b.call_id
    assert desde_a.tenant_id == a
    assert desde_b.tenant_id == b

    async with session.session_for(a) as sesion:
        filas = await session.fetch_all(sesion, "SELECT call_id FROM call_session")
    assert len(filas) == 1, "la politica de fila deja ver la llamada de la otra aseguradora"


async def test_la_tabla_no_tiene_ninguna_columna_de_audio(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """BR7.1: un campo que no existe no se llena 'temporalmente para depurar'."""
    a, _ = dos_aseguradoras
    async with session.session_for(a) as sesion:
        filas = await session.fetch_all(
            sesion,
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'call_session'",
        )
    columnas = {f["column_name"] for f in filas}
    assert not {c for c in columnas if "audio" in c or "record" in c or "sample" in c}


async def test_una_llamada_terminada_sin_motivo_no_cabe_en_la_tabla(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """BR1.6: el estado y el motivo no se separan."""
    a, _ = dos_aseguradoras
    llamada = await llamadas.open_call(
        tenant_id=a,
        visitor_key_digest=CLAVE_A,
        language="en",
        voice_mode=VoiceMode.PRIMARY,
        now=AHORA,
    )
    with pytest.raises(IntegrityError):
        async with session.session_for(a) as sesion:
            await session.execute_sql(
                sesion,
                "UPDATE call_session SET state = 'ended' WHERE call_id = :c",
                c=llamada.call_id,
            )


@pytest.mark.parametrize(
    ("columna", "valor"),
    [
        ("state", "speaking"),
        ("end_reason", "cancelled"),
        ("voice_mode", "cloned"),
        ("language", "fr"),
    ],
)
async def test_los_conjuntos_cerrados_lo_son_en_la_base(
    dos_aseguradoras: tuple[str, str], columna: str, valor: str
) -> None:
    a, _ = dos_aseguradoras
    llamada = await llamadas.open_call(
        tenant_id=a,
        visitor_key_digest=CLAVE_A,
        language="en",
        voice_mode=VoiceMode.PRIMARY,
        now=AHORA,
    )
    with pytest.raises(IntegrityError):
        async with session.session_for(a) as sesion:
            await session.execute_sql(
                sesion,
                f"UPDATE call_session SET {columna} = :v WHERE call_id = :c",  # noqa: S608
                v=valor,
                c=llamada.call_id,
            )


async def test_borrar_el_caso_se_lleva_la_llamada(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """La cascada es lo que hace que el borrado nocturno de U2 alcance (BR7.3)."""
    a, _ = dos_aseguradoras
    caso = await nuevo_caso(a)
    llamada = await llamadas.open_call(
        tenant_id=a,
        visitor_key_digest=CLAVE_A,
        language="en",
        voice_mode=VoiceMode.PRIMARY,
        now=AHORA,
    )
    await llamadas.attach_case(llamada, case_id=caso.case_id)

    async with session.session_for(a) as sesion:
        antes = await session.fetch_all(sesion, "SELECT call_id FROM call_session")
        assert [f["call_id"] for f in antes] == [llamada.call_id]
        await session.execute_sql(
            sesion, "DELETE FROM case_record WHERE case_id = :c", c=caso.case_id
        )
        despues = await session.fetch_all(sesion, "SELECT call_id FROM call_session")
    assert list(despues) == []


async def test_la_llave_foranea_es_compuesta_y_no_cruza_aseguradoras(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """La leccion de u9: las llaves foraneas no pasan por las politicas de fila,
    asi que con una llave simple la llamada de B podria apuntar al caso de A."""
    a, b = dos_aseguradoras
    caso_de_a = await nuevo_caso(a)
    llamada_de_b = await llamadas.open_call(
        tenant_id=b,
        visitor_key_digest=CLAVE_B,
        language="en",
        voice_mode=VoiceMode.PRIMARY,
        now=AHORA,
    )
    with pytest.raises(IntegrityError):
        async with session.session_for(b) as sesion:
            await session.execute_sql(
                sesion,
                "UPDATE call_session SET case_id = :caso WHERE call_id = :c",
                caso=caso_de_a.case_id,
                c=llamada_de_b.call_id,
            )


async def test_los_seis_motivos_de_final_caben(
    dos_aseguradoras: tuple[str, str],
) -> None:
    a, _ = dos_aseguradoras
    for motivo in EndReason:
        llamada = await llamadas.open_call(
            tenant_id=a,
            visitor_key_digest=CLAVE_A,
            language="en",
            voice_mode=VoiceMode.PRIMARY,
            now=AHORA,
        )
        terminada = await llamadas.end_call(llamada, reason=motivo, now=AHORA)
        assert terminada.state is CallState.ENDED
        assert terminada.end_reason is motivo
