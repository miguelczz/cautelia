"""El envoltorio propio de puntos de control: su aislamiento y su interfaz (FD-U12-3).

Paso 2 de U12. A diferencia de `test_runtime_tables.py` --que ataca las tres
tablas con SQL directo-- estas pruebas pasan siempre por
`TenantCheckpointSaver`, la pieza que de verdad va a usar el grafo. Es la mitad
que el paso 1 no podia cubrir: que la pieza tome su conexion por el punto unico
de sesion, con la aseguradora fijada por `config['configurable']` y nunca
asumida (BR6.1, BR3.1, BR3.2, BR6.3).
"""

from __future__ import annotations

import dataclasses
import importlib
import typing
import uuid
from datetime import UTC, datetime

import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import Checkpoint, CheckpointMetadata
from pydantic import BaseModel

from untangle.base import Use
from untangle.case_record import crypto
from untangle.compliance.controls.closure import ClosureOutcome, HandoffReason
from untangle.orchestration import checkpoint
from untangle.orchestration.checkpoint import TenantCheckpointSaver
from untangle.orchestration.nodes.compliance.node import ComplianceNodeOutput
from untangle.orchestration.nodes.decision.node import DecisionNodeOutput
from untangle.orchestration.nodes.intake.blocks import Block
from untangle.orchestration.nodes.intake.node import IntakeNodeOutput
from untangle.orchestration.nodes.policy_verification.node import PolicyVerificationNodeOutput
from untangle.orchestration.state import GraphState
from untangle.server import composition
from untangle.tenancy import purge as tenancy_purge
from untangle.tenancy import session

from .conftest import nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u12")


def _config(tenant_id: str, thread_id: str) -> RunnableConfig:
    return {"configurable": {"tenant_id": tenant_id, "thread_id": thread_id}}


def _checkpoint(texto: str) -> Checkpoint:
    """Un `Checkpoint` valido y minimo, con el dicho de la persona en un canal."""
    return {
        "v": 4,
        "id": str(uuid.uuid4()),
        "ts": datetime.now(UTC).isoformat(),
        "channel_values": {"texto": texto},
        "channel_versions": {"texto": "1"},
        "versions_seen": {},
        "updated_channels": None,
    }


def _metadata(step: int) -> CheckpointMetadata:
    return {"source": "loop", "step": step, "parents": {}}


def _con_checkpoint_id(config: RunnableConfig, guardado: RunnableConfig) -> RunnableConfig:
    """El config para el siguiente `aput`/`aput_writes`: el mismo hilo, con el
    identificador que devolvio el `aput` anterior como padre."""
    return {"configurable": {**config["configurable"], **guardado["configurable"]}}


# --- 1. Falla cerrado sin aseguradora (FD-U12-3) -------------------------------


async def test_sin_aseguradora_no_lee_ni_escribe_nada() -> None:
    """ "Si no llega, falla cerrado": nunca se asume ninguna aseguradora."""
    saver = TenantCheckpointSaver()

    with pytest.raises(checkpoint.MissingTenantError):
        await saver.aget_tuple({"configurable": {"thread_id": "cualquiera"}})

    with pytest.raises(checkpoint.MissingTenantError):
        await saver.aput(
            {"configurable": {"thread_id": "cualquiera"}}, _checkpoint("x"), _metadata(0), {}
        )

    with pytest.raises(checkpoint.MissingTenantError):
        _ = [c async for c in saver.alist(None)]


# --- 2. El aislamiento, a traves de la pieza real ------------------------------


async def test_el_checkpoint_de_una_aseguradora_no_existe_para_otra_con_el_mismo_hilo(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """BR6.1: mismo identificador de hilo en las dos puntas, y la segunda no ve nada.

    Es la mitad que la politica de fila por si sola no cubre: aqui la conexion
    la toma `TenantCheckpointSaver`, no una consulta de prueba escrita a mano, y
    eso es justo lo que este paso tenia que demostrar (FD-U12-3, riesgo de esta
    unidad).
    """
    ajena, propia = dos_aseguradoras
    caso = await nuevo_caso(ajena)
    saver = TenantCheckpointSaver(cipher=cifrador)

    await saver.aput(_config(ajena, caso.case_id), _checkpoint("lo que conto"), _metadata(0), {})

    # La misma aseguradora que escribio si lo ve.
    propio = await saver.aget_tuple(_config(ajena, caso.case_id))
    assert propio is not None

    # La otra, con el identificador de hilo identico, no ve nada -- ni siquiera
    # que existe (BR3.4): la respuesta es la misma que la de un hilo que nunca
    # existio.
    ajeno_desde_otra = await saver.aget_tuple(_config(propia, caso.case_id))
    assert ajeno_desde_otra is None

    vistos = [c async for c in saver.alist(_config(propia, caso.case_id))]
    assert vistos == []


async def test_las_escrituras_pendientes_tampoco_se_ven_entre_aseguradoras(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """Lo mismo para la tabla de escrituras pendientes, **por la pieza**.

    La consulta directa de abajo sola no bastaria: eso es la politica de fila que
    el paso 1 ya prueba. Lo que este paso tiene que demostrar es que la pieza no
    se las entrega a quien no es, asi que se pide por las dos puntas -- la que
    escribio las ve, la otra no -- y solo despues se confirma que en la tabla
    tampoco aparecen.
    """
    ajena, propia = dos_aseguradoras
    caso = await nuevo_caso(ajena)
    saver = TenantCheckpointSaver(cipher=cifrador)

    guardado = await saver.aput(
        _config(ajena, caso.case_id), _checkpoint("primer paso"), _metadata(0), {}
    )
    config_1 = _con_checkpoint_id(_config(ajena, caso.case_id), guardado)
    await saver.aput_writes(config_1, [("intake", {"campo": "valor"})], task_id="tarea-1")

    # La que escribio si las recupera: sin este control positivo, la asercion de
    # abajo pasaria igual con una pieza que no entregara nunca nada.
    propio = await saver.aget_tuple(_config(ajena, caso.case_id))
    assert propio is not None
    assert propio.pending_writes == [("tarea-1", "intake", {"campo": "valor"})]

    # La otra, por la misma pieza y el mismo hilo, no recupera ninguna.
    ajeno_desde_otra = await saver.aget_tuple(_config(propia, caso.case_id))
    assert ajeno_desde_otra is None

    async with session.session_for(propia) as sesion:
        filas = await session.fetch_all(sesion, "SELECT 1 FROM graph_checkpoint_write")
    assert not filas


# --- 3. Reanudar es leer el mayor paso, con su contenido integro (BR3.2) ------


async def test_reanudar_lee_el_mayor_paso_y_encadena_el_padre(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    saver = TenantCheckpointSaver(cipher=cifrador)
    config = _config(propia, caso.case_id)

    primero = await saver.aput(
        config, _checkpoint("dijo que lo chocaron en la salida 12"), _metadata(0), {}
    )
    config_1 = _con_checkpoint_id(config, primero)
    segundo = await saver.aput(config_1, _checkpoint("confirmo la placa ABC123"), _metadata(1), {})

    # Sin pedir un paso concreto: el mayor (BR3.2).
    ultimo = await saver.aget_tuple(config)

    assert ultimo is not None
    assert ultimo.checkpoint["channel_values"]["texto"] == "confirmo la placa ABC123"
    assert (
        ultimo.config["configurable"]["checkpoint_id"] == segundo["configurable"]["checkpoint_id"]
    )
    assert ultimo.parent_config is not None
    assert (
        ultimo.parent_config["configurable"]["checkpoint_id"]
        == primero["configurable"]["checkpoint_id"]
    )

    # Y el primero, sin padre: es el origen del hilo.
    origen = await saver.aget_tuple(
        {"configurable": {**config["configurable"], **primero["configurable"]}}
    )
    assert origen is not None
    assert origen.parent_config is None


# --- 4. El cifrado (BR6.3) -----------------------------------------------------


async def test_el_estado_y_los_metadatos_no_quedan_en_claro(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """Se comprueba contra la fila de verdad, no contra el tipo de la columna."""
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    saver = TenantCheckpointSaver(cipher=cifrador)
    dicho = "me chocaron por detras en la autopista salida 12"

    await saver.aput(_config(propia, caso.case_id), _checkpoint(dicho), _metadata(0), {})

    async with session.session_for(propia) as sesion:
        fila = await session.fetch_one(sesion, "SELECT payload, metadata FROM graph_checkpoint")
    assert fila is not None
    for columna in ("payload", "metadata"):
        guardado = bytes(fila[columna])
        assert dicho.encode("utf-8") not in guardado
        assert b"autopista" not in guardado


async def test_las_escrituras_pendientes_no_quedan_en_claro(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    saver = TenantCheckpointSaver(cipher=cifrador)
    config = _config(propia, caso.case_id)
    guardado = await saver.aput(config, _checkpoint("primer paso"), _metadata(0), {})
    config_1 = _con_checkpoint_id(config, guardado)

    dicho = "la placa es ABC123 y el otro vehiculo se dio a la fuga"
    await saver.aput_writes(config_1, [("intake", {"nota": dicho})], task_id="tarea-1")

    async with session.session_for(propia) as sesion:
        fila = await session.fetch_one(sesion, "SELECT value FROM graph_checkpoint_write")
    assert fila is not None
    guardado_bytes = bytes(fila["value"])
    assert dicho.encode("utf-8") not in guardado_bytes
    assert b"ABC123" not in guardado_bytes


# --- 5. El recorrido de ida y vuelta por la interfaz del framework ------------


async def test_recorrido_completo_por_la_interfaz_del_framework(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """Guardar un punto de control, guardar escrituras pendientes, recuperarlo.

    Es la prueba que cierra el paso: demuestra que `TenantCheckpointSaver`
    cumple el contrato de `BaseCheckpointSaver` -- no solo que escribe filas.
    """
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    saver = TenantCheckpointSaver(cipher=cifrador)
    config = _config(propia, caso.case_id)

    guardado_1 = await saver.aput(config, _checkpoint("primer paso"), _metadata(0), {})
    config_1 = _con_checkpoint_id(config, guardado_1)
    await saver.aput_writes(config_1, [("intake", {"campo": "valor"})], task_id="tarea-1")

    tupla = await saver.aget_tuple(config)
    assert tupla is not None
    assert tupla.checkpoint["channel_values"]["texto"] == "primer paso"
    assert tupla.metadata["step"] == 0
    assert tupla.pending_writes == [("tarea-1", "intake", {"campo": "valor"})]
    assert tupla.parent_config is None

    guardado_2 = await saver.aput(config_1, _checkpoint("segundo paso"), _metadata(1), {})
    assert (
        guardado_2["configurable"]["checkpoint_id"] != guardado_1["configurable"]["checkpoint_id"]
    )

    vistos = [c async for c in saver.alist(config)]
    assert [v.checkpoint["channel_values"]["texto"] for v in vistos] == [
        "segundo paso",
        "primer paso",
    ]

    # `before` deja el primero unicamente fuera, y `limit` corta la lista.
    solo_el_primero = [
        c
        async for c in saver.alist(
            config,
            before={"configurable": {"checkpoint_id": guardado_2["configurable"]["checkpoint_id"]}},
        )
    ]
    assert [v.checkpoint["channel_values"]["texto"] for v in solo_el_primero] == ["primer paso"]

    solo_uno = [c async for c in saver.alist(config, limit=1)]
    assert len(solo_uno) == 1


# --- 6. Reescrituras al mismo canal: gana la primera, salvo canal especial ----


async def test_una_escritura_normal_repetida_no_pisa_la_primera(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    saver = TenantCheckpointSaver(cipher=cifrador)
    config = _config(propia, caso.case_id)
    guardado = await saver.aput(config, _checkpoint("primer paso"), _metadata(0), {})
    config_1 = _con_checkpoint_id(config, guardado)

    await saver.aput_writes(config_1, [("intake", {"v": 1})], task_id="tarea-1")
    await saver.aput_writes(config_1, [("intake", {"v": 2})], task_id="tarea-1")

    tupla = await saver.aget_tuple(config)
    assert tupla is not None
    assert tupla.pending_writes == [("tarea-1", "intake", {"v": 1})]


async def test_en_un_lote_mixto_el_canal_especial_si_se_reemplaza(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """La sentencia se elige por escritura, no por lote.

    Un lote mixto --un canal normal y uno especial en la misma llamada-- es lo
    que deja un nodo que interrumpe **despues** de haber escrito algo. Elegir la
    sentencia mirando el lote entero descartaria en silencio el nuevo motivo de
    la pausa cuando el nodo se reintenta, y la bandeja veria el motivo viejo
    (BR4.1). Cada canal conserva su propia regla.
    """
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    saver = TenantCheckpointSaver(cipher=cifrador)
    config = _config(propia, caso.case_id)
    guardado = await saver.aput(config, _checkpoint("primer paso"), _metadata(0), {})
    config_1 = _con_checkpoint_id(config, guardado)

    await saver.aput_writes(
        config_1, [("intake", {"v": 1}), ("__interrupt__", {"motivo": "primero"})], task_id="t1"
    )
    await saver.aput_writes(
        config_1, [("intake", {"v": 2}), ("__interrupt__", {"motivo": "segundo"})], task_id="t1"
    )

    tupla = await saver.aget_tuple(config)
    assert tupla is not None
    por_canal = {canal: valor for _, canal, valor in tupla.pending_writes or []}
    assert por_canal["intake"] == {"v": 1}
    assert por_canal["__interrupt__"] == {"motivo": "segundo"}


async def test_un_lote_de_solo_canales_especiales_tambien_se_reemplaza(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    saver = TenantCheckpointSaver(cipher=cifrador)
    config = _config(propia, caso.case_id)
    guardado = await saver.aput(config, _checkpoint("primer paso"), _metadata(0), {})
    config_1 = _con_checkpoint_id(config, guardado)

    await saver.aput_writes(config_1, [("__interrupt__", {"motivo": "primero"})], task_id="t1")
    await saver.aput_writes(config_1, [("__interrupt__", {"motivo": "segundo"})], task_id="t1")

    tupla = await saver.aget_tuple(config)
    assert tupla is not None
    por_canal = {canal: valor for _, canal, valor in tupla.pending_writes or []}
    assert por_canal["__interrupt__"] == {"motivo": "segundo"}


# --- 7. El purgador ya cubre la tabla nueva (BR6.4) ---------------------------


async def test_el_purgador_del_caso_cubre_las_escrituras_pendientes() -> None:
    marcadas = await tenancy_purge.visitor_data_tables()
    assert "graph_checkpoint_write" in marcadas
    assert await tenancy_purge.tables_without_purger(composition.PURGADORES) == frozenset()


# --- Los tipos propios que viajan dentro de un punto de control ----------------


def test_el_punto_de_control_declara_sus_tipos_y_no_se_fia_del_permiso_general() -> None:
    """Lo que pasa cuando un tipo no esta declarado **no es un error: es un silencio**.

    LangGraph avisa hoy --"Deserializing unregistered type ... This will be blocked in
    a future version"-- y cuando lo bloquee no va a levantar: devuelve el valor
    degradado. Medido: `Block.SAFETY` declarado vuelve como `Block.SAFETY`, y sin
    declarar vuelve como la cadena `"safety"`. El codigo que lo lee compara contra el
    enum, asi que una conversacion reanudada dejaria de reconocer su propio bloque sin
    que nada fallara.

    **Los dos lados, y ese es el punto de la prueba.** Con solo el primero, esto pasa
    igual contra un serializador que acepte cualquier cosa --que es exactamente el
    valor por omision de hoy, y por tanto exactamente el defecto--. El segundo es el
    que demuestra que la lista esta en vigor.
    """
    serde = TenantCheckpointSaver().serde

    declarado, sin_declarar = serde.dumps_typed({"a": Block.SAFETY, "b": Use.CHAT})
    vuelta = serde.loads_typed((declarado, sin_declarar))

    assert vuelta["a"] is Block.SAFETY, "un tipo declarado tiene que volver con su tipo"
    # **`type(...) is str` y no `== Use.CHAT.value`.** `Use` es un `StrEnum`, asi que
    # el enum compara igual a su propio texto y esa asercion pasaba con el tipo puesto
    # y con el tipo perdido: la forma dos del catalogo de revision, cometida aqui
    # mismo. Lo que distingue los dos mundos es el **tipo**, no el valor.
    assert type(vuelta["b"]) is str, (
        "`Use` no esta en la lista y volvio con su tipo: el serializador esta "
        "aceptando cualquier cosa, que es el permiso general que esta lista sustituye"
    )


async def test_un_tipo_propio_del_estado_sobrevive_al_punto_de_control(
    cifrador: crypto.Cipher, dos_aseguradoras: tuple[str, str]
) -> None:
    """Y lo mismo por el camino de verdad: escrito, cifrado, leido y descifrado."""
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    guardador = TenantCheckpointSaver(cipher=cifrador)
    config: RunnableConfig = {"configurable": {"tenant_id": propia, "thread_id": caso.case_id}}

    punto: Checkpoint = {
        "v": 4,
        "id": str(uuid.uuid4()),
        "ts": datetime.now(UTC).isoformat(),
        "channel_values": {"node_writes": {"intake_next_block": Block.SAFETY}},
        "channel_versions": {"node_writes": 1},
        "versions_seen": {},
        "updated_channels": None,
    }
    metadatos: CheckpointMetadata = {"source": "loop", "step": 0, "parents": {}}
    await guardador.aput(config, punto, metadatos, {})

    tupla = await guardador.aget_tuple(config)

    assert tupla is not None
    escrito = tupla.checkpoint["channel_values"]["node_writes"]["intake_next_block"]
    # Con su tipo, no una cadena parecida: sin esta linea la prueba pasaria contra un
    # valor degradado, que es justo lo que va a pasar cuando LangGraph lo bloquee.
    assert escrito is Block.SAFETY


def test_la_lista_de_tipos_del_punto_de_control_nombra_modulos_que_existen() -> None:
    """Una lista de nombres en texto se queda vieja en silencio cuando algo se mueve.

    Si un tipo se renombra o cambia de modulo, la entrada deja de coincidir, el valor
    vuelve degradado y nada lo dice. Aqui se importa cada una.
    """
    assert checkpoint.TIPOS_DEL_PUNTO_DE_CONTROL, "la lista vacia no declararia nada"
    for modulo, nombre in checkpoint.TIPOS_DEL_PUNTO_DE_CONTROL:
        assert hasattr(importlib.import_module(modulo), nombre), f"{modulo}.{nombre}"


def _tipos_propios(anotacion: object, vistos: set[type]) -> None:
    """Las clases de `untangle` que alcanza una anotacion, entrando en modelos y dataclasses."""
    for argumento in typing.get_args(anotacion):
        _tipos_propios(argumento, vistos)
    if (
        not isinstance(anotacion, type)
        or not anotacion.__module__.startswith("untangle.")
        or anotacion in vistos
    ):
        return
    vistos.add(anotacion)
    if issubclass(anotacion, BaseModel):
        for campo in anotacion.model_fields.values():
            _tipos_propios(campo.annotation, vistos)
    elif dataclasses.is_dataclass(anotacion):
        for interna in typing.get_type_hints(anotacion).values():
            _tipos_propios(interna, vistos)


def test_todo_tipo_que_un_nodo_puede_escribir_esta_declarado() -> None:
    """La lista se quedo corta en silencio una vez, y esta prueba es para que no haya otra.

    El 2026-10-13 una conversacion simulada mostro "Blocked deserialization of
    untangle.rules.models.FiredRule" y cinco mas: `decision` y `compliance` escribian tipos
    que nadie habia declarado, y ninguna prueba lo veia porque las de arriba comprueban el
    mecanismo con un tipo de ejemplo. Aqui se recorre lo que cada nodo **declara que
    devuelve** --y el propio estado-- y se exige que toda clase propia que pueda viajar este
    en la lista. Un campo nuevo en la salida de un nodo, con un tipo nuevo, falla aqui.
    """
    vistos: set[type] = set()
    for raiz in (
        IntakeNodeOutput,
        PolicyVerificationNodeOutput,
        DecisionNodeOutput,
        ComplianceNodeOutput,
    ):
        for campo in raiz.model_fields.values():
            _tipos_propios(campo.annotation, vistos)
    for anotacion in typing.get_type_hints(GraphState).values():
        _tipos_propios(anotacion, vistos)

    declarados = set(checkpoint.TIPOS_DEL_PUNTO_DE_CONTROL)
    sin_declarar = sorted(
        (tipo.__module__, tipo.__name__)
        for tipo in vistos
        if (tipo.__module__, tipo.__name__) not in declarados
    )
    assert vistos, "el recorrido no encontro ningun tipo: la prueba no estaria mirando nada"
    assert sin_declarar == [], (
        "tipos que un nodo puede escribir y el punto de control no sabria leer de vuelta: "
        f"{sin_declarar}"
    )


def test_lo_que_escriben_decision_y_cumplimiento_vuelve_con_su_tipo() -> None:
    """Por el serializador de verdad: una regla disparada y un desenlace de cierre."""
    serde = TenantCheckpointSaver().serde
    vuelta = serde.loads_typed(
        serde.dumps_typed({"motivo": HandoffReason.RULE, "desenlace": ClosureOutcome.REFER})
    )

    assert type(vuelta["motivo"]) is HandoffReason
    assert type(vuelta["desenlace"]) is ClosureOutcome


async def test_si_otro_tomo_el_paso_leido_se_vuelve_a_numerar(
    cifrador: crypto.Cipher, dos_aseguradoras: tuple[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """El paso se numera con `MAX(step) + 1` **leido y escrito en dos sentencias**.

    Desde que el ritmo de fondo escribe su propio punto de control hay dos escritores
    de verdad para el mismo hilo: el turno y la verificacion de cobertura que ese turno
    lanzo. La unica del esquema los cazaba --que es lo correcto, mejor chocar que
    pisarse-- pero el que perdia se quedaba sin escribir, y lo que se perdia era la
    respuesta de cobertura. Salio como `IntegrityError` en un evento de fondo al
    cablear la cobertura de verdad.

    **Se provoca a mano y no con dos tareas en paralelo.** Dos `aput` simultaneos no
    chocan de forma fiable --se turnan casi siempre-- asi que una prueba escrita asi
    pasa igual con el reintento quitado: se comprobo. Aqui se le hace leer un paso que
    ya esta tomado, que es exactamente lo que ve el que pierde la carrera.
    """
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    guardador = TenantCheckpointSaver(cipher=cifrador)
    config: RunnableConfig = {"configurable": {"tenant_id": propia, "thread_id": caso.case_id}}

    def _punto() -> Checkpoint:
        return {
            "v": 4,
            "id": str(uuid.uuid4()),
            "ts": datetime.now(UTC).isoformat(),
            "channel_values": {"turn_text": "x"},
            "channel_versions": {"turn_text": 1},
            "versions_seen": {},
            "updated_channels": None,
        }

    metadatos: CheckpointMetadata = {"source": "loop", "step": 0, "parents": {}}
    await guardador.aput(config, _punto(), metadatos, {})  # ocupa el paso 0

    # El siguiente lee 0 --el que otro acaba de tomar-- una sola vez; despues lee de
    # verdad. Es el que pierde la carrera, visto desde dentro.
    real = session.fetch_one
    primera = {"pendiente": True}

    async def _lee_un_paso_viejo(sesion: object, sql: str, **kwargs: object) -> object:
        if "MAX(step)" in sql and primera["pendiente"]:
            primera["pendiente"] = False
            return {"siguiente": 0}
        return await real(sesion, sql, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(session, "fetch_one", _lee_un_paso_viejo)
    await guardador.aput(config, _punto(), metadatos, {})
    monkeypatch.undo()

    async with session.session_for(propia) as sesion:
        filas = await session.fetch_all(
            sesion,
            "SELECT step FROM graph_checkpoint WHERE thread_id = :hilo ORDER BY step",
            hilo=caso.case_id,
        )
    pasos = [f["step"] for f in filas]
    assert pasos == [0, 1], f"el que perdio la carrera se quedo sin fila: {pasos}"
