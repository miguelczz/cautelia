"""El ejecutor comun de nodos (pasos 4 y 5 de U12): la politica de fallo es dato (BR5.1 a BR5.5).

**Sin ninguna rama por nombre de nodo (BR5.1).** Todo lo que distingue a un nodo
de otro -- tiempo maximo, intentos, quien los cuenta y la clave de degradacion --
sale de su `NodeSpec` (C-15). Este modulo no importa ni menciona ninguno de los
cuatro paquetes de `orchestration.nodes.*`, y es exactamente esa ausencia la que
hace la regla comprobable: un `if spec.name == ...` no tiene donde esconderse si
el modulo entero no sabe que nodos existen.

**La taxonomia cerrada ya llega cerrada.** `ProviderError.kind` es
`ProviderErrorKind` desde la frontera del adaptador (`providers/ports.py`,
convencion 8a): este modulo no traduce nada, solo lee `.kind`. Lo unico que
agrega es `TIMEOUT` cuando el propio tiempo maximo del `NodeSpec` se agota --
`asyncio.wait_for` es quien lo hace cumplir, porque un nodo no tiene por que
saber cuanto tiempo le queda.

**Que hace un intento agotado.** El nodo deja subir la excepcion (C-15); el
ejecutor no la vuelve a subir. Escribe la fila de `NodeRun` de BR5.4 con el
`error_type` final, y devuelve un `NodeExecutionResult` con la **clave** del
catalogo de la frase de degradacion -- nunca la frase (convencion 4 del
equipo). Resolver esa clave a texto con `copy_catalog.api.t` y hacerla pasar
por `guard_output`, el punto unico de salida, es del paso 7 de esta unidad,
que todavia no existe: escribir la frase aqui adelantaria una frontera que ese
paso todavia no fija (que idioma, que turno, quien la dice). Es la misma
frontera, explicita y escrita, que el aviso de este paso pide dejar en vez de
suponerla.

**Que hace un relanzamiento (BR5.4).** Antes de llamar al nodo, se busca una
fila existente por la clave de idempotencia. Si ya esta en un desenlace
terminal (`succeeded` o `degraded`), no se llama al nodo otra vez: un
`succeeded` no trae su salida de vuelta -- LangGraph ya avanzo el grafo con lo
que esa corrida escribio (C-15: "la persistencia la hacen los modulos de
capacidad con clave idempotente") --, y lo unico que un relanzamiento puede
repetir sin gastar de nuevo es un `degraded` ya resuelto. Si la fila quedo a
medias (`running`, el proceso murio entre un intento fallido y el siguiente),
los intentos se retoman donde se quedaron en vez de reiniciar la cuenta.

**Que no hace este paso.** No construye la entrada tipada de un nodo a partir
del `GraphState` (eso es de quien invoque el grafo real, todavia sin construir);
y abre su tramo de nodo dando por hecho que ya hay un turno abierto encima
(`telemetry.traces.api.turn_span`) -- exactamente lo que un turno de verdad deja
puesto, y lo que las pruebas de este paso abren a mano.

## Enmienda del paso 5: el plazo del ritmo del turno es de la ejecucion completa

**El hallazgo.** `INTAKE_SPEC` -- el unico nodo del ritmo del turno -- declara
`timeout_ms=1_600` y `attempts=2`. Aplicar ese tiempo maximo **por intento**, como
hacia este modulo hasta este paso, deja un proveedor lento gastar 1.600 + 1.600 =
3.200 ms en el camino del turno: el cuadruple de la meta p95 de 800 ms que el PRD
aprobo (`nfr-requirements/performance-requirements.md`, "Por que PERF-U12.4 son
1.600 ms"). Ese documento fijo el techo como "el doble de la meta p95" y no
contemplo el reintento.

**La resolucion.** En el ritmo del turno, `timeout_ms` es el plazo de **la
ejecucion completa**, reintentos incluidos, no el de cada intento: quien espera
es la persona, y a la persona no le importa cuantos intentos hubo, le importa
cuando deja de esperar. En el ritmo de fondo nada cambia -- nadie los espera, y
los 60.000 ms de `policy_verification` siguen siendo correctos por la razon que
su propio modulo escribe --, y la diferencia la marca `spec.rhythm`, ya dato del
`NodeSpec`: ninguna rama por nombre de nodo (BR5.1) se necesita para esto.

**Como se mide el plazo restante.** Con el reloj **real** del bucle de eventos
(`asyncio.get_running_loop().time()`), nunca con `ClockPort`: `ClockPort` es el
reloj inyectado para el registro de `NodeRun` (deterministico en las pruebas,
como el resto de la unidad), y el plazo que hace cumplir `asyncio.wait_for` ya
era -- desde el paso 4 -- tiempo real del bucle, no tiempo de ese reloj de
pruebas. Mezclar los dos dejaria el plazo del ritmo del turno dependiendo de
cuanto avance el reloj falso en cada prueba, en vez de cuanto tiempo de verdad
paso.

## Enmienda del paso 5: el arrendamiento con latido (BR5.5)

Cada intento escribe su fila `running` **antes** de llamar al nodo -- no solo
despues de que falle, como hacia el paso 4 -- con `lease_owner` (este proceso),
`lease_expires_at` (el intento mas un margen de seguridad) y `heartbeat_at` (el
mismo instante). Un desenlace terminal (`succeeded`/`degraded`) suelta el
arrendamiento sin mas: nadie necesita retomar un trabajo que ya termino. El
barrido que toma lo vencido es `sweep.py`; este modulo solo renueva el latido
mientras esta vivo.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from untangle.base import Frozen, ProviderErrorKind
from untangle.copy_catalog.api import CopyKey
from untangle.orchestration.node_run import (
    TERMINAL_OUTCOMES,
    NodeRunOutcome,
    NodeRunRecord,
    NodeRunStore,
    idempotency_key,
)
from untangle.orchestration.state import NodeSpec
from untangle.providers.ports import ProviderError
from untangle.telemetry.traces import api as traces
from untangle.tenancy.models import TenantId

#: BR5.5: cuanto sobrevive un arrendamiento mas alla del propio tiempo maximo
#: del nodo. `asyncio.wait_for` ya acota la duracion real de un intento a
#: `spec.timeout_ms`; el margen es solo para que escribir el desenlace final
#: (la vuelta a la base tras el `wait_for`) no alcance a vencer un arrendamiento
#: que un proceso vivo todavia esta cerrando.
_LEASE_MARGIN = timedelta(seconds=5)


class Node[NodeInputT: Frozen, NodeOutputT](Protocol):
    """Lo que un nodo real implementa (C-15): su especificacion y su turno puro.

    `run` es **puro**: recibe su entrada tipada y devuelve su salida, sin abrir
    transacciones ni capturar su propio fallo para seguir adelante -- eso es
    justo lo que este ejecutor hace en su lugar.
    """

    spec: NodeSpec

    async def run(self, state: NodeInputT) -> NodeOutputT: ...


#: El reloj, inyectado como en el resto de la unidad: dos corridas identicas
#: tienen que medir la misma latencia sin depender de cuanto tarde la maquina.
ClockPort = Callable[[], datetime]


@dataclass(frozen=True)
class NodeExecutionResult[NodeOutputT]:
    """Lo que `NodeExecutor.run` devuelve. Nunca una excepcion de politica (BR5.2, BR5.3).

    Exactamente uno de los dos desenlaces: `SUCCEEDED` con `output` puesto, o
    `DEGRADED` con `degraded_copy_key` y `error_kind` puestos y `output` en
    `None`. Un relanzamiento sobre un trabajo ya `SUCCEEDED` puede devolver este
    resultado sin `output` (ver el docstring del modulo): quien reciba un
    `SUCCEEDED` sin salida sabe que el valor ya esta en otro lado, no que se
    perdio.
    """

    outcome: NodeRunOutcome
    attempts: int
    output: NodeOutputT | None = None
    degraded_copy_key: CopyKey | None = None
    error_kind: ProviderErrorKind | None = None


def _max_attempts(spec: NodeSpec) -> int:
    """BR5.1 como dato: cuantas veces llama **el ejecutor**, nunca por nombre de nodo.

    Cuando el propio nodo cuenta sus reintentos (`retries_owned_by == "node"`,
    FD-U12-2), el ejecutor llama una sola vez: un segundo bucle por encima
    duplicaria las llamadas que el nodo ya hizo por su cuenta.
    """
    return spec.attempts if spec.retries_owned_by == "executor" else 1


class NodeExecutor:
    """El ejecutor comun (C-15, BR5.1): una politica que lee de `NodeSpec`, sin ramas."""

    def __init__(self, *, store: NodeRunStore, clock: ClockPort, owner: str | None = None) -> None:
        self._store = store
        self._clock = clock
        # BR5.5: quien tiene el arrendamiento. Un identificador por instancia y
        # no por llamada -- todo lo que este proceso ejecuta con este
        # `NodeExecutor` es del mismo dueno -- generado si no se pasa uno, para
        # que las pruebas que no les importa quien lo tiene no tengan que
        # inventarlo.
        self._owner = owner if owner is not None else uuid.uuid4().hex

    async def run[NodeInputT: Frozen, NodeOutputT](
        self,
        node: Node[NodeInputT, NodeOutputT],
        node_input: NodeInputT,
        *,
        tenant_id: TenantId,
        case_id: str,
        timeout_ms: int | None = None,
    ) -> NodeExecutionResult[NodeOutputT]:
        """Corre el nodo con la politica de su `NodeSpec` (BR5.1 a BR5.5).

        `timeout_ms` sustituye al de la especificacion **solo para esta llamada**.
        Existe porque un mismo nodo sirve a dos canales con presupuestos distintos:
        el plazo de `intake` sale de doblar la meta p95 de la **voz**, donde alguien
        espera al telefono, y el chat lo heredaba por compartir el `NodeSpec`.
        Quien invoca el grafo sabe por que canal entro el turno; el nodo no, y el
        ejecutor tampoco. Sin el argumento, manda la especificacion.
        """
        spec = node.spec
        clave = idempotency_key(
            tenant_id=tenant_id, case_id=case_id, node=spec.name, node_input=node_input
        )

        previo = await self._store.find(tenant_id=tenant_id, idempotency_key=clave)
        if previo is not None and previo.outcome in TERMINAL_OUTCOMES:
            return self._resultado_cacheado(spec, previo)

        return await self._ejecutar(
            node,
            node_input,
            tenant_id=tenant_id,
            case_id=case_id,
            idempotency_key=clave,
            previo=previo,
            timeout_ms=timeout_ms,
        )

    def _resultado_cacheado[NodeOutputT](
        self, spec: NodeSpec, previo: NodeRunRecord
    ) -> NodeExecutionResult[NodeOutputT]:
        """BR5.4: la fila ya es terminal, asi que no se llama al nodo otra vez."""
        if previo.outcome is NodeRunOutcome.DEGRADED:
            return NodeExecutionResult(
                outcome=NodeRunOutcome.DEGRADED,
                attempts=previo.attempt,
                degraded_copy_key=CopyKey(spec.degraded_copy_key),
                error_kind=previo.error_type,
            )
        return NodeExecutionResult(outcome=NodeRunOutcome.SUCCEEDED, attempts=previo.attempt)

    def _deadline_s(
        self, spec: NodeSpec, *, reloj_real_inicio: float | None, timeout_ms: int | None = None
    ) -> float:
        """El plazo real, en segundos, del **proximo** intento.

        Ritmo de fondo: sin cambios desde el paso 4 -- `spec.timeout_ms` completo,
        porque nadie espera a un nodo de fondo y cada intento tiene su propio
        presupuesto (BR5.2).

        Ritmo del turno: `spec.timeout_ms` es el plazo de **toda la ejecucion**,
        no el de cada intento (enmienda del paso 5, ver el docstring del
        modulo). `reloj_real_inicio` es la lectura de `asyncio.get_running_loop().time()`
        tomada antes del primer intento; lo que resta se calcula contra el reloj
        real del bucle, nunca contra `self._clock()` (`ClockPort` es solo para
        el registro de `NodeRun`). Un plazo agotado antes de intentarlo devuelve
        `0.0` en vez de un numero negativo: `asyncio.wait_for` con un plazo
        negativo es un error de programacion, no un timeout.
        """
        presupuesto_ms = timeout_ms if timeout_ms is not None else spec.timeout_ms
        if spec.rhythm != "turn" or reloj_real_inicio is None:
            return presupuesto_ms / 1000
        transcurrido_s = asyncio.get_running_loop().time() - reloj_real_inicio
        return max(0.0, presupuesto_ms / 1000 - transcurrido_s)

    async def _ejecutar[NodeInputT: Frozen, NodeOutputT](  # noqa: PLR0913 -- el nodo, su entrada y las tres llaves de identidad de la fila (tenant, caso, clave), ninguna derivable de otra
        self,
        node: Node[NodeInputT, NodeOutputT],
        node_input: NodeInputT,
        *,
        tenant_id: TenantId,
        case_id: str,
        idempotency_key: str,
        previo: NodeRunRecord | None,
        timeout_ms: int | None,
    ) -> NodeExecutionResult[NodeOutputT]:
        spec = node.spec
        maximo = _max_attempts(spec)
        intento = previo.attempt if previo is not None else 0
        # Una fila resumida siempre llega sin `error_type`: una fila `running`
        # nunca lo lleva (ver el porque en el `upsert` de abajo), asi que un
        # relanzamiento a medias no hereda el tipo del fallo anterior y lo
        # vuelve a determinar con su proximo intento.
        ultimo_error: ProviderErrorKind | None = None
        inicio = previo.started_at if previo is not None else self._clock()
        # BR5.5, enmienda del paso 5: el reloj real del bucle, tomado una sola
        # vez por llamada a `run()` -- no por proceso ni por caso -- porque el
        # plazo que esta enmienda acota es el de **esta** ejecucion. Solo se lee
        # para el ritmo del turno; `_deadline_s` ignora el valor en el de fondo.
        reloj_real_inicio = asyncio.get_running_loop().time() if spec.rhythm == "turn" else None

        with traces.node_span(spec.name) as tramo:
            salida: NodeOutputT | None = None
            exito = False
            while intento < maximo:
                intento += 1

                # BR5.3 y BR5.5: rastro doble y arrendamiento renovado **antes**
                # de llamar al nodo, no solo despues de que falle -- a
                # diferencia del paso 4, que solo escribia esta fila tras un
                # intento agotado. Sin esto, un proceso que muriera durante el
                # primer intento no dejaria ninguna fila que un barrido pudiera
                # encontrar (BR5.5 exige un arrendamiento que vencer, y un
                # arrendamiento que nunca se escribio no vence, se pierde).
                #
                # `error_type` **no** viaja en esta fila: la restriccion
                # `node_run_error_con_su_desenlace` de la migracion exige que
                # solo lo lleven `failed` y `degraded`, nunca `running` -- un
                # intento en curso, por definicion, todavia no tiene un
                # desenlace que ese error explique. El tipo del ultimo fallo
                # vive en `ultimo_error`, en memoria, hasta que el bucle
                # termine y sea de verdad el error final.
                ahora = self._clock()
                await self._store.upsert(
                    NodeRunRecord(
                        tenant_id=tenant_id,
                        case_id=case_id,
                        node=spec.name,
                        rhythm=spec.rhythm,
                        attempt=intento,
                        max_attempts=spec.attempts,
                        outcome=NodeRunOutcome.RUNNING,
                        idempotency_key=idempotency_key,
                        started_at=inicio,
                        lease_owner=self._owner,
                        lease_expires_at=ahora
                        + timedelta(milliseconds=spec.timeout_ms)
                        + _LEASE_MARGIN,
                        heartbeat_at=ahora,
                    )
                )

                plazo_s = self._deadline_s(
                    spec, reloj_real_inicio=reloj_real_inicio, timeout_ms=timeout_ms
                )
                try:
                    if plazo_s <= 0:
                        # BR2.2/PERF-U12.4: el presupuesto de la ejecucion
                        # entera ya se agoto en un intento anterior. Ni
                        # siquiera se llama al nodo -- no queda tiempo que
                        # darle -- y cuenta como el mismo `TIMEOUT` que un
                        # `wait_for` real habria producido.
                        raise TimeoutError
                    salida = await asyncio.wait_for(node.run(node_input), timeout=plazo_s)
                except TimeoutError:
                    ultimo_error = ProviderErrorKind.TIMEOUT
                except ProviderError as error:
                    ultimo_error = error.kind
                else:
                    exito = True
                    break

            fin = self._clock()
            latencia_ms = max(0, int((fin - inicio).total_seconds() * 1000))

            if exito:
                tramo.set({"untangle.attempt": intento})
                await self._store.upsert(
                    NodeRunRecord(
                        tenant_id=tenant_id,
                        case_id=case_id,
                        node=spec.name,
                        rhythm=spec.rhythm,
                        attempt=intento,
                        max_attempts=spec.attempts,
                        outcome=NodeRunOutcome.SUCCEEDED,
                        idempotency_key=idempotency_key,
                        started_at=inicio,
                        finished_at=fin,
                        latency_ms=latencia_ms,
                    )
                )
                return NodeExecutionResult(
                    outcome=NodeRunOutcome.SUCCEEDED, attempts=intento, output=salida
                )

            # BR5.2, BR5.3: se agotaron los intentos. No sube ninguna
            # excepcion -- el caso y el turno se conservan -- y el desenlace es
            # `degraded` con la clave de su frase, nunca la frase misma.
            #
            # `ultimo_error` solo seria `None` aqui si `maximo` fuera 0, que
            # `NodeSpec.__post_init__` ya rechaza (`attempts >= 1`); el
            # respaldo existe para que el tipo no dependa de esa garantia
            # ajena, y para que un relanzamiento que llegara sin motivo
            # registrado degrade en vez de reventar el turno.
            error_final = ultimo_error or ProviderErrorKind.UNAVAILABLE
            tramo.set({"untangle.attempt": intento, "untangle.error_kind": error_final})
            await self._store.upsert(
                NodeRunRecord(
                    tenant_id=tenant_id,
                    case_id=case_id,
                    node=spec.name,
                    rhythm=spec.rhythm,
                    attempt=intento,
                    max_attempts=spec.attempts,
                    outcome=NodeRunOutcome.DEGRADED,
                    idempotency_key=idempotency_key,
                    started_at=inicio,
                    finished_at=fin,
                    error_type=error_final,
                    latency_ms=latencia_ms,
                )
            )
            return NodeExecutionResult(
                outcome=NodeRunOutcome.DEGRADED,
                attempts=intento,
                degraded_copy_key=CopyKey(spec.degraded_copy_key),
                error_kind=error_final,
            )


__all__ = ["ClockPort", "Node", "NodeExecutionResult", "NodeExecutor"]
