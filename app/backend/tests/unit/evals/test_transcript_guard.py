"""Pruebas del criterio que lee lo que la agente dijo: `transcript_guard_clean`.

Sin modelo y sin base de datos. Las frases que la guardia detiene salen de **sus propias
frases de prueba** (`app/evals/fixtures/compliance/`) y no se escriben aqui: si el
criterio y la guardia dejaran de coincidir, estas pruebas lo ven.

Lo que no se prueba aqui: que el corredor se lo agregue a todo caso con canal, que vive
en `test_runner.py`, ni que el conductor de chat entregue el numero del caso, que
necesita la base y vive en `tests/integration/u13/test_eval_driver.py`.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from untangle import paths
from untangle.base import Locale
from untangle.compliance.controls import phrases
from untangle.compliance.controls.models import GuardCategory
from untangle.compliance.controls.phrases import EmergencyPhraseMode
from untangle.evals import cli as evals_cli
from untangle.evals import compliance_fixtures as fx
from untangle.evals import loading, transcript_guard
from untangle.evals.evidence.board import GateFamily, family_of
from untangle.evals.gates.gate import blocking_criteria_from_registry
from untangle.evals.models import Channel, Dataset, GoldenCase
from untangle.evals.runner import api
from untangle.tenancy import config as tenancy_config

RAIZ = paths.repo_root()
IDIOMAS: tuple[Locale, ...] = ("es", "en")


@pytest.fixture(autouse=True)
def registros_limpios() -> Iterator[None]:
    api.reset()
    yield
    api.reset()


def _caso(
    *, language: Locale = "es", tenant: str | None = "stonecroft", channel: Channel | None = None
) -> GoldenCase:
    return GoldenCase(
        case_key=f"DS-6/{language}/prueba-de-la-transcripcion",
        dataset=Dataset.DS_6,
        language=language,
        tenant=tenant,
        channel=Channel.CHAT if channel is None else channel,
    )


def _agente(texto: str) -> api.Turn:
    return api.Turn(speaker="agent", text=texto)


def _asegurado(texto: str) -> api.Turn:
    return api.Turn(speaker="insured", text=texto)


def _transcripcion(*turnos: api.Turn, case_number: str | None = None) -> api.CaseTranscript:
    return api.CaseTranscript(
        case_key="DS-6/es/prueba-de-la-transcripcion", turns=turnos, case_number=case_number
    )


def _leer(
    caso: GoldenCase, transcripcion: api.CaseTranscript, root: Path = RAIZ
) -> api.CheckOutcome:
    return transcript_guard.check_transcript(case=caso, transcript=transcripcion, root=root)


def _frase_que_la_guardia_detiene(
    idioma: Locale, categoria: GuardCategory = GuardCategory.COVERAGE_PROMISE
) -> str:
    """Una frase de las pruebas de la guardia que esta detiene por esa categoria."""
    escena = fx.load_scene(RAIZ)
    for fila in fx.load_fixtures(idioma, RAIZ).guard:
        if fila.expected_category is categoria:
            return fx.fill(fila.text, escena.markers())
    msg = f"las frases de prueba de '{idioma}' no traen ninguna de '{categoria.value}'"
    raise AssertionError(msg)


# --- La conducta ---------------------------------------------------------------


def test_una_transcripcion_limpia_pasa() -> None:
    resultado = _leer(
        _caso(),
        _transcripcion(
            _agente("Hola, soy la asistente de IA de la demostración. ¿Qué pasó?"),
            _asegurado("Me chocaron en la esquina."),
            _agente("Gracias. ¿Hubo heridos?"),
        ),
    )

    assert resultado.passed is True
    assert resultado.detail == ""


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_un_turno_de_la_agente_que_afirma_cobertura_pone_el_caso_en_rojo(idioma: Locale) -> None:
    frase = _frase_que_la_guardia_detiene(idioma)

    resultado = _leer(
        _caso(language=idioma),
        _transcripcion(
            _agente("Hola."),
            _asegurado("¿Me cubre el seguro?"),
            _agente(frase),
        ),
    )

    assert resultado.passed is False
    # El indice es el de la transcripcion entera, contando los turnos del asegurado.
    assert "turno 2" in resultado.detail
    assert GuardCategory.COVERAGE_PROMISE.value in resultado.detail


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_coincide_con_la_guardia_en_cada_frase_de_prueba(idioma: Locale) -> None:
    """Lo que la guardia detiene, el criterio lo ve; lo que deja salir, el criterio lo deja.

    Es la prueba de que no hay una lista de frases propia: las dos miden lo mismo porque
    son la misma pieza. Recorre **todas** las frases de la guardia, de las siete categorias.
    """
    escena = fx.load_scene(RAIZ)
    filas = fx.load_fixtures(idioma, RAIZ).guard
    categorias_vistas = {f.expected_category for f in filas if f.expected_category is not None}
    assert categorias_vistas == set(GuardCategory), "una categoria sin frase de prueba no se mide"

    for fila in filas:
        resultado = _leer(
            _caso(language=idioma, tenant=escena.current.tenant_id),
            _transcripcion(
                _agente(fx.fill(fila.text, escena.markers())),
                case_number=escena.current_case_number,
            ),
        )
        if fila.expected_category is None:
            assert resultado.passed, f"{fila.id}: la guardia la deja salir y el criterio no"
        else:
            assert not resultado.passed, f"{fila.id}: la guardia la detiene y el criterio no"
            assert fila.expected_category.value in resultado.detail, fila.id


def test_el_cambio_de_idioma_no_esconde_la_afirmacion() -> None:
    """RT-10: la persona pide en espanol, la agente cae en ingles y afirma cobertura."""
    resultado = _leer(
        _caso(language="es"),
        _transcripcion(
            _agente("Hola."),
            _asegurado("Does my policy cover this?"),
            _agente(_frase_que_la_guardia_detiene("en")),
        ),
    )

    assert resultado.passed is False
    assert GuardCategory.COVERAGE_PROMISE.value in resultado.detail


def test_lo_que_dice_el_asegurado_no_se_lee() -> None:
    """El asegurado puede decir cualquier cosa: lo que se mide es lo que la agente le dijo."""
    resultado = _leer(
        _caso(),
        _transcripcion(
            _agente("Hola."),
            _asegurado(_frase_que_la_guardia_detiene("es")),
            _agente("Anotado."),
        ),
    )

    assert resultado.passed is True


@pytest.mark.parametrize(
    "turnos",
    [
        (),
        (_asegurado("Me chocaron."),),
    ],
    ids=["transcripcion-vacia", "solo-el-asegurado"],
)
def test_sin_ningun_turno_de_la_agente_no_puede_pasar(turnos: tuple[api.Turn, ...]) -> None:
    resultado = _leer(_caso(), _transcripcion(*turnos))

    assert resultado.passed is False
    assert "ningun turno de la agente" in resultado.detail


def test_el_numero_del_propio_caso_no_se_toma_por_ajeno() -> None:
    """Por eso el conductor entrega el numero: sin el, decirlo seria revelar otro caso."""
    escena = fx.load_scene(RAIZ)
    caso = _caso(tenant=escena.current.tenant_id)
    dicho = _agente(f"Su número de caso es {escena.current_case_number}.")

    con_numero = _leer(caso, _transcripcion(dicho, case_number=escena.current_case_number))
    sin_numero = _leer(caso, _transcripcion(dicho))

    assert con_numero.passed is True
    assert sin_numero.passed is False
    assert GuardCategory.CONFIG_DISCLOSURE.value in sin_numero.detail


def test_el_detalle_nunca_lleva_el_texto_del_turno() -> None:
    """El reporte de evaluaciones es un punto de salida: no lleva contenido."""
    frase = _frase_que_la_guardia_detiene("es")
    marca = "Referencia X9Q7ZW"

    resultado = _leer(_caso(), _transcripcion(_agente(f"{frase} {marca}")))

    assert resultado.passed is False
    assert frase not in resultado.detail
    assert marca not in resultado.detail
    assert "X9Q7ZW" not in resultado.detail


def test_un_caso_sin_aseguradora_sale_en_rojo_y_no_en_verde() -> None:
    resultado = _leer(_caso(tenant=None), _transcripcion(_agente("Hola.")))

    assert resultado.passed is False
    assert "aseguradora" in resultado.detail


def test_si_la_guardia_no_se_puede_cargar_la_compuerta_sale_en_rojo(tmp_path: Path) -> None:
    """Una compuerta que no pudo leer nunca se da por verde ni tumba la corrida."""
    resultado = _leer(_caso(), _transcripcion(_agente("Hola.")), root=tmp_path)

    assert resultado.passed is False
    assert "no pudo leer" in resultado.detail


# --- Falsos positivos que pondrian en rojo una conducta correcta -----------------


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_lo_que_la_guardia_pone_en_su_lugar_no_dispara_el_criterio(idioma: Locale) -> None:
    """Si una intervencion correcta de la guardia dejara el caso en rojo, el criterio
    castigaria justo la conducta que protege."""
    sustitutos = [phrases.allowed_text(categoria, locale=idioma) for categoria in GuardCategory]
    sustitutos.append(phrases.degraded_text(locale=idioma))
    sustitutos.append(phrases.identity_answer_text(locale=idioma))
    sustitutos.extend(phrases.emergency_text(modo, locale=idioma) for modo in EmergencyPhraseMode)

    resultado = _leer(
        _caso(language=idioma), _transcripcion(*(_agente(texto) for texto in sustitutos))
    )

    assert resultado.passed is True, resultado.detail


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_la_apertura_de_cada_aseguradora_sale_limpia(idioma: Locale) -> None:
    from untangle.chat import opening

    aseguradoras = tenancy_config.load(RAIZ / "app" / "config" / "tenants").available
    assert aseguradoras, "sin aseguradoras la prueba no mide nada"
    for aseguradora in aseguradoras:
        texto = opening.compose(aseguradora, language=idioma).text

        resultado = _leer(
            _caso(language=idioma, tenant=aseguradora.tenant_id), _transcripcion(_agente(texto))
        )

        assert resultado.passed is True, f"{aseguradora.tenant_id}/{idioma}: {resultado.detail}"


# --- Que esta registrado y como -----------------------------------------------------


def test_el_registro_lo_declara_compuerta_dura_y_lo_ofrece_al_corredor() -> None:
    evals_cli.register_all_probes()

    assert api.TRANSCRIPT_GUARD_CRITERION in api.registered_transcript_checks()
    assert api.TRANSCRIPT_GUARD_CRITERION in blocking_criteria_from_registry()
    # Y el tablero lo cuenta en la familia de lo que la agente no puede prometer: sin
    # familia, una compuerta nueva no saldria en el.
    assert family_of(api.TRANSCRIPT_GUARD_CRITERION) is GateFamily.NO_PROMISES


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_rt10_corre_por_el_canal_y_por_eso_recibe_el_criterio(idioma: Locale) -> None:
    """El caso que prometia no afirmar cobertura al cambiar de idioma, ahora medido."""
    caso = loading.load_case(
        RAIZ / "app" / "evals" / "cases" / "ds6" / "rt10-language-switch" / f"{idioma}.yaml"
    )

    assert caso.channel is Channel.CHAT
    assert caso.expected_verdicts == {}, "el criterio es implicito: el caso no lo nombra"
