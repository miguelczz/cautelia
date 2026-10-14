"""`mise run evals:label:queue`: arma la cola con una corrida ya hecha, sin tocar lo etiquetado.

Sin modelo y sin red. Las rutas del repositorio (transcripciones, cola, etiquetas) se
apuntan a un directorio temporal: ninguna prueba escribe en `app/evals/` ni en `tmp/`.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pytest

from untangle import paths
from untangle.evals.gates import loading
from untangle.evals.gates.label_cli import label_queue
from untangle.evals.gates.label_queue_cli import EXIT_NOTHING, EXIT_OK, EXIT_SHORT, build_queue
from untangle.evals.gates.models import HumanLabel, LabelingQueueEntry, LabelVerdict, Split
from untangle.evals.transcripts import NotSaved, TranscriptsFile, write_transcripts

from .builders import conversacion, corrida, corrida_completa


@pytest.fixture(autouse=True)
def _rutas_en_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Transcripciones, etiquetas y cola en un directorio temporal."""
    monkeypatch.setattr(paths, "transcripts_dir", lambda: tmp_path / "transcripts")
    monkeypatch.setattr(paths, "labels_dir", lambda: tmp_path / "labels")
    monkeypatch.setattr(paths, "labeling_queue_path", lambda: tmp_path / "labels" / "queue.yaml")
    return tmp_path


class Salida:
    """Recoge lo que el comando dice y lo que avisa como error."""

    def __init__(self) -> None:
        self.dicho: list[str] = []
        self.errores: list[str] = []

    def correr(self, *argumentos: str) -> int:
        return build_queue(
            list(argumentos), write_output=self.dicho.append, write_error=self.errores.append
        )

    @property
    def texto(self) -> str:
        return "\n".join(self.dicho)

    @property
    def error(self) -> str:
        return "\n".join(self.errores)


def _guardar_corrida(tmp_path: Path, archivo: TranscriptsFile | None = None) -> Path:
    return write_transcripts(archivo or corrida_completa(), tmp_path / "transcripts")


def _cola() -> tuple[LabelingQueueEntry, ...]:
    return loading.load_labeling_queue()


# --- Sin corrida -------------------------------------------------------------------


def test_sin_ninguna_corrida_lo_dice_en_una_frase_y_dice_que_correr_antes(
    tmp_path: Path,
) -> None:
    salida = Salida()

    codigo = salida.correr()

    assert codigo == EXIT_NOTHING
    assert "no hay ninguna corrida con conversaciones" in salida.error
    assert "mise run evals:conversaciones" in salida.error
    # Nada se escribio: ni cola ni directorios.
    assert not (tmp_path / "labels").exists()


def test_una_corrida_que_se_nombra_y_no_existe_se_dice(tmp_path: Path) -> None:
    _guardar_corrida(tmp_path)
    salida = Salida()

    codigo = salida.correr("--run", "run-que-no-existe")

    assert codigo == EXIT_NOTHING
    assert "run-que-no-existe" in salida.error


def test_un_criterio_desconocido_no_escribe_nada(tmp_path: Path) -> None:
    _guardar_corrida(tmp_path)
    salida = Salida()

    codigo = salida.correr("--criteria", "voice_guide", "tono_inventado")

    assert codigo == EXIT_NOTHING
    assert "tono_inventado" in salida.error
    assert not (tmp_path / "labels" / "queue.yaml").exists()


def test_un_archivo_de_transcripciones_roto_se_nombra(tmp_path: Path) -> None:
    roto = tmp_path / "transcripts" / "run-rota.json"
    roto.parent.mkdir(parents=True)
    roto.write_text("{}", encoding="utf-8")
    salida = Salida()

    codigo = salida.correr()

    assert codigo == EXIT_NOTHING
    assert "run-rota.json" in salida.error


# --- Arma la cola ---------------------------------------------------------------------


def test_arma_la_cola_con_veinte_por_idioma_y_la_deja_donde_la_lee_el_etiquetado(
    tmp_path: Path,
) -> None:
    _guardar_corrida(tmp_path)
    salida = Salida()

    codigo = salida.correr()

    assert codigo == EXIT_OK
    cola = _cola()
    assert [sum(1 for e in cola if e.language == i) for i in ("es", "en")] == [20, 20]
    assert "mise run evals:label" in salida.texto
    # El comando de etiquetar la lee tal cual.
    mostrados: list[str] = []
    label_queue(read_input=lambda _: "q", write_output=mostrados.append)
    assert any("la agente dijo:" in linea for linea in mostrados)


def test_por_omision_toma_la_ultima_corrida(tmp_path: Path) -> None:
    _guardar_corrida(tmp_path, corrida(conversacion("c0", "es"), run_id="run-vieja"))
    nueva = write_transcripts(
        corrida(conversacion("c0", "es"), run_id="run-nueva"), tmp_path / "transcripts"
    )
    os.utime(tmp_path / "transcripts" / "run-vieja.json", ns=(1_000_000_000, 1_000_000_000))
    os.utime(nueva, ns=(2_000_000_000, 2_000_000_000))
    salida = Salida()

    salida.correr("--per-language", "3")

    assert all(e.transcript_id.endswith("@run-nueva") for e in _cola())
    assert "run-nueva" in salida.texto


def test_se_puede_nombrar_la_corrida(tmp_path: Path) -> None:
    _guardar_corrida(tmp_path, corrida(conversacion("c0", "es"), run_id="run-vieja"))
    _guardar_corrida(tmp_path, corrida(conversacion("c0", "es"), run_id="run-nueva"))
    salida = Salida()

    salida.correr("--run", "run-vieja", "--per-language", "3")

    assert all(e.transcript_id.endswith("@run-vieja") for e in _cola())


def test_dos_corridas_del_comando_dejan_el_mismo_archivo_byte_a_byte(tmp_path: Path) -> None:
    _guardar_corrida(tmp_path)
    Salida().correr()
    primero = (tmp_path / "labels" / "queue.yaml").read_bytes()

    (tmp_path / "labels" / "queue.yaml").unlink()
    Salida().correr()

    assert (tmp_path / "labels" / "queue.yaml").read_bytes() == primero


def test_correrlo_otra_vez_no_cambia_nada_y_lo_dice(tmp_path: Path) -> None:
    _guardar_corrida(tmp_path)
    Salida().correr()
    antes = (tmp_path / "labels" / "queue.yaml").read_bytes()
    salida = Salida()

    codigo = salida.correr()

    assert codigo == EXIT_OK
    assert (tmp_path / "labels" / "queue.yaml").read_bytes() == antes
    assert "nada que agregar" in salida.texto


def test_dry_run_cuenta_y_no_escribe(tmp_path: Path) -> None:
    _guardar_corrida(tmp_path)
    salida = Salida()

    codigo = salida.correr("--dry-run")

    assert codigo == EXIT_OK
    assert "entradas nuevas: 40" in salida.texto
    assert not (tmp_path / "labels" / "queue.yaml").exists()


# --- No pisa lo etiquetado --------------------------------------------------------------


def test_no_toca_las_etiquetas_ni_las_entradas_que_ya_estaban(tmp_path: Path) -> None:
    _guardar_corrida(tmp_path)
    Salida().correr("--per-language", "10")
    primeras = _cola()
    etiquetas = tuple(
        HumanLabel(
            transcript_id=e.transcript_id,
            turn_index=e.turn_index,
            criterion=e.criterion,
            language=e.language,
            split=e.split,
            verdict=LabelVerdict.FAIL,
            labeled_at=date(2026, 10, 14),
        )
        for e in primeras
        if e.language == "es"
    )
    loading.save_labels("es", etiquetas)
    archivo_de_etiquetas = (tmp_path / "labels" / "es.yaml").read_bytes()

    codigo = Salida().correr()

    assert codigo == EXIT_OK
    assert (tmp_path / "labels" / "es.yaml").read_bytes() == archivo_de_etiquetas
    cola = _cola()
    assert cola[: len(primeras)] == primeras
    assert [sum(1 for e in cola if e.language == i) for i in ("es", "en")] == [20, 20]
    # Y lo ya etiquetado no se vuelve a preguntar: la cola alterna idioma, y las cinco
    # primeras en espanol ya tienen etiqueta, asi que la primera que sale es en ingles.
    mostrados: list[str] = []
    label_queue(read_input=lambda _: "q", write_output=mostrados.append)
    assert mostrados[0].lstrip().startswith("[en]")


def test_una_cola_rota_se_nombra_y_no_se_pisa(tmp_path: Path) -> None:
    _guardar_corrida(tmp_path)
    cola = tmp_path / "labels" / "queue.yaml"
    cola.parent.mkdir(parents=True)
    cola.write_text("entries: [1, 2]", encoding="utf-8")
    salida = Salida()

    codigo = salida.correr()

    assert codigo == EXIT_NOTHING
    assert "queue.yaml" in salida.error
    assert cola.read_text(encoding="utf-8") == "entries: [1, 2]"


# --- Cuando no alcanza ---------------------------------------------------------------------


def test_un_idioma_corto_se_dice_con_la_cifra_y_el_codigo_de_salida_lo_marca(
    tmp_path: Path,
) -> None:
    archivo = corrida(
        *(conversacion(f"c{n}", "es") for n in range(4)),
        conversacion("unica", "en", turnos_de_la_agente=3),
    )
    _guardar_corrida(tmp_path, archivo)
    salida = Salida()

    codigo = salida.correr()

    assert codigo == EXIT_SHORT
    assert "FALTAN 17 en 'en'" in salida.texto
    assert "solo trae 3" in salida.texto
    cola = _cola()
    assert sum(1 for e in cola if e.language == "en") == 3
    assert sum(1 for e in cola if e.language == "es") == 20


def test_sin_turnos_marcados_por_el_codigo_el_comando_lo_dice(tmp_path: Path) -> None:
    _guardar_corrida(tmp_path, corrida_completa(marcado_cada=None))
    salida = Salida()

    salida.correr()

    assert "el codigo no marco ningun turno como dudoso" in salida.texto


# --- Lo que dice del juez ---------------------------------------------------------------------


def test_avisa_que_con_veinte_por_idioma_el_juez_no_puede_encenderse(tmp_path: Path) -> None:
    _guardar_corrida(tmp_path)
    salida = Salida()

    salida.correr()

    assert "al menos 16 etiquetas 'pasa' y 16 'falla'" in salida.texto
    assert "0.80" in salida.texto
    assert "no alcanza para encenderlo" in salida.texto


def test_con_muchas_etiquetas_el_aviso_deja_de_decir_que_no_alcanza(tmp_path: Path) -> None:
    grande = corrida(
        *(
            conversacion(f"c{n}", idioma, turnos_de_la_agente=60)
            for idioma in ("es", "en")
            for n in range(4)
        )
    )
    _guardar_corrida(tmp_path, grande)
    salida = Salida()

    salida.correr("--per-language", "200")

    assert "no alcanza para encenderlo" not in salida.texto
    assert "alcanza solo si" in salida.texto


# --- Lo que imprime ---------------------------------------------------------------------------


def test_nunca_imprime_lo_que_dijo_la_agente_ni_la_persona(tmp_path: Path) -> None:
    _guardar_corrida(tmp_path)
    salida = Salida()

    salida.correr()

    assert "agente 0" not in salida.texto
    assert "persona 0" not in salida.texto


def test_cuenta_las_conversaciones_que_no_se_guardaron(tmp_path: Path) -> None:
    archivo = corrida_completa().evolve(
        not_saved=(NotSaved(case_key="DS-2/es/otra", reason="redaction_failed"),)
    )
    _guardar_corrida(tmp_path, archivo)
    salida = Salida()

    salida.correr()

    assert "DS-2/es/otra (redaction_failed)" in salida.texto


def test_las_etiquetas_nuevas_nacen_con_las_tres_particiones(tmp_path: Path) -> None:
    _guardar_corrida(tmp_path)

    Salida().correr()

    assert {e.split for e in _cola()} == {Split.FIT, Split.DEV, Split.TEST}
