"""Donde el resumen de traza se guarda y de donde se lee (C-23, BR6.6, BR7.4).

**Ninguna conexion propia.** Toda consulta pasa por el punto unico de sesion de
U2. Este archivo no sabe la direccion de la base, no construye un motor y no arma
SQL por concatenacion: los parametros se ligan.

## Con aseguradora fijada, al reves que el dinero

`spend/repository.py` pide una sesion **sin** aseguradora, porque sus cuatro
tablas son dato del proyecto y no tienen politica que fijar (BR7.1). Aqui es al
reves y por la misma razon leida del otro lado: el resumen de traza es la
**unica** de las cinco tablas de esta unidad que es dato de un visitante
(BR7.4). Lleva su
columna de aseguradora, su aislamiento habilitado y forzado, y su politica.

La consecuencia se ve en las lecturas de abajo: **ninguna filtra por aseguradora
en su `WHERE`**. No hace falta y seria peor, porque invitaria a creer que el
filtro es de este codigo. Lo hace la politica de fila, antes de que ninguna fila
llegue hasta aqui: un resumen de otra aseguradora no se devuelve y se disimula,
sino que la consulta devuelve cero filas y este archivo **no tendria forma de
distinguirlo** de un resumen que no existe aunque quisiera. Es la misma forma que
usa `case_record/repository.py`.

## El sujeto es el resumen de la clave, y nunca la clave

La columna guarda el resumen de la clave del navegador, nunca la clave (BR7.3), y
ese resumen **no se calcula en esta unidad**: lo calcula quien tiene la clave, con
`tenancy.visitor_access.visitor_key_digest`, que es la unica definicion del
proyecto. Dos funciones que hoy dan el mismo resumen son dos que manana pueden
dejar de darlo, y el dia que dejaran de coincidir ningun visitante volveria a ver
su propio resumen.

Envolverla aqui tampoco valdria: `tenancy.visitor_access` arrastra el punto de
sesion, y la superficie de las trazas es justamente lo que no puede arrastrarlo
(ver mas abajo).

## Por que `api.py` no importa este archivo

Se instala, como el transporte de la exportacion, y esa direccion no es gusto:

1. `untangle.evals` tiene un contrato de importacion --`evals-sin-base-de-datos`--
   que le prohibe llegar a `untangle.tenancy.session`, **tambien por cadena**. Es
   lo que mantiene vivo el camino "del clon al reporte" sin base de datos, y con
   ello la cifra publicada de NFR21. El reporte de evaluaciones enlaza trazas; el
   dia que importe `telemetry.traces.api`, si esa superficie arrastrara la base,
   la cifra se rompe sin que nadie lo pida.
2. La superficie se queda sin saber que existe una base, que es lo que permite
   que las pruebas unitarias de las trazas corran sin levantar ninguna.

Quien lo instala es la raiz de composicion (C-24), en el paso 22 de esta unidad.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import TypeAdapter

from untangle.telemetry.spend.models import CostStatus, Money
from untangle.telemetry.traces.models import (
    NodeTiming,
    TraceId,
    TraceSummary,
    TraceSummaryStatus,
)
from untangle.tenancy import session

#: Los nodos viajan como un solo valor JSON y no como tabla aparte: se escriben
#: en un solo acto --al completarse el rastro-- y se leen enteros. Ninguna
#: consulta del producto pregunta por un nodo suelto, y una tabla hija obligaria
#: a una segunda escritura que podria quedarse a medias.
_NODOS = TypeAdapter(tuple[NodeTiming, ...])

#: Inserta o completa. El resumen nace `recording` cuando sale la respuesta y se
#: reescribe entero al pasar a `ready` o a `lost`: son tres estados de la misma
#: fila, no tres filas.
#:
#: El `DO UPDATE` repite la condicion de aseguradora aunque la politica de fila ya
#: la imponga. No es redundancia inutil: en un `ON CONFLICT`, el conflicto de
#: clave se detecta **antes** que la politica, asi que sin esta linea un
#: identificador de traza repetido entre aseguradoras se convertiria en un error
#: del motor en vez de en una fila que no se toca.
GUARDAR = """
    INSERT INTO trace_summary (
        trace_id, tenant_id, case_id, visitor_key_hash, turn_ref, nodes,
        clauses_retrieved, clauses_verified, latency_ms, cost_usd, cost_status,
        status, created_at
    ) VALUES (
        :trace_id, :tenant_id, :case_id, :visitor_key_hash, :turn_ref,
        CAST(:nodes AS jsonb),
        :clauses_retrieved, :clauses_verified, :latency_ms, :cost_usd, :cost_status,
        :status, :created_at
    )
    ON CONFLICT (trace_id) DO UPDATE
       SET nodes = EXCLUDED.nodes,
           clauses_retrieved = EXCLUDED.clauses_retrieved,
           clauses_verified = EXCLUDED.clauses_verified,
           latency_ms = EXCLUDED.latency_ms,
           cost_usd = EXCLUDED.cost_usd,
           cost_status = EXCLUDED.cost_status,
           status = EXCLUDED.status
     WHERE trace_summary.tenant_id = :tenant_id
"""

LEER_POR_TRAZA = "SELECT * FROM trace_summary WHERE trace_id = :trace_id"

#: El ultimo resumen de un caso. `created_at` decide, y el identificador desempata
#: para que dos respuestas del mismo instante devuelvan siempre la misma y la
#: lectura no dependa del orden en que el motor las guardo.
LEER_ULTIMO_DEL_CASO = """
    SELECT * FROM trace_summary
     WHERE case_id = :case_id
     ORDER BY created_at DESC, trace_id DESC
     LIMIT 1
"""

#: El ultimo resumen de **cada** caso de una lista, en una sola lectura: el mismo orden
#: que `LEER_ULTIMO_DEL_CASO`, aplicado por caso. Para las superficies que muestran
#: varios casos y no pueden pagar una consulta por fila.
LEER_ULTIMOS_DE_VARIOS_CASOS = """
    SELECT DISTINCT ON (case_id) * FROM trace_summary
     WHERE case_id = ANY(:case_ids)
     ORDER BY case_id, created_at DESC, trace_id DESC
"""


def _a_resumen(fila: Mapping[str, Any]) -> TraceSummary:
    """La fila, de vuelta al modelo. Con sus invariantes vueltas a comprobar.

    Se reconstruye por el constructor y no por un atajo: un resumen `ready` sin
    nodos o con mas clausulas verificadas que recuperadas levanta aqui igual que
    levantaria al escribirse. Una fila que la base dejara pasar --porque alguien
    la escribio a mano-- no se convierte en un modelo que miente.
    """
    estado = TraceSummaryStatus(fila["status"])
    costo = fila["cost_usd"]
    return TraceSummary(
        trace_id=str(fila["trace_id"]),
        tenant_id=str(fila["tenant_id"]),
        case_id=str(fila["case_id"]),
        visitor_key_hash=str(fila["visitor_key_hash"]),
        turn_ref=fila["turn_ref"],
        nodes=_NODOS.validate_python(fila["nodes"]),
        clauses_retrieved=int(fila["clauses_retrieved"]),
        clauses_verified=int(fila["clauses_verified"]),
        latency_ms=fila["latency_ms"],
        cost=Money(amount_usd=costo, status=CostStatus(fila["cost_status"])),
        status=estado,
        created_at=fila["created_at"],
    )


def _de_resumen(summary: TraceSummary) -> dict[str, Any]:
    """El modelo, tal como va a la sentencia. Los enums salen por su valor."""
    return {
        "trace_id": summary.trace_id,
        "tenant_id": summary.tenant_id,
        "case_id": summary.case_id,
        "visitor_key_hash": summary.visitor_key_hash,
        "turn_ref": summary.turn_ref,
        "nodes": _NODOS.dump_json(summary.nodes).decode("utf-8"),
        "clauses_retrieved": summary.clauses_retrieved,
        "clauses_verified": summary.clauses_verified,
        "latency_ms": summary.latency_ms,
        "cost_usd": summary.cost.amount_usd,
        "cost_status": summary.cost.status.value,
        "status": summary.status.value,
        "created_at": summary.created_at,
    }


class DatabaseSummaryStore:
    """El almacen de verdad: la tabla `trace_summary`, por el punto unico.

    Implementa `api.SummaryStore`. No se declara heredando del `Protocol` a
    proposito: la conformidad la comprueba el comprobador de tipos en el sitio
    donde se instala, que es donde importa.
    """

    async def put(self, summary: TraceSummary) -> None:
        """Escribe el resumen, o completa el que ya existe. Los tres estados, una fila."""
        async with session.session_for(summary.tenant_id) as sesion:
            await session.execute_sql(sesion, GUARDAR, **_de_resumen(summary))

    async def get(self, trace_id: TraceId, *, tenant_id: str) -> TraceSummary | None:
        async with session.session_for(tenant_id) as sesion:
            fila = await session.fetch_one(sesion, LEER_POR_TRAZA, trace_id=trace_id)
        return _a_resumen(fila) if fila is not None else None

    async def latest_for_case(self, case_id: str, *, tenant_id: str) -> TraceSummary | None:
        async with session.session_for(tenant_id) as sesion:
            fila = await session.fetch_one(sesion, LEER_ULTIMO_DEL_CASO, case_id=case_id)
        return _a_resumen(fila) if fila is not None else None

    async def latest_for_cases(
        self, case_ids: Sequence[str], *, tenant_id: str
    ) -> dict[str, TraceSummary]:
        if not case_ids:
            return {}
        async with session.session_for(tenant_id) as sesion:
            filas = await session.fetch_all(
                sesion, LEER_ULTIMOS_DE_VARIOS_CASOS, case_ids=list(case_ids)
            )
        resumenes = (_a_resumen(fila) for fila in filas)
        return {resumen.case_id: resumen for resumen in resumenes}


__all__ = [
    "GUARDAR",
    "LEER_POR_TRAZA",
    "LEER_ULTIMOS_DE_VARIOS_CASOS",
    "LEER_ULTIMO_DEL_CASO",
    "DatabaseSummaryStore",
]
