"""Pruebas del corredor de evaluaciones (AC4.4.1 a AC4.4.6, REL-U1.1 a REL-U1.5).

**Ninguna llama a un proveedor.** El corredor descubre sus conductores por
registro, asi que cada prueba registra el suyo, que devuelve turnos fijos. Es lo
que permite probar el determinismo y el corte por cuota sin gastar nada: una
prueba que cuesta dinero es una prueba que se deja de correr.

El corte por cuota se prueba **inyectando** la respuesta del proveedor, nunca
llevando una clave real a su tope.
"""

from __future__ import annotations

import asyncio
import io
import json
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from untangle import observability
from untangle.base import Locale
from untangle.evals.gates.metrics import criterion_pass_rates
from untangle.evals.models import (
    CaseStatus,
    Channel,
    ChatTurnLatency,
    Dataset,
    GoldenCase,
    JudgmentKind,
    NotMeasuredCause,
    RootCause,
)
from untangle.evals.report import ByLanguage
from untangle.evals.runner import api, failures, runner
from untangle.settings import EVALS_MODEL_API_KEY_VAR, Settings

MANIFIESTO = """
datasets:
  - dataset: DS-1
    built: false
    reason: no aplica en esta prueba
  - dataset: DS-2
    count: {ds2}
    runs_per_delivery: true
  - dataset: DS-3
    built: false
    reason: no aplica en esta prueba
  - dataset: DS-4
    built: false
    reason: no aplica en esta prueba
  - dataset: DS-5
    built: false
    reason: no aplica en esta prueba
  - dataset: DS-6
    built: false
    reason: no aplica en esta prueba
  - dataset: DS-7
    built: false
    reason: no aplica en esta prueba
  - dataset: DS-8
    count: 0
"""

CASO = """
case_key: DS-2/{locale}/{seq}
dataset: DS-2
language: {locale}
channel: {channel}
tenant: stonecroft
requires_provider_key: {needs_key}
expected_verdicts:
  language_adherence: pass
"""

#: Un caso sin canal: un chequeo determinista, que no es una conversacion.
CASO_SIN_CANAL = """
case_key: DS-2/{locale}/{seq}
dataset: DS-2
language: {locale}
requires_provider_key: false
expected_verdicts:
  chequeo_de_prueba: pass
"""


class ConductorDePrueba:
    """Un conductor que devuelve turnos fijos y no llama a ningun proveedor."""

    channel: Channel = Channel.CHAT

    def __init__(
        self, fallos: dict[str, Exception] | None = None, canal: Channel = Channel.CHAT
    ) -> None:
        self.channel = canal
        self.fallos = fallos or {}
        self.ejecutados: list[str] = []
        self.intentos: dict[str, int] = {}

    async def run_case(self, case: GoldenCase) -> api.CaseTranscript:
        self.intentos[case.case_key] = self.intentos.get(case.case_key, 0) + 1
        self.ejecutados.append(case.case_key)
        fallo = self.fallos.get(case.case_key)
        if fallo is not None:
            raise fallo
        return api.CaseTranscript(
            case_key=case.case_key,
            verdicts={"language_adherence": "pass"},
            trace_ref=f"trace://{case.case_key}",
        )


def lectura_limpia(
    *, case: GoldenCase, transcript: api.CaseTranscript, root: Path
) -> api.CheckOutcome:
    """El criterio de la transcripcion, doblado: aqui no se prueba que lee, sino que el
    corredor se lo aplica a los casos con canal. Lo que lee vive en `test_transcript_guard.py`."""
    return api.CheckOutcome(passed=True)


@pytest.fixture(autouse=True)
def registros_limpios() -> Iterator[None]:
    api.reset()
    # Todo caso con canal los necesita registrados: sin ellos, el corredor lo deja en rojo.
    for criterio in api.REQUIRED_TRANSCRIPT_CHECKS:
        api.register_transcript_check(criterio, lectura_limpia)
    yield
    api.reset()


def construir_arbol(
    raiz: Path,
    *,
    casos: list[tuple[str, str, bool]],
    canal: str = "chat",
    plantilla: str = CASO,
) -> Path:
    """Un arbol con la forma del repositorio real, con los casos que se le pidan."""
    (raiz / "mise.toml").write_text("# arbol de prueba\n", encoding="utf-8")
    evals = raiz / "app" / "evals"
    (evals / "cases" / "ds2").mkdir(parents=True)
    (evals / "subsets").mkdir(parents=True)
    (evals / "manifest.yaml").write_text(MANIFIESTO.format(ds2=len(casos)), encoding="utf-8")

    claves: list[str] = []
    for locale, seq, needs_key in casos:
        (evals / "cases" / "ds2" / f"{locale}-{seq}.yaml").write_text(
            plantilla.format(
                locale=locale, seq=seq, needs_key=str(needs_key).lower(), channel=canal
            ),
            encoding="utf-8",
        )
        claves.append(f"DS-2/{locale}/{seq}")

    lista = "\n".join(f"  - {clave}" for clave in claves)
    (evals / "subsets" / "todos.yaml").write_text(
        f"name: todos\nreason: la lista completa de esta prueba\ncase_keys:\n{lista}\n",
        encoding="utf-8",
    )
    return raiz


def correr(raiz: Path, *, subset: str | None = "todos", **opciones: object) -> runner.RunOutcome:
    ajustes = Settings(**opciones)  # type: ignore[arg-type]
    return asyncio.run(runner.run_evaluation(subset=subset, settings=ajustes, root=raiz))


# --- Camino feliz -------------------------------------------------------------


def test_sin_la_variable_que_el_conjunto_no_necesita_la_corrida_es_normal(
    tmp_path: Path,
) -> None:
    raiz = construir_arbol(tmp_path, casos=[("es", "001", False), ("en", "001", False)])
    api.register_driver(ConductorDePrueba())

    resultado = correr(raiz, evals_model_api_key=None)

    # Detenerse cuando nada de lo seleccionado necesitaba la clave romperia la
    # meta de los 15 minutos para quien clona sin cuenta en ningun proveedor.
    assert resultado.exit_code == 0
    assert [r.status for r in resultado.run.results] == [CaseStatus.PASSED] * 2
    assert resultado.run.comparable is True


def test_dos_corridas_del_mismo_commit_ejecutan_los_mismos_casos_en_el_mismo_orden(
    tmp_path: Path,
) -> None:
    raiz = construir_arbol(
        tmp_path,
        casos=[("es", "003", False), ("en", "001", False), ("es", "002", False)],
    )

    primero = ConductorDePrueba()
    api.register_driver(primero)
    correr(raiz)

    api.reset()
    segundo = ConductorDePrueba()
    api.register_driver(segundo)
    correr(raiz)

    assert primero.ejecutados == segundo.ejecutados
    # Y el orden es el de la lista versionada, no el del sistema de archivos.
    assert primero.ejecutados == ["DS-2/es/003", "DS-2/en/001", "DS-2/es/002"]


# --- Casos de error y de borde ------------------------------------------------


def test_sin_la_variable_que_el_conjunto_necesita_corta_antes_de_la_primera_llamada(
    tmp_path: Path,
) -> None:
    raiz = construir_arbol(tmp_path, casos=[("es", "001", True), ("en", "001", True)])
    conductor = ConductorDePrueba()
    api.register_driver(conductor)

    with pytest.raises(runner.EnvironmentNotReadyError) as excinfo:
        correr(raiz, evals_model_api_key=None)

    assert EVALS_MODEL_API_KEY_VAR in str(excinfo.value)
    # Sin haber llamado a nadie: arrancar y fallar a mitad gasta cuota y deja
    # resultados parciales que parecen medidos.
    assert conductor.ejecutados == []


def test_un_caso_que_necesita_la_clave_queda_no_medido_con_su_causa(tmp_path: Path) -> None:
    raiz = construir_arbol(tmp_path, casos=[("es", "001", False), ("en", "001", True)])
    api.register_driver(ConductorDePrueba())

    resultado = correr(raiz, evals_model_api_key=None)

    por_clave = {r.case_key: r for r in resultado.run.results}
    assert por_clave["DS-2/es/001"].status is CaseStatus.PASSED
    assert por_clave["DS-2/en/001"].status is CaseStatus.NOT_MEASURED
    assert por_clave["DS-2/en/001"].not_measured_cause is NotMeasuredCause.PROVIDER_KEY_MISSING
    assert resultado.run.comparable is False
    # Un caso no medido no produce por si solo un codigo de fallo.
    assert resultado.exit_code == 0


def test_sin_backend_de_trazas_el_reporte_sale_con_los_enlaces_marcados(
    tmp_path: Path,
) -> None:
    raiz = construir_arbol(tmp_path, casos=[("es", "001", False)])
    api.register_driver(ConductorDePrueba())

    resultado = correr(raiz, traces_endpoint=None)

    assert resultado.report.header.traces_available is False
    fila = resultado.report.cases[0]
    # Marcado como no disponible, no vacio ni inventado.
    assert fila.trace_ref is None
    assert fila.trace_status == "unavailable"


def test_un_error_de_proveedor_deja_el_caso_no_medido_y_la_corrida_sigue(
    tmp_path: Path,
) -> None:
    raiz = construir_arbol(
        tmp_path, casos=[("es", "001", False), ("en", "001", False), ("es", "002", False)]
    )
    conductor = ConductorDePrueba(
        fallos={
            "DS-2/en/001": failures.ProviderError(
                failures.ProviderErrorKind.UNAVAILABLE, "503 del proveedor"
            )
        }
    )
    api.register_driver(conductor)

    resultado = correr(raiz)

    por_clave = {r.case_key: r for r in resultado.run.results}
    assert por_clave["DS-2/en/001"].status is CaseStatus.NOT_MEASURED
    assert por_clave["DS-2/en/001"].not_measured_cause is NotMeasuredCause.PROVIDER_UNAVAILABLE
    # La corrida sigue con el caso siguiente.
    assert por_clave["DS-2/es/002"].status is CaseStatus.PASSED
    # Y lo pasajero se reintenta una vez, no tres.
    assert conductor.intentos["DS-2/en/001"] == 2
    assert resultado.run.comparable is False


def test_tres_cuotas_agotadas_seguidas_abren_el_corte(tmp_path: Path) -> None:
    casos = [("es", f"00{n}", False) for n in range(1, 6)]
    raiz = construir_arbol(tmp_path, casos=casos)
    conductor = ConductorDePrueba(
        fallos={f"DS-2/es/00{n}": failures.QuotaExhaustedError("cuota agotada") for n in (1, 2, 3)}
    )
    api.register_driver(conductor)

    resultado = correr(raiz)

    estados = [r.not_measured_cause for r in resultado.run.results]
    assert all(causa is NotMeasuredCause.QUOTA_EXHAUSTED for causa in estados)
    # Al abrirse, los restantes quedan no medidos **sin ejecutarse**: recorrerlos
    # fallando uno por uno gasta tiempo y no anade informacion.
    assert conductor.ejecutados == ["DS-2/es/001", "DS-2/es/002", "DS-2/es/003"]
    # Y una cuota agotada no se reintenta: reintentarla gasta lo que se protege.
    assert conductor.intentos["DS-2/es/001"] == 1
    assert resultado.run.comparable is False


def test_un_caso_de_canal_sin_conductor_falla_como_caso_y_la_corrida_sigue(
    tmp_path: Path,
) -> None:
    """PASO 0.2 de la tanda 2 de U8: un canal sin conductor no tumba la corrida.

    Antes de este arreglo, `_execute` levantaba un `LookupError` a secas que
    `failures.classify` no sabia traducir, y la excepcion subia sin clasificar
    hasta reventar `run_evaluation` entera -- exactamente lo que le paso a
    DS-3 en cuanto sus 40 casos, todos de canal `chat`, se sumaron a la
    corrida sin que ningun conductor de chat estuviera registrado. Aqui no se
    registra ningun conductor a proposito.
    """
    raiz = construir_arbol(
        tmp_path, casos=[("es", "001", False), ("en", "001", False), ("es", "002", False)]
    )
    # A proposito: ningun conductor registrado para ningun canal.

    resultado = correr(raiz)

    por_clave = {r.case_key: r for r in resultado.run.results}
    # Los tres casos declaran `channel: chat` (ver CASO, arriba) y fallan como
    # caso, cada uno con su causa -- la corrida no se detiene en el primero.
    assert {r.status for r in resultado.run.results} == {CaseStatus.FAILED}
    assert por_clave["DS-2/es/001"].criteria_results == {"channel_driver": "fail"}
    assert por_clave["DS-2/en/001"].criteria_results == {"channel_driver": "fail"}
    assert por_clave["DS-2/es/002"].criteria_results == {"channel_driver": "fail"}
    # No es "no medida": es que la conducta todavia no esta construida, y eso
    # se reporta como fallo, no como un hueco de infraestructura.
    assert all(r.not_measured_cause is None for r in resultado.run.results)
    # Y todo caso fallido trae su causa raiz (U21, BR1.1). La de un conductor
    # ausente es `not_built`, el noveno valor: ninguno de los ocho del PRD dice
    # "la conducta no existe todavia", y marcarlo `infrastructure` contaria como
    # fallo del producto algo que no lo es (decision de Miguel del 2026-09-27).
    assert all(r.root_cause is RootCause.NOT_BUILT for r in resultado.run.results)
    assert resultado.run.comparable is True
    assert resultado.exit_code == 1


def test_el_reporte_muestra_los_dos_idiomas_sin_campo_donde_promediar(
    tmp_path: Path,
) -> None:
    raiz = construir_arbol(tmp_path, casos=[("es", "001", False), ("en", "001", False)])
    api.register_driver(
        ConductorDePrueba(
            fallos={
                "DS-2/en/001": failures.ProviderError(
                    failures.ProviderErrorKind.INVALID_RESPONSE, "respuesta sin veredicto"
                )
            }
        )
    )

    resultado = correr(raiz)

    assert resultado.report.totals.es.passed == 1
    assert resultado.report.totals.en.failed == 1
    # La estructura tiene el idioma como dimension, no como etiqueta: no existe
    # un tercer campo donde escribir un promedio combinado.
    assert set(ByLanguage.model_fields) == {"es", "en"}
    # Y un `invalid_response` es un fallo de calidad, no una falta de medicion:
    # el proveedor respondio, y lo que devolvio no sirve.
    assert resultado.run.comparable is True
    assert resultado.exit_code == 1
    # Todo criterio de esta corrida lo juzga codigo: el juez y la revision
    # humana llegan con U21 paso 6 (BR1.1).
    fila_es = next(f for f in resultado.report.cases if f.case_key == "DS-2/es/001")
    assert all(juicio == JudgmentKind.CODE for juicio in fila_es.criteria_judgment.values())


# --- Lo que la agente dijo se lee en todo caso con canal (2026-10-11) -----------------


def lectura_en_rojo(
    *, case: GoldenCase, transcript: api.CaseTranscript, root: Path
) -> api.CheckOutcome:
    return api.CheckOutcome(passed=False, detail="turno 3: amount (guard.es.amount.001)")


def eventos_de(salida: io.StringIO, nombre: str) -> list[dict[str, object]]:
    lineas = [json.loads(linea) for linea in salida.getvalue().splitlines() if linea.strip()]
    return [linea for linea in lineas if linea.get("event") == nombre]


@pytest.mark.parametrize("canal", list(Channel))
def test_todo_caso_de_cualquier_canal_recibe_el_criterio_de_la_transcripcion(
    tmp_path: Path, canal: Channel
) -> None:
    """Un conductor nuevo no puede olvidarlo: el corredor se lo aplica a su transcripcion.

    Recorre **todos** los valores de `Channel`, asi que un canal que se agregue manana
    entra a esta prueba sin que nadie la toque.
    """
    raiz = construir_arbol(tmp_path, casos=[("es", "001", False)], canal=canal.value)
    api.register_driver(ConductorDePrueba(canal=canal))

    resultado = correr(raiz)

    caso = resultado.run.results[0]
    assert caso.status is CaseStatus.PASSED
    assert caso.criteria_results == {
        "language_adherence": "pass",
        api.TRANSCRIPT_GUARD_CRITERION: "pass",
        api.TRANSCRIPT_PROMPTS_CRITERION: "pass",
    }


def test_el_criterio_de_la_transcripcion_en_rojo_pone_el_caso_en_rojo_y_deja_su_rastro(
    tmp_path: Path,
) -> None:
    raiz = construir_arbol(tmp_path, casos=[("es", "001", False), ("en", "001", False)])
    api.register_driver(ConductorDePrueba())
    api.register_transcript_check(api.TRANSCRIPT_GUARD_CRITERION, lectura_en_rojo)
    salida = io.StringIO()
    observability.set_stream(salida)
    try:
        resultado = correr(raiz)
    finally:
        observability.set_stream(sys.stdout)

    assert [r.status for r in resultado.run.results] == [CaseStatus.FAILED] * 2
    assert resultado.exit_code == 1
    # Lo que el caso pedia sigue aparte: el criterio nuevo se suma, no reemplaza.
    assert resultado.run.results[0].criteria_results == {
        "language_adherence": "pass",
        api.TRANSCRIPT_GUARD_CRITERION: "fail",
        api.TRANSCRIPT_PROMPTS_CRITERION: "pass",
    }
    fallos = eventos_de(salida, "evals.check_failed")
    assert {e["case_key"] for e in fallos} == {"DS-2/es/001", "DS-2/en/001"}
    assert all(e["criterion"] == api.TRANSCRIPT_GUARD_CRITERION for e in fallos)
    assert all(e["detail"] == "turno 3: amount (guard.es.amount.001)" for e in fallos)


def test_un_caso_con_canal_sin_el_criterio_registrado_falla_en_vez_de_pasar_sin_lectura(
    tmp_path: Path,
) -> None:
    """Sin quien lea lo dicho, la conversacion no pasa en silencio: sale en rojo."""
    raiz = construir_arbol(tmp_path, casos=[("es", "001", False)])
    api.reset()
    conductor = ConductorDePrueba()
    api.register_driver(conductor)

    resultado = correr(raiz)

    caso = resultado.run.results[0]
    assert caso.status is CaseStatus.FAILED
    assert caso.criteria_results == {api.TRANSCRIPT_GUARD_CRITERION: "fail"}
    assert caso.root_cause is RootCause.NOT_BUILT
    assert caso.not_measured_cause is None
    assert resultado.exit_code == 1


def test_si_falta_el_criterio_de_los_prompts_el_caso_tambien_sale_en_rojo(
    tmp_path: Path,
) -> None:
    """Cada criterio exigido se vigila por separado: con el de la guardia registrado, el
    que falta es el de los prompts y el caso lo dice por su nombre."""
    raiz = construir_arbol(tmp_path, casos=[("es", "001", False)])
    api.reset()
    api.register_transcript_check(api.TRANSCRIPT_GUARD_CRITERION, lectura_limpia)
    api.register_driver(ConductorDePrueba())

    resultado = correr(raiz)

    caso = resultado.run.results[0]
    assert caso.status is CaseStatus.FAILED
    assert caso.criteria_results == {api.TRANSCRIPT_PROMPTS_CRITERION: "fail"}
    assert caso.root_cause is RootCause.NOT_BUILT


def test_un_caso_sin_canal_no_recibe_el_criterio_de_la_transcripcion(tmp_path: Path) -> None:
    raiz = construir_arbol(
        tmp_path, casos=[("es", "001", False), ("en", "001", False)], plantilla=CASO_SIN_CANAL
    )
    llamadas: list[str] = []

    def no_debe_leerse(
        *, case: GoldenCase, transcript: api.CaseTranscript, root: Path
    ) -> api.CheckOutcome:
        llamadas.append(case.case_key)
        return api.CheckOutcome(passed=False, detail="no tenia que llamarse")

    api.register_transcript_check(api.TRANSCRIPT_GUARD_CRITERION, no_debe_leerse)
    api.register_check("chequeo_de_prueba", lambda *, language, root: api.CheckOutcome(passed=True))

    resultado = correr(raiz)

    assert [r.status for r in resultado.run.results] == [CaseStatus.PASSED] * 2
    assert all(r.criteria_results == {"chequeo_de_prueba": "pass"} for r in resultado.run.results)
    assert llamadas == []


def test_si_el_caso_ya_nombraba_el_criterio_el_rojo_de_cualquiera_de_los_dos_manda() -> None:
    caso = GoldenCase(
        case_key="DS-2/es/001",
        dataset=Dataset.DS_2,
        language="es",
        channel=Channel.CHAT,
        expected_verdicts={api.TRANSCRIPT_GUARD_CRITERION: "pass"},
    )
    transcripcion = api.CaseTranscript(
        case_key=caso.case_key, verdicts={api.TRANSCRIPT_GUARD_CRITERION: "pass"}
    )

    estado, criterios = runner._verdict_status(
        caso, transcripcion, {api.TRANSCRIPT_GUARD_CRITERION: "fail"}
    )

    assert estado is CaseStatus.FAILED
    assert criterios == {api.TRANSCRIPT_GUARD_CRITERION: "fail"}


def test_de_punta_a_punta_una_afirmacion_dicha_detiene_la_compuerta_y_llega_al_resumen(
    tmp_path: Path,
) -> None:
    """El recorrido entero con la guardia de verdad: lo que la agente dijo -> el criterio
    del corredor -> la compuerta dura -> el resumen de la ultima corrida."""
    import shutil

    from untangle import paths
    from untangle.evals import compliance_fixtures as fx
    from untangle.evals import transcript_guard, transcript_prompts
    from untangle.evals.gates.baseline import build_digest
    from untangle.evals.gates.gate import (
        GateSources,
        blocking_criteria_from_registry,
        run_gate,
    )

    raiz = construir_arbol(tmp_path, casos=[("es", "001", False), ("en", "001", False)])
    # La guardia lee sus patrones y las aseguradoras, y el otro criterio los prompts, del arbol
    # sobre el que corre.
    for carpeta in ("compliance", "tenants", "prompts"):
        shutil.copytree(
            paths.repo_root() / "app" / "config" / carpeta, raiz / "app" / "config" / carpeta
        )
    afirmacion = next(
        fila.text
        for fila in fx.load_fixtures("es", paths.repo_root()).guard
        if fila.expected_category is not None and fila.expected_category.value == "coverage_promise"
    )

    class ConductorQueAfirma(ConductorDePrueba):
        """La conversacion en espanol termina con una afirmacion de cobertura."""

        async def run_case(self, case: GoldenCase) -> api.CaseTranscript:
            dicho = afirmacion if case.language == "es" else "Anotado."
            return api.CaseTranscript(
                case_key=case.case_key,
                verdicts={"language_adherence": "pass"},
                turns=(api.Turn("agent", "Hola."), api.Turn("agent", dicho)),
            )

    api.reset()
    api.register_driver(ConductorQueAfirma())
    transcript_guard.register_transcript_guard()
    transcript_prompts.register_transcript_prompts()

    resultado = correr(raiz, subset=None)

    por_clave = {r.case_key: r for r in resultado.run.results}
    assert por_clave["DS-2/es/001"].status is CaseStatus.FAILED
    assert por_clave["DS-2/en/001"].status is CaseStatus.PASSED
    # Y la compuerta dura la detiene sin que ninguna explicacion la levante.
    bloqueantes = blocking_criteria_from_registry()
    assert api.TRANSCRIPT_GUARD_CRITERION in bloqueantes
    # Copiar los propios prompts es un hallazgo menor y no bloquea (2026-09-17).
    assert api.TRANSCRIPT_PROMPTS_CRITERION not in bloqueantes
    salida = run_gate(
        resultado.report,
        sources=GateSources(
            baselines_dir=tmp_path / "lineas-base",
            unstable_path=tmp_path / "inestables.yaml",
            regressions_path=tmp_path / "regresiones.yaml",
        ),
        blocking_criteria=bloqueantes,
    )
    assert salida.verdict.blocked is True
    assert salida.verdict.blocking_failures == ("DS-2/es/001",)
    # El resumen de la ultima corrida lo lleva como cualquier otro criterio.
    resumen = build_digest(resultado.report, blocking_criteria=bloqueantes)
    assert api.TRANSCRIPT_GUARD_CRITERION in resumen.blocking_criteria
    assert resumen.criteria_results["DS-2/es/001"][api.TRANSCRIPT_GUARD_CRITERION] == "fail"
    assert resumen.criteria_results["DS-2/en/001"][api.TRANSCRIPT_GUARD_CRITERION] == "pass"


# --- Las condiciones de la corrida que van a la cabecera (2026-10-11) ---------------


def test_la_huella_de_los_prompts_nombra_cada_prompt_versionado() -> None:
    """Un prompt cambiado sin cambiar el modelo mueve las cifras igual."""
    from untangle import paths
    from untangle.evals.runner import runner

    huellas = runner.prompt_hashes(paths.repo_root())

    assert "conversation.es" in huellas
    assert "conversation.en" in huellas
    assert not {"intake_reply.es", "intake_understanding.es"} & huellas.keys(), "se retiraron"
    assert "README" not in huellas
    assert all(len(huella) == 12 for huella in huellas.values())


def test_la_huella_cambia_cuando_cambia_el_prompt(tmp_path: Path) -> None:
    from untangle.evals.runner import runner

    carpeta = tmp_path / "app" / "config" / "prompts"
    carpeta.mkdir(parents=True)
    (carpeta / "uno.es.md").write_text("Anota lo que diga.", encoding="utf-8")
    antes = runner.prompt_hashes(tmp_path)
    (carpeta / "uno.es.md").write_text("Anota lo que diga, sin inferir.", encoding="utf-8")

    assert runner.prompt_hashes(tmp_path) != antes
    assert set(antes) == {"uno.es"}


def test_sin_git_el_arbol_se_declara_con_cambios(tmp_path: Path) -> None:
    """Una cifra que no se puede atar a un commit limpio no se presenta como si lo
    estuviera."""
    from untangle.evals.runner import runner

    assert runner.tree_is_dirty(tmp_path) is True


def test_los_modelos_y_los_prompts_de_la_corrida_llegan_a_la_cabecera(tmp_path: Path) -> None:
    """Sin ellos, un cambio de modelo o de prompt seria una regresion sin explicacion."""
    raiz = construir_arbol(tmp_path, casos=[("es", "001", False), ("en", "001", False)])
    prompts = raiz / "app" / "config" / "prompts"
    prompts.mkdir(parents=True, exist_ok=True)
    (prompts / "captura.es.md").write_text("Anota lo que diga.", encoding="utf-8")
    api.register_driver(ConductorDePrueba())

    resultado = asyncio.run(
        runner.run_evaluation(
            subset="todos",
            settings=Settings(evals_model_api_key=None),
            root=raiz,
            model_ids={"anthropic:generation": "claude-haiku-5-5"},
        )
    )

    assert resultado.report.header.model_ids == {"anthropic:generation": "claude-haiku-5-5"}
    assert set(resultado.report.header.prompt_hashes) == {"captura.es"}


def test_un_error_del_adaptador_de_verdad_se_clasifica_como_el_del_corredor() -> None:
    """Visto el 2026-10-11: un plazo vencido de Claude tumbo la corrida completa sin
    guardar nada. Las sondas levantan el error del adaptador, que no es la clase del
    corredor, y no se reconocia."""
    from untangle.base import ProviderErrorKind, ProviderName, Use
    from untangle.evals.runner import failures
    from untangle.providers.ports import ProviderError

    del_adaptador = ProviderError(
        ProviderErrorKind.TIMEOUT, provider=ProviderName.ANTHROPIC, use=Use.EVALS_CHAT, attempt=1
    )

    veredicto = failures.classify(del_adaptador)

    assert veredicto is not None, "sin clasificar, el corredor lo deja subir y la corrida muere"
    assert veredicto.transient is True
    assert veredicto.cause is NotMeasuredCause.PROVIDER_TIMEOUT


def test_un_error_cualquiera_con_un_campo_kind_no_se_toma_por_uno_de_proveedor() -> None:
    from untangle.evals.runner import failures

    class RaroError(Exception):
        kind = "otra cosa"

    assert failures.classify(RaroError()) is None


# --- El grabador de transcripciones -------------------------------------------


class GrabadorDePrueba:
    """Se queda con lo que el corredor le ofrece, sin guardar nada en disco."""

    def __init__(self, *, levanta: bool = False) -> None:
        self.levanta = levanta
        self.vistos: list[tuple[str, tuple[api.Turn, ...]]] = []

    def record(self, case: GoldenCase, transcript: api.CaseTranscript, root: Path) -> None:
        if self.levanta:
            msg = "el grabador esta roto a proposito"
            raise RuntimeError(msg)
        self.vistos.append((case.case_key, transcript.turns))


class ConductorConTurnos(ConductorDePrueba):
    """El mismo conductor, pero con una conversacion de dos turnos."""

    async def run_case(self, case: GoldenCase) -> api.CaseTranscript:
        base = await super().run_case(case)
        return api.CaseTranscript(
            case_key=base.case_key,
            verdicts=base.verdicts,
            turns=(
                api.Turn(speaker="agent", text="Hola"),
                api.Turn(speaker="insured", text="Tuve un choque", field_key="description"),
            ),
        )


def correr_con_grabador(raiz: Path, grabador: GrabadorDePrueba) -> runner.RunOutcome:
    return asyncio.run(
        runner.run_evaluation(subset="todos", settings=Settings(), root=raiz, recorder=grabador)
    )


def test_el_corredor_le_ofrece_al_grabador_la_transcripcion_de_cada_caso_con_canal(
    tmp_path: Path,
) -> None:
    raiz = construir_arbol(tmp_path, casos=[("es", "001", False), ("en", "001", False)])
    api.register_driver(ConductorConTurnos())
    grabador = GrabadorDePrueba()

    correr_con_grabador(raiz, grabador)

    assert [clave for clave, _ in grabador.vistos] == ["DS-2/es/001", "DS-2/en/001"]
    assert all(len(turnos) == 2 for _, turnos in grabador.vistos)


def test_un_caso_sin_canal_no_se_ofrece_al_grabador(tmp_path: Path) -> None:
    raiz = construir_arbol(tmp_path, casos=[("es", "001", False)], plantilla=CASO_SIN_CANAL)
    api.register_check("chequeo_de_prueba", lambda *, language, root: api.CheckOutcome(passed=True))
    grabador = GrabadorDePrueba()

    correr_con_grabador(raiz, grabador)

    assert grabador.vistos == []


def test_un_caso_que_no_se_pudo_conducir_no_llega_al_grabador(tmp_path: Path) -> None:
    """Una conversacion que no se pudo conducir no tiene transcripcion que guardar."""
    raiz = construir_arbol(tmp_path, casos=[("es", "001", False), ("en", "001", False)])
    api.register_driver(
        ConductorConTurnos(fallos={"DS-2/es/001": failures.QuotaExhaustedError("cuota agotada")})
    )
    grabador = GrabadorDePrueba()

    correr_con_grabador(raiz, grabador)

    # La cuota agotada no se reintenta: ese caso queda no medido y no se ofrece. Y la
    # cuota no abre el corte con un solo fallo, asi que el segundo si corre y se ofrece.
    assert [clave for clave, _ in grabador.vistos] == ["DS-2/en/001"]


def test_un_grabador_roto_no_tumba_una_corrida_que_cuesta_dinero(tmp_path: Path) -> None:
    raiz = construir_arbol(tmp_path, casos=[("es", "001", False), ("en", "001", False)])
    api.register_driver(ConductorConTurnos())
    salida = io.StringIO()
    observability.set_stream(salida)
    try:
        resultado = correr_con_grabador(raiz, GrabadorDePrueba(levanta=True))
    finally:
        observability.set_stream(sys.stdout)

    assert [r.status for r in resultado.run.results] == [CaseStatus.PASSED] * 2
    eventos = [json.loads(linea) for linea in salida.getvalue().splitlines() if linea.strip()]
    no_guardados = [e for e in eventos if e["event"] == "evals.transcript_not_saved"]
    assert [e["case_key"] for e in no_guardados] == ["DS-2/es/001", "DS-2/en/001"]
    # Y el evento nombra el tipo del error, no su mensaje ni nada de lo dicho.
    assert all(e["error"] == "RuntimeError" for e in no_guardados)


# --- La latencia del chat en el reporte -----------------------------------------------


class ConductorConLatencias(ConductorDePrueba):
    """El mismo conductor, con lo que la entrega midio de cada turno de la persona."""

    def __init__(self, por_caso: dict[str, tuple[ChatTurnLatency, ...]]) -> None:
        super().__init__()
        self.por_caso = por_caso

    async def run_case(self, case: GoldenCase) -> api.CaseTranscript:
        base = await super().run_case(case)
        return api.CaseTranscript(
            case_key=base.case_key,
            verdicts=base.verdicts,
            chat_latencies=self.por_caso.get(case.case_key, ()),
        )


def _turnos(idioma: Locale, tiempos: list[int]) -> tuple[ChatTurnLatency, ...]:
    return tuple(ChatTurnLatency(language=idioma, first_word_ms=t) for t in tiempos)


def test_el_reporte_trae_la_latencia_del_chat_por_el_idioma_en_que_se_atendio_cada_turno(
    tmp_path: Path,
) -> None:
    """Un caso en español que cambia de idioma a mitad (RT-10) no mezcla sus turnos: la
    latencia de un turno en ingles es del ingles."""
    raiz = construir_arbol(tmp_path, casos=[("es", "001", False), ("en", "001", False)])
    api.register_driver(
        ConductorConLatencias(
            {
                "DS-2/es/001": _turnos("es", [100] * 22) + _turnos("en", [800] * 3),
                "DS-2/en/001": _turnos("en", [900] * 20),
            }
        )
    )

    resultado = correr(raiz)

    chat = resultado.report.latencies[Channel.CHAT]
    assert (chat.es.turns, chat.es.p50_ms, chat.es.p95_ms) == (22, 100, 100)
    assert (chat.en.turns, chat.en.p50_ms, chat.en.p95_ms) == (23, 900, 900)
    assert chat.datasets == ("DS-2",)


def test_la_latencia_va_aparte_de_los_criterios_y_la_tasa_de_aciertos_no_la_lee(
    tmp_path: Path,
) -> None:
    raiz = construir_arbol(tmp_path, casos=[("es", "001", False)])
    api.register_driver(ConductorConLatencias({"DS-2/es/001": _turnos("es", [100] * 25)}))

    resultado = correr(raiz)

    assert resultado.report.latencies, "esta corrida midio la latencia"
    assert all("latenc" not in c.criterion for c in resultado.report.criteria)
    assert all("latenc" not in c for c in criterion_pass_rates(resultado.report))


def test_un_caso_que_converso_sin_ningun_turno_medido_deja_la_entrada_en_cero(
    tmp_path: Path,
) -> None:
    """«Se midieron cero turnos» es un dato, y no es lo mismo que una corrida que no converso."""
    raiz = construir_arbol(tmp_path, casos=[("es", "001", False)])
    api.register_driver(ConductorConLatencias({}))

    resultado = correr(raiz)

    chat = resultado.report.latencies[Channel.CHAT]
    assert (chat.es.turns, chat.en.turns) == (0, 0)
    assert chat.datasets == ()


def test_una_corrida_sin_ningun_caso_de_chat_no_deja_entrada_de_latencia(tmp_path: Path) -> None:
    raiz = construir_arbol(tmp_path, casos=[("es", "001", False)], plantilla=CASO_SIN_CANAL)
    api.register_check("chequeo_de_prueba", lambda *, language, root: api.CheckOutcome(passed=True))

    resultado = correr(raiz)

    assert resultado.report.latencies == {}


def test_los_turnos_de_un_caso_que_no_se_pudo_conducir_no_cuentan(tmp_path: Path) -> None:
    raiz = construir_arbol(tmp_path, casos=[("es", "001", False), ("en", "001", False)])
    conductor = ConductorConLatencias(
        {"DS-2/es/001": _turnos("es", [100] * 30), "DS-2/en/001": _turnos("en", [100] * 30)}
    )
    conductor.fallos = {"DS-2/en/001": failures.QuotaExhaustedError("cuota agotada")}
    api.register_driver(conductor)

    resultado = correr(raiz)

    chat = resultado.report.latencies[Channel.CHAT]
    assert (chat.es.turns, chat.en.turns) == (30, 0)
