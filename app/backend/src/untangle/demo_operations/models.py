"""Las dos entidades de registro de U20: `ResetRun` y `TenantFolderReport`.

Las dos se escriben como `gates/models.py`: las reglas de forma viven en el tipo
y no en quien lo construye, para que un estado imposible --una corrida
`succeeded` con un purgador que fallo-- no se pueda construir ni por descuido.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from untangle.base import Frozen


class ResetOutcome(StrEnum):
    """Como termino una corrida. Conjunto cerrado de tres.

    `PARTIAL` no es un lujo: siete purgadores que borraron y dos que fallaron no
    son un exito ni un fallo completo. Colapsarlo en `FAILED` haria que el
    reintento borrara otra vez lo ya borrado; en `SUCCEEDED`, dejaria datos de
    visitante con el contador de 24 horas reiniciado.
    """

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL = "partial"


class PurgerRow(Frozen):
    """Lo que dijo un purgador en una corrida: no un total, su propia fila.

    Un total no dice cual dejo de borrar el dia que algo cambie. Si el purgador
    fallo, `deleted` y `kept` son `None`: **no se sabe** cuanto borro, y un cero
    diria que no habia nada, que es justo la confusion entre "no hay" y "no pude
    comprobar" que el proyecto prohibe en todas partes.
    """

    name: str = Field(min_length=1)
    tables: tuple[str, ...] = ()
    deleted: int | None = Field(default=None, ge=0)
    kept: int | None = Field(default=None, ge=0)
    duration_seconds: float = Field(ge=0)
    #: El nombre del tipo de la excepcion, nunca su mensaje: un mensaje de error
    #: de base puede llevar un valor, y esta fila sale en logs y en el reporte.
    error_type: str | None = Field(default=None, min_length=1)

    @property
    def succeeded(self) -> bool:
        return self.error_type is None

    @model_validator(mode="after")
    def _un_fallo_no_declara_cuanto_borro(self) -> Self:
        if self.error_type is None:
            if self.deleted is None or self.kept is None:
                msg = f"el purgador '{self.name}' no fallo y no declara cuanto borro ni conservo"
                raise ValueError(msg)
        elif self.deleted is not None or self.kept is not None:
            msg = (
                f"el purgador '{self.name}' fallo con '{self.error_type}' y aun asi "
                "declara cuanto borro: no se sabe, y un numero inventado no sirve"
            )
            raise ValueError(msg)
        return self


class ResetRun(Frozen):
    """El registro de una corrida del reinicio nocturno (BR3.1).

    `outcome` se guarda --es lo que se consulta--, pero el tipo **comprueba que
    coincide con las filas**: una corrida con un purgador caido y resultado
    `succeeded` no existe.
    """

    reset_run_id: str = Field(min_length=1)
    started_at: datetime
    finished_at: datetime
    outcome: ResetOutcome
    purgers: tuple[PurgerRow, ...] = Field(min_length=1)

    @property
    def failures(self) -> tuple[PurgerRow, ...]:
        """Que purgadores fallaron y con que tipo de error. Derivado de las filas
        y no guardado aparte: dos copias podrian contradecirse."""
        return tuple(fila for fila in self.purgers if not fila.succeeded)

    @model_validator(mode="after")
    def _los_relojes_traen_zona_y_van_en_orden(self) -> Self:
        if self.started_at.tzinfo is None or self.finished_at.tzinfo is None:
            msg = (
                f"la corrida '{self.reset_run_id}' trae un reloj sin zona horaria: "
                "el contador de 24 horas no se puede comparar con un instante ambiguo"
            )
            raise ValueError(msg)
        if self.finished_at < self.started_at:
            msg = f"la corrida '{self.reset_run_id}' termina antes de empezar"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _un_purgador_aparece_una_sola_vez(self) -> Self:
        nombres = [fila.name for fila in self.purgers]
        repetidos = sorted({n for n in nombres if nombres.count(n) > 1})
        if repetidos:
            msg = f"la corrida '{self.reset_run_id}' repite los purgadores {repetidos}"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _el_resultado_coincide_con_las_filas(self) -> Self:
        esperado = outcome_of(self.purgers)
        if self.outcome is not esperado:
            msg = (
                f"la corrida '{self.reset_run_id}' declara '{self.outcome.value}' pero "
                f"sus filas dicen '{esperado.value}'"
            )
            raise ValueError(msg)
        return self


def outcome_of(rows: tuple[PurgerRow, ...]) -> ResetOutcome:
    """El resultado que dicen las filas: todos bien, todos mal, o de todo un poco."""
    fallaron = sum(1 for fila in rows if not fila.succeeded)
    if fallaron == 0:
        return ResetOutcome.SUCCEEDED
    if fallaron == len(rows):
        return ResetOutcome.FAILED
    return ResetOutcome.PARTIAL


class TenantFault(Frozen):
    """Una falta de una carpeta: **el archivo y el campo**, no un mensaje suelto."""

    file: str = Field(min_length=1)
    field: str = Field(min_length=1)
    detail: str = Field(min_length=1)


class TenantFolderReport(Frozen):
    """Lo que devuelve la validacion de una carpeta: todas las faltas (BR1.1)."""

    tenant_id: str = Field(min_length=1)
    missing: tuple[TenantFault, ...] = ()

    @property
    def complete(self) -> bool:
        return not self.missing
