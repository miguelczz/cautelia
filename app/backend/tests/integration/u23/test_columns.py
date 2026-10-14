"""Las tres columnas: su aislamiento en las trazas y lo que cuestan (BR3.1, BR2.3).

**BR3.1 es compuerta dura** y AC2.9.3 la enuncia como "reviso sus trazas". Se cumple
por construccion --cada llamada va dirigida a una aseguradora y la recuperacion ya es
por aseguradora, probado en U8 donde ocurre-- y lo que se comprueba aqui es el otro
lado: que la traza de cada columna **solo se lee desde su propia columna**, y que una
traza ajena y una inexistente se responden igual.

Lo que no se puede comprobar aqui es la cita de la clausula dentro de la traza: hace
falta el corpus ingerido y el modelo, y eso corre en la capa de evaluaciones y contra
el despliegue vivo. Queda dicho en los hallazgos y no se simula con un doble: una
prueba que leyera las trazas que escribio mi propio doble no probaria nada.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI

from untangle.case_record import api as casos
from untangle.case_record.models import Channel, Origin, RecordType
from untangle.chat import api as chat_api
from untangle.telemetry.traces import api as trazas
from untangle.tenancy import api as tenancy
from untangle.tenancy import session as db

from .conftest import AHORA, cliente, tres_aseguradoras

pytestmark = pytest.mark.usefixtures("base_de_u23")

#: Una pregunta de cobertura, la misma para las tres columnas.
PREGUNTA = "¿Mi póliza cubre el carro de alquiler mientras reparan el mío?"


async def _caso_en(tenant_id: str) -> str:
    vista = await casos.create_case(
        tenant_id,
        casos.NewCase(
            case_id=f"caso-de-{tenant_id}",
            record_type=RecordType.COVERAGE_INQUIRY,
            channel=Channel.CHAT,
            origin=Origin.PUBLIC_CHAT,
            language="es",
            policy_ref=None,
        ),
        now=AHORA,
    )
    return vista.case_id


async def _traza_de_columna(tenant_id: str, *, visitante: str) -> str:
    """Una traza abierta en esa aseguradora, a nombre de ese navegador.

    El resumen de la clave se calcula con la **unica** definicion del proyecto, la
    misma que usa la ruta: calcularlo aqui de otra forma probaria que dos funciones
    distintas coinciden, que no es lo que interesa.
    """
    caso = await _caso_en(tenant_id)
    trace_id = f"tr-{tenant_id}"
    await trazas.open_summary(
        trace_id=trace_id,
        tenant_id=tenant_id,
        case_id=caso,
        visitor_key_hash=tenancy.visitor_key_digest(visitante),
    )
    return trace_id


# --- BR3.1: la traza de una columna no se lee desde otra ----------------------


async def test_cada_columna_lee_su_traza_y_ninguna_lee_la_de_otra(app: FastAPI) -> None:
    """El mismo navegador, tres columnas, tres trazas: cada una solo en su sitio.

    Es el aislamiento que la vista existe para hacer visible, y se mira desde donde
    el visitante mira. El control positivo va primero: sin el, "no se ve la ajena"
    pasaria igual contra una ruta que no sirviera ninguna.
    """
    visitante = "clave-de-quien-compara"
    trazas_por_columna = {
        tenant_id: await _traza_de_columna(tenant_id, visitante=visitante)
        for tenant_id in tres_aseguradoras()
    }

    async with cliente(app) as http:
        http.cookies.set(chat_api.COOKIE, visitante)
        propias = {
            tenant_id: await http.get(f"/api/chat/{tenant_id}/trace/{trace_id}")
            for tenant_id, trace_id in trazas_por_columna.items()
        }
        # La traza de la primera columna, pedida por la ruta de las otras dos.
        primera, *resto = list(trazas_por_columna)
        cruzadas = [
            await http.get(f"/api/chat/{otra}/trace/{trazas_por_columna[primera]}")
            for otra in resto
        ]

    assert all(r.status_code == 200 for r in propias.values())
    assert all(r.json() is not None for r in propias.values()), "una columna no leyo su traza"
    assert [r.status_code for r in cruzadas] == [200] * len(resto)
    assert all(r.json() is None for r in cruzadas), "una columna leyo la traza de otra"


async def test_la_traza_de_otra_columna_y_una_inexistente_se_responden_igual(
    app: FastAPI,
) -> None:
    """Cualquier diferencia entre las dos respuestas le dice que esa traza existe."""
    visitante = "clave-de-quien-compara"
    primera, segunda = tres_aseguradoras()[0], tres_aseguradoras()[1]
    de_la_primera = await _traza_de_columna(primera, visitante=visitante)

    async with cliente(app) as http:
        http.cookies.set(chat_api.COOKIE, visitante)
        ajena = await http.get(f"/api/chat/{segunda}/trace/{de_la_primera}")
        inexistente = await http.get(f"/api/chat/{segunda}/trace/tr-que-no-existe")

    assert ajena.status_code == inexistente.status_code == 200
    assert ajena.json() == inexistente.json() is None


# --- BR2.3: una pregunta son tres mensajes ------------------------------------


async def test_una_pregunta_descuenta_un_mensaje_en_cada_una_de_las_tres(
    app: FastAPI,
) -> None:
    """Tres mensajes por tres rutas que ya llevan sus controles (BR2.3).

    No es un contador que esta vista mantenga --eso seria un segundo sitio donde el
    limite puede discrepar del que de verdad protege--: es lo que pasa. Lo que la
    prueba comprueba es que de verdad pasa, en las tres y una vez en cada una.
    """
    from .conftest import abrir_flujo, galleta_de

    for tenant_id in tres_aseguradoras():
        flujo = await abrir_flujo(tenant_id)
        async with cliente(app) as http:
            http.cookies.set(chat_api.COOKIE, galleta_de(flujo))
            respuesta = await http.post(
                f"/api/chat/{tenant_id}/messages",
                json={"text": PREGUNTA, "surface": "comparison", "locale": "es"},
            )
        assert respuesta.status_code == 202, respuesta.text

    contados = {}
    for tenant_id in tres_aseguradoras():
        async with db.session_for(tenant_id) as sesion:
            filas = await db.fetch_all(sesion, "SELECT message_count FROM chat_session")
        contados[tenant_id] = [int(fila["message_count"]) for fila in filas]

    assert contados == {tenant_id: [1] for tenant_id in tres_aseguradoras()}
    assert sum(sum(c) for c in contados.values()) == 3
