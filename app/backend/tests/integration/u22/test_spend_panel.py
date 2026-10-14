"""El tablero de gasto servido, contra la base (U22; publico desde el 2026-10-09).

Lo que se prueba aqui es lo que un doble no tiene: el registro de gasto **de
verdad**, con sus agregaciones en SQL y los casos que existen. Las pruebas de la
pantalla viven en el navegador; aqui se mira **la respuesta del servidor**.

Lo que no se puede hacer mal, y donde se ejerce:

1. **Ningun caso se identifica** en una superficie publica:
   `test_los_casos_salen_descritos_sin_identificador_ni_numero`.
2. **Lo de una llamada es de la llamada**, sea cual sea su uso:
   `test_la_actividad_de_cada_fila_sale_de_su_uso_y_de_su_llamada`.
3. **El tablero no decide cortar** (BR3.3): `test_el_estado_es_el_de_la_contabilidad...`.
4. **Ninguna cifra sin medir se escribe como cero** (BR1.2, BR3.5): el conteo de
   consultas sin precio viaja con cada total y `window` es nulo si no hay ventana.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi import FastAPI

from untangle.base import ProviderName, Use
from untangle.case_record import api as casos
from untangle.case_record.models import Channel, RecordType
from untangle.chat import opening
from untangle.server import spend_routes
from untangle.telemetry.spend import budget, repository
from untangle.telemetry.spend.models import WINDOW_START
from untangle.tenancy import api as tenancy
from untangle.tenancy import session

from .conftest import (
    OCTUBRE,
    SEPTIEMBRE,
    cliente,
    conversacion_del_navegador,
    crear_caso,
    gasto,
    registrar,
    sembrar_ventana,
)

#: Marcas reconocibles: si alguna aparece en la respuesta, el tablero identifico
#: un caso.
CASO_A = "caso-secreto-a-7f3c"
CASO_B = "caso-secreto-b-91de"

HOY = datetime.now(UTC).replace(hour=12, minute=0, second=0, microsecond=0)


def _total(cuerpo: dict[str, Any]) -> tuple[Decimal, int]:
    return Decimal(cuerpo["measured_usd"]), cuerpo["unmeasured_count"]


async def _panel(app: FastAPI, cookies: dict[str, str] | None = None) -> dict[str, Any]:
    spend_routes.reset_cache()
    async with cliente(app, cookies) as c:
        respuesta = await c.get("/api/spend")
    assert respuesta.status_code == 200
    return respuesta.json()  # type: ignore[no-any-return]


async def _sembrar_actividades() -> tuple[str, str]:
    """Una llamada, un chat, una prueba de calidad y una lectura sin precio.

    | fila | uso | llamada | actividad | medido | sin precio |
    | --- | --- | --- | --- | --- | --- |
    | V-1 | voice | call-1 | calls | 0,20 | |
    | V-2 | chat_reply | call-1 | calls | 0,05 | |
    | C-1 | chat_reply | | chat | 0,10 | |
    | E-1 | evals_chat | | quality_tests | 0,30 | |
    | L-1 | corpus | | policy_reading | | 1 |
    """
    await sembrar_ventana()
    a, b = sorted(tenancy.available_ids())[:2]
    await crear_caso(a, CASO_A, channel=Channel.VOICE)
    await crear_caso(b, CASO_B, record_type=RecordType.COVERAGE_INQUIRY)
    await registrar(
        gasto(
            "V-1",
            costo=Decimal("0.20"),
            proveedor=ProviderName.CARTESIA,
            use=Use.VOICE,
            call_ref="call-1",
            case_ref=CASO_A,
            tenant_ref=a,
            occurred_at=HOY,
        )
    )
    await registrar(
        gasto(
            "V-2",
            costo=Decimal("0.05"),
            proveedor=ProviderName.ANTHROPIC,
            use=Use.CHAT_REPLY,
            call_ref="call-1",
            case_ref=CASO_A,
            tenant_ref=a,
            occurred_at=HOY,
        )
    )
    await registrar(
        gasto(
            "C-1",
            costo=Decimal("0.10"),
            proveedor=ProviderName.ANTHROPIC,
            use=Use.CHAT_REPLY,
            case_ref=CASO_B,
            tenant_ref=b,
            occurred_at=HOY - timedelta(days=1),
        )
    )
    await registrar(
        gasto(
            "E-1",
            costo=Decimal("0.30"),
            proveedor=ProviderName.ANTHROPIC,
            use=Use.EVALS_CHAT,
            occurred_at=SEPTIEMBRE,
        )
    )
    await registrar(
        gasto("L-1", costo=None, use=Use.CORPUS, case_ref=CASO_B, tenant_ref=b, occurred_at=HOY)
    )
    return a, b


async def test_el_tablero_es_publico_y_no_pide_ninguna_credencial(app: FastAPI) -> None:
    await _sembrar_actividades()
    async with cliente(app) as c:
        respuesta = await c.get("/api/spend")

    assert respuesta.status_code == 200
    assert respuesta.headers["cache-control"] == "private, no-store"
    publicas = {s.value for s in app.state.surfaces.public_mounted()}
    assert "spend_panel" in publicas


async def test_la_actividad_de_cada_fila_sale_de_su_uso_y_de_su_llamada(app: FastAPI) -> None:
    await _sembrar_actividades()
    cuerpo = await _panel(app)

    actividades = {a["activity"]: _total(a["total"]) for a in cuerpo["by_activity"]}
    # El modelo que entendio dentro de la llamada (V-2) es de la llamada, no del chat.
    assert actividades == {
        "calls": (Decimal("0.25"), 0),
        "chat": (Decimal("0.10"), 0),
        "quality_tests": (Decimal("0.30"), 0),
        "policy_reading": (Decimal(0), 1),
    }
    assert _total(cuerpo["total"]) == (Decimal("0.65"), 1)


async def test_la_grafica_tiene_los_ultimos_30_dias_y_cada_dia_su_gasto(app: FastAPI) -> None:
    await _sembrar_actividades()
    dias = (await _panel(app))["by_day"]

    assert len(dias) == spend_routes.DAYS
    assert dias[-1]["day"] == HOY.date().isoformat()
    hoy = {a["activity"]: _total(a["total"]) for a in dias[-1]["activities"]}
    ayer = {a["activity"]: _total(a["total"]) for a in dias[-2]["activities"]}
    assert hoy["calls"] == (Decimal("0.25"), 0)
    assert ayer == {"chat": (Decimal("0.10"), 0)}


async def test_las_llamadas_y_los_chats_dicen_cuanto_costaron_y_cuantos_fueron(
    app: FastAPI,
) -> None:
    await _sembrar_actividades()
    cuerpo = await _panel(app)

    assert cuerpo["calls"]["count"] == 1
    assert _total(cuerpo["calls"]["total"]) == (Decimal("0.25"), 0)
    # Y cada proveedor dice con que modelo trabajo: el que se cobro en la fila.
    modelos = {p["provider"]: [m["model"] for m in p["models"]] for p in cuerpo["by_provider"]}
    assert modelos["cartesia"] == ["aura-2"]
    assert modelos["gemini"] == ["gemini-3.1-flash-lite"]
    assert cuerpo["chats"]["count"] == 1
    assert _total(cuerpo["chats"]["total"]) == (Decimal("0.10"), 0)


async def test_los_casos_salen_descritos_sin_identificador_ni_numero(app: FastAPI) -> None:
    a, b = await _sembrar_actividades()
    numeros = []
    for tenant, caso in ((a, CASO_A), (b, CASO_B)):
        vista = await casos.get_case(tenant, caso)
        assert vista is not None
        numeros.append(str(vista.case_number))
    spend_routes.reset_cache()
    async with cliente(app) as c:
        respuesta = await c.get("/api/spend")

    texto = respuesta.text
    for marca in (CASO_A, CASO_B, *numeros):
        assert marca not in texto, marca
    por_tipo = {c["record_type"]: c for c in respuesta.json()["cases"]}
    assert set(por_tipo) == {"claim", "coverage_inquiry"}
    llamada = por_tipo["claim"]
    assert llamada["channel"] == "voice"
    assert _total(llamada["total"]) == (Decimal("0.25"), 0)
    assert {p["provider"] for p in llamada["by_provider"]} == {"cartesia", "anthropic"}
    # La prueba de calidad no es un caso de nadie: no sale en la lista.
    assert all(Decimal(c["total"]["measured_usd"]) != Decimal("0.30") for c in por_tipo.values())


async def test_un_caso_borrado_no_sale_en_la_lista_pero_su_gasto_sigue_contando(
    app: FastAPI,
) -> None:
    a, _ = await _sembrar_actividades()
    async with session.session_for(a) as sesion:
        await session.execute_sql(sesion, "DELETE FROM case_record WHERE case_id = :c", c=CASO_A)
    cuerpo = await _panel(app)

    assert [c["record_type"] for c in cuerpo["cases"]] == ["coverage_inquiry"]
    assert _total(cuerpo["total"]) == (Decimal("0.65"), 1)


async def test_el_caso_de_este_navegador_sale_como_suyo_y_el_de_otro_no(app: FastAPI) -> None:
    _, b = await _sembrar_actividades()
    await conversacion_del_navegador(b, CASO_B, "clave-de-este-navegador")

    mio = await _panel(app, {"untangle_visitor": "clave-de-este-navegador"})
    ajeno = await _panel(app, {"untangle_visitor": "clave-de-otro-navegador"})

    suyos = {c["record_type"]: c["yours"] for c in mio["cases"]}
    assert suyos == {"coverage_inquiry": True, "claim": False}
    assert not any(c["yours"] for c in ajeno["cases"])


# --- Lo que no tiene precio se muestra en tokens (2026-10-11) ----------------------


async def test_los_tokens_de_lo_que_no_tiene_precio_salen_por_proveedor_actividad_y_caso(
    app: FastAPI,
) -> None:
    await sembrar_ventana()
    a = sorted(tenancy.available_ids())[0]
    await crear_caso(a, CASO_A, record_type=RecordType.COVERAGE_INQUIRY)
    # Dos lecturas de poliza en plan gratuito, con recuento (200.000 tokens cada una),
    # y una llamada que salio y no volvio: existe, y no se sabe cuanto consumio.
    for numero in (1, 2):
        await registrar(
            gasto(
                f"T-{numero}",
                costo=None,
                use=Use.CORPUS,
                case_ref=CASO_A,
                tenant_ref=a,
                billable=False,
                occurred_at=HOY,
            )
        )
    sin_recuento = gasto(
        "T-3", costo=None, use=Use.CORPUS, case_ref=CASO_A, tenant_ref=a, billable=False
    )
    await registrar(sin_recuento.model_copy(update={"units": Decimal(0), "occurred_at": HOY}))

    cuerpo = await _panel(app)

    (gemini,) = cuerpo["by_provider"]
    esperado = {"tokens": 400000, "uncounted": 1, "free_plan": True}
    assert gemini["unpriced"] == esperado
    lectura = next(x for x in cuerpo["by_activity"] if x["activity"] == "policy_reading")
    assert lectura["unpriced"] == esperado
    (caso,) = cuerpo["cases"]
    assert caso["unpriced"] == esperado
    assert caso["by_provider"][0]["unpriced"] == esperado
    # Los tokens no son dinero: el importe sigue en cero con sus tres sin precio.
    assert _total(caso["total"]) == (Decimal(0), 3)


async def test_un_solo_recuento_de_pago_sin_precio_quita_el_plan_gratuito(app: FastAPI) -> None:
    await sembrar_ventana()
    await registrar(gasto("G-1", costo=None, use=Use.CORPUS, billable=False, occurred_at=HOY))
    await registrar(gasto("G-2", costo=None, use=Use.VOICE, billable=True, occurred_at=HOY))

    (gemini,) = (await _panel(app))["by_provider"]

    assert gemini["unpriced"] == {"tokens": 400000, "uncounted": 0, "free_plan": False}


async def test_lo_que_tiene_precio_no_cuenta_como_sin_precio(app: FastAPI) -> None:
    await sembrar_ventana()
    await registrar(gasto("P-1", costo=Decimal("0.05"), billable=False, occurred_at=HOY))

    (gemini,) = (await _panel(app))["by_provider"]

    assert gemini["unpriced"] == {"tokens": 0, "uncounted": 0, "free_plan": False}


# --- Una comparacion es una sola cosa (2026-10-11) ---------------------------------

MIA = "clave-de-este-navegador"
OTRA = "clave-de-otro-navegador"
TERCERA = "clave-de-un-tercero"


async def _caso_de_navegador(
    tenant: str, case_id: str, clave: str, *, desde: str, gastado: str = "0.01"
) -> None:
    """Un caso con su conversacion, su divulgacion y un gasto, como lo deja el chat."""
    await crear_caso(tenant, case_id, record_type=RecordType.COVERAGE_INQUIRY)
    await conversacion_del_navegador(tenant, case_id, clave)
    await opening.record(
        tenant_id=tenant, case_id=case_id, language="es", catalog_key=desde, now=HOY
    )
    await registrar(
        gasto(
            f"G-{case_id}",
            costo=Decimal(gastado),
            case_ref=case_id,
            tenant_ref=tenant,
            occurred_at=HOY,
            billable=False,
        )
    )


async def test_las_consultas_de_un_clic_en_comparar_salen_juntas_y_el_resto_aparte(
    app: FastAPI,
) -> None:
    await sembrar_ventana()
    uno, dos, tres = sorted(tenancy.available_ids())[:3]
    comparacion = opening.COMPARISON_DISCLOSURE_BLOCK
    for tenant, case_id in ((uno, "cmp-1"), (dos, "cmp-2"), (tres, "cmp-3")):
        await _caso_de_navegador(tenant, case_id, MIA, desde=comparacion)
    # Otro navegador compara con una sola aseguradora, y un tercero chatea.
    await _caso_de_navegador(uno, "cmp-4", OTRA, desde=comparacion)
    await _caso_de_navegador(dos, "suelto", TERCERA, desde=str(opening.DISCLOSURE))

    spend_routes.reset_cache()
    async with cliente(app, {"untangle_visitor": MIA}) as c:
        respuesta = await c.get("/api/spend")
    cuerpo = respuesta.json()

    por_partes = sorted(cuerpo["comparisons"], key=lambda x: len(x["parts"]))
    assert [len(x["parts"]) for x in por_partes] == [1, 3]
    triple = por_partes[1]
    assert sorted(p["tenant_id"] for p in triple["parts"]) == sorted([uno, dos, tres])
    assert _total(triple["total"]) == (Decimal("0.03"), 0)
    # Es mia la comparacion del navegador que lleva mi galleta, y solo esa.
    assert [x["yours"] for x in por_partes] == [False, True]
    # El chat que no salio de la comparacion queda como caso suelto, y no se pierde.
    assert [x["tenant_id"] for x in cuerpo["cases"]] == [dos]
    for marca in ("cmp-1", "cmp-4", "suelto", tenancy.visitor_key_digest(MIA)):
        assert marca not in respuesta.text, marca


async def test_la_comparacion_se_agrupa_tambien_si_el_navegador_cerro_su_conversacion(
    app: FastAPI,
) -> None:
    await sembrar_ventana()
    uno, dos, _ = sorted(tenancy.available_ids())[:3]
    for tenant, case_id in ((uno, "cmp-1"), (dos, "cmp-2")):
        await _caso_de_navegador(tenant, case_id, MIA, desde=opening.COMPARISON_DISCLOSURE_BLOCK)
    # "Empezar de cero": la conversacion se cierra y el caso queda con su numero.
    async with session.session_for(uno) as sesion:
        await session.execute_sql(sesion, "UPDATE chat_session SET closed_at = now()")

    (comparacion,) = (await _panel(app))["comparisons"]

    assert len(comparacion["parts"]) == 2


# --- Lo que no hay no se escribe como cero ---------------------------------------


async def test_sin_fila_de_ventana_el_tablero_dice_que_no_hay_ventana_y_no_un_cero(
    app: FastAPI,
) -> None:
    await registrar(gasto("G-LIBRE", costo=Decimal("0.01"), billable=False))
    cuerpo = await _panel(app)

    assert cuerpo["window"] is None
    assert cuerpo["alert_sent_at"] is None
    assert [fila["provider"] for fila in cuerpo["by_provider"]] == ["gemini"]


async def test_sin_ningun_gasto_las_listas_van_vacias(app: FastAPI) -> None:
    await sembrar_ventana()
    cuerpo = await _panel(app)

    assert cuerpo["by_provider"] == []
    assert cuerpo["by_activity"] == []
    assert cuerpo["cases"] == []
    assert cuerpo["calls"]["count"] == 0
    assert all(dia["activities"] == [] for dia in cuerpo["by_day"])


# --- BR3.3: el tablero muestra lo decidido, no decide -----------------------------


@pytest.mark.parametrize(
    ("situacion", "ventana", "esperado"),
    [
        ("por debajo de la alerta", {"gastado": Decimal("1.00")}, "ok"),
        ("pasada la alerta", {"gastado": Decimal("3.20")}, "alerted"),
        ("techo alcanzado", {"gastado": Decimal("4.90")}, "exhausted"),
        ("reserva sin medir", {"gastado": Decimal("1.00"), "reserva": None}, "unmeasured"),
        ("llamada sin valorar", {"gastado": Decimal("1.00"), "sin_valorar": 1}, "unmeasured"),
    ],
)
async def test_el_estado_es_el_de_la_contabilidad_y_no_una_cuenta_del_tablero(
    app: FastAPI, situacion: str, ventana: dict[str, Any], esperado: str
) -> None:
    await sembrar_ventana(**ventana)

    servido = (await _panel(app))["window"]
    decidido = budget.state(await _ventana_guardada()).status

    assert servido["status"] == decidido.value == esperado, situacion


async def test_el_tablero_solo_lee_no_mueve_el_acumulado_ni_escribe_filas(app: FastAPI) -> None:
    await _sembrar_actividades()
    antes = await _ventana_guardada()
    for _ in range(3):
        await _panel(app)
    despues = await _ventana_guardada()

    assert despues == antes


async def _ventana_guardada() -> Any:
    ventana = await repository.load_window(WINDOW_START)
    assert ventana is not None
    return ventana


# --- PERF-U22.2: armar el tablero cabe en el presupuesto --------------------------

#: El p95 de PERF-U22.2, en segundos, sobre armar el tablero **sin** lo guardado.
PRESUPUESTO_S = 0.5
CORRIDAS = 30


async def test_armar_el_tablero_cabe_en_el_presupuesto_p95(app: FastAPI) -> None:
    """**Con datos de verdad**: 300 filas en tres meses, dos proveedores y un caso.

    Cada corrida vacia lo guardado: lo que se mide es la consulta, no la memoria.
    """
    await sembrar_ventana()
    await crear_caso(sorted(tenancy.available_ids())[0], "caso-perf")
    meses = (SEPTIEMBRE, OCTUBRE, HOY)
    for n in range(300):
        await registrar(
            gasto(
                f"P-{n}",
                costo=Decimal("0.001"),
                proveedor=ProviderName.GEMINI if n % 2 else ProviderName.DEEPGRAM,
                case_ref="caso-perf" if n % 3 == 0 else None,
                tenant_ref=sorted(tenancy.available_ids())[0] if n % 3 == 0 else None,
                occurred_at=meses[n % 3],
                billable=False,
            )
        )

    tiempos: list[float] = []
    async with cliente(app) as c:
        for _ in range(CORRIDAS):
            spend_routes.reset_cache()
            inicio = time.perf_counter()
            assert (await c.get("/api/spend")).status_code == 200
            tiempos.append(time.perf_counter() - inicio)

    tiempos.sort()
    p95 = tiempos[int(len(tiempos) * 0.95) - 1]
    assert p95 <= PRESUPUESTO_S, (
        f"p95 = {p95 * 1000:.0f} ms, presupuesto {PRESUPUESTO_S * 1000:.0f} ms"
    )
