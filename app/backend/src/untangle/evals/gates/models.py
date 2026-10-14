"""Las tres entidades nuevas de U21: la memoria entre corridas (entities.md).

Archivos versionados, como los casos de golden set y por la misma razon: la
compuerta corre en GitHub Actions, sin base de datos, y lo que decide si una
entrega pasa tiene que poder leerse en un diff (FD-U21-1, TECH-U21.4).
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from untangle.base import Frozen, Locale
from untangle.evals.latency_summary import ChannelLatency
from untangle.evals.models import (
    CASE_KEY_PATTERN,
    CaseStatus,
    Channel,
    NotMeasuredCause,
    RootCause,
)


class Baseline(Frozen):
    """La foto de una corrida que queda como referencia (AC4.5.4).

    Se publica solo por hito y solo con las compuertas duras en verde: la
    validacion de esa condicion vive en `gates.baseline`, no aqui, porque exige
    conocer el reporte completo y no solo la forma del archivo.
    """

    baseline_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    commit_sha: str = Field(min_length=1)
    published_at: datetime
    #: El veredicto de cada caso en esta linea base: es lo que permite decir
    #: que caso paso a fallar (AC5.9.2).
    case_verdicts: dict[str, CaseStatus] = Field(default_factory=dict)
    #: Tasa de aciertos por criterio y por idioma, nunca combinada (P12).
    metrics: dict[str, dict[Locale, float]] = Field(default_factory=dict)
    #: Los mismos de la cabecera del reporte: una linea base sin ellos no es
    #: comparable con nada (un cambio de modelo sin declarar seria invisible).
    model_ids: dict[str, str] = Field(default_factory=dict)
    #: La latencia de cada canal que converso en la corrida, por idioma y con su recuento de
    #: turnos (hoy solo el chat). **Seccion propia y aparte de `metrics`**: son tiempos y no
    #: tasas, y la comparacion de regresiones (`gates.compare`) no los lee. Aditiva: una linea
    #: base publicada antes de que existiera se sigue leyendo, con la seccion vacia, y el panel
    #: dice que no trae latencias.
    latencies: dict[Channel, ChannelLatency] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _las_claves_de_caso_tienen_forma_valida(self) -> Self:
        invalidas = [clave for clave in self.case_verdicts if not CASE_KEY_PATTERN.match(clave)]
        if invalidas:
            msg = (
                f"la linea base '{self.baseline_id}' trae identificadores de caso "
                f"con forma invalida: {', '.join(sorted(invalidas))}"
            )
            raise ValueError(msg)
        return self


class LastRunDigest(Frozen):
    """La foto de la ultima corrida completa, tal como salio (U22, FD-U22-10, BR4.3).

    **No es una linea base.** La linea base es una corrida verde y sirve para
    comparar; este resumen se escribe tambien cuando la corrida esta en rojo y
    sirve para contar como falla (la seccion "Como falla" del README). La
    compuerta sigue comparando contra la linea base y nada mas.

    Las cuatro reglas de forma viven en el tipo y no en quien lo construye: un
    escritor futuro no puede relajarlas por descuido.
    """

    run_id: str = Field(min_length=1)
    commit_sha: str = Field(min_length=1)
    produced_at: datetime
    #: Siempre `None`: un resumen de un subconjunto haria falsa toda proporcion que
    #: la seccion publique ("42 de 100" sobre 74 casos no es 42 de 100). El campo
    #: existe para que el tipo pueda **rechazar** la declaracion, no para usarse.
    subset: str | None = None
    case_verdicts: dict[str, CaseStatus] = Field(default_factory=dict)
    #: Solo de casos que el resumen trae: sin esto la seccion agruparia casos que
    #: no cuenta.
    root_causes: dict[str, RootCause] = Field(default_factory=dict)
    #: Por que no se midio cada caso no medido. "No lo se" sin su causa no se
    #: puede distinguir de "esta mal" (OBS-U1.3).
    not_measured_causes: dict[str, NotMeasuredCause] = Field(default_factory=dict)
    # --- Lo que el tablero "Que tan bien funciona" muestra (2026-10-11) ----------
    # Todo aditivo y con valor por omision: un resumen escrito antes de esta fecha
    # se sigue leyendo, y lo que no trae se muestra como no registrado.
    #: Como le fue a cada caso en cada criterio que se le midio (`pass` o `fail`).
    #: Es lo que deja decir **por que** fallo un caso y como va cada compuerta dura.
    criteria_results: dict[str, dict[str, str]] = Field(default_factory=dict)
    #: Los criterios que en esa corrida eran compuerta dura: un solo caso en rojo
    #: en cualquiera detiene la entrega.
    blocking_criteria: tuple[str, ...] = ()
    #: Con que modelo corrio cada uso, por identificador exacto.
    model_ids: dict[str, str] = Field(default_factory=dict)
    #: La huella de cada prompt versionado en esa corrida.
    prompt_hashes: dict[str, str] = Field(default_factory=dict)
    duration_seconds: float | None = Field(default=None, ge=0.0)
    #: `False` cuando hubo casos sin medir: la corrida no se compara con otra.
    comparable: bool = True
    #: Habia cambios sin guardar al correr: el commit no describe del todo lo medido.
    dirty_tree: bool = False

    @model_validator(mode="after")
    def _los_criterios_son_de_casos_del_resumen(self) -> Self:
        ajenos = sorted(set(self.criteria_results) - set(self.case_verdicts))
        if ajenos:
            msg = (
                f"el resumen de la corrida '{self.run_id}' trae criterios de casos que "
                f"no trae: {', '.join(ajenos)}"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _es_la_corrida_completa(self) -> Self:
        if self.subset is not None:
            msg = (
                f"el resumen de la corrida '{self.run_id}' declara el subconjunto "
                f"'{self.subset}': solo la corrida completa se resume (BR4.3)"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _las_claves_de_caso_tienen_forma_valida(self) -> Self:
        invalidas = [clave for clave in self.case_verdicts if not CASE_KEY_PATTERN.match(clave)]
        if invalidas:
            msg = (
                f"el resumen de la corrida '{self.run_id}' trae identificadores de caso "
                f"con forma invalida: {', '.join(sorted(invalidas))}"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _una_causa_raiz_es_de_un_caso_del_resumen(self) -> Self:
        ajenas = sorted(set(self.root_causes) - set(self.case_verdicts))
        if ajenas:
            msg = (
                f"el resumen de la corrida '{self.run_id}' declara causa raiz de casos que "
                f"no trae: {', '.join(ajenas)}"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _la_causa_de_no_medido_es_de_un_caso_no_medido(self) -> Self:
        ajenas = sorted(set(self.not_measured_causes) - set(self.case_verdicts))
        if ajenas:
            msg = (
                f"el resumen de la corrida '{self.run_id}' declara causa de no medido de "
                f"casos que no trae: {', '.join(ajenas)}"
            )
            raise ValueError(msg)
        medidos = sorted(
            caso
            for caso in self.not_measured_causes
            if self.case_verdicts[caso] is not CaseStatus.NOT_MEASURED
        )
        if medidos:
            msg = (
                f"el resumen de la corrida '{self.run_id}' declara causa de no medido de "
                f"casos que si se midieron: {', '.join(medidos)}"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _un_caso_no_medido_trae_su_causa(self) -> Self:
        # La misma regla que ya tiene `CaseResult` (OBS-U1.3): el resumen no la relaja.
        sin_causa = sorted(
            caso
            for caso, estado in self.case_verdicts.items()
            if estado is CaseStatus.NOT_MEASURED and caso not in self.not_measured_causes
        )
        if sin_causa:
            msg = (
                f"el resumen de la corrida '{self.run_id}' trae casos no medidos sin su "
                f"causa: {', '.join(sin_causa)} (OBS-U1.3)"
            )
            raise ValueError(msg)
        return self


class Split(StrEnum):
    """Las tres particiones fijas de DS-7 (entities.md).

    `fit` ajusta la rubrica, `dev` la revisa mientras se escribe, y solo `test`
    cuenta para la calibracion que enciende o apaga al juez (BR3.1): medir
    contra la particion que ajusto la rubrica inflaria el acuerdo.
    """

    FIT = "fit"
    DEV = "dev"
    TEST = "test"


class LabelVerdict(StrEnum):
    """El veredicto de una etiqueta o del juez sobre un criterio."""

    PASS = "pass"  # noqa: S105 -- veredicto de una etiqueta, no una credencial
    FAIL = "fail"


class HumanLabel(Frozen):
    """Una etiqueta humana sobre un turno y un criterio (DS-7).

    `transcript_id` y `turn_index` identifican el turno dentro de la
    transcripcion; no cargan el texto -- eso vive en la cola de etiquetado,
    que es lo unico que Miguel necesita ver mientras etiqueta.
    """

    transcript_id: str = Field(min_length=1)
    turn_index: int = Field(ge=0)
    criterion: str = Field(min_length=1)
    language: Locale
    split: Split
    verdict: LabelVerdict
    labeled_at: date


class LabelsFile(BaseModel):
    """La raiz de `app/evals/labels/<idioma>.yaml`: un archivo por idioma."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    language: Locale
    labels: tuple[HumanLabel, ...] = ()

    @model_validator(mode="after")
    def _todo_pertenece_al_idioma_del_archivo(self) -> Self:
        ajenas = sorted(
            f"{etiqueta.transcript_id}#{etiqueta.turn_index}"
            for etiqueta in self.labels
            if etiqueta.language != self.language
        )
        if ajenas:
            msg = (
                f"el archivo del idioma '{self.language}' trae etiquetas de otro "
                f"idioma: {', '.join(ajenas)}"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _un_turno_y_criterio_no_se_etiqueta_dos_veces(self) -> Self:
        vistos: set[tuple[str, int, str]] = set()
        for etiqueta in self.labels:
            clave = (etiqueta.transcript_id, etiqueta.turn_index, etiqueta.criterion)
            if clave in vistos:
                msg = (
                    f"el turno {etiqueta.transcript_id}#{etiqueta.turn_index} ya tiene "
                    f"una etiqueta para el criterio '{etiqueta.criterion}'"
                )
                raise ValueError(msg)
            vistos.add(clave)
        return self


class JudgeCalibrationRate(Frozen):
    """TPR y TNR de un criterio en un idioma, con su n y su intervalo (BR3.1).

    Reemplaza el `agreement_rate` de una unica cifra que el catalogo de
    componentes proponia (ADR-014): una sola tasa no distingue un juez que
    nunca dice que falla de uno calibrado de verdad.
    """

    criterion: str = Field(min_length=1)
    language: Locale
    #: Cuantas etiquetas de la particion de prueba entraron en el calculo.
    n: int = Field(ge=1)
    tpr: float = Field(ge=0.0, le=1.0)
    tnr: float = Field(ge=0.0, le=1.0)
    #: Limite inferior del intervalo de Wilson al 95 %. Es lo que se compara
    #: contra el umbral de `nfr-requirements` (FD-U21-4): exigir el limite
    #: inferior y no la media impide que una muestra pequena y afortunada
    #: habilite al juez.
    ci_low_tpr: float = Field(ge=0.0, le=1.0)
    ci_low_tnr: float = Field(ge=0.0, le=1.0)


class JudgeCalibration(Frozen):
    """Lo que el juez acerto contra las etiquetas humanas de DS-7 (AC4.6.1)."""

    calibration_id: str = Field(min_length=1)
    #: Identificador exacto del modelo, nunca un alias movil (BR3.2).
    judge_model: str = Field(min_length=1)
    rubric_version: str = Field(min_length=1)
    measured_at: datetime
    #: La calibracion que cuenta se mide sobre la particion de prueba (BR3.1),
    #: pero el campo queda explicito en vez de asumirlo en el codigo que lee
    #: el archivo.
    split: Split
    rates: tuple[JudgeCalibrationRate, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _la_calibracion_que_cuenta_es_sobre_la_particion_de_prueba(self) -> Self:
        if self.split is not Split.TEST:
            msg = (
                f"la calibracion '{self.calibration_id}' se mide sobre la particion "
                f"'{self.split.value}'; solo la particion 'test' cuenta (BR3.1)"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _no_repite_criterio_e_idioma(self) -> Self:
        vistos: set[tuple[str, str]] = set()
        for tasa in self.rates:
            clave = (tasa.criterion, tasa.language)
            if clave in vistos:
                msg = (
                    f"la calibracion '{self.calibration_id}' repite el criterio "
                    f"'{tasa.criterion}' en '{tasa.language}'"
                )
                raise ValueError(msg)
            vistos.add(clave)
        return self

    def rate_for(self, criterion: str, language: Locale) -> JudgeCalibrationRate | None:
        return next(
            (t for t in self.rates if t.criterion == criterion and t.language == language), None
        )


class LabelingQueueEntry(Frozen):
    """Un turno pendiente de etiquetar (F2, FD-U21-3).

    Vive aparte de `HumanLabel`: la cola trae el texto que Miguel necesita ver
    mientras etiqueta, y la etiqueta ya confirmada nunca carga texto -- el
    mismo principio de U3, con el turno en lugar del dato personal.
    """

    transcript_id: str = Field(min_length=1)
    turn_index: int = Field(ge=0)
    criterion: str = Field(min_length=1)
    language: Locale
    split: Split
    agent_text: str = Field(min_length=1)
    #: Lo ultimo que dijo la persona antes de este turno, ya redactado. Sin el no se puede
    #: etiquetar si la respuesta atiende lo que se pregunto ni si reconocio la emocion de
    #: quien escribia, y el juez tendra ese mismo contexto. `None` en una cola armada antes
    #: de que existiera (el archivo se sigue leyendo) o cuando la agente hablo primero.
    context: str | None = Field(default=None, min_length=1)


class LabelingQueueFile(BaseModel):
    """La raiz de la cola de etiquetado, versionada y llenada aparte por Miguel."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entries: tuple[LabelingQueueEntry, ...] = ()


class JudgeVerdictRecord(Frozen):
    """El veredicto grabado del juez sobre un turno y un criterio.

    "Grabado" y no "en vivo": la calibracion real contra DS-7 corre en la
    sesion local que tiene la clave del proveedor (CG-U21-4); este archivo es
    lo que esa corrida deja escrito, y `evals:calibrate` solo lo lee. Ninguna
    prueba de esta unidad llama al juez de verdad.
    """

    transcript_id: str = Field(min_length=1)
    turn_index: int = Field(ge=0)
    criterion: str = Field(min_length=1)
    language: Locale
    verdict: LabelVerdict


class JudgeVerdictsFile(BaseModel):
    """La raiz de `app/evals/judge-verdicts/<judge_model>-<rubric_version>.yaml`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    judge_model: str = Field(min_length=1)
    rubric_version: str = Field(min_length=1)
    verdicts: tuple[JudgeVerdictRecord, ...] = ()


class UnstableCase(Frozen):
    """Un caso que cambia de veredicto entre corridas identicas (BR2.4, P5).

    No cuenta para la compuerta y nunca se borra del set: marcarlo exige la
    evidencia de las dos corridas que lo demuestran.
    """

    case_key: str = Field(pattern=CASE_KEY_PATTERN.pattern)
    reason: str = Field(min_length=1)
    marked_at: date
    run_ids: tuple[str, ...] = Field(min_length=2)
    work_item: str = Field(min_length=1)


class RegressionExplanation(Frozen):
    """La explicacion escrita que desbloquea una regresion (AC5.9.2).

    Una explicacion que no nombra identificadores no cuenta: por eso
    `case_keys` es obligatorio y no puede estar vacio.
    """

    case_keys: tuple[str, ...] = Field(min_length=1)
    root_cause: RootCause
    explained_at: date
    #: Desde que commit vale: una explicacion no cubre regresiones futuras.
    commit_sha: str = Field(min_length=1)

    @model_validator(mode="after")
    def _las_claves_de_caso_tienen_forma_valida(self) -> Self:
        invalidas = [clave for clave in self.case_keys if not CASE_KEY_PATTERN.match(clave)]
        if invalidas:
            msg = (
                "una explicacion de regresion trae identificadores de caso con "
                f"forma invalida: {', '.join(sorted(invalidas))}"
            )
            raise ValueError(msg)
        return self


class UnstableCasesFile(BaseModel):
    """La raiz de `app/evals/unstable-cases.yaml`: una lista, no una tabla."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    unstable_cases: tuple[UnstableCase, ...] = ()

    @model_validator(mode="after")
    def _un_caso_no_aparece_dos_veces(self) -> Self:
        vistos: set[str] = set()
        for caso in self.unstable_cases:
            if caso.case_key in vistos:
                msg = f"el caso '{caso.case_key}' esta marcado inestable mas de una vez"
                raise ValueError(msg)
            vistos.add(caso.case_key)
        return self


class RegressionExplanationsFile(BaseModel):
    """La raiz de `app/evals/regressions.yaml`: una lista, no una tabla."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    explanations: tuple[RegressionExplanation, ...] = ()
