"""El archivo de transcripciones de una corrida: se escribe, se lee y se elige la ultima."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from untangle.evals.transcripts import (
    NotSaved,
    RecordedConversation,
    RecordedTurn,
    TranscriptsFile,
    TranscriptsLoadError,
    latest_path,
    load_transcripts,
    path_for,
    write_transcripts,
)

MOMENTO = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)


def _archivo(run_id: str = "run-aaa") -> TranscriptsFile:
    return TranscriptsFile(
        run_id=run_id,
        commit_sha="abc1234def",
        recorded_at=MOMENTO,
        conversations=(
            RecordedConversation(
                case_key="DS-2/es/chat-claim-end-to-end",
                language="es",
                tenant="stonecroft",
                turns=(
                    RecordedTurn(
                        index=0, speaker="agent", text="Hola", language="es", opening=True
                    ),
                    RecordedTurn(index=1, speaker="insured", text="Choque", language="es"),
                    RecordedTurn(
                        index=2,
                        speaker="agent",
                        text="Lo lamento. Donde fue?",
                        language="es",
                        signals=("after_emotion:fear_or_crying",),
                    ),
                ),
            ),
        ),
        not_saved=(NotSaved(case_key="DS-2/en/chat-claim-end-to-end", reason="redaction_failed"),),
    )


def test_lo_escrito_se_lee_igual(tmp_path: Path) -> None:
    destino = write_transcripts(_archivo(), tmp_path)

    assert destino == path_for("run-aaa", tmp_path)
    assert load_transcripts(destino) == _archivo()


def test_escribir_dos_veces_la_misma_corrida_sobrescribe_y_no_deja_temporales(
    tmp_path: Path,
) -> None:
    write_transcripts(_archivo(), tmp_path)
    write_transcripts(_archivo(), tmp_path)

    assert sorted(p.name for p in tmp_path.iterdir()) == ["run-aaa.json"]


def test_un_archivo_roto_se_nombra_y_no_se_lee_a_medias(tmp_path: Path) -> None:
    roto = tmp_path / "run-rota.json"
    roto.write_text('{"run_id": "run-rota"}', encoding="utf-8")

    with pytest.raises(TranscriptsLoadError, match=r"run-rota\.json"):
        load_transcripts(roto)


def test_un_archivo_que_no_existe_se_nombra(tmp_path: Path) -> None:
    with pytest.raises(TranscriptsLoadError, match=r"no-existe\.json"):
        load_transcripts(tmp_path / "no-existe.json")


def test_un_turno_sin_texto_no_es_valido() -> None:
    with pytest.raises(ValueError, match="text"):
        RecordedTurn(index=0, speaker="agent", text="", language="es")


def test_el_identificador_de_caso_tiene_que_tener_su_forma() -> None:
    with pytest.raises(ValueError, match="case_key"):
        RecordedConversation(case_key="una cosa cualquiera", language="es")


def test_sin_directorio_o_sin_archivos_no_hay_ultima(tmp_path: Path) -> None:
    assert latest_path(tmp_path / "no-existe") is None
    assert latest_path(tmp_path) is None


def test_la_ultima_es_la_escrita_mas_recientemente(tmp_path: Path) -> None:
    vieja = write_transcripts(_archivo("run-vieja"), tmp_path)
    nueva = write_transcripts(_archivo("run-nueva"), tmp_path)
    os.utime(vieja, ns=(1_000_000_000, 1_000_000_000))
    os.utime(nueva, ns=(2_000_000_000, 2_000_000_000))

    assert latest_path(tmp_path) == nueva
