"""Los dos carriles diarios, cableados contra la base (BR1.1, BR1.3, BR1.4).

Hasta la tanda 2, `decide` existia y **nadie la llamaba**: la ruta servia los dos
carriles en nulo y abria llamadas sin contarlas. Lo que se comprueba aqui es el
cable, y por eso todo entra por HTTP: una prueba contra la funcion volveria a
probar la decision que ya estaba probada.

La disponibilidad **lee** los contadores y la apertura los **consume**, y esa
diferencia es la mitad de lo que estas pruebas vigilan: un `GET` que gastara la
llamada del dia dejaria sin voz a quien solo miro la pagina.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import FastAPI

from untangle.providers import config as provider_config
from untangle.telemetry.spend import api as spend
from untangle.telemetry.spend.models import SITE_SUBJECT, QuotaScope, VoiceMode
from untangle.tenancy import api as tenancy
from untangle.voice import api as voz
from untangle.voice.availability import OFF_CODE_KEYS, VoiceOffCode

from .conftest import aseguradora, cliente, llamadas_en

pytestmark = pytest.mark.usefixtures("base_de_u17")


async def _disponibilidad(app: FastAPI, *, galleta: str | None = None) -> dict[str, object]:
    async with cliente(app) as http:
        if galleta is not None:
            http.cookies.set("untangle_visitor", galleta)
        respuesta = await http.get(f"/api/voice/{aseguradora()}/availability")
    assert respuesta.status_code == 200, respuesta.text
    cuerpo: dict[str, object] = respuesta.json()
    return cuerpo


# --- BR1.4: la llamada del dia de una conexion --------------------------------


def _llamadas_por_conexion() -> int:
    """El carril diario de una conexion, leido de `providers.yaml` (3 desde el
    2026-10-07; antes 1). Las pruebas lo agotan abriendo esas llamadas, no una."""
    return provider_config.load().providers.voice_limits.calls_per_visitor_per_day


async def _agotar_la_conexion(http: object, tenant: str) -> None:
    """Abre las llamadas que caben hoy desde esta conexion, comprobando cada una."""
    for _ in range(_llamadas_por_conexion()):
        abierta = await http.post(f"/api/voice/{tenant}/sessions", json={})  # type: ignore[attr-defined]
        assert abierta.status_code == 201, abierta.text


async def test_la_segunda_llamada_del_dia_de_una_conexion_no_se_abre(app: FastAPI) -> None:
    """Un carril de pocas llamadas al dia, y la peticion que sobra lo dice.

    El control positivo va primero: sin el, "la que sobra no se abre" pasaria
    igual contra una ruta que no abriera ninguna.
    """
    async with cliente(app) as http:
        await _agotar_la_conexion(http, aseguradora())
        sobrante = await http.post(f"/api/voice/{aseguradora()}/sessions", json={})

    assert sobrante.status_code == 503, sobrante.text
    assert sobrante.json()["code"] == "rate_limited_daily"
    assert await llamadas_en(aseguradora()) == _llamadas_por_conexion(), (
        "la llamada rechazada dejo fila"
    )


async def test_la_disponibilidad_dice_cual_carril_se_agoto(app: FastAPI) -> None:
    """Y lo dice **con la clave de su frase**, nunca con la frase."""
    async with cliente(app) as http:
        await _agotar_la_conexion(http, aseguradora())
        galleta = http.cookies.get("untangle_visitor")
        assert galleta is not None
        despues = await http.get(f"/api/voice/{aseguradora()}/availability")

    cuerpo = despues.json()
    assert cuerpo["available"] is False
    assert cuerpo["reason_code"] == "rate_limited_daily"
    assert cuerpo["reason_key"] == str(OFF_CODE_KEYS[VoiceOffCode.RATE_LIMITED_DAILY])
    # Y la clave es la de la voz, no la de U5 que habla del chat ("llegaste al limite de
    # hoy"): V15 de la auditoria. Escrita literal para que la tabla no se compare consigo.
    assert cuerpo["reason_key"] == "voice.availability.rate_limited_daily"


async def test_la_disponibilidad_distingue_el_cupo_del_sitio_del_de_la_conexion(
    app: FastAPI,
) -> None:
    """V15: el rechazo del sitio no se parece al de la conexion, ni en el codigo ni en la
    frase. Quien llega y ve "ya usaste tus llamadas" cuando nunca llamo no sabria que el
    limite es de todos."""
    async with cliente(app) as http:
        del_sitio = await spend.quota_state(QuotaScope.VOICE_CALLS_SITE_DAY, SITE_SUBJECT)
        for _ in range(del_sitio.remaining):
            decision = await spend.check_quota(QuotaScope.VOICE_CALLS_SITE_DAY, SITE_SUBJECT)
            assert decision.allowed
        despues = await http.get(f"/api/voice/{aseguradora()}/availability")
        intento = await http.post(f"/api/voice/{aseguradora()}/sessions", json={})

    cuerpo = despues.json()
    assert cuerpo["available"] is False
    assert cuerpo["reason_code"] == "rate_limited_site"
    assert cuerpo["reason_key"] == "voice.availability.rate_limited_site"
    assert intento.status_code == 503, intento.text
    assert intento.json()["code"] == "rate_limited_site"


async def test_mirar_la_pagina_no_gasta_la_llamada_del_dia(app: FastAPI) -> None:
    """Un `GET` que consumiera dejaria sin voz a quien solo abrio la pagina.

    **Con la galleta puesta desde el principio**, y eso es lo que hace que la
    prueba pueda fallar: la galleta del visitante es la misma del chat, asi que
    quien llega a la consola despues de escribir en el chat ya la trae y **si
    tiene contador**. Sin galleta no hay sujeto, el contador no existe y un `GET`
    que consumiera no tendria nada que consumir: la prueba pasaba igual con el
    defecto puesto, y por eso se corrigio.
    """
    galleta = "clave-de-quien-ya-escribio-en-el-chat"
    async with cliente(app) as http:
        http.cookies.set("untangle_visitor", galleta)
        for _ in range(3):
            mirada = await http.get(f"/api/voice/{aseguradora()}/availability")
            assert mirada.status_code == 200, mirada.text
            assert mirada.json()["available"] is True
        abierta = await http.post(f"/api/voice/{aseguradora()}/sessions", json={})

    assert abierta.status_code == 201, abierta.text


async def test_con_los_dos_carriles_agotados_responde_el_de_la_conexion(
    app: FastAPI,
) -> None:
    """El orden importa en lo que la persona lee, y por eso se comprueba por la puerta.

    Es el que puede entender como suyo: "ya hiciste tu llamada de hoy" se arregla
    manana, y "el sitio esta ocupado" no se arregla haciendo nada. Decirle el del
    sitio cuando los dos estan agotados le daria la explicacion que no le sirve.
    """
    async with cliente(app) as http:
        await _agotar_la_conexion(http, aseguradora())

        # El sitio, hasta el borde, con su propia cuota.
        del_sitio = await spend.quota_state(QuotaScope.VOICE_CALLS_SITE_DAY, SITE_SUBJECT)
        for _ in range(del_sitio.remaining):
            assert (await spend.check_quota(QuotaScope.VOICE_CALLS_SITE_DAY, SITE_SUBJECT)).allowed

        segunda = await http.post(f"/api/voice/{aseguradora()}/sessions", json={})

    assert segunda.status_code == 503, segunda.text
    assert segunda.json()["code"] == "rate_limited_daily"


# --- BR1.3: la asimetria de la retoma ----------------------------------------


async def _cortar(tenant_id: str, *, galleta: str) -> None:
    """Deja la llamada viva de ese navegador **cortada y retomable**.

    Se corta como la corta el socket --`DROPPED` con su ventana-- y no colgando:
    colgar es un final a proposito y no deja nada retomable (BR6.1), asi que una
    prueba que colgara estaria sembrando lo contrario de lo que quiere probar.
    """
    viva = await voz.find_live(
        tenant_id=tenant_id, visitor_key_digest=tenancy.visitor_key_digest(galleta)
    )
    assert viva is not None, "no hay llamada viva que cortar"
    await voz.end_call(
        viva,
        reason=voz.EndReason.DROPPED,
        now=datetime.now(UTC),
        resume_window=timedelta(seconds=tenancy.require(tenant_id).call.resume_window_seconds),
    )


async def test_una_retoma_no_gasta_otra_vez_la_llamada_del_dia(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La conexion ya gasto su llamada, y aun asi puede volver a la suya.

    Es la asimetria de BR1.3: una retoma se salta el carril de la conexion --no es
    una llamada nueva, es la misma conversacion-- y **no** se salta el del sitio,
    porque el minuto de audio se gasta igual.

    **Con un techo mayor que el del proyecto**, y por eso se dice: con 5 USD el cupo
    del sitio es de una llamada al dia, asi que la primera se lo lleva y la retoma
    choca contra el carril del sitio --que es la otra prueba, la de abajo--. Lo que
    esta comprueba es la asimetria, y para verla hace falta sitio para dos.
    """
    from .conftest import foto

    async def con_sitio_para_dos(*, now: object = None) -> object:
        del now
        return foto(techo="20.00")

    monkeypatch.setattr(spend, "budget_state", con_sitio_para_dos)

    async with cliente(app) as http:
        primera = await http.post(f"/api/voice/{aseguradora()}/sessions", json={})
        assert primera.status_code == 201, primera.text
        galleta = http.cookies.get("untangle_visitor")
        assert galleta is not None
        await _cortar(aseguradora(), galleta=galleta)

        retomada = await http.post(f"/api/voice/{aseguradora()}/sessions", json={})

    assert retomada.status_code == 201, retomada.text
    # Y vuelve **al mismo caso**: una retoma que abriera otro seria una llamada
    # nueva con otro nombre.
    assert retomada.json()["case_id"] == primera.json()["case_id"]


async def test_una_retoma_si_se_para_cuando_el_sitio_se_agoto(app: FastAPI) -> None:
    """La otra mitad de la asimetria, y la que de verdad protege el presupuesto.

    El carril del sitio se agota a mano --consumiendo su cuota como lo haria
    cualquier otra llamada-- y entonces ni una retoma entra.
    """
    async with cliente(app) as http:
        primera = await http.post(f"/api/voice/{aseguradora()}/sessions", json={})
        assert primera.status_code == 201, primera.text
        galleta = http.cookies.get("untangle_visitor")
        assert galleta is not None
        await _cortar(aseguradora(), galleta=galleta)

        # El sitio, hasta el borde.
        del_sitio = await spend.quota_state(QuotaScope.VOICE_CALLS_SITE_DAY, SITE_SUBJECT)
        for _ in range(del_sitio.remaining):
            decision = await spend.check_quota(QuotaScope.VOICE_CALLS_SITE_DAY, SITE_SUBJECT)
            assert decision.allowed

        retomada = await http.post(f"/api/voice/{aseguradora()}/sessions", json={})

    assert retomada.status_code == 503, retomada.text
    assert retomada.json()["code"] == "rate_limited_site"


# --- BR2.1: el modo lo decide la contabilidad, no la ruta ---------------------


async def test_la_llamada_se_abre_con_el_modo_que_decide_la_contabilidad(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Y no con `primary` escrito a mano, que es lo que habia en cuatro sitios.

    Se dobla **la decision de U5** y se comprueba que la fila de la llamada guarda
    lo que esa decision dijo. Doblarla es la unica forma de verlo: por el
    presupuesto, el respaldo no se alcanza --ver la prueba de abajo, en las
    unitarias de la cuota-- y lo que esta prueba vigila es el cable, no la
    aritmetica.
    """

    async def respaldo(call_id: str, **resto: object) -> VoiceMode:
        del call_id, resto
        return VoiceMode.FALLBACK

    monkeypatch.setattr(spend, "reserve_primary_voice", respaldo)

    async with cliente(app) as http:
        abierta = await http.post(f"/api/voice/{aseguradora()}/sessions", json={})

    assert abierta.status_code == 201, abierta.text
    assert abierta.json()["voice_mode"] == "fallback"


async def test_con_el_presupuesto_justo_la_llamada_entra_con_la_voz_de_respaldo(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El tramo entre las dos reservas, que es donde el arreglo se nota (U17, tanda 2).

    Una llamada con la voz principal cuesta mas que con la de respaldo (la
    sintesis es tres quintos). Con el restante **entre las dos**, el cupo del dia
    --que se calcula con la barata-- deja pasar la llamada, y el modo --que se
    decide con la cara-- responde respaldo. Es exactamente para lo que la voz de
    respaldo existe: que el enlace siga vivo cuando el presupuesto ya no paga la
    voz buena.

    **Las dos reservas se leen de la contabilidad y no se escriben aqui.** Estaban
    escritas (0,098 y 0,072 USD, con 3,45 gastados) y el 2026-10-06 el modelo del
    turno cambio de precio: la reserva subio, el restante escrito quedo por debajo
    de las dos, y esta prueba puso `main` en rojo acusando a un carril que estaba
    bien. Lo que se prueba es el tramo entre las dos, no sus cifras.

    Antes de la tanda 2 las dos preguntas usaban la misma reserva: en este tramo el
    carril se cerraba y la voz de respaldo no sonaba nunca. **Esta prueba se cae el
    dia que alguien vuelva a usar la misma en las dos.**
    """
    from .conftest import foto

    principal = spend.call_reserve(VoiceMode.PRIMARY).reserve.amount_usd
    respaldo = spend.call_reserve(VoiceMode.FALLBACK).reserve.amount_usd
    grabacion = spend.recording_reserve_usd().amount_usd
    assert principal is not None and respaldo is not None and grabacion is not None
    assert respaldo < principal, "sin tramo entre las dos reservas no hay nada que probar"
    techo = Decimal("5.00")
    # El restante publico queda justo a mitad de camino entre las dos reservas.
    gastado = techo - grabacion - (principal + respaldo) / 2

    async def entre_las_dos_reservas(*, now: object = None) -> object:
        del now
        return foto(gastado=str(gastado), techo=str(techo))

    monkeypatch.setattr(spend, "budget_state", entre_las_dos_reservas)

    async with cliente(app) as http:
        disponible = await http.get(f"/api/voice/{aseguradora()}/availability")
        abierta = await http.post(f"/api/voice/{aseguradora()}/sessions", json={})

    assert disponible.status_code == 200, disponible.text
    assert disponible.json()["available"] is True, "el carril se cerro teniendo con que pagar"
    assert disponible.json()["voice_mode"] == "fallback"
    assert abierta.status_code == 201, abierta.text
    assert abierta.json()["voice_mode"] == "fallback"


async def test_la_disponibilidad_avisa_del_modo_antes_de_llamar(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La consola avisa de que la voz puede sonar distinta **antes** del boton.

    Con el presupuesto ilegible --el unico camino por el que hoy se llega al
    respaldo-- la disponibilidad lo dice, y la voz queda cerrada por el techo: las
    dos cosas a la vez, que es "cerrado ante la duda para lo que cuesta dinero".
    """

    async def ilegible(*, now: object = None) -> object:
        del now
        msg = "la base no responde"
        raise RuntimeError(msg)

    monkeypatch.setattr(spend, "budget_state", ilegible)

    cuerpo = await _disponibilidad(app)

    assert cuerpo["voice_mode"] == "fallback"
    assert cuerpo["available"] is False
    assert cuerpo["reason_code"] == "budget_exhausted"
