"""La costura de la vista de comparacion: su superficie, su divulgacion y su corte.

Tres reglas se prueban aqui, y las tres por HTTP, porque lo que U23 anade no es una
ruta sino un **dato** que viaja con el mensaje (FD-U23-8):

- BR1.4: la divulgacion de la vista queda registrada en los tres casos.
- BR2.1: las tres columnas responden en el idioma de la pregunta.
- Q3: un texto que no es pregunta de cobertura no se admite en esa superficie, y
  aun asi descuenta su mensaje (BR2.3).
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI, Request, Response

from untangle.chat import api as chat_api
from untangle.chat import opening
from untangle.compliance.controls import repository as cumplimiento
from untangle.copy_catalog import api as copy_api
from untangle.tenancy import api as tenancy
from untangle.tenancy import session as db

from .conftest import (
    COOKIE,
    abrir_flujo,
    cliente,
    cola_de,
    eventos_de,
    galleta_de,
    tres_aseguradoras,
)

pytestmark = pytest.mark.usefixtures("base_de_u23")

#: Una pregunta de cobertura con senal de idioma en espanol.
PREGUNTA_ES = "¿Mi póliza cubre el carro de alquiler mientras reparan el mío?"

#: La misma pregunta en ingles.
PREGUNTA_EN = "Does my policy cover a rental car while mine is repaired?"

#: Un texto que **no** es una pregunta de cobertura: es el principio de un reporte.
REPORTE = "Me chocaron por detrás esta mañana y quiero reportarlo"


async def _preguntar(
    app: FastAPI, tenant_id: str, texto: str, **extra: object
) -> tuple[int, dict[str, object]]:
    """Una pregunta por la puerta, **con su flujo abierto antes**.

    El flujo va primero porque es lo que hace el navegador al cargar la pagina, y
    porque la prueba lee la cola de **ese** navegador: sin flujo abierto la respuesta
    espera en una cola reservada y la prueba no distinguiria "no se publico" de "nadie
    la ha abierto todavia". Una prueba que preguntara sin abrirlo estaria comprobando
    la mitad de la costura.
    """
    flujo = await abrir_flujo(tenant_id)
    async with cliente(app) as http:
        http.cookies.set(COOKIE, galleta_de(flujo))
        respuesta = await http.post(
            f"/api/chat/{tenant_id}/messages", json={"text": texto, **extra}
        )
    cuerpo: dict[str, object] = respuesta.json()
    return respuesta.status_code, cuerpo


async def _caso_de(tenant_id: str, session_id: str, *, esperar: float = 3.0) -> str | None:
    """El caso que esa conversacion acabo atando, leido de la base.

    **Espera**, porque la entrega corre en una tarea aparte: la ruta responde `202`
    en cuanto admite el mensaje y el caso nace dentro de la entrega. Sondear es lo
    que distingue "no se abrio" de "todavia no".
    """
    limite = esperar
    while True:
        async with db.session_for(tenant_id) as sesion:
            filas = await db.fetch_all(
                sesion,
                "SELECT case_id FROM chat_session WHERE chat_session_id = :chat_session_id",
                chat_session_id=session_id,
            )
        if filas and filas[0]["case_id"] is not None:
            return str(filas[0]["case_id"])
        if limite <= 0:
            return None
        await asyncio.sleep(0.05)
        limite -= 0.05


async def _casos_de(tenant_id: str) -> int:
    async with db.session_for(tenant_id) as sesion:
        filas = await db.fetch_all(sesion, "SELECT case_id FROM case_record")
    return len(filas)


async def _mensajes_contados(tenant_id: str) -> list[int]:
    async with db.session_for(tenant_id) as sesion:
        filas = await db.fetch_all(
            sesion, "SELECT message_count FROM chat_session ORDER BY chat_session_id"
        )
    return [int(fila["message_count"]) for fila in filas]


# --- BR1.4: la divulgacion queda registrada, y con la clave de su superficie ---


async def test_el_caso_del_chat_nace_con_su_divulgacion_registrada(app: FastAPI) -> None:
    """El control positivo, y una fila que **antes no se escribia nunca**.

    `chat/opening.py` tenia su `record` desde U13 y ninguna ruta lo llamaba: la
    conversacion quedaba marcada como divulgada --lo que impide atender un mensaje
    antes de la apertura-- pero `disclosure_record` se quedaba vacio. El dia que el
    ritmo de fondo se cablee, `closure` rechaza el cierre de un caso sin esa fila:
    todos los casos del chat se habrian quedado sin poder cerrarse por una
    divulgacion que si se mostro.
    """
    aseguradora = tres_aseguradoras()[0]

    estado, cuerpo = await _preguntar(app, aseguradora, PREGUNTA_ES)

    assert estado == 202, cuerpo
    caso = await _caso_de(aseguradora, str(cuerpo["session_id"]))
    assert caso is not None, "el primer turno no ato ningun caso a la conversacion"
    filas = await cumplimiento.disclosures(aseguradora, caso)
    assert [fila.catalog_key for fila in filas] == [str(opening.DISCLOSURE)]


async def test_la_vista_registra_su_propia_divulgacion_en_los_tres_casos(app: FastAPI) -> None:
    """BR1.4 literal: los **tres** casos, con la clave del bloque de la vista.

    Lo que la vista muestra dice mas que la apertura del chat --nombra la poliza de
    ejemplo de cada columna--, asi que registrar la del chat seria escribir que se
    dijo algo que no se dijo.
    """
    for aseguradora in tres_aseguradoras():
        estado, cuerpo = await _preguntar(
            app, aseguradora, PREGUNTA_ES, surface="comparison", locale="es"
        )

        assert estado == 202, cuerpo
        caso = await _caso_de(aseguradora, str(cuerpo["session_id"]))
        assert caso is not None
        filas = await cumplimiento.disclosures(aseguradora, caso)
        assert [fila.catalog_key for fila in filas] == [opening.COMPARISON_DISCLOSURE_BLOCK]
        assert [fila.language for fila in filas] == ["es"]


def test_el_catalogo_sigue_trayendo_el_bloque_que_la_vista_registra() -> None:
    """La clave registrada nombra un bloque del catalogo, no una frase suelta.

    Si alguien renombrara `comparison.disclosure.*`, la fila seguiria escribiendose
    con el nombre viejo y nadie se enteraria: lo que queda en el registro apuntaria
    a algo que ya no existe.
    """
    claves = copy_api.get_catalog().keys()

    assert any(
        str(clave).startswith(f"{opening.COMPARISON_DISCLOSURE_BLOCK}.") for clave in claves
    ), "el catalogo no trae ninguna clave bajo el bloque que la vista registra"


async def test_la_apertura_del_chat_no_se_publica_cuando_la_vista_mostro_la_suya(
    app: FastAPI,
) -> None:
    """Y su control positivo al lado: en el chat **si** se publica.

    Las dos mitades juntas, porque la primera sola pasaria igual con una ruta que no
    publicara ninguna apertura nunca.
    """
    desde_el_chat, desde_la_vista = tres_aseguradoras()[0], tres_aseguradoras()[1]

    flujo_chat = await abrir_flujo(desde_el_chat)
    async with cliente(app) as http:
        http.cookies.set(COOKIE, galleta_de(flujo_chat))
        aceptado = await http.post(
            f"/api/chat/{desde_el_chat}/messages", json={"text": PREGUNTA_ES}
        )
    assert aceptado.status_code == 202, aceptado.text
    del_chat = await eventos_de(cola_de(galleta_de(flujo_chat)))

    flujo_vista = await abrir_flujo(desde_la_vista)
    async with cliente(app) as http:
        http.cookies.set(COOKIE, galleta_de(flujo_vista))
        aceptado_vista = await http.post(
            f"/api/chat/{desde_la_vista}/messages",
            json={"text": PREGUNTA_ES, "surface": "comparison", "locale": "es"},
        )
    assert aceptado_vista.status_code == 202, aceptado_vista.text
    de_la_vista = await eventos_de(cola_de(galleta_de(flujo_vista)))

    def aperturas(eventos: list[dict[str, object]]) -> list[dict[str, object]]:
        return [e for e in eventos if str(e.get("message_id", "")).startswith("opening-")]

    assert aperturas(del_chat), "el chat dejo de publicar su apertura"
    assert not aperturas(de_la_vista), "la vista recibio tambien la apertura del chat"


# --- Q3: fuera de proposito lo decide el servidor -----------------------------


async def test_un_texto_que_no_es_pregunta_de_cobertura_no_se_admite_en_la_vista(
    app: FastAPI,
) -> None:
    """Y **no abre caso**: sin esto, una pregunta fuera de proposito abriria tres
    casos de siniestro desde una pantalla que compara coberturas."""
    aseguradora = tres_aseguradoras()[0]

    estado, cuerpo = await _preguntar(app, aseguradora, REPORTE, surface="comparison", locale="es")

    assert estado == 409, cuerpo
    assert cuerpo["copy_key"] == "comparison.out_of_scope.explanation"
    assert await _casos_de(aseguradora) == 0, "se abrio un caso con un texto fuera de proposito"


async def test_el_mismo_texto_si_se_admite_en_el_chat(app: FastAPI) -> None:
    """Lo que decide no es el texto: es la superficie desde la que llega.

    El chat existe precisamente para reportar un siniestro, y esta prueba es la que
    impide que el corte de la vista se convierta en un corte del chat.
    """
    aseguradora = tres_aseguradoras()[0]

    estado, cuerpo = await _preguntar(app, aseguradora, REPORTE)

    assert estado == 202, cuerpo


async def test_un_texto_fuera_de_proposito_descuenta_su_mensaje(app: FastAPI) -> None:
    """BR2.3: tres mensajes se mandaron, asi que tres se descuentan.

    Un corte antes de contar convertiria la vista en la unica superficie donde
    preguntar sale gratis, y el limite que de verdad protege dejaria de verlo.
    """
    aseguradora = tres_aseguradoras()[0]

    estado, cuerpo = await _preguntar(app, aseguradora, REPORTE, surface="comparison", locale="es")
    assert estado == 409, cuerpo

    assert await _mensajes_contados(aseguradora) == [1], "el mensaje rechazado no se conto"


# --- BR2.1: el idioma de la pregunta, el mismo en las tres --------------------


async def test_las_tres_responden_en_el_idioma_de_la_pregunta(app: FastAPI) -> None:
    """Con senal en el texto, las tres coinciden sin que nadie lo diga."""
    idiomas = []
    for aseguradora in tres_aseguradoras():
        estado, cuerpo = await _preguntar(
            app, aseguradora, PREGUNTA_EN, surface="comparison", locale="en"
        )
        assert estado == 202, cuerpo
        idiomas.append(cuerpo["language"])

    assert idiomas == ["en", "en", "en"]


async def test_una_pregunta_corta_sin_senal_no_se_parte_entre_idiomas(app: FastAPI) -> None:
    """La mitad que de verdad hacia falta (BR2.1), y la que mas sorprende.

    `¿Cubre granizo?` **es** una pregunta de cobertura en espanol y **no trae senal
    de idioma**: es demasiado corta para el umbral de confianza del detector. Sin el
    respaldo de la pantalla, cada columna cae en el idioma por omision de su
    aseguradora --`en`, `es`, `en`-- y pasan dos cosas, no una:

    1. La misma pregunta vuelve contestada en dos idiomas, y la comparacion compara
       tambien el idioma.
    2. Y peor: en las dos aseguradoras de idioma ingles la juzga el reconocedor de
       cobertura **en ingles**, que no la reconoce, asi que la vista responde "fuera
       de proposito" a una pregunta de cobertura legitima.

    Por eso la asercion es la de las tres juntas: `202` y el mismo idioma.
    """
    corta = "¿Cubre granizo?"

    respuestas = []
    for aseguradora in tres_aseguradoras():
        estado, cuerpo = await _preguntar(
            app, aseguradora, corta, surface="comparison", locale="es"
        )
        respuestas.append((aseguradora, estado, cuerpo.get("language")))

    assert [estado for _, estado, _ in respuestas] == [202, 202, 202], respuestas
    assert [idioma for _, _, idioma in respuestas] == ["es", "es", "es"], respuestas


async def test_dos_aseguradoras_abiertas_en_el_mismo_navegador_no_se_quitan_el_flujo(
    app: FastAPI,
) -> None:
    """La comparacion abre tres flujos con la misma galleta, y dos pestanas tambien.

    La cola era solo del navegador: el segundo flujo cerraba el primero y las
    respuestas de una aseguradora salian por el flujo de otra. En la pantalla, la
    respuesta de una columna aparecia bajo el nombre de otra y las demas decian "no
    se pudo revisar" (2026-10-10).
    """
    del app
    una, otra = tres_aseguradoras()[0], tres_aseguradoras()[1]
    galleta = galleta_de(await abrir_flujo(una))
    resumen = tenancy.visitor_key_digest(galleta)
    de_una = chat_api._COLAS.get(chat_api._flujo_de(una, resumen))
    assert de_una is not None

    # El mismo navegador --la misma galleta-- abre la otra aseguradora.
    rutas = {ruta.name: ruta for ruta in chat_api.router().routes}  # type: ignore[attr-defined]
    peticion = Request({"type": "http", "headers": [], "client": ("127.0.0.1", 1234)})
    await rutas["stream_chat"].endpoint(otra, peticion, Response(), galleta)  # type: ignore[attr-defined]
    de_otra = chat_api._COLAS.get(chat_api._flujo_de(otra, resumen))

    assert de_otra is not None
    assert de_otra is not de_una
    assert not de_una.closed, "abrir otra aseguradora cerro el flujo de la primera"
    # Y lo que se publica para una no aparece en la otra.
    de_una.publish({"kind": "turn.final", "message_id": "solo-de-una"})
    assert not any(
        e.get("message_id") == "solo-de-una" for e in await eventos_de(de_otra, durante=0.1)
    )
