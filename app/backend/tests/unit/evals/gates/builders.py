"""Ayudantes compartidos: construir un reporte pequeno sin pasar por el corredor.

Las pruebas de esta carpeta no llaman a ningun proveedor ni tocan
PostgreSQL (`unit-test-instructions.md`, "Sin modelo" / "Sin base de datos"):
un reporte se arma directo con los modelos.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from untangle.base import Locale
from untangle.evals.models import CaseStatus, JudgmentKind
from untangle.evals.report import (
    ByLanguage,
    CaseRow,
    CriterionReport,
    EvalReport,
    LanguageTally,
    RunHeader,
)
from untangle.evals.transcripts import RecordedConversation, RecordedTurn, TranscriptsFile

MOMENTO = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)


def fila(
    case_key: str,
    *,
    status: CaseStatus = CaseStatus.PASSED,
    language: Locale = "es",
    criterion: str = "citation_precision",
    judgment: JudgmentKind = JudgmentKind.CODE,
) -> CaseRow:
    """Una fila de reporte con un solo criterio, juzgado por codigo por defecto."""
    veredicto = "pass" if status is CaseStatus.PASSED else "fail"
    return CaseRow(
        case_key=case_key,
        language=language,
        status=status,
        criteria_results={criterion: veredicto},
        criteria_judgment={criterion: judgment},
    )


def reporte(
    filas: tuple[CaseRow, ...],
    *,
    run_id: str = "run-test",
    commit_sha: str = "abc1234def",
    subset: str | None = "smoke",
    comparable: bool = True,
) -> EvalReport:
    """Un `EvalReport` completo a partir de las filas dadas.

    `subset=None` es la corrida completa (BR1.6): `subset_declared` se deriva de
    el en vez de pedirse aparte, porque las dos siempre viajan juntas.
    """

    def _recuento(idioma: Locale) -> LanguageTally:
        elegidas = [f for f in filas if f.language == idioma]
        return LanguageTally(
            passed=sum(1 for f in elegidas if f.status is CaseStatus.PASSED),
            failed=sum(1 for f in elegidas if f.status is CaseStatus.FAILED),
        )

    criterios = sorted({c for f in filas for c in f.criteria_results})

    def _recuento_criterio(idioma: Locale, criterio: str) -> LanguageTally:
        elegidas = [f for f in filas if f.language == idioma and criterio in f.criteria_results]
        return LanguageTally(
            passed=sum(1 for f in elegidas if f.status is CaseStatus.PASSED),
            failed=sum(1 for f in elegidas if f.status is CaseStatus.FAILED),
        )

    return EvalReport(
        header=RunHeader(
            run_id=run_id,
            commit_sha=commit_sha,
            subset=subset,
            subset_declared=subset is not None,
            comparable=comparable,
            started_at=MOMENTO,
        ),
        totals=ByLanguage(es=_recuento("es"), en=_recuento("en")),
        criteria=tuple(
            CriterionReport(
                criterion=criterio,
                by_language=ByLanguage(
                    es=_recuento_criterio("es", criterio),
                    en=_recuento_criterio("en", criterio),
                ),
            )
            for criterio in criterios
        ),
        cases=filas,
    )


# --- Transcripciones de mentira, para la cola de etiquetado (DS-7) ----------------


def conversacion(
    nombre: str,
    idioma: Locale,
    *,
    turnos_de_la_agente: int = 10,
    marcado_cada: int | None = 5,
    senal: str = "several_questions",
) -> RecordedConversation:
    """Una conversacion: apertura, y despues pares persona-agente.

    El turno `k` de la agente lleva `senal` si `k` es multiplo de `marcado_cada`. El texto de
    cada turno nombra su conversacion y su posicion, para reconocerlo en la cola.
    """
    turnos = [
        RecordedTurn(
            index=0, speaker="agent", text=f"apertura {nombre}", language=idioma, opening=True
        )
    ]
    for k in range(turnos_de_la_agente):
        turnos.append(
            RecordedTurn(
                index=1 + 2 * k, speaker="insured", text=f"persona {k} {nombre}", language=idioma
            )
        )
        marcado = marcado_cada is not None and k % marcado_cada == 0
        turnos.append(
            RecordedTurn(
                index=2 + 2 * k,
                speaker="agent",
                text=f"agente {k} {nombre}",
                language=idioma,
                signals=(senal,) if marcado else (),
            )
        )
    return RecordedConversation(
        case_key=f"DS-2/{idioma}/{nombre}",
        language=idioma,
        tenant="stonecroft",
        turns=tuple(turnos),
    )


def corrida(*conversaciones: RecordedConversation, run_id: str = "run-prueba") -> TranscriptsFile:
    return TranscriptsFile(
        run_id=run_id, commit_sha="abc1234", recorded_at=MOMENTO, conversations=conversaciones
    )


def corrida_completa(**opciones: Any) -> TranscriptsFile:
    """Cuatro conversaciones por idioma, diez turnos de la agente cada una (40 por idioma)."""
    return corrida(
        *(conversacion(f"c{n}", idioma, **opciones) for idioma in ("es", "en") for n in range(4))
    )
