"""Las tres rutas de C-08 por HTTP, con la base efimera de verdad.

Se llama a la aplicacion con un cliente ASGI en el **mismo** bucle de eventos que
la base, por la razon que U6 dejo escrita: el cliente sincrono corre la
aplicacion en otro hilo con otro bucle y el grupo de conexiones no se comparte.

Lo que aqui se comprueba es lo que solo se ve por la puerta:

- que la disponibilidad responde **sin crear nada** --un navegador que solo mira
  no deja fila-- y dentro de su presupuesto de C-08;
- que el objeto `transport` llega concreto, con el unico formato del aplicativo,
  y que el token **no** viaja en la URL (BR1.4);
- que la llamada de otro navegador responde igual que una que no existe;
- que el cuerpo de abrir **no** admite un caso: nombrar un caso ajeno es el
  agujero que cierra el criterio `[bloquea]` AC1.27.3.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx2
import pytest
from fastapi import FastAPI

from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey
from untangle.providers.ports import SPEECH_AUDIO
from untangle.server import composition, voice_routes
from untangle.settings import Settings
from untangle.telemetry.spend import api as spend
from untangle.telemetry.spend import budget
from untangle.telemetry.spend.models import BudgetWindow
from untangle.telemetry.traces import api as trazas
from untangle.tenancy import api as tenancy
from untangle.tenancy import ephemeral, session
from untangle.voice import api as voz

pytestmark = pytest.mark.usefixtures("base_de_u16")

CLAVE_DE_ENLACES = "marca-de-clave-de-enlaces-que-no-debe-salir-000016"
#: La del token de socket, otra a proposito (PENDIENTES 1.16).
CLAVE_DEL_SOCKET = "marca-de-clave-del-token-de-voz-que-no-sale-000016"

#: Los presupuestos de C-08, en milisegundos. No se miden contra un proveedor:
#: estas rutas no llaman a ninguno, y lo que se vigila aqui es que ninguna se
#: vaya a la base mas veces de las que necesita.
PRESUPUESTO_DISPONIBILIDAD_MS = 300
PRESUPUESTO_SESION_MS = 1000


def _foto_abierta() -> object:
    """Una foto del presupuesto con el acumulado en cero, con la aritmetica de U5.

    **Con su reserva de grabacion convertida**, y eso no es decoracion: sin ella el
    restante publico sale `not_measured` --no se puede restar lo que no se sabe
    cuanto es-- y desde que U17 cablea los carriles, un restante sin medir cierra el
    carril del sitio. Estas pruebas miran el transporte, el token y el aislamiento;
    con el carril cerrado no llegarian a abrir ninguna llamada.
    """
    inicio = datetime(2026, 9, 16, tzinfo=UTC).date()
    return budget.state(
        BudgetWindow(
            window_start=inicio,
            window_end=inicio + timedelta(days=90),
            billable_spent_usd=Decimal("0"),
            unmeasured_billable_calls=0,
            recording_reserve_usd=spend.recording_reserve_usd().amount_usd,
            recording_reserve_status=spend.recording_reserve_usd().status,
            updated_at=datetime(2026, 9, 29, 12, 0, tzinfo=UTC),
        )
    )


@pytest.fixture
async def app(
    sesiones: ephemeral.EphemeralDatabase,
    demo_abierta: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[FastAPI]:
    ajustes = Settings(
        env="local",
        database_url=sesiones.app_url,
        commit_sha="abc1234",
        case_link_signing_key=CLAVE_DE_ENLACES,
        voice_token_signing_key=CLAVE_DEL_SOCKET,
    )
    construida = composition.build_app(ajustes, dist_dir=tmp_path)

    async def presupuesto_abierto(*, now: datetime | None = None) -> object:
        del now
        return _foto_abierta()

    monkeypatch.setattr(spend, "budget_state", presupuesto_abierto)
    try:
        yield construida
    finally:
        await session.dispose()
        session.configure(sesiones.app_url)
        spend.reset()
        trazas.reset_summaries()
        copy_api.reset()
        voice_routes.reset()


def _cliente(app: FastAPI) -> httpx2.AsyncClient:
    """Un navegador. **Sobre `https`**, y eso no es decoracion.

    La galleta del visitante se pone con `Secure`, asi que un cliente en `http`
    la recibe y no la vuelve a mandar nunca: colgar respondia 404 porque el
    servidor no sabia de quien era la llamada. Es el mismo modo de fallo que en
    produccion no puede pasar --el origen es seguro-- y que una prueba sobre
    `http` convertiria en un 404 que parece aislamiento.
    """
    transporte = httpx2.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx2.AsyncClient(transport=transporte, base_url="https://testserver")


def _aseguradora() -> str:
    return tenancy.available_ids()[0]


async def _contar_llamadas(tenant_id: str) -> int:
    async with session.session_for(tenant_id) as sesion:
        fila = await session.fetch_one(sesion, "SELECT count(*) AS total FROM call_session")
    return int(fila["total"]) if fila is not None else 0


# --- La disponibilidad (BR1.1) ------------------------------------------------


async def test_la_disponibilidad_trae_el_modo_y_los_limites(app: FastAPI) -> None:
    """Con eso la consola dibuja el estado real antes de ofrecer el boton."""
    async with _cliente(app) as cliente:
        respuesta = await cliente.get(f"/api/voice/{_aseguradora()}/availability")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["available"] is True
    assert cuerpo["voice_mode"] == "primary"
    limites = cuerpo["limits"]
    config = tenancy.require(_aseguradora()).call
    assert limites["max_call_seconds"] == config.max_call_seconds
    assert limites["warn_at_seconds"] == config.warn_at_seconds


async def test_los_carriles_diarios_viajan_con_el_numero_que_se_aplica(app: FastAPI) -> None:
    """P7, del otro lado: lo que esta construido **si** se promete.

    Hasta la tanda 2 de U17 estos dos salian nulos y esta prueba exigia que
    salieran nulos, con su razon escrita: nadie los hacia cumplir, y servir un
    numero habria dicho que habia un limite que no existia. Ahora los aplica la
    apertura --consumiendo la cuota de U5-- asi que el numero viaja.

    El del sitio es el **cupo de hoy** y no el tope escrito: se deriva del
    presupuesto que queda (BR5.6), y es el que la apertura va a aplicar. Servir el
    tope prometeria llamadas que no caben.
    """
    async with _cliente(app) as cliente:
        cuerpo = (await cliente.get(f"/api/voice/{_aseguradora()}/availability")).json()

    limites = cuerpo["limits"]
    assert (
        limites["calls_per_visitor_day"] == spend.current_runtime().voice_calls_per_visitor_per_day
    )
    assert limites["calls_per_site_day"] is not None
    assert limites["calls_per_site_day"] >= 1, "sin cupo del sitio no se ofreceria el boton"


async def test_mirar_la_disponibilidad_no_crea_ninguna_fila(app: FastAPI) -> None:
    """Un navegador que solo mira no deja rastro en ninguna tabla."""
    antes = await _contar_llamadas(_aseguradora())

    async with _cliente(app) as cliente:
        respuesta = await cliente.get(f"/api/voice/{_aseguradora()}/availability")

    assert respuesta.status_code == 200
    assert "set-cookie" not in {n.lower() for n in respuesta.headers}
    assert await _contar_llamadas(_aseguradora()) == antes


async def test_la_disponibilidad_cabe_en_su_presupuesto(app: FastAPI) -> None:
    """C-08 le da 300 ms. Se mide la ruta entera, con base y todo."""
    async with _cliente(app) as cliente:
        await cliente.get(f"/api/voice/{_aseguradora()}/availability")  # calienta el grupo
        inicio = time.perf_counter()
        await cliente.get(f"/api/voice/{_aseguradora()}/availability")
        transcurrido_ms = (time.perf_counter() - inicio) * 1000

    assert transcurrido_ms < PRESUPUESTO_DISPONIBILIDAD_MS


async def test_un_presupuesto_ilegible_cierra_la_voz_y_manda_una_clave(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un fallo de lectura del techo cierra, igual que en la compuerta de U15.

    Y lo que viaja es la **clave** del catalogo, nunca la frase: una frase
    resuelta en los dos lados acaba diciendose de dos maneras.
    """

    async def no_se_puede_leer(*, now: datetime | None = None) -> object:
        del now
        msg = "la base no responde"
        raise RuntimeError(msg)

    monkeypatch.setattr(spend, "budget_state", no_se_puede_leer)

    async with _cliente(app) as cliente:
        cuerpo = (await cliente.get(f"/api/voice/{_aseguradora()}/availability")).json()

    assert cuerpo["available"] is False
    assert cuerpo["reason_code"] == "budget_exhausted"
    assert cuerpo["reason_key"] == "spend.quota.budget_exhausted"
    # Y la frase **no** viaja: lo que la consola resuelve es la clave.
    frase = copy_api.t(CopyKey("spend.quota.budget_exhausted"), locale="en")
    assert frase not in repr(cuerpo)


async def test_con_el_techo_cerrado_la_disponibilidad_lo_dice(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Y con la misma clave del catalogo que el corte de la llamada.

    Va aparte de la del presupuesto ilegible: son dos causas distintas del mismo
    resultado, y con una sola prueba la otra se queda sin ninguna. Se comprobo
    quitando la consulta del techo y viendo que solo se caia una.
    """

    async def techo_cerrado(*, now: datetime | None = None) -> object:
        del now
        inicio = datetime(2026, 9, 16, tzinfo=UTC).date()
        return budget.state(
            BudgetWindow(
                window_start=inicio,
                window_end=inicio + timedelta(days=90),
                billable_spent_usd=Decimal("5.00"),
                # El techo que esta prueba agota, fijado: el por omision es 40 desde
                # el 2026-10-07.
                cap_usd=Decimal("5.00"),
                alert_usd=Decimal("3.00"),
                unmeasured_billable_calls=0,
                updated_at=datetime(2026, 9, 29, 12, 0, tzinfo=UTC),
            )
        )

    monkeypatch.setattr(spend, "budget_state", techo_cerrado)

    async with _cliente(app) as cliente:
        cuerpo = (await cliente.get(f"/api/voice/{_aseguradora()}/availability")).json()

    assert cuerpo["available"] is False
    assert cuerpo["reason_code"] == "budget_exhausted"
    assert cuerpo["reason_key"] == "spend.quota.budget_exhausted"


async def test_una_aseguradora_que_no_existe_responde_con_la_forma_de_c01(app: FastAPI) -> None:
    async with _cliente(app) as cliente:
        respuesta = await cliente.get("/api/voice/no-existe/availability")

    assert respuesta.status_code == 404
    assert respuesta.json()["code"] == "not_found"


# --- Abrir la llamada ---------------------------------------------------------


async def test_abrir_devuelve_el_transporte_concreto(app: FastAPI) -> None:
    """C-29 cerrado: un socket del mismo origen con el unico formato del aplicativo."""
    async with _cliente(app) as cliente:
        respuesta = await cliente.post(
            f"/api/voice/{_aseguradora()}/sessions", json={"language": "en"}
        )

    assert respuesta.status_code == 201
    transporte = respuesta.json()["transport"]
    assert transporte["kind"] == "websocket"
    assert transporte["url"] == f"/api/voice/{_aseguradora()}/socket"
    assert transporte["encoding"] == SPEECH_AUDIO.encoding.value
    assert transporte["sample_rate_hz"] == SPEECH_AUDIO.sample_rate_hz
    assert transporte["channels"] == SPEECH_AUDIO.channels
    assert transporte["frame_ms"] == voice_routes.FRAME_MS


async def test_el_token_no_viaja_en_la_url(app: FastAPI) -> None:
    """BR1.4. Un token en la cadena de consulta acaba en los registros del
    servidor y en el historial del navegador, y de ahi no se saca."""
    async with _cliente(app) as cliente:
        transporte = (
            await cliente.post(f"/api/voice/{_aseguradora()}/sessions", json={"language": "en"})
        ).json()["transport"]

    assert transporte["token"]
    assert transporte["token"] not in transporte["url"]
    assert "?" not in transporte["url"]


async def test_abrir_deja_la_llamada_con_su_caso(app: FastAPI) -> None:
    """El caso nace antes de la primera palabra: la divulgacion se registra
    contra el y va antes de cualquier pregunta (BR2.1, BR2.3)."""
    async with _cliente(app) as cliente:
        cuerpo = (
            await cliente.post(f"/api/voice/{_aseguradora()}/sessions", json={"language": "en"})
        ).json()

    assert cuerpo["case_id"] is not None
    viva = await voz.find_live(
        tenant_id=_aseguradora(),
        visitor_key_digest=(await _digest_del_unico_visitante(_aseguradora())),
    )
    assert viva is not None
    assert viva.case_id == cuerpo["case_id"]


async def _digest_del_unico_visitante(tenant_id: str) -> str:
    async with session.session_for(tenant_id) as sesion:
        fila = await session.fetch_one(
            sesion, "SELECT visitor_key_digest FROM call_session LIMIT 1"
        )
    assert fila is not None
    return str(fila["visitor_key_digest"])


async def test_el_cuerpo_de_abrir_no_admite_un_caso(app: FastAPI) -> None:
    """El criterio `[bloquea]` AC1.27.3, en la puerta.

    C-08 declaraba `case_id` para retomar. Aceptarlo dejaria que quien llama
    **nombre** un caso, y la poliza de ejemplo es publica: cualquiera podria
    abrir el de otra persona.

    El campo no se ignora: el cuerpo lo **rechaza**, porque los modelos de este
    proyecto no admiten campos de mas. Ignorarlo habria dejado a la consola
    creyendo que la retoma se pide asi, y a la siguiente persona que lea el
    contrato pensando que el campo hace algo.
    """
    antes = await _contar_llamadas(_aseguradora())

    async with _cliente(app) as cliente:
        respuesta = await cliente.post(
            f"/api/voice/{_aseguradora()}/sessions",
            json={"language": "en", "case_id": "case-de-otra-persona"},
        )

    assert respuesta.status_code == 422
    assert await _contar_llamadas(_aseguradora()) == antes


async def test_abrir_cabe_en_su_presupuesto(app: FastAPI) -> None:
    """C-08 le da un segundo: abre la llamada, el caso y firma el token."""
    async with _cliente(app) as cliente:
        await cliente.post(f"/api/voice/{_aseguradora()}/sessions", json={"language": "en"})
        inicio = time.perf_counter()
        await cliente.post(f"/api/voice/{_aseguradora()}/sessions", json={"language": "en"})
        transcurrido_ms = (time.perf_counter() - inicio) * 1000

    assert transcurrido_ms < PRESUPUESTO_SESION_MS


async def test_con_el_techo_cerrado_no_se_abre_ninguna_llamada(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """503 y **ninguna fila**: cobrar por una llamada que no se va a atender es
    justo lo que el techo existe para evitar."""

    async def techo_cerrado(*, now: datetime | None = None) -> object:
        del now
        inicio = datetime(2026, 9, 16, tzinfo=UTC).date()
        return budget.state(
            BudgetWindow(
                window_start=inicio,
                window_end=inicio + timedelta(days=90),
                billable_spent_usd=Decimal("5.00"),
                # El techo que esta prueba agota, fijado: el por omision es 40 desde
                # el 2026-10-07.
                cap_usd=Decimal("5.00"),
                alert_usd=Decimal("3.00"),
                unmeasured_billable_calls=0,
                updated_at=datetime(2026, 9, 29, 12, 0, tzinfo=UTC),
            )
        )

    monkeypatch.setattr(spend, "budget_state", techo_cerrado)
    antes = await _contar_llamadas(_aseguradora())

    async with _cliente(app) as cliente:
        respuesta = await cliente.post(
            f"/api/voice/{_aseguradora()}/sessions", json={"language": "en"}
        )

    assert respuesta.status_code == 503
    assert respuesta.json()["code"] == "budget_exhausted"
    assert await _contar_llamadas(_aseguradora()) == antes


# --- Cerrar la llamada --------------------------------------------------------


async def test_colgar_desde_fuera_termina_la_llamada(app: FastAPI) -> None:
    async with _cliente(app) as cliente:
        abierta = (
            await cliente.post(f"/api/voice/{_aseguradora()}/sessions", json={"language": "en"})
        ).json()
        respuesta = await cliente.delete(
            f"/api/voice/{_aseguradora()}/sessions/{abierta['call_id']}"
        )

    assert respuesta.status_code == 204
    assert (
        await voz.find_live(
            tenant_id=_aseguradora(),
            visitor_key_digest=await _digest_del_unico_visitante(_aseguradora()),
        )
        is None
    )


async def test_la_llamada_de_otro_navegador_responde_como_una_que_no_existe(
    app: FastAPI,
) -> None:
    """CD-10. Y **no la termina**: si respondiera 404 despues de cerrarla, el
    aislamiento seria una pantalla y no una compuerta.

    **El segundo navegador abre su propia llamada antes de intentarlo**, y esa
    linea es la prueba. Sin ella llega sin galleta, se le niega por no tener
    clave que resolver, y la prueba pasa igual con la comprobacion de a quien
    pertenece la llamada **quitada**: se comprobo rompiendola y quedandose en
    verde. Con su propia llamada abierta, lo unico que lo separa del caso ajeno
    es esa comprobacion.
    """
    async with _cliente(app) as primero:
        abierta = (
            await primero.post(f"/api/voice/{_aseguradora()}/sessions", json={"language": "en"})
        ).json()

    async with _cliente(app) as otro:
        await otro.post(f"/api/voice/{_aseguradora()}/sessions", json={"language": "en"})
        respuesta = await otro.delete(f"/api/voice/{_aseguradora()}/sessions/{abierta['call_id']}")

    assert respuesta.status_code == 404
    assert respuesta.json()["code"] == "not_found"
    # La del primero sigue viva: no se la llevo por delante el intento del otro.
    async with session.session_for(_aseguradora()) as sesion:
        fila = await session.fetch_one(
            sesion,
            "SELECT state FROM call_session WHERE call_id = :call_id",
            call_id=abierta["call_id"],
        )
    assert fila is not None
    assert fila["state"] != "ended"


async def test_un_identificador_inventado_responde_igual(app: FastAPI) -> None:
    async with _cliente(app) as cliente:
        await cliente.post(f"/api/voice/{_aseguradora()}/sessions", json={"language": "en"})
        respuesta = await cliente.delete(f"/api/voice/{_aseguradora()}/sessions/call-inventada")

    assert respuesta.status_code == 404
