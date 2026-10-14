"""La compuerta dura de la tanda: nada del visitante antes de la apertura (BR1.1).

Y los cinco controles con los contadores de verdad detras (BR3.1, BR3.2). Estas
pruebas pasan **por la pieza** --`session.admit`-- y no por la funcion pura de
`limits`, que ya tiene las suyas: lo que aqui se comprueba es que los contadores que
la decision recibe son los que la base tiene, que es donde un limite se cae sin que
la logica cambie.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest

from untangle.chat import session as chat
from untangle.chat.limits import LimitKind
from untangle.tenancy.models import ChatConfig

from .conftest import AHORA

pytestmark = pytest.mark.usefixtures("base_de_u13")

#: Numeros pequenos y distintos entre si, por la misma razon que en las unitarias:
#: con los tres iguales, mirar el contador equivocado no se notaria.
LIMITES = ChatConfig(
    messages_per_session=3,
    messages_per_origin_per_day=5,
    messages_per_site_per_day=7,
    min_seconds_between_messages=0,
    max_message_characters=100,
)


def _nav() -> str:
    return f"nav-{uuid.uuid4().hex[:12]}"


async def _abierta(tenant_id: str, *, origen: str | None = None) -> chat.ChatSession:
    return await chat.open_session(
        tenant_id=tenant_id,
        visitor_key_digest=_nav(),
        origin_digest=origen or f"org-{uuid.uuid4().hex[:8]}",
        language="es",
        now=AHORA,
    )


async def _con_apertura(tenant_id: str, *, origen: str | None = None) -> chat.ChatSession:
    return await chat.mark_opening_delivered(await _abierta(tenant_id, origen=origen), now=AHORA)


# --- BR1.1, compuerta dura ----------------------------------------------------


async def test_sin_la_apertura_entregada_ningun_mensaje_se_atiende(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Compuerta dura. Un solo fallo aqui detiene la entrega.

    No devuelve "rechazado": **levanta**. Atender el mensaje y registrar la
    divulgacion despues seria decir que se dijo algo que no se dijo, y devolver un
    rechazo dejaria la puerta abierta a que alguien lo tratara como un limite mas
    y lo ignorara.
    """
    _, propia = dos_aseguradoras
    sesion = await _abierta(propia)

    assert not sesion.opening_delivered
    with pytest.raises(chat.OpeningNotDeliveredError):
        await chat.admit(sesion, config=LIMITES, message_characters=10, now=AHORA)


async def test_con_la_apertura_entregada_el_mismo_mensaje_se_atiende(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """El control positivo. Sin el, una pieza que levantara siempre pasaria la
    prueba de arriba y el chat no atenderia a nadie."""
    _, propia = dos_aseguradoras
    sesion = await _con_apertura(propia)

    admision = await chat.admit(sesion, config=LIMITES, message_characters=10, now=AHORA)

    assert admision.admitted
    assert admision.limit is None


async def test_recargar_la_pagina_no_mueve_la_hora_de_la_apertura(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Cuando se dijo se dice una vez. La segunda marca no la reescribe."""
    _, propia = dos_aseguradoras
    sesion = await _con_apertura(propia)
    mas_tarde = AHORA + timedelta(hours=1)

    otra_vez = await chat.mark_opening_delivered(sesion, now=mas_tarde)

    assert otra_vez.disclosed_at == AHORA
    # Y en la base tampoco: la condicion de la sentencia es lo que lo impide, no
    # el valor que la funcion devuelve.
    assert (await _recargar(sesion)).disclosed_at == AHORA


# --- Los contadores de verdad -------------------------------------------------


async def test_el_limite_de_sesion_se_alcanza_contando_de_verdad(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Tres mensajes atendidos y contados; el cuarto ya no cabe."""
    _, propia = dos_aseguradoras
    sesion = await _con_apertura(propia)

    for _ in range(3):
        admision = await chat.admit(sesion, config=LIMITES, message_characters=10, now=AHORA)
        assert admision.admitted
        await chat.count_message(sesion, now=AHORA)
        sesion = await _recargar(sesion)

    agotada = await chat.admit(sesion, config=LIMITES, message_characters=10, now=AHORA)
    assert agotada.limit is LimitKind.SESSION


async def _recargar(sesion: chat.ChatSession) -> chat.ChatSession:
    """Vuelve a leer la conversacion por su identificador, con lo que la base tiene."""
    from untangle.tenancy import session as db

    async with db.session_for(sesion.tenant_id) as s:
        fila = await db.fetch_one(
            s,
            "SELECT case_id, language, origin_digest, message_count, last_message_at, "
            "disclosed_at FROM chat_session WHERE chat_session_id = :id",
            id=sesion.chat_session_id,
        )
    assert fila is not None
    return chat.ChatSession(
        chat_session_id=sesion.chat_session_id,
        tenant_id=sesion.tenant_id,
        language=fila["language"],
        origin_digest=fila["origin_digest"],
        message_count=fila["message_count"],
        case_id=fila["case_id"],
        last_message_at=fila["last_message_at"],
        disclosed_at=fila["disclosed_at"],
    )


async def test_el_limite_por_origen_cruza_conversaciones(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Es la razon de que el contador por origen exista: si viviera en la
    conversacion, abrir una nueva lo reiniciaria y el limite no seria limite.
    """
    _, propia = dos_aseguradoras
    origen = f"org-{uuid.uuid4().hex[:8]}"

    # Cinco mensajes repartidos entre conversaciones distintas del mismo origen.
    for _ in range(5):
        sesion = await _con_apertura(propia, origen=origen)
        await chat.count_message(sesion, now=AHORA)

    nueva = await _con_apertura(propia, origen=origen)
    admision = await chat.admit(nueva, config=LIMITES, message_characters=10, now=AHORA)

    assert admision.limit is LimitKind.ORIGIN


async def test_un_origen_distinto_no_hereda_el_limite_del_otro(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """El control positivo del anterior: sin el, un contador que sumara todo en
    una sola fila pasaria la prueba de arriba y castigaria a quien no gasto nada.
    """
    _, propia = dos_aseguradoras
    gastado = f"org-{uuid.uuid4().hex[:8]}"
    for _ in range(5):
        sesion = await _con_apertura(propia, origen=gastado)
        await chat.count_message(sesion, now=AHORA)

    otra = await _con_apertura(propia, origen=f"org-{uuid.uuid4().hex[:8]}")
    admision = await chat.admit(otra, config=LIMITES, message_characters=10, now=AHORA)

    assert admision.admitted


async def test_lo_gastado_ayer_no_cuenta_hoy(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """REL-U13.3: el limite diario se reinicia, y se comprueba a los dos lados.

    Un minuto **antes** de medianoche el limite sigue agotado; un minuto
    **despues** vuelve a haber cupo. Sin esta prueba, una ventana mal calculada
    --o simplemente ancha-- pasa inadvertida: todas las demas miden dentro del
    mismo dia y no notan la diferencia. Se encontro asi, ensanchando la ventana
    a proposito y viendo que nada se caia.
    """
    _, propia = dos_aseguradoras
    origen = f"org-{uuid.uuid4().hex[:8]}"
    for _ in range(5):
        sesion = await _con_apertura(propia, origen=origen)
        await chat.count_message(sesion, now=AHORA)

    de_hoy = await _con_apertura(propia, origen=origen)
    un_minuto_antes = AHORA.replace(hour=23, minute=59)
    agotado = await chat.admit(de_hoy, config=LIMITES, message_characters=10, now=un_minuto_antes)
    assert agotado.limit is LimitKind.ORIGIN, "el mismo dia sigue gastado"

    un_minuto_despues = un_minuto_antes + timedelta(minutes=2)
    manana = await chat.admit(de_hoy, config=LIMITES, message_characters=10, now=un_minuto_despues)
    assert manana.admitted, "pasada la medianoche vuelve a haber cupo"


async def test_lo_que_se_escribio_despues_no_cuenta_en_un_dia_anterior(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """El contador del dia es **de ese dia**, tambien mirado desde antes.

    Con el reloj de verdad no hay filas de manana, y por eso la condicion vieja
    --"desde hoy en adelante"-- nunca se noto. La noto el conductor de evaluaciones,
    que conversa en un dia fijo del pasado: sumaba todo lo escrito despues y un dia
    agoto el cupo sin que nadie hubiera escrito ese dia (2026-10-12).
    """
    _, propia = dos_aseguradoras
    origen = f"org-{uuid.uuid4().hex[:8]}"
    despues = AHORA + timedelta(days=3)
    for _ in range(7):
        sesion = await _con_apertura(propia, origen=origen)
        await chat.count_message(sesion, now=despues)

    antes = await _con_apertura(propia, origen=origen)
    admitido = await chat.admit(antes, config=LIMITES, message_characters=10, now=AHORA)
    assert admitido.admitted, "lo gastado tres dias despues no es de este dia"

    ese_dia = await chat.admit(antes, config=LIMITES, message_characters=10, now=despues)
    assert ese_dia.limit is LimitKind.ORIGIN, "y en su dia si sigue gastado"


async def test_olvidar_un_dia_pasado_lo_deja_en_cero_y_no_toca_los_demas(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Lo que usa el conductor de evaluaciones antes de cada conversacion."""
    ajena, propia = dos_aseguradoras
    origen = f"org-{uuid.uuid4().hex[:8]}"
    otro_dia = AHORA + timedelta(days=1)
    for cuando in (AHORA, otro_dia):
        for _ in range(5):
            sesion = await _con_apertura(propia, origen=origen)
            await chat.count_message(sesion, now=cuando)
    de_la_otra = await _con_apertura(ajena, origen=origen)
    for _ in range(5):
        await chat.count_message(await _con_apertura(ajena, origen=origen), now=AHORA)

    await chat.forget_past_day(propia, day=AHORA, now=AHORA + timedelta(days=30))

    nueva = await _con_apertura(propia, origen=origen)
    limpio = await chat.admit(nueva, config=LIMITES, message_characters=10, now=AHORA)
    assert limpio.admitted, "el dia olvidado vuelve a tener cupo"
    intacto = await chat.admit(nueva, config=LIMITES, message_characters=10, now=otro_dia)
    assert intacto.limit is LimitKind.ORIGIN, "el dia siguiente no se toco"
    ajeno = await chat.admit(de_la_otra, config=LIMITES, message_characters=10, now=AHORA)
    assert ajeno.limit is LimitKind.ORIGIN, "ni el mismo dia de otra aseguradora"


@pytest.mark.parametrize("adelanto", [timedelta(0), timedelta(hours=11), timedelta(days=2)])
async def test_no_se_olvida_el_dia_de_hoy_ni_uno_futuro(
    dos_aseguradoras: tuple[str, str], adelanto: timedelta
) -> None:
    """Olvidar hoy seria levantarle el limite a alguien: esa puerta no existe."""
    _, propia = dos_aseguradoras
    origen = f"org-{uuid.uuid4().hex[:8]}"
    for _ in range(5):
        sesion = await _con_apertura(propia, origen=origen)
        await chat.count_message(sesion, now=AHORA + adelanto)

    with pytest.raises(chat.DayStillCountsError):
        await chat.forget_past_day(propia, day=AHORA + adelanto, now=AHORA)

    nueva = await _con_apertura(propia, origen=origen)
    sigue = await chat.admit(nueva, config=LIMITES, message_characters=10, now=AHORA + adelanto)
    assert sigue.limit is LimitKind.ORIGIN, "y no se borro nada"


async def test_el_contador_no_sube_con_un_mensaje_rechazado(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """PERF-U13.2 y BR3.2: lo rechazado no gasta el presupuesto de nadie.

    Un mensaje demasiado largo se rechaza, y el siguiente --del tamano correcto--
    tiene que encontrar el contador intacto.
    """
    _, propia = dos_aseguradoras
    sesion = await _con_apertura(propia)

    rechazado = await chat.admit(sesion, config=LIMITES, message_characters=101, now=AHORA)
    assert rechazado.limit is LimitKind.SIZE

    recargada = await _recargar(sesion)
    assert recargada.message_count == 0
