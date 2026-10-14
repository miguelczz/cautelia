"""Pruebas de `evals:label`: se puede dejar a medias y retomar (FD-U21-3).

Sin entrada de verdad: `read_input`/`write_output` se inyectan.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from untangle import paths
from untangle.evals.gates import loading
from untangle.evals.gates.label_cli import label_queue
from untangle.evals.gates.models import LabelingQueueEntry, Split


@pytest.fixture(autouse=True)
def _cola_en_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Apunta la cola y las etiquetas a un directorio temporal (nunca `app/evals/`)."""
    monkeypatch.setattr(paths, "labeling_queue_path", lambda: tmp_path / "queue.yaml")
    monkeypatch.setattr(paths, "labels_dir", lambda: tmp_path)
    return tmp_path


def _escribir_cola(tmp_path: Path, entradas: tuple[LabelingQueueEntry, ...]) -> None:
    from untangle.evals.gates.models import LabelingQueueFile

    contenido = LabelingQueueFile(entries=entradas).model_dump(mode="json")
    import yaml

    (tmp_path / "queue.yaml").write_text(yaml.safe_dump(contenido), encoding="utf-8")


def test_una_cola_vacia_dice_por_que_lo_esta_y_no_que_no_haya_trabajo(tmp_path: Path) -> None:
    """Una cola vacia no es "ya terminaste": es que todavia no hay que etiquetar.

    Revisado el 2026-09-27. El mensaje decia "nada que hacer", que se lee como
    si el trabajo estuviera hecho. Cada entrada de la cola lleva un turno que la
    agente dijo de verdad, asi que la cola se llena de una corrida de
    evaluaciones con conversaciones (`mise run evals:label:queue` la arma; el
    conductor de chat de U13 ya existe). Un comando que parece terminado cuando
    esta bloqueado cuesta una tarde a quien lo corre.
    """
    salidas: list[str] = []
    codigo = label_queue(read_input=lambda _: "pasa", write_output=salidas.append)

    assert codigo == 0
    mensaje = salidas[0]
    assert "vacia" in mensaje
    # Lo que tiene que decir: que falta y que comando lo trae.
    assert "transcripciones" in mensaje
    assert "evals:conversaciones" in mensaje
    assert "evals:label:queue" in mensaje
    assert "no medida" in mensaje


def test_etiquetar_un_turno_lo_guarda(tmp_path: Path) -> None:
    entrada = LabelingQueueEntry(
        transcript_id="t1",
        turn_index=0,
        criterion="voice_guide",
        language="es",
        split=Split.TEST,
        agent_text="Buenos dias",
    )
    _escribir_cola(tmp_path, (entrada,))

    label_queue(read_input=lambda _: "pasa", write_output=lambda _: None)

    guardadas = loading.load_labels("es", tmp_path)
    assert len(guardadas) == 1
    assert guardadas[0].criterion == "voice_guide"


def test_salir_a_medias_deja_lo_ya_guardado(tmp_path: Path) -> None:
    entradas = (
        LabelingQueueEntry(
            transcript_id="t1",
            turn_index=0,
            criterion="voice_guide",
            language="es",
            split=Split.TEST,
            agent_text="turno 1",
        ),
        LabelingQueueEntry(
            transcript_id="t2",
            turn_index=0,
            criterion="voice_guide",
            language="es",
            split=Split.TEST,
            agent_text="turno 2",
        ),
    )
    _escribir_cola(tmp_path, entradas)

    respuestas = iter(["pasa", "q"])
    label_queue(read_input=lambda _: next(respuestas), write_output=lambda _: None)

    guardadas = loading.load_labels("es", tmp_path)
    assert len(guardadas) == 1
    assert guardadas[0].transcript_id == "t1"


def test_un_turno_ya_etiquetado_no_se_vuelve_a_preguntar(tmp_path: Path) -> None:
    entrada = LabelingQueueEntry(
        transcript_id="t1",
        turn_index=0,
        criterion="voice_guide",
        language="es",
        split=Split.TEST,
        agent_text="turno 1",
    )
    _escribir_cola(tmp_path, (entrada,))

    def _falla_si_se_llama(_: str) -> str:
        msg = "no deberia preguntar de nuevo"
        raise AssertionError(msg)

    label_queue(read_input=lambda _: "pasa", write_output=lambda _: None)
    # Segunda pasada: el turno ya esta etiquetado, no deberia preguntar.
    label_queue(read_input=_falla_si_se_llama, write_output=lambda _: None)


def test_muestra_lo_que_la_persona_dijo_antes_y_la_pregunta_del_criterio(tmp_path: Path) -> None:
    """Etiquetar relevancia o reconocimiento emocional sin ver que dijo la persona no sirve.

    El juez tendra ese mismo contexto, asi que quien etiqueta tambien lo ve; y ve la
    pregunta del criterio, porque el nombre solo ("voice_guide") no dice que se juzga.
    """
    entrada = LabelingQueueEntry(
        transcript_id="t1",
        turn_index=3,
        criterion="voice_guide",
        language="es",
        split=Split.TEST,
        agent_text="Lamento lo ocurrido. Cual es su numero de poliza?",
        context="Choque y estoy muy asustada",
    )
    _escribir_cola(tmp_path, (entrada,))

    salidas: list[str] = []
    label_queue(read_input=lambda _: "pasa", write_output=salidas.append)

    texto = "\n".join(salidas)
    assert "la persona dijo antes: Choque y estoy muy asustada" in texto
    assert "la agente dijo: Lamento lo ocurrido." in texto
    assert "guia de voz" in texto


def test_una_entrada_sin_contexto_no_inventa_uno(tmp_path: Path) -> None:
    entrada = LabelingQueueEntry(
        transcript_id="t1",
        turn_index=0,
        criterion="criterio-sin-declarar",
        language="es",
        split=Split.TEST,
        agent_text="Buenos dias",
    )
    _escribir_cola(tmp_path, (entrada,))

    salidas: list[str] = []
    label_queue(read_input=lambda _: "pasa", write_output=salidas.append)

    texto = "\n".join(salidas)
    assert "la persona dijo antes" not in texto
    assert "se pregunta" not in texto
    assert "la agente dijo: Buenos dias" in texto
