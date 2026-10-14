"""El tablero "Que tan bien funciona": la ultima corrida completa, como salio.

Decision de Miguel del 2026-10-09: la pestana muestra **la ultima corrida con sus
fallos**, no la linea base. Una linea base solo se publica en verde, asi que
mostrarla diria siempre 100 % y esconderia justo lo que alguien viene a ver.

Lee el resumen versionado (`app/evals/last-run.json`) y nada mas: no toca la base
ni a ningun proveedor. Lo que la corrida no midio se dice **no medido**, con su
causa, nunca en cero y nunca omitido. Los dos idiomas van lado a lado y no se
promedian (P12).

Los casos que se nombran son los del conjunto de prueba versionado
(`DS-3/es/...`), que estan en el repositorio: no son casos de visitantes.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from enum import StrEnum

from untangle.base import Frozen
from untangle.evals.gates.loading import load_last_run_digest
from untangle.evals.gates.models import LastRunDigest
from untangle.evals.models import CaseStatus


class GateFamily(StrEnum):
    """Las compuertas duras, agrupadas por lo que protegen. Cerrado: cada una tiene
    su frase en el catalogo."""

    CITATIONS = "citations"
    NO_PROMISES = "no_promises"
    PERSONAL_DATA = "personal_data"
    ISOLATION = "isolation"
    CONDUCT = "conduct"
    CONTENT = "content"


#: A que familia pertenece un criterio bloqueante, por su nombre. El orden importa:
#: el primer prefijo que coincide gana.
_FAMILIA_POR_PREFIJO: tuple[tuple[str, GateFamily], ...] = (
    ("citation_exists_", GateFamily.CITATIONS),
    # Lo que la agente dijo de verdad: cobertura, montos, culpa, consejo legal y sus propios
    # prompts (RT-5 cae aqui por su prefijo `rt`).
    ("transcript_", GateFamily.NO_PROMISES),
    ("rt4_", GateFamily.ISOLATION),
    ("rt14_", GateFamily.PERSONAL_DATA),
    ("rt15_cross_language_redacted", GateFamily.PERSONAL_DATA),
    ("content_", GateFamily.CONTENT),
    ("rt8_", GateFamily.CONDUCT),
    ("intake_", GateFamily.CONDUCT),
    ("rt", GateFamily.NO_PROMISES),
    ("quote_", GateFamily.NO_PROMISES),
    ("money_", GateFamily.NO_PROMISES),
)


def family_of(criterion: str) -> GateFamily | None:
    """La familia de una compuerta dura, o `None` si su nombre no es de ninguna."""
    for prefijo, familia in _FAMILIA_POR_PREFIJO:
        if criterion.startswith(prefijo):
            return familia
    return None


class Tally(Frozen):
    """Cuantos pasan, fallan y no se midieron. De un solo idioma."""

    passed: int = 0
    failed: int = 0
    not_measured: int = 0


class TallyByLanguage(Frozen):
    """Los dos idiomas, lado a lado. No hay un tercero combinado."""

    es: Tally = Tally()
    en: Tally = Tally()


class DatasetResult(Frozen):
    """Un tipo de prueba (`DS-2`, `DS-3`...) y como le fue en cada idioma."""

    dataset: str
    by_language: TallyByLanguage


class GateResult(Frozen):
    """Una compuerta dura: en cuantos casos se midio y en cuantos fallo.

    Con los dos recuentos en cero, esa compuerta **no se midio** en esta corrida.
    """

    family: GateFamily
    by_language: TallyByLanguage

    @property
    def measured(self) -> bool:
        idiomas = (self.by_language.es, self.by_language.en)
        return any(t.passed + t.failed for t in idiomas)


class FailedCase(Frozen):
    """Un caso del conjunto de prueba que fallo, con lo que fallo."""

    case_key: str
    dataset: str
    language: str
    criteria: tuple[str, ...] = ()
    #: Fallo una compuerta dura: detiene la entrega.
    blocking: bool = False
    root_cause: str | None = None


class NotMeasuredGroup(Frozen):
    cause: str
    count: int


class QualityBoard(Frozen):
    """Lo que la pestana dibuja."""

    run_id: str
    commit_sha: str
    produced_at: datetime
    duration_seconds: float | None = None
    comparable: bool = True
    dirty_tree: bool = False
    #: Los modelos de la corrida, por identificador exacto.
    models: tuple[str, ...] = ()
    totals: TallyByLanguage
    datasets: tuple[DatasetResult, ...] = ()
    gates: tuple[GateResult, ...] = ()
    failures: tuple[FailedCase, ...] = ()
    not_measured: tuple[NotMeasuredGroup, ...] = ()


def _partes(case_key: str) -> tuple[str, str]:
    conjunto, idioma, _ = case_key.split("/", 2)
    return conjunto, idioma


def _recuento(estados: list[CaseStatus]) -> Tally:
    return Tally(
        passed=sum(1 for e in estados if e is CaseStatus.PASSED),
        failed=sum(1 for e in estados if e is CaseStatus.FAILED),
        not_measured=sum(1 for e in estados if e is CaseStatus.NOT_MEASURED),
    )


def _por_idioma(casos: dict[str, CaseStatus]) -> TallyByLanguage:
    return TallyByLanguage(
        es=_recuento([e for clave, e in casos.items() if _partes(clave)[1] == "es"]),
        en=_recuento([e for clave, e in casos.items() if _partes(clave)[1] == "en"]),
    )


def _compuertas(digest: LastRunDigest) -> tuple[GateResult, ...]:
    """Cada familia, contando casos: un caso falla la familia si falla alguna de sus
    compuertas, y la pasa si las paso todas."""
    bloqueantes = set(digest.blocking_criteria)
    resultados: list[GateResult] = []
    for familia in GateFamily:
        estados: dict[str, CaseStatus] = {}
        for caso, criterios in digest.criteria_results.items():
            propios = [
                veredicto
                for criterio, veredicto in criterios.items()
                if criterio in bloqueantes and family_of(criterio) is familia
            ]
            if propios:
                estados[caso] = CaseStatus.FAILED if "fail" in propios else CaseStatus.PASSED
        resultados.append(GateResult(family=familia, by_language=_por_idioma(estados)))
    return tuple(resultados)


def _fallos(digest: LastRunDigest) -> tuple[FailedCase, ...]:
    bloqueantes = set(digest.blocking_criteria)
    fallos: list[FailedCase] = []
    for caso, estado in sorted(digest.case_verdicts.items()):
        if estado is not CaseStatus.FAILED:
            continue
        conjunto, idioma = _partes(caso)
        rojos = tuple(
            sorted(c for c, v in digest.criteria_results.get(caso, {}).items() if v == "fail")
        )
        causa = digest.root_causes.get(caso)
        fallos.append(
            FailedCase(
                case_key=caso,
                dataset=conjunto,
                language=idioma,
                criteria=rojos,
                blocking=any(c in bloqueantes for c in rojos),
                root_cause=None if causa is None else causa.value,
            )
        )
    # Lo que detiene una entrega, primero.
    return tuple(sorted(fallos, key=lambda f: (not f.blocking, f.case_key)))


def build_board(digest: LastRunDigest) -> QualityBoard:
    """El tablero de un resumen. Pura: no lee archivos."""
    conjuntos = sorted({_partes(clave)[0] for clave in digest.case_verdicts})
    causas = Counter(causa.value for causa in digest.not_measured_causes.values())
    return QualityBoard(
        run_id=digest.run_id,
        commit_sha=digest.commit_sha,
        produced_at=digest.produced_at,
        duration_seconds=digest.duration_seconds,
        comparable=digest.comparable,
        dirty_tree=digest.dirty_tree,
        models=tuple(sorted(set(digest.model_ids.values()))),
        totals=_por_idioma(digest.case_verdicts),
        datasets=tuple(
            DatasetResult(
                dataset=conjunto,
                by_language=_por_idioma(
                    {c: e for c, e in digest.case_verdicts.items() if _partes(c)[0] == conjunto}
                ),
            )
            for conjunto in conjuntos
        ),
        gates=_compuertas(digest),
        failures=_fallos(digest),
        not_measured=tuple(
            NotMeasuredGroup(cause=causa, count=cuantos)
            for causa, cuantos in sorted(causas.items())
        ),
    )


def current_board() -> QualityBoard | None:
    """El tablero de la ultima corrida completa, o `None` si no se ha guardado ninguna."""
    digest = load_last_run_digest()
    return None if digest is None else build_board(digest)


__all__ = [
    "DatasetResult",
    "FailedCase",
    "GateFamily",
    "GateResult",
    "NotMeasuredGroup",
    "QualityBoard",
    "Tally",
    "TallyByLanguage",
    "build_board",
    "current_board",
    "family_of",
]
