"""El reinicio devuelve los casos sembrados a su estado sembrado (AC5.6.4).

Es la mitad de ese criterio que faltaba, y la que no se nota hasta la segunda
semana: el reinicio **conserva** los casos del generador --borrarlos cada noche
vaciaria el corpus de demostracion sin que nadie lo hubiera pedido-- pero hasta
ahora no devolvia a su sitio el que alguien habia movido.

Quien los mueve es la bandeja: decidir un caso lo cierra y no vuelve a derivado,
y la prueba de humo lo dice con esas palabras. Sin este paso, la bandeja de la
demostracion pierde un caso por cada decision y la siembra no lo arregla: se
detiene nombrando el caso que esta en otro estado, que es lo correcto para un
comando a mano y no sirve para una corrida que nadie esta mirando.

**Los tres caminos se prueban**, porque los tres existen: el que esta bien no se
toca, el que falta se siembra, y el que esta en otro estado se borra y se vuelve
a sembrar.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI

from untangle.case_record import api as casos
from untangle.case_record import crypto
from untangle.case_record.models import CaseState, Resolution
from untangle.case_record.rules import TransitionContext
from untangle.rules import api as reglas
from untangle.server import demo_reset, synthetic_seed
from untangle.synthetic_data.cases import load_seeded_cases
from untangle.synthetic_data.models import SeededCaseRecord
from untangle.tenancy import session

from .conftest import aseguradora

pytestmark = pytest.mark.usefixtures("base_de_u20", "sin_transporte")

AHORA = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def cifrador(monkeypatch: pytest.MonkeyPatch) -> Iterator[crypto.Cipher]:
    """Un cifrador de la prueba, como lo instala la raiz de composicion."""
    monkeypatch.setenv(crypto.KEY_ENV_VAR, crypto.generate_key())
    cipher = crypto.Cipher.from_settings()
    crypto.install(cipher)
    yield cipher
    crypto.reset()


def _del_generador(tenant_id: str) -> SeededCaseRecord:
    """Un caso sembrado de esa aseguradora, el primero por su clave."""
    from untangle import paths

    registros = [r for r in load_seeded_cases(paths.data_dir()) if r.tenant_id == tenant_id]
    assert registros, f"'{tenant_id}' no trae casos sembrados en app/data"
    # Uno que **no** este cerrado: el que se va a mover tiene que poder moverse.
    abiertos = [r for r in registros if r.state.value != "closed"]
    assert abiertos, f"'{tenant_id}' no trae ningun caso sembrado sin cerrar"
    return abiertos[0]


async def test_un_caso_sembrado_que_alguien_cerro_vuelve_a_su_estado(app: FastAPI) -> None:
    """El camino que hacia falta: se cierra como lo cierra la bandeja y vuelve."""
    del app
    tenant_id = aseguradora()
    registro = _del_generador(tenant_id)
    cipher = crypto.active()
    await synthetic_seed.seed_case(registro, cipher=cipher, now=AHORA)
    case_id = synthetic_seed.seeded_case_id(registro.case_key)
    antes = await casos.get_case(tenant_id, case_id)
    assert antes is not None

    await casos.close_case(
        tenant_id,
        case_id,
        resolution=Resolution.SENT_TO_INSURER,
        closing_evidence=synthetic_seed.closing_evidence_for(registro.case_key),
        context=TransitionContext(actor=synthetic_seed.SEED_ACTOR, now=AHORA),
    )
    cerrado = await casos.get_case(tenant_id, case_id)
    assert cerrado is not None and cerrado.state is CaseState.CLOSED

    informe = await demo_reset.restore_seeded_cases(
        [registro], cipher=cipher, now=datetime.now(UTC)
    )

    assert informe.restored == (registro.case_key,)
    vuelto = await casos.get_case(tenant_id, case_id)
    assert vuelto is not None
    assert vuelto.state is antes.state
    # Y es **otro** caso con el mismo identificador: se borro y se volvio a
    # sembrar, porque un caso cerrado no se puede reabrir ni se debe.
    assert vuelto.case_number != antes.case_number


async def test_el_que_ya_esta_en_su_estado_no_se_toca(app: FastAPI) -> None:
    """El control que impide que la restauracion borre y siembre todas las noches.

    Sin esta prueba, una version que borrara y sembrara siempre pasaria la de
    arriba: cada corrida nocturna cambiaria el numero de cada caso sembrado, y
    quien anoto el de la demostracion de ayer no lo encontraria.
    """
    del app
    tenant_id = aseguradora()
    registro = _del_generador(tenant_id)
    cipher = crypto.active()
    await synthetic_seed.seed_case(registro, cipher=cipher, now=AHORA)
    case_id = synthetic_seed.seeded_case_id(registro.case_key)
    antes = await casos.get_case(tenant_id, case_id)
    assert antes is not None

    informe = await demo_reset.restore_seeded_cases(
        [registro], cipher=cipher, now=datetime.now(UTC)
    )

    assert informe.kept == (registro.case_key,)
    assert informe.restored == ()
    despues = await casos.get_case(tenant_id, case_id)
    assert despues is not None
    assert despues.case_number == antes.case_number


async def test_con_refresh_el_que_esta_en_su_estado_se_vuelve_a_sembrar(app: FastAPI) -> None:
    """Cuando el generador cambio lo que dice un caso (2026-10-09, los nombres).

    Comparar el estado no ve ese cambio: sin `refresh` el caso se queda como
    estaba y la bandeja seguiria mostrando los nombres viejos.
    """
    del app
    tenant_id = aseguradora()
    registro = _del_generador(tenant_id)
    cipher = crypto.active()
    await synthetic_seed.seed_case(registro, cipher=cipher, now=AHORA)
    case_id = synthetic_seed.seeded_case_id(registro.case_key)
    antes = await casos.get_case(tenant_id, case_id)
    assert antes is not None

    informe = await demo_reset.restore_seeded_cases(
        [registro], cipher=cipher, now=datetime.now(UTC), refresh=True
    )

    assert informe.restored == (registro.case_key,)
    assert informe.kept == ()
    despues = await casos.get_case(tenant_id, case_id)
    assert despues is not None
    assert despues.state is antes.state
    assert despues.case_number != antes.case_number


def _con_reglas(tenant_id: str) -> SeededCaseRecord:
    """Un caso sembrado de esa aseguradora que pasa por la decision, y por eso tiene evaluacion."""
    from untangle import paths

    registros = [
        r
        for r in load_seeded_cases(paths.data_dir())
        if r.tenant_id == tenant_id and synthetic_seed.evaluates_rules(r)
    ]
    assert registros, f"'{tenant_id}' no trae ningun caso sembrado que pase por la decision"
    return registros[0]


async def _borrar_su_evaluacion(tenant_id: str, case_id: str) -> None:
    """Deja el caso como estaba una base sembrada antes de que la siembra evaluara."""
    async with session.session_for(tenant_id) as sesion:
        borradas = await session.execute_sql(
            sesion, "DELETE FROM rule_evaluation WHERE case_id = :case_id", case_id=case_id
        )
    assert borradas == 1


async def test_el_que_esta_en_su_estado_recibe_la_evaluacion_que_le_falta(app: FastAPI) -> None:
    """Una base poblada antes de la evaluacion de reglas: el reinicio la completa, sin borrar.

    Es el camino por el que produccion deja los casos de ejemplo explicados sin que nadie corra
    nada a mano. El caso sigue siendo el mismo (su numero no cambia) y la segunda corrida ya no
    agrega nada.
    """
    del app
    tenant_id = aseguradora()
    registro = _con_reglas(tenant_id)
    cipher = crypto.active()
    await synthetic_seed.seed_case(registro, cipher=cipher, now=AHORA)
    case_id = synthetic_seed.seeded_case_id(registro.case_key)
    antes = await casos.get_case(tenant_id, case_id)
    assert antes is not None
    await _borrar_su_evaluacion(tenant_id, case_id)

    primera = await demo_reset.restore_seeded_cases(
        [registro], cipher=cipher, now=datetime.now(UTC)
    )
    segunda = await demo_reset.restore_seeded_cases(
        [registro], cipher=cipher, now=datetime.now(UTC)
    )

    assert primera.kept == (registro.case_key,)
    assert primera.completed == (registro.case_key,)
    assert segunda.completed == ()
    despues = await casos.get_case(tenant_id, case_id)
    assert despues is not None
    assert despues.case_number == antes.case_number
    assert len(await reglas.evaluations_for(tenant_id, case_id)) == 1


async def test_un_caso_devuelto_a_su_estado_vuelve_con_una_sola_evaluacion(app: FastAPI) -> None:
    """Borrar el caso arrastra su evaluacion (cuelga de el en cascada) y sembrarlo la guarda
    otra vez: ni queda la vieja ni quedan dos."""
    del app
    tenant_id = aseguradora()
    registro = _con_reglas(tenant_id)
    cipher = crypto.active()
    await synthetic_seed.seed_case(registro, cipher=cipher, now=AHORA)
    case_id = synthetic_seed.seeded_case_id(registro.case_key)
    antes = await reglas.evaluations_for(tenant_id, case_id)
    assert len(antes) == 1

    informe = await demo_reset.restore_seeded_cases(
        [registro], cipher=cipher, now=datetime.now(UTC), refresh=True
    )

    assert informe.restored == (registro.case_key,)
    despues = await reglas.evaluations_for(tenant_id, case_id)
    assert len(despues) == 1
    assert despues[0].evaluation_id == antes[0].evaluation_id
    assert despues[0].category == antes[0].category


async def test_el_que_no_esta_se_siembra(app: FastAPI) -> None:
    """Sobre una base recien barrida --o recien creada-- la vitrina se llena."""
    del app
    tenant_id = aseguradora()
    registro = _del_generador(tenant_id)

    informe = await demo_reset.restore_seeded_cases(
        [registro], cipher=crypto.active(), now=datetime.now(UTC)
    )

    assert informe.created == (registro.case_key,)
    vista = await casos.get_case(tenant_id, synthetic_seed.seeded_case_id(registro.case_key))
    assert vista is not None
    assert vista.state is CaseState(registro.state.value)


async def test_el_borrado_de_un_sembrado_no_puede_tocar_un_caso_de_visitante(
    app: FastAPI,
) -> None:
    """El alcance lo dice la sentencia y no quien llama (BR4.6 de U4).

    Un caso de visitante borrado no se puede volver a crear --lo que contenia lo
    dijo una persona-- asi que el borrado de un sembrado lleva su origen en el
    `WHERE`: aunque alguien le pase el identificador de un caso publico, no lo
    toca.
    """
    del app
    from untangle.case_record import purge as case_purge

    from .conftest import sembrar_datos_de_visitante

    tenant_id = aseguradora()
    sembrado = await sembrar_datos_de_visitante(tenant_id)

    borrado = await case_purge.delete_seeded_case(tenant_id, sembrado.case_id)

    assert borrado is False
    assert await casos.get_case(tenant_id, sembrado.case_id) is not None
