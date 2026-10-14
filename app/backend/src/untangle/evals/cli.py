"""El comando unico que corre las evaluaciones (BR1.1, FR11.3).

Vive fuera de `runner/` a proposito: es el punto que **compone** el corredor con
los chequeos deterministas, y si viviera dentro, `runner` tendria que importar
`deterministic` y los dos modulos hermanos formarian un ciclo. El contrato
`acyclic_siblings` de `import-linter` lo detecta.

El archivo de tareas, el README y el flujo de GitHub Actions invocan **este**
comando. La tuberia que mantiene su propia lista de pasos es un fallo del
chequeo, no una variante aceptable.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from untangle import paths
from untangle.evals import (
    citation_probes,
    compliance_probes,
    content_checks,
    deterministic,
    inbox_probes,
    injection_probes,
    intake_probes,
    integration_probes,
    live_probes,
    loading,
    quote_probes,
    redaction_probes,
    rules_probes,
    transcript_guard,
    transcript_prompts,
    understanding_probes,
)
from untangle.evals.drivers import chat as chat_driver
from untangle.evals.latency_summary import MIN_TURNS_PER_LANGUAGE, LatencySummary
from untangle.evals.report import EvalReport
from untangle.evals.runner import runner
from untangle.settings import Settings


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="untangle-evals",
        description="Corre las evaluaciones y escribe el reporte.",
    )
    parser.add_argument(
        "--subset",
        default=None,
        help="Nombre del subconjunto declarado (por ejemplo `smoke`).",
    )
    parser.add_argument(
        "--out",
        default=None,
        type=Path,
        help="Donde escribir el reporte. Por defecto, tmp/evals/reports/.",
    )
    return parser


def write_report(report: EvalReport, destination: Path) -> Path:
    """Escribe el reporte como archivo, con su commit y su fecha.

    Como archivo y no en una base de datos: esa dependencia es exactamente la que
    convierte un fallo de infraestructura en un fallo de entrega. La tuberia lo
    publica como artefacto de la corrida (decision Q4 de observabilidad).
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        report.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return destination


def summarize(report: EvalReport) -> str:
    """Una linea por idioma. Nunca una sola cifra combinada."""
    cabecera = report.header
    lineas = [
        f"corrida {cabecera.run_id} sobre {cabecera.commit_sha[:12]}",
        (f"subconjunto: {cabecera.subset}" if cabecera.subset_declared else "corrida completa"),
        f"duracion: {cabecera.duration_seconds:.2f} s",
        f"trazas: {'disponibles' if cabecera.traces_available else 'no disponibles'}",
    ]
    if not cabecera.comparable:
        causa = cabecera.non_comparable_cause
        lineas.append(
            f"NO COMPARABLE contra la linea base: {causa.value if causa else 'sin causa'}"
        )
    for idioma, recuento in (("es", report.totals.es), ("en", report.totals.en)):
        lineas.append(
            f"  {idioma}: {recuento.passed} pasan, {recuento.failed} fallan, "
            f"{recuento.not_measured} no medidos"
        )
    for canal, latencia in report.latencies.items():
        for idioma, resumen in (("es", latencia.es), ("en", latencia.en)):
            lineas.append(f"  latencia del {canal.value}, {idioma}: {_latency_line(resumen)}")
    return "\n".join(lineas)


def _latency_line(resumen: LatencySummary) -> str:
    """p50 y p95 con su recuento; con pocos turnos lo dice, porque asi no se publica."""
    if resumen.p50_ms is None or resumen.p95_ms is None:
        return "ningun turno medido"
    cifra = f"p50 {resumen.p50_ms} ms, p95 {resumen.p95_ms} ms sobre {resumen.turns} turnos"
    if resumen.publishable:
        return cifra
    return f"{cifra} (menos de {MIN_TURNS_PER_LANGUAGE}: no se publica)"


def register_all_probes() -> None:
    """Registra todos los chequeos y sondas del corredor (Flujo 1, paso 0).

    Extraido de `main()` para que `evals:gate` y `evals:baseline` (U21) puedan
    componer el mismo corredor sin duplicar esta lista: el punto que compone
    sigue siendo uno solo, ahora con tres comandos que lo invocan.
    """
    # Los chequeos deterministas de U1 se registran antes de resolver los casos:
    # son los que hacen que el subconjunto de arranque tenga algo que correr sin
    # clave de ningun proveedor (CG-2).
    deterministic.register_builtin_checks()
    # Los tres criterios de U12 que mide una prueba de integracion, en otro proceso
    # para que el corredor siga sin base (`integration_probes.py`).
    integration_probes.register_integration_probes()
    # Las sondas contra el despliegue vivo: hoy, el escenario RT-4. Sin
    # despliegue al que apuntar sus casos quedan **no medidos** con su causa,
    # nunca omitidos y nunca en verde (NFR10.3).
    live_probes.register_live_probes()
    content_checks.register_content_checks()
    # Las sondas sembradas de la redaccion: RT-14 y RT-15. Necesitan los dos
    # modelos de spaCy instalados, y por eso viven fuera del subconjunto de
    # arranque, que sigue corriendo sin ellos (`mise run models:install`).
    redaction_probes.register_redaction_probes()
    # Las catorce sondas de los controles de cumplimiento (U10) y sus objetivos.
    # Se registran aqui y no en la raiz de composicion del proceso servido: el
    # codigo de produccion no importa el corredor (contrato
    # `produccion-sin-evals`), y este es el punto que compone el corredor. Son
    # de reglas, sin base de datos y sin modelos de lenguaje, y por eso sus casos
    # entran al subconjunto de arranque.
    compliance_probes.register_compliance_probes()
    # Las cuatro sondas del motor de reglas (U9). De reglas, sin base de datos y
    # sin modelo, igual que las de U10; hoy fallan las cuatro porque ninguna
    # aseguradora trae todavia `rules/triage.yaml` real (llega en el paso 6 de
    # esta unidad), y por eso quedan fuera del subconjunto de arranque hasta
    # el paso 8.
    rules_probes.register_rules_probes()
    # Las ocho sondas de la captura (U11). De reglas, sin base de datos y sin
    # modelo, igual que las de U9 y U10; hoy fallan las ocho porque el
    # mecanismo que decide el orden de las preguntas y compone el turno
    # (BR3.1 a BR5.4) llega en la tanda 2 de esa unidad, y por eso quedan
    # fuera del subconjunto de arranque hasta que esa tanda las vea pasar.
    intake_probes.register_intake_probes()
    # Las tres sondas de la bandeja (U14, tanda 4). Funciones puras sobre
    # escenarios estructurados, la configuracion de cada aseguradora y el catalogo
    # de textos: sin base de datos y sin modelo, igual que las de U9, U10 y U11, y
    # por eso sus casos si entran al subconjunto de arranque. Lo que esta unidad
    # prueba con base --el aislamiento, la decision y el enlace-- vive en sus
    # pruebas de integracion.
    inbox_probes.register_inbox_probes()
    # Las seis sondas de la cotizacion (U19, tanda 1). De reglas, sin base de datos y sin
    # modelo: el motor real de elegibilidad, las frases reales del catalogo y la guardia de
    # salida de verdad. Dos son compuerta dura (AC6.2.2, AC6.2.4). Lo que mide la cotizacion
    # contra un modelo vive en los casos de canal de DS-4, que declaran la clave y no entran
    # al subconjunto de arranque.
    quote_probes.register_quote_probes()
    # El conductor del canal chat (U13). A diferencia de todo lo de arriba, no es
    # una sonda sino el conductor de un canal: corre la conversacion entera por
    # donde de verdad ocurre --conversacion, limites, idioma, entrega al grafo y
    # transcripcion-- y por eso necesita base de datos y, para responder, la clave
    # del proveedor. Sus casos declaran las dos cosas y quedan fuera del
    # subconjunto de arranque, que sigue corriendo sin ninguna de las dos.
    chat_driver.register()
    # El criterio que lee lo que la agente dijo (`transcript_guard_clean`). No lo pide
    # ningun caso: el corredor se lo agrega a todo caso con canal, y sin esta linea una
    # conversacion saldria en rojo por no tener quien la lea. Es compuerta dura.
    transcript_guard.register_transcript_guard()
    # Su hermano: ningun turno de la agente copia un fragmento largo de sus prompts.
    transcript_prompts.register_transcript_prompts()
    # La comprension de un mensaje (fase 0, 2026-10-07). Sin quien entienda
    # instalado --lo instala `untangle.server.understanding_cli`-- sus casos quedan
    # no medidos con su causa.
    understanding_probes.register_understanding_probes(paths.repo_root())
    # Las citas de DS-3 (fase 1, 2026-10-08): las mide `mise run evals:citas`, que
    # instala quien responde; sin el, quedan no medidas con su causa.
    citation_probes.register_citation_probes(paths.repo_root())
    # RT-2 por clausula envenenada (2026-10-12): el modelo que propone las citas, con la
    # clausula del fixture entregada a mano y sin base. Lo instala `understanding_cli` en
    # `citas` y `completa`; sin el, el caso queda no medido con su causa.
    injection_probes.register_injection_probes()


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    register_all_probes()

    try:
        resultado = asyncio.run(runner.run_evaluation(subset=args.subset, settings=Settings()))
    except runner.EnvironmentNotReadyError as error:
        print(str(error), file=sys.stderr)
        return 2
    except loading.LoadError as error:
        print(str(error), file=sys.stderr)
        return 2

    destino = args.out or (paths.reports_dir() / f"{resultado.run.run_id}.json")
    escrito = write_report(resultado.report, destino)

    print(summarize(resultado.report))
    print(f"reporte: {escrito}")
    return resultado.exit_code


if __name__ == "__main__":
    sys.exit(main())
