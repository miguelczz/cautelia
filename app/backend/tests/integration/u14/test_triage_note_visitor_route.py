"""El visitante con enlace ya no anota para las reglas: la ruta responde `403` y no escribe.

Hasta el plan 09 (fase 5) hacia de ajustador en su propio caso; ahora lo decide el ajustador de
IA, y quien anota para las reglas es el personal con credencial. Lo que se comprueba por la
puerta, no por la pantalla: que el bloque no se ofrezca es cortesia, lo que de verdad lo impide
es que la peticion directa se rechace. El control positivo va delante: el mismo caso, con
credencial, si se anota.

La logica de anotar con el enlace (`annotation.apply` con `principal_id=None`) sigue cubierta a
nivel de funcion en `test_triage_annotation_visitor.py`; ya no tiene ruta que la alcance.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI

from untangle.inbox import triage_notes
from untangle.inbox import visitor as enlace
from untangle.rules import api as reglas
from untangle.tenancy import visitor_access

from .conftest import CLAVE_DE_ENLACES, cliente, credencial_de, nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u14")

CON_REGLAS = "sunmeadow"

ANOTACION: dict[str, Any] = {
    "claim_amount": 7318,
    "coverage_disputed": True,
    "fraud_suspected": True,
}


def _ruta(tenant_id: str, case_id: str) -> str:
    return f"/api/inbox/{tenant_id}/cases/{case_id}/triage-note"


async def _canjear(http: Any, tenant_id: str, case_id: str) -> None:
    emitido = await visitor_access.issue_case_link(
        tenant_id=tenant_id,
        case_id=case_id,
        signing_key=CLAVE_DE_ENLACES,
        now=datetime.now(UTC),
    )
    canje = await http.post(f"/api{enlace.REDEEM_PATH}", json={"token": emitido.token})
    assert canje.status_code == 200, "el control: con el enlace vivo, entra"


async def test_el_visitante_no_anota_y_no_se_escribe_nada(app: FastAPI) -> None:
    caso = await nuevo_caso(CON_REGLAS)

    async with cliente(app) as http:
        await _canjear(http, CON_REGLAS, caso)
        respuesta = await http.put(
            _ruta(CON_REGLAS, caso), json=ANOTACION, headers={"Idempotency-Key": "visitante-1"}
        )

    assert respuesta.status_code == 403, respuesta.text
    assert await triage_notes.read(CON_REGLAS, caso) is None
    assert not await reglas.evaluations_for(CON_REGLAS, caso)


async def test_el_personal_si_anota_el_mismo_caso(app: FastAPI) -> None:
    """El control positivo: el rechazo de arriba es de **quien** pide y no del caso."""
    caso = await nuevo_caso(CON_REGLAS)

    async with cliente(app, credencial=credencial_de(CON_REGLAS)) as http:
        respuesta = await http.put(
            _ruta(CON_REGLAS, caso), json=ANOTACION, headers={"Idempotency-Key": "personal-1"}
        )

    assert respuesta.status_code == 200, respuesta.text
    nota = await triage_notes.read(CON_REGLAS, caso)
    assert nota is not None
    assert nota.values.claim_amount == 7318


async def test_una_credencial_vieja_en_el_navegador_no_le_da_al_visitante_la_anotacion(
    app: FastAPI,
) -> None:
    caso = await nuevo_caso(CON_REGLAS)

    async with cliente(app, credencial="una-credencial-que-no-vale") as http:
        await _canjear(http, CON_REGLAS, caso)
        respuesta = await http.put(
            _ruta(CON_REGLAS, caso), json=ANOTACION, headers={"Idempotency-Key": "visitante-2"}
        )

    assert respuesta.status_code == 403, respuesta.text
    assert await triage_notes.read(CON_REGLAS, caso) is None


async def test_un_enlace_de_otro_caso_o_sin_enlace_responde_como_un_caso_que_no_existe(
    app: FastAPI,
) -> None:
    """El `403` es solo para quien entro de verdad; el resto sigue siendo `404`, sin oraculo."""
    propio = await nuevo_caso(CON_REGLAS)
    ajeno = await nuevo_caso(CON_REGLAS)

    async with cliente(app) as http:
        await _canjear(http, CON_REGLAS, propio)
        de_otro_caso = await http.put(
            _ruta(CON_REGLAS, ajeno), json=ANOTACION, headers={"Idempotency-Key": "visitante-3"}
        )
    async with cliente(app) as sin_enlace:
        sin_enlace_alguno = await sin_enlace.put(
            _ruta(CON_REGLAS, propio), json=ANOTACION, headers={"Idempotency-Key": "visitante-4"}
        )

    assert de_otro_caso.status_code == 404
    assert sin_enlace_alguno.status_code == 404


async def test_la_lectura_del_visitante_ya_no_ofrece_anotar_ni_decidir(app: FastAPI) -> None:
    caso = await nuevo_caso(CON_REGLAS)

    async with cliente(app) as http:
        await _canjear(http, CON_REGLAS, caso)
        vista = await http.get(f"/api/inbox/{CON_REGLAS}/cases/{caso}")

    assert vista.status_code == 200, vista.text
    cuerpo = vista.json()
    assert cuerpo["can_annotate_triage"] is False
    assert cuerpo["triage_amount_steps"] == []
    assert cuerpo["available_actions"] == []
