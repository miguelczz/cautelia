"""El reporte de una corrida: por caso, por criterio y por idioma (C-27).

El idioma es una **dimension de la estructura**, no una etiqueta. Es una decision
de diseno y se nota en el modelo: no existe ningun campo donde escribir un
promedio combinado, asi que no hay forma de publicar uno por descuido. Un
promedio esconde que una capacidad funciona en un idioma y no en el otro, que es
precisamente el riesgo de un producto bilingue (P12, OBS-U1.4).

La cabecera va **arriba, antes de la primera cifra**, y no en un apendice: son
las condiciones bajo las que esa cifra vale.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from untangle.base import Frozen, Locale
from untangle.evals.latency_summary import ChannelLatency
from untangle.evals.models import (
    CaseStatus,
    Channel,
    JudgmentKind,
    NonComparableCause,
    NotMeasuredCause,
    RootCause,
)


class RunHeader(Frozen):
    """Las condiciones bajo las que valen las cifras de esta corrida."""

    run_id: str
    commit_sha: str
    #: Identificador **exacto** de modelo por uso, nunca un alias movil: un alias
    #: que se mueve convierte un cambio de modelo en una regresion inexplicable.
    model_ids: dict[str, str] = Field(default_factory=dict)
    #: Un prompt cambiado sin cambiar el modelo produce el mismo efecto y no se
    #: veria sin esto.
    prompt_hashes: dict[str, str] = Field(default_factory=dict)
    subset: str | None = None
    subset_declared: bool = False
    duration_seconds: float = 0.0
    comparable: bool = True
    non_comparable_cause: NonComparableCause | None = None
    started_at: datetime
    finished_at: datetime | None = None
    traces_available: bool = False
    #: La linea base contra la que se comparo, o `None` cuando no habia ninguna
    #: vigente: la corrida corre, publica y lo dice aqui en vez de callarlo
    #: (U21, FD-U21-5). Distinto de `comparable`: ese es sobre si *esta* corrida
    #: se pudo medir completa; esto es sobre si *hubo con que* compararla.
    baseline_id: str | None = None


class LanguageTally(Frozen):
    """El recuento de un idioma. Nunca se suma con el del otro."""

    passed: int = 0
    failed: int = 0
    not_measured: int = 0

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.not_measured


class ByLanguage(Frozen):
    """Los dos idiomas, lado a lado.

    No hay un tercer campo. Si lo hubiera, alguien escribiria el promedio ahi.
    """

    es: LanguageTally = LanguageTally()
    en: LanguageTally = LanguageTally()


class CriterionReport(Frozen):
    """Un criterio, con su recuento en cada idioma."""

    criterion: str
    by_language: ByLanguage = ByLanguage()


class CaseRow(Frozen):
    """Una fila del reporte: un caso dentro de esta corrida."""

    case_key: str
    language: Locale
    status: CaseStatus
    not_measured_cause: NotMeasuredCause | None = None
    criteria_results: dict[str, str] = Field(default_factory=dict)
    #: Quien juzgo cada criterio de `criteria_results`, misma clave (U21, BR1.1).
    #: Toda entrada de esta unidad es `code`: el juez y la revision humana
    #: llegan con el paso 6.
    criteria_judgment: dict[str, JudgmentKind] = Field(default_factory=dict)
    off_script_turns: int = 0
    duration_seconds: float = 0.0
    trace_ref: str | None = None
    #: `unavailable` cuando el backend de trazas no estaba corriendo. Marcado,
    #: no vacio ni inventado (BR1.3).
    trace_status: str = "unavailable"
    #: Lo llena la compuerta desde la explicacion que nombra este caso
    #: (U21, BR1.1, BR2.2); ausente cuando el caso fallo sin que nadie lo
    #: explicara todavia.
    root_cause: RootCause | None = None


class EvalReport(Frozen):
    """El reporte completo de una corrida."""

    header: RunHeader
    totals: ByLanguage = ByLanguage()
    criteria: tuple[CriterionReport, ...] = ()
    cases: tuple[CaseRow, ...] = ()
    #: La latencia de cada canal que conversa en esta corrida, por idioma y con su recuento.
    #: **Separada de `criteria` a proposito**: son tiempos y no tasas de aciertos, y no entran
    #: a la comparacion de regresiones. Vacia cuando la corrida no conversa por ningun canal.
    latencies: dict[Channel, ChannelLatency] = Field(default_factory=dict)
