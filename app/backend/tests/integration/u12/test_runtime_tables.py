"""Las tres tablas del runtime: su aislamiento, sus llaves y su cascada (BR6.1, BR6.3, BR6.4).

Estas pruebas no se pueden escribir sin base de datos, y por eso viven aqui: lo
que comprueban es lo que **PostgreSQL** hace, no lo que el codigo cree que hace.

Tres cosas, y cada una cierra un fallo distinto:

1. **La politica de fila.** Una fila de una aseguradora no existe para otra. Ni
   su contenido ni el hecho de que este ahi.
2. **La llave compuesta.** Las comprobaciones de llave foranea las hace el motor
   **por encima** de las politicas, asi que una llave de una sola columna dejaria
   a una aseguradora escribir una fila suya que nombrara el caso de otra. Es el
   agujero que U8 encontro de verdad en `coverage_answers` y que aqui no se
   vuelve a abrir.
3. **La cascada.** Un caso de visitante borrado no deja su punto de control, que
   guarda el estado serializado completo de la conversacion.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError

from untangle.case_record import crypto
from untangle.tenancy import session

from .conftest import AHORA, CasoSembrado, nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u12")

INSERTAR_PUNTO = (
    "INSERT INTO graph_checkpoint "
    "(checkpoint_id, tenant_id, case_id, thread_id, checkpoint_ns, step, payload_type, "
    "payload, metadata_type, metadata, sealed_key_id, created_at) "
    "VALUES (:checkpoint_id, :tenant_id, :case_id, :thread_id, :checkpoint_ns, :step, "
    ":payload_type, :payload, :metadata_type, :metadata, :sealed_key_id, :created_at)"
)
INSERTAR_PAUSA = (
    "INSERT INTO human_review_request "
    "(request_id, tenant_id, case_id, reason, status, created_at) "
    "VALUES (:request_id, :tenant_id, :case_id, :reason, :status, :created_at)"
)
INSERTAR_EJECUCION = (
    "INSERT INTO node_run "
    "(node_run_id, tenant_id, case_id, node, rhythm, attempt, max_attempts, outcome, "
    "idempotency_key, started_at) "
    "VALUES (:node_run_id, :tenant_id, :case_id, :node, :rhythm, :attempt, :max_attempts, "
    ":outcome, :idempotency_key, :started_at)"
)


#: Como cada prueba fabrica la fila de su tabla a partir de un caso sembrado.
Constructor = Callable[[CasoSembrado], dict[str, Any]]


def _id(prefijo: str) -> str:
    return f"{prefijo}-{uuid.uuid4().hex[:12]}"


def _punto(caso: CasoSembrado, cifrador: crypto.Cipher, texto: str) -> dict[str, Any]:
    # `seal` devuelve el tipo `Sealed`, que es bytes: es la unica forma de
    # fabricarlo, y por eso la prueba no puede escribir texto en claro sin querer.
    # `payload_type` y `metadata` los anadio el paso 2 (`TenantCheckpointSaver`
    # los llena de verdad); aqui bastan valores de relleno porque esta prueba
    # comprueba aislamiento y llaves, no la interfaz del checkpointer.
    sellado = cifrador.seal(texto)
    return {
        "checkpoint_id": _id("chk"),
        "tenant_id": caso.tenant_id,
        "case_id": caso.case_id,
        "thread_id": caso.case_id,
        "checkpoint_ns": "",
        "step": 1,
        "payload_type": "json",
        "payload": bytes(sellado),
        "metadata_type": "json",
        "metadata": bytes(cifrador.seal("{}")),
        "sealed_key_id": cifrador.id,
        "created_at": AHORA,
    }


def _pausa(caso: CasoSembrado) -> dict[str, Any]:
    return {
        "request_id": _id("req"),
        "tenant_id": caso.tenant_id,
        "case_id": caso.case_id,
        "reason": "compliance_referral",
        "status": "open",
        "created_at": AHORA,
    }


def _ejecucion(caso: CasoSembrado) -> dict[str, Any]:
    return {
        "node_run_id": _id("run"),
        "tenant_id": caso.tenant_id,
        "case_id": caso.case_id,
        "node": "policy_verification",
        "rhythm": "background",
        "attempt": 1,
        "max_attempts": 2,
        "outcome": "running",
        "idempotency_key": _id("idem"),
        "started_at": AHORA,
    }


async def _escribir(tenant_id: str, sentencia: str, fila: dict[str, Any]) -> None:
    async with session.session_for(tenant_id) as sesion:
        await session.execute_sql(sesion, sentencia, **fila)


async def _rechazo(tenant_id: str, sentencia: str, fila: dict[str, Any]) -> str:
    with pytest.raises(IntegrityError) as error:
        await _escribir(tenant_id, sentencia, fila)
    return str(error.value)


# --- 1. La politica de fila ---------------------------------------------------


async def test_el_punto_de_control_de_una_aseguradora_no_existe_para_otra(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """BR6.1: ni su contenido, ni el hecho de que este ahi.

    Es la mitad que la politica de fila **si** cubre. La otra mitad --que la
    pieza del framework tome su conexion por el punto unico-- es el paso 2.
    """
    ajena, propia = dos_aseguradoras
    caso_ajeno = await nuevo_caso(ajena)
    await _escribir(ajena, INSERTAR_PUNTO, _punto(caso_ajeno, cifrador, "lo que conto"))

    async with session.session_for(propia) as sesion:
        filas = await session.fetch_all(sesion, "SELECT checkpoint_id FROM graph_checkpoint")

    assert not filas


@pytest.mark.parametrize(
    ("sentencia", "constructor"),
    [
        (INSERTAR_PAUSA, _pausa),
        (INSERTAR_EJECUCION, _ejecucion),
    ],
)
async def test_las_otras_dos_tablas_tampoco_se_ven_entre_aseguradoras(
    dos_aseguradoras: tuple[str, str], sentencia: str, constructor: Any
) -> None:
    ajena, propia = dos_aseguradoras
    caso_ajeno = await nuevo_caso(ajena)
    await _escribir(ajena, sentencia, constructor(caso_ajeno))

    tabla = "human_review_request" if sentencia == INSERTAR_PAUSA else "node_run"
    async with session.session_for(propia) as sesion:
        filas = await session.fetch_all(sesion, f"SELECT 1 FROM {tabla}")  # noqa: S608

    assert not filas


# --- 2. La llave compuesta ----------------------------------------------------


@pytest.mark.parametrize(
    ("nombre", "sentencia", "constructor"),
    [
        ("graph_checkpoint_del_caso", INSERTAR_PUNTO, None),
        ("human_review_request_del_caso", INSERTAR_PAUSA, _pausa),
        ("node_run_del_caso", INSERTAR_EJECUCION, _ejecucion),
    ],
)
async def test_ninguna_fila_puede_apuntar_al_caso_de_otra_aseguradora(
    dos_aseguradoras: tuple[str, str],
    cifrador: crypto.Cipher,
    nombre: str,
    sentencia: str,
    constructor: Constructor | None,
) -> None:
    """La llave lleva la aseguradora, y por eso el motor rechaza el cruce.

    Dos inserciones con la misma fila, cambiando una sola cosa: la primera apunta
    a lo propio y entra --asi el rechazo de la segunda no se puede deber a otra
    restriccion--; la segunda apunta al caso de la otra aseguradora y choca.
    """
    ajena, propia = dos_aseguradoras
    caso_ajeno = await nuevo_caso(ajena)
    caso_propio = await nuevo_caso(propia)

    def fila(caso: CasoSembrado) -> dict[str, Any]:
        if constructor is None:
            return _punto(caso, cifrador, "lo que conto")
        return constructor(caso)

    await _escribir(propia, sentencia, fila(caso_propio))

    # La misma fila, con la aseguradora propia y el caso de la otra. El hilo
    # cambia con el caso: el hilo **es** el caso (BR3.1), y dejarlo igual haria
    # que chocara primero la unicidad del paso y no la llave, que es lo que esta
    # prueba mide.
    cruzada = fila(caso_propio) | {
        "case_id": caso_ajeno.case_id,
        "thread_id": caso_ajeno.case_id,
    }
    mensaje = await _rechazo(propia, sentencia, cruzada)

    assert nombre in mensaje


# --- 3. La cascada y el cifrado ----------------------------------------------


async def test_borrar_el_caso_se_lleva_las_tres_tablas(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """BR6.4: un caso de visitante borrado no deja su punto de control.

    Y esto no es solo orden: el punto de control guarda el estado serializado
    completo de la conversacion, asi que una fila huerfana seria una copia de todo
    lo que la persona conto.
    """
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    await _escribir(propia, INSERTAR_PUNTO, _punto(caso, cifrador, "lo que conto"))
    await _escribir(propia, INSERTAR_PAUSA, _pausa(caso))
    await _escribir(propia, INSERTAR_EJECUCION, _ejecucion(caso))

    async with session.session_for(propia) as sesion:
        await session.execute_sql(
            sesion, "DELETE FROM case_record WHERE case_id = :case_id", case_id=caso.case_id
        )
        quedan = await session.fetch_one(
            sesion,
            "SELECT (SELECT count(*) FROM graph_checkpoint) "
            "+ (SELECT count(*) FROM human_review_request) "
            "+ (SELECT count(*) FROM node_run) AS filas",
        )

    assert quedan is not None
    assert quedan["filas"] == 0


async def test_el_punto_de_control_no_guarda_el_texto_en_claro(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """SEC-U12.3: lo que queda en la tabla no se puede leer.

    Se comprueba contra la fila de verdad y no contra el tipo de la columna: una
    columna de bytes puede guardar texto en claro perfectamente.
    """
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    dicho = "me chocaron por detras en la autopista salida 12"
    await _escribir(propia, INSERTAR_PUNTO, _punto(caso, cifrador, dicho))

    async with session.session_for(propia) as sesion:
        fila = await session.fetch_one(sesion, "SELECT payload FROM graph_checkpoint")

    assert fila is not None
    guardado = bytes(fila["payload"])
    assert dicho.encode("utf-8") not in guardado
    assert b"autopista" not in guardado


async def test_dos_pausas_vivas_del_mismo_caso_no_caben(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Dos entradas abiertas del mismo caso dejarian a la bandeja con dos
    decisiones que tomar sobre lo mismo."""
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    await _escribir(propia, INSERTAR_PAUSA, _pausa(caso))

    mensaje = await _rechazo(propia, INSERTAR_PAUSA, _pausa(caso))

    assert "human_review_request_una_viva" in mensaje


async def test_el_mismo_trabajo_no_se_registra_dos_veces(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """BR5.4: la unicidad la impone la base y no el barrido.

    Un barrido con un error de concurrencia gastaria dos veces contra un tope de
    5 USD, y nadie lo notaria hasta que el tope se agotara.
    """
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    primera = _ejecucion(caso)
    await _escribir(propia, INSERTAR_EJECUCION, primera)

    # Otro identificador de fila, la misma clave de idempotencia: es el mismo
    # trabajo intentado otra vez.
    repetida = _ejecucion(caso) | {"idempotency_key": primera["idempotency_key"]}
    mensaje = await _rechazo(propia, INSERTAR_EJECUCION, repetida)

    assert "node_run_trabajo_unico" in mensaje
