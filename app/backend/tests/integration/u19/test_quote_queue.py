"""La bandeja del suscriptor: lo que trae y lo que no (BR4.2).

Entra por HTTP, y el recorte se comprueba **contra la API** y no contra la
pantalla: una lista filtrada en el navegador deja la peticion directa abierta, que
es la misma razon por la que el permiso tampoco vive alli.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI

from untangle.case_record.models import CaseState, RecordType
from untangle.tenancy.models import Role

from .conftest import cliente, credencial_de_rol, nueva_solicitud

pytestmark = pytest.mark.usefixtures("base_de_u19")


async def _cola(
    app: FastAPI, tenant_id: str, *, rol: Role = Role.UNDERWRITER, **parametros: str | int
) -> dict[str, Any]:
    async with cliente(app, credencial=credencial_de_rol(tenant_id, rol)) as http:
        respuesta = await http.get(f"/api/inbox/{tenant_id}/cases", params=parametros)
    assert respuesta.status_code == 200, respuesta.text
    cuerpo: dict[str, Any] = respuesta.json()
    return cuerpo


def _identificadores(pagina: dict[str, Any]) -> set[str]:
    return {fila["case_id"] for fila in pagina["items"]}


async def test_la_bandeja_del_suscriptor_trae_solo_solicitudes_derivadas(
    app: FastAPI, aseguradora_que_cotiza: str
) -> None:
    """Ni siniestros, ni solicitudes que todavia se estan capturando."""
    solicitud = await nueva_solicitud(aseguradora_que_cotiza)
    siniestro = await nueva_solicitud(aseguradora_que_cotiza, tipo=RecordType.CLAIM)
    cerrada = await nueva_solicitud(aseguradora_que_cotiza, estado=CaseState.CAPTURING)

    pagina = await _cola(app, aseguradora_que_cotiza)

    assert _identificadores(pagina) == {solicitud}, (
        f"la lista del suscriptor trajo lo que no es suyo (siniestro {siniestro}, "
        f"a medio capturar {cerrada})"
    )
    assert pagina["items"][0]["record_type"] == RecordType.QUOTE_REQUEST.value


async def test_la_lista_no_trae_la_solicitud_de_otra_aseguradora(
    app: FastAPI, aseguradora_que_cotiza: str, otra_aseguradora: str
) -> None:
    """El aislamiento, con dos filas que **no se distinguen por su contenido**.

    Las dos solicitudes se siembran iguales --mismo tipo, mismo estado, mismo
    idioma, mismo canal, mismo motivo--, asi que lo unico que separa una de otra es
    su aseguradora: una consulta a la que le faltara ese filtro traeria las dos y
    esta asercion se cae.
    """
    propia = await nueva_solicitud(aseguradora_que_cotiza)
    ajena = await nueva_solicitud(otra_aseguradora)

    pagina = await _cola(app, aseguradora_que_cotiza)

    assert _identificadores(pagina) == {propia}
    assert ajena not in _identificadores(pagina)


async def test_pedir_otro_estado_no_ensancha_la_lista_del_suscriptor(
    app: FastAPI, aseguradora_que_cotiza: str
) -> None:
    """Un filtro que no se cruza con su alcance devuelve la pagina vacia.

    Y no los derivados: responder filas que nadie pidio haria creer a quien las lee
    que eso es lo que hay en el estado que pidio.
    """
    await nueva_solicitud(aseguradora_que_cotiza)

    pagina = await _cola(app, aseguradora_que_cotiza, state=CaseState.CLOSED.value)

    assert pagina["items"] == []
    assert pagina["next_cursor"] is None


async def test_un_parametro_que_el_contrato_no_declara_no_ensancha_la_lista(
    app: FastAPI, aseguradora_que_cotiza: str
) -> None:
    """El tipo no lo pide quien llama: lo impone el alcance del rol."""
    solicitud = await nueva_solicitud(aseguradora_que_cotiza)
    await nueva_solicitud(aseguradora_que_cotiza, tipo=RecordType.CLAIM)

    pagina = await _cola(app, aseguradora_que_cotiza, record_type=RecordType.CLAIM.value)

    assert _identificadores(pagina) == {solicitud}


async def test_la_cola_del_ajustador_sigue_trayendo_sus_siniestros(
    app: FastAPI, aseguradora_que_cotiza: str
) -> None:
    """El alcance que anadio U19 es del suscriptor: la bandeja de U14 no cambia."""
    siniestro = await nueva_solicitud(aseguradora_que_cotiza, tipo=RecordType.CLAIM)

    pagina = await _cola(app, aseguradora_que_cotiza, rol=Role.ADJUSTER)

    assert siniestro in _identificadores(pagina)
