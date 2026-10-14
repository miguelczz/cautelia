"""La compuerta dura de U14: una credencial nunca ve casos de otra aseguradora.

BR1.4 `[bloquea]`, sobre las colisiones sembradas de DS-8 --mismo identificador de
caso, mismo numero de poliza y mismo nombre de asegurado en dos aseguradoras--.

**Por que las colisiones y no casos cualesquiera.** Con datos que no se parecen,
una consulta sin ningun filtro por aseguradora tambien devolveria "solo lo mio" y
esta prueba pasaria contra una bandeja sin aislamiento. Es la forma de prueba que
el catalogo llama "la asercion que no puede distinguir".

**Por que el control positivo va delante.** Las dos comprobaciones de rechazo
pasan igual contra una bandeja que no entregue nada nunca. La primera prueba de
este archivo es que la credencial legitima recibe su cola con su caso dentro; sin
ella, las otras dos no significan nada. Es el defecto que U13 encontro en su
propia prueba del resumen de traza, y no se repite.

**Por la interfaz y por una peticion directa.** Lo que impide la fuga no es que
la pantalla no ofrezca el boton: es que la ruta rechaza. Por eso todo aqui entra
por HTTP.
"""

from __future__ import annotations

import httpx2
import pytest
from fastapi import FastAPI

from .conftest import Colision, cliente, credencial_de, dos_aseguradoras_con_colision


def _ruta(tenant_id: str) -> str:
    return f"/api/inbox/{tenant_id}/cases"


def _sin_el_rastro(respuesta: httpx2.Response) -> dict[str, object]:
    """El cuerpo del error sin `trace_id`, que es lo unico que puede diferir.

    C-01 pone en **toda** respuesta de error un identificador de peticion. Cambia
    entre dos peticiones por definicion, asi que compararlo seria comparar el
    reloj. Todo lo demas --estado, codigo, titulo, detalle-- tiene que salir
    identico, y aqui se comprueba que el rastro estuvo y que era el unico campo
    distinto: quitarlo sin comprobar que estaba dejaria pasar una respuesta que
    no lo trae.
    """
    cuerpo = dict(respuesta.json())
    assert cuerpo.pop("trace_id", None), "la respuesta de error no trae rastro (C-01)"
    return cuerpo


async def test_la_credencial_legitima_recibe_su_cola(
    app: FastAPI, colisiones: tuple[Colision, ...]
) -> None:
    """El control positivo. Va primero porque sostiene a los dos siguientes."""
    propia, _ = dos_aseguradoras_con_colision(colisiones)
    async with cliente(app, credencial=credencial_de(propia)) as http:
        respuesta = await http.get(_ruta(propia))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    suyos = {fila["case_id"] for fila in cuerpo["items"]}
    esperados = {fila.case_id for fila in colisiones if fila.tenant_id == propia}
    assert suyos == esperados, "la cola no entrego exactamente los casos de esa aseguradora"


async def test_una_credencial_no_ve_la_cola_de_otra_aseguradora(
    app: FastAPI, colisiones: tuple[Colision, ...]
) -> None:
    """BR1.4: la aseguradora sale de la credencial y nunca de la direccion."""
    propia, ajena = dos_aseguradoras_con_colision(colisiones)
    async with cliente(app, credencial=credencial_de(propia)) as http:
        respuesta = await http.get(_ruta(ajena))

    assert respuesta.status_code == 404
    assert "items" not in respuesta.text, "el rechazo devolvio algo con forma de cola"


async def test_el_rechazo_es_el_mismo_que_el_de_una_credencial_ilegible(
    app: FastAPI, colisiones: tuple[Colision, ...]
) -> None:
    """Las dos respuestas se comparan **enteras**: la filtracion es la distincion.

    Comprobar solo que el caso ajeno no aparece dejaria pasar un rechazo que dice
    "esa aseguradora existe pero no es la tuya", que es justo lo que le falta a
    quien prueba identificadores.
    """
    propia, ajena = dos_aseguradoras_con_colision(colisiones)
    async with cliente(app, credencial=credencial_de(propia)) as http:
        con_credencial_ajena = await http.get(_ruta(ajena))
    async with cliente(app, credencial="no-es-una-credencial") as http:
        con_credencial_ilegible = await http.get(_ruta(ajena))

    assert con_credencial_ajena.status_code == con_credencial_ilegible.status_code
    assert _sin_el_rastro(con_credencial_ajena) == _sin_el_rastro(con_credencial_ilegible)


async def test_sin_credencial_la_cola_no_responde(
    app: FastAPI, colisiones: tuple[Colision, ...]
) -> None:
    """Y sin ninguna credencial, lo mismo: no hay cola publica."""
    propia, _ = dos_aseguradoras_con_colision(colisiones)
    async with cliente(app) as http:
        respuesta = await http.get(_ruta(propia))

    assert respuesta.status_code == 404


async def test_el_identificador_de_la_direccion_no_manda(
    app: FastAPI, colisiones: tuple[Colision, ...]
) -> None:
    """Una aseguradora que no existe responde igual que una que existe y no es tuya.

    Si respondieran distinto, pedir la cola de cada nombre plausible diria cuales
    aseguradoras estan desplegadas.
    """
    propia, ajena = dos_aseguradoras_con_colision(colisiones)
    async with cliente(app, credencial=credencial_de(propia)) as http:
        inventada = await http.get(_ruta("aseguradora-que-no-existe"))
        existente = await http.get(_ruta(ajena))

    assert inventada.status_code == existente.status_code
    assert _sin_el_rastro(inventada) == _sin_el_rastro(existente)


@pytest.mark.parametrize("credencial", ["", "no-es-una-credencial", "a.b.c"])
async def test_ninguna_credencial_rota_abre_la_cola(
    app: FastAPI, colisiones: tuple[Colision, ...], credencial: str
) -> None:
    propia, _ = dos_aseguradoras_con_colision(colisiones)
    async with cliente(app, credencial=credencial) as http:
        respuesta = await http.get(_ruta(propia))

    assert respuesta.status_code == 404
