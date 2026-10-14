"""La cola: su orden, sus filtros, sus casos a medias y su cursor (BR1.1 a BR1.5).

Todo entra por HTTP y no por la funcion: lo que esta unidad ofrece es una ruta, y
una prueba que llamara a `queue.page` no diria nada sobre lo que responde la
bandeja a quien la usa.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from fastapi import FastAPI

from untangle.case_record.models import CaseState, Channel, DerivationReason

from .conftest import AHORA, cliente, credencial_de, nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u14")


def _ruta(tenant_id: str) -> str:
    return f"/api/inbox/{tenant_id}/cases"


@pytest.fixture
def aseguradora() -> str:
    from untangle.tenancy import api as tenancy

    return tenancy.available_ids()[0]


async def _cola(app: FastAPI, aseguradora: str, **parametros: str | int) -> dict[str, Any]:
    async with cliente(app, credencial=credencial_de(aseguradora)) as http:
        respuesta = await http.get(_ruta(aseguradora), params=parametros)
    assert respuesta.status_code == 200, respuesta.text
    cuerpo: dict[str, Any] = respuesta.json()
    return cuerpo


# --- BR1.1: el orden ----------------------------------------------------------


async def test_dentro_de_una_prioridad_manda_la_espera_mas_larga(
    app: FastAPI, aseguradora: str
) -> None:
    """Dos casos de la misma prioridad, con esperas distintas.

    Con un solo caso el orden se satisface por casualidad; con dos de la misma
    prioridad, lo unico que puede decidir es la espera.
    """
    reciente = await nuevo_caso(aseguradora, derivado_en=AHORA)
    antiguo = await nuevo_caso(aseguradora, derivado_en=AHORA - timedelta(days=2))

    cuerpo = await _cola(app, aseguradora)

    assert [fila["case_id"] for fila in cuerpo["items"]] == [antiguo, reciente]


async def test_la_prioridad_manda_sobre_la_espera(app: FastAPI, aseguradora: str) -> None:
    """Y con las esperas invertidas: el alto reciente va delante del normal viejo.

    Puestas asi, un orden que solo mirara la espera daria justo lo contrario, y
    uno que solo mirara la prioridad no habria distinguido nada en la prueba de
    arriba. Las dos juntas fijan la regla entera.
    """
    normal_viejo = await nuevo_caso(
        aseguradora, motivo=DerivationReason.RULE, derivado_en=AHORA - timedelta(days=2)
    )
    alto_reciente = await nuevo_caso(
        aseguradora, motivo=DerivationReason.PERSON_REQUESTED, derivado_en=AHORA
    )

    cuerpo = await _cola(app, aseguradora)

    assert [fila["case_id"] for fila in cuerpo["items"]] == [alto_reciente, normal_viejo]
    assert cuerpo["items"][0]["priority"] == "high"


# --- BR1.2: lo que lleva la fila ----------------------------------------------


async def test_la_fila_lleva_los_seis_datos_con_que_se_elige(
    app: FastAPI, aseguradora: str
) -> None:
    """Completitud, categoria, canal, idioma, prioridad y desde cuando espera."""
    await nuevo_caso(aseguradora, idioma="en", canal=Channel.VOICE)

    fila = (await _cola(app, aseguradora))["items"][0]

    assert fila["completeness_total"] > 0, "una completitud sobre cero no dice nada"
    assert fila["completeness_complete"] == 0
    assert fila["record_type"] == "claim"
    assert fila["channel"] == "voice"
    assert fila["language"] == "en"
    assert fila["priority"] == "normal"
    assert fila["updated_at"]


#: Lo unico que una fila de la cola puede llevar. Escrito aqui y no derivado del
#: modelo a proposito: derivarlo haria que la prueba aceptara cualquier campo
#: nuevo por el hecho de existir, que es justo lo que tiene que impedir.
CAMPOS_DE_LA_FILA = frozenset(
    {
        "case_id",
        "case_number",
        "state",
        "record_type",
        "channel",
        "language",
        "priority",
        "completeness",
        "completeness_complete",
        "completeness_total",
        "derivation_reason",
        "updated_at",
    }
)


async def test_la_fila_no_lleva_ningun_campo_de_texto_libre(app: FastAPI, aseguradora: str) -> None:
    """Lo que hay en una fila son enums, numeros y horas: por eso no se redacta.

    El dia que entre un campo nuevo, esta prueba se cae y obliga a decidir a la
    vista si lleva texto de una persona --y entonces necesita redaccion-- en vez
    de descubrirlo en el reporte de redaccion cuando ya se publico.
    """
    await nuevo_caso(aseguradora)

    fila = (await _cola(app, aseguradora))["items"][0]

    assert set(fila) == CAMPOS_DE_LA_FILA


# --- BR1.3: el filtro que no deja nada ----------------------------------------


async def test_un_filtro_sin_resultados_responde_una_cola_vacia(
    app: FastAPI, aseguradora: str
) -> None:
    """Vacia y con exito, no un error: la pregunta era valida y la respuesta es cero."""
    await nuevo_caso(aseguradora, idioma="es")

    cuerpo = await _cola(app, aseguradora, language="en")

    assert cuerpo["items"] == []
    assert cuerpo["next_cursor"] is None


async def test_un_filtro_con_un_valor_que_no_existe_se_rechaza(
    app: FastAPI, aseguradora: str
) -> None:
    """Y no se ignora. Un filtro ignorado devuelve **mas** casos de los pedidos."""
    await nuevo_caso(aseguradora)

    async with cliente(app, credencial=credencial_de(aseguradora)) as http:
        respuesta = await http.get(_ruta(aseguradora), params={"channel": "paloma-mensajera"})

    assert respuesta.status_code == 422


@pytest.mark.parametrize(
    ("parametro", "valor", "esperados"),
    [("channel", "voice", 1), ("language", "en", 1), ("priority", "high", 1)],
)
async def test_cada_filtro_acota(
    app: FastAPI, aseguradora: str, parametro: str, valor: str, esperados: int
) -> None:
    """Un caso que coincide y otro que no, por cada filtro."""
    await nuevo_caso(
        aseguradora,
        canal=Channel.VOICE,
        idioma="en",
        motivo=DerivationReason.PERSON_REQUESTED,
    )
    await nuevo_caso(aseguradora, canal=Channel.CHAT, idioma="es", motivo=DerivationReason.RULE)

    cuerpo = await _cola(app, aseguradora, **{parametro: valor})

    assert len(cuerpo["items"]) == esperados


# --- BR1.5: los casos que esperan al asegurado --------------------------------


async def test_un_caso_que_espera_al_asegurado_sigue_en_la_cola(
    app: FastAPI, aseguradora: str
) -> None:
    """Con su completitud y su estado. Un caso a medias que no aparece es uno perdido."""
    esperando = await nuevo_caso(aseguradora, estado=CaseState.AWAITING_INSURED)

    cuerpo = await _cola(app, aseguradora)

    fila = next(f for f in cuerpo["items"] if f["case_id"] == esperando)
    assert fila["state"] == "awaiting_insured"
    assert fila["completeness_total"] > 0


@pytest.mark.parametrize("estado", [CaseState.OPEN, CaseState.CAPTURING])
async def test_un_caso_todavia_en_conversacion_no_aparece(
    app: FastAPI, aseguradora: str, estado: CaseState
) -> None:
    """Ni sin filtro ni pidiendolo por su nombre.

    Lo dice la tabla del diseno funcional: mientras el asegurado sigue hablando,
    el caso no espera nada del ajustador. La segunda mitad --pedirlo por su
    nombre-- es la que impide que la regla viva solo en el valor por defecto.
    """
    esperado = await nuevo_caso(aseguradora, estado=estado)
    await nuevo_caso(aseguradora, estado=CaseState.DERIVED)

    sin_filtro = await _cola(app, aseguradora)
    pidiendolo = await _cola(app, aseguradora, state=estado.value)

    assert esperado not in [f["case_id"] for f in sin_filtro["items"]]
    assert sin_filtro["items"], "la cola se vacio entera: el filtro se paso de largo"
    assert pidiendolo["items"] == []


async def test_un_caso_cerrado_si_aparece(app: FastAPI, aseguradora: str) -> None:
    """Un caso resuelto es lo que alguien busca cuando quiere ver como quedo."""
    derivado = await nuevo_caso(aseguradora, estado=CaseState.DERIVED)

    cuerpo = await _cola(app, aseguradora, state="derived")

    assert [f["case_id"] for f in cuerpo["items"]] == [derivado]


# --- La paginacion por cursor -------------------------------------------------


async def test_el_cursor_recorre_la_cola_entera_sin_repetir_ni_saltarse(
    app: FastAPI, aseguradora: str
) -> None:
    """Cinco casos de dos en dos: se ven los cinco, cada uno una vez.

    Se siembran con el **mismo** instante a proposito: con fechas distintas, un
    cursor que solo llevara la fecha funcionaria igual y la prueba no diria nada
    del tercer termino de la terna.
    """
    sembrados = {await nuevo_caso(aseguradora, derivado_en=AHORA) for _ in range(5)}

    vistos: list[str] = []
    cursor: str | None = None
    for _ in range(5):
        parametros: dict[str, str | int] = {"limit": 2}
        if cursor is not None:
            parametros["cursor"] = cursor
        cuerpo = await _cola(app, aseguradora, **parametros)
        vistos.extend(fila["case_id"] for fila in cuerpo["items"])
        cursor = cuerpo["next_cursor"]
        if cursor is None:
            break

    assert cursor is None, "la cola no llego a su final"
    assert len(vistos) == len(set(vistos)), "un caso salio en dos paginas"
    assert set(vistos) == sembrados


async def test_un_cursor_que_no_se_puede_leer_se_rechaza(app: FastAPI, aseguradora: str) -> None:
    """Y no empieza la cola desde el principio en silencio.

    Volver al principio sin decirlo hace que quien recorre la cola vea las mismas
    filas para siempre sin enterarse.
    """
    await nuevo_caso(aseguradora)

    async with cliente(app, credencial=credencial_de(aseguradora)) as http:
        respuesta = await http.get(_ruta(aseguradora), params={"cursor": "esto-no-es-un-cursor"})

    assert respuesta.status_code == 422


async def test_la_ultima_pagina_no_ofrece_continuacion(app: FastAPI, aseguradora: str) -> None:
    """Sin esto, quien pagina no sabria cuando parar y pediria una pagina vacia de mas."""
    await nuevo_caso(aseguradora)
    await nuevo_caso(aseguradora)

    cuerpo = await _cola(app, aseguradora, limit=2)

    assert len(cuerpo["items"]) == 2
    assert cuerpo["next_cursor"] is None
