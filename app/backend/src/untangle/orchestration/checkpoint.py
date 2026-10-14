"""El envoltorio propio de puntos de control (FD-U12-3, BR3.1, BR3.2, BR6.1, BR6.3).

**Por que una pieza propia y no la del framework.** `langgraph-checkpoint-postgres`
trae sus tres tablas, ninguna con columna de aseguradora, y guarda el estado en
claro. Adaptarlas dejaba el aislamiento y el cifrado --las dos cosas que este
proyecto no puede fallar-- apoyados en la forma interna de tablas ajenas que una
actualizacion puede cambiar sin avisar. Esta clase implementa
`BaseCheckpointSaver` (de `langgraph-checkpoint`, que si se queda) sobre las
tablas propias de esta unidad, y es la unica pieza del proyecto que las escribe.

**Toda conexion sale del punto unico de sesion, con la aseguradora ya fijada.**
La aseguradora no se ata a la instancia: viaja en `config["configurable"]["tenant_id"]`
en cada llamada, la pone quien invoca el grafo. **Si no llega, falla cerrado**
(`MissingTenantError`): sin aseguradora no se lee ni se escribe nada, nunca se
asume una. Es el mismo patron que el resto del aplicativo -- una sesion por
llamada, nunca una conexion propia (convencion 7 del equipo).

**El hilo es el caso.** BR3.1: "un caso es un hilo del grafo". Por eso
`thread_id` y `case_id` son el mismo valor en las tres tablas de esta unidad, y
esta pieza nunca recibe un `case_id` aparte: lo deriva de `thread_id`.

**Lo que se guarda va cifrado.** El estado (`payload`), los metadatos del punto
de control (`metadata`) y cada escritura pendiente (`value`) se cifran con el
cifrador activo del caso (`untangle.case_record.crypto`), la misma puerta que usa
U4 para los campos del caso (BR6.3). El serializador del framework
(`self.serde`, `JsonPlusSerializer` por omision) produce bytes binarios, no
texto, asi que `Cipher.seal` --que solo acepta `str`-- los recibe en base64: eso
no abre una segunda puerta de cifrado, solo adapta el tipo de entrada a la unica
que ya existe.
"""

from __future__ import annotations

import base64
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    get_checkpoint_id,
    get_checkpoint_metadata,
)
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from untangle import observability
from untangle.case_record import crypto
from untangle.case_record.crypto import Cipher, from_storage
from untangle.case_record.models import KeyId
from untangle.tenancy import session
from untangle.tenancy.models import TenantId

_SIGUIENTE_PASO = """
    SELECT COALESCE(MAX(step), -1) + 1 AS siguiente
    FROM graph_checkpoint
    WHERE tenant_id = :tenant_id AND thread_id = :thread_id AND checkpoint_ns = :checkpoint_ns
"""

_INSERTAR_CHECKPOINT = """
    INSERT INTO graph_checkpoint
        (checkpoint_id, tenant_id, case_id, thread_id, checkpoint_ns, step,
         parent_checkpoint_id, payload_type, payload, metadata_type, metadata,
         sealed_key_id, created_at)
    VALUES
        (:checkpoint_id, :tenant_id, :case_id, :thread_id, :checkpoint_ns, :step,
         :parent_checkpoint_id, :payload_type, :payload, :metadata_type, :metadata,
         :sealed_key_id, :created_at)
"""

_COLUMNAS_CHECKPOINT = (
    "checkpoint_id, thread_id, checkpoint_ns, step, parent_checkpoint_id, "
    "payload_type, payload, metadata_type, metadata, sealed_key_id"
)

_LEER_POR_ID = f"""
    SELECT {_COLUMNAS_CHECKPOINT}
    FROM graph_checkpoint
    WHERE tenant_id = :tenant_id AND thread_id = :thread_id
      AND checkpoint_ns = :checkpoint_ns AND checkpoint_id = :checkpoint_id
"""  # noqa: S608 -- `_COLUMNAS_CHECKPOINT` es una constante del modulo, no una entrada; los valores van ligados

_LEER_ULTIMO = f"""
    SELECT {_COLUMNAS_CHECKPOINT}
    FROM graph_checkpoint
    WHERE tenant_id = :tenant_id AND thread_id = :thread_id AND checkpoint_ns = :checkpoint_ns
    ORDER BY step DESC
    LIMIT 1
"""  # noqa: S608 -- misma constante, mismo motivo

_LISTAR = f"""
    SELECT {_COLUMNAS_CHECKPOINT}
    FROM graph_checkpoint
    WHERE tenant_id = :tenant_id AND thread_id = :thread_id AND checkpoint_ns = :checkpoint_ns
      AND (CAST(:antes_de AS integer) IS NULL OR step < CAST(:antes_de AS integer))
    ORDER BY step DESC
"""  # noqa: S608 -- misma constante, mismo motivo

_LEER_ESCRITURAS = """
    SELECT task_id, idx, channel, value_type, value, sealed_key_id
    FROM graph_checkpoint_write
    WHERE tenant_id = :tenant_id AND thread_id = :thread_id
      AND checkpoint_ns = :checkpoint_ns AND checkpoint_id = :checkpoint_id
    ORDER BY task_id, idx
"""

_UPSERT_ESCRITURA = """
    INSERT INTO graph_checkpoint_write
        (tenant_id, case_id, thread_id, checkpoint_ns, checkpoint_id, task_id,
         task_path, idx, channel, value_type, value, sealed_key_id, created_at)
    VALUES
        (:tenant_id, :case_id, :thread_id, :checkpoint_ns, :checkpoint_id, :task_id,
         :task_path, :idx, :channel, :value_type, :value, :sealed_key_id, :created_at)
    ON CONFLICT (tenant_id, thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
    DO UPDATE SET channel = excluded.channel, value_type = excluded.value_type,
                  value = excluded.value, sealed_key_id = excluded.sealed_key_id
"""

_INSERTAR_ESCRITURA = """
    INSERT INTO graph_checkpoint_write
        (tenant_id, case_id, thread_id, checkpoint_ns, checkpoint_id, task_id,
         task_path, idx, channel, value_type, value, sealed_key_id, created_at)
    VALUES
        (:tenant_id, :case_id, :thread_id, :checkpoint_ns, :checkpoint_id, :task_id,
         :task_path, :idx, :channel, :value_type, :value, :sealed_key_id, :created_at)
    ON CONFLICT (tenant_id, thread_id, checkpoint_ns, checkpoint_id, task_id, idx) DO NOTHING
"""

_BORRAR_CHECKPOINTS_DEL_HILO = """
    DELETE FROM graph_checkpoint
    WHERE tenant_id = :tenant_id AND thread_id = :thread_id
"""

_BORRAR_ESCRITURAS_DEL_HILO = """
    DELETE FROM graph_checkpoint_write
    WHERE tenant_id = :tenant_id AND thread_id = :thread_id
"""


class MissingTenantError(RuntimeError):
    """Falta la aseguradora en `config['configurable']`.

    Falla cerrado (FD-U12-3): sin aseguradora no se lee ni se escribe nada, y
    esta clase nunca la asume ni la deriva de otro campo.
    """


class MissingThreadError(RuntimeError):
    """Falta `thread_id` en `config['configurable']`. Sin hilo no hay caso (BR3.1)."""


class CheckpointUnavailableError(RuntimeError):
    """Una fila de esta unidad no se pudo descifrar con la clave activa.

    Misma politica que U4 (`case_record.crypto.Unavailable`): la fila la cifro
    una clave que este proceso no tiene, o esta corrupta. A diferencia de un
    campo del caso, que se abre igual con un hueco senalado, un punto de control
    que no se puede leer **no se puede reanudar de verdad**, asi que aqui se
    levanta en vez de fingir un estado vacio.
    """


@dataclass(frozen=True)
class _Ambito:
    """La aseguradora, el hilo y el espacio de nombres de una llamada.

    Las tres viajan juntas en `config['configurable']` en cada metodo de la
    interfaz; agruparlas es lo que deja los metodos de mas abajo con pocos
    argumentos en vez de repetir el trio en cada firma.
    """

    tenant_id: TenantId
    thread_id: str
    checkpoint_ns: str


def _scope(config: RunnableConfig) -> _Ambito:
    """La aseguradora y el hilo de `config`, o falla cerrado si faltan (FD-U12-3, BR3.1)."""
    configurable = config.get("configurable") or {}
    tenant_id = configurable.get("tenant_id")
    if not tenant_id:
        msg = (
            "falta 'tenant_id' en config['configurable']: el checkpointer de U12 "
            "no asume ninguna aseguradora (FD-U12-3)"
        )
        raise MissingTenantError(msg)
    thread_id = configurable.get("thread_id")
    if not thread_id:
        msg = "falta 'thread_id' en config['configurable']: un hilo es un caso (BR3.1)"
        raise MissingThreadError(msg)
    return _Ambito(
        tenant_id=str(tenant_id),
        thread_id=str(thread_id),
        checkpoint_ns=str(configurable.get("checkpoint_ns") or ""),
    )


def _seal_bytes(cipher: Cipher, raw: bytes) -> bytes:
    """Cifra bytes arbitrarios con el cifrador del caso.

    `Cipher.seal` solo acepta `str` porque su unico llamador hasta ahora --U4--
    cifra texto de personas. El serializador del framework produce bytes
    binarios (msgpack), no texto: se codifican en base64 antes de sellarlos.
    Sigue habiendo una sola puerta de cifrado; esto solo adapta el tipo de
    entrada a la que esa puerta ya acepta.
    """
    return bytes(cipher.seal(base64.b64encode(raw).decode("ascii")))


def _unseal_bytes(cipher: Cipher, raw: bytes, *, key_id: str, field: str) -> bytes:
    abierto = cipher.unseal(from_storage(raw), stored_key_id=key_id)
    if isinstance(abierto, crypto.Unavailable):
        msg = f"'{field}' no se pudo descifrar: {abierto.reason}"
        raise CheckpointUnavailableError(msg)
    return base64.b64decode(abierto)


@dataclass(frozen=True)
class _FilaCheckpoint:
    """Una fila de `graph_checkpoint`, ya descifrada."""

    checkpoint_id: str
    thread_id: str
    checkpoint_ns: str
    step: int
    parent_checkpoint_id: str | None
    checkpoint: Checkpoint
    metadata: CheckpointMetadata


#: Los tipos propios que viajan dentro de un punto de control, declarados.
#:
#: **Sin esta lista LangGraph avisa en cada lectura y va a bloquearla.** El aviso es
#: literal --"Deserializing unregistered type ... This will be blocked in a future
#: version"-- y lo que bloquearia no es un detalle: son los valores que `intake`
#: escribe en `node_writes`, asi que el dia que se cumpla ninguna conversacion podria
#: reanudar donde la dejaron. Se vio corriendo la demo a mano, no en ninguna prueba:
#: el aviso va a la salida del proceso y ningun `assert` lo mira.
#:
#: Es ademas una lista que conviene tener escrita por si misma. Un punto de control es
#: un dato que sobrevive al proceso que lo escribio: lo que entra ahi tiene que poder
#: volver a salir en la version siguiente del codigo, y una lista explicita convierte
#: "lo que sea que un nodo haya metido" en "estas cuatro cosas, a proposito".
TIPOS_DEL_PUNTO_DE_CONTROL: tuple[tuple[str, str], ...] = (
    ("untangle.orchestration.nodes.intake.blocks", "Block"),
    ("untangle.orchestration.nodes.intake.extraction", "ExtractedField"),
    ("untangle.orchestration.nodes.intake.node", "SessionEnd"),
    ("untangle.telemetry.traces.models", "NodeName"),
    # Lo que escribe `policy_verification` desde que corre de verdad (BR4.2): el
    # desenlace de la cobertura y la vista de cada cita. Sin declararlos, el turno
    # siguiente leeria el desenlace como una cadena y `_has_coverage_answer` seguiria
    # diciendo que si mientras la comparacion contra el enum deja de coincidir.
    ("untangle.policy_rag.citations.models", "CoverageOutcome"),
    ("untangle.orchestration.nodes.policy_verification.node", "CoverageCitationView"),
    # La poliza que el corpus devolvio y espera el si de la persona (P3): viaja en
    # `intake_policy_match` entre el turno que la encontro y el que la confirma. Sin
    # declararla, el serializador la bloqueaba al leer (aviso en los logs de
    # produccion del 2026-10-06) y `_poliza_en_espera` la reconstruia del
    # diccionario; cuando el bloqueo sea definitivo, no habria nada que reconstruir.
    ("untangle.orchestration.nodes.intake.policy", "PolicyMatch"),
    # **El bloqueo ya llego** (langgraph-checkpoint 4.2, visto el 2026-10-13 en una
    # conversacion simulada: "Blocked deserialization of ... not in
    # allowed_msgpack_modules"). Faltaba lo que escriben `decision` y `compliance`, y la
    # lectura de confirmacion ya resuelta de `intake`: al leer el estado en el turno
    # siguiente volvian degradados y nada fallaba. Desde ese dia la lista no se mantiene de
    # memoria: `test_todo_tipo_que_un_nodo_puede_escribir_esta_declarado` recorre lo que
    # cada nodo declara que devuelve y exige que este aqui.
    ("untangle.orchestration.nodes.intake.node", "ReadbackResolution"),
    ("untangle.rules.models", "FiredRule"),
    ("untangle.compliance.controls.closure", "ClosureDecision"),
    ("untangle.compliance.controls.closure", "ClosureOutcome"),
    ("untangle.compliance.controls.closure", "HandoffReason"),
    ("untangle.compliance.controls.closure", "ComplianceFinding"),
    ("untangle.compliance.controls.models", "ComplianceReview"),
    ("untangle.compliance.controls.models", "FindingCode"),
)


def _serializador() -> JsonPlusSerializer:
    """El serializador del punto de control, con los tipos propios declarados."""
    return JsonPlusSerializer(allowed_msgpack_modules=TIPOS_DEL_PUNTO_DE_CONTROL)


class TenantCheckpointSaver(BaseCheckpointSaver[int]):
    """El checkpointer propio de U12. Una sola instancia sirve a toda aseguradora.

    No guarda estado propio de aseguradora ni de caso: los dos llegan en
    `config['configurable']` en cada llamada (`tenant_id`, `thread_id`). Es lo
    que permite una unica instancia compartida por el proceso, igual que el
    punto unico de sesion es una unica funcion compartida.
    """

    def __init__(self, *, cipher: Cipher | None = None) -> None:
        super().__init__(serde=_serializador())
        # `None` == "usa el cifrador instalado del proceso" (`crypto.active()`).
        # Fijarlo aqui es lo que deja a una prueba pasar uno propio sin instalar
        # uno global.
        self._cipher_override = cipher

    def _cipher(self) -> Cipher:
        return self._cipher_override if self._cipher_override is not None else crypto.active()

    def _decode_row(self, fila: Mapping[str, Any], cipher: Cipher) -> _FilaCheckpoint:
        payload = _unseal_bytes(
            cipher, bytes(fila["payload"]), key_id=fila["sealed_key_id"], field="payload"
        )
        metadata = _unseal_bytes(
            cipher, bytes(fila["metadata"]), key_id=fila["sealed_key_id"], field="metadata"
        )
        checkpoint = self.serde.loads_typed((fila["payload_type"], payload))
        checkpoint_metadata = self.serde.loads_typed((fila["metadata_type"], metadata))
        return _FilaCheckpoint(
            checkpoint_id=fila["checkpoint_id"],
            thread_id=fila["thread_id"],
            checkpoint_ns=fila["checkpoint_ns"],
            step=fila["step"],
            parent_checkpoint_id=fila["parent_checkpoint_id"],
            checkpoint=checkpoint,
            metadata=checkpoint_metadata,
        )

    async def _pending_writes(
        self,
        sesion: session.TenantSession,
        ambito: _Ambito,
        checkpoint_id: str,
        cipher: Cipher,
    ) -> list[tuple[str, str, Any]]:
        filas = await session.fetch_all(
            sesion,
            _LEER_ESCRITURAS,
            tenant_id=ambito.tenant_id,
            thread_id=ambito.thread_id,
            checkpoint_ns=ambito.checkpoint_ns,
            checkpoint_id=checkpoint_id,
        )
        escrituras: list[tuple[str, str, Any]] = []
        for fila in filas:
            crudo = _unseal_bytes(
                cipher,
                bytes(fila["value"]),
                key_id=fila["sealed_key_id"],
                field="graph_checkpoint_write.value",
            )
            valor = self.serde.loads_typed((fila["value_type"], crudo))
            escrituras.append((fila["task_id"], fila["channel"], valor))
        return escrituras

    def _tuple_from_row(
        self,
        decodificada: _FilaCheckpoint,
        pending_writes: list[tuple[str, str, Any]],
    ) -> CheckpointTuple:
        config: RunnableConfig = {
            "configurable": {
                "thread_id": decodificada.thread_id,
                "checkpoint_ns": decodificada.checkpoint_ns,
                "checkpoint_id": decodificada.checkpoint_id,
            }
        }
        parent_config: RunnableConfig | None = None
        if decodificada.parent_checkpoint_id is not None:
            parent_config = {
                "configurable": {
                    "thread_id": decodificada.thread_id,
                    "checkpoint_ns": decodificada.checkpoint_ns,
                    "checkpoint_id": decodificada.parent_checkpoint_id,
                }
            }
        return CheckpointTuple(
            config,
            decodificada.checkpoint,
            decodificada.metadata,
            parent_config,
            pending_writes or None,
        )

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        """El punto de control pedido, o el ultimo del hilo si no se pide uno (BR3.2)."""
        ambito = _scope(config)
        checkpoint_id = get_checkpoint_id(config)
        cipher = self._cipher()

        async with session.session_for(ambito.tenant_id) as sesion:
            if checkpoint_id:
                fila = await session.fetch_one(
                    sesion,
                    _LEER_POR_ID,
                    tenant_id=ambito.tenant_id,
                    thread_id=ambito.thread_id,
                    checkpoint_ns=ambito.checkpoint_ns,
                    checkpoint_id=checkpoint_id,
                )
            else:
                # BR3.2: reanudar sin pedir un paso concreto es leer el mayor.
                fila = await session.fetch_one(
                    sesion,
                    _LEER_ULTIMO,
                    tenant_id=ambito.tenant_id,
                    thread_id=ambito.thread_id,
                    checkpoint_ns=ambito.checkpoint_ns,
                )
            if fila is None:
                return None

            decodificada = self._decode_row(fila, cipher)
            escrituras = await self._pending_writes(
                sesion, ambito, decodificada.checkpoint_id, cipher
            )
            return self._tuple_from_row(decodificada, escrituras)

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,  # noqa: A002 -- nombre de la interfaz
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        """Los puntos de control de un hilo, del mas reciente al mas viejo.

        Esta unidad no hace viaje en el tiempo ni depuracion por metadatos: nadie
        en el aplicativo llama a esto con `filter`, y `config=None` --listar entre
        aseguradoras-- se rechaza en vez de inventar un recorrido sin aseguradora
        que fijar (BR6.1). Lo que si se respeta es `before` y `limit`, que es lo
        que la interfaz promete para paginar el historial de un hilo.
        """
        if config is None:
            msg = (
                "listar puntos de control sin 'config' recorreria todas las "
                "aseguradoras a la vez; el checkpointer de U12 no lo hace (BR6.1)"
            )
            raise MissingTenantError(msg)
        if filter:
            msg = "el checkpointer de U12 no filtra por metadatos: nadie en este aplicativo lo pide"
            raise NotImplementedError(msg)

        ambito = _scope(config)
        cipher = self._cipher()

        antes_de: int | None = None
        if before is not None:
            anterior_id = get_checkpoint_id(before)
            if anterior_id is not None:
                async with session.session_for(ambito.tenant_id) as sesion:
                    fila_antes = await session.fetch_one(
                        sesion,
                        _LEER_POR_ID,
                        tenant_id=ambito.tenant_id,
                        thread_id=ambito.thread_id,
                        checkpoint_ns=ambito.checkpoint_ns,
                        checkpoint_id=anterior_id,
                    )
                antes_de = fila_antes["step"] if fila_antes is not None else None

        async with session.session_for(ambito.tenant_id) as sesion:
            filas = await session.fetch_all(
                sesion,
                _LISTAR,
                tenant_id=ambito.tenant_id,
                thread_id=ambito.thread_id,
                checkpoint_ns=ambito.checkpoint_ns,
                antes_de=antes_de,
            )
            if limit is not None:
                filas = filas[:limit]
            for fila in filas:
                decodificada = self._decode_row(fila, cipher)
                escrituras = await self._pending_writes(
                    sesion, ambito, decodificada.checkpoint_id, cipher
                )
                yield self._tuple_from_row(decodificada, escrituras)

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Un punto de control por caso, despues de cada turno (BR3.1)."""
        ambito = _scope(config)
        # El punto de control que habia en `config` --si alguno-- es el padre
        # del que se esta guardando ahora: es asi como se encadena la reanudacion.
        parent_checkpoint_id = get_checkpoint_id(config)
        cipher = self._cipher()

        payload_type, payload_raw = self.serde.dumps_typed(checkpoint)
        metadata_completa = get_checkpoint_metadata(config, metadata)
        metadata_type, metadata_raw = self.serde.dumps_typed(metadata_completa)

        # **El paso se numera contra lo que haya, y si otro llego primero se vuelve a
        # numerar.** `MAX(step) + 1` leido y escrito en dos sentencias es una carrera,
        # y desde que el ritmo de fondo escribe su propio punto de control hay de
        # verdad dos escritores para el mismo hilo: el turno y la verificacion de
        # cobertura que ese turno lanzo. La unica del esquema los cazaba --que es lo
        # correcto, mejor chocar que pisarse-- pero el que perdia se quedaba sin
        # escribir, y lo que se perdia era la respuesta de cobertura.
        #
        # Un reintento y no un bucle: el diseno sigue siendo un turno activo por caso,
        # asi que dos escritores a la vez es lo normal y tres seria otra cosa que hay
        # que mirar, no absorber.
        paso = await self._insertar_con_paso_libre(
            ambito,
            checkpoint_id=checkpoint["id"],
            parent_checkpoint_id=parent_checkpoint_id,
            payload_type=payload_type,
            payload=_seal_bytes(cipher, payload_raw),
            metadata_type=metadata_type,
            metadata=_seal_bytes(cipher, metadata_raw),
            sealed_key_id=cipher.id,
        )

        observability.emit(
            "orchestration.checkpoint_saved",
            tenant_id=ambito.tenant_id,
            thread_id=ambito.thread_id,
            checkpoint_ns=ambito.checkpoint_ns,
            step=paso,
        )
        return {
            "configurable": {
                "thread_id": ambito.thread_id,
                "checkpoint_ns": ambito.checkpoint_ns,
                "checkpoint_id": checkpoint["id"],
            }
        }

    async def _insertar_con_paso_libre(  # noqa: PLR0913 -- la fila entera, ningun campo derivable de otro
        self,
        ambito: _Ambito,
        *,
        checkpoint_id: str,
        parent_checkpoint_id: str | None,
        payload_type: str,
        payload: bytes,
        metadata_type: str,
        metadata: bytes,
        sealed_key_id: KeyId,
        intentos: int = 2,
    ) -> int:
        """Inserta el punto de control numerando su paso, y renumera si otro se adelanto.

        Devuelve el paso con el que quedo escrito. Levanta si tras los intentos sigue
        chocando: un tercer escritor en el mismo hilo no es una carrera normal, es un
        sintoma, y absorberlo lo dejaria sin ver.
        """
        for intento in range(1, intentos + 1):
            paso = -1
            try:
                # El `async with` va **dentro** del `try` a proposito: la sesion
                # confirma al salir, asi que el choque de la unica no aparece en la
                # sentencia sino al cerrar. Con el `try` por dentro, el reintento no
                # veia nada y la excepcion salia igual.
                async with session.session_for(ambito.tenant_id) as sesion:
                    siguiente = await session.fetch_one(
                        sesion,
                        _SIGUIENTE_PASO,
                        tenant_id=ambito.tenant_id,
                        thread_id=ambito.thread_id,
                        checkpoint_ns=ambito.checkpoint_ns,
                    )
                    paso = int(siguiente["siguiente"]) if siguiente is not None else 0
                    await session.execute_sql(
                        sesion,
                        _INSERTAR_CHECKPOINT,
                        checkpoint_id=checkpoint_id,
                        tenant_id=ambito.tenant_id,
                        case_id=ambito.thread_id,
                        thread_id=ambito.thread_id,
                        checkpoint_ns=ambito.checkpoint_ns,
                        step=paso,
                        parent_checkpoint_id=parent_checkpoint_id,
                        payload_type=payload_type,
                        payload=payload,
                        metadata_type=metadata_type,
                        metadata=metadata,
                        sealed_key_id=sealed_key_id,
                        created_at=datetime.now(UTC),
                    )
            except session.UniqueViolation:
                if intento == intentos:
                    raise
                observability.emit(
                    "orchestration.checkpoint_step_taken",
                    tenant_id=ambito.tenant_id,
                    thread_id=ambito.thread_id,
                    step=paso,
                )
                continue
            return paso
        msg = "inalcanzable: el bucle devuelve o levanta"  # pragma: no cover
        raise AssertionError(msg)  # pragma: no cover

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """Las escrituras de un paso que todavia no se guardo como punto de control."""
        ambito = _scope(config)
        checkpoint_id = get_checkpoint_id(config)
        if not checkpoint_id:
            msg = "aput_writes necesita 'checkpoint_id' en config['configurable']"
            raise MissingThreadError(msg)
        cipher = self._cipher()

        # Canales especiales (error, reintento programado, interrupcion,
        # reanudacion): una repeticion del mismo trabajo **reemplaza** su
        # escritura. Canales normales: la primera escritura gana, una repeticion
        # no la pisa (misma regla que la pieza oficial, WRITES_IDX_MAP).
        #
        # La sentencia se elige **por escritura y no por lote**: un lote mixto es
        # justo lo que deja un nodo que interrumpe despues de haber escrito algo,
        # y decidir por lote descartaria en silencio el nuevo motivo de la pausa
        # al reintentarse el nodo (BR4.1).
        ahora = datetime.now(UTC)
        async with session.session_for(ambito.tenant_id) as sesion:
            for posicion, (canal, valor) in enumerate(writes):
                tipo, crudo = self.serde.dumps_typed(valor)
                await session.execute_sql(
                    sesion,
                    _UPSERT_ESCRITURA if canal in WRITES_IDX_MAP else _INSERTAR_ESCRITURA,
                    tenant_id=ambito.tenant_id,
                    case_id=ambito.thread_id,
                    thread_id=ambito.thread_id,
                    checkpoint_ns=ambito.checkpoint_ns,
                    checkpoint_id=checkpoint_id,
                    task_id=task_id,
                    task_path=task_path,
                    idx=WRITES_IDX_MAP.get(canal, posicion),
                    channel=canal,
                    value_type=tipo,
                    value=_seal_bytes(cipher, crudo),
                    sealed_key_id=cipher.id,
                    created_at=ahora,
                )

    async def adelete_thread(self, thread_id: str) -> None:
        """Borra los puntos de control y las escrituras pendientes de un hilo.

        No la llama nadie en este aplicativo hoy -- el caso se borra completo
        por el purgador de U4, y la cascada se lleva las dos tablas (BR6.4) --
        pero la interfaz la declara y una implementacion que la dejara sin
        aseguradora que fijar seria un `DELETE` sin filtrar, asi que exige la
        misma sesion por aseguradora que todo lo demas aqui.
        """
        msg = (
            "adelete_thread necesita una aseguradora: llame a "
            "delete_thread_for(tenant_id, thread_id), no a este metodo de la "
            "interfaz generica"
        )
        raise MissingTenantError(msg)

    async def delete_thread_for(self, tenant_id: TenantId, thread_id: str) -> None:
        """La forma real de borrar un hilo, con la aseguradora explicita.

        `BaseCheckpointSaver.adelete_thread(thread_id)` no tiene donde poner la
        aseguradora en su firma; esta unidad prefiere fallar cerrado a
        adivinarla, asi que ofrece esta version con la aseguradora explicita
        para quien de verdad la necesite.
        """
        async with session.session_for(tenant_id) as sesion:
            await session.execute_sql(
                sesion, _BORRAR_ESCRITURAS_DEL_HILO, tenant_id=tenant_id, thread_id=thread_id
            )
            await session.execute_sql(
                sesion, _BORRAR_CHECKPOINTS_DEL_HILO, tenant_id=tenant_id, thread_id=thread_id
            )
