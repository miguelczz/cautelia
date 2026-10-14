"""El acceso del visitante: el enlace de una hora y la clave del navegador.

Corre contra PostgreSQL de verdad porque el aislamiento por fila es parte de lo
que se prueba: un enlace de otra aseguradora no se encuentra, y eso lo decide la
politica de la tabla, no el codigo.

El reloj se controla: esperar una hora no es una prueba.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from untangle.tenancy import ephemeral, session, visitor_access
from untangle.tenancy.models import (
    CaseLinkGrant,
    IssuedCaseLink,
    LinkRejectedError,
    LinkRejection,
)

CLAVE_DE_ENLACES = "clave-de-prueba-de-los-enlaces-para-la-firma-hmac"
CLAVE_DE_BANDEJA = "clave-de-prueba-de-la-bandeja-para-la-firma-hs256"
AHORA = datetime(2026, 9, 20, 9, 0, tzinfo=UTC)
CASO = "CASE-7F3A21"


async def _emitir(tenant: str = "stonecroft", caso: str = CASO) -> IssuedCaseLink:
    return await visitor_access.issue_case_link(
        tenant_id=tenant, case_id=caso, signing_key=CLAVE_DE_ENLACES, now=AHORA
    )


async def _canjear(
    token: str,
    *,
    tenant: str = "stonecroft",
    momento: datetime | None = None,
    clave: str = CLAVE_DE_ENLACES,
    caso_esperado: str | None = None,
) -> CaseLinkGrant:
    return await visitor_access.redeem_case_link(
        token,
        tenant_id=tenant,
        signing_key=clave,
        expected_case=caso_esperado,
        now=momento if momento is not None else AHORA,
    )


async def test_el_enlace_se_canjea_dos_veces_dentro_de_su_hora(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """BR3.2, FD-U2-3: quien cierra la pestana vuelve a entrar."""
    enlace = await _emitir()

    primero = await _canjear(enlace.token, momento=AHORA + timedelta(minutes=1))
    segundo = await _canjear(enlace.token, momento=AHORA + timedelta(minutes=10))

    assert primero.case_id == CASO
    assert segundo.case_id == CASO
    # El contador sube en cada canje: un canje repetido es un hecho observable y
    # no una conjetura.
    assert (primero.redeemed_count, segundo.redeemed_count) == (1, 2)


async def test_a_las_dos_horas_responde_como_un_caso_inexistente(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """BR3.1: una hora de vida, ni un minuto mas."""
    enlace = await _emitir()

    with pytest.raises(LinkRejectedError) as fallo:
        await _canjear(enlace.token, momento=AHORA + timedelta(hours=2))

    assert fallo.value.cause is LinkRejection.EXPIRED
    assert fallo.value.denial.status == 404


async def test_la_credencial_del_canje_no_vive_mas_que_su_enlace(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """BR3.4: si al enlace le quedan N minutos, la credencial dura N minutos."""
    enlace = await _emitir()

    concesion = await _canjear(enlace.token, momento=AHORA + timedelta(minutes=50))

    assert concesion.expires_at == enlace.expires_at
    assert concesion.expires_at - (AHORA + timedelta(minutes=50)) == timedelta(minutes=10)


async def test_las_cuatro_causas_de_rechazo_dan_respuestas_identicas(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """BR3.3, C-07: invalido, caducado, revocado y de otro caso, todos iguales.

    Se comparan **entre si**, no contra una plantilla, y ademas se comprueba que
    las cuatro causas fueron distintas: sin eso, cuatro caminos identicos daria
    el mismo resultado sin probar nada.
    """
    caducado = await _emitir()
    revocado = await _emitir()
    de_otro_caso = await _emitir(caso="CASE-OTRO-001")
    await visitor_access.revoke_case_link(
        tenant_id="stonecroft", link_id=revocado.link_id, now=AHORA
    )

    intentos = (
        ("no-es.un-token-valido", AHORA, None),
        (caducado.token, AHORA + timedelta(hours=2), None),
        (revocado.token, AHORA, None),
        (de_otro_caso.token, AHORA, CASO),
    )

    respuestas = []
    causas = []
    for token, momento, caso_esperado in intentos:
        with pytest.raises(LinkRejectedError) as fallo:
            await _canjear(token, momento=momento, caso_esperado=caso_esperado)
        respuestas.append((fallo.value.denial.status, fallo.value.denial.body()))
        causas.append(fallo.value.cause)

    assert len(set(respuestas)) == 1
    assert causas == [
        LinkRejection.INVALID,
        LinkRejection.EXPIRED,
        LinkRejection.REVOKED,
        LinkRejection.OTHER_CASE,
    ]


async def test_un_enlace_de_otra_aseguradora_responde_como_inexistente(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """La politica de la tabla, no un `if`: el enlace simplemente no esta ahi."""
    de_stonecroft = await _emitir(tenant="stonecroft")

    with pytest.raises(LinkRejectedError) as fallo:
        await _canjear(de_stonecroft.token, tenant="sunmeadow")

    assert fallo.value.cause is LinkRejection.INVALID


async def test_la_clave_de_bandeja_no_canjea_un_enlace_de_caso(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """SEC-U2.5, por el camino publico: una clave no valida lo de la otra."""
    enlace = await _emitir()

    with pytest.raises(LinkRejectedError) as fallo:
        await _canjear(enlace.token, clave=CLAVE_DE_BANDEJA)

    assert fallo.value.cause is LinkRejection.INVALID


async def test_del_token_solo_se_guarda_su_resumen(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """FD-U2-8: quien lea la tabla no puede reconstruir ningun enlace."""
    enlace = await _emitir()

    async with session.session_for("stonecroft") as sesion:
        filas = await session.fetch_all(
            sesion,
            "SELECT token_digest FROM case_access_link WHERE link_id = :id",
            id=enlace.link_id,
        )

    guardado = str(filas[0]["token_digest"])
    assert guardado != enlace.token
    assert enlace.token not in guardado
    assert guardado == visitor_access.token_digest(enlace.token)


async def test_pedir_otro_caso_con_la_concesion_responde_como_inexistente(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """BR3.1: la credencial abre su caso y nunca la lista de la aseguradora."""
    enlace = await _emitir()
    concesion = await _canjear(enlace.token)

    visitor_access.authorize_case(concesion, CASO)
    with pytest.raises(LinkRejectedError) as fallo:
        visitor_access.authorize_case(concesion, "CASE-DE-OTRO")

    assert fallo.value.cause is LinkRejection.OTHER_CASE


async def test_una_clave_de_navegador_usada_en_dos_aseguradoras_tiene_dos_filas(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """BR3.5: el mismo navegador en dos demostraciones, y ninguna ve la otra."""
    clave = visitor_access.new_visitor_key()

    en_stonecroft = await visitor_access.resolve_visitor_key(
        tenant_id="stonecroft",
        visitor_key=clave,
        origin="https://demo.untangle.local",
        now=AHORA,
    )
    en_sunmeadow = await visitor_access.resolve_visitor_key(
        tenant_id="sunmeadow",
        visitor_key=clave,
        origin="https://demo.untangle.local",
        now=AHORA,
    )

    assert en_stonecroft.visitor_key_hash == en_sunmeadow.visitor_key_hash
    assert en_stonecroft.tenant_id != en_sunmeadow.tenant_id

    for tenant_id in ("stonecroft", "sunmeadow"):
        async with session.session_for(tenant_id) as sesion:
            filas = await session.fetch_all(sesion, "SELECT tenant_id FROM visitor_key")
        assert [str(f["tenant_id"]) for f in filas] == [tenant_id]


async def test_volver_con_la_misma_clave_actualiza_su_ultimo_uso_sin_crear_otra_fila(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    clave = visitor_access.new_visitor_key()
    origen = "https://demo.untangle.local"

    primera = await visitor_access.resolve_visitor_key(
        tenant_id="stonecroft", visitor_key=clave, origin=origen, now=AHORA
    )
    despues = await visitor_access.resolve_visitor_key(
        tenant_id="stonecroft", visitor_key=clave, origin=origen, now=AHORA + timedelta(minutes=30)
    )

    assert despues.created_at == primera.created_at
    assert despues.last_seen_at == AHORA + timedelta(minutes=30)

    async with session.session_for("stonecroft") as sesion:
        filas = await session.fetch_all(sesion, "SELECT visitor_key_hash FROM visitor_key")
    assert len(filas) == 1


async def test_la_clave_de_navegador_no_guarda_nada_que_identifique_a_una_persona(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """La ausencia es deliberada: ni nombre, ni correo, ni direccion de red."""
    async with session.unscoped_session() as sesion:
        columnas = await session.fetch_all(
            sesion,
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'visitor_key'
            ORDER BY column_name
            """,
        )

    nombres = {str(c["column_name"]) for c in columnas}
    assert nombres == {
        "tenant_id",
        "visitor_key_hash",
        "origin",
        "created_at",
        "last_seen_at",
    }
