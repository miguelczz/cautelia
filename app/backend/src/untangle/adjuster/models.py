"""Los tipos de la corrida del ajustador de IA: estados, pasos y fuentes.

Todo vocabulario cerrado, como el resto del aplicativo: un paso con un identificador que no esta
en la lista o una fuente de una clase que nadie declaro no se puede escribir, ni en el modelo ni
--por las restricciones de la tabla-- en la base.

El texto de un paso y de una fuente lo escribe el ajustador y lo lee una persona; **no es una
clave del catalogo**. Es la explicacion de una decision de este caso, en el idioma del caso, y no
una frase fija del producto. Lo unico que viaja como clave es `title_key`, el titulo del paso, que
la interfaz resuelve por el catalogo en el idioma de quien mira.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from untangle.base import Frozen
from untangle.inbox.actions import InboxAction
from untangle.tenancy.models import TenantId


class RunStatus(StrEnum):
    """En que va la corrida de un caso."""

    RUNNING = "running"
    DECIDED = "decided"
    #: El tope diario de casos se alcanzo: el caso espera en `derived` y lo recoge el reintento.
    CAPPED = "capped"
    #: Agoto sus intentos sin decidir. El caso sigue en revision: un fallo nunca inventa una
    #: decision (A12).
    FAILED = "failed"


class StepId(StrEnum):
    """Los seis pasos del proceso, con identificador estable (A2, «Como decide»)."""

    CASE_READ = "case_read"
    POLICY_READ = "policy_read"
    CLAUSES = "clauses"
    RULES = "rules"
    VEHICLE_VALUE = "vehicle_value"
    DECISION = "decision"


class SourceKind(StrEnum):
    """De que clase es una fuente que respalda un paso."""

    #: Una clausula de la poliza recuperada y verificada. `ref` es su identificador.
    CLAUSE = "clause"
    #: Una regla del motor que se disparo. `ref` es su identificador versionado.
    RULE = "rule"
    #: Un dato de la poliza emitida (vigencia, vehiculo, limites). `ref` nombra el dato.
    POLICY = "policy"
    #: Un dato que la persona conto en el reporte. `ref` es la clave del campo.
    CASE = "case"
    #: Una pagina de la web de la que sale un valor. `url` es obligatoria.
    WEB = "web"


class StepSource(Frozen):
    """Una fuente de un paso: lo que lo respalda y como se llama para quien lo lee."""

    kind: SourceKind
    ref: str = Field(min_length=1)
    label: str = Field(min_length=1)
    url: str | None = None

    @model_validator(mode="after")
    def _la_web_trae_su_direccion(self) -> Self:
        if self.kind is SourceKind.WEB and not self.url:
            msg = "una fuente web trae la direccion de su pagina: sin ella no se puede comprobar"
            raise ValueError(msg)
        return self


class RunStep(Frozen):
    """Un paso del proceso, con su texto y sus fuentes."""

    id: StepId
    #: La clave del catalogo con el titulo del paso, si la interfaz lo muestra con uno propio.
    title_key: str | None = None
    text: str = Field(min_length=1)
    sources: tuple[StepSource, ...] = ()


class AdjusterRun(Frozen):
    """La corrida del ajustador sobre un caso, tal como esta guardada."""

    tenant_id: TenantId
    case_id: str
    status: RunStatus
    attempt: int = Field(ge=1)
    steps: tuple[RunStep, ...] = ()
    decision: InboxAction | None = None
    summary: str | None = None
    model: str = Field(min_length=1)
    searches_used: int = Field(default=0, ge=0)
    error_kind: str | None = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _los_campos_acompanan_al_estado(self) -> Self:
        decidida = self.status is RunStatus.DECIDED
        if decidida != (self.decision is not None) or decidida != bool(self.summary):
            msg = "una corrida decidida lleva su decision y su explicacion, y ninguna otra"
            raise ValueError(msg)
        if self.error_kind is not None and self.status is not RunStatus.FAILED:
            msg = "solo una corrida fallida lleva el tipo de su error"
            raise ValueError(msg)
        return self


class OpenedRun(Frozen):
    """Lo que devuelve abrir una corrida.

    `started` dice si **esta llamada** es la duena del trabajo: la corrida es nueva o se reabrio
    desde `capped` o `failed`. Con dos arranques del mismo caso, uno solo lo tiene en verdad.
    """

    run: AdjusterRun
    started: bool
