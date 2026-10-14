"""Carga y escritura de la linea base, los inestables y las explicaciones.

Mismo patron que `untangle.evals.loading` (CG-1, TECH-U21.4): cada fallo nombra
el archivo, y el listado se ordena antes de usarse para que dos corridas del
mismo commit vean lo mismo.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from untangle import paths
from untangle.base import Locale
from untangle.evals.gates.models import (
    Baseline,
    HumanLabel,
    JudgeCalibration,
    JudgeVerdictRecord,
    JudgeVerdictsFile,
    LabelingQueueEntry,
    LabelingQueueFile,
    LabelsFile,
    LastRunDigest,
    RegressionExplanation,
    RegressionExplanationsFile,
    UnstableCase,
    UnstableCasesFile,
)
from untangle.evals.loading import LoadError


def _read_yaml(path: Path) -> dict[str, Any]:
    """Copia local de `evals.loading._read_yaml`: el patron del repositorio es
    que cada modulo tenga la suya (ver `tenancy.config._read_yaml`), no
    importar un nombre privado de otro paquete.
    """
    try:
        crudo = path.read_text(encoding="utf-8")
    except OSError as error:
        msg = f"no se pudo leer '{path}': {error}"
        raise LoadError(msg) from error

    try:
        cargado = yaml.safe_load(crudo)
    except yaml.YAMLError as error:
        msg = f"'{path}' no es YAML valido: {error}"
        raise LoadError(msg) from error

    if cargado is None:
        msg = f"'{path}' esta vacio"
        raise LoadError(msg)
    if not isinstance(cargado, dict):
        msg = f"'{path}' no contiene un mapa en su raiz, sino {type(cargado).__name__}"
        raise LoadError(msg)
    return cargado


def _read_json(path: Path) -> dict[str, Any]:
    try:
        crudo = path.read_text(encoding="utf-8")
    except OSError as error:
        msg = f"no se pudo leer '{path}': {error}"
        raise LoadError(msg) from error

    try:
        cargado = json.loads(crudo)
    except json.JSONDecodeError as error:
        msg = f"'{path}' no es JSON valido: {error}"
        raise LoadError(msg) from error

    if not isinstance(cargado, dict):
        msg = f"'{path}' no contiene un mapa en su raiz, sino {type(cargado).__name__}"
        raise LoadError(msg)
    return cargado


def load_baseline(path: Path) -> Baseline:
    """Una linea base, validada contra su modelo."""
    datos = _read_json(path)
    try:
        return Baseline.model_validate(datos)
    except ValidationError as error:
        msg = f"la linea base '{path}' no valida su esquema: {error}"
        raise LoadError(msg) from error


def load_current_baseline(directory: Path | None = None) -> Baseline | None:
    """La linea base vigente, o `None` cuando no hay ninguna (FD-U21-5).

    Ausente es un estado valido: la primera corrida de un hito no tiene pasado
    contra el que compararse, y eso no es un error de carga.
    """
    base = directory if directory is not None else paths.baselines_dir()
    archivo = base / "current.json"
    if not archivo.is_file():
        return None
    return load_baseline(archivo)


def publish_baseline(baseline: Baseline, directory: Path | None = None) -> tuple[Path, Path]:
    """Escribe la linea base con su nombre y actualiza `current.json`.

    Devuelve las dos rutas escritas. Quien decide si esta corrida puede
    publicarse es `gates.baseline`; esta funcion solo escribe.
    """
    base = directory if directory is not None else paths.baselines_dir()
    base.mkdir(parents=True, exist_ok=True)
    contenido = baseline.model_dump_json(indent=2) + "\n"

    propia = base / f"{baseline.baseline_id}.json"
    propia.write_text(contenido, encoding="utf-8")

    vigente = base / "current.json"
    vigente.write_text(contenido, encoding="utf-8")

    return propia, vigente


def load_last_run_digest(path: Path | None = None) -> LastRunDigest | None:
    """El resumen de la ultima corrida completa, o `None` si todavia no hay ninguna.

    Ausente es un estado valido, como la linea base: no se ha corrido la corrida
    completa y la seccion dice "no medida". Uno presente pero roto si es un error
    y se nombra.
    """
    archivo = path if path is not None else paths.last_run_digest_path()
    if not archivo.is_file():
        return None
    datos = _read_json(archivo)
    try:
        return LastRunDigest.model_validate(datos)
    except ValidationError as error:
        msg = f"el resumen '{archivo}' no valida su esquema: {error}"
        raise LoadError(msg) from error


def save_last_run_digest(digest: LastRunDigest, path: Path | None = None) -> Path:
    """Escribe el resumen. Sobrescribe el anterior: es la foto de la ultima corrida."""
    archivo = path if path is not None else paths.last_run_digest_path()
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text(digest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return archivo


def load_unstable_cases(path: Path | None = None) -> tuple[UnstableCase, ...]:
    """Los casos inestables, o una tupla vacia si el archivo todavia no existe.

    Un archivo ausente no es un error (REL-U21.5): el set empieza vacio. Uno
    presente pero roto si lo es, y se nombra.
    """
    archivo = path if path is not None else paths.unstable_cases_path()
    if not archivo.is_file():
        return ()
    datos = _read_yaml(archivo)
    try:
        archivo_validado = UnstableCasesFile.model_validate(datos)
    except ValidationError as error:
        msg = f"'{archivo}' no valida su esquema de casos inestables: {error}"
        raise LoadError(msg) from error
    return archivo_validado.unstable_cases


def validate_regression_explanations_file(path: Path) -> None:
    """Comprueba la forma de `regressions.yaml`, propagando el error (`schema:check`).

    Distinta de `load_regression_explanations`: esta funcion es para quien
    **audita** el archivo y necesita nombrarlo si esta roto; la compuerta usa la
    otra, que trata un archivo roto como "sin explicaciones" (REL-U21.5).
    """
    datos = _read_yaml(path)
    try:
        RegressionExplanationsFile.model_validate(datos)
    except ValidationError as error:
        msg = f"'{path}' no valida su esquema de explicaciones de regresion: {error}"
        raise LoadError(msg) from error


def load_regression_explanations(path: Path | None = None) -> tuple[RegressionExplanation, ...]:
    """Las explicaciones de regresion versionadas.

    Un archivo ausente o roto se trata igual del lado de la compuerta: sin
    explicaciones validas, ninguna regresion cuenta como explicada (REL-U21.5,
    "el fallo es hacia el lado seguro"). Por eso esta funcion, a diferencia de
    las demas de este modulo, **no propaga** el error de carga: lo deja para
    que quien llama decida si bloquear o solo avisar.
    """
    archivo = path if path is not None else paths.regressions_path()
    if not archivo.is_file():
        return ()
    try:
        datos = _read_yaml(archivo)
        archivo_validado = RegressionExplanationsFile.model_validate(datos)
    except (LoadError, ValidationError):
        return ()
    return archivo_validado.explanations


# --- Etiquetas humanas (DS-7) ---------------------------------------------------


def load_labels(language: Locale, directory: Path | None = None) -> tuple[HumanLabel, ...]:
    """Las etiquetas de un idioma, o vacio si el archivo todavia no existe."""
    base = directory if directory is not None else paths.labels_dir()
    archivo = base / f"{language}.yaml"
    if not archivo.is_file():
        return ()
    datos = _read_yaml(archivo)
    try:
        archivo_validado = LabelsFile.model_validate(datos)
    except ValidationError as error:
        msg = f"'{archivo}' no valida su esquema de etiquetas: {error}"
        raise LoadError(msg) from error
    return archivo_validado.labels


def save_labels(
    language: Locale, labels: tuple[HumanLabel, ...], directory: Path | None = None
) -> Path:
    """Escribe el archivo de etiquetas de un idioma completo (se deja a medias
    y se retoma: la funcion siempre escribe el archivo entero, ordenado)."""
    base = directory if directory is not None else paths.labels_dir()
    base.mkdir(parents=True, exist_ok=True)
    archivo = base / f"{language}.yaml"
    ordenadas = tuple(sorted(labels, key=lambda e: (e.transcript_id, e.turn_index, e.criterion)))
    contenido = LabelsFile(language=language, labels=ordenadas).model_dump(mode="json")
    archivo.write_text(
        yaml.safe_dump(contenido, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return archivo


def load_labeling_queue(path: Path | None = None) -> tuple[LabelingQueueEntry, ...]:
    """La cola de turnos por etiquetar, o vacia si Miguel no la ha llenado."""
    archivo = path if path is not None else paths.labeling_queue_path()
    if not archivo.is_file():
        return ()
    datos = _read_yaml(archivo)
    try:
        archivo_validado = LabelingQueueFile.model_validate(datos)
    except ValidationError as error:
        msg = f"'{archivo}' no valida su esquema de cola de etiquetado: {error}"
        raise LoadError(msg) from error
    return archivo_validado.entries


def save_labeling_queue(entries: tuple[LabelingQueueEntry, ...], path: Path | None = None) -> Path:
    """Escribe la cola entera, en el orden dado (es el orden en que se etiqueta).

    Se escribe a un archivo temporal y se renombra: una cola a medias escrita no puede
    quedar en el sitio de la buena si algo interrumpe la escritura.
    """
    archivo = path if path is not None else paths.labeling_queue_path()
    archivo.parent.mkdir(parents=True, exist_ok=True)
    contenido = LabelingQueueFile(entries=entries).model_dump(mode="json", exclude_none=True)
    temporal = archivo.with_suffix(".yaml.tmp")
    temporal.write_text(
        yaml.safe_dump(contenido, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )
    os.replace(temporal, archivo)
    return archivo


# --- Veredictos grabados del juez ------------------------------------------------


def load_judge_verdicts(
    judge_model: str, rubric_version: str, directory: Path | None = None
) -> tuple[JudgeVerdictRecord, ...]:
    """Los veredictos grabados de una combinacion exacta de modelo y rubrica.

    Ausente es un archivo que nadie ha grabado todavia -- la calibracion real
    corre en la sesion local que tiene la clave (CG-U21-4) -- y no un error.
    """
    base = directory if directory is not None else paths.judge_verdicts_dir()
    archivo = base / f"{judge_model}-{rubric_version}.yaml"
    if not archivo.is_file():
        return ()
    datos = _read_yaml(archivo)
    try:
        archivo_validado = JudgeVerdictsFile.model_validate(datos)
    except ValidationError as error:
        msg = f"'{archivo}' no valida su esquema de veredictos del juez: {error}"
        raise LoadError(msg) from error
    return archivo_validado.verdicts


def validate_judge_verdicts_file(path: Path) -> None:
    """Comprueba la forma de un archivo de veredictos grabados (`schema:check`)."""
    datos = _read_yaml(path)
    try:
        JudgeVerdictsFile.model_validate(datos)
    except ValidationError as error:
        msg = f"'{path}' no valida su esquema de veredictos del juez: {error}"
        raise LoadError(msg) from error


# --- Calibraciones ---------------------------------------------------------------


def load_calibration(
    judge_model: str, rubric_version: str, directory: Path | None = None
) -> JudgeCalibration | None:
    """La calibracion de una combinacion exacta de modelo y rubrica (BR3.2).

    `None` cuando no existe: el que llama decide que hacer -- para la
    compuerta, "juez sin calibrar" (BR3.2); para `schema:check`, nada que
    validar.
    """
    base = directory if directory is not None else paths.calibrations_dir()
    archivo = base / f"{judge_model}-{rubric_version}.json"
    if not archivo.is_file():
        return None
    return load_calibration_file(archivo)


def load_calibration_file(path: Path) -> JudgeCalibration:
    """Una calibracion, validada contra su modelo. Nombra el archivo si falla."""
    datos = _read_json(path)
    try:
        return JudgeCalibration.model_validate(datos)
    except ValidationError as error:
        msg = f"la calibracion '{path}' no valida su esquema: {error}"
        raise LoadError(msg) from error


def save_calibration(calibration: JudgeCalibration, directory: Path | None = None) -> Path:
    """Escribe la calibracion con el nombre de su modelo y su rubrica."""
    base = directory if directory is not None else paths.calibrations_dir()
    base.mkdir(parents=True, exist_ok=True)
    archivo = base / f"{calibration.judge_model}-{calibration.rubric_version}.json"
    archivo.write_text(calibration.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return archivo
