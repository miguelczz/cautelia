"""Donde la activacion se escribe y de donde se lee (BR8.1, BR8.5).

**Ninguna conexion propia.** Toda consulta pasa por el punto unico de sesion de
U2, con la aseguradora fijada: las dos tablas llevan politica, y sin aseguradora
no se veria ni se escribiria ninguna fila. Los parametros se ligan; nada se arma
por concatenacion. Un contrato de importacion falla ante cualquier apertura de
conexion plantada aqui.

## Registrar un hito: una transaccion, dos escrituras de fila unica

Es la forma que fija PERF-U6.4 y la unica que cuenta cada hito una sola vez sin
leer antes:

1. **Se inserta el avance y se pide la fila de vuelta.** Si la sesion ya tenia
   ese hito, la clave primaria choca, `ON CONFLICT DO NOTHING` no escribe nada y
   la sentencia no devuelve fila.
2. **Solo si volvio una fila**, se suma uno al conteo del dia, la aseguradora y
   el hito, creando la fila del dia si no existia.

Las dos van en la misma transaccion: si la segunda falla, la primera no queda, y
la sesion no se queda con un hito "ya alcanzado" que nunca sumo. Sin lectura
previa no hay ventana entre leer y escribir: dos turnos simultaneos de la misma
sesion chocan en la clave primaria y solo uno suma.

## Lo que no se lee

El avance por sesion **no tiene ruta de lectura** (BR8.5). Este modulo lo
escribe y el purgador lo borra; lo unico que sale hacia un reporte es el conteo
por dia.
"""

from __future__ import annotations

from datetime import UTC, datetime

from untangle.telemetry.activation.models import ActivationDailyCount, ActivationMilestone
from untangle.tenancy import api as tenancy

INSERTAR_AVANCE = """
    INSERT INTO activation_progress (tenant_id, visitor_key_hash, milestone, reached_at)
    VALUES (:tenant_id, :visitor_key_hash, :milestone, :reached_at)
    ON CONFLICT (tenant_id, visitor_key_hash, milestone) DO NOTHING
    RETURNING milestone
"""

SUMAR_AL_DIA = """
    INSERT INTO activation_daily (tenant_id, day, milestone, count)
    VALUES (:tenant_id, :day, :milestone, 1)
    ON CONFLICT (tenant_id, day, milestone)
    DO UPDATE SET count = activation_daily.count + 1
"""

CONTEO_DE_LA_ASEGURADORA = """
    SELECT tenant_id, day, milestone, count
    FROM activation_daily
    ORDER BY day, milestone
"""


def en_utc(moment: datetime) -> datetime:
    """El instante normalizado a UTC: el dia del conteo se toma de aqui.

    Un dia local distinto por aseguradora partiria la misma noche en dos filas
    segun quien mire.
    """
    if moment.tzinfo is None:
        msg = "el instante de un hito tiene que llevar zona horaria; sin ella el dia es ambiguo"
        raise ValueError(msg)
    return moment.astimezone(UTC)


async def record(
    *,
    tenant_id: str,
    visitor_key_hash: str,
    milestone: ActivationMilestone,
    reached_at: datetime,
) -> bool:
    """Registra el hito si la sesion no lo tenia. Devuelve si conto.

    Una transaccion, dos escrituras de fila unica (PERF-U6.4). Si algo falla,
    levanta: decidir que hacer con el fallo es de la superficie, que es quien
    sabe que el turno no puede romperse por esto (BR8.3).
    """
    momento = en_utc(reached_at)
    async with tenancy.session_for(tenant_id) as sesion:
        nueva = await tenancy.fetch_one(
            sesion,
            INSERTAR_AVANCE,
            tenant_id=tenant_id,
            visitor_key_hash=visitor_key_hash,
            milestone=milestone.value,
            reached_at=momento,
        )
        if nueva is None:
            return False
        await tenancy.execute_sql(
            sesion,
            SUMAR_AL_DIA,
            tenant_id=tenant_id,
            day=momento.date(),
            milestone=milestone.value,
        )
    return True


async def daily_counts() -> tuple[ActivationDailyCount, ...]:
    """El conteo de todas las aseguradoras, por dia e hito (BR8.5, OBS-U6.3).

    Se recorre aseguradora por aseguradora por la misma razon que el purgador:
    la politica de fila no deja de aplicarse para leer, y sin aseguradora fijada
    no se veria ninguna fila.
    """
    filas: list[ActivationDailyCount] = []
    for tenant_id in tenancy.available_ids():
        async with tenancy.session_for(tenant_id) as sesion:
            leidas = await tenancy.fetch_all(sesion, CONTEO_DE_LA_ASEGURADORA)
        filas.extend(
            ActivationDailyCount(
                tenant_id=str(fila["tenant_id"]),
                day=fila["day"],
                milestone=ActivationMilestone(str(fila["milestone"])),
                count=int(fila["count"]),
            )
            for fila in leidas
        )
    return tuple(sorted(filas, key=lambda f: (f.day, f.tenant_id, f.milestone.value)))
