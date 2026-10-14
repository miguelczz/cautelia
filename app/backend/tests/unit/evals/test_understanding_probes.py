"""Las sondas de la comprension: que comparen lo que llegaria al caso, y que sin modelo
el caso quede no medido y nunca en verde.

Sin red: el puerto es un doble que devuelve lo que el modelo podria devolver. Lo que
se prueba es el juicio de la sonda, no al modelo.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from untangle import paths
from untangle.base import Locale
from untangle.evals import loading, understanding_probes
from untangle.evals.models import UnderstandingExpectation
from untangle.evals.runner import api as runner_api
from untangle.evals.runner.failures import TargetUnavailableError
from untangle.evals.runner.runner import _required_variables
from untangle.orchestration.nodes.intake.understanding import (
    Answer,
    UnderstandingRequest,
    UnderstandingResponse,
    UnderstoodItem,
    Want,
)
from untangle.settings import EVALS_ANTHROPIC_API_KEY_VAR, EVALS_MODEL_API_KEY_VAR

LICENCIA = UnderstandingExpectation(
    record_type="quote_request",
    captured=("driver_name", "driver_birth_date"),
    last_agent_text="¿Hace cuántos años tiene licencia de conducir?",
    message="Desde el 2022, recién cumplidos los 18 años, ¿cuántos años es eso?",
    wants=("continue",),
    items={"license_years": "4"},
    asks_question=True,
)


def _respuesta(*items: UnderstoodItem, **cambios: object) -> UnderstandingResponse:
    return UnderstandingResponse.model_validate(
        {
            "wants": Want.CONTINUE,
            "items": items,
            "person_question": "¿cuántos años es eso?",
            **cambios,
        }
    )


def test_cuatro_anios_pasa_y_dieciocho_falla() -> None:
    """E4, la captura de Miguel: el 18 que el texto trae no es la respuesta."""
    bien = _respuesta(UnderstoodItem(field_key="license_years", value="4"))
    mal = _respuesta(UnderstoodItem(field_key="license_years", value="18"))

    assert understanding_probes.evaluate(LICENCIA, bien, language="es") == []
    assert understanding_probes.evaluate(LICENCIA, mal, language="es") == [
        "'license_years' = '18', se esperaba '4'"
    ]


def test_compara_despues_de_la_normalizacion_del_codigo() -> None:
    """Lo que se mide es lo que llegaria al caso: «4 años» normaliza a 4."""
    respuesta = _respuesta(UnderstoodItem(field_key="license_years", value="4 años"))

    assert understanding_probes.evaluate(LICENCIA, respuesta, language="es") == []


def test_la_intencion_la_pregunta_y_la_respuesta_se_comprueban_cada_una() -> None:
    esperado = LICENCIA.model_copy(update={"answer": "yes"})
    respuesta = _respuesta(
        UnderstoodItem(field_key="license_years", value="4"),
        wants=Want.QUOTE,
        person_question=None,
        answer=Answer.NO,
    )

    fallos = understanding_probes.evaluate(esperado, respuesta, language="es")

    assert len(fallos) == 3
    assert any("intencion 'quote'" in f for f in fallos)
    assert any("respuesta 'no'" in f for f in fallos)
    assert any("pregunta de la persona" in f for f in fallos)


def test_un_dato_que_el_mensaje_no_dijo_falla() -> None:
    esperado = UnderstandingExpectation(
        message="Me rayaron el carro en el parqueadero",
        wants=("report_accident",),
        absent_items=("injuries",),
    )
    respuesta = UnderstandingResponse(
        wants=Want.REPORT_ACCIDENT,
        items=(UnderstoodItem(field_key="injuries", value="no"),),
    )

    fallos = understanding_probes.evaluate(esperado, respuesta, language="es")

    assert fallos == ["aparecio 'injuries' = 'no', que el mensaje no dijo"]


# --- `other_parties_denied`: quien dice que no hubo nadie mas ---------------------------------

#: Lo que el cierre directo lee como «no hubo terceros»: de la lista cerrada de
#: `other_parties_data_pending`, en los dos idiomas.
NEGACIONES_CLARAS: tuple[tuple[str, Locale], ...] = (
    ("ninguno", "es"),
    ("nadie más", "es"),
    ("no hubo otros vehículos", "es"),
    ("solo mi carro", "es"),
    ("none", "en"),
    ("nobody else", "en"),
)

#: Lo que NO es una negacion clara: nombra a alguien, o no se puede leer. El cierre directo
#: no ocurre con ninguno.
NO_SON_NEGACIONES: tuple[tuple[str, Locale], ...] = (
    ("un taxi que se fue", "es"),
    ("el otro conductor", "es"),
    ("no sé", "es"),
    ("ninguno, solo un poste", "es"),
    ("a taxi that drove off", "en"),
)


def _con_terceros(
    valor: str, *, espera_negacion: bool | None
) -> tuple[UnderstandingExpectation, UnderstandingResponse]:
    esperado = UnderstandingExpectation(
        message="me choqué contra un poste",
        wants=("report_accident",),
        other_parties_denied=espera_negacion,
    )
    respuesta = UnderstandingResponse(
        wants=Want.REPORT_ACCIDENT,
        items=(UnderstoodItem(field_key="other_parties", value=valor),),
    )
    return esperado, respuesta


@pytest.mark.parametrize(("valor", "idioma"), NEGACIONES_CLARAS)
def test_una_negacion_clara_cumple_lo_que_se_espera_de_quien_dijo_que_no_hubo_nadie(
    valor: str, idioma: Locale
) -> None:
    esperado, respuesta = _con_terceros(valor, espera_negacion=True)

    assert understanding_probes.evaluate(esperado, respuesta, language=idioma) == []


@pytest.mark.parametrize(("valor", "idioma"), NEGACIONES_CLARAS)
def test_una_negacion_clara_falla_si_la_persona_nombro_a_un_tercero(
    valor: str, idioma: Locale
) -> None:
    """El error caro: el modelo anota "ninguno" donde la persona nombro a alguien, y el caso
    se cerraria sin ajustador."""
    esperado, respuesta = _con_terceros(valor, espera_negacion=False)

    fallos = understanding_probes.evaluate(esperado, respuesta, language=idioma)

    assert fallos == [
        f"'other_parties' = {valor!r} es una negacion clara, y el mensaje nombra a alguien"
    ]


@pytest.mark.parametrize(("valor", "idioma"), NO_SON_NEGACIONES)
def test_un_tercero_nombrado_o_ilegible_cumple_lo_que_se_espera_de_quien_nombro_a_alguien(
    valor: str, idioma: Locale
) -> None:
    esperado, respuesta = _con_terceros(valor, espera_negacion=False)

    assert understanding_probes.evaluate(esperado, respuesta, language=idioma) == []


@pytest.mark.parametrize(("valor", "idioma"), NO_SON_NEGACIONES)
def test_lo_que_no_es_una_negacion_clara_falla_si_la_persona_dijo_que_no_hubo_nadie(
    valor: str, idioma: Locale
) -> None:
    """Sin esto el cierre directo no ocurriria nunca: el modelo escribe algo que la funcion
    del cierre no puede leer como «nadie mas»."""
    esperado, respuesta = _con_terceros(valor, espera_negacion=True)

    fallos = understanding_probes.evaluate(esperado, respuesta, language=idioma)

    assert fallos == [
        f"'other_parties' = {valor!r} no es una negacion clara, y el mensaje decia que no habia"
    ]


@pytest.mark.parametrize("espera_negacion", [True, False])
def test_si_other_parties_no_quedo_anotado_falla_lo_que_espera_una_negacion_o_un_tercero(
    espera_negacion: bool,
) -> None:
    esperado = UnderstandingExpectation(
        message="me choqué contra un poste, no había nadie más",
        wants=("report_accident",),
        other_parties_denied=espera_negacion,
    )
    respuesta = UnderstandingResponse(wants=Want.REPORT_ACCIDENT, items=())

    fallos = understanding_probes.evaluate(esperado, respuesta, language="es")

    assert len(fallos) == 1
    assert fallos[0].startswith("falta el campo 'other_parties'")


def test_sin_other_parties_denied_el_caso_no_mide_lo_que_se_dijo_de_los_demas() -> None:
    esperado, respuesta = _con_terceros("ninguno", espera_negacion=None)

    assert understanding_probes.evaluate(esperado, respuesta, language="es") == []


def test_lo_que_no_se_dijo_de_los_demas_se_mide_con_absent_items_y_no_con_la_negacion() -> None:
    """El primero de los tres casos: «ninguno» donde nadie dijo nada es un dato que el mensaje
    no dijo, y lo atrapa `absent_items` aunque la negacion sea clara."""
    esperado = UnderstandingExpectation(
        message="ayer se me dañó el carro en el parqueadero",
        wants=("report_accident",),
        absent_items=("other_parties",),
    )
    _, respuesta = _con_terceros("ninguno", espera_negacion=None)

    assert understanding_probes.evaluate(esperado, respuesta, language="es") == [
        "aparecio 'other_parties' = 'ninguno', que el mensaje no dijo"
    ]


CASOS_DE_TERCEROS = ("others-not-mentioned", "others-named", "others-denied")


def test_los_tres_casos_de_terceros_estan_escritos_en_los_dos_idiomas() -> None:
    casos = {c.case_key: c for c in loading.load_cases(paths.repo_root() / "app/evals/cases")}

    for idioma in ("es", "en"):
        no_dicho, nombrado, negado = (
            casos[f"DS-2/{idioma}/understand-{nombre}"].understanding
            for nombre in CASOS_DE_TERCEROS
        )
        assert no_dicho is not None
        assert no_dicho.absent_items == ("other_parties",)
        assert no_dicho.other_parties_denied is None, "no dijo nada: no hay negacion que medir"
        assert nombrado is not None
        assert nombrado.other_parties_denied is False
        assert negado is not None
        assert negado.other_parties_denied is True
        for nombre in CASOS_DE_TERCEROS:
            caso = casos[f"DS-2/{idioma}/understand-{nombre}"]
            criterio = understanding_probes.criterion_of(f"understand-{nombre}")
            assert caso.expected_verdicts == {criterio: "pass"}
            assert caso.requires_provider_key
            assert caso.tenant == "sunmeadow", "la aseguradora cuya primera regla cierra directo"


def test_los_casos_de_terceros_estan_en_el_subconjunto_entender_y_el_manifiesto_cuadra() -> None:
    raiz = paths.repo_root() / "app" / "evals"
    casos = loading.load_cases(raiz / "cases")
    entender = loading.load_subset("entender", raiz / "subsets")

    esperados = {
        f"DS-2/{idioma}/understand-{nombre}"
        for idioma in ("es", "en")
        for nombre in CASOS_DE_TERCEROS
    }
    assert esperados <= set(entender.case_keys)
    assert len(loading.resolve_subset_cases(entender, casos)) == len(entender.case_keys)
    assert loading.check_manifest_counts(loading.load_manifest(), casos) == ()
    assert loading.check_language_parity(casos) == ()


async def test_sin_modelo_instalado_el_caso_queda_no_medido() -> None:
    runner_api.reset()
    understanding_probes.install(None)
    understanding_probes.register_understanding_probes(paths.repo_root())
    sonda = runner_api.async_check_for("understanding_license_years_computed")
    assert sonda is not None

    with pytest.raises(TargetUnavailableError):
        await sonda(language="es", root=paths.repo_root())
    runner_api.reset()


async def test_con_el_modelo_instalado_corre_el_caso_de_su_archivo() -> None:
    """La sonda arma la peticion desde el archivo del caso: lo que falta sale del
    tipo de caso menos lo ya anotado."""
    vistas: list[UnderstandingRequest] = []

    async def entender(peticion: UnderstandingRequest) -> UnderstandingResponse:
        vistas.append(peticion)
        return _respuesta(UnderstoodItem(field_key="license_years", value="4"))

    runner_api.reset()
    understanding_probes.install(lambda: entender)
    understanding_probes.register_understanding_probes(paths.repo_root())
    sonda = runner_api.async_check_for("understanding_license_years_computed")
    assert sonda is not None

    resultado = await sonda(language="es", root=paths.repo_root())

    assert resultado.passed, resultado.detail
    [peticion] = vistas
    assert "license_years" in peticion.missing
    assert "driver_name" not in peticion.missing
    understanding_probes.install(None)
    runner_api.reset()


def test_cada_caso_de_comprension_pide_la_clave_de_claude_para_evaluaciones() -> None:
    casos = loading.load_cases(paths.repo_root() / Path("app/evals/cases"))
    de_comprension = tuple(c for c in casos if c.understanding is not None)
    otro = next(c for c in casos if c.requires_provider_key and c.understanding is None)

    variables = _required_variables((*de_comprension, otro))

    assert set(variables[EVALS_ANTHROPIC_API_KEY_VAR]) == {c.case_key for c in de_comprension}
    assert variables[EVALS_MODEL_API_KEY_VAR] == (otro.case_key,)
    assert len(de_comprension) == 58


# --- Quien conducia: el nombre completo se pregunta, se anota junto al carro y se puede leer ---

#: Los conductores que declara la poliza de los casos de abajo, el titular primero.
CONDUCTORES = ("Natalia Henao Rendón", "Mateo Henao Gómez")


def _del_conductor(valor: str) -> UnderstandingResponse:
    return UnderstandingResponse(
        wants=Want.CONTINUE,
        items=(UnderstoodItem(field_key="vehicle_and_driver", value=valor),),
    )


def _esperando_lectura(lectura: str | None) -> UnderstandingExpectation:
    return UnderstandingExpectation(
        record_type="claim",
        message="Se llama Carlos Ramírez Ospina, es mi hermano",
        wants=("continue",),
        declared_drivers=CONDUCTORES if lectura is not None else (),
        driver_reading=lectura,  # type: ignore[arg-type]
    )


@pytest.mark.parametrize(
    ("valor", "idioma", "lectura"),
    [
        # Nombre y apellido que la poliza no declara, pegados al verbo de conducir.
        ("Renault Logan. Manejaba su hermano Carlos Ramírez Ospina", "es", "unlisted"),
        ("Renault Logan. Driven by her brother Carlos Ramírez Ospina", "en", "unlisted"),
        # Otra persona sin nombre: la derivacion no lo puede leer, y no hay nombre inventado.
        ("Renault Logan. Manejaba su hijo", "es", "unknown"),
        ("Renault Logan. Driven by her son", "en", "unknown"),
        # Un conductor que la poliza si declara.
        ("Renault Logan. Manejaba Mateo Henao Gómez", "es", "listed"),
    ],
)
def test_la_lectura_del_conductor_es_la_de_la_derivacion(
    valor: str, idioma: Locale, lectura: str
) -> None:
    respuesta = _del_conductor(valor)

    assert (
        understanding_probes.evaluate(_esperando_lectura(lectura), respuesta, language=idioma) == []
    )
    otra = next(x for x in ("listed", "unlisted", "unknown") if x != lectura)
    fallos = understanding_probes.evaluate(_esperando_lectura(otra), respuesta, language=idioma)
    assert fallos == [
        f"'vehicle_and_driver' = {valor!r} se lee como '{lectura}', se esperaba '{otra}'"
    ]


def test_el_nombre_a_secas_no_se_lee_porque_le_falta_el_verbo() -> None:
    """El error probable: el modelo reemplaza el campo con solo el nombre. Sin un verbo de
    conducir pegado, la derivacion no lo lee."""
    respuesta = _del_conductor("Carlos Ramírez Ospina")

    assert understanding_probes.evaluate(
        _esperando_lectura("unlisted"), respuesta, language="es"
    ) == [
        "'vehicle_and_driver' = 'Carlos Ramírez Ospina' se lee como 'unknown', "
        "se esperaba 'unlisted'"
    ]


def test_un_nombre_inventado_donde_nadie_dijo_ninguno_no_pasa_por_desconocido() -> None:
    """Quien dijo «mi hijo» a secas y queda con nombre y apellido en el campo: el modelo lo
    invento, y la lectura ya no es `unknown`."""
    respuesta = _del_conductor("Renault Logan. Manejaba su hijo Carlos Ruiz Mora")

    fallos = understanding_probes.evaluate(_esperando_lectura("unknown"), respuesta, language="es")

    assert len(fallos) == 1
    assert "se lee como 'unlisted', se esperaba 'unknown'" in fallos[0]


def test_si_el_campo_del_conductor_no_quedo_anotado_falla_la_lectura() -> None:
    respuesta = UnderstandingResponse(wants=Want.CONTINUE, items=())

    fallos = understanding_probes.evaluate(_esperando_lectura("unlisted"), respuesta, language="es")

    assert fallos == ["falta el campo 'vehicle_and_driver' (el mensaje hablaba de quien conducia)"]


def test_sin_driver_reading_el_caso_no_mide_la_lectura_del_conductor() -> None:
    respuesta = _del_conductor("Carlos Ramírez Ospina")

    assert understanding_probes.evaluate(_esperando_lectura(None), respuesta, language="es") == []


@pytest.mark.parametrize(
    ("palabras", "respuesta", "pasa"),
    [
        (("nombre", "llama"), "¿Me dices el nombre completo de quien conducía?", True),
        (("nombre", "llama"), "¿Cómo se llama tu hijo?", True),
        (("name", "called"), "Could you tell me the full NAME of whoever was driving?", True),
        # Pregunta, pero no por el nombre.
        (("nombre", "llama"), "¿Cuándo y dónde pasó?", False),
        # Nombra el nombre, pero no pregunta.
        (("nombre", "llama"), "Anoté el nombre de quien conducía.", False),
        (("nombre", "llama"), "", False),
        (("nombre", "llama"), None, False),
        # Sin palabras el caso no mide la respuesta.
        ((), "¿Cuándo y dónde pasó?", True),
    ],
)
def test_la_respuesta_pregunta_por_lo_que_el_caso_espera(
    palabras: tuple[str, ...], respuesta: str | None, pasa: bool
) -> None:
    esperado = UnderstandingExpectation(
        message="Soy yo, pero manejaba mi hijo",
        wants=("continue",),
        reply_asks_for_any=palabras,
    )
    entendido = UnderstandingResponse(wants=Want.CONTINUE, reply=respuesta)

    fallos = understanding_probes.evaluate(esperado, entendido, language="es")

    assert (fallos == []) is pasa
    if not pasa:
        assert fallos == [f"la respuesta no pregunta por {list(palabras)}: {respuesta!r}"]


@pytest.mark.parametrize(
    ("palabras", "respuesta", "pasa"),
    [
        # Decir que falta, sin preguntarlo, es lo que la instruccion pide: cuenta.
        (("donde", "lugar"), "Todavía me falta el lugar. Puedes decírmelo ahora o después.", True),
        (("donde", "lugar"), "¿Me dices dónde fue?", True),
        (("donde", "lugar"), "Entendido, gracias.", False),
        (("donde", "lugar"), None, False),
        # Sin palabras el caso no mide la respuesta.
        ((), "Entendido, gracias.", True),
    ],
)
def test_la_respuesta_nombra_lo_que_el_caso_espera_sea_pregunta_o_no(
    palabras: tuple[str, ...], respuesta: str | None, pasa: bool
) -> None:
    esperado = UnderstandingExpectation(
        message="No, así está bien, eso es todo, gracias.",
        wants=("continue",),
        reply_mentions_any=palabras,
    )
    entendido = UnderstandingResponse(wants=Want.CONTINUE, reply=respuesta)

    fallos = understanding_probes.evaluate(esperado, entendido, language="es")

    assert (fallos == []) is pasa
    if not pasa:
        assert fallos == [f"la respuesta no nombra ninguna de {list(palabras)}: {respuesta!r}"]


@pytest.mark.parametrize(
    "cambios",
    [
        {"driver_reading": "unlisted"},
        {"declared_drivers": CONDUCTORES},
        {"captured": ("injuries",), "captured_values": {"vehicle_and_driver": "Renault Logan"}},
    ],
)
def test_una_expectativa_a_medias_no_se_acepta(cambios: dict[str, object]) -> None:
    """Cada una se lee contra la otra: sin conductores no hay contra que leer, y un valor de un
    dato que `captured` no lista nunca llegaria a la peticion."""
    with pytest.raises(ValueError, match=r"driver_reading|declared_drivers|captured_values"):
        UnderstandingExpectation(message="hola", wants=("greeting",), **cambios)  # type: ignore[arg-type]


def test_la_peticion_lleva_el_valor_de_lo_anotado_solo_donde_el_caso_lo_trae() -> None:
    esperado = UnderstandingExpectation(
        record_type="claim",
        captured=("injuries", "identity_and_policy", "vehicle_and_driver"),
        captured_values={"vehicle_and_driver": "Renault Logan. Manejaba su hermano"},
        message="Se llama Carlos Ramírez Ospina",
        wants=("continue",),
    )

    peticion = understanding_probes._peticion(esperado, tenant="stonecroft", language="es")

    assert {d.field_key: d.value for d in peticion.noted} == {
        "injuries": None,
        "identity_and_policy": None,
        "vehicle_and_driver": "Renault Logan. Manejaba su hermano",
    }
    assert "vehicle_and_driver" not in peticion.missing


CASOS_DEL_CONDUCTOR = ("other-driver-name-asked", "other-driver-name-given")


def _caso(nombre: str, idioma: Locale) -> UnderstandingExpectation:
    casos = {c.case_key: c for c in loading.load_cases(paths.repo_root() / "app/evals/cases")}
    esperado = casos[f"DS-2/{idioma}/understand-{nombre}"].understanding
    assert esperado is not None
    return esperado


def test_los_casos_del_conductor_estan_en_los_dos_idiomas_y_en_el_subconjunto() -> None:
    raiz = paths.repo_root() / "app" / "evals"
    casos = loading.load_cases(raiz / "cases")
    entender = loading.load_subset("entender", raiz / "subsets")

    esperados = {
        f"DS-2/{idioma}/understand-{nombre}"
        for idioma in ("es", "en")
        for nombre in CASOS_DEL_CONDUCTOR
    }
    por_clave = {c.case_key: c for c in casos}
    assert esperados <= set(entender.case_keys)
    assert esperados <= set(por_clave)
    for clave in esperados:
        caso = por_clave[clave]
        assert caso.requires_provider_key
        assert caso.expected_verdicts == {
            understanding_probes.criterion_of(clave.split("/")[-1]): "pass"
        }
    assert len(loading.resolve_subset_cases(entender, casos)) == len(entender.case_keys)
    assert loading.check_manifest_counts(loading.load_manifest(), casos) == ()
    assert loading.check_language_parity(casos) == ()


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_el_caso_de_preguntar_pasa_con_la_pregunta_y_falla_sin_ella_o_con_un_nombre_inventado(
    idioma: Locale,
) -> None:
    """Lo que un buen modelo contesta pasa, y las dos formas de fallar --seguir de largo sin
    preguntar, e inventar un nombre-- no."""
    esperado = _caso("other-driver-name-asked", idioma)
    anotado = "manejaba su hijo" if idioma == "es" else "driven by her son"
    pregunta = (
        "¿Me dices el nombre completo de quien conducía?"
        if idioma == "es"
        else "Can you tell me the full name of whoever was driving?"
    )
    bien = UnderstandingResponse(
        wants=Want.CONTINUE,
        answer=Answer.YES,
        items=(UnderstoodItem(field_key="vehicle_and_driver", value=anotado),),
        reply=pregunta,
    )
    de_largo = bien.model_copy(
        update={"reply": "¿Cuándo y dónde pasó?" if idioma == "es" else "When and where was it?"}
    )
    inventado = bien.model_copy(
        update={
            "items": (
                UnderstoodItem(field_key="vehicle_and_driver", value=f"{anotado} Carlos Ruiz Mora"),
            )
        }
    )

    assert understanding_probes.evaluate(esperado, bien, language=idioma) == []
    assert len(understanding_probes.evaluate(esperado, de_largo, language=idioma)) == 1
    assert any(
        "se lee como" in f
        for f in understanding_probes.evaluate(esperado, inventado, language=idioma)
    )


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_el_caso_del_nombre_dicho_pasa_con_el_valor_completo_y_falla_sin_el_carro_o_sin_el_verbo(
    idioma: Locale,
) -> None:
    esperado = _caso("other-driver-name-given", idioma)
    completo = (
        "Renault Logan. Manejaba su hermano Carlos Ramírez Ospina"
        if idioma == "es"
        else "Renault Logan. Driven by her brother Carlos Ramírez Ospina"
    )

    def _con(valor: str) -> UnderstandingResponse:
        return UnderstandingResponse(
            wants=Want.CONTINUE,
            items=(UnderstoodItem(field_key="vehicle_and_driver", value=valor),),
        )

    assert understanding_probes.evaluate(esperado, _con(completo), language=idioma) == []
    # Solo el nombre: pierde el carro y el verbo.
    solo_el_nombre = understanding_probes.evaluate(
        esperado, _con("Carlos Ramírez Ospina"), language=idioma
    )
    assert len(solo_el_nombre) == 2
    # El nombre con el verbo pero sin el carro que ya estaba.
    sin_carro = completo.removeprefix("Renault Logan. ")
    assert understanding_probes.evaluate(esperado, _con(sin_carro), language=idioma) == [
        f"'vehicle_and_driver' = {sin_carro!r}, no contiene 'Renault Logan'"
    ]


# --- Con el reporte a medias, la respuesta no lo da por hecho (2026-10-13) --------------------

CASOS_DEL_REPORTE_A_MEDIAS = ("done-with-data-missing", "whats-next-with-data-missing")

#: Lo que un buen modelo contesta a cada caso, por idioma.
BIEN_CONTESTADO = {
    ("done-with-data-missing", "es"): "Entiendo. Aún me falta saber dónde ocurrió. ¿Me lo cuentas?",
    ("done-with-data-missing", "en"): (
        "Understood. I still need to know where it happened. Can you tell me?"
    ),
    ("whats-next-with-data-missing", "es"): "Todavía me falta cuándo y dónde fue. ¿Me lo dices?",
    ("whats-next-with-data-missing", "en"): (
        "I still need to know when and where it happened. Can you tell me?"
    ),
}
#: Lo que contesto el modelo en la llamada simulada del 2026-10-13, y su equivalente en ingles.
PROMESA_FALSA = {
    "es": "De nada. Ya quedó anotado tu reporte; un ajustador lo revisará con tu póliza.",
    "en": "You're welcome. Your report is saved and an adjuster will review it.",
}


def test_los_casos_del_reporte_a_medias_estan_en_los_dos_idiomas_y_en_el_subconjunto() -> None:
    raiz = paths.repo_root() / "app" / "evals"
    casos = loading.load_cases(raiz / "cases")
    entender = loading.load_subset("entender", raiz / "subsets")

    esperados = {
        f"DS-2/{idioma}/understand-{nombre}"
        for idioma in ("es", "en")
        for nombre in CASOS_DEL_REPORTE_A_MEDIAS
    }
    por_clave = {c.case_key: c for c in casos}
    assert esperados <= set(entender.case_keys)
    assert esperados <= set(por_clave)
    for clave in esperados:
        caso = por_clave[clave]
        assert caso.requires_provider_key
        assert caso.expected_verdicts == {
            understanding_probes.criterion_of(clave.split("/")[-1]): "pass"
        }
        assert caso.understanding is not None
        assert caso.understanding.reply_claims_no_outcome is True
        assert caso.understanding.record_type == "claim"
    assert len(loading.resolve_subset_cases(entender, casos)) == len(entender.case_keys)
    assert loading.check_manifest_counts(loading.load_manifest(), casos) == ()
    assert loading.check_language_parity(casos) == ()


@pytest.mark.parametrize("nombre", CASOS_DEL_REPORTE_A_MEDIAS)
@pytest.mark.parametrize("idioma", ["es", "en"])
def test_el_caso_del_reporte_a_medias_pasa_con_lo_que_falta_y_falla_con_la_promesa_falsa(
    nombre: str, idioma: Locale
) -> None:
    """Lo que un buen modelo contesta pasa; la respuesta de la llamada simulada --que da el
    reporte por hecho y promete la revision-- falla, y el detalle dice que oracion fue."""
    esperado = _caso(nombre, idioma)

    def _con(reply: str | None) -> UnderstandingResponse:
        return UnderstandingResponse(wants=Want.CONTINUE, reply=reply)

    bien = _con(BIEN_CONTESTADO[nombre, idioma])
    assert understanding_probes.evaluate(esperado, bien, language=idioma) == []
    fallos = understanding_probes.evaluate(esperado, _con(PROMESA_FALSA[idioma]), language=idioma)
    assert any("da el reporte por hecho" in f for f in fallos), fallos
    # La promesa tambien incumple la otra mitad: no nombra lo que falta.
    assert any("no nombra ninguna de" in f for f in fallos), fallos


def test_sin_la_expectativa_la_respuesta_no_se_mide() -> None:
    sin_medir = UnderstandingExpectation(message="gracias", wants=("continue",))
    promesa = UnderstandingResponse(wants=Want.CONTINUE, reply=PROMESA_FALSA["es"])

    assert understanding_probes.evaluate(sin_medir, promesa, language="es") == []


def test_una_respuesta_vacia_no_afirma_nada() -> None:
    esperado = UnderstandingExpectation(
        message="gracias", wants=("continue",), reply_claims_no_outcome=True
    )

    for reply in (None, ""):
        sin_texto = UnderstandingResponse(wants=Want.CONTINUE, reply=reply)
        assert understanding_probes.evaluate(esperado, sin_texto, language="es") == []


def test_el_detalle_de_la_promesa_nombra_la_oracion_tal_como_se_escribio() -> None:
    esperado = UnderstandingExpectation(
        message="gracias", wants=("continue",), reply_claims_no_outcome=True
    )
    promesa = UnderstandingResponse(wants=Want.CONTINUE, reply=PROMESA_FALSA["es"])

    assert understanding_probes.evaluate(esperado, promesa, language="es") == [
        "la respuesta da el reporte por hecho o dice que lo revisa un ajustador: "
        "'Ya quedó anotado tu reporte'"
    ]
