"""El corredor de evaluaciones: los ocho pasos del Flujo 1.

Un solo comando corre las evaluaciones, y el archivo de tareas, el README y el
flujo de integracion continua invocan exactamente ese comando (BR1.1).

**El corredor nunca invoca un modelo para producir las respuestas del
asegurado** (BR1.11): salen del guion versionado del caso. Y no llama a ningun
proveedor por su cuenta: quien llama, si acaso, es el conductor del canal. El
juez vive en U21.

Los casos se ejecutan **de uno en uno**. No es pereza: es lo que exige REL-U1.1,
que dos corridas del mismo commit ejecuten los mismos casos en el mismo orden, y
lo que hace que un corte por cuota agotada sea predecible.

**Lo que la agente dijo se lee aqui y no en cada conductor.** A todo caso con canal
el corredor le agrega, sin que el caso lo pida, los criterios de transcripcion
registrados (hoy `transcript_guard_clean`, compuerta dura): un conductor nuevo no
los puede olvidar porque nunca los calcula, y si el criterio no esta registrado el
caso sale en rojo en vez de pasar sin que nadie lo lea.
"""

from __future__ import annotations

import asyncio
import hashlib
import subprocess  # solo para leer el commit, con argumentos fijos y sin shell
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from untangle import observability, paths
from untangle.base import Locale
from untangle.evals import loading
from untangle.evals.latency_summary import ChannelLatency, channel_latency
from untangle.evals.models import (
    CaseResult,
    CaseStatus,
    Channel,
    EvalRun,
    GoldenCase,
    JudgmentKind,
    NonComparableCause,
    NotMeasuredCause,
    SubsetDefinition,
)
from untangle.evals.report import (
    ByLanguage,
    CaseRow,
    CriterionReport,
    EvalReport,
    LanguageTally,
    RunHeader,
)
from untangle.evals.runner import api, failures
from untangle.settings import EVALS_ANTHROPIC_API_KEY_VAR, EVALS_MODEL_API_KEY_VAR, Settings


class EnvironmentNotReadyError(Exception):
    """Falta una variable que el conjunto seleccionado necesita (BR1.2).

    Se levanta **antes** de ejecutar el primer caso y antes de construir ningun
    cliente de proveedor. Arrancar y fallar a mitad gasta cuota y deja
    resultados parciales que parecen medidos.
    """


@dataclass(frozen=True)
class RunOutcome:
    """Lo que devuelve una corrida: el registro, su reporte y el codigo."""

    run: EvalRun
    report: EvalReport
    exit_code: int


def current_commit(root: Path) -> str:
    """El commit sobre el que corre. Una cifra sin commit no es reproducible."""
    try:
        completado = subprocess.run(
            ["git", "rev-parse", "HEAD"],  # noqa: S607
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return completado.stdout.strip() or "unknown"


def tree_is_dirty(root: Path) -> bool:
    """Si habia cambios sin guardar al correr: el commit ya no describe lo medido.

    Sin git, o si no responde, se dice que si: una cifra que no se puede atar a un
    commit limpio no se presenta como si lo estuviera.
    """
    try:
        completado = subprocess.run(
            # Solo lo que se mide: el aplicativo. El registro del flujo de trabajo
            # cambia a cada rato y no mueve ninguna cifra.
            ["git", "status", "--porcelain", "--untracked-files=no", "--", "app"],  # noqa: S607
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return True
    return bool(completado.stdout.strip())


def prompt_hashes(root: Path) -> dict[str, str]:
    """La huella de cada prompt versionado: un prompt cambiado sin cambiar el
    modelo mueve las cifras igual, y sin esto no se veria en el reporte."""
    carpeta = root / "app" / "config" / "prompts"
    if not carpeta.is_dir():
        return {}
    return {
        archivo.stem: hashlib.sha256(archivo.read_bytes()).hexdigest()[:12]
        for archivo in sorted(carpeta.glob("*.md"))
        if archivo.stem != "README"
    }


def _required_variables(cases: tuple[GoldenCase, ...]) -> dict[str, tuple[str, ...]]:
    """Que variable necesita cada caso seleccionado.

    Se mira **lo que va a correr**, no la lista entera de variables posibles: es
    la enmienda del 2026-09-19 a BR1.2, y es lo que sostiene la meta de los 15
    minutos para quien clona sin cuenta en ningun proveedor.
    """
    por_variable: dict[str, tuple[str, ...]] = {}
    for caso in cases:
        if not caso.requires_provider_key:
            continue
        # La comprension de un mensaje, las citas y la clausula envenenada llaman a Claude
        # con su propia clave de evaluaciones (2026-10-07); el resto, al modelo del uso
        # `evals`.
        variable = (
            EVALS_ANTHROPIC_API_KEY_VAR
            if caso.understanding is not None
            or caso.citation is not None
            or caso.poisoned_clause is not None
            else EVALS_MODEL_API_KEY_VAR
        )
        por_variable[variable] = (*por_variable.get(variable, ()), caso.case_key)
    return por_variable


def validate_environment(cases: tuple[GoldenCase, ...], settings: Settings) -> frozenset[str]:
    """Paso 1 del Flujo 1. Devuelve los casos que quedaran sin medir.

    Tres situaciones, y las tres estan en REL-U1.4:

    - Falta la variable y **todos** los casos seleccionados la necesitan: se
      detiene nombrandola, sin haber llamado a nadie.
    - Falta y **ninguno** la necesita: corre con normalidad.
    - Falta y solo la necesitan **algunos**: esos quedan no medidos con
      `provider_key_missing`, y la corrida terminara no comparable.
    """
    presentes = {
        EVALS_MODEL_API_KEY_VAR: settings.evals_model_api_key,
        EVALS_ANTHROPIC_API_KEY_VAR: settings.anthropic_api_key_evals,
    }
    sin_medir: set[str] = set()

    for variable, dependientes in _required_variables(cases).items():
        if presentes.get(variable):
            continue
        if len(dependientes) == len(cases):
            msg = (
                f"falta la variable de entorno {variable}, que necesitan los "
                f"{len(dependientes)} casos seleccionados; la corrida se detiene "
                "sin llamar a ningun proveedor (BR1.2)"
            )
            raise EnvironmentNotReadyError(msg)
        sin_medir.update(dependientes)

    return frozenset(sin_medir)


async def _execute(case: GoldenCase, root: Path) -> api.CaseTranscript:
    """Ejecuta un caso por quien corresponda.

    Un caso con canal lo ejecuta el conductor de ese canal; uno sin canal es un
    chequeo determinista, que se resuelve sin llamar a ningun modelo (CG-2).
    """
    if case.channel is not None:
        conductor = api.driver_for(case.channel)
        if conductor is None:
            msg = (
                f"el caso '{case.case_key}' declara el canal "
                f"'{case.channel.value}' y no hay conductor registrado para el"
            )
            raise failures.ChannelDriverMissingError(msg)
        return await conductor.run_case(case)

    veredictos: dict[str, str] = {}
    for criterio in sorted(case.expected_verdicts):
        chequeo = api.check_for(criterio)
        asincrono = api.async_check_for(criterio)
        if chequeo is not None:
            resultado = chequeo(language=case.language, root=root)
        elif asincrono is not None:
            # La comprension de un mensaje (2026-10-07) llama a un modelo; corre en
            # el mismo bucle que el corredor y que su registro de gasto.
            resultado = await asincrono(language=case.language, root=root)
        else:
            msg = (
                f"el caso '{case.case_key}' nombra el criterio '{criterio}', que no esta registrado"
            )
            raise LookupError(msg)
        veredictos[criterio] = "pass" if resultado.passed else "fail"
        if not resultado.passed:
            observability.emit(
                "evals.check_failed",
                case_key=case.case_key,
                criterion=criterio,
                detail=resultado.detail,
            )
    return api.CaseTranscript(case_key=case.case_key, verdicts=veredictos)


def _implicit_verdicts(
    case: GoldenCase, transcript: api.CaseTranscript, root: Path
) -> dict[str, str]:
    """Los criterios que el corredor le agrega a todo caso con canal, sin que el caso los pida.

    Se calculan **aqui y no en cada conductor** a proposito: un conductor nuevo no puede
    olvidarlos en silencio, porque nunca los calcula. Un caso sin canal es un chequeo
    determinista, no una conversacion, y no los recibe.

    Los criterios exigidos (`api.REQUIRED_TRANSCRIPT_CHECKS`) tienen que estar registrados:
    sin ellos la conversacion pasaria sin que nadie la leyera, y eso se reporta como caso en
    rojo.
    """
    if case.channel is None:
        return {}

    registrados = api.registered_transcript_checks()
    for exigido in api.REQUIRED_TRANSCRIPT_CHECKS:
        if exigido not in registrados:
            msg = (
                f"el caso '{case.case_key}' corre por el canal '{case.channel.value}' y el "
                f"criterio '{exigido}' no esta registrado: nadie leeria lo que la agente dijo"
            )
            raise failures.TranscriptCheckMissingError(exigido, msg)

    veredictos: dict[str, str] = {}
    for criterio, chequeo in sorted(registrados.items()):
        resultado = chequeo(case=case, transcript=transcript, root=root)
        veredictos[criterio] = "pass" if resultado.passed else "fail"
        if not resultado.passed:
            observability.emit(
                "evals.check_failed",
                case_key=case.case_key,
                criterion=criterio,
                detail=resultado.detail,
            )
    return veredictos


def _verdict_status(
    case: GoldenCase,
    transcript: api.CaseTranscript,
    implicit: Mapping[str, str] | None = None,
) -> tuple[CaseStatus, dict[str, str]]:
    """Compara lo producido contra lo esperado (Flujo 2, paso 5).

    `implicit` son los criterios que el corredor agrega por su cuenta (`_implicit_verdicts`):
    cuentan igual que los del caso, y uno en rojo pone el caso en rojo. Si el caso ya
    nombraba el mismo criterio, el rojo de cualquiera de los dos manda.
    """
    resultados: dict[str, str] = {}
    fallo = False

    for criterio, esperado in sorted(case.expected_verdicts.items()):
        obtenido = transcript.verdicts.get(criterio)
        if obtenido is None:
            resultados[criterio] = "fail"
            fallo = True
            continue
        coincide = obtenido == esperado
        resultados[criterio] = "pass" if coincide else "fail"
        fallo = fallo or not coincide

    if case.expected_record and transcript.record != case.expected_record:
        resultados["expected_record"] = "fail"
        fallo = True
    elif case.expected_record:
        resultados["expected_record"] = "pass"

    for criterio, veredicto in sorted((implicit or {}).items()):
        if veredicto == "fail" or criterio not in resultados:
            resultados[criterio] = veredicto
        fallo = fallo or veredicto == "fail"

    return (CaseStatus.FAILED if fallo else CaseStatus.PASSED), resultados


async def _run_one(
    case: GoldenCase,
    *,
    run_id: str,
    root: Path,
    traces_available: bool,
    recorder: api.TranscriptRecorder | None = None,
) -> tuple[CaseResult, failures.Verdict | None]:
    """Un caso, con la capa 2 de la politica de fallo aplicada por el corredor.

    El caso no captura su propio fallo para seguir adelante: deja subir la
    excepcion y este ejecutor comun aplica la politica (convencion 8b).

    `recorder`, si se pasa, se queda con la transcripcion del caso que se midio (no con
    la de un intento que se reintenta): el reporte solo guarda veredictos, y lo que la
    agente dijo se perdia con la corrida.
    """
    empezo = time.monotonic()
    intento = 0

    while True:
        try:
            transcripcion = await _execute(case, root)
            implicitos = _implicit_verdicts(case, transcripcion, root)
        except Exception as error:
            veredicto = failures.classify(error)
            if veredicto is None:
                raise

            if veredicto.transient and intento < failures.REINTENTOS_PARA_LO_PASAJERO:
                intento += 1
                observability.emit(
                    "evals.retry",
                    case_key=case.case_key,
                    attempt=intento,
                    error=str(error),
                )
                await asyncio.sleep(failures.backoff_seconds(case.case_key, intento))
                continue

            duracion = time.monotonic() - empezo
            if veredicto.cause is None:
                # `failure_criterion` distingue el proveedor respondiendo con
                # algo que no sirve (fallo de calidad) de una conducta que
                # todavia no existe, como un canal sin conductor registrado
                # (PASO 0.2): las dos son "failed" y no "not_measured", pero
                # agruparlas bajo la misma clave le mentiria al reporte sobre
                # cual es la causa.
                observability.emit(
                    "evals.case_failed",
                    case_key=case.case_key,
                    criterion=veredicto.failure_criterion,
                    error=str(error),
                )
                return (
                    CaseResult(
                        result_id=f"{run_id}:{case.case_key}",
                        run_id=run_id,
                        case_key=case.case_key,
                        status=CaseStatus.FAILED,
                        criteria_results={veredicto.failure_criterion: "fail"},
                        root_cause=veredicto.root_cause,
                        duration_seconds=duracion,
                    ),
                    veredicto,
                )

            observability.emit(
                "evals.not_measured",
                case_key=case.case_key,
                cause=veredicto.cause.value,
                error=str(error),
            )
            return (
                CaseResult(
                    result_id=f"{run_id}:{case.case_key}",
                    run_id=run_id,
                    case_key=case.case_key,
                    status=CaseStatus.NOT_MEASURED,
                    not_measured_cause=veredicto.cause,
                    duration_seconds=duracion,
                ),
                veredicto,
            )

        if recorder is not None and case.channel is not None:
            try:
                recorder.record(case, transcripcion, root)
            except Exception as error:  # noqa: BLE001 -- una corrida con modelo cuesta dinero: no se pierde porque no se pudo guardar una transcripcion; se dice y sigue
                observability.emit(
                    "evals.transcript_not_saved",
                    case_key=case.case_key,
                    error=type(error).__name__,
                )

        estado, resultados = _verdict_status(case, transcripcion, implicitos)
        return (
            CaseResult(
                result_id=f"{run_id}:{case.case_key}",
                run_id=run_id,
                case_key=case.case_key,
                status=estado,
                criteria_results=resultados,
                off_script_turns=transcripcion.off_script_turns,
                duration_seconds=time.monotonic() - empezo,
                trace_ref=transcripcion.trace_ref if traces_available else None,
                chat_latencies=transcripcion.chat_latencies,
            ),
            None,
        )


def _not_measured(run_id: str, case: GoldenCase, cause: NotMeasuredCause) -> CaseResult:
    return CaseResult(
        result_id=f"{run_id}:{case.case_key}",
        run_id=run_id,
        case_key=case.case_key,
        status=CaseStatus.NOT_MEASURED,
        not_measured_cause=cause,
    )


def build_report(run: EvalRun, cases: tuple[GoldenCase, ...]) -> EvalReport:
    """Paso 7 del Flujo 1: por caso, por criterio y por idioma."""
    idioma_de = {caso.case_key: caso.language for caso in cases}

    filas = tuple(
        CaseRow(
            case_key=resultado.case_key,
            language=idioma_de.get(resultado.case_key, "es"),
            status=resultado.status,
            not_measured_cause=resultado.not_measured_cause,
            criteria_results=resultado.criteria_results,
            # Todo criterio de esta unidad lo juzga codigo (U21, BR1.1): el
            # juez y la revision humana no existen todavia (paso 6).
            criteria_judgment=dict.fromkeys(resultado.criteria_results, JudgmentKind.CODE),
            off_script_turns=resultado.off_script_turns,
            duration_seconds=resultado.duration_seconds,
            trace_ref=resultado.trace_ref,
            trace_status="available" if resultado.trace_ref else "unavailable",
            root_cause=resultado.root_cause,
        )
        for resultado in run.results
    )

    def recuento(idioma: Locale, filtro: tuple[str, ...] | None = None) -> LanguageTally:
        elegidas = [
            fila
            for fila in filas
            if fila.language == idioma
            and (filtro is None or any(c in fila.criteria_results for c in filtro))
        ]
        return LanguageTally(
            passed=sum(1 for f in elegidas if f.status is CaseStatus.PASSED),
            failed=sum(1 for f in elegidas if f.status is CaseStatus.FAILED),
            not_measured=sum(1 for f in elegidas if f.status is CaseStatus.NOT_MEASURED),
        )

    criterios = sorted({criterio for fila in filas for criterio in fila.criteria_results})

    return EvalReport(
        header=RunHeader(
            run_id=run.run_id,
            commit_sha=run.commit_sha,
            model_ids=run.model_ids,
            prompt_hashes=run.prompt_hashes,
            subset=run.subset,
            subset_declared=run.subset_declared,
            duration_seconds=run.duration_seconds,
            comparable=run.comparable,
            non_comparable_cause=run.non_comparable_cause,
            started_at=run.started_at,
            finished_at=run.finished_at,
            traces_available=run.traces_available,
        ),
        totals=ByLanguage(es=recuento("es"), en=recuento("en")),
        criteria=tuple(
            CriterionReport(
                criterion=criterio,
                by_language=ByLanguage(
                    es=recuento("es", (criterio,)),
                    en=recuento("en", (criterio,)),
                ),
            )
            for criterio in criterios
        ),
        cases=filas,
        latencies=_latencies(run, cases),
    )


def _latencies(run: EvalRun, cases: tuple[GoldenCase, ...]) -> dict[Channel, ChannelLatency]:
    """La latencia del chat de esta corrida, por idioma, o nada si la corrida no conversa.

    Hay entrada del chat cuando algun caso seleccionado conversa por el chat, tenga o no
    turnos medidos: «se midieron cero turnos» es un dato y el panel lo dice, mientras que
    una corrida sin ningun caso de chat (el subconjunto de arranque) no tiene nada que decir
    de esta latencia y no deja entrada. Los conjuntos son los de los casos que si aportaron
    turnos.
    """
    if not any(caso.channel is Channel.CHAT for caso in cases):
        return {}
    conjunto_de = {caso.case_key: caso.dataset.value for caso in cases}
    con_turnos = [r for r in run.results if r.chat_latencies]
    return {
        Channel.CHAT: channel_latency(
            turns=(turno for r in con_turnos for turno in r.chat_latencies),
            datasets=(conjunto_de[r.case_key] for r in con_turnos if r.case_key in conjunto_de),
        )
    }


async def run_evaluation(
    *,
    subset: str | None = None,
    settings: Settings | None = None,
    root: Path | None = None,
    model_ids: Mapping[str, str] | None = None,
    recorder: api.TranscriptRecorder | None = None,
) -> RunOutcome:
    """Los ocho pasos del Flujo 1, en orden.

    `model_ids` son los modelos con los que corre, por uso: los conoce quien arma
    los proveedores, no el corredor. Sin ellos la cabecera lo dice vacio.

    `recorder` recibe la transcripcion de cada caso con canal que se mide, para que
    quien corre las conversaciones pueda guardar lo que la agente dijo (ya redactado,
    por su cuenta). El corredor nunca escribe texto de una conversacion por si mismo.
    """
    base = root if root is not None else paths.repo_root()
    opciones = settings if settings is not None else Settings()

    # Paso 2 -- manifiesto y casos.
    manifiesto = loading.load_manifest(base / "app" / "evals" / "manifest.yaml")
    todos = loading.load_cases(base / "app" / "evals" / "cases")
    problemas = loading.check_manifest_counts(manifiesto, todos)
    if problemas:
        msg = "; ".join(problemas)
        raise loading.LoadError(msg)

    # Paso 3 -- que casos se corren.
    definicion: SubsetDefinition | None = None
    if subset is not None:
        definicion = loading.load_subset(subset, base / "app" / "evals" / "subsets")
        seleccionados = loading.resolve_subset_cases(definicion, todos)
    else:
        corren = {d.dataset for d in manifiesto.datasets if d.built and d.runs_per_delivery}
        seleccionados = tuple(caso for caso in todos if caso.dataset in corren)

    # Paso 1 -- el entorno, mirando lo que va a correr.
    sin_clave = validate_environment(seleccionados, opciones)

    # Paso 4 -- abrir la corrida.
    run_id = f"run-{uuid.uuid4().hex[:12]}"
    empezo_reloj = time.monotonic()
    empezo = datetime.now(UTC)
    observability.emit(
        "evals.run_started",
        run_id=run_id,
        subset=subset,
        cases=len(seleccionados),
        traces_available=opciones.traces_available,
    )

    # Paso 5 -- ejecutar cada caso, de uno en uno.
    breaker = failures.CircuitBreaker()
    resultados: list[CaseResult] = []
    cortados = False

    for indice, caso in enumerate(seleccionados):
        if breaker.is_open:
            cortados = True
            causa = breaker.cause or NotMeasuredCause.QUOTA_EXHAUSTED
            resultados.extend(_not_measured(run_id, c, causa) for c in seleccionados[indice:])
            break

        if caso.case_key in sin_clave:
            resultados.append(_not_measured(run_id, caso, NotMeasuredCause.PROVIDER_KEY_MISSING))
            breaker.record(None)
            continue

        resultado, veredicto = await _run_one(
            caso,
            run_id=run_id,
            root=base,
            traces_available=opciones.traces_available,
            recorder=recorder,
        )
        resultados.append(resultado)
        breaker.record(veredicto)

    if cortados:
        observability.emit("evals.circuit_open", run_id=run_id, cause=str(breaker.cause))

    # Paso 6 -- cerrar la corrida.
    termino = datetime.now(UTC)
    hay_sin_medir = any(r.status is CaseStatus.NOT_MEASURED for r in resultados)
    causa_no_comparable: NonComparableCause | None = None
    if hay_sin_medir:
        causa_no_comparable = (
            NonComparableCause.QUOTA_EXHAUSTED
            if breaker.is_open
            else NonComparableCause.NOT_MEASURED_CASES
        )

    corrida = EvalRun(
        run_id=run_id,
        commit_sha=current_commit(base),
        subset=subset,
        subset_declared=subset is not None,
        model_ids=dict(model_ids or {}),
        prompt_hashes=prompt_hashes(base),
        duration_seconds=time.monotonic() - empezo_reloj,
        comparable=not hay_sin_medir,
        non_comparable_cause=causa_no_comparable,
        started_at=empezo,
        finished_at=termino,
        results=tuple(resultados),
        traces_available=opciones.traces_available,
    )

    # Paso 7 -- el reporte.
    reporte = build_report(corrida, seleccionados)

    # Paso 8 -- el codigo de salida. Un caso no medido no produce por si solo un
    # codigo de fallo, pero si marca la corrida como no comparable. Quien bloquea
    # la entrega lo decide U21.
    hubo_fallos = any(r.status is CaseStatus.FAILED for r in resultados)
    observability.emit(
        "evals.run_finished",
        run_id=run_id,
        duration_seconds=round(corrida.duration_seconds, 3),
        comparable=corrida.comparable,
        failed=sum(1 for r in resultados if r.status is CaseStatus.FAILED),
        not_measured=sum(1 for r in resultados if r.status is CaseStatus.NOT_MEASURED),
    )

    return RunOutcome(run=corrida, report=reporte, exit_code=1 if hubo_fallos else 0)
